"""New 60-second trial with retained successes and explicit prior timeouts."""
import asyncio
import copy
from pathlib import Path
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import run_visual_public_calibration_v4 as caller
from test_visual_public_calibration_v3_caller import fake_admission as base_admission
from test_visual_public_calibration_v2_caller import Clock, response


def fake_admission():
    admitted = base_admission()
    checkpoint = admitted["checkpoint"]
    gid = "Q001"
    request = next(r for r in admitted["requests"] if r["group_id"] == gid)
    verdict, usage = caller.parse_response(httpx.Response(200, json=response(["direct"] + ["unrelated"] * 3)))
    row = {"group_id": gid, "state": "completed", "selected_ids": ["S01"], "question_status": "clear"}
    receipt = {**row, "request_sha256": request["rest_sha256"], "attempt_claim_sha256": "c" * 64,
               "latency_ms": 100, "reported_usage": {"input": usage[0], "output": usage[1]},
               "known_cost_microusd": caller.cost(*usage), "failure_code": None, "verdict": verdict}
    checkpoint["rows"].append(row)
    checkpoint["receipts"][gid] = receipt
    binding = checkpoint["binding"]
    binding["receipt_bindings"][gid] = {"receipt_sha256": caller.digest(caller.canonical(receipt)),
        "claim_sha256": "c" * 64, "wire_sha256": request["wire_sha256"], "rest_sha256": request["rest_sha256"]}
    del binding["old_run_claim_sha256"]
    binding.update(old_authorization_id=caller.checkpoint_previous.AUTHORIZATION_ID,
                   old_approval_sha256=caller.OLD_APPROVAL_SHA, old_result_sha256=caller.OLD_RESULT_SHA,
                   base_checkpoint_sha256="a" * 64, inherited_groups=list(caller.OLD_GROUPS),
                   inherited_known_cost_microusd=caller.OLD_COST_MICROUSD,
                   inherited_input_tokens=caller.OLD_INPUT_TOKENS, inherited_output_tokens=caller.OLD_OUTPUT_TOKENS,
                   rows_sha256=caller.digest(caller.canonical(checkpoint["rows"])),
                   prior_failed_attempts={gid: {"receipt_sha256": "a" * 64, "claim_sha256": "b" * 64,
                      "wire_sha256": "c" * 64, "rest_sha256": "d" * 64, "failure_code": "provider_timeout",
                      "cost_unknown": True} for gid in caller.OLD_FAILED_GROUPS})
    checkpoint["binding_sha256"] = caller.digest(caller.canonical(binding))
    return admitted


def test_precise_new_guard_and_inert_live_entrypoints(tmp_path, monkeypatch):
    monkeypatch.setattr(caller, "LIVE_AUTHORIZED", False)
    assert not caller.LIVE_AUTHORIZED
    guards = caller.guards()
    assert guards["call_seconds"] == 60 and guards["max_calls"] == 62
    assert guards["input_total"] == 2031616 and guards["output_total"] == 126976
    assert 62 * caller.cost(caller.MAX_INPUT, caller.MAX_OUTPUT) == 926962
    assert guards["new_cost_cap_microusd"] == 950000 and guards["prior_unknown_cost_attempts"] == 3
    monkeypatch.setattr(caller.previous, "read_key", lambda: pytest.fail("no key before authorization"))
    with pytest.raises(caller.PilotError, match="precise_provider_envelope_not_authorized"):
        asyncio.run(caller.execute({}, "a" * 64, tmp_path))


def test_sixty_second_trial_retains_prior_failures_and_five_successes(tmp_path, monkeypatch):
    admitted = fake_admission()
    monkeypatch.setattr(caller, "read_bound", lambda *a, **k: {})
    monkeypatch.setattr(caller, "rest_body", lambda *a: b"synthetic")
    output, ledger = tmp_path / "out", tmp_path / "ledger"
    output.mkdir()
    ledger.mkdir()
    remaining = [r for r in admitted["requests"] if r["group_id"] not in caller.OLD_GROUPS]
    clock, sent = Clock(), []
    async def send(body):
        gid = remaining[len(sent)]["group_id"]
        sent.append(gid)
        good = {r["candidate_id"] for r in admitted["overlay"]
                if r["group_id"] == gid and r["qualification"] == "Yes"}
        clock.now += 45  # This valid response exceeds the old trial's deadline.
        return httpx.Response(200, json=response(["direct" if sid in good else "unrelated" for sid in caller.ISSUED]))
    result = asyncio.run(caller.run(admitted, "a" * 64, output, send, ledger=ledger,
                                   clock=clock, sleep=clock.sleep))
    assert len(sent) == result["provider_calls"] == 62
    assert not set(sent) & set(caller.OLD_GROUPS)
    assert set(caller.OLD_FAILED_GROUPS) <= set(sent)
    assert result["total_provider_calls"] == 67 and result["physical_attempt_history_count"] == 70
    assert result["score"]["calibration_passed"]
    assert result["prior_unknown_cost_attempts"] == 3 and result["unknown_cost_attempts"] == 0
    assert result["prior_failed_attempts"] == admitted["checkpoint"]["binding"]["prior_failed_attempts"]
    assert result["known_cost_microusd"] == 62 * caller.cost(1000, 550)
    assert result["combined_known_cost_microusd"] == caller.OLD_COST_MICROUSD + result["known_cost_microusd"]
    assert result["elapsed_ms"] == 62 * 45000
    with pytest.raises(FileExistsError):
        asyncio.run(caller.run(admitted, "a" * 64, output, send, ledger=ledger))


@pytest.mark.parametrize("mutation", ["lost_failure", "credited_failure", "changed_receipt", "lost_success"])
def test_prior_uncertainty_and_success_binding_cannot_be_erased(tmp_path, monkeypatch, mutation):
    admitted = fake_admission()
    checkpoint = admitted["checkpoint"]
    if mutation == "lost_failure":
        checkpoint["binding"]["prior_failed_attempts"].pop(caller.OLD_FAILED_GROUPS[0])
    elif mutation == "credited_failure":
        checkpoint["binding"]["prior_failed_attempts"][caller.OLD_FAILED_GROUPS[0]]["cost_unknown"] = False
    elif mutation == "changed_receipt":
        checkpoint["receipts"]["Q001"]["selected_ids"] = ["S04"]
    else:
        checkpoint["rows"].pop()
    # Even rehashing must not erase the explicit prior-error requirement.
    checkpoint["binding_sha256"] = caller.digest(caller.canonical(checkpoint["binding"]))
    with pytest.raises(caller.PilotError):
        caller._checkpoint_rows(admitted)


def test_three_new_timeouts_stop_without_resending_any_group(tmp_path, monkeypatch):
    admitted = fake_admission()
    monkeypatch.setattr(caller, "read_bound", lambda *a, **k: {})
    monkeypatch.setattr(caller, "rest_body", lambda *a: b"synthetic")
    output, ledger = tmp_path / "out", tmp_path / "ledger"
    output.mkdir()
    ledger.mkdir()
    clock, sent = Clock(), []
    async def send(body):
        sent.append(body)
        clock.now += 60
        raise httpx.ReadTimeout("synthetic")
    result = asyncio.run(caller.run(admitted, "a" * 64, output, send,
                                   ledger=ledger, clock=clock, sleep=clock.sleep))
    assert len(sent) == result["provider_calls"] == 3
    assert result["reason"] == "quality_unreachable" and result["status"] == "stopped"
    assert result["unknown_cost_attempts"] == result["prior_unknown_cost_attempts"] == 3
    assert result["physical_attempt_history_count"] == 11
    assert not result["score"]["calibration_passed"]
    assert not result["heldout_opened"] and not result["ask_enabled"]


def test_execute_claim_consumed_before_key_prevents_second_dispatch(tmp_path, monkeypatch):
    admitted = fake_admission()
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    monkeypatch.setattr(caller, "LIVE_AUTHORIZED", True)
    monkeypatch.setattr(caller.visual, "_inside_windows_job", lambda: True)
    monkeypatch.setattr(caller, "admit", lambda: admitted)
    monkeypatch.setattr(caller, "validate_approval", lambda *a: None)
    monkeypatch.setattr(caller, "ledger_dir", lambda: ledger)
    def stopped_key():
        raise caller.PilotError("synthetic_key_unavailable")
    monkeypatch.setattr(caller.previous, "read_key", stopped_key)
    with pytest.raises(caller.PilotError, match="synthetic_key_unavailable"):
        asyncio.run(caller.execute(admitted, "a" * 64, tmp_path, approval_file=tmp_path / "approval"))
    monkeypatch.setattr(caller.previous, "read_key", lambda: pytest.fail("claim must prevent replay"))
    with pytest.raises(FileExistsError):
        asyncio.run(caller.execute(admitted, "a" * 64, tmp_path, approval_file=tmp_path / "approval"))
