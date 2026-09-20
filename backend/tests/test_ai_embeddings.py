import json
import math
from types import SimpleNamespace

import httpx
import pytest

from app.ai.embeddings import (
    GeminiEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
    get_embedding_provider,
)
from app.ai.providers import AIProviderError
from app.config import Settings


def settings(**overrides) -> Settings:
    values = {
        "environment": "test",
        "database_url": "sqlite+aiosqlite:///:memory:",
        "secret_key": "test-only-secret-key-with-adequate-entropy-1234567890",
        "generation_source_encryption_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "rag_enabled": True,
        "rag_embedding_provider_enabled": True,
        "rag_embedding_api_key": "embedding-secret",
        "rag_embedding_quota_bucket": "test-project",
        "rag_embedding_provider_max_retries": 0,
        "rag_embedding_provider": "openai_compatible",
        "rag_embedding_model": "text-embedding-3-small",
        "rag_embedding_base_url": "https://api.openai.com/v1",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def vector(seed: float = 1.0) -> list[float]:
    return [seed, *([0.0] * 1535)]


async def test_embedding_wire_contract_and_usage_are_strict_and_content_free():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "object": "list",
                "model": "text-embedding-3-small",
                "data": [
                    {"object": "embedding", "index": 0, "embedding": vector(1.0)},
                    {"object": "embedding", "index": 1, "embedding": vector(2.0)},
                ],
                "usage": {"prompt_tokens": 17, "total_tokens": 17},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleEmbeddingProvider(settings(), client=client)
        result = await provider.embed_documents(("first", "second"))

    assert len(result.vectors) == 2
    assert all(len(item) == 1536 for item in result.vectors)
    assert result.usage.input_tokens == 17 and not result.usage.estimated
    assert captured["authorization"] == "Bearer embedding-secret"
    assert captured["body"] == {
        "model": "text-embedding-3-small",
        "input": ["first", "second"],
        "encoding_format": "float",
        "dimensions": 1536,
    }


async def test_embedding_provider_rejects_reordered_or_zero_vectors_without_retry():
    attempts = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            200,
            json={
                "model": "text-embedding-3-small",
                "data": [{"index": 1, "embedding": [0.0] * 1536}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleEmbeddingProvider(settings(), client=client)
        with pytest.raises(AIProviderError, match="invalid vector order") as failure:
            await provider.embed_query("query")
    assert failure.value.code == "invalid_embedding_output"
    assert attempts == 1


def test_index_worker_configuration_requires_embedding_role_credentials_only():
    configured = settings()
    assert configured.require_rag_index_worker_config() is configured
    with pytest.raises(ValueError, match="RAG_EMBEDDING_API_KEY"):
        settings(rag_embedding_api_key=None).require_rag_index_worker_config()


class GeminiModels:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    async def embed_content(self, **kwargs):
        self.requests.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return SimpleNamespace(
            embeddings=[SimpleNamespace(values=item) for item in response]
        )


class ProviderHttpError(Exception):
    def __init__(self, status_code: int, *, details=None):
        self.status_code = status_code
        self.details = details


def gemini_settings(**overrides) -> Settings:
    return settings(
        rag_embedding_provider="gemini",
        rag_embedding_model="gemini-embedding-001",
        rag_embedding_base_url=None,
        **overrides,
    )


async def test_gemini_embedding_tasks_preserve_order_and_normalize_reduced_vectors():
    first = [3.0, 4.0, *([0.0] * 1534)]
    second = [0.0, 12.0, 5.0, *([0.0] * 1533)]
    query = [8.0, 15.0, *([0.0] * 1534)]
    models = GeminiModels(((first, second), (query,)))
    provider = GeminiEmbeddingProvider(
        gemini_settings(), client=SimpleNamespace(aio=SimpleNamespace(models=models))
    )

    documents = await provider.embed_documents(("first", "second"))
    question = await provider.embed_query("question")

    assert models.requests[0]["model"] == "gemini-embedding-001"
    assert models.requests[0]["contents"] == ["first", "second"]
    assert models.requests[0]["config"] == {
        "task_type": "RETRIEVAL_DOCUMENT",
        "output_dimensionality": 1536,
    }
    assert models.requests[1]["config"]["task_type"] == "QUESTION_ANSWERING"
    assert documents.vectors[0][0:2] == pytest.approx((0.6, 0.8))
    assert documents.vectors[1][1:3] == pytest.approx((12 / 13, 5 / 13))
    assert question.vectors[0][0:2] == pytest.approx((8 / 17, 15 / 17))
    assert all(math.isclose(math.sqrt(math.fsum(value * value for value in vector)), 1.0, rel_tol=1e-6)
               for vector in (*documents.vectors, *question.vectors))
    assert documents.usage.estimated and question.usage.estimated
    assert provider.telemetry_snapshot().request_counts_by_stage == {
        "embedding_documents": 1,
        "embedding_query": 1,
    }


@pytest.mark.parametrize(
    "response",
    [
        (),
        ([float("nan"), *([0.0] * 1535)],),
        ([0.0] * 1536,),
        ([1.0] * 1535,),
    ],
)
async def test_gemini_embedding_rejects_count_nonfinite_zero_and_dimension_errors(response):
    models = GeminiModels((response,))
    provider = GeminiEmbeddingProvider(
        gemini_settings(), client=SimpleNamespace(aio=SimpleNamespace(models=models))
    )
    with pytest.raises(AIProviderError) as failure:
        await provider.embed_query("question")
    assert failure.value.code == "invalid_embedding_output"
    assert len(models.requests) == 1


async def test_gemini_embedding_has_one_application_retry_owner(monkeypatch):
    models = GeminiModels(
        (
            ProviderHttpError(429, details={"retryDelay": "9s"}),
            (vector(),),
        )
    )
    delays = []

    async def record_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("app.ai.embeddings.asyncio.sleep", record_sleep)
    provider = GeminiEmbeddingProvider(
        gemini_settings(
            rag_embedding_provider_max_retries=1,
            rag_embedding_retry_max_seconds=10,
        ),
        client=SimpleNamespace(aio=SimpleNamespace(models=models)),
    )

    result = await provider.embed_query("question")

    assert len(result.vectors) == 1
    assert delays == [9]
    assert len(models.requests) == 2
    telemetry = provider.telemetry_snapshot()
    assert telemetry.request_count == 2
    assert telemetry.retry_count == 1
    assert telemetry.rate_limit_wait_seconds == pytest.approx(9, abs=0.01)


def test_gemini_embedding_factory_and_sdk_disable_internal_retries():
    provider = get_embedding_provider(gemini_settings())
    try:
        assert isinstance(provider, GeminiEmbeddingProvider)
        assert provider._client._api_client._http_options.retry_options.attempts == 1
    finally:
        provider._client.close()


async def test_installed_gemini_embedding_sdk_uses_bounded_batch_wire_contract():
    from google import genai
    from google.genai import types

    captured = {}

    async def handler(request):
        captured["url"] = str(request.url)
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"embeddings": [{"values": vector()}, {"values": vector(2.0)}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        sdk = genai.Client(
            api_key="synthetic-test-only-key",
            http_options=types.HttpOptions(
                httpx_async_client=transport,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        try:
            provider = GeminiEmbeddingProvider(gemini_settings(), client=sdk)
            result = await provider.embed_documents(("first", "second"))
            assert len(result.vectors) == 2
        finally:
            await sdk.aio.aclose()
            sdk.close()

    assert captured["url"].endswith(
        "/models/gemini-embedding-001:batchEmbedContents"
    )
    requests = captured["payload"]["requests"]
    assert [item["content"]["parts"][0]["text"] for item in requests] == [
        "first",
        "second",
    ]
    assert all(item["taskType"] == "RETRIEVAL_DOCUMENT" for item in requests)
    assert all(item["outputDimensionality"] == 1536 for item in requests)
