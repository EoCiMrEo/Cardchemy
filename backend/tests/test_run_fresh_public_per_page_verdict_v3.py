"""Provider-free admission tests for the one-use per-page public pilot."""

from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
import sys

import httpx
import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "scripts"))
import run_fresh_public_per_page_verdict_v3 as caller  # noqa: E402
import test_run_fresh_public_source_id_v2_augmented as old_tests  # noqa: E402


@pytest.fixture
def public_packet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    packet = old_tests.public_packet.__wrapped__(tmp_path, monkeypatch)
    monkeypatch.setattr(caller, "SOURCE_MANIFEST_SHA256",
                        caller.digest(packet["manifest"].read_bytes()))
    return packet


def _admit(packet: dict, split: str = "calibration") -> dict:
    return caller.admit_public_packet(
        packet["frozen"], packet["manifest"], packet["overlap"], split)


def _approved_envelope(monkeypatch: pytest.MonkeyPatch, admitted: dict,
                       tmp_path: Path) -> dict:
    monkeypatch.setattr(caller, "LIVE_ENVELOPE_APPROVED", True)
    monkeypatch.setattr(caller, "AUTHORIZATION_ID", "per-page-public-test")
    monkeypatch.setattr(caller, "MODEL", "gemini-test-public")
    monkeypatch.setattr(caller, "SPLIT_COST_CAPS_MICROUSD",
                        {"calibration": 340_000, "heldout": 310_000})
    receipt = {
        "schema_version": caller.APPROVAL_SCHEMA,
        "authorization_id": caller.AUTHORIZATION_ID,
        "operator_approved": True,
        "public_only": True,
        "previous_attempt_cost_unknown": True,
        "corpus_id": caller.freezer.CORPUS_ID,
        "split": admitted["split"],
        "source_manifest_sha256": admitted["source_manifest_sha256"],
        "overlap_diagnostic_sha256": admitted["overlap_diagnostic_sha256"],
        "freeze_sha256": admitted["freeze_sha256"],
        "packet_sha256": admitted["packet_sha256"],
        "labels_sha256": admitted["labels_sha256"],
        "body_manifest_sha256": admitted["body_manifest_sha256"],
        "source_sha256": admitted["source_sha256"],
        "calibration_score_sha256": admitted["calibration_score_sha256"],
        "endpoint": caller._model_endpoint(),
        "model": caller.MODEL,
        "thinking": caller.THINKING,
        "automatic_retries": 0,
        "max_calls": len(admitted["requests"]),
        "max_input_tokens_per_call": caller.MAX_INPUT_PER_CALL,
        "max_output_tokens_per_call": caller.MAX_OUTPUT_PER_CALL,
        "max_new_cost_microusd": 340_000,
        "max_call_seconds": caller.MAX_CALL_SECONDS,
        "max_total_seconds": caller.MAX_TOTAL_SECONDS,
        "min_start_interval_seconds": caller.MIN_START_INTERVAL_SECONDS,
        "input_price_usd_per_million": "0.30",
        "output_price_usd_per_million": "2.50",
    }
    path = tmp_path / "local-test-approval.json"
    sha = caller.digest(caller.canonical_bytes(receipt))
    path.write_bytes(caller.canonical_bytes(receipt))
    return {"path": path, "sha": sha,
            "approval": caller.validate_approval(path, sha, admitted),
            "receipt": receipt}


def _response(ids: list[str], *, malformed: bool = False) -> httpx.Response:
    verdicts = [{"id": identifier, "useful_reading_page": True,
                 "requested_relation_present": True} for identifier in ids]
    if malformed:
        verdicts[-1]["id"] = "foreign-id"
    body = {
        "modelVersion": caller.MODEL,
        "candidates": [{"finishReason": "STOP", "content": {
            "parts": [{"text": json.dumps({"verdicts": verdicts})}]}}],
        "usageMetadata": {"promptTokenCount": 100,
                          "candidatesTokenCount": 20,
                          "thoughtsTokenCount": 5,
                          "totalTokenCount": 125},
    }
    return httpx.Response(200, json=body)


def test_keyless_public_preflight_builds_all_66_verdict_wires(public_packet: dict) -> None:
    admitted = _admit(public_packet)
    assert len(admitted["requests"]) == 66
    assert admitted["calibration_score_sha256"] is None
    assert admitted["max_rest_request_bytes"] <= caller.MAX_REST_BYTES
    assert all(set(row["body"]["generationConfig"]["responseJsonSchema"])
               == {"type", "additionalProperties", "properties", "required"}
               for row in admitted["requests"])
    assert all(row["body"]["store"] is False for row in admitted["requests"])
    assert all(len(row["issued_ids"]) == 4 for row in admitted["requests"])
    assert all(caller.digest(caller.canonical_bytes(row["body"])) ==
               row["rest_body_sha256"] for row in admitted["requests"])


def test_execute_and_key_access_are_closed_when_envelope_fence_is_off(
    monkeypatch: pytest.MonkeyPatch, public_packet: dict, tmp_path: Path,
) -> None:
    monkeypatch.setattr(caller, "LIVE_ENVELOPE_APPROVED", False)
    admitted = _admit(public_packet)
    key_reads: list[bool] = []
    monkeypatch.setattr(caller, "_source_judge_key",
                        lambda: key_reads.append(True))
    with pytest.raises(caller.PilotError, match="separate_operator_approval_required"):
        asyncio.run(caller._execute_http(admitted, {}, tmp_path / "results"))
    assert not key_reads
    assert not (tmp_path / "results").exists()
    with pytest.raises(caller.PilotError, match="separate_operator_approval_required"):
        caller.validate_approval(tmp_path / "missing.json", "0" * 64, admitted)


def test_heldout_sealed_until_new_calibration_score_passes(
    monkeypatch: pytest.MonkeyPatch, public_packet: dict, tmp_path: Path,
) -> None:
    reads: list[str] = []
    real = caller.scorer._packet_and_request_hashes

    def track(*args: object) -> tuple:
        reads.append(str(args[-1]))
        return real(*args)

    monkeypatch.setattr(caller.scorer, "_packet_and_request_hashes", track)
    with pytest.raises(caller.PilotError, match="calibration_score_required"):
        _admit(public_packet, "heldout")
    assert "heldout" not in reads
    old_result = tmp_path / "old-calibration"
    old_result.mkdir()
    with pytest.raises((caller.PilotError, caller.baseline.ScoreError)):
        caller.admit_public_packet(
            public_packet["frozen"], public_packet["manifest"],
            public_packet["overlap"], "heldout", old_result,
            calibration_approval_path=tmp_path / "old-approval.json",
            calibration_approval_sha="0" * 64)
    assert "heldout" not in reads


@pytest.mark.parametrize("change", [
    {"automatic_retries": 1}, {"max_calls": 67},
    {"max_input_tokens_per_call": 16_384},
    {"max_output_tokens_per_call": 2_048},
    {"max_call_seconds": 60}, {"max_total_seconds": 7_200},
    {"min_start_interval_seconds": 0},
    {"max_new_cost_microusd": 650_000},
    {"input_price_usd_per_million": "0.01"},
    {"output_price_usd_per_million": "0.01"},
])
def test_approval_binding_and_budget_changes_fail(
    monkeypatch: pytest.MonkeyPatch, public_packet: dict,
    tmp_path: Path, change: dict,
) -> None:
    admitted = _admit(public_packet)
    base = _approved_envelope(monkeypatch, admitted, tmp_path)
    mutated = copy.deepcopy(base["receipt"])
    mutated.update(change)
    path = tmp_path / "changed-approval.json"
    raw = caller.canonical_bytes(mutated)
    path.write_bytes(raw)
    with pytest.raises(caller.PilotError):
        caller.validate_approval(path, caller.digest(raw), admitted)
    with pytest.raises(caller.PilotError, match="approval_receipt_changed"):
        caller.validate_approval(base["path"], "0" * 64, admitted)


def test_valid_http_verdict_and_foreign_id_rejection(
    monkeypatch: pytest.MonkeyPatch, public_packet: dict, tmp_path: Path,
) -> None:
    admitted = _admit(public_packet)
    approved = _approved_envelope(monkeypatch, admitted, tmp_path)["approval"]
    ids = admitted["requests"][0]["issued_ids"]
    raw, input_tokens, output_tokens = caller._parse_response(
        _response(ids), ids, approved)
    assert caller.parse_per_page_source_verdict_output(raw, ids) == tuple(ids[:3])
    assert (input_tokens, output_tokens) == (100, 25)
    with pytest.raises(caller.PilotError, match="provider_verdicts_invalid"):
        caller._parse_response(_response(ids, malformed=True), ids, approved)


def test_malformed_verdict_consumes_one_claim_without_retry(
    monkeypatch: pytest.MonkeyPatch, public_packet: dict, tmp_path: Path,
) -> None:
    admitted = _admit(public_packet)
    approved = _approved_envelope(monkeypatch, admitted, tmp_path)["approval"]
    calls = 0

    async def invalid(_body: dict) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _response(admitted["requests"][0]["issued_ids"], malformed=True)

    ledger = tmp_path / "new-v3-ledger"
    ledger.mkdir()
    result = asyncio.run(caller.run_split(
        admitted, approved, tmp_path / "results", invalid, ledger=ledger))
    assert result["status"] == "stopped_no_retry"
    assert result["reason"] == "provider_verdicts_invalid"
    assert result["attempts_claimed"] == calls == 1
    assert result["reported_input_tokens"] == 100
    assert result["reported_output_tokens"] == 25
    assert result["known_cost_microusd"] == 93
    assert result["failed_attempt_cost_unknown"] is False
    assert len(list(ledger.glob("*.claim"))) == 2  # split + first group
    assert not (tmp_path / "results" / "run-complete.json").exists()


@pytest.mark.parametrize("change,reason", [
    ("candidates", "provider_candidate_invalid"),
    ("finish", "provider_finish_invalid"),
])
def test_malformed_200_preserves_usage_and_stops_once(
    monkeypatch: pytest.MonkeyPatch, public_packet: dict, tmp_path: Path,
    change: str, reason: str,
) -> None:
    admitted = _admit(public_packet)
    approved = _approved_envelope(monkeypatch, admitted, tmp_path)["approval"]
    calls = 0

    async def malformed(_body: dict) -> httpx.Response:
        nonlocal calls
        calls += 1
        response = _response(admitted["requests"][0]["issued_ids"])
        body = json.loads(response.content)
        if change == "candidates":
            body["candidates"] = []
        else:
            body["candidates"][0]["finishReason"] = "MAX_TOKENS"
        return httpx.Response(200, json=body)

    ledger = tmp_path / "ledger"
    ledger.mkdir()
    result = asyncio.run(caller.run_split(
        admitted, approved, tmp_path / "results", malformed,
        ledger=ledger))
    assert result["status"] == "stopped_no_retry"
    assert result["reason"] == reason
    assert result["attempts_claimed"] == calls == 1
    assert result["reported_input_tokens"] == 100
    assert result["reported_output_tokens"] == 25
    assert result["known_cost_microusd"] == 93
    assert result["failed_attempt_cost_unknown"] is False


def test_launcher_source_sha_is_bound_to_approval(
    monkeypatch: pytest.MonkeyPatch, public_packet: dict, tmp_path: Path,
) -> None:
    admitted = _admit(public_packet)
    launcher = _ROOT / "scripts" / "launch_fresh_public_per_page_verdict_v3.py"
    assert admitted["source_sha256"]["launcher"] == caller.digest(
        launcher.read_bytes())
    receipt = _approved_envelope(monkeypatch, admitted, tmp_path)
    changed_admission = copy.deepcopy(admitted)
    changed_admission["source_sha256"]["launcher"] = caller.digest(b"new-launcher")
    with pytest.raises(caller.PilotError, match="approval_identity_mismatch"):
        caller.validate_approval(receipt["path"], receipt["sha"], changed_admission)


def test_transient_503_is_one_failed_case_without_retry(
    monkeypatch: pytest.MonkeyPatch, public_packet: dict, tmp_path: Path,
) -> None:
    admitted = _admit(public_packet)
    approved = _approved_envelope(monkeypatch, admitted, tmp_path)["approval"]
    seen: list[str] = []

    async def transport(body: dict) -> httpx.Response:
        row = admitted["requests"][len(seen)]
        assert body == row["body"]
        seen.append(row["group_id"])
        if len(seen) == 1:
            return httpx.Response(503, content=b"")
        return _response(row["issued_ids"])

    clock, sleeper = old_tests._fake_clock()
    ledger = tmp_path / "new-v3-ledger"
    ledger.mkdir()
    result = asyncio.run(caller.run_split(
        admitted, approved, tmp_path / "results", transport,
        ledger=ledger, monotonic=clock, sleeper=sleeper))
    assert result["status"] == "complete_one_shot"
    assert result["attempts_claimed"] == len(seen) == 66
    assert len(set(seen)) == 66
    errors = (tmp_path / "results" / "errors.jsonl").read_text().splitlines()
    assert len(errors) == 1
    assert json.loads(errors[0])["reason"] == "provider_http_503"
    assert result["known_cost_microusd"] > 0


def test_unapproved_launcher_never_reads_root_key(monkeypatch: pytest.MonkeyPatch) -> None:
    import launch_fresh_public_per_page_verdict_v3 as launcher
    reads: list[bool] = []
    monkeypatch.setattr(launcher, "_read_key", lambda _: reads.append(True))
    assert launcher.main(["--execute"]) == 2
    assert reads == []
