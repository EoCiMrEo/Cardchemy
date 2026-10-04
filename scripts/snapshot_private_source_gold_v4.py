"""Read current authorized pages for the frozen private v4 gold-to-slate bridge.

Default invocation is a zero-read preflight. ``--execute`` reads the exact
stage-1 packet and optional byte-frozen slate pointers from owner-private Temp,
then obtains canonical pages and original-PDF manifests in one PostgreSQL
REPEATABLE READ READ ONLY transaction. It makes no Ask job or provider request.
The resulting private Temp JSON supplies ``authorized_pages`` to
``bridge_private_source_gold_v4.validate_bridge``; it is not a display score.

The optional slate input is a JSON list in the bridge's ``slates`` shape. It
must be captured before source-ID judgment and supplied with its exact SHA.
Without it, the output contains the twelve gold pages only.
"""

from __future__ import annotations

import argparse
import asyncio
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any
from uuid import UUID


SCHEMA = "private_source_gold_v4_authorized_pages_v1"
FROZEN_STAGE1_SHA256 = "53f0947bc3f01c488e28edb3f941bf13e51f8c85fdf7d3e8c8788ca976ab2477"
MAX_STAGE1_BYTES = 512 * 1024
MAX_SLATES_BYTES = 128 * 1024
MAX_PAGES = 60
MAX_OUTPUT_BYTES = 8 * 1024 * 1024
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_AI_CREDENTIAL_NAMES = frozenset({
    "FLASHCARD_AI_API_KEY", "RAG_AI_API_KEY", "RAG_EMBEDDING_API_KEY",
    "RAG_SOURCE_JUDGE_API_KEY", "AI_API_KEY", "GEMINI_API_KEY",
    "GOOGLE_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS",
})


class Refusal(ValueError):
    """A fixed failure code; never carry private text or database exceptions."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Refusal(code)


def _canonical_uuid(value: Any) -> bool:
    if type(value) is not str:
        return False
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def _temp_root() -> Path:
    return Path(tempfile.gettempdir()).resolve(strict=True)


def _temp_path(path: Path, *, existing: bool, root: Path | None = None) -> Path:
    root = root or _temp_root()
    _require(root.is_dir(), "private_temp_required")
    try:
        resolved = path.resolve(strict=existing)
        parent = path.parent.resolve(strict=True)
    except (OSError, RuntimeError):
        raise Refusal("private_temp_required") from None
    _require(resolved != root and resolved.is_relative_to(root)
             and parent.is_relative_to(root), "private_temp_required")
    # Symlinked private inputs or output parents can redirect content outside
    # the checked location between the path check and the later file operation.
    cursor = path if existing else path.parent
    while cursor != root and cursor.is_relative_to(root):
        _require(not cursor.is_symlink(), "private_temp_required")
        cursor = cursor.parent
    if existing:
        _require(resolved.is_file(), "private_temp_required")
    else:
        _require(not path.exists() and not path.is_symlink(), "output_exists")
    if os.name != "nt":
        _require(stat.S_IMODE(parent.stat().st_mode) & 0o077 == 0,
                 "private_temp_required")
    return resolved


def _read_hashed(path: Path, expected_sha: str, *, maximum: int, code: str,
                 root: Path | None = None) -> bytes:
    _require(type(expected_sha) is str and _SHA.fullmatch(expected_sha) is not None,
             code)
    resolved = _temp_path(path, existing=True, root=root)
    _require(0 < resolved.stat().st_size <= maximum, code)
    try:
        descriptor = os.open(resolved, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            details = os.fstat(stream.fileno())
            _require(stat.S_ISREG(details.st_mode)
                     and 0 < details.st_size <= maximum, code)
            raw = stream.read(maximum + 1)
    except OSError:
        raise Refusal(code) from None
    _require(0 < len(raw) <= maximum and sha256(raw).hexdigest() == expected_sha, code)
    return raw


def _stage1(raw: bytes, expected_sha: str) -> tuple[dict, dict[str, dict], dict[str, dict]]:
    # The pure bridge owns the byte/schema contract; no backend settings or
    # database module is imported when validating a private packet.
    import bridge_private_source_gold_v4 as bridge

    try:
        packet = bridge._json_exact(raw, expected_sha, "stage1_changed")
        cases, documents = bridge._stage1(packet, expected_sha)
    except (bridge.InvalidBridge, KeyError, TypeError, ValueError):
        raise Refusal("stage1_invalid") from None
    return packet, cases, documents


def _slate_pointers(raw: bytes, cases: dict[str, dict],
                    documents: dict[str, dict]) -> tuple[list[dict], set[tuple[str, int]]]:
    try:
        slates = json.loads(raw, object_pairs_hook=_unique_object)
    except (UnicodeError, ValueError):
        raise Refusal("slates_invalid") from None
    _require(type(slates) is list and len(slates) == 12, "slates_invalid")
    by_case: dict[str, list[dict]] = {}
    pointers: set[tuple[str, int]] = set()
    for row in slates:
        _require(type(row) is dict and set(row) == {"case_id", "candidates"}
                 and row["case_id"] in cases and row["case_id"] not in by_case
                 and type(row["candidates"]) is list
                 and len(row["candidates"]) <= 4, "slates_invalid")
        by_case[row["case_id"]] = row["candidates"]
        seen: set[tuple[str, int]] = set()
        for ordinal, candidate in enumerate(row["candidates"], 1):
            _require(type(candidate) is dict and set(candidate) == {
                "runtime_id", "document_id", "page_number", "start_offset", "end_offset"
            } and candidate["runtime_id"] == f"S{ordinal:02}"
                and _canonical_uuid(candidate["document_id"])
                and candidate["document_id"] in documents
                and type(candidate["page_number"]) is int
                and 1 <= candidate["page_number"] <= 100
                and type(candidate["start_offset"]) is int
                and type(candidate["end_offset"]) is int
                and 0 <= candidate["start_offset"] < candidate["end_offset"]
                and candidate["end_offset"] - candidate["start_offset"] <= 480,
                "slates_invalid")
            pointer = (candidate["document_id"], candidate["page_number"])
            _require(pointer not in seen, "slates_invalid")
            seen.add(pointer)
            pointers.add(pointer)
    _require(set(by_case) == set(cases), "slates_invalid")
    return slates, pointers


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate_json_key")
        value[key] = item
    return value


def _guard_runtime(environment: dict[str, str], expected_database: str) -> str:
    # Explicit process values only: Settings() would read the operator's root
    # .env and import app.database before this guard could refuse execution.
    _require(environment.get("ENVIRONMENT") == "development"
             and environment.get("RAG_ASK_ENABLED", "").lower() == "false",
             "development_ask_off_required")
    _require(not any(environment.get(name, "").strip() for name in _AI_CREDENTIAL_NAMES),
             "ai_credentials_present")
    _require(type(expected_database) is str
             and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", expected_database) is not None,
             "database_target_invalid")
    from sqlalchemy.engine import make_url

    url = environment.get("DATABASE_URL", "")
    try:
        target = make_url(url)
    except Exception:
        raise Refusal("database_target_invalid") from None
    _require(target.drivername == "postgresql+asyncpg" and target.host == "db"
             and target.port == 5432 and target.database == expected_database
             and bool(target.username) and bool(target.password) and not target.query,
             "database_target_invalid")
    return url


_PAGE_SQL = """
WITH authorized_subject AS (
    SELECT subject.id, subject.instructor_id, subject.corpus_revision,
           subject.active_embedding_space_hash
    FROM subjects AS subject
    JOIN users AS principal ON principal.id = CAST(:principal_id AS uuid)
    WHERE subject.id = CAST(:subject_id AS uuid)
      AND subject.corpus_revision = :corpus_revision
      AND subject.active_embedding_space_hash = :embedding_space_hash
      AND ((principal.role = 'INSTRUCTOR' AND subject.instructor_id = principal.id)
        OR (principal.role = 'STUDENT' AND EXISTS (
            SELECT 1 FROM enrollments AS enrollment
            WHERE enrollment.subject_id = subject.id
              AND enrollment.student_id = principal.id)))
)
SELECT document.id AS document_id, content.id AS content_revision_id,
       index_revision.id AS index_revision_id, page.page_number,
       page.content AS page_text, pdf.source_sha256 AS original_pdf_sha256,
       pdf.page_count AS original_pdf_page_count,
       pdf.byte_size AS original_pdf_byte_size,
       pdf.block_count AS original_pdf_block_count,
       (SELECT count(*) FROM subject_document_pdf_blocks AS block
        WHERE block.content_revision_id = pdf.content_revision_id) AS stored_block_count,
       (SELECT coalesce(sum(block.plaintext_size), 0)
        FROM subject_document_pdf_blocks AS block
        WHERE block.content_revision_id = pdf.content_revision_id) AS stored_pdf_bytes,
       scope.corpus_revision, scope.active_embedding_space_hash
FROM authorized_subject AS scope
JOIN subject_documents AS document
  ON document.subject_id = scope.id AND document.uploader_id = scope.instructor_id
 AND document.id = CAST(:document_id AS uuid)
JOIN subject_document_content_revisions AS content
  ON content.document_id = document.id AND content.subject_id = scope.id
 AND content.uploader_id = document.uploader_id
 AND content.id = CAST(:content_revision_id AS uuid)
 AND content.is_active AND content.status = 'ready'
 AND content.published_at IS NOT NULL AND content.reviewed_at IS NOT NULL
 AND content.reviewed_by_id = document.uploader_id
JOIN subject_document_index_revisions AS index_revision
  ON index_revision.content_revision_id = content.id
 AND index_revision.document_id = document.id AND index_revision.subject_id = scope.id
 AND index_revision.id = CAST(:index_revision_id AS uuid)
 AND index_revision.is_active AND index_revision.status = 'ready'
 AND index_revision.embedding_space_hash = scope.active_embedding_space_hash
JOIN subject_document_pages AS page
  ON page.content_revision_id = content.id AND page.document_id = document.id
 AND page.subject_id = scope.id AND page.uploader_id = document.uploader_id
 AND page.page_number = :page_number
 AND length(page.content) BETWEEN 1 AND 100000
JOIN subject_document_pdfs AS pdf
  ON pdf.content_revision_id = content.id AND pdf.document_id = document.id
 AND pdf.subject_id = scope.id AND pdf.uploader_id = document.uploader_id
 AND pdf.source_sha256 = content.source_sha256
 AND pdf.page_count = content.actual_page_count
 AND pdf.source_sha256 = :original_pdf_sha256
 AND pdf.page_count = :original_pdf_page_count
WHERE EXISTS (
    SELECT 1 FROM eligible_subject_knowledge_chunks AS eligible
    WHERE eligible.subject_id = scope.id
      AND eligible.corpus_revision = scope.corpus_revision
      AND eligible.embedding_space_hash = scope.active_embedding_space_hash
      AND eligible.document_id = document.id
      AND eligible.content_revision_id = content.id
      AND eligible.index_revision_id = index_revision.id
      AND eligible.page_number = page.page_number
)
"""


async def _collect_pages(db: Any, *, principal_id: str, subject_id: str,
                         corpus_revision: int, embedding_space_hash: str,
                         pointers: set[tuple[str, int]], documents: dict[str, dict],
                         cases: dict[str, dict]) -> list[dict[str, Any]]:
    from sqlalchemy import text

    await db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
    await db.execute(text("SET LOCAL statement_timeout = '15000ms'"))
    pages: list[dict[str, Any]] = []
    gold_by_pointer = {(case["document_id"], case["page_number"]): case
                       for case in cases.values()}
    for document_id, page_number in sorted(pointers):
        binding = documents[document_id]
        result = await db.execute(text(_PAGE_SQL), {
            "principal_id": principal_id, "subject_id": subject_id,
            "corpus_revision": corpus_revision,
            "embedding_space_hash": embedding_space_hash,
            "document_id": document_id, "page_number": page_number,
            **binding,
        })
        rows = result.mappings().all()
        _require(len(rows) == 1, "source_unavailable")
        row = rows[0]
        page_text = row["page_text"]
        _require(type(page_text) is str and 0 < len(page_text) <= 100_000
                 and int(row["stored_block_count"]) == int(row["original_pdf_block_count"])
                 and int(row["stored_pdf_bytes"]) == int(row["original_pdf_byte_size"])
                 and int(row["original_pdf_byte_size"]) > 0,
                 "source_unavailable")
        gold = gold_by_pointer.get((document_id, page_number))
        if gold is not None:
            _require(sha256(page_text.encode("utf-8")).hexdigest() == gold["page_sha256"],
                     "gold_page_changed")
        pages.append({
            "document_id": str(row["document_id"]),
            "content_revision_id": str(row["content_revision_id"]),
            "index_revision_id": str(row["index_revision_id"]),
            "page_number": int(row["page_number"]), "page_text": page_text,
            "original_pdf_sha256": row["original_pdf_sha256"],
            "original_pdf_page_count": int(row["original_pdf_page_count"]),
            "corpus_revision": int(row["corpus_revision"]),
            "embedding_space_hash": row["active_embedding_space_hash"],
            "current_authorized": True, "published": True, "index_ready": True,
        })
    return pages


def _validate_pages(pages: list[dict], cases: dict[str, dict],
                    documents: dict[str, dict], slates: list[dict] | None,
                    *, pointers: set[tuple[str, int]], corpus_revision: int,
                    embedding_space_hash: str) -> None:
    import bridge_private_source_gold_v4 as bridge

    _require(len(pages) == len(pointers), "source_unavailable")
    by_key: dict[str, dict] = {}
    for page in pages:
        binding = documents.get(page["document_id"])
        _require(binding is not None and all(page[key] == value for key, value in binding.items())
                 and (page["document_id"], page["page_number"]) in pointers
                 and page["corpus_revision"] == corpus_revision
                 and page["embedding_space_hash"] == embedding_space_hash
                 and page["current_authorized"] is True and page["published"] is True
                 and page["index_ready"] is True, "source_changed")
        key = bridge._digest([page["document_id"], page["page_number"]])
        _require(key not in by_key, "source_changed")
        by_key[key] = page
    for case in cases.values():
        page = by_key.get(case["page_key"])
        _require(page is not None and sha256(page["page_text"].encode("utf-8")).hexdigest()
                 == case["page_sha256"], "gold_page_changed")
    if slates is not None:
        for row in slates:
            for candidate in row["candidates"]:
                page = by_key.get(bridge._digest([
                    candidate["document_id"], candidate["page_number"]
                ]))
                _require(page is not None, "source_unavailable")
                cue = page["page_text"][candidate["start_offset"]:candidate["end_offset"]]
                _require(candidate["end_offset"] <= len(page["page_text"])
                         and bool(cue.strip()), "slates_invalid")


def _write_exclusive(path: Path, body: bytes) -> None:
    _require(0 < len(body) <= MAX_OUTPUT_BYTES, "snapshot_too_large")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        raise Refusal("output_exists") from None
    except OSError:
        raise Refusal("private_temp_required") from None
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        path.chmod(0o600)
    except Exception:
        path.unlink(missing_ok=True)
        raise


async def _execute(args: argparse.Namespace, *, environment: dict[str, str] | None = None,
                   root: Path | None = None, connect: Any = None) -> dict[str, Any]:
    _require(args.stage1_sha256 == FROZEN_STAGE1_SHA256
             and args.stage1 is not None and args.output is not None
             and _canonical_uuid(args.principal_id) and _canonical_uuid(args.subject_id)
             and type(args.corpus_revision) is int and args.corpus_revision >= 1
             and type(args.embedding_space_hash) is str
             and _SHA.fullmatch(args.embedding_space_hash) is not None
             and ((args.slates is None and args.slates_sha256 is None)
                  or (args.slates is not None and type(args.slates_sha256) is str
                      and _SHA.fullmatch(args.slates_sha256) is not None)),
             "invalid_arguments")
    root = root or _temp_root()
    database_url = _guard_runtime(dict(os.environ) if environment is None else environment,
                                  args.expected_database)
    stage1_path = _temp_path(args.stage1, existing=True, root=root)
    output_path = _temp_path(args.output, existing=False, root=root)
    _require(output_path.parent == stage1_path.parent, "private_temp_required")
    stage1_bytes = _read_hashed(stage1_path, FROZEN_STAGE1_SHA256,
                                maximum=MAX_STAGE1_BYTES, code="stage1_changed", root=root)
    stage1, cases, documents = _stage1(stage1_bytes, FROZEN_STAGE1_SHA256)
    _require(stage1["scope"] == {"corpus_revision": args.corpus_revision,
                                  "embedding_space_hash": args.embedding_space_hash},
             "scope_changed")
    slates = None
    pointers = {(case["document_id"], case["page_number"]) for case in cases.values()}
    if args.slates is not None:
        slate_bytes = _read_hashed(args.slates, args.slates_sha256,
                                   maximum=MAX_SLATES_BYTES, code="slates_changed", root=root)
        slates, additional = _slate_pointers(slate_bytes, cases, documents)
        pointers |= additional
    _require(len(pointers) <= MAX_PAGES, "slates_invalid")
    if connect is None:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.pool import NullPool

        engine = create_async_engine(database_url, echo=False, hide_parameters=True,
                                     poolclass=NullPool)
        try:
            async with asyncio.timeout(45):
                async with engine.connect() as db:
                    try:
                        pages = await _collect_pages(
                            db, principal_id=args.principal_id, subject_id=args.subject_id,
                            corpus_revision=args.corpus_revision,
                            embedding_space_hash=args.embedding_space_hash,
                            pointers=pointers, documents=documents, cases=cases,
                        )
                    finally:
                        await db.rollback()
        finally:
            await engine.dispose()
    else:
        # Injection exists for synthetic contract tests only.
        pages = await _collect_pages(
            connect, principal_id=args.principal_id, subject_id=args.subject_id,
            corpus_revision=args.corpus_revision,
            embedding_space_hash=args.embedding_space_hash,
            pointers=pointers, documents=documents, cases=cases,
        )
    _validate_pages(pages, cases, documents, slates, pointers=pointers,
                    corpus_revision=args.corpus_revision,
                    embedding_space_hash=args.embedding_space_hash)
    _require(_read_hashed(stage1_path, FROZEN_STAGE1_SHA256,
                          maximum=MAX_STAGE1_BYTES, code="stage1_changed", root=root)
             == stage1_bytes, "stage1_changed")
    if args.slates is not None:
        _require(_read_hashed(args.slates, args.slates_sha256,
                              maximum=MAX_SLATES_BYTES, code="slates_changed", root=root)
                 == slate_bytes, "slates_changed")
    body = json.dumps({
        "schema": SCHEMA, "stage1_sha256": FROZEN_STAGE1_SHA256,
        "slates_sha256": args.slates_sha256,
        "principal_id": args.principal_id, "subject_id": args.subject_id,
        "scope": stage1["scope"], "authorized_pages": pages,
        "release_gate_passed": False,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    _temp_path(output_path, existing=False, root=root)
    _write_exclusive(output_path, body)
    return {
        "schema": SCHEMA, "status": "snapshot_written",
        "stage1_sha256": FROZEN_STAGE1_SHA256,
        "gold_pages_bound": len(cases), "current_pages_written": len(pages),
        "provider_requests": 0, "database_writes": 0,
        "release_gate_passed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--stage1", type=Path)
    parser.add_argument("--stage1-sha256")
    parser.add_argument("--slates", type=Path)
    parser.add_argument("--slates-sha256")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--principal-id")
    parser.add_argument("--subject-id")
    parser.add_argument("--corpus-revision", type=int)
    parser.add_argument("--embedding-space-hash")
    parser.add_argument("--expected-database")
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({
            "schema": SCHEMA, "status": "preflight_unexecuted",
            "database_reads": 0, "database_writes": 0,
            "provider_requests": 0, "release_gate_passed": False,
        }, separators=(",", ":")))
        return 0
    try:
        report = asyncio.run(_execute(args))
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, Refusal) and exc.args else "snapshot_failed"
        report = {
            "schema": SCHEMA, "status": "refused_or_failed",
            "failure_code": code, "provider_requests": 0,
            "database_writes": 0, "release_gate_passed": False,
        }
    print(json.dumps(report, separators=(",", ":")))
    return 0 if report["status"] == "snapshot_written" else 1


if __name__ == "__main__":
    raise SystemExit(main())
