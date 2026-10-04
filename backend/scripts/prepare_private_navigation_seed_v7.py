"""Provider-free current seed and bounded wrong-source inputs for visual v7.

The eleven exposed questions and vectors are immutable September 28 inputs.
Current publication/revision/PDF bindings are obtained in read-only SQL; a
changed corpus revision is recorded, never silently substituted in old files.
N12 reuses its original exposed bag-of-words question. U01 and U02 are bounded
source-qualification controls, not assertions of corpus-wide absence. Their
fresh exact cues/pages need independent review before any provider execution.
Default invocation performs no file, environment, Settings or database read.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
from uuid import UUID

import prepare_private_navigation_v7 as current

previous = current.previous
snapshot = previous.snapshot
SCHEMA = "private_seed_visual_v7_preparation_v1"
ROSTER_SHA = "fca9588c20997424e716a726beac7a64db7bdde1036b18734db28ca4c8cdd730"
SCOPE_SHA = "5069818c55e848f0457d8747032274c44ccbf4d24309909746c604df4664cdae"
VECTOR_SHA = "7633a5a48c28386ec99fe72f24736f72a4b204413956fc2bb8ac1443f3e9ae47"
SEEDS = tuple([f"D{i:02}" for i in range(1, 7)] + [f"P{i:02}" for i in range(1, 5)] + ["H01"])
MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_SECONDS = 300
FAILURE_STAGE = "not_started"


def _bound(raw, digest, maximum=MAX_INPUT_BYTES):
    previous.require(type(raw) is bytes and 0 < len(raw) <= maximum
        and type(digest) is str and snapshot._SHA.fullmatch(digest)
        and sha256(raw).hexdigest() == digest, "input_changed")
    try:
        return json.loads(raw, object_pairs_hook=snapshot._unique_object)
    except (ValueError, UnicodeError, RecursionError):
        raise previous.Refusal("input_invalid") from None


def prepare(roster_raw, scope_raw, vector_raw, source_raw, *, source_sha256,
            roster_sha256=ROSTER_SHA, scope_sha256=SCOPE_SHA, vectors_sha256=VECTOR_SHA):
    """Validate frozen old questions/vectors plus separately pinned current pages."""
    roster = _bound(roster_raw, roster_sha256, 96_000)
    old = _bound(scope_raw, scope_sha256, 16_384)
    vector = _bound(vector_raw, vectors_sha256, previous.MAX_VECTOR_BYTES)
    source = _bound(source_raw, source_sha256)
    # The immutable old CLI packet serialized its revision argument as a
    # decimal string. Normalize only that separately SHA-bound old field;
    # current authorized source revisions remain exact integers.
    historical_revision = old.get("corpus_revision") if type(old) is dict else None
    if type(historical_revision) is str and historical_revision.isdecimal():
        parsed = int(historical_revision)
        if str(parsed) == historical_revision:
            historical_revision = parsed
    previous.require(type(roster) is dict and set(roster) == {"schema", "label", "cases"}
        and roster["schema"] == "cardchemy_original_pdf_page_holdout_v1"
        and type(roster["cases"]) is list and len(roster["cases"]) == 11,
        "seed_roster_invalid")
    previous.require(type(old) is dict and set(old) == {
        "principal_id", "subject_id", "corpus_revision", "embedding_space_hash"}
        and all(snapshot._canonical_uuid(old[k]) for k in ("principal_id", "subject_id"))
        and type(historical_revision) is int and historical_revision >= 1
        and type(old["embedding_space_hash"]) is str
        and snapshot._SHA.fullmatch(old["embedding_space_hash"]), "scope_invalid")
    previous.require(type(source) is dict and source.get("schema") == snapshot.SCHEMA
        and source.get("principal_id") == old["principal_id"]
        and source.get("subject_id") == old["subject_id"]
        and type(source.get("scope")) is dict
        and set(source["scope"]) == {"corpus_revision", "embedding_space_hash"}
        and type(source["scope"]["corpus_revision"]) is int
        and source["scope"]["corpus_revision"] >= 1
        and source["scope"]["embedding_space_hash"] == old["embedding_space_hash"]
        and source.get("release_gate_passed") is False
        and type(source.get("authorized_pages")) is list
        and 1 <= len(source["authorized_pages"]) <= snapshot.MAX_PAGES, "source_scope_changed")
    documents, by_pdf = {}, {}
    for page in source["authorized_pages"]:
        previous.require(type(page) is dict and all(snapshot._canonical_uuid(page.get(k))
            for k in ("document_id", "content_revision_id", "index_revision_id"))
            and page.get("current_authorized") is True and page.get("published") is True
            and page.get("index_ready") is True
            and page.get("corpus_revision") == source["scope"]["corpus_revision"]
            and page.get("embedding_space_hash") == old["embedding_space_hash"]
            and type(page.get("original_pdf_sha256")) is str
            and snapshot._SHA.fullmatch(page["original_pdf_sha256"])
            and type(page.get("original_pdf_page_count")) is int
            and 1 <= page["original_pdf_page_count"] <= 10_000, "source_invalid")
        binding = {k: page[k] for k in ("content_revision_id", "index_revision_id",
            "original_pdf_sha256", "original_pdf_page_count")}
        previous.require(documents.get(page["document_id"], binding) == binding,
            "source_changed")
        documents[page["document_id"]] = binding
        by_pdf.setdefault(binding["original_pdf_sha256"], set()).add(page["document_id"])
    cases = {}
    for row in roster["cases"]:
        previous.require(type(row) is dict and set(row) == {"case_id", "group", "question",
            "prior_question", "expected_pdf_sha256", "expected_page"}
            and row["case_id"] in SEEDS and row["case_id"] not in cases
            and row["group"] in ("direct", "paraphrase", "follow_up")
            and type(row["question"]) is str and 1 <= len(row["question"].strip()) <= 4_000
            and "\x00" not in row["question"] and type(row["prior_question"]) is str
            and len(row["prior_question"]) <= 1_000 and "\x00" not in row["prior_question"]
            and (row["group"] == "follow_up") == bool(row["prior_question"].strip())
            and type(row["expected_page"]) is int
            and type(row["expected_pdf_sha256"]) is str
            and len(by_pdf.get(row["expected_pdf_sha256"], ())) == 1, "seed_roster_invalid")
        document_id = next(iter(by_pdf[row["expected_pdf_sha256"]]))
        previous.require(1 <= row["expected_page"] <= documents[document_id]["original_pdf_page_count"],
            "gold_page_invalid")
        cases[row["case_id"]] = {"case_id": row["case_id"], "question": row["question"],
            "previous_turn": row["prior_question"],
            "form": "followup" if row["group"] == "follow_up" else row["group"],
            "document_id": document_id, "page_number": row["expected_page"],
            "page_key": previous.bridge._digest([document_id, row["expected_page"]])}
    previous.require(set(cases) == set(SEEDS), "seed_roster_invalid")
    previous.require(type(vector) is dict and set(vector) == {
        "schema", "roster_sha256", "embedding_space_hash", "model", "vectors"}
        and vector["schema"] == "cardchemy_private_query_vectors_v1"
        and vector["roster_sha256"] == roster_sha256
        and vector["embedding_space_hash"] == old["embedding_space_hash"]
        and vector["model"] == "gemini-embedding-001"
        and type(vector["vectors"]) is list and len(vector["vectors"]) == 11, "vector_invalid")
    embeddings = {}
    for row in vector["vectors"]:
        previous.require(type(row) is dict and set(row) == {"case_id", "question_sha256", "embedding"}
            and row["case_id"] in cases and row["case_id"] not in embeddings
            and row["question_sha256"] == sha256(cases[row["case_id"]]["question"].encode()).hexdigest()
            and type(row["embedding"]) is list and len(row["embedding"]) == 1536, "vector_invalid")
        try:
            previous.require(all(type(x) in (int, float) and math.isfinite(x) for x in row["embedding"])
                and abs(math.sqrt(math.fsum(x*x for x in row["embedding"])) - 1) <= .001,
                "vector_invalid")
        except (ValueError, OverflowError):
            raise previous.Refusal("vector_invalid") from None
        embeddings[row["case_id"]] = tuple(row["embedding"])
    scope = previous.Scope(old["principal_id"], old["subject_id"],
        source["scope"]["corpus_revision"], old["embedding_space_hash"])
    return scope, cases, documents, embeddings, {
        "roster_sha256": roster_sha256, "historical_scope_sha256": scope_sha256,
        "vectors_sha256": vectors_sha256, "source_snapshot_sha256": source_sha256,
        "historical_corpus_revision": historical_revision,
        "scope": source["scope"], "existing_raw_query_vectors_reused": 11}


async def _control_pool(db, retriever, case, documents):
    """Force one current gold page for a bounded candidate-level negative only."""
    from sqlalchemy import select
    from app.models.knowledge import SubjectDocumentChunk
    from app.ai.related_evidence import RelatedExcerptSelection
    binding = documents[case["document_id"]]
    chunk_id = await db.scalar(select(SubjectDocumentChunk.id).where(
        SubjectDocumentChunk.document_id == UUID(case["document_id"]),
        SubjectDocumentChunk.content_revision_id == UUID(binding["content_revision_id"]),
        SubjectDocumentChunk.index_revision_id == UUID(binding["index_revision_id"]),
        SubjectDocumentChunk.page_number == case["page_number"]
    ).order_by(SubjectDocumentChunk.chunk_index).limit(1))
    previous.require(chunk_id is not None, "control_source_unavailable")
    sources = await retriever.read_current_sources((chunk_id,))
    previous.require(len(sources) == 1, "control_source_unavailable")
    pages = await retriever.read_current_source_pages((chunk_id,), max_pages=1, max_tokens=8192)
    previous.require(len(pages) == 1 and chunk_id in pages, "control_source_unavailable")
    text = pages[chunk_id]
    previous.require(type(text) is str and text.strip(), "control_source_unavailable")
    from app.services.knowledge_retrieval import RetrievedKnowledgeChunk
    source = RetrievedKnowledgeChunk(**asdict(sources[0]), vector_similarity=None,
        lexical_score=None, vector_rank=None, lexical_rank=None, fusion_score=0.0)
    previous.require(str(source.document_id) == case["document_id"]
        and source.page_number == case["page_number"], "control_source_changed")
    return SimpleNamespace(selections=(RelatedExcerptSelection(source, 0, min(480, len(text)),
        "canonical_page", text),))


async def collect(session_factory, *, runtime, scope, cases, documents, embeddings, provenance):
    """Fresh read-only canonical gold then actual hybrid seeds and bounded controls."""
    global FAILURE_STAGE
    FAILURE_STAGE = "current_gold_pages"
    previous.require(runtime.space_hash == scope.embedding_space_hash, "profile_incompatible")
    pointers = {(c["document_id"], c["page_number"]) for c in cases.values()}
    async with session_factory() as db:
        try:
            pages = await snapshot._collect_pages(db, principal_id=scope.principal_id,
                subject_id=scope.subject_id, corpus_revision=scope.corpus_revision,
                embedding_space_hash=scope.embedding_space_hash, pointers=pointers,
                documents=documents, cases={})
        finally:
            await db.rollback()
    by_pointer = {(p["document_id"], p["page_number"]): p for p in pages}
    bound_cases = {}
    for key, case in cases.items():
        page = by_pointer.get((case["document_id"], case["page_number"]))
        previous.require(page is not None, "gold_page_unavailable")
        bound_cases[key] = {**case, "page_sha256": sha256(page["page_text"].encode()).hexdigest()}
    # The original N12 source checks bag-of-words word-order evidence. U01's
    # wrong source is BLEU, even though the full corpus has logistic evidence.
    controls = {
        "N12": {**bound_cases["D04"], "case_id": "N12", "form": "control"},
        "U01": {**bound_cases["D02"], "case_id": "U01", "form": "control",
            "question": bound_cases["D05"]["question"], "previous_turn": ""},
        "U02": {**bound_cases["D02"], "case_id": "U02", "form": "control",
            "question": bound_cases["D03"]["question"], "previous_turn": ""},
    }
    rows, aggregate = [], Counter()
    for key, case in [*bound_cases.items(), *controls.items()]:
        FAILURE_STAGE = "controlled_source_inputs" if key in ("U01", "U02") else "hybrid_seed_inputs"
        forced = key in ("U01", "U02")
        original_vector = {"N12": "D04", "U01": "D05", "U02": "D03"}.get(key, key)
        scoped = runtime
        if forced:
            async def pool(query, initial, retriever, fixed=case):
                return await _control_pool(retriever._db, retriever, fixed, documents)
            scoped = SimpleNamespace(**{**vars(runtime), "candidate_pool": pool})
        async with session_factory() as db:
            try:
                body, report = await current.collect(db, runtime=scoped, scope=scope,
                    gold={"scope": provenance["scope"]}, cases={key: case}, documents=documents,
                    embeddings={key: embeddings[original_vector]})
            finally:
                await db.rollback()
        row = body["cases"][0]
        row.update(evaluation_role=("bounded_wrong_source_control" if forced else
            "exposed_source_control" if key == "N12" else "exposed_seed"),
            require_empty_candidate_slate=forced, independent_candidate_labels="pending",
            gold_page_key=None if forced else case["page_key"],
            corpus_absence_claim=False, previous_turn=case["previous_turn"])
        rows.append(row)
        if key in SEEDS:
            aggregate["seed_gold_in_initial"] += int(report.get("gold_in_initial", 0))
            aggregate["seed_gold_in_pool"] += int(report.get("gold_in_pool", 0))
        for name in ("gold_in_initial", "gold_in_pool", "candidate_pages", "visual_inputs_prepared",
                     "clarification_needed", "context_bound_requests", "literal_context_requests"):
            aggregate[name] += int(report.get(name, 0))
    body = {"schema": SCHEMA, "policy": current.POLICY, "contract": current.CONTRACT,
        "principal_id": scope.principal_id, "subject_id": scope.subject_id,
        **provenance, "cases": rows, "release_gate_passed": False,
        "labels_pending": True, "provider_calls": 0, "database_writes": 0}
    report = {"schema": SCHEMA, "status": "seed_inputs_prepared", "case_count": len(rows),
        "seed_count": 11, "exposed_source_control_count": 1, "bounded_wrong_source_control_count": 2,
        "forms": dict(Counter(row["form"] for row in rows)), **aggregate,
        "labels_pending": True, "provider_calls": 0, "database_writes": 0,
        "release_gate_passed": False}
    return body, report


async def execute(args, *, environment=None, root=None, runtime=None, session_factory=None):
    global FAILURE_STAGE
    FAILURE_STAGE = "execution_admission"
    started = perf_counter()
    url = previous.guard_runtime(dict(os.environ) if environment is None else environment,
        args.expected_database)
    previous.require(args.roster_sha256 == ROSTER_SHA and args.scope_sha256 == SCOPE_SHA
        and args.vectors_sha256 == VECTOR_SHA, "historical_input_changed")
    paths = [snapshot._temp_path(p, existing=True, root=root) for p in (
        args.roster, args.scope_snapshot, args.vectors, args.source_snapshot)]
    output = snapshot._temp_path(args.output, existing=False, root=root)
    previous.require(len({p.parent for p in (*paths, output)}) == 1, "private_directory_required")
    digests = (args.roster_sha256, args.scope_sha256, args.vectors_sha256, args.source_sha256)
    raw = [snapshot._read_hashed(p, d, maximum=MAX_INPUT_BYTES,
        code="input_changed", root=root) for p, d in zip(paths, digests, strict=True)]
    scope, cases, documents, embeddings, provenance = prepare(*raw,
        source_sha256=args.source_sha256)
    FAILURE_STAGE = "runtime_profile"
    engine = None
    if runtime is None:
        previous.guard_resources()
        runtime = current.load_runtime()
    if session_factory is None:
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlalchemy.pool import NullPool
        engine = create_async_engine(url, echo=False, hide_parameters=True, poolclass=NullPool,
            connect_args={"server_settings": {"statement_timeout": "15000", "lock_timeout": "1000"}})
        session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    try:
        async with asyncio.timeout(max(.001, MAX_SECONDS - (perf_counter() - started))):
            body, report = await collect(session_factory, runtime=runtime, scope=scope,
                cases=cases, documents=documents, embeddings=embeddings, provenance=provenance)
            FAILURE_STAGE = "output_binding"
            for p, d, original in zip(paths, digests, raw, strict=True):
                previous.require(snapshot._read_hashed(p, d, maximum=MAX_INPUT_BYTES,
                    code="input_changed", root=root) == original, "input_changed")
            encoded = current.canonical(body)
            previous.require(perf_counter() - started < MAX_SECONDS, "time_budget_exceeded")
            previous.write_exclusive(output, encoded)
            if perf_counter() - started >= MAX_SECONDS:
                output.unlink(missing_ok=True)
                raise previous.Refusal("time_budget_exceeded")
            return {**report, "snapshot_sha256": sha256(encoded).hexdigest()}
    finally:
        if engine is not None:
            await asyncio.wait_for(engine.dispose(), timeout=5)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--execute", action="store_true")
    for name in ("roster", "scope-snapshot", "vectors", "source-snapshot", "output"):
        parser.add_argument("--" + name, type=Path)
    for name in ("roster-sha256", "scope-sha256", "vectors-sha256", "source-sha256", "expected-database"):
        parser.add_argument("--" + name)
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"schema": SCHEMA, "status": "unexecuted", "database_reads": 0,
            "database_writes": 0, "provider_calls": 0, "release_gate_passed": False}))
        return 0
    try:
        previous.require(all(v is not None for k, v in vars(args).items() if k != "execute"),
            "arguments_invalid")
        report = asyncio.run(execute(args))
    except Exception:
        report = {"schema": SCHEMA, "status": "refused_or_failed", "provider_calls": 0,
            "database_writes": 0, "release_gate_passed": False}
    print(json.dumps(report))
    return 0 if report["status"] == "seed_inputs_prepared" else 2


if __name__ == "__main__":
    raise SystemExit(main())
