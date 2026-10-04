"""No-key fake-transport checks for the one-shot public PDF caller."""

import asyncio
import json
from pathlib import Path
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from run_public_source_id_multipdf import (  # noqa: E402
    APPROVAL_SCHEMA, AUTHORIZATION_ID, ENDPOINT, MAX_CALL_SECONDS, MAX_CALLS_TOTAL,
    MAX_COST_MICROUSD, MAX_INPUT_TOTAL, MAX_OUTPUT_TOTAL,
    MAX_TOTAL_SECONDS, MIN_START_INTERVAL_SECONDS, MODEL,
    MAX_INPUT_PER_CALL, MAX_OUTPUT_PER_CALL,
    PilotFailure, _cost_microusd, _rest_body, _validate_approval,
    _parse_provider_response, _http_call, _load_public_requests,
    run_once,
)
from evaluate_source_id_multipdf import SCHEMA, digest
from prepare_public_source_id_multipdf import canonical_bytes
from app.ai.source_judgment import build_source_id_request
from app.workers.rag_answer import _source_judge_rest_body


def wire(source_id="S01"):
    return build_source_id_request("How is the public method defined?", [{
        "id": source_id, "page": 2,
        "page_text": "The public method has an explicit definition.",
        "cue": "an explicit definition",
    }])


def model_response(selected=("S01",), *, status=200, finish="STOP",
                   input_tokens=50, output_tokens=5, thought_tokens=3):
    body = {"candidates": [{"finishReason": finish,
                            "content": {"parts": [{"text": json.dumps({
                                "selected_ids": selected})}]}}],
            "usageMetadata": {"promptTokenCount": input_tokens,
                              "candidatesTokenCount": output_tokens,
                              "thoughtsTokenCount": thought_tokens,
                              "totalTokenCount": input_tokens + output_tokens + thought_tokens}}
    return httpx.Response(status, json=body, request=httpx.Request("POST", ENDPOINT))


def prepared_rows(count=2):
    rows = []
    for number in range(count):
        prompt = wire()
        rows.append({"group_id": f"G{number:02d}", "status": "callable",
                     "wire": prompt, "wire_sha256": digest(canonical_bytes(prompt))})
    return {"schema": SCHEMA, "split": "calibration", "requests": rows}, {
        "requests_sha256": "1" * 64, "fingerprint": "2" * 64,
        "callable_count": count,
    }, {"split": "calibration", "requests_sha256": "1" * 64,
        "prior_cost_microusd": 0}


def test_rest_request_has_only_public_current_question_and_source_ids():
    body = _rest_body(wire())
    assert _source_judge_rest_body(wire(), 1024) == body
    assert set(body) == {"systemInstruction", "contents", "generationConfig", "store"}
    assert body["store"] is False
    assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}
    assert "temperature" not in body["generationConfig"]
    assert "tools" not in body
    sent = body["contents"][0]["parts"][0]["text"]
    assert "Current question:\nHow is the public method defined?" in sent
    assert "<S01 page=2>" in sent
    assert "The public method has an explicit definition." in sent
    assert "<cue>\nan explicit definition\n</cue>" in sent
    assert "private_history" not in sent
    assert len(canonical_bytes(body)) <= 8192


def test_rest_body_refuses_oversized_serialized_request(monkeypatch):
    import run_public_source_id_multipdf as caller
    monkeypatch.setattr(caller, "MAX_REST_REQUEST_BYTES", 10)
    with pytest.raises(PilotFailure, match="rest_body_budget"):
        _rest_body(wire())


def test_worst_case_96_call_budget_is_below_two_dollars():
    assert 96 * _cost_microusd(8192, 1024) == 1_916_928
    assert 96 * _cost_microusd(8192, 1024) <= MAX_COST_MICROUSD


@pytest.mark.asyncio
async def test_http_transport_posts_only_to_exact_endpoint_with_no_redirect():
    observed = []

    async def handler(request):
        observed.append(request)
        return model_response()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler),
                                 follow_redirects=False) as client:
        await _http_call(client, "fake-key-never-sent", wire())
    assert len(observed) == 1
    assert observed[0].method == "POST"
    assert str(observed[0].url) == ENDPOINT
    assert observed[0].headers["x-goog-api-key"] == "fake-key-never-sent"
    body = json.loads(observed[0].content)
    assert set(body) == {"systemInstruction", "contents", "generationConfig", "store"}


def test_provider_usage_and_finish_must_fit_envelope():
    assert _parse_provider_response(model_response(), ["S01"])[1:] == (50, 8)
    with pytest.raises(PilotFailure, match="provider_http_400"):
        _parse_provider_response(model_response(status=400), ["S01"])
    with pytest.raises(PilotFailure, match="provider_token_limit_exceeded"):
        _parse_provider_response(model_response(input_tokens=8193), ["S01"])
    with pytest.raises(PilotFailure, match="provider_token_limit_exceeded"):
        _parse_provider_response(model_response(output_tokens=1025), ["S01"])
    with pytest.raises(PilotFailure, match="provider_http_429"):
        _parse_provider_response(model_response(status=429), ["S01"])


def test_prepared_request_cannot_replace_pinned_public_page(tmp_path, monkeypatch):
    import run_public_source_id_multipdf as caller
    packet_dir = tmp_path / "source"
    prepared_dir = tmp_path / "prepared"
    packet_dir.mkdir()
    prepared_dir.mkdir()
    source = {"schema": "public_fixture", "groups": []}
    source_sha = digest(canonical_bytes(source))
    (packet_dir / "blind-review-packet.json").write_bytes(canonical_bytes(source))
    monkeypatch.setattr(caller, "PACKET_SHA256", source_sha)
    expected = []
    for number in range(48):
        prompt = wire()
        expected.append({"group_id": f"G{number:02d}", "status": "callable",
                         "wire": prompt, "wire_sha256": digest(canonical_bytes(prompt))})
    monkeypatch.setattr(caller, "_split_requests", lambda _source, _split: expected)
    labels_sha = "a" * 64
    freeze_sha = "b" * 64
    fingerprint = caller._fingerprint(source_sha, labels_sha, freeze_sha)
    prepared = {"schema": SCHEMA, "split": "calibration",
                "source_packet_sha256": source_sha, "model": MODEL,
                "thinking": "low", "max_output_tokens": 1024,
                "fingerprint": fingerprint,
                "requests": json.loads(json.dumps(expected))}
    request_path = prepared_dir / "requests.json"
    receipt_path = prepared_dir / "prepare-receipt.json"
    request_path.write_bytes(canonical_bytes(prepared))
    receipt = {"schema": SCHEMA, "status": "prepared_no_provider_call",
               "requests_sha256": digest(request_path.read_bytes()),
               "labels_sha256": labels_sha,
               "freeze_receipt_sha256": freeze_sha,
               "fingerprint": fingerprint, "callable_count": 48,
               "clarification_count": 0}
    receipt_path.write_bytes(canonical_bytes(receipt))
    _load_public_requests(prepared_dir, digest(receipt_path.read_bytes()), packet_dir)
    prepared["requests"][0] = {**prepared["requests"][0],
                               "wire": build_source_id_request(
                                   "Different question?", [{
                                       "id": "S01", "page": 2,
                                       "page_text": "Invented source text.",
                                       "cue": "Invented source text."}])}
    request_path.write_bytes(canonical_bytes(prepared))
    receipt["requests_sha256"] = digest(request_path.read_bytes())
    receipt_path.write_bytes(canonical_bytes(receipt))
    with pytest.raises(PilotFailure, match="public_request_source_mismatch"):
        _load_public_requests(prepared_dir, digest(receipt_path.read_bytes()), packet_dir)


@pytest.mark.asyncio
async def test_run_once_writes_only_id_rows_and_immutable_claims(tmp_path):
    prepared, receipt, approval = prepared_rows()
    approval_claim = tmp_path.parent / f"{tmp_path.name}-approval.claim"
    starts = []
    now = [0.0]

    async def transport(sent):
        starts.append((now[0], sent))
        return model_response()

    async def sleeper(seconds):
        now[0] += seconds

    result = await run_once(prepared, receipt, approval, tmp_path, transport,
                            approval_claim_path=approval_claim,
                            clock=lambda: now[0], sleeper=sleeper)
    assert result["status"] == "complete_one_shot"
    assert result["attempts"] == 2
    assert starts[1][0] - starts[0][0] >= 6
    assert (tmp_path / "live-run.claim").exists()
    assert (tmp_path / "call-01.claim").exists()
    assert (tmp_path / "call-02.claim").exists()
    output = (tmp_path / "response-ids.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(output) == 2
    assert all(set(json.loads(line)) == {"group_id", "wire_sha256", "raw_json"}
               for line in output)
    with pytest.raises(FileExistsError):
        await run_once(prepared, receipt, approval, tmp_path, transport,
                       approval_claim_path=approval_claim,
                       clock=lambda: now[0], sleeper=sleeper)
    assert len(starts) == 2


@pytest.mark.asyncio
async def test_same_approval_cannot_repeat_in_another_prepared_directory(tmp_path):
    prepared, receipt, approval = prepared_rows(1)
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    approval_claim = tmp_path.parent / f"{tmp_path.name}-approval.claim"
    calls = 0

    async def transport(_sent):
        nonlocal calls
        calls += 1
        return model_response()

    await run_once(prepared, receipt, approval, first, transport,
                   approval_claim_path=approval_claim)
    with pytest.raises(FileExistsError):
        await run_once(prepared, receipt, approval, second, transport,
                       approval_claim_path=approval_claim)
    assert calls == 1
    assert not (second / "live-run.claim").exists()


@pytest.mark.asyncio
async def test_timeout_consumes_claim_and_never_retries(tmp_path):
    prepared, receipt, approval = prepared_rows(1)
    approval_claim = tmp_path.parent / f"{tmp_path.name}-approval.claim"
    calls = 0

    async def transport(_sent):
        nonlocal calls
        calls += 1
        raise TimeoutError

    result = await run_once(prepared, receipt, approval, tmp_path, transport,
                            approval_claim_path=approval_claim)
    assert result["status"] == "stopped_no_retry"
    assert result["failed_attempt_cost_unknown"] is True
    assert calls == 1
    assert (tmp_path / "live-run.claim").exists()
    assert (tmp_path / "response-ids.jsonl").read_bytes() == b""


@pytest.mark.asyncio
async def test_http_failure_saves_only_numeric_status_and_stops(tmp_path):
    prepared, receipt, approval = prepared_rows(2)
    approval_claim = tmp_path.parent / f"{tmp_path.name}-approval.claim"
    calls = 0

    async def transport(_sent):
        nonlocal calls
        calls += 1
        return httpx.Response(404, text="do not retain error body",
                              request=httpx.Request("POST", ENDPOINT))

    result = await run_once(prepared, receipt, approval, tmp_path, transport,
                            approval_claim_path=approval_claim)
    assert result["status"] == "stopped_no_retry"
    assert result["reason"] == "provider_http_error"
    assert result["http_status"] == 404
    assert result["attempts"] == calls == 1
    assert b"do not retain" not in (tmp_path / "live-failure.json").read_bytes()
    assert (tmp_path / "response-ids.jsonl").read_bytes() == b""


@pytest.mark.asyncio
async def test_foreign_id_and_nonstop_finish_stop_without_scoring(tmp_path):
    prepared, receipt, approval = prepared_rows(1)
    approval_claim = tmp_path.parent / f"{tmp_path.name}-approval.claim"

    async def foreign(_sent):
        return model_response(("S02",))

    result = await run_once(prepared, receipt, approval, tmp_path, foreign,
                            approval_claim_path=approval_claim)
    assert result["reason"] == "provider_ids_invalid"
    assert (tmp_path / "response-ids.jsonl").read_bytes() == b""
    prepared, receipt, approval = prepared_rows(1)
    other = tmp_path / "other"
    other.mkdir()

    async def unfinished(_sent):
        return model_response(finish="MAX_TOKENS")

    result = await run_once(prepared, receipt, approval, other, unfinished,
                            approval_claim_path=tmp_path.parent / f"{tmp_path.name}-other.claim")
    assert result["reason"] == "provider_finish_invalid"


def test_approval_must_bind_exact_envelope_and_prepare_hash(tmp_path):
    prepared = {"split": "calibration"}
    receipt = {"requests_sha256": "1" * 64, "fingerprint": "2" * 64}
    base = {"schema": APPROVAL_SCHEMA, "authorization_id": AUTHORIZATION_ID,
            "operator_approved": True, "previous_failed_cost_unknown": True,
            "endpoint": ENDPOINT, "model": MODEL, "split": "calibration",
            "requests_sha256": receipt["requests_sha256"],
            "prepare_receipt_sha256": digest(canonical_bytes(receipt)),
            "fingerprint": receipt["fingerprint"],
            "max_calls_total": MAX_CALLS_TOTAL,
            "max_input_tokens_total": MAX_INPUT_TOTAL,
            "max_output_tokens_total": MAX_OUTPUT_TOTAL,
            "max_cost_microusd": MAX_COST_MICROUSD,
            "max_input_tokens_per_call": MAX_INPUT_PER_CALL,
            "max_output_tokens_per_call": MAX_OUTPUT_PER_CALL,
            "input_price_usd_per_million": "1.50",
            "output_price_usd_per_million": "7.50",
            "max_call_seconds": MAX_CALL_SECONDS,
            "max_total_seconds": MAX_TOTAL_SECONDS,
            "min_start_interval_seconds": MIN_START_INTERVAL_SECONDS,
            "prior_cost_microusd": 0}
    path = tmp_path / "approval.json"
    path.write_bytes(canonical_bytes(base))
    _validate_approval(path, digest(path.read_bytes()), prepared, receipt)
    base["max_cost_microusd"] = MAX_COST_MICROUSD * 2
    path.write_bytes(canonical_bytes(base))
    with pytest.raises(PilotFailure, match="approval_envelope_mismatch"):
        _validate_approval(path, digest(path.read_bytes()), prepared, receipt)
