"""Offline proof for the unconditional vector foundation and SQLite fixtures."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import Column, MetaData, Table, create_engine, insert, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import OperationalError
from sqlalchemy.schema import CreateTable

from app.models.vector import EMBEDDING_DIMENSIONS, embedding_vector_type


MIGRATION_PATH = Path(__file__).resolve().parents[1] / "alembic/versions/20260918_0009_pgvector_foundation.py"


def load_migration():
    spec = importlib.util.spec_from_file_location("vector_foundation_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QueryResult:
    def __init__(self, row):
        self.row = row

    def scalar_one(self):
        assert self.row is not None
        return self.row

    def one_or_none(self):
        return self.row

    def one(self):
        assert self.row is not None
        return self.row


class VectorCatalog:
    def __init__(self, *, server=160000, available=(True, False), installed=None, privileges=(True, True), create_error=False):
        self.server = server
        self.available = available
        self.installed = installed
        self.privileges = privileges
        self.create_error = create_error
        self.created = 0
        self.statements = []

    def execute(self, query):
        sql = str(query)
        self.statements.append(sql)
        if "server_version_num" in sql:
            return QueryResult(self.server)
        if "pg_available_extension_versions" in sql:
            return QueryResult(self.available)
        if "FROM pg_extension" in sql:
            return QueryResult(self.installed)
        if "has_database_privilege" in sql:
            return QueryResult(self.privileges)
        if sql.startswith("CREATE EXTENSION"):
            self.created += 1
            if self.create_error:
                raise OperationalError(sql, None, Exception("PRIVATE_DATABASE_ERROR"))
            self.installed = ("0.8.6", "public")
            return QueryResult(None)
        raise AssertionError(f"Unexpected migration query: {sql}")


@pytest.mark.parametrize("catalog,expected_error", [
    (VectorCatalog(server=150000), "PostgreSQL 16"),
    (VectorCatalog(available=None), "not installed"),
    (VectorCatalog(installed=("0.8.5", "public")), "version is unsupported"),
    (VectorCatalog(installed=("0.8.6", "custom")), "public schema"),
    (VectorCatalog(privileges=(False, False)), "database CREATE"),
    (VectorCatalog(privileges=(True, False)), "database CREATE"),
    (VectorCatalog(create_error=True), "Could not install"),
], ids=["wrong-postgres", "missing-package", "old-preinstalled", "wrong-schema", "no-create", "no-superuser", "create-error"])
def test_migration_fails_closed_before_or_during_extension_install(monkeypatch, catalog, expected_error):
    migration = load_migration()
    monkeypatch.setattr(migration.op, "get_bind", lambda: catalog)
    with pytest.raises(RuntimeError, match=expected_error) as error:
        migration.upgrade()
    assert "PRIVATE_DATABASE_ERROR" not in str(error.value)
    assert catalog.created == (1 if catalog.create_error else 0)


def test_migration_accepts_compatible_preinstalled_extension_without_create(monkeypatch):
    migration = load_migration()
    catalog = VectorCatalog(installed=("0.8.6", "public"), privileges=(False, False))
    monkeypatch.setattr(migration.op, "get_bind", lambda: catalog)
    migration.upgrade()
    assert catalog.created == 0
    assert not any("has_database_privilege" in sql for sql in catalog.statements)
    migration.downgrade()
    assert catalog.installed == ("0.8.6", "public")


def test_migration_installs_exact_version_and_safe_downgrade_allows_reupgrade(monkeypatch):
    migration = load_migration()
    catalog = VectorCatalog()
    monkeypatch.setattr(migration.op, "get_bind", lambda: catalog)
    migration.upgrade()
    assert catalog.created == 1
    assert any("CREATE EXTENSION vector WITH SCHEMA public VERSION '0.8.6'" == sql for sql in catalog.statements)
    migration.downgrade()
    assert catalog.installed == ("0.8.6", "public")
    migration.upgrade()
    assert catalog.created == 1


def test_vector_type_is_postgres_vector_and_sqlite_fixture_json():
    table = Table("vector_probe", MetaData(), Column("embedding", embedding_vector_type(), nullable=False))
    pg_sql = str(CreateTable(table).compile(dialect=postgresql.dialect()))
    sqlite_sql = str(CreateTable(table).compile(dialect=sqlite.dialect()))
    assert EMBEDDING_DIMENSIONS == 1536
    assert "VECTOR(1536)" in pg_sql
    assert "JSON" in sqlite_sql

    engine = create_engine("sqlite:///:memory:")
    table.metadata.create_all(engine)
    fixture_vector = [0.0] * EMBEDDING_DIMENSIONS
    fixture_vector[0] = 1.0
    with engine.begin() as connection:
        connection.execute(insert(table).values(embedding=fixture_vector))
        stored = connection.scalar(select(table.c.embedding))
    assert stored == fixture_vector
    engine.dispose()
