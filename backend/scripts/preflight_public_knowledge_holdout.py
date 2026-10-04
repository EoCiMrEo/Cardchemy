"""Provider-free preflight for two public-PDF Knowledge holdout sources.

The SHA-frozen manifest and PDFs must remain under the operator's OS Temp.
This command never opens an application database, reads root .env, or creates
an embedding client. Its output contains counts and admission bounds only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from math import ceil
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.chunking import estimate_tokens, prepare_document  # noqa: E402
from app.config import Settings  # noqa: E402
from app.services.knowledge_capture import validate_capture_bounds  # noqa: E402
from app.services.pdf_processor import PDFProcessor  # noqa: E402


SCHEMA = "cardchemy_public_knowledge_holdout_preflight_v1"
MAX_MANIFEST_BYTES = 16_384
MAX_HOLDOUT_BYTES = 96_000
MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PAGES = 100
MAX_EXTRACTED_CHARS = 500_000
EXTRACTION_TIMEOUT_SECONDS = 60
EXTRACTION_MEMORY_MB = 512
CHUNK_TOKENS = 1_200
CHUNK_OVERLAP = 120
BATCH_SIZE = 32
MAX_INPUT_TOKENS_PER_CHUNK = 2_048
MAX_DOCUMENT_TOKENS = 8_000
MAX_DOCUMENT_REQUESTS = 2
MAX_QUERY_CASES = 12
MAX_QUERY_TOKENS = 1_024
PRICE_GUARD_USD_PER_MILLION = 0.20
MAX_COST_USD = 0.002
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_BASENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.pdf\Z", re.IGNORECASE)


class Refusal(RuntimeError):
    """A fixed safe refusal code; do not print PDF/parser exception details."""


def _check_code_defaults() -> None:
    """Stop if the checked-out extraction/index profile changes under this audit."""
    expected = {
        "pdf_max_upload_bytes": MAX_PDF_BYTES,
        "pdf_max_pages": MAX_PAGES,
        "pdf_max_extracted_chars": MAX_EXTRACTED_CHARS,
        "pdf_extraction_timeout_seconds": EXTRACTION_TIMEOUT_SECONDS,
        "pdf_extraction_memory_limit_mb": EXTRACTION_MEMORY_MB,
        "flashcard_ai_chunk_input_tokens": CHUNK_TOKENS,
        "flashcard_ai_chunk_overlap_tokens": CHUNK_OVERLAP,
        "rag_embedding_batch_size": BATCH_SIZE,
        "rag_embedding_max_input_tokens": MAX_INPUT_TOKENS_PER_CHUNK,
    }
    if any(Settings.model_fields[key].default != value for key, value in expected.items()):
        raise Refusal("profile_default_changed")


def _within_temp(path: Path) -> Path:
    resolved = path.resolve()
    root = Path(tempfile.gettempdir()).resolve()
    if not resolved.is_relative_to(root) or resolved == root or path.is_symlink():
        raise Refusal("temp_path_required")
    return resolved


def _https_url(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 1_024:
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username


def load_manifest(path: Path, expected_sha256: str) -> tuple[Path, list[dict[str, str]], str]:
    if not _SHA.fullmatch(expected_sha256):
        raise Refusal("manifest_hash_invalid")
    path = _within_temp(path)
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_MANIFEST_BYTES:
        raise Refusal("manifest_invalid")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise Refusal("manifest_changed")
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or set(data) != {"schema", "sources"}:
            raise ValueError
        sources = data["sources"]
        if data["schema"] != SCHEMA or not isinstance(sources, list) or len(sources) != 2:
            raise ValueError
        names: set[str] = set()
        hashes: set[str] = set()
        for row in sources:
            if not isinstance(row, dict) or set(row) != {
                "file", "sha256", "source_url", "license_url", "attribution"
            }:
                raise ValueError
            name, digest_value = row["file"], row["sha256"]
            attribution = row["attribution"]
            if (
                not isinstance(name, str) or not _BASENAME.fullmatch(name)
                or name in names or not isinstance(digest_value, str)
                or not _SHA.fullmatch(digest_value) or digest_value in hashes
                or not _https_url(row["source_url"])
                or not _https_url(row["license_url"])
                or not isinstance(attribution, str)
                or not 1 <= len(attribution.strip()) <= 300
            ):
                raise ValueError
            names.add(name)
            hashes.add(digest_value)
    except (UnicodeDecodeError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise Refusal("manifest_invalid") from None
    return path.parent, sources, digest


def load_holdout(
    path: Path, expected_sha256: str, *, directory: Path,
    source_hashes: set[str],
) -> tuple[list[dict[str, object]], int, str]:
    """Bind current-question cost to the independently frozen source roster."""
    if not _SHA.fullmatch(expected_sha256):
        raise Refusal("holdout_hash_invalid")
    resolved = _within_temp(path)
    if (resolved.parent != directory or not resolved.is_file()
        or not 0 < resolved.stat().st_size <= MAX_HOLDOUT_BYTES):
        raise Refusal("holdout_invalid")
    raw = resolved.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise Refusal("holdout_changed")
    try:
        data = json.loads(raw)
        rows = data["cases"]
        # The original roster's proposed quote windows were visually correct,
        # but none was a literal slice of the runtime extractor's page text.
        # Refuse that retired schema before any paid or database step.
        if (data["schema"] != "cardchemy_public_original_pdf_holdout_v2"
            or not isinstance(rows, list) or len(rows) != MAX_QUERY_CASES):
            raise ValueError
        counts = {group: 0 for group in ("direct", "paraphrase", "follow_up")}
        ids: set[str] = set()
        tokens = 0
        for row in rows:
            question = row["question"]
            raw_prior = row["prior_question"]
            # The frozen source-label roster uses JSON null for standalone
            # questions; the Ask diagnostic later normalizes that to "".
            prior = "" if raw_prior is None else raw_prior
            group = row["group"]
            case_id = row["id"]
            page = row["gold_physical_page"]
            window = row["gold_window_exact_extracted_text"]
            if (
                not isinstance(case_id, str) or not case_id or case_id in ids
                or group not in counts
                or row["document_sha256"] not in source_hashes
                or not isinstance(question, str)
                or not 0 < len(question.strip()) <= 4_000 or "\x00" in question
                or not isinstance(prior, str) or len(prior) > 1_000
                or "\x00" in prior
                or (group == "follow_up") != bool(prior.strip())
                or type(page) is not int or not 1 <= page <= MAX_PAGES
                or not isinstance(window, str)
                or not 1 <= len(window) <= 480 or not window.strip()
            ):
                raise ValueError
            ids.add(case_id)
            counts[group] += 1
            tokens += estimate_tokens(question)
        if set(counts.values()) != {4} or tokens > MAX_QUERY_TOKENS:
            raise ValueError
    except (UnicodeDecodeError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise Refusal("holdout_invalid") from None
    return rows, tokens, digest


def inspect_sources(
    directory: Path, sources: list[dict[str, str]],
    holdout_rows: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    rows: list[dict[str, int]] = []
    total_tokens = 0
    total_requests = 0
    for source in sources:
        path = directory / source["file"]
        resolved = _within_temp(path)
        if resolved.parent != directory or not resolved.is_file():
            raise Refusal("pdf_path_invalid")
        if not 0 < resolved.stat().st_size <= MAX_PDF_BYTES:
            raise Refusal("pdf_size_invalid")
        raw = resolved.read_bytes()
        if hashlib.sha256(raw).hexdigest() != source["sha256"]:
            raise Refusal("pdf_changed")
        try:
            extracted = PDFProcessor.extract_text_in_subprocess(
                raw,
                max_pages=MAX_PAGES,
                max_extracted_chars=MAX_EXTRACTED_CHARS,
                timeout_seconds=EXTRACTION_TIMEOUT_SECONDS,
                memory_limit_mb=EXTRACTION_MEMORY_MB,
                ocr_enabled=False,
            )
            prepared = prepare_document(
                extracted, max_tokens=CHUNK_TOKENS, overlap_tokens=CHUNK_OVERLAP,
            )
            validate_capture_bounds(prepared)
            input_tokens = sum(estimate_tokens(chunk.text) for chunk in prepared.chunks)
        except Exception:
            raise Refusal("pdf_extraction_or_capture_invalid") from None
        if holdout_rows is not None:
            pages = {page.page_number: page.text for page in extracted.pages}
            for case in holdout_rows:
                if case["document_sha256"] == source["sha256"]:
                    page_text = pages.get(case["gold_physical_page"])
                    if (page_text is None
                        or case["gold_window_exact_extracted_text"] not in page_text):
                        raise Refusal("gold_window_invalid")
        if (
            not prepared.chunks
            or any(estimate_tokens(chunk.text) > MAX_INPUT_TOKENS_PER_CHUNK
                   for chunk in prepared.chunks)
        ):
            raise Refusal("embedding_input_invalid")
        requests = ceil(len(prepared.chunks) / BATCH_SIZE)
        rows.append({
            "pages": len(extracted.pages), "chunks": len(prepared.chunks),
            "estimated_input_tokens": input_tokens, "document_requests": requests,
        })
        total_tokens += input_tokens
        total_requests += requests
    if total_tokens > MAX_DOCUMENT_TOKENS or total_requests > MAX_DOCUMENT_REQUESTS:
        raise Refusal("paid_envelope_exceeded")
    estimated_ceiling = (
        (MAX_DOCUMENT_TOKENS + MAX_QUERY_TOKENS)
        * PRICE_GUARD_USD_PER_MILLION / 1_000_000
    )
    if estimated_ceiling > MAX_COST_USD:
        raise Refusal("cost_guard_invalid")
    return {
        "provider_requests": 0, "database_writes": 0,
        "sources": rows,
        "estimated_document_tokens": total_tokens,
        "estimated_document_requests": total_requests,
        "envelope": {
            "document_requests": MAX_DOCUMENT_REQUESTS,
            "query_requests": MAX_QUERY_CASES,
            "document_input_tokens": MAX_DOCUMENT_TOKENS,
            "query_input_tokens": MAX_QUERY_TOKENS,
            "input_cost_guard_usd_per_million": PRICE_GUARD_USD_PER_MILLION,
            "estimated_cost_ceiling_usd": estimated_ceiling,
            "maximum_cost_usd": MAX_COST_USD,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--holdout", type=Path, required=True)
    parser.add_argument("--holdout-sha256", required=True)
    args = parser.parse_args()
    try:
        _check_code_defaults()
        directory, sources, digest = load_manifest(args.manifest, args.manifest_sha256)
        holdout_rows, query_tokens, holdout_digest = load_holdout(
            args.holdout, args.holdout_sha256, directory=directory,
            source_hashes={source["sha256"] for source in sources},
        )
        report = inspect_sources(directory, sources, holdout_rows)
    except Refusal as exc:
        raise SystemExit(f"Public Knowledge holdout preflight refused: {exc}") from None
    report["manifest_sha256"] = digest
    report["holdout_sha256"] = holdout_digest
    report["query_case_count"] = len(holdout_rows)
    report["estimated_query_tokens"] = query_tokens
    report["estimated_total_tokens"] = report["estimated_document_tokens"] + query_tokens
    report["estimated_total_cost_usd"] = (
        report["estimated_total_tokens"] * PRICE_GUARD_USD_PER_MILLION / 1_000_000
    )
    print(json.dumps(report, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
