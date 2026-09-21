"""Private Subject Ask AI conversations and durable answer-job state.

Conversation rows are owned by exactly one principal and Subject.  Answer jobs
snapshot the provider, embedding space and corpus revision used for one logical
question.  PostgreSQL migration triggers add transition/fencing rules; the ORM
constraints remain portable so offline SQLite tests exercise the same shape.
"""

from __future__ import annotations

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
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base
from app.time_utils import utcnow


ANSWER_ERROR_PAIRS = (
    "(status IN ('queued','running','completed') AND error_code IS NULL AND error_message IS NULL "
    "AND NOT error_retryable) OR "
    "(status IN ('failed','cancelled') AND error_code IS NOT NULL AND error_message IS NOT NULL "
    "AND (status = 'failed' OR NOT error_retryable) AND ("
    "(error_code = 'rag_answer_failed' AND error_message = 'Answer generation failed.') OR "
    "(error_code = 'rag_answer_cancelled' AND error_message = 'Answer generation was cancelled.') OR "
    "(error_code = 'rag_answer_lease_expired' AND error_message = 'Answer worker lease expired.') OR "
    "(error_code = 'rag_access_revoked' AND error_message = 'Subject access is no longer available.') OR "
    "(error_code = 'rag_corpus_changed' AND error_message = 'Course materials changed before the answer completed.') OR "
    "(error_code = 'rag_profile_mismatch' AND error_message = 'Ask AI configuration changed before execution.')))"
)


class RagThread(Base):
    __tablename__ = "rag_threads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("id", "user_id", "subject_id", name="uq_rag_threads_scope"),
        Index("ix_rag_threads_owner_updated", "user_id", "subject_id", "updated_at", "id"),
        Index("ix_rag_threads_subject", "subject_id", "id"),
        Index("ix_rag_threads_updated", "updated_at", "id"),
    )


class RagMessage(Base):
    __tablename__ = "rag_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    thread_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    subject_id = Column(UUID(as_uuid=True), nullable=False)
    role = Column(String(16), nullable=False)
    outcome = Column(String(16), nullable=True)
    content = Column(Text, nullable=False)
    source_count = Column(Integer, nullable=False, server_default=text("0"))
    corpus_revision = Column(BigInteger, nullable=True)
    embedding_space_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["thread_id", "user_id", "subject_id"],
            ["rag_threads.id", "rag_threads.user_id", "rag_threads.subject_id"],
            ondelete="CASCADE",
            name="fk_rag_messages_thread_scope",
        ),
        UniqueConstraint("id", "thread_id", "user_id", "subject_id", name="uq_rag_messages_scope"),
        CheckConstraint("role IN ('user','assistant')", name="ck_rag_messages_role"),
        CheckConstraint(
            "(role = 'user' AND outcome IS NULL AND source_count = 0 AND corpus_revision IS NULL "
            "AND embedding_space_hash IS NULL AND length(content) BETWEEN 1 AND 4000) OR "
            "(role = 'assistant' AND outcome IN ('answer','abstained') AND length(content) BETWEEN 1 AND 12000 "
            "AND corpus_revision IS NOT NULL AND corpus_revision >= 0 "
            "AND embedding_space_hash IS NOT NULL AND length(embedding_space_hash) = 64 "
            "AND ((outcome = 'answer' AND source_count BETWEEN 1 AND 5) "
            "OR (outcome = 'abstained' AND source_count = 0)))",
            name="ck_rag_messages_shape",
        ),
        CheckConstraint("expires_at > created_at", name="ck_rag_messages_expiry"),
        Index("ix_rag_messages_thread_created", "thread_id", "created_at", "id"),
        Index("ix_rag_messages_owner_expiry", "user_id", "expires_at", "id"),
        Index("ix_rag_messages_expiry", "expires_at", "id"),
    )


class RagMessageSource(Base):
    __tablename__ = "rag_message_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    message_id = Column(UUID(as_uuid=True), nullable=False)
    thread_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    subject_id = Column(UUID(as_uuid=True), nullable=False)
    chunk_id = Column(UUID(as_uuid=True), nullable=False)
    document_id = Column(UUID(as_uuid=True), nullable=False)
    content_revision_id = Column(UUID(as_uuid=True), nullable=False)
    index_revision_id = Column(UUID(as_uuid=True), nullable=False)
    citation_order = Column(Integer, nullable=False)
    claim_text = Column(Text, nullable=False)
    source_quote = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["message_id", "thread_id", "user_id", "subject_id"],
            ["rag_messages.id", "rag_messages.thread_id", "rag_messages.user_id", "rag_messages.subject_id"],
            ondelete="CASCADE",
            name="fk_rag_sources_message_scope",
        ),
        ForeignKeyConstraint(
            ["chunk_id", "index_revision_id", "content_revision_id", "document_id", "subject_id"],
            ["subject_document_chunks.id", "subject_document_chunks.index_revision_id",
             "subject_document_chunks.content_revision_id", "subject_document_chunks.document_id",
             "subject_document_chunks.subject_id"],
            ondelete="CASCADE",
            name="fk_rag_sources_chunk_scope",
        ),
        UniqueConstraint("message_id", "citation_order", name="uq_rag_sources_order"),
        UniqueConstraint("message_id", "chunk_id", name="uq_rag_sources_chunk"),
        CheckConstraint("citation_order BETWEEN 1 AND 5", name="ck_rag_sources_order"),
        CheckConstraint("length(claim_text) BETWEEN 1 AND 4000", name="ck_rag_sources_claim"),
        CheckConstraint("length(source_quote) BETWEEN 1 AND 12000", name="ck_rag_sources_quote"),
        Index("ix_rag_sources_message", "message_id", "citation_order"),
        Index("ix_rag_sources_chunk", "chunk_id", "message_id"),
        Index("ix_rag_sources_document", "document_id", "content_revision_id"),
    )


class RagAnswerJob(Base):
    __tablename__ = "rag_answer_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    thread_id = Column(UUID(as_uuid=True), nullable=False)
    question_message_id = Column(UUID(as_uuid=True), nullable=False)
    answer_message_id = Column(UUID(as_uuid=True), nullable=True)
    auth_session_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    subject_id = Column(UUID(as_uuid=True), nullable=False)
    request_id = Column(UUID(as_uuid=True), nullable=True)
    status = Column(String(24), nullable=False, server_default=text("'queued'"))
    operation_key_hash = Column(String(64), nullable=False)
    request_fingerprint = Column(String(64), nullable=False)
    document_ids = Column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False,
        default=list, server_default=text("'[]'"),
    )
    corpus_revision = Column(BigInteger, nullable=False)
    retrieval_policy = Column(String(64), nullable=False)
    embedding_space_hash = Column(String(64), nullable=False)
    ai_provider = Column(String(32), nullable=False)
    ai_base_url = Column(String(512), nullable=False)
    ai_model = Column(String(128), nullable=False)
    attempt_count = Column(Integer, nullable=False, server_default=text("0"))
    manual_retry_count = Column(Integer, nullable=False, server_default=text("0"))
    max_attempts = Column(Integer, nullable=False, server_default=text("3"))
    available_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deadline_at = Column(DateTime(timezone=True), nullable=False)
    worker_id = Column(String(128), nullable=True)
    claim_token = Column(String(64), nullable=True)
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_requested_at = Column(DateTime(timezone=True), nullable=True)
    provider_call_started_at = Column(DateTime(timezone=True), nullable=True)
    retrieval_completed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    estimated_input_tokens = Column(Integer, nullable=False, server_default=text("0"))
    estimated_output_tokens = Column(Integer, nullable=False, server_default=text("0"))
    actual_input_tokens = Column(Integer, nullable=True)
    actual_output_tokens = Column(Integer, nullable=True)
    provider_request_count = Column(Integer, nullable=False, server_default=text("0"))
    provider_retry_count = Column(Integer, nullable=False, server_default=text("0"))
    provider_rate_limit_wait_milliseconds = Column(BigInteger, nullable=False, server_default=text("0"))
    estimated_cost_microusd = Column(BigInteger, nullable=True)
    actual_cost_microusd = Column(BigInteger, nullable=True)
    usage_estimated = Column(Boolean, nullable=False, server_default=text("false"))
    support_rejection_count = Column(Integer, nullable=False, server_default=text("0"))
    error_code = Column(String(64), nullable=True)
    error_message = Column(String(500), nullable=True)
    error_retryable = Column(Boolean, nullable=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["thread_id", "user_id", "subject_id"],
            ["rag_threads.id", "rag_threads.user_id", "rag_threads.subject_id"],
            ondelete="CASCADE",
            name="fk_rag_answer_jobs_thread_scope",
        ),
        ForeignKeyConstraint(
            ["auth_session_id", "user_id"],
            ["auth_sessions.id", "auth_sessions.user_id"],
            ondelete="CASCADE",
            name="fk_rag_answer_jobs_auth_session",
        ),
        ForeignKeyConstraint(
            ["question_message_id", "thread_id", "user_id", "subject_id"],
            ["rag_messages.id", "rag_messages.thread_id", "rag_messages.user_id", "rag_messages.subject_id"],
            ondelete="CASCADE",
            name="fk_rag_answer_jobs_question_scope",
        ),
        ForeignKeyConstraint(
            ["answer_message_id", "thread_id", "user_id", "subject_id"],
            ["rag_messages.id", "rag_messages.thread_id", "rag_messages.user_id", "rag_messages.subject_id"],
            name="fk_rag_answer_jobs_answer_scope",
        ),
        UniqueConstraint("question_message_id", name="uq_rag_answer_jobs_question"),
        UniqueConstraint("answer_message_id", name="uq_rag_answer_jobs_answer"),
        UniqueConstraint("user_id", "operation_key_hash", name="uq_rag_answer_jobs_operation"),
        CheckConstraint("status IN ('queued','running','completed','failed','cancelled')", name="ck_rag_answer_jobs_status"),
        CheckConstraint(
            "length(operation_key_hash) = 64 AND length(request_fingerprint) = 64 "
            "AND corpus_revision >= 0 AND length(embedding_space_hash) = 64 "
            "AND length(trim(retrieval_policy)) BETWEEN 1 AND 64 "
            "AND length(trim(ai_provider)) BETWEEN 1 AND 32 "
            "AND length(trim(ai_base_url)) BETWEEN 1 AND 512 "
            "AND length(trim(ai_model)) BETWEEN 1 AND 128",
            name="ck_rag_answer_jobs_identity",
        ),
        CheckConstraint(
            "jsonb_typeof(document_ids) = 'array' AND jsonb_array_length(document_ids) <= 50",
            name="ck_rag_answer_jobs_documents",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint(
            "attempt_count BETWEEN 0 AND max_attempts AND max_attempts BETWEEN 1 AND 10 "
            "AND manual_retry_count BETWEEN 0 AND 10",
            name="ck_rag_answer_jobs_attempts",
        ),
        CheckConstraint(
            "estimated_input_tokens >= 0 AND estimated_output_tokens >= 0 "
            "AND (actual_input_tokens IS NULL OR actual_input_tokens >= 0) "
            "AND (actual_output_tokens IS NULL OR actual_output_tokens >= 0) "
            "AND provider_request_count >= 0 AND provider_retry_count >= 0 "
            "AND provider_retry_count <= provider_request_count "
            "AND provider_rate_limit_wait_milliseconds >= 0 "
            "AND (estimated_cost_microusd IS NULL OR estimated_cost_microusd >= 0) "
            "AND (actual_cost_microusd IS NULL OR actual_cost_microusd >= 0) "
            "AND support_rejection_count >= 0",
            name="ck_rag_answer_jobs_telemetry",
        ),
        CheckConstraint(
            "status <> 'running' OR (worker_id IS NOT NULL AND claim_token IS NOT NULL "
            "AND attempt_count >= 1 AND length(trim(worker_id)) BETWEEN 1 AND 128 "
            "AND length(claim_token) = 64 AND heartbeat_at IS NOT NULL "
            "AND lease_expires_at IS NOT NULL AND heartbeat_at <= lease_expires_at "
            "AND lease_expires_at <= deadline_at)",
            name="ck_rag_answer_jobs_running_claim",
        ),
        CheckConstraint(
            "(status IN ('completed','failed','cancelled') AND completed_at IS NOT NULL) OR "
            "(status IN ('queued','running') AND completed_at IS NULL)",
            name="ck_rag_answer_jobs_terminal",
        ),
        CheckConstraint(
            "(status = 'completed' AND answer_message_id IS NOT NULL AND error_code IS NULL) OR "
            "(status <> 'completed' AND answer_message_id IS NULL)",
            name="ck_rag_answer_jobs_result",
        ),
        CheckConstraint(ANSWER_ERROR_PAIRS, name="ck_rag_answer_jobs_error_pair"),
        CheckConstraint("available_at <= deadline_at AND created_at <= deadline_at", name="ck_rag_answer_jobs_deadline"),
        Index("ix_rag_answer_jobs_queue", "available_at", "created_at", "id",
              postgresql_where=text("status = 'queued'")),
        Index("ix_rag_answer_jobs_running_lease", "lease_expires_at", "id",
              postgresql_where=text("status = 'running'")),
        Index("ix_rag_answer_jobs_owner_created", "user_id", "subject_id", "created_at", "id"),
        Index("ix_rag_answer_jobs_thread_created", "thread_id", "created_at", "id"),
        Index("ix_rag_answer_jobs_auth_session", "auth_session_id", "id"),
    )


class RagAnswerQuotaEvent(Base):
    __tablename__ = "rag_answer_quota_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("rag_answer_jobs.id", ondelete="SET NULL"), nullable=True)
    operation_key_hash = Column(String(64), nullable=False)
    job_units = Column(Integer, nullable=False, server_default=text("1"))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "operation_key_hash", name="uq_rag_answer_quota_operation"),
        CheckConstraint("length(operation_key_hash) = 64", name="ck_rag_answer_quota_key_hash"),
        CheckConstraint("job_units = 1", name="ck_rag_answer_quota_job_units"),
        Index("ix_rag_answer_quota_user_created", "user_id", "created_at"),
        Index("ix_rag_answer_quota_created", "created_at"),
        Index("ix_rag_answer_quota_job", "job_id"),
    )


__all__ = [
    "RagAnswerJob",
    "RagAnswerQuotaEvent",
    "RagMessage",
    "RagMessageSource",
    "RagThread",
]
