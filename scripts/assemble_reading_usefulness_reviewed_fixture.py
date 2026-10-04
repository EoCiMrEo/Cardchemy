"""Assemble a reviewed v4 public fixture without assigning or scoring labels.

``prepare`` resolves opaque IDs using two pinned blind reviews and any required
independent adjudication. It writes the exact reviewed groups and their hash to
OS Temp so independent semantic and candidate-rights reviewers can bind their
receipts to those bytes. ``finalize`` requires those separately written receipts,
reassembles the pinned inputs, validates the entire fixture, and only then
publishes it exclusively. No PDF text is printed by either command.

The pinned inputs JSON has schema ``cardchemy_reading_usefulness_assembly_inputs_v1``
and keys ``corpus_root``, ``manifest_sha256``, ``plan_sha256``,
``attestations_path``, ``attestations_sha256`` and ``batches``. Batches have the
exact two ``review_evidence.batches`` shapes used by the fixture validator.
The separate pinned attestations JSON has schema
``cardchemy_reading_usefulness_assembly_attestations_v1`` and keys
``corpus_id``, ``manifest_sha256``, ``review_protocol``,
``document_rights_reviews`` and ``leakage_reviews``. Each leakage row has
``group_id`` plus the three validator leakage-review fields. The assembler
does not create, infer, or sign any of these attestations.
"""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
import os
from pathlib import Path
import secrets
from tempfile import gettempdir

import pypdf

import acquire_reading_usefulness_corpus as corpus
import derive_reading_usefulness_corpus_v4 as derived
import validate_reading_usefulness_fixture as validator


INPUT_SCHEMA = "cardchemy_reading_usefulness_assembly_inputs_v1"
ATTESTATION_SCHEMA = "cardchemy_reading_usefulness_assembly_attestations_v1"
PREPARED_SCHEMA = "cardchemy_reading_usefulness_assembled_groups_v1"
LABEL_KEYS = {"original_page_usefulness_per_window",
              "exact_cue_usefulness_per_window",
              "independent_reviewer_ids_and_adjudication"}
AUTHOR_KEYS = validator.GROUP_KEYS - LABEL_KEYS - {"leakage_review"}
BATCH_KEYS = {"scope", "author_draft_path", "author_draft_sha256",
              "blind_packet_path", "blind_packet_sha256", "opaque_mapping_path",
              "opaque_mapping_sha256", "review_a_path", "review_a_sha256",
              "review_b_path", "review_b_sha256", "adjudication_path",
              "adjudication_sha256"}


def _temp_path(path: Path, *, output: bool = False) -> None:
    temp = Path(gettempdir()).resolve()
    validator.require(path.is_absolute() and temp in path.resolve().parents,
                      "os_temp_path_required")
    validator.require(path.parent.is_dir() and
                      not any(parent.is_symlink() for parent in
                              (path, *path.parents) if parent != temp),
                      "temp_path_symlink_or_parent")
    if output:
        validator.require(not path.exists() and not path.is_symlink(), "output_exists")
    else:
        validator.require(path.is_file() and not path.is_symlink(), "input_missing")


def _pinned_json(path: Path, expected_sha256: str,
                 limit: int = validator.MAX_EVIDENCE_BYTES) -> dict:
    _temp_path(path)
    validator.require(validator.sha_field(expected_sha256), "expected_sha256")
    value, raw = validator.read_json(path, limit)
    validator.require(validator.digest(raw) == expected_sha256, "input_hash")
    return value


def _evidence(path_value: object, sha_value: object) -> dict:
    validator.require(type(path_value) is str and type(sha_value) is str,
                      "evidence_reference")
    _temp_path(Path(path_value))
    value, _ = validator._evidence(path_value, sha_value)
    return value


def _publish_exclusive(output: Path, data: bytes) -> None:
    """Expose complete bytes at a fresh OS-Temp name in one filesystem step."""
    candidate = output.parent / ("." + output.name + "." +
                                 secrets.token_hex(12) + ".assembly-candidate")
    _temp_path(candidate, output=True)
    try:
        with candidate.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(candidate, output)
    finally:
        candidate.unlink(missing_ok=True)


def _attestations(value: dict, groups: dict[str, dict],
                  documents: dict[str, dict], manifest_sha: str) -> tuple[dict, list[dict]]:
    validator.require(set(value) == {"schema", "corpus_id", "manifest_sha256",
                      "review_protocol", "document_rights_reviews", "leakage_reviews"}
                      and value["schema"] == ATTESTATION_SCHEMA
                      and value["corpus_id"] == derived.V4_CORPUS_ID
                      and value["manifest_sha256"] == manifest_sha,
                      "attestation_identity")
    protocol = value["review_protocol"]
    validator.require(protocol == {
        "independent_authors_and_blinded_reviewers": True,
        "adjudicated_before_first_model_score": True,
        "no_private_or_prior_scored_source": True,
    }, "review_protocol_attestation")
    rights = value["document_rights_reviews"]
    validator.require(type(rights) is list and len(rights) == len(documents),
                      "document_rights_attestation")
    rights_ids = set()
    for row in rights:
        validator.require(type(row) is dict and set(row) == {
            "source_document_sha256", "reviewer_id", "license_url",
            "notice_page_number", "text_reuse_permitted",
            "third_party_material_excluded"}, "document_rights_attestation")
        sha = row["source_document_sha256"]
        validator.require(sha in documents and sha not in rights_ids and
                          validator.text_field(row["reviewer_id"], 100) and
                          row["license_url"] == corpus.LICENSE_URL and
                          type(row["notice_page_number"]) is int and
                          row["notice_page_number"] == 1 and
                          row["text_reuse_permitted"] is True and
                          row["third_party_material_excluded"] is True,
                          "document_rights_attestation")
        rights_ids.add(sha)
    validator.require(rights_ids == set(documents), "document_rights_attestation")
    leakage = value["leakage_reviews"]
    validator.require(type(leakage) is list and len(leakage) == len(groups),
                      "leakage_attestation")
    leakage_by_id = {}
    for row in leakage:
        validator.require(type(row) is dict and set(row) == {
            "group_id", "reviewer_id", "source_and_template_disjoint",
            "no_paraphrase_or_page_text_leakage"}, "leakage_attestation")
        gid = row["group_id"]
        validator.require(gid in groups and gid not in leakage_by_id and
                          validator.text_field(row["reviewer_id"], 100) and
                          row["reviewer_id"] != groups[gid]["authored_by"] and
                          row["source_and_template_disjoint"] is True and
                          row["no_paraphrase_or_page_text_leakage"] is True,
                          "leakage_attestation")
        leakage_by_id[gid] = {key: row[key] for key in row if key != "group_id"}
    validator.require(set(leakage_by_id) == set(groups), "leakage_attestation")
    for gid, group in groups.items():
        group["leakage_review"] = leakage_by_id[gid]
    return protocol, rights


def _assemble_batch(batch: dict, groups: dict[str, dict],
                    documents: dict[str, dict], corpus_id: str,
                    manifest_sha: str) -> None:
    validator.require(type(batch) is dict and set(batch) == BATCH_KEYS and
                      batch["scope"] in {"train", "evaluation"}, "review_batch")
    draft = _evidence(batch["author_draft_path"], batch["author_draft_sha256"])
    blind = _evidence(batch["blind_packet_path"], batch["blind_packet_sha256"])
    mapping = _evidence(batch["opaque_mapping_path"], batch["opaque_mapping_sha256"])
    first = _evidence(batch["review_a_path"], batch["review_a_sha256"])
    second = _evidence(batch["review_b_path"], batch["review_b_sha256"])
    adjudication = _evidence(batch["adjudication_path"], batch["adjudication_sha256"])
    validator.require(draft.get("status") in {
        "author_only_pending_independent_blind_review_and_adjudication_no_model_score",
        "AUTHOR DRAFT ONLY; provisional labels; no independent reviews, rights review, adjudication, freeze, or model score",
    },
                      "author_draft_identity")
    validator.require(draft.get("corpus_id") == corpus_id and
                      draft.get("manifest_sha256") == manifest_sha and
                      type(draft.get("groups")) is list and len(draft["groups"]) == 96 and
                      blind.get("schema") == "cardchemy_reading_usefulness_blind_review_v2" and
                      blind.get("corpus_id") == corpus_id and
                      blind.get("manifest_sha256") == manifest_sha and
                      type(blind.get("groups")) is list and len(blind["groups"]) == 96 and
                      mapping.get("schema") == "cardchemy_reading_usefulness_blind_mapping_v1" and
                      mapping.get("author_draft_sha256") == batch["author_draft_sha256"] and
                      mapping.get("blind_packet_sha256") == batch["blind_packet_sha256"] and
                      type(mapping.get("groups")) is list and len(mapping["groups"]) == 96,
                      "batch_identity")
    authored = {group["id"]: group for group in draft["groups"]
                if type(group) is dict and type(group.get("id")) is str}
    projected = {group["id"]: group for group in blind["groups"]
                 if type(group) is dict and type(group.get("id")) is str}
    validator.require(len(authored) == 96 and len(projected) == 96,
                      "batch_group_identity")
    expected_scope = {"train"} if batch["scope"] == "train" else {"calibration", "heldout"}
    candidate_identity: dict[str, tuple] = {}
    author_by_candidate: dict[str, str] = {}
    destination: dict[str, tuple[dict, int]] = {}
    mapped_groups: set[str] = set()
    for entry in mapping["groups"]:
        validator.require(type(entry) is dict and set(entry) == {
            "opaque_group_id", "author_group_id", "split", "candidates"},
            "opaque_mapping_fields")
        opaque, gid, split = (entry[key] for key in
                              ("opaque_group_id", "author_group_id", "split"))
        validator.require(opaque in projected and gid in authored and
                          gid not in groups and gid not in mapped_groups and
                          split in expected_scope and authored[gid].get("split") == split and
                          type(entry["candidates"]) is list and
                          len(entry["candidates"]) == 4, "opaque_mapping_group")
        mapped_groups.add(gid)
        source = authored[gid]
        validator.require(AUTHOR_KEYS <= source.keys() and
                          type(source.get("four_exact_candidate_windows")) is list and
                          len(source["four_exact_candidate_windows"]) == 4 and
                          type(source.get("page_number_and_text_offsets_for_each_window")) is list and
                          len(source["page_number_and_text_offsets_for_each_window"]) == 4,
                          "author_group_fields")
        group = {key: copy.deepcopy(source[key]) for key in AUTHOR_KEYS}
        group.update({key: [None] * 4 for key in LABEL_KEYS})
        groups[gid] = group
        sha = group["source_document_sha256"]
        validator.require(sha in documents and
                          type(projected[opaque].get("candidates")) is list and
                          len(projected[opaque]["candidates"]) == 4,
                          "blind_group_identity")
        candidates = {item["id"]: item for item in projected[opaque]["candidates"]
                      if type(item) is dict and type(item.get("id")) is str}
        validator.require(len(candidates) == 4, "blind_candidate_identity")
        seen_indices: set[int] = set()
        for mapped in entry["candidates"]:
            validator.require(type(mapped) is dict and set(mapped) == {
                "opaque_candidate_id", "author_candidate_index"},
                "opaque_candidate_mapping")
            cid, index = mapped["opaque_candidate_id"], mapped["author_candidate_index"]
            validator.require(cid in candidates and cid not in destination and
                              type(index) is int and index in range(4) and
                              index not in seen_indices, "opaque_candidate_mapping")
            seen_indices.add(index)
            candidate = candidates[cid]
            offset = group["page_number_and_text_offsets_for_each_window"][index]
            validator.require(candidate.get("exact_window") ==
                              group["four_exact_candidate_windows"][index] and
                              candidate.get("source_offset") == offset and
                              type(offset) is dict and
                              type(offset.get("page_number")) is int,
                              "blind_projection_mismatch")
            candidate_identity[cid] = (opaque, documents[sha]["path"],
                                       offset["page_number"])
            author_by_candidate[cid] = group["authored_by"]
            destination[cid] = (group, index)
        validator.require(seen_indices == set(range(4)), "opaque_candidate_mapping")
    validator.require(set(authored) == mapped_groups and
                      set(projected) == {entry["opaque_group_id"] for entry in mapping["groups"]}
                      and len(destination) == 384, "review_mapping_coverage")
    first_id, first_rows = validator._review_rows(first, batch["blind_packet_sha256"],
                                                  candidate_identity, author_by_candidate)
    second_id, second_rows = validator._review_rows(second, batch["blind_packet_sha256"],
                                                    candidate_identity, author_by_candidate)
    validator.require(first_id != second_id and
                      batch["review_a_sha256"] != batch["review_b_sha256"],
                      "reviewer_independence")
    validator.require(adjudication.get("schema") ==
                      "cardchemy_reading_usefulness_adjudication_v1" and
                      adjudication.get("blind_packet_sha256") == batch["blind_packet_sha256"] and
                      adjudication.get("review_sha256") ==
                      sorted((batch["review_a_sha256"], batch["review_b_sha256"])) and
                      type(adjudication.get("rows")) is list, "adjudication_receipt")
    resolved = {}
    for row in adjudication["rows"]:
        validator.require(type(row) is dict and set(row) == {
            "candidate_id", "adjudicator_id", "original_page_useful",
            "exact_cue_useful", "resolution_reason"}, "adjudication_receipt")
        cid = row["candidate_id"]
        validator.require(cid in destination and cid not in resolved and
                          validator.text_field(row["adjudicator_id"], 100) and
                          row["adjudicator_id"] not in
                          {first_id, second_id, author_by_candidate[cid]} and
                          type(row["original_page_useful"]) is bool and
                          type(row["exact_cue_useful"]) is bool and
                          (not row["exact_cue_useful"] or row["original_page_useful"]) and
                          validator.text_field(row["resolution_reason"], 1000),
                          "adjudication_receipt")
        resolved[cid] = row
    required = set()
    for cid, (group, index) in destination.items():
        left, right = first_rows[cid], second_rows[cid]
        first_label = (left["original_page_useful"], left["exact_visible_cue_useful"])
        second_label = (right["original_page_useful"], right["exact_visible_cue_useful"])
        uncertain = left["uncertain"] or right["uncertain"]
        disagree = first_label != second_label
        if uncertain or disagree:
            required.add(cid)
            validator.require(cid in resolved, "unresolved_review")
            row = resolved[cid]
            page, cue = row["original_page_useful"], row["exact_cue_useful"]
            resolution = "resolved_disagreement" if disagree else "resolved_uncertainty"
        else:
            validator.require(cid not in resolved, "unrequested_adjudication")
            page, cue = first_label
            resolution = "agreement"
        group["original_page_usefulness_per_window"][index] = page
        group["exact_cue_usefulness_per_window"][index] = cue
        group["independent_reviewer_ids_and_adjudication"][index] = {
            "reviews": [
                {"reviewer_id": reviewer_id, "original_page_useful": label[0],
                 "exact_cue_useful": label[1]}
                for reviewer_id, label in ((first_id, first_label), (second_id, second_label))
            ],
            "adjudication": {"reviewer_ids": [first_id, second_id],
                             "original_page_useful": page,
                             "exact_cue_useful": cue, "resolution": resolution},
        }
    validator.require(set(resolved) == required, "adjudication_coverage")
    validator._review_batch(batch, {"corpus_id": corpus_id,
                                    "manifest_sha256": manifest_sha},
                            groups, documents)


def _assemble(inputs_path: Path, inputs_sha256: str) -> dict:
    inputs = _pinned_json(inputs_path, inputs_sha256)
    validator.require(set(inputs) == {"schema", "corpus_root", "manifest_sha256",
                      "plan_sha256", "attestations_path", "attestations_sha256",
                      "batches"} and inputs["schema"] == INPUT_SCHEMA,
                      "assembly_inputs")
    root = Path(inputs["corpus_root"])
    _temp_path(root / "manifest.json")
    manifest, manifest_raw = validator.read_json(root / "manifest.json", 64_000)
    plan, plan_raw = validator.read_json(root / "empty_fixture_plan.json", 32_768)
    validator.require(validator.digest(manifest_raw) == inputs["manifest_sha256"] ==
                      validator.CORPUS_MANIFEST_SHA256 and
                      validator.digest(plan_raw) == inputs["plan_sha256"] ==
                      validator.CORPUS_PLAN_SHA256 and
                      manifest.get("corpus_id") == derived.V4_CORPUS_ID and
                      type(manifest.get("documents")) is list and
                      len(manifest["documents"]) == 14,
                      "corpus_identity")
    documents = {row["sha256"]: row for row in manifest["documents"]
                 if type(row) is dict and type(row.get("sha256")) is str}
    validator.require(len(documents) == 14 and
                      all(type(row.get("path")) is str for row in documents.values()),
                      "document_identity")
    batches = inputs["batches"]
    validator.require(type(batches) is list and len(batches) == 2 and
                      {row.get("scope") for row in batches if type(row) is dict} ==
                      {"train", "evaluation"}, "review_batches")
    groups: dict[str, dict] = {}
    for batch in batches:
        _assemble_batch(batch, groups, documents, derived.V4_CORPUS_ID,
                        inputs["manifest_sha256"])
    validator.require(len(groups) == 192 and
                      all(set(group) == AUTHOR_KEYS | LABEL_KEYS for group in groups.values()),
                      "assembled_groups")
    split_counts: Counter[str] = Counter()
    useful_counts: Counter[tuple[str, int]] = Counter()
    relation_form_counts: Counter[tuple[str, str, str]] = Counter()
    positive_form_counts: Counter[tuple[str, str]] = Counter()
    for group in groups.values():
        split = group["split"]
        form = group["question_form"]
        relation = group["relation_family"]
        validator.require(split in validator.SPLIT_COUNTS and
                          form in validator.FORMS and relation in validator.RELATIONS,
                          "group_stratum")
        labels = group["exact_cue_usefulness_per_window"]
        pages = group["original_page_usefulness_per_window"]
        validator.require(all(type(page) is bool and type(cue) is bool and
                              (not cue or page)
                              for page, cue in zip(pages, labels, strict=True)),
                          "reviewed_label")
        useful = sum(page and cue for page, cue in zip(pages, labels, strict=True))
        validator.require(useful <= 3, "useful_count_limit")
        split_counts[split] += 1
        useful_counts[(split, useful)] += 1
        relation_form_counts[(split, relation, form)] += 1
        positive_form_counts[(split, form)] += useful > 0
    validator.require(dict(split_counts) == validator.SPLIT_COUNTS, "split_counts")
    for split in validator.SPLIT_COUNTS:
        for count in range(4):
            validator.require(useful_counts[(split, count)] ==
                              validator.USEFUL_COUNTS[split], "useful_count_strata")
        per_pair = validator.SPLIT_COUNTS[split] // (
            len(validator.RELATIONS) * len(validator.FORMS))
        for relation in validator.RELATIONS:
            for form in validator.FORMS:
                validator.require(relation_form_counts[(split, relation, form)] ==
                                  per_pair, "relation_form_strata")
        for form in validator.FORMS:
            validator.require(positive_form_counts[(split, form)] ==
                              3 * validator.USEFUL_COUNTS[split] // len(validator.FORMS),
                              "positive_form_strata")
    attestations = _pinned_json(Path(inputs["attestations_path"]),
                                inputs["attestations_sha256"])
    protocol, document_rights = _attestations(attestations, groups, documents,
                                             inputs["manifest_sha256"])
    split_order = {"train": 0, "calibration": 1, "heldout": 2}
    ordered = sorted(groups.values(), key=lambda group:
                     (split_order[group["split"]], group["id"]))
    groups_sha = validator.digest(corpus.canonical_bytes(ordered))
    return {"schema": PREPARED_SCHEMA,
            "status": "reviewed_groups_prepared_no_scoring",
            "inputs_path": str(inputs_path), "inputs_sha256": inputs_sha256,
            "corpus_root": str(root), "corpus_id": derived.V4_CORPUS_ID,
            "manifest_sha256": inputs["manifest_sha256"],
            "plan_sha256": inputs["plan_sha256"],
            "review_protocol": protocol,
            "document_rights_reviews": document_rights,
            "batches": batches,
            "groups": ordered, "groups_sha256": groups_sha}


def prepare(inputs: Path, expected_sha256: str, output: Path) -> dict[str, object]:
    _temp_path(output, output=True)
    prepared = _assemble(inputs, expected_sha256)
    data = corpus.canonical_bytes(prepared)
    validator.require(len(data) <= validator.MAX_FIXTURE_BYTES,
                      "prepared_size_limit")
    _publish_exclusive(output, data)
    return {"status": prepared["status"], "groups": len(prepared["groups"]),
            "groups_sha256": prepared["groups_sha256"],
            "prepared_sha256": validator.digest(data)}


def finalize(prepared_path: Path, expected_sha256: str,
             semantic_path: Path, semantic_sha256: str,
             rights_path: Path, rights_sha256: str,
             output: Path) -> dict[str, object]:
    _temp_path(output, output=True)
    prepared = _pinned_json(prepared_path, expected_sha256,
                            validator.MAX_FIXTURE_BYTES)
    validator.require(prepared.get("schema") == PREPARED_SCHEMA and
                      prepared.get("status") == "reviewed_groups_prepared_no_scoring" and
                      type(prepared.get("inputs_path")) is str and
                      type(prepared.get("inputs_sha256")) is str,
                      "prepared_identity")
    rebuilt = _assemble(Path(prepared["inputs_path"]), prepared["inputs_sha256"])
    validator.require(prepared == rebuilt and
                      prepared["groups_sha256"] ==
                      validator.digest(corpus.canonical_bytes(prepared["groups"])),
                      "prepared_reassembly_mismatch")
    semantic = _evidence(str(semantic_path), semantic_sha256)
    rights = _evidence(str(rights_path), rights_sha256)
    validator.require(semantic.get("groups_sha256") == prepared["groups_sha256"] and
                      rights.get("groups_sha256") == prepared["groups_sha256"],
                      "external_groups_hash")
    fixture = {"schema": validator.FIXTURE_SCHEMA,
               "corpus_id": prepared["corpus_id"],
               "manifest_sha256": prepared["manifest_sha256"],
               "plan_sha256": prepared["plan_sha256"],
               "extractor": {"name": "pypdf", "version": pypdf.__version__},
               "review_protocol": prepared["review_protocol"],
               "document_rights_reviews": prepared["document_rights_reviews"],
               "review_evidence": {"batches": prepared["batches"],
                   "semantic_leakage_audit_path": str(semantic_path),
                   "semantic_leakage_audit_sha256": semantic_sha256,
                   "rights_audit_path": str(rights_path),
                   "rights_audit_sha256": rights_sha256},
               "groups": prepared["groups"]}
    data = corpus.canonical_bytes(fixture)
    validator.require(len(data) <= validator.MAX_FIXTURE_BYTES, "fixture_size_limit")
    # The validator needs a path. Its temporary candidate is never a published
    # fixture; publication occurs only after the full corpus/evidence check.
    candidate = output.parent / ("." + output.name + "." +
                                 secrets.token_hex(12) + ".validation-candidate")
    _temp_path(candidate, output=True)
    try:
        with candidate.open("xb") as stream:
            stream.write(data)
        result = validator.validate(Path(prepared["corpus_root"]), candidate)
        _publish_exclusive(output, data)
    finally:
        candidate.unlink(missing_ok=True)
    return {"status": "reviewed_fixture_validated_no_scoring",
            "groups": result["groups"], "fixture_sha256": result["fixture_sha256"],
            "groups_sha256": prepared["groups_sha256"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    initial = commands.add_parser("prepare")
    initial.add_argument("--inputs", type=Path, required=True)
    initial.add_argument("--expected-sha256", required=True)
    initial.add_argument("--output", type=Path, required=True)
    final = commands.add_parser("finalize")
    final.add_argument("--prepared", type=Path, required=True)
    final.add_argument("--expected-sha256", required=True)
    final.add_argument("--semantic", type=Path, required=True)
    final.add_argument("--semantic-sha256", required=True)
    final.add_argument("--rights", type=Path, required=True)
    final.add_argument("--rights-sha256", required=True)
    final.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare(args.inputs, args.expected_sha256, args.output)
        else:
            result = finalize(args.prepared, args.expected_sha256,
                              args.semantic, args.semantic_sha256,
                              args.rights, args.rights_sha256, args.output)
    except validator.FixtureError as exc:
        raise SystemExit(f"Reviewed fixture assembly rejected: {exc}") from None
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        raise SystemExit("Reviewed fixture assembly rejected; private diagnostics withheld.") from None
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
