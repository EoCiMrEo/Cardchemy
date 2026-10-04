"""Keyless safety and same-wire checks for the approved public pilot."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import pytest


_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "scripts"))

import launch_fresh_public_per_page_verdict_flash_v1 as launcher  # noqa: E402
import prepare_fresh_public_per_page_verdict_flash_v1_approval as preparer  # noqa: E402
import run_fresh_public_per_page_verdict_flash_v1 as caller  # noqa: E402
import run_fresh_public_per_page_verdict_v3 as prior  # noqa: E402
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


def test_frozen_wire_and_scorer_are_identical_to_prior_candidate(
    public_packet: dict,
) -> None:
    new = _admit(caller, public_packet)
    old = _admit(prior, public_packet)
    assert len(new["requests"]) == len(old["requests"]) == 66
    assert new["body_manifest_sha256"] == old["body_manifest_sha256"]
    assert [(row["group_id"], row["wire_sha256"], row["rest_body_sha256"])
            for row in new["requests"]] == [
                (row["group_id"], row["wire_sha256"], row["rest_body_sha256"])
                for row in old["requests"]
            ]
    assert new["source_sha256"]["prototype"] == old["source_sha256"]["prototype"]
    assert new["source_sha256"]["scorer"] == old["source_sha256"]["scorer"]
    assert new["source_sha256"]["caller"] != old["source_sha256"]["caller"]
    assert new["source_sha256"]["launcher"] != old["source_sha256"]["launcher"]
    assert new["source_sha256"]["approval_preparer"] == caller.digest(
        (_ROOT / "scripts" /
         "prepare_fresh_public_per_page_verdict_flash_v1_approval.py").read_bytes()
    )


def test_new_envelope_is_exact_and_disabled_branch_remains_fail_closed(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert caller.MODEL == "gemini-3.5-flash"
    assert caller.THINKING == prior.THINKING == "low"
    assert caller.LIVE_ENVELOPE_APPROVED is True
    assert caller.AUTHORIZATION_ID == "lane6_public_per_page_verdict_flash_20260930"
    assert caller.AUTHORIZATION_ID != prior.AUTHORIZATION_ID
    assert caller.APPROVAL_SCHEMA != prior.APPROVAL_SCHEMA
    assert caller.CLAIM_SCHEMA != prior.CLAIM_SCHEMA
    assert caller.SPLIT_COST_CAPS_MICROUSD == {
        "calibration": 1_450_000, "heldout": 1_350_000,
    }
    assert caller._model_endpoint() == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-3.5-flash:generateContent"
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


def test_new_receipt_requires_stronger_model_price_and_new_source_hash(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    admitted = _admit(caller, public_packet)
    monkeypatch.setattr(caller, "LIVE_ENVELOPE_APPROVED", True)
    monkeypatch.setattr(caller, "AUTHORIZATION_ID", "test_stronger_page_judge")
    monkeypatch.setattr(caller, "SPLIT_COST_CAPS_MICROUSD",
                        {"calibration": 1_450_000, "heldout": 1_350_000})
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
        "max_new_cost_microusd": 1_450_000,
        "max_call_seconds": caller.MAX_CALL_SECONDS,
        "max_total_seconds": caller.MAX_TOTAL_SECONDS,
        "min_start_interval_seconds": caller.MIN_START_INTERVAL_SECONDS,
        "input_price_usd_per_million": "1.50",
        "output_price_usd_per_million": "9.00",
    }

    def validate(value: dict) -> dict:
        path = tmp_path / "receipt.json"
        raw = caller.canonical_bytes(value)
        path.write_bytes(raw)
        return caller.validate_approval(path, caller.digest(raw), admitted)

    assert validate(receipt)["model"] == "gemini-3.5-flash"
    with pytest.raises(caller.PilotError, match="approval_price_invalid"):
        validate({**receipt, "input_price_usd_per_million": "0.30"})
    with pytest.raises(caller.PilotError, match="approval_identity_mismatch"):
        validate({**receipt, "source_sha256": prior._source_files()})
    with pytest.raises(caller.PilotError, match="approval_envelope_invalid"):
        validate({**receipt, "max_new_cost_microusd": 340_000})


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
