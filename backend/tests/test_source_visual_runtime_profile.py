"""Offline visual-policy disclosure, release fence and credential isolation."""

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import yaml
from fastapi import HTTPException

from app.config import Settings
from app.models.knowledge import RagEmbeddingSpace, embedding_space_hash
from app.routers import rag as router


ROOT = Path(__file__).resolve().parents[2]


def settings():
    return Settings(
        _env_file=None,
        environment="test",
        database_url="sqlite+aiosqlite:///:memory:",
        secret_key="profile-only-test-secret-with-adequate-entropy-1234567890",
        generation_source_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        knowledge_pdf_encryption_key="AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE",
        rag_enabled=True,
        rag_ask_enabled=True,
        rag_embedding_provider_enabled=True,
        rag_source_judge_provider_enabled=True,
        rag_embedding_api_key="profile-test-embedding-secret",
        rag_source_judge_api_key="profile-test-judge-secret",
    )


class ProfileDb:
    def __init__(self, identity):
        self.space = SimpleNamespace(
            identity_hash=identity, provider="gemini", model="gemini-embedding-001",
        )
        self.reads = 0

    async def get(self, model, key):
        assert model is RagEmbeddingSpace
        assert key == self.space.identity_hash
        self.reads += 1
        return self.space


async def profile(monkeypatch, configured, *, matches=True):
    identity = embedding_space_hash(configured.rag_embedding_space_identity)
    db = ProfileDb(identity if matches else "different-space")
    subject_id, user = uuid4(), SimpleNamespace(id=uuid4())

    async def authorize(actual_db, actual_subject, actual_user):
        assert (actual_db, actual_subject, actual_user) == (db, subject_id, user)
        return SimpleNamespace(active_embedding_space_hash=db.space.identity_hash)

    monkeypatch.setattr(router.SubjectService, "check_subject_access", authorize)
    result = await router.get_rag_profile(subject_id, user, db, configured)
    assert db.reads == 1
    return result


async def test_visual_disclosure_uses_selected_policy_without_reopening_the_release_fence(monkeypatch):
    # Model an explicit retired fence; no database or provider is used.
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", "two_request_local_support_v1")
    result = await profile(monkeypatch, settings())
    assert result.ask_policy == "related_knowledge_navigation_v8"
    assert result.ask_enabled is False
    assert result.ask_available is False
    assert result.source_judge_available is False
    assert result.source_judge_model == "gemini-3.5-flash-lite"
    assert result.source_judge_thinking_level == "HIGH"
    assert result.source_judge_transfers_page_images is True
    assert result.source_judge_transfers_published_content is True
    assert result.source_judge_contract_version == "visual_source_id_v5"
    assert result.source_judge_transfers_literal_subject_context is True
    assert result.answer_available is False
    assert result.answer_provider is None and result.answer_model is None
    wire = result.model_dump_json()
    assert "secret" not in wire and "api_key" not in wire and "encryption_key" not in wire


async def test_visual_profile_still_requires_the_current_subject_embedding_space(monkeypatch):
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", "related_knowledge_navigation_v8")
    matching = await profile(monkeypatch, settings())
    assert matching.ask_enabled and matching.ask_available
    mismatching = await profile(monkeypatch, settings(), matches=False)
    assert mismatching.embedding_available is True
    assert not mismatching.active_embedding_space_matches
    assert not mismatching.ask_enabled and not mismatching.ask_available
    assert not mismatching.source_judge_available


async def test_historical_v4_profile_metadata_remains_text_only(monkeypatch):
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", "two_request_local_support_v1")
    monkeypatch.setattr(router, "ASK_REQUIRED_RELEASE_POLICY_VERSION", "related_knowledge_navigation_v4")
    result = await profile(monkeypatch, settings())
    assert result.ask_policy == "related_knowledge_navigation_v4"
    assert result.source_judge_thinking_level == "LOW"
    assert result.source_judge_transfers_page_images is False
    assert result.source_judge_contract_version == "source_id_only_public_v1"
    assert not result.ask_enabled


async def test_unauthorized_subject_profile_cannot_read_space_or_disclose_processors(monkeypatch):
    async def denied(*_args):
        raise HTTPException(status_code=404, detail="Subject not found")

    monkeypatch.setattr(router.SubjectService, "check_subject_access", denied)
    db = ProfileDb("never-read")
    with pytest.raises(HTTPException) as exc:
        await router.get_rag_profile(uuid4(), SimpleNamespace(id=uuid4()), db, settings())
    assert exc.value.status_code == 404
    assert db.reads == 0


def test_resolved_answer_worker_receives_only_required_pdf_and_provider_credentials():
    # Parse literal template YAML, without Compose interpolation or operator .env.
    services = yaml.safe_load((ROOT / "docker-compose.yml").read_text())["services"]
    env = services["answer-worker"]["environment"]
    assert env["KNOWLEDGE_PDF_ENCRYPTION_KEY"] == "${KNOWLEDGE_PDF_ENCRYPTION_KEY:-}"
    assert env["RAG_EMBEDDING_API_KEY"] == "${RAG_EMBEDDING_API_KEY:-}"
    assert env["RAG_SOURCE_JUDGE_API_KEY"] == "${RAG_SOURCE_JUDGE_API_KEY:-}"
    assert not any(name.startswith(("RAG_AI_", "FLASHCARD_AI_", "SMTP_")) for name in env)
    for name in ("index-worker", "email-worker", "migrate"):
        assert "KNOWLEDGE_PDF_ENCRYPTION_KEY" not in services[name]["environment"]
    for name, service in services.items():
        if "environment" in service and name != "answer-worker":
            assert "RAG_SOURCE_JUDGE_API_KEY" not in service["environment"]
    assert env["RAG_ASK_ENABLED"] == "${RAG_ASK_ENABLED:-false}"
    assert env["RAG_SOURCE_JUDGE_PROVIDER_ENABLED"] == "${RAG_SOURCE_JUDGE_PROVIDER_ENABLED:-false}"


def test_fresh_template_and_compose_keep_visual_limits_and_thinking_aligned():
    template = dict(
        line.split("=", 1) for line in (ROOT / ".env.example").read_text().splitlines()
        if line and not line.startswith("#") and "=" in line
    )
    env = yaml.safe_load((ROOT / "docker-compose.yml").read_text())["services"]["answer-worker"]["environment"]
    expected = {
        "RAG_SOURCE_JUDGE_MODEL": "gemini-3.5-flash-lite",
        "RAG_SOURCE_JUDGE_THINKING_LEVEL": "high",
        "RAG_SOURCE_JUDGE_MAX_INPUT_TOKENS": "32768",
        "RAG_SOURCE_JUDGE_MAX_OUTPUT_TOKENS": "4096",
        "RAG_SOURCE_JUDGE_PROVIDER_TIMEOUT_SECONDS": "120",
        "RAG_SOURCE_JUDGE_PROVIDER_MAX_RETRIES": "0",
        "RAG_SOURCE_JUDGE_INPUT_COST_PER_MILLION_USD": "0.30",
        "RAG_SOURCE_JUDGE_OUTPUT_COST_PER_MILLION_USD": "2.50",
    }
    for name, value in expected.items():
        assert template[name] == value
        assert env[name] == "${" + name + ":-" + value + "}"
    assert template["RAG_ASK_ENABLED"] == "false"
    assert template["RAG_SOURCE_JUDGE_PROVIDER_ENABLED"] == "false"

