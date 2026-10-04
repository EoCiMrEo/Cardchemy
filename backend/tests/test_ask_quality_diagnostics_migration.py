"""Retained Ask quality outcomes must survive a guarded rollback decision."""

import importlib.util
from pathlib import Path

import pytest


def test_quality_diagnostics_downgrade_refuses_retained_outcomes(monkeypatch):
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/20260925_0018_ask_quality_diagnostics.py"
    )
    spec = importlib.util.spec_from_file_location("ask_quality_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    class FakeBind:
        def scalar(self, statement):
            sql = str(statement)
            assert "rag_messages WHERE abstention_kind IS NOT NULL" in sql
            assert "rag_answer_jobs WHERE failure_reason IS NOT NULL" in sql
            assert "rag_answer_stage_attempts" in sql
            for field in (
                "failure_reason", "provider_finish_reason", "input_tokens", "output_tokens",
                "usage_estimated", "retrieval_ranks", "support_reason", "support_entailment",
                "support_question_relevance", "support_equivalence", "support_contradiction",
            ):
                assert field in sql
            return 1

    monkeypatch.setattr(migration.op, "get_bind", lambda: FakeBind())
    monkeypatch.setattr(
        migration.op, "drop_constraint",
        lambda *args, **kwargs: pytest.fail("DDL must not begin"),
    )
    with pytest.raises(RuntimeError, match="Lane 6 Ask diagnostics"):
        migration.downgrade()
