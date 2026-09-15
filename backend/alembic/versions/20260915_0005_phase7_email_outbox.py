"""Phase 7 durable transactional email outbox.

Revision ID: 20260915_0005
Revises: 20260915_0004
Create Date: 2026-09-15
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260915_0005"
down_revision: str | None = "20260915_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UUID = postgresql.UUID(as_uuid=True)
TIMESTAMPTZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("invite_links", sa.Column("recipient_email", sa.String(255), nullable=True))
    op.create_check_constraint(
        "ck_invite_links_recipient_email_normalized",
        "invite_links",
        "recipient_email IS NULL OR "
        "(recipient_email = lower(trim(recipient_email)) AND "
        "length(recipient_email) BETWEEN 3 AND 255)",
    )

    op.create_table(
        "email_outbox_messages",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("message_type", sa.String(32), nullable=False),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("message_id", sa.String(255), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default=sa.text("5"), nullable=False),
        sa.Column("available_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", TIMESTAMPTZ, nullable=False),
        sa.Column("last_attempt_at", TIMESTAMPTZ, nullable=True),
        sa.Column("delivery_started_at", TIMESTAMPTZ, nullable=True),
        sa.Column("claimed_at", TIMESTAMPTZ, nullable=True),
        sa.Column("lease_expires_at", TIMESTAMPTZ, nullable=True),
        sa.Column("worker_id", sa.String(128), nullable=True),
        sa.Column("claim_token", sa.String(64), nullable=True),
        sa.Column("sent_at", TIMESTAMPTZ, nullable=True),
        sa.Column("failed_at", TIMESTAMPTZ, nullable=True),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("password_reset_token_id", UUID, nullable=True),
        sa.Column("invite_link_id", UUID, nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "message_type IN ('password_reset', 'password_changed', 'student_invitation')",
            name="ck_email_outbox_messages_message_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sending', 'sent', 'failed')",
            name="ck_email_outbox_messages_status",
        ),
        sa.CheckConstraint(
            "recipient_email = lower(trim(recipient_email)) AND "
            "length(recipient_email) BETWEEN 3 AND 255",
            name="ck_email_outbox_messages_recipient_email_normalized",
        ),
        sa.CheckConstraint(
            "length(trim(message_id)) BETWEEN 1 AND 255",
            name="ck_email_outbox_messages_message_id_length",
        ),
        sa.CheckConstraint(
            "length(idempotency_key_hash) = 64",
            name="ck_email_outbox_messages_idempotency_key_hash",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND max_attempts BETWEEN 1 AND 10 "
            "AND attempt_count <= max_attempts",
            name="ck_email_outbox_messages_attempts",
        ),
        sa.CheckConstraint(
            "last_error_code IS NULL OR length(trim(last_error_code)) BETWEEN 1 AND 64",
            name="ck_email_outbox_messages_error_code_length",
        ),
        sa.CheckConstraint(
            "(message_type IN ('password_reset', 'password_changed') "
            "AND password_reset_token_id IS NOT NULL AND invite_link_id IS NULL) OR "
            "(message_type = 'student_invitation' AND invite_link_id IS NOT NULL "
            "AND password_reset_token_id IS NULL)",
            name="ck_email_outbox_messages_relevant_source",
        ),
        sa.CheckConstraint(
            "(status = 'sending' AND claimed_at IS NOT NULL "
            "AND lease_expires_at IS NOT NULL AND worker_id IS NOT NULL "
            "AND claim_token IS NOT NULL) OR "
            "(status <> 'sending' AND claimed_at IS NULL "
            "AND lease_expires_at IS NULL AND worker_id IS NULL "
            "AND claim_token IS NULL)",
            name="ck_email_outbox_messages_sending_claim",
        ),
        sa.CheckConstraint(
            "(status = 'sent' AND sent_at IS NOT NULL AND failed_at IS NULL) OR "
            "(status = 'failed' AND failed_at IS NOT NULL AND sent_at IS NULL) OR "
            "(status IN ('pending', 'sending') AND sent_at IS NULL AND failed_at IS NULL)",
            name="ck_email_outbox_messages_terminal_timestamps",
        ),
        sa.CheckConstraint(
            "worker_id IS NULL OR length(trim(worker_id)) BETWEEN 1 AND 128",
            name="ck_email_outbox_messages_worker_id_length",
        ),
        sa.CheckConstraint(
            "claim_token IS NULL OR length(claim_token) = 64",
            name="ck_email_outbox_messages_claim_token_length",
        ),
        sa.ForeignKeyConstraint(
            ["password_reset_token_id"],
            ["password_reset_tokens.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["invite_link_id"], ["invite_links.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", name="uq_email_outbox_messages_message_id"),
        sa.UniqueConstraint(
            "idempotency_key_hash",
            name="uq_email_outbox_messages_idempotency_key_hash",
        ),
        sa.UniqueConstraint(
            "message_type",
            "password_reset_token_id",
            name="uq_email_outbox_messages_type_password_reset_token",
        ),
        sa.UniqueConstraint(
            "message_type",
            "invite_link_id",
            name="uq_email_outbox_messages_type_invite_link",
        ),
    )
    op.create_index(
        "ix_email_outbox_messages_password_reset_token_id",
        "email_outbox_messages",
        ["password_reset_token_id"],
    )
    op.create_index(
        "ix_email_outbox_messages_invite_link_id",
        "email_outbox_messages",
        ["invite_link_id"],
    )
    op.create_index(
        "ix_email_outbox_messages_queue",
        "email_outbox_messages",
        ["available_at", "created_at", "id"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_email_outbox_messages_sending_lease",
        "email_outbox_messages",
        ["lease_expires_at", "id"],
        postgresql_where=sa.text("status = 'sending'"),
    )
    op.create_index(
        "ix_email_outbox_messages_expiry",
        "email_outbox_messages",
        ["expires_at", "id"],
        postgresql_where=sa.text(
            "status IN ('pending', 'sending') AND expires_at IS NOT NULL"
        ),
    )
    op.create_index(
        "ix_email_outbox_messages_sent_retention",
        "email_outbox_messages",
        ["sent_at", "id"],
        postgresql_where=sa.text("status = 'sent'"),
    )
    op.create_index(
        "ix_email_outbox_messages_failed_retention",
        "email_outbox_messages",
        ["failed_at", "id"],
        postgresql_where=sa.text("status = 'failed'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_email_outbox_messages_failed_retention",
        table_name="email_outbox_messages",
    )
    op.drop_index(
        "ix_email_outbox_messages_sent_retention",
        table_name="email_outbox_messages",
    )
    op.drop_index(
        "ix_email_outbox_messages_expiry",
        table_name="email_outbox_messages",
    )
    op.drop_index(
        "ix_email_outbox_messages_sending_lease",
        table_name="email_outbox_messages",
    )
    op.drop_index(
        "ix_email_outbox_messages_queue",
        table_name="email_outbox_messages",
    )
    op.drop_index(
        "ix_email_outbox_messages_invite_link_id",
        table_name="email_outbox_messages",
    )
    op.drop_index(
        "ix_email_outbox_messages_password_reset_token_id",
        table_name="email_outbox_messages",
    )
    op.drop_table("email_outbox_messages")

    op.drop_constraint(
        "ck_invite_links_recipient_email_normalized",
        "invite_links",
        type_="check",
    )
    op.drop_column("invite_links", "recipient_email")
