"""Dormant, one-shot public-only Gemini 3.6 source-ID transport diagnostic.

This is not a quality evaluation or application runtime. It uses one tiny
control excerpt and then the exact first frozen calibration slate, both built
from the hash-pinned public PDF packet. No credential is read until an exact
separate approval receipt passes. Set AUTHORIZATION_ID only after that approval;
the checked-in placeholder deliberately prevents live execution.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import re
import sys
from tempfile import gettempdir
import time
from typing import Awaitable, Callable

import httpx

from evaluate_source_id_multipdf import PACKET_SHA256, _split_requests, digest, write_exclusive
from finalize_public_source_id_multipdf import ReviewError, read_pinned
from run_public_source_id_multipdf import (
    PilotFailure, _canonical_json, _cost_microusd, _parse_provider_response,
    _rest_body, ensure,
)

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
from app.ai.source_judgment import build_source_id_request, canonical_bytes  # noqa: E402


MODEL = "gemini-3.6-flash"
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent"
APPROVAL_SCHEMA = "cardchemy_public_source_id_36_diagnostic_approval_v1"
AUTHORIZATION_ID = "2026-09-29-public-source-id-36-diagnostic-call-CTklT8rwbybcYrRgm9X3j3v3"
FIRST_WIRE_SHA256 = "90771c64eac9e4db61dae2a50208d5ca13e7d0a01b7297892ab45949332da9d0"
CONTROL_WIRE_SHA256 = "c4b56c11bcafa965caf08cbfad954e0345a80ab49814a5aba2f3d03d9afc686f"
FIRST_BODY_SHA256 = "26653c55684abcd45615243ad59558cd16026e44d730e5698f15cf8c8755cd61"
CONTROL_BODY_SHA256 = "73f656301a0e495f9fc3d8a168dcd971a3bdf5b926580ce22cda5436e0453948"
MAX_CALLS = 2
MAX_INPUT_PER_CALL = 8192
MAX_OUTPUT_PER_CALL = 1024
MAX_INPUT_TOTAL = 16384
MAX_OUTPUT_TOTAL = 2048
MAX_COST_MICROUSD = 40_000
MAX_CALL_SECONDS = 30
MAX_TOTAL_SECONDS = 120
MIN_START_INTERVAL_SECONDS = 6
INPUT_PRICE_USD_PER_MILLION = "1.50"
OUTPUT_PRICE_USD_PER_MILLION = "7.50"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_RETRY_AFTER_SECONDS = re.compile(r"[0-9]{1,4}\Z")


def public_requests(packet_dir: Path) -> tuple[dict, dict]:
    """Rebuild both exact wires from the pinned public packet, not caller data."""
    packet = read_pinned(packet_dir / "blind-review-packet.json", PACKET_SHA256, 1_000_000)
    first = _split_requests(packet, "calibration")[0]
    ensure(first["status"] == "callable" and
           first["wire_sha256"] == FIRST_WIRE_SHA256,
           "first_public_slate_mismatch")
    slate = first["wire"]
    candidate = slate["user_payload"]["candidates"][0]
    cue = candidate["cue"]
    control = build_source_id_request(
        "Which lecture page contains this public excerpt?",
        [{"id": candidate["id"], "page": candidate["page"],
          "page_text": cue, "cue": cue}],
    )
    ensure(digest(canonical_bytes(control)) == CONTROL_WIRE_SHA256,
           "control_public_wire_mismatch")
    control_body = _rest_body(control)
    slate_body = _rest_body(slate)
    ensure(digest(canonical_bytes(control_body)) == CONTROL_BODY_SHA256 and
           digest(canonical_bytes(slate_body)) == FIRST_BODY_SHA256,
           "public_body_mismatch")
    return control, slate


def validate_approval(path: Path, approval_sha256: str) -> dict:
    """Require a unique operator receipt bound to this exact two-call envelope."""
    ensure(AUTHORIZATION_ID != "PENDING_SEPARATE_OPERATOR_APPROVAL",
           "separate_operator_approval_required")
    ensure(type(approval_sha256) is str and _HEX64.fullmatch(approval_sha256),
           "approval_hash_required")
    approval = _canonical_json(path, 4096)
    ensure(digest(path.read_bytes()) == approval_sha256 and
           set(approval) == {
               "schema", "authorization_id", "operator_approved",
               "previous_failed_cost_unknown", "endpoint", "model",
               "source_packet_sha256", "control_body_sha256",
               "first_slate_body_sha256", "max_calls", "max_input_tokens_per_call",
               "max_output_tokens_per_call", "max_input_tokens_total",
               "max_output_tokens_total", "max_cost_microusd",
               "input_price_usd_per_million", "output_price_usd_per_million",
               "max_call_seconds", "max_total_seconds",
               "min_start_interval_seconds",
           } and
           approval["schema"] == APPROVAL_SCHEMA and
           approval["authorization_id"] == AUTHORIZATION_ID and
           approval["operator_approved"] is True and
           approval["previous_failed_cost_unknown"] is True and
           approval["endpoint"] == ENDPOINT and approval["model"] == MODEL and
           approval["source_packet_sha256"] == PACKET_SHA256 and
           approval["control_body_sha256"] == CONTROL_BODY_SHA256 and
           approval["first_slate_body_sha256"] == FIRST_BODY_SHA256 and
           approval["max_calls"] == MAX_CALLS and
           approval["max_input_tokens_per_call"] == MAX_INPUT_PER_CALL and
           approval["max_output_tokens_per_call"] == MAX_OUTPUT_PER_CALL and
           approval["max_input_tokens_total"] == MAX_INPUT_TOTAL and
           approval["max_output_tokens_total"] == MAX_OUTPUT_TOTAL and
           approval["max_cost_microusd"] == MAX_COST_MICROUSD and
           approval["input_price_usd_per_million"] == INPUT_PRICE_USD_PER_MILLION and
           approval["output_price_usd_per_million"] == OUTPUT_PRICE_USD_PER_MILLION and
           approval["max_call_seconds"] == MAX_CALL_SECONDS and
           approval["max_total_seconds"] == MAX_TOTAL_SECONDS and
           approval["min_start_interval_seconds"] == MIN_START_INTERVAL_SECONDS,
           "approval_envelope_mismatch")
    ensure(MAX_CALLS * _cost_microusd(MAX_INPUT_PER_CALL, MAX_OUTPUT_PER_CALL)
           <= MAX_COST_MICROUSD, "approval_cost_math_invalid")
    return approval


def approval_claim_path(approval_sha256: str) -> Path:
    ensure(type(approval_sha256) is str and _HEX64.fullmatch(approval_sha256),
           "approval_hash_required")
    directory = Path(gettempdir()).resolve() / "cardchemy-source-id-36-diagnostic-ledger"
    directory.mkdir(mode=0o777 if os.name == "nt" else 0o700, exist_ok=True)
    ensure(directory.is_dir() and not directory.is_symlink(),
           "approval_ledger_unavailable")
    return directory / f"approval-{approval_sha256}.claim"


async def http_call(client: httpx.AsyncClient, api_key: str,
                    wire: dict) -> httpx.Response:
    return await client.post(
        ENDPOINT,
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json=_rest_body(wire),
    )


async def run_once(
    wires: tuple[dict, dict], output: Path,
    transport: Callable[[dict], Awaitable[httpx.Response]],
    *, approval_sha256: str, claim_path: Path,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> dict:
    ensure(output.is_dir() and not output.is_symlink() and
           not any(output.iterdir()) and claim_path.is_absolute() and
           claim_path.parent.is_dir() and not claim_path.parent.is_symlink() and
           MAX_CALLS * _cost_microusd(MAX_INPUT_PER_CALL, MAX_OUTPUT_PER_CALL)
           <= MAX_COST_MICROUSD, "run_preflight_invalid")
    for wire, expected in zip(wires, (CONTROL_BODY_SHA256, FIRST_BODY_SHA256)):
        ensure(digest(canonical_bytes(_rest_body(wire))) == expected,
               "run_body_mismatch")
    write_exclusive(claim_path, {"approval_sha256": approval_sha256})
    write_exclusive(output / "run.claim", {"approval_sha256": approval_sha256})
    rows: list[dict] = []
    spent = 0
    input_total = 0
    output_total = 0
    start = clock()
    deadline = start + MAX_TOTAL_SECONDS
    previous_start: float | None = None
    for index, wire in enumerate(wires, start=1):
        if previous_start is not None:
            pause = MIN_START_INTERVAL_SECONDS - (clock() - previous_start)
            if pause > 0:
                # A second request cannot start if the mandatory spacing
                # would itself consume the remaining global allowance.
                if pause >= deadline - clock():
                    break
                await sleeper(pause)
        if clock() >= deadline:
            break
        remaining = MAX_CALLS - index + 1
        if spent + remaining * _cost_microusd(
            MAX_INPUT_PER_CALL, MAX_OUTPUT_PER_CALL) > MAX_COST_MICROUSD or \
           input_total + remaining * MAX_INPUT_PER_CALL > MAX_INPUT_TOTAL or \
           output_total + remaining * MAX_OUTPUT_PER_CALL > MAX_OUTPUT_TOTAL:
            break
        write_exclusive(output / f"call-{index:02d}.claim", {"step": index})
        previous_start = clock()
        remaining_seconds = deadline - previous_start
        if remaining_seconds <= 0:
            break
        row: dict = {"step": index, "http_status": None,
                     "elapsed_ms": 0, "response_bytes": None,
                     "retry_after_seconds": None,
                     "input_tokens": None, "output_tokens": None,
                     "validated": False}
        try:
            response = await asyncio.wait_for(
                transport(wire),
                timeout=min(MAX_CALL_SECONDS, remaining_seconds),
            )
            row["elapsed_ms"] = max(0, int((clock() - previous_start) * 1000))
            row["http_status"] = response.status_code
            row["response_bytes"] = len(response.content)
            retry_after = response.headers.get("retry-after", "")
            if _RETRY_AFTER_SECONDS.fullmatch(retry_after):
                seconds = int(retry_after)
                if seconds <= 3600:
                    row["retry_after_seconds"] = seconds
            ids = [candidate["id"] for candidate in
                   wire["user_payload"]["candidates"]]
            # Discard selected IDs and raw model text. Only strict validation
            # and numeric usage determine whether the second call can start.
            _, input_tokens, output_tokens = _parse_provider_response(response, ids)
            cost = _cost_microusd(input_tokens, output_tokens)
            if spent + cost > MAX_COST_MICROUSD or \
               input_total + input_tokens > MAX_INPUT_TOTAL or \
               output_total + output_tokens > MAX_OUTPUT_TOTAL:
                raise PilotFailure("observed_budget_exceeded")
            row["input_tokens"] = input_tokens
            row["output_tokens"] = output_tokens
            row["validated"] = True
            spent += cost
            input_total += input_tokens
            output_total += output_tokens
        except (Exception, asyncio.CancelledError):
            row["elapsed_ms"] = max(0, int((clock() - previous_start) * 1000))
            rows.append(row)
            break
        rows.append(row)
        if clock() >= deadline:
            break
    result = {"attempts": len(rows), "complete": len(rows) == MAX_CALLS and
              all(row["validated"] for row in rows),
              "known_cost_microusd": spent,
              "failed_attempt_cost_unknown": any(not row["validated"] for row in rows),
              "calls": rows}
    write_exclusive(output / "diagnostic-result.json", result)
    return result


async def _live(args: argparse.Namespace) -> dict:
    temp = Path(gettempdir()).resolve()
    for path in (args.packet_dir, args.approval_receipt, args.output_dir):
        ensure(path.is_absolute() and temp in path.resolve().parents,
               "os_temp_path_required")
    ensure(args.output_dir.is_dir() and not args.output_dir.is_symlink(),
           "os_temp_output_required")
    wires = public_requests(args.packet_dir)
    validate_approval(args.approval_receipt, args.approval_sha256)
    # Source and approval must validate before the local credential is read.
    from app.config import Settings
    api_key = Settings().rag_ai_api_key_value
    ensure(bool(api_key), "provider_key_unavailable")
    async with httpx.AsyncClient(timeout=MAX_CALL_SECONDS,
                                 follow_redirects=False) as client:
        return await run_once(
            wires, args.output_dir, lambda wire: http_call(client, api_key, wire),
            approval_sha256=args.approval_sha256,
            claim_path=approval_claim_path(args.approval_sha256),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet-dir", type=Path, required=True)
    parser.add_argument("--approval-receipt", type=Path, required=True)
    parser.add_argument("--approval-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = asyncio.run(_live(args))
        print(json.dumps(result, sort_keys=True))
        return 0 if result["complete"] else 2
    except (PilotFailure, ReviewError, OSError, ValueError, KeyError, TypeError) as exc:
        reason = str(exc) if isinstance(exc, PilotFailure) else type(exc).__name__
        print(json.dumps({"status": "diagnostic_rejected", "reason": reason,
                          "execution_uncertain": (args.output_dir / "run.claim").exists()},
                         sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
