"""Keyless-preflightable, public-only inline Batch source-ID evaluation.

This is an experiment tool, never an Ask runtime. Gemini Batch creation is not
idempotent: every POST has a durable claim before egress and is never replayed.
Polling is GET-only. Live modes remain fenced until a *separate Batch-specific*
approval is bound to this exact source file and the frozen public packet.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable
from decimal import Decimal, ROUND_CEILING
import json
import os
from pathlib import Path
import re
import sys
from tempfile import gettempdir
import time

import httpx

from evaluate_source_id_multipdf_36 import (
    MODEL, PACKET_SHA256, SCHEMA, _responses, digest, prepare, score,
    write_exclusive,
)
from finalize_public_source_id_multipdf import LABEL_SCHEMA, read_pinned
from prepare_public_source_id_multipdf import canonical_bytes
from run_public_source_id_multipdf_36 import (
    PilotFailure, _canonical_json, _cost_microusd,
    _load_public_requests, _parse_provider_response, _probe_writable_directory,
    _rest_body, _unique_pairs, ensure,
)
from run_public_source_id_multipdf_36_resume import (
    _OLD_CALIBRATION_SHA256, _OLD_KNOWN_COST_MICROUSD,
    _pinned_prior_receipts, _strict_lines, validate_prior,
)

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
from app.ai.source_judgment import parse_source_id_output  # noqa: E402


AUTHORIZATION_ID = "lane6-public-36-inline-batch-20260929-4d56d49e618a40fb9ab3848b2683e83f"
APPROVAL_SCHEMA = "cardchemy_public_source_id_36_inline_batch_approval_v1"
BATCH_SCHEMA = "cardchemy_public_source_id_36_inline_batch_v1"
CREATE_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-3.6-flash:batchGenerateContent"
)
GET_ENDPOINT_PREFIX = "https://generativelanguage.googleapis.com/v1beta/"
MAX_NEW_ITEMS = 93  # 45 unresolved calibration + at most 48 heldout.
MAX_BATCH_CREATES = 2
MAX_INPUT_PER_ITEM = 8_192
MAX_OUTPUT_PER_ITEM = 1_024
MAX_NEW_INPUT_TOKENS = MAX_NEW_ITEMS * MAX_INPUT_PER_ITEM
MAX_NEW_OUTPUT_TOKENS = MAX_NEW_ITEMS * MAX_OUTPUT_PER_ITEM
INPUT_PRICE = Decimal("0.75")
OUTPUT_PRICE = Decimal("3.75")
MAX_NEW_COST_MICROUSD = 1_000_000
MAX_CREATE_BODY_BYTES = 2_000_000  # Strictly below the official 20 MB inline limit.
MAX_CREATE_RESPONSE_BYTES = 8_192
MAX_GET_RESPONSE_BYTES = 1_000_000
MAX_ITEM_RESPONSE_BYTES = 8_192
MAX_HTTP_SECONDS = 30
POLL_INTERVAL_SECONDS = 30 * 60
MAX_STATUS_GETS = 100
MAX_TOTAL_SECONDS = 48 * 60 * 60
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_BATCH_NAME = re.compile(r"batches/[A-Za-z0-9_-]{1,128}\Z")
_PENDING = {"BATCH_STATE_PENDING", "BATCH_STATE_RUNNING",
            "JOB_STATE_PENDING", "JOB_STATE_RUNNING"}
_SUCCEEDED = {"BATCH_STATE_SUCCEEDED", "JOB_STATE_SUCCEEDED"}
_FAILED = {"BATCH_STATE_FAILED", "BATCH_STATE_CANCELLED",
           "BATCH_STATE_EXPIRED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED",
           "JOB_STATE_EXPIRED"}
_RESUME_STOP_APPROVAL_SHA256 = (
    "6f52f9460fbffb1fef88ab2a2cc44eef090117b80a146e8c035d1ee540e5963c"
)
_RESUME_STOP_FILES_SHA256 = {
    "run.claim": "c79c72bd3b9648a5e21bfef9284d77c1c151cb9ef53a98fd9dab1d55d02c5374",
    "prior-checkpoint.json": "7cf5f983848582a8f4bdf6fee534e2b73af4877094bc6aff6c59ddfc6879103f",
    "call-001.claim": "567b1bc2beb9d6a8f978f0d434317f214796635ec51c27efbdc0d211001131c9",
    "call-002.claim": "47723e2d9e02067ebd4aa9d1df5814e6731bc7723af60769ff17be2d3afdb0b9",
    "physical-outcomes.jsonl": "5ba939146cc3ba6aa3625052457cf9f576a550e275c9fc7c026130e9efc17ff1",
    "pilot-failure.json": "30147033fdf7faf23fa415bdf4c83d40ee95a3a761dc4ba1b195c80781c8042a",
    "calibration/response-ids.jsonl": _OLD_CALIBRATION_SHA256["response-ids.jsonl"],
    "calibration/usage-receipts.jsonl": _OLD_CALIBRATION_SHA256["usage-receipts.jsonl"],
}

Transport = Callable[[str, str, dict | None], Awaitable[httpx.Response]]


def _batch_cost_microusd(input_tokens: int, output_tokens: int) -> int:
    ensure(type(input_tokens) is int and type(output_tokens) is int and
           input_tokens >= 0 and output_tokens >= 0,
           "batch_usage_invalid")
    return int((Decimal(input_tokens) * INPUT_PRICE +
                Decimal(output_tokens) * OUTPUT_PRICE).to_integral_value(
                    rounding=ROUND_CEILING))


MAX_COST_PER_ITEM_MICROUSD = _batch_cost_microusd(
    MAX_INPUT_PER_ITEM, MAX_OUTPUT_PER_ITEM)
assert MAX_NEW_ITEMS * MAX_COST_PER_ITEM_MICROUSD == 928_512


def validate_resume_stop(stop_dir: Path, prepared: dict,
                         prior_checkpoint: dict,
                         prior_dir: Path) -> str:
    """Bind the later consumed two-503 attempt without opening selected IDs."""
    ensure(stop_dir.is_dir() and not stop_dir.is_symlink() and
           {entry.name for entry in stop_dir.iterdir()} ==
           {"run.claim", "prior-checkpoint.json", "call-001.claim",
            "call-002.claim", "physical-outcomes.jsonl", "pilot-failure.json",
            "calibration"}, "resume_stop_files_invalid")
    cal_dir = stop_dir / "calibration"
    ensure(cal_dir.is_dir() and not cal_dir.is_symlink() and
           {entry.name for entry in cal_dir.iterdir()} ==
           {"response-ids.jsonl", "usage-receipts.jsonl"},
           "resume_stop_files_invalid")
    for name, expected in _RESUME_STOP_FILES_SHA256.items():
        path = stop_dir / name
        ensure(path.is_file() and not path.is_symlink() and
               digest(path.read_bytes()) == expected,
               "resume_stop_file_changed")
    ensure(_canonical_json(stop_dir / "prior-checkpoint.json", 8_192) ==
           prior_checkpoint, "resume_stop_checkpoint_invalid")
    old_responses, old_usage = _pinned_prior_receipts(prior_dir)
    ensure((cal_dir / "response-ids.jsonl").read_bytes() == old_responses and
           (cal_dir / "usage-receipts.jsonl").read_bytes() == old_usage,
           "resume_stop_prefix_changed")
    run_claim = _canonical_json(stop_dir / "run.claim", 4_096)
    ensure(run_claim.get("approval_sha256") ==
           _RESUME_STOP_APPROVAL_SHA256 and
           run_claim.get("prior_checkpoint_sha256") ==
           digest(canonical_bytes(prior_checkpoint)),
           "resume_stop_run_invalid")
    row = prepared["requests"][3]
    claims = []
    for number in (1, 2):
        claim = _canonical_json(stop_dir / f"call-{number:03d}.claim", 4_096)
        ensure(claim.get("schema") ==
               "cardchemy_public_source_id_36_resume_v1_physical_claim" and
               claim.get("split") == "calibration" and
               claim.get("group_id") == row["group_id"] and
               claim.get("wire_sha256") == row["wire_sha256"] and
               claim.get("number") == number and
               claim.get("attempt_in_group") == number and
               claim.get("reserved_input_tokens") == MAX_INPUT_PER_ITEM and
               claim.get("reserved_output_tokens") == MAX_OUTPUT_PER_ITEM and
               claim.get("reserved_cost_microusd") == 19_968 and
               type(claim.get("started_unix_ms")) is int,
               "resume_stop_claim_invalid")
        claims.append(claim)
    raw = (stop_dir / "physical-outcomes.jsonl").read_bytes()
    lines = raw.splitlines(keepends=True)
    ensure(len(lines) == 2 and raw.endswith(b"\n"),
           "resume_stop_outcomes_invalid")
    outcomes = []
    for number, line in enumerate(lines, 1):
        try:
            outcome = json.loads(line, object_pairs_hook=_unique_pairs)
        except (ValueError, UnicodeError, TypeError) as exc:
            raise PilotFailure("resume_stop_outcomes_invalid") from exc
        ensure(type(outcome) is dict and canonical_bytes(outcome) == line and
               outcome.get("number") == number and
               outcome.get("attempt_in_group") == number and
               outcome.get("group_id") == row["group_id"] and
               outcome.get("split") == "calibration" and
               outcome.get("http_status") == 503 and
               outcome.get("accepted") is False and
               outcome.get("cost_receipt_missing") is True and
               type(outcome.get("elapsed_ms")) is int and
               0 < outcome["elapsed_ms"] <= 30_000,
               "resume_stop_outcomes_invalid")
        outcomes.append(outcome)
    ensure(claims[1]["started_unix_ms"] -
           (claims[0]["started_unix_ms"] + outcomes[0]["elapsed_ms"]) >=
           20_000, "resume_stop_spacing_invalid")
    failure = _canonical_json(stop_dir / "pilot-failure.json", 8_192)
    ensure(failure.get("status") == "stopped_no_replay" and
           failure.get("reason") == "provider_http_503_second" and
           failure.get("http_status") == 503 and
           failure.get("new_physical_calls") == 2 and
           failure.get("new_accepted_groups") == 0 and
           failure.get("new_cost_reserved_microusd") == 39_936 and
           failure.get("new_known_cost_microusd") == 0 and
           failure.get("new_input_tokens_reserved") == 16_384 and
           failure.get("new_output_tokens_reserved") == 2_048 and
           failure.get("new_observed_input_tokens") == 0 and
           failure.get("new_observed_output_tokens") == 0 and
           failure.get("new_failed_call_cost_unknown") is True and
           failure.get("calibration_passed") is False and
           failure.get("heldout_opened") is False and
           failure.get("release_gate_passed") is False,
           "resume_stop_failure_invalid")
    return digest(canonical_bytes(_RESUME_STOP_FILES_SHA256))


def _safe_json(response: httpx.Response, *, maximum: int) -> dict:
    ensure(response.status_code == 200,
           f"provider_http_{response.status_code}")
    ensure(len(response.content) <= maximum, "batch_response_oversize")
    try:
        value = json.loads(response.content, object_pairs_hook=_unique_pairs)
    except (ValueError, UnicodeError, TypeError) as exc:
        raise PilotFailure("batch_response_invalid") from exc
    ensure(type(value) is dict, "batch_response_invalid")
    return value


def _batch_request(rows: list[dict], *, split: str,
                   fingerprint: str) -> tuple[dict, str]:
    expected = 45 if split == "calibration" else 48
    ensure(len(rows) == expected and
           all(row.get("status") == "callable" for row in rows) and
           len({row["group_id"] for row in rows}) == expected,
           "batch_rows_invalid")
    requests = []
    for row in rows:
        group_id = row["group_id"]
        ensure(type(group_id) is str and 1 <= len(group_id) <= 128 and
               all(32 < ord(char) < 127 for char in group_id),
               "batch_group_id_invalid")
        requests.append({"request": _rest_body(row["wire"]),
                         "metadata": {"key": group_id}})
    body = {"batch": {
        "displayName": f"cardchemy-public-source-id-{split}-{fingerprint[:16]}",
        "inputConfig": {"requests": {"requests": requests}},
    }}
    raw = canonical_bytes(body)
    ensure(len(raw) <= MAX_CREATE_BODY_BYTES, "batch_create_body_budget")
    return body, digest(raw)


def _approval_claim_path(approval_sha: str) -> Path:
    ensure(type(approval_sha) is str and _HEX64.fullmatch(approval_sha),
           "approval_hash_required")
    directory = Path(gettempdir()).resolve() / "cardchemy-source-id-36-batch-ledger"
    directory.mkdir(mode=0o700 if os.name != "nt" else 0o777, exist_ok=True)
    ensure(directory.is_dir() and not directory.is_symlink(),
           "approval_ledger_unavailable")
    return directory / f"approval-{approval_sha}.claim"


def approval_template(checkpoint: dict) -> dict:
    """A future operator approval must match this exact immutable envelope."""
    return {
        "schema": APPROVAL_SCHEMA,
        "authorization_id": AUTHORIZATION_ID,
        "operator_approved": True,
        "prior_checkpoint_sha256": digest(canonical_bytes(checkpoint)),
        "resume_stop_files_sha256": checkpoint["resume_stop_files_sha256"],
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "source_packet_sha256": PACKET_SHA256,
        "labels_sha256": checkpoint["labels_sha256"],
        "freeze_receipt_sha256": checkpoint["freeze_receipt_sha256"],
        "fingerprint": checkpoint["fingerprint"],
        "create_endpoint": CREATE_ENDPOINT,
        "get_endpoint_prefix": GET_ENDPOINT_PREFIX,
        "model": MODEL,
        "store": False,
        "mode": "inline_batch_calibration_then_heldout_if_passed",
        "max_batch_creates": MAX_BATCH_CREATES,
        "max_new_items": MAX_NEW_ITEMS,
        "max_input_tokens_per_item": MAX_INPUT_PER_ITEM,
        "max_output_tokens_per_item": MAX_OUTPUT_PER_ITEM,
        "max_new_input_tokens": MAX_NEW_INPUT_TOKENS,
        "max_new_output_tokens": MAX_NEW_OUTPUT_TOKENS,
        "max_new_cost_microusd": MAX_NEW_COST_MICROUSD,
        "input_price_usd_per_million_guard": str(INPUT_PRICE),
        "output_price_usd_per_million_guard": str(OUTPUT_PRICE),
        "max_create_body_bytes": MAX_CREATE_BODY_BYTES,
        "max_http_seconds": MAX_HTTP_SECONDS,
        "poll_interval_seconds": POLL_INTERVAL_SECONDS,
        "max_status_gets": MAX_STATUS_GETS,
        "max_total_seconds": MAX_TOTAL_SECONDS,
        "prior_known_cost_microusd": _OLD_KNOWN_COST_MICROUSD,
        "prior_failed_cost_unknown": True,
    }


def validate_approval(path: Path, approval_sha: str,
                      checkpoint: dict) -> dict:
    ensure(AUTHORIZATION_ID != "PENDING_SEPARATE_OPERATOR_APPROVAL",
           "separate_batch_operator_approval_required")
    ensure(type(approval_sha) is str and _HEX64.fullmatch(approval_sha),
           "approval_hash_required")
    approval = _canonical_json(path, 8_192)
    ensure(digest(path.read_bytes()) == approval_sha and
           approval == approval_template(checkpoint),
           "batch_approval_envelope_mismatch")
    return approval


def _assert_temp(path: Path, *, kind: str) -> None:
    temp = Path(gettempdir()).resolve()
    ensure(path.is_absolute() and temp in path.resolve().parents and
           not path.is_symlink() and
           (path.is_dir() if kind == "directory" else
            path.is_file() if kind == "file" else
            not path.exists() if kind == "absent" else False),
           "os_temp_path_required")


def _admit(args: argparse.Namespace) -> tuple[dict, dict, dict, dict | None]:
    for path in (args.prior_dir, args.packet_dir, args.resume_stop_dir):
        _assert_temp(path, kind="directory")
    _assert_temp(args.labels, kind="file")
    ensure(args.labels.is_file() and not args.labels.is_symlink(),
           "labels_required")
    prepared, receipt, prior_checkpoint = validate_prior(
        args.prior_dir, args.packet_dir, args.labels,
        args.labels_sha256, args.freeze_receipt_sha256)
    stop_sha = validate_resume_stop(args.resume_stop_dir, prepared,
                                    prior_checkpoint, args.prior_dir)
    checkpoint = prior_checkpoint | {"resume_stop_files_sha256": stop_sha}
    _batch_request(prepared["requests"][3:], split="calibration",
                   fingerprint=prepared["fingerprint"])
    approval = None
    if args.mode != "preflight":
        _assert_temp(args.approval_receipt, kind="file")
        approval = validate_approval(args.approval_receipt,
                                     args.approval_sha256, checkpoint)
        claim_path = _approval_claim_path(args.approval_sha256)
        _probe_writable_directory(claim_path.parent)
        if args.mode == "submit-calibration":
            ensure(not claim_path.exists() and not claim_path.is_symlink(),
                   "batch_approval_claim_consumed")
    if args.mode == "submit-calibration":
        _assert_temp(args.output, kind="absent")
        ensure(args.output.parent.is_dir() and
               args.prior_dir.resolve() not in args.output.resolve().parents,
               "os_temp_output_required")
        _probe_writable_directory(args.output.parent)
    elif args.mode != "preflight":
        _assert_temp(args.output, kind="directory")
    return prepared, receipt, checkpoint, approval


def _read_pilot(output: Path, approval_sha: str,
                checkpoint: dict) -> dict:
    pilot = _canonical_json(output / "pilot.claim", 8_192)
    ensure(pilot.get("schema") == BATCH_SCHEMA + "_pilot_claim" and
           pilot.get("approval_sha256") == approval_sha and
           pilot.get("prior_checkpoint_sha256") ==
           digest(canonical_bytes(checkpoint)) and
           pilot.get("fingerprint") == checkpoint["fingerprint"] and
           pilot.get("started_unix_ms") is not None and
           type(pilot["started_unix_ms"]) is int,
           "batch_pilot_identity_invalid")
    global_claim = _canonical_json(_approval_claim_path(approval_sha), 8_192)
    ensure(global_claim.get("output_path") == str(output.resolve()) and
           global_claim.get("prior_checkpoint_sha256") ==
           pilot["prior_checkpoint_sha256"],
           "batch_approval_claim_mismatch")
    return pilot


def _read_create_result(split_dir: Path, split: str, body_sha: str) -> dict:
    claim = _canonical_json(split_dir / "create.claim", 8_192)
    count = 45 if split == "calibration" else 48
    ensure(claim.get("schema") == BATCH_SCHEMA + "_create_claim" and
           claim.get("split") == split and
           claim.get("body_sha256") == body_sha and
           claim.get("reserved_item_count") == count and
           claim.get("reserved_input_tokens") == count * MAX_INPUT_PER_ITEM and
           claim.get("reserved_output_tokens") == count * MAX_OUTPUT_PER_ITEM and
           claim.get("reserved_cost_microusd") == count * MAX_COST_PER_ITEM_MICROUSD and
           type(claim.get("created_unix_ms")) is int,
           "batch_create_claim_mismatch")
    result = _canonical_json(split_dir / "create-result.json", 8_192)
    name = result.get("name")
    ensure(result.get("schema") == BATCH_SCHEMA + "_create_result" and
           result.get("body_sha256") == body_sha and
           type(name) is str and _BATCH_NAME.fullmatch(name),
           "batch_create_result_invalid")
    return result


def _poll_admission(output: Path, split: str, batch_name: str,
                    approval_sha: str, pilot_started_ms: int,
                    now_ms: int) -> tuple[int, Path]:
    """Count all persisted GET claims, including uncertain prior outcomes."""
    ensure(0 <= now_ms - pilot_started_ms <
           (MAX_TOTAL_SECONDS - MAX_HTTP_SECONDS) * 1000,
           "batch_poll_time_budget")
    total = 0
    current_count = 0
    last_current_ms: int | None = None
    for item_split in ("calibration", "heldout"):
        directory = output / item_split
        if not directory.exists():
            continue
        ensure(directory.is_dir() and not directory.is_symlink(),
               "batch_poll_ledger_invalid")
        claims = sorted(directory.glob("poll-*.claim"))
        last_ms: int | None = None
        expected_name = batch_name if item_split == split else None
        if expected_name is None and claims:
            other_result = _canonical_json(directory / "create-result.json", 8_192)
            expected_name = other_result.get("name")
        for number, path in enumerate(claims, 1):
            ensure(path.name == f"poll-{number:03d}.claim",
                   "batch_poll_ledger_invalid")
            claim = _canonical_json(path, 4_096)
            started = claim.get("started_unix_ms")
            ensure(claim.get("schema") == BATCH_SCHEMA + "_poll_claim" and
                   claim.get("split") == item_split and
                   claim.get("batch_name") == expected_name and
                   claim.get("approval_sha256") == approval_sha and
                   claim.get("number") == number and
                   type(started) is int and
                   pilot_started_ms <= started <= now_ms and
                   (last_ms is None or
                    started - last_ms >= POLL_INTERVAL_SECONDS * 1000),
                   "batch_poll_ledger_invalid")
            last_ms = started
        total += len(claims)
        if item_split == split:
            current_count = len(claims)
            last_current_ms = last_ms
    ensure(total < MAX_STATUS_GETS, "batch_poll_count_budget")
    ensure(last_current_ms is None or
           now_ms - last_current_ms >= POLL_INTERVAL_SECONDS * 1000,
           "batch_poll_interval_budget")
    return current_count + 1, output / split / f"poll-{current_count + 1:03d}.claim"


def _batch_state(operation: dict, expected_name: str) -> tuple[str, dict | None]:
    """Normalize only documented REST Operation forms, never positional output.

    The Batch REST guide places state at ``metadata.state`` and inline output
    at ``response.inlinedResponses``. The resource reference also describes a
    typed Batch response with ``output.inlinedResponses.inlinedResponses``.
    ``done`` may be omitted while pending because it is a proto default.
    """
    ensure(operation.get("name") == expected_name and
           type(operation.get("metadata")) is dict,
           "batch_operation_invalid")
    state = operation["metadata"].get("state")
    done = operation.get("done", False)
    ensure(type(done) is bool, "batch_operation_invalid")
    if state in _PENDING:
        ensure(not done and "response" not in operation and
               "error" not in operation, "batch_operation_invalid")
        return "pending", None
    if state in _FAILED:
        raise PilotFailure("batch_job_failed")
    ensure(state in _SUCCEEDED and done and
           "error" not in operation,
           "batch_operation_invalid")
    response = operation.get("response")
    metadata_output = operation["metadata"].get("output")
    ensure((response is None) != (metadata_output is None),
           "batch_inline_output_ambiguous")
    if response is None:
        response = metadata_output
    ensure(type(response) is dict,
           "batch_inline_output_required")
    ensure(response.get("name", expected_name) == expected_name and
           "responsesFile" not in response,
           "batch_inline_output_required")
    direct = response.get("inlinedResponses")
    nested_output = response.get("output")
    ensure(not (direct is not None and nested_output is not None),
           "batch_inline_output_ambiguous")
    if nested_output is not None:
        ensure(type(nested_output) is dict and
               "responsesFile" not in nested_output,
               "batch_inline_output_required")
        direct = nested_output.get("inlinedResponses")
    if type(direct) is dict:
        ensure(set(direct) == {"inlinedResponses"},
               "batch_inline_output_invalid")
        direct = direct["inlinedResponses"]
    ensure(type(direct) is list,
           "batch_inline_output_required")
    stats = response.get("batchStats", operation["metadata"].get("batchStats"))
    if "batchStats" in response and "batchStats" in operation["metadata"]:
        ensure(response["batchStats"] == operation["metadata"]["batchStats"],
               "batch_stats_conflict")
    return "succeeded", {"inlinedResponses": direct, "batchStats": stats}


def _strict_count(value: object, expected: int) -> bool:
    return (type(value) is int or (type(value) is str and value.isdecimal())) and int(value) == expected


def _accepted_items(batch: dict, rows: list[dict],
                    batch_name: str) -> tuple[list[dict], list[dict], dict]:
    """Validate the *entire* inline result before writing even one selected ID."""
    stats = batch.get("batchStats")
    if stats is not None:
        ensure(type(stats) is dict and
               _strict_count(stats.get("requestCount"), len(rows)) and
               _strict_count(stats.get("successfulRequestCount", 0), len(rows)) and
               _strict_count(stats.get("failedRequestCount", 0), 0) and
               _strict_count(stats.get("pendingRequestCount", 0), 0),
               "batch_stats_invalid")
    items = batch.get("inlinedResponses")
    ensure(type(items) is list and len(items) == len(rows),
           "batch_item_count_invalid")
    # Provider order is not an identity. Every item must carry the issued
    # metadata key, and only that key may pair it with a public question.
    by_key: dict[str, dict] = {}
    expected_keys = {row["group_id"] for row in rows}
    for item in items:
        ensure(type(item) is dict and type(item.get("metadata")) is dict,
               "batch_item_identity_invalid")
        key = item["metadata"].get("key")
        ensure(type(key) is str and key in expected_keys and key not in by_key,
               "batch_item_identity_invalid")
        by_key[key] = item
    ensure(set(by_key) == expected_keys, "batch_item_identity_invalid")
    accepted: list[dict] = []
    usages: list[dict] = []
    totals = {"observed_input_tokens": 0, "observed_output_tokens": 0,
              "known_cost_microusd": 0}
    for row in rows:
        item = by_key[row["group_id"]]
        ensure("error" not in item and type(item.get("response")) is dict,
               "batch_item_failed")
        group_id = item["metadata"].get("key")
        response = item["response"]
        raw = canonical_bytes(response)
        ensure(len(raw) <= MAX_ITEM_RESPONSE_BYTES,
               "batch_item_response_oversize")
        issued = [candidate["id"] for candidate in
                  row["wire"]["user_payload"]["candidates"]]
        synthetic = httpx.Response(200, content=raw,
                                   request=httpx.Request("GET", GET_ENDPOINT_PREFIX + batch_name))
        selected_json, input_tokens, output_tokens = _parse_provider_response(
            synthetic, issued)
        cost = _batch_cost_microusd(input_tokens, output_tokens)
        accepted.append({"group_id": group_id,
                         "wire_sha256": row["wire_sha256"],
                         "raw_json": selected_json})
        usages.append({"group_id": group_id, "finish_reason": "STOP",
                       "input_tokens": input_tokens,
                       "output_tokens": output_tokens,
                       "cost_microusd": cost})
        totals["observed_input_tokens"] += input_tokens
        totals["observed_output_tokens"] += output_tokens
        totals["known_cost_microusd"] += cost
    return accepted, usages, totals


def _validate_sealed_items(seal: dict, rows: list[dict], *, split: str,
                           batch_name: str, approval_sha: str,
                           body_sha: str, checkpoint_sha: str) -> None:
    ensure(seal.get("schema") == BATCH_SCHEMA + "_complete_items" and
           seal.get("split") == split and
           seal.get("batch_name") == batch_name and
           seal.get("approval_sha256") == approval_sha and
           seal.get("body_sha256") == body_sha and
           seal.get("prior_checkpoint_sha256") == checkpoint_sha and
           type(seal.get("poll_number")) is int and
           1 <= seal["poll_number"] <= MAX_STATUS_GETS and
           type(seal.get("operation_sha256")) is str and
           _HEX64.fullmatch(seal["operation_sha256"]) and
           type(seal.get("accepted")) is list and
           type(seal.get("usages")) is list and
           len(seal["accepted"]) == len(seal["usages"]) == len(rows),
           "batch_complete_items_invalid")
    totals = {"observed_input_tokens": 0, "observed_output_tokens": 0,
              "known_cost_microusd": 0}
    for row, accepted, usage in zip(rows, seal["accepted"], seal["usages"],
                                    strict=True):
        ensure(type(accepted) is dict and
               set(accepted) == {"group_id", "wire_sha256", "raw_json"} and
               accepted["group_id"] == row["group_id"] and
               accepted["wire_sha256"] == row["wire_sha256"] and
               type(accepted["raw_json"]) is str and
               type(usage) is dict and
               set(usage) == {"group_id", "finish_reason", "input_tokens",
                              "output_tokens", "cost_microusd"} and
               usage["group_id"] == row["group_id"] and
               usage["finish_reason"] == "STOP" and
               type(usage["input_tokens"]) is int and
               type(usage["output_tokens"]) is int and
               0 <= usage["input_tokens"] <= MAX_INPUT_PER_ITEM and
               0 <= usage["output_tokens"] <= MAX_OUTPUT_PER_ITEM and
               usage["cost_microusd"] == _batch_cost_microusd(
                   usage["input_tokens"], usage["output_tokens"]),
               "batch_complete_items_invalid")
        issued = [candidate["id"] for candidate in
                  row["wire"]["user_payload"]["candidates"]]
        try:
            parse_source_id_output(accepted["raw_json"], issued)
        except Exception as exc:
            raise PilotFailure("batch_complete_items_invalid") from exc
        totals["observed_input_tokens"] += usage["input_tokens"]
        totals["observed_output_tokens"] += usage["output_tokens"]
        totals["known_cost_microusd"] += usage["cost_microusd"]
    ensure(seal.get("totals") == totals,
           "batch_complete_items_invalid")


def _write_or_confirm(path: Path, raw: bytes) -> None:
    if path.exists() or path.is_symlink():
        ensure(path.is_file() and not path.is_symlink() and
               path.read_bytes() == raw,
               "batch_materialized_file_mismatch")
        return
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _validate_batch_split(prepared: dict, response_path: Path,
                          usage_path: Path, prior_dir: Path) -> None:
    """Verify complete ordered receipts with the two distinct price regimes."""
    rows = prepared["requests"]
    response_lines = _strict_lines(response_path, max_bytes=256_000,
                                   max_lines=48)
    usage_lines = _strict_lines(usage_path, max_bytes=64_000,
                                max_lines=48)
    ensure(len(rows) == len(response_lines) == len(usage_lines) == 48,
           "batch_receipts_incomplete")
    if prepared["split"] == "calibration":
        prior_response, prior_usage = _pinned_prior_receipts(prior_dir)
        ensure(response_path.read_bytes().startswith(prior_response) and
               usage_path.read_bytes().startswith(prior_usage),
               "batch_prior_prefix_changed")
    for index, (row, response, usage) in enumerate(
            zip(rows, response_lines, usage_lines, strict=True)):
        expected_cost = (_cost_microusd if prepared["split"] == "calibration"
                         and index < 3 else _batch_cost_microusd)
        ensure(set(response) == {"group_id", "wire_sha256", "raw_json"} and
               response["group_id"] == row["group_id"] and
               response["wire_sha256"] == row["wire_sha256"] and
               type(response["raw_json"]) is str and
               set(usage) == {"group_id", "finish_reason", "input_tokens",
                              "output_tokens", "cost_microusd"} and
               usage["group_id"] == row["group_id"] and
               usage["finish_reason"] == "STOP" and
               type(usage["input_tokens"]) is int and
               type(usage["output_tokens"]) is int and
               0 <= usage["input_tokens"] <= MAX_INPUT_PER_ITEM and
               0 <= usage["output_tokens"] <= MAX_OUTPUT_PER_ITEM and
               type(usage["cost_microusd"]) is int and
               usage["cost_microusd"] == expected_cost(
                   usage["input_tokens"], usage["output_tokens"]),
               "batch_receipt_invalid")
        issued = [candidate["id"] for candidate in
                  row["wire"]["user_payload"]["candidates"]]
        try:
            parse_source_id_output(response["raw_json"], issued)
        except Exception as exc:
            raise PilotFailure("batch_receipt_invalid") from exc


def _score_split(prepared: dict, labels_path: Path, labels_sha: str,
                 freeze_sha: str, responses_path: Path,
                  checkpoint_sha: str, output: Path,
                  prior_dir: Path) -> dict:
    _validate_batch_split(prepared, responses_path,
                          responses_path.parent / "usage-receipts.jsonl",
                          prior_dir)
    labels = read_pinned(labels_path, labels_sha, 100_000)
    ensure(labels.get("schema") == LABEL_SCHEMA and
           labels.get("packet_sha256") == PACKET_SHA256 and
           len(labels.get("groups", [])) == 96,
           "labels_contract_mismatch")
    responses = _responses(responses_path, prepared["requests"])
    ensure(len(responses) == 48, "batch_split_incomplete")
    metrics = score(prepared, labels, responses)
    result = {"schema": SCHEMA, "split": prepared["split"],
              "fingerprint": prepared["fingerprint"],
              "source_packet_sha256": PACKET_SHA256,
              "labels_sha256": labels_sha,
              "freeze_receipt_sha256": freeze_sha,
              "requests_sha256": digest(canonical_bytes(prepared)),
              "responses_sha256": digest(responses_path.read_bytes()),
              "prior_checkpoint_sha256": checkpoint_sha,
              "public_passed": metrics["public_passed"],
              "release_gate_passed": False, "metrics": metrics}
    score_path = output / f"{prepared['split']}-score.json"
    if score_path.exists():
        ensure(_canonical_json(score_path, 100_000) == result,
               "batch_score_mismatch")
    else:
        write_exclusive(score_path, result)
    return result


def _read_calibration_pass(output: Path, prepared: dict, labels_path: Path,
                            labels_sha: str, freeze_sha: str,
                            prior_dir: Path,
                            checkpoint: dict) -> tuple[dict, str]:
    path = output / "calibration-score.json"
    ensure(not (output / "calibration" / "terminal.json").exists(),
           "calibration_gate_failed")
    score_result = _canonical_json(path, 100_000)
    response_path = output / "calibration" / "response-ids.jsonl"
    usage_path = response_path.parent / "usage-receipts.jsonl"
    _validate_batch_split(prepared, response_path,
                          usage_path,
                          prior_dir)
    _body, body_sha = _batch_request(prepared["requests"][3:],
                                     split="calibration",
                                     fingerprint=prepared["fingerprint"])
    created = _read_create_result(output / "calibration", "calibration",
                                  body_sha)
    seal = _canonical_json(output / "calibration" / "complete-items.json",
                           256_000)
    pilot = _canonical_json(output / "pilot.claim", 8_192)
    approval_sha = pilot.get("approval_sha256")
    ensure(type(approval_sha) is str and _HEX64.fullmatch(approval_sha),
           "calibration_completion_invalid")
    _validate_sealed_items(
        seal, prepared["requests"][3:], split="calibration",
        batch_name=created["name"], approval_sha=approval_sha,
        body_sha=body_sha,
        checkpoint_sha=digest(canonical_bytes(checkpoint)),
    )
    claim = _canonical_json(
        output / "calibration" / f"poll-{seal['poll_number']:03d}.claim",
        4_096,
    )
    ensure(claim.get("split") == "calibration" and
           claim.get("batch_name") == created["name"] and
           claim.get("approval_sha256") == approval_sha and
           claim.get("number") == seal["poll_number"],
           "calibration_completion_invalid")
    prior_responses, prior_usage = _pinned_prior_receipts(prior_dir)
    ensure(response_path.read_bytes() == prior_responses + b"".join(
               canonical_bytes(item) for item in seal["accepted"]) and
           usage_path.read_bytes() == prior_usage + b"".join(
               canonical_bytes(item) for item in seal["usages"]),
           "calibration_completion_invalid")
    labels = read_pinned(labels_path, labels_sha, 100_000)
    metrics = score(prepared, labels,
                    _responses(response_path, prepared["requests"]))
    ensure(score_result.get("schema") == SCHEMA and
           score_result.get("split") == "calibration" and
           score_result.get("fingerprint") == prepared["fingerprint"] and
           score_result.get("labels_sha256") == labels_sha and
           score_result.get("freeze_receipt_sha256") == freeze_sha and
           score_result.get("responses_sha256") == digest(response_path.read_bytes()) and
            score_result.get("prior_checkpoint_sha256") ==
            digest(canonical_bytes(checkpoint)) and
           score_result.get("public_passed") is True and
            score_result.get("release_gate_passed") is False and
           score_result.get("metrics") == metrics and
           metrics["public_passed"] is True,
           "calibration_gate_failed")
    completion = _canonical_json(output / "calibration" / "result.json", 8_192)
    ensure(completion.get("schema") == BATCH_SCHEMA + "_split_result" and
           completion.get("split") == "calibration" and
           completion.get("batch_name") == created["name"] and
           completion.get("create_body_sha256") == body_sha and
           completion.get("create_result_sha256") ==
           digest((output / "calibration" / "create-result.json").read_bytes()) and
           completion.get("complete_items_sha256") ==
           digest((output / "calibration" / "complete-items.json").read_bytes()) and
           completion.get("new_items") == 45 and
           completion.get("response_ids_sha256") == digest(response_path.read_bytes()) and
           completion.get("usage_receipts_sha256") == digest(usage_path.read_bytes()) and
           completion.get("score_sha256") == digest(path.read_bytes()) and
           completion.get("public_passed") is True and
           completion.get("release_gate_passed") is False and
           completion.get("new_cost_reserved_microusd") ==
           45 * MAX_COST_PER_ITEM_MICROUSD,
           "calibration_completion_invalid")
    return score_result, digest(path.read_bytes())


async def _request(transport: Transport, method: str, url: str,
                   body: dict | None) -> httpx.Response:
    return await asyncio.wait_for(transport(method, url, body),
                                  timeout=MAX_HTTP_SECONDS)


async def submit_calibration(args: argparse.Namespace, admitted: tuple,
                             transport: Transport,
                             wall_clock: Callable[[], float] = time.time) -> dict:
    prepared, _receipt, checkpoint, _approval = admitted
    body, body_sha = _batch_request(prepared["requests"][3:],
                                    split="calibration",
                                    fingerprint=prepared["fingerprint"])
    approval_sha = args.approval_sha256
    claim_path = _approval_claim_path(approval_sha)
    prior_responses, prior_usage = _pinned_prior_receipts(args.prior_dir)
    # A global approval claim is committed before any non-idempotent POST.
    args.output.mkdir(mode=0o700 if os.name != "nt" else 0o777)
    write_exclusive(claim_path, {
        "schema": BATCH_SCHEMA + "_approval_claim",
        "output_path": str(args.output.resolve()),
        "prior_checkpoint_sha256": digest(canonical_bytes(checkpoint)),
    })
    write_exclusive(args.output / "pilot.claim", {
        "schema": BATCH_SCHEMA + "_pilot_claim",
        "approval_sha256": approval_sha,
        "prior_checkpoint_sha256": digest(canonical_bytes(checkpoint)),
        "fingerprint": prepared["fingerprint"],
        "started_unix_ms": int(wall_clock() * 1000),
    })
    split_dir = args.output / "calibration"
    split_dir.mkdir()
    # Old receipts remain immutable in the previous output. These copies are
    # written only after all 45 batch items have been validated.
    write_exclusive(args.output / "prior-hashes.json", {
        "response_ids_sha256": digest(prior_responses),
        "usage_receipts_sha256": digest(prior_usage),
        "old_files_sha256": _OLD_CALIBRATION_SHA256,
    })
    write_exclusive(split_dir / "create.claim", {
        "schema": BATCH_SCHEMA + "_create_claim",
        "split": "calibration", "body_sha256": body_sha,
        "reserved_item_count": 45,
        "reserved_input_tokens": 45 * MAX_INPUT_PER_ITEM,
        "reserved_output_tokens": 45 * MAX_OUTPUT_PER_ITEM,
        "reserved_cost_microusd": 45 * MAX_COST_PER_ITEM_MICROUSD,
        "created_unix_ms": int(wall_clock() * 1000),
    })
    response = await _request(transport, "POST", CREATE_ENDPOINT, body)
    created = _safe_json(response, maximum=MAX_CREATE_RESPONSE_BYTES)
    name = created.get("name")
    ensure(type(name) is str and _BATCH_NAME.fullmatch(name),
           "batch_create_name_invalid")
    write_exclusive(split_dir / "create-result.json", {
        "schema": BATCH_SCHEMA + "_create_result",
        "body_sha256": body_sha, "name": name,
    })
    return {"status": "batch_created", "split": "calibration",
            "item_count": 45, "create_calls": 1,
            "reserved_cost_microusd": 45 * MAX_COST_PER_ITEM_MICROUSD,
            "raw_response_saved": False}


async def submit_heldout(args: argparse.Namespace, admitted: tuple,
                         transport: Transport,
                         wall_clock: Callable[[], float] = time.time) -> dict:
    prepared, _receipt, checkpoint, _approval = admitted
    pilot = _read_pilot(args.output, args.approval_sha256, checkpoint)
    now_ms = int(wall_clock() * 1_000)
    ensure(0 <= now_ms - pilot["started_unix_ms"] <
           (MAX_TOTAL_SECONDS - MAX_HTTP_SECONDS) * 1_000,
           "batch_total_time_budget")
    # A second paid job is useless if no authorized GET remains to measure it.
    _poll_admission(args.output, "heldout", "batches/pending",
                    args.approval_sha256, pilot["started_unix_ms"], now_ms)
    _read_calibration_pass(args.output, prepared, args.labels,
                            args.labels_sha256, args.freeze_receipt_sha256,
                            args.prior_dir, checkpoint)
    cal_score = args.output / "calibration-score.json"
    score_sha = digest(cal_score.read_bytes())
    split_dir = args.output / "heldout"
    ensure(not split_dir.exists() and not split_dir.is_symlink(),
           "heldout_create_claim_consumed")
    prepare(args.packet_dir, args.labels, args.labels_sha256,
            args.freeze_receipt_sha256, "heldout", split_dir,
            cal_score, score_sha)
    heldout, _heldout_receipt = _load_public_requests(
        split_dir, digest((split_dir / "prepare-receipt.json").read_bytes()),
        args.packet_dir)
    body, body_sha = _batch_request(heldout["requests"],
                                    split="heldout",
                                    fingerprint=heldout["fingerprint"])
    write_exclusive(split_dir / "create.claim", {
        "schema": BATCH_SCHEMA + "_create_claim",
        "split": "heldout", "body_sha256": body_sha,
        "reserved_item_count": 48,
        "reserved_input_tokens": 48 * MAX_INPUT_PER_ITEM,
        "reserved_output_tokens": 48 * MAX_OUTPUT_PER_ITEM,
        "reserved_cost_microusd": 48 * MAX_COST_PER_ITEM_MICROUSD,
        "created_unix_ms": int(wall_clock() * 1000),
        "calibration_score_sha256": score_sha,
    })
    response = await _request(transport, "POST", CREATE_ENDPOINT, body)
    created = _safe_json(response, maximum=MAX_CREATE_RESPONSE_BYTES)
    name = created.get("name")
    ensure(type(name) is str and _BATCH_NAME.fullmatch(name),
           "batch_create_name_invalid")
    write_exclusive(split_dir / "create-result.json", {
        "schema": BATCH_SCHEMA + "_create_result",
        "body_sha256": body_sha, "name": name,
    })
    return {"status": "batch_created", "split": "heldout",
            "item_count": 48, "create_calls": 1,
            "reserved_cost_microusd": 48 * MAX_COST_PER_ITEM_MICROUSD,
            "raw_response_saved": False}


def _materialize_complete(args: argparse.Namespace, prepared: dict,
                          checkpoint: dict, active: dict, split: str,
                          rows: list[dict], name: str, body_sha: str,
                          seal: dict) -> dict:
    split_dir = args.output / split
    _validate_sealed_items(seal, rows, split=split, batch_name=name,
                           approval_sha=args.approval_sha256,
                           body_sha=body_sha,
                           checkpoint_sha=digest(canonical_bytes(checkpoint)))
    claim = _canonical_json(
        split_dir / f"poll-{seal['poll_number']:03d}.claim", 4_096)
    ensure(claim.get("split") == split and
           claim.get("batch_name") == name and
           claim.get("approval_sha256") == args.approval_sha256 and
           claim.get("number") == seal["poll_number"],
           "batch_complete_items_claim_mismatch")
    prior_responses = b""
    prior_usage = b""
    if split == "calibration":
        prior_responses, prior_usage = _pinned_prior_receipts(args.prior_dir)
    response_bytes = prior_responses + b"".join(
        canonical_bytes(item) for item in seal["accepted"])
    usage_bytes = prior_usage + b"".join(
        canonical_bytes(item) for item in seal["usages"])
    response_path = split_dir / "response-ids.jsonl"
    usage_path = split_dir / "usage-receipts.jsonl"
    _write_or_confirm(response_path, response_bytes)
    _write_or_confirm(usage_path, usage_bytes)
    score_result = _score_split(active, args.labels, args.labels_sha256,
                                args.freeze_receipt_sha256, response_path,
                                digest(canonical_bytes(checkpoint)), args.output,
                                args.prior_dir)
    score_path = args.output / f"{split}-score.json"
    result = {"schema": BATCH_SCHEMA + "_split_result",
              "status": "batch_scored", "split": split,
              "batch_name": name,
              "create_body_sha256": body_sha,
              "create_result_sha256": digest(
                  (split_dir / "create-result.json").read_bytes()),
              "complete_items_sha256": digest(
                  (split_dir / "complete-items.json").read_bytes()),
              "response_ids_sha256": digest(response_path.read_bytes()),
              "usage_receipts_sha256": digest(usage_path.read_bytes()),
              "public_passed": score_result["public_passed"],
              "release_gate_passed": False,
              "new_items": len(rows),
              "new_observed_input_tokens": seal["totals"]["observed_input_tokens"],
              "new_observed_output_tokens": seal["totals"]["observed_output_tokens"],
              "new_known_cost_microusd": seal["totals"]["known_cost_microusd"],
              "new_cost_reserved_microusd":
                  len(rows) * MAX_COST_PER_ITEM_MICROUSD,
              "prior_known_cost_microusd": _OLD_KNOWN_COST_MICROUSD,
              "prior_failed_cost_unknown": True,
              "score_sha256": digest(score_path.read_bytes())}
    result_path = split_dir / "result.json"
    if result_path.exists():
        ensure(_canonical_json(result_path, 8_192) == result,
               "batch_result_mismatch")
    else:
        write_exclusive(result_path, result)
    return result


async def poll_split(args: argparse.Namespace, admitted: tuple,
                     transport: Transport, *, split: str,
                      wall_clock: Callable[[], float] = time.time) -> dict:
    """Make at most one GET. A later process may poll the same known job."""
    prepared, _receipt, checkpoint, _approval = admitted
    pilot = _read_pilot(args.output, args.approval_sha256, checkpoint)
    split_dir = args.output / split
    if split == "heldout":
        _read_calibration_pass(args.output, prepared, args.labels,
                                args.labels_sha256, args.freeze_receipt_sha256,
                                args.prior_dir, checkpoint)
        heldout, _heldout_receipt = _load_public_requests(
            split_dir, digest((split_dir / "prepare-receipt.json").read_bytes()),
            args.packet_dir)
        rows = heldout["requests"]
        active = heldout
    else:
        rows = prepared["requests"][3:]
        active = prepared
    _body, body_sha = _batch_request(rows, split=split,
                                     fingerprint=active["fingerprint"])
    created = _read_create_result(split_dir, split, body_sha)
    now_ms = int(wall_clock() * 1_000)
    ensure(0 <= now_ms - pilot["started_unix_ms"] <
           MAX_TOTAL_SECONDS * 1_000, "batch_poll_time_budget")
    name = created["name"]
    complete_path = split_dir / "complete-items.json"
    if complete_path.exists() or complete_path.is_symlink():
        seal = _canonical_json(complete_path, 256_000)
        result = _materialize_complete(args, prepared, checkpoint, active,
                                       split, rows, name, body_sha, seal)
        return result | {"status_gets_this_invocation": 0}
    response_path = split_dir / "response-ids.jsonl"
    usage_path = split_dir / "usage-receipts.jsonl"
    ensure(not any(path.exists() or path.is_symlink() for path in
                   (response_path, usage_path, args.output / f"{split}-score.json",
                    split_dir / "result.json", split_dir / "terminal.json")),
           "batch_split_already_terminal")
    url = GET_ENDPOINT_PREFIX + name
    number, claim_path = _poll_admission(
        args.output, split, name, args.approval_sha256,
        pilot["started_unix_ms"], now_ms)
    # A claim is fsynced before a GET; a timeout/HTTP failure still consumes it.
    write_exclusive(claim_path, {
        "schema": BATCH_SCHEMA + "_poll_claim",
        "split": split, "batch_name": name,
        "approval_sha256": args.approval_sha256,
        "number": number, "started_unix_ms": now_ms,
    })
    response = await _request(transport, "GET", url, None)
    ensure(0 <= int(wall_clock() * 1_000) - pilot["started_unix_ms"] <
           MAX_TOTAL_SECONDS * 1_000, "batch_poll_time_budget")
    operation = _safe_json(response, maximum=MAX_GET_RESPONSE_BYTES)
    try:
        state, batch = _batch_state(operation, name)
    except PilotFailure as exc:
        metadata = operation.get("metadata")
        if (operation.get("done") is True or
                (type(metadata) is dict and metadata.get("state") in _FAILED)):
            write_exclusive(split_dir / "terminal.json", {
                "schema": BATCH_SCHEMA + "_terminal",
                "reason": str(exc), "poll_number": number,
                "release_gate_passed": False,
            })
        raise
    if state == "pending":
        write_exclusive(split_dir / f"poll-{number:03d}.result.json", {
            "schema": BATCH_SCHEMA + "_poll_result",
            "state": "pending", "poll_number": number,
        })
        return {"status": "batch_pending", "split": split,
                "status_gets_this_invocation": 1,
                "next_poll_not_before_unix_ms":
                    now_ms + POLL_INTERVAL_SECONDS * 1_000,
                "release_gate_passed": False}
    assert batch is not None
    try:
        accepted, usages, totals = _accepted_items(batch, rows, name)
    except PilotFailure as exc:
        write_exclusive(split_dir / "terminal.json", {
            "schema": BATCH_SCHEMA + "_terminal",
            "reason": str(exc), "poll_number": number,
            "release_gate_passed": False,
        })
        raise
    seal = {"schema": BATCH_SCHEMA + "_complete_items",
            "split": split, "batch_name": name,
            "approval_sha256": args.approval_sha256,
            "body_sha256": body_sha,
            "prior_checkpoint_sha256": digest(canonical_bytes(checkpoint)),
            "poll_number": number,
            "operation_sha256": digest(response.content),
            "accepted": accepted, "usages": usages, "totals": totals}
    write_exclusive(complete_path, seal)
    return _materialize_complete(args, prepared, checkpoint, active,
                                 split, rows, name, body_sha, seal)


async def _http_transport(api_key: str, method: str, url: str,
                          body: dict | None) -> httpx.Response:
    async with httpx.AsyncClient(timeout=MAX_HTTP_SECONDS,
                                 follow_redirects=False) as client:
        return await client.request(method, url,
                                    headers={"x-goog-api-key": api_key,
                                             "Content-Type": "application/json"},
                                     content=canonical_bytes(body) if method == "POST"
                                     else None)


async def _live(args: argparse.Namespace, admitted: tuple) -> dict:
    from app.config import Settings
    api_key = Settings().rag_ai_api_key_value
    ensure(bool(api_key), "provider_key_unavailable")
    transport = lambda method, url, body: _http_transport(api_key, method, url, body)
    if args.mode == "submit-calibration":
        return await submit_calibration(args, admitted, transport)
    if args.mode == "poll-calibration":
        return await poll_split(args, admitted, transport, split="calibration")
    if args.mode == "submit-heldout":
        return await submit_heldout(args, admitted, transport)
    return await poll_split(args, admitted, transport, split="heldout")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("preflight", "submit-calibration",
                                          "poll-calibration", "submit-heldout",
                                          "poll-heldout"))
    parser.add_argument("--prior-dir", type=Path, required=True)
    parser.add_argument("--resume-stop-dir", type=Path, required=True)
    parser.add_argument("--packet-dir", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--labels-sha256", required=True)
    parser.add_argument("--freeze-receipt-sha256", required=True)
    parser.add_argument("--approval-receipt", type=Path)
    parser.add_argument("--approval-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        ensure(args.mode == "preflight" or
               (args.output is not None and args.approval_receipt is not None and
                args.approval_sha256 is not None), "batch_live_arguments_required")
        admitted = _admit(args)
        if args.mode == "preflight":
            result = {"status": "preflight_passed", "new_calls": 0,
                      "calibration_items": 45,
                      "conditional_heldout_items": 48,
                      "prior_checkpoint_sha256":
                          digest(canonical_bytes(admitted[2]))}
        else:
            result = asyncio.run(_live(args, admitted))
        print(json.dumps(result, sort_keys=True))
        return 0
    except (PilotFailure, OSError, ValueError, KeyError, TypeError,
            httpx.HTTPError, asyncio.TimeoutError) as exc:
        code = str(exc) if isinstance(exc, PilotFailure) else type(exc).__name__
        # Never print provider details, prompt content, or raw response text.
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,80}", code):
            code = "batch_execution_uncertain"
        print(json.dumps({"status": "batch_stopped", "reason": code,
                          "release_gate_passed": False}, sort_keys=True),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
