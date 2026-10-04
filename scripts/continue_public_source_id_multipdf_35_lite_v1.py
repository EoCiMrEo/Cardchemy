"""Offline, transport-injected continuation design for the frozen public pilot.

There is deliberately no provider adapter or live CLI. A later paid execution
requires a new, exact operator approval and a separately reviewed entry point.
The timed-out eleventh call is an uncertain physical attempt, never a result.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import json
import os
from pathlib import Path
import re
from tempfile import gettempdir
import time

import httpx

import evaluate_source_id_multipdf_35_lite as old_evaluator
from evaluate_source_id_multipdf_35_lite import (
    LABEL_SCHEMA, MODEL, PACKET_SHA256, THINKING, _fingerprint,
    _responses, _split_requests, _usage_receipts, ceil_ratio, digest, score,
    write_exclusive,
)
from finalize_public_source_id_multipdf import read_pinned
from prepare_public_source_id_multipdf import canonical_bytes
from run_public_source_id_multipdf_35_lite import (
    ENDPOINT, MAX_INPUT_PER_CALL, MAX_OUTPUT_PER_CALL,
    MAX_REST_REQUEST_BYTES, MIN_START_INTERVAL_SECONDS, PilotFailure,
    _canonical_json, _cost_microusd, _failure_code, _load_public_requests,
    _parse_provider_response, _rest_body, ensure,
)

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
import sys
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
from app.ai.source_judgment import parse_source_id_output  # noqa: E402


CONTINUATION_SCHEMA = "cardchemy_public_source_id_35_lite_continuation_v1"
APPROVAL_SCHEMA = CONTINUATION_SCHEMA + "_approval"
CALLER_FILENAME = "call_public_source_id_multipdf_35_lite_continuation_v1.py"
# Owner approved this exact public-only continuation envelope on 2026-09-30.
# A matching hash-bound receipt and fresh one-use claim are still required.
AUTHORIZATION_ID = "approved_public_flash_lite_continuation_20260930_v1"
LABELS_SHA256 = "bab352ebd06bc77d2bbbfa49f7e960d946bcb5af4d2346f943412c1699cd8ad1"
FREEZE_SHA256 = "114e122636eb1f8b6d334e550ac4aa0009fd34925238b035fd4721abf330cc51"
OLD_RUNNER_SHA256 = "31089ce26658610ff7d5c95246897538140e75ee7e7e0a89d4bd838ce62c1344"
OLD_EVALUATOR_SHA256 = "8efec637cf54f35c45003e0b3cdf8f534ca01bab766e5a2eab0f0d11909d4ac5"
OLD_APPROVAL_SHA256 = "ec9c6c0e52eb30019e51c9cb17458468a0eef257ac1476dd237748148754a6a8"
OLD_GLOBAL_CLAIM_SHA256 = "7cf9ee70f0869b11771391ceccc66f528c619794e11be5c579f8b815ba821ac5"
OLD_KNOWN_INPUT = 13_046
OLD_KNOWN_OUTPUT = 178
OLD_KNOWN_COST_MICROUSD = 4_363
MAX_NEW_CALLS = 85  # Only calibration 12–48 plus conditional heldout 1–48.
MAX_NEW_INPUT_TOKENS = MAX_NEW_CALLS * MAX_INPUT_PER_CALL
MAX_NEW_OUTPUT_TOKENS = MAX_NEW_CALLS * MAX_OUTPUT_PER_CALL
MAX_NEW_COST_MICROUSD = 500_000
MAX_CALL_SECONDS = 90
MAX_TOTAL_SECONDS = 180 * 60
MIN_SUCCESSFUL_PER_SPLIT = 46
MAX_FAILED_PER_SPLIT = 48 - MIN_SUCCESSFUL_PER_SPLIT
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")

_OLD_FILE_SHA256 = {
    "call-01.claim": "4b67e50e393b921de2d0d057e082514210f7cade6b755365b765aec0469453ab",
    "call-02.claim": "afc4d6fd53ebe5e2e87a857347d7fc836c787111dd5d5e8a671eb9ecb5f3e47b",
    "call-03.claim": "db2d1c357cc7354d472194e55e87a2a860085f25436479875a6919bea45ef142",
    "call-04.claim": "c7c7ad555c01b4fca0bebb68447850aa7f265cdff7f7329352dd60ff15bd41eb",
    "call-05.claim": "c9d49f6708d5885ca4a34678abaf7a250971382903e5c81560e294ac1ccde0db",
    "call-06.claim": "fcdb8c72c445b93bf0e688a30160acf91c30a462151b527466bbe066aadea2c0",
    "call-07.claim": "72c00cca4aefeb73b74ca22aa4f4c9825e2f899aaa944d60655f3f8bbca550e5",
    "call-08.claim": "52ae00329506152290a8a286bf987e834e818993386cfb5259e286b84ba9d7f0",
    "call-09.claim": "4d714f7c574d19a5a45e0105f520d371d8d88a7f5e229e7bcb45297314e7fa29",
    "call-10.claim": "37146b141bd0c1763a66c579f2596eccbff5f46258a3c06fe34470b2066c5f69",
    "call-11.claim": "b8c2d8c8a7b024f9990670e7ad685cf84800c3f88f520eee2f725eb45172bd77",
    "live-failure.json": "8a75d4be1c0cfbc12d00bcc8317ee2c57158aca75b80e1b73d0baa0bbc49e79a",
    "live-run.claim": OLD_GLOBAL_CLAIM_SHA256,
    "prepare-receipt.json": "6ce0540c4527a36ff2beed14a0bffd619972bed191b3b883e15fd7947a24eb0b",
    "requests.json": "70a3983993da01043b57272e3d7800ed2a964ea2a4000fa9495ab8ba21966763",
    "response-ids.jsonl": "ef208f1580e564db02021151537194404866281696fb1c2dbac8a63ae4d75104",
    "usage-receipts.jsonl": "fe3c4851396eb7bb3c75b02c631d7f9094e1a517248982d9395752da1191b9de",
}


def _read_lines(path: Path, *, expected: int | None,
                max_bytes: int) -> list[dict]:
    ensure(path.is_file() and not path.is_symlink() and
           path.stat().st_size <= max_bytes, "checkpoint_lines_invalid")
    raw = path.read_bytes()
    lines = raw.splitlines(keepends=True)
    ensure((expected is None or len(lines) == expected) and
           len(lines) <= 48 and b"\r" not in raw and
           all(line.endswith(b"\n") and len(line) <= 4_096 for line in lines),
           "checkpoint_lines_invalid")
    values = []
    for line in lines:
        try:
            value = json.loads(line)
        except (UnicodeError, ValueError) as exc:
            raise PilotFailure("checkpoint_lines_invalid") from exc
        ensure(type(value) is dict and canonical_bytes(value) == line,
               "checkpoint_lines_invalid")
        values.append(value)
    return values


def _exact_file(path: Path, expected_sha: str, max_bytes: int) -> bytes:
    ensure(path.is_file() and not path.is_symlink() and
           path.stat().st_size <= max_bytes, "checkpoint_file_changed")
    raw = path.read_bytes()
    ensure(digest(raw) == expected_sha, "checkpoint_file_changed")
    return raw


def _source_judgment_sha256() -> str:
    path = _BACKEND / "app/ai/source_judgment.py"
    ensure(path.is_file() and not path.is_symlink() and
           path.stat().st_size <= 100_000, "source_judgment_file_unavailable")
    return digest(path.read_bytes())


def prior_display_viability(rows: list[dict],
                            selected_by_group: dict[str, tuple[str, ...]],
                            labels: dict) -> dict:
    """Reject any irreversible violation already present in accepted receipts."""
    ensure(labels.get("schema") == LABEL_SCHEMA and
           labels.get("packet_sha256") == PACKET_SHA256 and
           type(labels.get("groups")) is list and len(labels["groups"]) == 96 and
           len(rows) == len(selected_by_group) == 10,
           "prior_labels_invalid")
    label_groups = {group["group_id"]: group for group in labels["groups"]
                    if group["split"] == "calibration"}
    ensure(len(label_groups) == 48, "prior_labels_invalid")
    negative = false_display = displayed = weak_displayed = 0
    for row in rows:
        group_id = row["group_id"]
        ensure(group_id in label_groups and group_id in selected_by_group,
               "prior_labels_invalid")
        group = label_groups[group_id]
        by_id = {item["id"]: item for item in group["labels"]}
        issued = {item["id"] for item in row["wire"]["user_payload"]["candidates"]}
        ensure(len(by_id) == 4 and set(by_id) == issued and
               all(type(item["page_useful"]) is bool and
                   type(item["cue_useful"]) is bool
                   for item in group["labels"]), "prior_labels_invalid")
        selected = selected_by_group[group_id]
        available = any(item["page_useful"] and item["cue_useful"]
                        for item in group["labels"])
        negative += not available
        false_display += not available and bool(selected)
        displayed += len(selected)
        weak_displayed += sum(not (by_id[source_id]["page_useful"] and
                                   by_id[source_id]["cue_useful"])
                              for source_id in selected)
    ensure(false_display == 0, "prior_false_no_useful_display_irreversible")
    return {"prior_negative_groups": negative,
            "prior_negative_false_displays": false_display,
            "prior_displayed_cards": displayed,
            "prior_weak_displayed_cards": weak_displayed}


def validate_prior(prior_dir: Path, packet_dir: Path, labels_path: Path,
                   old_approval_path: Path) -> tuple[dict, dict, dict]:
    """Pin exact old bytes and verify all ten accepted pairs without scoring."""
    ensure(prior_dir.is_dir() and not prior_dir.is_symlink(),
           "checkpoint_input_invalid")
    source_dir = Path(__file__).resolve().parent
    _exact_file(source_dir / "run_public_source_id_multipdf_35_lite.py",
                OLD_RUNNER_SHA256, 100_000)
    _exact_file(source_dir / "evaluate_source_id_multipdf_35_lite.py",
                OLD_EVALUATOR_SHA256, 100_000)
    for name, expected_sha in _OLD_FILE_SHA256.items():
        _exact_file(prior_dir / name, expected_sha,
                    1_000_000 if name == "requests.json" else 256_000)
    ensure({path.name for path in prior_dir.glob("call-*.claim")} ==
           {f"call-{n:02d}.claim" for n in range(1, 12)},
           "checkpoint_claim_count_invalid")
    _exact_file(old_approval_path, OLD_APPROVAL_SHA256, 4_096)
    old_scope = digest(canonical_bytes({
        "authorization_id": old_evaluator.AUTHORIZATION_ID,
        "split": "calibration",
    }))
    old_global_claim = (Path(gettempdir()).resolve() /
                        "cardchemy-source-id-35-lite-pilot-ledger" /
                        f"approval-{old_scope}.claim")
    _exact_file(old_global_claim, OLD_GLOBAL_CLAIM_SHA256, 4_096)
    _exact_file(labels_path, LABELS_SHA256, 100_000)
    _exact_file(labels_path.parent / "freeze-receipt.json", FREEZE_SHA256, 8_192)
    prepared, receipt = _load_public_requests(
        prior_dir, _OLD_FILE_SHA256["prepare-receipt.json"], packet_dir)
    ensure(prepared["split"] == "calibration" and
           receipt["labels_sha256"] == LABELS_SHA256 and
           receipt["freeze_receipt_sha256"] == FREEZE_SHA256 and
           receipt["fingerprint"] ==
           _fingerprint(PACKET_SHA256, LABELS_SHA256, FREEZE_SHA256) and
           receipt["callable_count"] == 48 and
           receipt["clarification_count"] == 0,
           "checkpoint_contract_mismatch")
    old_approval = _canonical_json(old_approval_path, 4_096)
    old_claim = _canonical_json(prior_dir / "live-run.claim", 4_096)
    ensure(old_approval.get("authorization_id") == old_evaluator.AUTHORIZATION_ID and
           old_approval.get("operator_approved") is True and
           old_approval.get("model") == MODEL and
           old_approval.get("split") == "calibration" and
           old_approval.get("requests_sha256") == receipt["requests_sha256"] and
           old_claim.get("approval_sha256") == OLD_APPROVAL_SHA256 and
           old_claim.get("requests_sha256") == receipt["requests_sha256"] and
           old_claim.get("fingerprint") == receipt["fingerprint"] and
           _canonical_json(old_global_claim, 4_096) == old_claim,
           "checkpoint_approval_mismatch")
    failure = _canonical_json(prior_dir / "live-failure.json", 4_096)
    ensure(failure.get("status") == "stopped_no_retry" and
           failure.get("reason") == "provider_timeout" and
           failure.get("attempts") == 11 and
           failure.get("failed_attempt_cost_unknown") is True and
           failure.get("known_cost_microusd") == OLD_KNOWN_COST_MICROUSD,
           "checkpoint_failure_mismatch")
    rows = prepared["requests"]
    ensure(len(rows) == 48 and len({r["group_id"] for r in rows}) == 48,
           "checkpoint_groups_invalid")
    response_lines = _read_lines(prior_dir / "response-ids.jsonl",
                                 expected=10, max_bytes=16_384)
    usage_lines = _read_lines(prior_dir / "usage-receipts.jsonl",
                              expected=10, max_bytes=16_384)
    input_total = output_total = cost_total = 0
    prior_selected: dict[str, tuple[str, ...]] = {}
    for index, row in enumerate(rows[:11], start=1):
        claim = _canonical_json(prior_dir / f"call-{index:02d}.claim", 1_024)
        ensure(row["status"] == "callable" and claim == {
            "group_id": row["group_id"], "wire_sha256": row["wire_sha256"]},
            "checkpoint_claim_mismatch")
        if index == 11:
            continue  # A claim plus timeout is never an accepted selection.
        response, usage = response_lines[index - 1], usage_lines[index - 1]
        ensure(set(response) == {"group_id", "wire_sha256", "raw_json"} and
               response["group_id"] == row["group_id"] and
               response["wire_sha256"] == row["wire_sha256"] and
               type(response["raw_json"]) is str,
               "checkpoint_response_mismatch")
        issued = [c["id"] for c in row["wire"]["user_payload"]["candidates"]]
        try:
            prior_selected[row["group_id"]] = parse_source_id_output(
                response["raw_json"], issued)
        except Exception as exc:
            raise PilotFailure("checkpoint_response_mismatch") from exc
        ensure(set(usage) == {"group_id", "finish_reason", "input_tokens",
                              "output_tokens", "cost_microusd"} and
               usage["group_id"] == row["group_id"] and
               usage["finish_reason"] == "STOP" and
               type(usage["input_tokens"]) is int and
               type(usage["output_tokens"]) is int and
               0 < usage["input_tokens"] <= MAX_INPUT_PER_CALL and
               0 <= usage["output_tokens"] <= MAX_OUTPUT_PER_CALL and
               usage["cost_microusd"] == _cost_microusd(
                   usage["input_tokens"], usage["output_tokens"]),
               "checkpoint_usage_mismatch")
        input_total += usage["input_tokens"]
        output_total += usage["output_tokens"]
        cost_total += usage["cost_microusd"]
    ensure((input_total, output_total, cost_total) ==
           (OLD_KNOWN_INPUT, OLD_KNOWN_OUTPUT, OLD_KNOWN_COST_MICROUSD),
           "checkpoint_usage_total_mismatch")
    labels = read_pinned(labels_path, LABELS_SHA256, 100_000)
    viability = prior_display_viability(rows[:10], prior_selected, labels)
    checkpoint = {
        "schema": CONTINUATION_SCHEMA + "_prior_checkpoint",
        "source_packet_sha256": PACKET_SHA256,
        "labels_sha256": LABELS_SHA256,
        "freeze_receipt_sha256": FREEZE_SHA256,
        "fingerprint": receipt["fingerprint"],
        "old_approval_sha256": OLD_APPROVAL_SHA256,
        "old_global_claim_sha256": OLD_GLOBAL_CLAIM_SHA256,
        "old_runner_sha256": OLD_RUNNER_SHA256,
        "old_evaluator_sha256": OLD_EVALUATOR_SHA256,
        "source_judgment_sha256": _source_judgment_sha256(),
        "old_files_sha256": _OLD_FILE_SHA256,
        "prior_accepted_groups": 10,
        "prior_uncertain_group_number": 11,
        "prior_known_input_tokens": input_total,
        "prior_known_output_tokens": output_total,
        "prior_known_cost_microusd": cost_total,
        "prior_timeout_cost_unknown": True,
        **viability,
    }
    return prepared, receipt, checkpoint


def _caller_sha256() -> str:
    """Bind exact live-adapter bytes without importing or executing them."""
    path = Path(__file__).with_name(CALLER_FILENAME)
    ensure(path.is_file() and not path.is_symlink() and
           path.stat().st_size <= 100_000, "caller_file_unavailable")
    return digest(path.read_bytes())


def approval_template(checkpoint: dict) -> dict:
    """Exact future receipt shape; this template is not an approval."""
    return {
        "schema": APPROVAL_SCHEMA,
        "authorization_id": AUTHORIZATION_ID,
        "operator_approved": True,
        "public_only": True,
        "prior_checkpoint_sha256": digest(canonical_bytes(checkpoint)),
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "caller_sha256": _caller_sha256(),
        "source_judgment_sha256": _source_judgment_sha256(),
        "source_packet_sha256": PACKET_SHA256,
        "labels_sha256": LABELS_SHA256,
        "freeze_receipt_sha256": FREEZE_SHA256,
        "fingerprint": checkpoint["fingerprint"],
        "endpoint": ENDPOINT, "model": MODEL, "thinking": THINKING,
        "store": False,
        "split_sequence": ["calibration", "heldout_if_calibration_passed"],
        "max_new_calibration_calls": 37,
        "max_new_heldout_calls": 48,
        "max_new_physical_calls": MAX_NEW_CALLS,
        "max_new_input_tokens": MAX_NEW_INPUT_TOKENS,
        "max_new_output_tokens": MAX_NEW_OUTPUT_TOKENS,
        "max_new_cost_microusd": MAX_NEW_COST_MICROUSD,
        "max_input_tokens_per_call": MAX_INPUT_PER_CALL,
        "max_output_tokens_per_call": MAX_OUTPUT_PER_CALL,
        "max_rest_request_bytes": MAX_REST_REQUEST_BYTES,
        "max_call_seconds": MAX_CALL_SECONDS,
        "max_total_seconds": MAX_TOTAL_SECONDS,
        "min_start_interval_seconds": MIN_START_INTERVAL_SECONDS,
        "automatic_retries": 0,
        "minimum_successful_responses_per_split": MIN_SUCCESSFUL_PER_SPLIT,
        "http_429_policy": "stop_without_retry",
        "prior_timeout_policy": "failed_case_11_no_replay",
        "input_price_usd_per_million": "0.30",
        "output_price_usd_per_million": "2.50",
        "prior_known_cost_microusd": OLD_KNOWN_COST_MICROUSD,
        "prior_timeout_cost_unknown": True,
        "earlier_failed_costs_unknown": True,
    }


def validate_approval(path: Path, approval_sha: str, checkpoint: dict) -> dict:
    ensure(AUTHORIZATION_ID != "PENDING_SEPARATE_OPERATOR_APPROVAL",
           "separate_operator_approval_required")
    ensure(type(approval_sha) is str and _HEX64.fullmatch(approval_sha),
           "approval_hash_required")
    value = _canonical_json(path, 8_192)
    ensure(digest(path.read_bytes()) == approval_sha and
           value == approval_template(checkpoint), "approval_envelope_mismatch")
    return value


def _approval_claim_path(checkpoint_sha: str) -> Path:
    ensure(_HEX64.fullmatch(checkpoint_sha), "checkpoint_hash_required")
    directory = Path(gettempdir()).resolve() / "cardchemy-source-id-35-lite-continuation-v1-ledger"
    directory.mkdir(mode=0o700 if os.name != "nt" else 0o777, exist_ok=True)
    ensure(directory.is_dir() and not directory.is_symlink(),
           "continuation_ledger_unavailable")
    scope = digest(canonical_bytes({"schema": CONTINUATION_SCHEMA,
                                    "authorization_id": AUTHORIZATION_ID,
                                    "checkpoint_sha256": checkpoint_sha}))
    return directory / f"approval-{scope}.claim"


def _append_sync(path: Path, value: dict) -> None:
    with path.open("ab") as stream:
        stream.write(canonical_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())


TRANSIENT_FAILURES = frozenset({
    "provider_timeout", "provider_http_408", "provider_http_502",
    "provider_http_503", "provider_http_504", "provider_connect_error",
    "provider_network_error", "provider_protocol_error",
    "provider_transport_error",
})


def score_failure_inclusive(prepared: dict, labels: dict,
                            responses: dict[str, tuple[str, ...]],
                            errors: dict[str, str]) -> dict:
    """Score every frozen group; a physical failure is a miss, never no-match."""
    rows = prepared["requests"]
    group_ids = [row["group_id"] for row in rows]
    ensure(len(rows) == len(set(group_ids)) == 48 and
           all(row["status"] == "callable" for row in rows) and
           not set(responses).intersection(errors) and
           set(responses).union(errors) == set(group_ids) and
           all(reason in TRANSIENT_FAILURES for reason in errors.values()),
           "split_outcomes_incomplete")
    old_metrics = score(prepared, labels, {
        **responses, **{group_id: None for group_id in errors},
    })
    counts = old_metrics["counts"]
    ensure(counts.get("invalid_model_outputs", 0) == len(errors),
           "split_response_invalid")
    split_labels = {group["group_id"]: group for group in labels["groups"]
                    if group["split"] == prepared["split"]}
    failed_negative = sum(
        not any(item["page_useful"] and item["cue_useful"]
                for item in split_labels[group_id]["labels"])
        for group_id in errors
    )
    failed_positive = len(errors) - failed_negative
    completed_negative = counts["no_useful_groups"] - failed_negative
    displayed = counts.get("displayed_cards", 0)
    useful = counts.get("displayed_useful_cues_and_pages", 0)
    availability = 48 - len(errors) >= MIN_SUCCESSFUL_PER_SPLIT
    common = (counts.get("false_no_useful_displays", 0) == 0 and
              counts.get("valid_no_useful_abstentions", 0) == completed_negative and
              displayed > 0 and 10 * useful >= 9 * displayed)
    positive = counts["positive_groups"]
    forms = old_metrics["by_form"]
    if prepared["split"] == "calibration":
        quality = (common and counts.get("positive_hit_at_three", 0) >=
                   max(30, ceil_ratio(5, 6, positive)) and
                   all(row.get("positive_hit_at_three", 0) >=
                       ceil_ratio(5, 6, row["positive_groups"])
                       for row in forms.values()))
    elif prepared["split"] == "heldout":
        quality = (common and counts.get("positive_hit_at_three", 0) >=
                   max(33, ceil_ratio(11, 12, positive)) and
                   counts.get("useful_first", 0) >=
                   max(31, ceil_ratio(31, 36, positive)) and
                   useful >= 60 and
                   counts.get("cardinality_correct", 0) >=
                   ceil_ratio(5, 6, positive) and
                   all(row.get("positive_hit_at_three", 0) >=
                       max(10, ceil_ratio(5, 6, row["positive_groups"]))
                       for row in forms.values()) and
                   all(row.get("cardinality_correct", 0) >=
                       ceil_ratio(5, 6, row["groups"])
                       for amount, row in old_metrics["by_available"].items()
                       if int(amount) > 0))
    else:
        raise PilotFailure("split_invalid")
    reported_counts = dict(counts)
    # The old scorer uses None for malformed output. Here None is a separately
    # claimed physical failure, so its inherited label would misstate evidence.
    reported_counts["invalid_model_outputs"] = 0
    reported_counts["provider_unavailable_groups"] = len(errors)
    return {
        **old_metrics,
        "schema": CONTINUATION_SCHEMA + "_metrics",
        "counts": reported_counts,
        "public_passed": bool(availability and quality),
        "availability_passed": availability,
        "source_quality_passed": bool(quality),
        "availability_successful": 48 - len(errors),
        "availability_failed": len(errors),
        "failed_positive_groups": failed_positive,
        "failed_negative_groups": failed_negative,
        "completed_negative_abstentions": completed_negative,
        "gate": {
            **old_metrics["gate"],
            "minimum_successful_responses_per_split": MIN_SUCCESSFUL_PER_SPLIT,
            "failed_physical_attempts_count_as_misses": True,
            "completed_negative_responses_must_be_empty": True,
            "all_displayed_cue_and_page_precision": 0.9,
        },
    }


def _score_split(prepared: dict, labels: dict, response_path: Path,
                 usage_path: Path, error_path: Path, output: Path,
                 *, prior_response: bytes = b"", prior_usage: bytes = b"") -> dict:
    rows = prepared["requests"]
    split = prepared["split"]
    error_rows = _read_lines(error_path, expected=None, max_bytes=16_384)
    errors: dict[str, str] = {}
    by_group = {row["group_id"]: (number, row)
                for number, row in enumerate(rows, start=1)}
    ensure(len(by_group) == 48, "split_groups_invalid")
    for item in error_rows:
        ensure(set(item) == {"group_id", "wire_sha256", "reason", "origin",
                             "claim_sha256"} and
               item["group_id"] in by_group and
               item["group_id"] not in errors and
               item["reason"] in TRANSIENT_FAILURES,
               "split_error_invalid")
        number, row = by_group[item["group_id"]]
        ensure(item["wire_sha256"] == row["wire_sha256"],
               "split_error_identity_invalid")
        if split == "calibration" and number == 11:
            ensure(item["origin"] == "prior" and
                   item["reason"] == "provider_timeout" and
                   item["claim_sha256"] == _OLD_FILE_SHA256["call-11.claim"],
                   "prior_timeout_changed")
        else:
            ensure(item["origin"] == "new" and
                   item["claim_sha256"] == digest(canonical_bytes({
                       "group_id": row["group_id"],
                       "wire_sha256": row["wire_sha256"],
                       "split": split, "number": number,
                   })), "split_error_claim_invalid")
        errors[item["group_id"]] = item["reason"]
    if split == "calibration":
        ensure(rows[10]["group_id"] in errors and
               not any(row["group_id"] in errors for row in rows[:10]) and
               response_path.read_bytes().startswith(prior_response) and
               usage_path.read_bytes().startswith(prior_usage) and
               bool(prior_response) and bool(prior_usage),
               "prior_checkpoint_changed")
    successful_rows = [row for row in rows if row["group_id"] not in errors]
    # The frozen parser checks issued IDs, uniqueness, count and ordering.
    responses = _responses(response_path, successful_rows)
    inputs, outputs, cost = _usage_receipts(usage_path, successful_rows)
    ensure(len(responses) + len(errors) == 48 and
           all(selected is not None for selected in responses.values()) and
           inputs <= 48 * MAX_INPUT_PER_CALL and
           outputs <= 48 * MAX_OUTPUT_PER_CALL,
           "split_incomplete")
    for number, row in enumerate(rows, start=1):
        if split == "calibration" and number <= 11:
            continue
        claim = _canonical_json(output / f"{split}-{number:02d}.claim", 1_024)
        ensure(claim == {"group_id": row["group_id"],
                         "wire_sha256": row["wire_sha256"],
                         "split": split, "number": number},
               "split_claim_missing")
    metrics = score_failure_inclusive(prepared, labels, responses, errors)
    result = {"schema": CONTINUATION_SCHEMA + "_score",
              "split": split,
              "fingerprint": prepared["fingerprint"],
              "requests_sha256": digest(canonical_bytes(prepared)),
              "responses_sha256": digest(response_path.read_bytes()),
              "usage_sha256": digest(usage_path.read_bytes()),
              "errors_sha256": digest(error_path.read_bytes()),
              "input_tokens": inputs, "output_tokens": outputs,
              "known_cost_microusd": cost,
              "public_passed": metrics["public_passed"],
              "release_gate_passed": False, "metrics": metrics}
    write_exclusive(output / f"{split}-score.json", result)
    return result


async def run_with_transport(
    prior_dir: Path, packet_dir: Path, labels_path: Path,
    old_approval_path: Path, new_approval_path: Path, new_approval_sha: str,
    output: Path, transport: Callable[[dict], Awaitable[httpx.Response]],
    *, clock: Callable[[], float] = time.monotonic,
    wall_clock: Callable[[], float] = time.time,
    sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> dict:
    """Exercise the prospective flow with an injected transport only.

    This module has no live entry point, credential reader or HTTP client. A
    separate exact approval and reviewed caller would be needed for any paid
    use. Every physical attempt gets one exclusive claim before transport.
    """
    prepared, _receipt, checkpoint = validate_prior(
        prior_dir, packet_dir, labels_path, old_approval_path)
    validate_approval(new_approval_path, new_approval_sha, checkpoint)
    temp = Path(gettempdir()).resolve()
    ensure(output.is_absolute() and temp in output.resolve().parents and
           not output.exists() and output.parent.is_dir() and
           all(output.resolve() != path.resolve() and
               path.resolve() not in output.resolve().parents
               for path in (prior_dir, packet_dir, labels_path.parent,
                            old_approval_path.parent,
                            temp / "cardchemy-source-id-35-lite-pilot-ledger")) and
           not output.parent.is_symlink(), "os_temp_output_required")
    checkpoint_sha = digest(canonical_bytes(checkpoint))
    claim_path = _approval_claim_path(checkpoint_sha)
    ensure(not claim_path.exists() and not claim_path.is_symlink(),
           "continuation_claim_consumed")
    ensure(MAX_NEW_CALLS * _cost_microusd(
        MAX_INPUT_PER_CALL, MAX_OUTPUT_PER_CALL) <= MAX_NEW_COST_MICROUSD,
        "reservation_budget")
    prior_response = _exact_file(prior_dir / "response-ids.jsonl",
                                 _OLD_FILE_SHA256["response-ids.jsonl"], 16_384)
    prior_usage = _exact_file(prior_dir / "usage-receipts.jsonl",
                              _OLD_FILE_SHA256["usage-receipts.jsonl"], 16_384)
    output.mkdir(mode=0o700 if os.name != "nt" else 0o777)
    write_exclusive(claim_path, {"schema": CONTINUATION_SCHEMA + "_claim",
                                 "checkpoint_sha256": checkpoint_sha,
                                 "approval_sha256": new_approval_sha,
                                 "output_name": output.name})
    write_exclusive(output / "run.claim", {
        "schema": CONTINUATION_SCHEMA + "_run_claim",
        "checkpoint_sha256": checkpoint_sha,
        "approval_sha256": new_approval_sha,
        "started_unix_ms": int(wall_clock() * 1000)})
    write_exclusive(output / "prior-checkpoint.json", checkpoint)
    calibration_dir = output / "calibration"
    calibration_dir.mkdir()
    response_path = calibration_dir / "response-ids.jsonl"
    usage_path = calibration_dir / "usage-receipts.jsonl"
    error_path = calibration_dir / "errors.jsonl"
    with response_path.open("xb") as stream:
        stream.write(prior_response)
        stream.flush()
        os.fsync(stream.fileno())
    with usage_path.open("xb") as stream:
        stream.write(prior_usage)
        stream.flush()
        os.fsync(stream.fileno())
    with error_path.open("xb") as stream:
        stream.write(canonical_bytes({
            "group_id": prepared["requests"][10]["group_id"],
            "wire_sha256": prepared["requests"][10]["wire_sha256"],
            "reason": "provider_timeout", "origin": "prior",
            "claim_sha256": _OLD_FILE_SHA256["call-11.claim"],
        }))
        stream.flush()
        os.fsync(stream.fileno())
    labels = read_pinned(labels_path, LABELS_SHA256, 100_000)
    started = clock()
    previous_start: float | None = None
    calls = accepted = input_total = output_total = known_cost = 0
    current_split = "calibration"
    heldout_opened = False
    calibration_passed = False

    async def call_rows(rows: list[dict], split: str, first_number: int,
                        responses: Path, usage: Path, errors: Path,
                        initial_failures: int) -> None:
        nonlocal calls, accepted, input_total, output_total, known_cost, previous_start
        failures = initial_failures
        for number, row in enumerate(rows, start=first_number):
            ensure(row["status"] == "callable", "callable_row_required")
            _rest_body(row["wire"])
            if previous_start is not None:
                delay = MIN_START_INTERVAL_SECONDS - (clock() - previous_start)
                if delay > 0:
                    await sleeper(delay)
            elapsed = clock() - started
            remaining = MAX_TOTAL_SECONDS - elapsed
            reservation = calls + 1
            ensure(remaining > 0 and reservation <= MAX_NEW_CALLS and
                   reservation * MAX_INPUT_PER_CALL <= MAX_NEW_INPUT_TOKENS and
                   reservation * MAX_OUTPUT_PER_CALL <= MAX_NEW_OUTPUT_TOKENS and
                   reservation * _cost_microusd(
                       MAX_INPUT_PER_CALL, MAX_OUTPUT_PER_CALL) <=
                   MAX_NEW_COST_MICROUSD, "remaining_budget")
            call_claim = {
                "group_id": row["group_id"],
                "wire_sha256": row["wire_sha256"],
                "split": split, "number": number,
            }
            claim_sha = write_exclusive(output / f"{split}-{number:02d}.claim",
                                        call_claim)
            previous_start = clock()
            calls += 1
            try:
                response = await asyncio.wait_for(
                    transport(row["wire"]),
                    timeout=min(MAX_CALL_SECONDS, remaining))
                issued = [c["id"] for c in
                          row["wire"]["user_payload"]["candidates"]]
                raw_json, used_input, used_output = _parse_provider_response(
                    response, issued)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                code = _failure_code(exc)
                # Quota/429 and permanent HTTP or schema failures stop. An
                # uncertain transient consumes this case without a replay.
                if code not in TRANSIENT_FAILURES:
                    raise
                _append_sync(errors, {
                    "group_id": row["group_id"],
                    "wire_sha256": row["wire_sha256"],
                    "reason": code, "origin": "new",
                    "claim_sha256": claim_sha,
                })
                failures += 1
                if failures > MAX_FAILED_PER_SPLIT:
                    raise PilotFailure("availability_gate_unreachable") from None
                continue
            cost = _cost_microusd(used_input, used_output)
            ensure(input_total + used_input <= MAX_NEW_INPUT_TOKENS and
                   output_total + used_output <= MAX_NEW_OUTPUT_TOKENS and
                   known_cost + cost <= MAX_NEW_COST_MICROUSD,
                   "observed_budget")
            input_total += used_input
            output_total += used_output
            known_cost += cost
            _append_sync(responses, {"group_id": row["group_id"],
                                     "wire_sha256": row["wire_sha256"],
                                     "raw_json": raw_json})
            _append_sync(usage, {"group_id": row["group_id"],
                                 "finish_reason": "STOP",
                                 "input_tokens": used_input,
                                 "output_tokens": used_output,
                                 "cost_microusd": cost})
            accepted += 1

    try:
        # Group 11 has an immutable old claim and timeout; it is never sent.
        await call_rows(prepared["requests"][11:], "calibration", 12,
                        response_path, usage_path, error_path, 1)
        calibration = _score_split(
            prepared, labels, response_path, usage_path, error_path, output,
            prior_response=prior_response, prior_usage=prior_usage)
        if not calibration["public_passed"]:
            result = {"status": "calibration_gate_failed",
                      "calibration_passed": False, "heldout_opened": False}
        else:
            calibration_passed = True
            # Recompute every score input before opening the independent split.
            ensure(digest(response_path.read_bytes()) ==
                   calibration["responses_sha256"] and
                   digest(usage_path.read_bytes()) == calibration["usage_sha256"] and
                   digest(error_path.read_bytes()) == calibration["errors_sha256"] and
                   calibration["metrics"]["public_passed"] is True,
                   "calibration_gate_changed")
            source = read_pinned(packet_dir / "blind-review-packet.json",
                                 PACKET_SHA256, 1_000_000)
            heldout_rows = _split_requests(source, "heldout")
            ensure(len(heldout_rows) == 48 and
                   len({r["group_id"] for r in heldout_rows}) == 48 and
                   not {r["group_id"] for r in heldout_rows}.intersection(
                       r["group_id"] for r in prepared["requests"]),
                   "heldout_groups_invalid")
            heldout = dict(prepared, split="heldout", requests=heldout_rows)
            heldout_dir = output / "heldout"
            heldout_dir.mkdir()
            heldout_response = heldout_dir / "response-ids.jsonl"
            heldout_usage = heldout_dir / "usage-receipts.jsonl"
            heldout_errors = heldout_dir / "errors.jsonl"
            heldout_response.touch(exist_ok=False)
            heldout_usage.touch(exist_ok=False)
            heldout_errors.touch(exist_ok=False)
            heldout_opened = True
            current_split = "heldout"
            await call_rows(heldout_rows, "heldout", 1,
                            heldout_response, heldout_usage, heldout_errors, 0)
            heldout_score = _score_split(
                heldout, labels, heldout_response, heldout_usage,
                heldout_errors, output)
            result = {"status": "public_pilot_complete",
                      "calibration_passed": True, "heldout_opened": True,
                      "heldout_passed": heldout_score["public_passed"],
                      "release_gate_passed": False}
    except (Exception, asyncio.CancelledError) as exc:
        reason = (_failure_code(exc) if not
                  (isinstance(exc, PilotFailure) and exc.args and
                   exc.args[0] == "availability_gate_unreachable") else
                  "availability_gate_unreachable")
        result = {"status": "stopped_no_replay",
                  "reason": reason,
                  "calibration_passed": calibration_passed,
                  "heldout_opened": heldout_opened,
                  "failed_attempt_cost_unknown": calls > accepted,
                  "release_gate_passed": False}
        if result["reason"].startswith("provider_http_"):
            result["http_status"] = int(result["reason"].split("_")[-1])
            result["reason"] = "provider_http_error"
    result.update({"schema": CONTINUATION_SCHEMA,
                   "split_at_stop": current_split,
                   "prior_accepted_groups": 10,
                   "prior_uncertain_group_number": 11,
                   "prior_timeout_cost_unknown": True,
                   "release_gate_passed": False,
                   "new_physical_calls": calls,
                   "new_accepted_responses": accepted,
                   "new_unreceipted_calls": calls - accepted,
                   "failed_attempt_cost_unknown": calls > accepted,
                   "new_reserved_cost_microusd": calls * _cost_microusd(
                       MAX_INPUT_PER_CALL, MAX_OUTPUT_PER_CALL),
                   "new_input_tokens": input_total,
                   "new_output_tokens": output_total,
                   "new_known_cost_microusd": known_cost})
    write_exclusive(output / "pilot-result.json", result)
    return result
