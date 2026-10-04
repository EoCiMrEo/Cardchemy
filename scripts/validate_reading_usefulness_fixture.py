"""Validate and freeze a reviewed public reading-usefulness fixture, without scoring.

The fixture keeps the group field names published by empty_fixture_plan().
Additional required fields are question_template_id, question_template,
authored_by, and leakage_review. Its top level has schema, corpus_id,
manifest_sha256, plan_sha256, review_protocol, document_rights_reviews, groups.
Each group has four parallel, ordered window/offset/label/review arrays. Offsets
are Python string offsets into pypdf's extract_text() for the one-based page.

``freeze`` creates a receipt exclusively and prints its SHA-256. Record that
digest outside the mutable audit folder before scoring. ``verify`` requires
the recorded digest and rechecks every source, label, and frozen input byte.
This cannot establish that a human label is correct or prove freeze chronology.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import logging
from pathlib import Path
import re
import sys
from tempfile import gettempdir

import pypdf
from pypdf import PdfReader

import acquire_reading_usefulness_corpus as corpus
import derive_reading_usefulness_corpus_v4 as derived

logging.getLogger("pypdf").setLevel(logging.ERROR)


FIXTURE_SCHEMA = "cardchemy_reading_usefulness_fixture_v2"
FREEZE_SCHEMA = "cardchemy_reading_usefulness_freeze_v1"
MODEL_BUNDLE_MANIFEST_SHA256 = "2b7d441b1eb987502a7668355de4cf39f68bee3fd1dacea8d7c2dc1a97278182"
CORPUS_PREREGISTRATION_SHA256 = "c3bf3a6a25cee67a0205e1dea82b4627cdaff2b0da5dc9a75d2258af229d6a43"
CORPUS_MANIFEST_SHA256 = "9978ad6fd2ca50f20d20ed8231e7434e2d8f91bbdc21b61e5e44ddcb76f0eae4"
CORPUS_PLAN_SHA256 = "3c2ea97e78c7c50aacb5c8aae48da18f3800b71bfb78eb17f715827baf9f4f62"
CORPUS_DERIVATION_RECEIPT_SHA256 = "7040773f2941d999d6703c63d0e8ff5b11189735ba05975a1e27b4f75b158b93"
RELATIONS = frozenset({"acronym_expansion", "definition", "mechanism", "measurement",
                       "reason", "process", "property_limitation", "application_example"})
FORMS = frozenset({"direct", "paraphrase", "follow-up"})
SPLIT_COUNTS = {"train": 96, "calibration": 48, "heldout": 48}
USEFUL_COUNTS = {"train": 24, "calibration": 12, "heldout": 12}
MAX_FIXTURE_BYTES = 4 * 1024 * 1024
MAX_EVIDENCE_BYTES = 4 * 1024 * 1024
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
ATTRIBUTION_RE = re.compile(
    r"creative\s+commons|creativecommons|cc\s+by|copyright|©|"
    r"licensed\s+under|attribution[-\s]+sharealike", re.IGNORECASE)
GROUP_KEYS = frozenset({
    "id", "split", "source_document_sha256", "question_form", "relation_family",
    "question", "prior_question_context_if_followup", "question_template_id",
    "question_template", "authored_by", "leakage_review",
    "four_exact_candidate_windows", "page_number_and_text_offsets_for_each_window",
    "original_page_usefulness_per_window", "exact_cue_usefulness_per_window",
    "independent_reviewer_ids_and_adjudication",
})


class FixtureError(ValueError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise FixtureError(code)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_bytes(path: Path, limit: int) -> bytes:
    require(not path.is_symlink() and path.is_file(), "file_missing_or_symlink")
    require(path.stat().st_size <= limit, "file_size_limit")
    return path.read_bytes()


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def read_json(path: Path, limit: int) -> tuple[dict, bytes]:
    raw = file_bytes(path, limit)
    try:
        value = json.loads(raw, object_pairs_hook=_unique_pairs)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FixtureError("invalid_json") from exc
    require(type(value) is dict, "json_object_required")
    require(raw == corpus.canonical_bytes(value), "noncanonical_json")
    return value, raw


def text_field(value: object, limit: int = 1000) -> bool:
    return type(value) is str and 0 < len(value) <= limit and value == value.strip() and "\x00" not in value


def exact_window_field(value: object) -> bool:
    # An exact PDF span can include a final newline. Trimming it here would
    # invalidate the independently reviewed source offset and window digest.
    return (type(value) is str and 0 < len(value) <= 480 and
            bool(value.strip()) and "\x00" not in value)


def sha_field(value: object) -> bool:
    return type(value) is str and HEX64.fullmatch(value) is not None


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _shingles(value: str, size: int = 12, *, page_attribution: bool = False) -> set[tuple[str, ...]]:
    # Common source notices do not establish a substantive cross-split leak.
    # Exact displayed cues are never filtered: a notice prefix must not mask
    # duplicated teaching text in the model's actual input.
    text = ("\n".join(line for line in value.splitlines()
                      if not ATTRIBUTION_RE.search(line))
            if page_attribution else value)
    words = WORD_RE.findall(text.casefold())
    return {tuple(words[index:index + size]) for index in range(len(words) - size + 1)}


def _cross_split_shingles(selected_pages: dict[tuple[str, int], tuple[str, str]],
                          selected_windows: list[tuple[str, str]]) -> None:
    window_owners: dict[tuple[str, ...], str] = {}
    for split, window in selected_windows:
        for shingle in _shingles(window):
            require(window_owners.get(shingle, split) == split,
                    "cross_split_cue_shingle_leakage")
            window_owners[shingle] = split
    page_owners: dict[tuple[str, ...], list[tuple[str, tuple[str, int]]]] = defaultdict(list)
    overlap: Counter[tuple[tuple[str, int], tuple[str, int]]] = Counter()
    for page_key, (split, page_text) in selected_pages.items():
        for shingle in _shingles(page_text, page_attribution=True):
            owners = page_owners[shingle]
            for previous_split, previous_key in owners:
                if previous_split != split:
                    pair = tuple(sorted((previous_key, page_key)))
                    overlap[pair] += 1
                    require(overlap[pair] < 8, "cross_split_page_shingle_leakage")
            owners.append((split, page_key))


def _evidence(path_value: object, expected_sha: object, limit: int = MAX_EVIDENCE_BYTES) -> tuple[dict, str]:
    require(text_field(path_value, 1000) and sha_field(expected_sha), "evidence_reference")
    path = Path(path_value)
    require(path.is_absolute() and not path.is_symlink() and
            Path(gettempdir()).resolve() in path.resolve().parents, "evidence_temp_path")
    raw = file_bytes(path, limit)
    actual = digest(raw)
    require(actual == expected_sha, "evidence_hash")
    try:
        data = json.loads(raw, object_pairs_hook=_unique_pairs)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FixtureError("evidence_json") from exc
    require(type(data) is dict, "evidence_json")
    return data, actual


def _review_labels(value: object, author: str, page: bool, cue: bool) -> None:
    require(type(value) is dict and set(value) == {"reviews", "adjudication"}, "review_structure")
    reviews = value["reviews"]
    require(type(reviews) is list and len(reviews) == 2, "two_independent_reviews")
    ids: list[str] = []
    opinions: list[tuple[bool, bool]] = []
    for review in reviews:
        require(type(review) is dict and set(review) == {
            "reviewer_id", "original_page_useful", "exact_cue_useful"}, "review_fields")
        reviewer = review["reviewer_id"]
        require(text_field(reviewer, 100) and reviewer != author, "reviewer_independence")
        p, c = review["original_page_useful"], review["exact_cue_useful"]
        require(type(p) is bool and type(c) is bool and (not c or p), "review_label")
        ids.append(reviewer)
        opinions.append((p, c))
    require(len(set(ids)) == 2, "duplicate_reviewer")
    resolved = value["adjudication"]
    require(type(resolved) is dict and set(resolved) == {
        "reviewer_ids", "original_page_useful", "exact_cue_useful", "resolution"}, "adjudication_fields")
    require(type(resolved["reviewer_ids"]) is list and
            set(resolved["reviewer_ids"]) == set(ids) and len(resolved["reviewer_ids"]) == 2,
            "adjudication_participants")
    require(type(resolved["original_page_useful"]) is bool and
            type(resolved["exact_cue_useful"]) is bool and
            (resolved["original_page_useful"], resolved["exact_cue_useful"]) == (page, cue) and
            (not cue or page), "adjudicated_label")
    expected = "agreement" if opinions[0] == opinions[1] else "resolved_disagreement"
    require(resolved["resolution"] in
            ({"agreement", "resolved_uncertainty"} if expected == "agreement"
             else {"resolved_disagreement"}), "adjudication_resolution")
    if resolved["resolution"] == "agreement":
        require(opinions[0] == (page, cue), "review_agreement_mismatch")


def _review_rows(review: dict, packet_sha: str, packet_candidates: dict[str, tuple],
                 author_by_candidate: dict[str, str]) -> tuple[str, dict[str, dict]]:
    reviewer = review.get("reviewer_id")
    rows = review.get("judgments")
    require(text_field(reviewer, 100) and review.get("packet_sha256") == packet_sha and
            review.get("reviewed_group_count") == 96 and
            review.get("reviewed_candidate_count") == 384 and
            type(rows) is list and len(rows) == 384, "review_receipt")
    by_id: dict[str, dict] = {}
    for row in rows:
        require(type(row) is dict and set(row) == {
            "id", "group_id", "source_pdf", "page_number", "original_page_useful",
            "exact_visible_cue_useful", "uncertain", "reason"}, "review_row")
        cid = row["id"]
        require(type(cid) is str and cid in packet_candidates and cid not in by_id and
                (row["group_id"], row["source_pdf"], row["page_number"]) ==
                packet_candidates[cid] and
                type(row["original_page_useful"]) is bool and
                type(row["exact_visible_cue_useful"]) is bool and
                type(row["uncertain"]) is bool and
                (not row["exact_visible_cue_useful"] or row["original_page_useful"]) and
                text_field(row["reason"], 1000) and
                reviewer != author_by_candidate[cid], "review_row")
        by_id[cid] = row
    require(set(by_id) == set(packet_candidates), "review_coverage")
    return reviewer, by_id


def _review_batch(batch: dict, fixture: dict, groups_by_id: dict[str, dict],
                  document_by_sha: dict[str, dict]) -> dict[str, str]:
    keys = {"scope", "author_draft_path", "author_draft_sha256",
            "blind_packet_path", "blind_packet_sha256", "opaque_mapping_path",
            "opaque_mapping_sha256", "review_a_path", "review_a_sha256",
            "review_b_path", "review_b_sha256", "adjudication_path",
            "adjudication_sha256"}
    require(type(batch) is dict and set(batch) == keys and
            batch["scope"] in {"train", "evaluation"}, "review_batch")
    draft, _ = _evidence(batch["author_draft_path"], batch["author_draft_sha256"])
    packet, packet_sha = _evidence(batch["blind_packet_path"], batch["blind_packet_sha256"])
    mapping, _ = _evidence(batch["opaque_mapping_path"], batch["opaque_mapping_sha256"])
    first, _ = _evidence(batch["review_a_path"], batch["review_a_sha256"])
    second, _ = _evidence(batch["review_b_path"], batch["review_b_sha256"])
    adjudication, _ = _evidence(batch["adjudication_path"], batch["adjudication_sha256"])
    require(packet.get("schema") == "cardchemy_reading_usefulness_blind_review_v2" and
            packet.get("corpus_id") == fixture["corpus_id"] and
            packet.get("manifest_sha256") == fixture["manifest_sha256"] and
            type(packet.get("groups")) is list and len(packet["groups"]) == 96,
            "blind_packet_identity")
    require(draft.get("status") in {
            "author_only_pending_independent_blind_review_and_adjudication_no_model_score",
            "AUTHOR DRAFT ONLY; provisional labels; no independent reviews, rights review, adjudication, freeze, or model score"} and
            draft.get("corpus_id") == fixture["corpus_id"] and
            draft.get("manifest_sha256") == fixture["manifest_sha256"] and
            type(draft.get("groups")) is list and len(draft["groups"]) == 96 and
            all(type(group) is dict and type(group.get("id")) is str
                for group in draft["groups"]), "author_draft_identity")
    draft_groups = {group["id"]: group for group in draft["groups"]}
    require(len(draft_groups) == 96, "author_draft_identity")
    require(mapping.get("schema") == "cardchemy_reading_usefulness_blind_mapping_v1" and
            mapping.get("author_draft_sha256") == batch["author_draft_sha256"] and
            mapping.get("blind_packet_sha256") == packet_sha and
            type(mapping.get("groups")) is list and len(mapping["groups"]) == 96,
            "opaque_mapping_identity")
    expected_scope = {"train"} if batch["scope"] == "train" else {"calibration", "heldout"}
    require(all(type(group) is dict and type(group.get("id")) is str
                for group in packet["groups"]), "opaque_group_identity")
    packet_groups = {group["id"]: group for group in packet["groups"]}
    require(len(packet_groups) == 96 and all(
                re.fullmatch(r"g_[0-9a-f]{24}", key) is not None
                for key in packet_groups), "opaque_group_identity")
    candidate_identity: dict[str, tuple] = {}
    author_by_candidate: dict[str, str] = {}
    fixture_by_candidate: dict[str, tuple[dict, int]] = {}
    mapped_author_ids: set[str] = set()
    for entry in mapping["groups"]:
        require(type(entry) is dict and set(entry) == {
            "opaque_group_id", "author_group_id", "split", "candidates"}, "opaque_mapping_fields")
        opaque_id, author_id, split = (entry[key] for key in
                                       ("opaque_group_id", "author_group_id", "split"))
        require(opaque_id in packet_groups and author_id in groups_by_id and
                author_id in draft_groups and
                author_id not in mapped_author_ids and split in expected_scope and
                groups_by_id[author_id]["split"] == split and
                draft_groups[author_id].get("split") == split and
                type(entry["candidates"]) is list and len(entry["candidates"]) == 4,
                "opaque_mapping_group")
        mapped_author_ids.add(author_id)
        projected = packet_groups[opaque_id]
        group = groups_by_id[author_id]
        authored = draft_groups[author_id]
        sha = group["source_document_sha256"]
        require(all(authored.get(key) == group[key] for key in (
                    "id", "split", "relation_family", "question_form", "question",
                    "prior_question_context_if_followup", "source_document_sha256")) and
                authored.get("source_document_path_author_aid", authored.get("source_pdf")) ==
                document_by_sha[sha]["path"] and
                authored.get("four_exact_candidate_windows") ==
                group["four_exact_candidate_windows"] and
                authored.get("page_number_and_text_offsets_for_each_window") ==
                group["page_number_and_text_offsets_for_each_window"],
                "author_draft_projection_mismatch")
        require(set(projected) == {"id", "relation_family", "question_form", "question",
                    "prior_question_context_if_followup", "source_document_sha256",
                    "source_document_path_author_aid", "candidates"} and
                projected["relation_family"] == group["relation_family"] and
                projected["question_form"] == group["question_form"] and
                projected["question"] == group["question"] and
                projected["prior_question_context_if_followup"] ==
                group["prior_question_context_if_followup"] and
                projected["source_document_sha256"] == sha and
                projected["source_document_path_author_aid"] == document_by_sha[sha]["path"] and
                type(projected["candidates"]) is list and len(projected["candidates"]) == 4,
                "blind_projection_mismatch")
        require(all(type(row) is dict and type(row.get("id")) is str
                    for row in projected["candidates"]), "opaque_candidate_identity")
        candidates = {row["id"]: row for row in projected["candidates"]}
        require(len(candidates) == 4 and all(
                    re.fullmatch(r"c_[0-9a-f]{24}", cid) is not None
                    for cid in candidates), "opaque_candidate_identity")
        seen_indices: set[int] = set()
        for mapped in entry["candidates"]:
            require(type(mapped) is dict and set(mapped) == {
                "opaque_candidate_id", "author_candidate_index"}, "opaque_candidate_mapping")
            cid, index = mapped["opaque_candidate_id"], mapped["author_candidate_index"]
            require(cid in candidates and cid not in candidate_identity and
                    type(index) is int and 0 <= index < 4 and index not in seen_indices,
                    "opaque_candidate_mapping")
            seen_indices.add(index)
            candidate = candidates[cid]
            require(set(candidate) == {"id", "exact_window", "source_offset"} and
                    candidate["exact_window"] == group["four_exact_candidate_windows"][index] and
                    candidate["source_offset"] ==
                    group["page_number_and_text_offsets_for_each_window"][index],
                    "blind_projection_mismatch")
            candidate_identity[cid] = (opaque_id, document_by_sha[sha]["path"],
                                       candidate["source_offset"]["page_number"])
            author_by_candidate[cid] = group["authored_by"]
            fixture_by_candidate[cid] = (group, index)
        require(seen_indices == {0, 1, 2, 3}, "opaque_candidate_mapping")
    require(set(packet_groups) == {entry["opaque_group_id"] for entry in mapping["groups"]} and
            len(candidate_identity) == 384 and
            mapped_author_ids == set(draft_groups) and
            mapped_author_ids == {gid for gid, group in groups_by_id.items()
                                  if group["split"] in expected_scope}, "review_mapping_coverage")
    first_id, a = _review_rows(first, packet_sha, candidate_identity, author_by_candidate)
    second_id, b = _review_rows(second, packet_sha, candidate_identity, author_by_candidate)
    require(first_id != second_id and
            batch["review_a_sha256"] != batch["review_b_sha256"], "reviewer_independence")
    require(adjudication.get("schema") == "cardchemy_reading_usefulness_adjudication_v1" and
            adjudication.get("blind_packet_sha256") == packet_sha and
            adjudication.get("review_sha256") ==
            sorted((batch["review_a_sha256"], batch["review_b_sha256"])) and
            type(adjudication.get("rows")) is list, "adjudication_receipt")
    resolved: dict[str, dict] = {}
    for row in adjudication["rows"]:
        require(type(row) is dict and set(row) == {"candidate_id", "adjudicator_id",
            "original_page_useful", "exact_cue_useful", "resolution_reason"},
            "adjudication_receipt")
        cid = row["candidate_id"]
        require(type(cid) is str and cid in candidate_identity and cid not in resolved and
                text_field(row["adjudicator_id"], 100) and
                row["adjudicator_id"] not in
                {first_id, second_id, author_by_candidate[cid]} and
                type(row["original_page_useful"]) is bool and
                type(row["exact_cue_useful"]) is bool and
                (not row["exact_cue_useful"] or row["original_page_useful"]) and
                text_field(row["resolution_reason"], 1000), "adjudication_receipt")
        resolved[cid] = row
    needed: set[str] = set()
    for cid, (group, index) in fixture_by_candidate.items():
        left, right = a[cid], b[cid]
        opinions = [(row["original_page_useful"], row["exact_visible_cue_useful"])
                    for row in (left, right)]
        uncertain = left["uncertain"] or right["uncertain"]
        disagreement = opinions[0] != opinions[1]
        fixture_review = group["independent_reviewer_ids_and_adjudication"][index]
        expected_reviews = {(first_id, *opinions[0]), (second_id, *opinions[1])}
        actual_reviews = {(row["reviewer_id"], row["original_page_useful"],
                           row["exact_cue_useful"]) for row in fixture_review["reviews"]}
        require(actual_reviews == expected_reviews, "review_receipt_mismatch")
        final = (group["original_page_usefulness_per_window"][index],
                 group["exact_cue_usefulness_per_window"][index])
        if uncertain or disagreement:
            needed.add(cid)
            require(cid in resolved and
                    final == (resolved[cid]["original_page_useful"],
                              resolved[cid]["exact_cue_useful"]) and
                    fixture_review["adjudication"]["resolution"] ==
                    ("resolved_disagreement" if disagreement else "resolved_uncertainty"),
                    "unresolved_review")
        else:
            require(cid not in resolved and final == opinions[0] and
                    fixture_review["adjudication"]["resolution"] == "agreement",
                    "review_receipt_mismatch")
    require(set(resolved) == needed, "adjudication_coverage")
    return {key: batch[key] for key in keys if key.endswith("sha256")}


def _external_evidence(fixture: dict, groups_by_id: dict[str, dict],
                       document_by_sha: dict[str, dict]) -> dict[str, object]:
    refs = fixture["review_evidence"]
    require(type(refs) is dict and set(refs) == {"batches",
            "semantic_leakage_audit_path", "semantic_leakage_audit_sha256",
            "rights_audit_path", "rights_audit_sha256"} and
            type(refs["batches"]) is list and len(refs["batches"]) == 2 and
            {row.get("scope") for row in refs["batches"] if type(row) is dict} ==
            {"train", "evaluation"}, "review_evidence")
    batch_pins = [_review_batch(batch, fixture, groups_by_id, document_by_sha)
                  for batch in refs["batches"]]
    groups = fixture["groups"]
    groups_sha = digest(corpus.canonical_bytes(groups))
    authors = {group["authored_by"] for group in groups}
    semantic, _ = _evidence(refs["semantic_leakage_audit_path"],
                            refs["semantic_leakage_audit_sha256"])
    doc_pairs = sorted([left, right] for left, first in document_by_sha.items()
                       for right, second in document_by_sha.items()
                       if left < right and first["split"] != second["split"])
    require(set(semantic) == {"schema", "manifest_sha256", "groups_sha256",
            "reviewer_id", "reviewed_group_ids", "reviewed_cross_split_document_pairs",
            "source_and_template_disjoint", "no_semantic_question_or_template_overlap",
            "no_paraphrase_or_page_text_leakage", "basis"} and
            semantic["schema"] == "cardchemy_reading_usefulness_semantic_leakage_audit_v1" and
            semantic["manifest_sha256"] == fixture["manifest_sha256"] and
            semantic["groups_sha256"] == groups_sha and
            text_field(semantic["reviewer_id"], 100) and
            semantic["reviewer_id"] not in authors and
            semantic["reviewed_group_ids"] == sorted(groups_by_id) and
            semantic["reviewed_cross_split_document_pairs"] == doc_pairs and
            semantic["source_and_template_disjoint"] is True and
            semantic["no_semantic_question_or_template_overlap"] is True and
            semantic["no_paraphrase_or_page_text_leakage"] is True and
            text_field(semantic["basis"], 2000), "semantic_leakage_audit")
    rights, _ = _evidence(refs["rights_audit_path"], refs["rights_audit_sha256"])
    require(set(rights) == {"schema", "manifest_sha256", "groups_sha256",
            "reviewer_id", "candidate_reviews"} and
            rights["schema"] == "cardchemy_reading_usefulness_candidate_rights_audit_v1" and
            rights["manifest_sha256"] == fixture["manifest_sha256"] and
            rights["groups_sha256"] == groups_sha and
            text_field(rights["reviewer_id"], 100) and
            rights["reviewer_id"] not in authors and
            type(rights["candidate_reviews"]) is list and
            len(rights["candidate_reviews"]) == 768, "candidate_rights_audit")
    expected: dict[tuple[str, int], tuple] = {}
    for group in groups:
        for index, (window, offset) in enumerate(zip(
                group["four_exact_candidate_windows"],
                group["page_number_and_text_offsets_for_each_window"], strict=True)):
            expected[(group["id"], index)] = (
                group["source_document_sha256"], offset["page_number"],
                offset["start"], offset["end"], digest(window.encode("utf-8")))
    seen: set[tuple[str, int]] = set()
    for row in rights["candidate_reviews"]:
        require(type(row) is dict and set(row) == {"group_id", "candidate_index",
            "source_document_sha256", "page_number", "start", "end",
            "exact_window_sha256", "page_rights_clear", "cue_rights_clear",
            "third_party_material_excluded", "basis"}, "candidate_rights_row")
        require(type(row["group_id"]) is str and type(row["candidate_index"]) is int,
                "candidate_rights_row")
        key = (row["group_id"], row["candidate_index"])
        require(key in expected and key not in seen and
                (row["source_document_sha256"], row["page_number"], row["start"],
                 row["end"], row["exact_window_sha256"]) == expected[key] and
                row["page_rights_clear"] is True and
                row["cue_rights_clear"] is True and
                row["third_party_material_excluded"] is True and
                text_field(row["basis"], 1000), "candidate_rights_row")
        seen.add(key)
    require(seen == set(expected), "candidate_rights_coverage")
    return {"review_batches": batch_pins,
            "semantic_leakage_audit_sha256": refs["semantic_leakage_audit_sha256"],
            "rights_audit_sha256": refs["rights_audit_sha256"]}


def validate(root: Path, fixture_path: Path) -> dict[str, object]:
    require(root.is_dir() and not root.is_symlink(), "corpus_root")
    prereg, prereg_raw = read_json(root / "preregistration.json", 32_768)
    manifest, manifest_raw = read_json(root / "manifest.json", 64_000)
    plan, plan_raw = read_json(root / "empty_fixture_plan.json", 32_768)
    derivation, derivation_raw = read_json(root / "derivation_receipt.json", 32_768)
    fixture, fixture_raw = read_json(fixture_path, MAX_FIXTURE_BYTES)
    require(prereg == derived.preregistration_v4(corpus.preregistration()) and
            digest(prereg_raw) == CORPUS_PREREGISTRATION_SHA256,
            "preregistration_identity")
    require(digest(manifest_raw) == CORPUS_MANIFEST_SHA256, "corpus_manifest_pin")
    require(manifest.get("schema") == "cardchemy_public_reading_corpus_manifest_v1" and
            manifest.get("corpus_id") == derived.V4_CORPUS_ID and
            manifest.get("preregistration_sha256") == digest(prereg_raw) and
            manifest.get("index_url") == corpus.INDEX_URL and
            manifest.get("license_url") == corpus.LICENSE_URL and
            manifest.get("all_pdf_first_pages_cc_by_4") is True and
            manifest.get("labels_written") is False and
            manifest.get("derived_from") == derived._parent_provenance() and
            manifest.get("local_copied_pdf_bytes") ==
            sum(row["bytes"] for row in manifest.get("documents", [])
                if type(row) is dict and type(row.get("bytes")) is int),
            "manifest_identity")
    require(type(manifest.get("requests_including_redirects")) is int and
            manifest["requests_including_redirects"] <= corpus.MAX_GETS and
            type(manifest.get("received_bytes")) is int and
            manifest["received_bytes"] <= corpus.MAX_BYTES and
            type(manifest.get("elapsed_seconds")) in (int, float) and
            0 <= manifest["elapsed_seconds"] <= corpus.MAX_ELAPSED_SECONDS,
            "manifest_budget")
    require(plan == derived.empty_fixture_plan_v4(
                corpus.empty_fixture_plan(derived.V3_MANIFEST_SHA256),
                digest(manifest_raw)) and
            digest(plan_raw) == CORPUS_PLAN_SHA256, "fixture_plan_identity")
    require(digest(derivation_raw) == CORPUS_DERIVATION_RECEIPT_SHA256 and
            derivation.get("schema") ==
            "cardchemy_public_reading_corpus_local_derivation_receipt_v1" and
            derivation.get("corpus_id") == derived.V4_CORPUS_ID and
            derivation.get("derived_from") == derived._parent_provenance() and
            derivation.get("preregistration_sha256") == digest(prereg_raw) and
            derivation.get("manifest_sha256") == digest(manifest_raw) and
            derivation.get("empty_fixture_plan_sha256") == digest(plan_raw) and
            derivation.get("documents") == 14 and
            derivation.get("requests_including_redirects") == 0 and
            derivation.get("provider_calls") == 0 and
            derivation.get("model_scores") == 0 and
            derivation.get("labels_written") is False,
            "derivation_identity")
    require(set(fixture) == {"schema", "corpus_id", "manifest_sha256", "plan_sha256",
                             "extractor", "review_protocol", "document_rights_reviews",
                             "review_evidence", "groups"} and
            fixture["schema"] == FIXTURE_SCHEMA and
            fixture["corpus_id"] == derived.V4_CORPUS_ID and
            fixture["manifest_sha256"] == digest(manifest_raw) and
            fixture["plan_sha256"] == digest(plan_raw), "fixture_identity")
    require(fixture["extractor"] == {"name": "pypdf", "version": pypdf.__version__},
            "extractor_identity")
    require(fixture["review_protocol"] == {
        "independent_authors_and_blinded_reviewers": True,
        "adjudicated_before_first_model_score": True,
        "no_private_or_prior_scored_source": True,
    }, "review_protocol")

    docs = manifest.get("documents")
    require(type(docs) is list and len(docs) == 14, "document_count")
    expected_urls = {url: split for split, urls in prereg["splits"].items() for url in urls}
    document_by_sha: dict[str, dict] = {}
    page_texts: dict[str, list[str]] = {}
    used_urls: set[str] = set()
    normalized_pages: dict[str, str] = {}
    for doc in docs:
        require(type(doc) is dict and set(doc) == {"split", "url", "path", "bytes",
            "sha256", "license_url", "pages", "alphanumeric_text_chars",
            "pages_with_at_least_40_alphanumeric_chars", "first_page_license"}, "document_fields")
        split, url, name, sha = (doc[key] for key in ("split", "url", "path", "sha256"))
        require(url in expected_urls and expected_urls[url] == split and url not in used_urls and
                name == url.rsplit("/", 1)[-1] and re.fullmatch(r"lec\d{2}[.]pdf", name) and
                sha_field(sha) and sha not in document_by_sha and
                doc["license_url"] == corpus.LICENSE_URL and
                doc["first_page_license"] == "CC BY 4.0", "document_identity")
        used_urls.add(url)
        path = root / name
        raw = file_bytes(path, corpus.MAX_PDF_BYTES)
        require(type(doc["bytes"]) is int and len(raw) == doc["bytes"] and digest(raw) == sha,
                "document_hash")
        reader = PdfReader(path, strict=False)
        require(not reader.is_encrypted and type(doc["pages"]) is int and
                len(reader.pages) == doc["pages"] and 1 <= doc["pages"] <= corpus.MAX_PDF_PAGES,
                "document_pages")
        texts = [(page.extract_text() or "") for page in reader.pages]
        require(bool(corpus.LICENSE_RE.search(texts[0])), "document_license_notice")
        counts = [sum(ch.isalnum() for ch in value) for value in texts]
        require(sum(counts) == doc["alphanumeric_text_chars"] and
                sum(count >= 40 for count in counts) == doc["pages_with_at_least_40_alphanumeric_chars"] and
                sum(counts) >= 1500 and sum(count >= 40 for count in counts) >= max(3, len(texts) // 3),
                "document_text_quality")
        for page_text in texts:
            key = _normalized(page_text)
            if len(key) >= 40:
                previous = normalized_pages.get(key)
                require(previous is None or previous == split, "cross_split_page_text_leakage")
                normalized_pages[key] = split
        document_by_sha[sha] = doc
        page_texts[sha] = texts
    require(used_urls == set(expected_urls), "document_roster")

    rights = fixture["document_rights_reviews"]
    require(type(rights) is list and len(rights) == len(docs), "rights_review_count")
    rights_seen: set[str] = set()
    for row in rights:
        require(type(row) is dict and set(row) == {"source_document_sha256", "reviewer_id",
                "license_url", "notice_page_number", "text_reuse_permitted",
                "third_party_material_excluded"}, "rights_review_fields")
        sha = row["source_document_sha256"]
        require(sha in document_by_sha and sha not in rights_seen and
                text_field(row["reviewer_id"], 100) and
                row["license_url"] == corpus.LICENSE_URL and
                type(row["notice_page_number"]) is int and row["notice_page_number"] == 1 and
                row["text_reuse_permitted"] is True and
                row["third_party_material_excluded"] is True, "rights_review")
        rights_seen.add(sha)
    require(rights_seen == set(document_by_sha), "rights_review_coverage")

    groups = fixture["groups"]
    require(type(groups) is list and len(groups) == 192, "group_count")
    split_counts: Counter[str] = Counter()
    useful_counts: Counter[tuple[str, int]] = Counter()
    relation_form_counts: Counter[tuple[str, str, str]] = Counter()
    form_positive_counts: Counter[tuple[str, str]] = Counter()
    ids: set[str] = set()
    groups_by_id: dict[str, dict] = {}
    used_docs: set[str] = set()
    template_owners: dict[str, str] = {}
    question_owners: dict[str, str] = {}
    window_owners: dict[str, str] = {}
    selected_pages: dict[tuple[str, int], tuple[str, str]] = {}
    selected_windows: list[tuple[str, str]] = []
    for group in groups:
        require(type(group) is dict and set(group) == GROUP_KEYS, "group_fields")
        gid, split, sha = (group[key] for key in ("id", "split", "source_document_sha256"))
        require(text_field(gid, 64) and gid not in ids and split in SPLIT_COUNTS and
                sha in document_by_sha and document_by_sha[sha]["split"] == split,
                "group_identity")
        ids.add(gid)
        groups_by_id[gid] = group
        used_docs.add(sha)
        form, relation = group["question_form"], group["relation_family"]
        require(form in FORMS and relation in RELATIONS, "group_stratum")
        require(text_field(group["question"], 1000) and
                text_field(group["question_template_id"], 100) and
                text_field(group["question_template"], 500) and
                text_field(group["authored_by"], 100), "group_text")
        prior = group["prior_question_context_if_followup"]
        require((text_field(prior, 500) if form == "follow-up" else prior is None), "followup_context")
        author = group["authored_by"]
        leakage = group["leakage_review"]
        require(type(leakage) is dict and set(leakage) == {"reviewer_id",
                "source_and_template_disjoint", "no_paraphrase_or_page_text_leakage"} and
                text_field(leakage["reviewer_id"], 100) and leakage["reviewer_id"] != author and
                leakage["source_and_template_disjoint"] is True and
                leakage["no_paraphrase_or_page_text_leakage"] is True, "leakage_review")
        for value, owners, code in (
            (group["question_template_id"], template_owners, "cross_split_template_id"),
            (_normalized(group["question_template"]), template_owners, "cross_split_template_text"),
            (_normalized(group["question"]), question_owners, "cross_split_question"),
        ):
            require(owners.get(value, split) == split, code)
            owners[value] = split
        windows = group["four_exact_candidate_windows"]
        offsets = group["page_number_and_text_offsets_for_each_window"]
        pages = group["original_page_usefulness_per_window"]
        cues = group["exact_cue_usefulness_per_window"]
        reviews = group["independent_reviewer_ids_and_adjudication"]
        require(all(type(value) is list and len(value) == 4 for value in
                    (windows, offsets, pages, cues, reviews)), "four_candidate_arrays")
        page_numbers: set[int] = set()
        useful = 0
        for index in range(4):
            window, offset, page, cue = windows[index], offsets[index], pages[index], cues[index]
            require(exact_window_field(window) and type(offset) is dict and
                    set(offset) == {"page_number", "start", "end", "page_text_sha256"} and
                    type(offset["page_number"]) is int and type(offset["start"]) is int and
                    type(offset["end"]) is int and type(page) is bool and type(cue) is bool and
                    (not cue or page), "candidate_fields")
            number, start, end = offset["page_number"], offset["start"], offset["end"]
            require(1 <= number <= len(page_texts[sha]) and number not in page_numbers and
                    0 <= start < end <= len(page_texts[sha][number - 1]) and
                    sha_field(offset["page_text_sha256"]) and
                    digest(page_texts[sha][number - 1].encode("utf-8")) == offset["page_text_sha256"] and
                    page_texts[sha][number - 1][start:end] == window, "exact_window_offset")
            page_numbers.add(number)
            selected_pages[(sha, number)] = (split, page_texts[sha][number - 1])
            selected_windows.append((split, window))
            key = _normalized(window)
            require(window_owners.get(key, split) == split, "cross_split_window_text")
            window_owners[key] = split
            _review_labels(reviews[index], author, page, cue)
            useful += page and cue
        require(useful <= 3, "useful_count_limit")
        split_counts[split] += 1
        useful_counts[(split, useful)] += 1
        relation_form_counts[(split, relation, form)] += 1
        form_positive_counts[(split, form)] += useful > 0
    require(used_docs == set(document_by_sha), "unused_source_document")
    require(dict(split_counts) == SPLIT_COUNTS, "split_counts")
    for split in SPLIT_COUNTS:
        for count in range(4):
            require(useful_counts[(split, count)] == USEFUL_COUNTS[split], "useful_count_strata")
        per_pair = SPLIT_COUNTS[split] // (len(RELATIONS) * len(FORMS))
        for relation in RELATIONS:
            for form in FORMS:
                require(relation_form_counts[(split, relation, form)] == per_pair,
                        "relation_form_strata")
        for form in FORMS:
            require(form_positive_counts[(split, form)] ==
                    3 * USEFUL_COUNTS[split] // len(FORMS),
                    "positive_form_strata")
    _cross_split_shingles(selected_pages, selected_windows)
    evidence_pins = _external_evidence(fixture, groups_by_id, document_by_sha)
    return {"status": "fixture_validated_no_scoring", "groups": len(groups),
            "documents": len(docs), "fixture_sha256": digest(fixture_raw),
            "manifest_sha256": digest(manifest_raw), "plan_sha256": digest(plan_raw),
            "preregistration_sha256": digest(prereg_raw),
            "derivation_receipt_sha256": digest(derivation_raw),
            "evidence_pins": evidence_pins}


def frozen_inputs(root: Path, fixture: Path, harness: Path, runtime: Path,
                  bundle_manifest: Path) -> dict[str, str]:
    validated = validate(root, fixture)
    require(digest(file_bytes(bundle_manifest, 64_000)) == MODEL_BUNDLE_MANIFEST_SHA256,
            "model_bundle_manifest_pin")
    return {"preregistration_sha256": validated["preregistration_sha256"],
            "corpus_manifest_sha256": validated["manifest_sha256"],
            "fixture_plan_sha256": validated["plan_sha256"],
            "corpus_derivation_receipt_sha256": validated["derivation_receipt_sha256"],
            "fixture_sha256": validated["fixture_sha256"],
             "evidence_pins": validated["evidence_pins"],
            "validator_sha256": digest(file_bytes(Path(__file__), 200_000)),
            "scoring_harness_sha256": digest(file_bytes(harness, 500_000)),
            "runtime_manifest_sha256": digest(file_bytes(runtime, 100_000)),
            "model_bundle_manifest_sha256": MODEL_BUNDLE_MANIFEST_SHA256}


def freeze(root: Path, fixture: Path, harness: Path, runtime: Path,
           bundle_manifest: Path, receipt: Path) -> dict[str, object]:
    pins = frozen_inputs(root, fixture, harness, runtime, bundle_manifest)
    body = corpus.canonical_bytes({"schema": FREEZE_SCHEMA, "corpus_id": derived.V4_CORPUS_ID,
                                   "pins": pins})
    require(not receipt.is_symlink(), "freeze_symlink")
    with receipt.open("xb") as stream:
        stream.write(body)
    return {"status": "frozen_no_scoring", "freeze_sha256": digest(body), **pins}


def verify(root: Path, fixture: Path, harness: Path, runtime: Path,
           bundle_manifest: Path, receipt: Path, expected_sha256: str) -> dict[str, object]:
    require(sha_field(expected_sha256), "expected_freeze_sha256")
    saved, raw = read_json(receipt, 4096)
    require(digest(raw) == expected_sha256 and saved.get("schema") == FREEZE_SCHEMA and
            saved.get("corpus_id") == derived.V4_CORPUS_ID and
            saved.get("pins") == frozen_inputs(root, fixture, harness, runtime, bundle_manifest),
            "freeze_mismatch")
    return {"status": "frozen_inputs_verified_no_scoring", "freeze_sha256": expected_sha256}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("validate", "freeze", "verify"))
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--harness", type=Path)
    parser.add_argument("--runtime-manifest", type=Path)
    parser.add_argument("--bundle-manifest", type=Path)
    parser.add_argument("--freeze-receipt", type=Path)
    parser.add_argument("--expected-freeze-sha256")
    args = parser.parse_args(argv)
    try:
        if args.mode == "validate":
            result = validate(args.corpus, args.fixture)
        else:
            require(all((args.harness, args.runtime_manifest, args.bundle_manifest,
                         args.freeze_receipt)), "freeze_arguments")
            if args.mode == "freeze":
                result = freeze(args.corpus, args.fixture, args.harness,
                                args.runtime_manifest, args.bundle_manifest, args.freeze_receipt)
            else:
                result = verify(args.corpus, args.fixture, args.harness, args.runtime_manifest,
                                args.bundle_manifest, args.freeze_receipt,
                                args.expected_freeze_sha256 or "")
    except (FixtureError, OSError, ValueError) as exc:
        print(json.dumps({"status": "fixture_rejected_no_scoring",
                          "reason": str(exc) if isinstance(exc, FixtureError) else type(exc).__name__},
                         sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
