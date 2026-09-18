"""Disposable PostgreSQL proof of the mandatory pgvector runtime contract."""

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import Column, MetaData, Table, insert, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.models.vector import EMBEDDING_DIMENSIONS, embedding_vector_type


pytestmark = pytest.mark.postgres


def load_vector_migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260918_0009_pgvector_foundation.py"
    spec = importlib.util.spec_from_file_location("postgres_vector_contract_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


async def apply_vector_foundation(connection, monkeypatch):
    migration = load_vector_migration()

    def run(sync_connection):
        monkeypatch.setattr(migration.op, "get_bind", lambda: sync_connection)
        migration.upgrade()

    await connection.run_sync(run)


@pytest_asyncio.fixture
async def isolated_vector_catalog(postgres_engine):
    """Change extension/role catalogs only inside an owned disposable child DB."""
    suffix = uuid4().hex
    database_name = f"vector_contract_{suffix}_test"
    role_name = f"vector_contract_{suffix}"
    child = None
    created_database = False
    created_role = False
    try:
        async with postgres_engine.connect() as admin:
            admin = await admin.execution_options(isolation_level="AUTOCOMMIT")
            await admin.execute(text(f'CREATE DATABASE "{database_name}" TEMPLATE template0'))
            created_database = True
            await admin.execute(text(f'CREATE ROLE "{role_name}" NOLOGIN NOSUPERUSER NOINHERIT'))
            created_role = True
        child = create_async_engine(postgres_engine.url.set(database=database_name), hide_parameters=True)
        async with child.connect() as connection:
            assert await connection.scalar(text("SELECT current_database()")) == database_name
        yield child, role_name, database_name
    finally:
        if child is not None:
            await child.dispose()
        async with postgres_engine.connect() as admin:
            admin = await admin.execution_options(isolation_level="AUTOCOMMIT")
            if created_database:
                await admin.execute(text(f'DROP DATABASE "{database_name}" WITH (FORCE)'))
            if created_role:
                await admin.execute(text(f'DROP ROLE "{role_name}"'))


async def test_pgvector_extension_version_schema_and_cosine_operator(postgres_engine):
    async with postgres_engine.connect() as connection:
        server_major = await connection.scalar(text("SHOW server_version_num"))
        installed = (await connection.execute(text("""
            SELECT extension.extversion, namespace.nspname
            FROM pg_extension AS extension
            JOIN pg_namespace AS namespace ON namespace.oid = extension.extnamespace
            WHERE extension.extname = 'vector'
        """))).one()
        distance = await connection.scalar(text("""
            SELECT '[1,0]'::public.vector OPERATOR(public.<=>) '[0,1]'::public.vector
        """))
    assert 160000 <= int(server_major) < 170000
    assert installed == ("0.8.6", "public")
    assert distance == pytest.approx(1.0)


async def test_asyncpg_sqlalchemy_vector_binding_round_trip_and_cosine(postgres_engine):
    table = Table(
        "vector_contract_binding_probe", MetaData(),
        Column("embedding", embedding_vector_type(), nullable=False),
    )
    stored_vector = [0.0] * EMBEDDING_DIMENSIONS
    stored_vector[0] = 1.0
    query_vector = [0.0] * EMBEDDING_DIMENSIONS
    query_vector[1] = 1.0
    async with postgres_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.run_sync(table.create)
            await connection.execute(insert(table).values(embedding=stored_vector))
            assert list(await connection.scalar(select(table.c.embedding))) == stored_vector
            distance = await connection.scalar(select(table.c.embedding.cosine_distance(query_vector)))
            assert distance == pytest.approx(1.0)
        finally:
            # The probe table, row and extension dependency never survive the test.
            await transaction.rollback()


async def test_preinstalled_vector_accepts_real_non_superuser(isolated_vector_catalog, monkeypatch):
    child, role_name, _ = isolated_vector_catalog
    async with child.begin() as connection:
        await connection.execute(text("CREATE EXTENSION vector WITH SCHEMA public VERSION '0.8.6'"))
        await connection.execute(text(f'SET LOCAL ROLE "{role_name}"'))
        assert await connection.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")) is False
        assert await connection.scalar(text("SELECT has_database_privilege(current_user, current_database(), 'CREATE')")) is False
        await apply_vector_foundation(connection, monkeypatch)
        assert await connection.scalar(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")) == "0.8.6"


@pytest.mark.parametrize("grant_create", [False, True], ids=["no-create", "create-without-superuser"])
async def test_vector_installation_rejects_real_insufficient_privileges(isolated_vector_catalog, monkeypatch, grant_create):
    child, role_name, database_name = isolated_vector_catalog
    async with child.begin() as connection:
        if grant_create:
            await connection.execute(text(f'GRANT CREATE ON DATABASE "{database_name}" TO "{role_name}"'))
        await connection.execute(text(f'SET LOCAL ROLE "{role_name}"'))
        with pytest.raises(RuntimeError, match="Vector extension installation needs database CREATE"):
            await apply_vector_foundation(connection, monkeypatch)
        assert await connection.scalar(text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")) == 0


async def test_vector_migration_rejects_real_preinstalled_wrong_schema(isolated_vector_catalog, monkeypatch):
    child, _, _ = isolated_vector_catalog
    async with child.begin() as connection:
        await connection.execute(text("CREATE SCHEMA vector_contract"))
        await connection.execute(text("CREATE EXTENSION vector WITH SCHEMA vector_contract VERSION '0.8.6'"))
        with pytest.raises(RuntimeError, match="must be in the public schema"):
            await apply_vector_foundation(connection, monkeypatch)


async def test_vector_migration_rejects_injected_old_catalog_version(isolated_vector_catalog, monkeypatch):
    """Exercise actual catalog rejection; this does not install old vector binaries."""
    child, _, _ = isolated_vector_catalog
    async with child.begin() as connection:
        await connection.execute(text("CREATE EXTENSION vector WITH SCHEMA public VERSION '0.8.6'"))
        # The reviewed image need not ship old installation scripts. An isolated
        # catalog fixture verifies fail-closed handling of incompatible metadata.
        await connection.execute(text("UPDATE pg_extension SET extversion = '0.8.5' WHERE extname = 'vector'"))
        with pytest.raises(RuntimeError, match="Installed vector extension version is unsupported"):
            await apply_vector_foundation(connection, monkeypatch)
        assert await connection.scalar(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")) == "0.8.5"
