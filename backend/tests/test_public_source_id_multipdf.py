"""Keyless cross-document packet selection on invented public-page stand-ins."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from prepare_public_source_id_multipdf import _exact_cue, _external_row  # noqa: E402
from app.ai.source_navigation import navigation_terms  # noqa: E402


def test_exact_cue_preserves_a_contiguous_question_bearing_span():
    page = ("unrelated heading and context. " * 25) + (
        "Angular distance is measured by the arc between two directions."
    )
    start, end = _exact_cue(page, navigation_terms("How is angular distance measured?"))
    assert 0 <= start < end <= len(page)
    assert end - start <= 480
    assert "Angular distance is measured" in page[start:end]


def test_external_page_is_from_another_pdf_in_the_same_split():
    matching = "Angular distance is measured by the arc between directions. " * 3
    metadata = {
        "source": {"split": "calibration"},
        "other": {"split": "calibration"},
        "heldout": {"split": "heldout"},
    }
    pages = {
        "source": ["license", matching],
        "other": [matching, "Context before angular distance. " + matching],
        "heldout": ["license", matching * 2],
    }
    group = {"source_document_sha256": "source", "split": "calibration",
             "question": "How is angular distance measured?",
             "prior_question_context_if_followup": None}
    row = _external_row(group, metadata, pages)
    assert row["document_sha256"] == "other"
    assert row["page"] == 2
    assert row["cue"] == row["page_text"][row["cue_start"]:row["cue_end"]]
    assert row["reviewed_page_useful"] is None
    assert row["reviewed_cue_useful"] is None
