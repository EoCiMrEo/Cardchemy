"""Keyless safety checks for the separately approved public checkpoint pilot."""

import asyncio
import json
from pathlib import Path
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import run_public_source_id_multipdf_36_resume as resume  # noqa: E402
from app.ai.source_judgment import build_source_id_request  # noqa: E402


def _row(group_id="G003"):
    wire = build_source_id_request("What does the public term mean?", [
        {"id": f"S{index:02d}", "page": index,
         "page_text": f"Public page {index} defines the public term.",
         "cue": "defines the public term"}
        for index in range(1, 5)
    ])
    return {"group_id": group_id, "status": "callable", "wire": wire,
            "wire_sha256": resume.digest(resume.canonical_bytes(wire))}


def _response(status=200, selected=("S01",)):
    body = {"candidates": [{"finishReason": "STOP", "content": {
        "parts": [{"text": json.dumps({"selected_ids": selected})}]}}],
        "usageMetadata": {"promptTokenCount": 80,
                          "candidatesTokenCount": 5,
                          "thoughtsTokenCount": 3,
                          "totalTokenCount": 88}}
    return httpx.Response(status, json=body,
                          request=httpx.Request("POST", resume.ENDPOINT))


def _clocked_state(tmp_path):
    now = [1000.0]

    async def sleeper(seconds):
        now[0] += seconds

    state = resume._PilotState(clock=lambda: now[0],
                               wall_clock=lambda: now[0],
                               sleeper=sleeper, output=tmp_path)
    (tmp_path / "physical-outcomes.jsonl").write_bytes(b"")
    responses = tmp_path / "response-ids.jsonl"
    usage = tmp_path / "usage-receipts.jsonl"
    responses.write_bytes(b"")
    usage.write_bytes(b"")
    return now, state, responses, usage


@pytest.mark.asyncio
async def test_only_explicit_503_retries_once_after_twenty_seconds(tmp_path):
    now, state, responses, usage = _clocked_state(tmp_path)
    starts = []

    async def transport(_wire):
        starts.append(now[0])
        return _response(503 if len(starts) == 1 else 200)

    row = _row()
    await resume._run_split({"split": "calibration"}, [row], state,
                            transport, responses, usage)
    assert starts == [1000.0, 1020.0]
    assert state.summary() == {
        "new_physical_calls": 2, "new_accepted_groups": 1,
        "new_input_tokens_reserved": 16_384,
        "new_output_tokens_reserved": 2_048,
        "new_cost_reserved_microusd": 39_936,
        "new_known_cost_microusd": resume._cost_microusd(80, 8),
        "new_observed_input_tokens": 80,
        "new_observed_output_tokens": 8,
        "new_failed_call_cost_unknown": True,
        "http_503_first_attempts": 1,
    }
    assert len(responses.read_bytes().splitlines()) == 1
    assert len(usage.read_bytes().splitlines()) == 1
    assert (tmp_path / "call-001.claim").exists()
    assert (tmp_path / "call-002.claim").exists()
    assert [json.loads(line)["accepted"] for line in
            (tmp_path / "physical-outcomes.jsonl").read_bytes().splitlines()] == [False, True]


@pytest.mark.asyncio
async def test_second_503_stops_with_no_accepted_row_and_no_third_call(tmp_path):
    now, state, responses, usage = _clocked_state(tmp_path)
    starts = []

    async def transport(_wire):
        starts.append(now[0])
        return _response(503)

    with pytest.raises(resume.PilotFailure, match="provider_http_503_second"):
        await resume._run_split({"split": "calibration"}, [_row()], state,
                                transport, responses, usage)
    assert starts == [1000.0, 1020.0]
    assert state.calls == 2 and state.successes == 0
    assert state.cost_reserved_microusd == 39_936
    assert responses.read_bytes() == usage.read_bytes() == b""
    assert not (tmp_path / "call-003.claim").exists()


@pytest.mark.asyncio
async def test_retry_waits_twenty_seconds_after_the_503_response(tmp_path):
    now, state, responses, usage = _clocked_state(tmp_path)
    starts = []

    async def transport(_wire):
        starts.append(now[0])
        if len(starts) == 1:
            now[0] += 1.25
            return _response(503)
        return _response(200)

    await resume._run_split({"split": "calibration"}, [_row()], state,
                            transport, responses, usage)
    assert starts == [1000.0, 1021.25]
    assert state.calls == 2 and state.successes == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 429, 500, 502, 504])
async def test_other_http_errors_never_retry(tmp_path, status):
    _now, state, responses, usage = _clocked_state(tmp_path)
    calls = 0

    async def transport(_wire):
        nonlocal calls
        calls += 1
        return _response(status)

    with pytest.raises(resume.PilotFailure, match=f"provider_http_{status}"):
        await resume._run_split({"split": "calibration"}, [_row()], state,
                                transport, responses, usage)
    assert calls == state.calls == 1
    assert not (tmp_path / "call-002.claim").exists()
    assert responses.read_bytes() == usage.read_bytes() == b""


@pytest.mark.asyncio
async def test_timeout_never_retries_or_accepts(tmp_path):
    _now, state, responses, usage = _clocked_state(tmp_path)
    calls = 0

    async def transport(_wire):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("secret content must not be persisted")

    with pytest.raises(httpx.ReadTimeout):
        await resume._run_split({"split": "calibration"}, [_row()], state,
                                transport, responses, usage)
    assert calls == state.calls == 1
    assert not (tmp_path / "call-002.claim").exists()
    assert responses.read_bytes() == usage.read_bytes() == b""


def test_pending_approval_and_exact_envelope_are_required(tmp_path, monkeypatch):
    checkpoint = {"labels_sha256": "a" * 64,
                  "freeze_receipt_sha256": "b" * 64,
                  "fingerprint": "c" * 64}
    approval_path = tmp_path / "approval.json"
    approval_path.write_bytes(resume.canonical_bytes({"operator_approved": True}))
    monkeypatch.setattr(resume, "AUTHORIZATION_ID", "PENDING_SEPARATE_OPERATOR_APPROVAL")
    with pytest.raises(resume.PilotFailure, match="separate_operator_approval_required"):
        resume.validate_approval(approval_path,
                                 resume.digest(approval_path.read_bytes()), checkpoint)
    monkeypatch.setattr(resume, "AUTHORIZATION_ID", "test-only-approval")
    with pytest.raises(resume.PilotFailure, match="approval_envelope_mismatch"):
        resume.validate_approval(approval_path,
                                 resume.digest(approval_path.read_bytes()), checkpoint)


def test_approved_budget_matches_full_reservation_and_old_cost_is_separate():
    assert resume._cost_microusd(8_192, 1_024) == resume._MAX_RESERVATION_PER_CALL
    assert resume.MAX_NEW_CALLS * resume._MAX_RESERVATION_PER_CALL == 3_714_048
    assert resume.MAX_NEW_COST_MICROUSD == 3_720_000
    assert resume.MAX_NEW_INPUT_TOKENS == resume.MAX_NEW_CALLS * 8_192
    assert resume.MAX_NEW_OUTPUT_TOKENS == resume.MAX_NEW_CALLS * 1_024
    assert resume._OLD_KNOWN_COST_MICROUSD == 7_823


def test_immutable_prefix_reader_rejects_partial_or_duplicate_lines(tmp_path):
    path = tmp_path / "lines.jsonl"
    path.write_bytes(b'{"a":1}')
    with pytest.raises(resume.PilotFailure, match="checkpoint_lines_invalid"):
        resume._strict_lines(path, max_bytes=100, max_lines=3)
    path.write_bytes(b'{"a":1,"a":2}\n')
    with pytest.raises(resume.PilotFailure, match="checkpoint_lines_invalid"):
        resume._strict_lines(path, max_bytes=100, max_lines=3)


def test_frozen_checkpoint_hashes_cover_the_four_claims_and_both_receipt_files():
    expected = {f"call-{index:02d}.claim" for index in range(1, 5)} | {
        "response-ids.jsonl", "usage-receipts.jsonl", "live-failure.json",
        "live-run.claim", "operator-approval.json", "prepare-receipt.json",
        "requests.json"}
    assert set(resume._OLD_CALIBRATION_SHA256) == expected
    assert all(resume._HEX64.fullmatch(value)
               for value in resume._OLD_CALIBRATION_SHA256.values())


def test_acceptance_gate_rejects_torn_or_mispaired_receipts(tmp_path):
    row = _row()
    response = {"group_id": row["group_id"],
                "wire_sha256": row["wire_sha256"],
                "raw_json": json.dumps({"selected_ids": ["S01"]},
                                       sort_keys=True, separators=(",", ":"))}
    usage = {"group_id": row["group_id"], "finish_reason": "STOP",
             "input_tokens": 80, "output_tokens": 8,
             "cost_microusd": resume._cost_microusd(80, 8)}
    response_path = tmp_path / "responses.jsonl"
    usage_path = tmp_path / "usage.jsonl"
    response_path.write_bytes(resume.canonical_bytes(response))
    usage_path.write_bytes(resume.canonical_bytes(usage))
    resume._validate_accepted_split({"requests": [row]}, response_path, usage_path)
    usage["group_id"] = "other"
    usage_path.write_bytes(resume.canonical_bytes(usage))
    with pytest.raises(resume.PilotFailure, match="accepted_pair_invalid"):
        resume._validate_accepted_split({"requests": [row]},
                                        response_path, usage_path)
    usage_path.write_bytes(b"")
    with pytest.raises(resume.PilotFailure):
        resume._validate_accepted_split({"requests": [row]},
                                        response_path, usage_path)


@pytest.mark.asyncio
async def test_run_starts_at_fourth_group_and_keeps_heldout_sealed_on_failed_gate(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(resume, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(resume, "AUTHORIZATION_ID", "test-only-approval")
    now = [1000.0]

    async def sleeper(seconds):
        now[0] += seconds

    prior = tmp_path / "prior"
    prior.mkdir()
    (prior / "response-ids.jsonl").write_bytes(b"old responses\n")
    (prior / "usage-receipts.jsonl").write_bytes(b"old usage\n")
    old_hashes = dict(resume._OLD_CALIBRATION_SHA256)
    old_hashes["response-ids.jsonl"] = resume.digest(b"old responses\n")
    old_hashes["usage-receipts.jsonl"] = resume.digest(b"old usage\n")
    monkeypatch.setattr(resume, "_OLD_CALIBRATION_SHA256", old_hashes)
    prepared = {"split": "calibration", "requests": [
        _row(f"G{index:03d}") for index in range(48)]}
    checkpoint = {"schema": "test-only"}
    approval = {"prior_checkpoint_sha256": resume.digest(
        resume.canonical_bytes(checkpoint)),
        "authorization_id": "test-only-approval"}
    calls = []

    async def transport(wire):
        calls.append(wire)
        return _response()

    def failed_calibration(*_args):
        return {"public_passed": False}

    monkeypatch.setattr(resume, "_score_complete_split", failed_calibration)
    output = tmp_path / "new-pilot"
    result = await resume.run_pilot(
        prior, tmp_path, tmp_path / "labels.json", "a" * 64, "b" * 64,
        approval, "c" * 64, output, transport,
        clock=lambda: now[0], wall_clock=lambda: now[0], sleeper=sleeper,
        prevalidated=(prepared, {}, checkpoint),
    )
    assert result["status"] == "calibration_gate_failed"
    assert result["new_physical_calls"] == len(calls) == 45
    assert result["new_accepted_groups"] == 45
    assert result["heldout_opened"] is False
    assert not (output / "heldout").exists()
    assert (output / "call-001.claim").exists()
    assert not (output / "call-046.claim").exists()
    assert (prior / "response-ids.jsonl").read_bytes() == b"old responses\n"


@pytest.mark.asyncio
async def test_tampered_prior_receipt_blocks_egress_after_prevalidation(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(resume, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(resume, "AUTHORIZATION_ID", "test-only-approval")
    prior = tmp_path / "prior"
    prior.mkdir()
    (prior / "response-ids.jsonl").write_bytes(b"changed after preflight\n")
    (prior / "usage-receipts.jsonl").write_bytes(b"unchanged\n")
    checkpoint = {"schema": "test-only"}
    approval = {"prior_checkpoint_sha256": resume.digest(
        resume.canonical_bytes(checkpoint)),
        "authorization_id": "test-only-approval"}
    calls = 0

    async def transport(_wire):
        nonlocal calls
        calls += 1
        return _response()

    output = tmp_path / "new-pilot"
    with pytest.raises(resume.PilotFailure, match="checkpoint_file_changed"):
        await resume.run_pilot(prior, tmp_path, tmp_path / "labels.json",
                               "a" * 64, "b" * 64, approval, "c" * 64,
                               output, transport,
                               prevalidated=({"split": "calibration",
                                              "requests": []}, {}, checkpoint))
    assert calls == 0
    assert not output.exists()


@pytest.mark.asyncio
async def test_nested_output_cannot_modify_the_consumed_prior_ledger(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(resume, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(resume, "AUTHORIZATION_ID", "test-only-approval")
    prior = tmp_path / "prior"
    prior.mkdir()
    checkpoint = {"schema": "test-only"}
    approval = {"prior_checkpoint_sha256": resume.digest(
        resume.canonical_bytes(checkpoint)),
        "authorization_id": "test-only-approval"}
    calls = 0

    async def transport(_wire):
        nonlocal calls
        calls += 1
        return _response()

    with pytest.raises(resume.PilotFailure, match="os_temp_output_required"):
        await resume.run_pilot(prior, tmp_path, tmp_path / "labels.json",
                               "a" * 64, "b" * 64, approval, "c" * 64,
                               prior / "new-pilot", transport,
                               prevalidated=({"split": "calibration",
                                              "requests": []}, {}, checkpoint))
    assert calls == 0
    assert not (prior / "new-pilot").exists()
