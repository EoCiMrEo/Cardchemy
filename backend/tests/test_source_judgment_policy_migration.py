"""Keyless contracts for the prospective v4 source-judgment schema only."""

import importlib.util
from pathlib import Path

import pytest

from app.models.rag import RagAnswerJob, RagAnswerStageAttempt


def _load(filename):
    path = Path(__file__).resolve().parents[1] / "alembic/versions" / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_v4_migration_preserves_used_v3_contract_and_model_guards():
    prior = _load("20260927_0028_source_navigation_v3.py")
    current = _load("20260928_0029_source_judgment_policy.py")
    visual = _load("20261001_0030_visual_source_judgment.py")
    completion = _load("20261001_0031_visual_source_completion.py")
    context = _load("20261002_0032_literal_subject_context.py")
    assert current.down_revision == prior.revision
    assert current.OLD_IDENTITY == prior.NEW_IDENTITY
    assert current.OLD_RESULT == prior.NEW_RESULT
    assert current.OLD_POLICIES == prior.NEW_POLICIES
    assert current.OLD_REFERENCE_PAIR == prior.NEW_REFERENCE_PAIR
    assert current.OLD_JOB_CLAUSE == prior.NEW_JOB_CLAUSE
    assert current.NEW_IDENTITY != current.OLD_IDENTITY
    assert "clarification_needed" in current.NEW_RESULT
    assert "hybrid_source_navigation_v9" in current.NEW_REFERENCE_PAIR
    assert all(column in RagAnswerJob.__table__.columns for column in current.JUDGE_COLUMNS)
    job_checks = {item.name: str(item.sqltext) for item in RagAnswerJob.__table__.constraints
                  if item.name and item.name.startswith("ck_")}
    stage_checks = {item.name: str(item.sqltext) for item in RagAnswerStageAttempt.__table__.constraints
                    if item.name and item.name.startswith("ck_")}
    assert visual.OLD_IDENTITY == current.NEW_IDENTITY
    assert visual.OLD_RESULT == current.NEW_RESULT
    assert visual.OLD_JUDGE_SNAPSHOT == current.JUDGE_SNAPSHOT
    assert context.down_revision == completion.revision
    assert context.OLD_IDENTITY == completion.NEW_IDENTITY
    assert context.OLD_RESULT == completion.NEW_RESULT
    assert context.OLD_JUDGE_SNAPSHOT == completion.JUDGE_SNAPSHOT
    clarity = _load("20261002_0033_visual_clarity_policy.py")
    assert clarity.down_revision == context.revision
    assert clarity.OLD_IDENTITY == context.NEW_IDENTITY
    assert clarity.OLD_RESULT == context.NEW_RESULT
    assert clarity.OLD_JUDGE_SNAPSHOT == context.JUDGE_SNAPSHOT
    assert job_checks["ck_rag_answer_jobs_identity"] == clarity.NEW_IDENTITY
    assert job_checks["ck_rag_answer_jobs_result"] == clarity.NEW_RESULT
    assert job_checks["ck_rag_answer_jobs_source_judge_snapshot"] == clarity.JUDGE_SNAPSHOT
    assert "hybrid_source_navigation_v9" in job_checks[
        "ck_rag_answer_jobs_source_judge_retrieval_pair"
    ]
    assert "manual_retry_number" not in current.NEW_JOB_NULL_RESULT
    assert "source_judgment" in stage_checks["ck_rag_answer_stage_name"]
    assert "retry_count = 0" in stage_checks["ck_rag_answer_stage_source_judge_cap"]
    assert "answer_policy_version IS NOT NULL" in stage_checks[
        "ck_rag_answer_stage_source_judgment_policy"
    ]
    assert "judged.worker_attempt_number = answer_job.attempt_count" in current.NEW_REFERENCE_KIND


def test_v4_downgrade_refuses_retained_snapshots_before_ddl(monkeypatch):
    migration = _load("20260928_0029_source_judgment_policy.py")

    class Bind:
        def scalar(self, statement):
            assert migration.V4 in str(statement)
            return 1

    monkeypatch.setattr(migration.op, "get_bind", lambda: Bind())
    monkeypatch.setattr(migration.op, "drop_index", lambda *_a, **_kw: pytest.fail("DDL before preservation check"))
    with pytest.raises(RuntimeError, match="v4 source-judgment job snapshots"):
        migration.downgrade()


def test_v4_patch_refuses_unknown_guard_and_retains_older_pairs(monkeypatch):
    prior = _load("20260927_0027_source_navigation_policy.py")
    v3 = _load("20260927_0028_source_navigation_v3.py")
    v4 = _load("20260928_0029_source_judgment_policy.py")
    state = {"definition": prior.NEW_REFERENCE_GUARD.replace(
        v3.OLD_REFERENCE_PAIR, v3.NEW_REFERENCE_PAIR,
    )}

    class Bind:
        def scalar(self, _statement):
            return state["definition"]

    monkeypatch.setattr(v4.op, "get_bind", lambda: Bind())
    monkeypatch.setattr(v4.op, "execute", lambda statement: state.update(definition=str(statement)))
    v4._replace_function("rag_related_evidence_guard()", v4.OLD_REFERENCE_PAIR,
                         v4.NEW_REFERENCE_PAIR)
    assert "hybrid_source_sufficiency_v7" in state["definition"]
    assert "hybrid_source_navigation_v8" in state["definition"]
    assert "related_knowledge_navigation_v3" in state["definition"]
    assert "related_knowledge_navigation_v4" in state["definition"]
    v4._replace_function("rag_related_evidence_guard()", v4.NEW_REFERENCE_PAIR,
                         v4.OLD_REFERENCE_PAIR, reverse=True)
    assert state["definition"] == prior.NEW_REFERENCE_GUARD.replace(
        v3.OLD_REFERENCE_PAIR, v3.NEW_REFERENCE_PAIR,
    )
    state["definition"] = "CREATE FUNCTION unrelated() RETURNS trigger AS $$ BEGIN RETURN NEW; END $$"
    with pytest.raises(RuntimeError, match="Unexpected rag_answer_job_guard"):
        v4._replace_function("rag_answer_job_guard()", v4.OLD_JOB_CLAUSE, v4.NEW_JOB_CLAUSE)


def test_v4_source_job_patch_is_reversible_without_rewriting_prior_policies():
    prior = _load("20260927_0027_source_navigation_policy.py")
    v3 = _load("20260927_0028_source_navigation_v3.py")
    v4 = _load("20260928_0029_source_judgment_policy.py")
    original = prior.NEW_JOB_GUARD.replace(v3.OLD_JOB_CLAUSE, v3.NEW_JOB_CLAUSE)
    pairs = (
        (v4.OLD_JOB_CLAUSE, v4.NEW_JOB_CLAUSE),
        (v4.OLD_JOB_NO_MATCH, v4.NEW_JOB_NO_MATCH),
        (v4.OLD_JOB_NULL_RESULT, v4.NEW_JOB_NULL_RESULT),
        (v4.OLD_JOB_NEW_SNAPSHOT, v4.NEW_JOB_NEW_SNAPSHOT),
        (v4.OLD_JOB_OLD_SNAPSHOT, v4.NEW_JOB_OLD_SNAPSHOT),
    )
    changed = original
    for old, new in pairs:
        assert changed.count(old) == 1
        changed = changed.replace(old, new)
    assert "clarification_needed" in changed
    assert "source_judge_model" in changed
    for old, new in reversed(pairs):
        assert changed.count(new) == 1
        changed = changed.replace(new, old)
    assert changed == original
