"""Keyless contract tests for the dormant public-only 3.6 diagnostic."""

import asyncio
import json
from pathlib import Path
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import diagnose_public_source_id_36 as diagnostic  # noqa: E402
from evaluate_source_id_multipdf import digest  # noqa: E402
from app.ai.source_judgment import build_source_id_request, canonical_bytes  # noqa: E402


def _wire(source_id="S01"):
    return build_source_id_request(
        "Which public source contains this definition?",
        [{"id": source_id, "page": 2,
          "page_text": "A public definition from the reviewed PDF.",
          "cue": "A public definition"}],
    )


def _response(selected=("S01",), *, status=200, input_tokens=50,
              output_tokens=5, thought_tokens=3):
    body = {
        "candidates": [{"finishReason": "STOP", "content": {"parts": [{
            "text": json.dumps({"selected_ids": selected})}]} }],
        "usageMetadata": {"promptTokenCount": input_tokens,
                          "candidatesTokenCount": output_tokens,
                          "thoughtsTokenCount": thought_tokens,
                          "totalTokenCount": input_tokens + output_tokens + thought_tokens},
    }
    return httpx.Response(status, json=body,
                          request=httpx.Request("POST", diagnostic.ENDPOINT))


def _approved_receipt():
    return {
        "schema": diagnostic.APPROVAL_SCHEMA,
        "authorization_id": diagnostic.AUTHORIZATION_ID,
        "operator_approved": True,
        "previous_failed_cost_unknown": True,
        "endpoint": diagnostic.ENDPOINT,
        "model": diagnostic.MODEL,
        "source_packet_sha256": diagnostic.PACKET_SHA256,
        "control_body_sha256": diagnostic.CONTROL_BODY_SHA256,
        "first_slate_body_sha256": diagnostic.FIRST_BODY_SHA256,
        "max_calls": diagnostic.MAX_CALLS,
        "max_input_tokens_per_call": diagnostic.MAX_INPUT_PER_CALL,
        "max_output_tokens_per_call": diagnostic.MAX_OUTPUT_PER_CALL,
        "max_input_tokens_total": diagnostic.MAX_INPUT_TOTAL,
        "max_output_tokens_total": diagnostic.MAX_OUTPUT_TOTAL,
        "max_cost_microusd": diagnostic.MAX_COST_MICROUSD,
        "input_price_usd_per_million": diagnostic.INPUT_PRICE_USD_PER_MILLION,
        "output_price_usd_per_million": diagnostic.OUTPUT_PRICE_USD_PER_MILLION,
        "max_call_seconds": diagnostic.MAX_CALL_SECONDS,
        "max_total_seconds": diagnostic.MAX_TOTAL_SECONDS,
        "min_start_interval_seconds": diagnostic.MIN_START_INTERVAL_SECONDS,
    }


def _wires(monkeypatch):
    first = _wire()
    candidate = first["user_payload"]["candidates"][0]
    control = build_source_id_request(
        "Which lecture page contains this public excerpt?",
        [{"id": candidate["id"], "page": candidate["page"],
          "page_text": candidate["cue"], "cue": candidate["cue"]}],
    )
    for name, wire in (("CONTROL_WIRE_SHA256", control),
                       ("FIRST_WIRE_SHA256", first)):
        monkeypatch.setattr(diagnostic, name, digest(canonical_bytes(wire)))
    for name, wire in (("CONTROL_BODY_SHA256", control),
                       ("FIRST_BODY_SHA256", first)):
        monkeypatch.setattr(
            diagnostic, name,
            digest(canonical_bytes(diagnostic._rest_body(wire))),
        )
    return control, first


def test_public_packet_is_rebuilt_and_hashed(monkeypatch, tmp_path):
    wires = _wires(monkeypatch)
    packet = {"public": "only"}
    first = {"status": "callable", "wire": wires[1],
             "wire_sha256": diagnostic.FIRST_WIRE_SHA256}
    monkeypatch.setattr(diagnostic, "read_pinned", lambda *_: packet)
    monkeypatch.setattr(diagnostic, "_split_requests", lambda *_: [first])
    assert diagnostic.public_requests(tmp_path) == wires
    first["wire_sha256"] = "0" * 64
    with pytest.raises(diagnostic.PilotFailure, match="first_public_slate_mismatch"):
        diagnostic.public_requests(tmp_path)


def test_approval_requires_the_exact_new_operator_identity(tmp_path):
    approval = _approved_receipt()
    path = tmp_path / "approval.json"
    approval["authorization_id"] = "wrong-approval"
    path.write_bytes(canonical_bytes(approval))
    sha = digest(path.read_bytes())
    with pytest.raises(diagnostic.PilotFailure,
                       match="approval_envelope_mismatch"):
        diagnostic.validate_approval(path, sha)
    approval["authorization_id"] = diagnostic.AUTHORIZATION_ID
    path.write_bytes(canonical_bytes(approval))
    sha = digest(path.read_bytes())
    assert diagnostic.validate_approval(path, sha) == approval
    approval["max_calls"] = 3
    path.write_bytes(canonical_bytes(approval))
    with pytest.raises(diagnostic.PilotFailure, match="approval_envelope_mismatch"):
        diagnostic.validate_approval(path, digest(path.read_bytes()))


def test_worst_case_stays_below_four_cents():
    assert diagnostic.MAX_CALLS * diagnostic._cost_microusd(8192, 1024) == 39_936
    assert diagnostic.MAX_COST_MICROUSD == 40_000
    assert diagnostic.MODEL == "gemini-3.6-flash"
    assert diagnostic.ENDPOINT.endswith("/models/gemini-3.6-flash:generateContent")


@pytest.mark.asyncio
async def test_exact_https_transport_and_no_redirect():
    seen = []

    async def handler(request):
        seen.append(request)
        return _response()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler),
                                 follow_redirects=False) as client:
        await diagnostic.http_call(client, "fake-key", _wire())
    assert len(seen) == 1
    assert str(seen[0].url) == diagnostic.ENDPOINT
    assert seen[0].headers["x-goog-api-key"] == "fake-key"
    body = json.loads(seen[0].content)
    assert body["store"] is False
    assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}


@pytest.mark.asyncio
async def test_control_503_stops_without_second_request_or_content(monkeypatch,
                                                                     tmp_path):
    wires = _wires(monkeypatch)
    calls = 0

    async def transport(_):
        nonlocal calls
        calls += 1
        return httpx.Response(503, text="sensitive echoed content",
                              headers={"Retry-After": "7"},
                              request=httpx.Request("POST", diagnostic.ENDPOINT))

    result = await diagnostic.run_once(
        wires, tmp_path, transport, approval_sha256="a" * 64,
        claim_path=tmp_path.parent / "one-time-approval.claim",
    )
    assert calls == result["attempts"] == 1
    assert result["calls"][0]["http_status"] == 503
    assert result["calls"][0]["retry_after_seconds"] == 7
    assert result["complete"] is False
    assert result["failed_attempt_cost_unknown"] is True
    saved = (tmp_path / "diagnostic-result.json").read_text()
    assert "sensitive echoed content" not in saved
    assert "selected_ids" not in saved
    assert "S01" not in saved
    assert (tmp_path / "call-01.claim").exists()
    assert not (tmp_path / "call-02.claim").exists()


@pytest.mark.asyncio
async def test_valid_control_allows_exactly_one_followup_with_six_second_gap(
        monkeypatch, tmp_path):
    wires = _wires(monkeypatch)
    now = [0.0]
    starts = []

    async def transport(_):
        starts.append(now[0])
        return _response()

    async def sleep(seconds):
        now[0] += seconds

    result = await diagnostic.run_once(
        wires, tmp_path, transport, approval_sha256="b" * 64,
        claim_path=tmp_path.parent / "two-time-approval.claim",
        clock=lambda: now[0], sleeper=sleep,
    )
    assert result["complete"] is True
    assert result["attempts"] == 2
    assert starts == [0.0, 6.0]
    assert all(row["validated"] and row["input_tokens"] == 50
               for row in result["calls"])
    saved = (tmp_path / "diagnostic-result.json").read_text()
    assert "selected_ids" not in saved
    assert "S01" not in saved
    second_output = tmp_path.parent / "another-output-for-same-approval"
    second_output.mkdir()
    with pytest.raises(FileExistsError):
        await diagnostic.run_once(
            wires, second_output, transport, approval_sha256="b" * 64,
            claim_path=tmp_path.parent / "two-time-approval.claim",
        )
    assert len(starts) == 2


@pytest.mark.asyncio
async def test_invalid_id_or_usage_blocks_second_call(monkeypatch, tmp_path):
    wires = _wires(monkeypatch)
    calls = 0

    async def transport(_):
        nonlocal calls
        calls += 1
        return _response(selected=("S02",))

    result = await diagnostic.run_once(
        wires, tmp_path, transport, approval_sha256="c" * 64,
        claim_path=tmp_path.parent / "invalid-approval.claim",
    )
    assert calls == 1
    assert result["calls"][0]["http_status"] == 200
    assert result["calls"][0]["validated"] is False
    assert result["complete"] is False

    other = tmp_path.parent / "invalid-usage-output"
    other.mkdir()
    calls = 0

    async def invalid_usage(_):
        nonlocal calls
        calls += 1
        return _response(input_tokens=8193)

    result = await diagnostic.run_once(
        wires, other, invalid_usage, approval_sha256="e" * 64,
        claim_path=tmp_path.parent / "invalid-usage-approval.claim",
    )
    assert calls == 1
    assert result["calls"][0]["http_status"] == 200
    assert result["calls"][0]["validated"] is False


@pytest.mark.asyncio
async def test_second_503_preserves_known_first_usage(monkeypatch, tmp_path):
    wires = _wires(monkeypatch)
    calls = 0

    async def transport(_):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response()
        return httpx.Response(503, text="do not write",
                              request=httpx.Request("POST", diagnostic.ENDPOINT))

    result = await diagnostic.run_once(
        wires, tmp_path, transport, approval_sha256="d" * 64,
        claim_path=tmp_path.parent / "second-approval.claim",
    )
    assert result["attempts"] == 2
    assert result["calls"][1]["http_status"] == 503
    assert result["known_cost_microusd"] == diagnostic._cost_microusd(50, 8)
    assert result["failed_attempt_cost_unknown"] is True
    assert "do not write" not in (tmp_path / "diagnostic-result.json").read_text()


@pytest.mark.asyncio
async def test_second_call_uses_only_remaining_global_seconds(monkeypatch, tmp_path):
    wires = _wires(monkeypatch)
    now = [0.0]
    allowed_timeouts = []
    calls = 0

    async def transport(_):
        nonlocal calls
        calls += 1
        if calls == 1:
            now[0] = 116.0
        return _response()

    async def bounded_wait(coroutine, timeout):
        allowed_timeouts.append(timeout)
        response = await coroutine
        if len(allowed_timeouts) == 2:
            now[0] += timeout
            raise TimeoutError
        return response

    monkeypatch.setattr(diagnostic.asyncio, "wait_for", bounded_wait)
    result = await diagnostic.run_once(
        wires, tmp_path, transport, approval_sha256="f" * 64,
        claim_path=tmp_path.parent / "global-deadline-approval.claim",
        clock=lambda: now[0],
    )
    assert calls == 2
    assert allowed_timeouts == [30, 4.0]
    assert result["attempts"] == 2
    assert result["complete"] is False
    assert result["calls"][1]["elapsed_ms"] == 4000
    assert result["failed_attempt_cost_unknown"] is True
    assert result["known_cost_microusd"] == diagnostic._cost_microusd(50, 8)


@pytest.mark.asyncio
async def test_spacing_cannot_overrun_global_allowance(monkeypatch, tmp_path):
    wires = _wires(monkeypatch)
    monkeypatch.setattr(diagnostic, "MAX_TOTAL_SECONDS", 5)
    calls = 0

    async def transport(_):
        nonlocal calls
        calls += 1
        return _response()

    result = await diagnostic.run_once(
        wires, tmp_path, transport, approval_sha256="9" * 64,
        claim_path=tmp_path.parent / "spacing-deadline-approval.claim",
        clock=lambda: 0.0,
    )
    assert calls == result["attempts"] == 1
    assert result["complete"] is False
    assert result["failed_attempt_cost_unknown"] is False
    assert not (tmp_path / "call-02.claim").exists()
