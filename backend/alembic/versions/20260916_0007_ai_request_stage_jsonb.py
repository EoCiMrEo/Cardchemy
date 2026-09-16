"""Use comparable JSONB for AI request-stage telemetry.

Revision ID: 20260916_0007
Revises: 20260916_0006
Create Date: 2026-09-16
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260916_0007"
down_revision: str | None = "20260916_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "generation_jobs",
        "provider_request_counts_by_stage",
        existing_type=sa.JSON(),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        postgresql_using="provider_request_counts_by_stage::jsonb",
    )


def downgrade() -> None:
    op.alter_column(
        "generation_jobs",
        "provider_request_counts_by_stage",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=sa.JSON(),
        existing_nullable=False,
        server_default=sa.text("'{}'::json"),
        postgresql_using="provider_request_counts_by_stage::json",
    )
