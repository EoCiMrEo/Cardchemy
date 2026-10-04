"""Keyless checks for immutable original-plus-reserve public packet admission."""

from __future__ import annotations

import copy
from pathlib import Path
import sys

import pytest


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import prepare_fresh_public_source_id_v2 as base  # noqa: E402
import prepare_fresh_public_source_id_v2_augmented as augmented_freezer  # noqa: E402
from test_prepare_fresh_public_source_id_v2 import example_inputs  # noqa: E402
from test_review_fresh_public_source_id_v2 import reserve_packet  # noqa: E402


def reserve_bundle(inputs: tuple) -> tuple:
    _, original, _, _, _, _, documents, manifest_sha, overlap_sha = inputs
    groups = []
    review_groups = []
    for split in base.SPLITS:
        docs = [row["document_id"] for row in documents if row["split"] == split]
        count = 6 if split == "calibration" else 4
        for form in base.FORMS[:3]:
            for index in range(count):
                gid = f"reserve-{split}-{form}-{index:02d}"
                candidates = [{"id": f"P{number + 1}", "document_id": docs[number // 2],
                               "page": number % 2 + 1, "context_start": 0,
                               "context_end": 100, "cue_start": 20, "cue_end": 60}
                              for number in range(4)]
                # The first reserve group intentionally has zero useful cards;
                # it stays admitted as a no-useful control despite its form.
                useful = (0 if index == 0 else
                          4 if split == "calibration" and
                          form in {"direct", "paraphrase"} and index == 1 else 3)
                review_groups.append({"group_id": gid, "candidates": [
                    {"id": f"P{number + 1}", "page_useful": number < useful,
                     "cue_useful": number < useful} for number in range(4)]})
                groups.append({"group_id": gid, "split": split, "form": form,
                               "question": f"Where is reserve concept {gid} discussed?",
                               "candidates": candidates})
    reserve = {"schema_version": "fresh_public_source_id_v2_reserve_authored",
               "corpus_id": base.CORPUS_ID, "source_manifest_sha256": manifest_sha,
               "overlap_review_sha256": overlap_sha,
               "author_id": "reserve_author_agent", "groups": groups}
    review_a = {"schema_version": base.REVIEW_SCHEMA,
                "reviewer_id": "reserve_reviewer_a", "groups": review_groups}
    review_b = copy.deepcopy(review_a)
    review_b["reviewer_id"] = "reserve_reviewer_b"
    adjudication = {"schema_version": base.ADJUDICATION_SCHEMA,
                    "reviewer_id": "reserve_adjudicator", "decisions": []}
    assert original["author_id"] != reserve["author_id"]
    return reserve, review_a, review_b, adjudication


def augmented(inputs: tuple, reserve: tuple | None = None) -> dict:
    return base.build_artifacts(*inputs, reserve_bundle=reserve or reserve_bundle(inputs))


def test_augmented_preserves_all_original_ids_and_all_reserve_groups():
    inputs = example_inputs()
    original = base.build_artifacts(*inputs)
    result = augmented(inputs)
    for split, count in (("calibration", 66), ("heldout", 60)):
        old_labels = original[f"{split}/labels.json"]["groups"]
        packet = result[f"{split}/packet.json"]
        labels = result[f"{split}/labels.json"]
        assert packet["schema_version"] == "fresh_public_source_id_v2_augmented_packet"
        assert labels["schema_version"] == "fresh_public_source_id_v2_augmented_labels"
        assert len(packet["groups"]) == len(labels["groups"]) == count
        assert [row["author_group_id"] for row in labels["groups"][:48]] == [
            row["author_group_id"] for row in old_labels]
        assert [row["group_id"] for row in labels["groups"]] == [
            f"G{index:03d}" for index in range(1, count + 1)]
        assert {row["origin"] for row in labels["groups"][:48]} == {"original"}
        assert {row["origin"] for row in labels["groups"][48:]} == {"reserve"}
        assert labels["packet_sha256"] == base.sha256_bytes(base.canonical_bytes(packet))
        assert "page_useful" not in base.canonical_bytes(packet).decode("utf-8")
        assert any(row["form"] == "direct" and not any(
            card["page_useful"] and card["cue_useful"] for card in row["candidates"])
            for row in labels["groups"][48:])


def test_augmented_rejects_missing_stratum_without_dropping_hard_cases():
    inputs = list(example_inputs())
    # Reduce every reserve group to a single useful card. Move one original
    # calibration three-useful group to one-useful, leaving only eleven threes.
    reserve = list(reserve_bundle(tuple(inputs)))
    for review in reserve[1:3]:
        for group in review["groups"]:
            for card in group["candidates"][1:]:
                card["page_useful"] = card["cue_useful"] = False
    target_gid = next(row["group_id"] for row in inputs[1]["groups"]
                      if row["split"] == "calibration" and row["form"] == "direct"
                      and row["group_id"].endswith("02"))
    for review in inputs[2:4]:
        target = next(row for row in review["groups"] if row["group_id"] == target_gid)
        for card in target["candidates"][1:]:
            card["page_useful"] = card["cue_useful"] = False
    with pytest.raises(base.FreezeError, match="at least twelve"):
        augmented(tuple(inputs), tuple(reserve))


def test_augmented_rejects_duplicate_original_and_reserve_question():
    inputs = example_inputs()
    reserve = list(reserve_bundle(inputs))
    reserve[0]["groups"][0]["question"] = inputs[1]["groups"][0]["question"]
    with pytest.raises(base.FreezeError, match="duplicate question"):
        augmented(inputs, tuple(reserve))


def test_augmented_keeps_exact_two_reviewed_overflow_groups():
    inputs = example_inputs()
    result = augmented(inputs)
    calibration = result["calibration/labels.json"]["groups"]
    overflow = [row for row in calibration if row["origin"] == "reserve" and
                sum(card["page_useful"] and card["cue_useful"]
                    for card in row["candidates"]) == 4]
    assert len(overflow) == 2
    reserve = list(reserve_bundle(inputs))
    target_gid = next(row["group_id"] for row in reserve[0]["groups"]
                      if row["split"] == "calibration" and row["form"] == "direct"
                      and row["group_id"].endswith("01"))
    for review in reserve[1:3]:
        target = next(row for row in review["groups"] if row["group_id"] == target_gid)
        target["candidates"][3]["page_useful"] = False
        target["candidates"][3]["cue_useful"] = False
    with pytest.raises(base.FreezeError, match="overflow roster changed"):
        augmented(inputs, tuple(reserve))


def test_reserve_blind_bytes_are_rechecked_against_authored_pdf_offsets(tmp_path):
    inputs, packet, mapping = reserve_packet(tmp_path)
    for did in base.EXPECTED:
        (tmp_path / f"{did}.pdf").write_bytes(b"synthetic path only")
    manifest_path = tmp_path / "manifest.json"
    augmented_freezer._reserve_blind_matches_authored(
        authored=inputs[1], packet=packet, mapping=mapping, pages=inputs[5],
        documents=inputs[6], manifest_path=manifest_path)
    changed = copy.deepcopy(packet)
    changed["groups"][0]["candidates"][0]["cue"] = "same topic but wrong cue"
    with pytest.raises(base.FreezeError, match="source/offset mismatch"):
        augmented_freezer._reserve_blind_matches_authored(
            authored=inputs[1], packet=changed, mapping=mapping,
            pages=inputs[5], documents=inputs[6], manifest_path=manifest_path)
