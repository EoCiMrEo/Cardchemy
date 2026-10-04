"""Structural policy rollout changes insertion eligibility, never stored history."""

import importlib.util
from pathlib import Path

import pytest


def _migration(filename):
    path = Path(__file__).resolve().parents[1] / "alembic/versions" / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _structural_migration():
    return _migration("20260927_0025_structural_source_policy.py")


def test_upgrade_changes_only_canonical_insertion_policy_and_preserves_v6_guard(monkeypatch):
    previous = _migration("20260927_0024_canonical_page_references.py")
    migration = _structural_migration()
    calls = []
    monkeypatch.setattr(migration.op, "execute", lambda statement: calls.append(str(statement)))
    migration.upgrade()
    assert migration.revision == "20260927_0025"
    assert migration.down_revision == previous.revision
    assert len(calls) == 1
    previous_guard = previous._guard_sql(canonical_pages=True)
    assert calls[0] == previous_guard.replace(
        "hybrid_source_sufficiency_v6", "hybrid_source_sufficiency_v7",
    )
    assert migration._guard_sql(retrieval_policy="hybrid_source_sufficiency_v6") == previous_guard
    assert "UPDATE rag_related_evidence" not in calls[0]
    assert "UPDATE rag_answer_jobs" not in calls[0]
    assert "DELETE FROM" not in calls[0]


def test_downgrade_refuses_any_retained_v7_snapshot_before_function_replacement(monkeypatch):
    migration = _structural_migration()

    class Bind:
        def scalar(self, statement):
            # Terminal and no-match jobs are also versioned history. The guard
            # must not silently ignore these because they lack reference rows.
            assert str(statement) == (
                "SELECT count(*) FROM rag_answer_jobs "
                "WHERE retrieval_policy = 'hybrid_source_sufficiency_v7'"
            )
            return 1

    monkeypatch.setattr(migration.op, "get_bind", lambda: Bind())
    monkeypatch.setattr(migration.op, "execute", lambda *_: pytest.fail("DDL must not begin"))
    with pytest.raises(RuntimeError, match="structural v7 job snapshots exist"):
        migration.downgrade()


def test_downgrade_restores_exact_v6_guard_when_no_v7_jobs_remain(monkeypatch):
    previous = _migration("20260927_0024_canonical_page_references.py")
    migration = _structural_migration()

    class Bind:
        def scalar(self, _statement):
            return 0

    calls = []
    monkeypatch.setattr(migration.op, "get_bind", lambda: Bind())
    monkeypatch.setattr(migration.op, "execute", lambda statement: calls.append(str(statement)))
    migration.downgrade()
    assert calls == [previous._guard_sql(canonical_pages=True)]


def test_guard_builder_refuses_unknown_policy():
    with pytest.raises(ValueError, match="Unsupported canonical reference policy"):
        _structural_migration()._guard_sql(retrieval_policy="hybrid_source_sufficiency_future")
