"""Additive source-kind references preserve historical rows and safe rollback."""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint

from app.models.rag import RagRelatedEvidence


def _migration():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/20260927_0024_canonical_page_references.py"
    spec = importlib.util.spec_from_file_location("canonical_page_reference_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_source_kind_model_stores_only_reference_with_legacy_default():
    table = RagRelatedEvidence.__table__
    assert table.c.source_kind.nullable is False
    assert table.c.source_kind.default.arg == "chunk"
    assert str(table.c.source_kind.server_default.arg) == "'chunk'"
    assert not {"source_quote", "page_content", "content"} & set(table.c.keys())
    checks = {check.name: str(check.sqltext) for check in table.constraints if isinstance(check, CheckConstraint)}
    assert checks["ck_rag_related_evidence_source_kind"] == "source_kind IN ('chunk','canonical_page')"
    assert "<= 480" in checks["ck_rag_related_evidence_offsets"]


def test_upgrade_preserves_existing_rows_and_uses_authoritative_kind_offsets(monkeypatch):
    migration = _migration()
    calls = []
    monkeypatch.setattr(migration.op, "add_column", lambda table, column: calls.append((table, column)))
    monkeypatch.setattr(migration.op, "create_check_constraint", lambda *args: calls.append(args))
    monkeypatch.setattr(migration.op, "execute", lambda query: calls.append(str(query)))
    migration.upgrade()
    assert migration.down_revision == "20260926_0023"
    assert str(calls[0][1].server_default.arg) == "'chunk'"
    sql = calls[-1]
    assert "NEW.source_kind = 'canonical_page' THEN page.content ELSE eligible.content" in sql
    for field in ("content_revision_id", "document_id", "subject_id", "uploader_id", "page_number"):
        assert f"page.{field} = eligible.{field}" in sql
    assert "eligible.corpus_revision = answer_job.corpus_revision" in sql
    assert "eligible.embedding_space_hash = answer_job.embedding_space_hash" in sql
    assert "enrollment.student_id = principal.id" in sql
    assert "NEW.end_offset - NEW.start_offset > 480" in sql
    assert "substring(source_content FROM NEW.start_offset + 1" in sql
    assert "hybrid_source_sufficiency_v6" in sql
    assert "NEW.expires_at > question_expiry" in sql
    assert "DELETE" not in sql and "UPDATE rag_related_evidence" not in sql


def test_downgrade_refuses_page_references_before_any_ddl(monkeypatch):
    migration = _migration()

    class Bind:
        def scalar(self, query):
            assert "WHERE source_kind = 'canonical_page'" in str(query)
            return 1

    monkeypatch.setattr(migration.op, "get_bind", lambda: Bind())
    monkeypatch.setattr(migration.op, "execute", lambda *_: pytest.fail("DDL must not begin"))
    with pytest.raises(RuntimeError, match="canonical page references exist"):
        migration.downgrade()


def test_downgrade_retains_legacy_references_and_restores_original_guard(monkeypatch):
    migration = _migration()

    class Bind:
        def scalar(self, _query):
            return 0

    calls = []
    monkeypatch.setattr(migration.op, "get_bind", lambda: Bind())
    monkeypatch.setattr(migration.op, "execute", lambda query: calls.append(str(query)))
    monkeypatch.setattr(migration.op, "drop_constraint", lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr(migration.op, "drop_column", lambda *args: calls.append(args))
    migration.downgrade()
    assert "NEW.source_kind" not in calls[0]
    assert "SELECT content INTO source_content FROM eligible_subject_knowledge_chunks" in calls[0]
    assert calls[-1] == ("rag_related_evidence", "source_kind")
