"""Synthetic checkpoint admission and injected transport; no real artifacts."""
import asyncio
import copy
import json
from pathlib import Path
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import run_visual_public_calibration_v3 as caller
from test_visual_public_calibration_v3_score import invented
from test_visual_public_calibration_v2_caller import Clock, response


def fake_admission():
    overlay, ids = invented()
    requests = [{"group_id": gid, "path": "synthetic", "wire_sha256": "b" * 64,
                 "rest_sha256": caller.digest(b"synthetic"), "rest_bytes": 9} for gid in ids]
    rows, receipts, bindings = [], {}, {}
    for gid in caller.OLD_GROUPS:
        good = [r["candidate_id"] for r in overlay
                if r["group_id"] == gid and r["qualification"] == "Yes"][:3]
        verdict, usage = caller.parse_response(httpx.Response(200, json=response([
            "direct" if sid in good else "unrelated" for sid in caller.ISSUED])))
        row = {"group_id": gid, "state": "completed", "selected_ids": good, "question_status": "clear"}
        receipt = {**row, "request_sha256": caller.digest(b"synthetic"), "attempt_claim_sha256": "c" * 64,
                   "latency_ms": 100, "reported_usage": {"input": usage[0], "output": usage[1]},
                   "known_cost_microusd": caller.cost(*usage), "failure_code": None, "verdict": verdict}
        receipts[gid] = receipt
        rows.append(row)
        bindings[gid] = {"receipt_sha256": caller.digest(caller.canonical(receipt)),
                         "claim_sha256": "c" * 64, "wire_sha256": "b" * 64,
                         "rest_sha256": caller.digest(b"synthetic")}
    binding = {"old_authorization_id": caller.previous.AUTHORIZATION_ID,
               "old_approval_sha256": caller.OLD_APPROVAL_SHA, "old_result_sha256": caller.OLD_RESULT_SHA,
               "old_run_claim_sha256": caller.OLD_RUN_CLAIM_SHA, "request_roster_sha256": "a" * 64,
               "receipt_bindings": bindings, "inherited_groups": list(caller.OLD_GROUPS),
               "inherited_known_cost_microusd": caller.OLD_COST_MICROUSD,
               "inherited_input_tokens": caller.OLD_INPUT_TOKENS,
               "inherited_output_tokens": caller.OLD_OUTPUT_TOKENS,
               "rows_sha256": caller.digest(caller.canonical(rows))}
    checkpoint = {"binding": binding, "binding_sha256": caller.digest(caller.canonical(binding)),
                  "rows": rows, "receipts": receipts}
    return {"overlay": overlay, "expected_ids": ids, "known_images": {"synthetic"},
            "request_roster_sha256": "a" * 64, "requests": requests, "checkpoint": checkpoint}


def setup_run(tmp_path, monkeypatch):
    admitted = fake_admission()
    monkeypatch.setattr(caller, "read_bound", lambda *a, **k: {})
    monkeypatch.setattr(caller, "rest_body", lambda *a: b"synthetic")
    output, ledger = tmp_path / "out", tmp_path / "ledger"
    output.mkdir()
    ledger.mkdir()
    return admitted, output, ledger


def test_new_only_budget_and_disabled_authorization_guard(monkeypatch):
    monkeypatch.setattr(caller, "LIVE_AUTHORIZED", False)
    guards = caller.guards()
    assert not caller.LIVE_AUTHORIZED and not guards["live_authorized"]
    assert guards["max_calls"] == 63 and guards["total_group_denominator"] == 67
    assert guards["input_total"] == 2064384 and guards["output_total"] == 129024
    assert 63 * caller.cost(caller.MAX_INPUT, caller.MAX_OUTPUT) == 941913
    assert guards["new_cost_cap_microusd"] == 950000
    assert not guards["heldout_permitted"] and not guards["private_data_permitted"]


@pytest.mark.parametrize("mutation", ["missing", "failed", "unknown", "changed_selection", "changed_receipt",
                                     "changed_wire", "old_hash", "changed_binding", "old_cost"])
def test_checkpoint_mutations_refuse_before_any_new_claim(tmp_path, monkeypatch, mutation):
    admitted, output, ledger = setup_run(tmp_path, monkeypatch)
    checkpoint = admitted["checkpoint"]
    if mutation == "missing":
        checkpoint["rows"].pop()
    elif mutation == "failed":
        checkpoint["rows"][0]["state"] = "failed"
    elif mutation == "unknown":
        checkpoint["rows"][0]["question_status"] = None
    elif mutation == "changed_selection":
        checkpoint["rows"][0]["selected_ids"] = ["S04"]
    elif mutation == "changed_receipt":
        checkpoint["receipts"][caller.OLD_GROUPS[0]]["verdict"]["generated_answer"] = True
    elif mutation == "changed_wire":
        next(r for r in admitted["requests"] if r["group_id"] == caller.OLD_GROUPS[0])["wire_sha256"] = "d" * 64
    elif mutation == "old_hash":
        checkpoint["binding"]["old_result_sha256"] = "e" * 64
    elif mutation == "changed_binding":
        checkpoint["binding_sha256"] = "f" * 64
    else:
        checkpoint["binding"]["inherited_known_cost_microusd"] += 1
    async def forbidden(*args):
        pytest.fail("bad checkpoint must not dispatch")
    with pytest.raises(caller.PilotError):
        asyncio.run(caller.run(admitted, "d" * 64, output, forbidden, ledger=ledger))
    assert not list(ledger.iterdir()) and not list(output.iterdir())


def test_complete_run_never_resends_old_groups_and_separates_spend(tmp_path, monkeypatch):
    admitted, output, ledger = setup_run(tmp_path, monkeypatch)
    remaining = [r for r in admitted["requests"] if r["group_id"] not in caller.OLD_GROUPS]
    starts, sent = [], []
    clock = Clock()
    async def send(body):
        gid = remaining[len(sent)]["group_id"]
        starts.append(clock())
        sent.append(gid)
        good = {r["candidate_id"] for r in admitted["overlay"]
                if r["group_id"] == gid and r["qualification"] == "Yes"}
        clock.now += 0.1
        return httpx.Response(200, json=response([
            "direct" if sid in good else "unrelated" for sid in caller.ISSUED]))
    result = asyncio.run(caller.run(admitted, "d" * 64, output, send, ledger=ledger,
                                   clock=clock, sleep=clock.sleep))
    assert result["provider_calls"] == 63 and result["total_provider_calls"] == 67
    assert not set(sent) & set(caller.OLD_GROUPS)
    assert len(list(output.glob("attempt-*.json"))) == 63
    assert len(list(ledger.glob("*-Q*.claim.json"))) == 63
    assert result["score"]["calibration_passed"] and result["score"]["metrics"]["valid_responses"] == 67
    assert all(b - a >= 20 for a, b in zip(starts, starts[1:]))
    assert result["known_cost_microusd"] == 63 * caller.cost(1000, 550)
    assert result["inherited_known_cost_microusd"] == 20718
    assert result["combined_known_cost_microusd"] == result["known_cost_microusd"] + 20718
    assert result["reserved_cost_microusd"] == 941913 and not result["resume_permitted"]
    with pytest.raises(FileExistsError):
        asyncio.run(caller.run(admitted, "d" * 64, output, send, ledger=ledger))
    assert len(sent) == 63


def test_no_match_timeout_is_failure_and_cannot_gain_empty_credit(tmp_path, monkeypatch):
    admitted, output, ledger = setup_run(tmp_path, monkeypatch)
    admitted["requests"].sort(key=lambda r: r["group_id"] != "Q067")
    physical = []
    async def send(body):
        physical.append(body)
        raise TimeoutError("never persist")
    result = asyncio.run(caller.run(admitted, "d" * 64, output, send, ledger=ledger))
    assert result["provider_calls"] == len(physical) == 1 and result["unknown_cost_attempts"] == 1
    assert result["reason"] == "quality_unreachable" and not result["score"]["calibration_passed"]
    assert result["score"]["metrics"]["total_request_denominator"] == 67
    assert "never persist" not in (output / "attempt-Q067.json").read_text()


@pytest.mark.parametrize("mutation", ["omitted", "duplicate"])
def test_request_roster_cannot_omit_cases_or_insert_replay(tmp_path, monkeypatch, mutation):
    admitted, output, ledger = setup_run(tmp_path, monkeypatch)
    if mutation == "omitted":
        admitted["requests"].pop()
    else:
        admitted["requests"][-1] = copy.deepcopy(admitted["requests"][0])
    async def forbidden(*args):
        pytest.fail("invalid roster must not dispatch")
    with pytest.raises(caller.PilotError, match="physical_attempt_roster_invalid"):
        asyncio.run(caller.run(admitted, "d" * 64, output, forbidden, ledger=ledger))
    assert not list(ledger.iterdir())


def test_default_execute_refuses_before_key_and_transport(tmp_path, monkeypatch):
    monkeypatch.setattr(caller, "LIVE_AUTHORIZED", False)
    def forbidden(*args, **kwargs):
        pytest.fail("inert code must not read key or create transport")
    monkeypatch.setattr(caller.previous, "read_key", forbidden)
    monkeypatch.setattr(caller.httpx, "AsyncClient", forbidden)
    with pytest.raises(caller.PilotError, match="precise_provider_envelope_not_authorized"):
        asyncio.run(caller.execute({}, "a" * 64, tmp_path))


def test_execute_claim_blocks_replay_before_key(tmp_path, monkeypatch):
    admitted = fake_admission()
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    monkeypatch.setattr(caller, "LIVE_AUTHORIZED", True)
    monkeypatch.setattr(caller.visual, "_inside_windows_job", lambda: True)
    monkeypatch.setattr(caller, "admit", lambda: admitted)
    monkeypatch.setattr(caller, "validate_approval", lambda *a: None)
    monkeypatch.setattr(caller, "ledger_dir", lambda: ledger)
    def key_stop():
        raise caller.PilotError("synthetic_key_stop")
    monkeypatch.setattr(caller.previous, "read_key", key_stop)
    with pytest.raises(caller.PilotError, match="synthetic_key_stop"):
        asyncio.run(caller.execute(admitted, "a" * 64, tmp_path, approval_file=tmp_path / "approval"))
    monkeypatch.setattr(caller.previous, "read_key", lambda: pytest.fail("no second key read"))
    with pytest.raises(FileExistsError):
        asyncio.run(caller.execute(admitted, "a" * 64, tmp_path, approval_file=tmp_path / "approval"))


@pytest.mark.parametrize("mutation", ["verdict", "question_status", "claim", "usage", "answer", "hash"])
def test_old_receipt_closed_bindings_cannot_change(mutation):
    admitted = fake_admission()
    gid = caller.OLD_GROUPS[0]
    receipt = copy.deepcopy(admitted["checkpoint"]["receipts"][gid])
    request = next(r for r in admitted["requests"] if r["group_id"] == gid)
    claim = {"authorization_id": caller.previous.AUTHORIZATION_ID, "group_id": gid,
             "approval_sha256": caller.OLD_APPROVAL_SHA, "rest_sha256": request["rest_sha256"],
             "started_epoch_ms": 100000, "reserved_microusd": caller.cost(caller.MAX_INPUT, caller.MAX_OUTPUT)}
    receipt["attempt_claim_sha256"] = caller.digest(caller.canonical(claim))
    assert caller.validate_old_receipt(receipt, claim, request)["group_id"] == gid
    if mutation == "verdict":
        receipt["verdict"]["selected_ids"] = ["S04"]
    elif mutation == "question_status":
        receipt["question_status"] = None
    elif mutation == "claim":
        claim["authorization_id"] = "wrong"
    elif mutation == "usage":
        receipt["reported_usage"]["output"] = 3000
    elif mutation == "answer":
        receipt["verdict"]["generated_answer"] = True
    else:
        receipt["request_sha256"] = "f" * 64
    with pytest.raises(caller.PilotError):
        caller.validate_old_receipt(receipt, claim, request)


def frozen_old(tmp_path, monkeypatch):
    """Disk serialization is part of the checkpoint boundary, including int keys."""
    admitted = fake_admission()
    requests = {r["group_id"]: r for r in admitted["requests"]}
    admitted["requests"] = [requests[g] for g in caller.OLD_GROUPS] + [
        r for r in admitted["requests"] if r["group_id"] not in caller.OLD_GROUPS]
    old_root, old_ledger, wire_root = tmp_path / "old", tmp_path / "old-ledger", tmp_path / "wire"
    for root in (old_root, old_ledger, wire_root):
        root.mkdir()
    raw_wire = caller.canonical({"synthetic": True})
    (wire_root / "synthetic").write_bytes(raw_wire)
    for request in admitted["requests"]:
        request["wire_sha256"] = caller.digest(raw_wire)
    monkeypatch.setattr(caller, "INPUT_ROOT", wire_root)
    monkeypatch.setattr(caller, "rest_body", lambda *args: b"synthetic")
    monkeypatch.setattr(caller.previous, "validate_approval", lambda *args: None)
    receipt_hashes, rows, receipts = {}, [], []
    for index, gid in enumerate(caller.OLD_GROUPS):
        receipt = copy.deepcopy(admitted["checkpoint"]["receipts"][gid])
        claim = {"authorization_id": caller.previous.AUTHORIZATION_ID, "group_id": gid,
                 "approval_sha256": caller.OLD_APPROVAL_SHA, "rest_sha256": requests[gid]["rest_sha256"],
                 "started_epoch_ms": 100000 + index * 20000,
                 "reserved_microusd": caller.cost(caller.MAX_INPUT, caller.MAX_OUTPUT)}
        caller.write_new(old_ledger / f"{caller.previous.AUTHORIZATION_ID}-{gid}.claim.json", claim)
        receipt["attempt_claim_sha256"] = caller.digest(caller.canonical(claim))
        caller.write_new(old_root / f"attempt-{gid}.json", receipt)
        receipt_hashes[gid] = caller.digest(caller.canonical(receipt))
        rows.append({k: receipt[k] for k in ("group_id", "state", "selected_ids", "question_status")})
        receipts.append(receipt)
    old_cost = sum(r["known_cost_microusd"] for r in receipts)
    old_input = sum(r["reported_usage"]["input"] for r in receipts)
    old_output = sum(r["reported_usage"]["output"] for r in receipts)
    monkeypatch.setattr(caller, "OLD_COST_MICROUSD", old_cost)
    monkeypatch.setattr(caller, "OLD_INPUT_TOKENS", old_input)
    monkeypatch.setattr(caller, "OLD_OUTPUT_TOKENS", old_output)
    run_claim = {"authorization_id": caller.previous.AUTHORIZATION_ID, "approval_sha256": caller.OLD_APPROVAL_SHA,
                 "request_roster_sha256": admitted["request_roster_sha256"], "pid": 12345}
    caller.write_new(old_ledger / f"{caller.previous.AUTHORIZATION_ID}.run-claim.json", run_claim)
    monkeypatch.setattr(caller, "OLD_RUN_CLAIM_SHA", caller.digest(caller.canonical(run_claim)))
    old_result = {"schema_version": "public_visual_calibration_v2_result", "status": "stopped",
                  "reason": "quality_unreachable", "authorization_id": caller.previous.AUTHORIZATION_ID,
                  "approval_sha256": caller.OLD_APPROVAL_SHA,
                  "request_roster_sha256": admitted["request_roster_sha256"], "provider_calls": 4,
                  "known_cost_microusd": old_cost, "unknown_cost_attempts": 0,
                  "reported_input_tokens": old_input, "reported_output_tokens": old_output,
                  "reserved_cost_microusd": 4 * caller.cost(caller.MAX_INPUT, caller.MAX_OUTPUT),
                  "elapsed_ms": 65000, "score": caller.previous.scorer.evaluate(admitted["overlay"], rows, admitted["expected_ids"]),
                  "ceiling": caller.previous.scorer.ceiling(admitted["overlay"], rows, admitted["expected_ids"]),
                  "receipt_hashes": receipt_hashes, "resume_permitted": False, "heldout_opened": False, "ask_enabled": False}
    caller.write_new(old_root / "result.json", old_result)
    monkeypatch.setattr(caller, "OLD_RESULT_PATH", old_root / "result.json")
    monkeypatch.setattr(caller, "OLD_RESULT_SHA", caller.digest(caller.canonical(old_result)))
    monkeypatch.setattr(caller, "OLD_LEDGER", old_ledger)
    return admitted, old_result


def test_full_disk_checkpoint_admission_handles_json_integer_keys(tmp_path, monkeypatch):
    admitted, old_result = frozen_old(tmp_path, monkeypatch)
    # JSON necessarily converts cardinality keys to strings; byte-normalized
    # equality retains every metric instead of rejecting a valid checkpoint.
    assert json.loads(caller.canonical(old_result))["score"] != old_result["score"]
    checkpoint = caller.admit_checkpoint(admitted)
    admitted["checkpoint"] = checkpoint
    assert len(caller._checkpoint_rows(admitted)) == 4
    assert checkpoint["binding"]["old_run_claim_sha256"] == caller.OLD_RUN_CLAIM_SHA
    assert checkpoint["binding_sha256"] == caller.digest(caller.canonical(checkpoint["binding"]))


@pytest.mark.parametrize("mutation", ["extra_claim", "missing_receipt", "source_bytes", "run_claim_bytes",
                                     "result_bytes", "rehash_wrong_total", "rehash_wrong_score"])
def test_disk_checkpoint_corruption_or_extra_attempt_is_rejected(tmp_path, monkeypatch, mutation):
    admitted, result = frozen_old(tmp_path, monkeypatch)
    if mutation == "extra_claim":
        (caller.OLD_LEDGER / f"{caller.previous.AUTHORIZATION_ID}-Q067.claim.json").write_bytes(b"{}")
    elif mutation == "missing_receipt":
        (caller.OLD_RESULT_PATH.parent / f"attempt-{caller.OLD_GROUPS[0]}.json").unlink()
    elif mutation == "source_bytes":
        (caller.INPUT_ROOT / "synthetic").write_bytes(b"{}")
    elif mutation == "run_claim_bytes":
        (caller.OLD_LEDGER / f"{caller.previous.AUTHORIZATION_ID}.run-claim.json").write_bytes(b"{}")
    elif mutation == "result_bytes":
        caller.OLD_RESULT_PATH.write_bytes(b"{}")
    else:
        if mutation == "rehash_wrong_total":
            result["known_cost_microusd"] += 1
        else:
            result["score"]["calibration_passed"] = not result["score"]["calibration_passed"]
        caller.OLD_RESULT_PATH.write_bytes(caller.canonical(result))
        monkeypatch.setattr(caller, "OLD_RESULT_SHA", caller.digest(caller.canonical(result)))
    with pytest.raises(caller.PilotError):
        caller.admit_checkpoint(admitted)
