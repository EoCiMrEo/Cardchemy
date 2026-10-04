"""Freeze a new public source-ID evaluation without network or provider access.

Inputs are an acquired eight-PDF manifest, an authored 96-group slate, two
independent page-and-cue reviews, and conflict-only adjudication. This tool
does not author questions, acquire PDFs, score responses, or open old fixtures.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import tempfile
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from pypdf import PdfReader


CORPUS_ID = "illinois-ece448-sp2022-source-id-v2"
MANIFEST_SCHEMA = "cardchemy_public_source_id_fresh_corpus_manifest_v2"
PACKET_SCHEMA = "fresh_public_source_id_v2_packet"
LABELS_SCHEMA = "fresh_public_source_id_v2_labels"
FREEZE_SCHEMA = "fresh_public_source_id_v2_freeze"
REVIEW_SCHEMA = "fresh_public_source_id_v2_review"
ADJUDICATION_SCHEMA = "fresh_public_source_id_v2_adjudication"
AUTHORED_SCHEMA = "fresh_public_source_id_v2_authored"
OVERLAP_DIAGNOSTIC_SCHEMA = "fresh_public_source_id_v2_overlap_diagnostic"
OVERLAP_REVIEW_SCHEMA = "fresh_public_source_id_v2_overlap_review"
OVERLAP_EXCLUSION_THRESHOLD = 0.5
OVERLAP_METHOD = "normalized_5gram_jaccard_v1"
SOURCE_BASE = "https://courses.grainger.illinois.edu/ece448/sp2022/slides/"
SCHEDULE_URL = "https://courses.grainger.illinois.edu/ece448/sp2022/lectures.html"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
PREREGISTRATION_SHA256 = "4dd13466920e66086cba7c433d6631d1944a71e9205f597387d61b08ae181fdc"
EXPECTED = {
    "lec04": ("calibration", 32),
    "lec05": ("calibration", 33),
    "lec06": ("calibration", 40),
    "lec07": ("calibration", 31),
    "lec08": ("heldout", 46),
    "lec09": ("heldout", 33),
    "lec11": ("heldout", 27),
    "lec13": ("heldout", 36),
}
SPLITS = ("calibration", "heldout")
FORMS = ("direct", "paraphrase", "followup", "no_useful")
HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
FIRST_PAGE_CC_BY_4 = re.compile(r"\bCC\s*-?\s*BY\s*-?\s*4[.]0\b", re.IGNORECASE)


class FreezeError(ValueError):
    """An input failed the preregistered freeze contract."""


def _fail(message: str) -> None:
    raise FreezeError(message)


def _require(condition: bool, message: str) -> None:
    if not condition:
        _fail(message)


def _keys(value: Any, required: set[str], allowed: set[str] | None = None) -> dict[str, Any]:
    _require(isinstance(value, dict), "expected object")
    _require(required <= value.keys(), f"missing fields: {sorted(required - value.keys())}")
    _require(value.keys() <= (allowed or required), f"unexpected fields: {sorted(value.keys() - (allowed or required))}")
    return value


def _nonempty(value: Any, label: str, maximum: int) -> str:
    _require(isinstance(value, str) and value == value.strip() and 0 < len(value) <= maximum, f"invalid {label}")
    return value


def _safe_id(value: Any, label: str) -> str:
    value = _nonempty(value, label, 64)
    _require(bool(SAFE_ID.fullmatch(value)), f"invalid {label}")
    return value


def _sha(value: Any, label: str) -> str:
    _require(isinstance(value, str) and bool(HEX_SHA256.fullmatch(value)), f"invalid {label}")
    return value


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    _fail(f"non-finite JSON constant {value}")


def read_json(path: Path) -> tuple[Any, str]:
    raw = path.read_bytes()
    _require(len(raw) <= 10_000_000, "input JSON exceeds 10 MB")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_pairs, parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FreezeError("invalid UTF-8 JSON") from exc
    return value, sha256_bytes(raw)


def _verified_child(root: Path, name: Any, *, comparison: bool = False) -> Path:
    allowed = ({"lectures.html"} | {f"{key}.pdf" for key in EXPECTED})
    if comparison:
        _require(isinstance(name, str) and bool(re.fullmatch(r"(?:lec[0-9]{2}|illinois-(?:17|37))[.]pdf", name)),
                 "unexpected comparison path")
    else:
        _require(isinstance(name, str) and name in allowed, "unexpected source path")
    path = root / name
    _require(path.is_file() and not path.is_symlink(), "source file missing or symlinked")
    _require(path.resolve().parent == root.resolve(), "source path escapes manifest directory")
    return path


def _verify_file(root: Path, record: dict[str, Any], maximum_bytes: int = 10_485_760,
                 *, comparison: bool = False) -> bytes:
    path = _verified_child(root, record.get("path"), comparison=comparison)
    expected_bytes = record.get("bytes")
    _require(type(expected_bytes) is int and 0 < expected_bytes <= maximum_bytes, "invalid source byte count")
    actual = path.read_bytes()
    _require(len(actual) == expected_bytes and sha256_bytes(actual) == _sha(record.get("sha256"), "source SHA-256"), "source hash/size mismatch")
    return actual


class _ScheduleLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            for key, value in attrs:
                if key.lower() == "href" and value:
                    self.urls.add(urljoin(SCHEDULE_URL, value))


def load_verified_pages(manifest: dict[str, Any], manifest_path: Path) -> tuple[dict[tuple[str, int], str], list[dict[str, Any]]]:
    """Recheck exact public roster, local bytes, and PDF page extraction."""
    _require(manifest.get("schema") == MANIFEST_SCHEMA and manifest.get("corpus_id") == CORPUS_ID and
             manifest.get("preregistration_sha256") == PREREGISTRATION_SHA256, "wrong manifest identity")
    _require(manifest.get("license_url") == LICENSE_URL and manifest.get("all_pdf_first_pages_cc_by_4") is True and
             manifest.get("labels_written") is False, "manifest license/unlabeled state mismatch")
    _require(manifest.get("content_overlap_review") == "required_before_question_authoring", "unexpected overlap state")
    schedule = _keys(manifest.get("schedule"), {"url", "path", "bytes", "sha256"})
    _require(schedule["url"] == SCHEDULE_URL, "wrong schedule URL")
    _require(schedule["path"] == "lectures.html", "wrong schedule path")
    schedule_raw = _verify_file(manifest_path.parent, schedule, 524_288)
    links = _ScheduleLinks()
    links.feed(schedule_raw.decode("utf-8", errors="replace"))
    _require({f"{SOURCE_BASE}{document_id}.pdf" for document_id in EXPECTED} <= links.urls, "schedule missing preregistered PDF link")
    documents = manifest.get("documents")
    _require(isinstance(documents, list) and len(documents) == 8, "manifest needs eight PDFs")
    pages: dict[tuple[str, int], str] = {}
    documents_out: list[dict[str, Any]] = []
    seen: set[str] = set()
    seen_digests: set[str] = set()
    for document in documents:
        _keys(document, {"split", "url", "path", "bytes", "sha256", "pages", "alphanumeric_text_chars", "pages_with_at_least_40_alphanumeric_chars", "first_page_license", "license_url"})
        document_id = Path(document["path"]).stem if isinstance(document["path"], str) else ""
        _require(document_id in EXPECTED and document_id not in seen, "unknown or repeated PDF")
        seen.add(document_id)
        split, expected_pages = EXPECTED[document_id]
        _require(document["split"] == split and document["url"] == f"{SOURCE_BASE}{document_id}.pdf" and
                 document["license_url"] == LICENSE_URL, "PDF roster/split mismatch")
        _require(document["pages"] == expected_pages and document["first_page_license"] == "CC BY 4.0", "PDF page/license metadata mismatch")
        raw = _verify_file(manifest_path.parent, document)
        _require(document["sha256"] not in seen_digests, "duplicate PDF bytes")
        seen_digests.add(document["sha256"])
        _require(raw.startswith(b"%PDF-"), "PDF signature mismatch")
        try:
            reader = PdfReader(io.BytesIO(raw), strict=False)
            _require(not reader.is_encrypted and len(reader.pages) == expected_pages, "PDF page count or encryption mismatch")
            texts = [(page.extract_text() or "") for page in reader.pages]
        except FreezeError:
            raise
        except Exception as exc:
            raise FreezeError("PDF parse/extraction failed") from exc
        alnum = [sum(char.isalnum() for char in text) for text in texts]
        _require(bool(FIRST_PAGE_CC_BY_4.search(texts[0])), "PDF title-page CC BY 4.0 declaration missing")
        _require(sum(alnum) >= 1500 and sum(count >= 40 for count in alnum) >= max(3, expected_pages // 3), "PDF text coverage too low")
        _require(sum(alnum) == document["alphanumeric_text_chars"] and sum(count >= 40 for count in alnum) == document["pages_with_at_least_40_alphanumeric_chars"], "PDF text metadata mismatch")
        for page, text in enumerate(texts, start=1):
            pages[(document_id, page)] = text
        documents_out.append({"document_id": document_id, "sha256": document["sha256"], "pages": expected_pages, "split": split})
    _require(seen == EXPECTED.keys(), "incomplete PDF roster")
    return pages, sorted(documents_out, key=lambda item: item["document_id"])


def validate_overlap_gate(manifest: dict[str, Any], manifest_sha256: str, diagnostic: dict[str, Any],
                          diagnostic_sha256: str, review: dict[str, Any]) -> str:
    """Admit an independent human overlap decision; numbers alone never pass."""
    _sha(manifest_sha256, "manifest SHA-256")
    _sha(diagnostic_sha256, "overlap diagnostic SHA-256")
    records = manifest.get("comparison_manifests")
    _require(isinstance(records, list) and len(records) == 2, "two source comparison manifests required")
    comparison = {}
    for record in records:
        record = _keys(record, {"role", "manifest_sha256", "document_count"})
        role = record["role"]
        _require(role in {"ece448_sp2020", "reserved_illinois"} and role not in comparison, "unknown comparison role")
        _sha(record["manifest_sha256"], "comparison manifest SHA-256")
        _require(record["document_count"] == (14 if role == "ece448_sp2020" else 2), "comparison document count mismatch")
        comparison[role] = record["manifest_sha256"]
    _require(set(comparison) == {"ece448_sp2020", "reserved_illinois"}, "missing comparison role")
    diagnostic = _keys(diagnostic, {"schema_version", "corpus_id", "source_manifest_sha256",
                                    "comparison_manifest_sha256", "method", "screening_only", "exclusion_threshold", "per_new_document",
                                    "new_page_count", "comparison_page_count"})
    _require(diagnostic["schema_version"] == OVERLAP_DIAGNOSTIC_SCHEMA and diagnostic["corpus_id"] == CORPUS_ID and
             diagnostic["source_manifest_sha256"] == manifest_sha256 and
             diagnostic["comparison_manifest_sha256"] == comparison and
             diagnostic["method"] == OVERLAP_METHOD and diagnostic["screening_only"] is True and
             type(diagnostic["exclusion_threshold"]) is float and
             diagnostic["exclusion_threshold"] == OVERLAP_EXCLUSION_THRESHOLD,
             "overlap diagnostic identity mismatch")
    _require(type(diagnostic["new_page_count"]) is int and diagnostic["new_page_count"] == 278 and
             type(diagnostic["comparison_page_count"]) is int and diagnostic["comparison_page_count"] > 0,
             "overlap diagnostic page counts invalid")
    rows = diagnostic["per_new_document"]
    _require(isinstance(rows, list) and len(rows) == 8, "overlap diagnostic needs eight documents")
    ids: set[str] = set()
    for row in rows:
        row = _keys(row, {"document_id", "max_page_jaccard", "exact_normalized_page_matches", "excluded_pages"})
        did = _safe_id(row["document_id"], "overlap document ID")
        _require(did in EXPECTED and did not in ids, "overlap document roster mismatch")
        ids.add(did)
        score = row["max_page_jaccard"]
        exact = row["exact_normalized_page_matches"]
        excluded = row["excluded_pages"]
        _require(type(score) in (int, float) and 0 <= score <= 1 and
                 type(exact) is int and 0 <= exact <= EXPECTED[did][1] and
                 type(excluded) is list and
                 all(type(page) is int and 1 <= page <= EXPECTED[did][1] for page in excluded) and
                 excluded == sorted(set(excluded)) and exact <= len(excluded),
                 "overlap metrics invalid")
    _require(ids == EXPECTED.keys(), "overlap diagnostic incomplete")
    review = _keys(review, {"schema_version", "corpus_id", "source_manifest_sha256", "diagnostic_sha256",
                            "reviewer_id", "decision", "reviewed_document_ids", "reviewed_comparison_roles", "attestation"})
    _require(review["schema_version"] == OVERLAP_REVIEW_SCHEMA and review["corpus_id"] == CORPUS_ID and
             review["source_manifest_sha256"] == manifest_sha256 and
             review["diagnostic_sha256"] == diagnostic_sha256 and
             review["decision"] == "approved_for_question_authoring" and
             review["attestation"] == "independent_blinded_content_overlap_review" and
             review["reviewed_document_ids"] == sorted(EXPECTED) and
             review["reviewed_comparison_roles"] == sorted(comparison), "overlap review not approved/bound")
    return _safe_id(review["reviewer_id"], "overlap reviewer ID")


def _token_shingles(value: str) -> tuple[tuple[str, ...], set[tuple[str, ...]]]:
    tokens = tuple(re.findall(r"[^\W_]+", value.casefold(), flags=re.UNICODE))
    return tokens, {tokens[index:index + 5] for index in range(max(0, len(tokens) - 4))}


def overlap_diagnostic(new_pages: dict[tuple[str, int], str], comparison_pages: dict[tuple[str, int], str],
                       manifest_sha256: str, comparison_manifest_sha256: dict[str, str]) -> dict[str, Any]:
    """Screen public PDF text only; similarity cannot establish independence."""
    _require(set(comparison_manifest_sha256) == {"ece448_sp2020", "reserved_illinois"}, "comparison roles invalid")
    _require(set(document_id for document_id, _ in new_pages) == EXPECTED.keys() and
             len(new_pages) == 278 and comparison_pages, "overlap source pages incomplete")
    postings: dict[tuple[str, ...], set[int]] = {}
    old_shingles: list[set[tuple[str, ...]]] = []
    old_token_sequences: set[tuple[str, ...]] = set()
    for text in comparison_pages.values():
        tokens, shingles = _token_shingles(text)
        old_token_sequences.add(tokens)
        index = len(old_shingles)
        old_shingles.append(shingles)
        for shingle in shingles:
            postings.setdefault(shingle, set()).add(index)
    max_by_doc = {document_id: 0.0 for document_id in EXPECTED}
    exact_by_doc = Counter()
    excluded_by_doc: dict[str, list[int]] = {document_id: [] for document_id in EXPECTED}
    for (document_id, page_number), text in new_pages.items():
        tokens, shingles = _token_shingles(text)
        if tokens and tokens in old_token_sequences:
            exact_by_doc[document_id] += 1
        candidates: set[int] = set()
        for shingle in shingles:
            candidates.update(postings.get(shingle, ()))
        best_page_score = 0.0
        for index in candidates:
            union = len(shingles | old_shingles[index])
            score = len(shingles & old_shingles[index]) / union if union else 0.0
            if score > max_by_doc[document_id]:
                max_by_doc[document_id] = score
            if score > best_page_score:
                best_page_score = score
        if best_page_score >= OVERLAP_EXCLUSION_THRESHOLD or (tokens and tokens in old_token_sequences):
            excluded_by_doc[document_id].append(page_number)
    return {"schema_version": OVERLAP_DIAGNOSTIC_SCHEMA, "corpus_id": CORPUS_ID,
            "source_manifest_sha256": _sha(manifest_sha256, "manifest SHA-256"),
            "comparison_manifest_sha256": {role: _sha(digest, "comparison SHA-256")
                                           for role, digest in comparison_manifest_sha256.items()},
            "method": OVERLAP_METHOD, "screening_only": True,
            "exclusion_threshold": OVERLAP_EXCLUSION_THRESHOLD,
            "new_page_count": len(new_pages), "comparison_page_count": len(comparison_pages),
            "per_new_document": [{"document_id": document_id,
                                  "max_page_jaccard": round(max_by_doc[document_id], 6),
                                  "exact_normalized_page_matches": exact_by_doc[document_id],
                                  "excluded_pages": sorted(excluded_by_doc[document_id])}
                                 for document_id in sorted(EXPECTED)]}


def _source_pdf_pages(raw: bytes, expected_pages: int) -> list[str]:
    _require(raw.startswith(b"%PDF-"), "comparison PDF signature mismatch")
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        _require(not reader.is_encrypted and len(reader.pages) == expected_pages, "comparison PDF page/encryption mismatch")
        return [(page.extract_text() or "") for page in reader.pages]
    except FreezeError:
        raise
    except Exception as exc:
        raise FreezeError("comparison PDF parse/extraction failed") from exc


def scan_overlap_files(manifest_path: Path, sp2020_manifest_path: Path,
                       reserved_manifest_path: Path, reserved_pdf_dir: Path) -> Path:
    """Write a source-only numeric screen to a new OS-Temp directory."""
    manifest, manifest_hash = read_json(manifest_path)
    new_pages, _ = load_verified_pages(manifest, manifest_path)
    records = manifest.get("comparison_manifests")
    _require(isinstance(records, list) and len(records) == 2, "comparison manifests missing")
    pinned = {row["role"]: row["manifest_sha256"] for row in records}
    old_manifest, old_hash = read_json(sp2020_manifest_path)
    reserved_manifest, reserved_hash = read_json(reserved_manifest_path)
    _require(old_hash == pinned.get("ece448_sp2020") and reserved_hash == pinned.get("reserved_illinois"),
             "comparison manifest hash mismatch")
    _require(old_manifest.get("schema") == "cardchemy_public_reading_corpus_manifest_v1" and
             old_manifest.get("corpus_id") == "illinois-ece448-sp2020-reading-usefulness-v4" and
             old_manifest.get("labels_written") is False, "wrong old public source manifest")
    _require(reserved_manifest.get("schema") == "cardchemy_public_source_metadata_comparison_v1" and
             reserved_manifest.get("corpus_id") == "illinois-ece448-sp2020-reserved" and
             reserved_manifest.get("labels_included") is False, "wrong reserved source metadata")
    comparison_pages: dict[tuple[str, int], str] = {}
    old_documents = old_manifest.get("documents")
    _require(isinstance(old_documents, list) and len(old_documents) == 14, "old public source roster invalid")
    for row in old_documents:
        _require(isinstance(row, dict) and isinstance(row.get("path"), str) and
                 bool(re.fullmatch(r"lec[0-9]{2}[.]pdf", row["path"])), "old source path invalid")
        raw = _verify_file(sp2020_manifest_path.parent, row, comparison=True)
        page_count = row.get("pages")
        _require(type(page_count) is int and 1 <= page_count <= 60, "old source pages invalid")
        for page, text in enumerate(_source_pdf_pages(raw, page_count), start=1):
            comparison_pages[(f"sp2020-{row['path']}", page)] = text
    reserved_documents = reserved_manifest.get("documents")
    _require(isinstance(reserved_documents, list) and len(reserved_documents) == 2, "reserved source roster invalid")
    for number, row in zip((17, 37), reserved_documents, strict=True):
        _require(isinstance(row, dict) and row.get("url") ==
                 f"https://courses.grainger.illinois.edu/ece448/sp2020/slides/lec{number:02d}.pdf", "reserved URL mismatch")
        filename = f"illinois-{number}.pdf"
        raw = _verify_file(reserved_pdf_dir, {"path": filename, "bytes": row.get("bytes"),
                                              "sha256": row.get("sha256")}, comparison=True)
        page_count = row.get("pages")
        _require(type(page_count) is int and 1 <= page_count <= 60, "reserved source pages invalid")
        for page, text in enumerate(_source_pdf_pages(raw, page_count), start=1):
            comparison_pages[(f"reserved-{number}", page)] = text
    diagnostic = overlap_diagnostic(new_pages, comparison_pages, manifest_hash, pinned)
    output = Path(tempfile.mkdtemp(prefix="cardchemy-fresh-public-overlap-v2-", dir=tempfile.gettempdir()))
    with (output / "overlap-diagnostic.json").open("xb") as handle:
        handle.write(canonical_bytes(diagnostic))
    return output / "overlap-diagnostic.json"


def _review_index(review: Any, group_ids: set[str], slate: dict[str, set[str]],
                  *, expected_groups: int = 96) -> tuple[str, dict[tuple[str, str], tuple[bool, bool]]]:
    review = _keys(review, {"schema_version", "reviewer_id", "groups"})
    _require(review["schema_version"] == REVIEW_SCHEMA, "wrong review version")
    reviewer_id = _safe_id(review["reviewer_id"], "reviewer ID")
    _require(isinstance(review["groups"], list) and len(review["groups"]) == expected_groups,
             f"review needs {expected_groups} groups")
    indexed: dict[tuple[str, str], tuple[bool, bool]] = {}
    seen_groups: set[str] = set()
    for group in review["groups"]:
        group = _keys(group, {"group_id", "candidates"})
        group_id = _safe_id(group["group_id"], "review group ID")
        _require(group_id in group_ids and group_id not in seen_groups, "review group mismatch")
        seen_groups.add(group_id)
        candidates = group["candidates"]
        _require(isinstance(candidates, list) and len(candidates) == 4, "review needs four candidates")
        for candidate in candidates:
            candidate = _keys(candidate, {"id", "page_useful", "cue_useful"})
            cid = _safe_id(candidate["id"], "review candidate ID")
            _require(cid in slate[group_id] and (group_id, cid) not in indexed, "review candidate mismatch")
            _require(type(candidate["page_useful"]) is bool and type(candidate["cue_useful"]) is bool, "review labels must be booleans")
            _require(not candidate["cue_useful"] or candidate["page_useful"], "useful cue requires useful page")
            indexed[(group_id, cid)] = (candidate["page_useful"], candidate["cue_useful"])
    _require(seen_groups == group_ids and len(indexed) == expected_groups * 4, "incomplete review")
    return reviewer_id, indexed


def _adjudicated_index(adjudication: Any, disagreements: set[tuple[str, str]], reviewer_ids: set[str]) -> tuple[str, dict[tuple[str, str], tuple[bool, bool]]]:
    adjudication = _keys(adjudication, {"schema_version", "reviewer_id", "decisions"})
    _require(adjudication["schema_version"] == ADJUDICATION_SCHEMA, "wrong adjudication version")
    reviewer_id = _safe_id(adjudication["reviewer_id"], "adjudicator ID")
    _require(reviewer_id not in reviewer_ids, "adjudicator must be independent")
    decisions = adjudication["decisions"]
    _require(isinstance(decisions, list) and len(decisions) == len(disagreements), "adjudication must cover exact disagreements")
    indexed: dict[tuple[str, str], tuple[bool, bool]] = {}
    for decision in decisions:
        decision = _keys(decision, {"group_id", "id", "page_useful", "cue_useful"})
        key = (_safe_id(decision["group_id"], "adjudication group ID"), _safe_id(decision["id"], "adjudication candidate ID"))
        _require(key in disagreements and key not in indexed, "unexpected/duplicate adjudication")
        _require(type(decision["page_useful"]) is bool and type(decision["cue_useful"]) is bool, "adjudication labels must be booleans")
        _require(not decision["cue_useful"] or decision["page_useful"], "useful cue requires useful page")
        indexed[key] = (decision["page_useful"], decision["cue_useful"])
    return reviewer_id, indexed


def build_artifacts(
    manifest: dict[str, Any], authored: dict[str, Any], review_a: dict[str, Any], review_b: dict[str, Any],
    adjudication: dict[str, Any], pages: dict[tuple[str, int], str], documents: list[dict[str, Any]],
    source_manifest_sha256: str, overlap_review_sha256: str,
    excluded_pages: set[tuple[str, int]] | None = None,
    *, reserve_bundle: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build strictly separated packet/labels objects from already-extracted pages."""
    _require(manifest.get("schema") == MANIFEST_SCHEMA and manifest.get("corpus_id") == CORPUS_ID and
             manifest.get("preregistration_sha256") == PREREGISTRATION_SHA256, "wrong manifest identity")
    _sha(source_manifest_sha256, "manifest SHA-256")
    _sha(overlap_review_sha256, "overlap review SHA-256")
    _require(manifest.get("content_overlap_review") == "required_before_question_authoring", "unexpected overlap state")
    authored = _keys(authored, {"schema_version", "corpus_id", "source_manifest_sha256", "overlap_review_sha256", "author_id", "groups"})
    _require(authored["schema_version"] == AUTHORED_SCHEMA and authored["corpus_id"] == CORPUS_ID, "wrong authored identity")
    _require(authored["source_manifest_sha256"] == source_manifest_sha256, "authored manifest hash mismatch")
    _require(authored["overlap_review_sha256"] == overlap_review_sha256, "authored overlap-review hash mismatch")
    author_id = _safe_id(authored["author_id"], "author ID")
    original_groups = authored["groups"]
    _require(isinstance(original_groups, list) and len(original_groups) == 96, "authored slate needs 96 groups")
    reserve_author_id = None
    reserve_groups: list[dict[str, Any]] = []
    if reserve_bundle is not None:
        reserve_authored = _keys(reserve_bundle[0], {"schema_version", "corpus_id",
                                                     "source_manifest_sha256", "overlap_review_sha256",
                                                     "author_id", "groups"})
        _require(reserve_authored["schema_version"] == "fresh_public_source_id_v2_reserve_authored" and
                 reserve_authored["corpus_id"] == CORPUS_ID and
                 reserve_authored["source_manifest_sha256"] == source_manifest_sha256 and
                 reserve_authored["overlap_review_sha256"] == overlap_review_sha256,
                 "reserve authored identity mismatch")
        reserve_author_id = _safe_id(reserve_authored["author_id"], "reserve author ID")
        _require(reserve_author_id != author_id, "reserve author must be independent")
        reserve_groups = reserve_authored["groups"]
        _require(isinstance(reserve_groups, list) and len(reserve_groups) == 30,
                 "reserve slate needs all 30 groups")
    groups = [*original_groups, *reserve_groups]
    split_documents = {split: {doc["document_id"] for doc in documents if doc["split"] == split} for split in SPLITS}
    _require(all(len(split_documents[split]) == 4 for split in SPLITS) and not (split_documents["calibration"] & split_documents["heldout"]), "four disjoint PDFs per split required")
    _require(len({doc["sha256"] for doc in documents}) == 8, "eight distinct PDF hashes required")
    excluded_pages = excluded_pages or set()
    packet_groups: dict[str, list[dict[str, Any]]] = {split: [] for split in SPLITS}
    slate: dict[str, set[str]] = {}
    group_splits: dict[str, str] = {}
    group_forms: dict[str, str] = {}
    group_origins: dict[str, str] = {}
    normalized_questions: set[str] = set()
    for group_index, group in enumerate(groups):
        group = _keys(group, {"group_id", "split", "form", "question", "candidates"})
        gid = _safe_id(group["group_id"], "group ID")
        _require(gid not in slate, "duplicate group ID")
        split, form = group["split"], group["form"]
        _require(split in SPLITS and form in FORMS, "invalid split/form")
        question = _nonempty(group["question"], "question", 1024)
        normalized_question = " ".join(question.casefold().split())
        _require(normalized_question not in normalized_questions, "duplicate question across slates")
        normalized_questions.add(normalized_question)
        candidate_inputs = group["candidates"]
        _require(isinstance(candidate_inputs, list) and len(candidate_inputs) == 4, "each group needs four candidates")
        packet_candidates: list[dict[str, Any]] = []
        ids: set[str] = set()
        represented_documents: set[str] = set()
        represented_pages: set[tuple[str, int]] = set()
        for candidate in candidate_inputs:
            candidate = _keys(candidate, {"id", "document_id", "page", "context_start", "context_end", "cue_start", "cue_end"})
            cid = _safe_id(candidate["id"], "candidate ID")
            document_id = _safe_id(candidate["document_id"], "document ID")
            page = candidate["page"]
            _require(cid not in ids and document_id in split_documents[split], "candidate ID/PDF mismatch")
            _require(type(page) is int and (document_id, page) in pages, "candidate page mismatch")
            _require((document_id, page) not in excluded_pages, "candidate page overlaps prior public corpus")
            _require((document_id, page) not in represented_pages, "duplicate candidate page")
            ids.add(cid)
            represented_documents.add(document_id)
            represented_pages.add((document_id, page))
            text = pages[(document_id, page)]
            context_start, context_end = candidate["context_start"], candidate["context_end"]
            cue_start, cue_end = candidate["cue_start"], candidate["cue_end"]
            _require(all(type(item) is int for item in (context_start, context_end, cue_start, cue_end)), "offsets must be integers")
            _require(0 <= context_start <= cue_start < cue_end <= context_end <= len(text), "invalid or noncontiguous offsets")
            context, cue = text[context_start:context_end], text[cue_start:cue_end]
            _require(0 < len(context) <= 1200 and 0 < len(cue) <= 480 and context.strip() and cue.strip(), "source window exceeds bounds/empty")
            packet_candidates.append({"id": cid, "document_id": document_id, "page": page,
                                      "context_start": context_start, "context_end": context_end, "context": context,
                                      "cue_start": cue_start, "cue_end": cue_end, "cue": cue,
                                      "page_text_sha256": sha256_bytes(text.encode("utf-8"))})
        _require(len(represented_documents) == 2, "exactly two PDFs per slate required")
        slate[gid] = ids
        group_splits[gid] = split
        group_forms[gid] = form
        group_origins[gid] = "original" if group_index < 96 else "reserve"
        packet_groups[split].append({"group_id": gid, "form": form, "question": question, "candidates": packet_candidates})
    for split in SPLITS:
        original_in_split = [group for group in packet_groups[split]
                             if group_origins[group["group_id"]] == "original"]
        _require(len(original_in_split) == 48 and
                 Counter(group["form"] for group in original_in_split) ==
                 {form: 12 for form in FORMS}, "each original split needs 12 groups per form")
        if reserve_bundle is not None:
            reserve_in_split = [group for group in packet_groups[split]
                                if group_origins[group["group_id"]] == "reserve"]
            reserve_each = 6 if split == "calibration" else 4
            _require(len(reserve_in_split) == 3 * reserve_each and
                     Counter(group["form"] for group in reserve_in_split) ==
                     {form: reserve_each for form in FORMS[:3]},
                     "reserve split/form balance mismatch")
    original_slate = {gid: ids for gid, ids in slate.items() if group_origins[gid] == "original"}
    reviewer_a, a = _review_index(review_a, set(original_slate), original_slate)
    reviewer_b, b = _review_index(review_b, set(original_slate), original_slate)
    _require(reviewer_a != reviewer_b, "two distinct independent reviewers required")
    _require(author_id not in {reviewer_a, reviewer_b}, "author cannot review source labels")
    disagreements = {key for key in a if a[key] != b[key]}
    adjudicator, resolved = _adjudicated_index(adjudication, disagreements, {reviewer_a, reviewer_b})
    _require(author_id != adjudicator, "author cannot adjudicate source labels")
    final = {key: resolved[key] if key in disagreements else a[key] for key in a}
    reviewer_ids = [reviewer_a, reviewer_b]
    adjudicator_ids = [adjudicator]
    if reserve_bundle is not None:
        reserve_slate = {gid: ids for gid, ids in slate.items() if group_origins[gid] == "reserve"}
        reserve_a_id, reserve_a = _review_index(reserve_bundle[1], set(reserve_slate),
                                                reserve_slate, expected_groups=30)
        reserve_b_id, reserve_b = _review_index(reserve_bundle[2], set(reserve_slate),
                                                reserve_slate, expected_groups=30)
        _require(reserve_a_id != reserve_b_id, "two independent reserve reviewers required")
        reserve_disagreements = {key for key in reserve_a if reserve_a[key] != reserve_b[key]}
        reserve_adjudicator, reserve_resolved = _adjudicated_index(
            reserve_bundle[3], reserve_disagreements, {reserve_a_id, reserve_b_id})
        _require({author_id, reserve_author_id}.isdisjoint(
            {reviewer_a, reviewer_b, adjudicator, reserve_a_id, reserve_b_id,
             reserve_adjudicator}), "authors cannot review or adjudicate")
        final.update({key: reserve_resolved[key] if key in reserve_disagreements
                      else reserve_a[key] for key in reserve_a})
        reviewer_ids.extend((reserve_a_id, reserve_b_id))
        adjudicator_ids.append(reserve_adjudicator)
    artifacts: dict[str, dict[str, Any]] = {}
    for split in SPLITS:
        # Source-form and gold-card counts must not leak through the packet's
        # fields, authored IDs, or the authored candidate/group ordering.
        sort_key = lambda group: sha256_bytes(  # noqa: E731
            f"{source_manifest_sha256}:group:{group['group_id']}".encode("utf-8"))
        if reserve_bundle is None:
            shuffled_groups = sorted(packet_groups[split], key=sort_key)
        else:
            # Preserve the original G001..G048 issue order exactly. Reserve
            # questions follow as G049.., so no original case is replaced.
            shuffled_groups = sorted(
                (group for group in packet_groups[split]
                 if group_origins[group["group_id"]] == "original"), key=sort_key)
            shuffled_groups += sorted(
                (group for group in packet_groups[split]
                 if group_origins[group["group_id"]] == "reserve"), key=sort_key)
        issued_groups: list[dict[str, Any]] = []
        labels_groups: list[dict[str, Any]] = []
        strata = Counter()
        for group_number, group in enumerate(shuffled_groups, start=1):
            author_gid = group["group_id"]
            issued_gid = f"G{group_number:03d}"
            shuffled_candidates = sorted(group["candidates"], key=lambda candidate: sha256_bytes(
                f"{source_manifest_sha256}:candidate:{author_gid}:{candidate['id']}".encode("utf-8")))
            issued_candidates: list[dict[str, Any]] = []
            issued_labels: list[dict[str, Any]] = []
            for candidate_number, candidate in enumerate(shuffled_candidates, start=1):
                author_cid = candidate["id"]
                issued_cid = f"S{candidate_number:02d}"
                issued_candidates.append({**candidate, "id": issued_cid})
                page_useful, cue_useful = final[(author_gid, author_cid)]
                issued_labels.append({"id": issued_cid, "page_useful": page_useful, "cue_useful": cue_useful})
            useful_count = sum(item["page_useful"] and item["cue_useful"] for item in issued_labels)
            if group_origins[author_gid] == "original" and group_forms[author_gid] == "no_useful":
                _require(useful_count == 0, "no-useful group has a useful page-and-cue card")
            elif group_origins[author_gid] == "original":
                _require(1 <= useful_count <= 3, "positive group needs one to three useful cards")
                strata[useful_count] += 1
            else:
                _require(0 <= useful_count <= 4, "reserve useful-card count invalid")
                if useful_count:
                    strata[useful_count] += 1
            issued_groups.append({"group_id": issued_gid, "question": group["question"], "candidates": issued_candidates})
            label_group = {"group_id": issued_gid, "author_group_id": author_gid,
                           "form": group_forms[author_gid], "candidates": issued_labels}
            if reserve_bundle is not None:
                label_group["origin"] = group_origins[author_gid]
            labels_groups.append(label_group)
        if reserve_bundle is None:
            _require(strata == {1: 12, 2: 12, 3: 12}, "each split needs twelve 1/2/3-useful strata")
        else:
            _require(all(strata[amount] >= 12 for amount in (1, 2, 3)),
                     "augmented split needs at least twelve 1/2/3-useful strata")
            _require(strata[4] == (2 if split == "calibration" else 0),
                     "approved reserve overflow roster changed")
        packet_schema = ("fresh_public_source_id_v2_augmented_packet"
                         if reserve_bundle is not None else PACKET_SCHEMA)
        labels_schema = ("fresh_public_source_id_v2_augmented_labels"
                         if reserve_bundle is not None else LABELS_SCHEMA)
        packet = {"schema_version": packet_schema, "corpus_id": CORPUS_ID,
                  "source_manifest_sha256": source_manifest_sha256,
                  "split": split, "documents": [{key: doc[key] for key in ("document_id", "sha256", "pages")}
                                                for doc in documents if doc["split"] == split], "groups": issued_groups}
        packet["documents"].sort(key=lambda document: document["document_id"])
        packet_path = f"{split}/packet.json"
        artifacts[packet_path] = packet
        artifacts[f"{split}/labels.json"] = {"schema_version": labels_schema, "corpus_id": CORPUS_ID,
                                                "source_manifest_sha256": source_manifest_sha256, "split": split,
                                                "packet_sha256": sha256_bytes(canonical_bytes(packet)),
                                                "reviewer_ids": reviewer_ids,
                                                "adjudicator_id": adjudicator_ids if reserve_bundle is not None else adjudicator,
                                                "disagreement_count": sum(group_splits[gid] == split for gid, _ in disagreements) +
                                                (sum(group_splits[gid] == split for gid, _ in reserve_disagreements)
                                                 if reserve_bundle is not None else 0),
                                                "groups": labels_groups}
    return artifacts


def freeze_files(manifest_path: Path, authored_path: Path, review_a_path: Path, review_b_path: Path,
                 adjudication_path: Path, overlap_diagnostic_path: Path, overlap_review_path: Path) -> Path:
    """Verify inputs and create an exclusive OS-Temp freeze directory."""
    manifest, manifest_hash = read_json(manifest_path)
    authored, authored_hash = read_json(authored_path)
    review_a, review_a_hash = read_json(review_a_path)
    review_b, review_b_hash = read_json(review_b_path)
    adjudication, adjudication_hash = read_json(adjudication_path)
    overlap_diagnostic, overlap_diagnostic_hash = read_json(overlap_diagnostic_path)
    overlap_review, overlap_review_hash = read_json(overlap_review_path)
    overlap_reviewer = validate_overlap_gate(manifest, manifest_hash, overlap_diagnostic,
                                             overlap_diagnostic_hash, overlap_review)
    excluded_pages = {(row["document_id"], page) for row in overlap_diagnostic["per_new_document"]
                      for page in row["excluded_pages"]}
    pages, documents = load_verified_pages(manifest, manifest_path)
    artifacts = build_artifacts(manifest, authored, review_a, review_b, adjudication, pages,
                                documents, manifest_hash, overlap_review_hash, excluded_pages)
    _require(overlap_reviewer not in artifacts["calibration/labels.json"]["reviewer_ids"] and
             overlap_reviewer != artifacts["calibration/labels.json"]["adjudicator_id"],
             "overlap reviewer must be independent of source-label reviewers")
    _require(overlap_reviewer != authored["author_id"],
             "overlap reviewer must be independent of question author")
    output = Path(tempfile.mkdtemp(prefix="cardchemy-fresh-public-source-id-v2-", dir=tempfile.gettempdir()))
    hashes: dict[str, str] = {}
    for relative, value in artifacts.items():
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        data = canonical_bytes(value)
        with target.open("xb") as handle:
            handle.write(data)
        hashes[relative] = sha256_bytes(data)
    freeze = {"schema_version": FREEZE_SCHEMA, "corpus_id": CORPUS_ID, "source_manifest_sha256": manifest_hash,
              "input_sha256": {"authored": authored_hash, "review_a": review_a_hash,
                               "review_b": review_b_hash, "adjudication": adjudication_hash,
                               "overlap_review": overlap_review_hash},
              "overlap_diagnostic_sha256": overlap_diagnostic_hash,
              "files": hashes}
    with (output / "freeze.json").open("xb") as handle:
        handle.write(canonical_bytes(freeze))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--scan-overlap", action="store_true", help="write source-only similarity screen; no labels")
    parser.add_argument("--comparison-sp2020", type=Path)
    parser.add_argument("--comparison-reserved-illinois", type=Path)
    parser.add_argument("--reserved-pdf-dir", type=Path)
    parser.add_argument("--authored", type=Path)
    parser.add_argument("--review-a", type=Path)
    parser.add_argument("--review-b", type=Path)
    parser.add_argument("--adjudication", type=Path)
    parser.add_argument("--overlap-diagnostic", type=Path)
    parser.add_argument("--overlap-review", type=Path)
    args = parser.parse_args()
    if args.scan_overlap:
        if not all((args.comparison_sp2020, args.comparison_reserved_illinois, args.reserved_pdf_dir)):
            parser.error("overlap scan requires both comparison manifests and reserved PDF directory")
        output = scan_overlap_files(args.manifest, args.comparison_sp2020,
                                    args.comparison_reserved_illinois, args.reserved_pdf_dir)
        print(output)
        return
    if not all((args.authored, args.review_a, args.review_b, args.adjudication,
                args.overlap_diagnostic, args.overlap_review)):
        parser.error("freeze requires authored slate, two reviews, adjudication, overlap diagnostic and overlap review")
    output = freeze_files(args.manifest, args.authored, args.review_a, args.review_b,
                          args.adjudication, args.overlap_diagnostic, args.overlap_review)
    print(output)


if __name__ == "__main__":
    main()
