"""Prepare blind, offline original-PDF page-and-cue reviews for the fresh v2 pilot.

The question author supplies an authored slate; this tool does not create or
judge questions. Give reviewers only the blind packet, never the mapping. Two
reviewers label it independently; a third resolves only disagreements. The
default 96-group packet remains tied to the original freezer. The separate
reserve_v1 profile prepares 30 groups and returns author-ID review material
for its own later admission gate.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import secrets
import tempfile

import prepare_fresh_public_source_id_v2 as freezer


BLIND_SCHEMA = "fresh_public_source_id_v2_blind_packet"
MAPPING_SCHEMA = "fresh_public_source_id_v2_blind_mapping"
RESPONSE_SCHEMA = "fresh_public_source_id_v2_blind_review"
DISPUTES_SCHEMA = "fresh_public_source_id_v2_blind_disputes"
ADJUDICATION_RESPONSE_SCHEMA = "fresh_public_source_id_v2_blind_adjudication"
RESERVE_AUTHORED_SCHEMA = "fresh_public_source_id_v2_reserve_authored"
RESERVE_PROFILE = "reserve_v1"
RESERVE_FORMS = ("direct", "paraphrase", "followup")
RESERVE_SPLIT_COUNTS = {"calibration": 6, "heldout": 4}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise freezer.FreezeError(message)


def _shuffle_key(salt: str, kind: str, value: str) -> str:
    return freezer.sha256_bytes(f"{salt}:{kind}:{value}".encode("utf-8"))


def build_blind_packet(authored: dict, pages: dict[tuple[str, int], str],
                       documents: list[dict], source_manifest_sha256: str,
                       overlap_review_sha256: str,
                       excluded_pages: set[tuple[str, int]],
                       pdf_paths: dict[str, Path], *, salt: str,
                       reserve: bool = False) -> tuple[dict, dict]:
    """Return reviewer-only material and a separate author-ID mapping."""
    _require(type(reserve) is bool, "invalid blind review profile")
    freezer._keys(authored, {"schema_version", "corpus_id", "source_manifest_sha256",
                            "overlap_review_sha256", "author_id", "groups"})
    _require(authored["schema_version"] == (RESERVE_AUTHORED_SCHEMA if reserve else freezer.AUTHORED_SCHEMA) and
             authored["corpus_id"] == freezer.CORPUS_ID and
             authored["source_manifest_sha256"] == source_manifest_sha256 and
             authored["overlap_review_sha256"] == overlap_review_sha256,
             "authored slate identity mismatch")
    author_id = freezer._safe_id(authored["author_id"], "author ID")
    _require(isinstance(salt, str) and len(salt) == 64 and
             all(char in "0123456789abcdef" for char in salt), "invalid blind salt")
    groups = authored["groups"]
    expected_groups = 30 if reserve else 96
    _require(isinstance(groups, list) and len(groups) == expected_groups,
             f"authored slate needs {expected_groups} groups")
    split_docs = {split: {doc["document_id"] for doc in documents if doc["split"] == split}
                  for split in freezer.SPLITS}
    _require(all(len(split_docs[split]) == 4 for split in freezer.SPLITS) and
             not (split_docs["calibration"] & split_docs["heldout"]),
             "four disjoint PDFs per split required")
    _require(set(pdf_paths) == set(freezer.EXPECTED), "PDF path roster mismatch")
    document_sha256 = {doc["document_id"]: freezer._sha(doc["sha256"], "PDF SHA-256")
                       for doc in documents}
    prepared: list[tuple[str, dict, list[tuple[str, dict]]]] = []
    seen_groups: set[str] = set()
    strata = Counter()
    for group in groups:
        freezer._keys(group, {"group_id", "split", "form", "question", "candidates"})
        gid = freezer._safe_id(group["group_id"], "group ID")
        split, form = group["split"], group["form"]
        _require(gid not in seen_groups and split in freezer.SPLITS and
                 form in (RESERVE_FORMS if reserve else freezer.FORMS),
                 "group ID/split/form invalid")
        seen_groups.add(gid)
        question = freezer._nonempty(group["question"], "question", 1024)
        candidates = group["candidates"]
        _require(isinstance(candidates, list) and len(candidates) == 4,
                 "each group needs four candidates")
        candidate_rows: list[tuple[str, dict]] = []
        seen_ids: set[str] = set()
        represented_pages: set[tuple[str, int]] = set()
        represented_docs: set[str] = set()
        for candidate in candidates:
            freezer._keys(candidate, {"id", "document_id", "page", "context_start",
                                      "context_end", "cue_start", "cue_end"})
            cid = freezer._safe_id(candidate["id"], "candidate ID")
            did = freezer._safe_id(candidate["document_id"], "document ID")
            page = candidate["page"]
            _require(cid not in seen_ids and did in split_docs[split] and
                     type(page) is int and (did, page) in pages and
                     (did, page) not in excluded_pages and
                     (did, page) not in represented_pages,
                     "candidate ID/PDF/page invalid or overlaps prior corpus")
            seen_ids.add(cid)
            represented_docs.add(did)
            represented_pages.add((did, page))
            text = pages[(did, page)]
            start, end = candidate["context_start"], candidate["context_end"]
            cue_start, cue_end = candidate["cue_start"], candidate["cue_end"]
            _require(all(type(value) is int for value in (start, end, cue_start, cue_end)) and
                     0 <= start <= cue_start < cue_end <= end <= len(text),
                     "invalid or noncontiguous candidate offsets")
            context, cue = text[start:end], text[cue_start:cue_end]
            _require(0 < len(context) <= 1200 and 0 < len(cue) <= 480 and
                     bool(context.strip()) and bool(cue.strip()),
                     "candidate context/cue invalid")
            candidate_rows.append((cid, {
                "document_id": did, "document_sha256": document_sha256[did],
                "page": page,
                "pdf_uri": pdf_paths[did].resolve().as_uri() + f"#page={page}",
                "context": context, "cue": cue,
                "page_text_sha256": freezer.sha256_bytes(text.encode("utf-8")),
            }))
        _require(len(represented_docs) == 2, "exactly two PDFs per slate required")
        strata[(split, form)] += 1
        prepared.append((gid, {"question": question}, candidate_rows))
    if reserve:
        _require(all(strata[(split, form)] == RESERVE_SPLIT_COUNTS[split]
                     for split in freezer.SPLITS for form in RESERVE_FORMS),
                 "reserve split/form balance invalid")
    else:
        _require(all(strata[(split, form)] == 12 for split in freezer.SPLITS
                     for form in freezer.FORMS), "each split needs 12 groups per form")

    blind_groups: list[dict] = []
    mapping_groups: list[dict] = []
    for number, (gid, public, candidate_rows) in enumerate(
            sorted(prepared, key=lambda item: _shuffle_key(salt, "group", item[0])), start=1):
        blind_gid = f"G{number:03d}"
        blind_candidates: list[dict] = []
        candidate_mapping: list[dict] = []
        for position, (cid, fields) in enumerate(
                sorted(candidate_rows, key=lambda item: _shuffle_key(salt, f"candidate:{gid}", item[0])), start=1):
            blind_cid = f"S{position:02d}"
            blind_candidates.append({"id": blind_cid, **fields})
            candidate_mapping.append({"id": blind_cid, "author_id": cid})
        blind_groups.append({"group_id": blind_gid, **public, "candidates": blind_candidates})
        mapping_groups.append({"group_id": blind_gid, "author_group_id": gid,
                               "candidates": candidate_mapping})
    mapping_base = {"schema_version": MAPPING_SCHEMA, "corpus_id": freezer.CORPUS_ID,
                    "source_manifest_sha256": source_manifest_sha256,
                    "author_id": author_id, "groups": mapping_groups}
    if reserve:
        mapping_base["profile"] = RESERVE_PROFILE
    packet = {"schema_version": BLIND_SCHEMA, "corpus_id": freezer.CORPUS_ID,
              "source_manifest_sha256": source_manifest_sha256,
              "mapping_sha256": freezer.sha256_bytes(freezer.canonical_bytes(mapping_base)),
              "review_rule": "Judge whether the original PDF page is useful related reading for the exact requested entity, relation and conditions. Separately judge whether the displayed exact cue helps a reader find that relation on the page. A useful cue requires a useful page. Inspect the original PDF at the physical page number; do not infer labels from form or desired count.",
              "groups": blind_groups}
    if reserve:
        packet["profile"] = RESERVE_PROFILE
    mapping = {**mapping_base,
               "packet_sha256": freezer.sha256_bytes(freezer.canonical_bytes(packet))}
    return packet, mapping


def _review_index(packet: dict, mapping: dict, review: dict, *, expected_groups: int) -> tuple[str, dict[tuple[str, str], tuple[bool, bool]]]:
    freezer._keys(review, {"schema_version", "reviewer_id", "packet_sha256", "groups"})
    _require(review["schema_version"] == RESPONSE_SCHEMA and
             review["packet_sha256"] == mapping["packet_sha256"],
             "blind review identity mismatch")
    reviewer_id = freezer._safe_id(review["reviewer_id"], "reviewer ID")
    _require(reviewer_id != mapping["author_id"], "author cannot review own slate")
    groups = review["groups"]
    _require(isinstance(groups, list) and len(groups) == expected_groups,
             f"review needs {expected_groups} groups")
    roster = {group["group_id"]: {candidate["id"] for candidate in group["candidates"]}
              for group in packet["groups"]}
    indexed: dict[tuple[str, str], tuple[bool, bool]] = {}
    seen_groups: set[str] = set()
    for group in groups:
        freezer._keys(group, {"group_id", "candidates"})
        gid = freezer._safe_id(group["group_id"], "review group ID")
        _require(gid in roster and gid not in seen_groups, "review group mismatch")
        seen_groups.add(gid)
        candidates = group["candidates"]
        _require(isinstance(candidates, list) and len(candidates) == 4,
                 "review needs four candidates per group")
        for candidate in candidates:
            freezer._keys(candidate, {"id", "page_useful", "cue_useful"})
            cid = freezer._safe_id(candidate["id"], "review candidate ID")
            key = (gid, cid)
            page, cue = candidate["page_useful"], candidate["cue_useful"]
            _require(cid in roster[gid] and key not in indexed and
                     type(page) is bool and type(cue) is bool and (not cue or page),
                     "review candidate/label invalid")
            indexed[key] = (page, cue)
    _require(seen_groups == set(roster) and len(indexed) == expected_groups * 4,
             "incomplete review")
    return reviewer_id, indexed


def blank_review_template(packet: dict, packet_sha256: str) -> dict:
    """Supply structure only; every human page/cue decision remains empty."""
    return {"schema_version": RESPONSE_SCHEMA, "reviewer_id": None,
            "packet_sha256": packet_sha256,
            "groups": [{"group_id": group["group_id"], "candidates": [
                {"id": row["id"], "page_useful": None, "cue_useful": None}
                for row in group["candidates"]]}
                for group in packet["groups"]]}


def bridge_reviews(packet: dict, mapping: dict, review_a: dict, review_b: dict) -> tuple[dict, dict, dict]:
    """Return two freezer reviews and a conflict-only blind adjudication packet."""
    marked = "profile" in packet or "profile" in mapping
    if marked:
        _require(packet.get("profile") == mapping.get("profile") == RESERVE_PROFILE,
                 "blind profile mismatch")
        freezer._keys(packet, {"schema_version", "corpus_id", "source_manifest_sha256",
                               "mapping_sha256", "review_rule", "groups", "profile"})
        freezer._keys(mapping, {"schema_version", "corpus_id", "source_manifest_sha256",
                                "author_id", "groups", "packet_sha256", "profile"})
    expected_groups = 30 if marked else 96
    _require(packet.get("schema_version") == BLIND_SCHEMA and
             mapping.get("schema_version") == MAPPING_SCHEMA and
             mapping.get("packet_sha256") == freezer.sha256_bytes(freezer.canonical_bytes(packet)) and
             packet.get("mapping_sha256") == freezer.sha256_bytes(freezer.canonical_bytes(
                 {key: value for key, value in mapping.items() if key != "packet_sha256"})) and
             packet.get("source_manifest_sha256") == mapping.get("source_manifest_sha256") and
             packet.get("corpus_id") == mapping.get("corpus_id") == freezer.CORPUS_ID,
             "blind packet/mapping mismatch")
    _require(len(packet.get("groups", [])) == len(mapping.get("groups", [])) == expected_groups,
             "blind packet/mapping roster mismatch")
    if marked:
        expected_ids = {f"G{number:03d}" for number in range(1, expected_groups + 1)}
        _require({group["group_id"] for group in packet["groups"]} ==
                 {group["group_id"] for group in mapping["groups"]} == expected_ids,
                 "reserve blind group roster mismatch")
        mapped = {group["group_id"]: group for group in mapping["groups"]}
        author_groups: set[str] = set()
        split_counts = Counter()
        for group in packet["groups"]:
            freezer._keys(group, {"group_id", "question", "candidates"})
            freezer._nonempty(group["question"], "question", 1024)
            linked = mapped[group["group_id"]]
            freezer._keys(linked, {"group_id", "author_group_id", "candidates"})
            author_gid = freezer._safe_id(linked["author_group_id"], "author group ID")
            _require(author_gid not in author_groups, "reserve author group roster mismatch")
            author_groups.add(author_gid)
            candidates, candidate_mapping = group["candidates"], linked["candidates"]
            _require(isinstance(candidates, list) and len(candidates) == 4 and
                     isinstance(candidate_mapping, list) and len(candidate_mapping) == 4,
                     "reserve needs four candidates per group")
            for row in candidates:
                freezer._keys(row, {"id", "document_id", "document_sha256", "page",
                                    "pdf_uri", "context", "cue", "page_text_sha256"})
            for row in candidate_mapping:
                freezer._keys(row, {"id", "author_id"})
            source_ids = {f"S{number:02d}" for number in range(1, 5)}
            _require({row["id"] for row in candidates} ==
                     {row["id"] for row in candidate_mapping} == source_ids,
                     "reserve candidate roster mismatch")
            for row in candidates:
                _require(row["document_id"] in freezer.EXPECTED and
                         type(row["page"]) is int and
                         1 <= row["page"] <= freezer.EXPECTED[row["document_id"]][1] and
                         isinstance(row["pdf_uri"], str) and
                         row["pdf_uri"].endswith(f"#page={row['page']}") and
                         isinstance(row["context"], str) and
                         0 < len(row["context"]) <= 1200 and
                         isinstance(row["cue"], str) and
                         0 < len(row["cue"]) <= 480 and row["cue"] in row["context"],
                         "reserve candidate source invalid")
                freezer._sha(row["document_sha256"], "PDF SHA-256")
                freezer._sha(row["page_text_sha256"], "page SHA-256")
            _require(len({row["document_id"] for row in candidates}) == 2 and
                     len({(row["document_id"], row["page"]) for row in candidates}) == 4,
                     "reserve two-PDF/page roster mismatch")
            splits = {freezer.EXPECTED[row["document_id"]][0] for row in candidates}
            _require(len(splits) == 1, "reserve candidate split mismatch")
            split_counts[next(iter(splits))] += 1
            _require(len({freezer._safe_id(row["author_id"], "author candidate ID")
                          for row in candidate_mapping}) == 4,
                     "reserve author candidate roster mismatch")
        _require(split_counts == {"calibration": 18, "heldout": 12},
                 "reserve split roster mismatch")
    reviewer_a, a = _review_index(packet, mapping, review_a,
                                  expected_groups=expected_groups)
    reviewer_b, b = _review_index(packet, mapping, review_b,
                                  expected_groups=expected_groups)
    _require(reviewer_a != reviewer_b, "two distinct reviewers required")
    mapping_by_group = {group["group_id"]: group for group in mapping["groups"]}
    _require(set(mapping_by_group) == {group["group_id"] for group in packet["groups"]},
             "blind mapping group mismatch")

    def convert(reviewer_id: str, labels: dict[tuple[str, str], tuple[bool, bool]]) -> dict:
        groups = []
        for group in packet["groups"]:
            gid = group["group_id"]
            linked = mapping_by_group[gid]
            candidate_map = {row["id"]: row["author_id"] for row in linked["candidates"]}
            _require(set(candidate_map) == {row["id"] for row in group["candidates"]},
                     "blind mapping candidate mismatch")
            groups.append({"group_id": linked["author_group_id"], "candidates": [
                {"id": candidate_map[row["id"]],
                 "page_useful": labels[(gid, row["id"])][0],
                 "cue_useful": labels[(gid, row["id"])][1]}
                for row in group["candidates"]]})
        return {"schema_version": freezer.REVIEW_SCHEMA, "reviewer_id": reviewer_id,
                "groups": groups}

    disagreements = {key for key in a if a[key] != b[key]}
    dispute_groups = []
    for group in packet["groups"]:
        selected = [row for row in group["candidates"]
                    if (group["group_id"], row["id"]) in disagreements]
        if selected:
            dispute_groups.append({"group_id": group["group_id"],
                                   "question": group["question"], "candidates": selected})
    disputes = {"schema_version": DISPUTES_SCHEMA,
                "packet_sha256": mapping["packet_sha256"],
                "review_rule": packet["review_rule"], "groups": dispute_groups}
    return convert(reviewer_a, a), convert(reviewer_b, b), disputes


def bridge_adjudication(packet: dict, mapping: dict, review_a: dict,
                        review_b: dict, adjudication: dict) -> dict:
    """Convert a third review of exact disagreements into the freezer schema."""
    _, _, disputes = bridge_reviews(packet, mapping, review_a, review_b)
    freezer._keys(adjudication, {"schema_version", "reviewer_id", "packet_sha256", "decisions"})
    _require(adjudication["schema_version"] == ADJUDICATION_RESPONSE_SCHEMA and
             adjudication["packet_sha256"] == mapping["packet_sha256"],
             "blind adjudication identity mismatch")
    reviewer_id = freezer._safe_id(adjudication["reviewer_id"], "adjudicator ID")
    _require(reviewer_id not in {mapping["author_id"], review_a["reviewer_id"],
                                 review_b["reviewer_id"]},
             "adjudicator must be independent")
    roster = {(group["group_id"], row["id"]) for group in disputes["groups"]
              for row in group["candidates"]}
    decisions = adjudication["decisions"]
    _require(isinstance(decisions, list) and len(decisions) == len(roster),
             "adjudication must cover exact disagreements")
    group_map = {group["group_id"]: group for group in mapping["groups"]}
    converted = []
    seen: set[tuple[str, str]] = set()
    for decision in decisions:
        freezer._keys(decision, {"group_id", "id", "page_useful", "cue_useful"})
        gid = freezer._safe_id(decision["group_id"], "adjudication group ID")
        cid = freezer._safe_id(decision["id"], "adjudication candidate ID")
        key = (gid, cid)
        page, cue = decision["page_useful"], decision["cue_useful"]
        _require(key in roster and key not in seen and type(page) is bool and
                 type(cue) is bool and (not cue or page),
                 "adjudication decision invalid")
        seen.add(key)
        linked = group_map[gid]
        author_cid = next(row["author_id"] for row in linked["candidates"] if row["id"] == cid)
        converted.append({"group_id": linked["author_group_id"], "id": author_cid,
                          "page_useful": page, "cue_useful": cue})
    return {"schema_version": freezer.ADJUDICATION_SCHEMA, "reviewer_id": reviewer_id,
            "decisions": converted}


def _write_exclusive(output: Path, value: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as handle:
        handle.write(freezer.canonical_bytes(value))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--reserve", action="store_true",
                         help="prepare the separate 30-group reserve_v1 blind profile")
    for name in ("manifest", "authored", "overlap-diagnostic", "overlap-review"):
        prepare.add_argument(f"--{name}", type=Path, required=True)
    bridge = sub.add_parser("bridge")
    final = sub.add_parser("finalize")
    for command in (bridge, final):
        for name in ("blind-packet", "mapping", "review-a", "review-b"):
            command.add_argument(f"--{name}", type=Path, required=True)
    final.add_argument("--adjudication", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "prepare":
        manifest, manifest_sha = freezer.read_json(args.manifest)
        authored, _ = freezer.read_json(args.authored)
        diagnostic, diagnostic_sha = freezer.read_json(args.overlap_diagnostic)
        overlap_review, overlap_review_sha = freezer.read_json(args.overlap_review)
        freezer.validate_overlap_gate(manifest, manifest_sha, diagnostic,
                                      diagnostic_sha, overlap_review)
        pages, documents = freezer.load_verified_pages(manifest, args.manifest)
        excluded = {(row["document_id"], page) for row in diagnostic["per_new_document"]
                    for page in row["excluded_pages"]}
        pdf_paths = {Path(row["path"]).stem: freezer._verified_child(args.manifest.parent, row["path"])
                     for row in manifest["documents"]}
        packet, mapping = build_blind_packet(authored, pages, documents, manifest_sha,
                                             overlap_review_sha, excluded, pdf_paths,
                                             salt=secrets.token_hex(32), reserve=args.reserve)
        reviewer_dir = Path(tempfile.mkdtemp(prefix="cardchemy-fresh-v2-review-"))
        operator_dir = Path(tempfile.mkdtemp(prefix="cardchemy-fresh-v2-mapping-"))
        reviewer_path, mapping_path = reviewer_dir / "blind-packet.json", operator_dir / "mapping.json"
        _write_exclusive(reviewer_path, packet)
        _write_exclusive(reviewer_dir / "blank-review-template.json",
                         blank_review_template(packet, mapping["packet_sha256"]))
        _write_exclusive(mapping_path, mapping)
        print(json.dumps({"blind_packet": str(reviewer_path), "mapping": str(mapping_path),
                          "packet_sha256": mapping["packet_sha256"], "network_calls": 0}))
        return
    packet, _ = freezer.read_json(args.blind_packet)
    mapping, _ = freezer.read_json(args.mapping)
    review_a, _ = freezer.read_json(args.review_a)
    review_b, _ = freezer.read_json(args.review_b)
    output = Path(tempfile.mkdtemp(prefix="cardchemy-fresh-v2-bridge-"))
    if args.mode == "bridge":
        original_a, original_b, disputes = bridge_reviews(packet, mapping, review_a, review_b)
        for name, value in (("review-a.json", original_a), ("review-b.json", original_b),
                            ("disputes.json", disputes)):
            _write_exclusive(output / name, value)
        print(json.dumps({"output": str(output),
                          "disagreement_count": sum(len(group["candidates"]) for group in disputes["groups"]),
                          "network_calls": 0}))
        return
    adjudication, _ = freezer.read_json(args.adjudication)
    original = bridge_adjudication(packet, mapping, review_a, review_b, adjudication)
    _write_exclusive(output / "adjudication.json", original)
    print(json.dumps({"output": str(output / "adjudication.json"), "network_calls": 0}))


if __name__ == "__main__":
    main()
