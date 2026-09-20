"""Content-free audit records staged with privileged business mutations."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.time_utils import utcnow


class AuditAction(str, enum.Enum):
    INVITATION_CREATED = "invitation.created"
    CARD_APPROVED = "card.approved"
    CARD_UNAPPROVED = "card.unapproved"
    CARDS_APPROVED = "cards.approved"
    SET_PUBLISHED = "set.published"
    SET_UNPUBLISHED = "set.unpublished"
    KNOWLEDGE_PUBLISHED = "knowledge.published"
    KNOWLEDGE_UNPUBLISHED = "knowledge.unpublished"
    KNOWLEDGE_REMOVED = "knowledge.removed"
    INSTRUCTOR_PROVISIONED = "account.instructor_provisioned"
    ACCOUNT_ROLE_CHANGED = "account.role_changed"
    ACCOUNT_DELETED = "account.deleted"


class AuditEvent(Base):
    """Opaque resource identities and fixed state fields; never free-form content.

    Resource IDs deliberately have no foreign keys: content deletion preserves
    operational history. Account deletion nulls its actor identity. Retention
    removes records independently of learning content.
    """

    __tablename__ = "audit_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    action = Column(String(48), nullable=False)
    actor_kind = Column(String(24), nullable=False)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    target_type = Column(String(16), nullable=False)
    target_id = Column(UUID(as_uuid=True), nullable=False)
    subject_id = Column(UUID(as_uuid=True), nullable=True)
    request_id = Column(UUID(as_uuid=True), nullable=True)
    state_before = Column(Boolean, nullable=True)
    state_after = Column(Boolean, nullable=True)
    affected_count = Column(Integer, nullable=True)
    role_before = Column(String(16), nullable=True)
    role_after = Column(String(16), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "action IN ('invitation.created', 'card.approved', 'card.unapproved', "
            "'cards.approved', 'set.published', 'set.unpublished', "
            "'knowledge.published', 'knowledge.unpublished', 'knowledge.removed', "
            "'account.instructor_provisioned', 'account.role_changed', 'account.deleted')",
            name="ck_audit_events_action",
        ),
        CheckConstraint("actor_kind IN ('user', 'operator', 'operator_database')", name="ck_audit_events_actor_kind"),
        CheckConstraint(
            "target_type IN ('invitation', 'card', 'set', 'knowledge', 'account')",
            name="ck_audit_events_target_type",
        ),
        CheckConstraint("affected_count IS NULL OR affected_count >= 0", name="ck_audit_events_affected_count"),
        CheckConstraint("role_before IS NULL OR role_before IN ('student', 'instructor')", name="ck_audit_events_role_before"),
        CheckConstraint("role_after IS NULL OR role_after IN ('student', 'instructor')", name="ck_audit_events_role_after"),
        Index("ix_audit_events_created_at", "created_at"),
        Index("ix_audit_events_actor_created", "actor_id", "created_at"),
        Index("ix_audit_events_target", "target_type", "target_id"),
    )
