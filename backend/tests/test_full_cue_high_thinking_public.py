"""Synthetic and keyless public-only controls for the high-thinking candidate."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import subprocess
import sys
import time

import httpx
import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import launch_fresh_public_full_cue_high_thinking_v1 as launcher  # noqa: E402
import prototype_categorical_page_judge_v1 as old_wire  # noqa: E402
import prototype_full_cue_high_thinking_v1 as wire  # noqa: E402
import run_fresh_public_categorical_page_judge_v1 as old_caller  # noqa: E402
import run_fresh_public_full_cue_high_thinking_v1 as caller  # noqa: E402
import test_run_fresh_public_source_id_v2_augmented as old_tests  # noqa: E402
from app.ai.source_judgment import SourceJudgmentError  # noqa: E402


@pytest.fixture
def public_packet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    # Synthetic tests start from a denied envelope regardless of whether the
    # separate real public pilot was approved. No test reads its key or ledger.
    monkeypatch.setattr(caller, "LIVE_ENVELOPE_APPROVED", False)
    monkeypatch.setattr(caller, "AUTHORIZATION_ID", "UNAPPROVED_public_full_cue_high_thinking_v1")
    monkeypatch.setattr(caller, "SPLIT_COST_CAPS_MICROUSD", {"calibration": 0, "heldout": 0})
    packet = old_tests.public_packet.__wrapped__(tmp_path, monkeypatch)
    monkeypatch.setattr(caller, "SOURCE_MANIFEST_SHA256",
                        caller.digest(packet["manifest"].read_bytes()))
    return packet


def _admit(packet: dict) -> dict:
    return caller.admit_public_packet(
        packet["frozen"], packet["manifest"], packet["overlap"],
        "calibration",
    )


def _approved(monkeypatch: pytest.MonkeyPatch) -> None:
    # Only a synthetic test overrides the production-disabled live fence.
    monkeypatch.setattr(caller, "LIVE_ENVELOPE_APPROVED", True)
    monkeypatch.setattr(caller, "AUTHORIZATION_ID", "test_full_cue_high_thinking_v1")
    monkeypatch.setattr(caller, "SPLIT_COST_CAPS_MICROUSD",
                        {"calibration": 600_000, "heldout": 550_000})


def _receipt(admitted: dict, tmp_path: Path) -> dict:
    approval = {
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
        "max_new_cost_microusd": caller.SPLIT_COST_CAPS_MICROUSD[admitted["split"]],
        "max_call_seconds": caller.MAX_CALL_SECONDS,
        "max_total_seconds": caller.MAX_TOTAL_SECONDS,
        "min_start_interval_seconds": caller.MIN_START_INTERVAL_SECONDS,
        "input_price_usd_per_million": "0.30",
        "output_price_usd_per_million": "2.50",
    }
    path = tmp_path / (admitted["split"] + "-synthetic-approval.json")
    raw = caller.canonical_bytes(approval)
    path.write_bytes(raw)
    return caller.validate_approval(path, caller.digest(raw), admitted)


def _response(ids: list[str], *, label: str = "DIRECT_RELATION",
              output_tokens: int = 1_800) -> httpx.Response:
    verdicts = [{"id": source_id, "label": label} for source_id in ids]
    return httpx.Response(200, json={
        "modelVersion": caller.MODEL,
        "candidates": [{"finishReason": "STOP", "content": {"parts": [{
            "text": json.dumps({"verdicts": verdicts}),
        }]}}],
        "usageMetadata": {"promptTokenCount": 300,
                          "candidatesTokenCount": 80,
                          "thoughtsTokenCount": output_tokens - 80,
                          "totalTokenCount": 300 + output_tokens},
    })


def test_same_full_cues_prompt_and_labels_with_only_rest_compute_change(
    public_packet: dict,
) -> None:
    admitted = _admit(public_packet)
    assert len(admitted["requests"]) == 66
    assert admitted["max_model_visible_input_bytes"] + 512 <= 8_192
    assert admitted["max_rest_request_bytes"] <= 12_288
    assert caller.LIVE_ENVELOPE_APPROVED is False
    assert caller.SPLIT_COST_CAPS_MICROUSD == {"calibration": 0, "heldout": 0}
    assert caller.AUTHORIZATION_ID.startswith("UNAPPROVED")
    assert caller.THINKING == "high"
    assert caller.MAX_OUTPUT_PER_CALL == 2_048
    assert caller.AUTHORIZATION_ID != old_caller.AUTHORIZATION_ID
    assert caller.CLAIM_SCHEMA != old_caller.CLAIM_SCHEMA
    for row in admitted["requests"]:
        body = row["body"]
        assert body["generationConfig"]["thinkingConfig"] == {
            "thinkingLevel": "high"}
        assert body["generationConfig"]["maxOutputTokens"] == 2_048
        assert body["store"] is False
        payload = json.loads(body["contents"][0]["parts"][0]["text"])
        assert [candidate["id"] for candidate in payload["candidates"]] == [
            "S01", "S02", "S03", "S04"]
        assert all(set(candidate) == {"id", "shown_cue", "page_text",
                                      "physical_page"}
                   for candidate in payload["candidates"])
        low_body = old_caller._rest_body(old_wire.build_categorical_public_wire(
            payload["question"], [
                {"id": item["id"], "page": item["physical_page"],
                 "cue": item["shown_cue"], "page_text": item["page_text"]}
                for item in payload["candidates"]]))
        assert body["systemInstruction"] == low_body["systemInstruction"]
        assert body["contents"] == low_body["contents"]
        assert body["generationConfig"]["responseJsonSchema"] == (
            low_body["generationConfig"]["responseJsonSchema"])
        assert caller.digest(caller.canonical_bytes(body)) == row[
            "rest_body_sha256"]


def test_no_approval_cannot_read_key_or_execute(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    admitted = _admit(public_packet)
    key_reads: list[bool] = []
    monkeypatch.setattr(caller, "_source_judge_key",
                        lambda: key_reads.append(True))
    with pytest.raises(caller.PilotError,
                       match="separate_operator_approval_required"):
        asyncio.run(caller._execute_http(admitted, {}, tmp_path / "unused"))
    monkeypatch.setattr(launcher, "_read_key",
                        lambda _: key_reads.append(True))
    assert launcher.main(["--execute"]) == 2
    assert not key_reads
    assert not (tmp_path / "unused").exists()


def test_parser_rejects_foreign_duplicate_answer_and_transport_failure() -> None:
    ids = ["S01", "S02", "S03", "S04"]
    valid = {"verdicts": [{"id": source_id, "label": "TOPIC_ONLY"}
                          for source_id in ids]}
    assert wire.parse_high_thinking_page_judge_output(
        json.dumps(valid), ids) == ()
    valid["verdicts"][0]["label"] = "USEFUL_BRIDGE"
    assert wire.parse_high_thinking_page_judge_output(
        json.dumps(valid), ids) == ("S01",)
    for malformed in (
        {"selected_ids": ["S01"], "answer": "forbidden"},
        {"verdicts": [{"id": "foreign", "label": "DIRECT_RELATION"},
                       *valid["verdicts"][1:]]},
        {"verdicts": [valid["verdicts"][0]] * 4},
    ):
        with pytest.raises(SourceJudgmentError):
            wire.parse_high_thinking_page_judge_output(
                json.dumps(malformed), ids)
    with pytest.raises(SourceJudgmentError,
                       match="source_judgment_transport_unavailable"):
        wire.parse_high_thinking_page_judge_output(None, ids,
                                                   transport_succeeded=False)


def test_high_thinking_usage_budget_includes_hidden_thoughts(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _approved(monkeypatch)
    admitted = _admit(public_packet)
    approval = _receipt(admitted, tmp_path)
    ids = admitted["requests"][0]["issued_ids"]
    selected, input_tokens, output_tokens = caller._parse_response(
        _response(ids, output_tokens=2_040), ids, approval)
    assert selected == tuple(ids[:3])
    assert (input_tokens, output_tokens) == (300, 2_040)
    with pytest.raises(caller.InvalidContentResponse, match="provider_token_limit_exceeded") as exc:
        caller._parse_response(_response(ids, output_tokens=2_049), ids,
                               approval)
    assert (exc.value.input_tokens, exc.value.output_tokens) == (300, 2_049)


def test_mathematically_unreachable_calibration_stops_without_opening_heldout(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _approved(monkeypatch)
    admitted = _admit(public_packet)
    approval = _receipt(admitted, tmp_path)
    seen = 0

    async def transport(body: dict) -> httpx.Response:
        nonlocal seen
        assert body == admitted["requests"][seen]["body"]
        row = admitted["requests"][seen]
        seen += 1
        return _response(row["issued_ids"], output_tokens=120)

    clock, sleeper = old_tests._fake_clock()
    ledger = tmp_path / "unique-ledger"
    ledger.mkdir()
    output = tmp_path / "results"
    result = asyncio.run(caller.run_split(
        admitted, approval, output, transport, ledger=ledger,
        monotonic=clock, sleeper=sleeper))
    assert result["status"] == "stopped_no_retry"
    assert result["reason"] == "calibration_quality_unreachable"
    assert 1 <= result["attempts_claimed"] == seen < 66
    assert len(list((output / "attempt-journal").glob("G*.json"))) == seen
    assert not (output / "selected-ids.jsonl").exists()
    assert not (output / "run-complete.json").exists()
    assert not (tmp_path / "sealed-heldout").exists()
    with pytest.raises(FileExistsError):
        asyncio.run(caller.run_split(
            admitted, approval, tmp_path / "new-results", transport,
            ledger=ledger, monotonic=clock, sleeper=sleeper))


def test_perfect_synthetic_calibration_passes_without_opening_heldout(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _approved(monkeypatch)
    admitted = _admit(public_packet)
    approval = _receipt(admitted, tmp_path)
    labels = json.loads((public_packet["frozen"] / "calibration" /
                         "labels.json").read_bytes())
    useful = {
        group["group_id"]: {
            row["id"] for row in group["candidates"]
            if row["page_useful"] and row["cue_useful"]
        } for group in labels["groups"]
    }
    seen = 0

    async def transport(body: dict) -> httpx.Response:
        nonlocal seen
        row = admitted["requests"][seen]
        assert body == row["body"]
        seen += 1
        verdicts = [{"id": source_id,
                     "label": ("DIRECT_RELATION" if source_id in useful[
                         row["group_id"]] else "TOPIC_ONLY")}
                    for source_id in row["issued_ids"]]
        response = _response(row["issued_ids"], output_tokens=1_800)
        payload = response.json()
        payload["candidates"][0]["content"]["parts"][0]["text"] = json.dumps(
            {"verdicts": verdicts})
        return httpx.Response(200, json=payload)

    clock, sleeper = old_tests._fake_clock()
    ledger = tmp_path / "gold-ledger"
    ledger.mkdir()
    output = tmp_path / "gold-results"
    result = asyncio.run(caller.run_split(
        admitted, approval, output, transport, ledger=ledger,
        monotonic=clock, sleeper=sleeper))
    assert result["status"] == "complete_one_shot"
    assert len(list((output / "attempt-journal").glob("G*.json"))) == 66
    assert len((output / "selected-ids.jsonl").read_bytes().splitlines()) == 66
    assert len((output / "usage-receipts.jsonl").read_bytes().splitlines()) == 66
    assert (output / "errors.jsonl").read_bytes() == b""
    score = caller.scorer.score_run(public_packet["frozen"], output)
    assert score["calibration_passed"] is True
    assert score["heldout_opened"] is False
    assert score["release_gate_passed"] is False
    assert score["calibration"]["metrics"]["counts"]["displayed_cards"] > 0
    assert score["calibration"]["metrics"]["counts"][
        "reported_output_tokens"] == 66 * 1_800
    assert score["calibration"]["metrics"]["counts"]["attempt_latency_count"] == 66
    assert result["latency_p95_ms"] == 0  # This fake transport consumes no clock time.
    for path in (output / "attempt-journal").glob("*.json"):
        raw = path.read_text()
        assert "raw_json" not in raw and "verdicts" not in raw
        record = json.loads(raw)
        assert set(record["response"]) == {
            "group_id", "request_sha256", "attempt_sha256", "selected_ids", "model"}



def test_failed_provider_cases_have_single_atomic_error_and_no_false_no_match(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _approved(monkeypatch)
    admitted = _admit(public_packet)
    approval = _receipt(admitted, tmp_path)
    calls = 0

    async def unavailable(_: dict) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, content=b"")

    clock, sleeper = old_tests._fake_clock()
    ledger = tmp_path / "error-ledger"
    ledger.mkdir()
    output = tmp_path / "error-results"
    result = asyncio.run(caller.run_split(
        admitted, approval, output, unavailable, ledger=ledger,
        monotonic=clock, sleeper=sleeper))
    assert result["status"] == "stopped_no_retry"
    assert result["reason"] == "too_many_provider_failures"
    assert result["attempts_claimed"] == calls == 3
    assert len(list((output / "attempt-journal").glob("G*.json"))) == 3
    assert not (output / "selected-ids.jsonl").exists()
    assert not (output / "run-complete.json").exists()


def test_usage_survives_over_budget_stop_without_storing_model_output(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _approved(monkeypatch)
    admitted = _admit(public_packet)
    approval = _receipt(admitted, tmp_path)
    calls = 0
    clock, sleeper = old_tests._fake_clock()

    async def over_budget(_: dict) -> httpx.Response:
        nonlocal calls
        calls += 1
        await sleeper(1.25)
        return _response(admitted["requests"][0]["issued_ids"], output_tokens=2_049)

    ledger = tmp_path / "over-budget-ledger"
    ledger.mkdir()
    output = tmp_path / "over-budget-result"
    result = asyncio.run(caller.run_split(
        admitted, approval, output, over_budget, ledger=ledger,
        monotonic=clock, sleeper=sleeper))
    assert calls == result["attempts_claimed"] == 1
    assert result["reason"] == "provider_token_limit_exceeded"
    assert result["reported_output_tokens"] == 2_049
    assert result["reported_input_tokens"] == 300
    assert result["known_cost_microusd"] == caller._cost_microusd(300, 2_049, approval)
    assert result["failed_attempt_cost_unknown"] is False
    assert result["attempt_latency_count"] == 1
    assert result["latency_max_ms"] == 1_250
    assert not list((output / "attempt-journal").iterdir())
    assert not (output / "run-complete.json").exists()


def test_best_possible_bound_keeps_all_perfect_prefixes_and_rejects_weak_padding(
    public_packet: dict,
) -> None:
    admitted = _admit(public_packet)
    outcomes = {}
    assert not caller._quality_unreachable(admitted, outcomes)
    for row in admitted["requests"]:
        outcomes[row["group_id"]] = admitted["quality_gold"][row["group_id"]]["useful_ids"][:3]
        assert not caller._quality_unreachable(admitted, outcomes)
    # The precision gate can fail even when every stratum retains its
    # required number of exact matches.
    chosen = {key: tuple(value) for key, value in outcomes.items()}
    for amount in (1, 2, 3):
        stratum = [row for row in admitted["requests"]
                   if len(admitted["quality_gold"][row["group_id"]]["useful_ids"]) == amount]
        for row in stratum[:len(stratum) // 6]:
            useful = chosen[row["group_id"]]
            chosen[row["group_id"]] = tuple(
                identifier for identifier in row["issued_ids"] if identifier not in useful)[:3]
        assert sum(set(chosen[row["group_id"]]) == set(
            admitted["quality_gold"][row["group_id"]]["useful_ids"])
            for row in stratum) >= caller.baseline.ceil_ratio(5, 6, len(stratum))
    displayed = sum(len(value) for value in chosen.values())
    helpful = sum(len(set(value).intersection(admitted["quality_gold"][key]["useful_ids"]))
                  for key, value in chosen.items())
    assert 10 * helpful < 9 * displayed
    assert caller._quality_unreachable(admitted, chosen)


def test_heldout_requires_real_calibration_receipts_and_accepts_different_latency(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _approved(monkeypatch)
    ledger = tmp_path / "staged-ledger"
    ledger.mkdir()
    calibration = _admit(public_packet)
    cal_approval = _receipt(calibration, tmp_path)

    def run_perfect(admitted: dict, approval: dict, path: Path, latency: float) -> dict:
        clock, sleeper = old_tests._fake_clock()
        seen = 0

        async def transport(_: dict) -> httpx.Response:
            nonlocal seen
            row = admitted["requests"][seen]
            seen += 1
            await sleeper(latency)
            useful = admitted["quality_gold"][row["group_id"]]["useful_ids"]
            payload = _response(row["issued_ids"], output_tokens=150).json()
            payload["candidates"][0]["content"]["parts"][0]["text"] = json.dumps({
                "verdicts": [{"id": sid, "label": "DIRECT_RELATION" if sid in useful
                               else "TOPIC_ONLY"} for sid in row["issued_ids"]]})
            return httpx.Response(200, json=payload)

        return asyncio.run(caller.run_split(admitted, approval, path, transport,
                                           ledger=ledger, monotonic=clock, sleeper=sleeper))

    cal_output = tmp_path / "calibration-result"
    assert run_perfect(calibration, cal_approval, cal_output, 0.1)["status"] == "complete_one_shot"
    cal_score = caller.scorer.score_run(public_packet["frozen"], cal_output)
    (cal_output / "score.json").write_bytes(caller.canonical_bytes(cal_score))
    assert cal_score["calibration_passed"]
    cal_receipt = tmp_path / "calibration-synthetic-approval.json"
    heldout = caller.admit_public_packet(
        public_packet["frozen"], public_packet["manifest"], public_packet["overlap"],
        "heldout", cal_output, ledger, cal_receipt, caller.digest(cal_receipt.read_bytes()))
    heldout_approval = _receipt(heldout, tmp_path)
    heldout_output = tmp_path / "heldout-result"
    assert run_perfect(heldout, heldout_approval, heldout_output, 0.2)["status"] == "complete_one_shot"
    score = caller.scorer.score_run(public_packet["frozen"], cal_output, heldout_output)
    assert score["heldout_passed"] and score["heldout_opened"]
    assert not score["release_gate_passed"]
    assert score["calibration"]["metrics"]["counts"]["latency_p95_ms"] == 100
    assert score["heldout"]["metrics"]["counts"]["latency_p95_ms"] == 200
    assert not caller._quality_unreachable(heldout, {})
    no_match = next(row for row in heldout["requests"]
                    if not heldout["quality_gold"][row["group_id"]]["useful_ids"])
    assert caller._quality_unreachable(heldout, {no_match["group_id"]: ("S01",)})
    # Tampering a passing receipt cannot open heldout on the next admission.
    saved = json.loads((cal_output / "score.json").read_bytes())
    saved["calibration_passed"] = False
    (cal_output / "score.json").write_bytes(caller.canonical_bytes(saved))
    with pytest.raises(caller.PilotError, match="calibration_score_changed"):
        caller.admit_public_packet(
            public_packet["frozen"], public_packet["manifest"], public_packet["overlap"],
            "heldout", cal_output, ledger, cal_receipt, caller.digest(cal_receipt.read_bytes()))


def test_detached_launcher_survives_parent_exit_with_no_network(
    tmp_path: Path,
) -> None:
    """A harmless fake child proves launch does not depend on parent lifetime."""
    output = tmp_path / "detached-fake-result"
    fake = tmp_path / "fake_child.py"
    fake.write_text(
        "import pathlib, sys, time\n"
        "time.sleep(0.4)\n"
        "p = pathlib.Path(sys.argv[sys.argv.index('--output-dir') + 1])\n"
        "p.mkdir()\n"
        "(p / 'finished.txt').write_text('done')\n",
        encoding="utf-8",
    )
    harness = tmp_path / "launch_fake.py"
    harness.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(ROOT / 'scripts')!r})\n"
        "import launch_fresh_public_full_cue_high_thinking_v1 as launcher\n"
        "import run_fresh_public_full_cue_high_thinking_v1 as caller\n"
        "caller.LIVE_ENVELOPE_APPROVED = True\n"
        "caller.AUTHORIZATION_ID = 'test_detached_fake_child'\n"
        f"launcher.CALLER = __import__('pathlib').Path({str(fake)!r})\n"
        f"launcher._detached_execute(['--execute', '--output-dir', {str(output)!r}, "
        "'--approval-sha256', 'a' * 64], {}, 'a' * 64)\n",
        encoding="utf-8",
    )
    result = subprocess.run([sys.executable, str(harness)],
                            cwd=ROOT, capture_output=True, text=True,
                            timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "detached-fake-result.launch-process.json").is_file()
    deadline = time.monotonic() + 10
    while not (output / "finished.txt").is_file() and time.monotonic() < deadline:
        time.sleep(0.1)
    assert (output / "finished.txt").read_text(encoding="utf-8") == "done"
