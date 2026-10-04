"""Provider-free tests for the pending augmented public v2 caller."""

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
import run_fresh_public_source_id_v2_augmented as caller  # noqa: E402
import test_prepare_fresh_public_source_id_v2 as packet_fixture  # noqa: E402


def _write(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = caller.canonical_bytes(value)
    path.write_bytes(raw)
    return caller.digest(raw)


@pytest.fixture
def public_packet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    inputs = list(packet_fixture.example_inputs())
    manifest_path = tmp_path / "source" / "manifest.json"
    manifest_hash = _write(manifest_path, inputs[0])
    inputs[1]["source_manifest_sha256"] = manifest_hash
    inputs[7] = manifest_hash
    artifacts = caller.freezer.build_artifacts(*inputs)
    for split in caller.scorer.SPLITS:
        packet = copy.deepcopy(artifacts[f"{split}/packet.json"])
        labels = copy.deepcopy(artifacts[f"{split}/labels.json"])
        per_form = 6 if split == "calibration" else 4
        source_indexes = [index for form in caller.scorer.FORMS[:3]
                          for index in [index for index, row in
                                        enumerate(labels["groups"])
                                        if row["form"] == form][:per_form]]
        packet["schema_version"] = caller.scorer.PACKET_SCHEMA
        labels["schema_version"] = caller.scorer.LABEL_SCHEMA
        for row in labels["groups"]:
            row["origin"] = "original"
        for index, source_index in enumerate(source_indexes, start=49):
            group = copy.deepcopy(packet["groups"][source_index])
            label = copy.deepcopy(labels["groups"][source_index])
            group["group_id"] = label["group_id"] = f"G{index:03d}"
            group["question"] += f" Additional reviewed public case {index}?"
            label["author_group_id"] = f"reserve-{split}-{index}"
            label["origin"] = "reserve"
            if split == "calibration" and index in (49, 50):
                for candidate_label in label["candidates"]:
                    candidate_label["page_useful"] = True
                    candidate_label["cue_useful"] = True
            packet["groups"].append(group)
            labels["groups"].append(label)
        labels["packet_sha256"] = caller.digest(caller.canonical_bytes(packet))
        labels["reviewer_ids"] = ["review-a", "review-b", "review-c", "review-d"]
        labels["adjudicator_id"] = ["review-e", "review-f"]
        artifacts[f"{split}/packet.json"] = packet
        artifacts[f"{split}/labels.json"] = labels
    frozen = tmp_path / "frozen"
    file_hashes = {name: _write(frozen / name, value)
                   for name, value in artifacts.items()}
    overlap = {
        "schema_version": caller.freezer.OVERLAP_DIAGNOSTIC_SCHEMA,
        "source_manifest_sha256": manifest_hash,
        "per_new_document": [
            {"document_id": document_id, "excluded_pages": []}
            for document_id in caller.freezer.EXPECTED
        ],
    }
    overlap_path = tmp_path / "overlap.json"
    overlap_hash = _write(overlap_path, overlap)
    _write(frozen / "freeze.json", {
        "schema_version": caller.scorer.FREEZE_SCHEMA,
        "corpus_id": caller.freezer.CORPUS_ID,
        "source_manifest_sha256": manifest_hash,
        "overlap_diagnostic_sha256": overlap_hash,
        "input_sha256": {name: caller.digest(name.encode()) for name in
                         ("original_authored", "original_review_a",
                          "original_review_b", "original_adjudication",
                          "reserve_authored", "reserve_blind_packet",
                          "reserve_mapping", "reserve_blind_review_a",
                          "reserve_blind_review_b", "reserve_blind_adjudication",
                          "overlap_review")},
        "files": file_hashes,
    })
    monkeypatch.setattr(caller, "SOURCE_MANIFEST_SHA256", manifest_hash)
    monkeypatch.setattr(caller.freezer, "load_verified_pages",
                        lambda _manifest, _path: (inputs[5], inputs[6]))
    return {"frozen": frozen, "manifest": manifest_path,
            "overlap": overlap_path, "pages": inputs[5]}


def _admit(public_packet: dict, split: str = "calibration",
           calibration_results: Path | None = None,
           calibration_ledger: Path | None = None,
           calibration_approval_path: Path | None = None,
           calibration_approval_sha: str | None = None) -> dict:
    return caller.admit_public_packet(
        public_packet["frozen"], public_packet["manifest"],
        public_packet["overlap"], split, calibration_results, calibration_ledger,
        calibration_approval_path, calibration_approval_sha)


def _approve(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
             admitted: dict) -> dict:
    monkeypatch.setattr(caller, "AUTHORIZATION_ID", "fresh-public-v2-augmented-test")
    monkeypatch.setattr(caller, "MODEL", "gemini-test-public")
    approval = {
        "schema_version": caller.APPROVAL_SCHEMA,
        "authorization_id": caller.AUTHORIZATION_ID,
        "operator_approved": True, "public_only": True,
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
        "endpoint": caller._model_endpoint(), "model": caller.MODEL,
        "thinking": caller.THINKING, "automatic_retries": 0,
        "max_calls": len(admitted["requests"]),
        "max_input_tokens_per_call": 8_192,
        "max_output_tokens_per_call": 1_024,
        "max_new_cost_microusd": caller.SPLIT_COST_CAPS_MICROUSD[admitted["split"]],
        "max_call_seconds": 30, "max_total_seconds": 3_600,
        "min_start_interval_seconds": 20,
        "input_price_usd_per_million": "0.30",
        "output_price_usd_per_million": "2.50",
    }
    path = tmp_path / f"{admitted['split']}-approval.json"
    approval_hash = _write(path, approval)
    return caller.validate_approval(path, approval_hash, admitted)


def _fake_clock() -> tuple[callable, callable]:
    elapsed = [0.0]

    def clock() -> float:
        return elapsed[0]

    async def sleep(seconds: float) -> None:
        elapsed[0] += seconds

    return clock, sleep


def _transport(admitted: dict, frozen: Path,
               *, bad_group: str | None = None,
               invalid_ids: bool = False) -> tuple[callable, list[dict]]:
    labels = json.loads((frozen / admitted["split"] / "labels.json").read_bytes())
    label_by_group = {row["group_id"]: row for row in labels["groups"]}
    calls: list[dict] = []

    async def send(body: dict) -> httpx.Response:
        row = admitted["requests"][len(calls)]
        assert body == row["body"]
        assert caller.digest(caller.canonical_bytes(body)) == row["rest_body_sha256"]
        calls.append(body)
        chosen = [item["id"] for item in
                  label_by_group[row["group_id"]]["candidates"]
                  if item["page_useful"] and item["cue_useful"]][:3]
        if row["group_id"] == bad_group:
            chosen = ["S99"] if invalid_ids else ["S01"]
        return httpx.Response(200, json={
            "modelVersion": caller.MODEL,
            "candidates": [{"finishReason": "STOP", "content": {"parts": [
                {"text": json.dumps({"selected_ids": chosen})}]}}],
            "usageMetadata": {"promptTokenCount": 1_000,
                              "candidatesTokenCount": 20,
                              "thoughtsTokenCount": 0,
                              "totalTokenCount": 1_020},
        })

    return send, calls


def _run(tmp_path: Path, public_packet: dict, monkeypatch: pytest.MonkeyPatch,
         *, bad_group: str | None = None, invalid_ids: bool = False,
         split: str = "calibration", calibration_results: Path | None = None) -> tuple[dict, Path, dict]:
    calibration_approval_path = (tmp_path / "calibration-approval.json"
                                 if calibration_results else None)
    admitted = _admit(
        public_packet, split, calibration_results,
        tmp_path / "ledger" if calibration_results else None,
        calibration_approval_path,
        caller.digest(calibration_approval_path.read_bytes())
        if calibration_approval_path else None)
    approval = _approve(tmp_path, monkeypatch, admitted)
    ledger = tmp_path / "ledger"
    ledger.mkdir(exist_ok=True)
    output = tmp_path / f"{split}-results"
    transport, calls = _transport(admitted, public_packet["frozen"],
                                  bad_group=bad_group, invalid_ids=invalid_ids)
    clock, sleep = _fake_clock()
    result = asyncio.run(caller.run_split(
        admitted, approval, output, transport, ledger=ledger,
        monotonic=clock, sleeper=sleep))
    assert result["attempts_claimed"] == len(calls)
    return result, output, admitted


def _passing_calibration(
    tmp_path: Path, public_packet: dict, monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict, Path, Path, str]:
    result, output, _admitted = _run(tmp_path, public_packet, monkeypatch)
    assert result["status"] == "complete_one_shot"
    score = caller.scorer.score_run(public_packet["frozen"], output)
    assert score["calibration_passed"] is True
    _write(output / "score.json", score)
    approval_path = tmp_path / "calibration-approval.json"
    return result, output, approval_path, caller.digest(approval_path.read_bytes())


def test_pinned_identity_still_requires_receipt_and_wire_is_cue_first(public_packet: dict) -> None:
    admitted = _admit(public_packet)
    assert caller.AUTHORIZATION_ID == "fresh_public_v2_126_20260930_ginu0a2J"
    assert caller.MODEL == "gemini-3.5-flash-lite"
    assert caller._model_endpoint().endswith(
        "/gemini-3.5-flash-lite:generateContent")
    first = admitted["requests"][0]
    text = first["body"]["contents"][0]["parts"][0]["text"]
    assert text.index('"shown_cue"') < text.index('"page_text"')
    assert "page_useful" not in text and "cue_useful" not in text
    assert first["rest_body_sha256"] == caller.digest(caller.canonical_bytes(first["body"]))
    assert first["body"]["store"] is False
    assert first["body"]["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}
    assert first["body"]["generationConfig"]["maxOutputTokens"] == 1_024
    assert len(admitted["requests"]) == 66
    assert caller.MAX_CALL_SECONDS == 30
    assert caller.MAX_TOTAL_SECONDS == 3_600
    assert caller.MAX_PILOT_WALL_SECONDS == 7_200
    assert caller.MIN_START_INTERVAL_SECONDS == 20
    assert caller.MAX_INPUT_PER_CALL * 126 == 1_032_192
    assert caller.MAX_OUTPUT_PER_CALL * 126 == 129_024
    assert caller.SPLIT_COST_CAPS_MICROUSD == {
        "calibration": 340_000, "heldout": 310_000,
    }


def test_exact_approval_requires_matching_body_code_and_cost(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    admitted = _admit(public_packet)
    approved = _approve(tmp_path, monkeypatch, admitted)
    worst_call_cost = caller._cost_microusd(8_192, 1_024, approved)
    assert worst_call_cost == 5_018
    assert 66 * worst_call_cost <= approved["max_new_cost_microusd"]
    assert 126 * worst_call_cost <= sum(caller.SPLIT_COST_CAPS_MICROUSD.values())
    path = tmp_path / "calibration-approval.json"
    approval = json.loads(path.read_bytes())
    for edit in (
        {"body_manifest_sha256": "0" * 64},
        {"source_sha256": {**approval["source_sha256"], "prototype": "0" * 64}},
        {"input_price_usd_per_million": "unknown"},
        {"max_new_cost_microusd": 1},
        {"max_output_tokens_per_call": 1},
        {"max_input_tokens_per_call": 16_384},
        {"max_calls": len(admitted["requests"]) - 1},
        {"automatic_retries": 1},
        {"endpoint": "https://example.invalid/generateContent"},
        {"model": "gemini-other"},
        {"thinking": "high"},
        {"max_call_seconds": 31},
        {"max_total_seconds": 7_200},
        {"min_start_interval_seconds": 19},
        {"output_price_usd_per_million": "2.51"},
        {"public_only": False},
        {"previous_attempt_cost_unknown": False},
    ):
        changed = {**approval, **edit}
        changed_path = tmp_path / "changed-approval.json"
        changed_sha = _write(changed_path, changed)
        with pytest.raises(caller.PilotError):
            caller.validate_approval(changed_path, changed_sha, admitted)


def test_frozen_public_page_bytes_and_excluded_pages_are_rechecked(
    public_packet: dict,
) -> None:
    key = next(iter(public_packet["pages"]))
    original = public_packet["pages"][key]
    public_packet["pages"][key] = "private replacement text"
    with pytest.raises(caller.PilotError, match="public_page_cue_changed"):
        _admit(public_packet)
    public_packet["pages"][key] = original
    overlap = json.loads(public_packet["overlap"].read_bytes())
    overlap["per_new_document"][0]["excluded_pages"] = [1]
    _write(public_packet["overlap"], overlap)
    with pytest.raises(caller.PilotError, match="overlap_diagnostic_invalid"):
        _admit(public_packet)


def test_fake_transport_produces_66_bound_receipts_and_calibration_score(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, output, admitted = _run(tmp_path, public_packet, monkeypatch)
    assert result["status"] == "complete_one_shot"
    assert result["attempts_claimed"] == 66
    assert result["reported_input_tokens"] == 66_000
    assert result["known_cost_microusd"] > 0
    assert result["authorization_id"] == caller.AUTHORIZATION_ID
    assert result["approval_receipt_sha256"] == caller.digest(
        (tmp_path / "calibration-approval.json").read_bytes())
    assert len(result["claim_manifest_sha256"]) == 64
    assert caller.scorer.score_run(public_packet["frozen"], output)["calibration_passed"] is True
    assert len(list((tmp_path / "ledger").glob("*.claim"))) == 67
    receipt_text = (output / "response-ids.jsonl").read_text(encoding="utf-8")
    assert len(receipt_text.splitlines()) == 66
    assert "Lecture" not in receipt_text and "Question" not in receipt_text
    assert "x-goog-api-key" not in receipt_text
    assert admitted["body_manifest_sha256"] == result["body_manifest_sha256"]


def test_failed_attempt_is_counted_without_retry_and_consumes_claim(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    admitted = _admit(public_packet)
    approval = _approve(tmp_path, monkeypatch, admitted)
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    calls = 0

    async def timeout(_body: dict) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("secret provider detail")

    clock, sleep = _fake_clock()
    result = asyncio.run(caller.run_split(
        admitted, approval, tmp_path / "stopped", timeout, ledger=ledger,
        monotonic=clock, sleeper=sleep))
    assert calls == 3
    assert result["status"] == "stopped_no_retry"
    assert result["reason"] == "too_many_provider_failures"
    assert result["failed_attempt_cost_unknown"] is True
    assert not (tmp_path / "stopped" / "evaluation.json").exists()
    assert "secret" not in (tmp_path / "stopped" / "run-stop.json").read_text()
    with pytest.raises(FileExistsError):
        asyncio.run(caller.run_split(admitted, approval,
                                     tmp_path / "second", timeout, ledger=ledger,
                                     monotonic=clock, sleeper=sleep))
    assert calls == 3


def test_invalid_id_stops_without_no_match_or_synthetic_remaining_errors(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, output, _admitted = _run(
        tmp_path, public_packet, monkeypatch,
        bad_group="G001", invalid_ids=True)
    assert result["reason"] == "provider_ids_invalid"
    assert result["attempts_claimed"] == 1
    assert (output / "errors.jsonl").read_bytes() == b""
    assert not (output / "evaluation.json").exists()


def test_one_transient_failure_counts_as_miss_and_run_continues(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    admitted = _admit(public_packet)
    approval = _approve(tmp_path, monkeypatch, admitted)
    send_normal, calls = _transport(admitted, public_packet["frozen"])
    failed_group = next(row["group_id"] for row in admitted["requests"]
                        if row["group_id"] == "G001")

    async def send(body: dict) -> httpx.Response:
        if len(calls) == 0:
            calls.append(body)
            return httpx.Response(503, json={"error": "do not persist"})
        return await send_normal(body)

    clock, sleep = _fake_clock()
    output = tmp_path / "one-transient"
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    result = asyncio.run(caller.run_split(
        admitted, approval, output, send, ledger=ledger,
        monotonic=clock, sleeper=sleep))
    assert result["status"] == "complete_one_shot"
    assert result["attempts_claimed"] == len(calls) == 66
    errors = [json.loads(line) for line in
              (output / "errors.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(errors) == 1
    assert errors[0]["group_id"] == failed_group
    assert errors[0]["reason"] == "provider_http_503"
    assert "do not persist" not in (output / "errors.jsonl").read_text()
    score = caller.scorer.score_run(public_packet["frozen"], output)
    assert score["calibration"]["metrics"]["counts"]["provider_failed_groups"] == 1


def test_complete_receipts_require_matching_physical_claims(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, output, admitted = _run(tmp_path, public_packet, monkeypatch)
    ledger = tmp_path / "ledger"
    scope = result["ledger_scope_sha256"]
    first = admitted["requests"][0]["group_id"]
    claim_path = ledger / f"{scope}-{first}.claim"
    changed = json.loads(claim_path.read_bytes())
    changed["rest_body_sha256"] = "0" * 64
    _write(claim_path, changed)
    with pytest.raises(caller.PilotError, match="attempt_claim_changed"):
        caller._verify_complete_claims(
            admitted, ledger, scope, output,
            result["approval_receipt_sha256"], result["pilot_start_epoch_ms"])


def test_http_response_stream_is_bounded_before_parsing(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    admitted = _admit(public_packet)
    approval = _approve(tmp_path, monkeypatch, admitted)
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    monkeypatch.setattr(caller, "_ledger_dir", lambda: ledger)
    monkeypatch.setattr(caller, "_source_judge_key", lambda: "fake-test-key")
    client_class = httpx.AsyncClient
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=b"x" * (caller.MAX_RESPONSE_BYTES + 1))

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        caller.httpx, "AsyncClient",
        lambda **kwargs: client_class(transport=transport, **kwargs),
    )
    result = asyncio.run(caller._execute_http(admitted, approval,
                                               tmp_path / "oversize"))
    assert result["status"] == "stopped_no_retry"
    assert result["reason"] == "provider_response_oversize"
    assert result["attempts_claimed"] == len(requests) == 1
    assert result["failed_attempt_cost_unknown"] is True


def test_failed_calibration_blocks_heldout_before_packet_read(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    labels = json.loads((public_packet["frozen"] / "calibration" /
                         "labels.json").read_bytes())
    negative_group = next(row["group_id"] for row in labels["groups"]
                          if row["form"] == "no_useful")
    result, output, _admitted = _run(
        tmp_path, public_packet, monkeypatch, bad_group=negative_group)
    assert result["status"] == "complete_one_shot"
    score = caller.scorer.score_run(public_packet["frozen"], output)
    assert score["calibration_passed"] is False
    _write(output / "score.json", score)
    heldout_packet = public_packet["frozen"] / "heldout" / "packet.json"
    heldout_packet.unlink()
    with pytest.raises(caller.PilotError, match="calibration_not_passed"):
        _admit(public_packet, "heldout", output, tmp_path / "ledger",
               tmp_path / "calibration-approval.json",
               caller.digest((tmp_path / "calibration-approval.json").read_bytes()))


def test_heldout_requires_saved_scored_calibration_pass(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(caller.PilotError, match="calibration_score_required"):
        _admit(public_packet, "heldout")
    result, calibration, _admitted = _run(tmp_path, public_packet, monkeypatch)
    assert result["status"] == "complete_one_shot"
    score = caller.scorer.score_run(public_packet["frozen"], calibration)
    _write(calibration / "score.json", score)
    cal_approval = tmp_path / "calibration-approval.json"
    cal_approval_sha = caller.digest(cal_approval.read_bytes())
    heldout = _admit(public_packet, "heldout", calibration, tmp_path / "ledger",
                     cal_approval, cal_approval_sha)
    assert heldout["calibration_score_sha256"] == caller.digest(caller.canonical_bytes(score))
    altered = copy.deepcopy(score)
    altered["calibration_passed"] = False
    _write(calibration / "score.json", altered)
    with pytest.raises(caller.PilotError, match="calibration_score_changed"):
        _admit(public_packet, "heldout", calibration, tmp_path / "ledger",
               cal_approval, cal_approval_sha)


def test_heldout_rechecks_calibration_approval_and_claim_provenance_before_packet(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    complete, calibration, approval_path, approval_sha = _passing_calibration(
        tmp_path, public_packet, monkeypatch)
    ledger = tmp_path / "ledger"
    assert len(_admit(public_packet, "heldout", calibration, ledger,
                      approval_path, approval_sha)["requests"]) == 60
    (public_packet["frozen"] / "heldout" / "packet.json").unlink()

    scope = complete["ledger_scope_sha256"]
    first_group = _admit(public_packet)["requests"][0]["group_id"]
    tamper_cases = (
        (calibration / "run-complete.json", "approval_receipt_sha256",
         "0" * 64, "calibration_run_provenance_invalid"),
        (calibration / "run-complete.json", "claim_manifest_sha256",
         "0" * 64, "calibration_run_provenance_invalid"),
        (ledger / f"{scope}.claim", "approval_receipt_sha256",
         "0" * 64, "split_claim_changed"),
        (ledger / f"{scope}-{first_group}.claim", "rest_body_sha256",
         "0" * 64, "attempt_claim_changed"),
    )
    for path, field, replacement, expected_reason in tamper_cases:
        original = path.read_bytes()
        changed = json.loads(original)
        changed[field] = replacement
        _write(path, changed)
        try:
            with pytest.raises(caller.PilotError, match=expected_reason):
                _admit(public_packet, "heldout", calibration, ledger,
                       approval_path, approval_sha)
        finally:
            path.write_bytes(original)

    original_approval = approval_path.read_bytes()
    changed_approval = json.loads(original_approval)
    changed_approval["body_manifest_sha256"] = "0" * 64
    changed_approval_sha = _write(approval_path, changed_approval)
    try:
        with pytest.raises(caller.PilotError, match="approval_identity_mismatch"):
            _admit(public_packet, "heldout", calibration, ledger,
                   approval_path, changed_approval_sha)
    finally:
        approval_path.write_bytes(original_approval)


def test_heldout_first_request_waits_even_after_calibration_finishes(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _complete, calibration, approval_path, approval_sha = _passing_calibration(
        tmp_path, public_packet, monkeypatch)
    admitted = _admit(public_packet, "heldout", calibration, tmp_path / "ledger",
                      approval_path, approval_sha)
    approval = _approve(tmp_path, monkeypatch, admitted)
    first_group = admitted["requests"][0]["group_id"]
    transport, calls = _transport(admitted, public_packet["frozen"],
                                  bad_group=first_group, invalid_ids=True)
    clock, sleep = _fake_clock()
    starts = []

    async def timed_transport(body: dict) -> httpx.Response:
        starts.append(clock())
        return await transport(body)

    result = asyncio.run(caller.run_split(
        admitted, approval, tmp_path / "heldout-delay", timed_transport,
        ledger=tmp_path / "ledger", monotonic=clock, sleeper=sleep))
    assert starts == [20.0]
    assert len(calls) == result["attempts_claimed"] == 1
    assert result["reason"] == "provider_ids_invalid"


def test_heldout_keeps_calibration_wall_start_and_stops_at_pilot_cap(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    complete, calibration, approval_path, approval_sha = _passing_calibration(
        tmp_path, public_packet, monkeypatch)
    ledger = tmp_path / "ledger"
    admitted = _admit(public_packet, "heldout", calibration, ledger,
                      approval_path, approval_sha)
    assert admitted["pilot_start_epoch_ms"] == complete["pilot_start_epoch_ms"]
    approval = _approve(tmp_path, monkeypatch, admitted)
    transport, calls = _transport(admitted, public_packet["frozen"])
    clock, sleep = _fake_clock()
    pilot_start = complete["pilot_start_epoch_ms"] / 1_000
    monkeypatch.setattr(caller.time, "time", lambda: pilot_start + 7_200)
    with pytest.raises(caller.PilotError, match="total_time_budget"):
        asyncio.run(caller.run_split(
            admitted, approval, tmp_path / "already-expired", transport,
            ledger=ledger, monotonic=clock, sleeper=sleep))
    assert calls == []
    assert not (tmp_path / "already-expired").exists()

    monkeypatch.setattr(caller.time, "time",
                        lambda: pilot_start + 7_200 - 25 + clock())
    result = asyncio.run(caller.run_split(
        admitted, approval, tmp_path / "near-expiry", transport,
        ledger=ledger, monotonic=clock, sleeper=sleep))
    assert result["status"] == "stopped_no_retry"
    assert result["reason"] == "total_time_budget"
    assert result["attempts_claimed"] == len(calls) == 1
    assert clock() == 20.0


def test_heldout_consumes_all_60_claims_after_calibration_pass(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calibration_result, calibration, _ = _run(tmp_path, public_packet, monkeypatch)
    assert calibration_result["status"] == "complete_one_shot"
    score = caller.scorer.score_run(public_packet["frozen"], calibration)
    assert score["calibration_passed"] is True
    _write(calibration / "score.json", score)
    heldout_result, heldout, admitted = _run(
        tmp_path, public_packet, monkeypatch,
        split="heldout", calibration_results=calibration)
    assert len(admitted["requests"]) == 60
    assert heldout_result["status"] == "complete_one_shot"
    assert heldout_result["attempts_claimed"] == 60
    assert 60 * caller._cost_microusd(8_192, 1_024, {
        "input_price_usd_per_million": "0.30",
        "output_price_usd_per_million": "2.50",
    }) <= caller.SPLIT_COST_CAPS_MICROUSD["heldout"]
    assert caller.scorer.score_run(
        public_packet["frozen"], calibration, heldout)["heldout_passed"] is True


def test_overflow_still_rejects_four_selected_ids_before_scoring(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    admitted = _admit(public_packet)
    approval = _approve(tmp_path, monkeypatch, admitted)
    body = {
        "modelVersion": caller.MODEL,
        "candidates": [{"finishReason": "STOP", "content": {"parts": [
            {"text": json.dumps({"selected_ids": ["S01", "S02", "S03", "S04"]})}
        ]}}],
        "usageMetadata": {"promptTokenCount": 1_000,
                          "candidatesTokenCount": 20,
                          "thoughtsTokenCount": 0,
                          "totalTokenCount": 1_020},
    }
    with pytest.raises(caller.PilotError, match="provider_ids_invalid"):
        caller._parse_response(httpx.Response(200, json=body),
                               ["S01", "S02", "S03", "S04"], approval)
