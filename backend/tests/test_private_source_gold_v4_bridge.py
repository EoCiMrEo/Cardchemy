"""Synthetic only: stage-1 gold, authorized revisions, v4 slate and cue labels."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from uuid import UUID

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
import bridge_private_source_gold_v4 as bridge


def _bytes(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _uuid(value: int) -> str:
    return str(UUID(int=value))


def _synthetic_inputs() -> dict:
    documents = {
        slot: {
            "document_id": _uuid(slot),
            "content_revision_id": _uuid(10 + slot),
            "index_revision_id": _uuid(20 + slot),
            "original_pdf_sha256": _sha(f"synthetic-pdf-{slot}".encode()),
            "original_pdf_page_count": 20,
        } for slot in (1, 2, 3)
    }
    stage_cases = []
    roster_cases = []
    label_cases = []
    pages = []
    slates = []
    forms = ["direct"] * 4 + ["paraphrase"] * 4 + ["followup"] * 4
    for index, form in enumerate(forms, 1):
        slot = 1 + (index - 1) % 3
        document = documents[slot]
        page_text = f"Synthetic page {index}: the method relates input {index} to output {index}."
        page_key = bridge._digest([document["document_id"], index])
        case_id = f"T{index:02}"
        stage_cases.append({
            "case_id": case_id, "form": form,
            "question": f"How does synthetic method {index} work?",
            "previous_turn": "Which method is in view?" if form == "followup" else "",
            "document_slot": slot, "page_number": index, "page_useful": "Yes",
            "page_sha256": _sha(page_text.encode()), "page_key": page_key,
            **document,
        })
        pages.append({
            **document, "page_number": index, "page_text": page_text,
            "corpus_revision": 7, "embedding_space_hash": "e" * 64,
            "current_authorized": True, "published": True, "index_ready": True,
        })
        cue_sha = _sha(page_text.encode())
        candidate = {"id": "C1", "page_key": page_key, "cue_sha256": cue_sha}
        roster_cases.append({
            "case_id": case_id, "cohort": "holdout", "form": form,
            "gold_page_key": page_key, "candidates": [candidate],
        })
        label_cases.append({
            "case_id": case_id, "candidates": [
                {**candidate, "page_useful": "Yes", "cue_useful": "Yes"}
            ],
        })
        slates.append({
            "case_id": case_id, "candidates": [{
                "runtime_id": "S01", "document_id": document["document_id"],
                "page_number": index, "start_offset": 0, "end_offset": len(page_text),
            }],
        })
    return {
        "stage1": {
            "schema": bridge.SCHEMA,
            "authored_input_sha256": "a" * 64,
            "reviewer_kind": "agent_self_review",
            "review_method": "authenticated_original_pdf_browser",
            "candidate_selection_seen": False,
            "frozen_at_utc": "2026-09-29T00:00:00Z",
            "scope": {"corpus_revision": 7, "embedding_space_hash": "e" * 64},
            "cases": stage_cases,
        },
        "roster": {
            "schema": "source_judgment_display_v4_roster",
            "policy": "related_knowledge_navigation_v4",
            "component": "private_holdout", "runtime_build_sha256": "b" * 64,
            "frozen_at_utc": "2026-09-29T00:01:00Z",
            "stage1_roster_sha256": "",
            "cases": roster_cases,
        },
        "labels": {
            "schema": "source_judgment_display_v4_labels",
            "component": "private_holdout", "roster_sha256": "",
            "reviewer_kind": "independent_reviewer", "reviewer_id": "synthetic_reviewer",
            "independent_of_runtime_selection": True,
            "original_pdf_inspected": True,
            "frozen_at_utc": "2026-09-29T00:02:00Z",
            "runtime_evaluated": False, "cases": label_cases,
        },
        "pages": pages, "slates": slates,
    }


def _validate(data: dict, *, stage1_sha256: str | None = None) -> dict:
    stage1_bytes = _bytes(data["stage1"])
    data["roster"]["stage1_roster_sha256"] = _sha(stage1_bytes)
    roster_bytes = _bytes(data["roster"])
    data["labels"]["roster_sha256"] = _sha(roster_bytes)
    labels_bytes = _bytes(data["labels"])
    return bridge.validate_bridge(
        stage1_bytes=stage1_bytes,
        stage1_sha256=stage1_sha256 or _sha(stage1_bytes),
        roster_bytes=roster_bytes, roster_sha256=_sha(roster_bytes),
        labels_bytes=labels_bytes, labels_sha256=_sha(labels_bytes),
        authorized_pages=data["pages"], slates=data["slates"],
    )


def test_binds_synthetic_gold_revision_slate_and_exact_cue_labels():
    result = _validate(_synthetic_inputs())
    assert result["gold_pages_bound"] == 12
    assert result["candidates_bound"] == 12
    assert len(result["stage1_sha256"]) == 64
    assert result["release_gate_passed"] is False
    assert "Synthetic page" not in json.dumps(result)


def test_default_cli_is_preflight_without_private_or_database_reads():
    result = subprocess.run([sys.executable, str(SCRIPT_DIR / "bridge_private_source_gold_v4.py")],
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == {
        "schema": "private_source_gold_v4_bridge_v1", "status": "preflight_only",
        "database_reads": 0, "provider_requests": 0, "release_gate_passed": False,
    }


def test_rejects_changed_stage1_bytes_even_with_matching_roster_claim():
    with pytest.raises(bridge.InvalidBridge, match="stage1_digest_changed"):
        _validate(_synthetic_inputs(), stage1_sha256="0" * 64)


def test_rejects_false_stage1_sha_in_candidate_roster():
    data = _synthetic_inputs()
    stage_bytes = _bytes(data["stage1"])
    data["roster"]["stage1_roster_sha256"] = "0" * 64
    roster_bytes = _bytes(data["roster"])
    data["labels"]["roster_sha256"] = _sha(roster_bytes)
    label_bytes = _bytes(data["labels"])
    with pytest.raises(bridge.InvalidBridge, match="stage1_roster_mismatch"):
        bridge.validate_bridge(
            stage1_bytes=stage_bytes, stage1_sha256=_sha(stage_bytes),
            roster_bytes=roster_bytes, roster_sha256=_sha(roster_bytes),
            labels_bytes=label_bytes, labels_sha256=_sha(label_bytes),
            authorized_pages=data["pages"], slates=data["slates"],
        )


def test_second_issued_page_requires_its_own_exact_cue_label():
    data = _synthetic_inputs()
    other = data["pages"][1]
    key = bridge._digest([other["document_id"], other["page_number"]])
    identity = {"id": "C2", "page_key": key,
                "cue_sha256": _sha(other["page_text"].encode())}
    data["roster"]["cases"][0]["candidates"].append(identity)
    data["labels"]["cases"][0]["candidates"].append({
        **identity, "page_useful": "No", "cue_useful": "No",
    })
    data["slates"][0]["candidates"].append({
        "runtime_id": "S02", "document_id": other["document_id"],
        "page_number": other["page_number"],
        "start_offset": 0, "end_offset": len(other["page_text"]),
    })
    assert _validate(data)["candidates_bound"] == 13
    data["labels"]["cases"][0]["candidates"].pop()
    with pytest.raises(bridge.InvalidBridge, match="invalid_v4_roster_or_labels"):
        _validate(data)


@pytest.mark.parametrize("change,code", [
    (lambda d: d["roster"]["cases"][0].update(gold_page_key="0" * 64),
     "gold_case_changed"),
    (lambda d: d["roster"]["cases"][0].update(form="paraphrase"),
     "invalid_v4_roster_or_labels"),
    (lambda d: d["stage1"]["cases"][0].update(original_pdf_sha256="0" * 64),
     "inconsistent_stage1_revision"),
    (lambda d: d["pages"][0].update(content_revision_id=_uuid(99)),
     "source_revision_changed"),
    (lambda d: d["pages"][0].update(index_revision_id=_uuid(99)),
     "source_revision_changed"),
    (lambda d: d["pages"][0].update(original_pdf_sha256="0" * 64),
     "source_revision_changed"),
    (lambda d: d["pages"][0].update(current_authorized=False),
     "source_not_current"),
    (lambda d: d["pages"][0].update(published=False),
     "source_not_current"),
    (lambda d: d["pages"][0].update(corpus_revision=8),
     "source_not_current"),
    (lambda d: d["pages"][0].update(page_text="Changed canonical page"),
     "gold_page_changed"),
    (lambda d: d["slates"][0]["candidates"][0].update(end_offset=5),
     "candidate_identity_changed"),
    (lambda d: d["slates"][0]["candidates"][0].update(runtime_id="S02"),
     "invalid_candidate_slice"),
    (lambda d: d["labels"]["cases"][0]["candidates"][0].update(cue_sha256="0" * 64),
     "invalid_v4_roster_or_labels"),
])
def test_refuses_unbound_gold_source_cue_or_label(change, code):
    data = deepcopy(_synthetic_inputs())
    change(data)
    with pytest.raises(bridge.InvalidBridge, match=code):
        _validate(data)
