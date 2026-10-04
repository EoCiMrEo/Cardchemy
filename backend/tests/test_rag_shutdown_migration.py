"""A downgrade must not rewrite terminal Ask shutdown history."""

import importlib.util
from pathlib import Path

import pytest


def test_ask_shutdown_downgrade_refuses_retained_terminal_outcomes(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "alembic/versions/20260922_0014_product_quality_shutdown_diagnostics.py"
    spec = importlib.util.spec_from_file_location("ask_shutdown_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    class FakeBind:
        def scalar(self, statement):
            assert "rag_ask_shutdown" in str(statement)
            return 1

    monkeypatch.setattr(migration.op, "get_bind", lambda: FakeBind())
    monkeypatch.setattr(migration.op, "drop_constraint", lambda *args, **kwargs: pytest.fail("DDL must not begin"))
    with pytest.raises(RuntimeError, match="retained Ask shutdown outcomes"):
        migration.downgrade()
