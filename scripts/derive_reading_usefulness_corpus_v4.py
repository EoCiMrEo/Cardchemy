"""Derive the v4 public reading corpus locally from the pinned v3 PDF bytes.

This command never downloads, labels, reviews, or scores anything. It creates a
new OS-Temp bundle and refuses to modify the acquired v3 corpus.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from tempfile import gettempdir


V3_CORPUS_ID = "illinois-ece448-sp2020-reading-usefulness-v3"
V4_CORPUS_ID = "illinois-ece448-sp2020-reading-usefulness-v4"
V3_DIR = "cardchemy-reading-usefulness-public-v3-20260928"
V4_DIR = "cardchemy-reading-usefulness-public-v4-20260928"
V3_PREREGISTRATION_SHA256 = "ee050f83d107c59cea09b2140f7cec81047684a9192d26ac7517a0753edfa881"
V3_MANIFEST_SHA256 = "fb59c3df42d87b0305ce2fe403c779a6f9c4f583b1bedd7bcd77860d05cd61e7"
V3_EMPTY_PLAN_SHA256 = "ca5941a973332a4b75b74d0640b16966c3dd8f94f3d6411ad5329809950e7852"
PDF_PREFIX = "https://courses.grainger.illinois.edu/ece448/sp2020/slides/"
V3_SPLITS = {
    "train": (10, 11, 14, 15, 16, 28),
    "calibration": (22, 27, 31, 32),
    "heldout": (25, 26, 33, 38),
}
V4_SPLITS = {
    "train": (10, 11, 14, 15, 16, 33),
    "calibration": (22, 25, 26, 27),
    "heldout": (28, 31, 32, 38),
}
RESERVED_RELEASE_HOLDOUT = (17, 37)
MAX_PDF_BYTES = 10 * 1024 * 1024


class DerivationError(RuntimeError):
    pass


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise DerivationError(reason)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n").encode()


def _read_json(path: Path, limit: int, expected_sha: str) -> dict[str, object]:
    _require(path.is_file() and not path.is_symlink(), "parent_metadata_missing_or_symlink")
    _require(path.stat().st_size <= limit, "parent_metadata_too_large")
    raw = path.read_bytes()
    _require(_sha(raw) == expected_sha, "parent_metadata_hash_mismatch")
    try:
        value = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise DerivationError("parent_metadata_invalid_json") from exc
    _require(type(value) is dict, "parent_metadata_not_object")
    return value


def _pdf_name(number: int) -> str:
    return f"lec{number:02d}.pdf"


def _pdf_url(number: int) -> str:
    return PDF_PREFIX + _pdf_name(number)


def _splits_as_urls(splits: dict[str, tuple[int, ...]]) -> dict[str, list[str]]:
    return {split: [_pdf_url(number) for number in numbers]
            for split, numbers in splits.items()}


def _parent_provenance() -> dict[str, object]:
    return {
        "corpus_id": V3_CORPUS_ID,
        "preregistration_sha256": V3_PREREGISTRATION_SHA256,
        "manifest_sha256": V3_MANIFEST_SHA256,
        "empty_fixture_plan_sha256": V3_EMPTY_PLAN_SHA256,
        "method": "local_hash_verified_pdf_copy_and_split_reallocation",
        "new_network_requests": 0,
        "model_scores": 0,
    }


def preregistration_v4(parent: dict[str, object]) -> dict[str, object]:
    result = copy.deepcopy(parent)
    result["corpus_id"] = V4_CORPUS_ID
    result["splits"] = _splits_as_urls(V4_SPLITS)
    result["derived_from"] = _parent_provenance()
    return result


def empty_fixture_plan_v4(parent: dict[str, object], manifest_sha: str) -> dict[str, object]:
    result = copy.deepcopy(parent)
    result["corpus_id"] = V4_CORPUS_ID
    result["manifest_sha256"] = manifest_sha
    return result


def _file_digest(path: Path, limit: int) -> tuple[str, int]:
    _require(path.is_file() and not path.is_symlink(), "parent_pdf_missing_or_symlink")
    size = path.stat().st_size
    _require(0 < size <= limit, "parent_pdf_size")
    digest = hashlib.sha256()
    seen = 0
    with path.open("rb") as source:
        _require(source.read(5) == b"%PDF-", "parent_not_pdf")
        source.seek(0)
        for block in iter(lambda: source.read(1024 * 1024), b""):
            seen += len(block)
            _require(seen <= limit, "parent_pdf_size")
            digest.update(block)
    _require(seen == size, "parent_pdf_changed_while_reading")
    return digest.hexdigest(), size


def _preflight(source_root: Path, output_root: Path) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, dict[str, object]]]:
    temp_root = Path(gettempdir()).resolve()
    _require(source_root.name == V3_DIR and source_root.parent.resolve() == temp_root and
             source_root.is_dir() and not source_root.is_symlink(), "pinned_v3_os_temp_root_required")
    _require(output_root.name.startswith("cardchemy-reading-usefulness-public-v4-") and
             output_root.parent.resolve() == temp_root and not output_root.exists() and
             not output_root.is_symlink(), "fresh_v4_os_temp_root_required")
    _require({split: len(numbers) for split, numbers in V4_SPLITS.items()} ==
             {"train": 6, "calibration": 4, "heldout": 4} and
             {number for numbers in V4_SPLITS.values() for number in numbers} ==
             {number for numbers in V3_SPLITS.values() for number in numbers} and
             not ({number for numbers in V4_SPLITS.values() for number in numbers} &
                  set(RESERVED_RELEASE_HOLDOUT)), "v4_roster_invalid")

    prereg = _read_json(source_root / "preregistration.json", 32_768,
                       V3_PREREGISTRATION_SHA256)
    manifest = _read_json(source_root / "manifest.json", 64_000,
                          V3_MANIFEST_SHA256)
    plan = _read_json(source_root / "empty_fixture_plan.json", 32_768,
                      V3_EMPTY_PLAN_SHA256)
    _require(prereg.get("corpus_id") == V3_CORPUS_ID and
             prereg.get("schema") == "cardchemy_public_reading_corpus_prereg_v1" and
             prereg.get("splits") == _splits_as_urls(V3_SPLITS) and
             prereg.get("reserved_release_holdout") ==
             [_pdf_url(number) for number in RESERVED_RELEASE_HOLDOUT],
             "parent_preregistration_identity")
    _require(manifest.get("corpus_id") == V3_CORPUS_ID and
             manifest.get("schema") == "cardchemy_public_reading_corpus_manifest_v1" and
             manifest.get("preregistration_sha256") == V3_PREREGISTRATION_SHA256 and
             manifest.get("all_pdf_first_pages_cc_by_4") is True and
             manifest.get("labels_written") is False,
             "parent_manifest_identity")
    _require(plan.get("corpus_id") == V3_CORPUS_ID and
             plan.get("schema") == "cardchemy_reading_usefulness_fixture_plan_v1" and
             plan.get("manifest_sha256") == V3_MANIFEST_SHA256 and
             plan.get("groups") == [], "parent_plan_identity")

    rows = manifest.get("documents")
    _require(type(rows) is list and len(rows) == 14, "parent_document_count")
    by_name: dict[str, dict[str, object]] = {}
    expected_old = {number: split for split, nums in V3_SPLITS.items() for number in nums}
    for row in rows:
        _require(type(row) is dict, "parent_document_entry")
        name = row.get("path")
        _require(type(name) is str and re.fullmatch(r"lec\d{2}[.]pdf", name) is not None,
                 "parent_document_name")
        number = int(name[3:5])
        _require(number in expected_old and name not in by_name and
                 row.get("url") == _pdf_url(number) and
                 row.get("split") == expected_old[number] and
                 row.get("first_page_license") == "CC BY 4.0" and
                 row.get("license_url") == prereg.get("license_url") and
                 type(row.get("bytes")) is int and
                 type(row.get("sha256")) is str and
                 re.fullmatch(r"[a-f0-9]{64}", row["sha256"]) is not None,
                 "parent_document_identity")
        digest, size = _file_digest(source_root / name, MAX_PDF_BYTES)
        _require(digest == row["sha256"] and size == row["bytes"],
                 "parent_pdf_hash_or_size_mismatch")
        by_name[name] = row
    _require(set(by_name) == {_pdf_name(n) for n in expected_old} and
             {p.name for p in source_root.glob("*.pdf")} == set(by_name),
             "parent_pdf_roster")
    return prereg, manifest, plan, by_name


def derive(source_root: Path, output_root: Path) -> dict[str, object]:
    prereg_v3, manifest_v3, plan_v3, by_name = _preflight(source_root, output_root)
    prereg_v4 = preregistration_v4(prereg_v3)
    prereg_raw = canonical_bytes(prereg_v4)
    prereg_sha = _sha(prereg_raw)
    new_docs = []
    for split, numbers in V4_SPLITS.items():
        for number in numbers:
            new_docs.append({**by_name[_pdf_name(number)], "split": split})
    manifest_v4 = {
        "schema": "cardchemy_public_reading_corpus_manifest_v1",
        "corpus_id": V4_CORPUS_ID,
        "preregistration_sha256": prereg_sha,
        "index_url": manifest_v3["index_url"],
        "license_url": manifest_v3["license_url"],
        "documents": new_docs,
        "requests_including_redirects": 0,
        "received_bytes": 0,
        "elapsed_seconds": 0,
        "all_pdf_first_pages_cc_by_4": True,
        "labels_written": False,
        "derived_from": _parent_provenance(),
        "local_copied_pdf_bytes": sum(row["bytes"] for row in new_docs),
    }
    manifest_raw = canonical_bytes(manifest_v4)
    manifest_sha = _sha(manifest_raw)
    plan_raw = canonical_bytes(empty_fixture_plan_v4(plan_v3, manifest_sha))
    plan_sha = _sha(plan_raw)

    output_root.mkdir()
    for row in new_docs:
        name = row["path"]
        with (source_root / name).open("rb") as source, (output_root / name).open("xb") as target:
            shutil.copyfileobj(source, target, length=1024 * 1024)
        digest, size = _file_digest(output_root / name, MAX_PDF_BYTES)
        _require(digest == row["sha256"] and size == row["bytes"],
                 "copied_pdf_hash_or_size_mismatch")
    for name, raw in (("preregistration.json", prereg_raw),
                      ("manifest.json", manifest_raw),
                      ("empty_fixture_plan.json", plan_raw)):
        with (output_root / name).open("xb") as target:
            target.write(raw)
    receipt = {
        "schema": "cardchemy_public_reading_corpus_local_derivation_receipt_v1",
        "corpus_id": V4_CORPUS_ID,
        "derived_from": _parent_provenance(),
        "preregistration_sha256": prereg_sha,
        "manifest_sha256": manifest_sha,
        "empty_fixture_plan_sha256": plan_sha,
        "documents": 14,
        "local_copied_pdf_bytes": manifest_v4["local_copied_pdf_bytes"],
        "requests_including_redirects": 0,
        "provider_calls": 0,
        "model_scores": 0,
        "labels_written": False,
    }
    with (output_root / "derivation_receipt.json").open("xb") as target:
        target.write(canonical_bytes(receipt))
    return {"status": "derived_unlabeled_no_scoring", "output": str(output_root),
            "documents": 14, "pdf_bytes": manifest_v4["local_copied_pdf_bytes"],
            "preregistration_sha256": prereg_sha, "manifest_sha256": manifest_sha,
            "empty_fixture_plan_sha256": plan_sha,
            "derivation_receipt_sha256": _sha(canonical_bytes(receipt))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    temp_root = Path(gettempdir())
    parser.add_argument("--source", type=Path, default=temp_root / V3_DIR)
    parser.add_argument("--output", type=Path, default=temp_root / V4_DIR)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps({"status": "local_derivation_preflight_no_write",
                          "source_corpus_id": V3_CORPUS_ID,
                          "target_corpus_id": V4_CORPUS_ID,
                          "splits": V4_SPLITS}, sort_keys=True))
        return 0
    try:
        result = derive(args.source, args.output)
    except (DerivationError, OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "local_derivation_rejected_no_scoring",
                          "reason": str(exc) if isinstance(exc, DerivationError)
                          else type(exc).__name__}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
