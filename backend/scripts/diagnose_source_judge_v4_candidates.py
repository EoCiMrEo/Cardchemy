"""Read-only v4 candidate recall on the frozen eleven-case private roster.

Default invocation is a no-database preflight. Execution requires the already
reviewed roster and precomputed query vectors under the isolated /private Temp
mount. It invokes the application's authorized retrieval and candidate pool,
but no embedding or source judge. Only content-free aggregates are emitted.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
from time import perf_counter
from types import SimpleNamespace
from uuid import UUID

import diagnose_source_navigation as base


SCHEMA = "source_judge_v4_candidate_recall_v1"
EXPECTED_CASES = 11
ROSTER_SHA256 = "fca9588c20997424e716a726beac7a64db7bdde1036b18734db28ca4c8cdd730"
VECTOR_SHA256 = "7633a5a48c28386ec99fe72f24736f72a4b204413956fc2bb8ac1443f3e9ae47"
MAX_SECONDS = 300
CASE_SECONDS = 20
SAFE_CODES = frozenset({
    "invalid_arguments", "private_mount_required", "roster_changed",
    "roster_invalid", "vector_packet_invalid", "vector_packet_changed",
    "vector_scope_mismatch", "database_target_invalid", "ai_credentials_present",
    "scope_unavailable", "scope_changed", "gold_unavailable", "source_changed",
    "probe_timeout", "output_exists", "probe_failed",
})


class Refusal(RuntimeError):
    """Fixed content-free failure code; private exception text is never printed."""


def _runtime_sha256() -> str:
    paths = (
        base.BACKEND_ROOT / "app/workers/rag_answer.py",
        base.BACKEND_ROOT / "app/ai/source_navigation.py",
        base.BACKEND_ROOT / "app/services/knowledge_retrieval.py",
        Path(base.__file__).resolve(),
        Path(__file__).resolve(),
    )
    digests = (hashlib.sha256(path.read_bytes()).hexdigest() for path in paths)
    return hashlib.sha256("|".join(digests).encode("ascii")).hexdigest()


def _require_safe_runtime(settings, scope: base.Scope) -> None:
    from sqlalchemy.engine import make_url
    from app.models.knowledge import embedding_space_hash

    if (
        make_url(settings.database_url).host != "db"
        or settings.environment != "development"
        or settings.rag_ask_enabled
    ):
        raise Refusal("database_target_invalid")
    if any((
        settings.flashcard_ai_api_key_value,
        settings.rag_ai_api_key_value,
        settings.rag_embedding_api_key_value,
        settings.rag_source_judge_api_key_value,
        os.environ.get("GOOGLE_API_KEY"),
        os.environ.get("GEMINI_API_KEY"),
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
    )):
        raise Refusal("ai_credentials_present")
    if (
        settings.rag_embedding_model != base.VECTOR_MODEL
        or embedding_space_hash(settings.rag_embedding_space_identity)
        != scope.embedding_space_hash
    ):
        raise Refusal("vector_scope_mismatch")


class _InspectedSourceCapture:
    """Observe authorized canonical-page reads without changing retrieval."""

    def __init__(self, retriever):
        self.retriever = retriever
        self.current_sources = ()

    async def expand_source_neighbors(self, anchors, **kwargs):
        return await self.retriever.expand_source_neighbors(anchors, **kwargs)

    async def read_current_sources(self, ids):
        self.current_sources = await self.retriever.read_current_sources(ids)
        return self.current_sources

    async def read_current_source_pages(self, ids, **kwargs):
        return await self.retriever.read_current_source_pages(ids, **kwargs)


async def evaluate_case(
    db, scope: base.Scope, case: base.Case, vector: tuple[float, ...],
) -> dict[str, object]:
    """Score designated current gold page, never infer unreviewed usefulness."""
    from sqlalchemy import text
    from app.ai.source_navigation import navigation_query_v4
    from app.services.knowledge_retrieval import (
        KnowledgeRetriever, SOURCE_NAVIGATION_RETRIEVAL_POLICY,
    )
    from app.workers.rag_answer import _v4_candidate_pool

    await db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
    history = (("user", case.prior_question),) if case.prior_question else ()
    local_query = navigation_query_v4(case.question, history)
    retriever = await KnowledgeRetriever.authorize(
        db, principal=SimpleNamespace(id=scope.principal_id),
        subject_id=scope.subject_id, query=local_query or case.question,
        document_ids=scope.document_ids,
        limit=SOURCE_NAVIGATION_RETRIEVAL_POLICY.max_results,
        policy=SOURCE_NAVIGATION_RETRIEVAL_POLICY,
    )
    if (
        retriever.scope.principal_id != scope.principal_id
        or retriever.scope.subject_id != scope.subject_id
        or retriever.scope.corpus_revision != scope.corpus_revision
        or retriever.scope.embedding_space_hash != scope.embedding_space_hash
        or retriever.scope.document_ids != scope.document_ids
    ):
        raise Refusal("scope_changed")
    gold = await base._read_gold(db, scope, case)
    gold_document_id = gold.pop("document_id")
    if (
        gold_document_id is None
        or not gold["current_published_gold"]
        or not gold["page_present"]
        or not gold["page_indexed"]
        or not gold["original_pdf_manifest_current"]
        or case.gold_window and gold["gold_window_extracted"] is not True
    ):
        raise Refusal("gold_unavailable")
    observation: dict[str, object] = {
        "group": case.group,
        "resolved": local_query is not None,
        "sql_gold_hit": False,
        "gold_inspected_hit": False,
        "gold_sent_hit": False,
        "inspected_pages": 0,
        "sent_pages": 0,
    }
    if local_query is None:
        return observation
    result = await retriever.retrieve(vector, embedding_space_hash=scope.embedding_space_hash)
    observation["sql_gold_hit"] = any(
        chunk.document_id == gold_document_id and chunk.page_number == case.expected_page
        for chunk in result.chunks
    )
    if result.insufficient:
        return observation
    capture = _InspectedSourceCapture(retriever)
    pool = await _v4_candidate_pool(local_query, result.chunks, capture)
    if pool.examined_pages != len(capture.current_sources):
        raise Refusal("source_changed")
    observation["inspected_pages"] = pool.examined_pages
    observation["sent_pages"] = len(pool.selections)
    observation["gold_inspected_hit"] = any(
        source.document_id == gold_document_id and source.page_number == case.expected_page
        for source in capture.current_sources
    )
    observation["gold_sent_hit"] = any(
        item.source.document_id == gold_document_id
        and item.source.page_number == case.expected_page
        for item in pool.selections
    )
    return observation


def aggregate(observations: tuple[dict[str, object], ...]) -> dict[str, object]:
    def counts(rows: tuple[dict[str, object], ...]) -> dict[str, int]:
        return {
            "cases": len(rows),
            "resolved": sum(bool(row["resolved"]) for row in rows),
            "sql_gold_hit": sum(bool(row["sql_gold_hit"]) for row in rows),
            "gold_inspected_hit": sum(bool(row["gold_inspected_hit"]) for row in rows),
            "gold_sent_hit": sum(bool(row["gold_sent_hit"]) for row in rows),
            "inspected_pages": sum(int(row["inspected_pages"]) for row in rows),
            "sent_pages": sum(int(row["sent_pages"]) for row in rows),
        }

    return {
        **counts(observations),
        "groups": {
            group: counts(tuple(row for row in observations if row["group"] == group))
            for group in ("direct", "paraphrase", "follow_up")
        },
        "any_useful_page_hit": "ungraded",
        "quality_labels_independent_for_this_slate": False,
    }


async def execute(
    cases: tuple[base.Case, ...], scope: base.Scope,
    vectors: dict[str, tuple[float, ...]],
    roster_path: Path, vector_path: Path, output_path: Path,
) -> dict[str, object]:
    from app.config import get_settings
    from app.database import async_session_maker, close_database
    from app.services.knowledge_retrieval import KnowledgeScopeUnavailable, KnowledgeSourceUnavailable

    if len(cases) != EXPECTED_CASES or set(vectors) != {case.case_id for case in cases}:
        raise Refusal("vector_packet_invalid")
    try:
        roster_path = base._under_private_mount(roster_path)
        vector_path = base._under_private_mount(vector_path)
        output_path = base._under_private_mount(output_path)
    except base.Refusal as exc:
        raise Refusal("private_mount_required") from exc
    if output_path.parent != base.PRIVATE_MOUNT.resolve() or output_path.exists():
        raise Refusal("output_exists")
    if hashlib.sha256(roster_path.read_bytes()).hexdigest() != ROSTER_SHA256:
        raise Refusal("roster_changed")
    if hashlib.sha256(vector_path.read_bytes()).hexdigest() != VECTOR_SHA256:
        raise Refusal("vector_packet_changed")
    _require_safe_runtime(get_settings(), scope)
    started = perf_counter()
    observations = []
    try:
        async with asyncio.timeout(MAX_SECONDS):
            for case in cases:
                async with asyncio.timeout(CASE_SECONDS):
                    async with async_session_maker() as db:
                        try:
                            observations.append(await evaluate_case(
                                db, scope, case, vectors[case.case_id],
                            ))
                        finally:
                            await db.rollback()
        if hashlib.sha256(roster_path.read_bytes()).hexdigest() != ROSTER_SHA256:
            raise Refusal("roster_changed")
        if hashlib.sha256(vector_path.read_bytes()).hexdigest() != VECTOR_SHA256:
            raise Refusal("vector_packet_changed")
        metrics = aggregate(tuple(observations))
        report = {
            "schema": SCHEMA,
            "status": "completed",
            "roster_sha256": ROSTER_SHA256,
            "vector_packet_sha256": VECTOR_SHA256,
            "runtime_sha256": _runtime_sha256(),
            "aggregate": metrics,
            "provider_requests": 0,
            "answer_requests": 0,
            "database_writes": 0,
            "release_gate_passed": False,
            "elapsed_seconds": round(perf_counter() - started, 3),
        }
        encoded = json.dumps(report, separators=(",", ":")).encode("ascii")
        try:
            descriptor = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise Refusal("output_exists") from None
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
        return report
    except KnowledgeScopeUnavailable:
        raise Refusal("scope_unavailable") from None
    except KnowledgeSourceUnavailable:
        raise Refusal("source_changed") from None
    except TimeoutError:
        raise Refusal("probe_timeout") from None
    finally:
        await close_database()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--roster", type=Path)
    parser.add_argument("--roster-sha256")
    parser.add_argument("--vectors", type=Path)
    parser.add_argument("--vectors-sha256")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--principal-id")
    parser.add_argument("--subject-id")
    parser.add_argument("--corpus-revision", type=int)
    parser.add_argument("--embedding-space-hash")
    parser.add_argument("--document-id", action="append", default=[])
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({
            "schema": SCHEMA, "status": "preflight_unexecuted",
            "provider_requests": 0, "database_reads": 0,
            "database_writes": 0, "release_gate_passed": False,
        }, separators=(",", ":")))
        return 0
    try:
        if not all((
            args.roster, args.vectors, args.output, args.principal_id,
            args.subject_id, args.corpus_revision, args.embedding_space_hash,
        )) or args.roster_sha256 != ROSTER_SHA256 or args.vectors_sha256 != VECTOR_SHA256:
            raise Refusal("invalid_arguments")
        roster_path = base._under_private_mount(args.roster)
        vector_path = base._under_private_mount(args.vectors)
        output_path = base._under_private_mount(args.output)
        if output_path.exists() or output_path.parent != base.PRIVATE_MOUNT.resolve():
            raise Refusal("output_exists")
        scope = base.Scope(
            UUID(args.principal_id), UUID(args.subject_id),
            args.corpus_revision, args.embedding_space_hash,
            tuple(sorted((UUID(value) for value in args.document_id), key=str)),
        )
        base.validate_scope(scope)
        cases, roster_digest = base.load_roster(roster_path, ROSTER_SHA256)
        if len(cases) != EXPECTED_CASES or roster_digest != ROSTER_SHA256:
            raise Refusal("roster_invalid")
        vectors, vector_digest = base.load_vectors(
            vector_path, VECTOR_SHA256,
            roster_sha256=roster_digest, cases=cases, scope=scope,
        )
        if vector_digest != VECTOR_SHA256:
            raise Refusal("vector_packet_changed")
        sys.path.insert(0, str(base.BACKEND_ROOT))
        report = asyncio.run(execute(
            cases, scope, vectors, roster_path, vector_path, output_path,
        ))
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, (Refusal, base.Refusal)) and exc.args and exc.args[0] in SAFE_CODES else "probe_failed"
        report = {
            "schema": SCHEMA, "status": "refused_or_failed", "failure_code": code,
            "provider_requests": 0, "answer_requests": 0,
            "database_writes": 0, "release_gate_passed": False,
        }
    print(json.dumps(report, separators=(",", ":")))
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
