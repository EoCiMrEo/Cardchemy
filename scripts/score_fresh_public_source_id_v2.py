"""Keyless, failure-inclusive score for a new, disjoint public PDF pilot.

This module only reads frozen public packets, independently reviewed labels,
and future ID-only result receipts. It has no provider client, credential
reader, live runner, or Ask activation path. Heldout files are opened only
after the complete calibration split passes every unchanged public gate.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.ai.source_judgment import (  # noqa: E402
    SourceJudgmentError, canonical_bytes as canonical_wire_bytes,
    parse_source_id_output,
)
from prototype_exhaustive_source_id_v2 import (  # noqa: E402
    SOURCE_ID_CANDIDATE_VERSION, build_exhaustive_public_wire,
)


PACKET_SCHEMA = "fresh_public_source_id_v2_packet"
LABEL_SCHEMA = "fresh_public_source_id_v2_labels"
FREEZE_SCHEMA = "fresh_public_source_id_v2_freeze"
EVALUATION_SCHEMA = "fresh_public_source_id_v2_evaluation"
SCORE_SCHEMA = "fresh_public_source_id_v2_score"
SPLITS = ("calibration", "heldout")
FORMS = ("direct", "paraphrase", "followup", "no_useful")
RECEIPT_FILES = ("response-ids.jsonl", "usage-receipts.jsonl", "errors.jsonl")
FROZEN_FILES = tuple(f"{split}/{name}" for split in SPLITS
                     for name in ("packet.json", "labels.json"))
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
TRANSIENT_FAILURES = frozenset({
    "provider_timeout", "provider_http_408", "provider_http_429",
    "provider_http_502", "provider_http_503", "provider_http_504",
    "provider_connect_error", "provider_network_error",
    "provider_protocol_error", "provider_transport_error",
})


class ScoreError(ValueError):
    """Closed, content-free diagnostic for a malformed public score input."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ScoreError(code)


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def ceil_ratio(numerator: int, denominator: int, count: int) -> int:
    return (numerator * count + denominator - 1) // denominator


def _read_canonical(path: Path, max_bytes: int) -> tuple[dict, str]:
    require(path.is_file() and not path.is_symlink() and
            0 < path.stat().st_size <= max_bytes, "file_missing_or_oversize")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
        require(type(value) is dict and canonical_bytes(value) == raw,
                "file_not_canonical")
    except (UnicodeError, ValueError) as exc:
        raise ScoreError("file_not_canonical") from exc
    return value, digest(raw)


def _read_lines(path: Path, max_bytes: int) -> tuple[list[dict], str]:
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_size <= max_bytes, "receipts_missing_or_oversize")
    raw = path.read_bytes()
    lines = raw.splitlines(keepends=True)
    require(len(lines) <= 48 and b"\r" not in raw and
            all(line.endswith(b"\n") and len(line) <= 4_096 for line in lines),
            "receipt_lines_invalid")
    values = []
    for line in lines:
        try:
            value = json.loads(line)
            require(type(value) is dict and canonical_bytes(value) == line,
                    "receipt_line_not_canonical")
        except (UnicodeError, ValueError) as exc:
            raise ScoreError("receipt_line_not_canonical") from exc
        values.append(value)
    return values, digest(raw)


def _valid_hash(value: object) -> bool:
    return type(value) is str and bool(HEX64.fullmatch(value))


def _freeze(frozen_dir: Path) -> tuple[dict, str]:
    freeze, freeze_sha = _read_canonical(frozen_dir / "freeze.json", 16_384)
    require(set(freeze) == {"schema_version", "corpus_id",
                            "source_manifest_sha256", "overlap_diagnostic_sha256",
                            "input_sha256", "files"} and
            freeze.get("schema_version") == FREEZE_SCHEMA and
            type(freeze.get("corpus_id")) is str and
            bool(freeze["corpus_id"]) and
            _valid_hash(freeze.get("source_manifest_sha256")) and
            _valid_hash(freeze.get("overlap_diagnostic_sha256")) and
            type(freeze.get("files")) is dict and
            set(freeze["files"]) == set(FROZEN_FILES) and
            all(_valid_hash(value) for value in freeze["files"].values()) and
            type(freeze.get("input_sha256")) is dict and
            set(freeze["input_sha256"]) == {
                "authored", "review_a", "review_b", "adjudication",
                "overlap_review"} and
            all(_valid_hash(value) for value in freeze["input_sha256"].values()),
            "freeze_invalid")
    return freeze, freeze_sha


def _packet_and_labels(frozen_dir: Path, freeze: dict,
                       split: str) -> tuple[dict, dict, str, str, dict[str, str]]:
    # Called for heldout only after calibration has passed.
    require(split in SPLITS, "split_invalid")
    packet, packet_sha = _read_canonical(frozen_dir / split / "packet.json", 500_000)
    labels, labels_sha = _read_canonical(frozen_dir / split / "labels.json", 150_000)
    require(packet_sha == freeze["files"][f"{split}/packet.json"] and
            labels_sha == freeze["files"][f"{split}/labels.json"],
            "frozen_file_changed")
    shared = (packet.get("corpus_id") == labels.get("corpus_id") ==
              freeze["corpus_id"] and
              packet.get("source_manifest_sha256") ==
              labels.get("source_manifest_sha256") ==
              freeze["source_manifest_sha256"])
    require(shared and
            set(packet) == {"schema_version", "corpus_id",
                            "source_manifest_sha256", "split", "documents", "groups"} and
            set(labels) == {"schema_version", "corpus_id",
                            "source_manifest_sha256", "split", "packet_sha256",
                            "reviewer_ids", "adjudicator_id", "disagreement_count",
                            "groups"} and
            packet.get("schema_version") == PACKET_SCHEMA and
            labels.get("schema_version") == LABEL_SCHEMA and
            packet.get("split") == labels.get("split") == split and
            labels.get("packet_sha256") == packet_sha and
            type(packet.get("documents")) is list and
            len(packet["documents"]) == 4 and
            type(packet.get("groups")) is list and
            len(packet["groups"]) == 48 and
            type(labels.get("groups")) is list and
            len(labels["groups"]) == 48 and
            type(labels.get("reviewer_ids")) is list and
            len(labels["reviewer_ids"]) == 2 and
            all(type(item) is str and bool(item) for item in labels["reviewer_ids"]) and
            labels["reviewer_ids"][0] != labels["reviewer_ids"][1] and
            type(labels.get("adjudicator_id")) is str and
            bool(labels["adjudicator_id"]) and
            labels["adjudicator_id"] not in labels["reviewer_ids"] and
            type(labels.get("disagreement_count")) is int and
            labels["disagreement_count"] >= 0,
            "split_packet_invalid")
    documents = {}
    document_shas = set()
    for document in packet["documents"]:
        require(type(document) is dict and
                set(document) == {"document_id", "sha256", "pages"} and
                type(document["document_id"]) is str and
                bool(document["document_id"]) and
                document["document_id"] not in documents and
                _valid_hash(document["sha256"]) and
                document["sha256"] not in document_shas and
                type(document["pages"]) is int and document["pages"] > 0,
                "split_documents_invalid")
        documents[document["document_id"]] = document
        document_shas.add(document["sha256"])
    by_label = {}
    for row in labels["groups"]:
        require(type(row) is dict and set(row) == {
                    "group_id", "author_group_id", "form", "candidates"} and
                type(row["group_id"]) is str and
                row["group_id"] not in by_label and
                type(row["author_group_id"]) is str and
                bool(row["author_group_id"]) and
                row["form"] in FORMS and
                type(row["candidates"]) is list and len(row["candidates"]) == 4,
                "labels_invalid")
        by_label[row["group_id"]] = row
    group_ids = set()
    form_counts = Counter()
    cardinality_counts = Counter()
    request_hashes = {}
    for group in packet["groups"]:
        require(type(group) is dict and
                set(group) == {"group_id", "question", "candidates"} and
                type(group["group_id"]) is str and bool(group["group_id"]) and
                group["group_id"] not in group_ids and
                type(group["question"]) is str and bool(group["question"].strip()) and
                type(group["candidates"]) is list and
                len(group["candidates"]) == 4,
                "packet_group_invalid")
        group_id = group["group_id"]
        group_ids.add(group_id)
        require(group_id in by_label, "labels_group_mismatch")
        form = by_label[group_id]["form"]
        form_counts[form] += 1
        label_rows = by_label[group_id]["candidates"]
        candidate_ids = []
        wire_candidates = []
        available = 0
        represented_documents = set()
        represented_pages = set()
        for candidate, label in zip(group["candidates"], label_rows, strict=True):
            require(type(candidate) is dict and set(candidate) == {
                "id", "document_id", "page", "context_start", "context_end",
                "context", "cue_start", "cue_end", "cue", "page_text_sha256"} and
                type(label) is dict and set(label) == {
                    "id", "page_useful", "cue_useful"} and
                candidate["id"] == label["id"] and
                type(candidate["id"]) is str and
                candidate["id"] not in candidate_ids and
                type(candidate["document_id"]) is str and
                candidate["document_id"] in documents and
                type(candidate["page"]) is int and
                0 < candidate["page"] <= documents[candidate["document_id"]]["pages"] and
                type(candidate["context_start"]) is int and
                type(candidate["context_end"]) is int and
                0 <= candidate["context_start"] < candidate["context_end"] and
                type(candidate["context"]) is str and
                candidate["context"] and
                candidate["context_end"] - candidate["context_start"] ==
                    len(candidate["context"]) and
                type(candidate["cue_start"]) is int and
                type(candidate["cue_end"]) is int and
                0 <= candidate["cue_start"] < candidate["cue_end"] and
                type(candidate["cue"]) is str and candidate["cue"] and
                candidate["cue_end"] - candidate["cue_start"] == len(candidate["cue"]) and
                candidate["context_start"] <= candidate["cue_start"] and
                candidate["cue_end"] <= candidate["context_end"] and
                candidate["context"][candidate["cue_start"] - candidate["context_start"]:
                                     candidate["cue_end"] - candidate["context_start"]] ==
                    candidate["cue"] and
                _valid_hash(candidate["page_text_sha256"]) and
                (candidate["document_id"], candidate["page"]) not in represented_pages and
                type(label["page_useful"]) is bool and
                type(label["cue_useful"]) is bool,
                "candidate_or_label_invalid")
            candidate_ids.append(candidate["id"])
            represented_documents.add(candidate["document_id"])
            represented_pages.add((candidate["document_id"], candidate["page"]))
            wire_candidates.append({"id": candidate["id"],
                                    "page": candidate["page"],
                                    "page_text": candidate["context"],
                                    "cue": candidate["cue"]})
            available += label["page_useful"] and label["cue_useful"]
        require(candidate_ids == ["S01", "S02", "S03", "S04"] and
                len(represented_documents) == 2,
                "candidate_ids_invalid")
        if form == "no_useful":
            require(available == 0, "negative_label_invalid")
        else:
            require(1 <= available <= 3, "positive_label_invalid")
            cardinality_counts[available] += 1
        try:
            wire = build_exhaustive_public_wire(group["question"], wire_candidates)
        except SourceJudgmentError as exc:
            raise ScoreError("wire_contract_invalid") from exc
        request_hashes[group_id] = digest(canonical_wire_bytes(wire))
    require(set(by_label) == group_ids and
            [group["group_id"] for group in packet["groups"]] ==
                [f"G{number:03d}" for number in range(1, 49)] and
            form_counts == Counter({name: 12 for name in FORMS}) and
            cardinality_counts == Counter({1: 12, 2: 12, 3: 12}),
            "split_balance_invalid")
    return packet, labels, packet_sha, labels_sha, request_hashes


def _result_receipts(results_dir: Path, split: str, freeze_sha: str,
                     packet_sha: str, labels_sha: str) -> tuple[dict, dict, dict]:
    evaluation, evaluation_sha = _read_canonical(
        results_dir / "evaluation.json", 16_384)
    require(set(evaluation) == {"schema_version", "split", "freeze_sha256",
                                "packet_sha256", "labels_sha256",
                                "candidate_version", "prototype_sha256",
                                "parser_sha256", "scorer_sha256", "model",
                                "thinking", "automatic_retries", "files"} and
            evaluation.get("schema_version") == EVALUATION_SCHEMA and
            evaluation.get("split") == split and
            evaluation.get("freeze_sha256") == freeze_sha and
            evaluation.get("packet_sha256") == packet_sha and
            evaluation.get("labels_sha256") == labels_sha and
            evaluation.get("candidate_version") == SOURCE_ID_CANDIDATE_VERSION and
            evaluation.get("prototype_sha256") == digest(
                Path(__file__).with_name("prototype_exhaustive_source_id_v2.py").read_bytes()) and
            evaluation.get("parser_sha256") == digest(
                (_BACKEND / "app/ai/source_judgment.py").read_bytes()) and
            evaluation.get("scorer_sha256") == digest(Path(__file__).read_bytes()) and
            type(evaluation.get("model")) is str and bool(evaluation["model"]) and
            type(evaluation.get("thinking")) is str and bool(evaluation["thinking"]) and
            type(evaluation.get("automatic_retries")) is int and
            evaluation["automatic_retries"] == 0 and
            type(evaluation.get("files")) is dict and
            set(evaluation["files"]) == set(RECEIPT_FILES) and
            all(_valid_hash(value) for value in evaluation["files"].values()),
            "evaluation_binding_invalid")
    receipts = {}
    for name in RECEIPT_FILES:
        rows, sha = _read_lines(results_dir / name, 256_000)
        require(sha == evaluation["files"][name], "receipts_changed")
        receipts[name] = rows
    return evaluation, {"evaluation": evaluation_sha, **evaluation["files"]}, receipts


def _index_receipts(rows: list[dict], expected_fields: set[str],
                    request_hashes: dict[str, str], code: str) -> dict[str, dict]:
    indexed = {}
    attempts = set()
    for row in rows:
        require(type(row) is dict and set(row) == expected_fields and
                type(row.get("group_id")) is str and
                row["group_id"] in request_hashes and
                row["group_id"] not in indexed and
                row.get("request_sha256") == request_hashes[row["group_id"]] and
                _valid_hash(row.get("attempt_sha256")) and
                row["attempt_sha256"] not in attempts,
                code)
        indexed[row["group_id"]] = row
        attempts.add(row["attempt_sha256"])
    return indexed


def _outcomes(packet: dict, request_hashes: dict[str, str],
              evaluation: dict, receipts: dict) -> tuple[dict, dict]:
    responses = _index_receipts(
        receipts["response-ids.jsonl"],
        {"group_id", "request_sha256", "attempt_sha256", "raw_json", "model"},
        request_hashes, "responses_invalid")
    usage = _index_receipts(
        receipts["usage-receipts.jsonl"],
        {"group_id", "request_sha256", "attempt_sha256", "finish_reason",
         "input_tokens", "output_tokens", "model"},
        request_hashes, "usage_invalid")
    errors = _index_receipts(
        receipts["errors.jsonl"],
        {"group_id", "request_sha256", "attempt_sha256", "reason",
         "failed_attempt_cost_unknown", "model"},
        request_hashes, "errors_invalid")
    require(set(responses) == set(usage) and
            not set(responses).intersection(errors) and
            set(responses).union(errors) == set(request_hashes) and
            not {row["attempt_sha256"] for row in responses.values()}.intersection(
                row["attempt_sha256"] for row in errors.values()) and
            all(type(row["reason"]) is str and
                row["reason"] in TRANSIENT_FAILURES and
                row["model"] == evaluation["model"] and
                row["failed_attempt_cost_unknown"] is True
                for row in errors.values()),
            "split_outcomes_incomplete")
    # An accepted row has exactly one reported usage receipt for the same
    # physical attempt. Error receipts never become empty/no-match responses.
    parsed = {}
    invalid = set()
    input_tokens = output_tokens = 0
    for group in packet["groups"]:
        group_id = group["group_id"]
        if group_id in errors:
            continue
        response = responses[group_id]
        spent = usage[group_id]
        require(response["attempt_sha256"] == spent["attempt_sha256"] and
                response["model"] == spent["model"] == evaluation["model"] and
                spent["finish_reason"] == "STOP" and
                type(spent["input_tokens"]) is int and
                type(spent["output_tokens"]) is int and
                0 < spent["input_tokens"] <= 8_192 and
                0 <= spent["output_tokens"] <= 1_024 and
                type(response["raw_json"]) is str,
                "response_usage_invalid")
        input_tokens += spent["input_tokens"]
        output_tokens += spent["output_tokens"]
        try:
            parsed[group_id] = parse_source_id_output(
                response["raw_json"],
                [candidate["id"] for candidate in group["candidates"]])
        except SourceJudgmentError:
            invalid.add(group_id)
    return parsed, {
        "provider_failed_groups": len(errors),
        "invalid_model_outputs": len(invalid),
        "accepted_responses": len(parsed),
        "reported_input_tokens": input_tokens,
        "reported_output_tokens": output_tokens,
        "failed_attempt_cost_unknown": bool(errors),
    }


def score_split(packet: dict, labels: dict, selected: dict[str, tuple[str, ...]],
                receipt_counts: dict) -> dict:
    """Count every frozen group; errors/invalid outputs are quality misses."""
    split = packet["split"]
    label_groups = {row["group_id"]: row for row in labels["groups"]}
    counts = Counter()
    by_form: dict[str, Counter] = defaultdict(Counter)
    by_available: dict[int, Counter] = defaultdict(Counter)
    for group in packet["groups"]:
        group_id = group["group_id"]
        label_by_id = {row["id"]: row for row in
                       label_groups[group_id]["candidates"]}
        useful_ids = {source_id for source_id, row in label_by_id.items()
                      if row["page_useful"] and row["cue_useful"]}
        available = len(useful_ids)
        chosen = selected.get(group_id, ())
        chosen_labels = [label_by_id[source_id] for source_id in chosen]
        useful = sum(row["page_useful"] and row["cue_useful"]
                     for row in chosen_labels)
        completed = group_id in selected
        counts["groups"] += 1
        counts["positive_groups"] += available > 0
        counts["no_useful_groups"] += available == 0
        counts["available_useful_cards"] += available
        counts["displayed_cards"] += len(chosen)
        counts["displayed_useful_pages"] += sum(row["page_useful"]
                                                for row in chosen_labels)
        counts["displayed_useful_cues_and_pages"] += useful
        counts["positive_hit_at_three"] += available > 0 and useful > 0
        counts["useful_first"] += available > 0 and bool(chosen) and bool(
            chosen_labels[0]["page_useful"] and chosen_labels[0]["cue_useful"])
        counts["false_no_useful_displays"] += available == 0 and bool(chosen)
        counts["valid_no_useful_abstentions"] += available == 0 and completed and not chosen
        counts["cardinality_correct"] += available > 0 and set(chosen) == useful_ids
        form_name = label_groups[group_id]["form"]
        form = by_form[form_name]
        form["positive_groups"] += available > 0
        form["positive_hit_at_three"] += available > 0 and useful > 0
        bucket = by_available[available]
        bucket["groups"] += 1
        bucket["cardinality_correct"] += completed and set(chosen) == useful_ids
    successful = receipt_counts["accepted_responses"]
    failed = receipt_counts["provider_failed_groups"]
    completed_negatives = sum(group["group_id"] in selected for group in
                              packet["groups"] if
                              label_groups[group["group_id"]]["form"] == "no_useful")
    displayed = counts["displayed_cards"]
    useful = counts["displayed_useful_cues_and_pages"]
    availability = successful >= 46 and failed <= 2
    common = (receipt_counts["invalid_model_outputs"] == 0 and
              counts["false_no_useful_displays"] == 0 and
              counts["valid_no_useful_abstentions"] == completed_negatives and
              displayed > 0 and 10 * useful >= 9 * displayed)
    positive = counts["positive_groups"]
    if split == "calibration":
        quality = (common and counts["positive_hit_at_three"] >=
                  max(30, ceil_ratio(5, 6, positive)) and
                  all(by_form[name]["positive_hit_at_three"] >=
                      ceil_ratio(5, 6, by_form[name]["positive_groups"])
                      for name in FORMS[:3]))
    elif split == "heldout":
        quality = (common and counts["positive_hit_at_three"] >=
                  max(33, ceil_ratio(11, 12, positive)) and
                  counts["useful_first"] >=
                  max(31, ceil_ratio(31, 36, positive)) and
                  useful >= 60 and
                  counts["cardinality_correct"] >= ceil_ratio(5, 6, positive) and
                  all(by_form[name]["positive_hit_at_three"] >=
                      max(10, ceil_ratio(5, 6, by_form[name]["positive_groups"]))
                      for name in FORMS[:3]) and
                  all(by_available[amount]["cardinality_correct"] >=
                      ceil_ratio(5, 6, by_available[amount]["groups"])
                      for amount in (1, 2, 3)))
    else:
        raise ScoreError("split_invalid")
    passed = bool(availability and quality)
    return {
        "schema_version": SCORE_SCHEMA + "_metrics",
        "split": split, "public_passed": bool(passed),
        "availability_passed": availability,
        "source_quality_passed": bool(quality),
        "counts": {**dict(counts), **receipt_counts,
                   "completed_negative_groups": completed_negatives},
        "by_form": {name: dict(by_form[name]) for name in FORMS},
        "by_available": {str(amount): dict(by_available[amount])
                         for amount in range(4)},
        "displayed_cue_and_page_useful_fraction": useful / displayed if displayed else 0.0,
        "displayed_original_page_useful_fraction":
            counts["displayed_useful_pages"] / displayed if displayed else 0.0,
        "gate": {
            "minimum_successful_responses_per_split": 46,
            "failed_physical_attempts_count_as_misses": True,
            "completed_negative_responses_must_be_empty": True,
            "no_useful_display": 0,
            "all_displayed_cue_and_page_precision": 0.9,
            "calibration_positive": "max(30,ceil(5P/6)) and ceil(5P_form/6)",
            "heldout_positive": "max(33,ceil(11P/12))",
            "heldout_useful_first": "max(31,ceil(31P/36))",
            "heldout_useful_cards": 60,
            "heldout_cardinality":
                "exact useful ID set: ceil(5P/6) and ceil(5N/6) per positive stratum",
            "heldout_per_form_positive": "max(10,ceil(5P_form/6))",
        },
    }


def _score_one(frozen_dir: Path, results_dir: Path, freeze: dict,
               freeze_sha: str, split: str) -> tuple[dict, dict, set[str]]:
    packet, labels, packet_sha, labels_sha, request_hashes = _packet_and_labels(
        frozen_dir, freeze, split)
    evaluation, receipt_hashes, receipts = _result_receipts(
        results_dir, split, freeze_sha, packet_sha, labels_sha)
    selected, receipt_counts = _outcomes(
        packet, request_hashes, evaluation, receipts)
    metrics = score_split(packet, labels, selected, receipt_counts)
    safe = {
        "schema_version": SCORE_SCHEMA, "split": split,
        "corpus_id": freeze["corpus_id"], "source_manifest_sha256":
            freeze["source_manifest_sha256"],
        "freeze_sha256": freeze_sha, "packet_sha256": packet_sha,
        "labels_sha256": labels_sha, "receipt_sha256": receipt_hashes,
        "execution": {key: evaluation[key] for key in (
            "candidate_version", "prototype_sha256", "parser_sha256",
            "scorer_sha256", "model", "thinking", "automatic_retries")},
        "public_passed": metrics["public_passed"],
        "release_gate_passed": False, "metrics": metrics,
    }
    return safe, evaluation, {doc["sha256"] for doc in packet["documents"]}


def score_run(frozen_dir: Path, calibration_results: Path,
              heldout_results: Path | None = None) -> dict:
    """Score calibration first; never read heldout content on a failed gate."""
    require(frozen_dir.is_dir() and not frozen_dir.is_symlink() and
            calibration_results.is_dir() and
            not calibration_results.is_symlink(), "score_directory_invalid")
    freeze, freeze_sha = _freeze(frozen_dir)
    calibration, calibration_eval, calibration_docs = _score_one(
        frozen_dir, calibration_results, freeze, freeze_sha, "calibration")
    result = {
        "schema_version": SCORE_SCHEMA + "_run",
        "calibration": calibration,
        "calibration_passed": calibration["public_passed"],
        "heldout_opened": False,
        "release_gate_passed": False,
    }
    if not calibration["public_passed"] or heldout_results is None:
        return result
    require(heldout_results.is_dir() and not heldout_results.is_symlink(),
            "score_directory_invalid")
    heldout, heldout_eval, heldout_docs = _score_one(
        frozen_dir, heldout_results, freeze, freeze_sha, "heldout")
    require(not calibration_docs.intersection(heldout_docs) and
            calibration["execution"] == heldout["execution"] and
            calibration_eval["freeze_sha256"] == heldout_eval["freeze_sha256"],
            "heldout_independence_or_execution_changed")
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
        result = score_run(args.frozen_dir, args.calibration_results,
                           args.heldout_results)
        raw = canonical_bytes(result)
        if args.output is not None:
            with args.output.open("xb") as stream:
                stream.write(raw)
        else:
            sys.stdout.buffer.write(raw)
    except (OSError, ScoreError) as exc:
        code = str(exc) if isinstance(exc, ScoreError) else "score_io_failed"
        parser.exit(2, f"score failed: {code}\n")


if __name__ == "__main__":
    main()
