"""Synthetic dispatcher custody only: no provider, database or operator input."""
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import asyncio
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from test_private_visual_trial_v7_preflight import synthetic
from test_private_source_display_v7_score import NOW
from tests.test_source_visual_provider import response

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import run_private_visual_trial_v7 as runner


def digest(raw):
    return sha256(raw).hexdigest()


def synthetic_bound(monkeypatch):
    prep = runner.preparation
    artifacts, current_code, values, _ = synthetic(monkeypatch)
    prepared = prep.prepare(artifacts, current_code=current_code)
    packet = values["packet"]
    scope = runner.guard.DispatchScope(UUID(packet["scope"]["principal_id"]),
        UUID(packet["scope"]["subject_id"]), 3, "e" * 64)
    code = dict(prepared.code_sha256)
    for name in runner.guard.REQUIRED_CODE_PATHS | {runner.CALLER_PATH, runner.GUARD_PATH}:
        code[name] = digest((prep.REPO / name).read_bytes())
    cases, pins = [], []
    for frozen, row in zip(prepared.cases, packet["cases"], strict=True):
        request = json.loads(frozen.request_bytes)
        parts = request["contents"][0]["parts"]
        candidates = []
        for ordinal, source in enumerate(json.loads(frozen.sources_bytes)):
            cue = json.loads(parts[1 + ordinal * 2]["text"])
            candidates.append(runner.guard.FrozenCandidate(source["id"], UUID(source["document_id"]),
                UUID(source["content_revision_id"]), uuid4(), source["page_number"],
                cue["cue_start"], cue["cue_end"], source["pdf_sha256"], source["cue_sha256"],
                source["png_sha256"], source["page_text_sha256"]))
        current_question = json.loads(parts[0]["text"])["question"]
        cases.append(runner.guard.FrozenDispatchCase(frozen.case_id, current_question,
            frozen.request_bytes, prep.scorer._snapshot(row["admission_snapshot"]), tuple(candidates),
            row["preceding_question"]))
        pins.append(runner.guard.GuardPins(prepared.bridge_sha256, prepared.runtime_sha256,
            frozen.request_sha256, frozen.admission_sha256, code[runner.GUARD_PATH], code))
    bound = runner.BoundTrial(scope, tuple(cases), tuple(pins))
    return prepared, bound


class Harness:
    def __init__(self, prepared, bound):
        self.prepared, self.bound = prepared, bound
        self.seconds = 0.0
        self.calls, self.starts, self.dispatches, self.selections = [], [], [], []
        self.payload = response()
        self.status = 200

    def now(self):
        return NOW + timedelta(seconds=self.seconds)

    async def sleep(self, seconds):
        self.seconds += seconds

    def envelope(self, case, *, trial_id, dispatch_nonce, selected_ids=None):
        pins = self.bound.pins[self.bound.cases.index(case)]
        receipt = {"schema": runner.guard.SCHEMA, "policy": runner.guard.POLICY,
            "contract": runner.guard.CONTRACT,
            "purpose": "provider_dispatch" if selected_ids is None else "post_selection_pdf_read",
            "case_id": case.case_id, "trial_id": str(trial_id), "dispatch_nonce": str(dispatch_nonce),
            "checked_at_utc": self.now().isoformat(), "bridge_sha256": pins.bridge_sha256,
            "runtime_sha256": pins.runtime_sha256, "request_sha256": pins.request_sha256,
            "admission_sha256": pins.admission_sha256, "guard_code_sha256": pins.guard_code_sha256,
            "source_code_sha256": runner.guard.verify_code_pins(pins), "scope": self.bound.scope.identity(),
            "admission_basis": "frozen_case_simulation_not_persisted_history",
            "persisted_job_authorized": False, "transaction_read_only": True,
            # Explicit synthetic parser input, never an executed production grant.
            "production_interfaces": True, "ask_enabled": False, "source_judge_enabled": False,
            "after_quota_wait": True, "selected_ids": None if selected_ids is None else list(selected_ids),
            "browser_page_open_observed": False, "sources": []}
        for candidate in case.candidates:
            receipt["sources"].append({**{key: str(getattr(candidate, key)) if key.endswith("_id") and key != "id"
                else getattr(candidate, key) for key in ("id", "document_id", "content_revision_id",
                "index_revision_id", "page_number", "pdf_sha256", "cue_sha256", "png_sha256", "page_text_sha256")},
                **dict.fromkeys(("current_authorized", "published", "index_ready", "current_revision",
                    "original_pdf_authenticated", "page_association_valid"), True)})
        raw = runner.preparation.canonical(receipt)
        return runner.GuardEnvelope(raw, digest(raw))

    async def before(self, case, **kwargs):
        self.dispatches.append(case.case_id)
        return self.envelope(case, **kwargs)

    async def after(self, case, selected, **kwargs):
        self.selections.append((case.case_id, selected))
        return self.envelope(case, selected_ids=selected, **kwargs)

    async def transport(self, endpoint, body, *, timeout_seconds):
        assert endpoint == runner.preparation.ENDPOINT and timeout_seconds == 120
        assert "model" not in json.loads(body)
        self.calls.append(body)
        self.starts.append(self.seconds)
        return runner.SuppliedHTTPResponse(self.status, runner.preparation.canonical(self.payload))

    def interfaces(self, **changes):
        args = dict(before_dispatch=self.before, post_selection=self.after, transport=self.transport,
            sleep=self.sleep, clock=self.now, monotonic=lambda: self.seconds)
        args.update(changes)
        return runner.MockInterfaces(**args)


@pytest.fixture
def harness(monkeypatch):
    prepared, bound = synthetic_bound(monkeypatch)
    return Harness(prepared, bound)


async def run(harness, tmp_path, **interfaces):
    ledger = runner.OneUseLedger(tmp_path)
    result = await runner.run_mock_trial(harness.prepared, harness.bound,
        binding_sha256=runner.binding_identity(harness.bound), interfaces=harness.interfaces(**interfaces), ledger=ledger)
    return result, ledger


@pytest.mark.asyncio
async def test_complete_mock_custody_never_claims_real_execution(harness, tmp_path):
    result, ledger = await run(harness, tmp_path)
    assert result["status"] == "mock_completed" and result["completed_cases"] == 12
    assert result["mock_transport_calls"] == 12 and result["provider_calls"] == 0
    assert result["known_guard_cost_microusd"] == 12 * 2100 and result["usage_unknown_attempts"] == 0
    assert result["reserved_cost_usd"] == "0.2408448"
    assert all(after - before >= 30 for before, after in zip(harness.starts, harness.starts[1:]))
    assert len(harness.dispatches) == len(harness.selections) == 12
    assert all(not result[name] for name in ("live_authorized", "physical_execution_proved",
        "actual_display_integrity_proved", "release_gate_passed"))
    assert len(list(tmp_path.glob("*.json"))) == 26
    raw = (tmp_path / "summary.json").read_text()
    assert harness.bound.cases[0].question not in raw and "discarded synthetic thought" not in raw
    with pytest.raises(runner.TrialError, match="ledger_already_consumed"):
        runner.OneUseLedger(tmp_path).claim({"new": True})


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["finish", "verdict", "tokens"])
async def test_known_usage_is_kept_before_strict_output_failure(harness, tmp_path, mutation):
    if mutation == "finish":
        harness.payload["candidates"][0]["finishReason"] = "MAX_TOKENS"
    elif mutation == "verdict":
        harness.payload["candidates"][0]["content"]["parts"][1]["text"] = '{"invented_answer":"private words"}'
    else:
        harness.payload["usageMetadata"].update(promptTokenCount=32769, totalTokenCount=33369)
    result, _ = await run(harness, tmp_path)
    assert result["status"] == "stopped" and result["completed_cases"] == 0
    assert result["mock_transport_calls"] == len(harness.calls) == 1
    assert result["known_guard_cost_microusd"] > 0 and result["usage_unknown_attempts"] == 0
    recorded = json.loads((tmp_path / "T01-result.json").read_bytes())
    assert recorded["known_guard_cost_microusd"] == result["known_guard_cost_microusd"]
    assert recorded["http_status"] == 200 and not harness.selections
    assert "private words" not in (tmp_path / "T01-result.json").read_text()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [503, 429, 400])
async def test_http_failure_is_unknown_cost_without_retry(harness, tmp_path, status):
    harness.status = status
    result, _ = await run(harness, tmp_path)
    assert result["status"] == "stopped" and result["mock_transport_calls"] == 1
    assert len(harness.calls) == 1 and not harness.selections
    assert result["usage_unknown_attempts"] == 1 and result["known_guard_cost_microusd"] == 0
    assert result["automatic_retries"] == 0


@pytest.mark.asyncio
async def test_incomplete_wait_cannot_send_a_second_request(harness, tmp_path):
    async def early_sleep(seconds):
        pass
    result, _ = await run(harness, tmp_path, sleep=early_sleep)
    assert result["status"] == "stopped" and result["completed_cases"] == 1
    assert result["mock_transport_calls"] == len(harness.calls) == 1
    assert result["failure_phase"] == "quota_wait" and len(harness.dispatches) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["before_dispatch", "post_selection"])
async def test_whole_guard_callback_has_an_interrupting_deadline(harness, tmp_path, monkeypatch, phase):
    assert runner.MAX_CALLBACK_SECONDS == runner.guard.MAX_FRESH_SECONDS == 5
    monkeypatch.setattr(runner, "MAX_CALLBACK_SECONDS", .005)
    cancelled = []
    async def blocked(*args, **kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)
    result, _ = await run(harness, tmp_path,
        **{("before_dispatch" if phase == "before_dispatch" else "post_selection"): blocked})
    assert result["status"] == "stopped" and result["failure_code"] == phase + "_timeout"
    assert cancelled == [True]
    assert result["mock_transport_calls"] == (0 if phase == "before_dispatch" else 1)
    assert result["known_guard_cost_microusd"] == (0 if phase == "before_dispatch" else 2100)


@pytest.mark.asyncio
async def test_stale_receipt_stops_before_transport(harness, tmp_path):
    async def old(case, **kwargs):
        envelope = await harness.before(case, **kwargs)
        harness.seconds += 6
        return envelope
    result, _ = await run(harness, tmp_path, before_dispatch=old)
    assert result["status"] == "stopped" and result["mock_transport_calls"] == 0
    assert result["usage_unknown_attempts"] == 0 and not harness.calls


@pytest.mark.asyncio
async def test_timeout_retains_durable_uncertain_attempt(harness, tmp_path, monkeypatch):
    monkeypatch.setattr(runner.preparation, "MAX_CALL_SECONDS", .005)
    async def blocked(*args, **kwargs):
        await asyncio.Event().wait()
    result, _ = await run(harness, tmp_path, transport=blocked)
    assert result["failure_code"] == "transport_timeout" and result["mock_transport_calls"] == 1
    assert result["usage_unknown_attempts"] == 1
    assert (tmp_path / "claim.json").exists() and (tmp_path / "T01-intent.json").exists()


@pytest.mark.asyncio
async def test_cancelled_transport_records_unknown_cost_then_propagates(harness, tmp_path):
    async def cancelled(*args, **kwargs):
        raise asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await run(harness, tmp_path, transport=cancelled)
    summary = json.loads((tmp_path / "summary.json").read_bytes())
    assert summary["failure_code"] == "cancelled" and summary["usage_unknown_attempts"] == 1
    assert summary["mock_transport_calls"] == 1


@pytest.mark.asyncio
async def test_changed_binding_refuses_before_claim_or_callback(harness, tmp_path):
    changed = replace(harness.bound, cases=(replace(harness.bound.cases[0], question="Different subject"),
        *harness.bound.cases[1:]))
    with pytest.raises(runner.TrialError):
        await runner.run_mock_trial(harness.prepared, changed, binding_sha256=runner.binding_identity(changed),
            interfaces=harness.interfaces(), ledger=runner.OneUseLedger(tmp_path))
    assert not list(tmp_path.iterdir()) and not harness.dispatches and not harness.calls


def test_import_and_cli_do_not_read_operator_configuration(monkeypatch, capsys):
    assert runner.LIVE_AUTHORIZED is False
    assert runner.main([]) == 0 and runner.main(["--execute"]) == 2
    messages = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert all(row["provider_calls"] == row["database_reads"] == row["database_writes"] == 0 for row in messages)
    body = """
import pathlib, sys
sys.path.insert(0, sys.argv[1])
def audit(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)) and pathlib.Path(args[0]).name == '.env':
        raise RuntimeError('operator env forbidden')
sys.addaudithook(audit)
import run_private_visual_trial_v7
assert 'app.database' not in sys.modules
assert run_private_visual_trial_v7.LIVE_AUTHORIZED is False
print('runner_import_inert')
"""
    result = subprocess.run([sys.executable, "-I", "-c", body, str(runner.preparation.REPO / "scripts")],
        capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "runner_import_inert" and result.stderr == ""


def test_ledger_checks_original_path_on_each_write(tmp_path, monkeypatch):
    ledger = runner.OneUseLedger(tmp_path)
    ledger.claim({"invented": True})
    old = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == tmp_path or old(path))
    with pytest.raises(runner.TrialError, match="ledger_directory_invalid"):
        ledger.write("summary.json", {"invented": True})
    assert not (tmp_path / "summary.json").exists()


def test_ledger_portable_without_python312_windows_junction_api(tmp_path, monkeypatch):
    monkeypatch.delattr(Path, "is_junction", raising=False)
    ledger = runner.OneUseLedger(tmp_path)
    ledger.claim({"invented": True})
    assert (tmp_path / "claim.json").is_file()
