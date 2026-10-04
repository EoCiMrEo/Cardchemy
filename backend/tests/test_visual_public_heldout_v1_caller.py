"""Synthetic transport and authorization tests; no PDF, credential or provider."""
import asyncio
import copy
import json
from pathlib import Path
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import run_visual_public_heldout_v1 as caller
import launch_visual_public_heldout_v1 as launcher
from test_visual_public_heldout_v1_score import fixture
from test_visual_public_calibration_v2_caller import Clock, response


def admitted():
    overlay, _, expected = fixture()
    requests = [{"group_id": gid, "path": f"{gid}.json", "wire_sha256": "a" * 64,
                 "rest_sha256": caller.digest(b"synthetic"), "rest_bytes": 9} for gid in expected]
    return dict(overlay=overlay, expected_ids=expected, requests=requests, known_images=set(),
                request_roster_sha256=caller.digest(caller.canonical(requests)), calibration_binding={"passed": True})


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(caller, "read_bound", lambda *a, **k: {})
    monkeypatch.setattr(caller, "rest_body", lambda *a: b"synthetic")
    out, ledger = tmp_path / "out", tmp_path / "ledger"
    out.mkdir(); ledger.mkdir()
    return out, ledger


def test_envelope_guard_precedes_key_and_resource_reads(tmp_path, monkeypatch):
    monkeypatch.setattr(caller, "LIVE_AUTHORIZED", False)
    monkeypatch.setattr(caller.previous, "read_key", lambda: pytest.fail("credential touched"))
    monkeypatch.setattr(caller.visual, "_inside_windows_job", lambda: pytest.fail("resource read"))
    with pytest.raises(caller.PilotError, match="precise_provider_envelope_not_authorized"):
        asyncio.run(caller.execute({}, "a" * 64, tmp_path))
    g = caller.guards()
    assert g["max_calls"] == 60 and g["input_total"] == 1966080 and g["output_total"] == 245760
    assert g["new_cost_cap_microusd"] == 1250000 and g["retries"] == 0
    assert 60 * caller.cost(32768, 4096) == 1204260
    assert g["heldout_permitted"] and not g["private_data_permitted"] and not g["ask_activation_permitted"]


def test_rest_preserves_actual_wire_and_uses_calibrated_prompt(monkeypatch):
    wire = {"generationConfig": {"maxOutputTokens": 4096}, "contents": ["opaque"]}
    before = copy.deepcopy(wire)
    def rest(parent, *args):
        assert parent["generationConfig"]["maxOutputTokens"] == 2048
        return b"bound output4096"
    monkeypatch.setattr(caller.calibration, "rest_body", rest)
    assert caller.rest_body(wire, set(), set()) == b"bound output4096" and wire == before
    wire["generationConfig"]["maxOutputTokens"] = 2048
    with pytest.raises(caller.PilotError, match="heldout_output_contract_invalid"):
        caller.rest_body(wire, set(), set())


def test_sixty_fresh_results_complete_with_spacing_and_no_replay(tmp_path, monkeypatch):
    a = admitted(); out, ledger = setup(tmp_path, monkeypatch)
    clock, starts = Clock(), []
    async def send(body):
        starts.append(clock.now)
        gid = a["requests"][len(starts)-1]["group_id"]
        good = {r["candidate_id"] for r in a["overlay"] if r["group_id"] == gid and r["qualification"] == "Yes"}
        return httpx.Response(200, json=response(["direct" if sid in good else "unrelated" for sid in caller.ISSUED]))
    result = asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger, clock=clock, sleep=clock.sleep))
    assert result["provider_calls"] == 60 and result["score"]["heldout_passed"]
    assert all(b-a >= 20 for a,b in zip(starts, starts[1:]))
    assert result["unknown_cost_attempts"] == 0 and not result["private_data_sent"] and not result["ask_enabled"]
    assert len(result["receipt_hashes"]) == 60
    with pytest.raises(FileExistsError):
        asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger))


@pytest.mark.parametrize("failure", ["timeout", "503", "unfinished"])
def test_third_failed_group_stops_without_retry_or_nomatch_credit(tmp_path, monkeypatch, failure):
    a = admitted(); out, ledger = setup(tmp_path, monkeypatch)
    clock, attempts = Clock(), []
    async def send(body):
        attempts.append(body)
        if failure == "timeout":
            raise httpx.ReadTimeout("untrusted detail")
        if failure == "503":
            return httpx.Response(503, content=b"private-looking provider body")
        r = response(["unrelated"] * 4)
        r["candidates"][0]["finishReason"] = "MAX_TOKENS"
        return httpx.Response(200, json=r)
    result = asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger, clock=clock, sleep=clock.sleep))
    assert len(attempts) == result["provider_calls"] == 3
    assert result["reason"] == "quality_unreachable" and not result["score"]["heldout_passed"]
    assert result["score"]["metrics"]["valid_empty_no_match"] == 0
    assert "untrusted detail" not in json.dumps(result) and "provider body" not in json.dumps(result)
    assert result["unknown_cost_attempts"] == (0 if failure == "unfinished" else 3)


@pytest.mark.parametrize("status", [400, 401, 403])
def test_permanent_failure_stops_one_attempt(tmp_path, monkeypatch, status):
    a = admitted(); out, ledger = setup(tmp_path, monkeypatch)
    clock = Clock()
    async def send(body): return httpx.Response(status, content=b"not retained")
    result = asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger, clock=clock, sleep=clock.sleep))
    assert result["provider_calls"] == 1 and result["reason"] == "provider_http_permanent"


def test_unknown_source_cannot_be_counted_as_useful(tmp_path, monkeypatch):
    a = admitted(); a["overlay"][3]["qualification"] = "Unsure"
    out, ledger = setup(tmp_path, monkeypatch); clock = Clock()
    async def send(body): return httpx.Response(200, json=response(["direct", "unrelated", "unrelated", "direct"]))
    result = asyncio.run(caller.run(a, "a" * 64, out, send, ledger=ledger, clock=clock, sleep=clock.sleep))
    assert result["provider_calls"] == 1 and result["reason"] == "quality_unreachable"
    assert result["score"]["metrics"]["unknown_displayed_cards"] == 1


def test_external_approval_covers_code_and_roster(monkeypatch):
    a = admitted()
    a.update(input_freeze_sha256=caller.INPUT_FREEZE_SHA, qualification_freeze_sha256=caller.QUALIFICATION_FREEZE_SHA)
    monkeypatch.setattr(caller, "code_hashes", lambda:{"synthetic": "a" * 64})
    expected = caller.expected_approval(a)
    monkeypatch.setattr(caller, "read_bound", lambda *args: expected)
    caller.validate_approval(Path("synthetic"), "b" * 64, a)
    a["request_roster_sha256"] = "c" * 64
    with pytest.raises(caller.PilotError, match="approval_contract_changed"):
        caller.validate_approval(Path("synthetic"), "b" * 64, a)


def test_launcher_stays_fenced_and_scrubs_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(caller, "LIVE_AUTHORIZED", False)
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *a, **k:pytest.fail("no worker"))
    with pytest.raises(caller.visual.PreparationError, match="fresh_provider_authorization_required"):
        launcher.detach(tmp_path / "approval.json", "a" * 64, tmp_path / "output")
    env = launcher.child_env({"SystemRoot": "C:/Windows", "RAG_SOURCE_JUDGE_API_KEY": "forbidden",
                              "HTTP_PROXY": "forbidden", "DATABASE_URL": "forbidden"})
    assert "forbidden" not in env.values()
