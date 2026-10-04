"""Synthetic, offline admission contracts for the 192-group public fixture."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

from pypdf import PdfReader, PdfWriter
import pypdf
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import acquire_reading_usefulness_corpus as corpus
import derive_reading_usefulness_corpus_v4 as derived
import build_reading_usefulness_source_inventory as inventory
import validate_reading_usefulness_fixture as validator


@pytest.mark.parametrize(("value", "accepted"), [
    ("Lecture definition\n", True),
    ("  ", False),
    ("\n", False),
    ("x" * 481, False),
    ("term\x00definition", False),
])
def test_exact_source_window_keeps_literal_pdf_newline(value, accepted):
    assert validator.exact_window_field(value) is accepted


def _write(path: Path, value: dict) -> bytes:
    raw = corpus.canonical_bytes(value)
    path.write_bytes(raw)
    return raw


def _pdf(path: Path, name: str) -> tuple[bytes, list[str]]:
    writer = PdfWriter()
    font = writer._add_object(DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    }))
    for page_number in range(1, 5):
        page = writer.add_blank_page(width=2000, height=800)
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        notice = "CC BY 4.0. " if page_number == 1 else ""
        text = (f"{notice}Window {name} page {page_number}: public lecture relation detail. "
                + f"Public source {name} page {page_number} explanatory body. " * 9)
        content = DecodedStreamObject()
        content.set_data(f"BT /F1 10 Tf 20 700 Td ({text}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(content)
    with path.open("wb") as stream:
        writer.write(stream)
    raw = path.read_bytes()
    texts = [(page.extract_text() or "") for page in PdfReader(path).pages]
    return raw, texts


def _review_evidence(root: Path, fixture: dict, docs: list[dict]) -> dict:
    by_sha = {doc["sha256"]: doc for doc in docs}
    groups = fixture["groups"]
    batches = []
    for scope in ("train", "evaluation"):
        selected = [group for group in groups if
                    (group["split"] == "train") == (scope == "train")]
        packet_groups, mappings, reviews_a, reviews_b = [], [], [], []
        for number, group in enumerate(selected):
            gid = f"g_{number:024x}"
            candidates, mapped = [], []
            for index, (window, offset) in enumerate(zip(
                    group["four_exact_candidate_windows"],
                    group["page_number_and_text_offsets_for_each_window"], strict=True)):
                cid = f"c_{number * 4 + index:024x}"
                candidates.append({"id": cid, "exact_window": window,
                                   "source_offset": offset})
                mapped.append({"opaque_candidate_id": cid,
                               "author_candidate_index": index})
                for reviewer, rows in (("reviewer-a", reviews_a),
                                       ("reviewer-b", reviews_b)):
                    rows.append({"id": cid, "group_id": gid,
                                 "source_pdf": by_sha[group["source_document_sha256"]]["path"],
                                 "page_number": offset["page_number"],
                                 "original_page_useful":
                                 group["original_page_usefulness_per_window"][index],
                                 "exact_visible_cue_useful":
                                 group["exact_cue_usefulness_per_window"][index],
                                 "uncertain": False, "reason": "independent page and cue review"})
            packet_groups.append({"id": gid, "relation_family": group["relation_family"],
                "question_form": group["question_form"], "question": group["question"],
                "prior_question_context_if_followup": group["prior_question_context_if_followup"],
                "source_document_sha256": group["source_document_sha256"],
                "source_document_path_author_aid":
                by_sha[group["source_document_sha256"]]["path"],
                "candidates": candidates})
            mappings.append({"opaque_group_id": gid, "author_group_id": group["id"],
                             "split": group["split"], "candidates": mapped})
        draft_path = root / f"{scope}-draft.json"
        authored_groups = []
        for group in selected:
            authored = copy.deepcopy(group)
            authored["source_document_path_author_aid"] = by_sha[
                group["source_document_sha256"]]["path"]
            authored_groups.append(authored)
        draft_sha = hashlib.sha256(_write(draft_path, {
            "status": "author_only_pending_independent_blind_review_and_adjudication_no_model_score",
            "corpus_id": fixture["corpus_id"],
            "manifest_sha256": fixture["manifest_sha256"],
            "groups": authored_groups})).hexdigest()
        blind_path = root / f"{scope}-blind.json"
        blind_sha = hashlib.sha256(_write(blind_path, {
            "schema": "cardchemy_reading_usefulness_blind_review_v2",
            "corpus_id": fixture["corpus_id"],
            "manifest_sha256": fixture["manifest_sha256"],
            "groups": packet_groups, "review_instruction": "independent synthetic review"})).hexdigest()
        mapping_path = root / f"{scope}-mapping.json"
        mapping_sha = hashlib.sha256(_write(mapping_path, {
            "schema": "cardchemy_reading_usefulness_blind_mapping_v1",
            "author_draft_sha256": draft_sha, "blind_packet_sha256": blind_sha,
            "groups": mappings})).hexdigest()
        review_refs = {}
        review_shas = []
        for label, reviewer, rows in (("a", "reviewer-a", reviews_a),
                                      ("b", "reviewer-b", reviews_b)):
            path = root / f"{scope}-review-{label}.json"
            sha = hashlib.sha256(_write(path, {"reviewer_id": reviewer,
                "packet_sha256": blind_sha, "reviewed_group_count": 96,
                "reviewed_candidate_count": 384, "judgments": rows})).hexdigest()
            review_refs[f"review_{label}_path"] = str(path)
            review_refs[f"review_{label}_sha256"] = sha
            review_shas.append(sha)
        adjudication_path = root / f"{scope}-adjudication.json"
        adjudication_sha = hashlib.sha256(_write(adjudication_path, {
            "schema": "cardchemy_reading_usefulness_adjudication_v1",
            "blind_packet_sha256": blind_sha, "review_sha256": sorted(review_shas),
            "rows": []})).hexdigest()
        batches.append({"scope": scope,
            "author_draft_path": str(draft_path), "author_draft_sha256": draft_sha,
            "blind_packet_path": str(blind_path), "blind_packet_sha256": blind_sha,
            "opaque_mapping_path": str(mapping_path), "opaque_mapping_sha256": mapping_sha,
            **review_refs, "adjudication_path": str(adjudication_path),
            "adjudication_sha256": adjudication_sha})
    groups_sha = hashlib.sha256(corpus.canonical_bytes(groups)).hexdigest()
    doc_pairs = sorted([left["sha256"], right["sha256"]] for left in docs for right in docs
                       if left["sha256"] < right["sha256"] and
                       left["split"] != right["split"])
    semantic_path = root / "semantic-leakage-audit.json"
    semantic_sha = hashlib.sha256(_write(semantic_path, {
        "schema": "cardchemy_reading_usefulness_semantic_leakage_audit_v1",
        "manifest_sha256": fixture["manifest_sha256"], "groups_sha256": groups_sha,
        "reviewer_id": "semantic-reviewer", "reviewed_group_ids": sorted(g["id"] for g in groups),
        "reviewed_cross_split_document_pairs": doc_pairs,
        "source_and_template_disjoint": True,
        "no_semantic_question_or_template_overlap": True,
        "no_paraphrase_or_page_text_leakage": True,
        "basis": "synthetic test corpus inspected for cross-split content"})).hexdigest()
    rights_rows = []
    for group in groups:
        for index, (window, offset) in enumerate(zip(
                group["four_exact_candidate_windows"],
                group["page_number_and_text_offsets_for_each_window"], strict=True)):
            rights_rows.append({"group_id": group["id"], "candidate_index": index,
                "source_document_sha256": group["source_document_sha256"],
                "page_number": offset["page_number"], "start": offset["start"],
                "end": offset["end"],
                "exact_window_sha256": hashlib.sha256(window.encode()).hexdigest(),
                "page_rights_clear": True, "cue_rights_clear": True,
                "third_party_material_excluded": True,
                "basis": "synthetic PDF and cue created by this test"})
    rights_path = root / "candidate-rights-audit.json"
    rights_sha = hashlib.sha256(_write(rights_path, {
        "schema": "cardchemy_reading_usefulness_candidate_rights_audit_v1",
        "manifest_sha256": fixture["manifest_sha256"], "groups_sha256": groups_sha,
        "reviewer_id": "rights-reviewer", "candidate_reviews": rights_rows})).hexdigest()
    return {"batches": batches,
            "semantic_leakage_audit_path": str(semantic_path),
            "semantic_leakage_audit_sha256": semantic_sha,
            "rights_audit_path": str(rights_path), "rights_audit_sha256": rights_sha}


@pytest.fixture(scope="module")
def packet(tmp_path_factory):
    root = tmp_path_factory.mktemp("public_reading_fixture")
    prereg = derived.preregistration_v4(corpus.preregistration())
    prereg_raw = _write(root / "preregistration.json", prereg)
    docs = []
    page_texts = {}
    by_split = {split: [] for split in validator.SPLIT_COUNTS}
    for split, urls in prereg["splits"].items():
        for url in urls:
            name = url.rsplit("/", 1)[-1]
            raw, texts = _pdf(root / name, name)
            sha = hashlib.sha256(raw).hexdigest()
            page_texts[sha] = texts
            by_split[split].append(sha)
            docs.append({"split": split, "url": url, "path": name, "bytes": len(raw),
                         "sha256": sha, "license_url": corpus.LICENSE_URL,
                         **corpus.pdf_metrics(raw)})
    manifest = {
        "schema": "cardchemy_public_reading_corpus_manifest_v1",
        "corpus_id": derived.V4_CORPUS_ID,
        "preregistration_sha256": hashlib.sha256(prereg_raw).hexdigest(),
        "index_url": corpus.INDEX_URL, "license_url": corpus.LICENSE_URL,
        "documents": docs, "requests_including_redirects": 0,
        "received_bytes": 0,
        "elapsed_seconds": 0, "all_pdf_first_pages_cc_by_4": True,
        "labels_written": False,
        "derived_from": derived._parent_provenance(),
        "local_copied_pdf_bytes": sum(doc["bytes"] for doc in docs),
    }
    manifest_raw = _write(root / "manifest.json", manifest)
    plan_raw = _write(root / "empty_fixture_plan.json", derived.empty_fixture_plan_v4(
        corpus.empty_fixture_plan(derived.V3_MANIFEST_SHA256),
        hashlib.sha256(manifest_raw).hexdigest()))
    _write(root / "derivation_receipt.json", {
        "schema": "cardchemy_public_reading_corpus_local_derivation_receipt_v1",
        "corpus_id": derived.V4_CORPUS_ID,
        "derived_from": derived._parent_provenance(),
        "preregistration_sha256": hashlib.sha256(prereg_raw).hexdigest(),
        "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "empty_fixture_plan_sha256": hashlib.sha256(plan_raw).hexdigest(),
        "documents": 14,
        "local_copied_pdf_bytes": sum(doc["bytes"] for doc in docs),
        "requests_including_redirects": 0,
        "provider_calls": 0,
        "model_scores": 0,
        "labels_written": False,
    })
    rights = [{"source_document_sha256": doc["sha256"], "reviewer_id": "rights-reviewer",
               "license_url": corpus.LICENSE_URL, "notice_page_number": 1,
               "text_reuse_permitted": True, "third_party_material_excluded": True}
              for doc in docs]
    groups = []
    for split in validator.SPLIT_COUNTS:
        serial = 0
        for relation_index, relation in enumerate(sorted(validator.RELATIONS)):
            for form_index, form in enumerate(sorted(validator.FORMS)):
                repeats = 4 if split == "train" else 2
                for repeat in range(repeats):
                    serial += 1
                    useful = repeat if split == "train" else (relation_index + form_index + repeat) % 4
                    sha = by_split[split][(serial - 1) % len(by_split[split])]
                    windows = []
                    offsets = []
                    page_labels = []
                    cue_labels = []
                    reviews = []
                    for index in range(4):
                        text = page_texts[sha][index]
                        start = text.index("Window ")
                        end = text.index(". ", start) + 1
                        cue = text[start:end]
                        page_useful = index < useful or (useful == 0 and index == 0)
                        cue_useful = index < useful
                        windows.append(cue)
                        offsets.append({"page_number": index + 1, "start": start, "end": end,
                                        "page_text_sha256": hashlib.sha256(text.encode()).hexdigest()})
                        page_labels.append(page_useful)
                        cue_labels.append(cue_useful)
                        opinions = [{"reviewer_id": person,
                                     "original_page_useful": page_useful,
                                     "exact_cue_useful": cue_useful}
                                    for person in ("reviewer-a", "reviewer-b")]
                        reviews.append({"reviews": opinions, "adjudication": {
                            "reviewer_ids": ["reviewer-a", "reviewer-b"],
                            "original_page_useful": page_useful,
                            "exact_cue_useful": cue_useful,
                            "resolution": "agreement"}})
                    groups.append({
                        "id": f"{split}-{serial:03d}", "split": split,
                        "source_document_sha256": sha, "question_form": form,
                        "relation_family": relation,
                        "question": f"{split} question {serial} about this public relation?",
                        "prior_question_context_if_followup": (
                            f"Which lecture concept is discussed in {split} case {serial}?"
                            if form == "follow-up" else None),
                        "question_template_id": f"{split}-{relation}-{form}",
                        "question_template": f"{split} {relation} {form} question about {{concept}}?",
                        "authored_by": "author", "leakage_review": {
                            "reviewer_id": "leakage-reviewer",
                            "source_and_template_disjoint": True,
                            "no_paraphrase_or_page_text_leakage": True},
                        "four_exact_candidate_windows": windows,
                        "page_number_and_text_offsets_for_each_window": offsets,
                        "original_page_usefulness_per_window": page_labels,
                        "exact_cue_usefulness_per_window": cue_labels,
                        "independent_reviewer_ids_and_adjudication": reviews,
                    })
    fixture = {"schema": validator.FIXTURE_SCHEMA, "corpus_id": derived.V4_CORPUS_ID,
               "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
               "plan_sha256": hashlib.sha256(plan_raw).hexdigest(),
               "extractor": {"name": "pypdf", "version": pypdf.__version__},
               "review_protocol": {
                   "independent_authors_and_blinded_reviewers": True,
                   "adjudicated_before_first_model_score": True,
                   "no_private_or_prior_scored_source": True,
                }, "document_rights_reviews": rights, "groups": groups}
    fixture["review_evidence"] = _review_evidence(root, fixture, docs)
    fixture_path = root / "reviewed_fixture.json"
    _write(fixture_path, fixture)
    return root, fixture_path, fixture


@pytest.fixture(autouse=True)
def synthetic_corpus_pins(packet, monkeypatch):
    root, _, _ = packet
    monkeypatch.setattr(validator, "CORPUS_PREREGISTRATION_SHA256",
                        hashlib.sha256((root / "preregistration.json").read_bytes()).hexdigest())
    monkeypatch.setattr(validator, "CORPUS_MANIFEST_SHA256",
                        hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest())
    monkeypatch.setattr(validator, "CORPUS_PLAN_SHA256",
                        hashlib.sha256((root / "empty_fixture_plan.json").read_bytes()).hexdigest())
    monkeypatch.setattr(validator, "CORPUS_DERIVATION_RECEIPT_SHA256",
                        hashlib.sha256((root / "derivation_receipt.json").read_bytes()).hexdigest())


def _mutated(packet, tmp_path, change):
    root, _, original = packet
    changed = copy.deepcopy(original)
    change(changed)
    path = tmp_path / "changed_fixture.json"
    _write(path, changed)
    return root, path


def test_full_synthetic_packet_passes_without_scoring(packet):
    root, path, _ = packet
    result = validator.validate(root, path)
    assert result["status"] == "fixture_validated_no_scoring"
    assert result["groups"] == 192 and result["documents"] == 14


def test_corpus_manifest_pin_is_required(packet, monkeypatch):
    root, path, _ = packet
    monkeypatch.setattr(validator, "CORPUS_MANIFEST_SHA256", "0" * 64)
    with pytest.raises(validator.FixtureError, match="corpus_manifest_pin"):
        validator.validate(root, path)


def test_derived_corpus_receipt_is_required(packet, monkeypatch):
    root, path, _ = packet
    monkeypatch.setattr(validator, "CORPUS_DERIVATION_RECEIPT_SHA256", "0" * 64)
    with pytest.raises(validator.FixtureError, match="derivation_identity"):
        validator.validate(root, path)


@pytest.mark.parametrize("field,reason", [
    ("blind_packet_sha256", "evidence_hash"),
    ("review_a_sha256", "evidence_hash"),
    ("opaque_mapping_sha256", "evidence_hash"),
    ("adjudication_sha256", "evidence_hash"),
    ("semantic_leakage_audit_sha256", "evidence_hash"),
    ("rights_audit_sha256", "evidence_hash"),
])
def test_external_review_evidence_is_hash_bound(packet, tmp_path, field, reason):
    def change(fixture):
        refs = fixture["review_evidence"]
        if field in refs:
            refs[field] = "0" * 64
        else:
            refs["batches"][0][field] = "0" * 64
    root, path = _mutated(packet, tmp_path, change)
    with pytest.raises(validator.FixtureError, match=reason):
        validator.validate(root, path)


def test_author_draft_must_match_opaque_mapping_and_fixture(packet, tmp_path):
    root, _, original = packet
    fixture = copy.deepcopy(original)
    batch = fixture["review_evidence"]["batches"][0]
    draft = json.loads(Path(batch["author_draft_path"]).read_bytes())
    draft["groups"][0]["question"] = "Different authored question?"
    draft_path = tmp_path / "altered-author-draft.json"
    batch["author_draft_sha256"] = hashlib.sha256(_write(draft_path, draft)).hexdigest()
    batch["author_draft_path"] = str(draft_path)
    mapping = json.loads(Path(batch["opaque_mapping_path"]).read_bytes())
    mapping["author_draft_sha256"] = batch["author_draft_sha256"]
    mapping_path = tmp_path / "altered-mapping.json"
    batch["opaque_mapping_sha256"] = hashlib.sha256(_write(mapping_path, mapping)).hexdigest()
    batch["opaque_mapping_path"] = str(mapping_path)
    path = tmp_path / "altered-fixture.json"
    _write(path, fixture)
    with pytest.raises(validator.FixtureError, match="author_draft_projection_mismatch"):
        validator.validate(root, path)


def test_count_bearing_opaque_group_id_is_rejected(packet, tmp_path):
    root, _, original = packet
    fixture = copy.deepcopy(original)
    batch = fixture["review_evidence"]["batches"][0]
    blind = json.loads(Path(batch["blind_packet_path"]).read_bytes())
    old_id = blind["groups"][0]["id"]
    blind["groups"][0]["id"] = "g_0_useful_count"
    blind_path = tmp_path / "count-bearing-blind.json"
    batch["blind_packet_sha256"] = hashlib.sha256(_write(blind_path, blind)).hexdigest()
    batch["blind_packet_path"] = str(blind_path)
    mapping = json.loads(Path(batch["opaque_mapping_path"]).read_bytes())
    mapping["blind_packet_sha256"] = batch["blind_packet_sha256"]
    next(entry for entry in mapping["groups"]
         if entry["opaque_group_id"] == old_id)["opaque_group_id"] = "g_0_useful_count"
    mapping_path = tmp_path / "count-bearing-mapping.json"
    batch["opaque_mapping_sha256"] = hashlib.sha256(_write(mapping_path, mapping)).hexdigest()
    batch["opaque_mapping_path"] = str(mapping_path)
    path = tmp_path / "count-bearing-fixture.json"
    _write(path, fixture)
    with pytest.raises(validator.FixtureError, match="opaque_group_identity"):
        validator.validate(root, path)


def test_attribution_prefix_cannot_hide_duplicate_selected_cue():
    repeated = ("CC BY 4.0. This public teaching passage explains how the precise "
                "source relation changes when the requested condition is reversed "
                "and why the observed result follows from that condition.")
    with pytest.raises(validator.FixtureError, match="cross_split_cue_shingle_leakage"):
        validator._cross_split_shingles({}, [("train", repeated), ("heldout", repeated)])


def test_uncertain_review_requires_separate_adjudication_before_freeze(packet, tmp_path):
    root, _, original = packet
    fixture = copy.deepcopy(original)
    refs = fixture["review_evidence"]
    batch = refs["batches"][0]
    second = json.loads(Path(batch["review_b_path"]).read_bytes())
    first_row = second["judgments"][0]
    first_row["uncertain"] = True
    second_path = tmp_path / "uncertain-review-b.json"
    batch["review_b_sha256"] = hashlib.sha256(_write(second_path, second)).hexdigest()
    batch["review_b_path"] = str(second_path)
    adjudication = json.loads(Path(batch["adjudication_path"]).read_bytes())
    adjudication["review_sha256"] = sorted((batch["review_a_sha256"],
                                             batch["review_b_sha256"]))
    adjudication["rows"] = [{
        "candidate_id": first_row["id"], "adjudicator_id": "third-reviewer",
        "original_page_useful": first_row["original_page_useful"],
        "exact_cue_useful": first_row["exact_visible_cue_useful"],
        "resolution_reason": "Synthetic original page and cue reviewed again",
    }]
    adjudication_path = tmp_path / "uncertain-adjudication.json"
    batch["adjudication_sha256"] = hashlib.sha256(
        _write(adjudication_path, adjudication)).hexdigest()
    batch["adjudication_path"] = str(adjudication_path)
    pending_path = tmp_path / "pending-uncertain-fixture.json"
    _write(pending_path, fixture)
    with pytest.raises(validator.FixtureError, match="unresolved_review"):
        validator.validate(root, pending_path)

    fixture["groups"][0]["independent_reviewer_ids_and_adjudication"][0][
        "adjudication"]["resolution"] = "resolved_uncertainty"
    groups_sha = hashlib.sha256(corpus.canonical_bytes(fixture["groups"])).hexdigest()
    for stem in ("semantic_leakage_audit", "rights_audit"):
        source = json.loads(Path(refs[f"{stem}_path"]).read_bytes())
        source["groups_sha256"] = groups_sha
        path = tmp_path / f"{stem}-resolved.json"
        refs[f"{stem}_sha256"] = hashlib.sha256(_write(path, source)).hexdigest()
        refs[f"{stem}_path"] = str(path)
    resolved_path = tmp_path / "resolved-uncertain-fixture.json"
    _write(resolved_path, fixture)
    assert validator.validate(root, resolved_path)["status"] == "fixture_validated_no_scoring"


@pytest.mark.parametrize("change,reason", [
    (lambda f: f["groups"].pop(), "group_count"),
    (lambda f: f["groups"][0]["four_exact_candidate_windows"].pop(), "four_candidate_arrays"),
    (lambda f: f["groups"][0]["page_number_and_text_offsets_for_each_window"][0].update(
        start=1000), "exact_window_offset"),
    (lambda f: f["groups"][0]["exact_cue_usefulness_per_window"].__setitem__(0, True),
     "adjudicated_label"),
    (lambda f: f["groups"][0]["independent_reviewer_ids_and_adjudication"][0]["reviews"][1].update(
        reviewer_id="reviewer-a"), "duplicate_reviewer"),
    (lambda f: f["groups"][0]["independent_reviewer_ids_and_adjudication"][0]["adjudication"].update(
        resolution="resolved_disagreement"), "adjudication_resolution"),
    (lambda f: f["groups"][0].update(question_form="unsupported"), "group_stratum"),
    (lambda f: f["groups"][0].update(prior_question_context_if_followup="extra"), "followup_context"),
    (lambda f: f["groups"][96].update(source_document_sha256=f["groups"][0]["source_document_sha256"]),
     "group_identity"),
    (lambda f: f["groups"][96].update(question_template_id=f["groups"][0]["question_template_id"]),
     "cross_split_template_id"),
    (lambda f: f["groups"][0]["leakage_review"].update(
        no_paraphrase_or_page_text_leakage=False), "leakage_review"),
    (lambda f: f["document_rights_reviews"][0].update(text_reuse_permitted=False),
     "rights_review"),
])
def test_malformed_or_unreviewed_packet_fails_closed(packet, tmp_path, change, reason):
    root, path = _mutated(packet, tmp_path, change)
    with pytest.raises(validator.FixtureError, match=reason):
        validator.validate(root, path)


def test_strata_rejects_count_and_relation_form_drift(packet, tmp_path):
    def change(fixture):
        group = fixture["groups"][0]
        group["relation_family"] = "definition" if group["relation_family"] != "definition" else "reason"
    root, path = _mutated(packet, tmp_path, change)
    with pytest.raises(validator.FixtureError, match="relation_form_strata"):
        validator.validate(root, path)


def test_strata_rejects_positive_form_drift(packet, tmp_path):
    def change(fixture):
        groups = [group for group in fixture["groups"]
                  if group["split"] == "heldout"
                  and group["relation_family"] == "acronym_expansion"]
        direct = next(group for group in groups if group["question_form"] == "direct"
                      and not any(group["exact_cue_usefulness_per_window"]))
        paraphrase = next(group for group in groups if group["question_form"] == "paraphrase"
                          and any(group["exact_cue_usefulness_per_window"]))
        direct["question_form"], paraphrase["question_form"] = (
            paraphrase["question_form"], direct["question_form"])

    root, path = _mutated(packet, tmp_path, change)
    with pytest.raises(validator.FixtureError, match="positive_form_strata"):
        validator.validate(root, path)


def test_document_bytes_and_license_provenance_are_rechecked(packet, tmp_path):
    root, fixture_path, _ = packet
    first = next(path for path in root.glob("lec*.pdf"))
    original = first.read_bytes()
    try:
        first.write_bytes(original + b"tampered")
        with pytest.raises(validator.FixtureError, match="document_hash"):
            validator.validate(root, fixture_path)
    finally:
        first.write_bytes(original)


def test_freeze_is_exclusive_and_external_pin_required(packet, tmp_path, monkeypatch):
    root, fixture_path, _ = packet
    harness = tmp_path / "harness.py"
    runtime = tmp_path / "runtime.json"
    bundle = tmp_path / "bundle-manifest.json"
    receipt = tmp_path / "freeze.json"
    harness.write_text("# synthetic offline scorer identity\n", encoding="utf-8")
    runtime.write_text("{}\n", encoding="utf-8")
    bundle.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(validator, "MODEL_BUNDLE_MANIFEST_SHA256",
                        hashlib.sha256(bundle.read_bytes()).hexdigest())
    result = validator.freeze(root, fixture_path, harness, runtime, bundle, receipt)
    pin = result["freeze_sha256"]
    assert validator.verify(root, fixture_path, harness, runtime, bundle, receipt, pin)["status"] == (
        "frozen_inputs_verified_no_scoring")
    with pytest.raises(FileExistsError):
        validator.freeze(root, fixture_path, harness, runtime, bundle, receipt)
    with pytest.raises(validator.FixtureError, match="expected_freeze_sha256"):
        validator.verify(root, fixture_path, harness, runtime, bundle, receipt, "")
    harness.write_text("# changed scorer identity\n", encoding="utf-8")
    with pytest.raises(validator.FixtureError, match="freeze_mismatch"):
        validator.verify(root, fixture_path, harness, runtime, bundle, receipt, pin)


def test_noncanonical_and_duplicate_json_keys_fail_before_labels(packet, tmp_path):
    root, _, fixture = packet
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(fixture, indent=2), encoding="utf-8")
    with pytest.raises(validator.FixtureError, match="noncanonical_json"):
        validator.validate(root, path)
    path.write_text('{"schema":"a","schema":"b"}\n', encoding="utf-8")
    with pytest.raises(validator.FixtureError, match="duplicate_json_key"):
        validator.validate(root, path)


def test_unlabeled_inventory_is_exact_bounded_and_exclusive(packet, tmp_path, monkeypatch):
    root, _, _ = packet
    monkeypatch.setattr(inventory, "gettempdir", lambda: str(tmp_path))
    output = tmp_path / "inventory.json"
    result = inventory.build(root, output)
    assert result["status"] == "unlabeled_inventory_created_no_scoring"
    assert result["documents"] == 14
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert "groups" not in saved and "labels" not in saved
    assert all(doc["license_url"] == corpus.LICENSE_URL for doc in saved["documents"])
    for doc in saved["documents"]:
        for page in doc["pages"]:
            assert len(page["candidate_windows"]) <= inventory.MAX_WINDOWS_PER_PAGE
            for window in page["candidate_windows"]:
                assert page["extracted_text"][window["start"]:window["end"]] == window["exact_text"]
                assert len(window["exact_text"]) <= inventory.MAX_WINDOW_CHARS
    with pytest.raises(validator.FixtureError, match="output_exists"):
        inventory.build(root, output)


def test_inventory_refuses_non_temp_destination(packet, tmp_path, monkeypatch):
    root, _, _ = packet
    monkeypatch.setattr(inventory, "gettempdir", lambda: str(tmp_path / "different"))
    with pytest.raises(validator.FixtureError, match="os_temp_output_required"):
        inventory.build(root, tmp_path / "inventory.json")
