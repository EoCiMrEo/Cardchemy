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
    Float,
    Index,
    Integer,
    JSON,
    PrimaryKeyConstraint,
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
    "(error_code = 'rag_ask_shutdown' AND error_message = 'Ask AI was paused before this answer completed.') OR "
    "(error_code = 'rag_access_revoked' AND error_message = 'Subject access is no longer available.') OR "
    "(error_code = 'rag_corpus_changed' AND error_message = 'Course materials changed before the answer completed.') OR "
    "(error_code = 'rag_profile_mismatch' AND error_message = 'Ask AI configuration changed before execution.') OR "
    "(error_code = 'rag_question_context_changed' AND error_message = 'The question context changed or expired. Start a new search.')))"
)


# Exact PostgreSQL checks and equally strict SQLite test equivalents.
QUESTION_CONTEXT_JOB_CHECK = "(answer_policy_version IS NOT NULL AND answer_policy_version = 'related_knowledge_navigation_v7' AND source_context_policy_version IS NOT NULL AND source_context_policy_version = 'literal_subject_admission_v1' AND source_context_admission_sha256 IS NOT NULL AND source_context_admission_sha256 ~ '^[0-9a-f]{64}$') OR (answer_policy_version IS NOT NULL AND answer_policy_version = 'related_knowledge_navigation_v8' AND source_context_policy_version IS NOT NULL AND source_context_policy_version = 'literal_subject_admission_v2' AND source_context_admission_sha256 IS NOT NULL AND source_context_admission_sha256 ~ '^[0-9a-f]{64}$') OR ((answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_navigation_v7','related_knowledge_navigation_v8')) AND source_context_policy_version IS NULL AND source_context_admission_sha256 IS NULL)"
QUESTION_CONTEXT_SHAPE_CHECK = "context_version IN ('literal_subject_admission_v1','literal_subject_admission_v2') AND current_question_sha256 ~ '^[0-9a-f]{64}$' AND admission_sha256 ~ '^[0-9a-f]{64}$' AND current_created_at <= captured_at AND current_expires_at > captured_at AND current_expires_at > current_created_at AND ((preceding_message_id IS NULL AND preceding_question_sha256 IS NULL AND preceding_created_at IS NULL AND preceding_expires_at IS NULL) OR (preceding_message_id IS NOT NULL AND preceding_question_sha256 IS NOT NULL AND preceding_created_at IS NOT NULL AND preceding_expires_at IS NOT NULL AND preceding_message_id <> current_message_id AND preceding_question_sha256 ~ '^[0-9a-f]{64}$' AND preceding_created_at < current_created_at AND preceding_expires_at > captured_at AND preceding_expires_at > preceding_created_at)) AND ((subject_start_offset IS NULL AND subject_end_offset IS NULL AND subject_start_byte_offset IS NULL AND subject_end_byte_offset IS NULL AND subject_sha256 IS NULL) OR (subject_start_offset IS NOT NULL AND subject_end_offset IS NOT NULL AND subject_start_byte_offset IS NOT NULL AND subject_end_byte_offset IS NOT NULL AND subject_sha256 IS NOT NULL AND preceding_message_id IS NOT NULL AND preceding_question_sha256 IS NOT NULL AND preceding_created_at IS NOT NULL AND preceding_expires_at IS NOT NULL AND subject_start_offset >= 0 AND subject_end_offset > subject_start_offset AND subject_end_offset - subject_start_offset <= 160 AND subject_start_byte_offset >= 0 AND subject_end_byte_offset > subject_start_byte_offset AND subject_end_byte_offset - subject_start_byte_offset <= 640 AND subject_sha256 ~ '^[0-9a-f]{64}$')) AND (NOT raw_question_clear OR (preceding_message_id IS NULL AND preceding_question_sha256 IS NULL AND preceding_created_at IS NULL AND preceding_expires_at IS NULL AND subject_start_offset IS NULL AND subject_end_offset IS NULL AND subject_start_byte_offset IS NULL AND subject_end_byte_offset IS NULL AND subject_sha256 IS NULL))"
QUESTION_CONTEXT_JOB_SQLITE_CHECK = "(answer_policy_version IS NOT NULL AND answer_policy_version = 'related_knowledge_navigation_v7' AND source_context_policy_version IS NOT NULL AND source_context_policy_version = 'literal_subject_admission_v1' AND source_context_admission_sha256 IS NOT NULL AND (length(source_context_admission_sha256) = 64 AND replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(source_context_admission_sha256,'0',''),'1',''),'2',''),'3',''),'4',''),'5',''),'6',''),'7',''),'8',''),'9',''),'a',''),'b',''),'c',''),'d',''),'e',''),'f','') = '')) OR (answer_policy_version IS NOT NULL AND answer_policy_version = 'related_knowledge_navigation_v8' AND source_context_policy_version IS NOT NULL AND source_context_policy_version = 'literal_subject_admission_v2' AND source_context_admission_sha256 IS NOT NULL AND (length(source_context_admission_sha256) = 64 AND replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(source_context_admission_sha256,'0',''),'1',''),'2',''),'3',''),'4',''),'5',''),'6',''),'7',''),'8',''),'9',''),'a',''),'b',''),'c',''),'d',''),'e',''),'f','') = '')) OR ((answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_navigation_v7','related_knowledge_navigation_v8')) AND source_context_policy_version IS NULL AND source_context_admission_sha256 IS NULL)"
QUESTION_CONTEXT_SHAPE_SQLITE_CHECK = "context_version IN ('literal_subject_admission_v1','literal_subject_admission_v2') AND (length(current_question_sha256) = 64 AND replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(current_question_sha256,'0',''),'1',''),'2',''),'3',''),'4',''),'5',''),'6',''),'7',''),'8',''),'9',''),'a',''),'b',''),'c',''),'d',''),'e',''),'f','') = '') AND (length(admission_sha256) = 64 AND replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(admission_sha256,'0',''),'1',''),'2',''),'3',''),'4',''),'5',''),'6',''),'7',''),'8',''),'9',''),'a',''),'b',''),'c',''),'d',''),'e',''),'f','') = '') AND current_created_at <= captured_at AND current_expires_at > captured_at AND current_expires_at > current_created_at AND ((preceding_message_id IS NULL AND preceding_question_sha256 IS NULL AND preceding_created_at IS NULL AND preceding_expires_at IS NULL) OR (preceding_message_id IS NOT NULL AND preceding_question_sha256 IS NOT NULL AND preceding_created_at IS NOT NULL AND preceding_expires_at IS NOT NULL AND preceding_message_id <> current_message_id AND (length(preceding_question_sha256) = 64 AND replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(preceding_question_sha256,'0',''),'1',''),'2',''),'3',''),'4',''),'5',''),'6',''),'7',''),'8',''),'9',''),'a',''),'b',''),'c',''),'d',''),'e',''),'f','') = '') AND preceding_created_at < current_created_at AND preceding_expires_at > captured_at AND preceding_expires_at > preceding_created_at)) AND ((subject_start_offset IS NULL AND subject_end_offset IS NULL AND subject_start_byte_offset IS NULL AND subject_end_byte_offset IS NULL AND subject_sha256 IS NULL) OR (subject_start_offset IS NOT NULL AND subject_end_offset IS NOT NULL AND subject_start_byte_offset IS NOT NULL AND subject_end_byte_offset IS NOT NULL AND subject_sha256 IS NOT NULL AND preceding_message_id IS NOT NULL AND preceding_question_sha256 IS NOT NULL AND preceding_created_at IS NOT NULL AND preceding_expires_at IS NOT NULL AND subject_start_offset >= 0 AND subject_end_offset > subject_start_offset AND subject_end_offset - subject_start_offset <= 160 AND subject_start_byte_offset >= 0 AND subject_end_byte_offset > subject_start_byte_offset AND subject_end_byte_offset - subject_start_byte_offset <= 640 AND (length(subject_sha256) = 64 AND replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(subject_sha256,'0',''),'1',''),'2',''),'3',''),'4',''),'5',''),'6',''),'7',''),'8',''),'9',''),'a',''),'b',''),'c',''),'d',''),'e',''),'f','') = ''))) AND (NOT raw_question_clear OR (preceding_message_id IS NULL AND preceding_question_sha256 IS NULL AND preceding_created_at IS NULL AND preceding_expires_at IS NULL AND subject_start_offset IS NULL AND subject_end_offset IS NULL AND subject_start_byte_offset IS NULL AND subject_end_byte_offset IS NULL AND subject_sha256 IS NULL))"


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
    abstention_kind = Column(String(32), nullable=True)
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
            "abstention_kind IS NULL OR (role = 'assistant' AND outcome = 'abstained' "
            "AND abstention_kind IN ('retrieval_insufficient','model_abstained','support_rejected'))",
            name="ck_rag_messages_abstention_kind",
        ),
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
    embedding_provider = Column(String(32), nullable=True)
    embedding_base_url = Column(String(512), nullable=True)
    embedding_model = Column(String(128), nullable=True)
    ai_provider = Column(String(32), nullable=True)
    ai_base_url = Column(String(512), nullable=True)
    ai_model = Column(String(128), nullable=True)
    ai_catalog_version = Column(String(64), nullable=True)
    ai_schema_policy_version = Column(String(64), nullable=True)
    # V4 source selection is a distinct provider role. These immutable
    # admission snapshots never reuse retired answer-model columns.
    source_judge_provider = Column(String(32), nullable=True)
    source_judge_base_url = Column(String(512), nullable=True)
    source_judge_model = Column(String(128), nullable=True)
    source_judge_contract_version = Column(String(64), nullable=True)
    source_judge_input_price_microusd_per_million = Column(BigInteger, nullable=True)
    source_judge_output_price_microusd_per_million = Column(BigInteger, nullable=True)
    source_judge_max_input_tokens = Column(Integer, nullable=True)
    source_judge_max_output_tokens = Column(Integer, nullable=True)
    # V5 alone snapshots visual thinking and the physical request deadline.
    source_judge_thinking_level = Column(String(16), nullable=True)
    source_judge_timeout_seconds = Column(Float, nullable=True)
    source_context_policy_version = Column(String(64), nullable=True)
    source_context_admission_sha256 = Column(String(64), nullable=True)
    answer_policy_version = Column(String(64), nullable=True)
    support_policy_version = Column(String(64), nullable=True)
    result_kind = Column(String(32), nullable=True)
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
    attempt_cost_microusd = Column(BigInteger, nullable=False, server_default=text("0"))
    attempt_cost_unknown = Column(Boolean, nullable=False, server_default=text("false"))
    usage_estimated = Column(Boolean, nullable=False, server_default=text("false"))
    support_rejection_count = Column(Integer, nullable=False, server_default=text("0"))
    error_code = Column(String(64), nullable=True)
    error_message = Column(String(500), nullable=True)
    error_retryable = Column(Boolean, nullable=False, server_default=text("false"))
    failed_stage = Column(String(32), nullable=True)
    provider_error_category = Column(String(64), nullable=True)
    failure_reason = Column(String(64), nullable=True)
    execution_uncertain = Column(Boolean, nullable=False, server_default=text("false"))
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
        UniqueConstraint("id", "thread_id", "user_id", "subject_id", name="uq_rag_answer_jobs_scope"),
        UniqueConstraint("user_id", "operation_key_hash", name="uq_rag_answer_jobs_operation"),
        CheckConstraint("status IN ('queued','running','completed','failed','cancelled')", name="ck_rag_answer_jobs_status"),
        CheckConstraint(
            "length(operation_key_hash) = 64 AND length(request_fingerprint) = 64 AND corpus_revision >= 0 AND length(embedding_space_hash) = 64 AND length(trim(retrieval_policy)) BETWEEN 1 AND 64 AND ((answer_policy_version IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3','related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6','related_knowledge_navigation_v7','related_knowledge_navigation_v8') AND ai_provider IS NULL AND ai_base_url IS NULL AND ai_model IS NULL AND support_policy_version IS NULL AND embedding_provider IS NOT NULL AND embedding_base_url IS NOT NULL AND embedding_model IS NOT NULL AND length(trim(embedding_provider)) BETWEEN 1 AND 32 AND length(trim(embedding_base_url)) BETWEEN 1 AND 512 AND length(trim(embedding_model)) BETWEEN 1 AND 128) OR ((answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3','related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6','related_knowledge_navigation_v7','related_knowledge_navigation_v8')) AND embedding_provider IS NULL AND embedding_base_url IS NULL AND embedding_model IS NULL AND ai_provider IS NOT NULL AND ai_base_url IS NOT NULL AND ai_model IS NOT NULL AND length(trim(ai_provider)) BETWEEN 1 AND 32 AND length(trim(ai_base_url)) BETWEEN 1 AND 512 AND length(trim(ai_model)) BETWEEN 1 AND 128))",
            name="ck_rag_answer_jobs_identity",
        ),
        CheckConstraint(
            "(answer_policy_version IS NOT NULL AND answer_policy_version = 'related_knowledge_navigation_v4' AND ai_catalog_version IS NULL AND ai_schema_policy_version IS NULL AND source_judge_provider IS NOT NULL AND source_judge_provider = 'gemini' AND source_judge_base_url IS NOT NULL AND source_judge_model IS NOT NULL AND source_judge_contract_version IS NOT NULL AND source_judge_input_price_microusd_per_million IS NOT NULL AND source_judge_output_price_microusd_per_million IS NOT NULL AND source_judge_max_input_tokens IS NOT NULL AND source_judge_max_output_tokens IS NOT NULL AND length(trim(source_judge_base_url)) BETWEEN 1 AND 512 AND length(trim(source_judge_model)) BETWEEN 1 AND 128 AND length(trim(source_judge_contract_version)) BETWEEN 1 AND 64 AND source_judge_input_price_microusd_per_million > 0 AND source_judge_output_price_microusd_per_million > 0 AND source_judge_max_input_tokens BETWEEN 1 AND 8192 AND source_judge_max_output_tokens BETWEEN 1 AND 1024 AND source_judge_thinking_level IS NULL AND source_judge_timeout_seconds IS NULL) OR (answer_policy_version IS NOT NULL AND answer_policy_version = 'related_knowledge_navigation_v5' AND ai_catalog_version IS NULL AND ai_schema_policy_version IS NULL AND source_judge_provider IS NOT NULL AND source_judge_provider = 'gemini' AND source_judge_base_url IS NOT NULL AND source_judge_base_url = 'https://generativelanguage.googleapis.com' AND source_judge_model IS NOT NULL AND source_judge_model = 'gemini-3.5-flash-lite' AND source_judge_contract_version IS NOT NULL AND source_judge_contract_version = 'visual_source_id_v1' AND source_judge_input_price_microusd_per_million IS NOT NULL AND source_judge_input_price_microusd_per_million >= 300000 AND source_judge_output_price_microusd_per_million IS NOT NULL AND source_judge_output_price_microusd_per_million >= 2500000 AND source_judge_max_input_tokens IS NOT NULL AND source_judge_max_input_tokens BETWEEN 1 AND 32768 AND source_judge_max_output_tokens IS NOT NULL AND source_judge_max_output_tokens BETWEEN 1 AND 2048 AND source_judge_thinking_level IS NOT NULL AND source_judge_thinking_level = 'high' AND source_judge_timeout_seconds IS NOT NULL AND source_judge_timeout_seconds BETWEEN 1 AND 60) OR (answer_policy_version IS NOT NULL AND answer_policy_version = 'related_knowledge_navigation_v6' AND ai_catalog_version IS NULL AND ai_schema_policy_version IS NULL AND source_judge_provider IS NOT NULL AND source_judge_provider = 'gemini' AND source_judge_base_url IS NOT NULL AND source_judge_base_url = 'https://generativelanguage.googleapis.com' AND source_judge_model IS NOT NULL AND source_judge_model = 'gemini-3.5-flash-lite' AND source_judge_contract_version IS NOT NULL AND source_judge_contract_version = 'visual_source_id_v2' AND source_judge_input_price_microusd_per_million IS NOT NULL AND source_judge_input_price_microusd_per_million >= 300000 AND source_judge_output_price_microusd_per_million IS NOT NULL AND source_judge_output_price_microusd_per_million >= 2500000 AND source_judge_max_input_tokens IS NOT NULL AND source_judge_max_input_tokens BETWEEN 1 AND 32768 AND source_judge_max_output_tokens IS NOT NULL AND source_judge_max_output_tokens BETWEEN 1 AND 4096 AND source_judge_thinking_level IS NOT NULL AND source_judge_thinking_level = 'high' AND source_judge_timeout_seconds IS NOT NULL AND source_judge_timeout_seconds BETWEEN 1 AND 60) OR (answer_policy_version IS NOT NULL AND answer_policy_version = 'related_knowledge_navigation_v7' AND ai_catalog_version IS NULL AND ai_schema_policy_version IS NULL AND source_judge_provider IS NOT NULL AND source_judge_provider = 'gemini' AND source_judge_base_url IS NOT NULL AND source_judge_base_url = 'https://generativelanguage.googleapis.com' AND source_judge_model IS NOT NULL AND source_judge_model = 'gemini-3.5-flash-lite' AND source_judge_contract_version IS NOT NULL AND source_judge_contract_version = 'visual_source_id_v3' AND source_judge_input_price_microusd_per_million IS NOT NULL AND source_judge_input_price_microusd_per_million >= 300000 AND source_judge_output_price_microusd_per_million IS NOT NULL AND source_judge_output_price_microusd_per_million >= 2500000 AND source_judge_max_input_tokens IS NOT NULL AND source_judge_max_input_tokens BETWEEN 1 AND 32768 AND source_judge_max_output_tokens IS NOT NULL AND source_judge_max_output_tokens BETWEEN 1 AND 4096 AND source_judge_thinking_level IS NOT NULL AND source_judge_thinking_level = 'high' AND source_judge_timeout_seconds IS NOT NULL AND source_judge_timeout_seconds BETWEEN 1 AND 120) OR (answer_policy_version IS NOT NULL AND answer_policy_version = 'related_knowledge_navigation_v8' AND ai_catalog_version IS NULL AND ai_schema_policy_version IS NULL AND source_judge_provider IS NOT NULL AND source_judge_provider = 'gemini' AND source_judge_base_url IS NOT NULL AND source_judge_base_url = 'https://generativelanguage.googleapis.com' AND source_judge_model IS NOT NULL AND source_judge_model = 'gemini-3.5-flash-lite' AND source_judge_contract_version IS NOT NULL AND source_judge_contract_version = 'visual_source_id_v5' AND source_judge_input_price_microusd_per_million IS NOT NULL AND source_judge_input_price_microusd_per_million >= 300000 AND source_judge_output_price_microusd_per_million IS NOT NULL AND source_judge_output_price_microusd_per_million >= 2500000 AND source_judge_max_input_tokens IS NOT NULL AND source_judge_max_input_tokens BETWEEN 1 AND 32768 AND source_judge_max_output_tokens IS NOT NULL AND source_judge_max_output_tokens BETWEEN 1 AND 4096 AND source_judge_thinking_level IS NOT NULL AND source_judge_thinking_level = 'high' AND source_judge_timeout_seconds IS NOT NULL AND source_judge_timeout_seconds BETWEEN 1 AND 120) OR ((answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6','related_knowledge_navigation_v7','related_knowledge_navigation_v8')) AND source_judge_provider IS NULL AND source_judge_base_url IS NULL AND source_judge_model IS NULL AND source_judge_contract_version IS NULL AND source_judge_input_price_microusd_per_million IS NULL AND source_judge_output_price_microusd_per_million IS NULL AND source_judge_max_input_tokens IS NULL AND source_judge_max_output_tokens IS NULL AND source_judge_thinking_level IS NULL AND source_judge_timeout_seconds IS NULL)",
            name="ck_rag_answer_jobs_source_judge_snapshot",
        ),
        CheckConstraint(
            "answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6','related_knowledge_navigation_v7','related_knowledge_navigation_v8') OR retrieval_policy = 'hybrid_source_navigation_v9'",
            name="ck_rag_answer_jobs_source_judge_retrieval_pair",
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
            "(answer_policy_version IS NULL OR length(trim(answer_policy_version)) BETWEEN 1 AND 64) "
            "AND (support_policy_version IS NULL OR length(trim(support_policy_version)) BETWEEN 1 AND 64) "
            "AND attempt_cost_microusd >= 0",
            name="ck_rag_answer_jobs_local_policy",
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
            "(status = 'completed' AND answer_policy_version IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3') AND result_kind IN ('related_knowledge','no_match') AND answer_message_id IS NULL AND error_code IS NULL) OR (status = 'completed' AND answer_policy_version IN ('related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6','related_knowledge_navigation_v7','related_knowledge_navigation_v8') AND result_kind IN ('related_knowledge','no_match','clarification_needed') AND answer_message_id IS NULL AND error_code IS NULL) OR (status = 'completed' AND (answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3','related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6','related_knowledge_navigation_v7','related_knowledge_navigation_v8')) AND result_kind IS NULL AND answer_message_id IS NOT NULL AND error_code IS NULL) OR (status <> 'completed' AND result_kind IS NULL AND answer_message_id IS NULL)",
            name="ck_rag_answer_jobs_result",
        ),
        CheckConstraint(QUESTION_CONTEXT_JOB_CHECK, name="ck_rag_answer_jobs_source_context_snapshot").ddl_if(dialect="postgresql"),
        CheckConstraint(QUESTION_CONTEXT_JOB_SQLITE_CHECK, name="ck_rag_answer_jobs_source_context_snapshot_sqlite").ddl_if(dialect="sqlite"),
        CheckConstraint(ANSWER_ERROR_PAIRS, name="ck_rag_answer_jobs_error_pair"),
        CheckConstraint(
            "failure_reason IS NULL OR failure_reason IN ("
            "'transport_timeout','transport_protocol','transport_network',"
            "'http_invalid_request','http_authentication','http_access_denied',"
            "'http_model_missing','http_rate_limited','http_server_error',"
            "'http_transient','http_rejected','sdk_unclassified',"
            "'output_empty','output_blocked','output_unfinished','json_invalid',"
            "'schema_invalid','citation_invalid','answer_too_long',"
            "'retrieval_failed','retrieval_timeout','local_support_unavailable',"
            "'local_support_timeout','rag_access_revoked','rag_corpus_changed',"
            "'internal_failure')",
            name="ck_rag_answer_jobs_failure_reason",
        ),
        CheckConstraint("available_at <= deadline_at AND created_at <= deadline_at", name="ck_rag_answer_jobs_deadline"),
        Index("ix_rag_answer_jobs_queue", "available_at", "created_at", "id",
              postgresql_where=text("status = 'queued'")),
        Index("ix_rag_answer_jobs_running_lease", "lease_expires_at", "id",
              postgresql_where=text("status = 'running'")),
        Index("ix_rag_answer_jobs_owner_created", "user_id", "subject_id", "created_at", "id"),
        Index("ix_rag_answer_jobs_thread_created", "thread_id", "created_at", "id"),
        Index("ix_rag_answer_jobs_auth_session", "auth_session_id", "id"),
    )


class RagAnswerQuestionContext(Base):
    """Immutable metadata-only v7 admission binding, with retention-safe FKs.

    Deleting a predecessor removes its binding, preserving the newer job.
    PostgreSQL 0032 additionally validates actual message bytes, ordering and
    deferred atomic admission; completed reference reads need no context row.
    """

    __tablename__ = "rag_answer_question_context"
    job_id = Column(UUID(as_uuid=True), primary_key=True)
    thread_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    subject_id = Column(UUID(as_uuid=True), nullable=False)
    current_message_id = Column(UUID(as_uuid=True), nullable=False)
    context_version = Column(String(64), nullable=False)
    raw_question_clear = Column(Boolean, nullable=False)
    current_question_sha256 = Column(String(64), nullable=False)
    current_created_at = Column(DateTime(timezone=True), nullable=False)
    current_expires_at = Column(DateTime(timezone=True), nullable=False)
    captured_at = Column(DateTime(timezone=True), nullable=False)
    admission_sha256 = Column(String(64), nullable=False)
    preceding_message_id = Column(UUID(as_uuid=True), nullable=True)
    preceding_question_sha256 = Column(String(64), nullable=True)
    preceding_created_at = Column(DateTime(timezone=True), nullable=True)
    preceding_expires_at = Column(DateTime(timezone=True), nullable=True)
    subject_start_offset = Column(Integer, nullable=True)
    subject_end_offset = Column(Integer, nullable=True)
    subject_start_byte_offset = Column(Integer, nullable=True)
    subject_end_byte_offset = Column(Integer, nullable=True)
    subject_sha256 = Column(String(64), nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("job_id", name="pk_rag_answer_question_context"),
        ForeignKeyConstraint(
            ['job_id', 'thread_id', 'user_id', 'subject_id'],
            ['rag_answer_jobs.id', 'rag_answer_jobs.thread_id', 'rag_answer_jobs.user_id', 'rag_answer_jobs.subject_id'],
            ondelete="CASCADE", name="fk_rag_question_context_job_scope",
        ),
        ForeignKeyConstraint(
            ['current_message_id', 'thread_id', 'user_id', 'subject_id'],
            ['rag_messages.id', 'rag_messages.thread_id', 'rag_messages.user_id', 'rag_messages.subject_id'],
            ondelete="CASCADE", name="fk_rag_question_context_current_scope",
        ),
        ForeignKeyConstraint(
            ['preceding_message_id', 'thread_id', 'user_id', 'subject_id'],
            ['rag_messages.id', 'rag_messages.thread_id', 'rag_messages.user_id', 'rag_messages.subject_id'],
            ondelete="CASCADE", name="fk_rag_question_context_preceding_scope",
        ),
        CheckConstraint(QUESTION_CONTEXT_SHAPE_CHECK, name="ck_rag_question_context_shape").ddl_if(dialect="postgresql"),
        CheckConstraint(QUESTION_CONTEXT_SHAPE_SQLITE_CHECK, name="ck_rag_question_context_shape_sqlite").ddl_if(dialect="sqlite"),
        Index("ix_rag_question_context_preceding", "preceding_message_id", "job_id"),
    )


class RagRelatedEvidence(Base):
    """At most three exact source slices for one private Ask job's current attempt.

    The source kind binds offsets to immutable chunk or canonical page content.
    The eligible chunk remains the discovery anchor in either case. References
    copy no source text and are reauthorized before any response is served.
    For v4, the database insertion trigger also requires a successful source
    judgment stage from the job's current worker attempt; this cross-table
    rule cannot be expressed as a row-level CheckConstraint here.
    """

    __tablename__ = "rag_related_evidence"

    job_id = Column(UUID(as_uuid=True), primary_key=True)
    excerpt_order = Column(Integer, primary_key=True)
    bundle_size = Column(Integer, nullable=False)
    thread_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    subject_id = Column(UUID(as_uuid=True), nullable=False)
    chunk_id = Column(UUID(as_uuid=True), nullable=False)
    document_id = Column(UUID(as_uuid=True), nullable=False)
    content_revision_id = Column(UUID(as_uuid=True), nullable=False)
    index_revision_id = Column(UUID(as_uuid=True), nullable=False)
    source_kind = Column(String(24), nullable=False, default="chunk", server_default=text("'chunk'"))
    start_offset = Column(Integer, nullable=False)
    end_offset = Column(Integer, nullable=False)
    manual_retry_number = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "thread_id", "user_id", "subject_id"],
            ["rag_answer_jobs.id", "rag_answer_jobs.thread_id", "rag_answer_jobs.user_id", "rag_answer_jobs.subject_id"],
            ondelete="CASCADE",
            name="fk_rag_related_evidence_job_scope",
        ),
        ForeignKeyConstraint(
            ["chunk_id", "index_revision_id", "content_revision_id", "document_id", "subject_id"],
            ["subject_document_chunks.id", "subject_document_chunks.index_revision_id",
             "subject_document_chunks.content_revision_id", "subject_document_chunks.document_id",
             "subject_document_chunks.subject_id"],
            ondelete="CASCADE",
            name="fk_rag_related_evidence_chunk_scope",
        ),
        UniqueConstraint("job_id", "chunk_id", name="uq_rag_related_evidence_chunk"),
        CheckConstraint("excerpt_order BETWEEN 1 AND 3", name="ck_rag_related_evidence_order"),
        CheckConstraint("bundle_size BETWEEN 1 AND 3 AND excerpt_order <= bundle_size", name="ck_rag_related_evidence_bundle"),
        CheckConstraint("source_kind IN ('chunk','canonical_page')", name="ck_rag_related_evidence_source_kind"),
        CheckConstraint(
            "start_offset >= 0 AND end_offset > start_offset AND end_offset - start_offset <= 480",
            name="ck_rag_related_evidence_offsets",
        ),
        CheckConstraint("manual_retry_number BETWEEN 0 AND 10", name="ck_rag_related_evidence_retry"),
        CheckConstraint("expires_at > created_at", name="ck_rag_related_evidence_expiry"),
        Index("ix_rag_related_evidence_owner_expiry", "user_id", "expires_at", "job_id"),
    )


class RagAnswerStageAttempt(Base):
    """Content-free timing and physical-call accounting for one job stage.

    PostgreSQL migration 0023 binds source-only stage policy and attempt numbers
    to the parent job before these row-level caps/unique indexes are evaluated.
    """

    __tablename__ = "rag_answer_stage_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    job_id = Column(UUID(as_uuid=True), ForeignKey("rag_answer_jobs.id", ondelete="CASCADE"), nullable=False)
    manual_retry_number = Column(Integer, nullable=False)
    worker_attempt_number = Column(Integer, nullable=False)
    stage = Column(String(32), nullable=False)
    answer_policy_version = Column(String(64), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    elapsed_milliseconds = Column(BigInteger, nullable=True)
    physical_request_count = Column(Integer, nullable=False, server_default=text("0"))
    retry_count = Column(Integer, nullable=False, server_default=text("0"))
    rate_limit_wait_milliseconds = Column(BigInteger, nullable=False, server_default=text("0"))
    error_category = Column(String(64), nullable=True)
    failure_reason = Column(String(64), nullable=True)
    provider_finish_reason = Column(String(32), nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    usage_estimated = Column(Boolean, nullable=True)
    retrieval_ranks = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    support_reason = Column(String(64), nullable=True)
    support_entailment = Column(String(16), nullable=True)
    support_question_relevance = Column(String(16), nullable=True)
    support_equivalence = Column(String(16), nullable=True)
    support_contradiction = Column(String(16), nullable=True)
    execution_uncertain = Column(Boolean, nullable=False, server_default=text("false"))

    __table_args__ = (
        UniqueConstraint("job_id", "manual_retry_number", "worker_attempt_number", "stage", name="uq_rag_answer_stage_attempt"),
        CheckConstraint("manual_retry_number BETWEEN 0 AND 10 AND worker_attempt_number BETWEEN 1 AND 10", name="ck_rag_answer_stage_attempt_numbers"),
        CheckConstraint("stage IN ('query_embedding','retrieval','source_judgment','answer','support','local_support')", name="ck_rag_answer_stage_name"),
        CheckConstraint(
            "stage <> 'source_judgment' OR (answer_policy_version IS NOT NULL AND answer_policy_version IN ('related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6','related_knowledge_navigation_v7','related_knowledge_navigation_v8'))",
            name="ck_rag_answer_stage_source_judgment_policy",
        ),
        CheckConstraint("physical_request_count >= 0 AND retry_count BETWEEN 0 AND physical_request_count AND rate_limit_wait_milliseconds >= 0 AND (elapsed_milliseconds IS NULL OR elapsed_milliseconds >= 0)", name="ck_rag_answer_stage_usage"),
        CheckConstraint(
            "(input_tokens IS NULL OR input_tokens >= 0) AND "
            "(output_tokens IS NULL OR output_tokens >= 0) AND "
            "(failure_reason IS NULL OR failure_reason IN ("
            "'transport_timeout','transport_protocol','transport_network',"
            "'http_invalid_request','http_authentication','http_access_denied',"
            "'http_model_missing','http_rate_limited','http_server_error',"
            "'http_transient','http_rejected','sdk_unclassified',"
            "'output_empty','output_blocked','output_unfinished','json_invalid',"
            "'schema_invalid','citation_invalid','answer_too_long',"
            "'retrieval_failed','retrieval_timeout','local_support_unavailable',"
            "'local_support_timeout','rag_access_revoked','rag_corpus_changed',"
            "'internal_failure')) AND "
            "(provider_finish_reason IS NULL OR provider_finish_reason IN ("
            "'FINISH_REASON_UNSPECIFIED','STOP','MAX_TOKENS','SAFETY','RECITATION',"
            "'LANGUAGE','OTHER','BLOCKLIST','PROHIBITED_CONTENT','SPII',"
            "'MALFORMED_FUNCTION_CALL','IMAGE_SAFETY','UNEXPECTED_TOOL_CALL',"
            "'IMAGE_PROHIBITED_CONTENT','NO_IMAGE','IMAGE_RECITATION','IMAGE_OTHER'))",
            name="ck_rag_answer_stage_quality_usage",
        ),
        CheckConstraint(
            "support_reason IS NULL OR support_reason IN ("
            "'supported','missing_evidence','entailment_rejected',"
            "'question_relevance_rejected','equivalence_rejected',"
            "'contradiction_detected','support_rejected')",
            name="ck_rag_answer_stage_support_reason",
        ),
        CheckConstraint(
            "(support_entailment IS NULL OR support_entailment IN ('pass','fail','not_run')) AND "
            "(support_question_relevance IS NULL OR support_question_relevance IN ('pass','fail','not_run')) AND "
            "(support_equivalence IS NULL OR support_equivalence IN ('pass','fail','not_run','not_required')) AND "
            "(support_contradiction IS NULL OR support_contradiction IN ('pass','fail','not_run'))",
            name="ck_rag_answer_stage_support_checks",
        ),
        CheckConstraint(
            "retrieval_ranks IS NULL OR (jsonb_typeof(retrieval_ranks) = 'array' "
            "AND jsonb_array_length(retrieval_ranks) <= 5)",
            name="ck_rag_answer_stage_retrieval_ranks",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint(
            "answer_policy_version IS NULL OR answer_policy_version NOT IN "
            "('two_request_local_support_v1','two_request_local_support_v2') "
            "OR (stage IN ('query_embedding','retrieval','answer','local_support') "
            "AND retry_count = 0 AND ((stage IN ('query_embedding','answer') "
            "AND physical_request_count <= 1) OR (stage IN ('retrieval','local_support') "
            "AND physical_request_count = 0)))",
            name="ck_rag_answer_stage_two_request_cap",
        ),
        CheckConstraint(
            "answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3') "
            "OR (stage IN ('query_embedding','retrieval') AND retry_count = 0 "
            "AND ((stage = 'query_embedding' AND physical_request_count <= 1) "
            "OR (stage = 'retrieval' AND physical_request_count = 0)))",
            name="ck_rag_answer_stage_source_only_cap",
        ),
        CheckConstraint(
            "answer_policy_version IS NULL OR answer_policy_version <> 'related_knowledge_navigation_v4' "
            "OR (stage IN ('query_embedding','retrieval','source_judgment') AND retry_count = 0 "
            "AND ((stage IN ('query_embedding','source_judgment') AND physical_request_count <= 1) "
            "OR (stage = 'retrieval' AND physical_request_count = 0)))",
            name="ck_rag_answer_stage_source_judge_cap",
        ),
        CheckConstraint(
            "answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_navigation_v5','related_knowledge_navigation_v6','related_knowledge_navigation_v7','related_knowledge_navigation_v8') OR (stage IN ('query_embedding','retrieval','source_judgment') AND retry_count = 0 AND ((stage IN ('query_embedding','source_judgment') AND physical_request_count <= 1) OR (stage = 'retrieval' AND physical_request_count = 0)))",
            name="ck_rag_answer_stage_visual_judge_cap",
        ),
        Index(
            "uq_rag_answer_stage_visual_remote_attempt",
            "job_id", "manual_retry_number", "stage", unique=True,
            postgresql_where=text(
                "answer_policy_version IN ('related_knowledge_navigation_v5','related_knowledge_navigation_v6','related_knowledge_navigation_v7','related_knowledge_navigation_v8') "
                "AND stage IN ('query_embedding','source_judgment')"
            ),
        ),
        Index(
            "uq_rag_answer_stage_local_remote_attempt",
            "job_id", "manual_retry_number", "stage",
            unique=True,
            postgresql_where=text(
                "answer_policy_version IN "
                "('two_request_local_support_v1','two_request_local_support_v2') "
                "AND stage IN ('query_embedding','answer')"
            ),
        ),
        Index(
            "uq_rag_answer_stage_source_embedding_attempt",
            "job_id", "manual_retry_number", "stage", unique=True,
            postgresql_where=text(
                "answer_policy_version IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3') "
                "AND stage = 'query_embedding'"
            ),
        ),
        Index(
            "uq_rag_answer_stage_source_judge_remote_attempt",
            "job_id", "manual_retry_number", "stage", unique=True,
            postgresql_where=text(
                "answer_policy_version = 'related_knowledge_navigation_v4' "
                "AND stage IN ('query_embedding','source_judgment')"
            ),
        ),
        Index("ix_rag_answer_stage_attempt_job", "job_id", "manual_retry_number", "worker_attempt_number"),
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
    "RagAnswerQuestionContext",
    "RagRelatedEvidence",
    "RagAnswerStageAttempt",
    "RagAnswerQuotaEvent",
    "RagMessage",
    "RagMessageSource",
    "RagThread",
]
