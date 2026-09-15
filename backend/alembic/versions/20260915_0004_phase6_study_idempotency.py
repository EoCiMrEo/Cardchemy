"""Phase 6 durable study-answer idempotency receipts.

Revision ID: 20260915_0004
Revises: 20260914_0003
Create Date: 2026-09-15
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260915_0004"
down_revision: str | None = "20260914_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "study_answer_submissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("flashcard_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("response_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(idempotency_key_hash) = 64",
            name="ck_study_answer_submissions_key_hash",
        ),
        sa.CheckConstraint(
            "length(request_fingerprint) = 64",
            name="ck_study_answer_submissions_request_fingerprint",
        ),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["flashcard_id"], ["flashcards.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "student_id",
            "idempotency_key_hash",
            name="uq_study_answer_submissions_student_key",
        ),
    )
    op.create_index(
        "ix_study_answer_submissions_flashcard_id",
        "study_answer_submissions",
        ["flashcard_id"],
    )
    op.create_index(
        "ix_study_answer_submissions_created_at",
        "study_answer_submissions",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_study_answer_submissions_created_at",
        table_name="study_answer_submissions",
    )
    op.drop_index(
        "ix_study_answer_submissions_flashcard_id",
        table_name="study_answer_submissions",
    )
    op.drop_table("study_answer_submissions")
