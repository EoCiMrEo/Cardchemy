"""Release shutdown must be fail closed without losing private history reads."""

import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.knowledge import RagEmbeddingSpace, embedding_space_hash
from app.models.rag import RagThread
from app.routers.rag import get_rag_profile
from app.schemas.rag import RagQuestionCreate
from app.services.rag_answers import RagAnswerService
from app.workers.rag_answer import RagAnswerWorker
from tests.test_rag_answers import _seed, _settings


@pytest.mark.parametrize(
    "overrides,runtime_policy",
    [
        ({"rag_ask_enabled": False}, "related_knowledge_navigation_v8"),
        ({"rag_source_judge_provider_enabled": False}, "related_knowledge_navigation_v8"),
        ({"rag_embedding_provider_enabled": False}, "related_knowledge_navigation_v8"),
        ({"rag_embedding_input_cost_per_million_usd": 0}, "related_knowledge_navigation_v8"),
        ({}, "two_request_local_support_v1"),
    ],
)
async def test_release_gate_blocks_new_mutations_and_worker_claims_but_retains_history(
    db, overrides, runtime_policy, monkeypatch
):
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", runtime_policy)
    _owner, student, _outsider, subject, _session = await _seed(db)
    settings = _settings(**overrides)
    # Isolate release/role/pricing gates from the separate Subject-space gate.
    identity = settings.rag_embedding_space_identity
    space = RagEmbeddingSpace(
        identity_hash=embedding_space_hash(identity),
        provider=identity[0], base_url=identity[1], model=identity[2],
        space_revision=identity[3], format_version=identity[4],
        dimensions=identity[5], representation=identity[6], metric=identity[7],
        document_task_mode=identity[8], query_task_mode=identity[9],
    )
    db.add(space)
    subject.active_embedding_space_hash = space.identity_hash
    await db.commit()
    assert settings.rag_index_available is settings.rag_embedding_provider_enabled
    assert settings.rag_answer_available is False
    service = RagAnswerService(settings)
    thread = RagThread(user_id=student.id, subject_id=subject.id)
    db.add(thread)
    await db.commit()

    assert [item.id for item in await service.list_threads(db, subject_id=subject.id, user=student, limit=10)] == [thread.id]
    assert (await service.history(db, subject_id=subject.id, thread_id=thread.id, user=student, limit=10)).messages == []

    with pytest.raises(HTTPException) as new_thread:
        await service.create_thread(db, subject_id=subject.id, user=student)
    assert new_thread.value.detail["code"] == "rag_ask_disabled"

    with pytest.raises(HTTPException) as new_question:
        await service.enqueue(
            db, subject_id=subject.id, thread_id=thread.id, user=student,
            data=RagQuestionCreate(question="Synthetic question?"), idempotency_key="shutdown-question",
        )
    assert new_question.value.detail["code"] == "rag_ask_disabled"

    with pytest.raises(HTTPException) as retry:
        await service.retry(
            db, subject_id=subject.id, thread_id=thread.id, job_id=uuid4(),
            user=student, idempotency_key="shutdown-retry",
        )
    assert retry.value.detail["code"] == "rag_ask_disabled"

    worker = RagAnswerWorker(settings=settings)
    assert await worker.claim_next() is None

    profile = await get_rag_profile(subject.id, student, db, settings)
    assert profile.rag_enabled is True
    assert profile.active_embedding_space_matches is True
    assert profile.ask_enabled is settings.rag_ask_effective_enabled
    assert profile.ask_available is False
    assert profile.source_judge_available is False
    assert profile.answer_available is False


async def test_disabled_answer_worker_pulses_without_claiming(monkeypatch):
    settings = _settings(rag_ask_enabled=True, rag_source_judge_provider_enabled=False)
    worker = RagAnswerWorker(settings=settings)
    stop = asyncio.Event()
    states = []

    async def pulse(state):
        states.append(state)
        stop.set()

    monkeypatch.setattr(worker, "_pulse", pulse)
    await worker.run(stop)
    assert states == ["disabled", "draining"]
