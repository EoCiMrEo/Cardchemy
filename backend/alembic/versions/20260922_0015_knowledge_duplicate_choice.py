"""Add durable, owner-scoped Knowledge duplicate choices.

Revision ID: 20260922_0015
Revises: 20260922_0014
Create Date: 2026-09-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20260922_0015"
down_revision = "20260922_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generation_jobs", sa.Column("knowledge_choice_candidate_id", UUID(as_uuid=True), nullable=True))
    op.add_column("generation_jobs", sa.Column("knowledge_choice_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("generation_jobs", sa.Column("knowledge_choice_key_hash", sa.String(64), nullable=True))
    op.add_column("generation_jobs", sa.Column("knowledge_choice", sa.String(24), nullable=True))
    op.add_column("generation_jobs", sa.Column("knowledge_upload_outcome", sa.String(24), nullable=True))
    op.create_foreign_key(
        "fk_generation_jobs_choice_candidate", "generation_jobs", "subject_documents",
        ["knowledge_choice_candidate_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key("fk_generation_jobs_choice_candidate_scope", "generation_jobs", "subject_documents", ["knowledge_choice_candidate_id", "subject_id", "user_id"], ["id", "subject_id", "uploader_id"], deferrable=True, initially="DEFERRED")
    op.create_check_constraint("ck_generation_jobs_choice", "generation_jobs", "knowledge_choice IS NULL OR knowledge_choice IN ('reuse', 'separate_copy')")
    op.create_check_constraint("ck_generation_jobs_choice_key", "generation_jobs", "knowledge_choice_key_hash IS NULL OR length(knowledge_choice_key_hash) = 64")
    op.create_check_constraint("ck_generation_jobs_upload_outcome", "generation_jobs", "knowledge_upload_outcome IS NULL OR knowledge_upload_outcome IN ('no_changes', 'reused', 'separate_copy')")
    op.create_check_constraint(
        "ck_generation_jobs_choice_outcome", "generation_jobs",
        "(knowledge_choice IS NULL AND knowledge_choice_key_hash IS NULL AND "
        "(knowledge_upload_outcome IS NULL OR knowledge_upload_outcome = 'no_changes')) OR "
        "(knowledge_choice IS NOT NULL AND knowledge_choice_key_hash IS NOT NULL AND "
        "knowledge_upload_outcome IS NOT NULL AND "
        "((knowledge_choice = 'reuse' AND knowledge_upload_outcome = 'reused') OR "
        "(knowledge_choice = 'separate_copy' AND knowledge_upload_outcome = 'separate_copy')))",
    )
    op.create_check_constraint(
        "ck_generation_jobs_outcome_capture", "generation_jobs",
        "(knowledge_upload_outcome <> 'no_changes' OR knowledge_capture_status IN ('unchanged', 'removed')) AND "
        "(knowledge_upload_outcome <> 'reused' OR knowledge_capture_status IN ('reused', 'removed'))",
    )
    op.create_check_constraint(
        "ck_generation_jobs_awaiting_choice", "generation_jobs",
        "status <> 'awaiting_choice' OR (knowledge_choice_expires_at IS NOT NULL AND knowledge_choice IS NULL "
        "AND knowledge_upload_outcome IS NULL AND knowledge_capture_status = 'pending')",
    )
    op.drop_constraint("ck_generation_jobs_status", "generation_jobs", type_="check")
    op.create_check_constraint("ck_generation_jobs_status", "generation_jobs", "status IN ('awaiting_upload', 'awaiting_choice', 'queued', 'running', 'completed', 'failed', 'cancelled')")
    op.drop_constraint("ck_generation_jobs_capture_status", "generation_jobs", type_="check")
    op.create_check_constraint("ck_generation_jobs_capture_status", "generation_jobs", "knowledge_capture_status IN ('not_requested', 'pending', 'captured', 'failed', 'removed', 'reused', 'unchanged')")
    op.drop_constraint("ck_generation_jobs_captured_revision", "generation_jobs", type_="check")
    op.create_check_constraint("ck_generation_jobs_captured_revision", "generation_jobs", "knowledge_capture_status NOT IN ('captured', 'reused', 'unchanged') OR (document_id IS NOT NULL AND knowledge_content_revision_id IS NOT NULL)")
    op.drop_index("ix_generation_jobs_user_active", table_name="generation_jobs")
    op.create_index("ix_generation_jobs_user_active", "generation_jobs", ["user_id", "status"], postgresql_where=sa.text("status IN ('awaiting_upload', 'awaiting_choice', 'queued', 'running')"))


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM generation_jobs WHERE status = 'awaiting_choice' OR knowledge_capture_status IN ('reused', 'unchanged') OR knowledge_upload_outcome IS NOT NULL")):
        raise RuntimeError("Cannot downgrade with retained Knowledge duplicate-choice outcomes")
    op.drop_index("ix_generation_jobs_user_active", table_name="generation_jobs")
    op.create_index("ix_generation_jobs_user_active", "generation_jobs", ["user_id", "status"], postgresql_where=sa.text("status IN ('awaiting_upload', 'queued', 'running')"))
    op.drop_constraint("ck_generation_jobs_captured_revision", "generation_jobs", type_="check")
    op.create_check_constraint("ck_generation_jobs_captured_revision", "generation_jobs", "knowledge_capture_status <> 'captured' OR (document_id IS NOT NULL AND knowledge_content_revision_id IS NOT NULL)")
    op.drop_constraint("ck_generation_jobs_capture_status", "generation_jobs", type_="check")
    op.create_check_constraint("ck_generation_jobs_capture_status", "generation_jobs", "knowledge_capture_status IN ('not_requested', 'pending', 'captured', 'failed', 'removed')")
    op.drop_constraint("ck_generation_jobs_status", "generation_jobs", type_="check")
    op.create_check_constraint("ck_generation_jobs_status", "generation_jobs", "status IN ('awaiting_upload', 'queued', 'running', 'completed', 'failed', 'cancelled')")
    op.drop_constraint("ck_generation_jobs_awaiting_choice", "generation_jobs", type_="check")
    op.drop_constraint("ck_generation_jobs_outcome_capture", "generation_jobs", type_="check")
    op.drop_constraint("ck_generation_jobs_choice_outcome", "generation_jobs", type_="check")
    op.drop_constraint("ck_generation_jobs_upload_outcome", "generation_jobs", type_="check")
    op.drop_constraint("ck_generation_jobs_choice_key", "generation_jobs", type_="check")
    op.drop_constraint("ck_generation_jobs_choice", "generation_jobs", type_="check")
    op.drop_constraint("fk_generation_jobs_choice_candidate_scope", "generation_jobs", type_="foreignkey")
    op.drop_constraint("fk_generation_jobs_choice_candidate", "generation_jobs", type_="foreignkey")
    for name in ("knowledge_upload_outcome", "knowledge_choice", "knowledge_choice_key_hash", "knowledge_choice_expires_at", "knowledge_choice_candidate_id"):
        op.drop_column("generation_jobs", name)
