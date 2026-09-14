"""Phase 4 AI quality, provenance, and cost telemetry.

Revision ID: 20260914_0003
Revises: 20260914_0002
Create Date: 2026-09-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260914_0003"
down_revision: str | None = "20260914_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generation_jobs",
        sa.Column("ai_provider", sa.String(32), nullable=False, server_default="unconfigured"),
    )
    op.add_column(
        "generation_jobs",
        sa.Column("ai_model", sa.String(128), nullable=False, server_default="unconfigured"),
    )
    op.add_column(
        "generation_jobs",
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "generation_jobs",
        sa.Column("estimated_output_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("generation_jobs", sa.Column("actual_input_tokens", sa.Integer(), nullable=True))
    op.add_column("generation_jobs", sa.Column("actual_output_tokens", sa.Integer(), nullable=True))
    op.add_column(
        "generation_jobs", sa.Column("estimated_cost_microusd", sa.BigInteger(), nullable=True)
    )
    op.add_column(
        "generation_jobs", sa.Column("actual_cost_microusd", sa.BigInteger(), nullable=True)
    )
    op.add_column(
        "generation_jobs",
        sa.Column("usage_estimated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "generation_jobs",
        sa.Column("accepted_card_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "generation_jobs",
        sa.Column("rejected_card_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("generation_jobs", sa.Column("limit_reason_code", sa.String(64), nullable=True))
    op.add_column("generation_jobs", sa.Column("limit_reason_message", sa.String(500), nullable=True))
    op.create_check_constraint(
        "ck_generation_jobs_estimated_tokens",
        "generation_jobs",
        "estimated_input_tokens >= 0 AND estimated_output_tokens >= 0",
    )
    op.create_check_constraint(
        "ck_generation_jobs_actual_tokens",
        "generation_jobs",
        "(actual_input_tokens IS NULL OR actual_input_tokens >= 0) AND "
        "(actual_output_tokens IS NULL OR actual_output_tokens >= 0)",
    )
    op.create_check_constraint(
        "ck_generation_jobs_cost",
        "generation_jobs",
        "(estimated_cost_microusd IS NULL OR estimated_cost_microusd >= 0) AND "
        "(actual_cost_microusd IS NULL OR actual_cost_microusd >= 0)",
    )
    op.create_check_constraint(
        "ck_generation_jobs_quality_counts",
        "generation_jobs",
        "accepted_card_count >= 0 AND rejected_card_count >= 0",
    )
    op.create_check_constraint(
        "ck_generation_jobs_limit_reason_pair",
        "generation_jobs",
        "(limit_reason_code IS NULL AND limit_reason_message IS NULL) OR "
        "(limit_reason_code IS NOT NULL AND limit_reason_message IS NOT NULL)",
    )

    op.drop_constraint("ck_flashcards_source_length", "flashcards", type_="check")
    op.drop_constraint("ck_flashcards_confidence", "flashcards", type_="check")
    op.alter_column("flashcards", "confidence_score", new_column_name="quality_score")
    op.alter_column("flashcards", "source_chunk", new_column_name="source_snippet")
    op.add_column("flashcards", sa.Column("source_page", sa.Integer(), nullable=True))
    op.add_column("flashcards", sa.Column("source_section", sa.String(255), nullable=True))
    op.create_check_constraint(
        "ck_flashcards_source_snippet_length",
        "flashcards",
        "source_snippet IS NULL OR length(source_snippet) <= 10000",
    )
    op.create_check_constraint(
        "ck_flashcards_quality_score", "flashcards", "quality_score BETWEEN 0 AND 1"
    )
    op.create_check_constraint(
        "ck_flashcards_source_page", "flashcards", "source_page IS NULL OR source_page >= 1"
    )
    op.create_check_constraint(
        "ck_flashcards_source_section_length",
        "flashcards",
        "source_section IS NULL OR length(source_section) <= 255",
    )


def downgrade() -> None:
    op.drop_constraint("ck_flashcards_source_section_length", "flashcards", type_="check")
    op.drop_constraint("ck_flashcards_source_page", "flashcards", type_="check")
    op.drop_constraint("ck_flashcards_quality_score", "flashcards", type_="check")
    op.drop_constraint("ck_flashcards_source_snippet_length", "flashcards", type_="check")
    op.drop_column("flashcards", "source_section")
    op.drop_column("flashcards", "source_page")
    op.alter_column("flashcards", "source_snippet", new_column_name="source_chunk")
    op.alter_column("flashcards", "quality_score", new_column_name="confidence_score")
    op.create_check_constraint(
        "ck_flashcards_confidence", "flashcards", "confidence_score BETWEEN 0 AND 1"
    )
    op.create_check_constraint(
        "ck_flashcards_source_length",
        "flashcards",
        "source_chunk IS NULL OR length(source_chunk) <= 10000",
    )

    for constraint in (
        "ck_generation_jobs_limit_reason_pair",
        "ck_generation_jobs_quality_counts",
        "ck_generation_jobs_cost",
        "ck_generation_jobs_actual_tokens",
        "ck_generation_jobs_estimated_tokens",
    ):
        op.drop_constraint(constraint, "generation_jobs", type_="check")
    for column in (
        "limit_reason_message",
        "limit_reason_code",
        "rejected_card_count",
        "accepted_card_count",
        "usage_estimated",
        "actual_cost_microusd",
        "estimated_cost_microusd",
        "actual_output_tokens",
        "actual_input_tokens",
        "estimated_output_tokens",
        "estimated_input_tokens",
        "ai_model",
        "ai_provider",
    ):
        op.drop_column("generation_jobs", column)
