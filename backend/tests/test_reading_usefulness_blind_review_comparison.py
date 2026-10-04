"""Independent public review comparison must fail closed and never infer labels."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import compare_reading_usefulness_blind_reviews as comparison


def _save(path: Path, value: dict) -> str:
    raw = json.dumps(value, sort_keys=True).encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def packets(tmp_path, monkeypatch):
    monkeypatch.setattr(comparison, "gettempdir", lambda: str(tmp_path))
    groups, judgments = [], []
    for number in range(96):
        name = f"group-{number}"
        candidates = []
        for index in range(4):
            key = f"{name}:{index + 1}"
            candidates.append({"id": key, "exact_window": "public cue",
                               "source_offset": {"page_number": index + 1}})
            judgments.append({"id": key, "group_id": name,
                              "source_pdf": "lec10.pdf", "page_number": index + 1,
                              "original_page_useful": index == 0,
                              "exact_visible_cue_useful": index == 0,
                              "uncertain": False, "reason": "reviewed original page"})
        groups.append({"id": name, "source_document_path_author_aid": "lec10.pdf",
                       "candidates": candidates})
    blind_path = tmp_path / "blind.json"
    blind_sha = _save(blind_path, {
        "schema": "cardchemy_reading_usefulness_blind_review_v1",
        "groups": groups})
    paths = []
    for reviewer in ("a", "b"):
        path = tmp_path / f"review-{reviewer}.json"
        _save(path, {"reviewer_id": reviewer, "packet_sha256": blind_sha,
                     "reviewed_group_count": 96, "reviewed_candidate_count": 384,
                     "judgments": copy.deepcopy(judgments)})
        paths.append(path)
    return blind_path, blind_sha, *paths


def test_complete_agreement_is_reported_without_model_scoring(packets):
    result = comparison.compare(*packets)
    assert result["candidate_count"] == 384
    assert result["agreed_candidates"] == 384
    assert result["fully_agreed_without_uncertainty"] is True
    assert result["unresolved"] == []


def test_uncertain_or_disagreed_is_unresolved_not_auto_adjudicated(packets):
    blind, sha, first, second = packets
    changed = json.loads(second.read_bytes())
    changed["judgments"][0].update(original_page_useful=False,
                                    exact_visible_cue_useful=False)
    changed["judgments"][1]["uncertain"] = True
    _save(second, changed)
    result = comparison.compare(blind, sha, first, second)
    assert result["disagreed_candidates"] == 1
    assert result["uncertain_candidates"] == 1
    assert len(result["unresolved"]) == 2
    assert result["fully_agreed_without_uncertainty"] is False


def test_missing_or_wrong_packet_review_is_refused(packets):
    blind, sha, first, second = packets
    changed = json.loads(second.read_bytes())
    changed["judgments"].pop()
    _save(second, changed)
    with pytest.raises(comparison.ReviewError, match="review_incomplete_or_wrong_packet"):
        comparison.compare(blind, sha, first, second)
    with pytest.raises(comparison.ReviewError, match="packet_identity_invalid"):
        comparison.compare(blind, "0" * 64, first, second)
