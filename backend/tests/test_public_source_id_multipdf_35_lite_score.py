"""Keyless public multi-PDF scorer gates and provider-wire boundaries."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from evaluate_source_id_multipdf_35_lite import (  # noqa: E402
    LABEL_SCHEMA, PACKET_SCHEMA, PACKET_SHA256, SCHEMA, _split_requests,
    _fingerprint, _global_approval_claim_path, digest, prepare, score,
    score_once,
)
from finalize_public_source_id_multipdf import ReviewError  # noqa: E402
from prepare_public_source_id_multipdf import canonical_bytes  # noqa: E402
import json
import pytest


def sample(split="heldout"):
    groups = []
    labels = []
    for index in range(96):
        group_split = "calibration" if index < 48 else "heldout"
        group_id = f"G{index:03d}"
        form = ("direct", "paraphrase", "follow-up")[index % 3]
        # Each form contains four groups at each 0/1/2/3 usefulness count.
        useful = (index // 3) % 4
        candidates = [{"id": f"S{number:02d}", "page": number,
                       "page_text": "The method is explained by its example.",
                       "cue": "explained by its example",
                       "document_sha256": "a" * 64 if number < 4 else "b" * 64,
                       "filename": "lec01.pdf" if number < 4 else "lec02.pdf"}
                      for number in range(1, 5)]
        groups.append({"group_id": group_id, "split": group_split,
                       "question_form": form, "question": "How is the method explained?",
                       "prior_for_local_context_only": "Earlier private context",
                       "candidates": candidates})
        labels.append({"group_id": group_id, "split": group_split,
                       "question_form": form,
                       "labels": [{"id": f"S{number:02d}",
                                   "page_useful": number <= useful,
                                   "cue_useful": number <= useful}
                                  for number in range(1, 5)]})
    packet = {"schema": PACKET_SCHEMA, "groups": groups}
    frozen = {"schema": LABEL_SCHEMA, "packet_sha256": PACKET_SHA256,
              "groups": labels}
    requests = _split_requests(packet, split)
    request_packet = {"schema": SCHEMA, "split": split, "requests": requests}
    responses = {}
    label_map = {group["group_id"]: group for group in labels}
    for request in requests:
        count = sum(item["page_useful"] for item in
                    label_map[request["group_id"]]["labels"])
        responses[request["group_id"]] = tuple(
            f"S{number:02d}" for number in range(1, count + 1))
    return packet, frozen, request_packet, responses


def frozen_public_fixture(tmp_path, monkeypatch):
    """Synthetic public pages; no real packet, key, or provider request."""
    import evaluate_source_id_multipdf_35_lite as evaluator

    packet, frozen, _requests, _responses = sample("calibration")
    frozen["reviewer_ids"] = ["reviewer-a", "reviewer-b"]
    packet_dir = tmp_path / "source"
    packet_dir.mkdir()
    (packet_dir / "blind-review-packet.json").write_bytes(canonical_bytes(packet))
    labels_path = tmp_path / "frozen-labels.json"
    labels_path.write_bytes(canonical_bytes(frozen))
    labels_sha = digest(labels_path.read_bytes())
    freeze = {"schema": LABEL_SCHEMA + "_freeze",
              "packet_sha256": PACKET_SHA256,
              "labels_sha256": labels_sha,
              "review_a_sha256": "a" * 64,
              "review_b_sha256": "b" * 64}
    freeze_path = tmp_path / "freeze-receipt.json"
    freeze_path.write_bytes(canonical_bytes(freeze))
    freeze_sha = digest(freeze_path.read_bytes())
    monkeypatch.setattr(evaluator, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(evaluator, "read_pinned", lambda path, _sha, _limit:
                        frozen if path.name == "frozen-labels.json" else packet)
    return packet_dir, labels_path, labels_sha, freeze_sha


def stage_complete_run(tmp_path, packet_dir, labels_path, labels_sha,
                       freeze_sha, directory_name, selected=None):
    """Reproduce all 48 offline receipts from a pinned prepared packet."""
    directory = tmp_path / directory_name
    prepare(packet_dir, labels_path, labels_sha, freeze_sha,
            "calibration", directory)
    prepared = json.loads((directory / "requests.json").read_bytes())
    receipt_path = directory / "prepare-receipt.json"
    receipt = json.loads(receipt_path.read_bytes())
    responses = sample("calibration")[3] if selected is None else selected
    started = 1_700_000_000_000
    run_claim = {"requests_sha256": receipt["requests_sha256"],
                 "fingerprint": receipt["fingerprint"],
                 "split": "calibration", "max_calls": 48,
                 "pilot_started_unix_ms": started,
                 "approval_sha256": "f" * 64}
    (directory / "live-run.claim").write_bytes(canonical_bytes(run_claim))
    global_claim = _global_approval_claim_path("calibration")
    if not global_claim.exists():
        global_claim.write_bytes(canonical_bytes(run_claim))
    assert global_claim.read_bytes() == canonical_bytes(run_claim)
    with (directory / "response-ids.jsonl").open("wb") as response_file, (
            directory / "usage-receipts.jsonl").open("wb") as usage_file:
        for number, row in enumerate(prepared["requests"], start=1):
            assert row["status"] == "callable"
            (directory / f"call-{number:02d}.claim").write_bytes(
                canonical_bytes({"group_id": row["group_id"],
                                 "wire_sha256": row["wire_sha256"]}))
            response_file.write(canonical_bytes({
                "group_id": row["group_id"],
                "wire_sha256": row["wire_sha256"],
                "raw_json": json.dumps({"selected_ids":
                                        responses[row["group_id"]]}),
            }))
            usage_file.write(canonical_bytes({
                "group_id": row["group_id"], "finish_reason": "STOP",
                "input_tokens": 50, "output_tokens": 8,
                "cost_microusd": 35,
            }))
    response_path = directory / "response-ids.jsonl"
    usage_path = directory / "usage-receipts.jsonl"
    live = {"status": "complete_one_shot", "split": "calibration",
            "fingerprint": receipt["fingerprint"],
            "requests_sha256": receipt["requests_sha256"],
            "approval_sha256": "f" * 64,
            "pilot_started_unix_ms": started,
            "last_call_started_unix_ms": started + 47_000,
            "attempts": 48, "prior_cost_microusd": 0,
            "known_cost_microusd": 48 * 35,
            "input_tokens": 48 * 50, "output_tokens": 48 * 8,
            "response_ids_sha256": digest(response_path.read_bytes()),
            "usage_receipts_sha256": digest(usage_path.read_bytes())}
    (directory / "live-result.json").write_bytes(canonical_bytes(live))
    return directory, response_path, digest(receipt_path.read_bytes())


def test_model_wire_contains_no_prior_or_document_identity():
    _packet, _frozen, prepared, _responses = sample("calibration")
    assert len(prepared["requests"]) == 48
    for row in prepared["requests"]:
        assert row["status"] == "callable"
        payload = row["wire"]["user_payload"]
        assert set(payload) == {"question", "candidates"}
        assert payload["question"] == "How is the method explained?"
        assert all(set(candidate) == {"id", "page", "page_text", "cue"}
                   for candidate in payload["candidates"])


def test_heldout_prepare_requires_passing_35_lite_calibration(tmp_path, monkeypatch):
    packet_dir, labels_path, labels_sha, freeze_sha = frozen_public_fixture(
        tmp_path, monkeypatch)
    with pytest.raises(ReviewError, match="calibration_gate_required"):
        prepare(packet_dir, labels_path, labels_sha, freeze_sha,
                "heldout", tmp_path / "heldout")
    calibration_dir, response_path, receipt_sha = stage_complete_run(
        tmp_path, packet_dir, labels_path, labels_sha, freeze_sha, "calibration")
    score_receipt = score_once(calibration_dir, labels_path, labels_sha,
                               freeze_sha, response_path, receipt_sha, packet_dir)
    assert score_receipt["public_passed"] is True
    score_path = calibration_dir / "score-result.json"
    score_receipt["schema"] = "cardchemy_public_source_id_multipdf_36_pilot_v1"
    score_path.write_bytes(canonical_bytes(score_receipt))
    with pytest.raises(ReviewError, match="calibration_gate_failed"):
        prepare(packet_dir, labels_path, labels_sha, freeze_sha,
                "heldout", tmp_path / "heldout", score_path,
                digest(score_path.read_bytes()))
    score_receipt["schema"] = SCHEMA
    score_receipt["public_passed"] = False
    score_path.write_bytes(canonical_bytes(score_receipt))
    with pytest.raises(ReviewError, match="calibration_gate_failed"):
        prepare(packet_dir, labels_path, labels_sha, freeze_sha,
                "heldout", tmp_path / "heldout", score_path,
                digest(score_path.read_bytes()))
    score_receipt["public_passed"] = True
    score_path.write_bytes(canonical_bytes(score_receipt))
    result = prepare(packet_dir, labels_path, labels_sha, freeze_sha,
                     "heldout", tmp_path / "heldout", score_path,
                     digest(score_path.read_bytes()))
    assert result["callable_count"] == 48
    assert result["clarification_count"] == 0


def test_forged_score_top_level_cannot_open_heldout(tmp_path, monkeypatch):
    packet_dir, labels_path, labels_sha, freeze_sha = frozen_public_fixture(
        tmp_path, monkeypatch)
    selected = sample("calibration")[3]
    selected[next(key for key, value in selected.items() if not value)] = ("S04",)
    calibration_dir, response_path, receipt_sha = stage_complete_run(
        tmp_path, packet_dir, labels_path, labels_sha, freeze_sha,
        "calibration", selected)
    result = score_once(calibration_dir, labels_path, labels_sha, freeze_sha,
                        response_path, receipt_sha, packet_dir)
    assert result["public_passed"] is False
    score_path = calibration_dir / "score-result.json"
    result["public_passed"] = True
    score_path.write_bytes(canonical_bytes(result))
    with pytest.raises(ReviewError, match="calibration_gate_failed"):
        prepare(packet_dir, labels_path, labels_sha, freeze_sha,
                "heldout", tmp_path / "heldout", score_path,
                digest(score_path.read_bytes()))
    assert not (tmp_path / "heldout").exists()


def test_perfect_selector_passes_calibration_and_heldout_gates():
    for split in ("calibration", "heldout"):
        _packet, frozen, prepared, responses = sample(split)
        result = score(prepared, frozen, responses)
        assert result["public_passed"] is True
        assert result["counts"]["positive_groups"] == 36
        assert result["counts"]["no_useful_groups"] == 12
        assert result["counts"]["displayed_useful_cues_and_pages"] == 72


def test_weak_card_and_no_useful_display_fail():
    _packet, frozen, prepared, responses = sample("calibration")
    negative = next(row["group_id"] for row in prepared["requests"]
                    if not responses[row["group_id"]])
    responses[negative] = ("S04",)
    result = score(prepared, frozen, responses)
    assert result["counts"]["false_no_useful_displays"] == 1
    assert result["public_passed"] is False


def test_invalid_model_output_is_not_counted_as_good_abstention():
    _packet, frozen, prepared, responses = sample("heldout")
    negative = next(row["group_id"] for row in prepared["requests"]
                    if not responses[row["group_id"]])
    responses[negative] = None
    result = score(prepared, frozen, responses)
    assert result["counts"]["invalid_model_outputs"] == 1
    assert result["counts"]["valid_no_useful_abstentions"] == 11
    assert result["public_passed"] is False


def test_local_clarification_does_not_count_as_model_no_match():
    _packet, frozen, prepared, responses = sample("calibration")
    negative = next(row for row in prepared["requests"]
                    if not responses[row["group_id"]])
    negative.update({"status": "clarification", "wire": None,
                     "wire_sha256": None})
    responses.pop(negative["group_id"])
    result = score(prepared, frozen, responses)
    assert result["counts"]["clarification_no_useful_groups"] == 1
    assert result["counts"]["valid_no_useful_abstentions"] == 11
    assert result["public_passed"] is False


def test_changed_cross_pdf_positive_prevalence_keeps_fractional_gate():
    _packet, frozen, prepared, responses = sample("heldout")
    groups = {item["group_id"]: item for item in frozen["groups"]}
    negatives = [row["group_id"] for row in prepared["requests"]
                 if not responses[row["group_id"]]]
    for group_id in negatives[:4]:
        groups[group_id]["labels"][3]["page_useful"] = True
        groups[group_id]["labels"][3]["cue_useful"] = True
        responses[group_id] = ("S04",)
    result = score(prepared, frozen, responses)
    assert result["counts"]["positive_groups"] == 40
    assert result["counts"]["no_useful_groups"] == 8
    assert result["counts"]["valid_no_useful_abstentions"] == 8
    assert result["public_passed"] is True


def test_scoring_requires_a_complete_claimed_live_run(tmp_path, monkeypatch):
    # Even a score-looking file cannot replace 48 recorded physical calls.
    import evaluate_source_id_multipdf_35_lite as scorer
    packet_dir, labels_path, labels_sha, freeze_sha = frozen_public_fixture(
        tmp_path, monkeypatch)
    directory = tmp_path / "calibration"
    prepare(packet_dir, labels_path, labels_sha, freeze_sha,
            "calibration", directory)
    receipt_path = directory / "prepare-receipt.json"
    with pytest.raises(ReviewError, match="input_invalid"):
        score_once(directory, labels_path, labels_sha, freeze_sha,
                   directory / "response-ids.jsonl",
                   digest(receipt_path.read_bytes()), packet_dir)
    assert not (directory / "score.claim").exists()
    assert not scorer._global_score_claim_path(
        json.loads(receipt_path.read_bytes())["fingerprint"],
        "calibration").exists()


def test_complete_live_result_scores_only_once_across_output_directories(
    tmp_path, monkeypatch,
):
    packet_dir, labels_path, labels_sha, freeze_sha = frozen_public_fixture(
        tmp_path, monkeypatch)
    first, responses, receipt_sha = stage_complete_run(
        tmp_path, packet_dir, labels_path, labels_sha, freeze_sha, "first")
    result = score_once(first, labels_path, labels_sha, freeze_sha,
                        responses, receipt_sha, packet_dir)
    assert result["public_passed"] is True
    second, responses_again, receipt_sha_again = stage_complete_run(
        tmp_path, packet_dir, labels_path, labels_sha, freeze_sha, "second")
    with pytest.raises(FileExistsError):
        score_once(second, labels_path, labels_sha, freeze_sha,
                   responses_again, receipt_sha_again, packet_dir)
    assert not (second / "score.claim").exists()


@pytest.mark.parametrize("removed", ["call-48.claim", "usage-receipts.jsonl",
                                     "response-ids.jsonl"])
def test_missing_one_physical_receipt_cannot_be_scored(
    tmp_path, monkeypatch, removed,
):
    packet_dir, labels_path, labels_sha, freeze_sha = frozen_public_fixture(
        tmp_path, monkeypatch)
    directory, responses, receipt_sha = stage_complete_run(
        tmp_path, packet_dir, labels_path, labels_sha, freeze_sha,
        "calibration")
    (directory / removed).unlink()
    with pytest.raises(ReviewError):
        score_once(directory, labels_path, labels_sha, freeze_sha,
                   responses, receipt_sha, packet_dir)
    assert not (directory / "score.claim").exists()
