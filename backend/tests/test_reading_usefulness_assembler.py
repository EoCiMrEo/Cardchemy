"""Offline assembly contracts; all review evidence here is synthetic test data."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import acquire_reading_usefulness_corpus as corpus
import assemble_reading_usefulness_reviewed_fixture as assembler
import validate_reading_usefulness_fixture as validator

# The source test fixture makes disposable PDFs and independent synthetic
# receipts. Importing its fixtures registers the same corpus-pin overrides.
from test_reading_usefulness_fixture import packet, synthetic_corpus_pins  # noqa: F401


def _save(path: Path, value: dict) -> str:
    raw = corpus.canonical_bytes(value)
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def inputs(packet, tmp_path):
    root, _, fixture = packet
    attestations = {
        "schema": assembler.ATTESTATION_SCHEMA,
        "corpus_id": fixture["corpus_id"],
        "manifest_sha256": fixture["manifest_sha256"],
        "review_protocol": fixture["review_protocol"],
        "document_rights_reviews": fixture["document_rights_reviews"],
        "leakage_reviews": [
            {"group_id": group["id"], **group["leakage_review"]}
            for group in fixture["groups"]
        ],
    }
    attestation_path = tmp_path / "attestations.json"
    attestation_sha = _save(attestation_path, attestations)
    value = {
        "schema": assembler.INPUT_SCHEMA,
        "corpus_root": str(root),
        "manifest_sha256": fixture["manifest_sha256"],
        "plan_sha256": fixture["plan_sha256"],
        "attestations_path": str(attestation_path),
        "attestations_sha256": attestation_sha,
        "batches": copy.deepcopy(fixture["review_evidence"]["batches"]),
    }
    path = tmp_path / "inputs.json"
    return value, path, root, fixture


def _prepare(inputs, tmp_path):
    value, path, _, _ = inputs
    digest = _save(path, value)
    output = tmp_path / "prepared.json"
    result = assembler.prepare(path, digest, output)
    return result, output


def _repin_evidence(batch: dict, field: str, value: dict, tmp_path: Path) -> None:
    path = tmp_path / f"replacement-{field}.json"
    batch[f"{field}_sha256"] = _save(path, value)
    batch[f"{field}_path"] = str(path)


def test_prepare_uses_review_labels_not_author_provisional_labels(inputs, tmp_path):
    baseline, baseline_path = _prepare(inputs, tmp_path)
    baseline_groups = json.loads(baseline_path.read_bytes())["groups"]
    value, path, _, _ = inputs
    batch = value["batches"][0]
    draft = json.loads(Path(batch["author_draft_path"]).read_bytes())
    draft["groups"][0]["original_page_usefulness_per_window"] = [False] * 4
    draft["groups"][0]["exact_cue_usefulness_per_window"] = [False] * 4
    _repin_evidence(batch, "author_draft", draft, tmp_path)
    mapping = json.loads(Path(batch["opaque_mapping_path"]).read_bytes())
    mapping["author_draft_sha256"] = batch["author_draft_sha256"]
    _repin_evidence(batch, "opaque_mapping", mapping, tmp_path)
    changed_path = tmp_path / "changed-inputs.json"
    changed_sha = _save(changed_path, value)
    changed_output = tmp_path / "changed-prepared.json"
    changed = assembler.prepare(changed_path, changed_sha, changed_output)
    assert changed["groups_sha256"] == baseline["groups_sha256"]
    assert json.loads(changed_output.read_bytes())["groups"] == baseline_groups
    assert changed["prepared_sha256"] != baseline["prepared_sha256"]


@pytest.mark.parametrize("review_change", ["uncertain", "disagreement"])
def test_unresolved_review_never_uses_author_label(inputs, tmp_path, review_change):
    value, path, _, _ = inputs
    batch = value["batches"][0]
    second = json.loads(Path(batch["review_b_path"]).read_bytes())
    if review_change == "uncertain":
        second["judgments"][0]["uncertain"] = True
    else:
        second["judgments"][0].update(
            original_page_useful=False, exact_visible_cue_useful=False)
    _repin_evidence(batch, "review_b", second, tmp_path)
    adjudication = json.loads(Path(batch["adjudication_path"]).read_bytes())
    adjudication["review_sha256"] = sorted((batch["review_a_sha256"],
                                             batch["review_b_sha256"]))
    _repin_evidence(batch, "adjudication", adjudication, tmp_path)
    digest = _save(path, value)
    output = tmp_path / "prepared.json"
    with pytest.raises(validator.FixtureError, match="unresolved_review"):
        assembler.prepare(path, digest, output)
    assert not output.exists()


def test_tampered_opaque_mapping_fails_even_when_rehashed(inputs, tmp_path):
    value, path, _, _ = inputs
    batch = value["batches"][0]
    mapping = json.loads(Path(batch["opaque_mapping_path"]).read_bytes())
    first, second = mapping["groups"][0]["candidates"][:2]
    first["author_candidate_index"], second["author_candidate_index"] = (
        second["author_candidate_index"], first["author_candidate_index"])
    _repin_evidence(batch, "opaque_mapping", mapping, tmp_path)
    digest = _save(path, value)
    output = tmp_path / "prepared.json"
    with pytest.raises(validator.FixtureError, match="blind_projection_mismatch"):
        assembler.prepare(path, digest, output)
    assert not output.exists()


def test_prepare_requires_external_rights_attestation(inputs, tmp_path):
    value, path, _, _ = inputs
    attestation = json.loads(Path(value["attestations_path"]).read_bytes())
    attestation["document_rights_reviews"].pop()
    attestation_path = tmp_path / "incomplete-attestation.json"
    value["attestations_path"] = str(attestation_path)
    value["attestations_sha256"] = _save(attestation_path, attestation)
    digest = _save(path, value)
    with pytest.raises(validator.FixtureError, match="document_rights_attestation"):
        assembler.prepare(path, digest, tmp_path / "prepared.json")


def test_reviewed_count_imbalance_stops_prepare_without_author_override(inputs, tmp_path):
    value, path, _, _ = inputs
    batch = value["batches"][0]
    first = json.loads(Path(batch["review_a_path"]).read_bytes())
    second = json.loads(Path(batch["review_b_path"]).read_bytes())
    positive = next(row for row in first["judgments"]
                    if row["exact_visible_cue_useful"])
    for receipt in (first, second):
        row = next(row for row in receipt["judgments"] if row["id"] == positive["id"])
        row["exact_visible_cue_useful"] = False
    _repin_evidence(batch, "review_a", first, tmp_path)
    _repin_evidence(batch, "review_b", second, tmp_path)
    adjudication = json.loads(Path(batch["adjudication_path"]).read_bytes())
    adjudication["review_sha256"] = sorted((batch["review_a_sha256"],
                                             batch["review_b_sha256"]))
    _repin_evidence(batch, "adjudication", adjudication, tmp_path)
    digest = _save(path, value)
    output = tmp_path / "prepared.json"
    with pytest.raises(validator.FixtureError, match="useful_count_strata"):
        assembler.prepare(path, digest, output)
    assert not output.exists()


def test_finalize_requires_external_receipts_and_validates_before_publish(inputs, tmp_path):
    result, prepared_path = _prepare(inputs, tmp_path)
    _, _, root, fixture = inputs
    refs = fixture["review_evidence"]
    output = tmp_path / "reviewed-fixture.json"
    with pytest.raises(validator.FixtureError, match="external_groups_hash"):
        semantic = json.loads(Path(refs["semantic_leakage_audit_path"]).read_bytes())
        wrong_path = tmp_path / "wrong-semantic.json"
        semantic["groups_sha256"] = "0" * 64
        wrong_sha = _save(wrong_path, semantic)
        assembler.finalize(prepared_path, result["prepared_sha256"],
                           wrong_path, wrong_sha,
                           Path(refs["rights_audit_path"]), refs["rights_audit_sha256"],
                           output)
    assert not output.exists()
    assert result["groups_sha256"] == hashlib.sha256(
        corpus.canonical_bytes(fixture["groups"])).hexdigest()
    finalized = assembler.finalize(
        prepared_path, result["prepared_sha256"],
        Path(refs["semantic_leakage_audit_path"]), refs["semantic_leakage_audit_sha256"],
        Path(refs["rights_audit_path"]), refs["rights_audit_sha256"], output)
    assert finalized["status"] == "reviewed_fixture_validated_no_scoring"
    assert validator.validate(root, output)["fixture_sha256"] == finalized["fixture_sha256"]
    with pytest.raises(validator.FixtureError, match="output_exists"):
        assembler.finalize(
            prepared_path, result["prepared_sha256"],
            Path(refs["semantic_leakage_audit_path"]), refs["semantic_leakage_audit_sha256"],
            Path(refs["rights_audit_path"]), refs["rights_audit_sha256"], output)


def test_prepared_group_tamper_cannot_be_rehashed_into_a_fixture(inputs, tmp_path):
    _, prepared_path = _prepare(inputs, tmp_path)
    _, _, _, fixture = inputs
    prepared = json.loads(prepared_path.read_bytes())
    current = prepared["groups"][0]["exact_cue_usefulness_per_window"][0]
    prepared["groups"][0]["exact_cue_usefulness_per_window"][0] = not current
    tampered_path = tmp_path / "tampered-prepared.json"
    tampered_sha = _save(tampered_path, prepared)
    refs = fixture["review_evidence"]
    with pytest.raises(validator.FixtureError, match="prepared_reassembly_mismatch"):
        assembler.finalize(
            tampered_path, tampered_sha,
            Path(refs["semantic_leakage_audit_path"]), refs["semantic_leakage_audit_sha256"],
            Path(refs["rights_audit_path"]), refs["rights_audit_sha256"],
            tmp_path / "should-not-exist.json")
