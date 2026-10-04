"""Prospective private12 source-ID controller; default and CLI remain inert.

A separately approved host owns private-transfer authority, the fresh approval
SHA, isolated resources and a RAM-only key delivered through explicit stdin.
This module neither loads that key nor constructs Settings. Callback receipts
prove current backend association, never actual browser display/usefulness.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from typing import Callable
from uuid import UUID, uuid4

REPO = Path(__file__).resolve().parents[2]
if Path("/app/app/__init__.py").is_file():
    sys.path.insert(0, "/app")
    import app  # noqa: F401 - execute the complete immutable image package
sys.path.insert(0, str(REPO / "scripts"))
import prepare_private_visual_trial_v8 as preparation
import run_private_visual_trial_v8 as custody
import private_visual_dispatch_guard_v8 as guard
import rehearse_private_visual_dispatch_v8 as rehearsal

SCHEMA = "private_visual_trial_v8_execution"
APPROVAL_SCHEMA = SCHEMA + "_approval"
LIVE_AUTHORIZED = False
EXECUTOR_PATH = "backend/scripts/execute_private_visual_trial_v8.py"
REHEARSAL_PATH = "backend/scripts/rehearse_private_visual_dispatch_v8.py"
MAX_GUARD_SECONDS = 5
MAX_ANCHOR_SECONDS = 10
MAX_RENDER_SECONDS = 30
SQL_TIMEOUT_MS = 5000
LOCK_TIMEOUT_MS = 1000
IDLE_TIMEOUT_MS = 15000


class ExecutionError(ValueError):
    """Only fixed codes; private/transport exception details stay excluded."""


def require(value: bool, code: str):
    if not value:
        raise ExecutionError(code)


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _now():
    return datetime.now(timezone.utc)


def _utc(value):
    return isinstance(value, datetime) and value.utcoffset() == timedelta(0)


def approval_payload(prepared, bound, *, trial_id: UUID, authorization_id: str,
                     approved_at: datetime, expires_at: datetime) -> bytes:
    """Format a prospective host approval; this grants no authority by itself."""
    require(type(trial_id) is UUID and trial_id.version == 4
        and type(authorization_id) is str and re.fullmatch(r"[a-zA-Z0-9_-]{8,160}", authorization_id)
        and _utc(approved_at) and _utc(expires_at)
        and timedelta(0) < expires_at - approved_at <= timedelta(days=1), "approval_identity_invalid")
    return preparation.canonical({"schema": APPROVAL_SCHEMA, "trial_id": str(trial_id),
        "authorization_id": authorization_id, "approved_at_utc": approved_at.isoformat(),
        "expires_at_utc": expires_at.isoformat(), "one_use": True,
        "private_transfer_approved": True, "provider_envelope_approved": True,
        "preflight_identity_sha256": preparation.report(prepared)["preflight_identity_sha256"],
        "binding_sha256": custody.binding_identity(bound),
        "executor_sha256": digest(Path(__file__).read_bytes()), "guards": preparation.guards()})


def _approval(raw: bytes, external_sha: str, *, prepared, bound, now: datetime) -> dict:
    require(LIVE_AUTHORIZED is True, "private_execution_not_authorized")
    require(type(raw) is bytes and 0 < len(raw) <= 32 * 1024
        and preparation.scorer.legacy._sha(external_sha) and digest(raw) == external_sha,
        "approval_unbound")
    try:
        value = json.loads(raw, object_pairs_hook=preparation.contract._unique,
            parse_constant=preparation.contract._reject_constant)
        require(type(value) is dict and preparation.canonical(value) == raw, "approval_invalid")
        expected = approval_payload(prepared, bound, trial_id=UUID(value["trial_id"]),
            authorization_id=value["authorization_id"],
            approved_at=datetime.fromisoformat(value["approved_at_utc"]),
            expires_at=datetime.fromisoformat(value["expires_at_utc"]))
        require(raw == expected and _utc(now)
            and datetime.fromisoformat(value["approved_at_utc"]) <= now < datetime.fromisoformat(value["expires_at_utc"]),
            "approval_invalid")
    except ExecutionError:
        raise
    except Exception:
        raise ExecutionError("approval_invalid") from None
    custody._validate_bound(prepared, bound, value["binding_sha256"])
    require(all(pins.code_sha256.get(EXECUTOR_PATH) == value["executor_sha256"]
        and REHEARSAL_PATH in pins.code_sha256 for pins in bound.pins), "executor_code_unbound")
    return value


class TrialLedger:
    """Append-only private receipts. A durable claim is never removed/replayed."""
    def __init__(self, directory: Path):
        self.directory, self.claimed, self.names = directory, False, set()
        self._directory()

    def _directory(self):
        require(isinstance(self.directory, Path) and self.directory.is_absolute()
            and self.directory.is_dir() and not self.directory.is_symlink()
            and not getattr(self.directory, "is_junction", lambda: False)()
            and self.directory.resolve() == self.directory, "ledger_directory_invalid")

    def write(self, name: str, value: dict):
        self._directory()
        allowed = {"claim.json", "summary.json", *{f"{cid}-{kind}.json"
            for cid in preparation.CASE_IDS for kind in ("intent", "usage", "result", "dispatch-guard", "selected-guard")}}
        require(name in allowed and name not in self.names
            and (self.claimed or name == "claim.json"), "ledger_record_invalid")
        raw = preparation.canonical(value)
        require(0 < len(raw) <= 64 * 1024, "ledger_record_invalid")
        try:
            with (self.directory / name).open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            raise ExecutionError("ledger_already_consumed") from None
        except OSError:
            raise ExecutionError("ledger_write_failed") from None
        self.names.add(name)
        if name == "claim.json":
            self.claimed = True


@dataclass(frozen=True, slots=True)
class Interfaces:
    session_factory: Callable = field(repr=False)
    quota: Callable = field(repr=False)
    transport: Callable = field(repr=False)
    current_selections: Callable = field(default=rehearsal.current_selections, repr=False)
    render: Callable = field(default=guard.prepare_dispatch_proof_v8, repr=False)
    final: Callable = field(default=guard.verify_private_visual_dispatch_v8, repr=False)
    validate_receipt: Callable = field(default=guard.require_dispatch_receipt_binding, repr=False)
    close: Callable | None = field(default=None, repr=False)
    clock: Callable = field(default=_now, repr=False)
    monotonic: Callable = field(default=time.monotonic, repr=False)
    sleep: Callable = field(default=asyncio.sleep, repr=False)
    synthetic: bool = False


async def native_transport(endpoint, body, *, api_key, timeout_seconds):
    """Explicit RAM-only key, one streamed POST, no SDK/proxy/redirect/retry."""
    import httpx
    require(endpoint == preparation.ENDPOINT and type(body) is bytes
        and 0 < len(body) <= preparation.contract.MAX_REQUEST_BYTES
        and type(api_key) is str and 0 < len(api_key) <= 512
        and timeout_seconds == preparation.MAX_CALL_SECONDS, "transport_scope_invalid")
    async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(retries=0), trust_env=False,
        follow_redirects=False, timeout=timeout_seconds) as client:
        async with client.stream("POST", endpoint, content=body, headers={
            "x-goog-api-key": api_key, "Content-Type": "application/json", "Accept-Encoding": "identity"}) as response:
            # Error bodies may include provider/private diagnostics; do not read them.
            if response.status_code != 200:
                return custody.SuppliedHTTPResponse(response.status_code, b"")
            require(response.headers.get("Content-Encoding", "identity").lower() == "identity",
                "provider_encoding_invalid")
            raw = bytearray()
            async for chunk in response.aiter_bytes(chunk_size=2048):
                raw.extend(chunk)
                require(len(raw) <= preparation.MAX_HTTP_RESPONSE_BYTES, "provider_response_oversize")
            return custody.SuppliedHTTPResponse(200, bytes(raw))


def production_interfaces(settings) -> Interfaces:
    """Called only after approval; Settings has no provider key and is not built here."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool
    from app.ai.rate_limit import ProviderRateGovernor
    engine = create_async_engine(settings.database_url, echo=False, hide_parameters=True, poolclass=NullPool,
        connect_args={"server_settings": {"statement_timeout": str(SQL_TIMEOUT_MS),
            "lock_timeout": str(LOCK_TIMEOUT_MS), "idle_in_transaction_session_timeout": str(IDLE_TIMEOUT_MS)}})
    governor = ProviderRateGovernor(requests_per_minute=settings.rag_source_judge_requests_per_minute,
        input_tokens_per_minute=settings.rag_source_judge_input_tokens_per_minute,
        safety_percent=settings.rag_source_judge_rate_limit_safety_percent)
    async def quota():
        return await governor.reserve(preparation.MAX_INPUT_TOKENS, operation="source_judgment", attempt=0)
    return Interfaces(session_factory=async_sessionmaker(engine, expire_on_commit=False, autoflush=False),
        quota=quota, transport=native_transport, close=engine.dispose)


def _environment(settings, bound):
    from app.config import ROOT_DIR
    require(not (ROOT_DIR / ".env").exists() and not (REPO / ".env").exists()
        and not any(name.endswith("API_KEY") for name in os.environ), "runtime_not_keyless")
    guard._settings(settings, bound.scope)
    require(Path("/sys/fs/cgroup/memory.max").read_text().strip() == "2147483648"
        and Path("/sys/fs/cgroup/cpu.max").read_text().strip() == "400000 100000", "resource_fence_required")


def _elapsed(interfaces, began):
    now = interfaces.monotonic()
    require(type(now) in (float, int) and math.isfinite(now) and now >= began
        and now - began <= preparation.MAX_TOTAL_SECONDS, "trial_deadline")
    return now


def _approval_current(approval, clock):
    now = clock()
    require(_utc(now) and datetime.fromisoformat(approval["approved_at_utc"]) <= now
        < datetime.fromisoformat(approval["expires_at_utc"]), "approval_expired")


async def _transaction(interfaces, operation, seconds):
    async with interfaces.session_factory() as db:
        await db.begin()
        try:
            async with asyncio.timeout(seconds):
                return await operation(db)
        finally:
            await db.rollback()


def _receipt(receipt, *, interfaces, prepared, bound, case, pins, trial_id, nonce, selected=None):
    encoded = preparation.canonical(receipt)
    interfaces.validate_receipt(encoded, receipt_sha256=digest(encoded), now=interfaces.clock(),
        trial_id=trial_id, dispatch_nonce=nonce, scope=bound.scope, case=case, pins=pins, selected_ids=selected)
    return encoded


async def execute_private_trial_v8(prepared, bound, *, settings, api_key: str,
    approval_bytes: bytes, approval_sha256: str, ledger: TrialLedger,
    interfaces: Interfaces | None = None) -> dict:
    """One approved private12 trial, stopping on any error without automatic replay.

    A host must obtain a fresh explicit private-transfer/provider envelope and
    enforce the hard OS process-tree deadline. Supplying mock callbacks is an
    ENVIRONMENT=test-only seam and yields no physical/backend/release credit.
    """
    initial_clock = interfaces.clock if interfaces is not None else _now
    began = (interfaces.monotonic if interfaces is not None else time.monotonic)()
    require(type(began) in (float, int) and math.isfinite(began), "clock_invalid")
    approval = _approval(approval_bytes, approval_sha256, prepared=prepared, bound=bound, now=initial_clock())
    require(type(api_key) is str and 0 < len(api_key) <= 512 and not any(ch.isspace() for ch in api_key)
        and all(32 < ord(ch) < 127 for ch in api_key), "provider_key_invalid")
    require(type(ledger) is TrialLedger and not ledger.claimed, "ledger_already_consumed")
    if interfaces is not None:
        require(type(interfaces) is Interfaces and interfaces.synthetic is True
            and os.environ.get("ENVIRONMENT") == "test", "injected_interfaces_forbidden")
    else:
        _environment(settings, bound)
    try:
        interfaces = interfaces or production_interfaces(settings)
    except Exception:
        raise ExecutionError("controller_runtime_unavailable") from None
    require(_elapsed(interfaces, began) - began <= preparation.MAX_STARTUP_SECONDS, "startup_deadline")
    trial_id = UUID(approval["trial_id"])
    ledger.write("claim.json", {"schema": SCHEMA + "_claim", "trial_id": str(trial_id),
        "authorization_id": approval["authorization_id"], "approval_sha256": approval_sha256,
        "preflight_identity_sha256": approval["preflight_identity_sha256"],
        "binding_sha256": approval["binding_sha256"], "guards": preparation.guards()})
    result = {"schema": SCHEMA, "trial_id": str(trial_id), "status": "running",
        "synthetic_interfaces": interfaces.synthetic, "provider_calls": 0, "synthetic_transport_calls": 0,
        "embedding_calls": 0, "answer_calls": 0, "verifier_calls": 0, "automatic_retries": 0,
        "database_writes": 0, "case_denominator": 12, "completed_cases": 0, "cases": [],
        "known_guard_cost_microusd": 0, "usage_unknown_attempts": 0,
        "reserved_input_tokens": 0, "reserved_output_tokens": 0, "reserved_cost_usd": "0",
        "browser_page_open_observed": False, "actual_display_integrity_proved": False,
        "release_gate_passed": False}
    per_call = (Decimal(preparation.MAX_INPUT_TOKENS) * preparation.INPUT_PRICE_USD_PER_MILLION
        + Decimal(preparation.MAX_OUTPUT_TOKENS) * preparation.OUTPUT_PRICE_USD_PER_MILLION) / 1_000_000
    reserved, last_start, current = Decimal(0), None, None
    phase, failure = "startup", None
    try:
        async with asyncio.timeout(preparation.MAX_TOTAL_SECONDS):
            for frozen, case, pins in zip(prepared.cases, bound.cases, bound.pins, strict=True):
                phase = "current_anchor_lookup"
                current = {"schema": SCHEMA + "_request_receipt", "case_id": case.case_id,
                    "request_sha256": frozen.request_sha256, "body_sha256": frozen.body_sha256,
                    "trial_id": str(trial_id), "physical_attempted": False, "synthetic_attempted": False,
                    "http_status": None, "selected_ids": [], "input_tokens": None,
                    "output_tokens_including_thinking": None, "known_guard_cost_microusd": None,
                    "usage_cost_unknown": False, "browser_page_open_observed": False}
                selections = await _transaction(interfaces,
                    lambda db: interfaces.current_selections(db, bound.scope, case), MAX_ANCHOR_SECONDS)
                phase = "authenticated_render"
                proof = await _transaction(interfaces, lambda db: interfaces.render(db, settings=settings,
                    scope=bound.scope, case=case, selections=selections, pins=pins), MAX_RENDER_SECONDS)
                request = json.loads(frozen.request_bytes)
                body = preparation.canonical({key: value for key, value in request.items() if key != "model"})
                require(digest(body) == frozen.body_sha256, "request_body_changed")
                phase = "quota_wait"
                now = _elapsed(interfaces, began)
                if last_start is not None:
                    await interfaces.sleep(max(0, preparation.MIN_CALL_INTERVAL_SECONDS - (now - last_start)))
                reservation = await interfaces.quota()
                require(callable(getattr(reservation, "commit", None)), "quota_reservation_invalid")
                now = _elapsed(interfaces, began)
                require(last_start is None or now - last_start >= preparation.MIN_CALL_INTERVAL_SECONDS,
                    "quota_wait_incomplete")
                _approval_current(approval, interfaces.clock)
                nonce = uuid4()
                current["dispatch_nonce"] = str(nonce)
                phase = "fresh_dispatch_guard"
                receipt = await _transaction(interfaces, lambda db: interfaces.final(db, settings=settings,
                    scope=bound.scope, case=case, selections=selections, pins=pins, proof=proof,
                    trial_id=trial_id, dispatch_nonce=nonce, after_quota_wait=True), MAX_GUARD_SECONDS)
                guard_bytes = _receipt(receipt, interfaces=interfaces, prepared=prepared, bound=bound,
                    case=case, pins=pins, trial_id=trial_id, nonce=nonce)
                require(reserved + per_call <= preparation.MAX_COST_USD, "cost_reservation_failed")
                reserved += per_call
                result["reserved_input_tokens"] += preparation.MAX_INPUT_TOKENS
                result["reserved_output_tokens"] += preparation.MAX_OUTPUT_TOKENS
                result["reserved_cost_usd"] = str(reserved)
                ledger.write(case.case_id + "-dispatch-guard.json", receipt)
                ledger.write(case.case_id + "-intent.json", {**current, "status": "dispatch_intent",
                    "guard_receipt_sha256": digest(guard_bytes), "reserved_cost_usd": str(per_call)})
                _receipt(receipt, interfaces=interfaces, prepared=prepared, bound=bound,
                    case=case, pins=pins, trial_id=trial_id, nonce=nonce)
                _approval_current(approval, interfaces.clock)
                last_start = _elapsed(interfaces, began)
                current.update(physical_attempted=not interfaces.synthetic,
                    synthetic_attempted=interfaces.synthetic, usage_cost_unknown=True)
                counter = "synthetic_transport_calls" if interfaces.synthetic else "provider_calls"
                result[counter] += 1
                phase = "provider_transport"
                async with asyncio.timeout(preparation.MAX_CALL_SECONDS):
                    response = await interfaces.transport(preparation.ENDPOINT, body, api_key=api_key,
                        timeout_seconds=preparation.MAX_CALL_SECONDS)
                require(type(response) is custody.SuppliedHTTPResponse and type(response.status) is int
                    and 100 <= response.status <= 599, "transport_response_invalid")
                current["http_status"] = response.status
                require(response.status == 200, "provider_http_failure")
                phase = "strict_response"
                require(type(response.body) is bytes and 0 < len(response.body) <= preparation.MAX_HTTP_RESPONSE_BYTES,
                    "response_size_invalid")
                # Native usage is captured even if finish/schema/verdict/token
                # validation fails later. Neither raw HTTP nor thinking is saved.
                current.update(custody._usage(response.body))
                ledger.write(case.case_id + "-usage.json", {**current, "status": "usage_observed"})
                phase = "usage_reconciliation"
                async with asyncio.timeout(MAX_GUARD_SECONDS):
                    await reservation.commit(current["input_tokens"])
                phase = "strict_response"
                projected = preparation.parse_supplied_response(frozen, response.body)
                selected = tuple(projected["selected_ids"])
                current.update(selected_ids=list(selected), question_status=projected["question_status"],
                    excluded_cue_conflicts=projected["excluded_cue_conflicts"])
                phase = "post_selection_guard"
                selected_receipt = await _transaction(interfaces, lambda db: interfaces.final(db, settings=settings,
                    scope=bound.scope, case=case, selections=selections, pins=pins, proof=proof,
                    trial_id=trial_id, dispatch_nonce=nonce, after_quota_wait=True,
                    selected_ids=selected), MAX_GUARD_SECONDS)
                selected_bytes = _receipt(selected_receipt, interfaces=interfaces, prepared=prepared, bound=bound,
                    case=case, pins=pins, trial_id=trial_id, nonce=nonce, selected=selected)
                ledger.write(case.case_id + "-selected-guard.json", selected_receipt)
                observation = {"case_id": case.case_id, "selected_ids": list(selected),
                    "question_status": projected["question_status"], "request_sha256": frozen.request_sha256,
                    "admission_sha256": frozen.admission_sha256,
                    "dispatch_guard_sha256": digest(guard_bytes), "selected_guard_sha256": digest(selected_bytes),
                    "backend_association_verified": not interfaces.synthetic,
                    "browser_page_open_observed": False,
                    "unverified_references": True}
                current.update(status="completed", **{key: value for key, value in observation.items()
                    if key not in ("case_id", "selected_ids", "question_status", "request_sha256")})
                ledger.write(case.case_id + "-result.json", current)
                result["cases"].append(observation)
                result["completed_cases"] += 1
                result["known_guard_cost_microusd"] += current["known_guard_cost_microusd"]
                current = None
                _elapsed(interfaces, began)
        result["status"] = "completed"
    except asyncio.CancelledError:
        failure = "cancelled"
    except TimeoutError:
        failure = phase + "_timeout"
    except (ExecutionError, custody.TrialError, preparation.Refusal, guard.DispatchGuardError,
            preparation.contract.VisualSourceJudgmentError):
        failure = phase + "_refused"
    except Exception:
        failure = phase + "_failed"
    finally:
        if interfaces.close is not None:
            try:
                await interfaces.close()
            except Exception:
                failure = failure or "cleanup_failed"
    if failure:
        result.update(status="stopped", failure_phase=phase, failure_code=failure)
        if current is not None:
            current.update(status="stopped", failure_code=failure)
            ledger.write(current["case_id"] + "-result.json", current)
            if current["known_guard_cost_microusd"] is not None:
                result["known_guard_cost_microusd"] += current["known_guard_cost_microusd"]
            elif current["physical_attempted"] or current["synthetic_attempted"]:
                result["usage_unknown_attempts"] += 1
    ledger.write("summary.json", result)
    if failure == "cancelled":
        raise asyncio.CancelledError
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps({"schema": SCHEMA, "status": "outer_host_required" if args.execute else "unexecuted",
        "live_authorized": False, "provider_calls": 0, "database_reads": 0, "database_writes": 0,
        "release_gate_passed": False}))
    return 2 if args.execute else 0


if __name__ == "__main__":
    raise SystemExit(main())
