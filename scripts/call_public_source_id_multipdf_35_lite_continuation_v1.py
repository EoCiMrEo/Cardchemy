"""Separately gated HTTP adapter for the public Flash-Lite continuation.

This is an evaluation-only entry point, never an Ask AI application worker.
Its preapproval mode reads frozen public inputs without a key or provider call.
The approved modes remain inert while the continuation authorization ID is
pending. No earlier claim or timed-out group can be replayed by this caller.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import re
import sys
from tempfile import gettempdir

import httpx

import continue_public_source_id_multipdf_35_lite_v1 as continuation
from finalize_public_source_id_multipdf import ReviewError
from run_public_source_id_multipdf_35_lite import (
    ENDPOINT, MAX_HTTP_RESPONSE_BYTES, PilotFailure, _probe_writable_directory,
    _rest_body,
)
from prepare_public_source_id_multipdf import canonical_bytes

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

_SAFE_CODE = re.compile(r"[a-z][a-z0-9_]{0,79}\Z")


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PilotFailure(code)


def _output_preflight(output: Path, prior_dir: Path, packet_dir: Path,
                      labels_path: Path, old_approval_path: Path) -> None:
    """Check the future output/claim location without creating either claim."""
    temp = Path(gettempdir()).resolve()
    _require(output.is_absolute() and not output.exists() and
             output.parent.is_dir() and not output.parent.is_symlink() and
             temp in output.resolve().parents and
             all(path.resolve() not in output.resolve().parents and
                 output.resolve() != path.resolve()
                 for path in (prior_dir, packet_dir, labels_path.parent,
                              old_approval_path.parent,
                              temp / "cardchemy-source-id-35-lite-pilot-ledger")),
             "os_temp_output_required")
    _probe_writable_directory(output.parent)


def _admit(args: argparse.Namespace, *, approved: bool) -> dict:
    """Always pin the old public run before any key, network or new claim."""
    prepared, receipt, checkpoint = continuation.validate_prior(
        args.prior_dir, args.packet_dir, args.labels_path,
        args.old_approval_path)
    _output_preflight(args.output, args.prior_dir, args.packet_dir,
                      args.labels_path, args.old_approval_path)
    if approved:
        _require(args.new_approval_path is not None and
                 args.new_approval_sha256 is not None,
                 "separate_operator_approval_required")
        continuation.validate_approval(
            args.new_approval_path, args.new_approval_sha256, checkpoint)
        claim = continuation._approval_claim_path(
            continuation.digest(canonical_bytes(checkpoint)))
        _probe_writable_directory(claim.parent)
        _require(not claim.exists() and not claim.is_symlink(),
                 "continuation_claim_consumed")
    else:
        _require(args.new_approval_path is None and
                 args.new_approval_sha256 is None,
                 "preapproval_arguments_invalid")
    # Never include source text, candidate IDs or the credential in output.
    return {
        "status": ("approved_preflight_passed" if approved else
                   "preapproval_preflight_passed"),
        "authorization_pending": not approved,
        "prior_accepted_groups": checkpoint["prior_accepted_groups"],
        "prior_uncertain_group_number": checkpoint[
            "prior_uncertain_group_number"],
        "new_calibration_calls_max": 37,
        "new_heldout_calls_max": 48,
        "source_packet_sha256": checkpoint["source_packet_sha256"],
        "frozen_request_count": len(prepared["requests"]),
        "frozen_prepare_receipt_sha256": continuation.digest(
            canonical_bytes(receipt)),
    }


def _source_judge_key() -> str:
    """Read only the dedicated source judge key after exact admission."""
    from app.config import Settings
    try:
        key = Settings().rag_source_judge_api_key_value
    except Exception as exc:
        raise PilotFailure("provider_key_unavailable") from exc
    _require(bool(key), "provider_key_unavailable")
    return key


async def _post_public_wire(client: httpx.AsyncClient, key: str,
                            wire: dict) -> httpx.Response:
    """One POST, no redirect/retry, and bounded decoded success bytes."""
    body = canonical_bytes(_rest_body(wire))
    async with client.stream(
        "POST", ENDPOINT,
        headers={"x-goog-api-key": key,
                 "Content-Type": "application/json",
                 "Accept-Encoding": "identity"},
        content=body,
    ) as response:
        # Error bodies may echo source text. Preserve only numeric status.
        if response.status_code != 200:
            return httpx.Response(response.status_code, request=response.request,
                                  content=b"")
        chunks: list[bytes] = []
        total = 0
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > MAX_HTTP_RESPONSE_BYTES:
                raise PilotFailure("provider_response_oversize")
            chunks.append(chunk)
        return httpx.Response(response.status_code,
                              request=response.request,
                              content=b"".join(chunks))


async def _execute(args: argparse.Namespace) -> dict:
    _require(args.ack_live is True, "explicit_live_execution_required")
    _admit(args, approved=True)
    key = _source_judge_key()
    # Core owns the durable one-use claim, 20-second pacing, 90-second total
    # per-call wait, 180-minute wall budget, failure accounting and scoring.
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(continuation.MAX_CALL_SECONDS),
        follow_redirects=False,
    ) as client:
        return await continuation.run_with_transport(
            args.prior_dir, args.packet_dir, args.labels_path,
            args.old_approval_path, args.new_approval_path,
            args.new_approval_sha256, args.output,
            lambda wire: _post_public_wire(client, key, wire),
        )


def _safe_reason(exc: BaseException) -> str:
    if isinstance(exc, (PilotFailure, ReviewError)) and exc.args:
        code = exc.args[0]
        if type(code) is str and _SAFE_CODE.fullmatch(code):
            return code
    return "local_preflight_rejected"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior-dir", required=True, type=Path)
    parser.add_argument("--packet-dir", required=True, type=Path)
    parser.add_argument("--labels-path", required=True, type=Path)
    parser.add_argument("--old-approval-path", required=True, type=Path)
    parser.add_argument("--new-approval-path", type=Path)
    parser.add_argument("--new-approval-sha256")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ack-live", action="store_true",
                        help="required only with --execute after exact approval")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preapproval-preflight", action="store_true")
    modes.add_argument("--approved-preflight", action="store_true")
    modes.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        _require(args.ack_live is args.execute, "execution_flag_invalid")
        if args.preapproval_preflight:
            result = _admit(args, approved=False)
        elif args.approved_preflight:
            result = _admit(args, approved=True)
            _source_judge_key()
            result["source_judge_key_present"] = True
        else:
            result = asyncio.run(_execute(args))
        print(json.dumps(result, sort_keys=True))
        passed = result.get("status") in {
            "preapproval_preflight_passed", "approved_preflight_passed",
        } or (result.get("status") == "public_pilot_complete" and
              result.get("heldout_passed") is True)
        return 0 if passed else 2
    except (PilotFailure, ReviewError, OSError, ValueError, TypeError,
            KeyError) as exc:
        print(json.dumps({"status": "pilot_rejected",
                          "reason": _safe_reason(exc)}, sort_keys=True),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
