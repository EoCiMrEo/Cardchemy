"""Keyless reviewer handoff tests for the fresh public page-and-cue pilot."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from test_prepare_fresh_public_source_id_v2 import example_inputs, freeze


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "review_fresh_public_source_id_v2.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("review_fresh_public_source_id_v2", SCRIPT)
assert SPEC and SPEC.loader
reviewer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reviewer)


def sample_packet(tmp_path):
    inputs = example_inputs()
    paths = {document_id: tmp_path / f"{document_id}.pdf" for document_id in freeze.EXPECTED}
    packet, mapping = reviewer.build_blind_packet(
        inputs[1], inputs[5], inputs[6], inputs[7], inputs[8], set(), paths,
        salt="1" * 64)
    return inputs, packet, mapping


def reserve_inputs():
    inputs = list(example_inputs())
    allowed = {"direct", "paraphrase", "followup"}
    keep = {group["group_id"] for group in inputs[1]["groups"]
            if group["form"] in allowed and int(group["group_id"].rsplit("-", 1)[1]) <
            (6 if group["split"] == "calibration" else 4)}
    inputs[1]["schema_version"] = reviewer.RESERVE_AUTHORED_SCHEMA
    inputs[1]["groups"] = [group for group in inputs[1]["groups"]
                            if group["group_id"] in keep]
    for review in inputs[2:4]:
        review["groups"] = [group for group in review["groups"]
                            if group["group_id"] in keep]
    assert len(inputs[1]["groups"]) == 30
    return inputs


def reserve_packet(tmp_path):
    inputs = reserve_inputs()
    paths = {document_id: tmp_path / f"{document_id}.pdf" for document_id in freeze.EXPECTED}
    packet, mapping = reviewer.build_blind_packet(
        inputs[1], inputs[5], inputs[6], inputs[7], inputs[8], set(), paths,
        salt="1" * 64, reserve=True)
    return inputs, packet, mapping


def answer(packet, mapping, original_review):
    source = {group["group_id"]: {row["id"]: row for row in group["candidates"]}
              for group in original_review["groups"]}
    mapping_groups = {group["group_id"]: group for group in mapping["groups"]}
    groups = []
    for group in packet["groups"]:
        linked = mapping_groups[group["group_id"]]
        id_map = {row["id"]: row["author_id"] for row in linked["candidates"]}
        groups.append({"group_id": group["group_id"], "candidates": [
            {"id": row["id"],
             "page_useful": source[linked["author_group_id"]][id_map[row["id"]]]["page_useful"],
             "cue_useful": source[linked["author_group_id"]][id_map[row["id"]]]["cue_useful"]}
            for row in group["candidates"]]})
    return {"schema_version": reviewer.RESPONSE_SCHEMA,
            "reviewer_id": original_review["reviewer_id"],
            "packet_sha256": mapping["packet_sha256"], "groups": groups}


def test_blind_packet_omits_forms_and_author_ids_and_links_original_pdf(tmp_path):
    inputs, packet, mapping = sample_packet(tmp_path)
    assert "profile" not in packet and "profile" not in mapping
    assert len(packet["groups"]) == len(mapping["groups"]) == 96
    assert sum(len(group["candidates"]) for group in packet["groups"]) == 384
    serialized = freeze.canonical_bytes(packet).decode("utf-8")
    assert "author_id" not in serialized
    assert "no_useful" not in serialized
    assert "page_useful" not in serialized
    assert all("form" not in group and "split" not in group
               for group in packet["groups"])
    assert mapping["author_id"] == inputs[1]["author_id"]
    template = reviewer.blank_review_template(packet, mapping["packet_sha256"])
    assert template["reviewer_id"] is None
    assert all(row["page_useful"] is None and row["cue_useful"] is None
               for group in template["groups"] for row in group["candidates"])
    for group in packet["groups"]:
        for row in group["candidates"]:
            assert row["pdf_uri"].endswith(f"#page={row['page']}")
            assert len(row["document_sha256"]) == 64
            assert row["cue"] in row["context"]


def test_two_independent_blind_reviews_bridge_to_freezer(tmp_path):
    inputs, packet, mapping = sample_packet(tmp_path)
    a, b = answer(packet, mapping, inputs[2]), answer(packet, mapping, inputs[3])
    original_a, original_b, disputes = reviewer.bridge_reviews(packet, mapping, a, b)
    assert original_a["reviewer_id"] == "reviewer_a"
    assert original_b["reviewer_id"] == "reviewer_b"
    assert disputes["groups"] == []
    artifacts = freeze.build_artifacts(inputs[0], inputs[1], original_a, original_b,
                                       inputs[4], inputs[5], inputs[6], inputs[7], inputs[8])
    assert len(artifacts["calibration/packet.json"]["groups"]) == 48
    assert len(artifacts["heldout/packet.json"]["groups"]) == 48


def test_disagreements_only_and_independent_adjudication(tmp_path):
    inputs, packet, mapping = sample_packet(tmp_path)
    a, b = answer(packet, mapping, inputs[2]), answer(packet, mapping, inputs[3])
    target = next(row for group in b["groups"] for row in group["candidates"]
                  if row["page_useful"])
    target["cue_useful"] = False
    original_a, original_b, disputes = reviewer.bridge_reviews(packet, mapping, a, b)
    assert sum(len(group["candidates"]) for group in disputes["groups"]) == 1
    group = disputes["groups"][0]
    cid = group["candidates"][0]["id"]
    decision = {"schema_version": reviewer.ADJUDICATION_RESPONSE_SCHEMA,
                "reviewer_id": "reviewer_c", "packet_sha256": mapping["packet_sha256"],
                "decisions": [{"group_id": group["group_id"], "id": cid,
                               "page_useful": True, "cue_useful": True}]}
    adjudication = reviewer.bridge_adjudication(packet, mapping, a, b, decision)
    assert len(adjudication["decisions"]) == 1
    freeze.build_artifacts(inputs[0], inputs[1], original_a, original_b,
                           adjudication, inputs[5], inputs[6], inputs[7], inputs[8])
    decision["reviewer_id"] = "reviewer_a"
    with pytest.raises(reviewer.freezer.FreezeError, match="independent"):
        reviewer.bridge_adjudication(packet, mapping, a, b, decision)


def test_identity_and_label_fail_closed(tmp_path):
    inputs, packet, mapping = sample_packet(tmp_path)
    a, b = answer(packet, mapping, inputs[2]), answer(packet, mapping, inputs[3])
    changed = copy.deepcopy(packet)
    changed["groups"][0]["question"] = "Changed question"
    with pytest.raises(reviewer.freezer.FreezeError, match="mismatch"):
        reviewer.bridge_reviews(changed, mapping, a, b)
    changed_mapping = copy.deepcopy(mapping)
    changed_mapping["groups"][0]["candidates"][0]["author_id"] = "tampered"
    with pytest.raises(reviewer.freezer.FreezeError, match="mismatch"):
        reviewer.bridge_reviews(packet, changed_mapping, a, b)
    invalid = copy.deepcopy(a)
    invalid["groups"][0]["candidates"][0]["cue_useful"] = True
    invalid["groups"][0]["candidates"][0]["page_useful"] = False
    with pytest.raises(reviewer.freezer.FreezeError, match="invalid"):
        reviewer.bridge_reviews(packet, mapping, invalid, b)
    invalid = copy.deepcopy(a)
    invalid["reviewer_id"] = inputs[1]["author_id"]
    with pytest.raises(reviewer.freezer.FreezeError, match="author cannot review"):
        reviewer.bridge_reviews(packet, mapping, invalid, b)
    with pytest.raises(reviewer.freezer.FreezeError, match="overlaps prior corpus"):
        reviewer.build_blind_packet(inputs[1], inputs[5], inputs[6], inputs[7],
                                    inputs[8], {("lec04", 1)},
                                    {did: tmp_path / f"{did}.pdf" for did in freeze.EXPECTED},
                                    salt="1" * 64)


def test_reserve_packet_is_separate_blind_profile_with_exact_balance(tmp_path):
    inputs, packet, mapping = reserve_packet(tmp_path)
    assert packet["profile"] == mapping["profile"] == reviewer.RESERVE_PROFILE
    assert len(packet["groups"]) == len(mapping["groups"]) == 30
    assert sum(len(group["candidates"]) for group in packet["groups"]) == 120
    authored_by_id = {group["group_id"]: group for group in inputs[1]["groups"]}
    strata = {}
    for group in mapping["groups"]:
        authored = authored_by_id[group["author_group_id"]]
        key = authored["split"], authored["form"]
        strata[key] = strata.get(key, 0) + 1
    assert strata == {(split, form): count
                      for split, count in (("calibration", 6), ("heldout", 4))
                      for form in reviewer.RESERVE_FORMS}
    serialized = freeze.canonical_bytes(packet).decode("utf-8")
    assert "author_id" not in serialized and "no_useful" not in serialized
    assert "page_useful" not in serialized and "cue_useful" not in serialized
    assert all("form" not in group and "split" not in group for group in packet["groups"])
    assert all(row["pdf_uri"].endswith(f"#page={row['page']}")
               for group in packet["groups"] for row in group["candidates"])


@pytest.mark.parametrize("edit,match", [
    (lambda inputs: inputs[1].update(schema_version=freeze.AUTHORED_SCHEMA), "identity"),
    (lambda inputs: inputs[1]["groups"].pop(), "30 groups"),
    (lambda inputs: inputs[1]["groups"][0].update(form="no_useful"), "invalid"),
    (lambda inputs: inputs[1]["groups"][0].update(form="paraphrase"), "balance"),
    (lambda inputs: inputs[1]["groups"][0]["candidates"][3].update(document_id="lec06"),
     "two PDFs"),
    (lambda inputs: inputs[1]["groups"][0]["candidates"][0].update(cue_end=1300),
     "offsets"),
])
def test_reserve_rejects_wrong_schema_shape_and_source_rules(tmp_path, edit, match):
    inputs = reserve_inputs()
    edit(inputs)
    with pytest.raises(reviewer.freezer.FreezeError, match=match):
        reviewer.build_blind_packet(
            inputs[1], inputs[5], inputs[6], inputs[7], inputs[8], set(),
            {did: tmp_path / f"{did}.pdf" for did in freeze.EXPECTED},
            salt="1" * 64, reserve=True)


def test_reserve_review_and_adjudication_restore_author_ids(tmp_path):
    inputs, packet, mapping = reserve_packet(tmp_path)
    a, b = answer(packet, mapping, inputs[2]), answer(packet, mapping, inputs[3])
    target = next(row for group in b["groups"] for row in group["candidates"]
                  if row["page_useful"])
    target["cue_useful"] = False
    original_a, original_b, disputes = reviewer.bridge_reviews(packet, mapping, a, b)
    assert len(original_a["groups"]) == len(original_b["groups"]) == 30
    assert {group["group_id"] for group in original_a["groups"]} == {
        group["group_id"] for group in inputs[1]["groups"]}
    assert original_a["schema_version"] == original_b["schema_version"] == freeze.REVIEW_SCHEMA
    assert sum(len(group["candidates"]) for group in disputes["groups"]) == 1
    disputed = disputes["groups"][0]
    decision = {"schema_version": reviewer.ADJUDICATION_RESPONSE_SCHEMA,
                "reviewer_id": "reviewer_c", "packet_sha256": mapping["packet_sha256"],
                "decisions": [{"group_id": disputed["group_id"],
                               "id": disputed["candidates"][0]["id"],
                               "page_useful": True, "cue_useful": True}]}
    original = reviewer.bridge_adjudication(packet, mapping, a, b, decision)
    assert original["schema_version"] == freeze.ADJUDICATION_SCHEMA
    assert original["decisions"][0]["group_id"] in {
        group["group_id"] for group in inputs[1]["groups"]}
    assert original["decisions"][0]["id"] in {"P1", "P2", "P3", "P4"}


def test_reserve_bridge_requires_profile_and_exact_roster(tmp_path):
    inputs, packet, mapping = reserve_packet(tmp_path)
    a, b = answer(packet, mapping, inputs[2]), answer(packet, mapping, inputs[3])
    for edit in (
        lambda p, m: p.pop("profile"),
        lambda p, m: m.pop("profile"),
        lambda p, m: p.update(profile="main_v1"),
        lambda p, m: m.update(profile="main_v1"),
    ):
        changed_packet, changed_mapping = copy.deepcopy(packet), copy.deepcopy(mapping)
        edit(changed_packet, changed_mapping)
        with pytest.raises(reviewer.freezer.FreezeError, match="profile"):
            reviewer.bridge_reviews(changed_packet, changed_mapping, a, b)
    changed_packet, changed_mapping = copy.deepcopy(packet), copy.deepcopy(mapping)
    changed_packet["groups"].pop()
    changed_mapping["groups"].pop()
    changed_packet["mapping_sha256"] = freeze.sha256_bytes(freeze.canonical_bytes(
        {key: value for key, value in changed_mapping.items() if key != "packet_sha256"}))
    changed_mapping["packet_sha256"] = freeze.sha256_bytes(freeze.canonical_bytes(changed_packet))
    with pytest.raises(reviewer.freezer.FreezeError, match="roster"):
        reviewer.bridge_reviews(changed_packet, changed_mapping, a, b)
    changed_packet, changed_mapping = copy.deepcopy(packet), copy.deepcopy(mapping)
    extra = copy.deepcopy(changed_packet["groups"][0]["candidates"][0])
    extra["id"] = "S05"
    changed_packet["groups"][0]["candidates"].append(extra)
    changed_mapping["groups"][0]["candidates"].append({"id": "S05", "author_id": "P5"})
    changed_packet["mapping_sha256"] = freeze.sha256_bytes(freeze.canonical_bytes(
        {key: value for key, value in changed_mapping.items() if key != "packet_sha256"}))
    changed_mapping["packet_sha256"] = freeze.sha256_bytes(freeze.canonical_bytes(changed_packet))
    with pytest.raises(reviewer.freezer.FreezeError, match="four candidates"):
        reviewer.bridge_reviews(changed_packet, changed_mapping, a, b)
    incomplete = copy.deepcopy(a)
    incomplete["groups"].pop()
    with pytest.raises(reviewer.freezer.FreezeError, match="30 groups"):
        reviewer.bridge_reviews(packet, mapping, incomplete, b)


def test_prepare_reserve_cli_writes_profiled_packet(tmp_path, monkeypatch, capsys):
    inputs = reserve_inputs()
    manifest = {**inputs[0], "documents": [
        {"path": f"{did}.pdf"} for did in freeze.EXPECTED]}
    diagnostic = {"per_new_document": [
        {"document_id": did, "excluded_pages": []} for did in freeze.EXPECTED]}
    values = {"manifest.json": (manifest, inputs[7]),
              "authored.json": (inputs[1], "b" * 64),
              "overlap-diagnostic.json": (diagnostic, "d" * 64),
              "overlap-review.json": ({}, inputs[8])}
    monkeypatch.setattr(reviewer.freezer, "read_json", lambda path: values[path.name])
    monkeypatch.setattr(reviewer.freezer, "validate_overlap_gate", lambda *args: None)
    monkeypatch.setattr(reviewer.freezer, "load_verified_pages", lambda *args: (inputs[5], inputs[6]))
    monkeypatch.setattr(reviewer.freezer, "_verified_child", lambda parent, name: tmp_path / name)
    monkeypatch.setattr(reviewer.tempfile, "mkdtemp", lambda prefix: str(tmp_path / prefix))
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "prepare", "--reserve",
                                  "--manifest", "manifest.json", "--authored", "authored.json",
                                  "--overlap-diagnostic", "overlap-diagnostic.json",
                                  "--overlap-review", "overlap-review.json"])
    reviewer.main()
    output = json.loads(capsys.readouterr().out)
    packet = json.loads(Path(output["blind_packet"]).read_text(encoding="utf-8"))
    mapping = json.loads(Path(output["mapping"]).read_text(encoding="utf-8"))
    assert packet["profile"] == mapping["profile"] == reviewer.RESERVE_PROFILE
    assert len(packet["groups"]) == 30
