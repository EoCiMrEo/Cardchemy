"""Content-free operational records with independently bounded retention."""

from sqlalchemy import CheckConstraint, Column, DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.time_utils import utcnow


class RequestEvent(Base):
    __tablename__ = "request_events"

    id = Column(UUID(as_uuid=True), primary_key=True)
    route = Column(String(160), nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=False)
    latency_milliseconds = Column(Integer, nullable=False)
    error_code = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())

    __table_args__ = (
        CheckConstraint("status_code BETWEEN 100 AND 599", name="ck_request_events_status"),
        CheckConstraint("latency_milliseconds >= 0", name="ck_request_events_latency"),
        Index("ix_request_events_created", "created_at", "id"),
    )


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    worker_id = Column(String(128), primary_key=True)
    kind = Column(String(16), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    status = Column(String(16), nullable=False)

    __table_args__ = (
        CheckConstraint("kind IN ('generation', 'email', 'index', 'answer')", name="ck_worker_heartbeats_kind"),
        CheckConstraint("status IN ('running', 'disabled', 'draining')", name="ck_worker_heartbeats_status"),
        Index("ix_worker_heartbeats_kind_seen", "kind", "last_seen_at"),
        Index("ix_worker_heartbeats_retention", "last_seen_at", "worker_id"),
    )
