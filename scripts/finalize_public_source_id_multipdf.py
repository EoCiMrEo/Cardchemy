"""Freeze independently reviewed cross-PDF source labels without model scoring.

The authored candidate packet has one unlabelled page per group. Two separate
reviews must cover every new candidate; disagreement or uncertainty requires a
third adjudication. This script checks exact public PDF bytes and page text,
but cannot substitute for the reviewers' usefulness judgement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from tempfile import gettempdir

from pypdf import PdfReader

from prepare_public_source_id_multipdf import canonical_bytes


PACKET_SCHEMA = "cardchemy_public_source_id_multipdf_review_v1"
REVIEW_SCHEMA = "cardchemy_public_source_id_multipdf_independent_review_v1"
LABEL_SCHEMA = "cardchemy_public_source_id_multipdf_labels_v1"
PACKET_SHA256 = "7ec9a83245fd432ff9f19047d1aa5aab1835a0bc9fdab04d9807d87787d19ae7"
EXISTING_SHA256 = "4019b9c280e318db6d052ea9346ad48338dbc70e0a7762a983ae66b60b561c97"
NEW_ONLY_SHA256 = "b3a05e3d33e1825f2121bd0f2ce83dc61d352062fa9dd37d61fa33f62e0720a1"
MANIFEST_SHA256 = "9978ad6fd2ca50f20d20ed8231e7434e2d8f91bbdc21b61e5e44ddcb76f0eae4"
SHA = re.compile(r"[0-9a-f]{64}\Z")


class ReviewError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ReviewError(code)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        require(key not in value, "duplicate_json_key")
        value[key] = item
    return value


def read_pinned(path: Path, expected_sha: str, max_bytes: int) -> dict:
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_size <= max_bytes, "input_file_invalid")
    raw = path.read_bytes()
    require(digest(raw) == expected_sha, "input_hash_mismatch")
    value = json.loads(raw, object_pairs_hook=_unique_pairs)
    require(type(value) is dict and raw == canonical_bytes(value),
            "input_format_invalid")
    return value


def read_review(path: Path, packet_sha: str) -> dict:
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_size <= 100_000, "review_file_invalid")
    raw = path.read_bytes()
    value = json.loads(raw, object_pairs_hook=_unique_pairs)
    require(type(value) is dict and raw == canonical_bytes(value) and
            set(value) == {"schema", "reviewer_id", "packet_sha256", "rows"} and
            value["schema"] == REVIEW_SCHEMA and
            value["packet_sha256"] == packet_sha and
            type(value["reviewer_id"]) is str and
            re.fullmatch(r"[a-z0-9_-]{3,40}", value["reviewer_id"]) and
            type(value["rows"]) is list, "review_format_invalid")
    return value


def _new_rows(packet: dict, existing: dict, new_only: dict) -> dict[str, dict]:
    require(packet.get("schema") == PACKET_SCHEMA and
            existing.get("schema") == PACKET_SCHEMA + "_sealed_existing_labels" and
            new_only.get("schema") == PACKET_SCHEMA + "_new_page_review" and
            all(type(value.get("groups")) is list and len(value["groups"]) == 96
                for value in (packet, existing, new_only)), "packet_shape_invalid")
    expected: dict[str, dict] = {}
    counts = {"calibration": 0, "heldout": 0}
    for group, old, new in zip(packet["groups"], existing["groups"],
                               new_only["groups"], strict=True):
        group_id, split = group["group_id"], group["split"]
        require(type(group_id) is str and group_id not in expected and
                split in counts and old["group_id"] == group_id and
                new["group_id"] == group_id and old["split"] == split and
                new["split"] == split and
                type(group["candidates"]) is list and
                len(group["candidates"]) == len(old["labels"]) == 4,
                "packet_group_invalid")
        counts[split] += 1
        new_candidates = []
        for candidate, label in zip(group["candidates"], old["labels"], strict=True):
            require(candidate["id"] == label["id"] and
                    candidate["document_sha256"] == label["document_sha256"] and
                    candidate["page"] == label["page"] and
                    type(candidate["page_text"]) is str and
                    type(candidate["cue"]) is str and
                    candidate["cue"] in candidate["page_text"],
                    "packet_candidate_invalid")
            if label["page_useful"] is None or label["cue_useful"] is None:
                require(label["page_useful"] is None and
                        label["cue_useful"] is None, "partial_old_label")
                new_candidates.append(candidate)
            else:
                require(type(label["page_useful"]) is bool and
                        type(label["cue_useful"]) is bool, "old_label_invalid")
        require(len(new_candidates) == 1 and new["candidate"] == new_candidates[0],
                "new_candidate_invalid")
        expected[group_id] = {"split": split, "candidate": new_candidates[0]}
    require(counts == {"calibration": 48, "heldout": 48}, "split_counts_invalid")
    return expected


def _validate_review_rows(review: dict, expected: dict[str, dict], *,
                          subset: set[str] | None = None) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    wanted = set(expected) if subset is None else subset
    for row in review["rows"]:
        require(type(row) is dict and set(row) == {
            "group_id", "candidate_id", "document_sha256", "page",
            "source_verified", "page_useful", "cue_useful",
        }, "review_row_fields")
        group_id = row["group_id"]
        require(type(group_id) is str and group_id in wanted and
                group_id not in rows, "review_row_identity")
        candidate = expected[group_id]["candidate"]
        require(row["candidate_id"] == candidate["id"] and
                row["document_sha256"] == candidate["document_sha256"] and
                row["page"] == candidate["page"] and
                type(row["source_verified"]) is bool and
                (row["page_useful"] is None or type(row["page_useful"]) is bool) and
                (row["cue_useful"] is None or type(row["cue_useful"]) is bool) and
                (row["cue_useful"] is not True or row["page_useful"] is True),
                "review_row_invalid")
        rows[group_id] = row
    require(set(rows) == wanted, "review_coverage_invalid")
    return rows


def _verify_public_pages(packet: dict, corpus: Path) -> None:
    manifest_path = corpus / "manifest.json"
    require(manifest_path.is_file() and not manifest_path.is_symlink(),
            "manifest_invalid")
    manifest_raw = manifest_path.read_bytes()
    require(digest(manifest_raw) == MANIFEST_SHA256, "manifest_hash_invalid")
    manifest = json.loads(manifest_raw)
    documents = manifest["documents"]
    require(type(documents) is list and len(documents) == 14, "manifest_invalid")
    indexed = {}
    for doc in documents:
        sha, name = doc["sha256"], doc["path"]
        require(type(sha) is str and SHA.fullmatch(sha) and
                type(name) is str and re.fullmatch(r"lec\d{2}[.]pdf", name) and
                sha not in indexed, "manifest_document_invalid")
        path = corpus / name
        require(path.is_file() and not path.is_symlink() and
                digest(path.read_bytes()) == sha, "public_pdf_hash_invalid")
        indexed[sha] = {"name": name, "split": doc["split"],
                        "pages": [(page.extract_text() or "") for page in
                                  PdfReader(path, strict=False).pages]}
    for group in packet["groups"]:
        require(len({row["document_sha256"] for row in group["candidates"]}) == 2,
                "cross_pdf_required")
        for candidate in group["candidates"]:
            doc = indexed.get(candidate["document_sha256"])
            page = candidate["page"]
            require(doc is not None and doc["split"] == group["split"] and
                    doc["name"] == candidate["filename"] and
                    type(page) is int and 1 <= page <= len(doc["pages"]) and
                    doc["pages"][page - 1] == candidate["page_text"] and
                    candidate["cue"] in doc["pages"][page - 1],
                    "public_pdf_page_mismatch")


def finalize(packet: dict, existing: dict, new_only: dict,
             review_a: dict, review_b: dict,
             adjudication: dict | None = None) -> dict:
    expected = _new_rows(packet, existing, new_only)
    require(review_a["reviewer_id"] != review_b["reviewer_id"],
            "reviewers_not_independent")
    rows_a = _validate_review_rows(review_a, expected)
    rows_b = _validate_review_rows(review_b, expected)
    disputes = {group_id for group_id in expected if
                not rows_a[group_id]["source_verified"] or
                not rows_b[group_id]["source_verified"] or
                any(rows_a[group_id][name] is None or
                    rows_b[group_id][name] is None or
                    rows_a[group_id][name] != rows_b[group_id][name]
                    for name in ("page_useful", "cue_useful"))}
    if disputes:
        require(adjudication is not None and
                adjudication["reviewer_id"] not in {
                    review_a["reviewer_id"], review_b["reviewer_id"]},
                "adjudication_required")
        judged = _validate_review_rows(adjudication, expected, subset=disputes)
    else:
        require(adjudication is None, "unneeded_adjudication")
        judged = {}
    resolved = {}
    for group_id in expected:
        row = judged.get(group_id) or rows_a[group_id]
        require(row["source_verified"] is True and
                type(row["page_useful"]) is bool and
                type(row["cue_useful"]) is bool,
                "unresolved_review")
        resolved[group_id] = row
    groups = []
    for group, old in zip(packet["groups"], existing["groups"], strict=True):
        labels = []
        for label in old["labels"]:
            if label["page_useful"] is None:
                fresh = resolved[group["group_id"]]
                label = {**label, "page_useful": fresh["page_useful"],
                         "cue_useful": fresh["cue_useful"]}
            labels.append(label)
        groups.append({"group_id": group["group_id"], "split": group["split"],
                       "question_form": group["question_form"], "labels": labels})
    return {"schema": LABEL_SCHEMA, "packet_sha256": PACKET_SHA256,
            "reviewer_ids": [review_a["reviewer_id"], review_b["reviewer_id"]],
            "adjudicator_id": adjudication["reviewer_id"] if disputes else None,
            "adjudicated_count": len(disputes), "groups": groups}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--packet-dir", type=Path, required=True)
    parser.add_argument("--review-a", type=Path, required=True)
    parser.add_argument("--review-b", type=Path, required=True)
    parser.add_argument("--adjudication", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        packet = read_pinned(args.packet_dir / "blind-review-packet.json",
                             PACKET_SHA256, 1_000_000)
        existing = read_pinned(args.packet_dir / "sealed-existing-labels.json",
                               EXISTING_SHA256, 100_000)
        new_only = read_pinned(args.packet_dir / "new-page-review.json",
                               NEW_ONLY_SHA256, 1_000_000)
        _verify_public_pages(packet, args.corpus)
        reviews = [read_review(args.review_a, PACKET_SHA256),
                   read_review(args.review_b, PACKET_SHA256)]
        adjudication = (read_review(args.adjudication, PACKET_SHA256)
                        if args.adjudication else None)
        result = finalize(packet, existing, new_only, *reviews, adjudication)
        temp = Path(gettempdir()).resolve()
        require(args.output.is_absolute() and temp in args.output.resolve().parents
                and not args.output.exists() and args.output.parent.is_dir(),
                "os_temp_output_required")
        args.output.mkdir(parents=False, exist_ok=False)
        raw = canonical_bytes(result)
        path = args.output / "frozen-labels.json"
        with path.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        receipt = {"schema": LABEL_SCHEMA + "_freeze", "labels_sha256": digest(raw),
                   "packet_sha256": PACKET_SHA256,
                   "review_a_sha256": digest(args.review_a.read_bytes()),
                   "review_b_sha256": digest(args.review_b.read_bytes()),
                   "adjudication_sha256": (digest(args.adjudication.read_bytes())
                                           if args.adjudication else None),
                   "adjudicated_count": result["adjudicated_count"]}
        with (args.output / "freeze-receipt.json").open("xb") as stream:
            stream.write(canonical_bytes(receipt))
            stream.flush()
            os.fsync(stream.fileno())
        print(json.dumps({"status": "frozen_no_model_score",
                          "groups": len(result["groups"]),
                          "adjudicated": result["adjudicated_count"],
                          "labels_sha256": digest(raw)}, sort_keys=True))
        return 0
    except (ReviewError, OSError, ValueError, KeyError, TypeError) as exc:
        code = str(exc) if isinstance(exc, ReviewError) else type(exc).__name__
        print(json.dumps({"status": "review_rejected", "reason": code},
                         sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
