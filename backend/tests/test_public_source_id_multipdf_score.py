"""Keyless public multi-PDF scorer gates and provider-wire boundaries."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from evaluate_source_id_multipdf import (  # noqa: E402
    LABEL_SCHEMA, PACKET_SCHEMA, PACKET_SHA256, SCHEMA, _split_requests,
    _fingerprint, score, score_once,
)
from finalize_public_source_id_multipdf import ReviewError  # noqa: E402
from prepare_public_source_id_multipdf import canonical_bytes  # noqa: E402
import hashlib
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


def test_scoring_requires_a_complete_claimed_live_run(tmp_path):
    _packet, frozen, prepared, _responses = sample("calibration")
    labels_path = tmp_path / "frozen-labels.json"
    labels_path.write_bytes(canonical_bytes(frozen))
    labels_sha = hashlib.sha256(labels_path.read_bytes()).hexdigest()
    freeze_sha = "a" * 64
    fingerprint = _fingerprint(PACKET_SHA256, labels_sha, freeze_sha)
    prepared.update({"fingerprint": fingerprint, "labels_sha256": labels_sha,
                     "freeze_receipt_sha256": freeze_sha})
    packet_path = tmp_path / "requests.json"
    packet_path.write_bytes(canonical_bytes(prepared))
    receipt = {"requests_sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
               "fingerprint": fingerprint, "labels_sha256": labels_sha,
               "freeze_receipt_sha256": freeze_sha, "callable_count": 48}
    receipt_path = tmp_path / "prepare-receipt.json"
    receipt_path.write_bytes(canonical_bytes(receipt))
    with pytest.raises(ReviewError, match="live_run_incomplete"):
        score_once(tmp_path, labels_path, labels_sha, freeze_sha,
                   tmp_path / "response-ids.jsonl",
                   hashlib.sha256(receipt_path.read_bytes()).hexdigest())
    assert not (tmp_path / "score.claim").exists()


def test_complete_live_result_scores_only_once_across_output_directories(
    tmp_path, monkeypatch,
):
    import json
    import evaluate_source_id_multipdf as scorer

    monkeypatch.setattr(scorer, "gettempdir", lambda: str(tmp_path))
    _packet, frozen, prepared, selected = sample("calibration")
    labels_path = tmp_path / "frozen-labels.json"
    labels_path.write_bytes(canonical_bytes(frozen))
    labels_sha = hashlib.sha256(labels_path.read_bytes()).hexdigest()
    freeze_sha = "a" * 64
    fingerprint = _fingerprint(PACKET_SHA256, labels_sha, freeze_sha)
    prepared.update({"fingerprint": fingerprint, "labels_sha256": labels_sha,
                     "freeze_receipt_sha256": freeze_sha})

    def stage(directory):
        directory.mkdir()
        requests_path = directory / "requests.json"
        requests_path.write_bytes(canonical_bytes(prepared))
        requests_sha = hashlib.sha256(requests_path.read_bytes()).hexdigest()
        receipt = {"requests_sha256": requests_sha,
                   "fingerprint": fingerprint, "labels_sha256": labels_sha,
                   "freeze_receipt_sha256": freeze_sha, "callable_count": 48}
        receipt_path = directory / "prepare-receipt.json"
        receipt_path.write_bytes(canonical_bytes(receipt))
        responses_path = directory / "response-ids.jsonl"
        with responses_path.open("wb") as stream:
            for row in prepared["requests"]:
                stream.write(canonical_bytes({
                    "group_id": row["group_id"],
                    "wire_sha256": row["wire_sha256"],
                    "raw_json": json.dumps({"selected_ids": selected[row["group_id"]]}),
                }))
        usage_path = directory / "usage-receipts.jsonl"
        usage_path.write_bytes(b"\n")
        live = {"status": "complete_one_shot", "split": "calibration",
                "fingerprint": fingerprint, "requests_sha256": requests_sha,
                "attempts": 48, "known_cost_microusd": 0,
                "response_ids_sha256": hashlib.sha256(responses_path.read_bytes()).hexdigest(),
                "usage_receipts_sha256": hashlib.sha256(usage_path.read_bytes()).hexdigest()}
        (directory / "live-result.json").write_bytes(canonical_bytes(live))
        return responses_path, hashlib.sha256(receipt_path.read_bytes()).hexdigest()

    first = tmp_path / "first"
    second = tmp_path / "second"
    responses, receipt_sha = stage(first)
    result = score_once(first, labels_path, labels_sha, freeze_sha,
                        responses, receipt_sha)
    assert result["public_passed"] is True
    responses_again, receipt_sha_again = stage(second)
    with pytest.raises(FileExistsError):
        score_once(second, labels_path, labels_sha, freeze_sha,
                   responses_again, receipt_sha_again)
    assert not (second / "score.claim").exists()
