"""Keyless synthetic successor guards; no PDF, credential or provider access."""
import asyncio
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import run_visual_public_heldout_v2 as caller
import launch_visual_public_heldout_v2 as launcher
from test_visual_public_heldout_v1_score import fixture
from test_visual_public_calibration_v2_caller import Clock, response


def admitted():
    overlay, rows, expected = fixture()
    requests = [{"group_id": gid, "path": f"{gid}.json", "wire_sha256": "a" * 64,
                 "rest_sha256": caller.digest(b"synthetic"), "rest_bytes": 9} for gid in expected]
    old = [r for r in rows if r["group_id"] in caller.OLD_SUCCESS_GROUPS]
    receipts = {r["group_id"]: dict(r) for r in old}
    binding = {"old_result_sha256": caller.OLD_RESULT_SHA, "old_approval_sha256": caller.OLD_APPROVAL_SHA,
        "prior_failed_attempts": {g: {"cost_unknown": True, "failure_code": caller.OLD_FAILURE_CODES[g]}
                                  for g in caller.OLD_FAILED_GROUPS},
        "rows_sha256": caller.digest(caller.canonical(old))}
    checkpoint = {"rows": old, "receipts": receipts, "binding": binding,
                  "binding_sha256": caller.digest(caller.canonical(binding))}
    new_requests = [r for r in requests if r["group_id"] not in caller.OLD_SUCCESS_GROUPS]
    return dict(overlay=overlay, expected_ids=expected, requests=new_requests,
                original_requests=requests, known_images=set(), checkpoint=checkpoint,
                request_roster_sha256=caller.digest(caller.canonical(new_requests)),
                calibration_binding={"passed": True})


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(caller, "read_bound", lambda *a, **k: {})
    monkeypatch.setattr(caller, "rest_body", lambda *a: b"synthetic")
    out, ledger = tmp_path / "out", tmp_path / "ledger"
    out.mkdir(); ledger.mkdir()
    return out, ledger


def success(a, gid):
    good = {r["candidate_id"] for r in a["overlay"] if r["group_id"] == gid and r["qualification"] == "Yes"}
    return httpx.Response(200, json=response(["direct" if sid in good else "unrelated" for sid in caller.ISSUED]))


def test_default_envelope_fence_precedes_credentials_resource_and_source(tmp_path, monkeypatch):
    monkeypatch.setattr(caller, "LIVE_AUTHORIZED", False)
    monkeypatch.setattr(caller.previous, "read_key", lambda: pytest.fail("credential touched"))
    monkeypatch.setattr(caller.visual, "_inside_windows_job", lambda: pytest.fail("resource read"))
    monkeypatch.setattr(caller, "admit", lambda: pytest.fail("source read"))
    with pytest.raises(caller.PilotError, match="precise_provider_envelope_not_authorized"):
        asyncio.run(caller.execute({}, "a" * 64, tmp_path))
    g = caller.guards()
    assert g["max_calls"] == 57 and g["input_total"] == 1867776 and g["output_total"] == 233472
    assert g["call_seconds"] == 120 and g["total_seconds"] == 9000 and g["spacing_seconds"] == 30
    assert g["http_503_cooldown_seconds"] == 120 and g["retries"] == 0
    assert 57 * caller.cost(32768, 4096) == 1144047
    assert not g["private_data_permitted"] and not g["ask_activation_permitted"]


def test_exact_three_successes_reused_and_57_new_calls_have_full60_denominator(tmp_path, monkeypatch):
    a = admitted(); before = copy.deepcopy(a)
    out, ledger = setup(tmp_path, monkeypatch); clock, starts, gids = Clock(), [], []
    async def send(body):
        starts.append(clock.now)
        gid = a["requests"][len(starts)-1]["group_id"]; gids.append(gid)
        return success(a, gid)
    result = asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger, clock=clock, sleep=clock.sleep))
    assert a == before and result["provider_calls"] == 57 and result["evaluated_group_attempts"] == 60
    assert result["total_physical_provider_calls"] == 63 and "total_provider_calls" not in result
    assert result["score"]["heldout_passed"] and result["score"]["metrics"]["attempted_groups"] == 60
    assert not set(gids) & set(caller.OLD_SUCCESS_GROUPS)
    assert set(caller.OLD_FAILED_GROUPS) <= set(gids)
    assert all(b-a >= 30 for a, b in zip(starts, starts[1:]))
    assert result["historical_physical_attempts"] == 6 and result["prior_unknown_cost_attempts"] == 3
    assert result["old_trial_remains_failed"] and not result["resume_permitted"] and not result["ask_enabled"]
    assert result["combined_known_cost_microusd"] == result["known_cost_microusd"] + 14444
    assert len(result["receipt_hashes"]) == 57
    with pytest.raises(FileExistsError):
        asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger))


def test_503_waits120_after_response_before_different_question_without_same_retry(tmp_path, monkeypatch):
    a = admitted(); out, ledger = setup(tmp_path, monkeypatch)
    clock, starts, gids = Clock(), [], []
    async def send(body):
        starts.append(clock.now); gid = a["requests"][len(starts)-1]["group_id"]; gids.append(gid)
        if len(starts) == 1:
            clock.now += 17
            return httpx.Response(503, content=b"not retained")
        return success(a, gid)
    result = asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger, clock=clock, sleep=clock.sleep))
    assert starts[1] >= starts[0] + 17 + 120
    assert gids[0] != gids[1] and len(set(gids)) == len(gids) == 57
    assert result["unknown_cost_attempts"] == 1
    assert result["score"]["metrics"]["failed_groups"] == 1


@pytest.mark.parametrize("failure", ["timeout", "503", "unfinished"])
def test_third_new_failure_stops_with_old_failures_separate(tmp_path, monkeypatch, failure):
    a = admitted(); out, ledger = setup(tmp_path, monkeypatch); clock, attempts = Clock(), []
    async def send(body):
        attempts.append(body)
        if failure == "timeout": raise httpx.ReadTimeout("not retained")
        if failure == "503": return httpx.Response(503)
        r = response(["unrelated"] * 4); r["candidates"][0]["finishReason"] = "MAX_TOKENS"
        return httpx.Response(200, json=r)
    result = asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger, clock=clock, sleep=clock.sleep))
    assert len(attempts) == result["provider_calls"] == 3 and result["evaluated_group_attempts"] == 6
    assert result["total_physical_provider_calls"] == 9
    assert result["reason"] == "quality_unreachable" and not result["score"]["heldout_passed"]
    assert result["score"]["metrics"]["failed_groups"] == 3
    assert result["prior_unknown_cost_attempts"] == 3


def test_total_time_budget_uses120seconds_before_dispatch(tmp_path, monkeypatch):
    a = admitted(); out, ledger = setup(tmp_path, monkeypatch); clock = Clock()
    monkeypatch.setattr(caller, "MAX_SECONDS", 119)
    async def send(body): pytest.fail("budget failed before dispatch")
    with pytest.raises(caller.PilotError, match="total_time_budget"):
        asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger, clock=clock, sleep=clock.sleep))
    assert not list(ledger.glob(caller.AUTHORIZATION_ID + "-Q*.claim.json"))


@pytest.mark.parametrize("status", [400, 401, 403])
def test_permanent_failure_stops_one_fresh_attempt(tmp_path, monkeypatch, status):
    a = admitted(); out, ledger = setup(tmp_path, monkeypatch); clock = Clock()
    async def send(body): return httpx.Response(status, content=b"never retained")
    result = asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger, clock=clock, sleep=clock.sleep))
    assert result["provider_calls"] == 1 and result["reason"] == "provider_http_permanent"


def test_corrupted_checkpoint_prevents_fresh_claim(tmp_path, monkeypatch):
    a = admitted(); a["checkpoint"]["rows"][0]["selected_ids"] = []
    out, ledger = setup(tmp_path, monkeypatch)
    async def send(body): pytest.fail("checkpoint fails before transport")
    with pytest.raises(caller.PilotError, match="checkpoint_binding_changed"):
        asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger))
    assert not list(ledger.iterdir())


def test_launcher_disabled_and_child_environment_has_no_secrets(tmp_path, monkeypatch):
    monkeypatch.setattr(caller, "LIVE_AUTHORIZED", False)
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *a, **k: pytest.fail("no child"))
    with pytest.raises(caller.visual.PreparationError, match="fresh_provider_authorization_required"):
        launcher.detach(tmp_path / "approval.json", "a" * 64, tmp_path / "output")
    env = launcher.child_env({"SystemRoot": "C:/Windows", "RAG_SOURCE_JUDGE_API_KEY": "forbidden",
                             "HTTP_PROXY": "forbidden", "DATABASE_URL": "forbidden"})
    assert "forbidden" not in env.values() and launcher.MAX_SECONDS == 9000


def test_new_approval_binds_checkpoint_code_and_prospective_limits(monkeypatch):
    a = admitted(); monkeypatch.setattr(caller, "code_hashes", lambda: {"synthetic": "a" * 64})
    expected = copy.deepcopy(caller.expected_approval(a))
    monkeypatch.setattr(caller, "read_bound", lambda *a, **k: expected)
    caller.validate_approval(Path("synthetic"), "a" * 64, a)
    a["checkpoint"]["binding"]["old_result_sha256"] = "b" * 64
    with pytest.raises(caller.PilotError, match="approval_contract_changed"):
        caller.validate_approval(Path("synthetic"), "a" * 64, a)


@pytest.fixture
def checkpoint_files(tmp_path, monkeypatch):
    """Invent all source/question/verdict records, including an old failed run."""
    a = admitted()
    base = {**a, "requests": a["original_requests"],
            "request_roster_sha256": caller.digest(caller.canonical(a["original_requests"]))}
    ledger, output = tmp_path / "old-ledger", tmp_path / "old-output"
    ledger.mkdir(); output.mkdir()
    old_authorization = "invented_consumed_public_trial"
    # Replace this caller's reference with a fake; never mutate v1 globals.
    monkeypatch.setattr(caller, "previous_trial", SimpleNamespace(
        AUTHORIZATION_ID=old_authorization, validate_approval=lambda *args: None))
    monkeypatch.setattr(caller, "OLD_LEDGER", ledger)
    monkeypatch.setattr(caller, "OLD_RESULT_PATH", output / "result.json")
    monkeypatch.setattr(caller, "OLD_APPROVAL_PATH", tmp_path / "approval.json")
    caller.write_new(ledger / f"{old_authorization}.run-claim.json", {
        "authorization_id": old_authorization, "approval_sha256": caller.OLD_APPROVAL_SHA,
        "request_roster_sha256": base["request_roster_sha256"], "pid": 123})
    usages = {"Q001": (6671, 672), "Q002": (6663, 1211), "Q005": (7116, 1440)}
    all_rows, receipt_hashes = [], {}
    for ordinal, request in enumerate(base["requests"][:6]):
        gid = request["group_id"]
        claim = {"authorization_id": old_authorization, "group_id": gid,
            "approval_sha256": caller.OLD_APPROVAL_SHA, "rest_sha256": request["rest_sha256"],
            "started_epoch_ms": 100000 + ordinal * 20000,
            "reserved_microusd": caller.cost(caller.MAX_INPUT, caller.MAX_OUTPUT)}
        caller.write_new(ledger / f"{old_authorization}-{gid}.claim.json", claim)
        if gid in caller.OLD_FAILED_GROUPS:
            row = {"group_id": gid, "state": "failed", "selected_ids": [], "question_status": None}
            verdict = usage = None; failure = caller.OLD_FAILURE_CODES[gid]
        else:
            verdict, _ = caller.calibration.parse_response(success(a, gid))
            row = {"group_id": gid, "state": "completed", "selected_ids": verdict["selected_ids"],
                   "question_status": verdict["question_status"]}
            usage = {"input": usages[gid][0], "output": usages[gid][1]}; failure = None
        all_rows.append(row)
        receipt = {**row, "request_sha256": request["rest_sha256"],
            "attempt_claim_sha256": caller.digest(caller.canonical(claim)), "latency_ms": 1000,
            "reported_usage": usage, "known_cost_microusd": caller.cost(*usages[gid]) if usage else None,
            "failure_code": failure, "verdict": verdict}
        caller.write_new(output / f"attempt-{gid}.json", receipt)
        receipt_hashes[gid] = caller.digest(caller.canonical(receipt))
    result = {"schema_version": "public_visual_heldout_v1_result", "authorization_id": old_authorization,
        "approval_sha256": caller.OLD_APPROVAL_SHA, "status": "stopped", "reason": "quality_unreachable",
        "provider_calls": 6, "request_roster_sha256": base["request_roster_sha256"],
        "calibration_binding": base["calibration_binding"], "input_freeze_sha256": caller.INPUT_FREEZE_SHA,
        "qualification_freeze_sha256": caller.QUALIFICATION_FREEZE_SHA,
        "known_cost_microusd": 14444, "unknown_cost_attempts": 3,
        "reported_input_tokens": 20450, "reported_output_tokens": 3323,
        "resume_permitted": False, "ask_enabled": False, "private_data_sent": False,
        "receipt_hashes": receipt_hashes,
        "score": caller.scorer.evaluate(base["overlay"], all_rows, base["expected_ids"]),
        "ceiling": caller.scorer.ceiling(base["overlay"], all_rows, base["expected_ids"])}
    caller.write_new(output / "result.json", result)
    monkeypatch.setattr(caller, "OLD_RESULT_SHA", caller.digest(caller.canonical(result)))
    return base, result, output, ledger


def test_all_old_physical_claims_and_costs_bound_before_success_reuse(checkpoint_files):
    base, _, output, ledger = checkpoint_files
    before = {p: p.read_bytes() for p in [*output.iterdir(), *ledger.iterdir()]}
    checkpoint = caller.admit_checkpoint(base)
    assert {r["group_id"] for r in checkpoint["rows"]} == set(caller.OLD_SUCCESS_GROUPS)
    assert len(checkpoint["binding"]["prior_failed_attempts"]) == 3
    assert checkpoint["binding"]["inherited_known_cost_microusd"] == 14444
    assert all(v["cost_unknown"] for v in checkpoint["binding"]["prior_failed_attempts"].values())
    assert before == {p: p.read_bytes() for p in before}


def test_old_extra_attempt_not_silently_dropped(checkpoint_files):
    base, _, output, _ = checkpoint_files
    caller.write_new(output / "attempt-Q007.json", {"invented": True})
    with pytest.raises(caller.PilotError, match="parent_physical_attempt_roster_changed"):
        caller.admit_checkpoint(base)


@pytest.mark.parametrize("gid,field,value,code", [
    ("Q001", "request_sha256", "e" * 64, "parent_attempt_changed"),
    ("Q003", "failure_code", "provider_http_503", "parent_failure_changed"),
    ("Q005", "known_cost_microusd", 0, "parent_usage_changed"),
])
def test_semantically_rebound_old_receipt_tamper_rejected(checkpoint_files, monkeypatch, gid, field, value, code):
    base, result, output, _ = checkpoint_files
    receipt_path = output / f"attempt-{gid}.json"
    receipt = json.loads(receipt_path.read_bytes()); receipt[field] = value
    receipt_path.write_bytes(caller.canonical(receipt))
    result["receipt_hashes"][gid] = caller.digest(caller.canonical(receipt))
    (output / "result.json").write_bytes(caller.canonical(result))
    monkeypatch.setattr(caller, "OLD_RESULT_SHA", caller.digest(caller.canonical(result)))
    with pytest.raises(caller.PilotError, match=code): caller.admit_checkpoint(base)


def test_old_failed_score_cannot_be_regraded_as_pass(checkpoint_files, monkeypatch):
    base, result, output, _ = checkpoint_files
    result["score"]["heldout_passed"] = True
    (output / "result.json").write_bytes(caller.canonical(result))
    monkeypatch.setattr(caller, "OLD_RESULT_SHA", caller.digest(caller.canonical(result)))
    with pytest.raises(caller.PilotError, match="parent_failed_score_changed"):
        caller.admit_checkpoint(base)
