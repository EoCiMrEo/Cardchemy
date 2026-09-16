"""PostgreSQL migration proof for durable AI request telemetry."""

import os

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine


pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_ai_request_telemetry_migration_columns_constraints_and_defaults():
    database_url = os.getenv("POSTGRES_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("POSTGRES_TEST_DATABASE_URL is not configured")
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            assert (
                await connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20260916_0007"
            )

            def inspect_schema(sync_connection):
                inspector = inspect(sync_connection)
                return (
                    {
                        column["name"]: column
                        for column in inspector.get_columns("generation_jobs")
                    },
                    {
                        constraint["name"]
                        for constraint in inspector.get_check_constraints("generation_jobs")
                    },
                )

            columns, checks = await connection.run_sync(inspect_schema)

        expected = {
            "estimated_request_count",
            "provider_request_count",
            "provider_retry_count",
            "provider_rate_limit_wait_milliseconds",
            "cached_input_tokens",
            "provider_request_counts_by_stage",
        }
        assert expected <= columns.keys()
        assert all(columns[name]["nullable"] is False for name in expected)
        assert (
            columns["provider_request_counts_by_stage"]["type"].__class__.__name__
            == "JSONB"
        )
        assert "ck_generation_jobs_request_telemetry" in checks
    finally:
        await engine.dispose()
