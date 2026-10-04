"""Disposable PostgreSQL v6 guards with synthetic courses and no provider calls."""
from datetime import timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.models.rag import RagAnswerJob, RagAnswerStageAttempt, RagMessage
from app.time_utils import utcnow
from tests.postgres.test_postgres_source_judgment_policy import _running, _v4_job

pytestmark = pytest.mark.postgres
V6 = "related_knowledge_navigation_v6"


@pytest_asyncio.fixture
async def visual_fixture_users(postgres_session_factory):
    users = []
    yield users
    if users:
        async with postgres_session_factory() as db:
            async with db.begin():
                await db.execute(text("DELETE FROM users WHERE id=ANY(CAST(:ids AS uuid[]))"), {"ids": users})


async def visual_job(engine, session_factory, monkeypatch, users):
    # Seed a real current synthetic course and preserve its separate v4 row.
    old_id, _v3_id, _question_id, _chunk_id = await _v4_job(engine, session_factory, monkeypatch, users)
    async with session_factory() as db:
        async with db.begin():
            old = await db.get(RagAnswerJob, old_id)
            old_question = await db.get(RagMessage, old.question_message_id)
            now = utcnow()
            question = RagMessage(thread_id=old.thread_id, user_id=old.user_id, subject_id=old.subject_id,
                role="user", content="What does alpha mean?", source_count=0,
                created_at=now, expires_at=old_question.expires_at)
            db.add(question)
            await db.flush()
            job = RagAnswerJob(thread_id=old.thread_id, question_message_id=question.id,
                auth_session_id=old.auth_session_id, user_id=old.user_id, subject_id=old.subject_id,
                status="queued", operation_key_hash=uuid4().hex * 2, request_fingerprint=uuid4().hex * 2,
                document_ids=list(old.document_ids), corpus_revision=old.corpus_revision,
                retrieval_policy="hybrid_source_navigation_v9", embedding_space_hash=old.embedding_space_hash,
                embedding_provider=old.embedding_provider, embedding_base_url=old.embedding_base_url,
                embedding_model=old.embedding_model, answer_policy_version=V6,
                source_judge_provider="gemini", source_judge_base_url="https://generativelanguage.googleapis.com",
                source_judge_model="gemini-3.5-flash-lite", source_judge_contract_version="visual_source_id_v2",
                source_judge_input_price_microusd_per_million=300000,
                source_judge_output_price_microusd_per_million=2500000,
                source_judge_max_input_tokens=32768, source_judge_max_output_tokens=4096,
                source_judge_thinking_level="high", source_judge_timeout_seconds=60,
                max_attempts=3, available_at=now, deadline_at=now + timedelta(minutes=5),
                estimated_input_tokens=32768, estimated_output_tokens=4096, estimated_cost_microusd=20000,
                created_at=now, updated_at=now)
            db.add(job)
            await db.flush()
            return job.id, old.id


def stage(job_id, name="source_judgment", **changes):
    values = dict(job_id=job_id, manual_retry_number=0, worker_attempt_number=1,
        stage=name, answer_policy_version=V6, physical_request_count=1 if name != "retrieval" else 0,
        retry_count=0, started_at=utcnow(), completed_at=utcnow(), execution_uncertain=False)
    values.update(changes)
    return RagAnswerStageAttempt(**values)


async def clarification(db, job_id):
    job = await db.get(RagAnswerJob, job_id, with_for_update=True)
    job.status, job.result_kind = "completed", "clarification_needed"
    job.completed_at = utcnow()
    job.worker_id = job.claim_token = job.heartbeat_at = job.lease_expires_at = None
    await db.flush()


@pytest.mark.parametrize("remote", [False, True])
async def test_v6_clarification_is_source_free_before_work_or_after_successful_current_judge(
    postgres_engine, postgres_session_factory, monkeypatch, visual_fixture_users, remote,
):
    job_id, old_id = await visual_job(postgres_engine, postgres_session_factory, monkeypatch, visual_fixture_users)
    await _running(postgres_session_factory, job_id)
    async with postgres_session_factory() as db:
        async with db.begin():
            if remote:
                db.add_all([stage(job_id, "query_embedding"), stage(job_id, "retrieval"), stage(job_id)])
                await db.flush()
            await clarification(db, job_id)
        old = await db.get(RagAnswerJob, old_id)
        assert old.answer_policy_version == "related_knowledge_navigation_v4"
        assert old.source_judge_model == "gemini-3.8-flash"
        assert old.source_judge_thinking_level is old.source_judge_timeout_seconds is None


@pytest.mark.parametrize("changes", [
    {"completed_at": None}, {"error_category": "invalid_ai_output"},
    {"failure_reason": "schema_invalid"}, {"execution_uncertain": True},
    {"physical_request_count": 0},
])
async def test_v6_post_provider_clarification_rejects_unfinished_failed_uncertain_or_zero_call(
    postgres_engine, postgres_session_factory, monkeypatch, visual_fixture_users, changes,
):
    job_id, _old_id = await visual_job(postgres_engine, postgres_session_factory, monkeypatch, visual_fixture_users)
    await _running(postgres_session_factory, job_id)
    async with postgres_session_factory() as db:
        async with db.begin():
            db.add_all([stage(job_id, "query_embedding"), stage(job_id, "retrieval"), stage(job_id, **changes)])
            await db.flush()
            with pytest.raises(DBAPIError):
                async with db.begin_nested():
                    await clarification(db, job_id)


@pytest.mark.parametrize("changes", [
    {"worker_attempt_number": 2}, {"manual_retry_number": 1},
    {"answer_policy_version": "related_knowledge_navigation_v4"},
    {"physical_request_count": 2}, {"retry_count": 1}, {"stage": "answer"},
])
async def test_v6_stage_rejects_stale_claim_policy_wrong_stage_and_repeat_remote_execution(
    postgres_engine, postgres_session_factory, monkeypatch, visual_fixture_users, changes,
):
    job_id, _old_id = await visual_job(postgres_engine, postgres_session_factory, monkeypatch, visual_fixture_users)
    await _running(postgres_session_factory, job_id)
    async with postgres_session_factory() as db:
        async with db.begin():
            with pytest.raises(DBAPIError):
                async with db.begin_nested():
                    db.add(stage(job_id, **changes))
                    await db.flush()
            db.add(stage(job_id))
            await db.flush()
            with pytest.raises(DBAPIError):
                async with db.begin_nested():
                    db.add(stage(job_id))
                    await db.flush()


@pytest.mark.parametrize("field,value", [("source_judge_thinking_level", "low"), ("source_judge_timeout_seconds", 30)])
async def test_v6_thinking_and_timeout_snapshots_cannot_mutate_after_admission(
    postgres_engine, postgres_session_factory, monkeypatch, visual_fixture_users, field, value,
):
    job_id, _old_id = await visual_job(postgres_engine, postgres_session_factory, monkeypatch, visual_fixture_users)
    async with postgres_session_factory() as db:
        async with db.begin():
            with pytest.raises(DBAPIError):
                async with db.begin_nested():
                    job = await db.get(RagAnswerJob, job_id, with_for_update=True)
                    setattr(job, field, value)
                    await db.flush()
