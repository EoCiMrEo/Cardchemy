"""Stage validated generation cards for an explicit smaller-target choice.

Revision ID: 20260925_0019
Revises: 20260925_0018
Create Date: 2026-09-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "20260925_0019"
down_revision = "20260925_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generation_jobs", sa.Column("card_choice_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("generation_jobs", sa.Column("card_choice_key_hash", sa.String(64), nullable=True))
    op.add_column("generation_jobs", sa.Column("selected_card_count", sa.Integer(), nullable=True))
    op.add_column(
        "generation_jobs",
        sa.Column("quality_attempts", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.drop_constraint("ck_generation_jobs_status", "generation_jobs", type_="check")
    op.create_check_constraint(
        "ck_generation_jobs_status", "generation_jobs",
        "status IN ('awaiting_upload', 'awaiting_choice', 'awaiting_card_choice', 'queued', 'running', 'completed', 'failed', 'cancelled')",
    )
    op.create_check_constraint(
        "ck_generation_jobs_card_choice_state", "generation_jobs",
        "status <> 'awaiting_card_choice' OR "
        "(job_kind = 'flashcards' AND card_choice_expires_at IS NOT NULL "
        "AND selected_card_count IS NULL AND generated_card_count IS NULL)",
    )
    op.create_check_constraint(
        "ck_generation_jobs_card_choice_key", "generation_jobs",
        "card_choice_key_hash IS NULL OR length(card_choice_key_hash) = 64",
    )
    op.create_check_constraint(
        "ck_generation_jobs_selected_card_count", "generation_jobs",
        "(card_choice_key_hash IS NULL AND selected_card_count IS NULL) OR "
        "(card_choice_key_hash IS NOT NULL AND selected_card_count BETWEEN 1 AND requested_card_count)",
    )
    op.drop_index("ix_generation_jobs_user_active", table_name="generation_jobs")
    op.create_index(
        "ix_generation_jobs_user_active", "generation_jobs", ["user_id", "status"],
        postgresql_where=sa.text("status IN ('awaiting_upload', 'awaiting_choice', 'awaiting_card_choice', 'queued', 'running')"),
    )
    op.create_index(
        "ix_generation_jobs_card_choice_expiry", "generation_jobs", ["card_choice_expires_at", "id"],
        postgresql_where=sa.text("status = 'awaiting_card_choice'"),
    )
    op.create_table(
        "generation_candidate_stages",
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("generation_jobs.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("key_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("manual_retry_number", sa.Integer(), nullable=False),
        sa.Column("validation_policy_version", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("key_version = 1", name="ck_generation_candidate_stage_key_version"),
        sa.CheckConstraint("length(nonce) = 12", name="ck_generation_candidate_stage_nonce_length"),
        sa.CheckConstraint("length(payload) BETWEEN 17 AND 16777216", name="ck_generation_candidate_stage_payload_length"),
        sa.CheckConstraint("candidate_count BETWEEN 1 AND 500", name="ck_generation_candidate_stage_count"),
        sa.CheckConstraint("attempt_number >= 1 AND manual_retry_number >= 0", name="ck_generation_candidate_stage_attempt"),
    )
    op.create_index("ix_generation_candidate_stage_expires_at", "generation_candidate_stages", ["expires_at", "job_id"])


def downgrade() -> None:
    incompatible = op.get_bind().scalar(sa.text(
        "SELECT (SELECT count(*) FROM generation_candidate_stages) + "
        "(SELECT count(*) FROM generation_jobs WHERE status = 'awaiting_card_choice' "
        "OR selected_card_count IS NOT NULL OR card_choice_key_hash IS NOT NULL "
        "OR quality_attempts <> '[]'::jsonb)"
    ))
    if incompatible:
        raise RuntimeError("Cannot downgrade while validated-card choice data exists")
    op.drop_index("ix_generation_candidate_stage_expires_at", table_name="generation_candidate_stages")
    op.drop_table("generation_candidate_stages")
    op.drop_index("ix_generation_jobs_card_choice_expiry", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_user_active", table_name="generation_jobs")
    op.create_index(
        "ix_generation_jobs_user_active", "generation_jobs", ["user_id", "status"],
        postgresql_where=sa.text("status IN ('awaiting_upload', 'awaiting_choice', 'queued', 'running')"),
    )
    op.drop_constraint("ck_generation_jobs_selected_card_count", "generation_jobs", type_="check")
    op.drop_constraint("ck_generation_jobs_card_choice_key", "generation_jobs", type_="check")
    op.drop_constraint("ck_generation_jobs_card_choice_state", "generation_jobs", type_="check")
    op.drop_constraint("ck_generation_jobs_status", "generation_jobs", type_="check")
    op.create_check_constraint(
        "ck_generation_jobs_status", "generation_jobs",
        "status IN ('awaiting_upload', 'awaiting_choice', 'queued', 'running', 'completed', 'failed', 'cancelled')",
    )
    op.drop_column("generation_jobs", "quality_attempts")
    op.drop_column("generation_jobs", "selected_card_count")
    op.drop_column("generation_jobs", "card_choice_key_hash")
    op.drop_column("generation_jobs", "card_choice_expires_at")
