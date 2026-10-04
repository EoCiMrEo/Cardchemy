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
import run_visual_public_heldout_v4 as caller
import launch_visual_public_heldout_v4 as launcher
from test_visual_public_heldout_v1_score import fixture
from test_visual_public_calibration_v2_caller import Clock, response



def source_fixture():
    overlay, _, expected = fixture()
    swaps = {f"Q{a:03d}": f"Q{b:03d}" for a, b in zip(range(1, 6), range(29, 34))}
    swaps.update({value: key for key, value in list(swaps.items())})
    for row in overlay:
        row["group_id"] = swaps.get(row["group_id"], row["group_id"])
    # This is an issued, exact page whose independent review is unresolved.
    for row in overlay:
        if (row["group_id"], row["candidate_id"]) == ("Q021", "S04"):
            row["qualification"] = "Unsure"
    outcomes = []
    for gid in expected:
        good = [row["candidate_id"] for row in overlay if row["group_id"] == gid and row["qualification"] == "Yes"]
        selected = good[:3 if gid in tuple(f"Q{n:03d}" for n in range(1, 6)) else 2 if gid in ("Q015", "Q016") else 1]
        if gid == "Q021": selected.append("S04")
        outcomes.append({"group_id": gid, "state": "completed", "question_status": "clear", "selected_ids": selected})
    for row in outcomes:
        if row["group_id"] in caller.FAILED_GROUPS:
            row.update(state="failed", selected_ids=[], question_status=None)
    return overlay, outcomes, expected


def admitted():
    overlay, original, expected = source_fixture()
    rows = [dict(row) for row in original[:21]]
    requests = [{"group_id": gid, "path": f"{gid}.json", "wire_sha256": "a" * 64,
                 "rest_sha256": caller.digest(b"synthetic"), "rest_bytes": 9} for gid in caller.NEW_GROUPS]
    binding = {"parent_report_sha256": caller.PARENT_REPORT_SHA, "parent_result_sha256": caller.PARENT_RESULT_SHA,
        "parent_approval_sha256": caller.PARENT_APPROVAL_SHA, "inherited_failures": list(caller.FAILED_GROUPS),
        "rows_sha256": caller.digest(caller.canonical(rows)), "parent_cooldown_until_epoch_ms": 0,
        "prospective_scorer_contract": caller.scorer.SCHEMA_VERSION, "review_unknown_credit": 0,
        "historical_trial_stays_stopped": True}
    checkpoint = {"rows": rows, "receipts": {gid: {} for gid in caller.PARENT_GROUPS},
        "prior_checkpoint": {"historical_physical_attempts": 17},
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
    assert guards["max_calls"] == 39 and guards["input_total"] == 1277952 and guards["output_total"] == 159744
    assert guards["new_cost_cap_microusd"] == 850000 and 39 * caller.cost(32768, 4096) == 782769
    assert guards["inherited_valid_responses"] == 19 and guards["inherited_failed_groups"] == 2
    assert guards["prior_physical_attempts"] == 24 and guards["prior_unknown_cost_attempts"] == 5
    assert guards["manual_failed_reattempts"] == guards["retries"] == 0
    assert guards["minimum_valid_responses"] == 58 and guards["maximum_failed_groups"] == 2


def test_no_arguments_is_inert_before_any_admission(monkeypatch):
    monkeypatch.setattr(caller, "LIVE_AUTHORIZED", False)
    monkeypatch.setattr(caller.sys, "argv", ["inert-caller"])
    monkeypatch.setattr(caller, "admit", lambda: pytest.fail("no input admission"))
    with pytest.raises(SystemExit) as stopped:
        caller.main()
    assert stopped.value.code == 2


def test_all39_untouched_calls_keep21_outcomes_and24_old_physical_attempts(tmp_path, monkeypatch):
    a = admitted(); before = copy.deepcopy(a)
    out, ledger = setup(tmp_path, monkeypatch); clock, starts, ids = Clock(), [], []
    async def send(body):
        starts.append(clock.now); gid = a["requests"][len(starts) - 1]["group_id"]; ids.append(gid)
        return success(a, gid)
    result = asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger, clock=clock, sleep=clock.sleep))
    assert a == before and tuple(ids) == caller.NEW_GROUPS
    assert result["provider_calls"] == 39 and result["evaluated_group_attempts"] == 60
    assert result["total_physical_provider_calls"] == 63 and result["historical_physical_attempts"] == 24
    assert result["score"]["heldout_passed"] and result["score"]["metrics"]["valid_responses"] == 58
    assert result["score"]["metrics"]["failed_groups"] == 2
    assert result["prior_unknown_cost_attempts"] == 5
    assert result["combined_known_cost_microusd"] == result["known_cost_microusd"] + 112666
    observed = json.loads((out / "progress.json").read_bytes())
    assert observed["inherited_physical_provider_calls"] == 24
    assert observed["inherited_evaluated_groups"] == 21
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
    assert result["evaluated_group_attempts"] == 22 and result["total_physical_provider_calls"] == 25
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


@pytest.mark.parametrize("field,value", [("group_id", "Q021"), ("group_id", "Q061"), ("rest_sha256", "b" * 64)])
def test_changed_or_reattempted_request_roster_rejected(tmp_path, monkeypatch, field, value):
    a = admitted(); a["requests"][0][field] = value
    out, ledger = setup(tmp_path, monkeypatch)
    async def send(body): pytest.fail("no provider")
    with pytest.raises(caller.PilotError, match="physical_attempt_roster_invalid|request_changed"):
        asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger))


def test_corrupted_inherited_failure_cannot_become_valid(tmp_path, monkeypatch):
    a = admitted(); a["checkpoint"]["rows"][12].update(state="completed", question_status="clear")
    out, ledger = setup(tmp_path, monkeypatch)
    async def send(body): pytest.fail("no provider")
    with pytest.raises(caller.PilotError, match="checkpoint_binding_changed"):
        asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger))
    assert not list(ledger.iterdir())


def test_foreground_launcher_inert_and_environment_contains_no_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(caller, "LIVE_AUTHORIZED", False)
    monkeypatch.setattr(launcher.audited.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("no child"))
    with pytest.raises(caller.visual.PreparationError, match="fresh_provider_authorization_required"):
        launcher.supervise(tmp_path / "approval.json", "a" * 64, tmp_path / "output")
    env = launcher.child_env({"SystemRoot": "C:/Windows", "RAG_SOURCE_JUDGE_API_KEY": "forbidden",
        "HTTP_PROXY": "forbidden", "DATABASE_URL": "forbidden"})
    assert "forbidden" not in env.values() and launcher.MAX_SECONDS == 9000
    assert not hasattr(launcher, "detach")




def test_preserved_unknown_still_counts_as_one_nonuseful_card():
    packet = admitted()
    score = caller.scorer.evaluate(packet["overlay"], caller.checkpoint_rows(packet), packet["expected_ids"])
    assert score["metrics"]["unknown_displayed_cards"] == 1
    assert score["metrics"]["useful_displayed_cards"] == 31
    assert score["metrics"]["all_displayed_cards"] == 32
    assert caller.scorer.ceiling(packet["overlay"], caller.checkpoint_rows(packet), packet["expected_ids"])["quality_reachable"]
    assert not caller.parent_trial.scorer.ceiling(packet["overlay"], caller.checkpoint_rows(packet), packet["expected_ids"])["quality_reachable"]


@pytest.mark.parametrize("pid,match", [(123, True), (124, True), (999, False), (True, False), (-1, False)])
def test_resource_pid_accepts_only_current_or_direct_venv_parent(pid, match, monkeypatch):
    simulated_os = SimpleNamespace(**(vars(caller.os) | {
        "getpid": lambda: 123, "getppid": lambda: 124, "name": "nt"}))
    monkeypatch.setattr(caller, "os", simulated_os)
    assert caller.resource_worker_pid_matches(pid) is match


def test_invalid_resource_receipt_rejects_before_inputs_or_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(caller, "LIVE_AUTHORIZED", True)
    monkeypatch.setattr(caller.visual, "_inside_windows_job", lambda: True)
    monkeypatch.setattr(caller, "read_existing", lambda path: ({"worker_pid": 999}, "a" * 64))
    monkeypatch.setattr(caller, "admit", lambda: pytest.fail("source admission must follow resource receipt"))
    monkeypatch.setattr(caller.previous, "read_key", lambda: pytest.fail("key touched"))
    with pytest.raises(caller.PilotError, match="resource_receipt_invalid"):
        asyncio.run(caller.execute({}, "a" * 64, tmp_path, approval_file=tmp_path / "approval.json"))


def test_approval_binds_all_checkpoint_and_code_fields(monkeypatch):
    packet = admitted()
    monkeypatch.setattr(caller, "code_hashes", lambda: {"synthetic": "a" * 64})
    receipt = copy.deepcopy(caller.expected_approval(packet))
    monkeypatch.setattr(caller, "read_bound", lambda *args, **kwargs: receipt)
    caller.validate_approval(Path("synthetic"), "a" * 64, packet)
    packet["checkpoint"]["binding"]["review_unknown_credit"] = 1
    with pytest.raises(caller.PilotError, match="approval_contract_changed"):
        caller.validate_approval(Path("synthetic"), "a" * 64, packet)


@pytest.fixture
def checkpoint_files(tmp_path, monkeypatch):
    overlay, outcomes, expected = source_fixture()
    ledger, output = tmp_path / "ledger", tmp_path / "output"
    ledger.mkdir(); output.mkdir()
    requests = [{"group_id": gid, "path": f"{gid}.json", "wire_sha256": "a" * 64,
                 "rest_sha256": caller.digest(b"synthetic"), "rest_bytes": 9}
                for gid in tuple(f"Q{n:03d}" for n in range(15, 61))]
    prior = {"binding": {"observed": 14}, "binding_sha256": "b" * 64,
             "rows": outcomes[:14], "receipts": {"prior": "kept"}, "prior_receipts": {"first": "kept"}}
    base = {"overlay": overlay, "expected_ids": expected, "requests": requests, "checkpoint": prior,
            "calibration_binding": {"passed": True}, "request_roster_sha256": caller.digest(caller.canonical(requests))}
    auth = "invented_consumed_v3"
    code = {"scripts/launch_visual_public_heldout_v3.py": "a" * 64}
    parent = SimpleNamespace(AUTHORIZATION_ID=auth, validate_approval=lambda *args: None,
        code_hashes=lambda: code, checkpoint_rows=lambda packet: [dict(row) for row in packet["checkpoint"]["rows"]],
        scorer=caller.scorer.historical)
    monkeypatch.setattr(caller, "parent_trial", parent)
    monkeypatch.setattr(caller, "PARENT_LEDGER", ledger)
    monkeypatch.setattr(caller, "PARENT_OUTPUT", output)
    monkeypatch.setattr(caller, "PARENT_APPROVAL_PATH", tmp_path / "approval.json")
    monkeypatch.setattr(caller, "PARENT_RESULT_PATH", output / "result.json")
    monkeypatch.setattr(caller, "PARENT_REPORT_PATH", tmp_path / "report.json")
    monkeypatch.setattr(caller, "process_absent", lambda pid: True)
    monkeypatch.setattr(caller, "PARENT_INPUT_TOKENS", 7000)
    monkeypatch.setattr(caller, "PARENT_OUTPUT_TOKENS", 7000)
    monkeypatch.setattr(caller, "PARENT_COST_MICROUSD", 19600)
    monkeypatch.setattr(caller, "OLD_COST_MICROUSD", 92054)
    fields = {"authorization_id": auth, "approval_sha256": caller.PARENT_APPROVAL_SHA,
        "request_roster_sha256": base["request_roster_sha256"],
        "checkpoint_binding_sha256": prior["binding_sha256"], "pid": 123}
    for role in ("execute", "run"):
        caller.write_new(ledger / f"{auth}.{role}-claim.json", fields)
    caller.write_new(ledger / f"{auth}.launch-claim.json", {
        "authorization_id": auth, "approval_sha256": caller.PARENT_APPROVAL_SHA,
        "approval_file": str(caller.PARENT_APPROVAL_PATH), "output_dir": str(output),
        "launcher_sha256": "a" * 64, "supervisor_pid": 124})
    caller.write_new(output.with_name(output.name + ".resource-process.json"), {
        "approval_sha256": caller.PARENT_APPROVAL_SHA, "cpus": 4, "memory_bytes": 2147483648,
        "timeout_seconds": 9000, "kill_tree_on_close": True, "worker_pid": 125})
    caller.write_new(output.with_name(output.name + ".supervisor-complete.json"), {
        "approval_sha256": caller.PARENT_APPROVAL_SHA, "exit_code": 0, "resume_permitted": False})
    bindings, hashes = {}, {}
    indexed = {request["group_id"]: request for request in requests}
    for ordinal, gid in enumerate(caller.PARENT_GROUPS):
        selected = outcomes[int(gid[1:]) - 1]["selected_ids"]
        claim = {**fields, "group_id": gid, "rest_sha256": indexed[gid]["rest_sha256"],
            "started_epoch_ms": 100000 + ordinal * 30000,
            "reserved_microusd": caller.cost(caller.MAX_INPUT, caller.MAX_OUTPUT)}
        caller.write_new(ledger / f"{auth}-{gid}.claim.json", claim)
        verdict, _ = caller.calibration.parse_response(httpx.Response(200, json=response([
            "direct" if sid in selected else "unrelated" for sid in caller.ISSUED])))
        receipt = {"group_id": gid, "state": "completed", "selected_ids": verdict["selected_ids"],
            "question_status": "clear", "request_sha256": indexed[gid]["rest_sha256"],
            "attempt_claim_sha256": caller.digest(caller.canonical(claim)), "latency_ms": 1000,
            "reported_usage": {"input": 1000, "output": 1000}, "known_cost_microusd": 2800,
            "failure_code": None, "verdict": verdict}
        caller.write_new(output / f"attempt-{gid}.json", receipt)
        hashes[gid] = caller.digest(caller.canonical(receipt))
        bindings[gid] = {"receipt_sha256": hashes[gid], "claim_sha256": caller.digest(caller.canonical(claim))}
    score = parent.scorer.evaluate(overlay, outcomes[:21], expected)
    ceiling = parent.scorer.ceiling(overlay, outcomes[:21], expected)
    result = {"schema_version": "public_visual_heldout_v3_result", "authorization_id": auth,
        "approval_sha256": caller.PARENT_APPROVAL_SHA, "status": "stopped", "reason": "quality_unreachable",
        "provider_calls": 7, "evaluated_group_attempts": 21, "total_physical_provider_calls": 24,
        "historical_physical_attempts": 17, "request_roster_sha256": base["request_roster_sha256"],
        "checkpoint_binding": prior["binding"], "inherited_receipts": prior["receipts"],
        "first_trial_valid_receipts": prior["prior_receipts"], "calibration_binding": base["calibration_binding"],
        "input_freeze_sha256": caller.INPUT_FREEZE_SHA, "qualification_freeze_sha256": caller.QUALIFICATION_FREEZE_SHA,
        "known_cost_microusd": 19600, "combined_known_cost_microusd": 92054,
        "unknown_cost_attempts": 0, "prior_unknown_cost_attempts": 5,
        "reported_input_tokens": 7000, "reported_output_tokens": 7000,
        "old_trial_remains_failed": True, "resume_permitted": False, "ask_enabled": False,
        "private_data_sent": False, "receipt_hashes": hashes, "score": score, "ceiling": ceiling}
    report = {"schema": "public_visual_heldout_v3_terminal_observation", "approval_sha256": caller.PARENT_APPROVAL_SHA,
        "terminal_result_sha256": caller.digest(caller.canonical(result)), "provider_calls": 7,
        "new_valid_responses": 7, "new_failures": 0, "new_unknown_cost_attempts": 0, "selected_unissued_ids": 0,
        "evaluated_groups": 21, "all_historical_physical_attempts": 24, "untouched_questions": 39,
        "new_known_cost_microusd": 19600, "new_input_tokens": 7000, "new_output_tokens": 7000,
        "prior_unknown_cost_attempts": 5, "all_displayed_cards": 32, "useful_displayed_cards": 31,
        "zero_credit_unsure_cards": 1, "terminal_reason": "unknown_displayed_zero",
        "parent_checkpoint_binding_sha256": prior["binding_sha256"],
        "request_roster_sha256": base["request_roster_sha256"], "caller_code_sha256": code,
        "old_trial_stays_stopped": True, "resume_permitted": False, "release_passed": False, "receipts": bindings}
    caller.write_new(caller.PARENT_RESULT_PATH, result)
    caller.write_new(caller.PARENT_REPORT_PATH, report)
    monkeypatch.setattr(caller, "PARENT_RESULT_SHA", caller.digest(caller.canonical(result)))
    monkeypatch.setattr(caller, "PARENT_REPORT_SHA", caller.digest(caller.canonical(report)))
    return base, result, report, output, ledger


def test_full_parent_chain_keeps_unsure_errors_and_twenty_four_attempts(checkpoint_files):
    base, _, _, output, ledger = checkpoint_files
    preserved = {path: path.read_bytes() for path in [*output.iterdir(), *ledger.iterdir()]}
    checkpoint = caller.admit_checkpoint(base)
    assert tuple(row["group_id"] for row in checkpoint["rows"]) == caller.OBSERVED_GROUPS
    assert checkpoint["binding"]["inherited_failures"] == ["Q013", "Q014"]
    assert checkpoint["binding"]["prior_physical_attempts"] == 24
    assert checkpoint["binding"]["review_unknown_credit"] == 0
    assert checkpoint["binding"]["historical_trial_stays_stopped"]
    assert all(path.read_bytes() == raw for path, raw in preserved.items())


@pytest.mark.parametrize("kind", ["extra_claim", "extra_receipt", "still_live", "supervisor_failure", "manifest"])
def test_unaccounted_or_live_or_rebound_parent_cannot_be_admitted(checkpoint_files, monkeypatch, kind):
    base, result, report, output, ledger = checkpoint_files
    if kind == "extra_claim": caller.write_new(ledger / "invented_consumed_v3-Q022.claim.json", {})
    elif kind == "extra_receipt": caller.write_new(output / "attempt-Q022.json", {})
    elif kind == "still_live": monkeypatch.setattr(caller, "process_absent", lambda pid: False)
    elif kind == "supervisor_failure":
        path = output.with_name(output.name + ".supervisor-complete.json")
        path.write_bytes(caller.canonical({"approval_sha256": caller.PARENT_APPROVAL_SHA,
                                         "exit_code": 2, "resume_permitted": False}))
    else:
        report["caller_code_sha256"] = {}
        caller.PARENT_REPORT_PATH.write_bytes(caller.canonical(report))
        monkeypatch.setattr(caller, "PARENT_REPORT_SHA", caller.digest(caller.canonical(report)))
    with pytest.raises(caller.PilotError, match="parent_"):
        caller.admit_checkpoint(base)


@pytest.mark.parametrize("field,value,reason", [
    ("request_sha256", "b" * 64, "parent_attempt_changed"),
    ("known_cost_microusd", 0, "parent_usage_changed"),
    ("selected_ids", [], "parent_valid_verdict_changed"),
])
def test_newly_sha_bound_receipt_still_needs_unchanged_semantics(checkpoint_files, monkeypatch, field, value, reason):
    base, result, report, output, _ = checkpoint_files
    path = output / "attempt-Q021.json"
    receipt = json.loads(path.read_bytes()); receipt[field] = value
    path.write_bytes(caller.canonical(receipt))
    sha = caller.digest(caller.canonical(receipt))
    report["receipts"]["Q021"]["receipt_sha256"] = result["receipt_hashes"]["Q021"] = sha
    caller.PARENT_RESULT_PATH.write_bytes(caller.canonical(result))
    report["terminal_result_sha256"] = caller.digest(caller.canonical(result))
    caller.PARENT_REPORT_PATH.write_bytes(caller.canonical(report))
    monkeypatch.setattr(caller, "PARENT_RESULT_SHA", report["terminal_result_sha256"])
    monkeypatch.setattr(caller, "PARENT_REPORT_SHA", caller.digest(caller.canonical(report)))
    with pytest.raises(caller.PilotError, match=reason):
        caller.admit_checkpoint(base)


def test_historical_failed_trial_must_not_be_regraded_as_complete(checkpoint_files, monkeypatch):
    base, result, report, _, _ = checkpoint_files
    result["status"] = "complete"
    caller.PARENT_RESULT_PATH.write_bytes(caller.canonical(result))
    report["terminal_result_sha256"] = caller.digest(caller.canonical(result))
    caller.PARENT_REPORT_PATH.write_bytes(caller.canonical(report))
    monkeypatch.setattr(caller, "PARENT_RESULT_SHA", report["terminal_result_sha256"])
    monkeypatch.setattr(caller, "PARENT_REPORT_SHA", caller.digest(caller.canonical(report)))
    with pytest.raises(caller.PilotError, match="parent_terminal_binding_changed"):
        caller.admit_checkpoint(base)
