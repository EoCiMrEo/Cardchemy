"""Additive 0033 constraints and guarded round-trip using invented rows only."""
import sqlite3

import pytest

from tests.test_visual_source_judgment_policy_migration import load
from tests.test_literal_subject_context_migration import current as previous, definitions as before_v7, insert, job_sample, context_sample
from app.models.rag import RagAnswerJob, RagAnswerStageAttempt, RagAnswerQuestionContext
from tests.test_visual_source_judgment_policy_migration import checks


def current():
    return load("20261002_0033_visual_clarity_policy.py")


def test_additive_v8_chain_matches_current_orm_and_preserves_installed_v7_checks():
    new, old = current(), previous()
    assert new.down_revision == old.revision
    for before, after in (("OLD_IDENTITY", "NEW_IDENTITY"), ("OLD_RESULT", "NEW_RESULT"),
                          ("OLD_JUDGE_SNAPSHOT", "JUDGE_SNAPSHOT"),
                          ("OLD_RETRIEVAL_PAIR", "NEW_RETRIEVAL_PAIR"),
                          ("OLD_JOB_CONTEXT_CHECK", "JOB_CONTEXT_CHECK"),
                          ("OLD_CONTEXT_SHAPE_CHECK", "CONTEXT_SHAPE_CHECK"),
                          ("OLD_STAGE_POLICY", "NEW_STAGE_POLICY"),
                          ("OLD_VISUAL_STAGE_CAP", "VISUAL_STAGE_CAP")):
        assert getattr(new, before) == getattr(old, after)
    for model, name, expected in (
        (RagAnswerJob, "ck_rag_answer_jobs_identity", new.NEW_IDENTITY),
        (RagAnswerJob, "ck_rag_answer_jobs_result", new.NEW_RESULT),
        (RagAnswerJob, "ck_rag_answer_jobs_source_judge_snapshot", new.JUDGE_SNAPSHOT),
        (RagAnswerJob, "ck_rag_answer_jobs_source_judge_retrieval_pair", new.NEW_RETRIEVAL_PAIR),
        (RagAnswerJob, "ck_rag_answer_jobs_source_context_snapshot", new.JOB_CONTEXT_CHECK),
        (RagAnswerQuestionContext, "ck_rag_question_context_shape", new.CONTEXT_SHAPE_CHECK),
        (RagAnswerStageAttempt, "ck_rag_answer_stage_source_judgment_policy", new.NEW_STAGE_POLICY),
        (RagAnswerStageAttempt, "ck_rag_answer_stage_visual_judge_cap", new.VISUAL_STAGE_CAP),
    ):
        assert checks(model)[name] == expected


def sample(policy="related_knowledge_navigation_v8"):
    row = job_sample("related_knowledge_navigation_v7")
    row.update(answer_policy_version=policy)
    if policy == "related_knowledge_navigation_v8":
        row.update(source_judge_contract_version="visual_source_id_v5",
                   source_context_policy_version="literal_subject_admission_v2")
    return row


def insert_job(row):
    m = current()
    insert(row, (m.NEW_IDENTITY, m.NEW_RESULT, m.JUDGE_SNAPSHOT, m.NEW_RETRIEVAL_PAIR, m.JOB_CONTEXT_CHECK))


@pytest.mark.parametrize("policy", ["related_knowledge_navigation_v7", "related_knowledge_navigation_v8"])
def test_genuine_old_and_new_job_pairs_remain_accepted(policy):
    insert_job(sample(policy))


@pytest.mark.parametrize(("field", "value"), [
    ("source_judge_contract_version", "visual_source_id_v3"),
    ("source_judge_contract_version", "visual_source_id_v4"),
    ("source_context_policy_version", "literal_subject_admission_v1"),
    ("source_context_policy_version", None),
    ("source_context_admission_sha256", "A" * 64),
    ("source_judge_timeout_seconds", 121),
    ("source_judge_max_output_tokens", 4097),
    ("source_judge_max_input_tokens", 32769),
    ("source_judge_model", "another-model"),
    ("source_judge_thinking_level", "low"),
    ("retrieval_policy", "hybrid_source_navigation_v8"),
    ("ai_model", "answer-model"),
])
def test_v8_wrong_contract_context_budget_and_answer_profile_are_rejected(field, value):
    row=sample(); row[field]=value
    with pytest.raises(sqlite3.IntegrityError): insert_job(row)


@pytest.mark.parametrize(("field", "value"), [
    ("source_judge_contract_version", "visual_source_id_v5"),
    ("source_context_policy_version", "literal_subject_admission_v2"),
])
def test_old_v7_is_not_reinterpreted_under_new_context_or_parser(field, value):
    row=sample("related_knowledge_navigation_v7"); row[field]=value
    with pytest.raises(sqlite3.IntegrityError): insert_job(row)


@pytest.mark.parametrize("version", ["literal_subject_admission_v1", "literal_subject_admission_v2"])
def test_old_and_new_context_shapes_keep_same_literal_bounds(version):
    row=context_sample(); row["context_version"]=version
    insert(row,(current().CONTEXT_SHAPE_CHECK,))
    row["subject_end_offset"]=row["subject_start_offset"]+161
    with pytest.raises(sqlite3.IntegrityError): insert(row,(current().CONTEXT_SHAPE_CHECK,))


def definitions():
    state=before_v7(); old=previous()
    for name,before,after in old._patches():
        assert state[name].count(before)==1
        state[name]=state[name].replace(before,after)
    name="enforce_rag_source_stage_parent_policy()"
    assert state[name].count(old.OLD_POLICIES)==2
    state[name]=state[name].replace(old.OLD_POLICIES,old.NEW_POLICIES)
    state["rag_answer_question_context_guard()"]=old._context_guard_sql()
    state["enforce_rag_question_context_admission()"]=old.CONTEXT_ADMISSION_GUARD
    return state


def test_sql_guard_patch_preserves_every_v7_definition_and_round_trips(monkeypatch):
    m=current(); original=definitions(); state=dict(original)
    class Bind:
        def scalar(self, statement): return state[statement.compile().params["name"]]
    monkeypatch.setattr(m.op,"get_bind",lambda:Bind())
    def execute(statement):
        definition=str(statement)
        name=next(name for name in state if name.split("(")[0] in definition)
        state[name]=definition
    monkeypatch.setattr(m.op,"execute",execute)
    for name,before,after in m._patches(): m._replace_function(name,before,after)
    m._patch_parent()
    assert "related_knowledge_navigation_v8" in state["rag_answer_job_guard()"]
    assert "related_knowledge_navigation_v7" in state["rag_answer_job_guard()"]
    assert "NEW.source_context_policy_version" in state["rag_answer_job_guard()"]
    m._patch_parent(reverse=True)
    for name,before,after in reversed(m._patches()): m._replace_function(name,after,before,reverse=True)
    assert state==original


def test_downgrade_refuses_v8_before_ddl_or_old_snapshot_change(monkeypatch):
    m=current()
    class Bind:
        def scalar(self,statement):
            assert m.V8 in str(statement)
            return 1
    monkeypatch.setattr(m.op,"get_bind",lambda:Bind())
    monkeypatch.setattr(m.op,"execute",lambda *_:pytest.fail("DDL before preservation guard"))
    with pytest.raises(RuntimeError,match="v8 clarity/visual job snapshots"): m.downgrade()
