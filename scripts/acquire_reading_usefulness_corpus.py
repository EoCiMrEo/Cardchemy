"""Acquire the preregistered public lecture PDFs for one offline audit.

This script never reads Cardchemy Knowledge or calls an AI provider. Its output
is an OS-Temp-only, source-disjoint, unlabeled corpus and provenance manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from tempfile import gettempdir
from urllib.parse import urljoin, urlparse

import requests
from pypdf import PdfReader


INDEX_URL = "https://courses.grainger.illinois.edu/ece448/sp2020/lectures.html"
PDF_PREFIX = "https://courses.grainger.illinois.edu/ece448/sp2020/slides/"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
CORPUS_ID = "illinois-ece448-sp2020-reading-usefulness-v3"
SPLITS = {
    "train": (10, 11, 14, 15, 16, 28),
    "calibration": (22, 27, 31, 32),
    "heldout": (25, 26, 33, 38),
}
RESERVED_RELEASE_HOLDOUT = frozenset({17, 37})
MAX_DOCUMENT_URLS = 18
MAX_GETS = 24
MAX_BYTES = 120 * 1024 * 1024
MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 100
MAX_ELAPSED_SECONDS = 30 * 60
MAX_INDEX_BYTES = 512 * 1024
LICENSE_RE = re.compile(r"\bCC\s*-?\s*BY\s*-?\s*4[.]0\b", re.IGNORECASE)


class AcquisitionError(RuntimeError):
    pass


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.hrefs.add(urljoin(INDEX_URL, value))


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n").encode()


def write_new(path: Path, content: bytes) -> None:
    with path.open("xb") as target:
        target.write(content)


def pdf_url(number: int) -> str:
    return f"{PDF_PREFIX}lec{number:02d}.pdf"


def preregistration() -> dict[str, object]:
    numbers = [number for docs in SPLITS.values() for number in docs]
    if len(numbers) != 14 or len(set(numbers)) != 14 or set(numbers) & RESERVED_RELEASE_HOLDOUT:
        raise AcquisitionError("invalid_preregistered_split")
    if len(numbers) > MAX_DOCUMENT_URLS:
        raise AcquisitionError("document_url_limit")
    return {
        "schema": "cardchemy_public_reading_corpus_prereg_v1",
        "corpus_id": CORPUS_ID,
        "index_url": INDEX_URL,
        "license_notice": "Each PDF must itself state CC BY 4.0 on its first page; embedded third-party media has separate attribution.",
        "license_url": LICENSE_URL,
        "reserved_release_holdout": [pdf_url(n) for n in sorted(RESERVED_RELEASE_HOLDOUT)],
        "splits": {name: [pdf_url(n) for n in docs] for name, docs in SPLITS.items()},
        "bounds": {
            "document_urls": MAX_DOCUMENT_URLS,
            "get_including_redirects": MAX_GETS,
            "received_bytes": MAX_BYTES,
            "bytes_per_pdf": MAX_PDF_BYTES,
            "pages_per_pdf": MAX_PDF_PAGES,
            "seconds_total": MAX_ELAPSED_SECONDS,
        },
    }


class BoundedFetcher:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.gets = 0
        self.bytes_received = 0
        self.started = time.monotonic()

    def fetch(self, url: str, byte_cap: int) -> bytes:
        current = url
        for _ in range(5):
            if self.gets >= MAX_GETS or time.monotonic() - self.started >= MAX_ELAPSED_SECONDS:
                raise AcquisitionError("request_or_time_limit")
            parsed = urlparse(current)
            if parsed.scheme != "https" or parsed.netloc != "courses.grainger.illinois.edu":
                raise AcquisitionError("source_host_mismatch")
            self.gets += 1
            with self.session.get(current, timeout=(15, 120), stream=True, allow_redirects=False) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    target = response.headers.get("Location")
                    if not target:
                        raise AcquisitionError("redirect_without_location")
                    current = urljoin(current, target)
                    continue
                if response.status_code != 200:
                    raise AcquisitionError(f"http_{response.status_code}")
                data = bytearray()
                for block in response.iter_content(64 * 1024):
                    if not block:
                        continue
                    self.bytes_received += len(block)
                    if self.bytes_received > MAX_BYTES or len(data) + len(block) > byte_cap:
                        raise AcquisitionError("byte_limit")
                    if time.monotonic() - self.started >= MAX_ELAPSED_SECONDS:
                        raise AcquisitionError("time_limit")
                    data.extend(block)
                return bytes(data)
        raise AcquisitionError("redirect_limit")


def pdf_metrics(data: bytes) -> dict[str, object]:
    if not data.startswith(b"%PDF-"):
        raise AcquisitionError("not_pdf")
    reader = PdfReader(io.BytesIO(data), strict=False)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PDF_PAGES:
        raise AcquisitionError("pdf_pages_or_encryption")
    first = reader.pages[0].extract_text() or ""
    if not LICENSE_RE.search(first):
        raise AcquisitionError("pdf_missing_first_page_cc_by_4_license")
    alnum_chars = 0
    usable_pages = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        chars = sum(ch.isalnum() for ch in text)
        alnum_chars += chars
        usable_pages += chars >= 40
    if alnum_chars < 1500 or usable_pages < max(3, len(reader.pages) // 3):
        raise AcquisitionError("pdf_text_quality")
    return {
        "pages": len(reader.pages),
        "alphanumeric_text_chars": alnum_chars,
        "pages_with_at_least_40_alphanumeric_chars": usable_pages,
        "first_page_license": "CC BY 4.0",
    }


def empty_fixture_plan(manifest_sha: str) -> dict[str, object]:
    return {
        "schema": "cardchemy_reading_usefulness_fixture_plan_v1",
        "corpus_id": CORPUS_ID,
        "manifest_sha256": manifest_sha,
        "status": "unlabeled; no model scoring authorized by this file",
        "groups": [],
        "targets": {
            "groups_by_split": {"train": 96, "calibration": 48, "heldout": 48},
            "candidates_per_group": 4,
            "true_useful_count_groups_by_split": {
                "train": {str(i): 24 for i in range(4)},
                "calibration": {str(i): 12 for i in range(4)},
                "heldout": {str(i): 12 for i in range(4)},
            },
            "relation_families": 8,
            "question_forms": ["direct", "paraphrase", "follow-up"],
        },
        "required_fields_per_group": [
            "id", "split", "source_document_sha256", "question_form", "relation_family",
            "question", "prior_question_context_if_followup", "four_exact_candidate_windows",
            "page_number_and_text_offsets_for_each_window", "original_page_usefulness_per_window",
            "exact_cue_usefulness_per_window", "independent_reviewer_ids_and_adjudication",
        ],
        "review_rule": "Independent authors and blinded reviewers adjudicate each exact cue and original page before first model score; no label is inferred from this plan.",
        "leakage_rule": "Disjoint documents and question templates across splits; no GTE packet, private lecture, or reserved release holdout.",
    }


def acquire(root: Path) -> None:
    if root.exists():
        raise AcquisitionError("output_path_already_exists")
    root.mkdir(parents=True)
    prereg = preregistration()
    prereg_bytes = canonical_bytes(prereg)
    write_new(root / "preregistration.json", prereg_bytes)
    fetcher = BoundedFetcher()
    try:
        page = fetcher.fetch(INDEX_URL, MAX_INDEX_BYTES)
        parser = LinkParser()
        parser.feed(page.decode("utf-8", errors="replace"))
        requested = set(url for urls in prereg["splits"].values() for url in urls)
        if not requested.issubset(parser.hrefs):
            raise AcquisitionError("preregistered_pdf_not_linked_from_index")
        docs: list[dict[str, object]] = []
        for split, numbers in SPLITS.items():
            for number in numbers:
                url = pdf_url(number)
                data = fetcher.fetch(url, MAX_PDF_BYTES)
                metrics = pdf_metrics(data)
                name = f"lec{number:02d}.pdf"
                write_new(root / name, data)
                docs.append({
                    "split": split,
                    "url": url,
                    "path": name,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "license_url": LICENSE_URL,
                    **metrics,
                })
        manifest = {
            "schema": "cardchemy_public_reading_corpus_manifest_v1",
            "corpus_id": CORPUS_ID,
            "preregistration_sha256": hashlib.sha256(prereg_bytes).hexdigest(),
            "index_url": INDEX_URL,
            "license_url": LICENSE_URL,
            "documents": docs,
            "requests_including_redirects": fetcher.gets,
            "received_bytes": fetcher.bytes_received,
            "elapsed_seconds": round(time.monotonic() - fetcher.started, 3),
            "all_pdf_first_pages_cc_by_4": True,
            "labels_written": False,
        }
        manifest_bytes = canonical_bytes(manifest)
        write_new(root / "manifest.json", manifest_bytes)
        manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
        write_new(root / "empty_fixture_plan.json", canonical_bytes(empty_fixture_plan(manifest_sha)))
        print(json.dumps({
            "status": "acquired_unlabeled",
            "root": str(root),
            "document_count": len(docs),
            "requests": fetcher.gets,
            "received_bytes": fetcher.bytes_received,
            "manifest_sha256": manifest_sha,
        }, sort_keys=True))
    except Exception as exc:
        failure = {
            "status": "failed_before_fixture_freeze",
            "reason": str(exc) if isinstance(exc, AcquisitionError) else type(exc).__name__,
            "requests": fetcher.gets,
            "received_bytes": fetcher.bytes_received,
        }
        write_new(root / "failure.json", canonical_bytes(failure))
        print(json.dumps(failure, sort_keys=True), file=sys.stderr)
        raise SystemExit(1) from None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(gettempdir()) / "cardchemy-reading-usefulness-public-20260928")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.execute:
        acquire(args.output)
    else:
        print(json.dumps(preregistration(), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
