"""The old three-call schema must not reinterpret retained two-request work."""

import importlib.util
from pathlib import Path

import pytest


def test_two_request_policy_downgrade_refuses_retained_jobs_or_stages(monkeypatch):
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/20260922_0017_ask_local_support_policy.py"
    )
    spec = importlib.util.spec_from_file_location("ask_local_support_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    class FakeBind:
        def scalar(self, statement):
            sql = str(statement)
            assert "two_request_local_support_v1" in sql
            assert "local_nli_qa_v1" in sql
            assert "stage = 'local_support'" in sql
            return 1

    monkeypatch.setattr(migration.op, "get_bind", lambda: FakeBind())
    monkeypatch.setattr(
        migration.op,
        "drop_index",
        lambda *args, **kwargs: pytest.fail("DDL must not begin"),
    )
    with pytest.raises(RuntimeError, match="two-request Ask jobs"):
        migration.downgrade()
