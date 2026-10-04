"""One-shot Gemini 3.6 source-ID pilot on pinned public PDFs, approval required.

This runner is not used by the application. It transmits only the current
public question and four exact, previously reviewed public page/cue candidates.
It refuses execution without a separate exact-envelope approval receipt.
No automatic retry or resume is possible after a durable run claim is made.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from tempfile import gettempdir, mkstemp
import time

import httpx

from evaluate_source_id_multipdf_36 import (
    MODEL, PACKET_SHA256, SCHEMA, THINKING, _fingerprint,
    _global_score_claim_path, _split_requests, digest, write_exclusive,
)
from finalize_public_source_id_multipdf import ReviewError, read_pinned, require

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
from app.ai.source_judgment import (  # noqa: E402
    MAX_OUTPUT_TOKENS, MAX_WIRE_BYTES, SourceJudgmentError,
    canonical_bytes, parse_source_id_output,
)


ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent"
APPROVAL_SCHEMA = "cardchemy_public_source_id_36_live_approval_v1"
AUTHORIZATION_ID = "lane6-public-36-eight-pdf-20260929-ff03e1f99d40410189f1f554b90a578c"
MAX_CALLS_PER_SPLIT = 48
MAX_CALLS_TOTAL = 96
MAX_INPUT_PER_CALL = 8192
MAX_OUTPUT_PER_CALL = 1024
MAX_INPUT_TOTAL = 786432
MAX_OUTPUT_TOTAL = 98304
MAX_COST_MICROUSD = 2_000_000
MAX_CALL_SECONDS = 30
MAX_TOTAL_SECONDS = 90 * 60
MIN_START_INTERVAL_SECONDS = 6
INPUT_USD_PER_MILLION = Decimal("1.50")
OUTPUT_USD_PER_MILLION = Decimal("7.50")
MAX_HTTP_RESPONSE_BYTES = 8192
MAX_REST_REQUEST_BYTES = 8192
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class PilotFailure(RuntimeError):
    """Safe content-free failure code."""


_SAFE_PILOT_FAILURE_CODES = frozenset({
    "total_time_budget", "remaining_budget", "cross_split_spacing",
    "observed_cost_budget", "wire_invalid", "wire_payload_invalid",
    "wire_candidate_invalid", "rest_body_budget", "duplicate_json_key",
    "provider_response_oversize", "provider_json_invalid",
    "provider_candidate_invalid", "provider_finish_invalid",
    "provider_ids_invalid", "provider_usage_missing",
    "provider_usage_invalid", "provider_token_limit_exceeded",
})


def _failure_code(exc: BaseException) -> str:
    """Classify failures without retaining exception messages or response data."""
    if isinstance(exc, PilotFailure):
        code = exc.args[0] if exc.args else None
        if type(code) is str and (code in _SAFE_PILOT_FAILURE_CODES or
                                  re.fullmatch(r"provider_http_[1-5][0-9]{2}", code)):
            return code
        return "pilot_guard_failed"
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return "provider_timeout"
    if isinstance(exc, httpx.ProxyError):
        return "provider_proxy_error"
    if isinstance(exc, httpx.ConnectError):
        return "provider_connect_error"
    if isinstance(exc, httpx.NetworkError):
        return "provider_network_error"
    if isinstance(exc, httpx.ProtocolError):
        return "provider_protocol_error"
    if isinstance(exc, httpx.RequestError):
        return "provider_transport_error"
    if isinstance(exc, PermissionError):
        return "local_permission_error"
    if isinstance(exc, OSError):
        return "local_io_error"
    if isinstance(exc, asyncio.CancelledError):
        return "execution_cancelled"
    return "provider_execution_uncertain"


def ensure(ok: bool, code: str) -> None:
    if not ok:
        raise PilotFailure(code)


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        ensure(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def _canonical_json(path: Path, max_bytes: int) -> dict:
    ensure(path.is_file() and not path.is_symlink() and
           path.stat().st_size <= max_bytes, "input_file_invalid")
    raw = path.read_bytes()
    value = json.loads(raw, object_pairs_hook=_unique_pairs)
    ensure(type(value) is dict and raw == canonical_bytes(value),
           "input_format_invalid")
    return value


def _cost_microusd(input_tokens: int, output_tokens: int) -> int:
    # USD per million tokens equals micro-USD per token exactly.
    return int((Decimal(input_tokens) * INPUT_USD_PER_MILLION +
                Decimal(output_tokens) * OUTPUT_USD_PER_MILLION
                ).to_integral_value(rounding=ROUND_CEILING))


def _approval_claim_path(approval_sha: str) -> Path:
    """Consume one approval across every prepared output directory."""
    ensure(type(approval_sha) is str and _HEX64.fullmatch(approval_sha),
           "approval_hash_required")
    directory = Path(gettempdir()).resolve() / "cardchemy-source-id-36-pilot-ledger"
    # Python's owner-only mkdir mode on Windows can discard the inherited
    # per-user Temp ACL when the sandbox and approved command use different
    # local identities. The user's Temp ACL remains the access boundary there.
    directory.mkdir(mode=0o700 if os.name != "nt" else 0o777, exist_ok=True)
    ensure(directory.is_dir() and not directory.is_symlink(),
           "approval_ledger_unavailable")
    return directory / f"approval-{approval_sha}.claim"


def _probe_writable_directory(directory: Path) -> None:
    """Check the executing identity's Temp ACL without consuming a run claim."""
    ensure(directory.is_dir() and not directory.is_symlink(),
           "os_temp_output_required")
    handle, name = mkstemp(prefix=".cardchemy-preflight-", dir=directory)
    try:
        os.write(handle, b"1")
        os.fsync(handle)
    finally:
        os.close(handle)
        Path(name).unlink()


def _pilot_timing_from_calibration(live_calibration: dict,
                                   now_unix_ms: int) -> tuple[int, int]:
    started = live_calibration.get("pilot_started_unix_ms")
    last_call = live_calibration.get("last_call_started_unix_ms")
    ensure(type(started) is int and started > 0 and
           started <= now_unix_ms and
           now_unix_ms - started < MAX_TOTAL_SECONDS * 1000,
           "total_time_budget")
    ensure(type(last_call) is int and
           started <= last_call <= now_unix_ms and
           last_call - started < MAX_TOTAL_SECONDS * 1000,
           "calibration_call_time_invalid")
    return started, last_call


def _ensure_claims_available(approval_claim_path: Path,
                             prepared_dir: Path) -> None:
    for path in (approval_claim_path, prepared_dir / "live-run.claim"):
        ensure(not path.exists() and not path.is_symlink(),
               "pilot_claim_consumed")


def _preflight_score_claim(fingerprint: str, split: str) -> None:
    """Probe the later scorer's ledger without consuming its one-shot claim."""
    score_claim = _global_score_claim_path(fingerprint, split)
    _probe_writable_directory(score_claim.parent)
    ensure(not score_claim.exists() and not score_claim.is_symlink(),
           "pilot_score_claim_consumed")


def _append_sync(path: Path, value: dict) -> None:
    raw = canonical_bytes(value)
    with path.open("ab") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _load_public_requests(prepared_dir: Path, prepare_sha: str,
                          packet_dir: Path) -> tuple[dict, dict]:
    ensure(len(prepare_sha) == 64, "prepare_hash_required")
    receipt_path = prepared_dir / "prepare-receipt.json"
    receipt = _canonical_json(receipt_path, 8192)
    ensure(digest(receipt_path.read_bytes()) == prepare_sha and
           receipt.get("schema") == SCHEMA and
           receipt.get("status") == "prepared_no_provider_call",
           "prepare_receipt_mismatch")
    prepared_path = prepared_dir / "requests.json"
    prepared = _canonical_json(prepared_path, 1_000_000)
    ensure(digest(prepared_path.read_bytes()) == receipt.get("requests_sha256") and
           prepared.get("schema") == SCHEMA and
           prepared.get("split") in {"calibration", "heldout"} and
           prepared.get("source_packet_sha256") == PACKET_SHA256 and
           prepared.get("model") == MODEL and
           prepared.get("thinking") == THINKING and
           prepared.get("max_output_tokens") == MAX_OUTPUT_TOKENS and
           prepared.get("fingerprint") == receipt.get("fingerprint") ==
           _fingerprint(PACKET_SHA256, receipt["labels_sha256"],
                        receipt["freeze_receipt_sha256"]),
           "prepared_contract_mismatch")
    source = read_pinned(packet_dir / "blind-review-packet.json",
                         PACKET_SHA256, 1_000_000)
    # Rebuild from the pinned public packet, not from an arbitrary prepared
    # request file. A fake hash/receipt cannot introduce private text.
    expected = _split_requests(source, prepared["split"])
    ensure(prepared.get("requests") == expected and
           len(expected) == MAX_CALLS_PER_SPLIT and
           sum(row["status"] == "callable" for row in expected) ==
           receipt.get("callable_count") and
           sum(row["status"] == "clarification" for row in expected) ==
           receipt.get("clarification_count"),
           "public_request_source_mismatch")
    for row in expected:
        if row["status"] == "callable":
            _rest_body(row["wire"])
    return prepared, receipt


def _validate_approval(approval_path: Path, approval_sha: str,
                       prepared: dict, receipt: dict) -> dict:
    ensure(AUTHORIZATION_ID != "PENDING_SEPARATE_OPERATOR_APPROVAL",
           "separate_operator_approval_required")
    ensure(type(approval_sha) is str and len(approval_sha) == 64,
           "approval_hash_required")
    approval = _canonical_json(approval_path, 4096)
    ensure(digest(approval_path.read_bytes()) == approval_sha and
           set(approval) == {"schema", "authorization_id", "operator_approved",
                             "previous_failed_cost_unknown", "endpoint", "model",
                             "split", "requests_sha256", "prepare_receipt_sha256",
                             "fingerprint", "max_calls_total", "max_input_tokens_total",
                             "max_output_tokens_total", "max_cost_microusd",
                             "max_input_tokens_per_call", "max_output_tokens_per_call",
                             "input_price_usd_per_million",
                             "output_price_usd_per_million",
                             "max_call_seconds", "max_total_seconds",
                             "min_start_interval_seconds", "prior_cost_microusd"} and
           approval["schema"] == APPROVAL_SCHEMA and
           approval["authorization_id"] == AUTHORIZATION_ID and
           approval["operator_approved"] is True and
           approval["previous_failed_cost_unknown"] is True and
           approval["endpoint"] == ENDPOINT and approval["model"] == MODEL and
           approval["split"] == prepared["split"] and
           approval["requests_sha256"] == receipt["requests_sha256"] and
           approval["prepare_receipt_sha256"] == digest(canonical_bytes(receipt)) and
           approval["fingerprint"] == receipt["fingerprint"] and
           approval["max_calls_total"] == MAX_CALLS_TOTAL and
           approval["max_input_tokens_total"] == MAX_INPUT_TOTAL and
           approval["max_output_tokens_total"] == MAX_OUTPUT_TOTAL and
           approval["max_cost_microusd"] == MAX_COST_MICROUSD and
           approval["max_input_tokens_per_call"] == MAX_INPUT_PER_CALL and
           approval["max_output_tokens_per_call"] == MAX_OUTPUT_PER_CALL and
           approval["input_price_usd_per_million"] == str(INPUT_USD_PER_MILLION) and
           approval["output_price_usd_per_million"] == str(OUTPUT_USD_PER_MILLION) and
           approval["max_call_seconds"] == MAX_CALL_SECONDS and
           approval["max_total_seconds"] == MAX_TOTAL_SECONDS and
           approval["min_start_interval_seconds"] == MIN_START_INTERVAL_SECONDS and
           type(approval["prior_cost_microusd"]) is int and
           0 <= approval["prior_cost_microusd"] <= MAX_COST_MICROUSD and
           (prepared["split"] != "calibration" or
            approval["prior_cost_microusd"] == 0),
           "approval_envelope_mismatch")
    return approval


def _rest_body(wire: dict) -> dict:
    ensure(set(wire) == {"system_instruction", "user_payload", "response_schema"} and
           len(canonical_bytes(wire)) <= MAX_WIRE_BYTES,
           "wire_invalid")
    payload = wire["user_payload"]
    ensure(type(payload) is dict and set(payload) == {"question", "candidates"} and
           type(payload["question"]) is str and type(payload["candidates"]) is list,
           "wire_payload_invalid")
    # Plain tagged text transmits the same exact page/cue fields without
    # double-JSON escaping. The complete REST body then stays below the
    # approved 8,192-byte admission cap even for the longest public slate.
    user_text = "Current question:\n" + payload["question"] + "\nCandidate pages:\n"
    for candidate in payload["candidates"]:
        ensure(type(candidate) is dict and set(candidate) ==
               {"id", "page", "page_text", "cue"}, "wire_candidate_invalid")
        source_id = candidate["id"]
        user_text += (f"<{source_id} page={candidate['page']}>\n<page>\n" +
                      candidate["page_text"] + "\n</page>\n<cue>\n" +
                      candidate["cue"] + f"\n</cue>\n</{source_id}>\n")
    body = {
        "systemInstruction": {"parts": [{"text": wire["system_instruction"]}]},
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": wire["response_schema"],
            "maxOutputTokens": MAX_OUTPUT_PER_CALL,
            "thinkingConfig": {"thinkingLevel": THINKING},
        },
        "store": False,
    }
    ensure(len(canonical_bytes(body)) <= MAX_REST_REQUEST_BYTES,
           "rest_body_budget")
    return body


def _parse_provider_response(response: httpx.Response,
                             issued_ids: list[str]) -> tuple[str, int, int]:
    # Status and size are safe diagnostics. Never read or persist the provider
    # error body: it may echo question or page content.
    ensure(response.status_code == 200,
           f"provider_http_{response.status_code}")
    ensure(len(response.content) <= MAX_HTTP_RESPONSE_BYTES,
           "provider_response_oversize")
    try:
        body = json.loads(response.content, object_pairs_hook=_unique_pairs)
    except (TypeError, ValueError, UnicodeError) as exc:
        raise PilotFailure("provider_json_invalid") from exc
    ensure(type(body) is dict and type(body.get("candidates")) is list and
           len(body["candidates"]) == 1, "provider_candidate_invalid")
    candidate = body["candidates"][0]
    ensure(type(candidate) is dict and candidate.get("finishReason") == "STOP" and
           type(candidate.get("content")) is dict and
           type(candidate["content"].get("parts")) is list and
           len(candidate["content"]["parts"]) == 1 and
           type(candidate["content"]["parts"][0]) is dict and
           type(candidate["content"]["parts"][0].get("text")) is str,
           "provider_finish_invalid")
    raw = candidate["content"]["parts"][0]["text"]
    try:
        selected = parse_source_id_output(raw, issued_ids)
    except SourceJudgmentError as exc:
        raise PilotFailure("provider_ids_invalid") from exc
    usage = body.get("usageMetadata")
    ensure(type(usage) is dict and
           type(usage.get("promptTokenCount")) is int and
           type(usage.get("candidatesTokenCount")) is int and
           type(usage.get("thoughtsTokenCount", 0)) is int and
           all(usage[name] >= 0 for name in
               ("promptTokenCount", "candidatesTokenCount")) and
           usage.get("thoughtsTokenCount", 0) >= 0,
           "provider_usage_missing")
    input_tokens = usage["promptTokenCount"]
    output_tokens = (usage["candidatesTokenCount"] +
                     usage.get("thoughtsTokenCount", 0))
    total = usage.get("totalTokenCount")
    ensure(total is None or (type(total) is int and total >= input_tokens),
           "provider_usage_invalid")
    if total is not None:
        output_tokens = max(output_tokens, total - input_tokens)
    ensure(input_tokens <= MAX_INPUT_PER_CALL and
           output_tokens <= MAX_OUTPUT_PER_CALL,
           "provider_token_limit_exceeded")
    return json.dumps({"selected_ids": selected}, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=True), input_tokens, output_tokens


async def _http_call(client: httpx.AsyncClient, api_key: str,
                     wire: dict) -> httpx.Response:
    # The transport has no retry middleware and refuses redirects. No key is
    # placed in the URL, logs or artifacts.
    return await client.post(ENDPOINT,
                             headers={"x-goog-api-key": api_key,
                                      "Content-Type": "application/json"},
                             json=_rest_body(wire))


async def run_once(prepared: dict, receipt: dict, approval: dict,
                   output: Path, transport: Callable[[dict], Awaitable[httpx.Response]],
                   *, approval_claim_path: Path,
                   clock: Callable[[], float] = time.monotonic,
                   sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
                   wall_clock: Callable[[], float] = time.time,
                   pilot_started_unix_ms: int | None = None,
                   last_calibration_call_unix_ms: int | None = None) -> dict:
    ensure(output.is_dir() and not output.is_symlink() and
           prepared["split"] == approval["split"] and
           receipt["requests_sha256"] == approval["requests_sha256"] and
           approval_claim_path.is_absolute() and
           approval_claim_path.parent.is_dir() and
           not approval_claim_path.parent.is_symlink() and
           output not in approval_claim_path.parents,
           "run_identity_invalid")
    requests = prepared["requests"]
    callable_rows = [row for row in requests if row["status"] == "callable"]
    ensure(len(callable_rows) <= MAX_CALLS_PER_SPLIT and
           len(callable_rows) == receipt["callable_count"],
           "run_count_invalid")
    prior_cost = approval["prior_cost_microusd"]
    # Reserve the full worst-case cost of every remaining call. Provider usage
    # can be absent on a failed or interrupted request, so no optimism here.
    ensure(prior_cost + len(callable_rows) * _cost_microusd(
        MAX_INPUT_PER_CALL, MAX_OUTPUT_PER_CALL) <= MAX_COST_MICROUSD,
        "run_cost_budget")
    current_unix_ms = int(wall_clock() * 1000)
    started_unix_ms = (current_unix_ms if pilot_started_unix_ms is None
                       else pilot_started_unix_ms)
    ensure(type(started_unix_ms) is int and started_unix_ms > 0 and
           started_unix_ms <= current_unix_ms and
           current_unix_ms - started_unix_ms < MAX_TOTAL_SECONDS * 1000,
           "total_time_budget")
    ensure((prepared["split"] == "calibration" and
            last_calibration_call_unix_ms is None) or
           (prepared["split"] == "heldout" and
            type(last_calibration_call_unix_ms) is int and
            started_unix_ms <= last_calibration_call_unix_ms <= current_unix_ms),
           "calibration_call_time_invalid")
    claim = {
        "requests_sha256": receipt["requests_sha256"],
        "fingerprint": receipt["fingerprint"],
        "split": prepared["split"], "max_calls": len(callable_rows),
        "pilot_started_unix_ms": started_unix_ms}
    write_exclusive(approval_claim_path, claim)
    write_exclusive(output / "live-run.claim", claim)
    response_path = output / "response-ids.jsonl"
    usage_path = output / "usage-receipts.jsonl"
    with response_path.open("xb"):
        pass
    with usage_path.open("xb"):
        pass
    previous_start: float | None = None
    last_call_started_unix_ms: int | None = None
    start = clock()
    spent = prior_cost
    input_total = 0
    output_total = 0
    attempts = 0
    current_claim_started: float | None = None
    try:
        for row in callable_rows:
            current_claim_started = None
            if previous_start is None and last_calibration_call_unix_ms is not None:
                pause = (last_calibration_call_unix_ms +
                         MIN_START_INTERVAL_SECONDS * 1000 -
                         int(wall_clock() * 1000)) / 1000
                if pause > 0:
                    await sleeper(pause)
            elif previous_start is not None:
                pause = MIN_START_INTERVAL_SECONDS - (clock() - previous_start)
                if pause > 0:
                    await sleeper(pause)
            now_unix_ms = int(wall_clock() * 1000)
            remaining_seconds = min(
                MAX_TOTAL_SECONDS - (clock() - start),
                (started_unix_ms + MAX_TOTAL_SECONDS * 1000 - now_unix_ms) / 1000,
            )
            ensure(now_unix_ms >= started_unix_ms and
                   remaining_seconds > 0, "total_time_budget")
            remaining = len(callable_rows) - attempts
            ensure(spent + remaining * _cost_microusd(
                MAX_INPUT_PER_CALL, MAX_OUTPUT_PER_CALL) <= MAX_COST_MICROUSD and
                input_total + remaining * MAX_INPUT_PER_CALL <= MAX_INPUT_TOTAL and
                output_total + remaining * MAX_OUTPUT_PER_CALL <= MAX_OUTPUT_TOTAL,
                "remaining_budget")
            # This file survives a crash and makes an uncertain physical request
            # visible. The whole run's claim refuses automatic restart.
            write_exclusive(output / f"call-{attempts + 1:02d}.claim", {
                "group_id": row["group_id"], "wire_sha256": row["wire_sha256"]})
            current_claim_started = clock()
            call_unix_ms = int(wall_clock() * 1000)
            call_remaining_seconds = min(
                MAX_TOTAL_SECONDS - (clock() - start),
                (started_unix_ms + MAX_TOTAL_SECONDS * 1000 - call_unix_ms) / 1000,
            )
            ensure(call_unix_ms >= started_unix_ms and
                   call_remaining_seconds > 0, "total_time_budget")
            if attempts == 0 and last_calibration_call_unix_ms is not None:
                ensure(call_unix_ms - last_calibration_call_unix_ms >=
                       MIN_START_INTERVAL_SECONDS * 1000,
                       "cross_split_spacing")
            previous_start = clock()
            last_call_started_unix_ms = call_unix_ms
            attempts += 1
            response = await asyncio.wait_for(transport(row["wire"]),
                                              timeout=min(MAX_CALL_SECONDS,
                                                          call_remaining_seconds))
            issued = [item["id"] for item in
                      row["wire"]["user_payload"]["candidates"]]
            raw_json, input_tokens, output_tokens = _parse_provider_response(
                response, issued)
            cost = _cost_microusd(input_tokens, output_tokens)
            ensure(spent + cost <= MAX_COST_MICROUSD,
                   "observed_cost_budget")
            input_total += input_tokens
            output_total += output_tokens
            spent += cost
            _append_sync(response_path, {"group_id": row["group_id"],
                                         "wire_sha256": row["wire_sha256"],
                                         "raw_json": raw_json})
            _append_sync(usage_path, {"group_id": row["group_id"],
                                      "finish_reason": "STOP",
                                      "input_tokens": input_tokens,
                                      "output_tokens": output_tokens,
                                      "cost_microusd": cost})
    except (Exception, asyncio.CancelledError) as exc:
        code = _failure_code(exc)
        http_status = None
        if isinstance(code, str) and code.startswith("provider_http_"):
            status_text = code.removeprefix("provider_http_")
            if status_text.isdecimal():
                http_status = int(status_text)
                code = "provider_http_error"
        failure = {"status": "stopped_no_retry", "reason": code,
                   "attempts": attempts, "known_cost_microusd": spent,
                   "failed_attempt_cost_unknown": attempts > 0}
        if current_claim_started is not None:
            failure["elapsed_since_call_claim_ms"] = max(
                0, int((clock() - current_claim_started) * 1000))
        if http_status is not None:
            failure["http_status"] = http_status
        write_exclusive(output / "live-failure.json", failure)
        return failure
    result = {"status": "complete_one_shot", "split": prepared["split"],
               "fingerprint": receipt["fingerprint"],
               "requests_sha256": receipt["requests_sha256"],
               "pilot_started_unix_ms": started_unix_ms,
               "last_call_started_unix_ms": last_call_started_unix_ms,
               "attempts": attempts, "known_cost_microusd": spent,
              "input_tokens": input_total, "output_tokens": output_total,
              "response_ids_sha256": digest(response_path.read_bytes()),
              "usage_receipts_sha256": digest(usage_path.read_bytes())}
    write_exclusive(output / "live-result.json", result)
    return result


def _admit_cli(args: argparse.Namespace) -> tuple[dict, dict, dict, int | None, int | None]:
    temp = Path(gettempdir()).resolve()
    for path in (args.prepared_dir, args.packet_dir, args.approval_receipt):
        ensure(path.is_absolute() and temp in path.resolve().parents,
               "os_temp_input_required")
    prepared, receipt = _load_public_requests(args.prepared_dir,
                                              args.prepare_sha256,
                                              args.packet_dir)
    approval = _validate_approval(args.approval_receipt,
                                   args.approval_sha256, prepared, receipt)
    pilot_started_unix_ms = None
    last_calibration_call_unix_ms = None
    if prepared["split"] == "heldout":
        ensure(args.calibration_score is not None and
               args.calibration_score_sha256 is not None and
               args.calibration_live_result is not None and
               args.calibration_live_result_sha256 is not None and
               args.calibration_score.is_absolute() and
               temp in args.calibration_score.resolve().parents and
               args.calibration_live_result.is_absolute() and
               temp in args.calibration_live_result.resolve().parents,
               "calibration_gate_required")
        calibration = _canonical_json(args.calibration_score, 100_000)
        live_calibration = _canonical_json(args.calibration_live_result, 8192)
        ensure(digest(args.calibration_score.read_bytes()) ==
               args.calibration_score_sha256 and
               digest(args.calibration_live_result.read_bytes()) ==
               args.calibration_live_result_sha256 and
               calibration.get("schema") == SCHEMA and
               calibration.get("split") == "calibration" and
               calibration.get("public_passed") is True and
               calibration.get("fingerprint") == receipt["fingerprint"] and
               calibration.get("labels_sha256") == receipt["labels_sha256"] and
               live_calibration.get("status") == "complete_one_shot" and
               live_calibration.get("split") == "calibration" and
               live_calibration.get("fingerprint") == receipt["fingerprint"] and
               live_calibration.get("requests_sha256") ==
               calibration.get("requests_sha256") and
               live_calibration.get("response_ids_sha256") ==
               calibration.get("responses_sha256") and
               type(live_calibration.get("known_cost_microusd")) is int and
               live_calibration["known_cost_microusd"] ==
               approval["prior_cost_microusd"],
               "calibration_gate_failed")
        pilot_started_unix_ms, last_calibration_call_unix_ms = _pilot_timing_from_calibration(
            live_calibration, int(time.time() * 1000))
    ensure(args.prepared_dir / "live-run.claim" != args.approval_receipt,
           "approval_path_invalid")
    _probe_writable_directory(args.prepared_dir)
    approval_claim_path = _approval_claim_path(args.approval_sha256)
    _probe_writable_directory(approval_claim_path.parent)
    _ensure_claims_available(approval_claim_path, args.prepared_dir)
    _preflight_score_claim(receipt["fingerprint"], prepared["split"])
    return (prepared, receipt, approval, pilot_started_unix_ms,
            last_calibration_call_unix_ms)


async def _live_cli(args: argparse.Namespace) -> dict:
    (prepared, receipt, approval, pilot_started_unix_ms,
     last_calibration_call_unix_ms) = _admit_cli(args)
    # No credential is read until all public-only identity and approval gates
    # pass. The sole local root configuration remains the source of secrets.
    from app.config import Settings
    api_key = Settings().rag_ai_api_key_value
    ensure(bool(api_key), "provider_key_unavailable")
    async with httpx.AsyncClient(timeout=MAX_CALL_SECONDS,
                                 follow_redirects=False) as client:
        return await run_once(prepared, receipt, approval, args.prepared_dir,
                               lambda wire: _http_call(client, api_key, wire),
                               approval_claim_path=_approval_claim_path(
                                   args.approval_sha256),
                               pilot_started_unix_ms=pilot_started_unix_ms,
                               last_calibration_call_unix_ms=
                               last_calibration_call_unix_ms)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-dir", type=Path, required=True)
    parser.add_argument("--packet-dir", type=Path, required=True)
    parser.add_argument("--prepare-sha256", required=True)
    parser.add_argument("--approval-receipt", type=Path, required=True)
    parser.add_argument("--approval-sha256", required=True)
    parser.add_argument("--calibration-score", type=Path)
    parser.add_argument("--calibration-score-sha256")
    parser.add_argument("--calibration-live-result", type=Path)
    parser.add_argument("--calibration-live-result-sha256")
    parser.add_argument("--preflight-only", action="store_true",
                        help="validate packet, approval and Temp ACL without a provider call")
    args = parser.parse_args()
    try:
        if args.preflight_only:
            prepared, receipt, _approval, _started, _last = _admit_cli(args)
            result = {"status": "preflight_passed", "split": prepared["split"],
                      "fingerprint": receipt["fingerprint"],
                      "callable_count": receipt["callable_count"]}
        else:
            result = asyncio.run(_live_cli(args))
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] in {"complete_one_shot", "preflight_passed"} else 2
    except (PilotFailure, ReviewError, OSError, ValueError, KeyError, TypeError) as exc:
        code = str(exc) if isinstance(exc, (PilotFailure, ReviewError)) else type(exc).__name__
        print(json.dumps({"status": "pilot_rejected", "reason": code,
                          "execution_uncertain": (args.prepared_dir / "live-run.claim").exists()},
                         sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
