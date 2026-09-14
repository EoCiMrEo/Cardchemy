import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from app.ai.providers import (
    AIProviderInvalidOutputError,
    GeminiProvider,
    OpenAICompatibleProvider,
)
from app.config import Settings


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: str


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
    def __init__(self, text='{"value":"ok"}'):
        self.text = text
        self.request = None

    async def generate_content(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(
            text=self.text,
            usage_metadata=SimpleNamespace(prompt_token_count=11, candidates_token_count=7),
        )


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
    assert models.request["config"]["response_json_schema"]["additionalProperties"] is False


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
    configured = settings()
    assert "provider-secret" not in repr(configured)
    assert configured.ai_pricing_configured is False
