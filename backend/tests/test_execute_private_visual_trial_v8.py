"""Prospective inner controller with exclusively synthetic SQL/HTTP/key seams."""
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import asyncio
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import httpx
import pytest

from test_private_visual_trial_v8_caller import Harness, synthetic_bound
from test_private_source_display_v8_score import NOW
from tests.test_source_visual_provider import response

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import execute_private_visual_trial_v8 as inner


def digest(raw):
    return sha256(raw).hexdigest()


class Db:
    def __init__(self, events):
        self.events, self.identity = events, uuid4()

    async def __aenter__(self):
        self.events.append((self.identity, "enter"))
        return self

    async def __aexit__(self, *args):
        self.events.append((self.identity, "exit"))

    async def begin(self):
        self.events.append((self.identity, "begin"))

    async def rollback(self):
        self.events.append((self.identity, "rollback"))

    async def commit(self):
        pytest.fail("controller must never commit")


class ControllerHarness(Harness):
    def __init__(self, prepared, bound):
        super().__init__(prepared, bound)
        self.events, self.transactions, self.keys, self.closed, self.actual_input_tokens = [], [], [], [], []

    def factory(self):
        self.transactions.append(Db(self.events))
        return self.transactions[-1]

    async def anchors(self, db, scope, case):
        self.events.append((db.identity, "lookup"))
        return ("synthetic selections", case.case_id)

    async def render(self, db, **args):
        self.events.append((db.identity, "render"))
        return object()

    async def quota(self):
        self.events.append((None, "quota"))
        harness = self
        class Reservation:
            async def commit(self, actual):
                harness.actual_input_tokens.append(actual)
        return Reservation()

    async def final(self, db, **args):
        case = args["case"]
        self.events.append((db.identity, "selected" if "selected_ids" in args else "dispatch"))
        envelope = self.envelope(case, trial_id=args["trial_id"], dispatch_nonce=args["dispatch_nonce"],
            selected_ids=args.get("selected_ids"))
        return json.loads(envelope.receipt_bytes)

    async def transport(self, endpoint, body, *, api_key, timeout_seconds):
        self.events.append((None, "transport"))
        self.keys.append(api_key)
        return await super().transport(endpoint, body, timeout_seconds=timeout_seconds)

    async def close(self):
        self.closed.append(True)

    def controller_interfaces(self, **changes):
        args = dict(session_factory=self.factory, quota=self.quota, transport=self.transport,
            current_selections=self.anchors, render=self.render, final=self.final,
            clock=self.now, monotonic=lambda: self.seconds, sleep=self.sleep,
            close=self.close, synthetic=True)
        args.update(changes)
        return inner.Interfaces(**args)


@pytest.fixture
def harness(monkeypatch):
    prepared, bound = synthetic_bound(monkeypatch)
    code = dict(bound.pins[0].code_sha256)
    for relative in (inner.EXECUTOR_PATH, inner.REHEARSAL_PATH):
        code[relative] = digest((inner.REPO / relative).read_bytes())
    bound = replace(bound, pins=tuple(replace(pin, code_sha256=code) for pin in bound.pins))
    return ControllerHarness(prepared, bound)


def approval(harness):
    raw = inner.approval_payload(harness.prepared, harness.bound, trial_id=uuid4(),
        authorization_id="invented_private_test_authority", approved_at=NOW,
        expires_at=NOW + timedelta(hours=1))
    return raw, digest(raw)


async def run(harness, tmp_path, monkeypatch, **changes):
    monkeypatch.setattr(inner, "LIVE_AUTHORIZED", True)
    raw, pin = approval(harness)
    return await inner.execute_private_trial_v8(harness.prepared, harness.bound,
        settings=object(), api_key="invented-private-test-key", approval_bytes=raw, approval_sha256=pin,
        ledger=inner.TrialLedger(tmp_path), interfaces=harness.controller_interfaces(**changes))


@pytest.mark.asyncio
async def test_complete_private_mock_has_four_fresh_rolled_back_transactions_per_case(harness, tmp_path, monkeypatch):
    result = await run(harness, tmp_path, monkeypatch)
    assert result["status"] == "completed" and result["completed_cases"] == 12
    assert result["provider_calls"] == 0 and result["synthetic_transport_calls"] == 12
    assert result["known_guard_cost_microusd"] == 25200 and result["reserved_cost_usd"] == "0.2408448"
    assert result["database_writes"] == result["embedding_calls"] == result["answer_calls"] == 0
    assert result["verifier_calls"] == result["automatic_retries"] == 0
    assert len(harness.transactions) == 48
    for db in harness.transactions:
        actions = [kind for identity, kind in harness.events if identity == db.identity]
        assert actions[0:2] == ["enter", "begin"] and actions[-2:] == ["rollback", "exit"]
        assert len(actions) == 5
    assert harness.closed == [True]
    assert harness.actual_input_tokens == [2000] * 12
    assert all(after - before >= 30 for before, after in zip(harness.starts, harness.starts[1:]))
    first = [kind for _, kind in harness.events[:22]]
    assert first.index("render") < first.index("quota") < first.index("dispatch") < first.index("transport")
    assert all(not row["backend_association_verified"] and not row["browser_page_open_observed"]
        for row in result["cases"])
    assert not result["actual_display_integrity_proved"] and not result["release_gate_passed"]
    assert len(list(tmp_path.glob("*.json"))) == 62
    text = "\n".join(path.read_text() for path in tmp_path.glob("*.json"))
    assert "invented-private-test-key" not in text and "discarded synthetic thought" not in text


@pytest.mark.asyncio
async def test_candidate_local_negative_cue_conflict_does_not_drop_valid_page_or_promote_weak_one(
    harness, tmp_path, monkeypatch,
):
    verdict = {"question_status": "clear", "pages": [
        {"id": "S01", "usefulness": "direct", "cue_locates": True},
        {"id": "S02", "usefulness": "topic_only", "cue_locates": True},
        {"id": "S03", "usefulness": "unrelated", "cue_locates": False},
        {"id": "S04", "usefulness": "unrelated", "cue_locates": False},
    ]}
    harness.payload["candidates"][0]["content"]["parts"][1]["text"] = json.dumps(verdict)
    result = await run(harness, tmp_path, monkeypatch)
    assert result["status"] == "completed" and result["completed_cases"] == 12
    assert result["synthetic_transport_calls"] == 12 and result["provider_calls"] == 0
    assert all(row["selected_ids"] == ["S01"] for row in result["cases"])
    for cid in inner.preparation.CASE_IDS:
        receipt = json.loads((tmp_path / (cid + "-result.json")).read_bytes())
        assert receipt["selected_ids"] == ["S01"] and receipt["excluded_cue_conflicts"] == 1
    assert not result["actual_display_integrity_proved"] and not result["release_gate_passed"]


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["finish", "schema", "over_budget"])
async def test_usage_is_preserved_before_strict_rejection(harness, tmp_path, monkeypatch, mutation):
    if mutation == "finish":
        harness.payload["candidates"][0]["finishReason"] = "MAX_TOKENS"
    elif mutation == "schema":
        harness.payload["candidates"][0]["content"]["parts"][1]["text"] = '{"answer":"private text"}'
    else:
        harness.payload["usageMetadata"].update(promptTokenCount=32769, totalTokenCount=33369)
    result = await run(harness, tmp_path, monkeypatch)
    assert result["status"] == "stopped" and result["completed_cases"] == 0
    assert result["synthetic_transport_calls"] == 1 and result["usage_unknown_attempts"] == 0
    receipt = json.loads((tmp_path / "T01-result.json").read_bytes())
    assert receipt["known_guard_cost_microusd"] == result["known_guard_cost_microusd"] > 0
    assert harness.actual_input_tokens == [receipt["input_tokens"]]
    assert len(harness.transactions) == 3 and len(harness.calls) == 1
    assert "private text" not in (tmp_path / "T01-result.json").read_text()


@pytest.mark.asyncio
async def test_usage_checkpoint_is_durable_before_the_strict_parser_runs(harness, tmp_path, monkeypatch):
    def reject(*args, **kwargs):
        usage = json.loads((tmp_path / "T01-usage.json").read_bytes())
        assert usage["known_guard_cost_microusd"] == 2100 and usage["status"] == "usage_observed"
        raise inner.preparation.Refusal("invented_strict_failure")
    monkeypatch.setattr(inner.preparation, "parse_supplied_response", reject)
    result = await run(harness, tmp_path, monkeypatch)
    assert result["status"] == "stopped" and result["known_guard_cost_microusd"] == 2100
    assert result["usage_unknown_attempts"] == 0


@pytest.mark.asyncio
async def test_http_503_records_uncertain_cost_and_stops_without_replay(harness, tmp_path, monkeypatch):
    harness.status = 503
    result = await run(harness, tmp_path, monkeypatch)
    assert result["status"] == "stopped" and result["usage_unknown_attempts"] == 1
    assert result["synthetic_transport_calls"] == 1 and result["automatic_retries"] == 0
    assert not harness.actual_input_tokens
    assert (tmp_path / "T01-intent.json").exists() and not (tmp_path / "T02-intent.json").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["render", "final"])
async def test_failed_readonly_phase_rolls_back_and_cannot_dispatch(harness, tmp_path, monkeypatch, stage):
    async def fail(*args, **kwargs):
        raise RuntimeError("invented private internal SQL details")
    result = await run(harness, tmp_path, monkeypatch, **{stage: fail})
    assert result["status"] == "stopped" and result["synthetic_transport_calls"] == 0
    assert all(any(identity == db.identity and kind == "rollback" for identity, kind in harness.events)
        for db in harness.transactions)
    assert "internal SQL" not in json.dumps(result)


@pytest.mark.asyncio
async def test_final_callback_has_interrupting_five_second_boundary(harness, tmp_path, monkeypatch):
    assert inner.MAX_GUARD_SECONDS == 5
    monkeypatch.setattr(inner, "MAX_GUARD_SECONDS", .005)
    cancelled = []
    async def blocked(*args, **kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)
    result = await run(harness, tmp_path, monkeypatch, final=blocked)
    assert result["failure_code"] == "fresh_dispatch_guard_timeout" and cancelled == [True]
    assert result["synthetic_transport_calls"] == 0 and harness.closed == [True]


@pytest.mark.asyncio
async def test_post_selection_revalidation_failure_keeps_known_usage(harness, tmp_path, monkeypatch):
    async def final(db, **args):
        if "selected_ids" in args:
            raise inner.guard.DispatchGuardError("invented_source_changed")
        return await harness.final(db, **args)
    result = await run(harness, tmp_path, monkeypatch, final=final)
    assert result["failure_phase"] == "post_selection_guard" and result["completed_cases"] == 0
    assert result["known_guard_cost_microusd"] == 2100 and result["usage_unknown_attempts"] == 0
    assert len(harness.transactions) == 4 and len(harness.calls) == 1 and result["cases"] == []


@pytest.mark.asyncio
async def test_cancellation_after_dispatch_keeps_ledger_and_propagates(harness, tmp_path, monkeypatch):
    async def cancel(*args, **kwargs):
        raise asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await run(harness, tmp_path, monkeypatch, transport=cancel)
    saved = json.loads((tmp_path / "summary.json").read_bytes())
    assert saved["failure_code"] == "cancelled" and saved["usage_unknown_attempts"] == 1
    assert saved["synthetic_transport_calls"] == 1 and harness.closed == [True]


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["flag", "sha", "expiry", "scope", "transfer", "cost"])
async def test_no_approval_forgery_can_reach_ledger_or_sql(harness, tmp_path, monkeypatch, change):
    raw, pin = approval(harness)
    monkeypatch.setattr(inner, "LIVE_AUTHORIZED", change != "flag")
    value = json.loads(raw)
    if change == "sha":
        pin = "a" * 64
    elif change == "expiry":
        value["expires_at_utc"] = (NOW - timedelta(seconds=1)).isoformat()
    elif change == "scope":
        value["binding_sha256"] = "a" * 64
    elif change == "transfer":
        value["private_transfer_approved"] = False
    elif change == "cost":
        value["guards"]["max_cost_usd"] = "10"
    if change not in ("flag", "sha"):
        raw = inner.preparation.canonical(value)
        pin = digest(raw)
    with pytest.raises(inner.ExecutionError):
        await inner.execute_private_trial_v8(harness.prepared, harness.bound, settings=object(),
            api_key="invented-private-test-key", approval_bytes=raw, approval_sha256=pin,
            ledger=inner.TrialLedger(tmp_path), interfaces=harness.controller_interfaces())
    assert not list(tmp_path.iterdir()) and not harness.transactions and not harness.calls


@pytest.mark.asyncio
async def test_claim_cannot_be_reused_even_after_failure(harness, tmp_path, monkeypatch):
    harness.status = 503
    await run(harness, tmp_path, monkeypatch)
    with pytest.raises(inner.ExecutionError, match="ledger_already_consumed"):
        await run(harness, tmp_path, monkeypatch)
    assert len(harness.calls) == 1


@pytest.mark.asyncio
async def test_startup_budget_includes_approval_and_runtime_setup(harness, tmp_path, monkeypatch):
    ticks = iter((0.0, 31.0))
    with pytest.raises(inner.ExecutionError, match="startup_deadline"):
        await run(harness, tmp_path, monkeypatch, monotonic=lambda: next(ticks))
    assert not list(tmp_path.iterdir()) and not harness.transactions


@pytest.mark.asyncio
async def test_expiring_approval_cannot_send_another_request_after_quota_wait(harness, tmp_path, monkeypatch):
    monkeypatch.setattr(inner, "LIVE_AUTHORIZED", True)
    raw = inner.approval_payload(harness.prepared, harness.bound, trial_id=uuid4(),
        authorization_id="invented_private_test_authority", approved_at=NOW,
        expires_at=NOW + timedelta(seconds=10))
    result = await inner.execute_private_trial_v8(harness.prepared, harness.bound, settings=object(),
        api_key="invented-private-test-key", approval_bytes=raw, approval_sha256=digest(raw),
        ledger=inner.TrialLedger(tmp_path), interfaces=harness.controller_interfaces())
    assert result["status"] == "stopped" and result["completed_cases"] == 1
    assert result["synthetic_transport_calls"] == 1 and result["failure_phase"] == "quota_wait"


@pytest.mark.asyncio
async def test_production_factory_error_is_safe_before_claim_or_dispatch(harness, tmp_path, monkeypatch):
    raw, pin = approval(harness)
    monkeypatch.setattr(inner, "LIVE_AUTHORIZED", True)
    monkeypatch.setattr(inner, "_now", lambda: NOW)
    monkeypatch.setattr(inner, "_environment", lambda *args: None)
    def fail(*args):
        raise RuntimeError("invented private connection details")
    monkeypatch.setattr(inner, "production_interfaces", fail)
    with pytest.raises(inner.ExecutionError, match="^controller_runtime_unavailable$"):
        await inner.execute_private_trial_v8(harness.prepared, harness.bound, settings=object(),
            api_key="invented-private-test-key", approval_bytes=raw, approval_sha256=pin,
            ledger=inner.TrialLedger(tmp_path))
    assert not list(tmp_path.iterdir()) and not harness.transactions


@pytest.mark.asyncio
async def test_native_transport_uses_explicit_key_without_retries_or_proxy(monkeypatch):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=response())
    def transport(**kwargs):
        assert kwargs == {"retries": 0}
        return httpx.MockTransport(handler)
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", transport)
    got = await inner.native_transport(inner.preparation.ENDPOINT, b"{}",
        api_key="invented-ram-only-key", timeout_seconds=120)
    assert got.status == 200 and len(requests) == 1
    assert requests[0].method == "POST" and requests[0].headers["x-goog-api-key"] == "invented-ram-only-key"


@pytest.mark.asyncio
async def test_native_http_failure_never_reads_provider_error_body(monkeypatch):
    class ForbiddenErrorBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            pytest.fail("provider error body must not be read")
            yield b"unreachable"
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda **kwargs:
        httpx.MockTransport(lambda request: httpx.Response(503, stream=ForbiddenErrorBody())))
    got = await inner.native_transport(inner.preparation.ENDPOINT, b"{}",
        api_key="invented-ram-only-key", timeout_seconds=120)
    assert got.status == 503 and got.body == b""


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["oversize", "gzip"])
async def test_native_response_limits_precede_parser_and_receipts(monkeypatch, kind):
    payload = b" " * 65537 if kind == "oversize" else b"{}"
    headers = {"Content-Encoding": "gzip"} if kind == "gzip" else {}
    class RawBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield payload
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda **kwargs:
        httpx.MockTransport(lambda request: httpx.Response(200, headers=headers, stream=RawBody())))
    with pytest.raises(inner.ExecutionError):
        await inner.native_transport(inner.preparation.ENDPOINT, b"{}",
            api_key="invented-ram-only-key", timeout_seconds=120)


@pytest.mark.asyncio
async def test_production_interfaces_use_real_quota_signature_and_actual_usage_without_sql(monkeypatch):
    """Construct an unconnected real engine/governor; only HTTP is synthetic."""
    from app.config import Settings
    from app.ai.rate_limit import ProviderRateReservation
    from sqlalchemy.ext.asyncio import create_async_engine
    import sqlalchemy.ext.asyncio as sqlalchemy_async
    engines, engine_arguments, requests = [], [], []
    def engine_factory(*args, **kwargs):
        # A local unused URL selects no retained database, and even that URL
        # must never connect during this integration boundary test.
        assert args == ("postgresql+asyncpg://invented:invented@127.0.0.1:1/private_controller_test",)
        engine_arguments.append(kwargs)
        engine = create_async_engine(*args, **kwargs)
        monkeypatch.setattr(engine.sync_engine.pool, "connect",
            lambda *a, **k: pytest.fail("SQL connection attempted"))
        engines.append(engine)
        return engine
    monkeypatch.setattr(sqlalchemy_async, "create_async_engine", engine_factory)
    settings = Settings(_env_file=None, environment="development",
        secret_key="invented-private-controller-secret-12345678901234567890",
        generation_source_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        knowledge_pdf_encryption_key="AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE",
        database_url="postgresql+asyncpg://invented:invented@127.0.0.1:1/private_controller_test",
        flashcard_ai_api_key=None, rag_ai_api_key=None, rag_embedding_api_key=None, rag_source_judge_api_key=None,
        rag_ask_enabled=False, rag_source_judge_provider_enabled=False,
        rag_source_judge_requests_per_minute=5, rag_source_judge_input_tokens_per_minute=250000,
        rag_source_judge_rate_limit_safety_percent=80)
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=response())
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda **kwargs: httpx.MockTransport(handler))
    interfaces = inner.production_interfaces(settings)
    try:
        assert not interfaces.synthetic and len(engines) == 1
        assert engine_arguments[0]["hide_parameters"] is True
        assert engine_arguments[0]["connect_args"]["server_settings"] == {
            "statement_timeout": "5000", "lock_timeout": "1000", "idle_in_transaction_session_timeout": "15000"}
        reservation = await interfaces.quota()
        assert type(reservation) is ProviderRateReservation
        governor = reservation._governor
        before = await governor.snapshot()
        assert before.request_attempts == 1 and before.retry_attempts == 0
        assert before.current_window_input_tokens == 32768 and before.actual_input_tokens == 0
        assert governor.requests_per_window == 4 and governor.input_tokens_per_window == 200000
        supplied = await interfaces.transport(inner.preparation.ENDPOINT, b"{}",
            api_key="invented-explicit-ram-key", timeout_seconds=120)
        usage = inner.custody._usage(supplied.body)
        await reservation.commit(usage["input_tokens"])
        after = await governor.snapshot()
        assert after.current_window_input_tokens == after.actual_input_tokens == 2000
        assert after.estimated_input_tokens == 32768
        assert after.by_operation["source_judgment"].actual_input_tokens == 2000
        assert after.by_operation["source_judgment"].request_attempts == 1
        assert len(requests) == 1 and requests[0].headers["x-goog-api-key"] == "invented-explicit-ram-key"
    finally:
        await interfaces.close()


@pytest.mark.asyncio
async def test_quota_failure_retains_conservative_reservation_and_never_commits_usage(harness, tmp_path, monkeypatch):
    from app.ai.rate_limit import ProviderRateGovernor
    governor = ProviderRateGovernor(requests_per_minute=5, input_tokens_per_minute=250000, safety_percent=80)
    async def quota():
        return await governor.reserve(32768, operation="source_judgment", attempt=0)
    harness.status = 503
    result = await run(harness, tmp_path, monkeypatch, quota=quota)
    snapshot = await governor.snapshot()
    assert result["usage_unknown_attempts"] == 1 and result["synthetic_transport_calls"] == 1
    assert snapshot.current_window_input_tokens == 32768 and snapshot.actual_input_tokens == 0
    assert snapshot.request_attempts == 1 and snapshot.retry_attempts == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["absent", "boolean_input", "negative_output", "invalid_json"])
async def test_malformed_native_usage_keeps_attempt_and_unknown_cost_with_max_reservation(
    harness, tmp_path, monkeypatch, mutation,
):
    from app.ai.rate_limit import ProviderRateGovernor
    governor = ProviderRateGovernor(requests_per_minute=5, input_tokens_per_minute=250000, safety_percent=80)
    async def quota():
        return await governor.reserve(32768, operation="source_judgment", attempt=0)
    if mutation == "absent":
        harness.payload.pop("usageMetadata")
    elif mutation == "boolean_input":
        harness.payload["usageMetadata"]["promptTokenCount"] = True
    elif mutation == "negative_output":
        harness.payload["usageMetadata"]["candidatesTokenCount"] = -1
    async def transport(*args, **kwargs):
        supplied = await harness.transport(*args, **kwargs)
        return inner.custody.SuppliedHTTPResponse(200, b"{" if mutation == "invalid_json" else supplied.body)
    result = await run(harness, tmp_path, monkeypatch, quota=quota, transport=transport)
    snapshot = await governor.snapshot()
    assert result["status"] == "stopped" and result["failure_phase"] == "strict_response"
    assert result["synthetic_transport_calls"] == 1 and result["provider_calls"] == 0
    assert result["usage_unknown_attempts"] == 1 and result["known_guard_cost_microusd"] == 0
    assert snapshot.current_window_input_tokens == 32768 and snapshot.actual_input_tokens == 0
    assert snapshot.request_attempts == 1 and snapshot.retry_attempts == 0
    saved = json.loads((tmp_path / "T01-result.json").read_bytes())
    assert saved["synthetic_attempted"] and not saved["physical_attempted"] and saved["usage_cost_unknown"]
    assert saved["http_status"] == 200 and saved["input_tokens"] is None
    assert not (tmp_path / "T01-usage.json").exists() and not (tmp_path / "T02-intent.json").exists()
    assert len(harness.calls) == 1


@pytest.mark.asyncio
async def test_usage_reconciliation_failure_preserves_durable_charge_and_stops(harness, tmp_path, monkeypatch):
    class Reservation:
        async def commit(self, actual):
            raise RuntimeError("invented internal governor error")
    async def quota():
        return Reservation()
    result = await run(harness, tmp_path, monkeypatch, quota=quota)
    assert result["failure_phase"] == "usage_reconciliation" and result["completed_cases"] == 0
    assert result["known_guard_cost_microusd"] == 2100 and result["usage_unknown_attempts"] == 0
    assert json.loads((tmp_path / "T01-usage.json").read_bytes())["input_tokens"] == 2000
    assert len(harness.calls) == 1


def test_import_and_default_cli_remain_inert_without_operator_env_reads(capsys):
    assert inner.LIVE_AUTHORIZED is False
    assert inner.main([]) == 0 and inner.main(["--execute"]) == 2
    assert all(json.loads(row)["provider_calls"] == 0 for row in capsys.readouterr().out.splitlines())
    body = """
import pathlib, sys
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
def audit(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)) and pathlib.Path(args[0]).name == '.env':
        raise RuntimeError('operator env forbidden')
sys.addaudithook(audit)
import execute_private_visual_trial_v8
assert 'app.database' not in sys.modules
assert execute_private_visual_trial_v8.LIVE_AUTHORIZED is False
print('controller_import_inert')
"""
    result = subprocess.run([sys.executable, "-I", "-c", body,
        str(inner.REPO / "backend/scripts"), str(inner.REPO / "scripts")],
        capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "controller_import_inert" and result.stderr == ""
