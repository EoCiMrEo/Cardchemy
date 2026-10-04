"""Frozen development sample selection without reading PDFs or old outcomes."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import prepare_visual_source_feasibility_review_v1 as review
import summarize_visual_source_feasibility_v1 as summary


def rows():
    return {f"P{n:03d}": {"page_usefulness": "No", "cue_usefulness": "No"}
            for n in range(1, 265)}


def test_sample_is_deterministic_without_votes_results_or_gap_leakage():
    a, b = rows(), rows()
    selected = review.select_weak(a, b)
    assert len(selected) == len(set(selected)) == 16
    assert not set(selected) & review.GAPS
    assert selected == review.select_weak(dict(reversed(list(a.items()))), b)
    a[selected[0]]["page_usefulness"] = "Unsure"
    assert selected[0] not in review.select_weak(a, b)


def test_both_reviews_must_explicitly_find_page_and_cue_weak():
    a, b = rows(), rows()
    selected = review.select_weak(a, b)
    b[selected[0]]["cue_usefulness"] = "Yes"
    assert selected[0] not in review.select_weak(a, b)


def test_incomplete_review_roster_cannot_supply_control_sample():
    a, b = rows(), rows()
    b.pop("P264")
    with pytest.raises(review.visual.PreparationError, match="complete_review_roster"):
        review.select_weak(a, b)


def test_no_weak_supply_cannot_silently_use_uncertain_candidates():
    a, b = rows(), rows()
    for row in b.values():
        row["page_usefulness"] = "Unsure"
    with pytest.raises(review.visual.PreparationError, match="insufficient_agreed_weak_pairs"):
        review.select_weak(a, b)


def valid_review():
    roster = {f"R{n:02d}" for n in range(1, 30)}
    value = {"reviewer": "a", "packet_sha256": "a" * 64,
             "access_mapping_sha256": "b437660b9344fb00c8d346112dbf9dc08ef2d8f089d78996fba7225e2136224c",
             "images_visually_inspected": 29, "provider_calls": 0, "model_quality_pass": False,
             "judgments": [{"review_id": rid, "readability": "Yes", "input_usefulness": "No",
                            "cue_usefulness": "No", "question_clarity": "Unsure", "reason": "unclear_relation"}
                           for rid in sorted(roster)]}
    return roster, value


def test_complete_tri_state_review_keeps_uncertain_clarity():
    roster, value = valid_review()
    indexed = summary.validate_review(value, roster, "a" * 64, "a")
    assert len(indexed) == 29
    assert {r["question_clarity"] for r in indexed.values()} == {"Unsure"}


@pytest.mark.parametrize("mutation", ["incomplete", "duplicate", "packet", "inspection", "cue", "free_text"])
def test_incomplete_or_unbound_reviews_cannot_supply_a_feasibility_claim(mutation):
    roster, value = valid_review()
    if mutation == "incomplete":
        value["judgments"].pop()
    elif mutation == "duplicate":
        value["judgments"][-1]["review_id"] = value["judgments"][0]["review_id"]
    elif mutation == "packet":
        value["packet_sha256"] = "b" * 64
    elif mutation == "inspection":
        value["images_visually_inspected"] = 0
    elif mutation == "cue":
        value["judgments"][0]["cue_usefulness"] = "Yes"
    else:
        value["judgments"][0]["answer"] = "forbidden"
    with pytest.raises(review.visual.PreparationError):
        summary.validate_review(value, roster, "a" * 64, "a")
