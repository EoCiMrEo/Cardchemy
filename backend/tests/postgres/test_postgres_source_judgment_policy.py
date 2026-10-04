"""Disposable PostgreSQL contracts for the prospective source-ID stage.

These tests make no provider call and never activate the retained Ask worker.
"""

from datetime import timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.models.knowledge import SubjectDocumentChunk
from app.models.rag import RagAnswerJob, RagAnswerStageAttempt, RagMessage, RagRelatedEvidence
from app.time_utils import utcnow
from tests.postgres.test_postgres_rag_answers import _ready_course, _student_and_job


pytestmark = pytest.mark.postgres
V4 = "related_knowledge_navigation_v4"


@pytest_asyncio.fixture
async def v4_fixture_users(postgres_session_factory):
    """Keep synthetic queued jobs out of subsequent shared-database tests."""
    users = []
    yield users
    if users:
        async with postgres_session_factory() as db:
            async with db.begin():
                await db.execute(
                    text("DELETE FROM users WHERE id=ANY(CAST(:ids AS uuid[]))"),
                    {"ids": users},
                )


async def _v4_job(engine, session_factory, monkeypatch, users):
    # The v3 fixture seeds a real enrolled and published synthetic course; v4
    # is inserted separately so its immutable snapshot is never a rewritten v3.
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", "related_knowledge_navigation_v3")
    settings, owner_id, subject_id, _content_id, chunk_id = await _ready_course(
        engine, session_factory,
    )
    users.append(owner_id)
    student_id, auth_id, thread_id, old_id = await _student_and_job(
        session_factory, settings, subject_id, key=f"v3-before-v4-{uuid4().hex}",
    )
    users.append(student_id)
    async with session_factory() as db:
        async with db.begin():
            old = await db.get(RagAnswerJob, old_id)
            old_question = await db.get(RagMessage, old.question_message_id)
            assert old is not None and old_question is not None
            assert old.source_judge_provider is None
            now = utcnow()
            question = RagMessage(
                thread_id=thread_id, user_id=student_id, subject_id=subject_id,
                role="user", outcome=None, content="What is alpha?", source_count=0,
                created_at=now, expires_at=old_question.expires_at,
            )
            db.add(question)
            await db.flush()
            job = RagAnswerJob(
                thread_id=thread_id, question_message_id=question.id,
                auth_session_id=auth_id, user_id=student_id, subject_id=subject_id,
                status="queued", operation_key_hash=uuid4().hex * 2,
                request_fingerprint=uuid4().hex * 2,
                document_ids=list(old.document_ids), corpus_revision=old.corpus_revision,
                retrieval_policy=old.retrieval_policy,
                embedding_space_hash=old.embedding_space_hash,
                embedding_provider=old.embedding_provider,
                embedding_base_url=old.embedding_base_url,
                embedding_model=old.embedding_model,
                answer_policy_version=V4,
                source_judge_provider="gemini",
                source_judge_base_url="https://generativelanguage.googleapis.com",
                source_judge_model="gemini-3.8-flash",
                source_judge_contract_version="source_id_only_public_v1",
                source_judge_input_price_microusd_per_million=1_500_000,
                source_judge_output_price_microusd_per_million=7_500_000,
                source_judge_max_input_tokens=8_192,
                source_judge_max_output_tokens=1_024,
                max_attempts=3, available_at=now, deadline_at=now + timedelta(minutes=5),
                estimated_input_tokens=8_192,
                estimated_output_tokens=1_024,
                estimated_cost_microusd=20_000,
                created_at=now, updated_at=now,
            )
            db.add(job)
            await db.flush()
            return job.id, old_id, question.id, chunk_id


async def _running(session_factory, job_id):
    async with session_factory() as db:
        async with db.begin():
            job = await db.get(RagAnswerJob, job_id, with_for_update=True)
            assert job is not None
            now = utcnow()
            job.status = "running"
            job.attempt_count = 1
            job.worker_id = "v4-disposable-test"
            job.claim_token = "d" * 64
            job.heartbeat_at = now
            job.lease_expires_at = min(job.deadline_at, now + timedelta(seconds=30))
            job.provider_call_started_at = now
            job.retrieval_completed_at = now


def _stage(job_id, stage, *, policy=V4, calls=0, retries=0, finished=True):
    return RagAnswerStageAttempt(
        job_id=job_id, manual_retry_number=0, worker_attempt_number=1,
        stage=stage, answer_policy_version=policy,
        physical_request_count=calls, retry_count=retries,
        started_at=utcnow(), completed_at=utcnow() if finished else None,
        execution_uncertain=not finished,
    )


async def test_v4_stage_parent_and_one_physical_call_guards(
    postgres_engine, postgres_session_factory, monkeypatch, v4_fixture_users,
):
    job_id, old_id, _question_id, _chunk_id = await _v4_job(
        postgres_engine, postgres_session_factory, monkeypatch, v4_fixture_users,
    )
    await _running(postgres_session_factory, job_id)
    async with postgres_session_factory() as db:
        async with db.begin():
            db.add(_stage(job_id, "query_embedding", calls=1))
            db.add(_stage(job_id, "retrieval"))
            await db.flush()
            for stage in (
                _stage(job_id, "answer", calls=1),
                _stage(job_id, "query_embedding", calls=1),
                _stage(job_id, "source_judgment", calls=2),
                _stage(job_id, "source_judgment", calls=1, retries=1),
                _stage(job_id, "source_judgment", policy="related_knowledge_navigation_v3", calls=1),
                _stage(job_id, "source_judgment", policy=None, calls=1),
            ):
                with pytest.raises(DBAPIError):
                    async with db.begin_nested():
                        db.add(stage)
                        await db.flush()
            db.add(_stage(job_id, "source_judgment", calls=1))
            await db.flush()
            with pytest.raises(DBAPIError):
                async with db.begin_nested():
                    db.add(_stage(job_id, "source_judgment", calls=1))
                    await db.flush()
    async with postgres_session_factory() as db:
        stages = (await db.scalars(select(RagAnswerStageAttempt).where(
            RagAnswerStageAttempt.job_id == job_id,
        ))).all()
        assert sorted((stage.stage, stage.physical_request_count) for stage in stages) == [
            ("query_embedding", 1), ("retrieval", 0), ("source_judgment", 1),
        ]
        old = await db.get(RagAnswerJob, old_id)
        assert old is not None and old.answer_policy_version == "related_knowledge_navigation_v3"
        assert old.source_judge_provider is None


async def test_v4_reference_requires_successful_judgment_and_immutable_snapshot(
    postgres_engine, postgres_session_factory, monkeypatch, v4_fixture_users,
):
    job_id, _old_id, question_id, chunk_id = await _v4_job(
        postgres_engine, postgres_session_factory, monkeypatch, v4_fixture_users,
    )
    await _running(postgres_session_factory, job_id)
    async with postgres_session_factory() as db:
        async with db.begin():
            job = await db.get(RagAnswerJob, job_id, with_for_update=True)
            question = await db.get(RagMessage, question_id)
            chunk = await db.get(SubjectDocumentChunk, chunk_id)
            assert job is not None and question is not None and chunk is not None
            now = utcnow()

            def reference(kind="canonical_page"):
                return RagRelatedEvidence(
                    job_id=job_id, excerpt_order=1, bundle_size=1,
                    thread_id=job.thread_id, user_id=job.user_id,
                    subject_id=job.subject_id, chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    content_revision_id=chunk.content_revision_id,
                    index_revision_id=chunk.index_revision_id,
                    source_kind=kind, start_offset=0, end_offset=10,
                    manual_retry_number=0, created_at=now,
                    expires_at=question.expires_at,
                )

            with pytest.raises(DBAPIError):
                async with db.begin_nested():
                    db.add(reference())
                    await db.flush()
            db.add(_stage(job_id, "source_judgment", calls=1))
            await db.flush()
            with pytest.raises(DBAPIError):
                async with db.begin_nested():
                    db.add(reference("chunk"))
                    await db.flush()
            db.add(reference())
            await db.flush()
            with pytest.raises(DBAPIError):
                async with db.begin_nested():
                    job.source_judge_model = "changed-after-admission"
                    await db.flush()
            await db.refresh(job)
            job.status = "completed"
            job.result_kind = "related_knowledge"
            job.completed_at = utcnow()
            job.worker_id = None
            job.claim_token = None
            job.heartbeat_at = None
            job.lease_expires_at = None
            await db.flush()
    async with postgres_session_factory() as db:
        job = await db.get(RagAnswerJob, job_id)
        assert job is not None and job.result_kind == "related_knowledge"
        assert job.answer_message_id is None and job.source_judge_model == "gemini-3.8-flash"


async def test_v4_reclaimed_attempt_cannot_reuse_prior_judgment_for_references(
    postgres_engine, postgres_session_factory, monkeypatch, v4_fixture_users,
):
    job_id, _old_id, question_id, chunk_id = await _v4_job(
        postgres_engine, postgres_session_factory, monkeypatch, v4_fixture_users,
    )
    await _running(postgres_session_factory, job_id)
    async with postgres_session_factory() as db:
        async with db.begin():
            db.add(_stage(job_id, "source_judgment", calls=1))
            await db.flush()
            job = await db.get(RagAnswerJob, job_id, with_for_update=True)
            assert job is not None
            job.status = "queued"
            job.worker_id = None
            job.claim_token = None
            job.heartbeat_at = None
            job.lease_expires_at = None
            await db.flush()
            now = utcnow()
            job.status = "running"
            job.attempt_count = 2
            job.worker_id = "v4-reclaimed-test"
            job.claim_token = "e" * 64
            job.heartbeat_at = now
            job.lease_expires_at = min(job.deadline_at, now + timedelta(seconds=30))
            await db.flush()
            question = await db.get(RagMessage, question_id)
            chunk = await db.get(SubjectDocumentChunk, chunk_id)
            assert question is not None and chunk is not None
            with pytest.raises(DBAPIError):
                async with db.begin_nested():
                    db.add(RagRelatedEvidence(
                        job_id=job_id, excerpt_order=1, bundle_size=1,
                        thread_id=job.thread_id, user_id=job.user_id,
                        subject_id=job.subject_id, chunk_id=chunk.id,
                        document_id=chunk.document_id,
                        content_revision_id=chunk.content_revision_id,
                        index_revision_id=chunk.index_revision_id,
                        source_kind="canonical_page", start_offset=0,
                        end_offset=10, manual_retry_number=0,
                        created_at=now, expires_at=question.expires_at,
                    ))
                    await db.flush()


async def test_v4_clarification_is_source_free_and_cannot_follow_remote_work(
    postgres_engine, postgres_session_factory, monkeypatch, v4_fixture_users,
):
    job_id, _old_id, _question_id, _chunk_id = await _v4_job(
        postgres_engine, postgres_session_factory, monkeypatch, v4_fixture_users,
    )
    await _running(postgres_session_factory, job_id)
    async with postgres_session_factory() as db:
        async with db.begin():
            job = await db.get(RagAnswerJob, job_id, with_for_update=True)
            assert job is not None
            job.status = "completed"
            job.result_kind = "clarification_needed"
            job.completed_at = utcnow()
            job.worker_id = None
            job.claim_token = None
            job.heartbeat_at = None
            job.lease_expires_at = None
            # _running deliberately records an embedding boundary timestamp;
            # the DB cares whether an actual stage was attempted, not a clock.
            await db.flush()
    job_id_2, _old_id, _question_id, _chunk_id = await _v4_job(
        postgres_engine, postgres_session_factory, monkeypatch, v4_fixture_users,
    )
    await _running(postgres_session_factory, job_id_2)
    async with postgres_session_factory() as db:
        async with db.begin():
            db.add(_stage(job_id_2, "query_embedding", calls=1))
            await db.flush()
            job = await db.get(RagAnswerJob, job_id_2, with_for_update=True)
            assert job is not None
            with pytest.raises(DBAPIError):
                async with db.begin_nested():
                    job.status = "completed"
                    job.result_kind = "clarification_needed"
                    job.completed_at = utcnow()
                    job.worker_id = None
                    job.claim_token = None
                    job.heartbeat_at = None
                    job.lease_expires_at = None
                    await db.flush()
