"""Keyless guards for a private, explicitly authorized 20-card evaluation."""

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.ai.contracts import CandidateBatch, ExtractedDocument, ExtractedPage
from app.config import Settings
from scripts.evaluate_private_generation import (
    BudgetedProvider, EvaluationRefused, MAX_REQUESTS,
    bounded_settings, require_explicit_envelope, require_preflight,
    select_latest_failed_source, _aggregate,
)


def settings(**overrides):
    return Settings(_env_file=None, **({
        "environment": "test",
        "database_url": "sqlite+aiosqlite:///:memory:",
        "secret_key": "test-only-secret-key-with-adequate-entropy-1234567890",
        "generation_source_encryption_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "flashcard_ai_provider_enabled": True,
        "flashcard_ai_provider": "gemini",
        "flashcard_ai_model": "gemini-3.5-flash-lite",
        "flashcard_ai_thinking_level": "minimal",
        "flashcard_ai_api_key": "offline-test-key",
        "flashcard_ai_quota_bucket": "offline-test-bucket",
        "flashcard_ai_input_cost_per_million_usd": "0.30",
        "flashcard_ai_output_cost_per_million_usd": "2.50",
    } | overrides))


def approved_envelope():
    return {
        "RUN_PRIVATE_GENERATION_LIVE": "1",
        "PRIVATE_GENERATION_APPROVED_ENDPOINT": "https://generativelanguage.googleapis.com",
        "PRIVATE_GENERATION_APPROVED_MODEL": "gemini-3.5-flash-lite",
        "PRIVATE_GENERATION_APPROVED_REQUESTS": "16",
        "PRIVATE_GENERATION_APPROVED_INPUT_TOKENS": "120000",
        "PRIVATE_GENERATION_APPROVED_OUTPUT_TOKENS": "48000",
        "PRIVATE_GENERATION_APPROVED_COST_USD": "0.18",
        "PRIVATE_GENERATION_APPROVED_WALL_SECONDS": "480",
        "PRIVATE_GENERATION_APPROVED_CALL_SECONDS": "30",
        "PRIVATE_GENERATION_SOURCE_SELECTOR": "latest_failed_20_published",
        "PRIVATE_GENERATION_APPROVED_INPUT_PRICE_PER_MILLION_USD": "0.30",
        "PRIVATE_GENERATION_APPROVED_OUTPUT_PRICE_PER_MILLION_USD": "2.50",
    }


@pytest.mark.parametrize("field", list(approved_envelope()))
def test_each_explicit_authorization_field_is_required(field):
    environment = approved_envelope()
    environment.pop(field)
    with pytest.raises(EvaluationRefused):
        require_explicit_envelope(settings(), environment)


@pytest.mark.parametrize("overrides", [
    {"flashcard_ai_model": "gemini-3.8-flash", "flashcard_ai_thinking_level": "low"},
    {"flashcard_ai_base_url": "https://proxy.example.test"},
    {"flashcard_ai_output_cost_per_million_usd": "2.49"},
    {"flashcard_ai_output_cost_per_million_usd": "4.00"},
    {"flashcard_ai_quota_bucket": ""},
])
def test_live_profile_or_price_drift_is_refused(overrides):
    with pytest.raises((EvaluationRefused, ValidationError)):
        require_explicit_envelope(settings(**overrides), approved_envelope())


def test_bounded_preflight_is_keyless_and_enforces_one_retry_owner():
    bounded = bounded_settings(settings(flashcard_ai_provider_max_retries=3))
    assert bounded.flashcard_ai_provider_max_retries == 0
    assert bounded.flashcard_ai_concurrency == 1
    assert bounded.flashcard_ai_provider_timeout_seconds == 30
    assert bounded.flashcard_ai_max_job_input_tokens == 120_000
    assert bounded.flashcard_ai_max_job_output_tokens == 48_000
    assert bounded.flashcard_ai_max_estimated_cost_usd == Decimal("0.18")
    document = ExtractedDocument(pages=[ExtractedPage(
        page_number=1, text="Photosynthesis converts light into chemical energy. " * 20,
    )])
    prepared = require_preflight(document, bounded)
    assert prepared.chunks


class OfflineProvider:
    def __init__(self, *, error=False):
        self.calls = 0
        self.error = error

    async def generate_structured(self, **_arguments):
        self.calls += 1
        if self.error:
            raise RuntimeError("private provider message")
        return SimpleNamespace(usage=SimpleNamespace(
            input_tokens=2, output_tokens=3, estimated=False,
        ))


async def test_physical_request_and_output_reservations_refuse_extra_call():
    inner = OfflineProvider()
    guard = BudgetedProvider(inner, bounded_settings(settings()))
    arguments = {
        "response_model": CandidateBatch,
        "system_prompt": "System instruction",
        "user_prompt": "Short source",
        "max_output_tokens": 8_000,
    }
    for _ in range(6):
        await guard.generate_structured(**arguments)
    with pytest.raises(EvaluationRefused):
        await guard.generate_structured(**arguments)
    assert guard.requests == inner.calls == 6 < MAX_REQUESTS
    assert guard.reserved_output_tokens == 48_000
    with pytest.raises(EvaluationRefused):
        await guard.generate_structured(**(arguments | {"user_prompt": "x" * 120_000}))
    assert inner.calls == 6


async def test_uncertain_provider_attempt_is_counted_without_private_output():
    inner = OfflineProvider(error=True)
    guard = BudgetedProvider(inner, bounded_settings(settings()))
    with pytest.raises(RuntimeError):
        await guard.generate_structured(
            response_model=CandidateBatch, system_prompt="private system",
            user_prompt="private source", max_output_tokens=512,
        )
    assert guard.requests == inner.calls == 1
    assert guard.usage_uncertain
    summary = _aggregate(
        result=None, error=None, provider=guard, started=0,
        page_count=2, chunk_count=3,
    )
    assert summary["cost_unknown"] is True
    assert "private source" not in str(summary)


class ReadOnlySelectorDB:
    def __init__(self, rows):
        self.rows = rows
        self.selects = 0

    async def execute(self, statement):
        assert statement.is_select
        self.selects += 1
        return SimpleNamespace(all=lambda: self.rows)


async def test_latest_failed_source_selector_refuses_absent_or_tied_result_without_writes():
    empty = ReadOnlySelectorDB([])
    with pytest.raises(EvaluationRefused):
        await select_latest_failed_source(empty)
    assert empty.selects == 1
    timestamp = object()
    tied = ReadOnlySelectorDB([
        SimpleNamespace(user_id=uuid4(), subject_id=uuid4(), document_id=uuid4(), id=uuid4(), completed_at=timestamp),
        SimpleNamespace(user_id=uuid4(), subject_id=uuid4(), document_id=uuid4(), id=uuid4(), completed_at=timestamp),
    ])
    with pytest.raises(EvaluationRefused):
        await select_latest_failed_source(tied)
    assert tied.selects == 1


async def test_reauthorization_blocks_provider_before_physical_attempt():
    inner = OfflineProvider()
    checks = 0

    async def revoked():
        nonlocal checks
        checks += 1
        raise EvaluationRefused("Source no longer published")

    guard = BudgetedProvider(inner, bounded_settings(settings()), reauthorize=revoked)
    with pytest.raises(EvaluationRefused):
        await guard.generate_structured(
            response_model=CandidateBatch, system_prompt="private system",
            user_prompt="private source", max_output_tokens=512,
        )
    assert checks == 1
    assert guard.requests == inner.calls == 0
    assert guard.usage_uncertain is False


def test_aggregate_allowlists_pipeline_reason_and_hides_source_drift():
    from app.ai.pipeline import PipelineError

    guard = BudgetedProvider(OfflineProvider(), bounded_settings(settings()))
    error = PipelineError(
        "insufficient_grounded_cards", "private model detail", retryable=True,
        quality_diagnostics={"rounds": [], "rejections": {"private": 3}},
    )
    summary = _aggregate(
        result=None, error=error, provider=guard, started=0,
        page_count=1, chunk_count=1,
    )
    assert summary["failure_code"] == "insufficient_grounded_cards"
    assert "private model detail" not in str(summary)
    drift = _aggregate(
        result=None, error=error, provider=guard, started=0,
        page_count=1, chunk_count=1, source_changed=True,
    )
    assert drift["failure_code"] == "source_changed"
