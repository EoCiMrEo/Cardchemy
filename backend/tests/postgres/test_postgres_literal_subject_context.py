"""Disposable PostgreSQL enactment of immutable v7 literal admission context.

All messages below are invented test content. No provider, retained database,
operator configuration, private lecture, or actual source judgment is used.
"""
from datetime import timedelta
import hashlib
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.source_judgment_visual_v3 import (
    AdmissionUserMessage, SubjectAdmissionSnapshot, admission_identity,
)
from app.ai import source_judgment_visual_v3 as v7_contract
from app.ai.source_navigation_context_v1 import resolve_subject_context
from app.database import Base
from app.models.rag import RagAnswerJob, RagAnswerStageAttempt, RagMessage, RagThread
from app.models.subject import Subject
from app.models.user import AuthSession, User, UserRole
from app.time_utils import utcnow


pytestmark = pytest.mark.postgres
CONTEXT_TABLE = "rag_answer_question_context"
V7 = "related_knowledge_navigation_v7"


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@pytest_asyncio.fixture
async def context_db(postgres_engine):
    """Rollback every invented row, including successful DDL-guard exercises."""
    async with postgres_engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(bind=connection, expire_on_commit=False) as db:
            now = utcnow() - timedelta(seconds=1)
            owner = User(id=uuid4(), email=f"context-{uuid4().hex}@example.test",
                         hashed_password="fixture", role=UserRole.INSTRUCTOR)
            db.add(owner)
            await db.flush()
            subject = Subject(id=uuid4(), name="Literal context fixture", instructor_id=owner.id)
            db.add(subject)
            await db.flush()
            auth = AuthSession(id=uuid4(), user_id=owner.id, refresh_jti_hash=uuid4().hex * 2,
                               expires_at=now + timedelta(hours=2))
            thread = RagThread(id=uuid4(), user_id=owner.id, subject_id=subject.id,
                               created_at=now - timedelta(hours=1), updated_at=now)
            db.add_all((auth, thread))
            await db.flush()
            yield db, {"owner": owner, "subject": subject, "auth": auth, "thread": thread, "now": now}
        if transaction.is_active:
            await transaction.rollback()


async def add_question(db, scope, *, content="I am reading about Vector Models.",
                       created_at=None, expires_at=None, thread_id=None):
    created = created_at or scope["now"] - timedelta(minutes=5)
    question = RagMessage(id=uuid4(), thread_id=thread_id or scope["thread"].id,
                          user_id=scope["owner"].id, subject_id=scope["subject"].id,
                          role="user", content=content, source_count=0,
                          created_at=created, expires_at=expires_at or created + timedelta(days=1))
    db.add(question)
    await db.flush()
    return question


def message_snapshot(message, *, contract=v7_contract):
    return contract.AdmissionUserMessage(message_id=message.id, user_id=message.user_id,
                                thread_id=message.thread_id, subject_id=message.subject_id,
                                content_sha256=digest(message.content), created_at=message.created_at,
                                expires_at=message.expires_at)


async def add_job(db, scope, *, previous=None, raw_clear=False, bind=True,
                  context_overrides=None, profile_overrides=None,
                  contract=v7_contract, policy=V7):
    current = await add_question(db, scope, content="What does it stand for?" if not raw_clear
                                 else "What is a Vector Model?", created_at=scope["now"])
    snapshot = contract.SubjectAdmissionSnapshot(current=message_snapshot(current, contract=contract),
        preceding=message_snapshot(previous, contract=contract) if previous is not None else None,
        corpus_revision=0, embedding_space_hash="a" * 64, captured_at=current.created_at,
        raw_question_clear=raw_clear)
    admission_sha = contract.admission_identity(snapshot, checked_at=utcnow())
    values = dict(id=uuid4(), thread_id=current.thread_id, question_message_id=current.id,
        auth_session_id=scope["auth"].id, user_id=current.user_id, subject_id=current.subject_id,
        status="queued", operation_key_hash=uuid4().hex * 2, request_fingerprint=uuid4().hex * 2,
        document_ids=[], corpus_revision=0, retrieval_policy="hybrid_source_navigation_v9",
        embedding_space_hash="a" * 64, embedding_provider="gemini",
        embedding_base_url="https://generativelanguage.googleapis.com", embedding_model="gemini-embedding-001",
        source_judge_provider="gemini", source_judge_base_url="https://generativelanguage.googleapis.com",
        source_judge_model="gemini-3.5-flash-lite", source_judge_contract_version=contract.CONTRACT_VERSION,
        source_judge_input_price_microusd_per_million=300000,
        source_judge_output_price_microusd_per_million=2500000,
        source_judge_max_input_tokens=32768, source_judge_max_output_tokens=4096,
        source_judge_thinking_level="high", source_judge_timeout_seconds=120,
        source_context_policy_version=contract.ADMISSION_SCHEMA,
        source_context_admission_sha256=admission_sha, answer_policy_version=policy,
        max_attempts=3, available_at=scope["now"], deadline_at=scope["now"] + timedelta(hours=1),
        created_at=scope["now"], updated_at=scope["now"])
    values.update(profile_overrides or {})
    job = RagAnswerJob(**values)
    db.add(job)
    await db.flush()
    row = dict(job_id=job.id, thread_id=current.thread_id, user_id=current.user_id,
        subject_id=current.subject_id, current_message_id=current.id,
        context_version=contract.ADMISSION_SCHEMA, raw_question_clear=raw_clear,
        current_question_sha256=digest(current.content), current_created_at=current.created_at,
        current_expires_at=current.expires_at, captured_at=current.created_at, admission_sha256=admission_sha,
        preceding_message_id=None, preceding_question_sha256=None, preceding_created_at=None,
        preceding_expires_at=None, subject_start_offset=None, subject_end_offset=None,
        subject_start_byte_offset=None, subject_end_byte_offset=None, subject_sha256=None)
    if previous is not None:
        anchor = resolve_subject_context(current.content, (("user", previous.content),), raw_navigation_query=None).anchor
        row.update(preceding_message_id=previous.id, preceding_question_sha256=digest(previous.content),
                   preceding_created_at=previous.created_at, preceding_expires_at=previous.expires_at)
        if anchor is not None:
            row.update(subject_start_offset=anchor.start_offset, subject_end_offset=anchor.end_offset,
                       subject_start_byte_offset=anchor.start_byte_offset,
                       subject_end_byte_offset=anchor.end_byte_offset, subject_sha256=anchor.subject_sha256)
    row.update(context_overrides or {})
    if bind:
        await db.execute(insert(Base.metadata.tables[CONTEXT_TABLE]).values(row))
    return job, current, row


async def check_admission(db):
    await db.execute(text("SET CONSTRAINTS trg_rag_question_context_admission IMMEDIATE"))


async def test_deferred_context_is_mandatory_at_transaction_boundary(context_db):
    db, scope = context_db
    with pytest.raises(DBAPIError):
        async with db.begin_nested():
            await add_job(db, scope, raw_clear=True, bind=False)
            # INSERT itself succeeded. The deferred enqueue guard fires here.
            await check_admission(db)
    job, current, _row = await add_job(db, scope, raw_clear=True)
    await check_admission(db)
    assert await db.scalar(select(RagAnswerJob.id).where(RagAnswerJob.id == job.id)) == job.id
    assert current.role == "user"


async def test_deleting_predecessor_removes_only_binding_and_preserves_new_job(context_db):
    db, scope = context_db
    previous = await add_question(db, scope)
    job, current, _row = await add_job(db, scope, previous=previous)
    await check_admission(db)
    await db.execute(delete(RagMessage).where(RagMessage.id == previous.id))
    assert await db.scalar(select(RagAnswerJob.id).where(RagAnswerJob.id == job.id)) == job.id
    assert await db.scalar(select(RagMessage.id).where(RagMessage.id == current.id)) == current.id
    assert await db.scalar(select(Base.metadata.tables[CONTEXT_TABLE].c.job_id).where(
        Base.metadata.tables[CONTEXT_TABLE].c.job_id == job.id)) is None
    # The INSERT-only deferred guard is not re-fired during retention cleanup.
    await check_admission(db)


async def test_current_question_deletion_cascades_own_job_and_binding(context_db):
    db, scope = context_db
    job, current, _row = await add_job(db, scope, raw_clear=True)
    await check_admission(db)
    await db.execute(delete(RagMessage).where(RagMessage.id == current.id))
    assert await db.scalar(select(RagAnswerJob.id).where(RagAnswerJob.id == job.id)) is None
    assert await db.scalar(select(Base.metadata.tables[CONTEXT_TABLE].c.job_id).where(
        Base.metadata.tables[CONTEXT_TABLE].c.job_id == job.id)) is None


@pytest.mark.parametrize("field", ["user_id", "thread_id", "subject_id", "current_message_id"])
async def test_context_scope_is_bound_to_parent_and_messages(context_db, field):
    db, scope = context_db
    previous = await add_question(db, scope)
    with pytest.raises(DBAPIError):
        async with db.begin_nested():
            await add_job(db, scope, previous=previous, context_overrides={field: uuid4()})


@pytest.mark.parametrize("field,value", [
    ("admission_sha256", "b" * 64), ("current_question_sha256", "b" * 64),
    ("preceding_question_sha256", "b" * 64), ("subject_sha256", "b" * 64),
    ("subject_start_offset", 0), ("subject_start_byte_offset", 0),
    ("subject_end_byte_offset", 100),
])
async def test_literal_binding_rejects_hash_offset_or_parent_tampering(context_db, field, value):
    db, scope = context_db
    previous = await add_question(db, scope)
    with pytest.raises(DBAPIError):
        async with db.begin_nested():
            await add_job(db, scope, previous=previous, context_overrides={field: value})


async def test_multibyte_literal_offsets_are_verified_by_actual_postgres(context_db):
    db, scope = context_db
    previous = await add_question(db, scope, content="I am reading about Café Models.")
    job, _current, row = await add_job(db, scope, previous=previous)
    assert row["subject_end_byte_offset"] > row["subject_end_offset"]
    await check_admission(db)
    assert await db.scalar(select(Base.metadata.tables[CONTEXT_TABLE].c.job_id).where(
        Base.metadata.tables[CONTEXT_TABLE].c.job_id == job.id)) == job.id


async def test_context_and_job_admission_metadata_cannot_be_updated(context_db):
    db, scope = context_db
    job, _current, row = await add_job(db, scope, raw_clear=True)
    await check_admission(db)
    table = Base.metadata.tables[CONTEXT_TABLE]
    with pytest.raises(DBAPIError):
        async with db.begin_nested():
            await db.execute(update(table).where(table.c.job_id == job.id).values(admission_sha256="b" * 64))
    for changes in ({"source_context_admission_sha256": "b" * 64},
                    {"source_context_policy_version": "other"},
                    {"source_judge_timeout_seconds": 119}):
        with pytest.raises(DBAPIError):
            async with db.begin_nested():
                await db.execute(update(RagAnswerJob).where(RagAnswerJob.id == job.id).values(**changes))
    # An exact no-op update is harmless and allowed.
    await db.execute(update(table).where(table.c.job_id == job.id).values(admission_sha256=row["admission_sha256"]))


async def test_strict_latest_user_is_not_replaced_by_older_after_unsafe_turn(context_db):
    db, scope = context_db
    older = await add_question(db, scope, created_at=scope["now"] - timedelta(minutes=10))
    latest = await add_question(db, scope, content="Compare Vector Models and Matrix Models.")
    with pytest.raises(DBAPIError):
        async with db.begin_nested():
            await add_job(db, scope, previous=older)
    # Preserve the unsafe latest turn as conservative clarification, without a
    # previous subject. An older unambiguous topic is never used instead.
    job, _current, row = await add_job(db, scope)
    await check_admission(db)
    assert row["preceding_message_id"] is None and latest.id != older.id
    assert await db.scalar(select(Base.metadata.tables[CONTEXT_TABLE].c.raw_question_clear).where(
        Base.metadata.tables[CONTEXT_TABLE].c.job_id == job.id)) is False


async def test_expired_latest_user_cannot_make_older_user_eligible(context_db):
    db, scope = context_db
    older = await add_question(db, scope, created_at=scope["now"] - timedelta(minutes=10))
    await add_question(db, scope, created_at=scope["now"] - timedelta(minutes=5),
                       expires_at=scope["now"] - timedelta(minutes=1))
    with pytest.raises(DBAPIError):
        async with db.begin_nested():
            await add_job(db, scope, previous=older)
    await add_job(db, scope)
    await check_admission(db)


async def test_future_queued_user_and_equal_timestamp_peer_cannot_supply_context(context_db):
    db, scope = context_db
    previous = await add_question(db, scope)
    await add_question(db, scope, content="I am reading about Matrix Models.",
                       created_at=scope["now"] + timedelta(seconds=1))
    await add_question(db, scope, content="I am reading about Scalar Models.", created_at=scope["now"])
    job, _current, row = await add_job(db, scope, previous=previous)
    await check_admission(db)
    assert row["preceding_message_id"] == previous.id
    assert await db.scalar(select(Base.metadata.tables[CONTEXT_TABLE].c.job_id).where(
        Base.metadata.tables[CONTEXT_TABLE].c.job_id == job.id)) == job.id


@pytest.mark.parametrize("changes", [
    {"source_judge_timeout_seconds": 120.1}, {"source_judge_contract_version": "visual_source_id_v2"},
    {"source_judge_max_output_tokens": 4097}, {"source_judge_max_input_tokens": 32769},
    {"ai_model": "an-answer-model"}, {"source_context_policy_version": None},
])
async def test_v7_profile_deadline_and_source_only_caps_are_actual_checks(context_db, changes):
    db, scope = context_db
    with pytest.raises(DBAPIError):
        async with db.begin_nested():
            await add_job(db, scope, raw_clear=True, profile_overrides=changes)


async def test_v7_stage_rows_allow_one_embedding_one_judge_zero_answer_and_no_retry(context_db):
    db, scope = context_db
    job, _current, _row = await add_job(db, scope, raw_clear=True)
    await check_admission(db)
    now = utcnow()
    job.status, job.attempt_count = "running", 1
    job.worker_id, job.claim_token = "context-test", uuid4().hex * 2
    job.heartbeat_at, job.lease_expires_at = now, now + timedelta(minutes=5)
    await db.flush()
    for stage in ("query_embedding", "source_judgment"):
        db.add(RagAnswerStageAttempt(job_id=job.id, manual_retry_number=0, worker_attempt_number=1,
            stage=stage, answer_policy_version=V7, physical_request_count=1, retry_count=0))
    await db.flush()
    for changes in (
        {"stage": "query_embedding"}, {"stage": "source_judgment"},
        {"stage": "query_embedding", "physical_request_count": 2},
        {"stage": "source_judgment", "physical_request_count": 2},
        {"stage": "source_judgment", "physical_request_count": 1, "retry_count": 1},
        {"stage": "answer"}, {"stage": "local_support"},
        {"stage": "retrieval", "physical_request_count": 1},
        {"stage": "retrieval", "physical_request_count": 2},
        {"stage": "retrieval", "retry_count": 1},
        {"stage": "retrieval", "answer_policy_version": None},
    ):
        with pytest.raises(DBAPIError):
            async with db.begin_nested():
                values = dict(job_id=job.id, manual_retry_number=0, worker_attempt_number=1,
                    stage="retrieval", answer_policy_version=V7, physical_request_count=0, retry_count=0)
                values.update(changes)
                db.add(RagAnswerStageAttempt(**values))
                await db.flush()
