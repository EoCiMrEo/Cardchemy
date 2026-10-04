"""Read-only, provider-free inventory of current published generation sources.

The latest failed 20-card job identifies one owner and Subject. At most three
current Knowledge documents in that Subject are inspected. Only ordinal and
bounded aggregate measurements leave this process; source text, titles and
database identities never do. A preflight estimates budget admission, not
distinct fact capacity or card yield.

Run inside the generation-worker image with the current backend mounted at
``/app``. No AI provider or SDK client is constructed by this script.
"""

from __future__ import annotations

import asyncio
from contextlib import redirect_stderr, redirect_stdout
import json
import logging
import os
from pathlib import Path
import sys
from uuid import UUID

sys.path.insert(0, "/app" if Path("/app/app").is_dir() else str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, text  # noqa: E402

from app.ai.chunking import prepare_document  # noqa: E402
from app.ai.pipeline import FlashcardGenerationPipeline, PipelineError  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.database import async_session_maker, close_database  # noqa: E402
from app.models.knowledge import (  # noqa: E402
    SubjectDocument, SubjectDocumentContentRevision, SubjectDocumentIndexRevision,
)
from app.models.subject import Subject  # noqa: E402
from scripts.evaluate_private_generation import (  # noqa: E402
    MAX_COST_MICROUSD, MAX_INPUT_TOKENS, MAX_OUTPUT_TOKENS, MAX_REQUESTS,
    MODEL, TARGET_CARDS, EvaluationRefused, _PreflightOnlyProvider,
    bounded_settings, current_source_identity, load_authorized_pages,
    select_latest_failed_source,
)


MAX_DOCUMENTS = 3
_phase = "configuration"


async def select_current_document_ids(db, *, owner_id: UUID, subject_id: UUID) -> list[UUID]:
    """Find at most three current, authorized and active-space sources."""

    document = SubjectDocument
    content = SubjectDocumentContentRevision
    index = SubjectDocumentIndexRevision
    rows = (await db.execute(
        select(document.id)
        .join(Subject, document.subject_id == Subject.id)
        .join(content, content.document_id == document.id)
        .join(index, index.content_revision_id == content.id)
        .where(
            Subject.id == subject_id,
            Subject.instructor_id == owner_id,
            document.subject_id == subject_id,
            document.uploader_id == owner_id,
            content.subject_id == subject_id,
            content.uploader_id == owner_id,
            content.is_active.is_(True),
            content.status == "ready",
            content.reviewed_at.is_not(None),
            content.published_at.is_not(None),
            index.document_id == document.id,
            index.subject_id == subject_id,
            index.uploader_id == owner_id,
            index.is_active.is_(True),
            index.status == "ready",
            index.embedding_space_hash == Subject.active_embedding_space_hash,
        )
        .distinct()
        .order_by(document.id)
        .limit(MAX_DOCUMENTS + 1)
    )).all()
    if not rows or len(rows) > MAX_DOCUMENTS:
        raise EvaluationRefused("The current published source count is unavailable or exceeds the inventory cap")
    return [row[0] for row in rows]


def source_metrics(source, settings, *, slot: int) -> dict[str, object]:
    """Measure one source without provider calls or returning private content."""

    prepared = prepare_document(
        source.document,
        max_tokens=settings.flashcard_ai_chunk_input_tokens,
        overlap_tokens=settings.flashcard_ai_chunk_overlap_tokens,
    )
    chunks = list(prepared.chunks)
    pipeline = FlashcardGenerationPipeline(settings=settings, provider=_PreflightOnlyProvider())
    status = "no_usable_text"
    if chunks:
        try:
            pipeline._preflight(chunks, TARGET_CARDS, pipeline._summary_packs(chunks))
        except PipelineError:
            status = "budget_refused"
        else:
            status = "admissible"
    model_matches = settings.flashcard_ai_provider == "gemini" and settings.flashcard_ai_model == MODEL
    within_reference_caps = bool(
        status == "admissible"
        and model_matches
        and pipeline.estimated_request_count <= MAX_REQUESTS
        and pipeline.estimated_input_tokens <= MAX_INPUT_TOKENS
        and pipeline.estimated_output_tokens <= MAX_OUTPUT_TOKENS
        and pipeline.estimated_cost_microusd is not None
        and pipeline.estimated_cost_microusd <= MAX_COST_MICROUSD
    )
    return {
        "slot": slot,
        "canonical_page_count": len(source.document.pages),
        "nonempty_page_count": sum(bool(page.text.strip()) for page in source.document.pages),
        "prepared_chunk_count": len(chunks),
        "preflight_status": status,
        "estimated_requests": pipeline.estimated_request_count if chunks else None,
        "estimated_input_tokens": pipeline.estimated_input_tokens if chunks else None,
        "estimated_output_tokens": pipeline.estimated_output_tokens if chunks else None,
        "estimated_cost_microusd": pipeline.estimated_cost_microusd if chunks else None,
        "within_reference_caps": within_reference_caps,
        "sparsity_unproven": True,
    }


async def inspect() -> dict[str, object]:
    """Inventory a single owner's Subject inside a read-only transaction."""

    global _phase
    settings = bounded_settings(get_settings())
    _phase = "database_session"
    async with async_session_maker() as db:
        async with db.begin():
            _phase = "read_only_transaction"
            await db.execute(text("SET TRANSACTION READ ONLY"))
            _phase = "source_selection"
            owner_id, subject_id, failed_document_id, _job_id = await select_latest_failed_source(db)
            document_ids = await select_current_document_ids(db, owner_id=owner_id, subject_id=subject_id)
            if failed_document_id not in document_ids:
                raise EvaluationRefused("The failed source is not current in this Subject")
            _phase = "authorized_pages"
            sources = []
            for slot, document_id in enumerate(document_ids, start=1):
                source = await load_authorized_pages(
                    db, owner_id=owner_id, subject_id=subject_id,
                    document_id=document_id, settings=settings,
                )
                _phase = "aggregate_preflight"
                sources.append(source_metrics(source, settings, slot=slot))
                _phase = "source_reauthorization"
                current_ids = await current_source_identity(
                    db, owner_id=owner_id, subject_id=subject_id,
                    document_id=document_id,
                )
                if tuple(current_ids) != (source.content_revision_id, source.index_revision_id):
                    raise EvaluationRefused("A published source changed during inventory")
                _phase = "authorized_pages"
    return {
        "provider_requests": 0,
        "source_selector": "latest_failed_20_subject",
        "target_cards": TARGET_CARDS,
        "document_count": len(sources),
        "failed_20_source_slot": document_ids.index(failed_document_id) + 1,
        "configured_model_matches_reference": (
            settings.flashcard_ai_provider == "gemini" and settings.flashcard_ai_model == MODEL
        ),
        "reference_caps": {
            "requests": MAX_REQUESTS,
            "input_tokens": MAX_INPUT_TOKENS,
            "output_tokens": MAX_OUTPUT_TOKENS,
            "cost_microusd": MAX_COST_MICROUSD,
        },
        "sparsity_unproven": True,
        "sources": sources,
    }


def main() -> int:
    async def run() -> dict[str, object]:
        try:
            return await inspect()
        finally:
            await close_database()

    logging.disable(logging.CRITICAL)
    try:
        with open(os.devnull, "w", encoding="utf-8") as sink:
            with redirect_stdout(sink), redirect_stderr(sink):
                result = asyncio.run(run())
    except Exception:
        print(json.dumps({
            "status": "unavailable", "phase": _phase,
            "provider_requests": 0, "sparsity_unproven": True,
        }, separators=(",", ":")))
        return 1
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
