"""Blind review packets must not reveal an author's provisional labels."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import build_reading_usefulness_blind_review as blind


def _draft(path: Path) -> str:
    group = {
        "id": "train-1", "split": "train", "relation_family": "definition",
        "question_form": "direct", "question": "What does the concept mean?",
        "prior_question_context_if_followup": None,
        "source_document_sha256": "a" * 64,
        "source_document_path_author_aid": "lec10.pdf",
        "four_exact_candidate_windows": ["one", "two", "three", "four"],
        "page_number_and_text_offsets_for_each_window": [
            {"page_number": number, "start": 0, "end": len(window),
             "page_text_sha256": "b" * 64}
            for number, window in enumerate(("one", "two", "three", "four"), 1)
        ],
        "original_page_usefulness_per_window": [True, False, False, False],
        "exact_cue_usefulness_per_window": [True, False, False, False],
    }
    packet = {
        "status": "author_only_pending_independent_blind_review_and_adjudication_no_model_score",
        "corpus_id": "public", "manifest_sha256": "c" * 64,
        "groups": [group],
    }
    raw = json.dumps(packet).encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def test_packet_omits_proposed_labels_and_requires_exact_draft(tmp_path, monkeypatch):
    monkeypatch.setattr(blind, "gettempdir", lambda: str(tmp_path))
    source = tmp_path / "draft.json"
    expected = _draft(source)
    output = tmp_path / "blind.json"
    mapping = tmp_path / "mapping.json"
    result = blind.project(source, output, mapping, expected)
    assert result["groups"] == 1 and result["candidates"] == 4
    projected = json.loads(output.read_bytes())
    assert "exact_cue_usefulness_per_window" not in output.read_text(encoding="utf-8")
    assert "original_page_usefulness_per_window" not in output.read_text(encoding="utf-8")
    assert {candidate["exact_window"] for candidate in projected["groups"][0]["candidates"]} == {
        "one", "two", "three", "four"}
    assert projected["groups"][0]["id"].startswith("g_")
    assert "train-1" not in output.read_text(encoding="utf-8")
    assert "train-1" in mapping.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="author_draft_identity_invalid"):
        blind.project(source, tmp_path / "other.json", tmp_path / "other-map.json",
                      "0" * 64)
    with pytest.raises(ValueError, match="temp_input_or_output_invalid"):
        blind.project(source, output, mapping, expected)


def test_packet_refuses_non_temp_output(tmp_path, monkeypatch):
    monkeypatch.setattr(blind, "gettempdir", lambda: str(tmp_path / "other"))
    source = tmp_path / "draft.json"
    expected = _draft(source)
    with pytest.raises(ValueError, match="temp_input_or_output_invalid"):
        blind.project(source, tmp_path / "blind.json", tmp_path / "map.json", expected)


def test_eval_author_schema_still_omits_all_provisional_labels(tmp_path, monkeypatch):
    monkeypatch.setattr(blind, "gettempdir", lambda: str(tmp_path))
    source = tmp_path / "eval-draft.json"
    _draft(source)
    packet = json.loads(source.read_bytes())
    packet["status"] = (
        "AUTHOR DRAFT ONLY; provisional labels; no independent reviews, "
        "rights review, adjudication, freeze, or model score")
    group = packet["groups"][0]
    group["source_pdf"] = group.pop("source_document_path_author_aid")
    group["author_notes_per_window"] = ["provisional" for _ in range(4)]
    raw = json.dumps(packet).encode("utf-8")
    source.write_bytes(raw)
    output = tmp_path / "eval-blind.json"
    blind.project(source, output, tmp_path / "eval-map.json",
                  hashlib.sha256(raw).hexdigest())
    projected = json.loads(output.read_bytes())
    assert projected["groups"][0]["source_document_path_author_aid"] == "lec10.pdf"
    assert "author_notes_per_window" not in output.read_text(encoding="utf-8")
    assert "usefulness_per_window" not in output.read_text(encoding="utf-8")
