"""Freeze all original and reserve public source-ID cases after blind review.

This command is keyless and networkless. It never removes an original or
reserve question on the basis of its independently reviewed usefulness label.
It cannot open heldout model results or enable the Ask runtime.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

import prepare_fresh_public_source_id_v2 as base
import review_fresh_public_source_id_v2 as blind


FREEZE_SCHEMA = "fresh_public_source_id_v2_augmented_freeze"
INPUT_NAMES = (
    "original_authored", "original_review_a", "original_review_b",
    "original_adjudication", "reserve_authored", "reserve_blind_packet",
    "reserve_mapping", "reserve_blind_review_a", "reserve_blind_review_b",
    "reserve_blind_adjudication", "overlap_review",
)
HUMAN_REVIEW_INPUTS = frozenset({
    "original_review_a", "original_review_b", "original_adjudication",
    "reserve_blind_review_a", "reserve_blind_review_b",
    "reserve_blind_adjudication", "overlap_review",
})


def _reserve_blind_matches_authored(
    *, authored: dict, packet: dict, mapping: dict,
    pages: dict[tuple[str, int], str], documents: list[dict],
    manifest_path: Path,
) -> None:
    """Bind blinded candidate bytes back to the exact authored PDF offsets."""
    base._require(packet.get("profile") == mapping.get("profile") == blind.RESERVE_PROFILE,
                  "reserve blind profile mismatch")
    authored_groups = {group["group_id"]: group for group in authored["groups"]}
    base._require(len(authored_groups) == len(packet.get("groups", [])) ==
                  len(mapping.get("groups", [])) == 30,
                  "reserve author/blind roster mismatch")
    documents_by_id = {row["document_id"]: row for row in documents}
    mapping_by_id = {row["group_id"]: row for row in mapping["groups"]}
    base._require(len(mapping_by_id) == 30 and
                  set(mapping_by_id) == {row["group_id"] for row in packet["groups"]},
                  "reserve blind mapping groups mismatch")
    seen_authored: set[str] = set()
    for group in packet["groups"]:
        linked = mapping_by_id[group["group_id"]]
        author_gid = linked["author_group_id"]
        base._require(author_gid in authored_groups and author_gid not in seen_authored,
                      "reserve blind author group mismatch")
        seen_authored.add(author_gid)
        authored_group = authored_groups[author_gid]
        base._require(group["question"] == authored_group["question"],
                      "reserve blind question changed")
        authored_candidates = {row["id"]: row for row in authored_group["candidates"]}
        mapped_candidates = {row["id"]: row["author_id"]
                             for row in linked["candidates"]}
        base._require(len(authored_candidates) == len(mapped_candidates) == 4,
                      "reserve blind candidate mapping mismatch")
        for candidate in group["candidates"]:
            blind_id = candidate["id"]
            base._require(blind_id in mapped_candidates and
                          mapped_candidates[blind_id] in authored_candidates,
                          "reserve blind candidate ID mismatch")
            source = authored_candidates[mapped_candidates[blind_id]]
            did, page = source["document_id"], source["page"]
            text = pages.get((did, page))
            base._require(text is not None and did in documents_by_id,
                          "reserve blind candidate page mismatch")
            expected_context = text[source["context_start"]:source["context_end"]]
            expected_cue = text[source["cue_start"]:source["cue_end"]]
            pdf_path = base._verified_child(manifest_path.parent, f"{did}.pdf")
            base._require(candidate == {
                "id": blind_id,
                "document_id": did,
                "document_sha256": documents_by_id[did]["sha256"],
                "page": page,
                "pdf_uri": pdf_path.resolve().as_uri() + f"#page={page}",
                "context": expected_context,
                "cue": expected_cue,
                "page_text_sha256": base.sha256_bytes(text.encode("utf-8")),
            }, "reserve blind candidate source/offset mismatch")
    base._require(seen_authored == set(authored_groups),
                  "reserve blind author roster incomplete")


def freeze_augmented_files(paths: dict[str, Path]) -> Path:
    """Validate all immutable inputs and create a new exclusive Temp freeze."""
    expected = {"manifest", "overlap_diagnostic", *INPUT_NAMES}
    base._require(set(paths) == expected, "augmented freeze input roster mismatch")
    values: dict[str, dict] = {}
    hashes: dict[str, str] = {}
    for name in sorted(expected):
        value, sha = base.read_json(paths[name])
        # Independent reviewers may emit pretty JSON. Bind its raw byte hash,
        # reject duplicate keys in read_json, and canonicalize only the frozen
        # output. Machine-authored source, mapping and roster inputs remain
        # byte-canonical to prevent alternate representations.
        base._require(type(value) is dict and
                      (name in HUMAN_REVIEW_INPUTS or
                       base.canonical_bytes(value) == paths[name].read_bytes()),
                      f"noncanonical augmented input: {name}")
        values[name], hashes[name] = value, sha
    manifest, manifest_sha = values["manifest"], hashes["manifest"]
    overlap_reviewer = base.validate_overlap_gate(
        manifest, manifest_sha, values["overlap_diagnostic"],
        hashes["overlap_diagnostic"], values["overlap_review"])
    pages, documents = base.load_verified_pages(manifest, paths["manifest"])
    excluded = {(row["document_id"], page)
                for row in values["overlap_diagnostic"]["per_new_document"]
                for page in row["excluded_pages"]}
    reserve_a, reserve_b, disputes = blind.bridge_reviews(
        values["reserve_blind_packet"], values["reserve_mapping"],
        values["reserve_blind_review_a"], values["reserve_blind_review_b"])
    _reserve_blind_matches_authored(
        authored=values["reserve_authored"], packet=values["reserve_blind_packet"],
        mapping=values["reserve_mapping"], pages=pages, documents=documents,
        manifest_path=paths["manifest"])
    reserve_adjudication = blind.bridge_adjudication(
        values["reserve_blind_packet"], values["reserve_mapping"],
        values["reserve_blind_review_a"], values["reserve_blind_review_b"],
        values["reserve_blind_adjudication"])
    artifacts = base.build_artifacts(
        manifest, values["original_authored"], values["original_review_a"],
        values["original_review_b"], values["original_adjudication"],
        pages, documents, manifest_sha, hashes["overlap_review"], excluded,
        reserve_bundle=(values["reserve_authored"], reserve_a, reserve_b,
                        reserve_adjudication))
    for split in base.SPLITS:
        label = artifacts[f"{split}/labels.json"]
        base._require(overlap_reviewer not in label["reviewer_ids"] and
                      overlap_reviewer not in label["adjudicator_id"] and
                      overlap_reviewer not in {
                          values["original_authored"]["author_id"],
                          values["reserve_authored"]["author_id"]},
                      "overlap reviewer cannot author or review source labels")
        actual_disputes = sum(len(group["candidates"])
                              for group in disputes["groups"])
        base._require(actual_disputes == len(reserve_adjudication["decisions"]),
                      "reserve adjudication count mismatch")
    output = Path(tempfile.mkdtemp(
        prefix="cardchemy-fresh-public-source-id-v2-augmented-",
        dir=tempfile.gettempdir()))
    file_hashes: dict[str, str] = {}
    for relative, value in artifacts.items():
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = base.canonical_bytes(value)
        with target.open("xb") as handle:
            handle.write(raw)
        file_hashes[relative] = base.sha256_bytes(raw)
    freeze = {
        "schema_version": FREEZE_SCHEMA,
        "corpus_id": base.CORPUS_ID,
        "source_manifest_sha256": manifest_sha,
        "overlap_diagnostic_sha256": hashes["overlap_diagnostic"],
        "input_sha256": {name: hashes[name] for name in INPUT_NAMES},
        "files": file_hashes,
    }
    with (output / "freeze.json").open("xb") as handle:
        handle.write(base.canonical_bytes(freeze))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "overlap_diagnostic", *INPUT_NAMES):
        parser.add_argument(f"--{name.replace('_', '-')}", type=Path, required=True)
    args = parser.parse_args()
    paths = {name: getattr(args, name)
             for name in ("manifest", "overlap_diagnostic", *INPUT_NAMES)}
    output = freeze_augmented_files(paths)
    print(json.dumps({"freeze_dir": str(output), "network_calls": 0}))


if __name__ == "__main__":
    main()
