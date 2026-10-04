"""Independent disposable PostgreSQL negatives for the v8/v5/0033 boundary.

Invented data only; no Settings(), operator credentials, provider transport,
retained database, or private source is used. Existing v7 helper defaults and
implementation-owned positive tests remain unchanged.
"""
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.exc import DBAPIError

from app.ai import source_judgment_visual_v5 as contract
from app.database import Base
from app.models.rag import RagAnswerJob, RagAnswerStageAttempt, RagMessage
from app.services.rag_question_context_v2 import (
    QuestionContextUnavailable,
    rehydrate_question_context,
)
from app.time_utils import utcnow
from tests.postgres.test_postgres_literal_subject_context import (
    CONTEXT_TABLE,
    add_job,
    add_question,
    check_admission,
    context_db,
)

pytestmark = pytest.mark.postgres
POLICY = "related_knowledge_navigation_v8"


@pytest.mark.parametrize("field", [
    "source_judge_provider", "source_judge_base_url", "source_judge_model",
    "source_judge_contract_version", "source_judge_input_price_microusd_per_million",
    "source_judge_output_price_microusd_per_million", "source_judge_max_input_tokens",
    "source_judge_max_output_tokens", "source_judge_thinking_level",
    "source_judge_timeout_seconds", "source_context_admission_sha256",
])
async def test_v8_source_snapshot_null_cannot_pass_sql_unknown(context_db, field):
    db, scope = context_db
    with pytest.raises(DBAPIError):
        async with db.begin_nested():
            await add_job(db, scope, raw_clear=True, contract=contract, policy=POLICY,
                          profile_overrides={field: None})


@pytest.mark.parametrize("changes", [
    {"retrieval_policy": "hybrid_source_navigation_v8"},
    {"source_judge_provider": "other"},
    {"source_judge_base_url": "https://example.test"},
    {"source_judge_model": "different-model"},
    {"source_judge_input_price_microusd_per_million": 299999},
    {"source_judge_output_price_microusd_per_million": 2499999},
    {"source_judge_max_input_tokens": 32769},
    {"source_judge_thinking_level": "low"},
    {"source_context_admission_sha256": "A" * 64},
    {"ai_provider": "gemini"},
    {"ai_base_url": "https://generativelanguage.googleapis.com"},
    {"support_policy_version": "local-support"},
    {"ai_catalog_version": "retired-answer-catalog"},
    {"ai_schema_policy_version": "retired-answer-schema"},
])
async def test_v8_exact_source_only_profile_cannot_be_reinterpreted(context_db, changes):
    db, scope = context_db
    with pytest.raises(DBAPIError):
        async with db.begin_nested():
            await add_job(db, scope, raw_clear=True, contract=contract, policy=POLICY,
                          profile_overrides=changes)


async def test_v8_contract_cannot_be_stored_under_historical_v7_policy(context_db):
    db, scope = context_db
    with pytest.raises(DBAPIError):
        async with db.begin_nested():
            await add_job(db, scope, raw_clear=True, contract=contract)
    old, _, _ = await add_job(db, scope, raw_clear=True)
    await check_admission(db)
    with pytest.raises(QuestionContextUnavailable, match="^question_context_unavailable$"):
        await rehydrate_question_context(db, job=old, checked_at=utcnow())
    assert old.answer_policy_version == "related_knowledge_navigation_v7"
    assert old.source_context_policy_version == "literal_subject_admission_v1"


async def test_v8_existing_wrong_current_message_cannot_supply_context(context_db):
    db, scope = context_db
    other = await add_question(db, scope, content="Explain Matrix Models.")
    with pytest.raises(DBAPIError):
        async with db.begin_nested():
            await add_job(db, scope, raw_clear=True, contract=contract, policy=POLICY,
                          context_overrides={"current_message_id": other.id})


@pytest.mark.parametrize("field,value", [
    ("user_id", None), ("thread_id", None), ("subject_id", None),
    ("admission_sha256", "b" * 64), ("current_question_sha256", "b" * 64),
    ("preceding_question_sha256", "b" * 64), ("subject_sha256", "b" * 64),
    ("subject_start_offset", 0), ("subject_start_byte_offset", 0),
    ("subject_end_byte_offset", 100),
])
async def test_v8_parent_and_literal_anchor_tampering_are_rejected(context_db, field, value):
    db, scope = context_db
    previous = await add_question(db, scope, content="Explain Vector Models.")
    with pytest.raises(DBAPIError):
        async with db.begin_nested():
            await add_job(db, scope, previous=previous, contract=contract, policy=POLICY,
                          context_overrides={field: uuid4() if value is None else value})


async def test_v8_job_and_context_updates_cannot_change_admitted_pair(context_db):
    db, scope = context_db
    previous = await add_question(db, scope, content="Explain Vector Models.")
    job, _, row = await add_job(db, scope, previous=previous, contract=contract, policy=POLICY)
    await check_admission(db)
    table = Base.metadata.tables[CONTEXT_TABLE]
    for changes in (
        {"context_version": "literal_subject_admission_v1"},
        {"subject_sha256": "b" * 64}, {"subject_start_offset": 0},
        {"current_question_sha256": "b" * 64},
    ):
        with pytest.raises(DBAPIError):
            async with db.begin_nested():
                await db.execute(update(table).where(table.c.job_id == job.id).values(**changes))
    for changes in (
        {"answer_policy_version": "related_knowledge_navigation_v7"},
        {"source_judge_contract_version": "visual_source_id_v3"},
        {"source_context_policy_version": "literal_subject_admission_v1"},
        {"source_context_admission_sha256": "b" * 64},
        {"retrieval_policy": "hybrid_source_navigation_v8"},
    ):
        with pytest.raises(DBAPIError):
            async with db.begin_nested():
                await db.execute(update(RagAnswerJob).where(RagAnswerJob.id == job.id).values(**changes))
    await db.execute(update(table).where(table.c.job_id == job.id)
                     .values(admission_sha256=row["admission_sha256"]))
    hydrated = await rehydrate_question_context(db, job=job, checked_at=utcnow())
    assert hydrated.binding.anchor.subject == "Vector Models"


@pytest.mark.parametrize("target,field", [
    ("current", "content"), ("current", "expires_at"),
    ("preceding", "content"), ("preceding", "expires_at"),
])
async def test_v8_rehydration_rejects_current_or_preceding_message_change(context_db, target, field):
    db, scope = context_db
    previous = await add_question(db, scope, content="Explain Vector Models.")
    job, current, _ = await add_job(db, scope, previous=previous, contract=contract, policy=POLICY)
    await check_admission(db)
    message = current if target == "current" else previous
    replacement = "Explain Matrix Models." if field == "content" else utcnow() + timedelta(hours=1)
    await db.execute(update(RagMessage).where(RagMessage.id == message.id).values(**{field: replacement}))
    with pytest.raises(QuestionContextUnavailable, match="^question_context_unavailable$"):
        await rehydrate_question_context(db, job=job, checked_at=utcnow())


async def test_v8_deleted_predecessor_does_not_rebind_or_delete_historical_job(context_db):
    db, scope = context_db
    previous = await add_question(db, scope, content="Explain Vector Models.")
    job, _, _ = await add_job(db, scope, previous=previous, contract=contract, policy=POLICY)
    await check_admission(db)
    await db.execute(delete(RagMessage).where(RagMessage.id == previous.id))
    assert await db.scalar(select(RagAnswerJob.id).where(RagAnswerJob.id == job.id)) == job.id
    with pytest.raises(QuestionContextUnavailable, match="^question_context_unavailable$"):
        await rehydrate_question_context(db, job=job, checked_at=utcnow())
    await check_admission(db)


async def _running_v8(db, scope):
    job, _, _ = await add_job(db, scope, raw_clear=True, contract=contract, policy=POLICY)
    await check_admission(db)
    now = utcnow()
    job.status, job.attempt_count = "running", 1
    job.worker_id, job.claim_token = "synthetic-v8-worker", "a" * 64
    job.heartbeat_at, job.lease_expires_at = now, now + timedelta(minutes=5)
    await db.flush()
    return job


@pytest.mark.parametrize("changes", [
    {"stage": "query_embedding", "physical_request_count": 2},
    {"stage": "source_judgment", "physical_request_count": 2},
    {"stage": "source_judgment", "retry_count": 1},
    {"stage": "answer"}, {"stage": "support"}, {"stage": "local_support"},
    {"stage": "retrieval", "physical_request_count": 1},
    {"answer_policy_version": None},
    {"answer_policy_version": "related_knowledge_navigation_v7"},
])
async def test_v8_physical_stage_parent_and_zero_retry_caps(context_db, changes):
    db, scope = context_db
    job = await _running_v8(db, scope)
    with pytest.raises(DBAPIError):
        async with db.begin_nested():
            values = dict(job_id=job.id, manual_retry_number=0, worker_attempt_number=1,
                          stage="source_judgment", answer_policy_version=POLICY,
                          physical_request_count=1, retry_count=0)
            values.update(changes)
            db.add(RagAnswerStageAttempt(**values))
            await db.flush()


@pytest.mark.parametrize("stage", ["query_embedding", "source_judgment"])
async def test_v8_new_worker_attempt_cannot_replay_remote_stage(context_db, stage):
    db, scope = context_db
    job = await _running_v8(db, scope)
    db.add(RagAnswerStageAttempt(job_id=job.id, manual_retry_number=0,
                                worker_attempt_number=1, stage=stage,
                                answer_policy_version=POLICY,
                                physical_request_count=1, retry_count=0))
    await db.flush()
    # Reclaim through the existing queued -> running transition; directly
    # rewriting a running attempt is correctly forbidden by the job guard.
    job.status = "queued"
    await db.flush()
    job.status = "running"
    job.attempt_count = 2
    await db.flush()
    with pytest.raises(DBAPIError):
        async with db.begin_nested():
            db.add(RagAnswerStageAttempt(job_id=job.id, manual_retry_number=0,
                                        worker_attempt_number=2, stage=stage,
                                        answer_policy_version=POLICY,
                                        physical_request_count=1, retry_count=0))
            await db.flush()
