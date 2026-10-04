"""Prospective twelve-case source-ID dispatcher, restricted to synthetic mocks.

There is no credential, HTTP, database, Docker or real activation implementation
here. The CLI refuses execution. The explicit mock engine tests durable custody,
quotas, bounded callbacks, strict fresh guards and production response parsing.
A future approved host must additionally prove actual transport/SQL interfaces,
OS resource fences and display observations; mock receipts are never that proof.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Callable
from uuid import UUID, uuid4

import prepare_private_visual_trial_v7 as preparation

if str(preparation.BACKEND / "scripts") not in sys.path:
    sys.path.insert(0, str(preparation.BACKEND / "scripts"))
import private_visual_dispatch_guard_v7 as guard

SCHEMA = "private_visual_trial_v7_mock"
LIVE_AUTHORIZED = False
MODE = "synthetic_mock_only"
# Fresh receipts cannot prove a callback that was allowed to block for the
# entire startup window. The host must additionally bound each SQL statement
# and lock wait; this coroutine ceiling bounds the whole final callback.
MAX_CALLBACK_SECONDS = guard.MAX_FRESH_SECONDS
CALLER_PATH = "scripts/run_private_visual_trial_v7.py"
GUARD_PATH = "backend/scripts/private_visual_dispatch_guard_v7.py"


class TrialError(ValueError):
    """Content-free fixed refusal; no wrapped private exceptions are retained."""


def require(ok: bool, code: str):
    if not ok:
        raise TrialError(code)


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _utc_now():
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class BoundTrial:
    scope: guard.DispatchScope
    cases: tuple[guard.FrozenDispatchCase, ...] = field(repr=False)
    pins: tuple[guard.GuardPins, ...] = field(repr=False)


@dataclass(frozen=True, slots=True)
class GuardEnvelope:
    receipt_bytes: bytes = field(repr=False)
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class SuppliedHTTPResponse:
    status: int
    body: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class MockInterfaces:
    """Callbacks are synthetic test seams; they confer no production authority.

    before_dispatch(case, trial_id=..., dispatch_nonce=...) runs AFTER waits.
    post_selection(case, selected_ids, trial_id=..., dispatch_nonce=...) obtains
    another fresh guard. transport(endpoint, body, timeout_seconds=...) supplies
    bytes; the engine itself creates no HTTP client or reads any credential.
    """
    before_dispatch: Callable = field(repr=False)
    post_selection: Callable = field(repr=False)
    transport: Callable = field(repr=False)
    sleep: Callable = field(default=asyncio.sleep, repr=False)
    clock: Callable = field(default=_utc_now, repr=False)
    monotonic: Callable = field(default=time.monotonic, repr=False)
    mode: str = MODE


def binding_identity(bound: BoundTrial) -> str:
    """Hydrated index/offset/code bindings need their own prospective host pin."""
    require(type(bound) is BoundTrial and type(bound.cases) is tuple and type(bound.pins) is tuple
            and len(bound.cases) == len(bound.pins) == preparation.MAX_CALLS, "binding_invalid")
    return digest(preparation.canonical({"scope": bound.scope.identity(), "cases": [
        {"identity_sha256": guard._case_identity(case, bound.scope, pins),
         "guard_code_sha256": pins.guard_code_sha256, "code_sha256": dict(pins.code_sha256)}
        for case, pins in zip(bound.cases, bound.pins, strict=True)]}))


def _validate_bound(prepared: preparation.PreparedTrial, bound: BoundTrial, expected_sha: str):
    require(type(prepared) is preparation.PreparedTrial and len(prepared.cases) == preparation.MAX_CALLS
            and preparation.scorer.legacy._sha(expected_sha)
            and binding_identity(bound) == expected_sha, "binding_invalid")
    require(digest(preparation.canonical(bound.scope.identity())) == prepared.scope_sha256,
            "binding_scope_invalid")
    packet = json.loads(dict(prepared.artifacts)["requests"])
    by_case = {row["case_id"]: row for row in packet["cases"]}
    for frozen, case, pins in zip(prepared.cases, bound.cases, bound.pins, strict=True):
        require(case.case_id == frozen.case_id and case.request_bytes == frozen.request_bytes
            and pins.request_sha256 == frozen.request_sha256
            and pins.admission_sha256 == frozen.admission_sha256
            and pins.bridge_sha256 == prepared.bridge_sha256 and pins.runtime_sha256 == prepared.runtime_sha256
            and preparation.scorer.admission_packet(case.snapshot) == by_case[case.case_id]["admission_snapshot"]
            and case.preceding_question == by_case[case.case_id]["preceding_question"], "binding_case_invalid")
        code = dict(pins.code_sha256)
        require(all(code.get(name) == value for name, value in prepared.code_sha256)
            and CALLER_PATH in code and GUARD_PATH in code
            and code[GUARD_PATH] == pins.guard_code_sha256, "binding_code_invalid")
        guard.verify_code_pins(pins)
        envelope = json.loads(case.request_bytes)
        wire_question = json.loads(envelope["contents"][0]["parts"][0]["text"])["question"]
        require(case.question == wire_question, "binding_question_invalid")
        sources = json.loads(frozen.sources_bytes)
        for ordinal, (source, candidate) in enumerate(zip(sources, case.candidates, strict=True)):
            wire = json.loads(envelope["contents"][0]["parts"][1 + 2 * ordinal]["text"])
            expected = {"id": candidate.id, "document_id": str(candidate.document_id),
                "content_revision_id": str(candidate.content_revision_id), "page_number": candidate.page_number,
                "pdf_sha256": candidate.pdf_sha256, "cue_sha256": candidate.cue_sha256,
                "png_sha256": candidate.png_sha256, "page_text_sha256": candidate.page_text_sha256}
            require(all(source[key] == value for key, value in expected.items())
                and type(candidate.index_revision_id) is UUID and candidate.index_revision_id.int > 0
                and type(candidate.start_offset) is int and type(candidate.end_offset) is int
                and candidate.start_offset == wire["cue_start"] and candidate.end_offset == wire["cue_end"],
                "binding_source_invalid")


class OneUseLedger:
    """Exclusive append-only mock receipts; a claim survives error/interruption.

    The future host must create an owner-private directory first. No arbitrary
    input file is read. This component never removes or reuses existing claims.
    """
    def __init__(self, directory: Path):
        require(type(directory) is Path or isinstance(directory, Path), "ledger_directory_invalid")
        require(directory.is_absolute() and directory.is_dir() and not directory.is_symlink()
                and not getattr(directory, "is_junction", lambda: False)() and directory.resolve() == directory,
                "ledger_directory_invalid")
        self.directory = directory
        self.claimed = False
        self._written: set[str] = set()

    def _write(self, name: str, value: dict):
        require(self.directory.is_dir() and not self.directory.is_symlink()
                and not getattr(self.directory, "is_junction", lambda: False)()
                and self.directory.resolve() == self.directory,
                "ledger_directory_invalid")
        raw = preparation.canonical(value)
        require(0 < len(raw) <= 64 * 1024 and name not in self._written, "ledger_receipt_invalid")
        try:
            with (self.directory / name).open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            raise TrialError("ledger_already_consumed") from None
        except OSError:
            raise TrialError("ledger_write_failed") from None
        self._written.add(name)

    def claim(self, value: dict):
        require(not self.claimed, "ledger_already_consumed")
        self._write("claim.json", value)
        self.claimed = True

    def write(self, name: str, value: dict):
        require(self.claimed and (name == "summary.json" or name in {
            f"{case}-{suffix}.json" for case in preparation.CASE_IDS for suffix in ("intent", "result")}),
            "ledger_receipt_invalid")
        self._write(name, value)


def _usage(raw: bytes) -> dict:
    """Retain known token charges even when the later strict verdict is invalid."""
    from app.ai.providers.source_visual import parse_http_response
    response = parse_http_response(raw)
    inp = response.input_tokens
    out = response.candidate_tokens + response.thinking_tokens
    micro = Decimal(inp) * preparation.INPUT_PRICE_USD_PER_MILLION + Decimal(out) * preparation.OUTPUT_PRICE_USD_PER_MILLION
    return {"input_tokens": inp, "output_tokens_including_thinking": out,
        "known_guard_cost_microusd": int(micro.to_integral_value(rounding=ROUND_CEILING)),
        "usage_cost_unknown": False}


def _receipt(envelope, *, prepared, bound, case, pins, interfaces, trial_id, nonce, selected=None):
    require(type(envelope) is GuardEnvelope, "guard_callback_invalid")
    return guard.require_dispatch_receipt_binding(envelope.receipt_bytes,
        receipt_sha256=envelope.receipt_sha256, now=interfaces.clock(), trial_id=trial_id,
        dispatch_nonce=nonce, scope=bound.scope, case=case, pins=pins, selected_ids=selected)


def _elapsed(interfaces, began: float):
    current = interfaces.monotonic()
    require(type(current) in (float, int) and math.isfinite(current) and current >= began,
            "clock_invalid")
    require(current - began <= preparation.MAX_TOTAL_SECONDS, "trial_deadline")
    return current


async def run_mock_trial(
    prepared: preparation.PreparedTrial, bound: BoundTrial, *, binding_sha256: str,
    interfaces: MockInterfaces, ledger: OneUseLedger, trial_id: UUID | None = None,
) -> dict:
    """Run only supplied synthetic interfaces, with no production/release credit."""
    require(type(interfaces) is MockInterfaces and interfaces.mode == MODE and LIVE_AUTHORIZED is False,
            "live_dispatch_unimplemented")
    trial_id = uuid4() if trial_id is None else trial_id
    require(type(trial_id) is UUID and trial_id.version == 4, "trial_identity_invalid")
    began = interfaces.monotonic()
    require(type(began) in (float, int) and math.isfinite(began), "clock_invalid")
    _validate_bound(prepared, bound, binding_sha256)
    require(_elapsed(interfaces, began) - began <= preparation.MAX_STARTUP_SECONDS, "startup_deadline")
    preflight_sha = preparation.report(prepared)["preflight_identity_sha256"]
    ledger.claim({"schema": SCHEMA + "_claim", "mode": MODE, "trial_id": str(trial_id),
        "preflight_identity_sha256": preflight_sha, "binding_sha256": binding_sha256,
        "live_authorized": False, "guards": preparation.guards()})
    result = {"schema": SCHEMA, "mode": MODE, "trial_id": str(trial_id), "status": "running",
        "live_authorized": False, "provider_calls": 0, "mock_transport_calls": 0,
        "embedding_calls": 0, "answer_calls": 0, "verifier_calls": 0, "automatic_retries": 0,
        "case_denominator": 12, "completed_cases": 0, "known_guard_cost_microusd": 0,
        "usage_unknown_attempts": 0, "reserved_input_tokens": 0, "reserved_output_tokens": 0,
        "reserved_cost_usd": "0", "physical_execution_proved": False,
        "actual_display_integrity_proved": False, "release_gate_passed": False}
    last_start = None
    reserved = Decimal(0)
    per_call = (Decimal(preparation.MAX_INPUT_TOKENS) * preparation.INPUT_PRICE_USD_PER_MILLION
        + Decimal(preparation.MAX_OUTPUT_TOKENS) * preparation.OUTPUT_PRICE_USD_PER_MILLION) / 1_000_000
    current_row = None
    failure = None
    phase = "startup"
    try:
        async with asyncio.timeout(preparation.MAX_TOTAL_SECONDS):
            for frozen, case, pins in zip(prepared.cases, bound.cases, bound.pins, strict=True):
                phase = "quota_wait"
                now = _elapsed(interfaces, began)
                if last_start is not None:
                    await interfaces.sleep(max(0, preparation.MIN_CALL_INTERVAL_SECONDS - (now - last_start)))
                now = _elapsed(interfaces, began)
                require(last_start is None or now - last_start >= preparation.MIN_CALL_INTERVAL_SECONDS,
                        "quota_wait_incomplete")
                nonce = uuid4()
                request = json.loads(frozen.request_bytes)
                body = preparation.canonical({key: value for key, value in request.items() if key != "model"})
                require(digest(body) == frozen.body_sha256, "request_body_changed")
                current_row = {"schema": SCHEMA + "_request_receipt", "mode": MODE,
                    "case_id": case.case_id, "request_sha256": frozen.request_sha256,
                    "body_sha256": frozen.body_sha256, "trial_id": str(trial_id), "dispatch_nonce": str(nonce),
                    "mock_transport_attempted": False, "http_status": None, "selected_ids": [],
                    "input_tokens": None, "output_tokens_including_thinking": None,
                    "known_guard_cost_microusd": None, "usage_cost_unknown": False,
                    "physical_execution_proved": False, "actual_display_integrity_proved": False}
                phase = "before_dispatch"
                async with asyncio.timeout(MAX_CALLBACK_SECONDS):
                    dispatch_guard = await interfaces.before_dispatch(case, trial_id=trial_id, dispatch_nonce=nonce)
                _receipt(dispatch_guard, prepared=prepared, bound=bound, case=case, pins=pins,
                         interfaces=interfaces, trial_id=trial_id, nonce=nonce)
                require(reserved + per_call <= preparation.MAX_COST_USD, "cost_reservation_failed")
                reserved += per_call
                result["reserved_input_tokens"] += preparation.MAX_INPUT_TOKENS
                result["reserved_output_tokens"] += preparation.MAX_OUTPUT_TOKENS
                result["reserved_cost_usd"] = str(reserved)
                intent = {**current_row, "guard_sha256": dispatch_guard.receipt_sha256,
                    "reserved_input_tokens": preparation.MAX_INPUT_TOKENS,
                    "reserved_output_tokens": preparation.MAX_OUTPUT_TOKENS,
                    "reserved_cost_usd": str(per_call), "status": "dispatch_intent"}
                ledger.write(case.case_id + "-intent.json", intent)
                # fsync/quota/guard time is accounted before the final freshness check.
                _receipt(dispatch_guard, prepared=prepared, bound=bound, case=case, pins=pins,
                         interfaces=interfaces, trial_id=trial_id, nonce=nonce)
                last_start = _elapsed(interfaces, began)
                current_row.update(mock_transport_attempted=True, usage_cost_unknown=True)
                result["mock_transport_calls"] += 1
                phase = "transport"
                async with asyncio.timeout(preparation.MAX_CALL_SECONDS):
                    response = await interfaces.transport(preparation.ENDPOINT, body,
                        timeout_seconds=preparation.MAX_CALL_SECONDS)
                require(type(response) is SuppliedHTTPResponse and type(response.status) is int
                    and 100 <= response.status <= 599, "transport_response_invalid")
                current_row["http_status"] = response.status
                require(response.status == 200, "provider_http_failure")
                phase = "response"
                require(type(response.body) is bytes and 0 < len(response.body) <= preparation.MAX_HTTP_RESPONSE_BYTES,
                        "response_size_invalid")
                current_row.update(_usage(response.body))
                projection = preparation.parse_supplied_response(frozen, response.body)
                current_row.update(selected_ids=projection["selected_ids"], question_status=projection["question_status"])
                selected = tuple(projection["selected_ids"])
                phase = "post_selection"
                async with asyncio.timeout(MAX_CALLBACK_SECONDS):
                    selected_guard = await interfaces.post_selection(case, selected,
                        trial_id=trial_id, dispatch_nonce=nonce)
                _receipt(selected_guard, prepared=prepared, bound=bound, case=case, pins=pins,
                         interfaces=interfaces, trial_id=trial_id, nonce=nonce, selected=selected)
                current_row.update(status="mock_completed", dispatch_guard_sha256=dispatch_guard.receipt_sha256,
                    post_selection_guard_sha256=selected_guard.receipt_sha256)
                ledger.write(case.case_id + "-result.json", current_row)
                result["completed_cases"] += 1
                result["known_guard_cost_microusd"] += current_row["known_guard_cost_microusd"]
                current_row = None
                _elapsed(interfaces, began)
        result["status"] = "mock_completed"
    except asyncio.CancelledError:
        failure = "cancelled"
    except TimeoutError:
        failure = phase + "_timeout"
    except (TrialError, preparation.Refusal, guard.DispatchGuardError, preparation.contract.VisualSourceJudgmentError):
        failure = phase + "_refused"
    except Exception:
        failure = phase + "_failed"
    if failure:
        result.update(status="stopped", failure_phase=phase, failure_code=failure)
        if current_row is not None:
            current_row.update(status="stopped", failure_code=failure)
            ledger.write(current_row["case_id"] + "-result.json", current_row)
            if current_row["known_guard_cost_microusd"] is not None:
                result["known_guard_cost_microusd"] += current_row["known_guard_cost_microusd"]
            elif current_row["mock_transport_attempted"]:
                result["usage_unknown_attempts"] += 1
    ledger.write("summary.json", result)
    if failure == "cancelled":
        raise asyncio.CancelledError
    return result


def score_supplied_measurement(prepared, measurement: bytes, *, measurement_sha256: str) -> dict:
    """No measurements/flags are invented from backend guard or mock receipts."""
    scored = preparation.score_supplied_measurement(prepared, measurement,
        measurement_sha256=measurement_sha256)
    return {"schema": SCHEMA + "_supplied_score", "supplied_measurement_score": scored,
        "physical_execution_proved": False, "actual_display_integrity_proved": False,
        "release_gate_passed": False}


def main(argv=None):
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps({"schema": SCHEMA, "status": "live_dispatch_unimplemented" if args.execute else "unexecuted",
        "live_authorized": False, "provider_calls": 0, "database_reads": 0, "database_writes": 0,
        "release_gate_passed": False}))
    return 2 if args.execute else 0


if __name__ == "__main__":
    raise SystemExit(main())
