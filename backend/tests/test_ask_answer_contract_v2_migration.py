"""The future Ask answer shape must retain the two-request DB guard."""

import importlib.util
from pathlib import Path

import pytest


def _migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/20260925_0020_ask_answer_contract_v2_stage_guard.py"
    )
    spec = importlib.util.spec_from_file_location("ask_answer_contract_v2_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_v2_upgrade_covers_both_policies_and_remote_uniqueness(monkeypatch):
    migration = _migration()
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        migration.op, "drop_index", lambda name, **_: calls.append(("drop_index", name)),
    )
    monkeypatch.setattr(
        migration.op, "drop_constraint", lambda name, *_args, **_: calls.append(("drop_constraint", name)),
    )

    def check(name, table, sql):
        assert table == "rag_answer_stage_attempts"
        assert "two_request_local_support_v1" in sql
        assert "two_request_local_support_v2" in sql
        assert "retry_count = 0" in sql
        assert "physical_request_count <= 1" in sql
        calls.append(("check", name))

    def index(name, table, columns, *, unique, postgresql_where):
        assert table == "rag_answer_stage_attempts"
        assert columns == ["job_id", "manual_retry_number", "stage"]
        assert unique
        predicate = str(postgresql_where)
        assert "two_request_local_support_v1" in predicate
        assert "two_request_local_support_v2" in predicate
        assert "query_embedding" in predicate and "answer" in predicate
        calls.append(("index", name))

    monkeypatch.setattr(migration.op, "create_check_constraint", check)
    monkeypatch.setattr(migration.op, "create_index", index)
    migration.upgrade()
    assert calls == [
        ("drop_index", "uq_rag_answer_stage_local_remote_attempt"),
        ("drop_constraint", "ck_rag_answer_stage_two_request_cap"),
        ("check", "ck_rag_answer_stage_two_request_cap"),
        ("index", "uq_rag_answer_stage_local_remote_attempt"),
    ]


def test_v2_downgrade_refuses_retained_jobs_before_ddl(monkeypatch):
    migration = _migration()

    class FakeBind:
        def scalar(self, statement):
            sql = str(statement)
            assert "rag_answer_jobs" in sql and "rag_answer_stage_attempts" in sql
            assert "two_request_local_support_v2" in sql
            return 1

    monkeypatch.setattr(migration.op, "get_bind", lambda: FakeBind())
    monkeypatch.setattr(
        migration.op, "drop_index", lambda *args, **kwargs: pytest.fail("DDL must not begin"),
    )
    with pytest.raises(RuntimeError, match="answer-contract v2 records"):
        migration.downgrade()
