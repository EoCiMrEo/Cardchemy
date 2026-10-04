"""Keyless, fake-transport checks for the failure-inclusive Flash-Lite proposal."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import continue_public_source_id_multipdf_35_lite_v1 as continuation  # noqa: E402
from evaluate_source_id_multipdf_35_lite import (  # noqa: E402
    LABEL_SCHEMA, PACKET_SCHEMA, PACKET_SHA256, _split_requests,
)
from prepare_public_source_id_multipdf import canonical_bytes  # noqa: E402


def _fixture() -> tuple[dict, dict, dict]:
    """48 groups per split, with four of each 0–3-card stratum per form."""
    groups = []
    labels = []
    for index in range(96):
        split = "calibration" if index < 48 else "heldout"
        form = ("direct", "paraphrase", "follow-up")[index % 3]
        useful = (index // 3) % 4
        group_id = f"G{index:03d}"
        candidates = [{
            "id": f"S{number:02d}", "page": number,
            "page_text": f"source {number} explains public method {index}.",
            "cue": f"source {number} explains public method {index}",
        } for number in range(1, 5)]
        groups.append({
            "group_id": group_id, "split": split, "question_form": form,
            "question": f"How is public method {index} explained?",
            "prior_for_local_context_only": None,
            "candidates": candidates,
        })
        labels.append({
            "group_id": group_id, "split": split, "question_form": form,
            "labels": [{
                "id": f"S{number:02d}",
                "page_useful": number <= useful,
                "cue_useful": number <= useful,
            } for number in range(1, 5)],
        })
    packet = {"schema": PACKET_SCHEMA, "groups": groups}
    frozen = {"schema": LABEL_SCHEMA, "packet_sha256": PACKET_SHA256,
              "groups": labels}
    requests = {
        split: {"split": split, "fingerprint": "f" * 64,
                "requests": _split_requests(packet, split)}
        for split in ("calibration", "heldout")
    }
    assert all(row["status"] == "callable" for data in requests.values()
               for row in data["requests"])
    return packet, frozen, requests


def _perfect(split: str, requests: dict) -> dict[str, tuple[str, ...]]:
    result = {}
    offset = 0 if split == "calibration" else 48
    for number, row in enumerate(requests[split]["requests"]):
        useful = ((number + offset) // 3) % 4
        result[row["group_id"]] = tuple(
            f"S{index:02d}" for index in range(1, useful + 1))
    return result


@pytest.mark.parametrize("split", ["calibration", "heldout"])
def test_error_is_availability_failure_and_never_no_match(split):
    _packet, labels, requests = _fixture()
    responses = _perfect(split, requests)
    negative = next(group_id for group_id, selected in responses.items()
                    if not selected)
    responses.pop(negative)
    metrics = continuation.score_failure_inclusive(
        requests[split], labels, responses, {negative: "provider_timeout"})
    assert metrics["availability_successful"] == 47
    assert metrics["availability_failed"] == 1
    assert metrics["failed_negative_groups"] == 1
    assert metrics["counts"]["valid_no_useful_abstentions"] == 11
    assert metrics["counts"]["invalid_model_outputs"] == 0
    assert metrics["counts"]["provider_unavailable_groups"] == 1
    assert metrics["public_passed"] is True


def test_availability_and_display_quality_gates_are_independent():
    _packet, labels, requests = _fixture()
    responses = _perfect("calibration", requests)
    failed = list(responses)[:3]
    for group_id in failed:
        responses.pop(group_id)
    metrics = continuation.score_failure_inclusive(
        requests["calibration"], labels, responses,
        {group_id: "provider_http_503" for group_id in failed})
    assert metrics["availability_successful"] == 45
    assert metrics["availability_passed"] is False
    assert metrics["public_passed"] is False

    responses = _perfect("calibration", requests)
    negative = next(group_id for group_id, selected in responses.items()
                    if not selected)
    responses[negative] = ("S04",)
    metrics = continuation.score_failure_inclusive(
        requests["calibration"], labels, responses, {})
    assert metrics["availability_passed"] is True
    assert metrics["counts"]["false_no_useful_displays"] == 1
    assert metrics["source_quality_passed"] is False
    assert metrics["public_passed"] is False

    responses = _perfect("calibration", requests)
    for group_id in [key for key, selected in responses.items()
                     if len(selected) == 1][:9]:
        responses[group_id] += ("S04",)
    metrics = continuation.score_failure_inclusive(
        requests["calibration"], labels, responses, {})
    assert metrics["displayed_cue_and_page_useful_fraction"] < 0.9
    assert metrics["public_passed"] is False


def test_missing_outcome_and_quota_as_miss_are_rejected():
    _packet, labels, requests = _fixture()
    responses = _perfect("calibration", requests)
    responses.pop(next(iter(responses)))
    with pytest.raises(continuation.PilotFailure,
                       match="split_outcomes_incomplete"):
        continuation.score_failure_inclusive(
            requests["calibration"], labels, responses, {})
    with pytest.raises(continuation.PilotFailure,
                       match="split_outcomes_incomplete"):
        continuation.score_failure_inclusive(
            requests["calibration"], labels, responses,
            {"G000": "provider_http_429"})


def test_prior_false_display_blocks_before_any_new_claim():
    _packet, labels, requests = _fixture()
    rows = requests["calibration"]["requests"][:10]
    selected = {row["group_id"]: _perfect("calibration", requests)[row["group_id"]]
                for row in rows}
    viable = continuation.prior_display_viability(rows, selected, labels)
    assert viable["prior_negative_false_displays"] == 0
    selected[rows[0]["group_id"]] = ("S04",)
    with pytest.raises(continuation.PilotFailure,
                       match="prior_false_no_useful_display_irreversible"):
        continuation.prior_display_viability(rows, selected, labels)


def _stage_fake_run(tmp_path: Path, monkeypatch):
    packet, labels, requests = _fixture()
    prior_dir = tmp_path / "prior"
    packet_dir = tmp_path / "packet"
    labels_dir = tmp_path / "labels"
    approval_dir = tmp_path / "old-approval"
    for directory in (prior_dir, packet_dir, labels_dir, approval_dir):
        directory.mkdir()
    labels_path = labels_dir / "frozen-labels.json"
    old_approval = approval_dir / "approval-calibration.json"
    old_approval.write_text("{}", encoding="utf-8")
    prior_response = b""
    prior_usage = b""
    perfect = _perfect("calibration", requests)
    for row in requests["calibration"]["requests"][:10]:
        prior_response += canonical_bytes({
            "group_id": row["group_id"], "wire_sha256": row["wire_sha256"],
            "raw_json": json.dumps({"selected_ids": perfect[row["group_id"]]}),
        })
        prior_usage += canonical_bytes({
            "group_id": row["group_id"], "finish_reason": "STOP",
            "input_tokens": 50, "output_tokens": 8, "cost_microusd": 35,
        })
    (prior_dir / "response-ids.jsonl").write_bytes(prior_response)
    (prior_dir / "usage-receipts.jsonl").write_bytes(prior_usage)
    hashes = dict(continuation._OLD_FILE_SHA256)
    hashes["response-ids.jsonl"] = continuation.digest(prior_response)
    hashes["usage-receipts.jsonl"] = continuation.digest(prior_usage)
    monkeypatch.setattr(continuation, "_OLD_FILE_SHA256", hashes)
    monkeypatch.setattr(continuation, "AUTHORIZATION_ID", "synthetic-test-only")
    monkeypatch.setattr(continuation, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(continuation, "validate_prior",
                        lambda *_: (requests["calibration"], {},
                                   {"fingerprint": "f" * 64}))
    monkeypatch.setattr(continuation, "validate_approval", lambda *_: {})
    monkeypatch.setattr(continuation, "read_pinned",
                        lambda path, *_: labels if path == labels_path else packet)

    class FakeTime:
        now = 0.0

        def clock(self):
            return self.now

        async def sleep(self, duration):
            self.now += duration

    return (prior_dir, packet_dir, labels_path, old_approval,
            tmp_path / "new-approval.json", FakeTime())


def _response_for_wire(wire: dict) -> httpx.Response:
    index = int(wire["user_payload"]["question"].split("method ")[1].split()[0])
    useful = (index // 3) % 4
    selected = [f"S{number:02d}" for number in range(1, useful + 1)]
    return httpx.Response(200, json={
        "candidates": [{"finishReason": "STOP", "content": {"parts": [{
            "text": json.dumps({"selected_ids": selected}),
        }]}}],
        "usageMetadata": {"promptTokenCount": 50,
                          "candidatesTokenCount": 8},
    })


def test_fake_transport_never_replays_eleven_and_opens_conditional_holdout(
    tmp_path, monkeypatch,
):
    prior, packet, labels, old_approval, new_approval, fake_time = (
        _stage_fake_run(tmp_path, monkeypatch))
    sent = []

    async def transport(wire):
        index = int(wire["user_payload"]["question"].split("method ")[1].split()[0])
        sent.append(index)
        if index == 10:
            raise AssertionError("the old timed-out case was replayed")
        if index == 11:
            raise TimeoutError("synthetic transport timeout")
        return _response_for_wire(wire)

    result = asyncio.run(continuation.run_with_transport(
        prior, packet, labels, old_approval, new_approval, "f" * 64,
        tmp_path / "result", transport, clock=fake_time.clock,
        sleeper=fake_time.sleep))
    assert result["status"] == "public_pilot_complete", result
    assert result["new_physical_calls"] == 85
    assert result["new_accepted_responses"] == 84
    assert result["new_unreceipted_calls"] == 1
    assert result["heldout_opened"] is True
    assert sent == list(range(11, 48)) + list(range(48, 96))
    assert not (tmp_path / "result" / "calibration-11.claim").exists()
    assert (tmp_path / "result" / "calibration-score.json").is_file()
    assert (tmp_path / "result" / "heldout-score.json").is_file()
    cal_score = json.loads((tmp_path / "result" / "calibration-score.json").read_bytes())
    assert cal_score["metrics"]["availability_successful"] == 46
    assert cal_score["metrics"]["failed_negative_groups"] == 0
    assert cal_score["metrics"]["failed_positive_groups"] == 2
    with pytest.raises(continuation.PilotFailure,
                       match="continuation_claim_consumed"):
        asyncio.run(continuation.run_with_transport(
            prior, packet, labels, old_approval, new_approval, "f" * 64,
            tmp_path / "another", transport, clock=fake_time.clock,
            sleeper=fake_time.sleep))
    assert len(sent) == 85


def test_quota_stops_without_further_calls_or_holdout(tmp_path, monkeypatch):
    prior, packet, labels, old_approval, new_approval, fake_time = (
        _stage_fake_run(tmp_path, monkeypatch))
    sent = []

    async def transport(wire):
        sent.append(wire["user_payload"]["question"])
        return httpx.Response(429, json={"ignored": "untrusted"})

    result = asyncio.run(continuation.run_with_transport(
        prior, packet, labels, old_approval, new_approval, "f" * 64,
        tmp_path / "result", transport, clock=fake_time.clock,
        sleeper=fake_time.sleep))
    assert len(sent) == 1
    assert result["status"] == "stopped_no_replay"
    assert result["reason"] == "provider_http_error"
    assert result["http_status"] == 429
    assert result["new_physical_calls"] == 1
    assert result["heldout_opened"] is False
    assert not (tmp_path / "result" / "calibration-score.json").exists()


def test_third_availability_failure_stops_when_gate_is_unreachable(
    tmp_path, monkeypatch,
):
    prior, packet, labels, old_approval, new_approval, fake_time = (
        _stage_fake_run(tmp_path, monkeypatch))
    sent = []

    async def transport(wire):
        sent.append(wire["user_payload"]["question"])
        return httpx.Response(503, json={"ignored": "untrusted"})

    result = asyncio.run(continuation.run_with_transport(
        prior, packet, labels, old_approval, new_approval, "f" * 64,
        tmp_path / "result", transport, clock=fake_time.clock,
        sleeper=fake_time.sleep))
    assert len(sent) == 2  # The prior timeout already used one failed slot.
    assert result["reason"] == "availability_gate_unreachable"
    assert result["new_physical_calls"] == 2
    assert result["heldout_opened"] is False
    assert not (tmp_path / "result" / "calibration-score.json").exists()


def test_failed_calibration_quality_keeps_heldout_sealed(tmp_path, monkeypatch):
    prior, packet, labels, old_approval, new_approval, fake_time = (
        _stage_fake_run(tmp_path, monkeypatch))
    sent = []

    async def transport(wire):
        sent.append(wire["user_payload"]["question"])
        return httpx.Response(200, json={
            "candidates": [{"finishReason": "STOP", "content": {"parts": [{
                "text": '{"selected_ids":[]}',
            }]}}],
            "usageMetadata": {"promptTokenCount": 50,
                              "candidatesTokenCount": 8},
        })

    result = asyncio.run(continuation.run_with_transport(
        prior, packet, labels, old_approval, new_approval, "f" * 64,
        tmp_path / "result", transport, clock=fake_time.clock,
        sleeper=fake_time.sleep))
    assert result["status"] == "calibration_gate_failed"
    assert result["new_physical_calls"] == 37
    assert result["heldout_opened"] is False
    assert not (tmp_path / "result" / "heldout").exists()
    score = json.loads((tmp_path / "result" / "calibration-score.json").read_bytes())
    assert score["metrics"]["availability_passed"] is True
    assert score["metrics"]["source_quality_passed"] is False


def test_pending_approval_blocks_even_if_receipt_path_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(continuation, "AUTHORIZATION_ID",
                        "PENDING_SEPARATE_OPERATOR_APPROVAL")
    with pytest.raises(continuation.PilotFailure,
                       match="separate_operator_approval_required"):
        continuation.validate_approval(tmp_path / "fake.json", "f" * 64,
                                       {"fingerprint": "f" * 64})


def test_future_approval_binds_exact_adapter_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(continuation, "AUTHORIZATION_ID", "synthetic-test-only")
    monkeypatch.setattr(continuation, "_caller_sha256", lambda: "a" * 64)
    monkeypatch.setattr(continuation, "_source_judgment_sha256",
                        lambda: "c" * 64)
    checkpoint = {"fingerprint": "f" * 64}
    receipt = continuation.approval_template(checkpoint)
    path = tmp_path / "new-approval.json"
    path.write_bytes(canonical_bytes(receipt))
    assert continuation.validate_approval(
        path, continuation.digest(path.read_bytes()), checkpoint) == receipt
    monkeypatch.setattr(continuation, "_caller_sha256", lambda: "b" * 64)
    with pytest.raises(continuation.PilotFailure,
                       match="approval_envelope_mismatch"):
        continuation.validate_approval(
            path, continuation.digest(path.read_bytes()), checkpoint)
    monkeypatch.setattr(continuation, "_caller_sha256", lambda: "a" * 64)
    monkeypatch.setattr(continuation, "_source_judgment_sha256",
                        lambda: "d" * 64)
    with pytest.raises(continuation.PilotFailure,
                       match="approval_envelope_mismatch"):
        continuation.validate_approval(
            path, continuation.digest(path.read_bytes()), checkpoint)


def test_approved_envelope_still_requires_exact_receipt_and_is_bounded():
    assert continuation.AUTHORIZATION_ID == (
        "approved_public_flash_lite_continuation_20260930_v1")
    assert continuation.MAX_NEW_CALLS == 37 + 48
    assert continuation.MAX_NEW_INPUT_TOKENS == 696_320
    assert continuation.MAX_NEW_OUTPUT_TOKENS == 87_040
    assert continuation.MAX_CALL_SECONDS == 90
    assert continuation.MAX_TOTAL_SECONDS == 180 * 60
    assert continuation.MIN_START_INTERVAL_SECONDS >= 20
    assert (continuation.MAX_NEW_CALLS * continuation._cost_microusd(
        continuation.MAX_INPUT_PER_CALL,
        continuation.MAX_OUTPUT_PER_CALL) <=
        continuation.MAX_NEW_COST_MICROUSD == 500_000)
