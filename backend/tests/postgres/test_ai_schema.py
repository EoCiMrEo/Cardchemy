"""PostgreSQL migration and constraint proofs for AI quality."""

import pytest
from sqlalchemy import inspect


pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_ai_schema_migration_columns_and_constraints(postgres_engine):
    async with postgres_engine.connect() as connection:
        def inspect_schema(sync_connection):
            inspector = inspect(sync_connection)
            return (
                {column["name"] for column in inspector.get_columns("generation_jobs")},
                {column["name"] for column in inspector.get_columns("flashcards")},
                {constraint["name"] for constraint in inspector.get_check_constraints("generation_jobs")},
                {constraint["name"] for constraint in inspector.get_check_constraints("flashcards")},
            )

        job_columns, card_columns, job_checks, card_checks = await connection.run_sync(inspect_schema)
        assert {
            "ai_provider",
            "ai_model",
            "estimated_input_tokens",
            "actual_input_tokens",
            "estimated_cost_microusd",
            "accepted_card_count",
            "rejected_card_count",
            "limit_reason_code",
        } <= job_columns
        assert {"quality_score", "source_snippet", "source_page", "source_section"} <= card_columns
        assert "confidence_score" not in card_columns
        assert "source_chunk" not in card_columns
        assert "ck_generation_jobs_cost" in job_checks
        assert "ck_generation_jobs_limit_reason_pair" in job_checks
        assert "ck_flashcards_quality_score" in card_checks
        assert "ck_flashcards_source_page" in card_checks
