"""Actual enqueue/context/retry contracts on invented local data only."""
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, func, select

from app.config import ASK_REQUIRED_RELEASE_POLICY_VERSION
from app.models.rag import RagAnswerQuestionContext, RagAnswerQuotaEvent, RagMessage
from app.schemas.rag import RagQuestionCreate
from app.services.knowledge_retrieval import KnowledgeRetriever
from app.services.rag_answers import RagAnswerService
from app.services.rag_question_context_v2 import rehydrate_question_context
from app.time_utils import utcnow
from tests.test_rag_answers import _authorize, _seed, _settings


@pytest.fixture(autouse=True)
def release_policy(monkeypatch):
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", ASK_REQUIRED_RELEASE_POLICY_VERSION)


async def fixture(db, monkeypatch):
    _, student, _, subject, _ = await _seed(db)
    settings = _settings(rag_answer_max_active_jobs_per_user=4)
    monkeypatch.setattr(KnowledgeRetriever, "authorize", _authorize(settings))
    service = RagAnswerService(settings)
    async with db.begin():
        thread = await service.create_thread(db, subject_id=subject.id, user=student)
    return service, student, subject, thread


async def enqueue(db, service, student, subject, thread, question, key):
    return await service.enqueue(db, subject_id=subject.id, thread_id=thread.id,
        user=student, data=RagQuestionCreate(question=question), idempotency_key="context-" + key)


async def test_clear_question_and_idempotent_replay_keep_one_context_and_quota(db, monkeypatch):
    service, student, subject, thread = await fixture(db, monkeypatch)
    async with db.begin():
        first = await enqueue(db, service, student, subject, thread, "Explain Bluebird encoding.", "clear-context")
    async with db.begin():
        replay = await enqueue(db, service, student, subject, thread, "Explain Bluebird encoding.", "clear-context")
        hydrated = await rehydrate_question_context(db, job=first, checked_at=utcnow())
        assert first.id == replay.id
        assert hydrated.snapshot.raw_question_clear
        assert hydrated.snapshot.preceding is None
        assert hydrated.local_query == hydrated.question
        assert await db.scalar(select(func.count(RagAnswerQuestionContext.job_id))) == 1
        assert await db.scalar(select(func.count(RagAnswerQuotaEvent.id))) == 1


async def test_ordinary_learning_ignore_keeps_exact_current_question_without_prior_transfer(db, monkeypatch):
    service, student, subject, thread = await fixture(db, monkeypatch)
    question = "What does the Bag-of-Words model ignore about word order?"
    async with db.begin():
        await enqueue(db, service, student, subject, thread, "Explain Bluebird encoding.", "ignore-prior")
    async with db.begin():
        job = await enqueue(db, service, student, subject, thread, question, "ignore-current")
    async with db.begin():
        hydrated = await rehydrate_question_context(db, job=job, checked_at=utcnow())
        assert job.answer_policy_version == "related_knowledge_navigation_v8"
        assert job.source_judge_contract_version == "visual_source_id_v5"
        assert job.source_context_policy_version == "literal_subject_admission_v2"
        assert hydrated.question == hydrated.local_query == question
        assert hydrated.snapshot.preceding is None and hydrated.binding.anchor is None
        assert not hydrated.needs_clarification


async def test_followup_is_bound_at_admission_despite_later_queued_turn(db, monkeypatch):
    service, student, subject, thread = await fixture(db, monkeypatch)
    async with db.begin():
        prior = await enqueue(db, service, student, subject, thread, "Explain Bluebird encoding.", "prior")
    async with db.begin():
        followup = await enqueue(db, service, student, subject, thread, "How does it work?", "followup")
    async with db.begin():
        await enqueue(db, service, student, subject, thread, "Explain Redfox parsing.", "later")
    async with db.begin():
        hydrated = await rehydrate_question_context(db, job=followup, checked_at=utcnow())
        assert hydrated.snapshot.preceding.message_id == prior.question_message_id
        assert hydrated.binding.anchor.subject == "Bluebird encoding"
        assert hydrated.local_query == "How does it work? Bluebird encoding"
        assert "Redfox" not in hydrated.local_query


async def test_expired_latest_user_never_falls_back_to_older_topic(db, monkeypatch):
    service, student, subject, thread = await fixture(db, monkeypatch)
    async with db.begin():
        now = utcnow()
        db.add_all([
            RagMessage(id=uuid4(), thread_id=thread.id, user_id=student.id, subject_id=subject.id,
                role="user", content="Explain Bluebird encoding.", source_count=0,
                created_at=now-timedelta(seconds=3), expires_at=now+timedelta(days=1)),
            RagMessage(id=uuid4(), thread_id=thread.id, user_id=student.id, subject_id=subject.id,
                role="user", content="Explain Redfox parsing.", source_count=0,
                created_at=now-timedelta(seconds=2), expires_at=now-timedelta(seconds=1)),
        ])
    async with db.begin():
        job = await enqueue(db, service, student, subject, thread, "How does it work?", "expired-latest")
    async with db.begin():
        hydrated = await rehydrate_question_context(db, job=job, checked_at=utcnow())
        assert hydrated.needs_clarification
        assert hydrated.snapshot.preceding is None
        assert hydrated.local_query is None


async def test_deleted_context_blocks_manual_retry_before_new_quota_reservation(db, monkeypatch):
    service, student, subject, thread = await fixture(db, monkeypatch)
    from tests.test_rag_answers import _activate_space
    await _activate_space(db, subject, service.settings)
    async with db.begin():
        job = await enqueue(db, service, student, subject, thread, "Explain Bluebird encoding.", "retry-context")
        job.status = "failed"
        job.error_code = "rag_answer_failed"
        job.error_message = "Answer generation failed."
        job.error_retryable = True
        job.completed_at = utcnow()
        await db.execute(delete(RagAnswerQuestionContext).where(RagAnswerQuestionContext.job_id == job.id))
    with pytest.raises(HTTPException) as error:
        async with db.begin():
            await service.retry(db, subject_id=subject.id, thread_id=thread.id, job_id=job.id,
                user=student, idempotency_key="retry-deleted")
    assert error.value.detail["code"] == "rag_question_context_changed"
    assert await db.scalar(select(func.count(RagAnswerQuotaEvent.id))) == 1
