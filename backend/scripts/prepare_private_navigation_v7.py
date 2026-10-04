"""Provider-free current v7 hybrid inputs from frozen review questions.

The reused v6 validator owns vector/source pins and read-only SQL. Question
admission here is simulated from the frozen evaluation case, not persisted
chat history. Real admission ordering/fencing is tested separately in PG.
No provider, key, Ask job, label change or runtime enablement occurs.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from types import FunctionType, SimpleNamespace
from uuid import UUID, uuid4

import prepare_private_navigation_v6 as previous

# Compatibility handles for the existing isolated outer diagnostic's exact
# vector/source pin validation. They do not load settings or operator state.
snapshot, vectors = previous.snapshot, previous.vectors

SCHEMA = "private_hybrid_visual_v7_preparation_v1"
POLICY = "related_knowledge_navigation_v7"
CONTRACT = "visual_source_id_v3"
FAILURE_STAGE = "not_started"


def local_resolution(question, history):
    from app.ai.source_navigation import navigation_query_v4
    from app.ai.source_navigation_context_v1 import resolve_subject_context
    raw = navigation_query_v4(question, ())
    resolution = resolve_subject_context(question, history, raw_navigation_query=raw)
    if resolution.status == "needs_clarification":
        return None, raw, resolution
    query = raw if resolution.anchor is None else f"{question.strip()} {resolution.anchor.subject}"
    return (query if len(query) <= 4000 else None), raw, resolution


def load_runtime():
    global FAILURE_STAGE
    FAILURE_STAGE = "runtime_settings"
    from app.config import ROOT_DIR, Settings, ASK_REQUIRED_RELEASE_POLICY_VERSION
    previous.require(not (ROOT_DIR / ".env").exists(), "operator_env_mount_forbidden")
    settings = Settings(_env_file=None)
    previous.require(settings.environment == "development" and settings.rag_ask_enabled is False
        and settings.rag_source_judge_provider_enabled is False
        and ASK_REQUIRED_RELEASE_POLICY_VERSION == POLICY
        and settings.rag_source_judge_contract_version == CONTRACT
        and settings.rag_source_judge_max_input_tokens == 32768
        and settings.rag_source_judge_max_output_tokens == 4096
        and settings.rag_source_judge_provider_timeout_seconds == 120
        and settings.rag_source_judge_provider_max_retries == 0
        and all(getattr(settings, name) is None for name in (
            "flashcard_ai_api_key", "rag_ai_api_key", "rag_embedding_api_key", "rag_source_judge_api_key")),
        "runtime_not_closed")
    from app.models.knowledge import embedding_space_hash
    from app.services.knowledge_retrieval import KnowledgeRetriever, SOURCE_NAVIGATION_RETRIEVAL_POLICY
    from app.workers.rag_answer import _v4_candidate_pool
    return SimpleNamespace(settings=settings,
        space_hash=embedding_space_hash(settings.rag_embedding_space_identity),
        navigation_query=lambda question, history: local_resolution(question, history)[0],
        retriever=KnowledgeRetriever, retrieval_policy=SOURCE_NAVIGATION_RETRIEVAL_POLICY,
        candidate_pool=_v4_candidate_pool)


async def collect(db, *, runtime, scope, gold, cases, documents, embeddings):
    global FAILURE_STAGE
    FAILURE_STAGE = "candidate_collection"
    from app.ai import source_judgment_visual_v3 as contract
    from app.services.source_visual_preparation_v3 import prepare_visual_sources_v3
    questions = {case["question"]: case for case in cases.values()}
    previous.require(len(questions) == len(cases), "evaluation_question_ambiguous")
    context_rows = {}

    async def visual_prepare(db, *, question, **kwargs):
        global FAILURE_STAGE
        FAILURE_STAGE = "question_admission"
        case = questions[question]
        history = (("user", case["previous_turn"]),) if case["previous_turn"] else ()
        query, raw, resolved = local_resolution(question, history)
        previous.require(query is not None, "evaluation_context_unresolved")
        now = datetime.now(timezone.utc)
        thread_id = uuid4()
        common = dict(user_id=UUID(scope.principal_id), thread_id=thread_id,
                      subject_id=UUID(scope.subject_id), expires_at=now + timedelta(days=90))
        current = contract.AdmissionUserMessage(message_id=uuid4(),
            content_sha256=sha256(question.encode()).hexdigest(), created_at=now - timedelta(seconds=1), **common)
        prior_question = case["previous_turn"] if raw is None else None
        preceding = (contract.AdmissionUserMessage(message_id=uuid4(),
            content_sha256=sha256(prior_question.encode()).hexdigest(),
            created_at=now - timedelta(seconds=2), **common) if prior_question is not None else None)
        snapshot = contract.SubjectAdmissionSnapshot(current, preceding, scope.corpus_revision,
            scope.embedding_space_hash, now, raw is not None)
        binding = contract.bind_question_context(question, snapshot, checked_at=now,
            raw_navigation_query=raw, preceding_question=prior_question, anchor=resolved.anchor)
        FAILURE_STAGE = "visual_source_preparation"
        prepared = await prepare_visual_sources_v3(db, question=question, snapshot=snapshot,
            checked_at=now, raw_navigation_query=raw, preceding_question=prior_question,
            anchor=resolved.anchor, **kwargs)
        context_rows[case["case_id"]] = {
            "admission_basis": "frozen_case_simulation_not_persisted_history",
            "admission": asdict(snapshot), "admission_sha256": binding.admission_sha256,
            "current_question_sha256": binding.current_question_sha256,
            "literal_anchor": asdict(binding.anchor) if binding.anchor is not None else None,
        }
        return prepared

    scoped_runtime = SimpleNamespace(**vars(runtime), visual_prepare=visual_prepare)
    body, report = await previous.collect(db, runtime=scoped_runtime, scope=scope,
        gold=gold, cases=cases, documents=documents, embeddings=embeddings)
    for row in body["cases"]:
        row["question_context"] = context_rows.get(row["case_id"])
    body.update(schema=SCHEMA, policy=POLICY, contract=CONTRACT,
        admission_basis="frozen_case_simulation_not_persisted_history")
    report.update(schema=SCHEMA, admission_basis="frozen_case_simulation_not_persisted_history",
        context_bound_requests=len(context_rows), literal_context_requests=sum(
            row["literal_anchor"] is not None for row in context_rows.values()))
    return body, report


def canonical(value):
    global FAILURE_STAGE
    FAILURE_STAGE = "serialization"
    def supported(item):
        if isinstance(item, UUID):
            return str(item)
        if type(item) is datetime:
            return item.isoformat()
        raise TypeError("unsupported_output_type")
    return previous.json.dumps(value, default=supported, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode("utf-8")


async def execute(args, **kwargs):
    global FAILURE_STAGE
    FAILURE_STAGE = "exact_input_admission"
    # Keep the consumed v6 module and its state unchanged while reusing its
    # exact input/resource/read-only/rollback/fsync publication mechanics.
    namespace = dict(previous.execute.__globals__, collect=collect, load_runtime=load_runtime,
                     canonical=canonical)
    reused = FunctionType(previous.execute.__code__, namespace, argdefs=previous.execute.__defaults__)
    reused.__kwdefaults__ = dict(previous.execute.__kwdefaults__ or {})
    return await reused(args, **kwargs)


def main():
    namespace = dict(previous.main.__globals__, execute=execute, SCHEMA=SCHEMA)
    return FunctionType(previous.main.__code__, namespace)()


if __name__ == "__main__":
    raise SystemExit(main())
