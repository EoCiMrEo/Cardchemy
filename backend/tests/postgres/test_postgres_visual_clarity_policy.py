"""Disposable 0033 v8 enactment; historical v7 context coverage remains intact."""
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
import pytest

from app.ai import source_judgment_visual_v5 as contract
from app.models.rag import RagAnswerJob
from app.services.rag_question_context_v2 import rehydrate_question_context
from app.time_utils import utcnow
from tests.postgres.test_postgres_literal_subject_context import (
    add_job, add_question, check_admission, context_db,
)

pytestmark = pytest.mark.postgres
POLICY = "related_knowledge_navigation_v8"


async def test_v8_deferred_context_is_mandatory_and_genuine_v7_still_accepted(context_db):
    db, scope = context_db
    with pytest.raises(DBAPIError):
        async with db.begin_nested():
            await add_job(db, scope, raw_clear=True, bind=False, contract=contract, policy=POLICY)
            await check_admission(db)
    new, _, _ = await add_job(db, scope, raw_clear=True, contract=contract, policy=POLICY)
    old, _, _ = await add_job(db, scope, raw_clear=True)
    await check_admission(db)
    assert await db.scalar(select(RagAnswerJob.id).where(RagAnswerJob.id == new.id)) == new.id
    assert await db.scalar(select(RagAnswerJob.id).where(RagAnswerJob.id == old.id)) == old.id
    hydrated = await rehydrate_question_context(db, job=new, checked_at=utcnow())
    assert hydrated.binding.contract_version == contract.CONTRACT_VERSION
    assert hydrated.snapshot.schema_version == contract.ADMISSION_SCHEMA
    assert hydrated.snapshot.preceding is None and not hydrated.needs_clarification


async def test_v8_literal_predecessor_round_trip_keeps_v1_grammar_and_offsets(context_db):
    db, scope = context_db
    previous = await add_question(db, scope, content="Explain Vector Models.")
    new, _, _ = await add_job(db, scope, previous=previous, contract=contract, policy=POLICY)
    await check_admission(db)
    hydrated = await rehydrate_question_context(db, job=new, checked_at=utcnow())
    assert hydrated.binding.anchor.subject == "Vector Models"
    assert hydrated.binding.anchor.policy_id == "literal_subject_anchor_v1"
    assert hydrated.local_query == "What does it stand for? Vector Models"


@pytest.mark.parametrize("overrides", [
    {"source_judge_contract_version": "visual_source_id_v3"},
    {"source_context_policy_version": "literal_subject_admission_v1"},
    {"source_context_policy_version": None},
    {"source_judge_timeout_seconds": 121},
    {"source_judge_max_output_tokens": 4097},
    {"ai_model": "retired-answer"},
])
async def test_v8_wrong_profile_rejected_before_admission(context_db, overrides):
    db, scope = context_db
    with pytest.raises(DBAPIError):
        async with db.begin_nested():
            await add_job(db, scope, raw_clear=True, contract=contract, policy=POLICY,
                          profile_overrides=overrides)


async def test_v8_context_cannot_be_substituted_with_v7_row(context_db):
    db, scope = context_db
    with pytest.raises(DBAPIError):
        async with db.begin_nested():
            await add_job(db, scope, raw_clear=True, contract=contract, policy=POLICY,
                          context_overrides={"context_version": "literal_subject_admission_v1"})
