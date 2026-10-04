"""Keyless safety and source-binding checks for the categorical pilot."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import httpx
import pytest


_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "scripts"))

import launch_fresh_public_categorical_page_judge_v1 as launcher  # noqa: E402
import prepare_fresh_public_categorical_page_judge_v1_approval as preparer  # noqa: E402
import run_fresh_public_categorical_page_judge_v1 as caller  # noqa: E402
import run_fresh_public_per_page_verdict_flash_v1 as prior  # noqa: E402
import test_run_fresh_public_source_id_v2_augmented as old_tests  # noqa: E402


@pytest.fixture
def public_packet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    packet = old_tests.public_packet.__wrapped__(tmp_path, monkeypatch)
    source_sha = caller.digest(packet["manifest"].read_bytes())
    monkeypatch.setattr(caller, "SOURCE_MANIFEST_SHA256", source_sha)
    monkeypatch.setattr(prior, "SOURCE_MANIFEST_SHA256", source_sha)
    return packet


def _admit(module: object, packet: dict) -> dict:
    return module.admit_public_packet(
        packet["frozen"], packet["manifest"], packet["overlap"],
        "calibration",
    )


def _receipt(admitted: dict, tmp_path: Path) -> dict:
    value = {
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
        "calibration_score_sha256": None,
        "endpoint": caller._model_endpoint(),
        "model": caller.MODEL,
        "thinking": caller.THINKING,
        "automatic_retries": 0,
        "max_calls": 66,
        "max_input_tokens_per_call": caller.MAX_INPUT_PER_CALL,
        "max_output_tokens_per_call": caller.MAX_OUTPUT_PER_CALL,
        "max_new_cost_microusd": caller.SPLIT_COST_CAPS_MICROUSD["calibration"],
        "max_call_seconds": caller.MAX_CALL_SECONDS,
        "max_total_seconds": caller.MAX_TOTAL_SECONDS,
        "min_start_interval_seconds": caller.MIN_START_INTERVAL_SECONDS,
        "input_price_usd_per_million": "0.30",
        "output_price_usd_per_million": "2.50",
    }
    path = tmp_path / "approval.json"
    raw = caller.canonical_bytes(value)
    path.write_bytes(raw)
    return caller.validate_approval(path, caller.digest(raw), admitted)


def _response(ids: list[str], *, malformed: bool = False) -> httpx.Response:
    rows = [{"id": identifier, "label": "DIRECT_RELATION"}
            for identifier in ids]
    if malformed:
        rows[-1]["id"] = "foreign-id"
    return httpx.Response(200, json={
        "modelVersion": caller.MODEL,
        "candidates": [{"finishReason": "STOP", "content": {"parts": [{
            "text": json.dumps({"verdicts": rows}),
        }]}}],
        "usageMetadata": {"promptTokenCount": 100,
                          "candidatesTokenCount": 20,
                          "thoughtsTokenCount": 5,
                          "totalTokenCount": 125},
    })


def test_frozen_packet_is_same_but_categorical_wire_and_scorer_are_distinct(
    public_packet: dict,
) -> None:
    new = _admit(caller, public_packet)
    old = _admit(prior, public_packet)
    assert len(new["requests"]) == len(old["requests"]) == 66
    assert new["packet_sha256"] == old["packet_sha256"]
    assert new["labels_sha256"] == old["labels_sha256"]
    assert new["body_manifest_sha256"] != old["body_manifest_sha256"]
    assert new["source_sha256"]["prototype"] != old["source_sha256"]["prototype"]
    assert new["source_sha256"]["scorer"] != old["source_sha256"]["scorer"]
    assert new["source_sha256"]["caller"] != old["source_sha256"]["caller"]
    assert new["source_sha256"]["launcher"] != old["source_sha256"]["launcher"]
    assert new["source_sha256"]["approval_preparer"] == caller.digest(
        (_ROOT / "scripts" /
         "prepare_fresh_public_categorical_page_judge_v1_approval.py").read_bytes()
    )


def test_all_66_public_bodies_are_complete_bound_and_within_both_budgets(
    public_packet: dict,
) -> None:
    admitted = _admit(caller, public_packet)
    assert len(admitted["requests"]) == 66
    assert len({row["group_id"] for row in admitted["requests"]}) == 66
    assert admitted["max_rest_request_bytes"] <= caller.MAX_REST_BYTES
    assert (admitted["max_model_visible_input_bytes"] +
            caller.INPUT_TOKEN_PROTOCOL_RESERVE <= caller.MAX_INPUT_PER_CALL)
    assert all(row["issued_ids"] == ["S01", "S02", "S03", "S04"]
               for row in admitted["requests"])
    for row in admitted["requests"]:
        body = row["body"]
        assert set(body) == {"systemInstruction", "contents", "generationConfig",
                             "store"}
        assert body["store"] is False
        assert body["generationConfig"]["thinkingConfig"] == {
            "thinkingLevel": "low"}
        assert body["generationConfig"]["maxOutputTokens"] == 1_024
        assert body["generationConfig"]["responseJsonSchema"]["properties"][
            "verdicts"]["minItems"] == 4
        payload = json.loads(body["contents"][0]["parts"][0]["text"])
        assert [item["id"] for item in payload["candidates"]] == row["issued_ids"]
        assert all(set(item) == {"id", "shown_cue", "page_text", "physical_page"}
                   for item in payload["candidates"])
        assert caller.digest(caller.canonical_bytes(body)) == row["rest_body_sha256"]
    manifest = [{key: row[key] for key in
                 ("group_id", "wire_sha256", "rest_body_sha256")}
                for row in admitted["requests"]]
    assert caller.digest(caller.canonical_bytes(manifest)) == admitted[
        "body_manifest_sha256"]


def test_new_envelope_is_exact_and_disabled_branch_remains_fail_closed(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert caller.MODEL == "gemini-3.5-flash-lite"
    assert caller.THINKING == prior.THINKING == "low"
    assert caller.LIVE_ENVELOPE_APPROVED is True
    assert caller.AUTHORIZATION_ID == "lane6_public_categorical_page_judge_20260930"
    assert caller.AUTHORIZATION_ID != prior.AUTHORIZATION_ID
    assert caller.APPROVAL_SCHEMA != prior.APPROVAL_SCHEMA
    assert caller.CLAIM_SCHEMA != prior.CLAIM_SCHEMA
    assert caller.SPLIT_COST_CAPS_MICROUSD == {
        "calibration": 340_000, "heldout": 310_000,
    }
    assert caller._model_endpoint() == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-3.5-flash-lite:generateContent"
    )
    monkeypatch.setattr(caller, "LIVE_ENVELOPE_APPROVED", False)
    with pytest.raises(caller.PilotError, match="separate_operator_approval_required"):
        caller._model_endpoint()
    admitted = _admit(caller, public_packet)
    key_reads: list[bool] = []
    monkeypatch.setattr(caller, "_source_judge_key",
                        lambda: key_reads.append(True))
    with pytest.raises(caller.PilotError, match="separate_operator_approval_required"):
        asyncio.run(caller._execute_http(admitted, {}, tmp_path / "unused"))
    assert not key_reads
    assert not (tmp_path / "unused").exists()


def test_new_receipt_requires_lite_price_and_new_source_hash(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    admitted = _admit(caller, public_packet)
    monkeypatch.setattr(caller, "LIVE_ENVELOPE_APPROVED", True)
    monkeypatch.setattr(caller, "AUTHORIZATION_ID", "test_categorical_page_judge")
    monkeypatch.setattr(caller, "SPLIT_COST_CAPS_MICROUSD",
                        {"calibration": 340_000, "heldout": 310_000})
    receipt = {
        "schema_version": caller.APPROVAL_SCHEMA,
        "authorization_id": caller.AUTHORIZATION_ID,
        "operator_approved": True,
        "public_only": True,
        "previous_attempt_cost_unknown": True,
        "corpus_id": caller.freezer.CORPUS_ID,
        "split": "calibration",
        "source_manifest_sha256": admitted["source_manifest_sha256"],
        "overlap_diagnostic_sha256": admitted["overlap_diagnostic_sha256"],
        "freeze_sha256": admitted["freeze_sha256"],
        "packet_sha256": admitted["packet_sha256"],
        "labels_sha256": admitted["labels_sha256"],
        "body_manifest_sha256": admitted["body_manifest_sha256"],
        "source_sha256": admitted["source_sha256"],
        "calibration_score_sha256": None,
        "endpoint": caller._model_endpoint(),
        "model": caller.MODEL,
        "thinking": caller.THINKING,
        "automatic_retries": 0,
        "max_calls": 66,
        "max_input_tokens_per_call": caller.MAX_INPUT_PER_CALL,
        "max_output_tokens_per_call": caller.MAX_OUTPUT_PER_CALL,
        "max_new_cost_microusd": 340_000,
        "max_call_seconds": caller.MAX_CALL_SECONDS,
        "max_total_seconds": caller.MAX_TOTAL_SECONDS,
        "min_start_interval_seconds": caller.MIN_START_INTERVAL_SECONDS,
        "input_price_usd_per_million": "0.30",
        "output_price_usd_per_million": "2.50",
    }

    def validate(value: dict) -> dict:
        path = tmp_path / "receipt.json"
        raw = caller.canonical_bytes(value)
        path.write_bytes(raw)
        return caller.validate_approval(path, caller.digest(raw), admitted)

    assert validate(receipt)["model"] == "gemini-3.5-flash-lite"
    with pytest.raises(caller.PilotError, match="approval_price_invalid"):
        validate({**receipt, "input_price_usd_per_million": "1.50"})
    with pytest.raises(caller.PilotError, match="approval_identity_mismatch"):
        validate({**receipt, "source_sha256": prior._source_files()})
    with pytest.raises(caller.PilotError, match="approval_envelope_invalid"):
        validate({**receipt, "max_new_cost_microusd": 1_450_000})


def test_parse_valid_four_labels_and_reject_foreign_id(
    public_packet: dict, tmp_path: Path,
) -> None:
    admitted = _admit(caller, public_packet)
    approval = _receipt(admitted, tmp_path)
    ids = admitted["requests"][0]["issued_ids"]
    raw, input_tokens, output_tokens = caller._parse_response(
        _response(ids), ids, approval)
    assert caller.parse_categorical_page_judge_output(raw, ids) == tuple(ids[:3])
    assert (input_tokens, output_tokens) == (100, 25)
    with pytest.raises(caller.InvalidContentResponse,
                       match="provider_verdicts_invalid"):
        caller._parse_response(_response(ids, malformed=True), ids, approval)


def test_three_provider_503s_stop_after_ten_or_fewer_claims_without_retry(
    public_packet: dict, tmp_path: Path,
) -> None:
    admitted = _admit(caller, public_packet)
    approval = _receipt(admitted, tmp_path)
    seen: list[str] = []

    async def transport(body: dict) -> httpx.Response:
        row = admitted["requests"][len(seen)]
        assert body == row["body"]
        seen.append(row["group_id"])
        return httpx.Response(503, content=b"")

    clock, sleeper = old_tests._fake_clock()
    ledger = tmp_path / "separate-categorical-ledger"
    ledger.mkdir()
    result = asyncio.run(caller.run_split(
        admitted, approval, tmp_path / "results", transport,
        ledger=ledger, monotonic=clock, sleeper=sleeper))
    assert result["status"] == "stopped_no_retry"
    assert result["reason"] == "too_many_provider_failures"
    assert result["attempts_claimed"] == len(seen) == 3
    assert len(set(seen)) == 3
    assert len(list(ledger.glob("*.claim"))) == 4  # split + three calls
    assert len((tmp_path / "results" / "errors.jsonl").read_text().splitlines()) == 3
    assert not (tmp_path / "results" / "run-complete.json").exists()


def test_mock_66_response_run_scores_only_calibration(
    public_packet: dict, tmp_path: Path,
) -> None:
    admitted = _admit(caller, public_packet)
    approval = _receipt(admitted, tmp_path)
    calls = 0

    async def transport(body: dict) -> httpx.Response:
        nonlocal calls
        row = admitted["requests"][calls]
        assert body == row["body"]
        calls += 1
        return _response(row["issued_ids"])

    clock, sleeper = old_tests._fake_clock()
    ledger = tmp_path / "mock-categorical-ledger"
    ledger.mkdir()
    output = tmp_path / "results"
    result = asyncio.run(caller.run_split(
        admitted, approval, output, transport,
        ledger=ledger, monotonic=clock, sleeper=sleeper))
    assert result["status"] == "complete_one_shot"
    assert result["attempts_claimed"] == calls == 66
    score = caller.scorer.score_run(public_packet["frozen"], output)
    assert score["heldout_opened"] is False
    assert score["release_gate_passed"] is False
    assert score["calibration"]["metrics"]["counts"]["accepted_responses"] == 66


def test_cli_returns_distinct_failure_after_durable_failed_quality_score(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "new-categorical-result"
    monkeypatch.setattr(sys, "argv", [
        "pilot", "--execute", "--frozen-dir", str(tmp_path),
        "--source-manifest", str(tmp_path / "public-manifest.json"),
        "--overlap-diagnostic", str(tmp_path / "overlap.json"),
        "--split", "calibration", "--approval-receipt",
        str(tmp_path / "approval.json"), "--approval-sha256", "0" * 64,
        "--output-dir", str(output),
    ])
    monkeypatch.setattr(caller, "admit_public_packet", lambda *args, **kwargs: {})
    monkeypatch.setattr(caller, "validate_approval", lambda *args: {})

    async def completed(_admitted: dict, _approval: dict, directory: Path) -> dict:
        directory.mkdir()
        caller._write_exclusive(directory / "run-complete.json",
                                {"status": "complete_one_shot"})
        return {"status": "complete_one_shot"}

    monkeypatch.setattr(caller, "_execute_http", completed)
    monkeypatch.setattr(caller.scorer, "score_run", lambda *args: {
        "calibration_passed": False, "heldout_opened": False,
        "release_gate_passed": False,
    })
    assert caller.main() == 3
    assert (output / "run-complete.json").exists()
    assert json.loads((output / "score.json").read_text())[
        "calibration_passed"] is False


def test_preparer_and_launcher_do_not_read_key_or_write_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    approval_path = tmp_path / "approval.json"
    monkeypatch.setattr(sys, "argv", [
        "prepare", "--frozen-dir", str(tmp_path),
        "--source-manifest", str(tmp_path / "missing.json"),
        "--overlap-diagnostic", str(tmp_path / "missing-overlap.json"),
        "--split", "calibration", "--output", str(approval_path),
    ])
    assert preparer.main() == 2
    assert not approval_path.exists()
    key_reads: list[bool] = []
    monkeypatch.setattr(launcher, "_read_key", lambda _: key_reads.append(True))
    assert launcher.main(["--execute"]) == 2
    assert not key_reads


def test_heldout_stays_sealed_without_this_candidates_pass(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[str] = []
    real = caller.scorer._packet_and_request_hashes

    def track(*args: object) -> tuple:
        opened.append(str(args[-1]))
        return real(*args)

    monkeypatch.setattr(caller.scorer, "_packet_and_request_hashes", track)
    with pytest.raises(caller.PilotError, match="calibration_score_required"):
        caller.admit_public_packet(
            public_packet["frozen"], public_packet["manifest"],
            public_packet["overlap"], "heldout",
        )
    assert "heldout" not in opened
    assert not (tmp_path / "heldout-results").exists()
