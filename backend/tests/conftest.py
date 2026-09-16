import os
from pathlib import Path

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import make_url

os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test-only-secret-key-with-adequate-entropy-1234567890"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/test"
os.environ["GENERATION_SOURCE_ENCRYPTION_KEY"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
if os.environ.get("RUN_LIVE_AI_TESTS") != "1":
    os.environ["AI_API_KEY"] = "test-only-provider-key"
os.environ["EMAIL_LEASE_SECONDS"] = "240"

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
import app.models  # noqa: F401,E402 - registers every table on Base


@pytest.fixture
def postgres_test_database_url() -> str:
    """Require an explicitly named disposable PostgreSQL database before writes."""
    raw_url = os.getenv("POSTGRES_TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("POSTGRES_TEST_DATABASE_URL is not configured")
    try:
        url = make_url(raw_url)
    except Exception:
        pytest.fail("POSTGRES_TEST_DATABASE_URL is invalid", pytrace=False)
    database_name = (url.database or "").lower()
    host = (url.host or "").lower()
    host_is_local = host in {"localhost", "127.0.0.1", "::1"}
    host_is_ci_service = os.getenv("CI") == "true" and host in {"db", "postgres"}
    host_is_container_service = Path("/.dockerenv").exists() and host == "db"
    if (
        url.drivername != "postgresql+asyncpg"
        or not database_name.endswith("_test")
        or len(database_name) <= len("_test")
        or not (host_is_local or host_is_ci_service or host_is_container_service)
    ):
        pytest.fail(
            "POSTGRES_TEST_DATABASE_URL must select a disposable PostgreSQL test database",
            pytrace=False,
        )
    return raw_url


@pytest_asyncio.fixture
async def postgres_engine(postgres_test_database_url):
    """Use a fresh event-loop-local engine and verify the current schema head."""
    expected_database = make_url(postgres_test_database_url).database
    migration_dir = Path(__file__).resolve().parents[1] / "alembic"
    heads = ScriptDirectory(str(migration_dir)).get_heads()
    if len(heads) != 1:
        pytest.fail("PostgreSQL tests require one maintained Alembic head", pytrace=False)
    engine = create_async_engine(postgres_test_database_url, pool_size=8, max_overflow=0)
    try:
        async with engine.connect() as connection:
            actual_database = await connection.scalar(text("SELECT current_database()"))
            if actual_database != expected_database:
                pytest.fail("PostgreSQL test database identity changed", pytrace=False)
            revisions = set((await connection.scalars(text("SELECT version_num FROM alembic_version"))).all())
            if revisions != set(heads):
                pytest.fail(
                    "PostgreSQL test database must be migrated to the current Alembic head",
                    pytrace=False,
                )
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def postgres_session_factory(postgres_engine):
    return async_sessionmaker(postgres_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def db(session_factory):
    async with session_factory() as session:
        yield session
