"""Acquire one unlabeled, source-disjoint ECE448 Spring 2022 public PDF corpus.

Default invocation is an offline preregistration print. Network mode requires a
    separate one-use operator approval artifact and two prior public-source
manifests. This module has no provider client and never reads Cardchemy data.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from tempfile import gettempdir
from urllib.parse import urljoin, urlsplit

import requests
from pypdf import PdfReader


HOST = "courses.grainger.illinois.edu"
SCHEDULE_URL = f"https://{HOST}/ece448/sp2022/lectures.html"
PDF_PREFIX = f"https://{HOST}/ece448/sp2022/slides/"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
CORPUS_ID = "illinois-ece448-sp2022-source-id-v2"
SCHEMA = "cardchemy_public_source_id_fresh_corpus_manifest_v2"
PREREG_SCHEMA = "cardchemy_public_source_id_fresh_corpus_prereg_v2"
DEFAULT_OUTPUT_NAME = "cardchemy-source-id-fresh-sp2022-v2"
SP2020_MANIFEST_SHA256 = "9978ad6fd2ca50f20d20ed8231e7434e2d8f91bbdc21b61e5e44ddcb76f0eae4"
ROSTER = (
    ("calibration", 4, 32), ("calibration", 5, 33),
    ("calibration", 6, 40), ("calibration", 7, 31),
    ("heldout", 8, 46), ("heldout", 9, 33),
    ("heldout", 11, 27), ("heldout", 13, 36),
)
RESERVED_HASHES = {
    f"https://{HOST}/ece448/sp2020/slides/lec17.pdf":
        "f8d3ef7b5284c827286183d9b14e00fef51acaf49742f2d9ee3b85631abf3e49",
    f"https://{HOST}/ece448/sp2020/slides/lec37.pdf":
        "5b8c326ccff98c51b114ae45acd95f985c75464858a2da68e3cd06b2c4e66fe6",
}
MAX_GETS = 13
MAX_REDIRECTS_PER_FETCH = 2
MAX_SCHEDULE_BYTES = 512 * 1024
MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_RECEIVED_BYTES = 84_410_368
MAX_PDF_PAGES = 60
MAX_ELAPSED_SECONDS = 30 * 60
CONNECT_TIMEOUT = 15
READ_TIMEOUT = 120
LICENSE_RE = re.compile(r"\bCC\s*-?\s*BY\s*-?\s*4[.]0\b", re.IGNORECASE)
SHA_RE = re.compile(r"[a-f0-9]{64}\Z")
NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,80}\Z")
APPROVAL_ID_RE = re.compile(r"[a-f0-9]{32}\Z")


class AcquisitionError(RuntimeError):
    """A content-free, operator-safe guard failure."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise AcquisitionError(code)


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("ascii")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pdf_url(number: int) -> str:
    return f"{PDF_PREFIX}lec{number:02d}.pdf"


def preregistration() -> dict[str, object]:
    require(len(ROSTER) == 8 and len({row[1] for row in ROSTER}) == 8 and
            [row[0] for row in ROSTER] == ["calibration"] * 4 + ["heldout"] * 4,
            "invalid_preregistered_split")
    return {
        "schema": PREREG_SCHEMA,
        "corpus_id": CORPUS_ID,
        "schedule_url": SCHEDULE_URL,
        "license_url": LICENSE_URL,
        "license_rule": "CC BY 4.0 on each PDF first page; third-party media separately attributed",
        "documents": [
            {"split": split, "url": pdf_url(number), "pages": pages}
            for split, number, pages in ROSTER
        ],
        "bounds": {
            "max_gets_including_redirects": MAX_GETS,
            "max_redirects_per_fetch": MAX_REDIRECTS_PER_FETCH,
            "max_schedule_bytes": MAX_SCHEDULE_BYTES,
            "max_pdf_bytes": MAX_PDF_BYTES,
            "max_received_bytes": MAX_RECEIVED_BYTES,
            "max_pdf_pages": MAX_PDF_PAGES,
            "connect_timeout_seconds": CONNECT_TIMEOUT,
            "read_timeout_seconds": READ_TIMEOUT,
            "max_elapsed_seconds": MAX_ELAPSED_SECONDS,
        },
    }


# Literal freeze; changing the preregistration requires a reviewed new version.
PREREGISTRATION_SHA256 = "4dd13466920e66086cba7c433d6631d1944a71e9205f597387d61b08ae181fdc"


def checked_preregistration() -> tuple[dict[str, object], bytes]:
    value = preregistration()
    raw = canonical_bytes(value)
    require(sha256(raw) == PREREGISTRATION_SHA256, "preregistration_changed")
    return value, raw


def write_new(path: Path, data: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(data)


def strict_json(raw: bytes) -> object:
    def no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            require(key not in result, "metadata_duplicate_key")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=no_duplicate_keys)
    except (ValueError, UnicodeError) as exc:
        raise AcquisitionError("metadata_invalid_json") from exc


def read_small_regular(path: Path, limit: int = 1_048_576) -> bytes:
    require(path.is_file() and not path.is_symlink(), "metadata_missing_or_symlink")
    require(path.stat().st_size <= limit, "metadata_byte_limit")
    raw = path.read_bytes()
    require(len(raw) <= limit, "metadata_byte_limit")
    return raw


def checked_url(url: str, allowed_paths: set[str]) -> None:
    try:
        parsed = urlsplit(url)
        valid = (parsed.scheme == "https" and parsed.netloc == HOST and
                 parsed.hostname == HOST and parsed.username is None and
                 parsed.password is None and parsed.port is None and
                 not parsed.query and not parsed.fragment and
                 parsed.path in allowed_paths)
    except ValueError:
        valid = False
    require(valid, "source_url_rejected")


class ScheduleLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.urls.add(urljoin(SCHEDULE_URL, value))


def require_schedule_links(data: bytes) -> None:
    parser = ScheduleLinks()
    parser.feed(data.decode("utf-8", errors="replace"))
    require({pdf_url(number) for _, number, _ in ROSTER}.issubset(parser.urls),
            "preregistered_pdf_not_linked_from_schedule")


def pdf_metrics(data: bytes, expected_pages: int) -> dict[str, object]:
    require(data.startswith(b"%PDF-"), "not_pdf")
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        require(not reader.is_encrypted, "pdf_encrypted")
        pages = len(reader.pages)
        require(pages == expected_pages and 1 <= pages <= MAX_PDF_PAGES,
                "pdf_page_count")
        first = reader.pages[0].extract_text() or ""
        require(bool(LICENSE_RE.search(first)), "pdf_missing_first_page_cc_by_4")
        chars = [sum(character.isalnum() for character in (page.extract_text() or ""))
                 for page in reader.pages]
    except AcquisitionError:
        raise
    except Exception as exc:
        raise AcquisitionError("pdf_parse_failed") from exc
    total = sum(chars)
    usable = sum(count >= 40 for count in chars)
    require(total >= 1500 and usable >= max(3, pages // 3), "pdf_text_quality")
    return {
        "pages": pages,
        "alphanumeric_text_chars": total,
        "pages_with_at_least_40_alphanumeric_chars": usable,
        "first_page_license": "CC BY 4.0",
    }


def comparison_metadata(paths: dict[str, Path]) -> tuple[list[dict[str, object]], set[str]]:
    """Read only public source metadata; never inspect old question labels."""
    require(set(paths) == {"ece448_sp2020", "reserved_illinois"},
            "comparison_manifest_set_incomplete")
    records: list[dict[str, object]] = []
    hashes: set[str] = set()
    for role, expected_count in (("ece448_sp2020", 14),
                                 ("reserved_illinois", 2)):
        raw = read_small_regular(paths[role])
        if role == "ece448_sp2020":
            require(sha256(raw) == SP2020_MANIFEST_SHA256,
                    "sp2020_manifest_hash_mismatch")
        value = strict_json(raw)
        require(type(value) is dict and type(value.get("documents")) is list and
                len(value["documents"]) == expected_count,
                "comparison_manifest_invalid")
        corpus_id = value.get("corpus_id")
        require(type(corpus_id) is str, "comparison_manifest_invalid")
        if role == "ece448_sp2020":
            require(corpus_id == "illinois-ece448-sp2020-reading-usefulness-v4",
                    "comparison_identity_mismatch")
        else:
            require("ece448" in corpus_id.lower() and "sp2020" in corpus_id.lower() and
                    "reserved" in corpus_id.lower(), "comparison_identity_mismatch")
        rows = value["documents"]
        role_hashes: set[str] = set()
        role_urls: set[str] = set()
        for row in rows:
            require(type(row) is dict and type(row.get("sha256")) is str and
                    bool(SHA_RE.fullmatch(row["sha256"])) and
                    type(row.get("url")) is str,
                    "comparison_manifest_invalid")
            digest = row["sha256"]
            url = row["url"]
            require(digest not in role_hashes and url not in role_urls,
                    "comparison_manifest_duplicate")
            if role == "ece448_sp2020":
                require(url.startswith(f"https://{HOST}/ece448/sp2020/slides/") and
                        url.endswith(".pdf"), "comparison_identity_mismatch")
            else:
                require(RESERVED_HASHES.get(url) == digest,
                        "comparison_identity_mismatch")
            role_hashes.add(digest)
            role_urls.add(url)
        if role == "reserved_illinois":
            require(role_urls == set(RESERVED_HASHES), "comparison_identity_mismatch")
        hashes.update(role_hashes)
        records.append({"role": role, "manifest_sha256": sha256(raw),
                        "document_count": expected_count})
    return records, hashes


class BoundedFetcher:
    def __init__(self, session: object, clock=time.monotonic) -> None:
        self.session = session
        self.clock = clock
        self.started = clock()
        self.gets = 0
        self.received_bytes = 0
        self.allowed_paths = {urlsplit(SCHEDULE_URL).path} | {
            urlsplit(pdf_url(number)).path for _, number, _ in ROSTER
        }

    def elapsed(self) -> float:
        return self.clock() - self.started

    def check_time(self) -> None:
        require(self.elapsed() < MAX_ELAPSED_SECONDS, "whole_run_time_limit")

    def fetch(self, url: str, byte_limit: int) -> bytes:
        current = url
        redirects = 0
        while True:
            checked_url(current, self.allowed_paths)
            self.check_time()
            require(self.gets < MAX_GETS, "physical_get_limit")
            remaining = MAX_ELAPSED_SECONDS - self.elapsed()
            timeout = (min(CONNECT_TIMEOUT, remaining), min(READ_TIMEOUT, remaining))
            self.gets += 1  # An uncertain transport call consumes its GET.
            try:
                response = self.session.get(current, timeout=timeout, stream=True,
                                            allow_redirects=False,
                                            headers={"Accept-Encoding": "identity"})
                with response:
                    self.check_time()
                    if response.status_code in (301, 302, 303, 307, 308):
                        require(redirects < MAX_REDIRECTS_PER_FETCH,
                                "per_fetch_redirect_limit")
                        location = response.headers.get("Location")
                        require(bool(location), "redirect_without_location")
                        target = urljoin(current, location)
                        checked_url(target, self.allowed_paths)
                        require(target == url, "redirect_file_substitution_rejected")
                        redirects += 1
                        current = target
                        continue  # Never stream a redirect body.
                    require(response.status_code == 200, "http_non_200")
                    require(response.headers.get("Content-Encoding", "identity").lower()
                            == "identity", "content_encoding_rejected")
                    content_length = response.headers.get("Content-Length")
                    if content_length is not None:
                        require(content_length.isdecimal() and
                                int(content_length) <= byte_limit and
                                int(content_length) + self.received_bytes <= MAX_RECEIVED_BYTES,
                                "declared_byte_limit")
                    data = bytearray()
                    for block in response.iter_content(64 * 1024):
                        self.check_time()
                        if not block:
                            continue
                        self.received_bytes += len(block)
                        require(self.received_bytes <= MAX_RECEIVED_BYTES and
                                len(data) + len(block) <= byte_limit,
                                "streamed_byte_limit")
                        data.extend(block)
                    self.check_time()
                    return bytes(data)
            except AcquisitionError:
                raise
            except requests.RequestException as exc:
                raise AcquisitionError("transport_failed_no_retry") from exc


def validate_material(root: Path, manifest: dict[str, object],
                      old_hashes: set[str]) -> None:
    """Rehash and reparse local bytes independently of download-time checks."""
    require(manifest.get("schema") == SCHEMA and manifest.get("corpus_id") == CORPUS_ID and
            manifest.get("preregistration_sha256") == PREREGISTRATION_SHA256,
            "manifest_identity_invalid")
    schedule = manifest.get("schedule")
    require(type(schedule) is dict and schedule.get("url") == SCHEDULE_URL and
            schedule.get("path") == "lectures.html", "manifest_schedule_invalid")
    schedule_raw = read_small_regular(root / "lectures.html", MAX_SCHEDULE_BYTES)
    require(schedule.get("bytes") == len(schedule_raw) and
            schedule.get("sha256") == sha256(schedule_raw), "schedule_hash_mismatch")
    require_schedule_links(schedule_raw)
    docs = manifest.get("documents")
    require(type(docs) is list and len(docs) == len(ROSTER), "manifest_roster_invalid")
    current_hashes: set[str] = set()
    for row, (split, number, pages) in zip(docs, ROSTER, strict=True):
        name = f"lec{number:02d}.pdf"
        require(type(row) is dict and row.get("split") == split and
                row.get("url") == pdf_url(number) and row.get("path") == name and
                row.get("license_url") == LICENSE_URL,
                "manifest_roster_invalid")
        raw = read_small_regular(root / name, MAX_PDF_BYTES)
        digest = sha256(raw)
        require(row.get("bytes") == len(raw) and row.get("sha256") == digest,
                "pdf_hash_mismatch")
        require(digest not in current_hashes and digest not in old_hashes,
                "source_duplicate_hash")
        current_hashes.add(digest)
        metrics = pdf_metrics(raw, pages)
        require(all(row.get(key) == value for key, value in metrics.items()),
                "manifest_pdf_metrics_mismatch")
    require(manifest.get("all_pdf_first_pages_cc_by_4") is True and
            manifest.get("labels_written") is False and
            manifest.get("content_overlap_review") == "required_before_question_authoring",
            "manifest_unlabeled_license_invalid")


def verify_manifest(root: Path, comparison_paths: dict[str, Path]) -> dict[str, object]:
    """Independent offline admission before any question/review packet."""
    records, old_hashes = comparison_metadata(comparison_paths)
    raw = read_small_regular(root / "manifest.json", 64_000)
    value = strict_json(raw)
    require(type(value) is dict and value.get("comparison_manifests") == records,
            "comparison_manifest_changed")
    validate_material(root, value, old_hashes)
    return {"status": "verified_unlabeled", "manifest_sha256": sha256(raw),
            "document_count": len(ROSTER)}


def acquire(root: Path, session: object,
            comparison_paths: dict[str, Path], clock=time.monotonic) -> dict[str, object]:
    """Run once using a caller-supplied transport; production CLI owns approval."""
    _, prereg_raw = checked_preregistration()
    comparisons, old_hashes = comparison_metadata(comparison_paths)
    require(not root.exists(), "output_path_already_exists")
    root.mkdir(parents=False, exist_ok=False)
    fetcher = BoundedFetcher(session, clock)
    try:
        write_new(root / "preregistration.json", prereg_raw)
        schedule_raw = fetcher.fetch(SCHEDULE_URL, MAX_SCHEDULE_BYTES)
        require_schedule_links(schedule_raw)
        write_new(root / "lectures.html", schedule_raw)
        docs: list[dict[str, object]] = []
        for split, number, expected_pages in ROSTER:
            url = pdf_url(number)
            raw = fetcher.fetch(url, MAX_PDF_BYTES)
            metrics = pdf_metrics(raw, expected_pages)
            digest = sha256(raw)
            require(digest not in old_hashes and
                    digest not in {row["sha256"] for row in docs},
                    "source_duplicate_hash")
            name = f"lec{number:02d}.pdf"
            write_new(root / name, raw)
            docs.append({"split": split, "url": url, "path": name,
                         "bytes": len(raw), "sha256": digest,
                         "license_url": LICENSE_URL, **metrics})
        fetcher.check_time()
        manifest = {
            "schema": SCHEMA,
            "corpus_id": CORPUS_ID,
            "preregistration_sha256": PREREGISTRATION_SHA256,
            "schedule": {"url": SCHEDULE_URL, "path": "lectures.html",
                         "bytes": len(schedule_raw), "sha256": sha256(schedule_raw)},
            "license_url": LICENSE_URL,
            "documents": docs,
            "requests_including_redirects": fetcher.gets,
            "received_bytes": fetcher.received_bytes,
            "elapsed_seconds": round(fetcher.elapsed(), 3),
            "comparison_manifests": comparisons,
            "all_pdf_first_pages_cc_by_4": True,
            "labels_written": False,
            "content_overlap_review": "required_before_question_authoring",
        }
        validate_material(root, manifest, old_hashes)
        manifest_raw = canonical_bytes(manifest)
        write_new(root / "manifest.json", manifest_raw)
        return {"status": "acquired_unlabeled", "root": str(root),
                "document_count": len(docs), "requests": fetcher.gets,
                "received_bytes": fetcher.received_bytes,
                "manifest_sha256": sha256(manifest_raw)}
    except Exception as exc:
        # No success manifest survives a failed acquisition. Keep partial bytes
        # and a content-free receipt so the attempted run remains auditable.
        (root / "manifest.json").unlink(missing_ok=True)
        reason = str(exc) if isinstance(exc, AcquisitionError) else "unexpected_failure"
        receipt = {"status": "failed_before_review", "reason": reason,
                   "requests": fetcher.gets, "received_bytes": fetcher.received_bytes,
                   "preregistration_sha256": PREREGISTRATION_SHA256}
        write_new(root / "failure.json", canonical_bytes(receipt))
        raise AcquisitionError(reason) from None


def provider_credentials_present(environ: dict[str, str]) -> bool:
    names = ("GOOGLE_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY",
             "ANTHROPIC_API_KEY", "AZURE_OPENAI_API_KEY",
             "RAG_EMBEDDING_API_KEY", "RAG_SOURCE_JUDGE_API_KEY",
             "RAG_AI_API_KEY", "FLASHCARD_AI_API_KEY", "AI_API_KEY",
             "GOOGLE_APPLICATION_CREDENTIALS")
    return any(environ.get(name, "").strip() for name in names)


def approved_once(path: Path) -> None:
    temp = Path(gettempdir()).resolve()
    require(path.resolve().parent == temp and not path.is_symlink(),
            "approval_must_be_os_temp_file")
    value = strict_json(read_small_regular(path, 4_096))
    require(type(value) is dict and value.get("schema") ==
            "cardchemy_public_source_id_fresh_acquisition_approval_v1" and
            value.get("corpus_id") == CORPUS_ID and
            value.get("preregistration_sha256") == PREREGISTRATION_SHA256 and
            value.get("authorization") == "I_APPROVE_ONE_PUBLIC_PDF_ACQUISITION" and
            value.get("max_gets_including_redirects") == MAX_GETS and
            type(value.get("approval_id")) is str and
            bool(APPROVAL_ID_RE.fullmatch(value["approval_id"])),
            "approval_artifact_invalid")
    marker = temp / f"cardchemy-source-id-fresh-v2-{value['approval_id']}.used"
    try:
        with marker.open("xb") as handle:
            handle.write(canonical_bytes({"approval_id": value["approval_id"],
                                          "preregistration_sha256": PREREGISTRATION_SHA256}))
    except FileExistsError as exc:
        raise AcquisitionError("approval_already_used") from exc


def output_root(name: str) -> Path:
    require(bool(NAME_RE.fullmatch(name)), "output_name_invalid")
    return Path(gettempdir()).resolve() / name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    parser.add_argument("--approval-file", type=Path)
    parser.add_argument("--comparison-sp2020", type=Path)
    parser.add_argument("--comparison-reserved-illinois", type=Path)
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME)
    args = parser.parse_args(argv)
    try:
        prereg, _ = checked_preregistration()
        if not args.execute and not args.preflight:
            print(json.dumps({"status": "offline_preregistration_only",
                              "network_requests": 0,
                              "preregistration_sha256": PREREGISTRATION_SHA256,
                              "default_os_temp_output": str(output_root(args.output_name)),
                              "preregistration": prereg}, sort_keys=True, indent=2))
            return 0
        require(args.comparison_sp2020 is not None and
                args.comparison_reserved_illinois is not None,
                "comparison_manifests_required")
        root = output_root(args.output_name)
        require(not root.exists(), "output_path_already_exists")
        comparisons = {
            "ece448_sp2020": args.comparison_sp2020,
            "reserved_illinois": args.comparison_reserved_illinois,
        }
        records, _ = comparison_metadata(comparisons)  # No old labels or PDF bytes.
        if args.preflight:
            print(json.dumps({"status": "offline_preflight_ready",
                              "network_requests": 0,
                              "preregistration_sha256": PREREGISTRATION_SHA256,
                              "output": str(root), "output_available": True,
                              "comparison_manifests": records}, sort_keys=True))
            return 0
        require(args.approval_file is not None, "approval_artifact_required")
        require(not provider_credentials_present(dict(os.environ)),
                "provider_credentials_present")
        approved_once(args.approval_file)
        session = requests.Session()
        session.trust_env = False
        session.verify = True
        session.mount("https://", requests.adapters.HTTPAdapter(max_retries=0))
        result = acquire(root, session, comparisons)
        print(json.dumps(result, sort_keys=True))
        return 0
    except AcquisitionError as exc:
        print(json.dumps({"status": "acquisition_rejected_or_failed",
                          "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
