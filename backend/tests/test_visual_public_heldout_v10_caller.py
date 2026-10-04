"""Invented v10 receipts/transports; no source, credential or HTTP execution."""
import asyncio
import copy
import json
from pathlib import Path
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import run_visual_public_heldout_v10 as caller
import launch_visual_public_heldout_v10 as launcher
from test_visual_public_heldout_v4_caller import source_fixture
from test_visual_public_calibration_v2_caller import Clock, response


@pytest.fixture(autouse=True)
def injected_inert_authority(monkeypatch):
    # Routine tests use invented disabled authority, never the approved live
    # envelope or operator inputs/credentials.
    monkeypatch.setattr(caller, "LIVE_AUTHORIZED", False)
    monkeypatch.setattr(caller, "APPROVAL_REPLY", "PENDING_EXACT_5_REQUEST_PROVIDER_APPROVAL")


def admitted():
    overlay, outcomes, expected = source_fixture()
    observed = copy.deepcopy(outcomes[:56])
    observed[-1].update(state="failed", selected_ids=[], question_status=None)
    rows = [copy.deepcopy(row) for row in observed if row["group_id"] != "Q056"]
    requests = [{"group_id": gid, "path": f"{gid}.json", "wire_sha256": "a" * 64,
                 "rest_sha256": caller.digest(b"synthetic"), "rest_bytes": 9} for gid in caller.NEW_GROUPS]
    binding = {"parent_report_sha256": caller.PARENT_REPORT_SHA,
        "parent_result_sha256": caller.PARENT_RESULT_SHA, "parent_approval_sha256": caller.PARENT_APPROVAL_SHA,
        "inherited_failures": list(caller.FAILED_GROUPS), "manual_failed_group_ids": ["Q056"],
        "all_observed_rows_sha256": caller.digest(caller.canonical(observed)),
        "rows_sha256": caller.digest(caller.canonical(rows)), "parent_cooldown_until_epoch_ms": 0,
        "historical_trial_stays_stopped": True, "historical_physical_attempts": 64,
        "superseded_failed_outcomes": [copy.deepcopy(observed[-1])]}
    checkpoint = {"rows": rows, "all_observed_rows": observed,
        "receipts": {gid: {"group_id": gid} for gid in caller.PARENT_GROUPS},
        "prior_checkpoint": {"preserved_physical_attempts": 24},
        "binding": binding, "binding_sha256": caller.digest(caller.canonical(binding))}
    return {"overlay": overlay, "expected_ids": expected, "requests": requests,
        "known_images": set(), "checkpoint": checkpoint,
        "process_identity_binding": {"invented": "proof"}, "process_identity_binding_sha256": "b" * 64,
        "request_roster_sha256": caller.digest(caller.canonical(requests)), "calibration_binding": {"passed": True}}


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(caller, "read_bound", lambda *args, **kwargs: {})
    monkeypatch.setattr(caller, "rest_body", lambda *args: b"synthetic")
    out, ledger = tmp_path / "out", tmp_path / "ledger"
    out.mkdir(); ledger.mkdir()
    return out, ledger


def success(packet, gid):
    useful = {r["candidate_id"] for r in packet["overlay"]
              if r["group_id"] == gid and r["qualification"] == "Yes"}
    return httpx.Response(200, json=response(["direct" if sid in useful else "unrelated" for sid in caller.ISSUED]))


def run(packet, out, ledger, send, clock):
    return asyncio.run(caller.run(packet, "a" * 64, out, send, ledger=ledger, clock=clock, sleep=clock.sleep))


def test_live_fence_precedes_all_resources_inputs_credentials(tmp_path, monkeypatch):
    assert caller.LIVE_AUTHORIZED is False
    assert caller.APPROVAL_REPLY == "PENDING_EXACT_5_REQUEST_PROVIDER_APPROVAL"
    monkeypatch.setattr(caller.visual, "_inside_windows_job", lambda: pytest.fail("resource touched"))
    monkeypatch.setattr(caller, "admit", lambda: pytest.fail("source touched"))
    monkeypatch.setattr(caller.previous, "read_key", lambda: pytest.fail("key touched"))
    with pytest.raises(caller.PilotError, match="precise_provider_envelope_not_authorized"):
        asyncio.run(caller.execute({}, "a" * 64, tmp_path))
    monkeypatch.setattr(launcher.audited.subprocess, "Popen", lambda *a, **kw: pytest.fail("child launched"))
    with pytest.raises(caller.visual.PreparationError, match="fresh_provider_authorization_required"):
        launcher.supervise(tmp_path / "approval.json", "a" * 64, tmp_path / "output")


def test_no_mode_is_inert(monkeypatch):
    monkeypatch.setattr(caller.sys, "argv", ["inert-caller"])
    monkeypatch.setattr(caller, "admit", lambda: pytest.fail("inputs touched"))
    with pytest.raises(SystemExit) as stopped:
        caller.main()
    assert stopped.value.code == 2


def test_frozen_guards_and_isolated_child_environment():
    guards = caller.guards()
    assert guards["max_calls"] == 5 and guards["call_seconds"] == 120
    assert guards["input_total"] == 163840 and guards["output_total"] == 20480
    assert guards["new_cost_cap_microusd"] == 110000
    assert 5 * caller.cost(32768, 4096) == 100355
    assert guards["prior_physical_attempts"] == 64 and guards["prior_unknown_cost_attempts"] == 8
    assert guards["manual_failed_reattempts"] == 1 and guards["manual_group_ids"] == ["Q056"]
    assert guards["inherited_evaluated_groups"] == 56 and guards["active_inherited_outcomes"] == 55
    assert guards["inherited_valid_responses"] == 53 and guards["inherited_failed_groups"] == 2
    assert guards["minimum_valid_responses"] == 58 and guards["maximum_failed_groups"] == 2
    assert guards["retries"] == 0 and not guards["live_authorized"]
    env = launcher.child_env({"SystemRoot": "C:/Windows", "RAG_SOURCE_JUDGE_API_KEY": "never",
        "DATABASE_URL": "never", "HTTP_PROXY": "never"})
    assert "never" not in env.values() and launcher.MAX_SECONDS == 9000
    assert not hasattr(launcher, "detach")


def test_growing_local_metadata_is_bounded_without_changing_provider_caps(tmp_path):
    content = {"invented_metadata": "x" * 120000}
    path = tmp_path / "local.json"
    raw = caller.canonical(content); path.write_bytes(raw)
    assert caller.read_bound(path, caller.digest(raw)) == content
    assert caller.MAX_RESPONSE == 65536 and caller.visual.MAX_REQUEST_BYTES == 6 * 1024 * 1024
    with pytest.raises(caller.PilotError, match="bound_file_changed"):
        caller.read_bound(path, "b" * 64)
    with pytest.raises(caller.PilotError, match="bound_file_changed"):
        caller.read_bound(path, caller.digest(raw), 100000)
    raw = caller.canonical({"invented_metadata": "x" * caller.LOCAL_METADATA_BYTES})
    path.write_bytes(raw)
    with pytest.raises(caller.PilotError, match="bound_file_changed"):
        caller.read_bound(path, caller.digest(raw))


def test_all5_calls_yield60_scored_outcomes_and69_historical_attempts(tmp_path, monkeypatch):
    packet = admitted(); before = copy.deepcopy(packet)
    out, ledger = setup(tmp_path, monkeypatch); clock, ids, starts = Clock(), [], []
    async def send(body):
        gid = packet["requests"][len(ids)]["group_id"]
        ids.append(gid); starts.append(clock.now)
        return success(packet, gid)
    result = run(packet, out, ledger, send, clock)
    assert packet == before and tuple(ids) == caller.NEW_GROUPS
    assert ids[0] == "Q056" and ids[-1] == "Q060" and len(ids) == len(set(ids)) == 5
    assert result["provider_calls"] == 5 and result["evaluated_group_attempts"] == 60
    assert result["total_physical_provider_calls"] == 69 and result["historical_physical_attempts"] == 64
    assert result["score"]["heldout_passed"] and result["score"]["metrics"]["valid_responses"] == 58
    assert result["score"]["metrics"]["failed_groups"] == 2
    assert result["score"]["metrics"]["unknown_displayed_cards"] == 1
    assert result["combined_known_cost_microusd"] == result["known_cost_microusd"] + 322399
    assert result["prior_unknown_cost_attempts"] == 8
    assert result["checkpoint_binding"]["superseded_failed_outcomes"] == [before["checkpoint"]["all_observed_rows"][-1]]
    assert result["inherited_receipts"]["Q056"] == {"group_id": "Q056"}
    assert not result["resume_permitted"] and not result["ask_enabled"] and result["old_trial_remains_failed"]
    assert all(b - a >= 30 for a, b in zip(starts, starts[1:]))
    assert len(list(ledger.glob(caller.AUTHORIZATION_ID + "-Q*.claim.json"))) == 5
    assert set(json.loads((out / "attempt-Q056.json").read_bytes())) == caller.RECEIPT_FIELDS
    with pytest.raises(FileExistsError):
        run(packet, out, ledger, send, clock)


@pytest.mark.parametrize("failure", ["timeout", "503", "unfinished", "bad_verdict"])
def test_first_new_failure_stops_without_retry(tmp_path, monkeypatch, failure):
    packet = admitted(); out, ledger = setup(tmp_path, monkeypatch); clock, calls = Clock(), []
    async def send(body):
        calls.append(body)
        if failure == "timeout": raise httpx.ReadTimeout("not retained")
        if failure == "503": return httpx.Response(503, content=b"not retained")
        value = response(["unrelated"] * 4)
        if failure == "unfinished": value["candidates"][0]["finishReason"] = "MAX_TOKENS"
        else: value["candidates"][0]["content"]["parts"][0]["text"] = "{}"
        return httpx.Response(200, json=value)
    result = run(packet, out, ledger, send, clock)
    assert len(calls) == result["provider_calls"] == 1
    assert result["evaluated_group_attempts"] == 56 and result["total_physical_provider_calls"] == 65
    assert result["status"] == "stopped" and result["reason"] == "quality_unreachable"
    assert result["ceiling"]["upper_bounds"]["valid_responses"] == 57
    receipt = json.loads((out / "attempt-Q056.json").read_bytes())
    assert receipt["failure_code"] and receipt["selected_ids"] == []
    assert receipt["verdict_failure_subcode"] == ("verdict_fields_invalid" if failure == "bad_verdict" else None)


def test_same_strict_cue_failure_preserves_known_usage_without_retry(tmp_path, monkeypatch):
    packet = admitted(); out, ledger = setup(tmp_path, monkeypatch)
    clock, calls = Clock(), []
    async def send(body):
        calls.append(body)
        value = response(["topic_only"] * 4)
        verdict = json.loads(value["candidates"][0]["content"]["parts"][0]["text"])
        verdict["pages"][0]["cue_locates"] = True
        value["candidates"][0]["content"]["parts"][0]["text"] = json.dumps(verdict)
        return httpx.Response(200, json=value)
    result = run(packet, out, ledger, send, clock)
    assert len(calls) == result["provider_calls"] == 1
    receipt = json.loads((out / "attempt-Q056.json").read_bytes())
    assert receipt["state"] == "failed" and receipt["failure_code"] == "provider_verdict_invalid"
    assert receipt["verdict_failure_subcode"] == "cue_without_useful_page"
    assert receipt["reported_usage"] == {"input": 1000, "output": 550}
    assert receipt["known_cost_microusd"] == caller.cost(1000, 550)
    assert result["unknown_cost_attempts"] == 0 and result["prior_unknown_cost_attempts"] == 8
    assert result["combined_known_cost_microusd"] == 322399 + caller.cost(1000, 550)
    assert result["status"] == "stopped" and not result["score"]["heldout_passed"]
    assert result["inherited_receipts"]["Q056"] == {"group_id": "Q056"}


@pytest.mark.parametrize("field,value", [("group_id", "Q054"), ("group_id", "Q057"),
                                         ("group_id", "Q061"), ("rest_sha256", "b" * 64)])
def test_changed_roster_or_wire_rejected_before_transport(tmp_path, monkeypatch, field, value):
    packet = admitted(); packet["requests"][0][field] = value
    out, ledger = setup(tmp_path, monkeypatch)
    async def send(body): pytest.fail("no transport")
    with pytest.raises(caller.PilotError, match="physical_attempt_roster_invalid|request_changed"):
        run(packet, out, ledger, send, Clock())


@pytest.mark.parametrize("section", ["rows", "all_observed_rows", "binding"])
def test_corrupted_checkpoint_rejected_before_new_claim(tmp_path, monkeypatch, section):
    packet = admitted()
    if section == "binding": packet["checkpoint"][section]["manual_failed_group_ids"] = ["Q013"]
    else: packet["checkpoint"][section][12].update(state="completed", question_status="clear")
    out, ledger = setup(tmp_path, monkeypatch)
    async def send(body): pytest.fail("no transport")
    with pytest.raises(caller.PilotError, match="checkpoint_binding_changed"):
        run(packet, out, ledger, send, Clock())
    assert not list(ledger.iterdir())


def test_no_call_after_deadline_or_reservation_failure(tmp_path, monkeypatch):
    packet = admitted(); out, ledger = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(caller, "COST_CAP_MICROUSD", caller.cost(32768, 4096) - 1)
    async def send(body): pytest.fail("no transport")
    with pytest.raises(caller.PilotError, match="cost_reserve_budget"):
        run(packet, out, ledger, send, Clock())
    assert not list(ledger.glob(caller.AUTHORIZATION_ID + "-Q*.claim.json"))


def test_wall_time_reservation_precedes_claim(tmp_path, monkeypatch):
    packet = admitted(); out, ledger = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(caller, "MAX_SECONDS", 119)
    async def send(body): pytest.fail("no transport")
    with pytest.raises(caller.PilotError, match="total_time_budget"):
        run(packet, out, ledger, send, Clock())
    assert not list(ledger.glob(caller.AUTHORIZATION_ID + "-Q*.claim.json"))


def test_bound_parent503_cooldown_precedes_new_attempt(tmp_path, monkeypatch):
    packet = admitted(); out, ledger = setup(tmp_path, monkeypatch)
    clock, calls = Clock(), []
    binding = packet["checkpoint"]["binding"]
    binding["parent_cooldown_until_epoch_ms"] = 220000
    packet["checkpoint"]["binding_sha256"] = caller.digest(caller.canonical(binding))
    monkeypatch.setattr(caller.time, "time", lambda: 100 + clock.now)
    async def send(body):
        calls.append(clock.now)
        return httpx.Response(503, content=b"not retained")
    result = run(packet, out, ledger, send, clock)
    assert calls == [120] and result["provider_calls"] == 1
    claim = json.loads(next(ledger.glob(caller.AUTHORIZATION_ID + "-Q*.claim.json")).read_bytes())
    assert claim["started_epoch_ms"] == binding["parent_cooldown_until_epoch_ms"]
    assert result["status"] == "stopped" and not result["resume_permitted"]


def test_approval_binds_every_checkpoint_and_code_field(monkeypatch):
    packet = admitted()
    monkeypatch.setattr(caller, "code_hashes", lambda: {"invented": "a" * 64})
    receipt = copy.deepcopy(caller.expected_approval(packet))
    monkeypatch.setattr(caller, "read_bound", lambda *a, **kw: receipt)
    caller.validate_approval(Path("synthetic"), "a" * 64, packet)
    packet["checkpoint"]["binding"]["manual_failed_group_ids"] = ["Q013"]
    with pytest.raises(caller.PilotError, match="approval_contract_changed"):
        caller.validate_approval(Path("synthetic"), "a" * 64, packet)


def test_parser_success_matches_immutable_historical_parser():
    for labels in (["direct", "unrelated", "concrete_learning_step", "topic_only"], ["unrelated"] * 4):
        value = httpx.Response(200, json=response(labels))
        assert caller.parse_response(value) == caller.calibration.parse_response(value)


@pytest.mark.parametrize("raw,subcode", [("{}", "verdict_fields_invalid"), ("not json", "verdict_json_invalid"),
    ('{"question_status":"clear","pages":[],"pages":[]}', "duplicate_json_key"),
    ('{"question_status":"clear","pages":[NaN]}', "nonfinite_json")])
def test_failed_final_verdict_keeps_usage_and_only_closed_diagnostic(raw, subcode):
    value = response(["unrelated"] * 4)
    value["candidates"][0]["content"]["parts"][0]["text"] = raw
    with pytest.raises(caller.ContentError, match="provider_verdict_invalid") as stopped:
        caller.parse_response(httpx.Response(200, json=value))
    assert stopped.value.safe_verdict_subcode == subcode
    assert stopped.value.usage == (1000, 550)
    assert raw not in str(stopped.value)


def test_diagnostic_unknown_exception_message_cannot_escape(monkeypatch):
    error = caller.ContentError("provider_verdict_invalid", (10, 3))
    monkeypatch.setattr(caller.calibration, "parse_response", lambda r: (_ for _ in ()).throw(error))
    private_detail = "not a permitted code"
    monkeypatch.setattr(caller.calibration.prototype, "parse_verdict", lambda *a: (_ for _ in ()).throw(
        caller.calibration.prototype.previous.VisualVerdictError(private_detail)))
    with pytest.raises(caller.ContentError) as stopped:
        caller.parse_response(httpx.Response(200, json=response(["unrelated"] * 4)))
    assert stopped.value.safe_verdict_subcode == "verdict_schema_invalid"
    assert private_detail not in str(stopped.value)


def test_failed_verdict_diagnostic_never_turns_rejection_into_success(monkeypatch):
    error = caller.ContentError("provider_verdict_invalid", (10, 3))
    monkeypatch.setattr(caller.calibration, "parse_response", lambda r: (_ for _ in ()).throw(error))
    with pytest.raises(caller.ContentError) as stopped:
        caller.parse_response(httpx.Response(200, json=response(["unrelated"] * 4)))
    assert stopped.value is error and stopped.value.safe_verdict_subcode is None


def test_invalid_resource_receipt_rejected_before_source_or_key(tmp_path, monkeypatch):
    monkeypatch.setattr(caller, "LIVE_AUTHORIZED", True)
    monkeypatch.setattr(caller.visual, "_inside_windows_job", lambda: True)
    monkeypatch.setattr(caller, "read_existing", lambda p: ({"worker_pid": 999}, "a" * 64))
    monkeypatch.setattr(caller, "admit", lambda: pytest.fail("source touched"))
    monkeypatch.setattr(caller.previous, "read_key", lambda: pytest.fail("key touched"))
    with pytest.raises(caller.PilotError, match="resource_receipt_invalid"):
        asyncio.run(caller.execute({}, "a" * 64, tmp_path, approval_file=tmp_path / "approval.json"))


def test_last_response_failure_cannot_be_reported_complete(tmp_path, monkeypatch):
    packet = admitted(); out, ledger = setup(tmp_path, monkeypatch)
    clock, called = Clock(), []
    async def send(body):
        gid = packet["requests"][len(called)]["group_id"]
        called.append(gid)
        if gid == "Q060":
            return httpx.Response(503, content=b"not retained")
        return success(packet, gid)
    result = run(packet, out, ledger, send, clock)
    assert len(called) == 5 and result["evaluated_group_attempts"] == 60
    assert result["status"] == "stopped" and result["reason"] == "quality_unreachable"
    assert not result["score"]["heldout_passed"]
    assert result["score"]["metrics"]["valid_responses"] == 57


def bound_parent_fixture(monkeypatch):
    """Invent a v9 terminal checkpoint, without reading real public files."""
    from test_visual_public_heldout_v9_caller import admitted as previous_admitted
    base = previous_admitted()
    fake_hashes = {"scripts/launch_visual_public_heldout_v9.py": "a" * 64}
    monkeypatch.setattr(caller.parent_trial, "validate_approval", lambda *args: None)
    monkeypatch.setattr(caller.parent_trial, "code_hashes", lambda: fake_hashes)
    values = {}
    controls = {}
    for role in ("launch", "execute", "run"):
        claim = {"authorization_id": caller.parent_trial.AUTHORIZATION_ID,
            "approval_sha256": caller.PARENT_APPROVAL_SHA}
        if role == "launch":
            claim.update(approval_file=str(caller.PARENT_APPROVAL_PATH),
                output_dir=str(caller.PARENT_OUTPUT), launcher_sha256="a" * 64,
                supervisor_pid=7, created_epoch_ms=1000)
        else:
            claim.update(request_roster_sha256=base["request_roster_sha256"],
                checkpoint_binding_sha256=base["checkpoint"]["binding_sha256"], pid=8)
        sha = caller.digest(caller.canonical(claim))
        values[caller.PARENT_LEDGER / f"{caller.parent_trial.AUTHORIZATION_ID}.{role}-claim.json"] = (claim, sha)
        controls[role] = {"sha256": sha}
    resource = {"approval_sha256": caller.PARENT_APPROVAL_SHA, "cpus": 4,
        "memory_bytes": 2147483648, "timeout_seconds": 9000,
        "kill_tree_on_close": True, "worker_pid": 8}
    complete = {"approval_sha256": caller.PARENT_APPROVAL_SHA, "exit_code": 0, "resume_permitted": False}
    for suffix, value in ((".resource-process.json", resource), (".supervisor-complete.json", complete)):
        values[caller.PARENT_OUTPUT.with_name(caller.PARENT_OUTPUT.name + suffix)] = (value, caller.digest(caller.canonical(value)))
    receipt_bindings = {}
    rows = copy.deepcopy(base["checkpoint"]["rows"])
    for gid, usage, started in (("Q055", (6000, 1866), 2000), ("Q056", (7479, 1579), 32000)):
        request = next(item for item in base["requests"] if item["group_id"] == gid)
        claim = {"authorization_id": caller.parent_trial.AUTHORIZATION_ID,
            "approval_sha256": caller.PARENT_APPROVAL_SHA, "group_id": gid,
            "rest_sha256": request["rest_sha256"],
            "checkpoint_binding_sha256": base["checkpoint"]["binding_sha256"],
            "reserved_microusd": caller.cost(32768, 4096), "started_epoch_ms": started}
        claim_sha = caller.digest(caller.canonical(claim))
        values[caller.PARENT_LEDGER / f"{caller.parent_trial.AUTHORIZATION_ID}-{gid}.claim.json"] = (claim, claim_sha)
        verdict = caller.parse_response(success(base, gid))[0] if gid == "Q055" else None
        receipt = {"group_id": gid, "state": "completed" if verdict else "failed",
            "selected_ids": verdict["selected_ids"] if verdict else [],
            "question_status": verdict["question_status"] if verdict else None,
            "request_sha256": request["rest_sha256"], "attempt_claim_sha256": claim_sha,
            "latency_ms": 1000, "reported_usage": {"input": usage[0], "output": usage[1]},
            "known_cost_microusd": caller.cost(*usage), "verdict": verdict,
            "failure_code": None if verdict else "provider_verdict_invalid",
            "verdict_failure_subcode": None if verdict else "cue_without_useful_page"}
        receipt_sha = caller.digest(caller.canonical(receipt))
        values[caller.PARENT_OUTPUT / f"attempt-{gid}.json"] = (receipt, receipt_sha)
        receipt_bindings[gid] = {"receipt_sha256": receipt_sha, "claim_sha256": claim_sha}
        rows.append({key: receipt[key] for key in ("group_id", "state", "selected_ids", "question_status")})
    rows.sort(key=lambda row: row["group_id"])
    result = {"schema_version": "public_visual_heldout_v9_result",
        "authorization_id": caller.parent_trial.AUTHORIZATION_ID,
        "approval_sha256": caller.PARENT_APPROVAL_SHA, "status": "stopped", "reason": "quality_unreachable",
        "provider_calls": 2, "evaluated_group_attempts": 56, "total_physical_provider_calls": 64,
        "historical_physical_attempts": 62, "checkpoint_binding": base["checkpoint"]["binding"],
        "inherited_receipts": base["checkpoint"]["receipts"],
        "prior_checkpoint": base["checkpoint"]["prior_checkpoint"],
        "calibration_binding": base["calibration_binding"], "input_freeze_sha256": caller.INPUT_FREEZE_SHA,
        "qualification_freeze_sha256": caller.QUALIFICATION_FREEZE_SHA,
        "request_roster_sha256": base["request_roster_sha256"], "known_cost_microusd": 12657,
        "combined_known_cost_microusd": 322399, "reported_input_tokens": 13479,
        "reported_output_tokens": 3445, "unknown_cost_attempts": 0, "prior_unknown_cost_attempts": 8,
        "old_trial_remains_failed": True, "resume_permitted": False, "ask_enabled": False,
        "private_data_sent": False,
        "score": caller.scorer.evaluate(base["overlay"], rows, base["expected_ids"]),
        "ceiling": caller.scorer.ceiling(base["overlay"], rows, base["expected_ids"]),
        "receipt_hashes": {gid: binding["receipt_sha256"] for gid, binding in receipt_bindings.items()}}
    report = {"schema": "public_visual_heldout_v9_terminal_observation",
        "terminal_result_sha256": caller.PARENT_RESULT_SHA,
        "approval_sha256": caller.PARENT_APPROVAL_SHA, "failed_evaluated_groups": ["Q013", "Q014", "Q056"],
        "caller_code_sha256": fake_hashes, "caller_hashes_match": True, "recorded_processes_absent": True,
        "controls": controls, "receipts": receipt_bindings,
        "resource_receipt_sha256": values[caller.PARENT_OUTPUT.with_name(caller.PARENT_OUTPUT.name + ".resource-process.json")][1],
        "supervisor_complete_sha256": values[caller.PARENT_OUTPUT.with_name(caller.PARENT_OUTPUT.name + ".supervisor-complete.json")][1]}
    values[caller.PARENT_RESULT_PATH] = (result, caller.PARENT_RESULT_SHA)
    values[caller.PARENT_REPORT_PATH] = (report, caller.PARENT_REPORT_SHA)
    def bound(path, sha, *args):
        value, frozen_sha = values[path]
        assert sha == frozen_sha
        return value
    monkeypatch.setattr(caller, "read_bound", bound)
    monkeypatch.setattr(caller, "read_existing", lambda path: values[path])
    original_glob = Path.glob
    def glob(path, pattern):
        if path == caller.PARENT_OUTPUT and pattern == "attempt-*.json":
            return iter(caller.PARENT_OUTPUT / f"attempt-{gid}.json" for gid in caller.PARENT_GROUPS)
        if path == caller.PARENT_LEDGER and pattern == caller.parent_trial.AUTHORIZATION_ID + "-Q*.claim.json":
            return iter(caller.PARENT_LEDGER / f"{caller.parent_trial.AUTHORIZATION_ID}-{gid}.claim.json" for gid in caller.PARENT_GROUPS)
        return original_glob(path, pattern)
    monkeypatch.setattr(Path, "glob", glob)
    return base, result, values


def test_real_parent_checkpoint_shape_retains_valid55_and_replaces_only_failed56(monkeypatch):
    base, _, _ = bound_parent_fixture(monkeypatch)
    checkpoint = caller.admit_checkpoint(base, process_observer=lambda pid: True)
    assert len(checkpoint["rows"]) == 55
    assert tuple(row["group_id"] for row in checkpoint["rows"]) == caller.ACTIVE_INHERITED_GROUPS
    assert next(row for row in checkpoint["rows"] if row["group_id"] == "Q055")["state"] == "completed"
    assert [row["group_id"] for row in checkpoint["rows"] if row["state"] == "failed"] == ["Q013", "Q014"]
    assert checkpoint["binding"]["manual_failed_group_ids"] == ["Q056"]
    assert checkpoint["binding"]["superseded_failed_outcomes"] == [checkpoint["all_observed_rows"][-1]]
    assert checkpoint["binding"]["historical_physical_attempts"] == 64


def test_changed_parent_case_score_cannot_be_admitted(monkeypatch):
    base, result, _ = bound_parent_fixture(monkeypatch)
    result["score"]["metrics"]["valid_responses"] = 52
    with pytest.raises(caller.PilotError, match="parent_historical_score_changed"):
        caller.admit_checkpoint(base, process_observer=lambda pid: True)


def test_unreleased_parent_process_prevents_checkpoint_admission(monkeypatch):
    base, _, _ = bound_parent_fixture(monkeypatch)
    with pytest.raises(caller.PilotError, match="parent_process_still_live"):
        caller.admit_checkpoint(base, process_observer=lambda pid: False)
