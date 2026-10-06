"""Actual ORM/migration parity and SQL admission binding using invented data."""
from datetime import timedelta
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, event, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateTable

from app.database import Base
from app.models.rag import RagAnswerJob, RagAnswerQuestionContext, RagAnswerStageAttempt, RagMessage, RagThread
from app.models.subject import Subject
from app.models.user import AuthSession, User, UserRole
from app.services.rag_question_context import (
    QuestionContextUnavailable, capture_question_context, persist_question_context, rehydrate_question_context,
)
from app.ai.source_navigation import navigation_query_v4
from app.time_utils import utcnow


def _migration():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/20261002_0033_visual_clarity_policy.py"
    spec = importlib.util.spec_from_file_location("literal_context_model_parity", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _checks(model):
    return {constraint.name: str(constraint.sqltext)
            for constraint in model.__table__.constraints if isinstance(constraint, CheckConstraint)}


def test_exact_migration_constraints_and_policy_index_match_current_orm():
    m = _migration()
    jobs, stages, context = _checks(RagAnswerJob), _checks(RagAnswerStageAttempt), _checks(RagAnswerQuestionContext)
    for suffix, expected in (("identity", m.NEW_IDENTITY), ("result", m.NEW_RESULT),
                             ("source_judge_snapshot", m.JUDGE_SNAPSHOT),
                             ("source_judge_retrieval_pair", m.NEW_RETRIEVAL_PAIR),
                             ("source_context_snapshot", m.JOB_CONTEXT_CHECK)):
        assert jobs["ck_rag_answer_jobs_" + suffix] == expected
    assert stages["ck_rag_answer_stage_source_judgment_policy"] == m.NEW_STAGE_POLICY
    assert stages["ck_rag_answer_stage_visual_judge_cap"] == m.VISUAL_STAGE_CAP
    assert context["ck_rag_question_context_shape"] == m.CONTEXT_SHAPE_CHECK
    indexes = {index.name: index for index in RagAnswerStageAttempt.__table__.indexes}
    assert str(indexes["uq_rag_answer_stage_visual_remote_attempt"].dialect_options["postgresql"]["where"]) == m.NEW_VISUAL_INDEX
    assert tuple(RagAnswerQuestionContext.__table__.columns.keys()) == m.CONTEXT_COLUMNS
    assert set(RagAnswerJob.__table__.columns) >= {
        RagAnswerJob.__table__.columns.source_context_policy_version,
        RagAnswerJob.__table__.columns.source_context_admission_sha256,
    }


def test_context_keys_lifetime_and_column_types_match_additive_migration():
    m, table = _migration(), RagAnswerQuestionContext.__table__
    assert table.primary_key.name == "pk_rag_answer_question_context"
    assert tuple(table.primary_key.columns.keys()) == ("job_id",)
    expected = {
        "fk_rag_question_context_job_scope": ("job_id", "rag_answer_jobs"),
        "fk_rag_question_context_current_scope": ("current_message_id", "rag_messages"),
        "fk_rag_question_context_preceding_scope": ("preceding_message_id", "rag_messages"),
    }
    fks = {constraint.name: constraint for constraint in table.constraints
           if isinstance(constraint, ForeignKeyConstraint)}
    assert set(fks) == set(expected)
    for name, (key, target) in expected.items():
        assert tuple(fks[name].column_keys) == (key, "thread_id", "user_id", "subject_id")
        assert fks[name].ondelete == "CASCADE"
        assert [element.target_fullname for element in fks[name].elements] == [
            target + ".id", target + ".thread_id", target + ".user_id", target + ".subject_id",
        ]
    nullable = set(m.PRECEDING_COLUMNS + m.SUBJECT_COLUMNS)
    for name in m.CONTEXT_COLUMNS:
        assert table.columns[name].nullable == (name in nullable)
    assert [(index.name, tuple(index.columns.keys()), index.unique) for index in table.indexes] == [
        ("ix_rag_question_context_preceding", ("preceding_message_id", "job_id"), False),
    ]
    assert not {"question", "content", "subject", "preceding_question"}.intersection(table.columns.keys())


def test_postgres_ddl_keeps_exact_regex_checks_and_omits_sqlite_checks():
    for model in (RagAnswerJob, RagAnswerQuestionContext):
        pg = str(CreateTable(model.__table__).compile(dialect=postgresql.dialect()))
        lite = str(CreateTable(model.__table__).compile(dialect=sqlite.dialect()))
        assert " ~ '^[0-9a-f]{64}$'" in pg and "_snapshot_sqlite" not in pg and "_shape_sqlite" not in pg
        assert " ~ " not in lite and "replace(" in lite


@pytest.fixture
async def actual_context_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


async def _seed(db, *, current_text="What does it stand for?", prior_text="What is BERT?", expired_prior=False):
    now = utcnow()
    user = User(id=uuid4(), email=f"orm-context-{uuid4().hex}@example.test",
                hashed_password="invented", role=UserRole.INSTRUCTOR)
    db.add(user)
    await db.flush()
    subject = Subject(id=uuid4(), name="Invented source context", instructor_id=user.id, corpus_revision=7)
    session = AuthSession(id=uuid4(), user_id=user.id, refresh_jti_hash=uuid4().hex * 2,
                          expires_at=now + timedelta(days=1))
    db.add_all([subject, session])
    await db.flush()
    thread = RagThread(id=uuid4(), user_id=user.id, subject_id=subject.id,
                       created_at=now - timedelta(hours=1), updated_at=now)
    db.add(thread)
    await db.flush()
    prior = RagMessage(id=uuid4(), thread_id=thread.id, user_id=user.id, subject_id=subject.id,
                       role="user", outcome=None, source_count=0, content=prior_text,
                       created_at=now - timedelta(seconds=10),
                       expires_at=now - timedelta(seconds=1) if expired_prior else now + timedelta(days=1))
    db.add(prior)
    await db.flush()
    current = RagMessage(id=uuid4(), thread_id=thread.id, user_id=user.id, subject_id=subject.id,
                         role="user", outcome=None, source_count=0, content=current_text,
                         created_at=now, expires_at=now + timedelta(days=1))
    capture = await capture_question_context(
        db, current=current, thread=thread, corpus_revision=7,
        embedding_space_hash="c" * 64, captured_at=now,
        raw_navigation_query=navigation_query_v4(current.content, ()),
    )
    db.add(current)
    await db.flush()
    job = RagAnswerJob(
        id=uuid4(), thread_id=thread.id, question_message_id=current.id,
        auth_session_id=session.id, user_id=user.id, subject_id=subject.id,
        operation_key_hash=uuid4().hex * 2, request_fingerprint=uuid4().hex * 2,
        document_ids=[], corpus_revision=7, retrieval_policy="hybrid_source_navigation_v9",
        embedding_space_hash="c" * 64, embedding_provider="gemini",
        embedding_base_url="https://generativelanguage.googleapis.com", embedding_model="gemini-embedding-001",
        answer_policy_version="related_knowledge_navigation_v8",
        source_judge_provider="gemini", source_judge_base_url="https://generativelanguage.googleapis.com",
        source_judge_model="gemini-3.5-flash-lite", source_judge_contract_version="visual_source_id_v5",
        source_judge_input_price_microusd_per_million=300000,
        source_judge_output_price_microusd_per_million=2500000,
        source_judge_max_input_tokens=32768, source_judge_max_output_tokens=4096,
        source_judge_thinking_level="high", source_judge_timeout_seconds=120,
        status="queued", available_at=now, deadline_at=now + timedelta(seconds=300),
        created_at=now, updated_at=now,
    )
    db.add(job)
    binding = await persist_question_context(db, job=job, captured=capture)
    # Explicit parent flush keeps the transaction's SQL FK order inspectable.
    await db.flush([job])
    await db.flush()
    return now, prior, current, job, binding


@pytest.mark.parametrize("case", ["anchored", "clear", "expired_prior", "ambiguous_prior"])
async def test_production_models_and_default_helper_roundtrip(actual_context_db, case):
    db = actual_context_db
    values = {"current_text": "What does BERT stand for?"} if case == "clear" else (
        {"expired_prior": True} if case == "expired_prior" else (
            {"prior_text": "Explain BERT and BLEU"} if case == "ambiguous_prior" else {}))
    now, _prior, current, job, binding = await _seed(db, **values)
    assert isinstance(binding, RagAnswerQuestionContext)
    job_id, question_text = job.id, current.content
    await db.commit()
    db.expire_all()
    stored = await db.get(RagAnswerJob, job_id)
    hydrated = await rehydrate_question_context(db, job=stored, checked_at=now + timedelta(seconds=1))
    assert hydrated.question == question_text
    if case == "anchored":
        assert hydrated.binding.anchor.subject == "BERT" and not hydrated.needs_clarification
    elif case == "clear":
        assert hydrated.snapshot.preceding is None and hydrated.local_query == question_text
    else:
        assert hydrated.needs_clarification and hydrated.binding.anchor is None


async def test_prior_retention_delete_removes_binding_and_preserves_newer_job(actual_context_db):
    db = actual_context_db
    now, prior, _current, job, _binding = await _seed(db)
    job_id = job.id
    await db.commit()
    await db.delete(prior)
    await db.commit()
    db.expire_all()
    assert await db.get(RagAnswerQuestionContext, job_id) is None
    retained_job = await db.get(RagAnswerJob, job_id)
    assert retained_job is not None
    with pytest.raises(QuestionContextUnavailable):
        await rehydrate_question_context(db, job=retained_job, checked_at=now + timedelta(seconds=1))


@pytest.mark.parametrize("invalid", [None, "x" * 64, "A" * 64, "a" * 63, "a" * 65])
async def test_current_job_context_hash_portable_orm_constraint_rejects_invalid_hash(actual_context_db, invalid):
    db = actual_context_db
    _now, _prior, _current, job, _binding = await _seed(db)
    job.source_context_admission_sha256 = invalid
    with pytest.raises(IntegrityError):
        await db.flush()


@pytest.mark.parametrize("invalid", ["x" * 64, "A" * 64, "a" * 63, "a" * 65])
async def test_context_subject_hash_portable_orm_constraint_rejects_invalid_hash(actual_context_db, invalid):
    db = actual_context_db
    _now, _prior, _current, _job, binding = await _seed(db)
    binding.subject_sha256 = invalid
    with pytest.raises(IntegrityError):
        await db.flush()


@pytest.mark.parametrize("change,value", [
    ("source_judge_timeout_seconds", 121), ("source_judge_max_output_tokens", 4097),
    ("source_judge_contract_version", "visual_source_id_v2"),
    ("source_context_policy_version", "wrong-context-policy"),
])
async def test_current_production_job_rejects_budget_or_contract_reinterpretation(actual_context_db, change, value):
    db = actual_context_db
    _now, _prior, _current, job, _binding = await _seed(db)
    setattr(job, change, value)
    with pytest.raises(IntegrityError):
        await db.flush()


@pytest.mark.parametrize("change,value", [
    ("subject_start_offset", None), ("subject_end_offset", 1000),
    ("subject_start_byte_offset", -1), ("preceding_question_sha256", None),
    ("raw_question_clear", True), ("context_version", "wrong-context-policy"),
])
async def test_current_production_binding_rejects_partial_or_invalid_context_shape(actual_context_db, change, value):
    db = actual_context_db
    _now, _prior, _current, _job, binding = await _seed(db)
    setattr(binding, change, value)
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_production_context_cross_subject_fk_is_authoritative(actual_context_db):
    db = actual_context_db
    _now, _prior, _current, _job, binding = await _seed(db)
    binding.subject_id = uuid4()
    with pytest.raises(IntegrityError):
        await db.flush()
