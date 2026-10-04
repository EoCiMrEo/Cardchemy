"""Read-only, provider-free diagnostic of the current v3/v9 Ask navigation path.

This does not enqueue an Ask job, call Gemini, change a policy, or establish a
release gate. It uses an explicitly supplied real principal and a frozen gold
roster, then runs the existing lexical fallback or, with a separate SHA-frozen
private query-vector packet, the current hybrid retriever and source selector
against current published Knowledge. Vector origin is supplied, not proved by
this probe. Private questions, quotes, and source identities are written only
beneath the one-off container's /private OS-Temp bind mount.

Default invocation is a no-DB preflight. The intended one-off process has the
backend Compose environment and network, no AI credential, a read-only
PostgreSQL transaction for every case, and no mounted repository write path.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from time import perf_counter
from types import SimpleNamespace
from uuid import UUID


SCHEMA = "source_navigation_lexical_diagnostic_v1"
HYBRID_SCHEMA = "source_navigation_hybrid_diagnostic_v1"
ROSTER_SCHEMA = "cardchemy_original_pdf_page_holdout_v1"
VECTOR_SCHEMA = "cardchemy_private_query_vectors_v1"
VECTOR_MODEL = "gemini-embedding-001"
VECTOR_DIMENSIONS = 1_536
VECTOR_NORM_TOLERANCE = 0.001
MAX_VECTOR_PACKET_BYTES = 1_000_000
PRIVATE_MOUNT = Path("/private")
BACKEND_ROOT = (Path("/app") if (Path("/app") / "app").is_dir()
                else Path(__file__).resolve().parents[1])
MAX_CASES = 24
MAX_SECONDS = 300
CASE_SECONDS = 20
SAFE_CODES = frozenset({
    "invalid_arguments", "roster_invalid", "roster_changed", "private_mount_required",
    "output_exists", "database_target_invalid", "scope_unavailable", "scope_changed",
    "source_changed", "gold_ambiguous", "probe_timeout", "probe_failed",
    "vector_packet_invalid", "vector_packet_changed", "vector_scope_mismatch",
})
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_CASE_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,31}\Z")


class Refusal(RuntimeError):
    """Fixed safe code. Never print or persist exception text from a private read."""


@dataclass(frozen=True, slots=True)
class Case:
    case_id: str
    group: str
    question: str
    prior_question: str
    expected_pdf_sha256: str
    expected_page: int
    gold_window: str


@dataclass(frozen=True, slots=True)
class Scope:
    principal_id: UUID
    subject_id: UUID
    corpus_revision: int
    embedding_space_hash: str
    document_ids: tuple[UUID, ...] = ()


def _under_private_mount(path: Path) -> Path:
    root = PRIVATE_MOUNT.resolve()
    resolved = path.resolve()
    if not root.is_dir() or not resolved.is_relative_to(root) or resolved == root:
        raise Refusal("private_mount_required")
    return resolved


def load_roster(path: Path, expected_sha256: str) -> tuple[tuple[Case, ...], str]:
    path = _under_private_mount(path)
    if not _SHA.fullmatch(expected_sha256) or not path.is_file() or path.stat().st_size > 96_000:
        raise Refusal("roster_invalid")
    raw = path.read_bytes()
    if not 1 <= len(raw) <= 96_000:
        raise Refusal("roster_invalid")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise Refusal("roster_changed")
    try:
        data = json.loads(raw)
        rows = data["cases"]
        if data["schema"] != ROSTER_SCHEMA or not isinstance(rows, list) or not 1 <= len(rows) <= MAX_CASES:
            raise ValueError
        cases = []
        for row in rows:
            case = Case(
                case_id=row["case_id"], group=row["group"], question=row["question"],
                prior_question=row.get("prior_question", ""),
                expected_pdf_sha256=row["expected_pdf_sha256"],
                expected_page=row["expected_page"], gold_window=row.get("gold_window", ""),
            )
            if (not isinstance(case.case_id, str) or not _CASE_ID.fullmatch(case.case_id)
                or case.group not in ("direct", "paraphrase", "follow_up")
                or not isinstance(case.question, str) or not 0 < len(case.question.strip()) <= 4_000
                or "\x00" in case.question or not isinstance(case.prior_question, str)
                or len(case.prior_question) > 1_000 or "\x00" in case.prior_question
                or (case.group == "follow_up") != bool(case.prior_question.strip())
                or not isinstance(case.expected_pdf_sha256, str)
                or not _SHA.fullmatch(case.expected_pdf_sha256)
                or type(case.expected_page) is not int or not 1 <= case.expected_page <= 100
                or not isinstance(case.gold_window, str)
                or len(case.gold_window) > 480 or "\x00" in case.gold_window):
                raise ValueError
            cases.append(case)
        if len({case.case_id for case in cases}) != len(cases):
            raise ValueError
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise Refusal("roster_invalid") from None
    return tuple(cases), digest


def load_vectors(path: Path, expected_sha256: str, *, roster_sha256: str,
                 cases: tuple[Case, ...], scope: Scope) -> tuple[dict[str, tuple[float, ...]], str]:
    """Validate a complete, byte-frozen private packet before any database read.

    The vector is for the original current question, exactly as the Ask worker
    embeds it. The roster SHA also binds each follow-up's local history. Model
    and space fields are assertions about packet provenance, not an attestation
    that the external provider produced the values.
    """
    path = _under_private_mount(path)
    if (not isinstance(expected_sha256, str) or not _SHA.fullmatch(expected_sha256)
        or not path.is_file() or not 1 <= path.stat().st_size <= MAX_VECTOR_PACKET_BYTES):
        raise Refusal("vector_packet_invalid")
    raw = path.read_bytes()
    if not 1 <= len(raw) <= MAX_VECTOR_PACKET_BYTES:
        raise Refusal("vector_packet_invalid")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise Refusal("vector_packet_changed")
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or set(data) != {
            "schema", "roster_sha256", "embedding_space_hash", "model", "vectors",
        } or data["schema"] != VECTOR_SCHEMA or data["roster_sha256"] != roster_sha256:
            raise ValueError
        if data["model"] != VECTOR_MODEL or data["embedding_space_hash"] != scope.embedding_space_hash:
            raise Refusal("vector_scope_mismatch")
        rows = data["vectors"]
        if not isinstance(rows, list) or len(rows) != len(cases):
            raise ValueError
        by_case = {case.case_id: case for case in cases}
        vectors: dict[str, tuple[float, ...]] = {}
        for row in rows:
            if (not isinstance(row, dict) or set(row) != {"case_id", "question_sha256", "embedding"}
                or not isinstance(row["case_id"], str) or row["case_id"] not in by_case
                or row["case_id"] in vectors or not isinstance(row["question_sha256"], str)
                or row["question_sha256"] != hashlib.sha256(
                    by_case[row["case_id"]].question.encode("utf-8")
                ).hexdigest()):
                raise ValueError
            values = row["embedding"]
            if not isinstance(values, list) or len(values) != VECTOR_DIMENSIONS or any(
                type(value) not in (float, int) or not math.isfinite(value) for value in values
            ):
                raise ValueError
            vector = tuple(float(value) for value in values)
            norm = math.sqrt(math.fsum(value * value for value in vector))
            if not math.isfinite(norm) or abs(norm - 1.0) > VECTOR_NORM_TOLERANCE:
                raise ValueError
            vectors[row["case_id"]] = vector
        if set(vectors) != set(by_case):
            raise ValueError
    except Refusal:
        raise
    except (KeyError, TypeError, ValueError, OverflowError, UnicodeDecodeError, json.JSONDecodeError):
        raise Refusal("vector_packet_invalid") from None
    return vectors, digest


def validate_scope(scope: Scope) -> None:
    if (type(scope.corpus_revision) is not int or scope.corpus_revision < 1
        or not _SHA.fullmatch(scope.embedding_space_hash)
        or len(scope.document_ids) > 50 or len(set(scope.document_ids)) != len(scope.document_ids)):
        raise Refusal("invalid_arguments")


def _runtime_sha256() -> str:
    paths = (
        BACKEND_ROOT / "app/ai/source_navigation.py",
        BACKEND_ROOT / "app/ai/related_evidence.py",
        BACKEND_ROOT / "app/services/knowledge_retrieval.py",
        Path(__file__).resolve(),
    )
    digests = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
    return hashlib.sha256("|".join(digests).encode("ascii")).hexdigest()


_GOLD_SQL = """
WITH authorized_subject AS (
    SELECT subject.id, subject.corpus_revision, subject.active_embedding_space_hash
    FROM subjects AS subject JOIN users AS principal ON principal.id = :principal_id
    WHERE subject.id = :subject_id AND subject.corpus_revision = :corpus_revision
      AND subject.active_embedding_space_hash = :space_hash
      AND ((principal.role = 'INSTRUCTOR' AND subject.instructor_id = principal.id)
        OR (principal.role = 'STUDENT' AND EXISTS (
            SELECT 1 FROM enrollments AS enrollment
            WHERE enrollment.student_id = principal.id AND enrollment.subject_id = subject.id)))
)
SELECT document.id AS document_id, content.id AS content_revision_id,
       page.id IS NOT NULL AS page_present,
       CASE WHEN :gold_window = '' THEN NULL
            ELSE COALESCE(position(:gold_window in page.content) > 0, false)
       END AS gold_window_extracted,
       EXISTS (SELECT 1 FROM eligible_subject_knowledge_chunks AS eligible
               WHERE eligible.subject_id = scope.id
                 AND eligible.corpus_revision = scope.corpus_revision
                 AND eligible.embedding_space_hash = scope.active_embedding_space_hash
                 AND eligible.document_id = document.id
                 AND eligible.content_revision_id = content.id
                 AND eligible.page_number = :gold_page) AS page_indexed,
       (pdf.content_revision_id IS NOT NULL
        AND pdf.source_sha256 = content.source_sha256
        AND pdf.page_count = content.actual_page_count
        AND :gold_page <= pdf.page_count) AS original_pdf_manifest_current
FROM authorized_subject AS scope
JOIN subject_documents AS document ON document.subject_id = scope.id
JOIN subject_document_content_revisions AS content
  ON content.document_id = document.id AND content.subject_id = scope.id
 AND content.is_active AND content.status = 'ready' AND content.published_at IS NOT NULL
 AND content.reviewed_at IS NOT NULL AND content.reviewed_by_id = document.uploader_id
JOIN subject_document_index_revisions AS index_revision
  ON index_revision.content_revision_id = content.id AND index_revision.subject_id = scope.id
 AND index_revision.is_active AND index_revision.status = 'ready'
 AND index_revision.embedding_space_hash = scope.active_embedding_space_hash
LEFT JOIN subject_document_pages AS page
  ON page.content_revision_id = content.id AND page.page_number = :gold_page
LEFT JOIN subject_document_pdfs AS pdf ON pdf.content_revision_id = content.id
WHERE document.uploader_id = (SELECT instructor_id FROM subjects WHERE id = scope.id)
  AND content.source_sha256 = :expected_pdf_sha256
  AND (NOT :has_document_filter OR document.id = ANY(CAST(:document_ids AS uuid[])))
LIMIT 2
"""


_PDF_SQL = """
WITH authorized_subject AS (
    SELECT subject.id, subject.corpus_revision, subject.active_embedding_space_hash
    FROM subjects AS subject JOIN users AS principal ON principal.id = :principal_id
    WHERE subject.id = :subject_id AND subject.corpus_revision = :corpus_revision
      AND subject.active_embedding_space_hash = :space_hash
      AND ((principal.role = 'INSTRUCTOR' AND subject.instructor_id = principal.id)
        OR (principal.role = 'STUDENT' AND EXISTS (
            SELECT 1 FROM enrollments AS enrollment
            WHERE enrollment.student_id = principal.id AND enrollment.subject_id = subject.id)))
)
SELECT (pdf.content_revision_id IS NOT NULL
        AND pdf.source_sha256 = content.source_sha256
        AND pdf.page_count = content.actual_page_count
        AND :page_number <= pdf.page_count) AS original_pdf_manifest_current
FROM authorized_subject AS scope
JOIN subject_document_content_revisions AS content
  ON content.subject_id = scope.id AND content.id = :content_revision_id
 AND content.document_id = :document_id AND content.is_active AND content.status = 'ready'
 AND content.published_at IS NOT NULL AND content.reviewed_at IS NOT NULL
JOIN subject_documents AS document
  ON document.id = content.document_id AND document.uploader_id = content.reviewed_by_id
JOIN subject_document_index_revisions AS index_revision
  ON index_revision.content_revision_id = content.id AND index_revision.subject_id = scope.id
 AND index_revision.is_active AND index_revision.status = 'ready'
 AND index_revision.embedding_space_hash = scope.active_embedding_space_hash
LEFT JOIN subject_document_pdfs AS pdf ON pdf.content_revision_id = content.id
WHERE (NOT :has_document_filter OR document.id = ANY(CAST(:document_ids AS uuid[])))
"""


async def _read_gold(db, scope: Scope, case: Case) -> dict:
    from sqlalchemy import text
    rows = (await db.execute(text(_GOLD_SQL), {
        "principal_id": scope.principal_id, "subject_id": scope.subject_id,
        "corpus_revision": scope.corpus_revision, "space_hash": scope.embedding_space_hash,
        "gold_window": case.gold_window, "gold_page": case.expected_page,
        "expected_pdf_sha256": case.expected_pdf_sha256,
        "has_document_filter": bool(scope.document_ids),
        "document_ids": list(scope.document_ids),
    })).mappings().all()
    if len(rows) > 1:
        raise Refusal("gold_ambiguous")
    if not rows:
        return {"current_published_gold": False, "page_present": False,
                "gold_window_extracted": False, "page_indexed": False,
                "original_pdf_manifest_current": False, "document_id": None}
    row = rows[0]
    return {"current_published_gold": True, "page_present": bool(row["page_present"]),
            "gold_window_extracted": (bool(row["gold_window_extracted"])
                                      if case.gold_window else None),
            "page_indexed": bool(row["page_indexed"]),
            "original_pdf_manifest_current": bool(row["original_pdf_manifest_current"]),
            "document_id": row["document_id"]}


async def _read_selected_pdf_manifest(db, scope: Scope, source) -> bool:
    from sqlalchemy import text
    row = (await db.execute(text(_PDF_SQL), {
        "principal_id": scope.principal_id, "subject_id": scope.subject_id,
        "corpus_revision": scope.corpus_revision, "space_hash": scope.embedding_space_hash,
        "content_revision_id": source.content_revision_id,
        "document_id": source.document_id, "page_number": source.page_number,
        "has_document_filter": bool(scope.document_ids),
        "document_ids": list(scope.document_ids),
    })).mappings().one_or_none()
    return bool(row and row["original_pdf_manifest_current"])


async def evaluate_case(db, scope: Scope, case: Case, *,
                        query_embedding: tuple[float, ...] | None = None) -> dict:
    """One repeatable-read, read-only snapshot; output remains private."""
    from sqlalchemy import text
    from app.ai.source_navigation import navigation_query, select_navigation_pages
    from app.services.knowledge_retrieval import (
        KnowledgeRetriever, SOURCE_NAVIGATION_RETRIEVAL_POLICY,
    )
    from app.services.rag_answers import locate_page_reference

    await db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
    local_query = navigation_query(case.question,
                                   (("user", case.prior_question),) if case.prior_question else ())
    retriever = await KnowledgeRetriever.authorize(
        db, principal=SimpleNamespace(id=scope.principal_id), subject_id=scope.subject_id,
        query=local_query or case.question, document_ids=scope.document_ids,
        limit=SOURCE_NAVIGATION_RETRIEVAL_POLICY.max_results,
        policy=SOURCE_NAVIGATION_RETRIEVAL_POLICY,
    )
    if (retriever.scope.principal_id != scope.principal_id
        or retriever.scope.subject_id != scope.subject_id
        or retriever.scope.corpus_revision != scope.corpus_revision
        or retriever.scope.embedding_space_hash != scope.embedding_space_hash
        or retriever.scope.document_ids != scope.document_ids):
        raise Refusal("scope_changed")
    gold = await _read_gold(db, scope, case)
    chunks = ()
    neighbors = []
    selection = None
    if local_query is not None:
        chunks = (await retriever.retrieve(
            query_embedding, embedding_space_hash=scope.embedding_space_hash,
        ) if query_embedding is not None else await retriever.retrieve_lexical()).chunks

        async def expand(anchors, radius, max_chunks, max_pages, max_tokens):
            found = await retriever.expand_source_neighbors(
                anchors, radius=radius, max_chunks=max_chunks,
                max_pages=max_pages, max_tokens=max_tokens,
            )
            neighbors.extend(found)
            return found

        async def pages(chunk_ids, max_pages, max_tokens):
            return await retriever.read_current_source_pages(
                chunk_ids, max_pages=max_pages, max_tokens=max_tokens,
            )

        selection, _radius = await select_navigation_pages(local_query, chunks, expand, pages)

    chosen = selection.selections if selection is not None else ()
    current = (await retriever.read_current_sources(
        tuple(item.source.chunk_id for item in chosen)) if chosen else ())
    by_id = {source.chunk_id: source for source in current}
    if len(by_id) != len(chosen):
        raise Refusal("source_changed")
    canonical = (await retriever.read_current_source_pages(
        tuple(item.source.chunk_id for item in chosen), max_pages=max(1, len(chosen)),
        max_tokens=8_192,
    ) if chosen else {})
    selected = []
    for item in chosen:
        source = by_id[item.source.chunk_id]
        fields = ("document_id", "content_revision_id", "index_revision_id", "page_number",
                  "section", "document_title", "content", "token_count",
                  "embedding_space_hash", "corpus_revision")
        if any(getattr(source, field) != getattr(item.source, field) for field in fields):
            raise Refusal("source_changed")
        page = canonical.get(source.chunk_id)
        if item.source_kind == "canonical_page":
            valid = (page is not None and page == item.page_content
                     and 0 <= item.start_offset < item.end_offset <= len(page)
                     and page[item.start_offset:item.end_offset] == item.quote)
            span = (item.start_offset, item.end_offset) if valid else None
        elif item.source_kind == "chunk":
            valid = (0 <= item.start_offset < item.end_offset <= len(source.content)
                     and source.content[item.start_offset:item.end_offset] == item.quote)
            span = locate_page_reference(page, item.quote) if valid and page else None
        else:
            valid, span = False, None
        if not valid or len(item.quote) > 480:
            raise Refusal("source_changed")
        selected.append({
            "document_id": str(source.document_id), "content_revision_id": str(source.content_revision_id),
            "page_number": source.page_number, "source_kind": item.source_kind,
            "quote": item.quote, "start_offset": item.start_offset,
            "end_offset": item.end_offset, "exact_source_slice": True,
            "canonical_page_aligned": span is not None,
            "original_pdf_manifest_current": await _read_selected_pdf_manifest(db, scope, source),
            "opened_original_pdf": False,
        })
    gold_id = gold.pop("document_id")
    def is_gold(item) -> bool:
        return gold_id is not None and item.document_id == gold_id and item.page_number == case.expected_page
    return {
        "case_id": case.case_id, "group": case.group, "question": case.question,
        "prior_question": case.prior_question, "gold_pdf_sha256": case.expected_pdf_sha256,
        "gold_page_number": case.expected_page, "gold": gold,
        "navigation_query_resolved": local_query is not None,
        "query_vector_used": query_embedding is not None and local_query is not None,
        "navigation_query": local_query,
        "sql_candidate_count": len(chunks),
        "gold_sql_rank": next((index for index, chunk in enumerate(chunks, 1) if is_gold(chunk)), None),
        "neighbor_count": len(neighbors),
        "gold_in_neighbor_pool": any(is_gold(item.chunk) for item in neighbors),
        "examined_chunks": selection.examined_chunks if selection else 0,
        "examined_pages": selection.examined_pages if selection else 0,
        "examined_tokens": selection.examined_tokens if selection else 0,
        "result_kind": "related_pages" if selected else "no_match",
        "gold_display_rank": next((index for index, item in enumerate(selected, 1)
                                   if gold_id is not None and item["document_id"] == str(gold_id)
                                   and item["page_number"] == case.expected_page), None),
        "selected": selected,
        "provider_requests": 0, "database_writes": 0, "answer_requests": 0,
        "release_gate_passed": False,
    }


def aggregate(observations: tuple[dict, ...]) -> dict:
    groups = {}
    for group in ("direct", "paraphrase", "follow_up"):
        rows = [row for row in observations if row["group"] == group]
        groups[group] = {"cases": len(rows),
                         "current_published_gold": sum(row["gold"]["current_published_gold"] for row in rows),
                         "gold_sql_hit": sum(row["gold_sql_rank"] is not None for row in rows),
                         "gold_display_hit": sum(row["gold_display_rank"] is not None for row in rows)}
    return {"cases": len(observations), "groups": groups,
            "current_published_gold": sum(row["gold"]["current_published_gold"] for row in observations),
            "gold_window_extracted": sum(row["gold"]["gold_window_extracted"] is True
                                         for row in observations),
            "gold_page_indexed": sum(row["gold"]["page_indexed"] for row in observations),
            "resolved_queries": sum(row["navigation_query_resolved"] for row in observations),
            "query_vectors_used": sum(row["query_vector_used"] for row in observations),
            "sql_gold_hit": sum(row["gold_sql_rank"] is not None for row in observations),
            "neighbor_gold_hit": sum(row["gold_in_neighbor_pool"] for row in observations),
            "display_gold_hit": sum(row["gold_display_rank"] is not None for row in observations),
            "displayed_cards": sum(len(row["selected"]) for row in observations),
            "pdf_manifests_current": sum(item["original_pdf_manifest_current"]
                                         for row in observations for item in row["selected"])}


async def execute(cases: tuple[Case, ...], roster_sha256: str, roster_path: Path,
                  output_path: Path, scope: Scope, *,
                  vectors: dict[str, tuple[float, ...]] | None = None,
                  vector_path: Path | None = None,
                  vector_sha256: str | None = None) -> dict:
    from sqlalchemy.engine import make_url
    from app.config import get_settings
    from app.database import async_session_maker, close_database
    from app.models.knowledge import embedding_space_hash
    from app.services.knowledge_retrieval import KnowledgeScopeUnavailable

    settings = get_settings()
    if (make_url(settings.database_url).host != "db" or settings.environment != "development"
        or settings.rag_ask_enabled):
        raise Refusal("database_target_invalid")
    started = perf_counter()
    observations = []
    hybrid = vectors is not None
    schema = HYBRID_SCHEMA if hybrid else SCHEMA
    search_mode = ("hybrid_precomputed_query_vector" if hybrid
                   else "lexical_fallback_without_embedding_attempt")
    if (hybrid != (vector_path is not None and vector_sha256 is not None)
        or hybrid and set(vectors) != {case.case_id for case in cases}):
        raise Refusal("vector_packet_invalid")
    if hybrid and (settings.rag_embedding_model != VECTOR_MODEL
                   or embedding_space_hash(settings.rag_embedding_space_identity)
                   != scope.embedding_space_hash):
        raise Refusal("vector_scope_mismatch")
    try:
        async with asyncio.timeout(MAX_SECONDS):
            for case in cases:
                async with asyncio.timeout(CASE_SECONDS):
                    async with async_session_maker() as db:
                        try:
                            observations.append(await evaluate_case(
                                db, scope, case,
                                query_embedding=vectors[case.case_id] if vectors is not None else None,
                            ))
                        finally:
                            await db.rollback()
        if hashlib.sha256(roster_path.read_bytes()).hexdigest() != roster_sha256:
            raise Refusal("roster_changed")
        if hybrid and hashlib.sha256(vector_path.read_bytes()).hexdigest() != vector_sha256:
            raise Refusal("vector_packet_changed")
        metrics = aggregate(tuple(observations))
        private = {"schema": schema, "roster_sha256": roster_sha256,
                   "runtime_sha256": _runtime_sha256(), "scope": {
                       "principal_id": str(scope.principal_id), "subject_id": str(scope.subject_id),
                       "corpus_revision": scope.corpus_revision,
                       "embedding_space_hash": scope.embedding_space_hash,
                       "document_ids": [str(value) for value in scope.document_ids],
                   }, "search_mode": search_mode,
                   "vector_packet_sha256": vector_sha256 if hybrid else None,
                   "vector_model": VECTOR_MODEL if hybrid else None,
                   "quality_labels_independent": False,
                   "opened_pdf_route_tested": False, "release_gate_passed": False,
                   "observations": observations, "aggregate": metrics}
        encoded = json.dumps(private, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        try:
            descriptor = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise Refusal("output_exists") from None
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
        return {"schema": schema, "status": "completed_private_observations",
                "search_mode": search_mode,
                "aggregate": metrics, "provider_requests": 0, "answer_requests": 0,
                "database_writes": 0, "quality_labels_independent": False,
                "opened_pdf_route_tested": False, "release_gate_passed": False,
                "elapsed_seconds": round(perf_counter() - started, 3)}
    except KnowledgeScopeUnavailable:
        raise Refusal("scope_unavailable") from None
    except TimeoutError:
        raise Refusal("probe_timeout") from None
    finally:
        await close_database()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--roster", type=Path)
    parser.add_argument("--roster-sha256")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--principal-id")
    parser.add_argument("--subject-id")
    parser.add_argument("--corpus-revision", type=int)
    parser.add_argument("--embedding-space-hash")
    parser.add_argument("--document-id", action="append", default=[])
    parser.add_argument("--vectors", type=Path,
                        help="SHA-frozen /private packet; enables hybrid retrieval without provider calls")
    parser.add_argument("--vectors-sha256")
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"schema": HYBRID_SCHEMA if args.vectors else SCHEMA,
                          "status": "preflight_unexecuted",
                          "provider_requests": 0, "database_reads": 0, "database_writes": 0,
                          "release_gate_passed": False}, separators=(",", ":")))
        return 0
    try:
        if not all((args.roster, args.roster_sha256, args.output, args.principal_id,
                    args.subject_id, args.corpus_revision, args.embedding_space_hash)):
            raise Refusal("invalid_arguments")
        roster_path = _under_private_mount(args.roster)
        output_path = _under_private_mount(args.output)
        if output_path.exists() or output_path.parent != PRIVATE_MOUNT.resolve():
            raise Refusal("output_exists")
        scope = Scope(UUID(args.principal_id), UUID(args.subject_id), args.corpus_revision,
                      args.embedding_space_hash,
                      tuple(sorted((UUID(value) for value in args.document_id), key=str)))
        validate_scope(scope)
        cases, digest = load_roster(roster_path, args.roster_sha256)
        if bool(args.vectors) != bool(args.vectors_sha256):
            raise Refusal("invalid_arguments")
        vector_path = _under_private_mount(args.vectors) if args.vectors else None
        vectors, vector_digest = (load_vectors(
            vector_path, args.vectors_sha256, roster_sha256=digest,
            cases=cases, scope=scope,
        ) if vector_path else (None, None))
        sys.path.insert(0, str(BACKEND_ROOT))
        report = asyncio.run(execute(
            cases, digest, roster_path, output_path, scope,
            vectors=vectors, vector_path=vector_path, vector_sha256=vector_digest,
        ))
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, Refusal) and exc.args and exc.args[0] in SAFE_CODES else "probe_failed"
        report = {"schema": HYBRID_SCHEMA if args.vectors else SCHEMA,
                  "status": "refused_or_failed", "failure_code": code,
                  "provider_requests": 0, "answer_requests": 0, "database_writes": 0,
                  "release_gate_passed": False}
    print(json.dumps(report, separators=(",", ":")))
    return 0 if report["status"] == "completed_private_observations" else 1


if __name__ == "__main__":
    raise SystemExit(main())
