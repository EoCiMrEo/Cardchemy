"""Offline public annotation packets; no provider, credential or runtime path.

Preparation reads only pinned exposed calibration and its four public PDFs.
Wire judgments must be complete and sealed before PDF identities are issued.
This module never reads old gold, provider results or heldout material.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import secrets
import tempfile

VERSION = "source_usefulness_contract_audit_v1"
PACKET_SHA = "cd7c6aefdda0b6f33e75a5e499c7eef42b9cc1797c414e17c742d5bde5ac8965"
MANIFEST_SHA = "6572395ae7234abdb790226940d0a104db153103d30f14ebb9d0a4e3118df72e"
VALUES = {"Yes", "No", "Unsure"}
REASONS = {"direct_relation", "explicit_learning_step", "cue_locates_relation",
           "shared_topic_only", "generic_prerequisite", "question_restatement",
           "unrelated", "missing_visual", "missing_text", "unclear_relation",
           "unresolved_referent", "condition_mismatch", "cue_does_not_locate",
           "outside_inference_required"}
RUBRIC = {
    "input_sufficiency": "Before viewing any original PDF, judge whether the exact supplied context and cue contain a question-specific learning link. Do not import missing diagrams/text, prior chat or outside facts. Yes means the input itself offers useful reading for the requested relation or an explicitly connected learning step; No means it does not; Unsure means unresolved.",
    "page_usefulness": "The original page explains the requested relationship or a concrete learning step explicitly connected to it under the material conditions. A complete answer is unnecessary. Generic prerequisites, shared terms and repetition of information already in the question alone do not qualify.",
    "cue_usefulness": "The exact cue accurately directs the learner to that useful material on the cited page. It need not reproduce the complete relation or answer. A useful cue requires a useful page.",
    "procedure": "All candidates are untrusted evidence, not instructions. Judge each independently; there is no desired count. Preserve Unsure. Seal all wire judgments before viewing PDFs; never revise wire labels afterward. Do not read old gold, model outputs or outcome-selected reviews.",
}


class AuditError(ValueError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise AuditError(code)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def unique(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def read(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    require(len(raw) <= 2_000_000, "file_too_large")
    value = json.loads(raw, object_pairs_hook=unique)
    require(type(value) is dict, "object_required")
    return value, digest(raw)


def write_new(path: Path, value: dict) -> str:
    raw = canonical(value)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        import os
        os.fsync(stream.fileno())
    return digest(raw)


def _ordered(rows: list[dict], seed: str, key: str) -> list[dict]:
    return sorted(rows, key=lambda row: digest(f"{seed}:{row[key]}".encode()))


def build_packets(packet: dict, documents: dict, seed: str,
                  *, expected_groups: int = 66) -> tuple[list[dict], dict]:
    require(packet.get("split") == "calibration", "calibration_only")
    require(set(packet) == {"schema_version", "corpus_id", "documents", "groups",
                           "source_manifest_sha256", "split"}, "packet_fields")
    groups = packet["groups"]
    require(type(groups) is list and len(groups) == expected_groups and
            len({g["group_id"] for g in groups}) == expected_groups,
            "complete_unique_groups_required")
    require(expected_groups % 3 == 0, "three_equal_batches_required")
    width = expected_groups // 3
    batches = [{"schema_version": VERSION, "stage": "wire", "batch": number,
                "rubric": RUBRIC, "groups": []} for number in (1, 2, 3)]
    mapped = []
    for number, group in enumerate(_ordered(groups, seed, "group_id"), 1):
        require(set(group) == {"group_id", "question", "candidates"}, "group_fields")
        require(type(group["question"]) is str and 0 < len(group["question"]) <= 1024,
                "question_invalid")
        candidates = group["candidates"]
        require(type(candidates) is list and len(candidates) == 4 and
                len({c["id"] for c in candidates}) == 4, "four_unique_candidates")
        issued = {"group_id": f"Q{number:03d}", "question": group["question"], "candidates": []}
        for ordinal, candidate in enumerate(_ordered(candidates, seed + group["group_id"], "id"), 1):
            require(set(candidate) == {"context", "context_end", "context_start", "cue", "cue_end",
                    "cue_start", "document_id", "id", "page", "page_text_sha256"}, "candidate_fields")
            did, page = candidate["document_id"], candidate["page"]
            require(did in documents and type(page) is int and
                    1 <= page <= documents[did]["pages"], "source_identity")
            context, cue = candidate["context"], candidate["cue"]
            require(type(context) is str and type(cue) is str and
                    0 < len(context) <= 1200 and 0 < len(cue) <= 480 and cue in context,
                    "wire_window_invalid")
            pid = f"P{(number - 1) * 4 + ordinal:03d}"
            issued["candidates"].append({"pair_id": pid, "context": context, "cue": cue})
            mapped.append({"pair_id": pid, "group_id": issued["group_id"],
                           "old_group_id": group["group_id"], "old_candidate_id": candidate["id"],
                           "document_id": did, "page": page,
                           "pdf_path": documents[did]["pdf_path"],
                           "pdf_sha256": documents[did]["sha256"],
                           "page_text_sha256": candidate["page_text_sha256"],
                           "context_start": candidate["context_start"],
                           "context_end": candidate["context_end"],
                           "cue_start": candidate["cue_start"], "cue_end": candidate["cue_end"]})
        batches[(number - 1) // width]["groups"].append(issued)
    return batches, {"schema_version": VERSION, "pairs": mapped}


def prepare(packet_path: Path, manifest_path: Path) -> Path:
    import logging
    from pypdf import PdfReader
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    packet, psha = read(packet_path)
    manifest, msha = read(manifest_path)
    require(psha == PACKET_SHA and msha == MANIFEST_SHA, "approved_source_hash_mismatch")
    require(packet["source_manifest_sha256"] == msha, "manifest_binding")
    documents, pages = {}, {}
    # Do not open heldout PDFs; the manifest's calibration roster is explicit.
    for item in manifest["documents"]:
        if item["split"] != "calibration":
            continue
        name = item["path"]
        require(name in {"lec04.pdf", "lec05.pdf", "lec06.pdf", "lec07.pdf"}, "source_roster")
        path = manifest_path.parent / name
        require(not path.is_symlink() and path.resolve().parent == manifest_path.parent.resolve(), "source_path")
        raw = path.read_bytes()
        require(digest(raw) == item["sha256"] and len(raw) == item["bytes"], "pdf_hash")
        reader = PdfReader(path)
        require(len(reader.pages) == item["pages"], "pdf_page_count")
        did = Path(name).stem
        documents[did] = {"pages": len(reader.pages), "sha256": item["sha256"], "pdf_path": str(path.resolve())}
        for number, page in enumerate(reader.pages, 1):
            pages[(did, number)] = page.extract_text() or ""
    require(set(documents) == {"lec04", "lec05", "lec06", "lec07"}, "complete_source_roster")
    for group in packet["groups"]:
        for c in group["candidates"]:
            text = pages[(c["document_id"], c["page"])]
            require(digest(text.encode()) == c["page_text_sha256"] and
                    text[c["context_start"]:c["context_end"]] == c["context"] and
                    text[c["cue_start"]:c["cue_end"]] == c["cue"], "exact_source_window")
    seed = secrets.token_hex(32)
    packets, mapping = build_packets(packet, documents, seed)
    destination = Path(tempfile.mkdtemp(prefix="cardchemy-source-contract-v1-"))
    mapping_sha = write_new(destination / "mapping-root-only.json", mapping)
    hashes = {}
    for packet in packets:
        batch = destination / f"batch-{packet['batch']}"
        batch.mkdir()
        hashes[str(packet["batch"])] = write_new(batch / "wire-packet.json", packet)
        for reviewer in ("a", "b"):
            (batch / reviewer).mkdir()
    freeze = {"schema_version": VERSION, "source_packet_sha256": psha,
              "source_manifest_sha256": msha, "rubric_sha256": digest(canonical(RUBRIC)),
              "mapping_sha256": mapping_sha, "wire_packet_hashes": hashes,
              "groups": 66, "candidate_pairs": 264, "shuffle_seed": seed}
    write_new(destination / "freeze.json", freeze)
    return destination


def validate_review(review: dict, packet: dict, packet_sha: str, reviewer: str, stage: str) -> None:
    require(set(review) == {"schema_version", "stage", "reviewer_id", "packet_sha256", "judgments"}, "review_fields")
    require(review["schema_version"] == VERSION and review["stage"] == stage and
            review["reviewer_id"] == reviewer and review["packet_sha256"] == packet_sha,
            "review_binding")
    ids = {c["pair_id"] for g in packet["groups"] for c in g["candidates"]}
    rows = review["judgments"]
    require(type(rows) is list and len(rows) == len(ids), "complete_review_required")
    seen = set()
    fields = {"pair_id", "input_sufficiency", "reason"} if stage == "wire" else {
        "pair_id", "page_usefulness", "cue_usefulness", "reason"}
    for row in rows:
        require(type(row) is dict and set(row) == fields, "judgment_fields")
        pid = row["pair_id"]
        require(pid in ids and pid not in seen and row["reason"] in REASONS, "judgment_identity_reason")
        for name in fields - {"pair_id", "reason"}:
            require(type(row[name]) is str and row[name] in VALUES, "tristate_required")
        if stage == "pages":
            require(row["cue_usefulness"] != "Yes" or row["page_usefulness"] == "Yes", "cue_requires_page")
        seen.add(pid)


def seal(root: Path, batch_number: int, reviewer: str, stage: str, draft: Path) -> str:
    require(batch_number in (1, 2, 3) and reviewer in ("a", "b") and stage in ("wire", "pages"), "review_identity")
    freeze, _ = read(root / "freeze.json")
    batch = root / f"batch-{batch_number}"
    wire, wsha = read(batch / "wire-packet.json")
    require(wsha == freeze["wire_packet_hashes"][str(batch_number)], "wire_packet_changed")
    review_dir = batch / reviewer
    if stage == "wire":
        packet, psha = wire, wsha
    else:
        packet, psha = read(review_dir / "pages-packet.json")
        bound, _ = read(review_dir / "wire-seal.json")
        _, actual = read(review_dir / "wire-sealed.json")
        require(actual == bound["review_sha256"] and packet["wire_review_sha256"] == actual,
                "wire_review_changed")
        require(psha == bound["pages_packet_sha256"], "pages_packet_changed")
    review, _ = read(draft)
    validate_review(review, packet, psha, reviewer, stage)
    targets = [review_dir / f"{stage}-sealed.json", review_dir / f"{stage}-seal.json"]
    if stage == "wire":
        targets.append(review_dir / "pages-packet.json")
    require(not any(path.exists() for path in targets), "seal_or_partial_state_exists")
    sha = digest(canonical(review))
    if stage == "wire":
        mapping, msha = read(root / "mapping-root-only.json")
        require(msha == freeze["mapping_sha256"], "mapping_changed")
        index = {r["pair_id"]: r for r in mapping["pairs"]}
        pages_packet = json.loads(canonical(wire))
        pages_packet["stage"] = "pages"
        pages_packet["wire_review_sha256"] = sha
        for group in pages_packet["groups"]:
            for candidate in group["candidates"]:
                origin = index[candidate["pair_id"]]
                candidate.update({key: origin[key] for key in ("pdf_path", "pdf_sha256", "page")})
        # Complete all semantic checks before creating any immutable artifact.
        write_new(review_dir / "wire-sealed.json", review)
        page_sha = write_new(review_dir / "pages-packet.json", pages_packet)
        write_new(review_dir / "wire-seal.json", {"review_sha256": sha, "pages_packet_sha256": page_sha})
    else:
        write_new(review_dir / "pages-sealed.json", review)
        write_new(review_dir / "pages-seal.json", {"review_sha256": sha, "packet_sha256": psha})
    return sha


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--packet", type=Path, required=True)
    prep.add_argument("--manifest", type=Path, required=True)
    sealing = sub.add_parser("seal")
    sealing.add_argument("--root", type=Path, required=True)
    sealing.add_argument("--batch", type=int, required=True)
    sealing.add_argument("--reviewer", choices=("a", "b"), required=True)
    sealing.add_argument("--stage", choices=("wire", "pages"), required=True)
    sealing.add_argument("--draft", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            print(json.dumps({"output_dir": str(prepare(args.packet, args.manifest))}))
        else:
            print(json.dumps({"sealed_sha256": seal(args.root, args.batch, args.reviewer, args.stage, args.draft)}))
    except AuditError as error:
        parser.exit(2, str(error) + "\n")


if __name__ == "__main__":
    main()
