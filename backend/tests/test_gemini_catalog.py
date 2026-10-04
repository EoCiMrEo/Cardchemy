"""Offline role-by-model Gemini wire-policy matrix; no provider quota is used."""

import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.ai.answering import GroundedAnswerOutput
from app.ai.contracts import CandidateBatch, SummaryOutput
from app.ai.gemini_catalog import CATALOG, CATALOG_VERSION, SCHEMA_POLICY_VERSION
from app.ai.providers import AIProviderError, GeminiProvider
from app.config import Settings


def configured(**overrides) -> Settings:
    values = {
        "environment": "test",
        "database_url": "sqlite+aiosqlite:///:memory:",
        "secret_key": "test-only-secret-key-with-adequate-entropy-1234567890",
        "generation_source_encryption_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "flashcard_ai_api_key": "synthetic-flashcard-key",
        "rag_ai_api_key": "synthetic-answer-key",
        "flashcard_ai_provider_max_retries": 0,
        "rag_ai_provider_max_retries": 0,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class Synthetic400(Exception):
    status_code = 400


class RejectingModels:
    def __init__(self) -> None:
        self.calls = []

    async def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        raise Synthetic400()


@pytest.mark.parametrize("model_id", sorted(CATALOG))
@pytest.mark.parametrize(
    "role,response_model",
    [("flashcard", SummaryOutput), ("flashcard", CandidateBatch),
     ("rag_answer", GroundedAnswerOutput)],
)
async def test_role_by_model_payload_and_unsupported_parameter_400(
    model_id, role, response_model
):
    thinking = "low" if model_id in {"gemini-3.7-flash", "gemini-3.8-flash"} else "minimal"
    prefix = "flashcard_ai" if role == "flashcard" else "rag_ai"
    values = configured(**{
        f"{prefix}_model": model_id,
        f"{prefix}_thinking_level": thinking,
    })
    models = RejectingModels()
    adapter = GeminiProvider(values, client=SimpleNamespace(aio=SimpleNamespace(models=models)), role=role)
    with pytest.raises(AIProviderError) as failure:
        await adapter.generate_structured(
            response_model=response_model,
            system_prompt="trusted synthetic policy",
            user_prompt="synthetic untrusted evidence",
            max_output_tokens=512,
            operation="offline_payload_matrix",
        )
    assert failure.value.code == "ai_provider_invalid_request"
    assert not failure.value.retryable
    assert len(models.calls) == 1
    payload = models.calls[0]
    assert payload["model"] == model_id
    assert payload["config"]["thinking_config"] == {"thinking_level": thinking}
    assert payload["config"]["response_mime_type"] == "application/json"
    assert payload["config"]["response_json_schema"]["type"] == "object"
    assert '"format"' not in json.dumps(payload["config"]["response_json_schema"])
    assert "temperature" not in payload["config"]
    assert adapter.capability.schema_policy_version == SCHEMA_POLICY_VERSION


def test_catalog_versions_roles_and_verified_model_budgets():
    assert CATALOG_VERSION == "gemini-text-2026-09-22-v1"
    assert set(CATALOG) == {
        "gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.6-flash",
        "gemini-3.7-flash", "gemini-3.8-flash",
    }
    for capability in CATALOG.values():
        assert capability.roles == ("flashcard", "rag_answer")
        assert capability.context_window_tokens == 1_048_576
        assert capability.max_output_tokens == 65_536
        assert capability.sampling_policy == "provider_default"
        assert capability.usage_policy == "candidate_plus_thought"


@pytest.mark.parametrize("model_id", ["gemini-3.7-flash", "gemini-3.8-flash"])
def test_minimal_thinking_rejected_for_newer_models_before_provider_execution(model_id):
    with pytest.raises(ValidationError, match="does not support the configured thinking level"):
        configured(flashcard_ai_model=model_id, flashcard_ai_thinking_level="minimal")
    bypassed = configured().model_copy(update={
        "flashcard_ai_model": model_id, "flashcard_ai_thinking_level": "minimal"
    })
    with pytest.raises(AIProviderError) as failure:
        GeminiProvider(bypassed, client=object())
    assert failure.value.code == "ai_model_thinking_incompatible"


def test_unknown_model_and_oversized_budgets_fail_closed():
    with pytest.raises(ValidationError, match="verified Gemini model"):
        configured(flashcard_ai_model="gemini-unknown")
    with pytest.raises(ValidationError, match="context budget"):
        configured(flashcard_ai_context_window_tokens=1_048_577)
    with pytest.raises(ValidationError, match="output budget"):
        configured(flashcard_ai_max_output_tokens=65_537)
