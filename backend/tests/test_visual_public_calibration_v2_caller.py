"""One-use networkless caller contracts with invented pages and responses."""
import asyncio
import copy
import json
from pathlib import Path
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import run_visual_public_calibration_v2 as caller
from test_visual_public_calibration_v2_score import invented


def response(labels=None, **usage_overrides):
    labels = labels or ["unrelated"] * 4
    value = {"question_status": "clear", "pages": [
        {"id": sid, "usefulness": label, "cue_locates": label in ("direct", "concrete_learning_step")}
        for sid, label in zip(caller.ISSUED, labels, strict=True)]}
    usage = {"promptTokenCount": 1000, "candidatesTokenCount": 150, "thoughtsTokenCount": 400, "totalTokenCount": 1550}
    usage.update(usage_overrides)
    return {"modelVersion": caller.MODEL, "usageMetadata": usage, "candidates": [
        {"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(value)}]}}]}


def test_id_only_response_and_thinking_tokens_are_counted():
    value, tokens = caller.parse_response(httpx.Response(200, json=response(["direct", "topic_only", "unrelated", "uncertain"])))
    assert value["selected_ids"] == ["S01"]
    assert value["generated_answer"] is False
    assert tokens == (1000, 550)


@pytest.mark.parametrize("mutation,code", [
    ("model", "provider_model_mismatch"), ("missing_usage", "provider_usage_invalid"),
    ("bool_usage", "provider_usage_invalid"), ("huge_input", "provider_token_limit_exceeded"),
    ("huge_thoughts", "provider_token_limit_exceeded"), ("total_below_sum", "provider_usage_invalid"),
    ("new_id", "provider_verdict_invalid"), ("answer", "provider_verdict_invalid"),
    ("finish", "provider_finish_invalid"), ("two_candidates", "provider_candidate_invalid"),
    ("oversize", "provider_response_oversize")])
def test_malformed_and_overbudget_provider_data_stops_safely(mutation, code):
    body = response()
    if mutation == "model":
        body["modelVersion"] = "another-model"
    elif mutation == "missing_usage":
        del body["usageMetadata"]
    elif mutation == "bool_usage":
        body["usageMetadata"]["promptTokenCount"] = True
    elif mutation == "huge_input":
        body["usageMetadata"].update(promptTokenCount=40000, totalTokenCount=40550)
    elif mutation == "huge_thoughts":
        body["usageMetadata"].update(thoughtsTokenCount=3000, totalTokenCount=4150)
    elif mutation == "total_below_sum":
        body["usageMetadata"]["totalTokenCount"] = 1400
    elif mutation in ("new_id", "answer"):
        value = json.loads(body["candidates"][0]["content"]["parts"][0]["text"])
        if mutation == "new_id":
            value["pages"][0]["id"] = "S99"
        else:
            value["answer"] = "forbidden"
        body["candidates"][0]["content"]["parts"][0]["text"] = json.dumps(value)
    elif mutation == "finish":
        body["candidates"][0]["finishReason"] = "MAX_TOKENS"
    elif mutation == "two_candidates":
        body["candidates"].append(copy.deepcopy(body["candidates"][0]))
    else:
        body["padding"] = "x" * 65536
    with pytest.raises(caller.PilotError, match=code):
        caller.parse_response(httpx.Response(200, json=body))


@pytest.mark.parametrize("status,code", [(503, "provider_http_503"), (429, "provider_http_429"), (400, "provider_http_permanent")])
def test_numeric_http_failures_never_expose_body(status, code):
    with pytest.raises(caller.PilotError, match=code):
        caller.parse_response(httpx.Response(status, text="private provider detail"))


def test_bound_file_requires_external_hash_canonical_unique_json(tmp_path):
    file = tmp_path / "file.json"
    raw = caller.canonical({"synthetic": True})
    file.write_bytes(raw)
    assert caller.read_bound(file, caller.digest(raw)) == {"synthetic": True}
    with pytest.raises(caller.PilotError):
        caller.read_bound(file, "a" * 64)
    raw = b'{"synthetic":true,"synthetic":false}'
    file.write_bytes(raw)
    with pytest.raises(caller.PilotError):
        caller.read_bound(file, caller.digest(raw))


def test_full_cost_guard_covers_all_67_attempts():
    assert caller.cost(caller.MAX_INPUT, caller.MAX_OUTPUT) == 14951
    assert 67 * caller.cost(caller.MAX_INPUT, caller.MAX_OUTPUT) <= caller.COST_CAP_MICROUSD
    assert caller.guards()["input_total"] == 2195456
    assert caller.guards()["output_total"] == 137216


def test_shuffled_blind_review_ids_are_bound_to_original_slates_not_ordinals():
    rows = [{"old_group_id": f"G{g:03d}", "group_id": f"Q{67-g:03d}",
             "old_candidate_id": f"S{c:02d}", "pair_id": f"P{(g-1)*4+c:03d}"}
            for g in range(1, 67) for c in range(1, 5)]
    mapping = caller.bind_group_ids(rows)
    assert mapping["G001"] == "Q066" and mapping["G066"] == "Q001"
    rows[0]["group_id"] = "Q001"
    with pytest.raises(caller.PilotError):
        caller.bind_group_ids(rows)


class Clock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now

    async def sleep(self, value):
        self.now += value


def fake_admission():
    overlay, ids = invented()
    return {"overlay": overlay, "expected_ids": ids, "known_images": {"synthetic"},
            "request_roster_sha256": "a" * 64, "requests": [
                {"group_id": gid, "path": "synthetic", "wire_sha256": "b" * 64,
                 "rest_sha256": caller.digest(b"synthetic")} for gid in ids]}


def test_failure_counts_once_no_retry_and_unreachable_no_match_stops(tmp_path, monkeypatch):
    admitted = fake_admission()
    # Put the admitted no-match control first; timeout cannot count as a valid empty result.
    admitted["requests"] = [admitted["requests"][-1]] + admitted["requests"][:-1]
    monkeypatch.setattr(caller, "read_bound", lambda *a, **k: {})
    monkeypatch.setattr(caller, "rest_body", lambda *a: b"synthetic")
    output, ledger = tmp_path / "out", tmp_path / "ledger"
    output.mkdir()
    ledger.mkdir()
    physical = []
    async def send(body):
        physical.append(body)
        raise TimeoutError("do not print this")
    clock = Clock()
    result = asyncio.run(caller.run(admitted, "c" * 64, output, send, ledger=ledger,
                                   clock=clock, sleep=clock.sleep))
    assert len(physical) == result["provider_calls"] == 1
    assert result["reason"] == "quality_unreachable"
    assert result["unknown_cost_attempts"] == 1
    assert result["score"]["metrics"]["valid_empty_no_match"] == 0
    assert result["score"]["metrics"]["total_request_denominator"] == 67
    assert "do not print this" not in (output / "attempt-Q067.json").read_text()
    with pytest.raises(FileExistsError):
        asyncio.run(caller.run(admitted, "d" * 64, output, send, ledger=ledger))
    assert len(physical) == 1


def test_permanent_error_stops_immediately_with_cost_uncertainty(tmp_path, monkeypatch):
    admitted = fake_admission()
    monkeypatch.setattr(caller, "read_bound", lambda *a, **k: {})
    monkeypatch.setattr(caller, "rest_body", lambda *a: b"synthetic")
    output, ledger = tmp_path / "out", tmp_path / "ledger"
    output.mkdir()
    ledger.mkdir()
    async def send(body):
        return httpx.Response(400, text="do not retain")
    result = asyncio.run(caller.run(admitted, "c" * 64, output, send, ledger=ledger))
    assert result["provider_calls"] == 1
    assert result["reason"] == "provider_http_permanent"
    assert result["known_cost_microusd"] == 0 and result["unknown_cost_attempts"] == 1
    assert not result["score"]["calibration_passed"]


def test_complete_injected_transport_keeps_spacing_cost_and_67_receipts(tmp_path, monkeypatch):
    admitted = fake_admission()
    monkeypatch.setattr(caller, "read_bound", lambda *a, **k: {})
    monkeypatch.setattr(caller, "rest_body", lambda *a: b"synthetic")
    output, ledger = tmp_path / "out", tmp_path / "ledger"
    output.mkdir()
    ledger.mkdir()
    starts = []
    clock = Clock()
    async def send(body):
        index = len(starts)
        starts.append(clock())
        gid = admitted["requests"][index]["group_id"]
        good = {r["candidate_id"] for r in admitted["overlay"] if r["group_id"] == gid and r["qualification"] == "Yes"}
        clock.now += 0.1
        return httpx.Response(200, json=response(["direct" if sid in good else "unrelated" for sid in caller.ISSUED]))
    result = asyncio.run(caller.run(admitted, "c" * 64, output, send, ledger=ledger, clock=clock, sleep=clock.sleep))
    assert result["provider_calls"] == 67 and result["score"]["calibration_passed"]
    assert all(b - a >= 20 for a, b in zip(starts, starts[1:]))
    assert len(list(output.glob("attempt-*.json"))) == 67
    assert len(list(ledger.glob("*-Q*.claim.json"))) == 67
    assert result["known_cost_microusd"] == 67 * caller.cost(1000, 550)
    assert result["unknown_cost_attempts"] == 0


def test_only_dedicated_key_is_read_and_duplicate_assignment_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(caller, "REPO", tmp_path)
    env = tmp_path / ".env"
    env.write_text('DATABASE_URL=unrelated-secret\nRAG_SOURCE_JUDGE_API_KEY="synthetic-key" # local\n', encoding="utf-8")
    assert caller.read_key() == "synthetic-key"
    env.write_text('RAG_SOURCE_JUDGE_API_KEY=synthetic-one\nRAG_SOURCE_JUDGE_API_KEY=synthetic-two\n', encoding="utf-8")
    with pytest.raises(caller.PilotError, match="source_judge_key_unavailable"):
        caller.read_key()
