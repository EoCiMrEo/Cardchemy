"""Invented checkpoints and transports; no live source, key or provider read."""
import asyncio
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import run_visual_public_heldout_v3 as caller
import launch_visual_public_heldout_v3 as launcher
from test_visual_public_heldout_v1_score import fixture
from test_visual_public_calibration_v2_caller import Clock, response
from test_visual_public_heldout_v2_caller import admitted as parent_admitted


def admitted():
    overlay, original, expected = fixture()
    rows = [dict(r) for r in original[:14]]
    for row in rows:
        if row["group_id"] in caller.FAILED_GROUPS:
            row.update(state="failed", selected_ids=[], question_status=None)
    requests = [{"group_id": gid, "path": f"{gid}.json", "wire_sha256": "a" * 64,
                 "rest_sha256": caller.digest(b"synthetic"), "rest_bytes": 9} for gid in caller.NEW_GROUPS]
    binding = {"parent_report_sha256": caller.PARENT_REPORT_SHA,
        "parent_approval_sha256": caller.PARENT_APPROVAL_SHA, "inherited_failures": list(caller.FAILED_GROUPS),
        "rows_sha256": caller.digest(caller.canonical(rows)), "parent_cooldown_until_epoch_ms": 0}
    checkpoint = {"rows": rows, "receipts": {g: {} for g in caller.PARENT_GROUPS},
        "prior_receipts": {g: {} for g in caller.parent_trial.OLD_SUCCESS_GROUPS},
        "binding": binding, "binding_sha256": caller.digest(caller.canonical(binding))}
    return dict(overlay=overlay, expected_ids=expected, requests=requests, known_images=set(), checkpoint=checkpoint,
        request_roster_sha256=caller.digest(caller.canonical(requests)), calibration_binding={"passed": True})


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(caller, "read_bound", lambda *args, **kwargs: {})
    monkeypatch.setattr(caller, "rest_body", lambda *args: b"synthetic")
    out, ledger = tmp_path / "out", tmp_path / "ledger"
    out.mkdir(); ledger.mkdir()
    return out, ledger


def success(a, gid):
    good = {r["candidate_id"] for r in a["overlay"] if r["group_id"] == gid and r["qualification"] == "Yes"}
    return httpx.Response(200, json=response(["direct" if sid in good else "unrelated" for sid in caller.ISSUED]))


def test_disabled_execution_rejects_before_resource_source_or_key(tmp_path, monkeypatch):
    monkeypatch.setattr(caller, "LIVE_AUTHORIZED", False)
    assert caller.LIVE_AUTHORIZED is False
    monkeypatch.setattr(caller.previous, "read_key", lambda: pytest.fail("key touched"))
    monkeypatch.setattr(caller.visual, "_inside_windows_job", lambda: pytest.fail("resource touched"))
    monkeypatch.setattr(caller, "admit", lambda: pytest.fail("source touched"))
    with pytest.raises(caller.PilotError, match="precise_provider_envelope_not_authorized"):
        asyncio.run(caller.execute({}, "a" * 64, tmp_path))
    guards = caller.guards()
    assert guards["max_calls"] == 46 and guards["input_total"] == 1507328 and guards["output_total"] == 188416
    assert guards["new_cost_cap_microusd"] == 1000000 and 46 * caller.cost(32768, 4096) == 923266
    assert guards["inherited_valid_responses"] == 12 and guards["inherited_failed_groups"] == 2
    assert guards["prior_physical_attempts"] == 17 and guards["prior_unknown_cost_attempts"] == 5
    assert guards["manual_failed_reattempts"] == guards["retries"] == 0
    assert guards["minimum_valid_responses"] == 58 and guards["maximum_failed_groups"] == 2


def test_no_arguments_is_inert_before_any_admission(monkeypatch):
    monkeypatch.setattr(caller, "LIVE_AUTHORIZED", False)
    monkeypatch.setattr(caller.sys, "argv", ["inert-caller"])
    monkeypatch.setattr(caller, "admit", lambda: pytest.fail("no input admission"))
    with pytest.raises(SystemExit) as stopped:
        caller.main()
    assert stopped.value.code == 2


def test_all46_untouched_calls_keep14_outcomes_and17_old_physical_attempts(tmp_path, monkeypatch):
    a = admitted(); before = copy.deepcopy(a)
    out, ledger = setup(tmp_path, monkeypatch); clock, starts, ids = Clock(), [], []
    async def send(body):
        starts.append(clock.now); gid = a["requests"][len(starts) - 1]["group_id"]; ids.append(gid)
        return success(a, gid)
    result = asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger, clock=clock, sleep=clock.sleep))
    assert a == before and tuple(ids) == caller.NEW_GROUPS
    assert result["provider_calls"] == 46 and result["evaluated_group_attempts"] == 60
    assert result["total_physical_provider_calls"] == 63 and result["historical_physical_attempts"] == 17
    assert result["score"]["heldout_passed"] and result["score"]["metrics"]["valid_responses"] == 58
    assert result["score"]["metrics"]["failed_groups"] == 2
    assert result["prior_unknown_cost_attempts"] == 5
    assert result["combined_known_cost_microusd"] == result["known_cost_microusd"] + 72454
    observed = json.loads((out / "progress.json").read_bytes())
    assert observed["inherited_physical_provider_calls"] == 17
    assert observed["inherited_evaluated_groups"] == 14
    assert "inherited_provider_calls" not in observed
    assert all(b - a >= 30 for a, b in zip(starts, starts[1:]))
    assert not result["ask_enabled"] and not result["resume_permitted"] and result["old_trial_remains_failed"]
    with pytest.raises(FileExistsError):
        asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger))


@pytest.mark.parametrize("failure", ["timeout", "503", "unfinished"])
def test_one_additional_failure_makes58_valid_unreachable(tmp_path, monkeypatch, failure):
    a = admitted(); out, ledger = setup(tmp_path, monkeypatch); clock, attempts = Clock(), []
    async def send(body):
        attempts.append(body)
        if failure == "timeout": raise httpx.ReadTimeout("not retained")
        if failure == "503": return httpx.Response(503, content=b"not retained")
        r = response(["unrelated"] * 4); r["candidates"][0]["finishReason"] = "MAX_TOKENS"
        return httpx.Response(200, json=r)
    result = asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger, clock=clock, sleep=clock.sleep))
    assert len(attempts) == result["provider_calls"] == 1
    assert result["evaluated_group_attempts"] == 15 and result["total_physical_provider_calls"] == 18
    assert result["reason"] == "quality_unreachable" and result["score"]["metrics"]["failed_groups"] == 3
    assert not result["score"]["heldout_passed"]
    assert result["ceiling"]["upper_bounds"]["valid_responses"] == 57


def test_inherited_503_cooldown_precedes_first_different_question(tmp_path, monkeypatch):
    a = admitted(); binding = a["checkpoint"]["binding"]
    binding["parent_cooldown_until_epoch_ms"] = 150000
    a["checkpoint"]["binding_sha256"] = caller.digest(caller.canonical(binding))
    monkeypatch.setattr(caller.time, "time", lambda: 100)
    out, ledger = setup(tmp_path, monkeypatch); clock, starts = Clock(), []
    async def send(body):
        starts.append(clock.now)
        return success(a, a["requests"][len(starts) - 1]["group_id"])
    asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger, clock=clock, sleep=clock.sleep))
    assert starts[0] == 50


def test_time_or_cost_fails_before_any_physical_attempt(tmp_path, monkeypatch):
    a = admitted(); out, ledger = setup(tmp_path, monkeypatch); clock = Clock()
    monkeypatch.setattr(caller, "MAX_SECONDS", 119)
    async def send(body): pytest.fail("no provider")
    with pytest.raises(caller.PilotError, match="total_time_budget"):
        asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger, clock=clock, sleep=clock.sleep))
    assert not list(ledger.glob(caller.AUTHORIZATION_ID + "-Q*.claim.json"))


def test_cost_reservation_precedes_dispatch(tmp_path, monkeypatch):
    a = admitted(); out, ledger = setup(tmp_path, monkeypatch); clock = Clock()
    monkeypatch.setattr(caller, "COST_CAP_MICROUSD", caller.cost(32768, 4096) - 1)
    async def send(body): pytest.fail("no provider")
    with pytest.raises(caller.PilotError, match="cost_reserve_budget"):
        asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger, clock=clock, sleep=clock.sleep))
    assert not list(ledger.glob(caller.AUTHORIZATION_ID + "-Q*.claim.json"))


@pytest.mark.parametrize("field,value", [("group_id", "Q014"), ("group_id", "Q061"), ("rest_sha256", "b" * 64)])
def test_changed_or_reattempted_request_roster_rejected(tmp_path, monkeypatch, field, value):
    a = admitted(); a["requests"][0][field] = value
    out, ledger = setup(tmp_path, monkeypatch)
    async def send(body): pytest.fail("no provider")
    with pytest.raises(caller.PilotError, match="physical_attempt_roster_invalid|request_changed"):
        asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger))


def test_corrupted_inherited_failure_cannot_become_valid(tmp_path, monkeypatch):
    a = admitted(); a["checkpoint"]["rows"][-1].update(state="completed", question_status="clear")
    out, ledger = setup(tmp_path, monkeypatch)
    async def send(body): pytest.fail("no provider")
    with pytest.raises(caller.PilotError, match="checkpoint_binding_changed"):
        asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger))
    assert not list(ledger.iterdir())


def test_foreground_launcher_inert_and_environment_contains_no_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(caller, "LIVE_AUTHORIZED", False)
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("no child"))
    with pytest.raises(caller.visual.PreparationError, match="fresh_provider_authorization_required"):
        launcher.supervise(tmp_path / "approval.json", "a" * 64, tmp_path / "output")
    env = launcher.child_env({"SystemRoot": "C:/Windows", "RAG_SOURCE_JUDGE_API_KEY": "forbidden",
        "HTTP_PROXY": "forbidden", "DATABASE_URL": "forbidden"})
    assert "forbidden" not in env.values() and launcher.MAX_SECONDS == 9000
    assert not hasattr(launcher, "detach")


@pytest.fixture
def parent_files(tmp_path, monkeypatch):
    base = parent_admitted()
    ledger, output = tmp_path / "ledger", tmp_path / "output"
    ledger.mkdir(); output.mkdir()
    auth = "invented_consumed_v2"
    code = {"scripts/launch_visual_public_heldout_v2.py": "a" * 64}
    fake_parent = SimpleNamespace(AUTHORIZATION_ID=auth, OLD_SUCCESS_GROUPS=("Q001", "Q002", "Q005"),
        OLD_COST_MICROUSD=14444, validate_approval=lambda *args: None, code_hashes=lambda: code,
        checkpoint_rows=lambda a: [dict(r) for r in a["checkpoint"]["rows"]])
    monkeypatch.setattr(caller, "parent_trial", fake_parent)
    monkeypatch.setattr(caller, "PARENT_LEDGER", ledger)
    monkeypatch.setattr(caller, "PARENT_OUTPUT", output)
    monkeypatch.setattr(caller, "PARENT_APPROVAL_PATH", tmp_path / "approval.json")
    monkeypatch.setattr(caller, "process_absent", lambda pid: True)
    monkeypatch.setattr(caller, "PARENT_INPUT_TOKENS", 9000)
    monkeypatch.setattr(caller, "PARENT_OUTPUT_TOKENS", 9000)
    monkeypatch.setattr(caller, "PARENT_COST_MICROUSD", 25200)
    monkeypatch.setattr(caller, "OLD_COST_MICROUSD", 39644)
    fields = {"authorization_id": auth, "approval_sha256": caller.PARENT_APPROVAL_SHA,
              "checkpoint_binding_sha256": base["checkpoint"]["binding_sha256"],
              "request_roster_sha256": base["request_roster_sha256"], "pid": 123}
    for role in ("execute", "run"):
        caller.write_new(ledger / f"{auth}.{role}-claim.json", fields)
    caller.write_new(ledger / f"{auth}.launch-claim.json", {
        "authorization_id": auth, "approval_sha256": caller.PARENT_APPROVAL_SHA,
        "approval_file": str(caller.PARENT_APPROVAL_PATH), "output_dir": str(output),
        "launcher_sha256": "a" * 64})
    caller.write_new(output.with_name(output.name + ".resource-process.json"), {
        "approval_sha256": caller.PARENT_APPROVAL_SHA, "cpus": 4, "memory_bytes": 2147483648,
        "timeout_seconds": 9000, "kill_tree_on_close": True, "worker_pid": 124})
    caller.write_new(output.with_name(output.name + ".launch-process.json"), {
        "approval_sha256": caller.PARENT_APPROVAL_SHA, "output_dir": str(output), "supervisor_pid": 125})
    all_rows = fake_parent.checkpoint_rows(base); bindings = {}
    indexed = {r["group_id"]: r for r in base["requests"]}
    for ordinal, gid in enumerate(caller.PARENT_GROUPS):
        request = indexed[gid]
        claim = {**fields, "group_id": gid, "rest_sha256": request["rest_sha256"],
            "started_epoch_ms": 100000 + ordinal * 200000,
            "reserved_microusd": caller.cost(caller.MAX_INPUT, caller.MAX_OUTPUT)}
        caller.write_new(ledger / f"{auth}-{gid}.claim.json", claim)
        if gid in caller.FAILED_GROUPS:
            row = {"group_id": gid, "state": "failed", "selected_ids": [], "question_status": None}
            verdict = usage = None; failure = "provider_http_503"
        else:
            verdict, _ = caller.calibration.parse_response(success(base, gid))
            row = {"group_id": gid, "state": "completed", "selected_ids": verdict["selected_ids"],
                "question_status": verdict["question_status"]}
            usage = {"input": 1000, "output": 1000}; failure = None
        receipt = {**row, "request_sha256": request["rest_sha256"],
            "attempt_claim_sha256": caller.digest(caller.canonical(claim)), "latency_ms": 1000,
            "reported_usage": usage, "known_cost_microusd": 2800 if usage else None,
            "failure_code": failure, "verdict": verdict}
        caller.write_new(output / f"attempt-{gid}.json", receipt)
        bindings[gid] = {"claim_sha256": caller.digest(caller.canonical(claim)),
                        "receipt_sha256": caller.digest(caller.canonical(receipt))}
        all_rows.append(row)
    all_rows.sort(key=lambda r: r["group_id"])
    report = {"schema": "public_visual_heldout_v2_interrupted_observation", "status": "interrupted_processes_absent",
        "approval_sha256": caller.PARENT_APPROVAL_SHA, "request_roster_sha256": base["request_roster_sha256"],
        "checkpoint_binding_sha256": base["checkpoint"]["binding_sha256"], "caller_code_sha256": code,
        "new_physical_claims": 11, "new_receipts": 11, "valid_new_responses": 9, "evaluated_groups": 14,
        "all_physical_attempts": 17, "in_flight_claims_without_receipt": 0, "new_known_cost_microusd": 25200,
        "inherited_known_cost_microusd": 14444, "new_reported_input_tokens": 9000,
        "new_reported_output_tokens": 9000, "new_unknown_cost_attempts": 2, "prior_unknown_cost_attempts": 3,
        "failures": {g: "provider_http_503" for g in caller.FAILED_GROUPS},
        "resume_permitted": False, "provider_restarted": False, "ask_enabled": False, "private_data_sent": False,
        "release_passed": False, "receipts": bindings,
        "partial_score": caller.scorer.evaluate(base["overlay"], all_rows, base["expected_ids"]),
        "ceiling": caller.scorer.ceiling(base["overlay"], all_rows, base["expected_ids"])}
    path = tmp_path / "observation.json"; caller.write_new(path, report)
    monkeypatch.setattr(caller, "PARENT_REPORT_PATH", path)
    monkeypatch.setattr(caller, "PARENT_REPORT_SHA", caller.digest(caller.canonical(report)))
    return base, report, ledger, output


def test_all14_observed_rows_and17_physical_attempts_bound(parent_files):
    base, _, ledger, output = parent_files
    before = {p: p.read_bytes() for p in [*ledger.iterdir(), *output.iterdir()]}
    checkpoint = caller.admit_checkpoint(base)
    assert tuple(r["group_id"] for r in checkpoint["rows"]) == caller.OBSERVED_GROUPS
    assert checkpoint["binding"]["inherited_failures"] == ["Q013", "Q014"]
    assert checkpoint["binding"]["prior_physical_attempts"] == 17
    assert before == {p: p.read_bytes() for p in before}


def test_still_live_parent_rejects_source_reuse(parent_files, monkeypatch):
    base, _, _, _ = parent_files
    monkeypatch.setattr(caller, "process_absent", lambda pid: False)
    with pytest.raises(caller.PilotError, match="parent_process_still_live"):
        caller.admit_checkpoint(base)


@pytest.mark.parametrize("mutation", ["extra_claim", "extra_receipt", "terminal_result"])
def test_ambiguous_or_new_parent_attempt_not_dropped(parent_files, mutation):
    base, _, ledger, output = parent_files
    if mutation == "extra_claim":
        caller.write_new(ledger / "invented_consumed_v2-Q015.claim.json", {})
    elif mutation == "extra_receipt": caller.write_new(output / "attempt-Q015.json", {})
    else: caller.write_new(output / "result.json", {})
    with pytest.raises(caller.PilotError, match="parent_physical_attempt_roster_changed|parent_terminal_state_changed"):
        caller.admit_checkpoint(base)


def test_rebound_failed_receipt_cannot_become_success(parent_files, monkeypatch):
    base, report, _, output = parent_files
    receipt_path = output / "attempt-Q014.json"
    receipt = json.loads(receipt_path.read_bytes()); receipt["state"] = "completed"
    receipt_path.write_bytes(caller.canonical(receipt))
    report["receipts"]["Q014"]["receipt_sha256"] = caller.digest(caller.canonical(receipt))
    caller.PARENT_REPORT_PATH.write_bytes(caller.canonical(report))
    monkeypatch.setattr(caller, "PARENT_REPORT_SHA", caller.digest(caller.canonical(report)))
    with pytest.raises(caller.PilotError, match="parent_failure_changed"):
        caller.admit_checkpoint(base)


@pytest.mark.parametrize("field,value,code", [
    ("known_cost_microusd", 0, "parent_usage_changed"),
    ("request_sha256", "b" * 64, "parent_attempt_changed"),
    ("selected_ids", [], "parent_valid_verdict_changed"),
])
def test_semantically_rebound_valid_receipt_is_rejected(parent_files, monkeypatch, field, value, code):
    base, report, _, output = parent_files
    path = output / "attempt-Q003.json"
    receipt = json.loads(path.read_bytes()); receipt[field] = value
    path.write_bytes(caller.canonical(receipt))
    report["receipts"]["Q003"]["receipt_sha256"] = caller.digest(caller.canonical(receipt))
    caller.PARENT_REPORT_PATH.write_bytes(caller.canonical(report))
    monkeypatch.setattr(caller, "PARENT_REPORT_SHA", caller.digest(caller.canonical(report)))
    with pytest.raises(caller.PilotError, match=code):
        caller.admit_checkpoint(base)


def test_approval_binds_all_checkpoint_and_code_fields(monkeypatch):
    a = admitted(); monkeypatch.setattr(caller, "code_hashes", lambda: {"synthetic": "a" * 64})
    receipt = copy.deepcopy(caller.expected_approval(a))
    monkeypatch.setattr(caller, "read_bound", lambda *args, **kwargs: receipt)
    caller.validate_approval(Path("synthetic"), "a" * 64, a)
    a["checkpoint"]["binding"]["parent_report_sha256"] = "b" * 64
    with pytest.raises(caller.PilotError, match="approval_contract_changed"):
        caller.validate_approval(Path("synthetic"), "a" * 64, a)
