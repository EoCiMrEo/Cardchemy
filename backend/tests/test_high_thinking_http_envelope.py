"""Synthetic transport regression; no real credentials, corpus or HTTP calls."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import httpx
import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import run_fresh_public_full_cue_high_thinking_v1 as consumed  # noqa: E402
import run_fresh_public_full_cue_high_thinking_v2 as candidate  # noqa: E402
import test_full_cue_high_thinking_public as controls  # noqa: E402


IDS = ["S01", "S02", "S03", "S04"]
LIMITS = {"max_input_tokens_per_call": 8_192,
          "max_output_tokens_per_call": 2_048}


def _payload() -> dict:
    return {
        "modelVersion": candidate.MODEL,
        "candidates": [{"finishReason": "STOP", "content": {"parts": [{
            "text": json.dumps({"verdicts": [
                {"id": identifier, "label": "DIRECT_RELATION"}
                for identifier in IDS]}),
            "thoughtSignature": "",
        }]}}],
        "usageMetadata": {"promptTokenCount": 300,
                          "candidatesTokenCount": 80,
                          "thoughtsTokenCount": 1_000,
                          "totalTokenCount": 1_380},
    }


def _envelope(size: int) -> bytes:
    payload = _payload()
    # Synthetic opaque metadata models the official optional response field.
    # It is not evidence that this field caused the actual G003 size failure.
    missing = size - len(candidate.canonical_bytes(payload))
    assert missing >= 0
    payload["candidates"][0]["content"]["parts"][0]["thoughtSignature"] = "A" * missing
    raw = candidate.canonical_bytes(payload)
    assert len(raw) == size
    return raw


def test_unapproved_transport_is_disabled_and_old_one_use_source_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # This control injects the preapproval state even after a separately
    # authorized real public pilot; it must never use that live envelope.
    monkeypatch.setattr(candidate, "LIVE_ENVELOPE_APPROVED", False)
    monkeypatch.setattr(candidate, "AUTHORIZATION_ID", "UNAPPROVED_synthetic_transport_v2")
    monkeypatch.setattr(candidate, "SPLIT_COST_CAPS_MICROUSD", {"calibration": 0, "heldout": 0})
    assert consumed.MAX_RESPONSE_BYTES == 8_192
    assert candidate.MAX_RESPONSE_BYTES == 65_536
    assert candidate.LIVE_ENVELOPE_APPROVED is False
    assert candidate.AUTHORIZATION_ID.startswith("UNAPPROVED")
    assert candidate.SPLIT_COST_CAPS_MICROUSD == {"calibration": 0, "heldout": 0}
    assert candidate.CLAIM_SCHEMA != consumed.CLAIM_SCHEMA
    assert candidate.APPROVAL_SCHEMA != consumed.APPROVAL_SCHEMA
    assert candidate.scorer is consumed.scorer
    assert candidate.parse_high_thinking_page_judge_output is consumed.parse_high_thinking_page_judge_output
    assert candidate.MAX_OUTPUT_PER_CALL == consumed.MAX_OUTPUT_PER_CALL == 2_048


@pytest.mark.parametrize("size", [8_192, 8_193, 16_384, 65_536])
def test_bounded_metadata_does_not_change_selected_ids_or_billable_usage(size: int) -> None:
    response = httpx.Response(200, content=_envelope(size))
    assert candidate._parse_response(response, IDS, LIMITS) == (
        ("S01", "S02", "S03"), 300, 1_080)
    if size > 8_192:
        with pytest.raises(consumed.PilotError, match="provider_response_oversize"):
            consumed._parse_response(response, IDS, LIMITS)


def test_more_than_transport_limit_still_fails_before_parsing() -> None:
    with pytest.raises(candidate.PilotError, match="provider_response_oversize"):
        candidate._parse_response(httpx.Response(200, content=_envelope(65_537)), IDS, LIMITS)


@pytest.mark.parametrize("kind,code", [
    ("large_visible_json", "provider_verdicts_invalid"),
    ("foreign_id", "provider_verdicts_invalid"),
    ("answer_field", "provider_verdicts_invalid"),
    ("extra_part", "provider_finish_invalid"),
    ("unfinished", "provider_finish_invalid"),
    ("token_overrun", "provider_token_limit_exceeded"),
])
def test_larger_transport_does_not_relax_model_output_or_token_guards(kind: str, code: str) -> None:
    payload = _payload()
    item = payload["candidates"][0]
    part = item["content"]["parts"][0]
    part["thoughtSignature"] = "A" * 16_384
    if kind == "large_visible_json":
        part["text"] += " " * 2_048
    elif kind == "foreign_id":
        part["text"] = part["text"].replace("S01", "FOREIGN")
    elif kind == "answer_field":
        visible = json.loads(part["text"])
        visible["answer"] = "Not allowed."
        part["text"] = json.dumps(visible)
    elif kind == "extra_part":
        item["content"]["parts"].append({"text": "", "thoughtSignature": "AA=="})
    elif kind == "unfinished":
        item["finishReason"] = "MAX_TOKENS"
    else:
        payload["usageMetadata"]["thoughtsTokenCount"] = 2_000
        payload["usageMetadata"]["totalTokenCount"] = 2_380
    with pytest.raises(candidate.InvalidContentResponse, match=code):
        candidate._parse_response(httpx.Response(200, json=payload), IDS, LIMITS)


@pytest.mark.parametrize("size,passes", [(16_384, True), (65_536, True), (65_537, False)])
def test_real_http_read_loop_is_bounded_and_has_no_retry(
    size: int, passes: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = _envelope(size)
    chunks_read: list[int] = []
    requests: list[httpx.Request] = []
    client_type = httpx.AsyncClient

    class FakeStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            for start in range(0, len(raw), 2_048):
                chunk = raw[start:start + 2_048]
                chunks_read.append(len(chunk))
                yield chunk

    async def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, stream=FakeStream())

    def local_client(**kwargs):
        return client_type(**kwargs, transport=httpx.MockTransport(handle))

    async def single_attempt(admitted, approval, output, send):
        response = await send({"synthetic": "no real question or source"})
        return candidate._parse_response(response, IDS, LIMITS)

    monkeypatch.setattr(candidate, "LIVE_ENVELOPE_APPROVED", True)
    monkeypatch.setattr(candidate, "_source_judge_key", lambda: "synthetic-test-key")
    monkeypatch.setattr(candidate, "run_split", single_attempt)
    monkeypatch.setattr(candidate.httpx, "AsyncClient", local_client)
    approval = {"endpoint": "https://provider.invalid/synthetic", "max_call_seconds": 30}
    operation = candidate._execute_http({}, approval, tmp_path / "unused")
    if passes:
        assert asyncio.run(operation) == (("S01", "S02", "S03"), 300, 1_080)
    else:
        with pytest.raises(candidate.PilotError, match="provider_response_oversize"):
            asyncio.run(operation)
    assert len(requests) == 1
    assert requests[0].headers["accept-encoding"] == "identity"
    assert sum(chunks_read) <= 65_536 + 2_048
    assert not (tmp_path / "unused").exists()


@pytest.mark.parametrize("control", [
    "test_no_approval_cannot_read_key_or_execute",
    "test_mathematically_unreachable_calibration_stops_without_opening_heldout",
    "test_perfect_synthetic_calibration_passes_without_opening_heldout",
    "test_failed_provider_cases_have_single_atomic_error_and_no_false_no_match",
    "test_heldout_requires_real_calibration_receipts_and_accepts_different_latency",
])
def test_existing_full_run_controls_with_new_transport(
    control: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Exercise the existing transaction, durable-journal and admission scenarios
    # against the new transport version, using only injected synthetic packets.
    monkeypatch.setattr(controls, "caller", candidate)
    original_response = controls._response

    def response_with_metadata(*args, **kwargs):
        payload = original_response(*args, **kwargs).json()
        payload["candidates"][0]["content"]["parts"][0]["thoughtSignature"] = "A" * 16_384
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(controls, "_response", response_with_metadata)
    packet = controls.public_packet.__wrapped__(tmp_path, monkeypatch)
    getattr(controls, control)(packet, tmp_path, monkeypatch)
    for journal in tmp_path.rglob("attempt-journal/*.json"):
        stored = journal.read_text(encoding="utf-8")
        assert "thoughtSignature" not in stored and "AAAA" not in stored


def test_new_transport_preserves_every_public_request_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(controls, "caller", candidate)
    packet = controls.public_packet.__wrapped__(tmp_path, monkeypatch)
    admitted = controls._admit(packet)
    for row in admitted["requests"]:
        payload = json.loads(row["body"]["contents"][0]["parts"][0]["text"])
        wire = candidate.build_high_thinking_public_wire(payload["question"], [
            {"id": item["id"], "page": item["physical_page"],
             "cue": item["shown_cue"], "page_text": item["page_text"]}
            for item in payload["candidates"]])
        assert candidate._rest_body(wire) == consumed._rest_body(wire) == row["body"]
