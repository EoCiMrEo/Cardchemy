"""The multi-PDF pilot cannot freeze labels without independent review."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from finalize_public_source_id_multipdf import (  # noqa: E402
    PACKET_SCHEMA, ReviewError, finalize,
)


def sample():
    groups, old_groups, new_groups = [], [], []
    rows_a, rows_b = [], []
    for index in range(96):
        group_id = f"G{index:03d}"
        split = "calibration" if index < 48 else "heldout"
        candidates = [{"id": f"S{number:02d}", "document_sha256":
                       "a" * 64 if number < 4 else "b" * 64,
                       "page": number, "page_text": f"Exact page {number} text.",
                       "cue": f"Exact page {number}", "filename":
                       "lec01.pdf" if number < 4 else "lec02.pdf"}
                      for number in range(1, 5)]
        labels = [{"id": candidate["id"], "document_sha256":
                   candidate["document_sha256"], "page": candidate["page"],
                   "page_useful": False if number < 4 else None,
                   "cue_useful": False if number < 4 else None}
                  for number, candidate in enumerate(candidates, 1)]
        groups.append({"group_id": group_id, "split": split,
                       "question_form": "direct", "candidates": candidates})
        old_groups.append({"group_id": group_id, "split": split, "labels": labels})
        new_groups.append({"group_id": group_id, "split": split,
                           "candidate": candidates[3]})
        row = {"group_id": group_id, "candidate_id": "S04",
               "document_sha256": "b" * 64, "page": 4,
               "source_verified": True, "page_useful": False,
               "cue_useful": False}
        rows_a.append(row)
        rows_b.append(row.copy())
    packet = {"schema": PACKET_SCHEMA, "groups": groups}
    existing = {"schema": PACKET_SCHEMA + "_sealed_existing_labels",
                "groups": old_groups}
    new_only = {"schema": PACKET_SCHEMA + "_new_page_review",
                "groups": new_groups}
    a = {"reviewer_id": "independent_a", "rows": rows_a}
    b = {"reviewer_id": "independent_b", "rows": rows_b}
    return packet, existing, new_only, a, b


def test_agreed_two_reviewers_freeze_all_96_pages():
    packet, existing, new_only, a, b = sample()
    labels = finalize(packet, existing, new_only, a, b)
    assert len(labels["groups"]) == 96
    assert labels["adjudicated_count"] == 0
    assert all(type(group["labels"][3]["page_useful"]) is bool
               for group in labels["groups"])


def test_disagreement_or_uncertainty_requires_third_adjudicator():
    packet, existing, new_only, a, b = sample()
    b["rows"][0]["page_useful"] = None
    with pytest.raises(ReviewError, match="adjudication_required"):
        finalize(packet, existing, new_only, a, b)
    third = {"reviewer_id": "independent_c", "rows": [
        {**a["rows"][0], "page_useful": True, "cue_useful": True}]}
    labels = finalize(packet, existing, new_only, a, b, third)
    assert labels["adjudicated_count"] == 1
    assert labels["groups"][0]["labels"][3]["page_useful"] is True


def test_missing_coverage_and_wrong_candidate_rejected():
    packet, existing, new_only, a, b = sample()
    a["rows"].pop()
    with pytest.raises(ReviewError, match="review_coverage_invalid"):
        finalize(packet, existing, new_only, a, b)
    packet, existing, new_only, a, b = sample()
    b["rows"][0]["candidate_id"] = "S01"
    with pytest.raises(ReviewError, match="review_row_invalid"):
        finalize(packet, existing, new_only, a, b)


def test_same_reviewer_and_unverified_source_rejected():
    packet, existing, new_only, a, b = sample()
    b["reviewer_id"] = a["reviewer_id"]
    with pytest.raises(ReviewError, match="reviewers_not_independent"):
        finalize(packet, existing, new_only, a, b)
    packet, existing, new_only, a, b = sample()
    a["rows"][0]["source_verified"] = False
    b["rows"][0]["source_verified"] = False
    with pytest.raises(ReviewError, match="adjudication_required"):
        finalize(packet, existing, new_only, a, b)


def test_useful_exact_cue_requires_a_useful_source_page():
    packet, existing, new_only, a, b = sample()
    a["rows"][0]["cue_useful"] = True
    with pytest.raises(ReviewError, match="review_row_invalid"):
        finalize(packet, existing, new_only, a, b)
