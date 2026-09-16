"""Durable AI provider request telemetry.

Revision ID: 20260916_0006
Revises: 20260915_0005
Create Date: 2026-09-16
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260916_0006"
down_revision: str | None = "20260915_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generation_jobs",
        sa.Column("estimated_request_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "generation_jobs",
        sa.Column("provider_request_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "generation_jobs",
        sa.Column("provider_retry_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "generation_jobs",
        sa.Column(
            "provider_rate_limit_wait_milliseconds",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "generation_jobs",
        sa.Column("cached_input_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "generation_jobs",
        sa.Column(
            "provider_request_counts_by_stage",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.create_check_constraint(
        "ck_generation_jobs_request_telemetry",
        "generation_jobs",
        "estimated_request_count >= 0 AND provider_request_count >= 0 AND "
        "provider_retry_count >= 0 AND provider_retry_count <= provider_request_count AND "
        "provider_rate_limit_wait_milliseconds >= 0 AND cached_input_tokens >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_generation_jobs_request_telemetry", "generation_jobs", type_="check"
    )
    for column in (
        "provider_request_counts_by_stage",
        "cached_input_tokens",
        "provider_rate_limit_wait_milliseconds",
        "provider_retry_count",
        "provider_request_count",
        "estimated_request_count",
    ):
        op.drop_column("generation_jobs", column)
