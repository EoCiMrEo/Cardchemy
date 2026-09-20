"""Explicitly authorized, hard-bounded deployment-model RAG evaluation.

This test is skipped unless both RUN_LIVE_RAG_TESTS=1 and
RAG_LIVE_EVAL_AUTHORIZED=I_ACCEPT_PROVIDER_CHARGES are set. It admits exactly
one query embedding plus one answer and one support request. Normal CI never
spends provider quota.
"""

import asyncio
from decimal import Decimal
import os
from uuid import uuid4

import pytest

from app.ai.answering import (
    ClaimSupportOutput,
    GroundedAnswerOutput,
    render_answer_prompts,
    render_support_prompts,
    validate_grounded_answer,
    validate_support_output,
)
from app.ai.embeddings import get_embedding_provider
from app.ai.providers import get_ai_provider
from app.config import Settings, get_settings
from app.services.knowledge_retrieval import RetrievedKnowledgeChunk


LIVE_BASE_URL = "https://generativelanguage.googleapis.com"
LIVE_ANSWER_MODEL = "gemini-3.5-flash"
LIVE_EMBEDDING_MODEL = "gemini-embedding-001"
MAX_CALLS = 3
MAX_INPUT_TOKENS = 12_000
MAX_OUTPUT_TOKENS = 2_048
MAX_COST_USD = Decimal("0.04")
MAX_SECONDS = 60


def require_live_rag_authorization(settings: Settings) -> Settings:
    if os.getenv("RUN_LIVE_RAG_TESTS") != "1" or os.getenv("RAG_LIVE_EVAL_AUTHORIZED") != "I_ACCEPT_PROVIDER_CHARGES":
        raise RuntimeError("Live RAG evaluation requires both explicit authorization flags")
    if not settings.rag_enabled or not settings.rag_ai_provider_enabled or not settings.rag_embedding_provider_enabled:
        raise RuntimeError("Live RAG evaluation requires all RAG provider lanes enabled")
    if (
        settings.rag_ai_provider != "gemini"
        or settings.rag_embedding_provider != "gemini"
        or settings.rag_ai_endpoint_identity != LIVE_BASE_URL
        or settings.rag_embedding_endpoint_identity != LIVE_BASE_URL
        or settings.rag_ai_model != LIVE_ANSWER_MODEL
        or settings.rag_embedding_model != LIVE_EMBEDDING_MODEL
        or settings.rag_ai_thinking_level != "minimal"
    ):
        raise RuntimeError("Live RAG evaluation requires the reviewed endpoint and pinned model snapshots")
    if not settings.rag_ai_quota_bucket or not settings.rag_embedding_quota_bucket:
        raise RuntimeError("Live RAG evaluation requires explicit quota buckets")
    # Conservative price floors reviewed for this harness. Operators must
    # refresh them against current official pricing before authorizing a run.
    if (
        settings.rag_ai_input_cost_per_million_usd < Decimal("1.50")
        or settings.rag_ai_output_cost_per_million_usd < Decimal("9.00")
        or settings.rag_embedding_input_cost_per_million_usd < Decimal("0.15")
    ):
        raise RuntimeError("Live RAG evaluation requires reviewed conservative price floors")
    return settings.model_copy(update={
        "rag_ai_provider_max_retries": 0,
        "rag_embedding_provider_max_retries": 0,
        "rag_ai_concurrency": 1,
        "rag_embedding_concurrency": 1,
        "rag_ai_max_output_tokens": 1_024,
        "rag_ai_max_job_input_tokens": MAX_INPUT_TOKENS,
        "rag_ai_max_job_output_tokens": MAX_OUTPUT_TOKENS,
        "rag_ai_max_estimated_cost_usd": MAX_COST_USD,
        "rag_embedding_max_input_tokens": 512,
        "rag_embedding_batch_size": 1,
        "rag_embedding_max_estimated_cost_usd": Decimal("0.001"),
        "rag_ai_provider_timeout_seconds": 30,
        "rag_embedding_provider_timeout_seconds": 30,
    })


@pytest.mark.ai_live
@pytest.mark.skipif(
    os.getenv("RUN_LIVE_RAG_TESTS") != "1"
    or os.getenv("RAG_LIVE_EVAL_AUTHORIZED") != "I_ACCEPT_PROVIDER_CHARGES",
    reason="live RAG evaluation requires two explicit authorization flags",
)
async def test_live_rag_answer_and_support_with_hard_bounds():
    settings = require_live_rag_authorization(get_settings())
    answer_provider = get_ai_provider(settings, role="rag_answer")
    embedding_provider = get_embedding_provider(settings)
    chunk = RetrievedKnowledgeChunk(
        chunk_id=uuid4(), document_id=uuid4(), document_title="Authored evaluation lecture",
        content_revision_id=uuid4(), index_revision_id=uuid4(), page_number=1,
        section="Orbital terms", content="Perihelion is the point in an orbit nearest the Sun.",
        token_count=14, embedding_space_hash="a" * 64, corpus_revision=1,
        vector_similarity=1.0, lexical_score=1.0, vector_rank=1, lexical_rank=1,
        fusion_score=1.0,
    )
    question = "What is perihelion?"
    answer_system, answer_user = render_answer_prompts(
        question=question, history=(), chunks=(chunk,)
    )
    async with asyncio.timeout(MAX_SECONDS):
        embedding = await embedding_provider.embed_query(question)
        answer_response = await answer_provider.generate_structured(
            response_model=GroundedAnswerOutput,
            system_prompt=answer_system,
            user_prompt=answer_user,
            max_output_tokens=1_024,
            operation="rag_answer",
        )
        claims = validate_grounded_answer(answer_response.data, (chunk,))
        assert claims
        support_system, support_user = render_support_prompts(
            question=question, claims=claims, chunks=(chunk,)
        )
        support_response = await answer_provider.generate_structured(
            response_model=ClaimSupportOutput,
            system_prompt=support_system,
            user_prompt=support_user,
            max_output_tokens=512,
            operation="rag_support",
        )
    assert validate_support_output(support_response.data, len(claims))
    assert len(embedding.vectors) == 1 and len(embedding.vectors[0]) == 1_536
    assert answer_provider.telemetry_snapshot().request_count == 2
    assert embedding_provider.telemetry_snapshot().request_count == 1
    assert MAX_CALLS == 3
    answer_input_tokens = (
        answer_response.usage.input_tokens + support_response.usage.input_tokens
    )
    input_tokens = embedding.usage.input_tokens + answer_input_tokens
    output_tokens = answer_response.usage.output_tokens + support_response.usage.output_tokens
    assert input_tokens <= MAX_INPUT_TOKENS and output_tokens <= MAX_OUTPUT_TOKENS
    assert not answer_response.usage.estimated and not support_response.usage.estimated
    cost = (
        Decimal(answer_input_tokens) * settings.rag_ai_input_cost_per_million_usd
        + Decimal(output_tokens) * settings.rag_ai_output_cost_per_million_usd
    ) / Decimal(1_000_000)
    cost += Decimal(embedding.usage.input_tokens) * settings.rag_embedding_input_cost_per_million_usd / Decimal(1_000_000)
    assert cost <= MAX_COST_USD


def _guard_settings(**overrides) -> Settings:
    values = {
        "environment": "test",
        "database_url": "sqlite+aiosqlite:///:memory:",
        "secret_key": "test-only-secret-key-with-adequate-entropy-1234567890",
        "generation_source_encryption_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "rag_enabled": True,
        "rag_ai_provider_enabled": True,
        "rag_embedding_provider_enabled": True,
        "rag_ai_api_key": "not-used",
        "rag_embedding_api_key": "not-used",
        "rag_ai_quota_bucket": "live-rag-answer",
        "rag_embedding_quota_bucket": "live-rag-embedding",
    }
    return Settings(_env_file=None, **(values | overrides))


def test_live_rag_guard_requires_separate_explicit_authorization(monkeypatch):
    monkeypatch.delenv("RUN_LIVE_RAG_TESTS", raising=False)
    monkeypatch.delenv("RAG_LIVE_EVAL_AUTHORIZED", raising=False)
    with pytest.raises(RuntimeError, match="explicit authorization"):
        require_live_rag_authorization(_guard_settings())


@pytest.mark.parametrize("overrides", [
    {
        "rag_ai_provider": "openai_compatible",
        "rag_ai_base_url": "https://model.example.test/v1",
        "rag_ai_model": "gpt-4.1-mini",
    },
    {"rag_ai_model": "gemini-3.5-flash-latest"},
    {"rag_ai_thinking_level": "high"},
    {
        "rag_embedding_provider": "openai_compatible",
        "rag_embedding_base_url": "https://api.openai.com/v1",
        "rag_embedding_model": "text-embedding-3-large",
    },
    {"rag_ai_quota_bucket": ""},
    {"rag_ai_input_cost_per_million_usd": "1.49"},
    {"rag_ai_output_cost_per_million_usd": "8.99"},
    {"rag_embedding_input_cost_per_million_usd": "0.149"},
])
def test_live_rag_guard_refuses_unreviewed_endpoint_model_quota_or_price(
    monkeypatch, overrides
):
    monkeypatch.setenv("RUN_LIVE_RAG_TESTS", "1")
    monkeypatch.setenv("RAG_LIVE_EVAL_AUTHORIZED", "I_ACCEPT_PROVIDER_CHARGES")
    with pytest.raises(RuntimeError, match="reviewed|quota"):
        require_live_rag_authorization(_guard_settings(**overrides))


def test_live_rag_guard_clamps_calls_retries_tokens_time_and_cost(monkeypatch):
    monkeypatch.setenv("RUN_LIVE_RAG_TESTS", "1")
    monkeypatch.setenv("RAG_LIVE_EVAL_AUTHORIZED", "I_ACCEPT_PROVIDER_CHARGES")
    bounded = require_live_rag_authorization(_guard_settings(
        rag_ai_provider_max_retries=3,
        rag_embedding_provider_max_retries=3,
    ))
    assert bounded.rag_ai_provider_max_retries == bounded.rag_embedding_provider_max_retries == 0
    assert bounded.rag_ai_concurrency == bounded.rag_embedding_concurrency == 1
    assert bounded.rag_ai_max_output_tokens == 1_024
    assert bounded.rag_ai_max_job_input_tokens == MAX_INPUT_TOKENS
    assert bounded.rag_ai_max_job_output_tokens == MAX_OUTPUT_TOKENS
    assert bounded.rag_ai_max_estimated_cost_usd == MAX_COST_USD
    assert bounded.rag_ai_provider_timeout_seconds == bounded.rag_embedding_provider_timeout_seconds == 30
