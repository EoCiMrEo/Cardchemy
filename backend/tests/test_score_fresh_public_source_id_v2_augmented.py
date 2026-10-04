"""Synthetic-only contracts for all-group augmented source-ID scoring."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "scripts"))
import score_fresh_public_source_id_v2_augmented as scorer  # noqa: E402


def _write(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = scorer.canonical_bytes(value)
    path.write_bytes(raw)
    return scorer.digest(raw)


def _write_lines(path: Path, rows: list[dict]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = b"".join(scorer.canonical_bytes(row) for row in rows)
    path.write_bytes(raw)
    return scorer.digest(raw)


def _split_payload(split: str) -> tuple[dict, dict]:
    docs = [{"document_id": f"{split}-doc-{number}",
             "sha256": scorer.digest(f"{split}-pdf-{number}".encode()),
             "pages": 40} for number in range(4)]
    groups = []
    label_groups = []
    forms = ["direct", "paraphrase", "followup", "no_useful"]
    reserve_per_form = (scorer.SPLIT_GROUPS[split] - 48) // 3
    for number in range(scorer.SPLIT_GROUPS[split]):
        original = number < 48
        form = forms[number // 12] if original else forms[(number - 48) // reserve_per_form]
        # Keep the original 48 and every reserve item, including hard items.
        available = (4 if split == "calibration" and number in (48, 49)
                     else 0 if form == "no_useful" else number % 3 + 1)
        candidates = []
        labels = []
        for index in range(4):
            context = f"Exact page evidence for {split} group {number} page {index}."
            cue = "Exact page evidence"
            candidates.append({
                "id": f"S{index + 1:02d}",
                "document_id": docs[index % 2]["document_id"],
                "page": index + 1,
                "context_start": 0, "context_end": len(context),
                "context": context,
                "cue_start": 0, "cue_end": len(cue), "cue": cue,
                "page_text_sha256": scorer.digest(context.encode()),
            })
            labels.append({"id": f"S{index + 1:02d}",
                           "page_useful": index < available,
                           "cue_useful": index < available})
        group_id = f"G{number + 1:03d}"
        groups.append({"group_id": group_id, "question": f"Question {number} là gì?",
                       "candidates": candidates})
        label_groups.append({"group_id": group_id,
                             "author_group_id": f"auth-{split}-{number}",
                             "form": form,
                             "origin": "original" if original else "reserve",
                             "candidates": labels})
    manifest_sha = scorer.digest(b"fresh manifest")
    packet = {"schema_version": scorer.PACKET_SCHEMA, "corpus_id": "synthetic-fresh-v2",
              "source_manifest_sha256": manifest_sha, "split": split,
              "documents": docs, "groups": groups}
    labels = {"schema_version": scorer.LABEL_SCHEMA,
              "corpus_id": "synthetic-fresh-v2",
              "source_manifest_sha256": manifest_sha, "split": split,
              "packet_sha256": scorer.digest(scorer.canonical_bytes(packet)),
              "reviewer_ids": ["reviewer-a", "reviewer-b", "reviewer-c", "reviewer-d"],
              "adjudicator_id": ["reviewer-e", "reviewer-f"],
              "disagreement_count": 0,
              "groups": label_groups}
    return packet, labels


def _freeze(tmp_path: Path) -> Path:
    frozen = tmp_path / "frozen"
    files = {}
    for split in scorer.SPLITS:
        packet, labels = _split_payload(split)
        files[f"{split}/packet.json"] = _write(frozen / split / "packet.json", packet)
        files[f"{split}/labels.json"] = _write(frozen / split / "labels.json", labels)
    _write(frozen / "freeze.json", {
        "schema_version": scorer.FREEZE_SCHEMA,
        "corpus_id": "synthetic-fresh-v2",
        "source_manifest_sha256": scorer.digest(b"fresh manifest"),
        "overlap_diagnostic_sha256": scorer.digest(b"synthetic-overlap-diagnostic"),
        "input_sha256": {name: scorer.digest(name.encode()) for name in
                         ("original_authored", "original_review_a",
                          "original_review_b", "original_adjudication",
                          "reserve_authored", "reserve_blind_packet",
                          "reserve_mapping", "reserve_blind_review_a",
                          "reserve_blind_review_b", "reserve_blind_adjudication",
                          "overlap_review")},
        "files": files,
    })
    return frozen


def _results(tmp_path: Path, frozen: Path, split: str,
             *, fail_groups: set[str] = frozenset(),
             choices: dict[str, list[str] | str] | None = None) -> Path:
    choices = choices or {}
    results = tmp_path / f"{split}-results"
    packet = json.loads((frozen / split / "packet.json").read_bytes())
    labels = json.loads((frozen / split / "labels.json").read_bytes())
    by_label = {row["group_id"]: row for row in labels["groups"]}
    responses, usage, errors = [], [], []
    for index, group in enumerate(packet["groups"]):
        group_id = group["group_id"]
        wire = scorer.build_exhaustive_public_wire(
            group["question"], [{"id": row["id"], "page": row["page"],
                                 "page_text": row["context"], "cue": row["cue"]}
                                for row in group["candidates"]])
        request_sha = scorer.digest(scorer.canonical_wire_bytes(wire))
        attempt_sha = scorer.digest(f"{split}-{index}-attempt".encode())
        common = {"group_id": group_id, "request_sha256": request_sha,
                  "attempt_sha256": attempt_sha}
        if group_id in fail_groups:
            errors.append({**common, "reason": "provider_timeout",
                           "failed_attempt_cost_unknown": True,
                           "model": "future-public-model"})
            continue
        selected = [row["id"] for row in by_label[group_id]["candidates"]
                    if row["page_useful"] and row["cue_useful"]][:3]
        chosen = choices.get(group_id, selected)
        raw_json = chosen if isinstance(chosen, str) else json.dumps(
            {"selected_ids": chosen}, separators=(",", ":"))
        responses.append({**common, "raw_json": raw_json,
                          "model": "future-public-model"})
        usage.append({**common, "finish_reason": "STOP",
                      "input_tokens": 1_000, "output_tokens": 20,
                      "model": "future-public-model"})
    files = {
        "response-ids.jsonl": _write_lines(results / "response-ids.jsonl", responses),
        "usage-receipts.jsonl": _write_lines(results / "usage-receipts.jsonl", usage),
        "errors.jsonl": _write_lines(results / "errors.jsonl", errors),
    }
    _write(results / "evaluation.json", {
        "schema_version": scorer.EVALUATION_SCHEMA, "split": split,
        "freeze_sha256": scorer.digest((frozen / "freeze.json").read_bytes()),
        "packet_sha256": scorer.digest((frozen / split / "packet.json").read_bytes()),
        "labels_sha256": scorer.digest((frozen / split / "labels.json").read_bytes()),
        "candidate_version": scorer.SOURCE_ID_CANDIDATE_VERSION,
        "prototype_sha256": scorer.digest((_ROOT / "scripts" /
            "prototype_exhaustive_source_id_v2.py").read_bytes()),
        "parser_sha256": scorer.digest((_ROOT / "backend" / "app" / "ai" /
            "source_judgment.py").read_bytes()),
        "scorer_sha256": scorer.digest(Path(scorer.__file__).read_bytes()),
        "model": "future-public-model", "thinking": "low",
        "automatic_retries": 0, "files": files,
    })
    return results


def test_passes_fresh_calibration_then_disjoint_heldout(tmp_path: Path) -> None:
    frozen = _freeze(tmp_path)
    calibration = _results(tmp_path, frozen, "calibration")
    heldout = _results(tmp_path, frozen, "heldout")
    result = scorer.score_run(frozen, calibration, heldout)
    assert result["calibration_passed"] is True
    assert result["heldout_opened"] is True
    assert result["heldout_passed"] is True
    assert result["release_gate_passed"] is False
    assert result["heldout"]["metrics"]["counts"]["groups"] == 60
    assert result["heldout"]["metrics"]["counts"]["displayed_cards"] == 96


def test_calibration_false_no_useful_display_keeps_heldout_unopened(tmp_path: Path) -> None:
    frozen = _freeze(tmp_path)
    calibration = _results(tmp_path, frozen, "calibration",
                           choices={"G037": ["S01"]})
    result = scorer.score_run(frozen, calibration, tmp_path / "missing-heldout")
    assert result["calibration_passed"] is False
    assert result["heldout_opened"] is False
    assert result["calibration"]["metrics"]["counts"]["false_no_useful_displays"] == 1


def test_two_transport_failures_are_misses_but_n_minus_two_valid_can_pass(tmp_path: Path) -> None:
    frozen = _freeze(tmp_path)
    calibration = _results(tmp_path, frozen, "calibration",
                           fail_groups={"G001", "G002"})
    result = scorer.score_run(frozen, calibration)
    counts = result["calibration"]["metrics"]["counts"]
    assert result["calibration_passed"] is True
    assert counts["accepted_responses"] == 64
    assert counts["positive_hit_at_three"] == 52
    assert counts["provider_failed_groups"] == 2
    assert counts["failed_attempt_cost_unknown"] is True


def test_three_transport_failures_break_availability(tmp_path: Path) -> None:
    frozen = _freeze(tmp_path)
    calibration = _results(tmp_path, frozen, "calibration",
                           fail_groups={"G037", "G038", "G039"})
    result = scorer.score_run(frozen, calibration)
    assert result["calibration_passed"] is False
    assert result["calibration"]["metrics"]["availability_passed"] is False
    assert result["calibration"]["metrics"]["counts"]["valid_no_useful_abstentions"] == 9


def test_invalid_foreign_id_is_not_no_match(tmp_path: Path) -> None:
    frozen = _freeze(tmp_path)
    calibration = _results(tmp_path, frozen, "calibration",
                           choices={"G037": '{"selected_ids":["S99"]}'})
    result = scorer.score_run(frozen, calibration)
    assert result["calibration_passed"] is False
    assert result["calibration"]["metrics"]["counts"]["invalid_model_outputs"] == 1
    assert result["calibration"]["metrics"]["counts"]["valid_no_useful_abstentions"] == 11


def test_all_displayed_precision_counts_weak_positive_cards(tmp_path: Path) -> None:
    frozen = _freeze(tmp_path)
    choices = {f"G{number:03d}": ["S01", "S02", "S03"]
               for number in range(1, 37, 3)}
    calibration = _results(tmp_path, frozen, "calibration", choices=choices)
    result = scorer.score_run(frozen, calibration)
    metrics = result["calibration"]["metrics"]
    assert metrics["counts"]["positive_hit_at_three"] == 54
    assert metrics["counts"]["false_no_useful_displays"] == 0
    assert metrics["displayed_cue_and_page_useful_fraction"] < 0.9
    assert result["calibration_passed"] is False


def test_response_receipt_hash_change_fails_closed(tmp_path: Path) -> None:
    frozen = _freeze(tmp_path)
    calibration = _results(tmp_path, frozen, "calibration")
    with (calibration / "response-ids.jsonl").open("ab") as stream:
        stream.write(b"\n")
    with pytest.raises(scorer.ScoreError):
        scorer.score_run(frozen, calibration)


def test_wrong_model_or_retries_binding_fails_closed(tmp_path: Path) -> None:
    frozen = _freeze(tmp_path)
    calibration = _results(tmp_path, frozen, "calibration")
    path = calibration / "evaluation.json"
    evaluation = json.loads(path.read_bytes())
    evaluation["automatic_retries"] = 1
    _write(path, evaluation)
    with pytest.raises(scorer.ScoreError, match="evaluation_binding_invalid"):
        scorer.score_run(frozen, calibration)


def test_completed_no_useful_groups_must_abstain(tmp_path: Path) -> None:
    frozen = _freeze(tmp_path)
    calibration = _results(tmp_path, frozen, "calibration",
                           fail_groups={"G037", "G038"})
    result = scorer.score_run(frozen, calibration)
    metrics = result["calibration"]["metrics"]
    assert metrics["counts"]["valid_no_useful_abstentions"] == 10
    assert metrics["counts"]["completed_negative_groups"] == 10
    assert result["calibration_passed"] is True


def test_same_count_with_weak_ids_fails_heldout_cardinality(tmp_path: Path) -> None:
    frozen = _freeze(tmp_path)
    calibration = _results(tmp_path, frozen, "calibration")
    # Seven two-useful groups display one truly useful and one weak page.
    # Hit, useful-first, >=60 useful cards, and >=90% displayed precision
    # still pass; exact useful-ID cardinality must reject the split.
    wrong = {f"G{number:03d}": ["S01", "S03"]
             for number in (2, 5, 8, 11, 14, 17, 20)}
    heldout = _results(tmp_path, frozen, "heldout", choices=wrong)
    result = scorer.score_run(frozen, calibration, heldout)
    metrics = result["heldout"]["metrics"]
    assert result["calibration_passed"] is True
    assert metrics["counts"]["positive_hit_at_three"] == 48
    assert metrics["counts"]["useful_first"] == 48
    assert metrics["counts"]["displayed_useful_cues_and_pages"] == 89
    assert metrics["displayed_cue_and_page_useful_fraction"] >= 0.9
    assert metrics["counts"]["cardinality_correct"] == 41
    assert result["heldout_passed"] is False


def test_reserve_zero_useful_counts_as_no_match_despite_authored_form(
    tmp_path: Path,
) -> None:
    frozen = _freeze(tmp_path)
    packet_path = frozen / "calibration" / "packet.json"
    labels_path = frozen / "calibration" / "labels.json"
    freeze_path = frozen / "freeze.json"
    labels = json.loads(labels_path.read_bytes())
    reserve = labels["groups"][50]
    assert reserve["origin"] == "reserve" and reserve["form"] != "no_useful"
    for row in reserve["candidates"]:
        row["page_useful"] = row["cue_useful"] = False
    _write(labels_path, labels)
    freeze = json.loads(freeze_path.read_bytes())
    freeze["files"]["calibration/labels.json"] = scorer.digest(labels_path.read_bytes())
    _write(freeze_path, freeze)
    calibration = _results(tmp_path, frozen, "calibration")
    metrics = scorer.score_run(frozen, calibration)["calibration"]["metrics"]
    assert metrics["counts"]["no_useful_groups"] == 13
    assert metrics["counts"]["valid_no_useful_abstentions"] == 13
    assert metrics["by_form"][reserve["form"]]["positive_groups"] == 17
    assert metrics["counts"]["groups"] == 66


def test_reserve_no_match_false_display_is_rejected(tmp_path: Path) -> None:
    frozen = _freeze(tmp_path)
    labels_path = frozen / "calibration" / "labels.json"
    freeze_path = frozen / "freeze.json"
    labels = json.loads(labels_path.read_bytes())
    reserve = labels["groups"][50]
    for row in reserve["candidates"]:
        row["page_useful"] = row["cue_useful"] = False
    _write(labels_path, labels)
    freeze = json.loads(freeze_path.read_bytes())
    freeze["files"]["calibration/labels.json"] = scorer.digest(labels_path.read_bytes())
    _write(freeze_path, freeze)
    calibration = _results(tmp_path, frozen, "calibration",
                           choices={reserve["group_id"]: ["S01"]})
    result = scorer.score_run(frozen, calibration)
    assert result["calibration_passed"] is False
    assert result["calibration"]["metrics"]["counts"]["false_no_useful_displays"] == 1


def test_omitting_an_original_or_reserve_group_rejects_freeze(tmp_path: Path) -> None:
    frozen = _freeze(tmp_path)
    packet_path = frozen / "calibration" / "packet.json"
    freeze_path = frozen / "freeze.json"
    packet = json.loads(packet_path.read_bytes())
    for removed in (0, 48):
        changed = {**packet, "groups": [row for index, row in
                                     enumerate(packet["groups"]) if index != removed]}
        _write(packet_path, changed)
        freeze = json.loads(freeze_path.read_bytes())
        freeze["files"]["calibration/packet.json"] = scorer.digest(packet_path.read_bytes())
        _write(freeze_path, freeze)
        with pytest.raises(scorer.ScoreError, match="split_packet_invalid"):
            scorer._packet_and_labels(frozen, scorer._freeze(frozen)[0], "calibration")
        _write(packet_path, packet)
        freeze["files"]["calibration/packet.json"] = scorer.digest(packet_path.read_bytes())
        _write(freeze_path, freeze)


def test_heldout_must_stay_unread_when_calibration_fails(tmp_path: Path) -> None:
    frozen = _freeze(tmp_path)
    calibration = _results(tmp_path, frozen, "calibration",
                           choices={"G037": ["S01"]})
    heldout_packet = frozen / "heldout" / "packet.json"
    heldout_packet.unlink()
    result = scorer.score_run(frozen, calibration, tmp_path / "unopened")
    assert result["calibration_passed"] is False
    assert result["heldout_opened"] is False


def test_two_calibration_overflow_groups_require_exactly_three_useful_ids(
    tmp_path: Path,
) -> None:
    frozen = _freeze(tmp_path)
    passing = _results(tmp_path, frozen, "calibration")
    result = scorer.score_run(frozen, passing)
    assert result["calibration_passed"] is True
    assert result["calibration"]["metrics"]["by_available"]["4"] == {
        "groups": 2, "cardinality_correct": 2,
    }
    failing = _results(tmp_path, frozen, "calibration",
                       choices={"G049": ["S01", "S02"]})
    # The result directory is separate from the first one in an actual
    # evaluation. Here the helper rewrites the synthetic fixture in place.
    assert failing == passing
    result = scorer.score_run(frozen, failing)
    assert result["calibration_passed"] is False
    assert result["calibration"]["metrics"]["by_available"]["4"]["cardinality_correct"] == 1


def test_four_useful_cards_are_forbidden_in_heldout(tmp_path: Path) -> None:
    frozen = _freeze(tmp_path)
    labels_path = frozen / "heldout" / "labels.json"
    freeze_path = frozen / "freeze.json"
    labels = json.loads(labels_path.read_bytes())
    reserve = labels["groups"][48]
    assert reserve["origin"] == "reserve"
    for row in reserve["candidates"]:
        row["page_useful"] = row["cue_useful"] = True
    _write(labels_path, labels)
    freeze = json.loads(freeze_path.read_bytes())
    freeze["files"]["heldout/labels.json"] = scorer.digest(labels_path.read_bytes())
    _write(freeze_path, freeze)
    with pytest.raises(scorer.ScoreError, match="label_availability_invalid"):
        scorer._packet_and_labels(frozen, scorer._freeze(frozen)[0], "heldout")
