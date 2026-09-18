"""Private Subject Knowledge storage and durable indexing state.

Content revisions own instructor review and publication. Index revisions can
be rebuilt independently without transferring approval to changed content.
PostgreSQL triggers in Alembic enforce aggregate reservations and actual rows;
SQLite models exist for offline relationship/transaction fixtures only.
"""

import hashlib
import uuid

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Column, DateTime, ForeignKey,
    ForeignKeyConstraint, Index, Integer, String, Text, UniqueConstraint,
    func, text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.models.vector import embedding_vector_type
from app.time_utils import utcnow


def embedding_space_hash(identity: tuple[str, str, str, str, str, int, str, str]) -> str:
    """Hash the ordered Settings identity with unambiguous length framing.

    The PostgreSQL identity trigger uses the same UTF-8 byte lengths. Credentials
    are excluded; endpoint/model/revision/format/dimensions/representation/metric
    all contribute, so equal dimensions do not imply compatible spaces.
    """
    values = [str(value) for value in identity]
    framed = "".join(f"{len(value.encode('utf-8'))}:{value}" for value in values)
    return hashlib.sha256(framed.encode("utf-8")).hexdigest()


ERROR_PAIRS = (
    "(error_code IS NULL AND error_message IS NULL) OR "
    "(error_code IS NOT NULL AND error_message IS NOT NULL AND ("
    "(error_code = 'knowledge_extraction_failed' AND error_message = 'Document extraction failed.') OR "
    "(error_code = 'knowledge_index_failed' AND error_message = 'Document indexing failed.') OR "
    "(error_code = 'knowledge_capacity_exceeded' AND error_message = 'Knowledge storage capacity was exceeded.') OR "
    "(error_code = 'knowledge_cancelled' AND error_message = 'Document processing was cancelled.') OR "
    "(error_code = 'knowledge_lease_expired' AND error_message = 'Document processing lease expired.')))"
)


class KnowledgeStorageUsage(Base):
    __tablename__ = "knowledge_storage_usage"

    scope_type = Column(String(12), primary_key=True)
    scope_id = Column(UUID(as_uuid=True), primary_key=True)
    document_count = Column(Integer, nullable=False, server_default=text("0"))
    charged_bytes = Column(BigInteger, nullable=False, server_default=text("0"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("scope_type IN ('global', 'subject', 'uploader')", name="ck_knowledge_usage_scope"),
        CheckConstraint("document_count >= 0 AND charged_bytes >= 0", name="ck_knowledge_usage_nonnegative"),
        CheckConstraint(
            "(scope_type = 'global' AND document_count <= 500 AND charged_bytes <= 2147483648) OR "
            "(scope_type = 'subject' AND document_count <= 50 AND charged_bytes <= 268435456) OR "
            "(scope_type = 'uploader' AND document_count <= 100 AND charged_bytes <= 536870912)",
            name="ck_knowledge_usage_limits",
        ),
    )


class RagEmbeddingSpace(Base):
    """Immutable, credential-free identity shared by corpus and index snapshots."""

    __tablename__ = "rag_embedding_spaces"

    identity_hash = Column(String(64), primary_key=True)
    provider = Column(String(32), nullable=False)
    base_url = Column(String(512), nullable=False)
    model = Column(String(128), nullable=False)
    space_revision = Column(String(64), nullable=False)
    format_version = Column(String(64), nullable=False)
    dimensions = Column(Integer, nullable=False)
    representation = Column(String(16), nullable=False)
    metric = Column(String(16), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "length(identity_hash) = 64 AND provider = 'openai_compatible' AND "
            "length(trim(base_url)) BETWEEN 1 AND 512 AND length(trim(model)) BETWEEN 1 AND 128 AND "
            "length(trim(space_revision)) BETWEEN 1 AND 64 AND format_version = 'raw_text_v1' AND "
            "dimensions = 1536 AND representation = 'float32' AND metric = 'cosine'",
            name="ck_rag_embedding_spaces_identity",
        ),
    )


class SubjectDocument(Base):
    __tablename__ = "subject_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    subject_id = Column(UUID(as_uuid=True), nullable=False)
    uploader_id = Column(UUID(as_uuid=True), nullable=False)
    title = Column(String(255), nullable=False)
    source_pdf_name = Column(String(255), nullable=False)
    source_sha256 = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["subject_id", "uploader_id"], ["subjects.id", "subjects.instructor_id"],
            ondelete="CASCADE", name="fk_subject_documents_owner",
        ),
        UniqueConstraint("id", "subject_id", "uploader_id", name="uq_subject_documents_scope"),
        UniqueConstraint("id", "subject_id", name="uq_subject_documents_subject"),
        CheckConstraint("length(trim(title)) BETWEEN 1 AND 255", name="ck_subject_documents_title"),
        CheckConstraint("length(source_pdf_name) BETWEEN 1 AND 255", name="ck_subject_documents_filename"),
        CheckConstraint("length(source_sha256) = 64", name="ck_subject_documents_hash"),
        CheckConstraint("source_sha256 ~ '^[0-9a-f]{64}$'", name="ck_subject_documents_hash_format").ddl_if(dialect="postgresql"),
        Index("ix_subject_documents_subject_created", "subject_id", "created_at", "id"),
        Index("ix_subject_documents_subject_hash", "subject_id", "source_sha256"),
        Index("ix_subject_documents_uploader_created", "uploader_id", "created_at", "id"),
    )


class SubjectDocumentContentRevision(Base):
    __tablename__ = "subject_document_content_revisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    document_id = Column(UUID(as_uuid=True), nullable=False)
    subject_id = Column(UUID(as_uuid=True), nullable=False)
    uploader_id = Column(UUID(as_uuid=True), nullable=False)
    revision_no = Column(Integer, nullable=False)
    source_sha256 = Column(String(64), nullable=False)
    extraction_version = Column(String(64), nullable=False)
    status = Column(String(24), nullable=False, server_default=text("'processing'"))
    is_active = Column(Boolean, nullable=False, server_default=text("false"))
    reserved_page_count = Column(Integer, nullable=False)
    reserved_page_chars = Column(Integer, nullable=False)
    reserved_page_bytes = Column(Integer, nullable=False)
    actual_page_count = Column(Integer, nullable=False, server_default=text("0"))
    actual_page_chars = Column(Integer, nullable=False, server_default=text("0"))
    actual_page_bytes = Column(Integer, nullable=False, server_default=text("0"))
    # This equals the document owner when reviewed. The composite document FK
    # already owns account deletion, avoiding a second SET NULL cascade that
    # would temporarily invalidate an otherwise deleting reviewed revision.
    reviewed_by_id = Column(UUID(as_uuid=True), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "subject_id", "uploader_id"],
            ["subject_documents.id", "subject_documents.subject_id", "subject_documents.uploader_id"],
            ondelete="CASCADE", name="fk_knowledge_content_document",
        ),
        UniqueConstraint("document_id", "revision_no", name="uq_knowledge_content_number"),
        UniqueConstraint("id", "document_id", "subject_id", "uploader_id", name="uq_knowledge_content_scope"),
        CheckConstraint("revision_no >= 1", name="ck_knowledge_content_number"),
        CheckConstraint("length(source_sha256) = 64", name="ck_knowledge_content_hash"),
        CheckConstraint("source_sha256 ~ '^[0-9a-f]{64}$'", name="ck_knowledge_content_hash_format").ddl_if(dialect="postgresql"),
        CheckConstraint("length(trim(extraction_version)) BETWEEN 1 AND 64", name="ck_knowledge_content_extraction_version"),
        CheckConstraint(
            "status IN ('processing', 'pending_index', 'ready', 'extraction_failed', 'cancelled')",
            name="ck_knowledge_content_status",
        ),
        CheckConstraint(
            "reserved_page_count BETWEEN 0 AND 100 AND reserved_page_chars BETWEEN 0 AND 500000 AND "
            "reserved_page_bytes BETWEEN 0 AND 2097152 AND actual_page_count BETWEEN 0 AND reserved_page_count AND "
            "actual_page_chars BETWEEN 0 AND reserved_page_chars AND actual_page_bytes BETWEEN 0 AND reserved_page_bytes",
            name="ck_knowledge_content_capacity",
        ),
        CheckConstraint("published_at IS NULL OR reviewed_at IS NOT NULL", name="ck_knowledge_content_review_before_publish"),
        CheckConstraint(
            "(reviewed_at IS NULL AND reviewed_by_id IS NULL) OR "
            "(reviewed_at IS NOT NULL AND reviewed_by_id IS NOT NULL AND reviewed_by_id = uploader_id AND status = 'ready')",
            name="ck_knowledge_content_owner_review",
        ),
        CheckConstraint(
            "status <> 'ready' OR (actual_page_count > 0 AND actual_page_count = reserved_page_count "
            "AND actual_page_chars = reserved_page_chars AND actual_page_bytes = reserved_page_bytes)",
            name="ck_knowledge_content_ready",
        ),
        CheckConstraint("NOT is_active OR status = 'ready'", name="ck_knowledge_content_active_ready"),
        CheckConstraint(
            ERROR_PAIRS,
            name="ck_knowledge_content_error_pair",
        ),
        Index("ix_knowledge_content_document_created", "document_id", "created_at", "id"),
        Index("ix_knowledge_content_subject_hash", "subject_id", "source_sha256"),
        Index("uq_knowledge_content_active", "document_id", unique=True,
              postgresql_where=text("is_active"), sqlite_where=text("is_active")),
    )


class SubjectDocumentPage(Base):
    __tablename__ = "subject_document_pages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    content_revision_id = Column(UUID(as_uuid=True), nullable=False)
    document_id = Column(UUID(as_uuid=True), nullable=False)
    subject_id = Column(UUID(as_uuid=True), nullable=False)
    uploader_id = Column(UUID(as_uuid=True), nullable=False)
    page_number = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["content_revision_id", "document_id", "subject_id", "uploader_id"],
            ["subject_document_content_revisions.id", "subject_document_content_revisions.document_id",
             "subject_document_content_revisions.subject_id", "subject_document_content_revisions.uploader_id"],
            ondelete="CASCADE", name="fk_knowledge_pages_content",
        ),
        UniqueConstraint("content_revision_id", "page_number", name="uq_knowledge_pages_number"),
        CheckConstraint("page_number BETWEEN 1 AND 100", name="ck_knowledge_pages_number"),
        CheckConstraint("length(content) <= 500000", name="ck_knowledge_pages_chars"),
        Index("ix_knowledge_pages_document", "document_id", "content_revision_id", "page_number"),
    )


class SubjectDocumentIndexRevision(Base):
    __tablename__ = "subject_document_index_revisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    content_revision_id = Column(UUID(as_uuid=True), nullable=False)
    document_id = Column(UUID(as_uuid=True), nullable=False)
    subject_id = Column(UUID(as_uuid=True), nullable=False)
    uploader_id = Column(UUID(as_uuid=True), nullable=False)
    revision_no = Column(Integer, nullable=False)
    chunker_version = Column(String(64), nullable=False)
    embedding_provider = Column(String(32), nullable=False)
    embedding_base_url = Column(String(512), nullable=False)
    embedding_model = Column(String(128), nullable=False)
    embedding_space_revision = Column(String(64), nullable=False)
    embedding_format_version = Column(String(64), nullable=False)
    embedding_dimensions = Column(Integer, nullable=False)
    embedding_representation = Column(String(16), nullable=False)
    embedding_metric = Column(String(16), nullable=False)
    embedding_space_hash = Column(String(64), ForeignKey("rag_embedding_spaces.identity_hash"), nullable=False)
    status = Column(String(24), nullable=False, server_default=text("'pending_index'"))
    is_active = Column(Boolean, nullable=False, server_default=text("false"))
    reserved_chunk_count = Column(Integer, nullable=False)
    reserved_index_bytes = Column(BigInteger, nullable=False)
    actual_chunk_count = Column(Integer, nullable=False, server_default=text("0"))
    actual_embedded_count = Column(Integer, nullable=False, server_default=text("0"))
    actual_index_bytes = Column(BigInteger, nullable=False, server_default=text("0"))
    error_code = Column(String(64), nullable=True)
    error_message = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["content_revision_id", "document_id", "subject_id", "uploader_id"],
            ["subject_document_content_revisions.id", "subject_document_content_revisions.document_id",
             "subject_document_content_revisions.subject_id", "subject_document_content_revisions.uploader_id"],
            ondelete="CASCADE", name="fk_knowledge_index_content",
        ),
        UniqueConstraint("content_revision_id", "revision_no", name="uq_knowledge_index_number"),
        UniqueConstraint("id", "content_revision_id", "document_id", "subject_id", "uploader_id", name="uq_knowledge_index_scope"),
        UniqueConstraint("id", "embedding_space_hash", name="uq_knowledge_index_space"),
        CheckConstraint("revision_no >= 1", name="ck_knowledge_index_number"),
        CheckConstraint(
            "length(trim(chunker_version)) BETWEEN 1 AND 64 AND "
            "length(trim(embedding_provider)) BETWEEN 1 AND 32 AND "
            "length(trim(embedding_base_url)) BETWEEN 1 AND 512 AND "
            "length(trim(embedding_model)) BETWEEN 1 AND 128 AND "
            "length(trim(embedding_space_revision)) BETWEEN 1 AND 64 AND "
            "length(trim(embedding_format_version)) BETWEEN 1 AND 64 AND "
            "length(embedding_space_hash) = 64",
            name="ck_knowledge_index_identity",
        ),
        CheckConstraint(
            "embedding_dimensions = 1536 AND embedding_representation = 'float32' AND embedding_metric = 'cosine'",
            name="ck_knowledge_index_vector_space",
        ),
        CheckConstraint(
            "status IN ('pending_index', 'indexing', 'ready', 'index_failed', 'cancelled')",
            name="ck_knowledge_index_status",
        ),
        CheckConstraint(
            "reserved_chunk_count BETWEEN 0 AND 512 AND reserved_index_bytes BETWEEN 0 AND 16777216 AND "
            "actual_chunk_count BETWEEN 0 AND reserved_chunk_count AND "
            "actual_embedded_count BETWEEN 0 AND actual_chunk_count AND "
            "actual_index_bytes BETWEEN 0 AND reserved_index_bytes",
            name="ck_knowledge_index_capacity",
        ),
        CheckConstraint(
            ERROR_PAIRS,
            name="ck_knowledge_index_error_pair",
        ),
        CheckConstraint(
            "status <> 'ready' OR (actual_chunk_count > 0 AND actual_chunk_count = reserved_chunk_count "
            "AND actual_embedded_count = actual_chunk_count)", name="ck_knowledge_index_ready",
        ),
        CheckConstraint("NOT is_active OR status = 'ready'", name="ck_knowledge_index_active_ready"),
        Index("ix_knowledge_index_content_created", "content_revision_id", "created_at", "id"),
        Index("ix_knowledge_index_subject_status", "subject_id", "status", "id"),
        Index("ix_knowledge_index_document", "document_id", "id"),
        Index("ix_knowledge_index_space", "embedding_space_hash", "subject_id"),
        Index("uq_knowledge_index_active", "content_revision_id", unique=True,
              postgresql_where=text("is_active"), sqlite_where=text("is_active")),
    )


class SubjectDocumentChunk(Base):
    __tablename__ = "subject_document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    index_revision_id = Column(UUID(as_uuid=True), nullable=False)
    content_revision_id = Column(UUID(as_uuid=True), nullable=False)
    document_id = Column(UUID(as_uuid=True), nullable=False)
    subject_id = Column(UUID(as_uuid=True), nullable=False)
    uploader_id = Column(UUID(as_uuid=True), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer, nullable=False)
    section = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=False)
    embedding_space_hash = Column(String(64), nullable=False)
    embedding = Column(embedding_vector_type(), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["index_revision_id", "content_revision_id", "document_id", "subject_id", "uploader_id"],
            ["subject_document_index_revisions.id", "subject_document_index_revisions.content_revision_id",
             "subject_document_index_revisions.document_id", "subject_document_index_revisions.subject_id",
             "subject_document_index_revisions.uploader_id"],
            ondelete="CASCADE", name="fk_knowledge_chunks_index",
        ),
        ForeignKeyConstraint(
            ["index_revision_id", "embedding_space_hash"],
            ["subject_document_index_revisions.id", "subject_document_index_revisions.embedding_space_hash"],
            ondelete="CASCADE", name="fk_knowledge_chunks_space",
        ),
        ForeignKeyConstraint(
            ["content_revision_id", "page_number"],
            ["subject_document_pages.content_revision_id", "subject_document_pages.page_number"],
            ondelete="CASCADE", name="fk_knowledge_chunks_page",
        ),
        UniqueConstraint("index_revision_id", "chunk_index", name="uq_knowledge_chunks_index"),
        CheckConstraint("chunk_index BETWEEN 0 AND 511 AND page_number BETWEEN 1 AND 100", name="ck_knowledge_chunks_position"),
        CheckConstraint("length(trim(content)) BETWEEN 1 AND 500000 AND token_count BETWEEN 1 AND 8192", name="ck_knowledge_chunks_content"),
        CheckConstraint("section IS NULL OR length(section) BETWEEN 1 AND 255", name="ck_knowledge_chunks_section"),
        CheckConstraint("length(embedding_space_hash) = 64", name="ck_knowledge_chunks_space_hash"),
        CheckConstraint(
            "embedding IS NULL OR (embedding OPERATOR(public.<#>) embedding) < 0",
            name="ck_knowledge_chunks_nonzero_vector",
        ).ddl_if(dialect="postgresql"),
        Index("ix_knowledge_chunks_subject_revision", "subject_id", "index_revision_id", "chunk_index"),
        Index("ix_knowledge_chunks_document", "document_id", "index_revision_id", "chunk_index"),
        Index("ix_knowledge_chunks_content_page", "content_revision_id", "page_number"),
        Index("ix_knowledge_chunks_fts", func.to_tsvector(text("'simple'::regconfig"), content),
              postgresql_using="gin").ddl_if(dialect="postgresql"),
    )


class SubjectDocumentIndexJob(Base):
    __tablename__ = "subject_document_index_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    index_revision_id = Column(UUID(as_uuid=True), nullable=False)
    content_revision_id = Column(UUID(as_uuid=True), nullable=False)
    document_id = Column(UUID(as_uuid=True), nullable=False)
    subject_id = Column(UUID(as_uuid=True), nullable=False)
    uploader_id = Column(UUID(as_uuid=True), nullable=False)
    status = Column(String(24), nullable=False, server_default=text("'queued'"))
    operation_key_hash = Column(String(64), nullable=False)
    request_fingerprint = Column(String(64), nullable=False)
    corpus_revision = Column(BigInteger, nullable=False)
    attempt_count = Column(Integer, nullable=False, server_default=text("0"))
    max_attempts = Column(Integer, nullable=False, server_default=text("3"))
    available_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deadline_at = Column(DateTime(timezone=True), nullable=False)
    worker_id = Column(String(128), nullable=True)
    claim_token = Column(String(64), nullable=True)
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_requested_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["index_revision_id", "content_revision_id", "document_id", "subject_id", "uploader_id"],
            ["subject_document_index_revisions.id", "subject_document_index_revisions.content_revision_id",
             "subject_document_index_revisions.document_id", "subject_document_index_revisions.subject_id",
             "subject_document_index_revisions.uploader_id"],
            ondelete="CASCADE", name="fk_knowledge_jobs_index",
        ),
        UniqueConstraint("index_revision_id", name="uq_knowledge_jobs_index_revision"),
        UniqueConstraint("uploader_id", "operation_key_hash", name="uq_knowledge_jobs_operation"),
        CheckConstraint(
            "length(operation_key_hash) = 64 AND length(request_fingerprint) = 64 AND corpus_revision >= 0",
            name="ck_knowledge_jobs_identity",
        ),
        CheckConstraint(
            "operation_key_hash ~ '^[0-9a-f]{64}$' AND request_fingerprint ~ '^[0-9a-f]{64}$' AND "
            "(claim_token IS NULL OR claim_token ~ '^[0-9a-f]{64}$')",
            name="ck_knowledge_jobs_hash_format",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint("status IN ('queued', 'running', 'completed', 'failed', 'cancelled')", name="ck_knowledge_jobs_status"),
        CheckConstraint("attempt_count BETWEEN 0 AND max_attempts AND max_attempts BETWEEN 1 AND 10", name="ck_knowledge_jobs_attempts"),
        CheckConstraint(
            "status <> 'running' OR (worker_id IS NOT NULL AND claim_token IS NOT NULL AND "
            "attempt_count >= 1 AND "
            "length(trim(worker_id)) BETWEEN 1 AND 128 AND length(claim_token) = 64 AND "
            "heartbeat_at IS NOT NULL AND lease_expires_at IS NOT NULL "
            "AND heartbeat_at <= lease_expires_at AND lease_expires_at <= deadline_at)",
            name="ck_knowledge_jobs_running_claim",
        ),
        CheckConstraint(
            ERROR_PAIRS,
            name="ck_knowledge_jobs_error_pair",
        ),
        CheckConstraint(
            "(status IN ('completed','failed','cancelled') AND completed_at IS NOT NULL) OR "
            "(status IN ('queued','running') AND completed_at IS NULL)", name="ck_knowledge_jobs_terminal",
        ),
        CheckConstraint("available_at <= deadline_at AND created_at <= deadline_at", name="ck_knowledge_jobs_deadline"),
        Index("ix_knowledge_jobs_queue", "available_at", "created_at", "id", postgresql_where=text("status = 'queued'")),
        Index("ix_knowledge_jobs_running_lease", "lease_expires_at", "id", postgresql_where=text("status = 'running'")),
        Index("ix_knowledge_jobs_subject", "subject_id", "created_at", "id"),
        Index("ix_knowledge_jobs_document", "document_id", "id"),
    )
