"""Phase 3 durable, bounded PDF generation jobs.

Revision ID: 20260914_0002
Revises: 20260914_0001
Create Date: 2026-09-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260914_0002"
down_revision: str | None = "20260914_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UUID = postgresql.UUID(as_uuid=True)
TIMESTAMPTZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "generation_jobs",
        sa.Column("id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("subject_id", UUID, nullable=False),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("progress", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("stage", sa.String(64), server_default=sa.text("'awaiting_upload'"), nullable=False),
        sa.Column("set_title", sa.String(255), nullable=False),
        sa.Column("set_description", sa.Text(), nullable=True),
        sa.Column("requested_card_count", sa.Integer(), nullable=False),
        sa.Column("source_pdf_name", sa.String(255), nullable=False),
        sa.Column("source_media_type", sa.String(64), nullable=True),
        sa.Column("source_size_bytes", sa.Integer(), nullable=True),
        sa.Column("source_sha256", sa.String(64), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("manual_retry_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default=sa.text("3"), nullable=False),
        sa.Column("available_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
        sa.Column("upload_expires_at", TIMESTAMPTZ, nullable=True),
        sa.Column("started_at", TIMESTAMPTZ, nullable=True),
        sa.Column("heartbeat_at", TIMESTAMPTZ, nullable=True),
        sa.Column("lease_expires_at", TIMESTAMPTZ, nullable=True),
        sa.Column("cancellation_requested_at", TIMESTAMPTZ, nullable=True),
        sa.Column("completed_at", TIMESTAMPTZ, nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("error_retryable", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("worker_id", sa.String(128), nullable=True),
        sa.Column("claim_token", sa.String(64), nullable=True),
        sa.Column("generated_card_count", sa.Integer(), nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('awaiting_upload', 'queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_generation_jobs_status",
        ),
        sa.CheckConstraint("progress BETWEEN 0 AND 100", name="ck_generation_jobs_progress"),
        sa.CheckConstraint(
            "requested_card_count BETWEEN 1 AND 500", name="ck_generation_jobs_card_count"
        ),
        sa.CheckConstraint(
            "(source_size_bytes IS NULL AND source_sha256 IS NULL AND source_media_type IS NULL) "
            "OR (source_size_bytes > 0 AND source_sha256 IS NOT NULL AND source_media_type IS NOT NULL)",
            name="ck_generation_jobs_source_metadata",
        ),
        sa.CheckConstraint(
            "source_sha256 IS NULL OR length(source_sha256) = 64",
            name="ck_generation_jobs_source_hash",
        ),
        sa.CheckConstraint("length(request_fingerprint) = 64", name="ck_generation_jobs_fingerprint"),
        sa.CheckConstraint("length(idempotency_key_hash) = 64", name="ck_generation_jobs_idempotency_hash"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_generation_jobs_attempt_count"),
        sa.CheckConstraint("manual_retry_count >= 0", name="ck_generation_jobs_manual_retry_count"),
        sa.CheckConstraint("max_attempts BETWEEN 1 AND 10", name="ck_generation_jobs_max_attempts"),
        sa.CheckConstraint(
            "generated_card_count IS NULL OR generated_card_count >= 0",
            name="ck_generation_jobs_generated_count",
        ),
        sa.CheckConstraint(
            "status <> 'running' OR "
            "(worker_id IS NOT NULL AND claim_token IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_generation_jobs_running_claim",
        ),
        sa.CheckConstraint(
            "status <> 'completed' OR "
            "(progress = 100 AND completed_at IS NOT NULL AND generated_card_count IS NOT NULL)",
            name="ck_generation_jobs_completed",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "idempotency_key_hash", name="uq_generation_jobs_user_idempotency"
        ),
    )
    op.create_index(
        "ix_generation_jobs_user_created", "generation_jobs", ["user_id", "created_at", "id"]
    )
    op.create_index(
        "ix_generation_jobs_subject_created",
        "generation_jobs",
        ["subject_id", "created_at", "id"],
    )
    op.create_index("ix_generation_jobs_created", "generation_jobs", ["created_at", "id"])
    op.create_index(
        "ix_generation_jobs_queue",
        "generation_jobs",
        ["available_at", "created_at", "id"],
        postgresql_where=sa.text("status = 'queued'"),
    )
    op.create_index(
        "ix_generation_jobs_running_lease",
        "generation_jobs",
        ["lease_expires_at", "id"],
        postgresql_where=sa.text("status = 'running'"),
    )
    op.create_index(
        "ix_generation_jobs_user_active",
        "generation_jobs",
        ["user_id", "status"],
        postgresql_where=sa.text("status IN ('awaiting_upload', 'queued', 'running')"),
    )

    op.create_table(
        "generation_job_sources",
        sa.Column("job_id", UUID, nullable=False),
        sa.Column("key_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", TIMESTAMPTZ, nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("key_version = 1", name="ck_generation_job_sources_key_version"),
        sa.CheckConstraint("length(nonce) = 12", name="ck_generation_job_sources_nonce_length"),
        sa.CheckConstraint("length(payload) > 16", name="ck_generation_job_sources_payload_length"),
        sa.ForeignKeyConstraint(["job_id"], ["generation_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index(
        "ix_generation_job_sources_expires_at",
        "generation_job_sources",
        ["expires_at"],
        postgresql_where=sa.text("expires_at IS NOT NULL"),
    )

    op.create_table(
        "generation_quota_events",
        sa.Column("id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("job_id", UUID, nullable=True),
        sa.Column("operation_key_hash", sa.String(64), nullable=False),
        sa.Column("job_units", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("card_units", sa.Integer(), nullable=False),
        sa.Column("upload_bytes", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(operation_key_hash) = 64", name="ck_generation_quota_events_key_hash"),
        sa.CheckConstraint("job_units = 1", name="ck_generation_quota_events_job_units"),
        sa.CheckConstraint("card_units > 0", name="ck_generation_quota_events_card_units"),
        sa.CheckConstraint("upload_bytes >= 0", name="ck_generation_quota_events_upload_bytes"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["generation_jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "operation_key_hash", name="uq_generation_quota_events_operation"
        ),
    )
    op.create_index(
        "ix_generation_quota_events_user_created",
        "generation_quota_events",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_generation_quota_events_created", "generation_quota_events", ["created_at"]
    )
    op.create_index(
        "ix_generation_quota_events_job_id", "generation_quota_events", ["job_id"]
    )

    op.add_column("flashcard_sets", sa.Column("generation_job_id", UUID, nullable=True))
    op.create_foreign_key(
        "fk_flashcard_sets_generation_job_id",
        "flashcard_sets",
        "generation_jobs",
        ["generation_job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_flashcard_sets_generation_job_id", "flashcard_sets", ["generation_job_id"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_flashcard_sets_generation_job_id", "flashcard_sets", type_="unique"
    )
    op.drop_constraint(
        "fk_flashcard_sets_generation_job_id", "flashcard_sets", type_="foreignkey"
    )
    op.drop_column("flashcard_sets", "generation_job_id")
    op.drop_table("generation_quota_events")
    op.drop_table("generation_job_sources")
    op.drop_table("generation_jobs")
