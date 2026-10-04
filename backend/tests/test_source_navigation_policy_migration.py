"""Navigation policy migration preserves source-only caps and historical guards."""

import importlib.util
from pathlib import Path

import pytest


def _load(filename):
    path = Path(__file__).resolve().parents[1] / "alembic/versions" / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_static_history_guards_match_used_revisions():
    migration = _load("20260927_0027_source_navigation_policy.py")
    source = _load("20260926_0022_related_knowledge_only.py")
    structural = _load("20260927_0025_structural_source_policy.py")
    assert migration.OLD_IDENTITY == source._NEW_IDENTITY
    assert migration.OLD_RESULT == source._NEW_RESULT
    assert migration.OLD_JOB_GUARD == source._guard_sql(source_only=True)
    assert migration.OLD_REFERENCE_GUARD == structural._guard_sql(
        retrieval_policy="hybrid_source_sufficiency_v7",
    )


def test_downgrade_refuses_retained_navigation_work_before_ddl(monkeypatch):
    migration = _load("20260927_0027_source_navigation_policy.py")

    class Bind:
        def scalar(self, statement):
            assert "related_knowledge_navigation_v2" in str(statement)
            return 1

    monkeypatch.setattr(migration.op, "get_bind", lambda: Bind())
    monkeypatch.setattr(migration.op, "execute", lambda *_: pytest.fail("DDL before preservation check"))
    with pytest.raises(RuntimeError, match="source-navigation job snapshots"):
        migration.downgrade()


def test_stage_parent_guard_binds_policy_and_both_attempt_identities():
    migration = _load("20260927_0027_source_navigation_policy.py")
    guard = migration._stage_guard(migration.SOURCE_POLICIES)
    assert "related_knowledge_navigation_v2" in guard
    assert "IS DISTINCT FROM parent_job.answer_policy_version" in guard
    assert "NEW.manual_retry_number IS DISTINCT FROM parent_job.manual_retry_count" in guard
    assert "NEW.worker_attempt_number IS DISTINCT FROM parent_job.attempt_count" in guard
    assert "FOR KEY SHARE" in guard


def test_canonical_reference_guard_requires_exact_policy_pair_and_current_scope():
    migration = _load("20260927_0027_source_navigation_policy.py")
    guard = migration.NEW_REFERENCE_GUARD
    assert "IS NOT DISTINCT FROM 'hybrid_source_navigation_v8'" in guard
    assert "IS NOT DISTINCT FROM 'related_knowledge_navigation_v2'" in guard
    assert "IS NOT DISTINCT FROM 'hybrid_source_sufficiency_v7'" in guard
    assert "eligible.corpus_revision = answer_job.corpus_revision" in guard
    assert "eligible.embedding_space_hash = answer_job.embedding_space_hash" in guard
    assert "NEW.end_offset - NEW.start_offset > 480" in guard
    assert "question_expiry <= now()" in guard
    assert "UPDATE rag_answer_jobs" not in guard
    assert "DELETE FROM" not in guard
