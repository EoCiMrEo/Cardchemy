"""Opt-in live evaluation with request/token admission and a reviewed-price cap.

Run explicitly with:
    RUN_LIVE_AI_TESTS=1 pytest -m ai_live tests/integration/test_live_ai_pipeline.py

Requires explicit nonzero input/output token prices. No key material is printed.
Only the official OpenAI endpoint and the pinned non-reasoning GPT-4o Mini
snapshot are admitted; reasoning/provider variants need their own billing bound.
"""

from decimal import Decimal
import json
import os
from types import SimpleNamespace

import pytest


LIVE_MODEL = "gpt-4o-mini-2024-07-18"
LIVE_BASE_URL = "https://api.openai.com/v1"


def require_supported_live_configuration(settings):
    """Refuse unknown billing/output semantics before creating a provider."""
    if not settings.flashcard_ai_quota_bucket:
        raise RuntimeError("Live evaluation requires an explicit FLASHCARD_AI_QUOTA_BUCKET")
    if (
        settings.flashcard_ai_provider != "openai_compatible"
        or str(settings.flashcard_ai_base_url).rstrip("/") != LIVE_BASE_URL
        or settings.flashcard_ai_model != LIVE_MODEL
    ):
        raise RuntimeError("Live evaluation hard budget requires the supported non-reasoning model and official endpoint")
    # Published text prices reviewed 2026-09-16. Explicitly supplied prices must
    # be at least these floors, and operators must refresh them before a run:
    # https://developers.openai.com/api/docs/models/gpt-4o-mini
    if (
        settings.flashcard_ai_input_cost_per_million_usd < Decimal("0.15")
        or settings.flashcard_ai_output_cost_per_million_usd < Decimal("0.60")
    ):
        raise RuntimeError("Live evaluation hard budget requires reviewed prices at or above the supported model price floors")


def require_reserved_price_budget(settings):
    """Price the whole token envelope before constructing a live SDK client."""
    from app.ai.pipeline import cost_microusd

    if settings.flashcard_ai_input_cost_per_million_usd <= 0 or settings.flashcard_ai_output_cost_per_million_usd <= 0:
        raise RuntimeError("Live evaluation hard budget requires explicit nonzero token prices")
    reserved_cost = cost_microusd(settings, 8_192, 2_048)
    if reserved_cost is None or reserved_cost > 20_000:
        raise RuntimeError("Live evaluation refused its full token envelope outside the hard budget")


def build_budgeted_live_provider(settings):
    from app.ai.providers import get_ai_provider

    require_supported_live_configuration(settings)
    require_reserved_price_budget(settings)
    settings.require_generation_worker_config()
    bounded_settings = settings.model_copy(update={
        "flashcard_ai_provider_max_retries": 0,
        "flashcard_ai_refill_rounds": 0,
        "flashcard_ai_concurrency": 1,
        "flashcard_ai_cards_per_request": 2,
        "flashcard_ai_max_output_tokens": 2_048,
        "flashcard_ai_max_job_input_tokens": 8_192,
        "flashcard_ai_max_job_output_tokens": 2_048,
        "flashcard_ai_max_estimated_cost_usd": Decimal("0.02"),
        "flashcard_ai_provider_timeout_seconds": 30,
    })
    return BudgetedLiveProvider(get_ai_provider(bounded_settings), bounded_settings)


class BudgetedLiveProvider:
    """Admit one conservatively bounded request; require reported usage afterward."""

    def __init__(self, provider, settings):
        self.provider = provider
        self.settings = settings
        self.requests = 0

    def telemetry_snapshot(self):
        return self.provider.telemetry_snapshot()

    async def generate_structured(self, **arguments):
        from app.ai.providers import _closed_schema

        require_reserved_price_budget(self.settings)
        schema = json.dumps(_closed_schema(arguments["response_model"]), ensure_ascii=False)
        # One token per UTF-8 byte overestimates ordinary byte-based text
        # tokenizers. Include the complete schema and 1,024 tokens of provider
        # framing headroom instead of relying on the application's text estimate.
        input_bound = sum(len(value.encode("utf-8")) for value in (
            arguments["system_prompt"], arguments["user_prompt"], schema,
        )) + 1_024
        requested_output = arguments["max_output_tokens"]
        if self.requests >= 1 or input_bound > 8_192 or not 1 <= requested_output <= 2_048:
            raise RuntimeError("Live evaluation refused a request outside its hard budget")
        self.requests += 1
        response = await self.provider.generate_structured(**arguments)
        if response.usage.estimated:
            raise RuntimeError("Live evaluation requires provider-reported token usage")
        if response.usage.input_tokens > 8_192 or response.usage.output_tokens > 2_048:
            raise RuntimeError("Live evaluation provider-reported usage exceeded the token budget")
        return response


@pytest.mark.ai_live
@pytest.mark.skipif(os.getenv("RUN_LIVE_AI_TESTS") != "1", reason="live AI tests require explicit opt-in")
async def test_live_ai_pipeline():
    from app.ai.contracts import ExtractedDocument, ExtractedPage
    from app.ai.pipeline import FlashcardGenerationPipeline
    from app.config import get_settings

    settings = get_settings()
    if not settings.flashcard_ai_provider_enabled:
        pytest.skip("FLASHCARD_AI_PROVIDER_ENABLED is not true")
    provider = build_budgeted_live_provider(settings)
    settings = provider.settings

    result = await FlashcardGenerationPipeline(settings=settings, provider=provider).run(
        ExtractedDocument(
            pages=[
                ExtractedPage(
                    page_number=1,
                    text=(
                        "Merge sort has O(n log n) worst-case time. "
                        "Binary search has O(log n) search time. "
                        "A queue follows first-in, first-out order."
                    ),
                ),
                ExtractedPage(
                    page_number=2,
                    text=(
                        "A stack follows last-in, first-out order. "
                        "Dijkstra's algorithm requires nonnegative edge weights. "
                        "Breadth-first search finds shortest paths in unweighted graphs."
                    ),
                ),
            ]
        ),
        2,
    )
    assert len(result.get("final_cards") or []) == 2
    assert provider.requests == result["provider_request_count"] == 1
    assert result["provider_retry_count"] == 0
    assert result["usage_estimated"] is False
    assert result["actual_input_tokens"] <= 8_192
    assert result["actual_output_tokens"] <= 2_048
    assert result["actual_cost_microusd"] <= 20_000


class OfflineBudgetProbe:
    def __init__(self, *, estimated=False):
        self.calls = 0
        self.response = SimpleNamespace(data="offline-result", usage=SimpleNamespace(
            input_tokens=2, output_tokens=1, estimated=estimated,
        ))

    async def generate_structured(self, **_):
        self.calls += 1
        return self.response


def budget_settings(**overrides):
    from app.config import Settings

    values = {"environment": "test", "database_url": "sqlite+aiosqlite:///:memory:",
              "secret_key": "test-only-secret-key-with-adequate-entropy-1234567890",
              "generation_source_encryption_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
              "flashcard_ai_input_cost_per_million_usd": "0.15", "flashcard_ai_output_cost_per_million_usd": "0.60",
              "flashcard_ai_quota_bucket": "test-live-flashcards"}
    return Settings(_env_file=None, **(values | overrides))


@pytest.mark.parametrize("configuration", [
    {"flashcard_ai_quota_bucket": ""},
    {"flashcard_ai_provider": "gemini", "flashcard_ai_model": "gemini-3.8-flash"},
    {"flashcard_ai_provider": "openai_compatible", "flashcard_ai_base_url": LIVE_BASE_URL, "flashcard_ai_model": "o4-mini"},
    {"flashcard_ai_provider": "openai_compatible", "flashcard_ai_base_url": "https://model.example.com/v1", "flashcard_ai_model": LIVE_MODEL},
    {"flashcard_ai_provider": "openai_compatible", "flashcard_ai_base_url": "https://api.openai.com/v1/other", "flashcard_ai_model": LIVE_MODEL},
    {"flashcard_ai_provider": "openai_compatible", "flashcard_ai_base_url": LIVE_BASE_URL, "flashcard_ai_model": "gpt-4o-mini"},
    {"flashcard_ai_provider": "openai_compatible", "flashcard_ai_base_url": LIVE_BASE_URL, "flashcard_ai_model": LIVE_MODEL,
     "flashcard_ai_input_cost_per_million_usd": "0.14"},
    {"flashcard_ai_provider": "openai_compatible", "flashcard_ai_base_url": LIVE_BASE_URL, "flashcard_ai_model": LIVE_MODEL,
     "flashcard_ai_output_cost_per_million_usd": "0.59"},
    {"flashcard_ai_provider": "openai_compatible", "flashcard_ai_base_url": LIVE_BASE_URL, "flashcard_ai_model": LIVE_MODEL,
     "flashcard_ai_input_cost_per_million_usd": "3"},
], ids=["missing-quota-bucket", "thinking-gemini", "reasoning-model", "custom-provider", "changed-endpoint", "moving-alias",
        "underpriced-input", "underpriced-output", "reserved-cost-overrun"])
def test_live_evaluation_refuses_unsupported_billing_before_provider_construction(monkeypatch, configuration):
    def forbidden_factory(_):
        pytest.fail("Provider construction must not precede hard budget admission")

    monkeypatch.setattr("app.ai.providers.get_ai_provider", forbidden_factory)
    with pytest.raises(RuntimeError, match="hard budget|FLASHCARD_AI_QUOTA_BUCKET"):
        build_budgeted_live_provider(budget_settings(**configuration))


def test_live_evaluation_clamps_sdk_and_pipeline_limits_before_provider_construction(monkeypatch):
    constructed_settings = []

    def offline_factory(settings):
        constructed_settings.append(settings)
        return OfflineBudgetProbe()

    monkeypatch.setattr("app.ai.providers.get_ai_provider", offline_factory)
    provider = build_budgeted_live_provider(budget_settings(
        flashcard_ai_provider="openai_compatible", flashcard_ai_base_url=LIVE_BASE_URL, flashcard_ai_model=LIVE_MODEL,
        flashcard_ai_provider_max_retries=3, flashcard_ai_refill_rounds=2,
    ))
    assert constructed_settings == [provider.settings]
    assert provider.settings.flashcard_ai_provider_max_retries == provider.settings.flashcard_ai_refill_rounds == 0
    assert provider.settings.flashcard_ai_concurrency == 1
    assert provider.settings.flashcard_ai_cards_per_request == 2
    assert provider.settings.flashcard_ai_max_output_tokens == provider.settings.flashcard_ai_max_job_output_tokens == 2_048
    assert provider.settings.flashcard_ai_max_job_input_tokens == 8_192
    assert provider.settings.flashcard_ai_max_estimated_cost_usd == Decimal("0.02")
    assert provider.settings.flashcard_ai_provider_timeout_seconds == 30


async def test_live_evaluation_budget_allows_one_call_and_refuses_a_second():
    from app.ai.contracts import CandidateBatch

    probe = OfflineBudgetProbe()
    provider = BudgetedLiveProvider(probe, budget_settings())
    arguments = {"response_model": CandidateBatch, "system_prompt": "system", "user_prompt": "source facts", "max_output_tokens": 64}
    assert (await provider.generate_structured(**arguments)).data == "offline-result"
    with pytest.raises(RuntimeError, match="hard budget"):
        await provider.generate_structured(**arguments)
    assert probe.calls == 1


@pytest.mark.parametrize("prompt,output,prices", [
    ("source " * 10_000, 64, {}),
    ("source facts", 2_049, {}),
    ("source facts", 64, {"flashcard_ai_output_cost_per_million_usd": "10000"}),
    ("source facts", 64, {"flashcard_ai_input_cost_per_million_usd": "3"}),
    ("source facts", 64, {"flashcard_ai_input_cost_per_million_usd": "0", "flashcard_ai_output_cost_per_million_usd": "0"}),
], ids=["input-budget", "output-budget", "cost-budget", "reserved-cost-budget", "missing-prices"])
async def test_live_evaluation_budget_refuses_token_and_cost_overruns_before_a_call(prompt, output, prices):
    from app.ai.contracts import CandidateBatch

    probe = OfflineBudgetProbe()
    provider = BudgetedLiveProvider(probe, budget_settings(**prices))
    with pytest.raises(RuntimeError, match="hard budget"):
        await provider.generate_structured(response_model=CandidateBatch, system_prompt="system", user_prompt=prompt, max_output_tokens=output)
    assert probe.calls == 0


async def test_live_evaluation_schema_overflow_is_refused_before_a_call():
    from pydantic import Field, create_model

    large_schema = create_model("LargeResponse", answer=(str, Field(description="x" * 8_192)))
    probe = OfflineBudgetProbe()
    provider = BudgetedLiveProvider(probe, budget_settings())
    with pytest.raises(RuntimeError, match="hard budget"):
        await provider.generate_structured(response_model=large_schema, system_prompt="system", user_prompt="facts", max_output_tokens=64)
    assert probe.calls == 0


async def test_live_evaluation_rejects_estimated_usage_without_admitting_a_retry():
    from app.ai.contracts import CandidateBatch

    probe = OfflineBudgetProbe(estimated=True)
    provider = BudgetedLiveProvider(probe, budget_settings())
    arguments = {"response_model": CandidateBatch, "system_prompt": "system", "user_prompt": "facts", "max_output_tokens": 64}
    with pytest.raises(RuntimeError, match="provider-reported"):
        await provider.generate_structured(**arguments)
    with pytest.raises(RuntimeError, match="hard budget"):
        await provider.generate_structured(**arguments)
    assert probe.calls == 1


@pytest.mark.parametrize("input_tokens,output_tokens", [(8_193, 1), (2, 2_049)], ids=["reported-input", "reported-output"])
async def test_live_evaluation_rejects_reported_overruns_without_admitting_a_retry(input_tokens, output_tokens):
    from app.ai.contracts import CandidateBatch

    probe = OfflineBudgetProbe()
    probe.response.usage.input_tokens = input_tokens
    probe.response.usage.output_tokens = output_tokens
    provider = BudgetedLiveProvider(probe, budget_settings())
    arguments = {"response_model": CandidateBatch, "system_prompt": "system", "user_prompt": "facts", "max_output_tokens": 64}
    with pytest.raises(RuntimeError, match="provider-reported usage exceeded"):
        await provider.generate_structured(**arguments)
    with pytest.raises(RuntimeError, match="hard budget"):
        await provider.generate_structured(**arguments)
    assert probe.calls == 1
