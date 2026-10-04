"""The related-evidence downgrade must preserve populated private excerpts."""

import importlib.util
from pathlib import Path

import pytest


def _migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/20260925_0021_rag_related_evidence.py"
    )
    spec = importlib.util.spec_from_file_location("rag_related_evidence_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_related_evidence_downgrade_refuses_populated_table_before_ddl(monkeypatch):
    migration = _migration()

    class FakeBind:
        def scalar(self, statement):
            assert "rag_related_evidence" in str(statement)
            return 1

    monkeypatch.setattr(migration.op, "get_bind", lambda: FakeBind())
    monkeypatch.setattr(
        migration.op, "execute", lambda *_args, **_kwargs: pytest.fail("DDL must not begin"),
    )
    with pytest.raises(RuntimeError, match="related evidence records exist"):
        migration.downgrade()
