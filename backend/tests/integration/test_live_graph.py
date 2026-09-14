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
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY is not configured")

    from app.agents.graph import create_flashcard_graph

    result = await create_flashcard_graph().ainvoke(
        {
            "pdf_text": "Analysis of Algorithms. " * 300 + "\nComplexity Theory. " * 300,
            "target_count": 5,
            "summary": "",
            "chunks": [],
            "mapped_generated_cards": [],
            "final_cards": [],
            "errors": [],
        }
    )
    assert result.get("final_cards")
