"""Synthetic review bridging must carry only identical cues and remain blind."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import bridge_reading_usefulness_reviews as bridge
import build_reading_usefulness_blind_review as blind


def _save(path: Path, value: dict) -> dict[str, str]:
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.write_bytes(raw)
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}


def _draft() -> dict:
    groups = []
    for number in range(96):
        windows = [f"synthetic cue {number} {index}" for index in range(4)]
        groups.append({
            "id": f"train-{number:03}", "split": "train",
            "relation_family": "definition", "question_form": "direct",
            "question": f"What is synthetic concept {number}?",
            "prior_question_context_if_followup": None,
            "question_template_id": f"synthetic-template-{number}",
            "question_template": "What is the synthetic concept?",
            "source_document_sha256": "a" * 64,
            "source_document_path_author_aid": "lec10.pdf",
            "authored_by": "synthetic_author",
            "four_exact_candidate_windows": windows,
            "page_number_and_text_offsets_for_each_window": [
                {"page_number": index + 1, "start": 0, "end": len(window),
                 "page_text_sha256": "b" * 64}
                for index, window in enumerate(windows)
            ],
            "original_page_usefulness_per_window": [True, False, False, False],
            "exact_cue_usefulness_per_window": [True, False, False, False],
            "author_notes_per_window": ["AUTHOR_LABEL_SENTINEL"] * 4,
        })
    return {
        "status": "author_only_pending_independent_blind_review_and_adjudication_no_model_score",
        "corpus_id": "synthetic-public", "manifest_sha256": "c" * 64,
        "groups": groups,
    }


def _blind(tmp_path: Path, name: str, draft_ref: dict[str, str]) -> tuple[dict, dict]:
    packet_path = tmp_path / f"{name}-blind.json"
    mapping_path = tmp_path / f"{name}-mapping.json"
    blind.project(Path(draft_ref["path"]), packet_path, mapping_path,
                  draft_ref["sha256"])
    return ({"path": str(packet_path),
             "sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest()},
            {"path": str(mapping_path),
             "sha256": hashlib.sha256(mapping_path.read_bytes()).hexdigest()})


@pytest.fixture
def case(tmp_path, monkeypatch):
    monkeypatch.setattr(blind, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(bridge, "gettempdir", lambda: str(tmp_path))
    old = _draft()
    new = copy.deepcopy(old)
    changed = new["groups"][7]
    changed["four_exact_candidate_windows"][2] = "new synthetic cue only"
    changed["page_number_and_text_offsets_for_each_window"][2]["end"] = len(
        changed["four_exact_candidate_windows"][2])
    old_ref = _save(tmp_path / "old-draft.json", old)
    new_ref = _save(tmp_path / "new-draft.json", new)
    old_blind, old_mapping = _blind(tmp_path, "old", old_ref)
    new_blind, new_mapping = _blind(tmp_path, "new", new_ref)
    config = {
        "schema": "cardchemy_reading_review_bridge_config_v1", "scope": "train",
        "old_draft": old_ref, "old_blind": old_blind, "old_mapping": old_mapping,
        "new_draft": new_ref, "new_blind": new_blind, "new_mapping": new_mapping,
        "allowed_question_rewrites": [],
    }
    return tmp_path, config


def _review(packet: dict, packet_sha: str, reviewer: str,
            useful_ids: set[str]) -> dict:
    rows = []
    for group in packet["groups"]:
        for candidate in group["candidates"]:
            useful = candidate["id"] in useful_ids
            rows.append({
                "id": candidate["id"], "group_id": group["id"],
                "source_pdf": group["source_document_path_author_aid"],
                "page_number": candidate["source_offset"]["page_number"],
                "original_page_useful": useful,
                "exact_visible_cue_useful": useful,
                "uncertain": False, "reason": "synthetic independent judgment",
            })
    return {"reviewer_id": reviewer, "packet_sha256": packet_sha,
            "reviewed_group_count": len(packet["groups"]),
            "reviewed_candidate_count": len(rows), "judgments": rows}


def _adjudication(packet_sha: str, reviews: list[dict], cid: str) -> dict:
    return {
        "schema": "cardchemy_reading_usefulness_adjudication_v1",
        "blind_packet_sha256": packet_sha,
        "review_sha256": sorted(row["sha256"] for row in reviews),
        "rows": [{"candidate_id": cid, "adjudicator_id": "synthetic_adjudicator",
                  "original_page_useful": True, "exact_cue_useful": True,
                  "resolution_reason": "synthetic original page reviewed"}],
    }


def test_project_and_merge_carry_only_unchanged_judgments(case, monkeypatch, capsys):
    tmp_path, config = case
    config_ref = _save(tmp_path / "bridge-config.json", config)
    delta_path = tmp_path / "delta.json"
    bridge_path = tmp_path / "bridge-map.json"
    monkeypatch.setattr(sys, "argv", [
        "bridge", "project", "--config", config_ref["path"],
        "--config-sha256", config_ref["sha256"],
        "--delta-output", str(delta_path), "--bridge-output", str(bridge_path),
    ])
    assert bridge.main() == 0
    project_receipt = json.loads(capsys.readouterr().out)
    assert (project_receipt["changed_candidates"],
            project_receipt["carried_candidates"]) == (1, 383)
    delta = json.loads(delta_path.read_bytes())
    bridge_map = json.loads(bridge_path.read_bytes())
    assert len(delta["groups"]) == 1
    assert len(delta["groups"][0]["candidates"]) == 1
    assert "AUTHOR_LABEL_SENTINEL" not in delta_path.read_text(encoding="utf-8")
    assert "authored_by" not in delta_path.read_text(encoding="utf-8")
    assert "usefulness_per_window" not in delta_path.read_text(encoding="utf-8")
    assert "author_candidate_index" not in delta_path.read_text(encoding="utf-8")

    changed_link = next(row for row in bridge_map["links"] if row["changed"])
    carried_link = next(row for row in bridge_map["links"] if not row["changed"])
    old_packet = json.loads(Path(config["old_blind"]["path"]).read_bytes())
    old_a = _save(tmp_path / "old-a.json", _review(
        old_packet, config["old_blind"]["sha256"], "old_reviewer_a",
        {carried_link["old_candidate_id"]}))
    old_b = _save(tmp_path / "old-b.json", _review(
        old_packet, config["old_blind"]["sha256"], "old_reviewer_b", set()))
    old_adj = _save(tmp_path / "old-adj.json", _adjudication(
        config["old_blind"]["sha256"], [old_a, old_b],
        carried_link["old_candidate_id"]))
    delta_sha = hashlib.sha256(delta_path.read_bytes()).hexdigest()
    delta_a = _save(tmp_path / "delta-a.json", _review(
        delta, delta_sha, "delta_reviewer_a", {changed_link["new_candidate_id"]}))
    delta_b = _save(tmp_path / "delta-b.json", _review(
        delta, delta_sha, "delta_reviewer_b", set()))
    delta_adj = _save(tmp_path / "delta-adj.json", _adjudication(
        delta_sha, [delta_a, delta_b], changed_link["new_candidate_id"]))
    merge_config = {
        "schema": "cardchemy_reading_review_merge_config_v1",
        "bridge_config": config_ref,
        "delta_packet": {"path": str(delta_path), "sha256": delta_sha},
        "bridge_map": {"path": str(bridge_path),
                       "sha256": hashlib.sha256(bridge_path.read_bytes()).hexdigest()},
        "old_review_a": old_a, "old_review_b": old_b,
        "old_adjudication": old_adj,
        "delta_review_a": delta_a, "delta_review_b": delta_b,
        "delta_adjudication": delta_adj,
    }
    merge_ref = _save(tmp_path / "merge-config.json", merge_config)
    outputs = [tmp_path / name for name in (
        "complete-a.json", "complete-b.json", "complete-adj.json", "receipt.json")]
    monkeypatch.setattr(sys, "argv", [
        "bridge", "merge", "--config", merge_ref["path"],
        "--config-sha256", merge_ref["sha256"],
        "--review-a-output", str(outputs[0]),
        "--review-b-output", str(outputs[1]),
        "--adjudication-output", str(outputs[2]),
        "--receipt-output", str(outputs[3]),
    ])
    assert bridge.main() == 0
    capsys.readouterr()
    complete_a, complete_b, adjudication, receipt = [
        json.loads(path.read_bytes()) for path in outputs]
    assert len(complete_a["judgments"]) == len(complete_b["judgments"]) == 384
    assert complete_a["packet_sha256"] == config["new_blind"]["sha256"]
    by_a = {row["id"]: row for row in complete_a["judgments"]}
    by_b = {row["id"]: row for row in complete_b["judgments"]}
    assert by_a[carried_link["new_candidate_id"]]["exact_visible_cue_useful"]
    assert not by_b[carried_link["new_candidate_id"]]["exact_visible_cue_useful"]
    assert by_a[changed_link["new_candidate_id"]]["exact_visible_cue_useful"]
    assert not by_b[changed_link["new_candidate_id"]]["exact_visible_cue_useful"]
    assert {row["candidate_id"] for row in adjudication["rows"]} == {
        carried_link["new_candidate_id"], changed_link["new_candidate_id"]}
    assert receipt["carried_candidates"] == 383
    assert receipt["newly_reviewed_candidates"] == 1
    assert receipt["actual_old_reviewer_ids"] == ["old_reviewer_a", "old_reviewer_b"]
    assert receipt["actual_delta_reviewer_ids"] == ["delta_reviewer_a", "delta_reviewer_b"]
    assert all("AUTHOR_LABEL_SENTINEL" not in path.read_text(encoding="utf-8")
               for path in outputs)

    # A correctly repinned but wrong page identity still cannot be merged.
    wrong_review = json.loads(Path(delta_a["path"]).read_bytes())
    wrong_review["judgments"][0]["page_number"] += 1
    wrong_ref = _save(tmp_path / "wrong-delta-a.json", wrong_review)
    wrong_adjudication = _adjudication(
        delta_sha, [wrong_ref, delta_b], changed_link["new_candidate_id"])
    wrong_config = {**merge_config,
                    "delta_review_a": wrong_ref,
                    "delta_adjudication": _save(
                        tmp_path / "wrong-delta-adj.json", wrong_adjudication)}
    with pytest.raises(bridge.BridgeError, match="review_row"):
        bridge.merge(wrong_config)


def test_project_requires_new_review_for_offset_only_change(case):
    tmp_path, config = case
    revised = json.loads(Path(config["old_draft"]["path"]).read_bytes())
    revised["groups"][7]["page_number_and_text_offsets_for_each_window"][2][
        "page_number"] = 8
    config["new_draft"] = _save(tmp_path / "offset-draft.json", revised)
    config["new_blind"], config["new_mapping"] = _blind(
        tmp_path, "offset", config["new_draft"])
    packet, mapping, _ = bridge.derive(config)
    assert len(packet["groups"]) == 1
    assert len(packet["groups"][0]["candidates"]) == 1
    assert sum(row["changed"] for row in mapping["links"]) == 1


def test_project_requires_registered_question_rewrite_and_rereviews_all_four(case):
    tmp_path, config = case
    revised = json.loads(Path(config["old_draft"]["path"]).read_bytes())
    revised["groups"][7]["question"] = "What is the revised synthetic concept?"
    config["new_draft"] = _save(tmp_path / "rewrite-draft.json", revised)
    config["new_blind"], config["new_mapping"] = _blind(
        tmp_path, "rewrite", config["new_draft"])
    with pytest.raises(bridge.BridgeError, match="unregistered_question_rewrite"):
        bridge.derive(config)
    config["allowed_question_rewrites"] = [["train-007", "train-007"]]
    packet, mapping, _ = bridge.derive(config)
    assert len(packet["groups"]) == 1
    assert len(packet["groups"][0]["candidates"]) == 4
    assert sum(row["changed"] for row in mapping["links"]) == 4


@pytest.mark.parametrize("location", ["group", "candidate", "offset"])
def test_project_rejects_author_label_added_to_blind_packet(case, location):
    tmp_path, config = case
    tampered = json.loads(Path(config["new_blind"]["path"]).read_bytes())
    group = tampered["groups"][0]
    candidate = group["candidates"][0]
    target = {"group": group, "candidate": candidate,
              "offset": candidate["source_offset"]}[location]
    target["author_proposed_label"] = "AUTHOR_LABEL_SENTINEL"
    config["new_blind"] = _save(tmp_path / f"tampered-{location}.json", tampered)
    mapping = json.loads(Path(config["new_mapping"]["path"]).read_bytes())
    mapping["blind_packet_sha256"] = config["new_blind"]["sha256"]
    config["new_mapping"] = _save(tmp_path / f"tampered-map-{location}.json", mapping)
    with pytest.raises(bridge.BridgeError, match="projection_groups|projection_candidates"):
        bridge.derive(config)


def test_project_rejects_reused_candidate_id_across_groups(case):
    tmp_path, config = case
    tampered = json.loads(Path(config["new_blind"]["path"]).read_bytes())
    first, second = tampered["groups"][:2]
    duplicate = first["candidates"][0]["id"]
    original = second["candidates"][0]["id"]
    second["candidates"][0]["id"] = duplicate
    config["new_blind"] = _save(tmp_path / "duplicate-blind.json", tampered)
    mapping = json.loads(Path(config["new_mapping"]["path"]).read_bytes())
    mapping["blind_packet_sha256"] = config["new_blind"]["sha256"]
    for group in mapping["groups"]:
        for candidate in group["candidates"]:
            if candidate["opaque_candidate_id"] == original:
                candidate["opaque_candidate_id"] = duplicate
    config["new_mapping"] = _save(tmp_path / "duplicate-map.json", mapping)
    with pytest.raises(bridge.BridgeError, match="projection_candidates"):
        bridge.derive(config)
