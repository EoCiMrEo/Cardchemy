"""Keyless, failure-inclusive public score for the categorical page judge.

The reviewed 66/60 augmented packets and every v2 quality threshold are reused
without copying or changing the historical scorer. This scorer accepts only a
prospectively versioned four-label wire. It opens heldout content only after
the entire calibration split passes, and it never activates Ask.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import score_fresh_public_source_id_v2_augmented as baseline
from prototype_categorical_page_judge_v1 import (
    CATEGORICAL_PAGE_JUDGE_VERSION,
    build_categorical_public_wire,
    parse_categorical_page_judge_output,
)
from app.ai.source_judgment import SourceJudgmentError


EVALUATION_SCHEMA = "fresh_public_categorical_page_judge_v1_evaluation"
SCORE_SCHEMA = "fresh_public_categorical_page_judge_v1_score"
RECEIPT_FILES = (
    "response-verdicts.jsonl", "usage-receipts.jsonl", "errors.jsonl",
)


def _packet_and_request_hashes(
    frozen_dir: Path, freeze: dict, split: str,
) -> tuple[dict, dict, str, str, dict[str, str]]:
    """Validate old immutable packets, then bind the new label-free wire."""
    packet, labels, packet_sha, labels_sha, _ = baseline._packet_and_labels(
        frozen_dir, freeze, split,
    )
    requests = {}
    for group in packet["groups"]:
        candidates = [
            {
                "id": row["id"],
                "page": row["page"],
                "page_text": row["context"],
                "cue": row["cue"],
            }
            for row in group["candidates"]
        ]
        try:
            wire = build_categorical_public_wire(group["question"], candidates)
        except SourceJudgmentError as exc:
            raise baseline.ScoreError("verdict_wire_contract_invalid") from exc
        requests[group["group_id"]] = baseline.digest(
            baseline.canonical_wire_bytes(wire),
        )
    return packet, labels, packet_sha, labels_sha, requests


def _result_receipts(
    results_dir: Path, split: str, freeze_sha: str,
    packet_sha: str, labels_sha: str,
) -> tuple[dict, dict, dict]:
    evaluation, evaluation_sha = baseline._read_canonical(
        results_dir / "evaluation.json", 16_384,
    )
    prototype_sha = baseline.digest(
        Path(__file__).with_name(
            "prototype_categorical_page_judge_v1.py",
        ).read_bytes(),
    )
    baseline.require(
        set(evaluation) == {
            "schema_version", "split", "freeze_sha256", "packet_sha256",
            "labels_sha256", "candidate_version", "prototype_sha256",
            "parser_sha256", "scorer_sha256", "gate_scorer_sha256",
            "inherited_wire_sha256", "inherited_contract_sha256",
            "model", "thinking", "automatic_retries", "files",
        }
        and evaluation.get("schema_version") == EVALUATION_SCHEMA
        and evaluation.get("split") == split
        and evaluation.get("freeze_sha256") == freeze_sha
        and evaluation.get("packet_sha256") == packet_sha
        and evaluation.get("labels_sha256") == labels_sha
        and evaluation.get("candidate_version") == CATEGORICAL_PAGE_JUDGE_VERSION
        and evaluation.get("prototype_sha256") == prototype_sha
        and evaluation.get("parser_sha256") == prototype_sha
        and evaluation.get("scorer_sha256") == baseline.digest(
            Path(__file__).read_bytes(),
        )
        and evaluation.get("gate_scorer_sha256") == baseline.digest(
            Path(baseline.__file__).read_bytes(),
        )
        and evaluation.get("inherited_wire_sha256") == baseline.digest(
            Path(__file__).with_name(
                "prototype_exhaustive_source_id_v2.py",
            ).read_bytes(),
        )
        and evaluation.get("inherited_contract_sha256") == baseline.digest(
            (baseline._BACKEND / "app/ai/source_judgment.py").read_bytes(),
        )
        and evaluation.get("model") == "gemini-3.5-flash-lite"
        and evaluation.get("thinking") == "low"
        and type(evaluation.get("automatic_retries")) is int
        and evaluation["automatic_retries"] == 0
        and type(evaluation.get("files")) is dict
        and set(evaluation["files"]) == set(RECEIPT_FILES)
        and all(baseline._valid_hash(value)
                for value in evaluation["files"].values()),
        "evaluation_binding_invalid",
    )
    receipts = {}
    for name in RECEIPT_FILES:
        rows, sha = baseline._read_lines(results_dir / name, 512_000)
        baseline.require(sha == evaluation["files"][name], "receipts_changed")
        receipts[name] = rows
    return evaluation, {"evaluation": evaluation_sha, **evaluation["files"]}, receipts


def _outcomes(
    packet: dict, request_hashes: dict[str, str], evaluation: dict,
    receipts: dict,
) -> tuple[dict[str, tuple[str, ...]], dict]:
    responses = baseline._index_receipts(
        receipts["response-verdicts.jsonl"],
        {"group_id", "request_sha256", "attempt_sha256", "raw_json", "model"},
        request_hashes, "responses_invalid",
    )
    usage = baseline._index_receipts(
        receipts["usage-receipts.jsonl"],
        {"group_id", "request_sha256", "attempt_sha256", "finish_reason",
         "input_tokens", "output_tokens", "model"},
        request_hashes, "usage_invalid",
    )
    errors = baseline._index_receipts(
        receipts["errors.jsonl"],
        {"group_id", "request_sha256", "attempt_sha256", "reason",
         "failed_attempt_cost_unknown", "model"},
        request_hashes, "errors_invalid",
    )
    baseline.require(
        set(responses) == set(usage)
        and not set(responses).intersection(errors)
        and set(responses).union(errors) == set(request_hashes)
        and not {row["attempt_sha256"] for row in responses.values()}.intersection(
            {row["attempt_sha256"] for row in errors.values()},
        )
        and all(
            type(row["reason"]) is str
            and row["reason"] in baseline.TRANSIENT_FAILURES
            and row["model"] == evaluation["model"]
            and row["failed_attempt_cost_unknown"] is True
            for row in errors.values()
        ),
        "split_outcomes_incomplete",
    )
    parsed: dict[str, tuple[str, ...]] = {}
    invalid = set()
    input_tokens = output_tokens = 0
    for group in packet["groups"]:
        group_id = group["group_id"]
        if group_id in errors:
            continue
        response = responses[group_id]
        spent = usage[group_id]
        baseline.require(
            response["attempt_sha256"] == spent["attempt_sha256"]
            and response["model"] == spent["model"] == evaluation["model"]
            and spent["finish_reason"] == "STOP"
            and type(spent["input_tokens"]) is int
            and type(spent["output_tokens"]) is int
            and 0 < spent["input_tokens"] <= 8_192
            and 0 <= spent["output_tokens"] <= 1_024
            and type(response["raw_json"]) is str,
            "response_usage_invalid",
        )
        input_tokens += spent["input_tokens"]
        output_tokens += spent["output_tokens"]
        try:
            parsed[group_id] = parse_categorical_page_judge_output(
                response["raw_json"],
                [candidate["id"] for candidate in group["candidates"]],
            )
        except (SourceJudgmentError, UnicodeError):
            invalid.add(group_id)
    return parsed, {
        "provider_failed_groups": len(errors),
        "invalid_model_outputs": len(invalid),
        "accepted_responses": len(parsed),
        "reported_input_tokens": input_tokens,
        "reported_output_tokens": output_tokens,
        "failed_attempt_cost_unknown": bool(errors),
    }


def _score_one(
    frozen_dir: Path, results_dir: Path, freeze: dict,
    freeze_sha: str, split: str,
) -> tuple[dict, dict, set[str]]:
    packet, labels, packet_sha, labels_sha, request_hashes = (
        _packet_and_request_hashes(frozen_dir, freeze, split)
    )
    evaluation, receipt_hashes, receipts = _result_receipts(
        results_dir, split, freeze_sha, packet_sha, labels_sha,
    )
    selected, receipt_counts = _outcomes(
        packet, request_hashes, evaluation, receipts,
    )
    metrics = baseline.score_split(packet, labels, selected, receipt_counts)
    if split == "calibration":
        # The approved v3 gate names exact 1/2/3-useful selection as a
        # precondition for opening the different-PDF holdout. The inherited
        # calibration scorer reports these counts but gates only positive hit;
        # preserve its existing 5/6 per-stratum ratio here without changing
        # the consumed v2 scorer or its historical result.
        strata = metrics["by_available"]
        cardinality_passed = all(
            strata[str(amount)]["cardinality_correct"] >=
            baseline.ceil_ratio(5, 6, strata[str(amount)]["groups"])
            for amount in (1, 2, 3)
        )
        metrics["source_quality_passed"] = bool(
            metrics["source_quality_passed"] and cardinality_passed)
        metrics["public_passed"] = bool(
            metrics["public_passed"] and cardinality_passed)
        metrics["gate"]["calibration_per_stratum_cardinality"] = (
            "exact useful ID set: ceil(5N/6) in each 1/2/3-useful stratum"
        )
    safe = {
        "schema_version": SCORE_SCHEMA,
        "split": split,
        "corpus_id": freeze["corpus_id"],
        "source_manifest_sha256": freeze["source_manifest_sha256"],
        "freeze_sha256": freeze_sha,
        "packet_sha256": packet_sha,
        "labels_sha256": labels_sha,
        "receipt_sha256": receipt_hashes,
        "execution": {key: evaluation[key] for key in (
            "candidate_version", "prototype_sha256", "parser_sha256",
            "scorer_sha256", "gate_scorer_sha256", "inherited_wire_sha256",
            "inherited_contract_sha256", "model", "thinking", "automatic_retries",
        )},
        "public_passed": metrics["public_passed"],
        "release_gate_passed": False,
        "metrics": metrics,
    }
    return safe, evaluation, {
        document["sha256"] for document in packet["documents"]
    }


def score_run(
    frozen_dir: Path, calibration_results: Path,
    heldout_results: Path | None = None,
) -> dict:
    """Read calibration first; a failed gate does not touch heldout files."""
    baseline.require(
        frozen_dir.is_dir() and not frozen_dir.is_symlink()
        and calibration_results.is_dir()
        and not calibration_results.is_symlink(),
        "score_directory_invalid",
    )
    freeze, freeze_sha = baseline._freeze(frozen_dir)
    calibration, calibration_eval, calibration_docs = _score_one(
        frozen_dir, calibration_results, freeze, freeze_sha, "calibration",
    )
    result = {
        "schema_version": SCORE_SCHEMA + "_run",
        "calibration": calibration,
        "calibration_passed": calibration["public_passed"],
        "heldout_opened": False,
        "release_gate_passed": False,
    }
    if not calibration["public_passed"] or heldout_results is None:
        return result
    baseline.require(
        heldout_results.is_dir() and not heldout_results.is_symlink(),
        "score_directory_invalid",
    )
    heldout, heldout_eval, heldout_docs = _score_one(
        frozen_dir, heldout_results, freeze, freeze_sha, "heldout",
    )
    baseline.require(
        not calibration_docs.intersection(heldout_docs)
        and calibration["execution"] == heldout["execution"]
        and calibration_eval["freeze_sha256"] == heldout_eval["freeze_sha256"],
        "heldout_independence_or_execution_changed",
    )
    result["heldout"] = heldout
    result["heldout_opened"] = True
    result["heldout_passed"] = heldout["public_passed"]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-dir", required=True, type=Path)
    parser.add_argument("--calibration-results", required=True, type=Path)
    parser.add_argument("--heldout-results", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = score_run(
            args.frozen_dir, args.calibration_results, args.heldout_results,
        )
        raw = baseline.canonical_bytes(result)
        if args.output is not None:
            with args.output.open("xb") as stream:
                stream.write(raw)
        else:
            sys.stdout.buffer.write(raw)
    except (OSError, baseline.ScoreError) as exc:
        code = str(exc) if isinstance(exc, baseline.ScoreError) else "score_io_failed"
        parser.exit(2, f"score failed: {code}\n")


if __name__ == "__main__":
    main()
