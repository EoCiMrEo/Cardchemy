"""Provider-free tests for the pending fresh public v2 caller."""

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
import run_fresh_public_source_id_v2 as caller  # noqa: E402
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
                         ("authored", "review_a", "review_b",
                          "adjudication", "overlap_review")},
        "files": file_hashes,
    })
    monkeypatch.setattr(caller, "SOURCE_MANIFEST_SHA256", manifest_hash)
    monkeypatch.setattr(caller.freezer, "load_verified_pages",
                        lambda _manifest, _path: (inputs[5], inputs[6]))
    return {"frozen": frozen, "manifest": manifest_path,
            "overlap": overlap_path, "pages": inputs[5]}


def _admit(public_packet: dict, split: str = "calibration",
           calibration_results: Path | None = None) -> dict:
    return caller.admit_public_packet(
        public_packet["frozen"], public_packet["manifest"],
        public_packet["overlap"], split, calibration_results)


def _approve(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
             admitted: dict) -> dict:
    monkeypatch.setattr(caller, "AUTHORIZATION_ID", "fresh-public-v2-test-approval")
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
        "max_calls": 48, "max_input_tokens_per_call": 8_192,
        "max_output_tokens_per_call": 1_024,
        "max_new_cost_microusd": 500_000,
        "max_call_seconds": 30, "max_total_seconds": 3_600,
        "min_start_interval_seconds": 6,
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
                  if item["page_useful"] and item["cue_useful"]]
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
    admitted = _admit(public_packet, split, calibration_results)
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


def test_default_identity_remains_pending_and_wire_is_cue_first(public_packet: dict) -> None:
    admitted = _admit(public_packet)
    assert caller.AUTHORIZATION_ID == "PENDING_SEPARATE_OPERATOR_APPROVAL"
    assert caller.MODEL == "PENDING_SEPARATE_MODEL_APPROVAL"
    with pytest.raises(caller.PilotError, match="separate_operator_approval_required"):
        caller._model_endpoint()
    first = admitted["requests"][0]
    text = first["body"]["contents"][0]["parts"][0]["text"]
    assert text.index('"shown_cue"') < text.index('"page_text"')
    assert "page_useful" not in text and "cue_useful" not in text
    assert first["rest_body_sha256"] == caller.digest(caller.canonical_bytes(first["body"]))


def test_exact_approval_requires_matching_body_code_and_cost(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    admitted = _admit(public_packet)
    _approve(tmp_path, monkeypatch, admitted)
    path = tmp_path / "calibration-approval.json"
    approval = json.loads(path.read_bytes())
    for edit in (
        {"body_manifest_sha256": "0" * 64},
        {"source_sha256": {**approval["source_sha256"], "prototype": "0" * 64}},
        {"input_price_usd_per_million": "unknown"},
        {"max_new_cost_microusd": 1},
        {"max_output_tokens_per_call": 1},
        {"max_input_tokens_per_call": 16_384},
        {"automatic_retries": 1},
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


def test_fake_transport_produces_48_bound_receipts_and_calibration_score(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, output, admitted = _run(tmp_path, public_packet, monkeypatch)
    assert result["status"] == "complete_one_shot"
    assert result["attempts_claimed"] == 48
    assert result["reported_input_tokens"] == 48_000
    assert result["known_cost_microusd"] > 0
    assert result["authorization_id"] == caller.AUTHORIZATION_ID
    assert result["approval_receipt_sha256"] == caller.digest(
        (tmp_path / "calibration-approval.json").read_bytes())
    assert len(result["claim_manifest_sha256"]) == 64
    assert caller.scorer.score_run(public_packet["frozen"], output)["calibration_passed"] is True
    assert len(list((tmp_path / "ledger").glob("*.claim"))) == 49
    receipt_text = (output / "response-ids.jsonl").read_text(encoding="utf-8")
    assert len(receipt_text.splitlines()) == 48
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
    assert result["attempts_claimed"] == len(calls) == 48
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
        caller._verify_complete_claims(admitted, ledger, scope, output)


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
        _admit(public_packet, "heldout", output)


def test_heldout_requires_saved_scored_calibration_pass(
    public_packet: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(caller.PilotError, match="calibration_score_required"):
        _admit(public_packet, "heldout")
    result, calibration, _admitted = _run(tmp_path, public_packet, monkeypatch)
    assert result["status"] == "complete_one_shot"
    score = caller.scorer.score_run(public_packet["frozen"], calibration)
    _write(calibration / "score.json", score)
    heldout = _admit(public_packet, "heldout", calibration)
    assert heldout["calibration_score_sha256"] == caller.digest(caller.canonical_bytes(score))
    altered = copy.deepcopy(score)
    altered["calibration_passed"] = False
    _write(calibration / "score.json", altered)
    with pytest.raises(caller.PilotError, match="calibration_score_changed"):
        _admit(public_packet, "heldout", calibration)
