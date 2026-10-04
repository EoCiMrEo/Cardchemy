"""Synthetic-only contracts for blind, complete, irreversible source reviews."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import audit_source_usefulness_contract_v1 as audit  # noqa: E402


@pytest.fixture
def synthetic_source(tmp_path: Path) -> tuple[dict, dict]:
    """Three invented groups; fake PDF identities are never opened."""
    documents = {
        f"hidden-document-{number}": {
            "pages": 8,
            "pdf_path": str(tmp_path / f"hidden-document-{number}.pdf"),
            "sha256": audit.digest(f"fake-pdf-{number}".encode()),
        }
        for number in range(4)
    }
    groups = []
    for group_number in range(3):
        candidates = []
        for candidate_number in range(4):
            cue = f"  Synthetic relation {group_number}:{candidate_number} – α.  "
            context = f"Before\n{cue}\nAfter."
            candidates.append({
                "id": f"old-output-SELECTED-{group_number}-{candidate_number}",
                "document_id": f"hidden-document-{candidate_number}",
                "page": candidate_number + 1,
                "context": context,
                "context_start": 11,
                "context_end": 11 + len(context),
                "cue": cue,
                "cue_start": 18,
                "cue_end": 18 + len(cue),
                "page_text_sha256": audit.digest(f"fake-page-{group_number}-{candidate_number}".encode()),
            })
        groups.append({
            "group_id": f"old-label-TRUE-{group_number}",
            "question": f"What connects synthetic step {group_number} to its result?",
            "candidates": candidates,
        })
    return {
        "schema_version": "synthetic_input_v1",
        "corpus_id": "hidden-original-corpus",
        "documents": list(documents),
        "groups": groups,
        "source_manifest_sha256": "f" * 64,
        "split": "calibration",
    }, documents


@pytest.fixture
def workspace(tmp_path: Path, synthetic_source: tuple[dict, dict]) -> Path:
    packet, documents = synthetic_source
    batches, mapping = audit.build_packets(packet, documents, "synthetic-seed", expected_groups=3)
    root = tmp_path / "audit"
    root.mkdir()
    mapping_sha = audit.write_new(root / "mapping-root-only.json", mapping)
    hashes = {}
    for batch in batches:
        directory = root / f"batch-{batch['batch']}"
        directory.mkdir()
        hashes[str(batch["batch"])] = audit.write_new(directory / "wire-packet.json", batch)
        for reviewer in ("a", "b"):
            (directory / reviewer).mkdir()
    audit.write_new(root / "freeze.json", {
        "schema_version": audit.VERSION,
        "source_packet_sha256": audit.digest(audit.canonical(packet)),
        "source_manifest_sha256": packet["source_manifest_sha256"],
        "rubric_sha256": audit.digest(audit.canonical(audit.RUBRIC)),
        "mapping_sha256": mapping_sha,
        "wire_packet_hashes": hashes,
        "groups": 3,
        "candidate_pairs": 12,
        "shuffle_seed": "synthetic-seed",
    })
    return root


def review_for(packet: dict, packet_sha: str, reviewer: str = "a") -> dict:
    rows = []
    for group in packet["groups"]:
        for index, candidate in enumerate(group["candidates"]):
            value = ("Yes", "No", "Unsure")[index % 3]
            fields = {"input_sufficiency": value} if packet["stage"] == "wire" else {
                "page_usefulness": value, "cue_usefulness": value,
            }
            rows.append({"pair_id": candidate["pair_id"], **fields, "reason": "direct_relation"})
    return {
        "schema_version": audit.VERSION,
        "stage": packet["stage"],
        "reviewer_id": reviewer,
        "packet_sha256": packet_sha,
        "judgments": rows,
    }


def draft_for(root: Path, *, stage: str = "wire", reviewer: str = "a", batch: int = 1) -> Path:
    directory = root / f"batch-{batch}"
    packet_path = directory / "wire-packet.json" if stage == "wire" else directory / reviewer / "pages-packet.json"
    packet, packet_sha = audit.read(packet_path)
    draft = root / f"draft-{batch}-{reviewer}-{stage}.json"
    audit.write_new(draft, review_for(packet, packet_sha, reviewer))
    return draft


def snapshot(directory: Path) -> dict[str, bytes]:
    return {str(path.relative_to(directory)): path.read_bytes() for path in directory.rglob("*") if path.is_file()}


def test_all_pairs_and_exact_windows_survive_three_balanced_blind_batches(synthetic_source):
    packet, documents = synthetic_source
    before = deepcopy(packet)
    batches, mapping = audit.build_packets(packet, documents, "synthetic-seed", expected_groups=3)
    assert packet == before
    assert [batch["batch"] for batch in batches] == [1, 2, 3]
    assert [len(batch["groups"]) for batch in batches] == [1, 1, 1]
    original_groups = {group["group_id"]: group for group in packet["groups"]}
    original_pairs = {(group["group_id"], candidate["id"]): candidate
                      for group in packet["groups"] for candidate in group["candidates"]}
    origins = {row["pair_id"]: row for row in mapping["pairs"]}
    assert len(origins) == len(mapping["pairs"]) == 12
    assert {(row["old_group_id"], row["old_candidate_id"]) for row in origins.values()} == set(original_pairs)
    issued_ids = []
    for batch in batches:
        assert set(batch) == {"schema_version", "stage", "batch", "rubric", "groups"}
        for group in batch["groups"]:
            assert set(group) == {"group_id", "question", "candidates"}
            assert len(group["candidates"]) == 4
            for candidate in group["candidates"]:
                assert set(candidate) == {"pair_id", "context", "cue"}
                issued_ids.append(candidate["pair_id"])
                origin = origins[candidate["pair_id"]]
                original = original_pairs[origin["old_group_id"], origin["old_candidate_id"]]
                assert group["question"] == original_groups[origin["old_group_id"]]["question"]
                assert candidate["context"] == original["context"]
                assert candidate["cue"] == original["cue"]
                for name in ("document_id", "page", "page_text_sha256", "context_start", "context_end", "cue_start", "cue_end"):
                    assert origin[name] == original[name]
                assert origin["pdf_path"] == documents[original["document_id"]]["pdf_path"]
    assert len(set(issued_ids)) == 12
    assert set(issued_ids) == set(origins)
    wire = audit.canonical(batches).decode()
    for hidden in ("hidden-document-", "old-label-TRUE-", "old-output-SELECTED-", "hidden-original-corpus",
                   "pdf_path", "page_text_sha256", "context_start", "document_id"):
        assert hidden not in wire
    assert audit.build_packets(packet, documents, "synthetic-seed", expected_groups=3) == (batches, mapping)
    _, other_mapping = audit.build_packets(packet, documents, "another-seed", expected_groups=3)
    assert [(row["old_group_id"], row["old_candidate_id"]) for row in mapping["pairs"]] != [
        (row["old_group_id"], row["old_candidate_id"]) for row in other_mapping["pairs"]
    ]


@pytest.mark.parametrize("level,field", [("packet", "old_labels"), ("group", "model_output"),
                                          ("candidate", "gold_useful")])
def test_review_leaking_extra_source_fields_are_rejected(synthetic_source, level, field):
    packet, documents = synthetic_source
    target = packet if level == "packet" else packet["groups"][0]
    if level == "candidate":
        target = target["candidates"][0]
    target[field] = "must not enter blind packet"
    with pytest.raises(audit.AuditError, match="fields"):
        audit.build_packets(packet, documents, "synthetic-seed", expected_groups=3)


@pytest.mark.parametrize("mutation,error", [
    ("heldout", "calibration_only"), ("missing_group", "complete_unique_groups_required"),
    ("duplicate_group", "complete_unique_groups_required"), ("missing_pair", "four_unique_candidates"),
    ("duplicate_pair", "four_unique_candidates"), ("foreign_document", "source_identity"),
    ("outside_page", "source_identity"), ("changed_cue", "wire_window_invalid"),
])
def test_incomplete_or_foreign_source_rosters_are_rejected(synthetic_source, mutation, error):
    packet, documents = synthetic_source
    candidates = packet["groups"][0]["candidates"]
    if mutation == "heldout":
        packet["split"] = "heldout"
    elif mutation == "missing_group":
        packet["groups"].pop()
    elif mutation == "duplicate_group":
        packet["groups"][1] = deepcopy(packet["groups"][0])
    elif mutation == "missing_pair":
        candidates.pop()
    elif mutation == "duplicate_pair":
        candidates[1] = deepcopy(candidates[0])
    elif mutation == "foreign_document":
        candidates[0]["document_id"] = "unknown-source"
    elif mutation == "outside_page":
        candidates[0]["page"] = 9
    else:
        candidates[0]["cue"] = "invented text not in context"
    with pytest.raises(audit.AuditError, match=error):
        audit.build_packets(packet, documents, "synthetic-seed", expected_groups=3)


@pytest.mark.parametrize("stage", ["wire", "pages"])
@pytest.mark.parametrize("mutation,error", [
    ("missing", "complete_review_required"), ("duplicate", "judgment_identity_reason"),
    ("foreign", "judgment_identity_reason"), ("extra", "judgment_fields"),
    ("invalid_reason", "judgment_identity_reason"), ("bool_label", "tristate_required"),
    ("lowercase_label", "tristate_required"), ("null_label", "tristate_required"),
])
def test_reviews_require_every_issued_pair_once_with_explicit_tristate(workspace, stage, mutation, error):
    packet, sha = audit.read(workspace / "batch-1" / "wire-packet.json")
    packet["stage"] = stage
    review = review_for(packet, sha)
    audit.validate_review(review, packet, sha, "a", stage)
    row = review["judgments"][0]
    label = "input_sufficiency" if stage == "wire" else "page_usefulness"
    if mutation == "missing":
        review["judgments"].pop()
    elif mutation == "duplicate":
        review["judgments"][1] = deepcopy(row)
    elif mutation == "foreign":
        row["pair_id"] = "P999"
    elif mutation == "extra":
        row["old_gold"] = True
    elif mutation == "invalid_reason":
        row["reason"] = "model_said_so"
    else:
        row[label] = {"bool_label": True, "lowercase_label": "yes", "null_label": None}[mutation]
    with pytest.raises(audit.AuditError, match=error):
        audit.validate_review(review, packet, sha, "a", stage)


@pytest.mark.parametrize("field,value", [("schema_version", "old_schema"), ("stage", "pages"),
                                         ("reviewer_id", "b"), ("packet_sha256", "0" * 64)])
def test_review_cannot_be_reused_for_another_packet_reviewer_or_stage(workspace, field, value):
    packet, sha = audit.read(workspace / "batch-1" / "wire-packet.json")
    review = review_for(packet, sha)
    review[field] = value
    with pytest.raises(audit.AuditError, match="review_binding"):
        audit.validate_review(review, packet, sha, "a", "wire")


@pytest.mark.parametrize("page_value", ["No", "Unsure"])
def test_useful_cue_requires_yes_for_page(workspace, page_value):
    packet, sha = audit.read(workspace / "batch-1" / "wire-packet.json")
    packet["stage"] = "pages"
    review = review_for(packet, sha)
    review["judgments"][0].update(page_usefulness=page_value, cue_usefulness="Yes")
    with pytest.raises(audit.AuditError, match="cue_requires_page"):
        audit.validate_review(review, packet, sha, "a", "pages")


def test_pdf_identities_appear_only_after_complete_wire_review_is_sealed(workspace, monkeypatch):
    directory = workspace / "batch-1" / "a"
    assert snapshot(directory) == {}
    draft = draft_for(workspace)
    incomplete, _ = audit.read(draft)
    incomplete["judgments"].pop()
    draft.write_bytes(audit.canonical(incomplete))
    with pytest.raises(audit.AuditError, match="complete_review_required"):
        audit.seal(workspace, 1, "a", "wire", draft)
    assert snapshot(directory) == {}
    packet, packet_sha = audit.read(workspace / "batch-1" / "wire-packet.json")
    complete = review_for(packet, packet_sha)
    draft.write_bytes(audit.canonical(complete))
    write_new = audit.write_new
    writes = []

    def tracked_write(path, value):
        if path.name == "pages-packet.json":
            sealed, sealed_sha = audit.read(directory / "wire-sealed.json")
            assert sealed == complete
            assert value["wire_review_sha256"] == sealed_sha
        writes.append(path.name)
        return write_new(path, value)

    monkeypatch.setattr(audit, "write_new", tracked_write)
    sealed_sha = audit.seal(workspace, 1, "a", "wire", draft)
    assert writes.index("wire-sealed.json") < writes.index("pages-packet.json")
    pages, pages_sha = audit.read(directory / "pages-packet.json")
    assert pages["stage"] == "pages"
    assert pages["wire_review_sha256"] == sealed_sha
    mapping, _ = audit.read(workspace / "mapping-root-only.json")
    origins = {row["pair_id"]: row for row in mapping["pairs"]}
    for group in pages["groups"]:
        for candidate in group["candidates"]:
            origin = origins[candidate["pair_id"]]
            for field in ("pdf_path", "pdf_sha256", "page"):
                assert candidate[field] == origin[field]
            assert "old_candidate_id" not in candidate
    seal, _ = audit.read(directory / "wire-seal.json")
    assert seal == {"review_sha256": sealed_sha, "pages_packet_sha256": pages_sha}
    assert snapshot(workspace / "batch-1" / "b") == {}
    assert snapshot(workspace / "batch-2" / "a") == {}
    page_draft = draft_for(workspace, stage="pages")
    audit.seal(workspace, 1, "a", "pages", page_draft)
    assert audit.read(directory / "wire-sealed.json")[0] == complete
    assert (directory / "pages-seal.json").is_file()


@pytest.mark.parametrize("target,error", [("wire-packet.json", "wire_packet_changed"),
                                          ("mapping-root-only.json", "mapping_changed")])
def test_tampering_before_wire_seal_rejects_without_new_review_artifacts(workspace, target, error):
    draft = draft_for(workspace)
    path = workspace / target if target.startswith("mapping") else workspace / "batch-1" / target
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(audit.AuditError, match=error):
        audit.seal(workspace, 1, "a", "wire", draft)
    assert snapshot(workspace / "batch-1" / "a") == {}


@pytest.mark.parametrize("target,error", [("wire-sealed.json", "wire_review_changed"),
                                          ("pages-packet.json", "pages_packet_changed")])
def test_tampering_after_wire_seal_blocks_page_review(workspace, target, error):
    audit.seal(workspace, 1, "a", "wire", draft_for(workspace))
    draft = draft_for(workspace, stage="pages")
    directory = workspace / "batch-1" / "a"
    path = directory / target
    path.write_bytes(path.read_bytes() + b" ")
    before = snapshot(directory)
    with pytest.raises(audit.AuditError, match=error):
        audit.seal(workspace, 1, "a", "pages", draft)
    assert snapshot(directory) == before


@pytest.mark.parametrize("existing", ["wire-sealed.json", "wire-seal.json", "pages-packet.json"])
def test_existing_partial_wire_state_cannot_be_reopened(workspace, existing):
    directory = workspace / "batch-1" / "a"
    audit.write_new(directory / existing, {"interrupted_seal": True})
    draft = draft_for(workspace)
    before = snapshot(directory)
    with pytest.raises((audit.AuditError, FileExistsError)):
        audit.seal(workspace, 1, "a", "wire", draft)
    assert snapshot(directory) == before


@pytest.mark.parametrize("stage", ["wire", "pages"])
def test_completed_seals_cannot_be_overwritten(workspace, stage):
    wire_draft = draft_for(workspace)
    audit.seal(workspace, 1, "a", "wire", wire_draft)
    draft = wire_draft
    if stage == "pages":
        draft = draft_for(workspace, stage="pages")
        audit.seal(workspace, 1, "a", "pages", draft)
    before = snapshot(workspace / "batch-1" / "a")
    with pytest.raises((audit.AuditError, FileExistsError)):
        audit.seal(workspace, 1, "a", stage, draft)
    assert snapshot(workspace / "batch-1" / "a") == before


def test_interrupted_page_packet_write_cannot_resume_wire_review(workspace, monkeypatch):
    directory = workspace / "batch-1" / "a"
    draft = draft_for(workspace)
    write_new = audit.write_new

    def interrupted_write(path, value):
        if path.name == "pages-packet.json":
            raise OSError("synthetic write interruption")
        return write_new(path, value)

    with monkeypatch.context() as patch:
        patch.setattr(audit, "write_new", interrupted_write)
        with pytest.raises(OSError, match="synthetic write interruption"):
            audit.seal(workspace, 1, "a", "wire", draft)
    assert (directory / "wire-sealed.json").is_file()
    assert not (directory / "pages-packet.json").exists()
    before = snapshot(directory)
    with pytest.raises((audit.AuditError, FileExistsError)):
        audit.seal(workspace, 1, "a", "wire", draft)
    assert snapshot(directory) == before


def test_exclusive_json_write_preserves_existing_bytes_and_duplicate_keys_are_rejected(tmp_path):
    path = tmp_path / "existing.json"
    audit.write_new(path, {"sealed": True})
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        audit.write_new(path, {"sealed": False})
    assert path.read_bytes() == before
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_bytes(b'{"judgments":[],"judgments":[]}')
    with pytest.raises(audit.AuditError, match="duplicate_json_key"):
        audit.read(duplicate)
