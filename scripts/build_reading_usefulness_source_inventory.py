"""Build an unlabeled, OS-Temp-only inventory of the pinned public PDF corpus.

This extracts exact page text and bounded authoring suggestions. It does not
create questions, labels, a reviewed fixture, or any model score. The output
contains copyrighted source text and must remain in OS Temp, outside Git.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import re
import sys
from tempfile import gettempdir

from pypdf import PdfReader

import acquire_reading_usefulness_corpus as corpus
import derive_reading_usefulness_corpus_v4 as derived
import validate_reading_usefulness_fixture as fixture_guard

logging.getLogger("pypdf").setLevel(logging.ERROR)


MAX_WINDOWS_PER_PAGE = 12
MAX_WINDOW_CHARS = 480
MIN_WINDOW_ALNUM = 40


def suggested_windows(page_text: str) -> tuple[list[dict[str, object]], int]:
    """Return exact, disjoint text spans; report omitted suggestions explicitly."""
    windows: list[dict[str, object]] = []
    omitted = 0
    cursor = 0
    while cursor < len(page_text):
        while cursor < len(page_text) and page_text[cursor].isspace():
            cursor += 1
        if cursor >= len(page_text):
            break
        limit = min(cursor + MAX_WINDOW_CHARS, len(page_text))
        end = limit
        if limit < len(page_text) and not page_text[limit].isspace():
            # Prefer a paragraph/line boundary, then a word boundary. A short
            # fragment is retained in the next exact span rather than dropped.
            newline = page_text.rfind("\n", cursor + 160, limit)
            space = page_text.rfind(" ", cursor + 160, limit)
            if newline > cursor:
                end = newline
            elif space > cursor:
                end = space
        while end > cursor and page_text[end - 1].isspace():
            end -= 1
        if end <= cursor:
            end = limit
        exact = page_text[cursor:end]
        if sum(ch.isalnum() for ch in exact) >= MIN_WINDOW_ALNUM:
            if len(windows) < MAX_WINDOWS_PER_PAGE:
                windows.append({"start": cursor, "end": end, "exact_text": exact})
            else:
                omitted += 1
        cursor = max(end, cursor + 1)
    return windows, omitted


def build(corpus_root: Path, output: Path) -> dict[str, object]:
    guard = fixture_guard
    guard.require(corpus_root.is_dir() and not corpus_root.is_symlink(), "corpus_root")
    guard.require(output.parent.resolve() == Path(gettempdir()).resolve(), "os_temp_output_required")
    guard.require(not output.exists() and not output.is_symlink(), "output_exists")
    prereg, prereg_raw = guard.read_json(corpus_root / "preregistration.json", 32_768)
    manifest, manifest_raw = guard.read_json(corpus_root / "manifest.json", 64_000)
    plan, _ = guard.read_json(corpus_root / "empty_fixture_plan.json", 32_768)
    guard.require(prereg == derived.preregistration_v4(corpus.preregistration()) and
                  guard.digest(prereg_raw) == guard.CORPUS_PREREGISTRATION_SHA256 and
                  guard.digest(manifest_raw) == guard.CORPUS_MANIFEST_SHA256 and
                  plan == derived.empty_fixture_plan_v4(
                      corpus.empty_fixture_plan(derived.V3_MANIFEST_SHA256),
                      guard.digest(manifest_raw)),
                  "corpus_and_plan_pin")
    guard.require(manifest.get("schema") == "cardchemy_public_reading_corpus_manifest_v1" and
                  manifest.get("corpus_id") == derived.V4_CORPUS_ID and
                  manifest.get("preregistration_sha256") == guard.digest(prereg_raw) and
                  manifest.get("all_pdf_first_pages_cc_by_4") is True and
                  manifest.get("labels_written") is False and
                  manifest.get("derived_from") == derived._parent_provenance() and
                  manifest.get("license_url") == corpus.LICENSE_URL,
                  "manifest_identity")
    docs = manifest.get("documents")
    guard.require(type(docs) is list and len(docs) == 14, "document_roster")
    expected = {url: split for split, urls in prereg["splits"].items() for url in urls}
    seen: set[str] = set()
    inventory_docs: list[dict[str, object]] = []
    page_count = 0
    window_count = 0
    omitted_count = 0
    for doc in docs:
        guard.require(type(doc) is dict, "document_entry")
        url, split, name = (doc.get(key) for key in ("url", "split", "path"))
        guard.require(type(url) is str and url in expected and url not in seen and
                      expected[url] == split and name == url.rsplit("/", 1)[-1] and
                      re.fullmatch(r"lec\d{2}[.]pdf", name) and
                      doc.get("license_url") == corpus.LICENSE_URL and
                      doc.get("first_page_license") == "CC BY 4.0",
                      "document_identity")
        seen.add(url)
        path = corpus_root / name
        raw = guard.file_bytes(path, corpus.MAX_PDF_BYTES)
        guard.require(type(doc.get("bytes")) is int and len(raw) == doc["bytes"] and
                      guard.digest(raw) == doc.get("sha256"), "document_hash")
        reader = PdfReader(path, strict=False)
        guard.require(not reader.is_encrypted and type(doc.get("pages")) is int and
                      len(reader.pages) == doc["pages"] and
                      1 <= len(reader.pages) <= corpus.MAX_PDF_PAGES, "document_pages")
        pages = []
        for index, pdf_page in enumerate(reader.pages, 1):
            page_text = pdf_page.extract_text() or ""
            if index == 1:
                guard.require(bool(corpus.LICENSE_RE.search(page_text)), "document_license_notice")
            suggestions, omitted = suggested_windows(page_text)
            pages.append({"page_number": index, "page_text_sha256": guard.digest(
                page_text.encode("utf-8")), "extracted_text": page_text,
                "candidate_windows": suggestions,
                "omitted_candidate_window_count": omitted})
            page_count += 1
            window_count += len(suggestions)
            omitted_count += omitted
        counts = [sum(ch.isalnum() for ch in page["extracted_text"]) for page in pages]
        guard.require(sum(counts) == doc.get("alphanumeric_text_chars") and
                      sum(count >= 40 for count in counts) == doc.get(
                          "pages_with_at_least_40_alphanumeric_chars") and
                      sum(counts) >= 1500, "document_text_quality")
        inventory_docs.append({"split": split, "url": url, "path": name,
                               "source_document_sha256": doc["sha256"],
                               "license_url": corpus.LICENSE_URL,
                               "first_page_license": "CC BY 4.0", "pages": pages})
    guard.require(seen == set(expected), "document_roster")
    body = corpus.canonical_bytes({
        "schema": "cardchemy_reading_usefulness_source_inventory_v1",
        "corpus_id": derived.V4_CORPUS_ID,
        "manifest_sha256": guard.digest(manifest_raw),
        "extractor": {"name": "pypdf", "version": fixture_guard.pypdf.__version__},
        "status": "unlabeled authoring aid; no model scoring",
        "license_review_warning": "CC BY 4.0 notice is verified on each first page; reviewers must exclude embedded third-party material before tracked reuse.",
        "documents": inventory_docs,
    })
    with output.open("xb") as stream:
        stream.write(body)
    return {"status": "unlabeled_inventory_created_no_scoring", "output": str(output),
            "inventory_sha256": guard.digest(body), "documents": len(inventory_docs),
            "pages": page_count, "suggested_windows": window_count,
            "omitted_suggestions": omitted_count}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = build(args.corpus, args.output)
    except (fixture_guard.FixtureError, OSError, ValueError) as exc:
        print(json.dumps({"status": "inventory_rejected_no_scoring",
                          "reason": str(exc) if isinstance(exc, fixture_guard.FixtureError)
                          else type(exc).__name__}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
