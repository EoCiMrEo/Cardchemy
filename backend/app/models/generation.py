"""Persistent, owner-scoped state for PDF flashcard generation jobs."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.time_utils import utcnow


class GenerationJobStatus(str, enum.Enum):
    AWAITING_UPLOAD = "awaiting_upload"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GenerationJob(Base):
    """Small durable queue row; ciphertext lives in a separate table."""

    __tablename__ = "generation_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    # Authoritative Knowledge capture association. Removing a document detaches
    # this provenance without deleting the generation result or allowing retry
    # to recapture removed content.
    document_id = Column(
        UUID(as_uuid=True), ForeignKey("subject_documents.id", ondelete="SET NULL"), nullable=True,
    )
    knowledge_capture_removed = Column(Boolean, nullable=False, default=False, server_default=text("false"))

    idempotency_key_hash = Column(String(64), nullable=False)
    request_fingerprint = Column(String(64), nullable=False)
    status = Column(
        String(24), nullable=False, default=GenerationJobStatus.AWAITING_UPLOAD.value
    )
    progress = Column(Integer, nullable=False, default=0, server_default=text("0"))
    stage = Column(
        String(64), nullable=False, default="awaiting_upload", server_default=text("'awaiting_upload'")
    )

    set_title = Column(String(255), nullable=False)
    set_description = Column(Text, nullable=True)
    requested_card_count = Column(Integer, nullable=False)
    source_pdf_name = Column(String(255), nullable=False)
    source_media_type = Column(String(64), nullable=True)
    source_size_bytes = Column(Integer, nullable=True)
    source_sha256 = Column(String(64), nullable=True)

    attempt_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    manual_retry_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    max_attempts = Column(Integer, nullable=False, default=3, server_default=text("3"))
    available_at = Column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    upload_expires_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_requested_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    error_code = Column(String(64), nullable=True)
    error_message = Column(String(500), nullable=True)
    error_retryable = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    worker_id = Column(String(128), nullable=True)
    claim_token = Column(String(64), nullable=True)
    generated_card_count = Column(Integer, nullable=True)

    # Immutable provider identity plus bounded usage/quality telemetry. The
    # worker updates the counters as calls complete; keeping them on the small
    # job row makes cost and quality decisions visible without exposing source
    # content or model prompts.
    ai_provider = Column(
        String(32), nullable=False, default="unconfigured", server_default=text("'unconfigured'")
    )
    ai_model = Column(
        String(128), nullable=False, default="unconfigured", server_default=text("'unconfigured'")
    )
    estimated_input_tokens = Column(Integer, nullable=False, default=0, server_default=text("0"))
    estimated_output_tokens = Column(Integer, nullable=False, default=0, server_default=text("0"))
    estimated_request_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    provider_request_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    provider_retry_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    provider_rate_limit_wait_milliseconds = Column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    cached_input_tokens = Column(Integer, nullable=False, default=0, server_default=text("0"))
    provider_request_counts_by_stage = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )
    actual_input_tokens = Column(Integer, nullable=True)
    actual_output_tokens = Column(Integer, nullable=True)
    estimated_cost_microusd = Column(BigInteger, nullable=True)
    actual_cost_microusd = Column(BigInteger, nullable=True)
    usage_estimated = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    accepted_card_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    rejected_card_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    limit_reason_code = Column(String(64), nullable=True)
    limit_reason_message = Column(String(500), nullable=True)

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

    source = relationship(
        "GenerationJobSource",
        back_populates="job",
        uselist=False,
        passive_deletes=True,
        lazy="raise",
    )
    result_set = relationship(
        "FlashcardSet", back_populates="generation_job", uselist=False, passive_deletes=True
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "subject_id", "user_id"],
            ["subject_documents.id", "subject_documents.subject_id", "subject_documents.uploader_id"],
            name="fk_generation_jobs_document_scope", deferrable=True, initially="DEFERRED",
        ),
        CheckConstraint("NOT knowledge_capture_removed OR document_id IS NULL", name="ck_generation_jobs_removed_capture"),
        Index("ix_generation_jobs_document", "document_id", "subject_id", "user_id"),
        UniqueConstraint(
            "user_id", "idempotency_key_hash", name="uq_generation_jobs_user_idempotency"
        ),
        CheckConstraint(
            "status IN ('awaiting_upload', 'queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_generation_jobs_status",
        ),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_generation_jobs_progress"),
        CheckConstraint(
            "requested_card_count BETWEEN 1 AND 500", name="ck_generation_jobs_card_count"
        ),
        CheckConstraint(
            "(source_size_bytes IS NULL AND source_sha256 IS NULL AND source_media_type IS NULL) "
            "OR (source_size_bytes > 0 AND source_sha256 IS NOT NULL AND source_media_type IS NOT NULL)",
            name="ck_generation_jobs_source_metadata",
        ),
        CheckConstraint(
            "source_sha256 IS NULL OR length(source_sha256) = 64",
            name="ck_generation_jobs_source_hash",
        ),
        CheckConstraint(
            "length(request_fingerprint) = 64", name="ck_generation_jobs_fingerprint"
        ),
        CheckConstraint(
            "length(idempotency_key_hash) = 64", name="ck_generation_jobs_idempotency_hash"
        ),
        CheckConstraint("attempt_count >= 0", name="ck_generation_jobs_attempt_count"),
        CheckConstraint("manual_retry_count >= 0", name="ck_generation_jobs_manual_retry_count"),
        CheckConstraint("max_attempts BETWEEN 1 AND 10", name="ck_generation_jobs_max_attempts"),
        CheckConstraint(
            "generated_card_count IS NULL OR generated_card_count >= 0",
            name="ck_generation_jobs_generated_count",
        ),
        CheckConstraint(
            "estimated_input_tokens >= 0 AND estimated_output_tokens >= 0",
            name="ck_generation_jobs_estimated_tokens",
        ),
        CheckConstraint(
            "estimated_request_count >= 0 AND provider_request_count >= 0 AND "
            "provider_retry_count >= 0 AND provider_retry_count <= provider_request_count AND "
            "provider_rate_limit_wait_milliseconds >= 0 AND cached_input_tokens >= 0",
            name="ck_generation_jobs_request_telemetry",
        ),
        CheckConstraint(
            "(actual_input_tokens IS NULL OR actual_input_tokens >= 0) AND "
            "(actual_output_tokens IS NULL OR actual_output_tokens >= 0)",
            name="ck_generation_jobs_actual_tokens",
        ),
        CheckConstraint(
            "(estimated_cost_microusd IS NULL OR estimated_cost_microusd >= 0) AND "
            "(actual_cost_microusd IS NULL OR actual_cost_microusd >= 0)",
            name="ck_generation_jobs_cost",
        ),
        CheckConstraint(
            "accepted_card_count >= 0 AND rejected_card_count >= 0",
            name="ck_generation_jobs_quality_counts",
        ),
        CheckConstraint(
            "(limit_reason_code IS NULL AND limit_reason_message IS NULL) OR "
            "(limit_reason_code IS NOT NULL AND limit_reason_message IS NOT NULL)",
            name="ck_generation_jobs_limit_reason_pair",
        ),
        CheckConstraint(
            "status <> 'running' OR "
            "(worker_id IS NOT NULL AND claim_token IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_generation_jobs_running_claim",
        ),
        CheckConstraint(
            "status <> 'completed' OR "
            "(progress = 100 AND completed_at IS NOT NULL AND generated_card_count IS NOT NULL)",
            name="ck_generation_jobs_completed",
        ),
        Index("ix_generation_jobs_user_created", "user_id", "created_at", "id"),
        Index("ix_generation_jobs_subject_created", "subject_id", "created_at", "id"),
        Index("ix_generation_jobs_created", "created_at", "id"),
        Index("ix_generation_jobs_retention", "completed_at", "id", postgresql_where=text("status IN ('completed','failed','cancelled')")),
        Index(
            "ix_generation_jobs_queue",
            "available_at",
            "created_at",
            "id",
            postgresql_where=text("status = 'queued'"),
        ),
        Index(
            "ix_generation_jobs_running_lease",
            "lease_expires_at",
            "id",
            postgresql_where=text("status = 'running'"),
        ),
        Index(
            "ix_generation_jobs_user_active",
            "user_id",
            "status",
            postgresql_where=text("status IN ('awaiting_upload', 'queued', 'running')"),
        ),
    )


class GenerationJobSource(Base):
    """One encrypted temporary source object for a generation job."""

    __tablename__ = "generation_job_sources"

    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("generation_jobs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    key_version = Column(Integer, nullable=False, default=1, server_default=text("1"))
    nonce = Column(LargeBinary, nullable=False)
    payload = Column(LargeBinary, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

    job = relationship("GenerationJob", back_populates="source")

    __table_args__ = (
        CheckConstraint("key_version = 1", name="ck_generation_job_sources_key_version"),
        CheckConstraint("length(nonce) = 12", name="ck_generation_job_sources_nonce_length"),
        CheckConstraint("length(payload) > 16", name="ck_generation_job_sources_payload_length"),
        Index(
            "ix_generation_job_sources_expires_at",
            "expires_at",
            postgresql_where=text("expires_at IS NOT NULL"),
        ),
    )


class GenerationQuotaEvent(Base):
    """Append-only quota charge; survives subject/job deletion for the day."""

    __tablename__ = "generation_quota_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(
        UUID(as_uuid=True), ForeignKey("generation_jobs.id", ondelete="SET NULL"), nullable=True
    )
    operation_key_hash = Column(String(64), nullable=False)
    job_units = Column(Integer, nullable=False, default=1, server_default=text("1"))
    card_units = Column(Integer, nullable=False)
    upload_bytes = Column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "operation_key_hash", name="uq_generation_quota_events_operation"
        ),
        CheckConstraint(
            "length(operation_key_hash) = 64", name="ck_generation_quota_events_key_hash"
        ),
        CheckConstraint("job_units = 1", name="ck_generation_quota_events_job_units"),
        CheckConstraint("card_units > 0", name="ck_generation_quota_events_card_units"),
        CheckConstraint("upload_bytes >= 0", name="ck_generation_quota_events_upload_bytes"),
        Index("ix_generation_quota_events_user_created", "user_id", "created_at"),
        Index("ix_generation_quota_events_created", "created_at"),
        Index("ix_generation_quota_events_job_id", "job_id"),
    )
