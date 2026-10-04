"""Local, read-only 20-card source preflight with aggregate-only output.

Run inside the generation-worker image with the current backend mounted at
``/app``. This script does not construct an SDK provider or make AI requests.
It deliberately does not print source text, document IDs, or settings secrets.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, "/app" if Path("/app/app").is_dir() else str(Path(__file__).resolve().parents[1] / "backend"))

from app.ai.pipeline import FlashcardGenerationPipeline  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.database import async_session_maker, close_database  # noqa: E402
from scripts.evaluate_private_generation import (  # noqa: E402
    MAX_COST_MICROUSD, MAX_INPUT_TOKENS, MAX_OUTPUT_TOKENS, MAX_REQUESTS,
    MODEL, TARGET_CARDS, EvaluationRefused, _PreflightOnlyProvider,
    bounded_settings, load_authorized_pages, require_preflight,
    select_latest_failed_source,
)
from sqlalchemy import text  # noqa: E402

_phase = "configuration"


async def inspect() -> dict[str, object]:
    global _phase
    settings = bounded_settings(get_settings())
    _phase = "database_session"
    async with async_session_maker() as db:
        async with db.begin():
            _phase = "read_only_transaction"
            await db.execute(text("SET TRANSACTION READ ONLY"))
            _phase = "source_selection"
            owner_id, subject_id, document_id, _job_id = await select_latest_failed_source(db)
            _phase = "authorized_pages"
            source = await load_authorized_pages(
                db, owner_id=owner_id, subject_id=subject_id,
                document_id=document_id, settings=settings,
            )
    _phase = "no_yield_preflight"
    prepared = require_preflight(source.document, settings)
    _phase = "aggregate_estimate"
    pipeline = FlashcardGenerationPipeline(settings=settings, provider=_PreflightOnlyProvider())
    chunks = list(prepared.chunks)
    pipeline._preflight(chunks, TARGET_CARDS, pipeline._summary_packs(chunks))
    return {
        "provider_requests": 0,
        "source_selector": "latest_failed_20_published",
        "selected_source_current_reviewed_published": True,
        "configured_model_matches_draft": settings.flashcard_ai_model == MODEL,
        "canonical_page_count": len(source.document.pages),
        "prepared_chunk_count": len(chunks),
        "target_cards": TARGET_CARDS,
        "estimated_requests": pipeline.estimated_request_count,
        "estimated_input_tokens": pipeline.estimated_input_tokens,
        "estimated_output_tokens": pipeline.estimated_output_tokens,
        "estimated_cost_microusd": pipeline.estimated_cost_microusd,
        "within_draft_caps": bool(
            pipeline.estimated_request_count <= MAX_REQUESTS
            and pipeline.estimated_input_tokens <= MAX_INPUT_TOKENS
            and pipeline.estimated_output_tokens <= MAX_OUTPUT_TOKENS
            and pipeline.estimated_cost_microusd is not None
            and pipeline.estimated_cost_microusd <= MAX_COST_MICROUSD
        ),
        "caps": {
            "requests": MAX_REQUESTS, "input_tokens": MAX_INPUT_TOKENS,
            "output_tokens": MAX_OUTPUT_TOKENS, "cost_microusd": MAX_COST_MICROUSD,
        },
    }


def main() -> int:
    async def run() -> dict[str, object]:
        try:
            return await inspect()
        finally:
            await close_database()

    try:
        result = asyncio.run(run())
    except EvaluationRefused:
        raise SystemExit(f"Private generation source or no-yield preflight unavailable at {_phase}") from None
    except Exception:
        raise SystemExit(f"Private generation preflight unavailable at {_phase}") from None
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
