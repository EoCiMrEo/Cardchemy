import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.ai.providers import (
    AIProviderError,
    AIProviderInvalidOutputError,
    GeminiProvider,
    OpenAICompatibleProvider,
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
        "ai_api_key": "provider-secret",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class GeminiModels:
    def __init__(self, text='{"value":"ok"}', errors=None):
        self.text = text
        self.request = None
        self.requests = []
        self.errors = list(errors or [])

    async def generate_content(self, **kwargs):
        self.request = kwargs
        self.requests.append(kwargs)
        if self.errors:
            raise self.errors.pop(0)
        return SimpleNamespace(
            text=self.text,
            usage_metadata=SimpleNamespace(prompt_token_count=11, candidates_token_count=7),
        )


def test_gemini_sdk_retry_layer_is_explicitly_disabled():
    provider = GeminiProvider(settings())

    assert provider._client._api_client._http_options.retry_options.attempts == 1


@pytest.mark.asyncio
async def test_gemini_adapter_uses_schema_system_boundary_and_usage():
    models = GeminiModels()
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
    assert models.request["config"]["system_instruction"] == "system"
    assert models.request["config"]["response_json_schema"] == {
        "type": "object",
        "properties": {"value": {"type": "string"}},
        "required": ["value"],
    }


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
    assert "AI_MODEL" in error.value.safe_message
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
    assert "AI_MODEL" in error.value.safe_message
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
    with pytest.raises(AIProviderError) as error:
        await GeminiProvider(
            settings(), client=client, rate_governor=governor
        ).generate_structured(
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


@pytest.mark.asyncio
async def test_retry_after_is_honored_and_success_reconciles_actual_usage(monkeypatch):
    models = GeminiModels(errors=[ProviderHttpError(429, retry_after=9)])
    client = SimpleNamespace(aio=SimpleNamespace(models=models))
    governor = RecordingGovernor()
    delays = []

    async def record_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("app.ai.providers.asyncio.sleep", record_sleep)
    response = await GeminiProvider(
        settings(), client=client, rate_governor=governor
    ).generate_structured(
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
            settings(ai_retry_max_seconds=30),
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


@pytest.mark.asyncio
async def test_openai_compatible_adapter_contract_and_estimator_fallback():
    captured = {}

    async def handler(request: httpx.Request):
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"value":"local"}'}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await OpenAICompatibleProvider(
            settings(ai_provider="openai_compatible", ai_base_url="http://model.internal/v1"),
            client=client,
        ).generate_structured(
            response_model=Output,
            system_prompt="system",
            user_prompt="data",
            max_output_tokens=100,
            operation="card generation",
        )

    assert response.data.value == "local"
    assert response.usage.estimated is True
    assert captured["messages"][0] == {"role": "system", "content": "system"}
    assert captured["response_format"]["json_schema"]["strict"] is True


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
async def test_supported_provider_profiles_normalize_the_same_contract():
    gemini_models = GeminiModels('{"value":"same"}')
    gemini = await GeminiProvider(
        settings(), client=SimpleNamespace(aio=SimpleNamespace(models=gemini_models))
    ).generate_structured(
        response_model=Output,
        system_prompt="system",
        user_prompt="data",
        max_output_tokens=100,
        operation="contract parity",
    )

    async def handler(_request: httpx.Request):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"value":"same"}'}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        compatible = await OpenAICompatibleProvider(
            settings(ai_provider="openai_compatible", ai_base_url="http://model.internal/v1"),
            client=client,
        ).generate_structured(
            response_model=Output,
            system_prompt="system",
            user_prompt="data",
            max_output_tokens=100,
            operation="contract parity",
        )

    assert gemini.data.model_dump() == compatible.data.model_dump() == {"value": "same"}
    assert gemini.usage == compatible.usage


def test_ai_configuration_matrix_and_secret_repr():
    with pytest.raises(ValidationError):
        settings(ai_provider="openai_compatible", ai_base_url=None)
    with pytest.raises(ValidationError):
        settings(ai_input_cost_per_million_usd="1", ai_output_cost_per_million_usd="0")
    with pytest.raises(ValidationError):
        settings(ai_base_url="https://user:password@example.com/v1")
    with pytest.raises(ValidationError):
        settings(ai_provider_max_retries=4)
    with pytest.raises(ValidationError):
        settings(ai_retry_base_seconds=2)
    configured = settings()
    assert "provider-secret" not in repr(configured)
    assert configured.ai_pricing_configured is False
