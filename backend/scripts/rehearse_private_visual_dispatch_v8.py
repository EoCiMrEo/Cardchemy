"""Provider-free rehearsal of current SQL/PDF guards for frozen v8 requests.

Runs only inside the bounded, keyless diagnostic container. Every transaction
is read-only and rolled back. A guard receipt proves backend association only;
it is neither provider authority nor a browser/opened-page measurement.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import UUID, uuid4

REPO = Path(__file__).resolve().parents[2]
# Direct script execution does not add the image WORKDIR to Python's path.
# Load the complete image package before the copied preflight's backend path;
# copied fragments are hash witnesses, not an alternative partial app package.
if Path("/app/app/__init__.py").is_file():
    sys.path.insert(0, "/app")
    import app
sys.path.insert(0, str(REPO / "scripts"))
import prepare_private_visual_trial_v8 as preparation
import private_visual_dispatch_guard_v8 as guard

HYBRID_SHA = "676b95a04e79ddcafef16049e6bc54566ded20885a51c67ed5cbb2affb6463bd"
SCHEMA = "private_visual_dispatch_rehearsal_v8"
SQL_TIMEOUT_MS = 5000
LOCK_TIMEOUT_MS = 1000
FINAL_GUARD_SECONDS = 5
FAILURE_STAGE = "startup"


def bind_cases(prepared, packet, hybrid, code):
    """Bind index/offset identities to the old hashed hybrid, never current SQL."""
    scope = guard.DispatchScope(**{**packet["scope"],
        "principal_id": UUID(packet["scope"]["principal_id"]),
        "subject_id": UUID(packet["scope"]["subject_id"])})
    rows = {row["case_id"]: row for row in packet["cases"]}
    indexed = {row["case_id"]: row for row in hybrid["cases"]}
    cases = []
    for frozen in prepared.cases:
        row = rows[frozen.case_id]
        prior = indexed[frozen.case_id]
        preparation.require(prior["question"] == json.loads(row["request"]["contents"][0]["parts"][0]["text"])["question"],
                            "hybrid_question_changed")
        sources = json.loads(frozen.sources_bytes)
        candidates = []
        for source, old in zip(sources, prior["candidates"], strict=True):
            preparation.require(all(source[name] == old[name] for name in (
                "document_id", "content_revision_id", "page_number"))
                and source["cue_sha256"] == old["cue_sha256"]
                and source["page_text_sha256"] == old["page_sha256"], "hybrid_candidate_changed")
            candidates.append(guard.FrozenCandidate(
                source["id"], UUID(source["document_id"]), UUID(source["content_revision_id"]),
                UUID(old["index_revision_id"]), source["page_number"], old["start_offset"], old["end_offset"],
                source["pdf_sha256"], source["cue_sha256"], source["png_sha256"], source["page_text_sha256"]))
        question = json.loads(row["request"]["contents"][0]["parts"][0]["text"])["question"]
        case = guard.FrozenDispatchCase(frozen.case_id, question, frozen.request_bytes,
            preparation.scorer._snapshot(row["admission_snapshot"]), tuple(candidates), row["preceding_question"])
        pins = guard.GuardPins(prepared.bridge_sha256, prepared.runtime_sha256,
            frozen.request_sha256, frozen.admission_sha256,
            sha256(Path(guard.__file__).read_bytes()).hexdigest(), code)
        cases.append((case, pins))
    preparation.require(len(cases) == 12, "case_count_changed")
    return scope, tuple(cases)


async def current_selections(db, scope, case):
    from sqlalchemy import select, text
    from app.ai.related_evidence import RelatedExcerptSelection
    from app.models.knowledge import SubjectDocumentChunk
    from app.services.knowledge_retrieval import KnowledgeRetriever, SOURCE_NAVIGATION_RETRIEVAL_POLICY
    from app.ai.source_navigation import navigation_query_v4
    await db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
    query = navigation_query_v4(case.question, ()) or case.question
    retriever = await KnowledgeRetriever.authorize(db, principal=SimpleNamespace(id=scope.principal_id),
        subject_id=scope.subject_id, query=query, document_ids=tuple(dict.fromkeys(
            row.document_id for row in case.candidates)), limit=SOURCE_NAVIGATION_RETRIEVAL_POLICY.max_results,
        policy=SOURCE_NAVIGATION_RETRIEVAL_POLICY)
    preparation.require(retriever.scope.corpus_revision == scope.corpus_revision
        and retriever.scope.embedding_space_hash == scope.embedding_space_hash, "scope_changed")
    ids = []
    for source in case.candidates:
        chunk = await db.scalar(select(SubjectDocumentChunk.id).where(
            SubjectDocumentChunk.subject_id == scope.subject_id,
            SubjectDocumentChunk.document_id == source.document_id,
            SubjectDocumentChunk.content_revision_id == source.content_revision_id,
            SubjectDocumentChunk.index_revision_id == source.index_revision_id,
            SubjectDocumentChunk.page_number == source.page_number,
            SubjectDocumentChunk.embedding_space_hash == scope.embedding_space_hash,
        ).order_by(SubjectDocumentChunk.chunk_index, SubjectDocumentChunk.id).limit(1))
        preparation.require(chunk is not None, "current_anchor_unavailable")
        ids.append(chunk)
    current = {row.chunk_id: row for row in await retriever.read_current_sources(ids)}
    pages = await retriever.read_current_source_pages(ids, max_pages=4, max_tokens=8192)
    preparation.require(len(current) == len(pages) == 4, "current_sources_unavailable")
    return tuple(RelatedExcerptSelection(current[chunk], source.start_offset, source.end_offset,
        source_kind="canonical_page", page_content=pages[chunk]) for chunk, source in zip(ids, case.candidates, strict=True))


async def execute(directory):
    global FAILURE_STAGE
    preparation.require(HYBRID_SHA != "0" * 64, "matching_v8_freeze_required")
    FAILURE_STAGE = "runtime_environment"
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool
    from app.config import Settings, ROOT_DIR
    preparation.require(not (ROOT_DIR / ".env").exists() and not (REPO / ".env").exists()
        and not any(key.endswith("API_KEY") for key in os.environ), "runtime_not_closed")
    preparation.require(Path("/sys/fs/cgroup/memory.max").read_text().strip() == "2147483648"
        and Path("/sys/fs/cgroup/cpu.max").read_text().strip() == "400000 100000", "resource_fence_required")
    settings = Settings(_env_file=None)
    FAILURE_STAGE = "frozen_preflight"
    prepared = preparation.preflight_directory(directory)
    packet = json.loads(dict(prepared.artifacts)["requests"])
    raw = (directory / "hybrid-preparation.json").read_bytes()
    preparation.require(sha256(raw).hexdigest() == HYBRID_SHA, "hybrid_changed")
    code = dict(prepared.code_sha256)
    for name in guard.REQUIRED_CODE_PATHS | {"backend/scripts/rehearse_private_visual_dispatch_v8.py"}:
        code[name] = sha256((REPO / name).read_bytes()).hexdigest()
    FAILURE_STAGE = "frozen_candidate_bindings"
    scope, cases = bind_cases(prepared, packet, json.loads(raw), code)
    FAILURE_STAGE = "database_engine"
    engine = create_async_engine(settings.database_url, echo=False, hide_parameters=True, poolclass=NullPool,
        connect_args={"server_settings": {"statement_timeout": str(SQL_TIMEOUT_MS),
            "lock_timeout": str(LOCK_TIMEOUT_MS), "idle_in_transaction_session_timeout": "15000"}})
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    completed = []
    try:
        for case, pins in cases:
            FAILURE_STAGE = "current_anchor_lookup"
            # The anchor lookup is in its own transaction, before a fresh guard.
            async with factory() as db:
                FAILURE_STAGE = "authenticated_render"
                await db.begin()
                try:
                    async with asyncio.timeout(10):
                        selections = await current_selections(db, scope, case)
                finally:
                    await db.rollback()
            async with factory() as db:
                FAILURE_STAGE = "fresh_dispatch_guard"
                await db.begin()
                try:
                    async with asyncio.timeout(30):
                        proof = await guard.prepare_dispatch_proof_v8(db, settings=settings, scope=scope,
                            case=case, selections=selections, pins=pins)
                finally:
                    await db.rollback()
            # A separate short read demonstrates the exact final production
            # callback, with no provider operation at this rehearsal boundary.
            trial, nonce = uuid4(), uuid4()
            async with factory() as db:
                await db.begin()
                try:
                    async with asyncio.timeout(FINAL_GUARD_SECONDS):
                        receipt = await guard.verify_private_visual_dispatch_v8(db, settings=settings, scope=scope,
                            case=case, selections=selections, pins=pins, proof=proof, trial_id=trial,
                            dispatch_nonce=nonce, after_quota_wait=True)
                        encoded = preparation.canonical(receipt)
                        guard.require_dispatch_receipt_binding(encoded, receipt_sha256=sha256(encoded).hexdigest(),
                            now=datetime.now(timezone.utc), trial_id=trial, dispatch_nonce=nonce,
                            scope=scope, case=case, pins=pins)
                finally:
                    await db.rollback()
            completed.append({"case_id": case.case_id, "exact_request_verified": True,
                "fresh_sql_pdf_guard_verified": True, "guard_receipt_sha256": sha256(encoded).hexdigest()})
    finally:
        await engine.dispose()
    return {"schema": SCHEMA, "status": "rehearsal_passed", "provider_calls": 0, "database_writes": 0,
        "case_count": len(completed), "cases": completed, "code_sha256": code,
        "hybrid_sha256": HYBRID_SHA, "bridge_sha256": prepared.bridge_sha256,
        "sql_statement_timeout_ms": SQL_TIMEOUT_MS, "sql_lock_timeout_ms": LOCK_TIMEOUT_MS,
        "final_callback_timeout_seconds": FINAL_GUARD_SECONDS, "separate_fresh_transactions": True,
        "root_env_mounted": False, "provider_credentials_present": False,
        "provider_dispatch_observed": False, "browser_page_open_observed": False, "release_gate_passed": False}


if __name__ == "__main__":
    try:
        result = asyncio.run(execute(Path(sys.argv[1])))
    except Exception as error:
        code = str(error) if type(error) in (preparation.Refusal, guard.DispatchGuardError) else "local_rehearsal_failed"
        result = {"schema": SCHEMA, "status": "rehearsal_refused", "failure_code": code,
                  "failure_stage": FAILURE_STAGE, "exception_kind": type(error).__name__,
                  "provider_calls": 0, "database_writes": 0, "release_gate_passed": False}
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["status"] == "rehearsal_passed" else 2)
