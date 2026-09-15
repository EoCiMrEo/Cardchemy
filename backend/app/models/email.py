"""Durable transactional email outbox state."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.time_utils import utcnow


class EmailMessageType(str, enum.Enum):
    PASSWORD_RESET = "password_reset"
    PASSWORD_CHANGED = "password_changed"
    STUDENT_INVITATION = "student_invitation"


class EmailOutboxStatus(str, enum.Enum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"


class EmailOutboxMessage(Base):
    """Small durable queue row; secret links and rendered bodies are derived at send time."""

    __tablename__ = "email_outbox_messages"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    message_type = Column(String(32), nullable=False)
    recipient_email = Column(String(255), nullable=False)
    message_id = Column(String(255), nullable=False)
    idempotency_key_hash = Column(String(64), nullable=False)

    status = Column(
        String(16),
        nullable=False,
        default=EmailOutboxStatus.PENDING.value,
        server_default=text("'pending'"),
    )
    attempt_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    max_attempts = Column(Integer, nullable=False, default=5, server_default=text("5"))
    available_at = Column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    delivery_started_at = Column(DateTime(timezone=True), nullable=True)

    claimed_at = Column(DateTime(timezone=True), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    worker_id = Column(String(128), nullable=True)
    claim_token = Column(String(64), nullable=True)

    sent_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
    last_error_code = Column(String(64), nullable=True)

    password_reset_token_id = Column(
        UUID(as_uuid=True),
        ForeignKey("password_reset_tokens.id", ondelete="CASCADE"),
        nullable=True,
    )
    invite_link_id = Column(
        UUID(as_uuid=True),
        ForeignKey("invite_links.id", ondelete="CASCADE"),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
        onupdate=utcnow,
    )

    password_reset_token = relationship("PasswordResetToken", lazy="raise")
    invite_link = relationship("InviteLink", lazy="raise")

    __table_args__ = (
        UniqueConstraint("message_id", name="uq_email_outbox_messages_message_id"),
        UniqueConstraint(
            "idempotency_key_hash",
            name="uq_email_outbox_messages_idempotency_key_hash",
        ),
        UniqueConstraint(
            "message_type",
            "password_reset_token_id",
            name="uq_email_outbox_messages_type_password_reset_token",
        ),
        UniqueConstraint(
            "message_type",
            "invite_link_id",
            name="uq_email_outbox_messages_type_invite_link",
        ),
        CheckConstraint(
            "message_type IN ('password_reset', 'password_changed', 'student_invitation')",
            name="ck_email_outbox_messages_message_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'sending', 'sent', 'failed')",
            name="ck_email_outbox_messages_status",
        ),
        CheckConstraint(
            "recipient_email = lower(trim(recipient_email)) AND "
            "length(recipient_email) BETWEEN 3 AND 255",
            name="ck_email_outbox_messages_recipient_email_normalized",
        ),
        CheckConstraint(
            "length(trim(message_id)) BETWEEN 1 AND 255",
            name="ck_email_outbox_messages_message_id_length",
        ),
        CheckConstraint(
            "length(idempotency_key_hash) = 64",
            name="ck_email_outbox_messages_idempotency_key_hash",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND max_attempts BETWEEN 1 AND 10 "
            "AND attempt_count <= max_attempts",
            name="ck_email_outbox_messages_attempts",
        ),
        CheckConstraint(
            "last_error_code IS NULL OR length(trim(last_error_code)) BETWEEN 1 AND 64",
            name="ck_email_outbox_messages_error_code_length",
        ),
        CheckConstraint(
            "(message_type IN ('password_reset', 'password_changed') "
            "AND password_reset_token_id IS NOT NULL AND invite_link_id IS NULL) OR "
            "(message_type = 'student_invitation' AND invite_link_id IS NOT NULL "
            "AND password_reset_token_id IS NULL)",
            name="ck_email_outbox_messages_relevant_source",
        ),
        CheckConstraint(
            "(status = 'sending' AND claimed_at IS NOT NULL "
            "AND lease_expires_at IS NOT NULL AND worker_id IS NOT NULL "
            "AND claim_token IS NOT NULL) OR "
            "(status <> 'sending' AND claimed_at IS NULL "
            "AND lease_expires_at IS NULL AND worker_id IS NULL "
            "AND claim_token IS NULL)",
            name="ck_email_outbox_messages_sending_claim",
        ),
        CheckConstraint(
            "(status = 'sent' AND sent_at IS NOT NULL AND failed_at IS NULL) OR "
            "(status = 'failed' AND failed_at IS NOT NULL AND sent_at IS NULL) OR "
            "(status IN ('pending', 'sending') AND sent_at IS NULL AND failed_at IS NULL)",
            name="ck_email_outbox_messages_terminal_timestamps",
        ),
        CheckConstraint(
            "worker_id IS NULL OR length(trim(worker_id)) BETWEEN 1 AND 128",
            name="ck_email_outbox_messages_worker_id_length",
        ),
        CheckConstraint(
            "claim_token IS NULL OR length(claim_token) = 64",
            name="ck_email_outbox_messages_claim_token_length",
        ),
        Index("ix_email_outbox_messages_password_reset_token_id", "password_reset_token_id"),
        Index("ix_email_outbox_messages_invite_link_id", "invite_link_id"),
        Index(
            "ix_email_outbox_messages_queue",
            "available_at",
            "created_at",
            "id",
            postgresql_where=text("status = 'pending'"),
        ),
        Index(
            "ix_email_outbox_messages_sending_lease",
            "lease_expires_at",
            "id",
            postgresql_where=text("status = 'sending'"),
        ),
        Index(
            "ix_email_outbox_messages_expiry",
            "expires_at",
            "id",
            postgresql_where=text(
                "status IN ('pending', 'sending') AND expires_at IS NOT NULL"
            ),
        ),
        Index(
            "ix_email_outbox_messages_sent_retention",
            "sent_at",
            "id",
            postgresql_where=text("status = 'sent'"),
        ),
        Index(
            "ix_email_outbox_messages_failed_retention",
            "failed_at",
            "id",
            postgresql_where=text("status = 'failed'"),
        ),
    )
