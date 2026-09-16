"""Opt-in live AI smoke test.

Run explicitly with:
    RUN_LIVE_AI_TESTS=1 pytest -m ai_live tests/integration/test_live_graph.py

No key material is printed, even partially.
"""

import os

import pytest


@pytest.mark.ai_live
@pytest.mark.skipif(os.getenv("RUN_LIVE_AI_TESTS") != "1", reason="live AI tests require explicit opt-in")
async def test_live_flashcard_graph():
    from app.agents.graph import create_flashcard_graph
    from app.ai.contracts import ExtractedDocument, ExtractedPage
    from app.config import get_settings

    settings = get_settings()
    if not settings.ai_provider_enabled:
        pytest.skip("AI_PROVIDER_ENABLED is not true")
    settings.require_generation_worker_config()

    result = await create_flashcard_graph(settings=settings).ainvoke(
        {
            "pdf_document": ExtractedDocument(
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
            "target_count": 5,
        }
    )
    assert len(result.get("final_cards") or []) == 5
