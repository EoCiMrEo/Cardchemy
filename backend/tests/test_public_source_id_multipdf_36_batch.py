"""Provider-free admission and REST contract tests for the public Batch pilot."""

import argparse
import asyncio
import json
from pathlib import Path
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import run_public_source_id_multipdf_36_batch as batch  # noqa: E402
from app.ai.source_judgment import build_source_id_request  # noqa: E402


def _rows(count=45):
    result = []
    for number in range(count):
        wire = build_source_id_request(
            f"What is the public method {number}?", [
                {"id": f"S{index:02d}", "page": index,
                 "page_text": f"Public page {index} defines public method {number}.",
                 "cue": f"defines public method {number}"}
                for index in range(1, 5)])
        result.append({"group_id": f"G{number:03d}", "status": "callable",
                       "wire": wire,
                       "wire_sha256": batch.digest(batch.canonical_bytes(wire))})
    return result


def _provider_response(selected=("S01",)):
    return {"candidates": [{"finishReason": "STOP", "content": {
        "parts": [{"text": json.dumps({"selected_ids": selected})}]}}],
        "usageMetadata": {"promptTokenCount": 80,
                          "candidatesTokenCount": 5,
                          "thoughtsTokenCount": 3,
                          "totalTokenCount": 88}}


def _items(rows):
    return [{"metadata": {"key": row["group_id"]},
             "response": _provider_response()} for row in rows]


def _operation(name, state, items=None, *, location="response", done=True):
    metadata = {"state": state}
    operation = {"name": name, "metadata": metadata}
    if done:
        operation["done"] = True
        if location == "response":
            operation["response"] = {"inlinedResponses": items}
        else:
            metadata["output"] = {"inlinedResponses": {
                "inlinedResponses": items}}
    return operation


def _http_json(body, method="GET"):
    return httpx.Response(200, json=body,
                          request=httpx.Request(method, "https://example.test/"))


def test_batch_guard_matches_approved_public_envelope():
    assert batch.AUTHORIZATION_ID == (
        "lane6-public-36-inline-batch-20260929-"
        "4d56d49e618a40fb9ab3848b2683e83f")
    assert batch.MAX_COST_PER_ITEM_MICROUSD == 9_984
    assert batch.MAX_NEW_ITEMS * batch.MAX_COST_PER_ITEM_MICROUSD == 928_512
    assert batch.MAX_NEW_COST_MICROUSD == 1_000_000
    assert batch.MAX_STATUS_GETS == 100
    assert batch.POLL_INTERVAL_SECONDS == 1_800
    assert batch.MAX_TOTAL_SECONDS == 48 * 3_600
    assert batch.MAX_HTTP_SECONDS == 30


def test_rest_operation_pending_and_two_documented_success_shapes():
    name = "batches/testbatch"
    pending = {"name": name, "metadata": {"state": "JOB_STATE_PENDING"}}
    assert batch._batch_state(pending, name) == ("pending", None)
    assert batch._batch_state(pending | {"done": False}, name) == (
        "pending", None)
    rows = _rows()
    for location, state in (("response", "JOB_STATE_SUCCEEDED"),
                            ("metadata", "BATCH_STATE_SUCCEEDED")):
        operation = _operation(name, state, list(reversed(_items(rows))),
                               location=location)
        status, result = batch._batch_state(operation, name)
        assert status == "succeeded"
        accepted, usage, totals = batch._accepted_items(result, rows, name)
        assert [item["group_id"] for item in accepted] == [
            row["group_id"] for row in rows]
        assert len(usage) == 45
        assert totals["known_cost_microusd"] == 45 * batch._batch_cost_microusd(80, 8)


@pytest.mark.parametrize("operation", [
    {"metadata": {"state": "JOB_STATE_SUCCEEDED"}, "done": True,
     "response": {"inlinedResponses": []}},
    {"name": "batches/wrong", "metadata": {"state": "JOB_STATE_SUCCEEDED"},
     "done": True, "response": {"inlinedResponses": []}},
    {"name": "batches/testbatch", "metadata": {"state": "JOB_STATE_PENDING"},
     "done": True, "response": {"inlinedResponses": []}},
    {"name": "batches/testbatch", "metadata": {"state": "JOB_STATE_SUCCEEDED"},
     "done": True, "response": {"inlinedResponses": []},
     "error": {"code": 3}},
    {"name": "batches/testbatch", "metadata": {"state": "JOB_STATE_FAILED"},
     "done": True, "error": {"code": 3}},
    {"name": "batches/testbatch", "metadata": {"state": "JOB_STATE_SUCCEEDED",
        "output": {"inlinedResponses": {"inlinedResponses": []}}},
     "done": True, "response": {"inlinedResponses": []}},
])
def test_rest_operation_rejects_unknown_identity_state_and_ambiguous_output(operation):
    with pytest.raises(batch.PilotFailure):
        batch._batch_state(operation, "batches/testbatch")


def test_rest_items_require_metadata_keys_and_every_valid_item():
    rows = _rows()
    name = "batches/testbatch"
    items = _items(rows)
    good = {"inlinedResponses": items,
            "batchStats": {"requestCount": "45",
                           "successfulRequestCount": "45"}}
    assert len(batch._accepted_items(good, rows, name)[0]) == 45
    for broken in (
        [item.copy() for item in items[:-1]] + [items[0]],
        [{"response": _provider_response()}] + items[1:],
        [items[0] | {"error": {"code": 3}}] + items[1:],
        items[:-1],
    ):
        with pytest.raises(batch.PilotFailure):
            batch._accepted_items(good | {"inlinedResponses": broken}, rows, name)
    with pytest.raises(batch.PilotFailure, match="batch_stats_invalid"):
        batch._accepted_items(good | {"batchStats": {
            "requestCount": "45", "successfulRequestCount": "44",
            "failedRequestCount": "1"}}, rows, name)


def _synthetic_admission(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(batch, "AUTHORIZATION_ID", "synthetic-batch-authorization")
    prior = tmp_path / "prior"
    prior.mkdir()
    stop = tmp_path / "stop"
    stop.mkdir()
    packet = tmp_path / "packet"
    packet.mkdir()
    labels = tmp_path / "labels.json"
    labels.write_text("{}", encoding="utf-8")
    parent = tmp_path / "new-pilot"
    parent.mkdir()
    output = parent / "pilot"
    prepared = {"requests": _rows(48), "fingerprint": "f" * 64,
                "split": "calibration"}
    checkpoint = {"fingerprint": "f" * 64, "labels_sha256": "a" * 64,
                  "freeze_receipt_sha256": "b" * 64}
    monkeypatch.setattr(batch, "validate_prior",
                        lambda *_: (prepared, {}, checkpoint))
    monkeypatch.setattr(batch, "validate_resume_stop",
                        lambda *_: "c" * 64)
    args = argparse.Namespace(mode="preflight", prior_dir=prior,
                              resume_stop_dir=stop, packet_dir=packet,
                              labels=labels, labels_sha256="a" * 64,
                              freeze_receipt_sha256="b" * 64,
                              approval_receipt=None, approval_sha256=None,
                              output=output)
    return args, prepared, checkpoint | {"resume_stop_files_sha256": "c" * 64}


def test_preflight_and_existing_approval_receipt_enter_fake_create(tmp_path, monkeypatch):
    args, prepared, checkpoint = _synthetic_admission(tmp_path, monkeypatch)
    admitted = batch._admit(args)
    assert admitted[2] == checkpoint
    monkeypatch.setattr(batch, "_pinned_prior_receipts", lambda _: (b"a", b"b"))
    approval_path = tmp_path / "approval.json"
    batch.write_exclusive(approval_path, batch.approval_template(checkpoint))
    args.mode = "submit-calibration"
    args.approval_receipt = approval_path
    args.approval_sha256 = batch.digest(approval_path.read_bytes())
    admitted = batch._admit(args)
    calls = []

    async def transport(method, url, body):
        calls.append((method, url, len(body["batch"]["inputConfig"]
                                      ["requests"]["requests"])))
        return _http_json({"name": "batches/synthetic"}, "POST")

    result = asyncio.run(batch.submit_calibration(
        args, admitted, transport, wall_clock=lambda: 1000.0))
    assert calls == [("POST", batch.CREATE_ENDPOINT, 45)]
    assert result["reserved_cost_microusd"] == 45 * 9_984
    assert (args.output / "calibration" / "create.claim").is_file()
    with pytest.raises(batch.PilotFailure, match="batch_approval_claim_consumed"):
        batch._admit(args)


def test_poll_ledger_survives_new_invocation_and_enforces_spacing(tmp_path, monkeypatch):
    args, _prepared, checkpoint = _synthetic_admission(tmp_path, monkeypatch)
    monkeypatch.setattr(batch, "_pinned_prior_receipts", lambda _: (b"a", b"b"))
    approval_path = tmp_path / "approval.json"
    batch.write_exclusive(approval_path, batch.approval_template(checkpoint))
    args.mode = "submit-calibration"
    args.approval_receipt = approval_path
    args.approval_sha256 = batch.digest(approval_path.read_bytes())
    admitted = batch._admit(args)

    async def create(_method, _url, _body):
        return _http_json({"name": "batches/synthetic"}, "POST")

    asyncio.run(batch.submit_calibration(
        args, admitted, create, wall_clock=lambda: 1000.0))
    args.mode = "poll-calibration"
    admitted = batch._admit(args)
    calls = []

    async def pending(method, url, body):
        calls.append((method, url, body))
        return _http_json({"name": "batches/synthetic",
                           "metadata": {"state": "JOB_STATE_PENDING"}})

    first = asyncio.run(batch.poll_split(
        args, admitted, pending, split="calibration",
        wall_clock=lambda: 1001.0))
    assert first["status"] == "batch_pending"
    assert len(calls) == 1
    with pytest.raises(batch.PilotFailure, match="batch_poll_interval_budget"):
        asyncio.run(batch.poll_split(
            args, admitted, pending, split="calibration",
            wall_clock=lambda: 2800.0))
    assert len(calls) == 1
    second = asyncio.run(batch.poll_split(
        args, admitted, pending, split="calibration",
        wall_clock=lambda: 2801.0))
    assert second["status"] == "batch_pending"
    assert len(calls) == 2
    assert (args.output / "calibration" / "poll-001.claim").is_file()
    assert (args.output / "calibration" / "poll-002.claim").is_file()


def test_heldout_requires_complete_provider_receipt_and_recomputed_pass(
        tmp_path, monkeypatch):
    args, prepared, checkpoint = _synthetic_admission(tmp_path, monkeypatch)
    old_responses = b"".join(batch.canonical_bytes({
        "group_id": row["group_id"], "wire_sha256": row["wire_sha256"],
        "raw_json": json.dumps({"selected_ids": ["S01"]},
                               sort_keys=True, separators=(",", ":"))})
        for row in prepared["requests"][:3])
    old_usage = b"".join(batch.canonical_bytes({
        "group_id": row["group_id"], "finish_reason": "STOP",
        "input_tokens": 80, "output_tokens": 8,
        "cost_microusd": batch._cost_microusd(80, 8)})
        for row in prepared["requests"][:3])
    monkeypatch.setattr(batch, "_pinned_prior_receipts",
                        lambda _: (old_responses, old_usage))
    labels = {"schema": batch.LABEL_SCHEMA,
              "packet_sha256": batch.PACKET_SHA256,
              "groups": [{} for _ in range(96)]}
    monkeypatch.setattr(batch, "read_pinned", lambda *_: labels)
    monkeypatch.setattr(batch, "score", lambda *_: {
        "public_passed": True, "counts": {"groups": 48}})
    approval_path = tmp_path / "approval.json"
    batch.write_exclusive(approval_path, batch.approval_template(checkpoint))
    args.mode = "submit-calibration"
    args.approval_receipt = approval_path
    args.approval_sha256 = batch.digest(approval_path.read_bytes())
    admitted = batch._admit(args)

    async def create(_method, _url, _body):
        return _http_json({"name": "batches/synthetic"}, "POST")

    asyncio.run(batch.submit_calibration(
        args, admitted, create, wall_clock=lambda: 1000.0))
    args.mode = "submit-heldout"
    admitted = batch._admit(args)
    attempted = []

    async def heldout_transport(method, _url, _body):
        attempted.append(method)
        return _http_json({"name": "batches/heldout"}, "POST")

    with pytest.raises(batch.PilotFailure):
        asyncio.run(batch.submit_heldout(
            args, admitted, heldout_transport, wall_clock=lambda: 1002.0))
    assert attempted == []
    assert not (args.output / "heldout").exists()

    args.mode = "poll-calibration"
    admitted = batch._admit(args)

    async def completed(_method, _url, _body):
        operation = _operation("batches/synthetic", "JOB_STATE_SUCCEEDED",
                               list(reversed(_items(prepared["requests"][3:]))))
        operation["metadata"]["batchStats"] = {
            "requestCount": "45", "successfulRequestCount": "45"}
        return _http_json(operation)

    scored = asyncio.run(batch.poll_split(
        args, admitted, completed, split="calibration",
        wall_clock=lambda: 1001.0))
    assert scored["public_passed"] is True
    result_path = args.output / "calibration" / "result.json"
    original = result_path.read_bytes()
    receipt = json.loads(original)
    result_path.write_bytes(batch.canonical_bytes(
        receipt | {"create_body_sha256": "0" * 64}))
    args.mode = "submit-heldout"
    with pytest.raises(batch.PilotFailure, match="calibration_completion_invalid"):
        asyncio.run(batch.submit_heldout(
            args, admitted, heldout_transport, wall_clock=lambda: 1002.0))
    assert attempted == []
    result_path.write_bytes(original)

    seal_path = args.output / "calibration" / "complete-items.json"
    original_seal = seal_path.read_bytes()
    seal = json.loads(original_seal)
    seal["accepted"][0]["raw_json"] = json.dumps({"selected_ids": ["S02"]})
    seal_path.write_bytes(batch.canonical_bytes(seal))
    with pytest.raises(batch.PilotFailure):
        asyncio.run(batch.submit_heldout(
            args, admitted, heldout_transport, wall_clock=lambda: 1002.0))
    assert attempted == []
    seal_path.write_bytes(original_seal)

    with pytest.raises(batch.PilotFailure, match="batch_total_time_budget"):
        asyncio.run(batch.submit_heldout(
            args, admitted, heldout_transport,
            wall_clock=lambda: 1000.0 + batch.MAX_TOTAL_SECONDS))
    assert attempted == []

    def prepare_heldout(_packet, _labels, _labels_sha, _freeze, split,
                        output, _cal_score, _cal_sha):
        assert split == "heldout"
        output.mkdir()
        batch.write_exclusive(output / "prepare-receipt.json", {"ok": True})

    monkeypatch.setattr(batch, "prepare", prepare_heldout)
    monkeypatch.setattr(batch, "_load_public_requests",
                        lambda *_: ({"requests": _rows(48),
                                     "fingerprint": prepared["fingerprint"]}, {}))
    accepted = asyncio.run(batch.submit_heldout(
        args, admitted, heldout_transport, wall_clock=lambda: 1002.0))
    assert accepted["item_count"] == 48
    assert attempted == ["POST"]


def test_get_budget_is_global_and_total_deadline_is_strict(tmp_path):
    output = tmp_path / "pilot"
    output.mkdir()
    cal = output / "calibration"
    cal.mkdir()
    held = output / "heldout"
    held.mkdir()
    batch.write_exclusive(cal / "create-result.json",
                          {"name": "batches/calibration"})
    batch.write_exclusive(held / "create-result.json",
                          {"name": "batches/heldout"})
    approval = "a" * 64
    for split, directory, count, name in (
            ("calibration", cal, 50, "batches/calibration"),
            ("heldout", held, 49, "batches/heldout")):
        for number in range(1, count + 1):
            batch.write_exclusive(directory / f"poll-{number:03d}.claim", {
                "schema": batch.BATCH_SCHEMA + "_poll_claim",
                "split": split, "batch_name": name,
                "approval_sha256": approval, "number": number,
                "started_unix_ms": 1000 + (number - 1) * 1_800_000,
            })
    now_ms = 1000 + 50 * 1_800_000
    number, path = batch._poll_admission(
        output, "heldout", "batches/heldout", approval, 1000, now_ms)
    assert number == 50
    batch.write_exclusive(path, {
        "schema": batch.BATCH_SCHEMA + "_poll_claim",
        "split": "heldout", "batch_name": "batches/heldout",
        "approval_sha256": approval, "number": 50,
        "started_unix_ms": now_ms,
    })
    with pytest.raises(batch.PilotFailure, match="batch_poll_count_budget"):
        batch._poll_admission(output, "heldout", "batches/heldout",
                              approval, 1000, now_ms + 1_800_000)
    with pytest.raises(batch.PilotFailure, match="batch_poll_time_budget"):
        batch._poll_admission(output, "heldout", "batches/heldout",
                              approval, 1000,
                              1000 + batch.MAX_TOTAL_SECONDS * 1000)
