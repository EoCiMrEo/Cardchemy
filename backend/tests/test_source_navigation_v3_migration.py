"""The corrected selector has a new immutable job and retrieval snapshot."""

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


def test_v3_migration_starts_from_used_v2_contract_and_retains_old_read_rows():
    prior = _load("20260927_0027_source_navigation_policy.py")
    current = _load("20260927_0028_source_navigation_v3.py")
    assert current.down_revision == prior.revision
    assert current.OLD_IDENTITY == prior.NEW_IDENTITY
    assert current.OLD_RESULT == prior.NEW_RESULT
    assert current.OLD_POLICIES == prior.SOURCE_POLICIES
    assert "related_knowledge_navigation_v2" in current.NEW_POLICIES
    assert "related_knowledge_navigation_v3" in current.NEW_POLICIES
    assert "hybrid_source_navigation_v8" in current.NEW_REFERENCE_PAIR
    assert "hybrid_source_navigation_v9" in current.NEW_REFERENCE_PAIR


def test_v3_downgrade_refuses_retained_jobs_before_any_schema_change(monkeypatch):
    migration = _load("20260927_0028_source_navigation_v3.py")

    class Bind:
        def scalar(self, statement):
            assert "related_knowledge_navigation_v3" in str(statement)
            return 1

    monkeypatch.setattr(migration.op, "get_bind", lambda: Bind())
    monkeypatch.setattr(migration.op, "drop_constraint", lambda *_a, **_kw: pytest.fail("DDL before preservation check"))
    with pytest.raises(RuntimeError, match="v3 source-navigation job snapshots"):
        migration.downgrade()


def test_v3_function_replacement_refuses_an_unexpected_installed_guard(monkeypatch):
    migration = _load("20260927_0028_source_navigation_v3.py")

    class Bind:
        def scalar(self, _statement):
            return "CREATE FUNCTION unrelated() RETURNS trigger AS $$ BEGIN RETURN NEW; END $$"

    monkeypatch.setattr(migration.op, "get_bind", lambda: Bind())
    monkeypatch.setattr(migration.op, "execute", lambda *_a: pytest.fail("Changed unknown function"))
    with pytest.raises(RuntimeError, match="Unexpected rag_answer_job_guard"):
        migration._replace_function(
            "rag_answer_job_guard()", migration.OLD_JOB_CLAUSE, migration.NEW_JOB_CLAUSE,
        )


def test_v3_function_clauses_upgrade_and_reverse_without_erasing_v2(monkeypatch):
    prior = _load("20260927_0027_source_navigation_policy.py")
    migration = _load("20260927_0028_source_navigation_v3.py")
    state = {"definition": prior.NEW_REFERENCE_GUARD}

    class Bind:
        def scalar(self, _statement):
            return state["definition"]

    monkeypatch.setattr(migration.op, "get_bind", lambda: Bind())
    monkeypatch.setattr(migration.op, "execute", lambda statement: state.update(definition=str(statement)))
    migration._replace_function(
        "rag_related_evidence_guard()", migration.OLD_REFERENCE_PAIR,
        migration.NEW_REFERENCE_PAIR,
    )
    assert "hybrid_source_navigation_v8" in state["definition"]
    assert "hybrid_source_navigation_v9" in state["definition"]
    migration._replace_function(
        "rag_related_evidence_guard()", migration.NEW_REFERENCE_PAIR,
        migration.OLD_REFERENCE_PAIR, reject_existing=False,
    )
    assert state["definition"] == prior.NEW_REFERENCE_GUARD
