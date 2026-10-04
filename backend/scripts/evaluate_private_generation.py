"""Explicitly authorized, aggregate-only evaluation of published local Knowledge.

This is a one-shot operator tool. It never writes cards or source text and makes
no provider call unless every envelope field is supplied explicitly. A separate
owner decision is required before setting those fields for a paid run.
"""

from __future__ import annotations

import asyncio
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import logging
import os
from pathlib import Path
import sys
from time import monotonic
from typing import Awaitable, Callable
from uuid import UUID

from sqlalchemy import select, text

# Direct `python scripts/evaluate_private_generation.py` must import the
# backend package without depending on an operator PYTHONPATH override.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.chunking import prepare_document
from app.ai.contracts import ExtractedDocument, ExtractedPage
from app.ai.grounding import REJECTION_CATEGORIES
from app.ai.pipeline import FlashcardGenerationPipeline, PipelineError, cost_microusd
from app.config import Settings, get_settings
from app.database import async_session_maker
from app.models.generation import GenerationJob
from app.models.knowledge import (
    SubjectDocument, SubjectDocumentContentRevision,
    SubjectDocumentIndexRevision, SubjectDocumentPage,
)
from app.models.subject import Subject


MODEL = "gemini-3.5-flash-lite"
ENDPOINT = "https://generativelanguage.googleapis.com"
TARGET_CARDS = 20
MAX_REQUESTS = 16
MAX_INPUT_TOKENS = 120_000
MAX_OUTPUT_TOKENS = 48_000
MAX_COST_MICROUSD = 180_000
MAX_WALL_SECONDS = 480
MAX_CALL_SECONDS = 30
PRICE_FLOOR_INPUT = Decimal("0.30")
PRICE_FLOOR_OUTPUT = Decimal("2.50")
SOURCE_SELECTOR = "latest_failed_20_published"
SAFE_PIPELINE_CODES = frozenset({
    "insufficient_grounded_cards", "document_has_no_text",
    "generation_job_timeout", "ai_input_token_limit",
    "ai_output_token_limit", "ai_cost_limit", "ai_estimated_cost_limit",
    "ai_context_window_limit", "invalid_ai_output", "ai_provider_timeout",
    "ai_provider_unavailable", "ai_provider_invalid_request",
    "ai_provider_authentication_failed", "ai_provider_access_denied",
    "ai_model_unavailable", "ai_provider_rate_limited",
    "ai_provider_rejected_request", "ai_provider_request_token_limit",
    "ai_model_output_incompatible", "ai_model_schema_incompatible",
})


class EvaluationRefused(RuntimeError):
    """Safe, content-free refusal before a live request."""


def require_explicit_envelope(settings: Settings, environment: dict[str, str]) -> None:
    """Match each owner-approved field before DB access or provider creation."""

    exact = {
        "RUN_PRIVATE_GENERATION_LIVE": "1",
        "PRIVATE_GENERATION_APPROVED_ENDPOINT": ENDPOINT,
        "PRIVATE_GENERATION_APPROVED_MODEL": MODEL,
        "PRIVATE_GENERATION_APPROVED_REQUESTS": str(MAX_REQUESTS),
        "PRIVATE_GENERATION_APPROVED_INPUT_TOKENS": str(MAX_INPUT_TOKENS),
        "PRIVATE_GENERATION_APPROVED_OUTPUT_TOKENS": str(MAX_OUTPUT_TOKENS),
        "PRIVATE_GENERATION_APPROVED_COST_USD": "0.18",
        "PRIVATE_GENERATION_APPROVED_WALL_SECONDS": str(MAX_WALL_SECONDS),
        "PRIVATE_GENERATION_APPROVED_CALL_SECONDS": str(MAX_CALL_SECONDS),
        "PRIVATE_GENERATION_SOURCE_SELECTOR": SOURCE_SELECTOR,
    }
    if any(environment.get(name) != expected for name, expected in exact.items()):
        raise EvaluationRefused("The explicit live evaluation envelope is incomplete or mismatched")
    try:
        approved_input = Decimal(environment["PRIVATE_GENERATION_APPROVED_INPUT_PRICE_PER_MILLION_USD"])
        approved_output = Decimal(environment["PRIVATE_GENERATION_APPROVED_OUTPUT_PRICE_PER_MILLION_USD"])
    except (KeyError, InvalidOperation):
        raise EvaluationRefused("The explicit live evaluation prices are missing or invalid") from None
    if (
        settings.flashcard_ai_input_cost_per_million_usd != approved_input
        or settings.flashcard_ai_output_cost_per_million_usd != approved_output
        or approved_input < PRICE_FLOOR_INPUT
        or approved_output < PRICE_FLOOR_OUTPUT
        or not settings.flashcard_ai_quota_bucket
    ):
        raise EvaluationRefused("The approved prices or provider quota bucket are unavailable")
    if (
        not settings.flashcard_ai_provider_enabled
        or settings.flashcard_ai_provider != "gemini"
        or settings.flashcard_ai_model != MODEL
        or settings.flashcard_ai_thinking_level != "minimal"
        or settings.flashcard_ai_base_url is not None
    ):
        raise EvaluationRefused("The approved native Gemini profile is unavailable")
    if (cost_microusd(settings, MAX_INPUT_TOKENS, MAX_OUTPUT_TOKENS) or 10**9) > MAX_COST_MICROUSD:
        raise EvaluationRefused("The full token envelope exceeds its approved price cap")


def bounded_settings(settings: Settings) -> Settings:
    """Narrow runtime limits without modifying the installation configuration."""

    return settings.model_copy(update={
        "flashcard_ai_provider_max_retries": 0,
        "flashcard_ai_concurrency": 1,
        "flashcard_ai_max_output_tokens": min(8_192, settings.flashcard_ai_max_output_tokens),
        "flashcard_ai_max_job_input_tokens": MAX_INPUT_TOKENS,
        "flashcard_ai_max_job_output_tokens": MAX_OUTPUT_TOKENS,
        "flashcard_ai_max_estimated_cost_usd": Decimal("0.18"),
        "flashcard_ai_provider_timeout_seconds": MAX_CALL_SECONDS,
    })


@dataclass(frozen=True)
class PrivateSource:
    owner_id: UUID
    subject_id: UUID
    document_id: UUID
    content_revision_id: UUID
    index_revision_id: UUID
    document: ExtractedDocument


async def current_source_identity(db, *, owner_id: UUID, subject_id: UUID, document_id: UUID):
    """Return the sole active published source and compatible ready index."""

    content = SubjectDocumentContentRevision
    index = SubjectDocumentIndexRevision
    identities = (await db.execute(
        select(content.id, index.id)
        .join(SubjectDocument, content.document_id == SubjectDocument.id)
        .join(Subject, SubjectDocument.subject_id == Subject.id)
        .join(index, index.content_revision_id == content.id)
        .where(
            Subject.id == subject_id,
            Subject.instructor_id == owner_id,
            SubjectDocument.id == document_id,
            SubjectDocument.uploader_id == owner_id,
            content.subject_id == subject_id,
            content.is_active.is_(True),
            content.status == "ready",
            content.reviewed_at.is_not(None),
            content.published_at.is_not(None),
            index.document_id == document_id,
            index.subject_id == subject_id,
            index.is_active.is_(True),
            index.status == "ready",
            index.embedding_space_hash == Subject.active_embedding_space_hash,
        )
        .limit(2)
    )).all()
    if len(identities) != 1:
        raise EvaluationRefused("The authorized published source is unavailable or ambiguous")
    return identities[0]


async def select_latest_failed_source(db) -> tuple[UUID, UUID, UUID, UUID]:
    """Choose a unique latest failed 20-card capture without exposing its IDs."""

    job = GenerationJob
    content = SubjectDocumentContentRevision
    rows = (await db.execute(
        select(job.user_id, job.subject_id, job.document_id, content.id, job.completed_at)
        .join(Subject, job.subject_id == Subject.id)
        .join(SubjectDocument, job.document_id == SubjectDocument.id)
        .join(content, job.knowledge_content_revision_id == content.id)
        .where(
            job.job_kind == "flashcards",
            job.status == "failed",
            job.error_code == "insufficient_grounded_cards",
            job.requested_card_count == TARGET_CARDS,
            job.completed_at.is_not(None),
            job.user_id == Subject.instructor_id,
            SubjectDocument.uploader_id == job.user_id,
            content.document_id == job.document_id,
            content.subject_id == job.subject_id,
            content.source_sha256 == job.source_sha256,
            content.is_active.is_(True),
            content.status == "ready",
            content.reviewed_at.is_not(None),
            content.published_at.is_not(None),
        )
        .order_by(job.completed_at.desc(), job.id.desc())
        .limit(2)
    )).all()
    if not rows or (len(rows) > 1 and rows[0].completed_at == rows[1].completed_at):
        raise EvaluationRefused("The latest failed 20-card source is unavailable or ambiguous")
    return rows[0].user_id, rows[0].subject_id, rows[0].document_id, rows[0].id


async def load_authorized_pages(db, *, owner_id: UUID, subject_id: UUID, document_id: UUID, settings: Settings) -> PrivateSource:
    """Read only canonical pages tied to the current authorized source identity."""

    content_id, index_id = await current_source_identity(
        db, owner_id=owner_id, subject_id=subject_id, document_id=document_id,
    )
    rows = (await db.execute(
        select(SubjectDocumentPage.page_number, SubjectDocumentPage.content)
        .where(SubjectDocumentPage.content_revision_id == content_id)
        .order_by(SubjectDocumentPage.page_number)
        .limit(settings.pdf_max_pages + 1)
    )).all()
    if not rows or len(rows) > settings.pdf_max_pages:
        raise EvaluationRefused("The authorized published source is unavailable or too large")
    if sum(len(page or "") for _, page in rows) > settings.pdf_max_extracted_chars:
        raise EvaluationRefused("The authorized published source exceeds the generation text limit")
    return PrivateSource(
        owner_id=owner_id, subject_id=subject_id, document_id=document_id,
        content_revision_id=content_id, index_revision_id=index_id,
        document=ExtractedDocument(pages=[
            ExtractedPage(page_number=number, text=page or "") for number, page in rows
        ]),
    )


async def reauthorize_source(source: PrivateSource) -> None:
    async with async_session_maker() as db:
        async with db.begin():
            await db.execute(text("SET TRANSACTION READ ONLY"))
            content_id, index_id = await current_source_identity(
                db, owner_id=source.owner_id, subject_id=source.subject_id,
                document_id=source.document_id,
            )
            if (content_id, index_id) != (
                source.content_revision_id, source.index_revision_id,
            ):
                raise EvaluationRefused("The published source changed during evaluation")


class _PreflightOnlyProvider:
    async def generate_structured(self, **_arguments):
        raise EvaluationRefused("Preflight cannot make a provider request")


def require_preflight(document: ExtractedDocument, settings: Settings):
    """Reject an unaffordable no-yield path before constructing the SDK client."""

    prepared = prepare_document(
        document, max_tokens=settings.flashcard_ai_chunk_input_tokens,
        overlap_tokens=settings.flashcard_ai_chunk_overlap_tokens,
    )
    pipeline = FlashcardGenerationPipeline(settings=settings, provider=_PreflightOnlyProvider())
    chunks = list(prepared.chunks)
    if not chunks:
        raise EvaluationRefused("The authorized published source has no usable text")
    pipeline._preflight(chunks, TARGET_CARDS, pipeline._summary_packs(chunks))
    if (
        pipeline.estimated_request_count > MAX_REQUESTS
        or pipeline.estimated_input_tokens > MAX_INPUT_TOKENS
        or pipeline.estimated_output_tokens > MAX_OUTPUT_TOKENS
        or pipeline.estimated_cost_microusd is None
        or pipeline.estimated_cost_microusd > MAX_COST_MICROUSD
    ):
        raise EvaluationRefused("The no-yield plan exceeds the approved live envelope")
    return prepared


class BudgetedProvider:
    """Reserve worst-case physical request usage before crossing the provider boundary."""

    def __init__(
        self, provider, settings: Settings,
        reauthorize: Callable[[], Awaitable[None]] | None = None,
    ):
        self.provider = provider
        self.settings = settings
        self.reauthorize = reauthorize
        self._lock = asyncio.Lock()
        self.requests = 0
        self.reserved_input_tokens = 0
        self.reserved_output_tokens = 0
        self.usage_uncertain = False

    def telemetry_snapshot(self):
        snapshot = getattr(self.provider, "telemetry_snapshot", None)
        return snapshot() if callable(snapshot) else None

    async def generate_structured(self, **arguments):
        from app.ai.providers import _closed_schema

        async with self._lock:
            schema = json.dumps(_closed_schema(arguments["response_model"]), ensure_ascii=False)
            input_bound = sum(len(value.encode("utf-8")) for value in (
                arguments["system_prompt"], arguments["user_prompt"], schema,
            )) + 1_024
            output_bound = arguments["max_output_tokens"]
            next_input = self.reserved_input_tokens + input_bound
            next_output = self.reserved_output_tokens + output_bound
            if (
                self.requests >= MAX_REQUESTS
                or input_bound < 1
                or not 1 <= output_bound <= 8_192
                or next_input > MAX_INPUT_TOKENS
                or next_output > MAX_OUTPUT_TOKENS
                or (cost_microusd(self.settings, next_input, next_output) or 10**9) > MAX_COST_MICROUSD
            ):
                raise EvaluationRefused("A physical request exceeds the approved live envelope")
            if self.reauthorize is not None:
                await self.reauthorize()
            self.requests += 1
            self.reserved_input_tokens = next_input
            self.reserved_output_tokens = next_output
            self.usage_uncertain = True
            response = await self.provider.generate_structured(**arguments)
            usage = response.usage
            if usage.estimated or usage.input_tokens > input_bound or usage.output_tokens > output_bound:
                raise EvaluationRefused("Provider usage is uncertain or exceeds its reservation")
            self.usage_uncertain = False
            return response


def _aggregate(*, result: dict | None, error: PipelineError | None, provider: BudgetedProvider, started: float, page_count: int, chunk_count: int, source_changed: bool = False) -> dict:
    quality = result.get("quality_diagnostics", {}) if result else (error.quality_diagnostics if error else {})
    cards = result.get("final_cards", []) if result else (error.validated_cards if error else ())
    rejections = quality.get("rejections", {}) if isinstance(quality, dict) else {}
    return {
        "status": "completed" if result else "failed",
        "failure_code": (
            "source_changed" if source_changed else (
                error.code if error and error.code in SAFE_PIPELINE_CODES else
                ("generation_failed" if error else (None if result else "execution_uncertain"))
            )
        ),
        "requested_cards": TARGET_CARDS,
        "validated_cards": len(cards),
        "canonical_pages": page_count,
        "prepared_chunks": chunk_count,
        "accepted_page_count": len({
            card["source_page"] if isinstance(card, dict) else card.source_page for card in cards
        }),
        "physical_requests": provider.requests,
        "reserved_input_tokens": provider.reserved_input_tokens,
        "reserved_output_tokens": provider.reserved_output_tokens,
        "actual_cost_microusd": (
            (result.get("actual_cost_microusd") if result else (
                error.actual_cost_microusd if error else None
            )) if not provider.usage_uncertain
            and not (result.get("usage_estimated") if result else (
                error.usage_estimated if error else True
            )) else None
        ),
        "cost_unknown": bool(provider.usage_uncertain or (
            result.get("usage_estimated") if result else (
                error.usage_estimated if error else provider.requests > 0
            )
        )),
        "elapsed_seconds": round(monotonic() - started, 3),
        "rounds": [{name: int(item.get(name, 0)) for name in (
            "round", "raw_count", "grounded_count", "valid_count",
            "distinct_count", "accepted_count", "missing_count",
        )} for item in quality.get("rounds", [])[:10] if isinstance(item, dict)],
        "rejections": {name: int(rejections.get(name, 0)) for name in REJECTION_CATEGORIES},
    }


async def run_private_evaluation() -> dict:
    settings = get_settings()
    require_explicit_envelope(settings, os.environ)
    settings = bounded_settings(settings)
    settings.require_generation_worker_config()
    async with async_session_maker() as db:
        async with db.begin():
            await db.execute(text("SET TRANSACTION READ ONLY"))
            owner_id, subject_id, document_id, selected_revision_id = await select_latest_failed_source(db)
            source = await load_authorized_pages(
                db, owner_id=owner_id, subject_id=subject_id,
                document_id=document_id, settings=settings,
            )
            if source.content_revision_id != selected_revision_id:
                raise EvaluationRefused("The published source changed during selection")
    document = source.document
    prepared = require_preflight(document, settings)
    await reauthorize_source(source)
    from app.ai.providers import get_ai_provider

    provider = BudgetedProvider(
        get_ai_provider(settings), settings,
        reauthorize=lambda: reauthorize_source(source),
    )
    pipeline = FlashcardGenerationPipeline(settings=settings, provider=provider)
    started = monotonic()
    result = None
    error = None
    source_changed = False
    try:
        async with asyncio.timeout(MAX_WALL_SECONDS):
            result = await pipeline.run(document, TARGET_CARDS, prepared=prepared)
    except PipelineError as exc:
        error = exc
    except Exception:
        # Errors, SDK messages and model output stay out of the result/logs.
        pass
    try:
        await reauthorize_source(source)
    except Exception:
        # A revision, publication or active index changed while work was in
        # flight. No cards or source detail may appear in the aggregate.
        result = None
        error = None
        source_changed = True
    return _aggregate(
        result=result, error=error, provider=provider, started=started,
        page_count=len(document.pages), chunk_count=len(prepared.chunks),
        source_changed=source_changed,
    )


def main() -> int:
    # The source, SDK and model output are private; this one-shot tool emits
    # only the allowlisted aggregate below, even when a provider call fails.
    logging.disable(logging.CRITICAL)
    try:
        with open(os.devnull, "w", encoding="utf-8") as sink:
            with redirect_stdout(sink), redirect_stderr(sink):
                aggregate = asyncio.run(run_private_evaluation())
    except Exception:
        aggregate = {"status": "refused", "reason": "authorization_or_budget_preflight_failed"}
    print(json.dumps(aggregate, sort_keys=True))
    return 0 if aggregate["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
