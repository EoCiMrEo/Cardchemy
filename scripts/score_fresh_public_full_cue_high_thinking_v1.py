"""Keyless, failure-inclusive public score for full-cue high thinking.

The reviewed 66/60 augmented packets and every v2 quality threshold are reused
without copying or changing the historical scorer. This scorer accepts only a
prospectively versioned four-label wire. It opens heldout content only after
the entire calibration split passes, and it never activates Ask.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import sys

import score_fresh_public_source_id_v2_augmented as baseline
from prototype_full_cue_high_thinking_v1 import (
    FULL_CUE_HIGH_THINKING_VERSION,
    build_high_thinking_public_wire,
)
from app.ai.source_judgment import SourceJudgmentError


EVALUATION_SCHEMA = "fresh_public_full_cue_high_thinking_v1_evaluation"
SCORE_SCHEMA = "fresh_public_full_cue_high_thinking_v1_score"
RECEIPT_FILES = (
    "selected-ids.jsonl", "usage-receipts.jsonl", "errors.jsonl",
)
MAX_LATENCY_MS = 31_000


def _latency_p95(values: list[int]) -> int:
    baseline.require(bool(values) and all(type(value) is int and
                     0 <= value <= MAX_LATENCY_MS for value in values),
                     "latency_receipts_invalid")
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


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
            wire = build_high_thinking_public_wire(group["question"], candidates)
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
            "prototype_full_cue_high_thinking_v1.py",
        ).read_bytes(),
    )
    baseline.require(
        set(evaluation) == {
            "schema_version", "split", "freeze_sha256", "packet_sha256",
            "labels_sha256", "candidate_version", "prototype_sha256",
            "parser_sha256", "scorer_sha256", "gate_scorer_sha256",
            "inherited_wire_sha256", "inherited_contract_sha256",
            "model", "thinking", "max_output_tokens_per_call",
            "automatic_retries", "attempt_latency_count",
            "latency_p95_ms", "files",
        }
        and evaluation.get("schema_version") == EVALUATION_SCHEMA
        and evaluation.get("split") == split
        and evaluation.get("freeze_sha256") == freeze_sha
        and evaluation.get("packet_sha256") == packet_sha
        and evaluation.get("labels_sha256") == labels_sha
        and evaluation.get("candidate_version") == FULL_CUE_HIGH_THINKING_VERSION
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
        and evaluation.get("thinking") == "high"
        and type(evaluation.get("max_output_tokens_per_call")) is int
        and evaluation["max_output_tokens_per_call"] == 2_048
        and type(evaluation.get("automatic_retries")) is int
        and evaluation["automatic_retries"] == 0
        and type(evaluation.get("attempt_latency_count")) is int
        and evaluation["attempt_latency_count"] == baseline.SPLIT_GROUPS[split]
        and type(evaluation.get("latency_p95_ms")) is int
        and 0 <= evaluation["latency_p95_ms"] <= MAX_LATENCY_MS
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
        receipts["selected-ids.jsonl"],
        {"group_id", "request_sha256", "attempt_sha256", "selected_ids", "model"},
        request_hashes, "responses_invalid",
    )
    usage = baseline._index_receipts(
        receipts["usage-receipts.jsonl"],
        {"group_id", "request_sha256", "attempt_sha256", "finish_reason",
         "input_tokens", "output_tokens", "latency_ms", "model"},
        request_hashes, "usage_invalid",
    )
    errors = baseline._index_receipts(
        receipts["errors.jsonl"],
        {"group_id", "request_sha256", "attempt_sha256", "reason",
         "failed_attempt_cost_unknown", "latency_ms", "model"},
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
            and type(row["latency_ms"]) is int
            and 0 <= row["latency_ms"] <= MAX_LATENCY_MS
            for row in errors.values()
        ),
        "split_outcomes_incomplete",
    )
    parsed: dict[str, tuple[str, ...]] = {}
    input_tokens = output_tokens = 0
    latencies_ms = [row["latency_ms"] for row in errors.values()]
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
            and 0 <= spent["output_tokens"] <= 2_048
            and type(spent["latency_ms"]) is int
            and 0 <= spent["latency_ms"] <= MAX_LATENCY_MS
            and type(response["selected_ids"]) is list,
            "response_usage_invalid",
        )
        input_tokens += spent["input_tokens"]
        output_tokens += spent["output_tokens"]
        latencies_ms.append(spent["latency_ms"])
        ids = [candidate["id"] for candidate in group["candidates"]]
        selected = response["selected_ids"]
        baseline.require(
            len(selected) <= 3 and
            all(type(source_id) is str and source_id in ids
                for source_id in selected) and
            selected == [source_id for source_id in ids
                         if source_id in selected],
            "selected_ids_invalid",
        )
        parsed[group_id] = tuple(selected)
    baseline.require(len(latencies_ms) == len(request_hashes) and
                     evaluation["attempt_latency_count"] == len(latencies_ms) and
                     evaluation["latency_p95_ms"] == _latency_p95(latencies_ms),
                     "latency_receipts_invalid")
    return parsed, {
        "provider_failed_groups": len(errors),
        "invalid_model_outputs": 0,
        "accepted_responses": len(parsed),
        "reported_input_tokens": input_tokens,
        "reported_output_tokens": output_tokens,
        "attempt_latency_count": len(latencies_ms),
        "latency_p95_ms": evaluation["latency_p95_ms"],
        "failed_attempt_cost_unknown": bool(errors),
    }


def gate_metrics(packet: dict, labels: dict, selected: dict,
                 receipt_counts: dict) -> dict:
    """Share the frozen gates with conservative, best-possible stop checks."""
    metrics = baseline.score_split(packet, labels, selected, receipt_counts)
    if packet["split"] == "calibration":
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
    return metrics


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
    metrics = gate_metrics(packet, labels, selected, receipt_counts)
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
            "inherited_contract_sha256", "model", "thinking",
            "max_output_tokens_per_call", "automatic_retries",
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
