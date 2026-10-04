"""No-network successor tests: historical costs, fresh dispatch and 4,096 thinking cap."""
import asyncio
import copy
from pathlib import Path
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import run_visual_public_calibration_v5 as caller
from test_visual_public_calibration_v4_caller import fake_admission as old_admission
from test_visual_public_calibration_v2_caller import Clock, response


def fake_admission():
    admitted = old_admission()
    admitted["original_requests"] = copy.deepcopy(admitted["requests"])
    rows, receipts, bindings = [], {}, {}
    for gid in caller.OLD_GROUPS:
        request = next(r for r in admitted["requests"] if r["group_id"] == gid)
        good = {r["candidate_id"] for r in admitted["overlay"] if r["group_id"] == gid and r["qualification"] == "Yes"}
        verdict, usage = caller.parse_response(httpx.Response(200, json=response([
            "direct" if sid in good else "unrelated" for sid in caller.ISSUED])))
        row = {"group_id": gid, "state": "completed", "selected_ids": verdict["selected_ids"], "question_status": "clear"}
        receipt = {**row, "request_sha256": request["rest_sha256"], "attempt_claim_sha256": "c" * 64,
                   "latency_ms": 100, "reported_usage": {"input": usage[0], "output": usage[1]},
                   "known_cost_microusd": caller.cost(*usage), "failure_code": None, "verdict": verdict}
        rows.append(row)
        receipts[gid] = receipt
        bindings[gid] = {"receipt_sha256": caller.digest(caller.canonical(receipt)), "claim_sha256": "c" * 64,
                         "wire_sha256": request["wire_sha256"], "rest_sha256": request["rest_sha256"]}
    failures = {}
    for gid in (*caller.OLD_FAILED_GROUPS, "Q019", "Q032", "Q053"):
        failures[gid] = {"receipt_sha256": "a" * 64, "claim_sha256": "b" * 64,
                         "wire_sha256": "c" * 64, "rest_sha256": "d" * 64,
                         "failure_code": "provider_finish_invalid" if gid in caller.OLD_FAILED_GROUPS else "provider_timeout",
                         "cost_unknown": gid not in caller.OLD_FAILED_GROUPS}
        if gid in caller.OLD_FAILED_GROUPS:
            failures[gid]["known_cost_microusd"] = 5000
    binding = {"old_authorization_id": caller.checkpoint_previous.AUTHORIZATION_ID,
               "old_result_sha256": caller.OLD_RESULT_SHA, "old_approval_sha256": caller.OLD_APPROVAL_SHA,
               "inherited_groups": list(caller.OLD_GROUPS), "receipt_bindings": bindings,
               "inherited_known_cost_microusd": caller.OLD_COST_MICROUSD,
               "inherited_input_tokens": caller.OLD_INPUT_TOKENS, "inherited_output_tokens": caller.OLD_OUTPUT_TOKENS,
               "prior_failed_attempts": failures, "rows_sha256": caller.digest(caller.canonical(rows))}
    admitted["checkpoint"] = {"rows": rows, "receipts": receipts, "binding": binding,
                              "binding_sha256": caller.digest(caller.canonical(binding))}
    return admitted


def test_fresh_envelope_required_before_key_or_resource_read(tmp_path, monkeypatch):
    monkeypatch.setattr(caller, "LIVE_AUTHORIZED", False)
    monkeypatch.setattr(caller.previous, "read_key", lambda: pytest.fail("no key"))
    with pytest.raises(caller.PilotError, match="precise_provider_envelope_not_authorized"):
        asyncio.run(caller.execute({}, "a" * 64, tmp_path))
    g = caller.guards()
    assert g["input_total"] == 1540096 and g["output_total"] == 192512
    assert g["output_per_call"] == 4096 and g["max_calls"] == 47
    assert g["retries"] == 0 and g["minimum_valid_empty_no_match"] == 10
    assert 47 * caller.cost(caller.MAX_INPUT, caller.MAX_OUTPUT) == 943337
    assert g["new_cost_cap_microusd"] == 950000 and not g["heldout_permitted"]


def test_output_limit_counts_thinking_and_total_tokens():
    r = response(["direct"] + ["unrelated"] * 3)
    r["usageMetadata"].update(candidatesTokenCount=200, thoughtsTokenCount=3000, totalTokenCount=4200)
    verdict, usage = caller.parse_response(httpx.Response(200, json=r))
    assert usage == (1000, 3200) and verdict["selected_ids"] == ["S01"]
    r["usageMetadata"]["totalTokenCount"] = 5200
    with pytest.raises(caller.ContentError, match="provider_token_limit_exceeded"):
        caller.parse_response(httpx.Response(200, json=r))


def test_rest_changes_only_output_bound(monkeypatch):
    old = {"generationConfig": {"maxOutputTokens": 2048, "thinkingConfig": {"thinkingLevel": "HIGH"}},
           "contents": [{"parts": [{"text": "synthetic"}]}], "store": False}
    monkeypatch.setattr(caller.previous, "rest_body", lambda *a: caller.canonical(old))
    actual = __import__("json").loads(caller.rest_body({}, set(), set()))
    expected = copy.deepcopy(old)
    expected["generationConfig"]["maxOutputTokens"] = 4096
    assert actual == expected


def test_complete_success_reuses_twenty_never_replays_and_preserves_all_costs(tmp_path, monkeypatch):
    admitted = fake_admission()
    monkeypatch.setattr(caller, "read_bound", lambda *a, **k: {})
    monkeypatch.setattr(caller, "rest_body", lambda *a: b"synthetic")
    out, ledger = tmp_path / "out", tmp_path / "ledger"
    out.mkdir(); ledger.mkdir()
    remaining = [r for r in admitted["requests"] if r["group_id"] not in caller.OLD_GROUPS]
    clock, sent = Clock(), []
    async def send(body):
        gid = remaining[len(sent)]["group_id"]
        sent.append(gid)
        good = {r["candidate_id"] for r in admitted["overlay"] if r["group_id"] == gid and r["qualification"] == "Yes"}
        clock.now += 40
        return httpx.Response(200, json=response(["direct" if sid in good else "unrelated" for sid in caller.ISSUED]))
    result = asyncio.run(caller.run(admitted, "a" * 64, out, send, ledger=ledger, clock=clock, sleep=clock.sleep))
    assert len(sent) == result["provider_calls"] == 47 and not set(sent) & set(caller.OLD_GROUPS)
    assert set(caller.OLD_FAILED_GROUPS) <= set(sent)
    assert result["score"]["calibration_passed"] and result["total_provider_calls"] == 67
    assert result["physical_attempt_history_count"] == 73
    assert result["combined_known_cost_microusd"] == 130870 + 47 * caller.cost(1000, 550)
    assert len(result["prior_failed_attempts"]) == 6 and result["prior_unknown_cost_attempts"] == 3
    assert not result["heldout_opened"] and not result["ask_enabled"]
    with pytest.raises(FileExistsError):
        asyncio.run(caller.run(admitted, "a" * 64, out, send, ledger=ledger))


@pytest.mark.parametrize("mutation", ["lost_failure", "unknown_erased", "lost_success", "altered_receipt", "wrong_original_request"])
def test_historical_binding_rejects_tampering(mutation):
    admitted = fake_admission()
    c = admitted["checkpoint"]
    if mutation == "lost_failure": c["binding"]["prior_failed_attempts"].pop("Q003")
    elif mutation == "unknown_erased": c["binding"]["prior_failed_attempts"]["Q019"]["cost_unknown"] = False
    elif mutation == "lost_success": c["rows"].pop()
    elif mutation == "altered_receipt": c["receipts"]["Q013"]["selected_ids"] = []
    else: admitted["original_requests"][0]["rest_sha256"] = "e" * 64
    c["binding_sha256"] = caller.digest(caller.canonical(c["binding"]))
    with pytest.raises(caller.PilotError): caller._checkpoint_rows(admitted)


def test_third_new_failure_stops_without_automatic_retries(tmp_path, monkeypatch):
    admitted = fake_admission()
    monkeypatch.setattr(caller, "read_bound", lambda *a, **k: {})
    monkeypatch.setattr(caller, "rest_body", lambda *a: b"synthetic")
    out, ledger = tmp_path / "out", tmp_path / "ledger"
    out.mkdir(); ledger.mkdir()
    clock, sent = Clock(), []
    async def send(body):
        sent.append(body); clock.now += 60
        raise httpx.ReadTimeout("synthetic")
    r = asyncio.run(caller.run(admitted, "a" * 64, out, send, ledger=ledger, clock=clock, sleep=clock.sleep))
    assert len(sent) == r["provider_calls"] == 3 and r["reason"] == "quality_unreachable"
    assert r["unknown_cost_attempts"] == 3 and not r["score"]["calibration_passed"]


@pytest.mark.parametrize("status, expected", [(503, "provider_http_503"), (429, "provider_http_429"),
                                               (401, "provider_http_permanent"), (400, "provider_http_permanent")])
def test_non_200_retains_safe_classification_without_name_error(status, expected):
    with pytest.raises(caller.PilotError, match=expected):
        caller.parse_response(httpx.Response(status, content=b""))
