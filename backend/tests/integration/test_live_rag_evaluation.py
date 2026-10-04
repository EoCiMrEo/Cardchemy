"""Explicitly authorized one-embedding source-only smoke; no answer generation."""
import asyncio
from decimal import Decimal
import os
from uuid import uuid4

import pytest

from app.ai.embeddings import get_embedding_provider
from app.ai.related_evidence import select_source_first_excerpts
from app.config import ROOT_DIR, Settings
from app.services.knowledge_retrieval import RetrievedKnowledgeChunk

LIVE_BASE_URL = "https://generativelanguage.googleapis.com"
LIVE_EMBEDDING_MODEL = "gemini-embedding-001"
MAX_CALLS = 1
MAX_INPUT_TOKENS = 512
MAX_COST_USD = Decimal("0.001")
MAX_SECONDS = 45


def require_live_rag_authorization(settings: Settings) -> Settings:
    if (os.getenv("RUN_LIVE_RAG_TESTS") != "1"
            or os.getenv("RAG_LIVE_EVAL_AUTHORIZED") != "I_ACCEPT_EMBEDDING_CHARGES_SOURCE_ONLY"):
        raise RuntimeError("Live source-only evaluation requires explicit authorization")
    if not settings.rag_enabled or not settings.rag_embedding_provider_enabled:
        raise RuntimeError("Live source-only evaluation requires the embedding lane")
    if (settings.rag_embedding_provider != "gemini"
            or settings.rag_embedding_endpoint_identity != LIVE_BASE_URL
            or settings.rag_embedding_model != LIVE_EMBEDDING_MODEL
            or not settings.rag_embedding_quota_bucket
            or settings.rag_embedding_input_cost_per_million_usd < Decimal("0.20")):
        raise RuntimeError("Live evaluation requires reviewed endpoint/model/quota/price")
    return settings.model_copy(update={
        "rag_embedding_provider_max_retries": 0,
        "rag_embedding_concurrency": 1,
        "rag_embedding_max_input_tokens": MAX_INPUT_TOKENS,
        "rag_embedding_batch_size": 1,
        "rag_embedding_max_estimated_cost_usd": MAX_COST_USD,
        "rag_embedding_provider_timeout_seconds": 30,
    })


@pytest.mark.ai_live
@pytest.mark.skipif(
    os.getenv("RUN_LIVE_RAG_TESTS") != "1"
    or os.getenv("RAG_LIVE_EVAL_AUTHORIZED") != "I_ACCEPT_EMBEDDING_CHARGES_SOURCE_ONLY",
    reason="live source-only evaluation requires its own explicit authorization",
)
async def test_live_rag_embedding_and_source_selection_with_hard_bounds():
    settings = require_live_rag_authorization(Settings(_env_file=ROOT_DIR / ".env"))
    provider = get_embedding_provider(settings)
    question = "What is perihelion?"
    try:
        async with asyncio.timeout(MAX_SECONDS):
            result = await provider.embed_query(question)
    except Exception:
        pytest.fail("Live embedding failed; previous attempt cost is unknown", pytrace=False)
    assert len(result.vectors) == 1 and len(result.vectors[0]) == 1536
    assert provider.telemetry_snapshot().request_count == MAX_CALLS
    assert result.usage.input_tokens <= MAX_INPUT_TOKENS
    assert Decimal(result.usage.input_tokens) * settings.rag_embedding_input_cost_per_million_usd / Decimal(1_000_000) <= MAX_COST_USD
    chunk = RetrievedKnowledgeChunk(
        chunk_id=uuid4(), document_id=uuid4(), document_title="Authored evaluation lecture",
        content_revision_id=uuid4(), index_revision_id=uuid4(), page_number=1,
        section="Orbital terms", content="Perihelion is the point in an orbit nearest the Sun.",
        token_count=14, embedding_space_hash="a" * 64, corpus_revision=1,
        vector_similarity=1.0, lexical_score=1.0, vector_rank=1, lexical_rank=1,
        fusion_score=1.0,
    )
    excerpts = select_source_first_excerpts(question=question, chunks=(chunk,))
    assert len(excerpts) == 1
    assert excerpts[0].source.content[excerpts[0].start_offset:excerpts[0].end_offset] == chunk.content
    # This is a smoke of provider shape and deterministic selection, not a retrieval-quality gate.


def _guard_settings(**overrides):
    values = dict(environment="test", database_url="sqlite+aiosqlite:///:memory:",
                  secret_key="test-only-secret-key-with-adequate-entropy-1234567890",
                  generation_source_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                  rag_enabled=True, rag_embedding_provider_enabled=True,
                  rag_embedding_api_key="not-used", rag_embedding_quota_bucket="live-rag-embedding",
                  rag_embedding_input_cost_per_million_usd=Decimal("0.20"))
    return Settings(_env_file=None, **(values | overrides))


def test_live_source_guard_rejects_absent_and_legacy_answer_authorization(monkeypatch):
    monkeypatch.setenv("RUN_LIVE_RAG_TESTS", "1")
    monkeypatch.setenv("RAG_LIVE_EVAL_AUTHORIZED", "I_ACCEPT_PROVIDER_CHARGES")
    with pytest.raises(RuntimeError, match="explicit authorization"):
        require_live_rag_authorization(_guard_settings())


@pytest.mark.parametrize("overrides", [
    {"rag_enabled": False}, {"rag_embedding_provider_enabled": False},
    {"rag_embedding_quota_bucket": ""}, {"rag_embedding_input_cost_per_million_usd": Decimal("0.199")},
])
def test_live_source_guard_rejects_unreviewed_lane_or_budget(monkeypatch, overrides):
    monkeypatch.setenv("RUN_LIVE_RAG_TESTS", "1")
    monkeypatch.setenv("RAG_LIVE_EVAL_AUTHORIZED", "I_ACCEPT_EMBEDDING_CHARGES_SOURCE_ONLY")
    with pytest.raises(RuntimeError):
        require_live_rag_authorization(_guard_settings(**overrides))


def test_live_source_guard_clamps_embedding_without_answer_or_verifier(monkeypatch):
    monkeypatch.setenv("RUN_LIVE_RAG_TESTS", "1")
    monkeypatch.setenv("RAG_LIVE_EVAL_AUTHORIZED", "I_ACCEPT_EMBEDDING_CHARGES_SOURCE_ONLY")
    bounded = require_live_rag_authorization(_guard_settings(rag_embedding_provider_max_retries=3))
    assert bounded.rag_embedding_provider_max_retries == 0
    assert bounded.rag_embedding_concurrency == 1
    assert bounded.rag_embedding_max_input_tokens == 512
    assert bounded.rag_embedding_provider_timeout_seconds == 30
    assert bounded.rag_embedding_max_estimated_cost_usd == MAX_COST_USD
