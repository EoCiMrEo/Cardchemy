"""Add Ask shutdown diagnostics and Gemini catalog snapshots.

Revision ID: 20260922_0014
Revises: 20260920_0013
Create Date: 2026-09-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20260922_0014"
down_revision = "20260920_0013"
branch_labels = None
depends_on = None


_SHUTDOWN_ERROR = (
    "(error_code = 'rag_ask_shutdown' AND error_message = 'Ask AI was paused before this answer completed.') OR "
)


def _answer_error_pairs(*, include_shutdown: bool) -> str:
    return (
        "(status IN ('queued','running','completed') AND error_code IS NULL AND error_message IS NULL "
        "AND NOT error_retryable) OR "
        "(status IN ('failed','cancelled') AND error_code IS NOT NULL AND error_message IS NOT NULL "
        "AND (status = 'failed' OR NOT error_retryable) AND ("
        "(error_code = 'rag_answer_failed' AND error_message = 'Answer generation failed.') OR "
        "(error_code = 'rag_answer_cancelled' AND error_message = 'Answer generation was cancelled.') OR "
        "(error_code = 'rag_answer_lease_expired' AND error_message = 'Answer worker lease expired.') OR "
        + (_SHUTDOWN_ERROR if include_shutdown else "")
        + "(error_code = 'rag_access_revoked' AND error_message = 'Subject access is no longer available.') OR "
        "(error_code = 'rag_corpus_changed' AND error_message = 'Course materials changed before the answer completed.') OR "
        "(error_code = 'rag_profile_mismatch' AND error_message = 'Ask AI configuration changed before execution.')))"
    )


def upgrade() -> None:
    op.drop_constraint("ck_rag_answer_jobs_error_pair", "rag_answer_jobs", type_="check")
    op.create_check_constraint("ck_rag_answer_jobs_error_pair", "rag_answer_jobs", _answer_error_pairs(include_shutdown=True))
    for table in ("generation_jobs", "rag_answer_jobs"):
        op.add_column(table, sa.Column("ai_catalog_version", sa.String(64), nullable=True))
        op.add_column(table, sa.Column("ai_schema_policy_version", sa.String(64), nullable=True))

    op.add_column("rag_answer_jobs", sa.Column("failed_stage", sa.String(32), nullable=True))
    op.add_column("rag_answer_jobs", sa.Column("provider_error_category", sa.String(64), nullable=True))
    op.add_column(
        "rag_answer_jobs",
        sa.Column("execution_uncertain", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_table(
        "rag_answer_stage_attempts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", UUID(as_uuid=True), nullable=False),
        sa.Column("manual_retry_number", sa.Integer(), nullable=False),
        sa.Column("worker_attempt_number", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("elapsed_milliseconds", sa.BigInteger(), nullable=True),
        sa.Column("physical_request_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rate_limit_wait_milliseconds", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_category", sa.String(64), nullable=True),
        sa.Column("execution_uncertain", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["job_id"], ["rag_answer_jobs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("job_id", "manual_retry_number", "worker_attempt_number", "stage", name="uq_rag_answer_stage_attempt"),
        sa.CheckConstraint("manual_retry_number BETWEEN 0 AND 10 AND worker_attempt_number BETWEEN 1 AND 10", name="ck_rag_answer_stage_attempt_numbers"),
        sa.CheckConstraint("stage IN ('query_embedding','retrieval','answer','support')", name="ck_rag_answer_stage_name"),
        sa.CheckConstraint("physical_request_count >= 0 AND retry_count BETWEEN 0 AND physical_request_count AND rate_limit_wait_milliseconds >= 0 AND (elapsed_milliseconds IS NULL OR elapsed_milliseconds >= 0)", name="ck_rag_answer_stage_usage"),
    )
    op.create_index(
        "ix_rag_answer_stage_attempt_job",
        "rag_answer_stage_attempts",
        ["job_id", "manual_retry_number", "worker_attempt_number"],
    )


def downgrade() -> None:
    # Old schema cannot represent this terminal outcome. Require operator-led
    # backup/restore rather than silently rewriting retained question history.
    shutdown_count = op.get_bind().scalar(sa.text(
        "SELECT count(*) FROM rag_answer_jobs WHERE error_code = 'rag_ask_shutdown'"
    ))
    if shutdown_count:
        raise RuntimeError("Cannot downgrade while retained Ask shutdown outcomes exist")
    op.drop_constraint("ck_rag_answer_jobs_error_pair", "rag_answer_jobs", type_="check")
    op.create_check_constraint("ck_rag_answer_jobs_error_pair", "rag_answer_jobs", _answer_error_pairs(include_shutdown=False))
    op.drop_index("ix_rag_answer_stage_attempt_job", table_name="rag_answer_stage_attempts")
    op.drop_table("rag_answer_stage_attempts")
    op.drop_column("rag_answer_jobs", "execution_uncertain")
    op.drop_column("rag_answer_jobs", "provider_error_category")
    op.drop_column("rag_answer_jobs", "failed_stage")
    for table in ("rag_answer_jobs", "generation_jobs"):
        op.drop_column(table, "ai_schema_policy_version")
        op.drop_column(table, "ai_catalog_version")
