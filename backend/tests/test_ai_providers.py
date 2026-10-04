import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.ai.providers import (
    AIProviderError,
    AIProviderInvalidOutputError,
    GeminiProvider,
    current_attempt_scope,
    get_ai_provider,
    provider_attempt_scope,
    _normalize_provider_error,
)
from app.config import Settings


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: str


class ConstrainedOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: str = Field(min_length=2, max_length=20, pattern=r"^[a-z]+$")
    labels: list[str] = Field(min_length=1, max_length=4)


def settings(**overrides) -> Settings:
    values = {
        "environment": "test",
        "database_url": "sqlite+aiosqlite:///:memory:",
        "secret_key": "test-only-secret-key-with-adequate-entropy-1234567890",
        "generation_source_encryption_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "flashcard_ai_api_key": "provider-secret",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class GeminiModels:
    def __init__(
        self,
        text='{"value":"ok"}',
        errors=None,
        cached_input_tokens=0,
        thought_tokens=0,
        finish_reason=None,
    ):
        self.text = text
        self.request = None
        self.requests = []
        self.errors = list(errors or [])
        self.cached_input_tokens = cached_input_tokens
        self.thought_tokens = thought_tokens
        self.finish_reason = finish_reason

    async def generate_content(self, **kwargs):
        self.request = kwargs
        self.requests.append(kwargs)
        if self.errors:
            raise self.errors.pop(0)
        return SimpleNamespace(
            text=self.text,
            usage_metadata=SimpleNamespace(
                prompt_token_count=11,
                candidates_token_count=7,
                cached_content_token_count=self.cached_input_tokens,
                thoughts_token_count=self.thought_tokens,
            ),
            candidates=[SimpleNamespace(finish_reason=self.finish_reason)] if self.finish_reason else [],
        )


def test_gemini_sdk_retry_layer_is_explicitly_disabled():
    provider = GeminiProvider(settings())

    assert provider._client._api_client._http_options.retry_options.attempts == 1


@pytest.mark.asyncio
async def test_attempt_scopes_isolate_concurrent_calls_on_one_provider():
    owner = object()

    async def measured(operation: str, attempts: int, wait: float):
        async with provider_attempt_scope(owner) as scope:
            for attempt in range(attempts):
                current = current_attempt_scope(owner)
                assert current is scope
                current.record_request(
                    operation,
                    retry=attempt > 0,
                    waited_seconds=wait if attempt == 0 else 0.0,
                )
                await asyncio.sleep(0)
            return scope.snapshot()

    first, second = await asyncio.gather(
        measured("first", 1, 0.25),
        measured("second", 3, 0.75),
    )

    assert (first.request_count, first.retry_count) == (1, 0)
    assert first.request_counts_by_stage == {"first": 1}
    assert first.rate_limit_wait_seconds == pytest.approx(0.25)
    assert (second.request_count, second.retry_count) == (3, 2)
    assert second.request_counts_by_stage == {"second": 3}
    assert second.rate_limit_wait_seconds == pytest.approx(0.75)


@pytest.mark.asyncio
@pytest.mark.parametrize("status,expected_attempts", [(429, 2), (404, 1)])
async def test_installed_gemini_sdk_wire_contract_has_one_retry_owner(
    monkeypatch, status, expected_attempts
):
    """Exercise the actual SDK with an in-memory transport, without provider calls."""
    from google import genai
    from google.genai import types

    attempts = []
    delays = []

    async def handler(request):
        attempts.append(request)
        payload = json.loads(request.content)
        assert payload["generationConfig"]["responseMimeType"] == "application/json"
        assert payload["generationConfig"]["responseJsonSchema"]["type"] == "object"
        if len(attempts) == 1:
            return httpx.Response(status, json={"error": {"code": status, "message": "synthetic failure"}})
        return httpx.Response(200, json={
            "candidates": [{"content": {"role": "model", "parts": [{"text": '{"value":"ok"}'}]}}],
            "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 7},
        })

    async def record_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("app.ai.providers.asyncio.sleep", record_sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        sdk = genai.Client(api_key="synthetic-test-only-key", http_options=types.HttpOptions(
            httpx_async_client=transport, retry_options=types.HttpRetryOptions(attempts=1)
        ))
        try:
            adapter = GeminiProvider(settings(), client=sdk)
            arguments = dict(response_model=Output, system_prompt="trusted synthetic instruction",
                             user_prompt="synthetic evidence", max_output_tokens=100, operation="sdk_contract")
            if status == 404:
                with pytest.raises(AIProviderError, match="selected model"):
                    await adapter.generate_structured(**arguments)
                assert delays == []
            else:
                response = await adapter.generate_structured(**arguments)
                assert response.data.value == "ok"
                assert response.usage.input_tokens == 11
                assert response.usage.output_tokens == 7
                assert delays == [3]
            assert len(attempts) == expected_attempts
            assert adapter.telemetry_snapshot().request_count == expected_attempts
        finally:
            await sdk.aio.aclose()
            sdk.close()


@pytest.mark.asyncio
async def test_gemini_adapter_uses_schema_system_boundary_and_usage():
    models = GeminiModels(cached_input_tokens=4)
    client = SimpleNamespace(aio=SimpleNamespace(models=models))
    response = await GeminiProvider(settings(), client=client).generate_structured(
        response_model=Output,
        system_prompt="system",
        user_prompt="untrusted document",
        max_output_tokens=100,
        operation="test",
    )

    assert response.data.value == "ok"
    assert response.usage.input_tokens == 11
    assert response.usage.output_tokens == 7
    assert response.usage.cached_input_tokens == 4
    assert models.request["config"]["system_instruction"] == "system"
    assert models.request["config"]["thinking_config"] == {"thinking_level": "low"}
    assert "temperature" not in models.request["config"]
    assert models.request["config"]["response_json_schema"] == {
        "type": "object",
        "properties": {"value": {"type": "string"}},
        "required": ["value"],
    }


@pytest.mark.asyncio
async def test_gemini_adapter_counts_billable_thinking_as_output_usage():
    models = GeminiModels(thought_tokens=13)
    client = SimpleNamespace(aio=SimpleNamespace(models=models))

    response = await GeminiProvider(settings(), client=client).generate_structured(
        response_model=Output,
        system_prompt="system",
        user_prompt="untrusted document",
        max_output_tokens=100,
        operation="thinking_usage",
    )

    assert response.usage.input_tokens == 11
    assert response.usage.output_tokens == 20
    assert response.usage.estimated is False


@pytest.mark.asyncio
async def test_gemini_adapter_uses_minimal_inline_schema():
    models = GeminiModels('{"value":"valid","labels":["one"]}')
    client = SimpleNamespace(aio=SimpleNamespace(models=models))

    await GeminiProvider(settings(), client=client).generate_structured(
        response_model=ConstrainedOutput,
        system_prompt="system",
        user_prompt="data",
        max_output_tokens=100,
        operation="schema subset",
    )

    schema = models.request["config"]["response_json_schema"]
    serialized = json.dumps(schema)
    assert schema == {
        "type": "object",
        "properties": {
            "value": {"type": "string"},
            "labels": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["value", "labels"],
    }
    assert "additionalProperties" not in serialized
    assert "$defs" not in serialized
    assert "$ref" not in serialized
    assert "minLength" not in serialized
    assert "maxLength" not in serialized
    assert "pattern" not in serialized


class ProviderHttpError(Exception):
    def __init__(self, status_code: int, *, retry_after=None, details=None):
        self.status_code = status_code
        self.response = (
            SimpleNamespace(headers={"Retry-After": str(retry_after)})
            if retry_after is not None
            else None
        )
        self.details = details


class RecordingReservation:
    def __init__(self, governor):
        self.governor = governor

    async def commit(self, actual_input_tokens):
        self.governor.commits.append(actual_input_tokens)


class RecordingGovernor:
    def __init__(self):
        self.admissions = []
        self.commits = []

    async def reserve(self, input_tokens, *, operation, attempt):
        self.admissions.append((input_tokens, operation, attempt))
        return RecordingReservation(self)


@pytest.mark.asyncio
async def test_permanent_provider_error_is_clear_and_not_retried():
    models = GeminiModels(errors=[ProviderHttpError(404)])
    client = SimpleNamespace(aio=SimpleNamespace(models=models))

    with pytest.raises(AIProviderError) as error:
        await GeminiProvider(settings(), client=client).generate_structured(
            response_model=Output,
            system_prompt="system",
            user_prompt="data",
            max_output_tokens=100,
            operation="model unavailable",
        )

    assert error.value.code == "ai_model_unavailable"
    assert error.value.retryable is False
    assert "selected model" in error.value.safe_message
    assert len(models.requests) == 1


@pytest.mark.asyncio
async def test_invalid_request_is_classified_as_model_compatibility_failure():
    models = GeminiModels(errors=[ProviderHttpError(400)])
    client = SimpleNamespace(aio=SimpleNamespace(models=models))

    with pytest.raises(AIProviderError) as error:
        await GeminiProvider(settings(), client=client).generate_structured(
            response_model=Output,
            system_prompt="system",
            user_prompt="data",
            max_output_tokens=100,
            operation="invalid schema",
        )

    assert error.value.code == "ai_provider_invalid_request"
    assert error.value.retryable is False
    assert "selected model" in error.value.safe_message
    assert len(models.requests) == 1


@pytest.mark.asyncio
async def test_rate_limit_retries_three_times_with_bounded_delays(monkeypatch):
    models = GeminiModels(errors=[ProviderHttpError(429)] * 4)
    client = SimpleNamespace(aio=SimpleNamespace(models=models))
    governor = RecordingGovernor()
    delays = []

    async def record_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("app.ai.providers.asyncio.sleep", record_sleep)
    provider = GeminiProvider(settings(), client=client, rate_governor=governor)
    with pytest.raises(AIProviderError) as error:
        await provider.generate_structured(
            response_model=Output,
            system_prompt="system",
            user_prompt="data",
            max_output_tokens=100,
            operation="rate limited",
        )

    assert error.value.code == "ai_provider_rate_limited"
    assert error.value.retryable is True
    assert len(models.requests) == 4
    assert delays == [3, 3, 3]
    assert [attempt for _, _, attempt in governor.admissions] == [0, 1, 2, 3]
    assert {operation for _, operation, _ in governor.admissions} == {"rate limited"}
    assert governor.commits == []
    telemetry = provider.telemetry_snapshot()
    assert telemetry.request_count == 4
    assert telemetry.retry_count == 3
    assert telemetry.rate_limit_wait_seconds == 9
    assert telemetry.request_counts_by_stage == {"rate limited": 4}


@pytest.mark.asyncio
async def test_retry_after_is_honored_and_success_reconciles_actual_usage(monkeypatch):
    models = GeminiModels(errors=[ProviderHttpError(429, retry_after=9)])
    client = SimpleNamespace(aio=SimpleNamespace(models=models))
    governor = RecordingGovernor()
    delays = []

    async def record_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("app.ai.providers.asyncio.sleep", record_sleep)
    provider = GeminiProvider(settings(), client=client, rate_governor=governor)
    response = await provider.generate_structured(
        response_model=Output,
        system_prompt="system boundary",
        user_prompt="untrusted document",
        max_output_tokens=100,
        operation="summary_map",
    )

    assert response.usage.input_tokens == 11
    assert delays == [9]
    assert [attempt for _, _, attempt in governor.admissions] == [0, 1]
    assert all(tokens > 0 for tokens, _, _ in governor.admissions)
    assert governor.commits == [11]
    telemetry = provider.telemetry_snapshot()
    assert telemetry.request_count == 2
    assert telemetry.retry_count == 1
    assert telemetry.rate_limit_wait_seconds == 9
    assert telemetry.request_counts_by_stage == {"summary_map": 2}


@pytest.mark.asyncio
async def test_retry_after_beyond_configured_max_stops_without_early_retry(monkeypatch):
    models = GeminiModels(errors=[ProviderHttpError(429, retry_after=31)])
    client = SimpleNamespace(aio=SimpleNamespace(models=models))
    governor = RecordingGovernor()
    delays = []

    async def record_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("app.ai.providers.asyncio.sleep", record_sleep)
    with pytest.raises(AIProviderError) as error:
        await GeminiProvider(
            settings(flashcard_ai_retry_max_seconds=30),
            client=client,
            rate_governor=governor,
        ).generate_structured(
            response_model=Output,
            system_prompt="system",
            user_prompt="data",
            max_output_tokens=100,
            operation="rate limited",
        )

    assert error.value.code == "ai_provider_rate_limited"
    assert error.value.retryable is True
    assert len(models.requests) == 1
    assert len(governor.admissions) == 1
    assert delays == []


def test_legacy_text_provider_is_rejected_before_new_work():
    with pytest.raises(ValidationError, match="flashcard_ai_provider"):
        settings(flashcard_ai_provider="openai_compatible")
    bypassed = settings().model_copy(update={"flashcard_ai_provider": "openai_compatible"})
    with pytest.raises(AIProviderError, match="not supported"):
        get_ai_provider(bypassed)


@pytest.mark.asyncio
async def test_answer_profile_is_independent_of_flashcard_model_key_and_card_controls():
    configured = settings(
        flashcard_ai_provider="gemini", flashcard_ai_model="gemini-3.8-flash",
        flashcard_ai_api_key="flashcard-secret", flashcard_ai_cards_per_request=17,
        rag_enabled=True, rag_ai_provider_enabled=True, rag_ai_provider="gemini",
        rag_ai_model="gemini-3.5-flash", rag_ai_api_key="answer-secret",
        rag_ai_max_output_tokens=128,
        rag_ai_requests_per_minute=2, rag_ai_input_tokens_per_minute=100_000,
        rag_ai_quota_bucket="test-answer-account",
    )
    profile = configured.text_provider_profile("rag_answer")
    assert not hasattr(profile, "cards_per_request")
    assert "answer-secret" not in repr(profile)
    assert "flashcard-secret" not in repr(profile)
    assert profile.model == "gemini-3.5-flash"
    models = GeminiModels('{"value":"answer"}')
    adapter = GeminiProvider(
        configured, client=SimpleNamespace(aio=SimpleNamespace(models=models)), role="rag_answer"
    )
    response = await adapter.generate_structured(
        response_model=Output, system_prompt="trusted", user_prompt="untrusted",
        max_output_tokens=512, operation="answer_test",
    )
    assert response.data.value == "answer"
    assert adapter.profile.api_key_value == "answer-secret"
    assert models.request["model"] == "gemini-3.5-flash"
    assert models.request["config"]["max_output_tokens"] == 128
    assert adapter.rate_governor.requests_per_window == 1  # 2 RPM * 80% safety


@pytest.mark.asyncio
async def test_native_gemini_answer_profile_uses_rag_role_model_key_and_limits():
    models = GeminiModels('{"value":"grounded"}')
    configured = settings(
        flashcard_ai_provider="gemini",
        flashcard_ai_model="gemini-3.8-flash",
        flashcard_ai_api_key="flashcard-secret",
        rag_enabled=True,
        rag_ai_provider_enabled=True,
        rag_ai_provider="gemini",
        rag_ai_model="gemini-3.5-flash",
        rag_ai_api_key="answer-secret",
        rag_ai_base_url=None,
        rag_ai_max_output_tokens=128,
        rag_ai_requests_per_minute=2,
        rag_ai_input_tokens_per_minute=100_000,
        rag_ai_quota_bucket="test-answer-account",
    )
    client = SimpleNamespace(aio=SimpleNamespace(models=models))
    adapter = GeminiProvider(configured, client=client, role="rag_answer")
    response = await adapter.generate_structured(
        response_model=Output,
        system_prompt="trusted answer policy",
        user_prompt="untrusted evidence",
        max_output_tokens=512,
        operation="answer_test",
    )

    assert response.data.value == "grounded"
    assert adapter.profile.api_key_value == "answer-secret"
    assert adapter.profile.model == "gemini-3.5-flash"
    assert models.request["model"] == "gemini-3.5-flash"
    assert models.request["config"]["system_instruction"] == "trusted answer policy"
    assert models.request["config"]["max_output_tokens"] == 128
    assert models.request["config"]["thinking_config"] == {"thinking_level": "minimal"}
    assert "temperature" not in models.request["config"]
    assert adapter.rate_governor.requests_per_window == 1

    created = get_ai_provider(configured, role="rag_answer")
    try:
        assert isinstance(created, GeminiProvider)
        assert created._client._api_client._http_options.retry_options.attempts == 1
    finally:
        await created._client.aio.aclose()
        created._client.close()


@pytest.mark.asyncio
async def test_provider_rejects_extra_structured_fields():
    models = GeminiModels('{"value":"ok","extra":"rejected"}')
    client = SimpleNamespace(aio=SimpleNamespace(models=models))
    with pytest.raises(AIProviderInvalidOutputError):
        await GeminiProvider(settings(), client=client).generate_structured(
            response_model=Output,
            system_prompt="system",
            user_prompt="data",
            max_output_tokens=100,
            operation="test",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text_value,finish_reason,expected_reason",
    [
        ("", "STOP", "output_empty"),
        ("{broken", "STOP", "json_invalid"),
        ('{"value": 9}', "STOP", "schema_invalid"),
        ('{"value":"ok"}', "MAX_TOKENS", "output_unfinished"),
        ('{"value":"ok"}', "SAFETY", "output_blocked"),
    ],
)
async def test_invalid_gemini_output_retains_safe_finish_and_billable_usage(
    text_value, finish_reason, expected_reason
):
    models = GeminiModels(
        text_value, thought_tokens=3,
        finish_reason=SimpleNamespace(name=finish_reason),
    )
    adapter = GeminiProvider(
        settings(rag_enabled=True, rag_ai_provider_enabled=True,
                 rag_ai_api_key="test-answer-key", rag_ai_quota_bucket="test-answer"),
        client=SimpleNamespace(aio=SimpleNamespace(models=models)),
        role="rag_answer",
    )
    with pytest.raises(AIProviderInvalidOutputError) as rejected:
        await adapter.generate_structured(
            response_model=Output, system_prompt="trusted", user_prompt="private fixture",
            max_output_tokens=100, operation="rag_answer",
        )
    error = rejected.value
    assert error.code == "invalid_ai_output"
    assert error.reason_code == expected_reason
    assert error.finish_reason == finish_reason
    assert error.usage is not None
    assert (error.usage.input_tokens, error.usage.output_tokens) == (11, 10)
    assert error.usage.estimated is False
    assert len(models.requests) == 1
    assert (await adapter.rate_governor.snapshot()).actual_input_tokens == 11
    assert "private fixture" not in str(error)


def test_provider_failure_subreasons_distinguish_transport_http_and_unknown_sdk():
    request = httpx.Request("POST", "https://example.test/generate")
    network = _normalize_provider_error(httpx.ConnectError("synthetic", request=request))
    server = _normalize_provider_error(httpx.HTTPStatusError(
        "synthetic", request=request,
        response=httpx.Response(503, request=request),
    ))
    unknown = _normalize_provider_error(RuntimeError("synthetic SDK failure"))
    assert (network.code, network.reason_code) == ("ai_provider_unavailable", "transport_network")
    assert (server.code, server.reason_code) == ("ai_provider_unavailable", "http_server_error")
    assert (unknown.code, unknown.reason_code) == ("ai_provider_unavailable", "sdk_unclassified")


def test_ai_configuration_matrix_and_secret_repr():
    with pytest.raises(ValidationError):
        settings(flashcard_ai_provider="openai_compatible", flashcard_ai_base_url=None)
    with pytest.raises(ValidationError):
        settings(flashcard_ai_input_cost_per_million_usd="1", flashcard_ai_output_cost_per_million_usd="0")
    with pytest.raises(ValidationError):
        settings(flashcard_ai_base_url="https://user:password@example.com/v1")
    with pytest.raises(ValidationError):
        settings(flashcard_ai_provider_max_retries=4)
    with pytest.raises(ValidationError):
        settings(flashcard_ai_retry_base_seconds=2)
    configured = settings()
    assert "provider-secret" not in repr(configured)
    assert configured.flashcard_ai_pricing_configured is False
