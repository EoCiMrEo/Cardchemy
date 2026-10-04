"""One-use public source-ID v2 caller; no approval or model is installed.

The default command is a keyless, networkless packet preflight. Execution
requires a later source change that pins the separately approved authorization
identity and model, plus an exact approval receipt. This research tool never
reads private Knowledge, changes application state, or enables Ask.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from tempfile import gettempdir
import time

import httpx

import prepare_fresh_public_source_id_v2 as freezer
import score_fresh_public_source_id_v2 as scorer
from prototype_exhaustive_source_id_v2 import build_exhaustive_public_wire
from app.ai.source_judgment import (
    SourceJudgmentError, canonical_bytes as wire_bytes, parse_source_id_output,
)


AUTHORIZATION_ID = "PENDING_SEPARATE_OPERATOR_APPROVAL"
MODEL = "PENDING_SEPARATE_MODEL_APPROVAL"
THINKING = "low"
APPROVAL_SCHEMA = "fresh_public_source_id_v2_live_approval"
CLAIM_SCHEMA = "fresh_public_source_id_v2_attempt_claim"
SOURCE_MANIFEST_SHA256 = "6572395ae7234abdb790226940d0a104db153103d30f14ebb9d0a4e3118df72e"
MAX_REST_BYTES = 12_288
MAX_RESPONSE_BYTES = 8_192
MAX_INPUT_PER_CALL = 8_192
MAX_OUTPUT_PER_CALL = 1_024
MAX_CALL_SECONDS = 30
MAX_TOTAL_SECONDS = 7_200
MIN_START_INTERVAL_SECONDS = 6
MAX_NEW_COST_MICROUSD = 5_000_000
INPUT_TOKEN_PROTOCOL_RESERVE = 512
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
MODEL_NAME = re.compile(r"gemini-[a-z0-9][a-z0-9.-]{0,80}\Z")
SAFE_FAILURES = frozenset({
    "provider_timeout", "provider_transport_error", "provider_connect_error",
    "provider_network_error", "provider_protocol_error", "provider_proxy_error",
    "provider_http_error", "provider_response_oversize", "provider_json_invalid",
    "provider_candidate_invalid", "provider_finish_invalid", "provider_ids_invalid",
    "provider_usage_invalid", "provider_token_limit_exceeded", "provider_model_mismatch",
    "new_cost_budget", "total_time_budget", "attempt_spacing_invalid",
    "local_io_error", "execution_cancelled", "provider_execution_uncertain",
    "provider_http_408", "provider_http_429", "provider_http_502",
    "provider_http_503", "provider_http_504", "too_many_provider_failures",
})
SCORABLE_TRANSIENT_FAILURES = scorer.TRANSIENT_FAILURES


class PilotError(ValueError):
    """Safe, content-free rejection code."""


def require(ok: bool, code: str) -> None:
    if not ok:
        raise PilotError(code)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: object) -> bytes:
    return scorer.canonical_bytes(value)


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def _read_canonical(path: Path, max_bytes: int) -> tuple[dict, str]:
    require(path.is_file() and not path.is_symlink() and
            0 < path.stat().st_size <= max_bytes, "input_file_invalid")
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                           parse_constant=lambda _: require(False, "nonfinite_json"))
    except (UnicodeError, ValueError) as exc:
        raise PilotError("input_json_invalid") from exc
    require(type(value) is dict and canonical_bytes(value) == raw,
            "input_not_canonical")
    return value, digest(raw)


def _write_exclusive(path: Path, value: object) -> None:
    with path.open("xb") as stream:
        stream.write(canonical_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())


def _append(path: Path, value: object) -> None:
    with path.open("ab") as stream:
        stream.write(canonical_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())


def _source_files() -> dict[str, str]:
    root = Path(__file__).resolve().parents[1]
    return {
        "caller": digest(Path(__file__).read_bytes()),
        "freezer": digest((root / "scripts/prepare_fresh_public_source_id_v2.py").read_bytes()),
        "prototype": digest((root / "scripts/prototype_exhaustive_source_id_v2.py").read_bytes()),
        "parser": digest((root / "backend/app/ai/source_judgment.py").read_bytes()),
        "scorer": digest((root / "scripts/score_fresh_public_source_id_v2.py").read_bytes()),
    }


def _model_endpoint() -> str:
    require(AUTHORIZATION_ID != "PENDING_SEPARATE_OPERATOR_APPROVAL" and
            bool(re.fullmatch(r"[A-Za-z0-9_-]{12,100}", AUTHORIZATION_ID)),
            "separate_operator_approval_required")
    require(MODEL_NAME.fullmatch(MODEL) is not None, "separate_model_approval_required")
    return ("https://generativelanguage.googleapis.com/v1beta/models/" +
            MODEL + ":generateContent")


def _rest_body(wire: dict) -> dict:
    # The v2 wire presents shown_cue before page_text. Never substitute the
    # dormant v4 app serializer, which has a different candidate presentation.
    require(set(wire) == {"system_instruction", "user_payload", "response_schema"},
            "wire_invalid")
    body = {
        "systemInstruction": {"parts": [{"text": wire["system_instruction"]}]},
        "contents": [{"role": "user", "parts": [{"text": json.dumps(
            wire["user_payload"], separators=(",", ":"), ensure_ascii=False,
            allow_nan=False)}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": wire["response_schema"],
            "maxOutputTokens": MAX_OUTPUT_PER_CALL,
            "thinkingConfig": {"thinkingLevel": THINKING},
        },
        "store": False,
    }
    require(len(canonical_bytes(body)) <= MAX_REST_BYTES, "rest_body_budget")
    return body


def _calibration_pass(frozen_dir: Path, results_dir: Path) -> str:
    # The scorer itself opens only calibration on this call. A partial result
    # or a malformed receipt cannot be promoted by a caller-supplied flag.
    score = scorer.score_run(frozen_dir, results_dir)
    require(score["calibration_passed"] is True and
            score["heldout_opened"] is False, "calibration_not_passed")
    score_sha = digest(canonical_bytes(score))
    saved, saved_sha = _read_canonical(results_dir / "score.json", 100_000)
    require(saved_sha == score_sha and saved == score,
            "calibration_score_changed")
    return score_sha


def admit_public_packet(frozen_dir: Path, manifest_path: Path,
                        overlap_path: Path, split: str,
                        calibration_results: Path | None = None) -> dict:
    """Revalidate the exact public PDFs and frozen v2 packet before any key."""
    require(split in scorer.SPLITS and frozen_dir.is_dir() and
            not frozen_dir.is_symlink(), "split_or_freeze_invalid")
    freeze, freeze_sha = scorer._freeze(frozen_dir)
    require(freeze["corpus_id"] == freezer.CORPUS_ID and
            freeze["source_manifest_sha256"] == SOURCE_MANIFEST_SHA256,
            "public_source_identity_invalid")
    manifest, manifest_sha = freezer.read_json(manifest_path)
    require(manifest_sha == SOURCE_MANIFEST_SHA256, "public_manifest_changed")
    pages, documents = freezer.load_verified_pages(manifest, manifest_path)
    overlap, overlap_sha = freezer.read_json(overlap_path)
    require(overlap_sha == freeze["overlap_diagnostic_sha256"] and
            overlap.get("schema_version") == freezer.OVERLAP_DIAGNOSTIC_SCHEMA and
            overlap.get("source_manifest_sha256") == manifest_sha and
            type(overlap.get("per_new_document")) is list and
            len(overlap["per_new_document"]) == 8,
            "overlap_diagnostic_invalid")
    excluded = set()
    seen_overlap_documents = set()
    for row in overlap["per_new_document"]:
        require(type(row) is dict and row.get("document_id") in freezer.EXPECTED and
                row["document_id"] not in seen_overlap_documents and
                type(row.get("excluded_pages")) is list and
                all(type(page) is int and 1 <= page <= freezer.EXPECTED[row["document_id"]][1]
                    for page in row["excluded_pages"]) and
                row["excluded_pages"] == sorted(set(row["excluded_pages"])),
                "overlap_exclusion_invalid")
        seen_overlap_documents.add(row["document_id"])
        excluded.update((row["document_id"], page) for page in row["excluded_pages"])
    require(seen_overlap_documents == set(freezer.EXPECTED),
            "overlap_exclusion_invalid")
    calibration_score_sha = None
    if split == "heldout":
        require(calibration_results is not None, "calibration_score_required")
        calibration_score_sha = _calibration_pass(frozen_dir, calibration_results)
    else:
        require(calibration_results is None, "calibration_results_unexpected")
    packet, labels, packet_sha, labels_sha, request_hashes = scorer._packet_and_labels(
        frozen_dir, freeze, split)
    expected_documents = [
        {key: document[key] for key in ("document_id", "sha256", "pages")}
        for document in documents if document["split"] == split
    ]
    require(packet["documents"] == expected_documents,
            "public_pdf_roster_changed")
    requests = []
    for group in packet["groups"]:
        candidates = []
        for candidate in group["candidates"]:
            key = (candidate["document_id"], candidate["page"])
            require(key in pages and key not in excluded and
                    candidate["page_text_sha256"] == digest(pages[key].encode("utf-8")) and
                    pages[key][candidate["context_start"]:candidate["context_end"]] ==
                    candidate["context"] and
                    pages[key][candidate["cue_start"]:candidate["cue_end"]] ==
                    candidate["cue"], "public_page_cue_changed")
            candidates.append({"id": candidate["id"], "page": candidate["page"],
                               "page_text": candidate["context"],
                               "cue": candidate["cue"]})
        try:
            wire = build_exhaustive_public_wire(group["question"], candidates)
        except SourceJudgmentError as exc:
            raise PilotError("wire_contract_invalid") from exc
        wire_sha = digest(wire_bytes(wire))
        require(wire_sha == request_hashes[group["group_id"]],
                "wire_hash_changed")
        body = _rest_body(wire)
        requests.append({"group_id": group["group_id"], "wire_sha256": wire_sha,
                         "rest_body_sha256": digest(canonical_bytes(body)),
                         "body": body, "issued_ids":
                         [candidate["id"] for candidate in group["candidates"]]})
    body_manifest = [{key: row[key] for key in
                      ("group_id", "wire_sha256", "rest_body_sha256")}
                     for row in requests]
    require(len(requests) == 48 and len(set(request_hashes.values())) == 48,
            "request_count_invalid")
    return {"split": split, "freeze_sha256": freeze_sha,
            "source_manifest_sha256": manifest_sha,
            "overlap_diagnostic_sha256": overlap_sha,
            "packet_sha256": packet_sha, "labels_sha256": labels_sha,
            "body_manifest_sha256": digest(canonical_bytes(body_manifest)),
            "source_sha256": _source_files(), "requests": requests,
            "calibration_score_sha256": calibration_score_sha,
            "max_rest_request_bytes": max(len(canonical_bytes(row["body"]))
                                          for row in requests)}


def _price(value: object) -> Decimal:
    require(type(value) is str and bool(re.fullmatch(r"[0-9]{1,4}(?:\.[0-9]{1,6})?", value)),
            "approval_price_invalid")
    try:
        price = Decimal(value)
    except InvalidOperation as exc:
        raise PilotError("approval_price_invalid") from exc
    require(price > 0, "approval_price_invalid")
    return price


def _cost_microusd(input_tokens: int, output_tokens: int,
                   approval: dict) -> int:
    return int((Decimal(input_tokens) * _price(approval["input_price_usd_per_million"]) +
                Decimal(output_tokens) * _price(approval["output_price_usd_per_million"])
                ).to_integral_value(rounding=ROUND_CEILING))


def validate_approval(path: Path, expected_sha: str, admitted: dict) -> dict:
    endpoint = _model_endpoint()
    require(type(expected_sha) is str and HEX64.fullmatch(expected_sha) is not None,
            "approval_hash_required")
    approval, actual_sha = _read_canonical(path, 8_192)
    require(actual_sha == expected_sha, "approval_receipt_changed")
    fields = {"schema_version", "authorization_id", "operator_approved",
              "public_only", "previous_attempt_cost_unknown", "corpus_id",
              "split", "source_manifest_sha256", "overlap_diagnostic_sha256",
              "freeze_sha256", "packet_sha256", "labels_sha256",
              "body_manifest_sha256", "source_sha256", "calibration_score_sha256",
              "endpoint", "model", "thinking", "automatic_retries",
              "max_calls", "max_input_tokens_per_call", "max_output_tokens_per_call",
              "max_new_cost_microusd", "max_call_seconds", "max_total_seconds",
              "min_start_interval_seconds", "input_price_usd_per_million",
              "output_price_usd_per_million"}
    require(set(approval) == fields and
            approval["schema_version"] == APPROVAL_SCHEMA and
            approval["authorization_id"] == AUTHORIZATION_ID and
            approval["operator_approved"] is True and
            approval["public_only"] is True and
            approval["previous_attempt_cost_unknown"] is True and
            approval["corpus_id"] == freezer.CORPUS_ID and
            approval["endpoint"] == endpoint and approval["model"] == MODEL and
            approval["thinking"] == THINKING and
            type(approval["automatic_retries"]) is int and
            approval["automatic_retries"] == 0 and
            type(approval["max_calls"]) is int and approval["max_calls"] == 48 and
            type(approval["max_input_tokens_per_call"]) is int and
            admitted["max_rest_request_bytes"] + INPUT_TOKEN_PROTOCOL_RESERVE <=
                approval["max_input_tokens_per_call"] <= MAX_INPUT_PER_CALL and
            type(approval["max_output_tokens_per_call"]) is int and
            approval["max_output_tokens_per_call"] == MAX_OUTPUT_PER_CALL and
            type(approval["max_call_seconds"]) is int and
            1 <= approval["max_call_seconds"] <= MAX_CALL_SECONDS and
            type(approval["max_total_seconds"]) is int and
            1 <= approval["max_total_seconds"] <= MAX_TOTAL_SECONDS and
            type(approval["min_start_interval_seconds"]) is int and
            MIN_START_INTERVAL_SECONDS <= approval["min_start_interval_seconds"] <= 3_600 and
            type(approval["max_new_cost_microusd"]) is int and
            0 < approval["max_new_cost_microusd"] <= MAX_NEW_COST_MICROUSD,
            "approval_envelope_invalid")
    for name in ("split", "source_manifest_sha256", "overlap_diagnostic_sha256",
                 "freeze_sha256", "packet_sha256", "labels_sha256",
                 "body_manifest_sha256", "source_sha256",
                 "calibration_score_sha256"):
        require(approval[name] == admitted[name], "approval_identity_mismatch")
    _price(approval["input_price_usd_per_million"])
    _price(approval["output_price_usd_per_million"])
    require(48 * _cost_microusd(approval["max_input_tokens_per_call"],
                                approval["max_output_tokens_per_call"], approval) <=
            approval["max_new_cost_microusd"], "approval_cost_budget")
    return {**approval, "_receipt_sha256": actual_sha}


def _parse_response(response: httpx.Response, issued_ids: list[str],
                    approval: dict) -> tuple[str, int, int]:
    if response.status_code in (408, 429, 502, 503, 504):
        raise PilotError(f"provider_http_{response.status_code}")
    require(response.status_code == 200, "provider_http_error")
    require(len(response.content) <= MAX_RESPONSE_BYTES,
            "provider_response_oversize")
    try:
        body = json.loads(response.content, object_pairs_hook=_unique_pairs)
    except (TypeError, ValueError, UnicodeError) as exc:
        raise PilotError("provider_json_invalid") from exc
    require(type(body) is dict and body.get("modelVersion") == MODEL,
            "provider_model_mismatch")
    candidates = body.get("candidates")
    require(type(candidates) is list and len(candidates) == 1 and
            type(candidates[0]) is dict, "provider_candidate_invalid")
    candidate = candidates[0]
    content = candidate.get("content")
    require(candidate.get("finishReason") == "STOP" and
            type(content) is dict and type(content.get("parts")) is list and
            len(content["parts"]) == 1 and type(content["parts"][0]) is dict and
            type(content["parts"][0].get("text")) is str,
            "provider_finish_invalid")
    try:
        selected = parse_source_id_output(content["parts"][0]["text"], issued_ids)
    except SourceJudgmentError as exc:
        raise PilotError("provider_ids_invalid") from exc
    usage = body.get("usageMetadata")
    require(type(usage) is dict and type(usage.get("promptTokenCount")) is int and
            type(usage.get("candidatesTokenCount")) is int and
            type(usage.get("thoughtsTokenCount", 0)) is int and
            usage["promptTokenCount"] > 0 and usage["candidatesTokenCount"] >= 0 and
            usage.get("thoughtsTokenCount", 0) >= 0,
            "provider_usage_invalid")
    input_tokens = usage["promptTokenCount"]
    output_tokens = usage["candidatesTokenCount"] + usage.get("thoughtsTokenCount", 0)
    total = usage.get("totalTokenCount")
    require(total is None or (type(total) is int and total >= input_tokens),
            "provider_usage_invalid")
    if total is not None:
        output_tokens = max(output_tokens, total - input_tokens)
    require(input_tokens <= approval["max_input_tokens_per_call"] and
            output_tokens <= approval["max_output_tokens_per_call"],
            "provider_token_limit_exceeded")
    raw_json = json.dumps({"selected_ids": selected}, separators=(",", ":"),
                          sort_keys=True, ensure_ascii=True)
    return raw_json, input_tokens, output_tokens


def _failure_code(exc: BaseException) -> str:
    if isinstance(exc, PilotError) and exc.args and exc.args[0] in SAFE_FAILURES:
        return exc.args[0]
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
    if isinstance(exc, OSError):
        return "local_io_error"
    if isinstance(exc, asyncio.CancelledError):
        return "execution_cancelled"
    return "provider_execution_uncertain"


def _ledger_dir() -> Path:
    # Claims must survive TEMP/TMP changes and process restarts. This ignored
    # workspace directory is deliberately separate from disposable result data.
    workspace = Path(__file__).resolve().parents[1]
    parent = workspace / ".agent" / ".verification"
    root = parent / "fresh-public-source-id-v2-ledger"
    require((workspace / ".agent").is_dir() and
            not (workspace / ".agent").is_symlink() and
            not parent.is_symlink() and not root.is_symlink(),
            "ledger_unavailable")
    parent.mkdir(mode=0o700 if os.name != "nt" else 0o777, exist_ok=True)
    root.mkdir(mode=0o700 if os.name != "nt" else 0o777, exist_ok=True)
    require(root.is_dir() and not root.is_symlink(), "ledger_unavailable")
    return root


def _attempt_claim(admitted: dict, row: dict) -> dict:
    return {"schema_version": CLAIM_SCHEMA, "kind": "physical_attempt",
            "authorization_id": AUTHORIZATION_ID, "split": admitted["split"],
            "group_id": row["group_id"], "request_sha256": row["wire_sha256"],
            "rest_body_sha256": row["rest_body_sha256"], "model": MODEL}


def _verify_complete_claims(admitted: dict, ledger: Path, scope: str,
                            output: Path) -> str:
    split_claim, _ = _read_canonical(ledger / f"{scope}.claim", 4_096)
    require(split_claim == {
        "schema_version": CLAIM_SCHEMA, "kind": "split",
        "authorization_id": AUTHORIZATION_ID, "split": admitted["split"],
        "freeze_sha256": admitted["freeze_sha256"],
        "body_manifest_sha256": admitted["body_manifest_sha256"],
    }, "split_claim_changed")
    claims = {}
    for row in admitted["requests"]:
        group_id = row["group_id"]
        actual, claim_sha = _read_canonical(
            ledger / f"{scope}-{group_id}.claim", 4_096)
        require(actual == _attempt_claim(admitted, row), "attempt_claim_changed")
        claims[group_id] = claim_sha
    received = set()
    for name in scorer.RECEIPT_FILES:
        rows, _ = scorer._read_lines(output / name, 256_000)
        for row in rows:
            group_id = row.get("group_id")
            require(group_id in claims and
                    row.get("attempt_sha256") == claims[group_id],
                    "receipt_claim_mismatch")
            if name != "usage-receipts.jsonl":
                require(group_id not in received, "receipt_claim_duplicate")
                received.add(group_id)
    require(received == set(claims), "receipt_claim_incomplete")
    return digest(canonical_bytes(claims))


async def run_split(admitted: dict, approval: dict, output: Path,
                    transport: Callable[[dict], Awaitable[httpx.Response]],
                    *, ledger: Path | None = None,
                    monotonic: Callable[[], float] = time.monotonic,
                    sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep) -> dict:
    """Consume one split and one group claim before every physical attempt."""
    require(_model_endpoint() == approval["endpoint"] and
            approval["authorization_id"] == AUTHORIZATION_ID and
            approval["model"] == MODEL and approval["split"] == admitted["split"] and
            HEX64.fullmatch(approval.get("_receipt_sha256", "")) is not None and
            approval["body_manifest_sha256"] == admitted["body_manifest_sha256"] and
            len(admitted["requests"]) == 48,
            "run_identity_invalid")
    ledger = _ledger_dir() if ledger is None else ledger
    require(ledger.is_dir() and not ledger.is_symlink() and
            not output.exists() and not output.is_symlink(),
            "run_output_or_ledger_invalid")
    # A copied approval or result directory cannot reset this claim scope.
    scope = digest((AUTHORIZATION_ID + ":" + admitted["freeze_sha256"] +
                    ":" + admitted["split"]).encode("ascii"))
    _write_exclusive(ledger / f"{scope}.claim", {
        "schema_version": CLAIM_SCHEMA, "kind": "split",
        "authorization_id": AUTHORIZATION_ID, "split": admitted["split"],
        "freeze_sha256": admitted["freeze_sha256"],
        "body_manifest_sha256": admitted["body_manifest_sha256"],
    })
    output.mkdir(mode=0o700)
    for name in scorer.RECEIPT_FILES:
        with (output / name).open("xb"):
            pass
    start = monotonic()
    last_start: float | None = None
    known_cost = 0
    unknown_attempts = 0
    input_total = output_total = 0
    attempts = 0
    current_group = None
    try:
        for row in admitted["requests"]:
            if last_start is not None:
                pause = approval["min_start_interval_seconds"] - (monotonic() - last_start)
                if pause > 0:
                    require(pause < approval["max_total_seconds"] - (monotonic() - start),
                            "total_time_budget")
                    await sleeper(pause)
                require(monotonic() - last_start >= approval["min_start_interval_seconds"],
                        "attempt_spacing_invalid")
            remaining = approval["max_total_seconds"] - (monotonic() - start)
            require(remaining > 0, "total_time_budget")
            worst = _cost_microusd(approval["max_input_tokens_per_call"],
                                   approval["max_output_tokens_per_call"], approval)
            require(known_cost + (unknown_attempts + 48 - attempts) * worst <=
                    approval["max_new_cost_microusd"], "new_cost_budget")
            require(len(canonical_bytes(row["body"])) + INPUT_TOKEN_PROTOCOL_RESERVE <=
                    approval["max_input_tokens_per_call"], "new_cost_budget")
            current_group = row["group_id"]
            attempt = _attempt_claim(admitted, row)
            claim_raw = canonical_bytes(attempt)
            _write_exclusive(ledger / f"{scope}-{current_group}.claim", attempt)
            attempt_sha = digest(claim_raw)
            last_start = monotonic()
            attempts += 1
            try:
                response = await asyncio.wait_for(
                    transport(row["body"]),
                    timeout=min(approval["max_call_seconds"], remaining))
                raw_json, input_tokens, output_tokens = _parse_response(
                    response, row["issued_ids"], approval)
            except (Exception, asyncio.CancelledError) as exc:
                reason = _failure_code(exc)
                if reason not in SCORABLE_TRANSIENT_FAILURES:
                    raise
                _append(output / "errors.jsonl", {
                    "group_id": current_group,
                    "request_sha256": row["wire_sha256"],
                    "attempt_sha256": attempt_sha,
                    "reason": reason,
                    "failed_attempt_cost_unknown": True,
                    "model": MODEL,
                })
                unknown_attempts += 1
                current_group = None
                if unknown_attempts > 2:
                    raise PilotError("too_many_provider_failures") from exc
                continue
            cost = _cost_microusd(input_tokens, output_tokens, approval)
            require(known_cost + cost + unknown_attempts * worst <=
                    approval["max_new_cost_microusd"],
                    "new_cost_budget")
            known_cost += cost
            input_total += input_tokens
            output_total += output_tokens
            common = {"group_id": current_group,
                      "request_sha256": row["wire_sha256"],
                      "attempt_sha256": attempt_sha}
            _append(output / "response-ids.jsonl", {
                **common, "raw_json": raw_json, "model": MODEL})
            _append(output / "usage-receipts.jsonl", {
                **common, "finish_reason": "STOP", "input_tokens": input_tokens,
                "output_tokens": output_tokens, "model": MODEL})
            current_group = None
    except (Exception, asyncio.CancelledError) as exc:
        reason = _failure_code(exc)
        stopped = {"status": "stopped_no_retry", "split": admitted["split"],
                   "reason": reason, "attempts_claimed": attempts,
                   "last_claimed_group": current_group,
                   "known_cost_microusd": known_cost,
                   "failed_attempt_cost_unknown": current_group is not None or unknown_attempts > 0}
        _write_exclusive(output / "run-stop.json", stopped)
        return stopped
    claim_manifest_sha = _verify_complete_claims(admitted, ledger, scope, output)
    files = {name: digest((output / name).read_bytes()) for name in scorer.RECEIPT_FILES}
    evaluation = {
        "schema_version": scorer.EVALUATION_SCHEMA, "split": admitted["split"],
        "freeze_sha256": admitted["freeze_sha256"],
        "packet_sha256": admitted["packet_sha256"],
        "labels_sha256": admitted["labels_sha256"],
        "candidate_version": scorer.SOURCE_ID_CANDIDATE_VERSION,
        "prototype_sha256": admitted["source_sha256"]["prototype"],
        "parser_sha256": admitted["source_sha256"]["parser"],
        "scorer_sha256": admitted["source_sha256"]["scorer"],
        "model": MODEL, "thinking": THINKING, "automatic_retries": 0,
        "files": files,
    }
    _write_exclusive(output / "evaluation.json", evaluation)
    complete = {"status": "complete_one_shot", "split": admitted["split"],
                "authorization_id": AUTHORIZATION_ID,
                "approval_receipt_sha256": approval["_receipt_sha256"],
                "ledger_scope_sha256": scope,
                "claim_manifest_sha256": claim_manifest_sha,
                "attempts_claimed": attempts, "known_cost_microusd": known_cost,
                "reported_input_tokens": input_total,
                "reported_output_tokens": output_total,
                "evaluation_sha256": digest(canonical_bytes(evaluation)),
                "body_manifest_sha256": admitted["body_manifest_sha256"]}
    _write_exclusive(output / "run-complete.json", complete)
    return complete


def _preflight_report(admitted: dict) -> dict:
    return {key: admitted[key] for key in (
        "split", "source_manifest_sha256", "overlap_diagnostic_sha256",
        "freeze_sha256", "packet_sha256", "labels_sha256",
        "body_manifest_sha256", "source_sha256", "calibration_score_sha256",
        "max_rest_request_bytes")}


def _source_judge_key() -> str:
    # Only the approved execute path imports settings. No credential is logged.
    from app.config import Settings
    key = Settings().rag_source_judge_api_key_value
    require(bool(key), "source_judge_key_unavailable")
    return key


async def _execute_http(admitted: dict, approval: dict, output: Path) -> dict:
    key = _source_judge_key()
    async with httpx.AsyncClient(follow_redirects=False, trust_env=False,
                                 timeout=approval["max_call_seconds"]) as client:
        async def send(body: dict) -> httpx.Response:
            async with client.stream(
                "POST", approval["endpoint"],
                headers={"x-goog-api-key": key,
                         "Content-Type": "application/json",
                         "Accept-Encoding": "identity"},
                content=canonical_bytes(body),
            ) as response:
                if response.status_code != 200:
                    # Error bodies may contain provider details; the numeric
                    # status is sufficient to decide fail/continue.
                    return httpx.Response(response.status_code, content=b"")
                chunks = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=2_048):
                    chunks.extend(chunk)
                    if len(chunks) > MAX_RESPONSE_BYTES:
                        raise PilotError("provider_response_oversize")
                return httpx.Response(response.status_code, content=bytes(chunks))
        return await run_split(admitted, approval, output, send)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-dir", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--overlap-diagnostic", type=Path, required=True)
    parser.add_argument("--split", choices=scorer.SPLITS, default="calibration")
    parser.add_argument("--calibration-results", type=Path)
    parser.add_argument("--approval-receipt", type=Path)
    parser.add_argument("--approval-sha256")
    parser.add_argument("--output-dir", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--preflight-only", action="store_true")
    modes.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        admitted = admit_public_packet(args.frozen_dir, args.source_manifest,
                                       args.overlap_diagnostic, args.split,
                                       args.calibration_results)
        if not args.preflight_only and not args.execute:
            print(json.dumps({"status": "preapproval_preflight_passed",
                              **_preflight_report(admitted)}, sort_keys=True))
            return 0
        require(args.approval_receipt is not None and
                args.approval_sha256 is not None,
                "separate_operator_approval_required")
        approval = validate_approval(args.approval_receipt,
                                     args.approval_sha256, admitted)
        if args.preflight_only:
            _source_judge_key()
            print(json.dumps({"status": "approval_preflight_passed",
                              **_preflight_report(admitted)}, sort_keys=True))
            return 0
        require(args.output_dir is not None and not args.output_dir.exists() and
                args.output_dir.resolve().is_relative_to(Path(gettempdir()).resolve()),
                "os_temp_output_required")
        result = asyncio.run(_execute_http(admitted, approval, args.output_dir))
        if result["status"] == "complete_one_shot":
            score = scorer.score_run(
                args.frozen_dir,
                args.output_dir if args.split == "calibration" else args.calibration_results,
                args.output_dir if args.split == "heldout" else None)
            _write_exclusive(args.output_dir / "score.json", score)
            result["calibration_passed"] = score["calibration_passed"] if args.split == "calibration" else None
            result["heldout_passed"] = score.get("heldout_passed") if args.split == "heldout" else None
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "complete_one_shot" else 2
    except (PilotError, freezer.FreezeError, scorer.ScoreError,
            OSError, ValueError, TypeError, KeyError) as exc:
        code = str(exc) if isinstance(exc, PilotError) else "preflight_or_score_rejected"
        print(json.dumps({"status": "pilot_rejected", "reason": code},
                         sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
