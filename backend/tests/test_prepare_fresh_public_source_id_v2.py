"""Keyless contract tests for the fresh public PDF packet freezer."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "prepare_fresh_public_source_id_v2.py"
SPEC = importlib.util.spec_from_file_location("prepare_fresh_public_source_id_v2", SCRIPT)
assert SPEC and SPEC.loader
freeze = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(freeze)


def example_inputs():
    manifest_hash = "a" * 64
    documents = [
        {"document_id": document_id, "sha256": hashlib.sha256(document_id.encode()).hexdigest(),
         "pages": page_count, "split": split}
        for document_id, (split, page_count) in freeze.EXPECTED.items()
    ]
    pages = {(document_id, page): f"Lecture {document_id} page {page}. CC BY 4.0. " + "A useful point is stated here. " * 30
             for document_id in freeze.EXPECTED for page in (1, 2)}
    groups = []
    review_groups = []
    for split in freeze.SPLITS:
        docs = [doc["document_id"] for doc in documents if doc["split"] == split]
        for form in freeze.FORMS:
            for number in range(12):
                gid = f"{split}-{form}-{number:02d}"
                candidates = []
                review_candidates = []
                useful_count = 0 if form == "no_useful" else number % 3 + 1
                for index in range(4):
                    cid = f"P{index + 1}"
                    doc_id = docs[index // 2]
                    candidates.append({"id": cid, "document_id": doc_id, "page": index % 2 + 1,
                                       "context_start": 0, "context_end": 100, "cue_start": 20, "cue_end": 60})
                    useful = index < useful_count
                    review_candidates.append({"id": cid, "page_useful": useful, "cue_useful": useful})
                groups.append({"group_id": gid, "split": split, "form": form,
                               "question": f"Where is concept {hashlib.sha256(gid.encode()).hexdigest()[:8]} discussed?", "candidates": candidates})
                review_groups.append({"group_id": gid, "candidates": review_candidates})
    authored = {"schema_version": freeze.AUTHORED_SCHEMA, "corpus_id": freeze.CORPUS_ID,
                "source_manifest_sha256": manifest_hash, "overlap_review_sha256": "c" * 64,
                "author_id": "author_agent", "groups": groups}
    review_a = {"schema_version": freeze.REVIEW_SCHEMA, "reviewer_id": "reviewer_a", "groups": review_groups}
    review_b = copy.deepcopy(review_a)
    review_b["reviewer_id"] = "reviewer_b"
    adjudication = {"schema_version": freeze.ADJUDICATION_SCHEMA, "reviewer_id": "reviewer_c", "decisions": []}
    manifest = {"schema": freeze.MANIFEST_SCHEMA, "corpus_id": freeze.CORPUS_ID,
                "preregistration_sha256": freeze.PREREGISTRATION_SHA256,
                "content_overlap_review": "required_before_question_authoring",
                "comparison_manifests": [
                    {"role": "ece448_sp2020", "manifest_sha256": "d" * 64, "document_count": 14},
                    {"role": "reserved_illinois", "manifest_sha256": "e" * 64, "document_count": 2},
                ]}
    return manifest, authored, review_a, review_b, adjudication, pages, documents, manifest_hash, "c" * 64


def build(inputs):
    return freeze.build_artifacts(*inputs)


def test_fresh_split_packet_is_label_free_and_hash_bound():
    artifacts = build(example_inputs())
    assert set(artifacts) == {"calibration/packet.json", "calibration/labels.json",
                              "heldout/packet.json", "heldout/labels.json"}
    for split in freeze.SPLITS:
        packet = artifacts[f"{split}/packet.json"]
        labels = artifacts[f"{split}/labels.json"]
        assert len(packet["groups"]) == len(labels["groups"]) == 48
        assert len(packet["documents"]) == 4
        assert labels["packet_sha256"] == freeze.sha256_bytes(freeze.canonical_bytes(packet))
        serialized = freeze.canonical_bytes(packet).decode("utf-8")
        assert "page_useful" not in serialized and "cue_useful" not in serialized
        assert "reviewer" not in serialized and "label" not in serialized
        assert "no_useful" not in serialized and "paraphrase" not in serialized
        assert all(candidate["id"] in {"S01", "S02", "S03", "S04"}
                   for group in packet["groups"] for candidate in group["candidates"])
        assert all(candidate["cue"] == example_inputs()[5][(candidate["document_id"], candidate["page"])][candidate["cue_start"]:candidate["cue_end"]]
                   for group in packet["groups"] for candidate in group["candidates"])


def test_two_reviewers_and_exact_disagreement_adjudication():
    inputs = list(example_inputs())
    gid = inputs[3]["groups"][0]["group_id"]
    inputs[3]["groups"][0]["candidates"][0]["page_useful"] = False
    inputs[3]["groups"][0]["candidates"][0]["cue_useful"] = False
    with pytest.raises(freeze.FreezeError, match="adjudication"):
        build(inputs)
    inputs[4]["decisions"] = [{"group_id": gid, "id": "P1", "page_useful": True, "cue_useful": True}]
    artifacts = build(inputs)
    assert artifacts["calibration/labels.json"]["disagreement_count"] == 1
    assert artifacts["heldout/labels.json"]["disagreement_count"] == 0
    inputs[4]["reviewer_id"] = "reviewer_a"
    with pytest.raises(freeze.FreezeError, match="independent"):
        build(inputs)


@pytest.mark.parametrize("edit,match", [
    (lambda data: data[1]["groups"][0]["candidates"][0].update(cue_end=1300), "offsets"),
    (lambda data: data[1]["groups"][0]["candidates"][0].update(document_id="lec08"), "PDF mismatch"),
    (lambda data: data[1]["groups"][0]["candidates"][3].update(document_id="lec06"), "two PDFs"),
    (lambda data: data[1]["groups"][0].update(form="no_useful"), "12 groups per form"),
    (lambda data: data[2].update(reviewer_id="reviewer_b"), "distinct independent"),
    (lambda data: data[1]["groups"][0]["candidates"][0].update(page_useful=True), "unexpected fields"),
])
def test_rejects_source_split_review_and_label_leak_errors(edit, match):
    inputs = list(example_inputs())
    edit(inputs)
    with pytest.raises(freeze.FreezeError, match=match):
        build(inputs)


def test_no_useful_and_strata_are_review_derived():
    inputs = list(example_inputs())
    group = next(group for group in inputs[2]["groups"] if "no_useful" in group["group_id"])
    matching = next(other for other in inputs[3]["groups"] if other["group_id"] == group["group_id"])
    for item in (group["candidates"][0], matching["candidates"][0]):
        item["page_useful"] = item["cue_useful"] = True
    with pytest.raises(freeze.FreezeError, match="no-useful"):
        build(inputs)
    inputs = list(example_inputs())
    for review in inputs[2:4]:
        item = review["groups"][0]["candidates"][1]
        item["page_useful"] = item["cue_useful"] = True
    with pytest.raises(freeze.FreezeError, match="strata"):
        build(inputs)


def test_canonical_json_is_deterministic_and_duplicate_keys_reject(tmp_path):
    a = freeze.canonical_bytes({"b": 2, "a": 1})
    assert a == b'{"a":1,"b":2}\n'
    file = tmp_path / "duplicate.json"
    file.write_text('{"a":1,"a":2}', encoding="utf-8")
    with pytest.raises(freeze.FreezeError, match="duplicate"):
        freeze.read_json(file)


def test_verified_child_rejects_path_traversal_and_symlink(tmp_path):
    (tmp_path / "lec04.pdf").write_bytes(b"sample")
    assert freeze._verified_child(tmp_path, "lec04.pdf").name == "lec04.pdf"
    with pytest.raises(freeze.FreezeError, match="unexpected source path"):
        freeze._verified_child(tmp_path, "../lec04.pdf")


def test_packet_schema_uses_only_explicit_source_offsets():
    inputs = list(example_inputs())
    candidate = inputs[1]["groups"][0]["candidates"][0]
    candidate["context_start"] = 30
    with pytest.raises(freeze.FreezeError, match="offsets"):
        build(inputs)
    candidate["context_start"] = 20
    candidate["cue_start"] = 20
    packet = build(inputs)["calibration/packet.json"]
    assert any(candidate["context_start"] == 20 for group in packet["groups"] for candidate in group["candidates"])


def test_review_requires_both_page_and_visible_cue():
    inputs = list(example_inputs())
    for review in inputs[2:4]:
        review["groups"][0]["candidates"][0]["cue_useful"] = False
    with pytest.raises(freeze.FreezeError, match="positive group"):
        build(inputs)


def test_disjoint_source_roster_required():
    inputs = list(example_inputs())
    inputs[6][0]["split"] = "heldout"
    with pytest.raises(freeze.FreezeError, match="four disjoint PDFs"):
        build(inputs)


def test_prior_corpus_overlap_pages_cannot_enter_candidate_slate():
    with pytest.raises(freeze.FreezeError, match="overlaps prior public corpus"):
        freeze.build_artifacts(*example_inputs(), excluded_pages={("lec04", 1)})


def test_question_author_cannot_grade_or_adjudicate_own_slates():
    inputs = list(example_inputs())
    inputs[1]["author_id"] = "reviewer_a"
    with pytest.raises(freeze.FreezeError, match="author cannot review"):
        build(inputs)
    inputs = list(example_inputs())
    inputs[1]["author_id"] = "reviewer_c"
    with pytest.raises(freeze.FreezeError, match="author cannot adjudicate"):
        build(inputs)


def test_overlap_diagnostic_reports_exact_normalized_page_and_is_screening_only():
    new_pages = {(document_id, page): f"Unique {document_id} page {page} concept sequence"
                 for document_id, (_, count) in freeze.EXPECTED.items() for page in range(1, count + 1)}
    new_pages[("lec04", 1)] = "Alpha, beta gamma delta epsilon zeta."
    old_pages = {("sp2020", 1): "ALPHA beta gamma delta epsilon zeta"}
    diagnostic = freeze.overlap_diagnostic(
        new_pages, old_pages, "a" * 64, {"ece448_sp2020": "d" * 64, "reserved_illinois": "e" * 64})
    assert diagnostic["new_page_count"] == 278
    assert diagnostic["screening_only"] is True
    assert diagnostic["method"] == freeze.OVERLAP_METHOD
    assert diagnostic["exclusion_threshold"] == 0.5
    first = diagnostic["per_new_document"][0]
    assert first == {"document_id": "lec04", "max_page_jaccard": 1.0,
                     "exact_normalized_page_matches": 1, "excluded_pages": [1]}
    manifest = example_inputs()[0]
    review = {"schema_version": freeze.OVERLAP_REVIEW_SCHEMA, "corpus_id": freeze.CORPUS_ID,
              "source_manifest_sha256": "a" * 64,
              "diagnostic_sha256": freeze.sha256_bytes(freeze.canonical_bytes(diagnostic)),
              "reviewer_id": "independent_overlap", "decision": "approved_for_question_authoring",
              "reviewed_document_ids": sorted(freeze.EXPECTED),
              "reviewed_comparison_roles": ["ece448_sp2020", "reserved_illinois"],
              "attestation": "independent_blinded_content_overlap_review"}
    assert freeze.validate_overlap_gate(manifest, "a" * 64, diagnostic,
                                        review["diagnostic_sha256"], review) == "independent_overlap"
    review["decision"] = "pending"
    with pytest.raises(freeze.FreezeError, match="not approved"):
        freeze.validate_overlap_gate(manifest, "a" * 64, diagnostic,
                                     review["diagnostic_sha256"], review)


def test_manifest_rehashes_exact_roster_and_rechecks_title_page(monkeypatch, tmp_path):
    class FakePage:
        def __init__(self, text):
            self.text = text

        def extract_text(self):
            return self.text

    class FakeReader:
        def __init__(self, source, strict=False):
            document_id = source.getvalue().decode().rsplit(" ", 1)[-1]
            count = freeze.EXPECTED[document_id][1]
            self.is_encrypted = False
            self.pages = [FakePage("CC BY 4.0 " + "topic " * 20)] + [FakePage("topic " * 20) for _ in range(count - 1)]

    monkeypatch.setattr(freeze, "PdfReader", FakeReader)
    schedule = "".join(f'<a href="slides/{document_id}.pdf">Lecture</a>' for document_id in freeze.EXPECTED).encode()
    (tmp_path / "lectures.html").write_bytes(schedule)
    documents = []
    for document_id, (split, count) in freeze.EXPECTED.items():
        raw = f"%PDF-1.7 synthetic {document_id}".encode()
        (tmp_path / f"{document_id}.pdf").write_bytes(raw)
        texts = [page.extract_text() for page in FakeReader(io.BytesIO(raw)).pages]
        documents.append({"split": split, "url": f"{freeze.SOURCE_BASE}{document_id}.pdf",
                          "path": f"{document_id}.pdf", "bytes": len(raw), "sha256": freeze.sha256_bytes(raw),
                          "pages": count, "alphanumeric_text_chars": sum(sum(char.isalnum() for char in text) for text in texts),
                          "pages_with_at_least_40_alphanumeric_chars": count,
                          "first_page_license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/"})
    manifest = {"schema": freeze.MANIFEST_SCHEMA, "corpus_id": freeze.CORPUS_ID,
                "preregistration_sha256": freeze.PREREGISTRATION_SHA256,
                "license_url": freeze.LICENSE_URL, "all_pdf_first_pages_cc_by_4": True, "labels_written": False,
                "content_overlap_review": "required_before_question_authoring",
                "schedule": {"url": "https://courses.grainger.illinois.edu/ece448/sp2022/lectures.html",
                             "path": "lectures.html", "bytes": len(schedule), "sha256": freeze.sha256_bytes(schedule)},
                "documents": documents}
    pages, metadata = freeze.load_verified_pages(manifest, tmp_path / "manifest.json")
    assert len(metadata) == 8 and len(pages) == 278
    (tmp_path / "lec04.pdf").write_bytes(b"tampered")
    with pytest.raises(freeze.FreezeError, match="hash/size"):
        freeze.load_verified_pages(manifest, tmp_path / "manifest.json")


def test_freeze_writes_exclusive_temp_hash_receipt(monkeypatch, tmp_path):
    inputs = list(example_inputs())
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(freeze.canonical_bytes(inputs[0]))
    inputs[1]["source_manifest_sha256"] = freeze.sha256_bytes(manifest_path.read_bytes())
    diagnostic = {"schema_version": freeze.OVERLAP_DIAGNOSTIC_SCHEMA, "corpus_id": freeze.CORPUS_ID,
                  "source_manifest_sha256": inputs[1]["source_manifest_sha256"],
                  "comparison_manifest_sha256": {record["role"]: record["manifest_sha256"] for record in inputs[0]["comparison_manifests"]},
                  "method": freeze.OVERLAP_METHOD, "screening_only": True,
                  "exclusion_threshold": freeze.OVERLAP_EXCLUSION_THRESHOLD,
                  "new_page_count": 278, "comparison_page_count": 500,
                  "per_new_document": [{"document_id": document_id, "max_page_jaccard": 0.1,
                                        "exact_normalized_page_matches": 0, "excluded_pages": []}
                                       for document_id in sorted(freeze.EXPECTED)]}
    diagnostic_path = tmp_path / "overlap_diagnostic.json"
    diagnostic_path.write_bytes(freeze.canonical_bytes(diagnostic))
    overlap_review = {"schema_version": freeze.OVERLAP_REVIEW_SCHEMA, "corpus_id": freeze.CORPUS_ID,
                      "source_manifest_sha256": inputs[1]["source_manifest_sha256"],
                      "diagnostic_sha256": freeze.sha256_bytes(diagnostic_path.read_bytes()),
                      "reviewer_id": "overlap_reviewer", "decision": "approved_for_question_authoring",
                      "reviewed_document_ids": sorted(freeze.EXPECTED),
                      "reviewed_comparison_roles": ["ece448_sp2020", "reserved_illinois"],
                      "attestation": "independent_blinded_content_overlap_review"}
    overlap_review_path = tmp_path / "overlap_review.json"
    overlap_review_path.write_bytes(freeze.canonical_bytes(overlap_review))
    inputs[1]["overlap_review_sha256"] = freeze.sha256_bytes(overlap_review_path.read_bytes())
    paths = [tmp_path / name for name in ("authored.json", "review_a.json", "review_b.json", "adjudication.json")]
    for path, value in zip(paths, inputs[1:5]):
        path.write_bytes(freeze.canonical_bytes(value))
    monkeypatch.setattr(freeze, "load_verified_pages", lambda manifest, path: (inputs[5], inputs[6]))
    monkeypatch.setattr(freeze.tempfile, "gettempdir", lambda: str(tmp_path))
    output = freeze.freeze_files(manifest_path, *paths, diagnostic_path, overlap_review_path)
    second_output = freeze.freeze_files(manifest_path, *paths, diagnostic_path, overlap_review_path)
    assert output != second_output and output.parent == tmp_path
    receipt = json.loads((output / "freeze.json").read_text(encoding="utf-8"))
    assert set(receipt["files"]) == {"calibration/packet.json", "calibration/labels.json",
                                      "heldout/packet.json", "heldout/labels.json"}
    for relative, digest in receipt["files"].items():
        assert freeze.sha256_bytes((output / relative).read_bytes()) == digest
    assert receipt["source_manifest_sha256"] == inputs[1]["source_manifest_sha256"]
    assert receipt["input_sha256"]["overlap_review"] == inputs[1]["overlap_review_sha256"]
    sys.path.insert(0, str(SCRIPT.parent))
    import score_fresh_public_source_id_v2 as scorer

    scorer_freeze, _ = scorer._freeze(output)
    for split in freeze.SPLITS:
        packet, labels, packet_sha, labels_sha, request_hashes = scorer._packet_and_labels(
            output, scorer_freeze, split)
        assert len(packet["groups"]) == len(labels["groups"]) == len(request_hashes) == 48
        assert packet_sha == receipt["files"][f"{split}/packet.json"]
        assert labels_sha == receipt["files"][f"{split}/labels.json"]
