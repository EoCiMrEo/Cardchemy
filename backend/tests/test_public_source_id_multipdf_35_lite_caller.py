"""No-key fake-transport checks for the one-shot public PDF caller."""

import asyncio
import argparse
import json
from pathlib import Path
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from run_public_source_id_multipdf_35_lite import (  # noqa: E402
    APPROVAL_SCHEMA, AUTHORIZATION_ID, ENDPOINT, MAX_CALL_SECONDS, MAX_CALLS_TOTAL,
    MAX_COST_MICROUSD, MAX_INPUT_TOTAL, MAX_OUTPUT_TOTAL,
    MAX_TOTAL_SECONDS, MIN_START_INTERVAL_SECONDS, MODEL,
    MAX_INPUT_PER_CALL, MAX_OUTPUT_PER_CALL,
    PilotFailure, _cost_microusd, _failure_code, _rest_body, _validate_approval,
    _parse_provider_response, _http_call, _load_public_requests,
    run_once,
)
from evaluate_source_id_multipdf_35_lite import (
    LABEL_SCHEMA, PACKET_SHA256, PILOT_SYSTEM_INSTRUCTION, SCHEMA,
    build_pilot_request, digest,
)
from finalize_public_source_id_multipdf import ReviewError
from prepare_public_source_id_multipdf import canonical_bytes
from app.workers.rag_answer import _source_judge_rest_body


def wire(source_id="S01"):
    return build_pilot_request("How is the public method defined?", [{
        "id": source_id, "page": 2,
        "page_text": "The public method has an explicit definition.",
        "cue": "an explicit definition",
    }])


def test_35_lite_identity_and_ledger_are_separate_from_consumed_36(
    tmp_path, monkeypatch,
):
    import evaluate_source_id_multipdf_36 as old_evaluator
    import evaluate_source_id_multipdf_35_lite as evaluator
    import run_public_source_id_multipdf_36 as old_caller
    import run_public_source_id_multipdf_35_lite as caller

    assert MODEL == "gemini-3.5-flash-lite"
    assert ENDPOINT == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-3.5-flash-lite:generateContent"
    )
    assert SCHEMA != old_evaluator.SCHEMA
    assert APPROVAL_SCHEMA != old_caller.APPROVAL_SCHEMA
    assert caller.AUTHORIZATION_ID.startswith(
        "lane6-public-35-lite-eight-pdf-20260929-"
    )
    assert evaluator._fingerprint("a" * 64, "b" * 64, "c" * 64) != (
        old_evaluator._fingerprint("a" * 64, "b" * 64, "c" * 64)
    )
    monkeypatch.setattr(evaluator, "gettempdir", lambda: str(tmp_path))
    assert caller._approval_claim_path("d" * 64, "calibration").parent == (
        tmp_path / "cardchemy-source-id-35-lite-pilot-ledger"
    )
    assert (caller._approval_claim_path("d" * 64, "calibration") ==
            caller._approval_claim_path("e" * 64, "calibration"))
    assert (caller._approval_claim_path("d" * 64, "calibration") !=
            caller._approval_claim_path("d" * 64, "heldout"))


def test_heldout_inherits_calibration_wall_clock_and_acl_probe(tmp_path):
    import run_public_source_id_multipdf_35_lite as caller

    started = 1_700_000_000_000
    last_call = started + 10_000
    assert caller._pilot_timing_from_calibration(
        {"pilot_started_unix_ms": started,
         "last_call_started_unix_ms": last_call},
        started + MAX_TOTAL_SECONDS * 1000 - 1,
    ) == (started, last_call)
    with pytest.raises(PilotFailure, match="total_time_budget"):
        caller._pilot_timing_from_calibration(
            {"pilot_started_unix_ms": started,
             "last_call_started_unix_ms": last_call},
            started + MAX_TOTAL_SECONDS * 1000,
        )
    with pytest.raises(PilotFailure, match="total_time_budget"):
        caller._pilot_timing_from_calibration(
            {"pilot_started_unix_ms": True}, started + 1,
        )
    with pytest.raises(PilotFailure, match="calibration_call_time_invalid"):
        caller._pilot_timing_from_calibration(
            {"pilot_started_unix_ms": started}, last_call + 1,
        )
    caller._probe_writable_directory(tmp_path)
    assert not list(tmp_path.iterdir())
    with pytest.raises(PilotFailure, match="os_temp_output_required"):
        caller._probe_writable_directory(tmp_path / "missing")


def test_preflight_rejects_consumed_global_or_local_claim(tmp_path):
    import run_public_source_id_multipdf_35_lite as caller

    prepared_dir = tmp_path / "prepared"
    prepared_dir.mkdir()
    approval_claim = tmp_path / "approval.claim"
    caller._ensure_claims_available(approval_claim, prepared_dir)
    approval_claim.write_bytes(b"claimed")
    with pytest.raises(PilotFailure, match="pilot_claim_consumed"):
        caller._ensure_claims_available(approval_claim, prepared_dir)
    approval_claim.unlink()
    (prepared_dir / "live-run.claim").write_bytes(b"claimed")
    with pytest.raises(PilotFailure, match="pilot_claim_consumed"):
        caller._ensure_claims_available(approval_claim, prepared_dir)


def test_keyless_score_ledger_preflight_preserves_one_shot_claim(
    tmp_path, monkeypatch,
):
    import evaluate_source_id_multipdf_35_lite as evaluator
    import run_public_source_id_multipdf_35_lite as caller

    monkeypatch.setattr(evaluator, "gettempdir", lambda: str(tmp_path))
    fingerprint = "e" * 64
    caller._preflight_score_claim(fingerprint, "calibration")
    score_claim = evaluator._global_score_claim_path(fingerprint, "calibration")
    assert score_claim.parent == tmp_path / "cardchemy-source-id-35-lite-pilot-ledger"
    assert not score_claim.exists()
    original = canonical_bytes({"request": "first"})
    score_claim.write_bytes(original)
    with pytest.raises(PilotFailure, match="pilot_score_claim_consumed"):
        caller._preflight_score_claim(fingerprint, "calibration")
    assert score_claim.read_bytes() == original


def test_preapproval_preflight_checks_frozen_labels_without_key_or_claim(
    tmp_path, monkeypatch,
):
    import evaluate_source_id_multipdf_35_lite as evaluator
    import run_public_source_id_multipdf_35_lite as caller

    monkeypatch.setattr(evaluator, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(caller, "gettempdir", lambda: str(tmp_path))
    labels = {"schema": LABEL_SCHEMA, "packet_sha256": PACKET_SHA256,
              "groups": [{} for _ in range(96)],
              "reviewer_ids": ["reviewer-a", "reviewer-b"]}
    labels_path = tmp_path / "frozen-labels.json"
    labels_path.write_bytes(canonical_bytes(labels))
    labels_sha = digest(labels_path.read_bytes())
    freeze = {"schema": LABEL_SCHEMA + "_freeze",
              "packet_sha256": PACKET_SHA256,
              "labels_sha256": labels_sha,
              "review_a_sha256": "a" * 64,
              "review_b_sha256": "b" * 64}
    freeze_path = tmp_path / "freeze-receipt.json"
    freeze_path.write_bytes(canonical_bytes(freeze))
    prepared_dir = tmp_path / "prepared"
    packet_dir = tmp_path / "source"
    prepared_dir.mkdir()
    packet_dir.mkdir()
    prompt = wire()
    prepared = {"split": "calibration", "requests": [{"status": "callable",
                "wire": prompt}]}
    receipt = {"labels_sha256": labels_sha,
               "freeze_receipt_sha256": digest(freeze_path.read_bytes()),
               "fingerprint": "e" * 64, "callable_count": 1}
    monkeypatch.setattr(caller, "_load_public_requests",
                        lambda *_args: (prepared, receipt))
    monkeypatch.setattr(caller, "_source_judge_key",
                        lambda: pytest.fail("credential read in keyless preflight"))
    monkeypatch.setattr(caller, "_validate_approval",
                        lambda *_args: pytest.fail("approval read in keyless preflight"))
    args = argparse.Namespace(
        approval_receipt=None, approval_sha256=None,
        calibration_score=None, calibration_score_sha256=None,
        calibration_live_result=None, calibration_live_result_sha256=None,
        prepared_dir=prepared_dir, packet_dir=packet_dir,
        prepare_sha256="1" * 64, labels=labels_path,
    )
    result = caller._admit_preapproval_cli(args)
    assert result["status"] == "preapproval_preflight_passed"
    assert result["authorization_pending"] is True
    assert result["source_judge_key_checked"] is False
    assert result["max_input_token_admission_estimate"] <= MAX_INPUT_PER_CALL
    assert not (prepared_dir / "live-run.claim").exists()
    assert not list(tmp_path.glob("**/approval-*.claim"))
    prepared["split"] = "heldout"
    with pytest.raises(PilotFailure, match="calibration_gate_required"):
        caller._admit_preapproval_cli(args)
    prepared["split"] = "calibration"
    freeze["labels_sha256"] = "f" * 64
    freeze_path.write_bytes(canonical_bytes(freeze))
    with pytest.raises(ReviewError, match="input_hash_mismatch"):
        caller._admit_preapproval_cli(args)


@pytest.mark.asyncio
async def test_heldout_waits_for_twenty_seconds_after_last_calibration_start(tmp_path):
    prepared, receipt, approval = prepared_rows(1)
    prepared["split"] = approval["split"] = "heldout"
    started = 1_700_000_000_000
    last_calibration = started + 10_000
    now_ms = last_calibration + 5_000
    monotonic = 0.0
    starts = []

    async def sleeper(seconds):
        nonlocal now_ms, monotonic
        now_ms += round(seconds * 1000)
        monotonic += seconds

    async def transport(_wire):
        starts.append(now_ms)
        return model_response()

    result = await run_once(
        prepared, receipt, approval, tmp_path, transport,
        approval_claim_path=tmp_path.parent / f"{tmp_path.name}-gap.claim",
        clock=lambda: monotonic, sleeper=sleeper,
        wall_clock=lambda: now_ms / 1000,
        pilot_started_unix_ms=started,
        last_calibration_call_unix_ms=last_calibration,
    )
    assert result["status"] == "complete_one_shot"
    assert starts == [last_calibration + 20_000]
    assert result["last_call_started_unix_ms"] == starts[0]


@pytest.mark.asyncio
async def test_heldout_remaining_global_deadline_bounds_the_physical_call(tmp_path):
    prepared, receipt, approval = prepared_rows(1)
    prepared["split"] = approval["split"] = "heldout"
    started = 1_700_000_000_000
    just_before_deadline = started + MAX_TOTAL_SECONDS * 1000 - 50
    calls = 0

    async def slow(_wire):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.2)
        return model_response()

    result = await run_once(
        prepared, receipt, approval, tmp_path, slow,
        approval_claim_path=tmp_path.parent / f"{tmp_path.name}-deadline.claim",
        wall_clock=lambda: just_before_deadline / 1000,
        pilot_started_unix_ms=started,
        last_calibration_call_unix_ms=started,
    )
    assert calls == 1
    assert result["status"] == "stopped_no_retry"
    assert result["reason"] == "provider_timeout"
    assert result["attempts"] == 1
    assert result["failed_attempt_cost_unknown"] is True
    assert (tmp_path / "call-01.claim").exists()


@pytest.mark.asyncio
async def test_expired_deadline_after_call_claim_sends_nothing(tmp_path):
    prepared, receipt, approval = prepared_rows(1)
    prepared["split"] = approval["split"] = "heldout"
    started = 1_700_000_000_000
    deadline = started + MAX_TOTAL_SECONDS * 1000
    instants = iter((started, deadline - 1, deadline - 1, deadline))
    calls = 0

    async def transport(_wire):
        nonlocal calls
        calls += 1
        return model_response()

    result = await run_once(
        prepared, receipt, approval, tmp_path, transport,
        approval_claim_path=tmp_path.parent / f"{tmp_path.name}-expired.claim",
        wall_clock=lambda: next(instants) / 1000,
        pilot_started_unix_ms=started,
        last_calibration_call_unix_ms=started,
    )
    assert calls == 0
    assert result["status"] == "stopped_no_retry"
    assert result["reason"] == "total_time_budget"
    assert result["attempts"] == 0
    assert (tmp_path / "call-01.claim").exists()


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
    assert body["systemInstruction"]["parts"][0]["text"] == PILOT_SYSTEM_INSTRUCTION
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


def test_only_dedicated_source_judge_key_is_selected(monkeypatch):
    import app.config as config
    import run_public_source_id_multipdf_35_lite as caller

    class JudgeSettings:
        rag_source_judge_api_key_value = "test-judge-key"

        @property
        def rag_ai_api_key_value(self):
            raise AssertionError("embedding credential must not be read")

    monkeypatch.setattr(config, "Settings", JudgeSettings)
    assert caller._source_judge_key() == "test-judge-key"

    class EmbeddingOnlySettings:
        rag_source_judge_api_key_value = None
        rag_ai_api_key_value = "test-embedding-key"

    monkeypatch.setattr(config, "Settings", EmbeddingOnlySettings)
    with pytest.raises(PilotFailure, match="provider_key_unavailable"):
        caller._source_judge_key()


def test_rest_body_refuses_oversized_serialized_request(monkeypatch):
    import run_public_source_id_multipdf_35_lite as caller
    monkeypatch.setattr(caller, "MAX_REST_REQUEST_BYTES", 10)
    with pytest.raises(PilotFailure, match="rest_body_budget"):
        _rest_body(wire())


def test_rest_body_has_separate_input_token_admission_estimate(monkeypatch):
    import run_public_source_id_multipdf_35_lite as caller

    body = _rest_body(wire())
    assert len(canonical_bytes(body)) + caller.INPUT_TOKEN_PROTOCOL_RESERVE <= (
        MAX_INPUT_PER_CALL
    )
    monkeypatch.setattr(caller, "INPUT_TOKEN_PROTOCOL_RESERVE", MAX_INPUT_PER_CALL)
    with pytest.raises(PilotFailure, match="input_token_admission_budget"):
        _rest_body(wire())


def test_worst_case_96_call_budget_is_below_fifty_cents():
    assert 96 * _cost_microusd(8192, 1024) == 481_728
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
    import run_public_source_id_multipdf_35_lite as caller
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
                               "wire": build_pilot_request(
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
    assert starts[1][0] - starts[0][0] >= 20
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
async def test_first_calibration_http_400_stops_before_second_call(tmp_path):
    prepared, receipt, approval = prepared_rows(2)
    approval_claim = tmp_path.parent / f"{tmp_path.name}-approval.claim"
    calls = 0

    async def transport(_sent):
        nonlocal calls
        calls += 1
        return model_response(status=400)

    result = await run_once(
        prepared, receipt, approval, tmp_path, transport,
        approval_claim_path=approval_claim,
    )
    assert calls == result["attempts"] == 1
    assert result["status"] == "stopped_no_retry"
    assert result["http_status"] == 400
    assert result["failed_attempt_cost_unknown"] is True
    assert approval_claim.exists()
    assert (tmp_path / "call-01.claim").exists()
    assert not (tmp_path / "call-02.claim").exists()
    assert (tmp_path / "response-ids.jsonl").read_bytes() == b""
    assert not (tmp_path / "live-result.json").exists()


@pytest.mark.parametrize("exc, expected", [
    (httpx.ConnectError("private source should not be logged"),
     "provider_connect_error"),
    (httpx.ProxyError("private source should not be logged"),
     "provider_proxy_error"),
    (httpx.ReadTimeout("private source should not be logged"),
     "provider_timeout"),
    (httpx.RemoteProtocolError("private source should not be logged"),
     "provider_protocol_error"),
    (PermissionError("private path should not be logged"),
     "local_permission_error"),
    (PilotFailure("private source should not be logged"),
     "pilot_guard_failed"),
])
def test_failure_classification_never_uses_exception_message(exc, expected):
    assert _failure_code(exc) == expected


@pytest.mark.asyncio
async def test_connect_error_saves_only_class_and_elapsed_without_retry(tmp_path):
    prepared, receipt, approval = prepared_rows(1)
    approval_claim = tmp_path.parent / f"{tmp_path.name}-connect.claim"
    calls = 0
    now = [1.0]

    async def transport(_sent):
        nonlocal calls
        calls += 1
        now[0] += 0.125
        raise httpx.ConnectError("do not retain private source or key")

    result = await run_once(prepared, receipt, approval, tmp_path, transport,
                            approval_claim_path=approval_claim,
                            clock=lambda: now[0])
    assert result["status"] == "stopped_no_retry"
    assert result["reason"] == "provider_connect_error"
    assert result["elapsed_since_call_claim_ms"] == 125
    assert result["attempts"] == calls == 1
    assert result["failed_attempt_cost_unknown"] is True
    assert (tmp_path / "call-01.claim").exists()
    assert (tmp_path / "response-ids.jsonl").read_bytes() == b""
    assert (tmp_path / "usage-receipts.jsonl").read_bytes() == b""
    saved = (tmp_path / "live-failure.json").read_bytes()
    assert b"do not retain" not in saved


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


def test_approval_must_bind_exact_envelope_and_prepare_hash(tmp_path, monkeypatch):
    import run_public_source_id_multipdf_35_lite as caller

    assert AUTHORIZATION_ID.startswith(
        "lane6-public-35-lite-eight-pdf-20260929-"
    )
    prepared = {"split": "calibration"}
    receipt = {"requests_sha256": "1" * 64, "fingerprint": "2" * 64}
    base = {"schema": APPROVAL_SCHEMA,
            "authorization_id": "PENDING_SEPARATE_OPERATOR_APPROVAL",
            "operator_approved": True, "public_only": True,
            "free_tier_expected": True,
            "previous_failed_cost_unknown": True,
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
            "input_price_usd_per_million": "0.30",
            "output_price_usd_per_million": "2.50",
            "max_call_seconds": MAX_CALL_SECONDS,
            "max_total_seconds": MAX_TOTAL_SECONDS,
            "min_start_interval_seconds": MIN_START_INTERVAL_SECONDS,
            "prior_cost_microusd": 0}
    path = tmp_path / "approval.json"
    path.write_bytes(canonical_bytes(base))
    monkeypatch.setattr(caller, "AUTHORIZATION_ID", "PENDING_SEPARATE_OPERATOR_APPROVAL")
    with pytest.raises(PilotFailure, match="separate_operator_approval_required"):
        _validate_approval(path, digest(path.read_bytes()), prepared, receipt)
    approved_id = "separately-approved-test-only-id"
    monkeypatch.setattr(caller, "AUTHORIZATION_ID", approved_id)
    base["authorization_id"] = approved_id
    path.write_bytes(canonical_bytes(base))
    _validate_approval(path, digest(path.read_bytes()), prepared, receipt)
    base["max_cost_microusd"] = MAX_COST_MICROUSD * 2
    path.write_bytes(canonical_bytes(base))
    with pytest.raises(PilotFailure, match="approval_envelope_mismatch"):
        _validate_approval(path, digest(path.read_bytes()), prepared, receipt)
