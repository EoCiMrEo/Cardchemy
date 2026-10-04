"""Synthetic-only gates for the inactive four-verdict public scorer."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "scripts"))

import score_fresh_public_per_page_verdict_v3 as scorer  # noqa: E402
from test_score_fresh_public_source_id_v2_augmented import (  # noqa: E402
    _freeze, _write, _write_lines,
)


def _results(
    tmp_path: Path, frozen: Path, split: str,
    *, fail_groups: set[str] = frozenset(),
    choices: dict[str, list[str] | str] | None = None,
) -> Path:
    choices = choices or {}
    results = tmp_path / f"{split}-v3-results"
    packet = json.loads((frozen / split / "packet.json").read_bytes())
    labels = json.loads((frozen / split / "labels.json").read_bytes())
    by_label = {row["group_id"]: row for row in labels["groups"]}
    responses, usage, errors = [], [], []
    for number, group in enumerate(packet["groups"]):
        group_id = group["group_id"]
        wire = scorer.build_per_page_public_wire(
            group["question"], [
                {"id": row["id"], "page": row["page"],
                 "page_text": row["context"], "cue": row["cue"]}
                for row in group["candidates"]
            ],
        )
        request_sha = scorer.baseline.digest(
            scorer.baseline.canonical_wire_bytes(wire),
        )
        attempt_sha = scorer.baseline.digest(
            f"v3-{split}-{number}-attempt".encode(),
        )
        common = {
            "group_id": group_id, "request_sha256": request_sha,
            "attempt_sha256": attempt_sha,
        }
        if group_id in fail_groups:
            errors.append({
                **common, "reason": "provider_timeout",
                "failed_attempt_cost_unknown": True, "model": "synthetic-model",
            })
            continue
        useful_ids = [row["id"] for row in by_label[group_id]["candidates"]
                      if row["page_useful"] and row["cue_useful"]]
        chosen = choices.get(group_id, useful_ids)
        raw_json = (chosen if isinstance(chosen, str) else json.dumps({
            "verdicts": [
                {"id": row["id"], "useful_reading_page": row["id"] in chosen,
                 "requested_relation_present": row["id"] in chosen}
                for row in group["candidates"]
            ],
        }, separators=(",", ":")))
        responses.append({
            **common, "raw_json": raw_json, "model": "synthetic-model",
        })
        usage.append({
            **common, "finish_reason": "STOP", "input_tokens": 1_000,
            "output_tokens": 80, "model": "synthetic-model",
        })
    files = {
        "response-verdicts.jsonl": _write_lines(
            results / "response-verdicts.jsonl", responses),
        "usage-receipts.jsonl": _write_lines(
            results / "usage-receipts.jsonl", usage),
        "errors.jsonl": _write_lines(results / "errors.jsonl", errors),
    }
    prototype_sha = scorer.baseline.digest(
        (_ROOT / "scripts" / "prototype_per_page_source_verdict_v3.py").read_bytes(),
    )
    _write(results / "evaluation.json", {
        "schema_version": scorer.EVALUATION_SCHEMA, "split": split,
        "freeze_sha256": scorer.baseline.digest((frozen / "freeze.json").read_bytes()),
        "packet_sha256": scorer.baseline.digest(
            (frozen / split / "packet.json").read_bytes()),
        "labels_sha256": scorer.baseline.digest(
            (frozen / split / "labels.json").read_bytes()),
        "candidate_version": scorer.SOURCE_VERDICT_CANDIDATE_VERSION,
        "prototype_sha256": prototype_sha, "parser_sha256": prototype_sha,
        "scorer_sha256": scorer.baseline.digest(Path(scorer.__file__).read_bytes()),
        "gate_scorer_sha256": scorer.baseline.digest(
            Path(scorer.baseline.__file__).read_bytes()),
        "inherited_wire_sha256": scorer.baseline.digest(
            (_ROOT / "scripts" / "prototype_exhaustive_source_id_v2.py").read_bytes()),
        "inherited_contract_sha256": scorer.baseline.digest(
            (_ROOT / "backend" / "app" / "ai" / "source_judgment.py").read_bytes()),
        "model": "synthetic-model", "thinking": "low",
        "automatic_retries": 0, "files": files,
    })
    return results


def test_perfect_calibration_then_disjoint_heldout_passes_only_public_gate(
    tmp_path: Path,
) -> None:
    frozen = _freeze(tmp_path)
    result = scorer.score_run(
        frozen,
        _results(tmp_path, frozen, "calibration"),
        _results(tmp_path, frozen, "heldout"),
    )
    assert result["calibration_passed"] is True
    assert result["heldout_opened"] is True
    assert result["heldout_passed"] is True
    assert result["release_gate_passed"] is False
    assert result["heldout"]["metrics"]["counts"]["groups"] == 60
    assert result["calibration"]["metrics"]["by_available"]["4"] == {
        "groups": 2, "cardinality_correct": 2,
    }


def test_false_no_match_display_never_opens_heldout(tmp_path: Path) -> None:
    frozen = _freeze(tmp_path)
    calibration = _results(
        tmp_path, frozen, "calibration", choices={"G037": ["S01"]},
    )
    # This path may not exist: a failed calibration must not even stat it.
    result = scorer.score_run(frozen, calibration, tmp_path / "sealed-heldout")
    assert result["calibration_passed"] is False
    assert result["heldout_opened"] is False
    assert result["calibration"]["metrics"]["counts"][
        "false_no_useful_displays"] == 1


def test_underselecting_useful_pages_breaks_heldout_cardinality(tmp_path: Path) -> None:
    frozen = _freeze(tmp_path)
    calibration = _results(tmp_path, frozen, "calibration")
    heldout = _results(
        tmp_path, frozen, "heldout",
        choices={f"G{number:03d}": ["S01"]
                 for number in (2, 5, 8, 11, 14, 17, 20)},
    )
    result = scorer.score_run(frozen, calibration, heldout)
    assert result["heldout_opened"] is True
    assert result["heldout_passed"] is False
    metrics = result["heldout"]["metrics"]
    assert metrics["displayed_cue_and_page_useful_fraction"] == 1.0
    assert metrics["by_available"]["2"]["cardinality_correct"] < 14


def test_underselecting_useful_pages_keeps_heldout_sealed_at_calibration(
    tmp_path: Path,
) -> None:
    frozen = _freeze(tmp_path)
    calibration = _results(
        tmp_path, frozen, "calibration",
        choices={f"G{number:03d}": ["S01"]
                 for number in (2, 5, 8, 11, 14, 17, 20)},
    )
    # Each result still hits a useful page and every shown card is useful.
    # The inherited calibration scorer would pass, but exact multi-page
    # selection is part of the approved v3 gate before opening heldout.
    result = scorer.score_run(frozen, calibration, tmp_path / "sealed-heldout")
    metrics = result["calibration"]["metrics"]
    assert metrics["counts"]["positive_hit_at_three"] == 54
    assert metrics["displayed_cue_and_page_useful_fraction"] == 1.0
    assert metrics["by_available"]["2"]["cardinality_correct"] < 14
    assert metrics["source_quality_passed"] is False
    assert result["calibration_passed"] is False
    assert result["heldout_opened"] is False


def test_four_page_overflow_requires_three_qualified_ids(tmp_path: Path) -> None:
    frozen = _freeze(tmp_path)
    calibration = _results(
        tmp_path, frozen, "calibration", choices={"G049": ["S01", "S02"]},
    )
    result = scorer.score_run(frozen, calibration, tmp_path / "sealed-heldout")
    assert result["calibration_passed"] is False
    assert result["calibration"]["metrics"]["by_available"]["4"] == {
        "groups": 2, "cardinality_correct": 1,
    }


def test_failure_counts_as_miss_and_no_match_is_not_invented(tmp_path: Path) -> None:
    frozen = _freeze(tmp_path)
    calibration = _results(
        tmp_path, frozen, "calibration", fail_groups={"G001", "G002"},
    )
    result = scorer.score_run(frozen, calibration)
    counts = result["calibration"]["metrics"]["counts"]
    assert counts["accepted_responses"] == 64
    assert counts["provider_failed_groups"] == 2
    assert counts["positive_hit_at_three"] == 52
    assert result["calibration_passed"] is True


def test_malformed_verdict_is_invalid_not_valid_abstention(tmp_path: Path) -> None:
    frozen = _freeze(tmp_path)
    calibration = _results(
        tmp_path, frozen, "calibration",
        choices={"G037": '{"selected_ids":[]}'},
    )
    result = scorer.score_run(frozen, calibration, tmp_path / "sealed-heldout")
    assert result["calibration_passed"] is False
    counts = result["calibration"]["metrics"]["counts"]
    assert counts["invalid_model_outputs"] == 1
    assert counts["valid_no_useful_abstentions"] == 11
    assert result["heldout_opened"] is False


@pytest.mark.parametrize("mutate", ["receipt", "version", "retry", "gate_code"])
def test_binding_or_receipt_change_fails_closed(tmp_path: Path, mutate: str) -> None:
    frozen = _freeze(tmp_path)
    calibration = _results(tmp_path, frozen, "calibration")
    if mutate == "receipt":
        with (calibration / "response-verdicts.jsonl").open("ab") as stream:
            stream.write(b"\n")
    else:
        path = calibration / "evaluation.json"
        evaluation = json.loads(path.read_bytes())
        if mutate == "version":
            evaluation["candidate_version"] = "old_source_id_candidate"
        elif mutate == "retry":
            evaluation["automatic_retries"] = 1
        else:
            evaluation["gate_scorer_sha256"] = scorer.baseline.digest(b"old-gate")
        _write(path, evaluation)
    with pytest.raises(scorer.baseline.ScoreError):
        scorer.score_run(frozen, calibration)


def test_request_hash_is_specific_to_new_verdict_wire(tmp_path: Path) -> None:
    frozen = _freeze(tmp_path)
    calibration = _results(tmp_path, frozen, "calibration")
    path = calibration / "response-verdicts.jsonl"
    rows = [json.loads(line) for line in path.read_bytes().splitlines()]
    rows[0]["request_sha256"] = scorer.baseline.digest(b"old-wire")
    _write_lines(path, rows)
    evaluation_path = calibration / "evaluation.json"
    evaluation = json.loads(evaluation_path.read_bytes())
    evaluation["files"]["response-verdicts.jsonl"] = scorer.baseline.digest(
        path.read_bytes(),
    )
    _write(evaluation_path, evaluation)
    with pytest.raises(scorer.baseline.ScoreError, match="responses_invalid"):
        scorer.score_run(frozen, calibration)
