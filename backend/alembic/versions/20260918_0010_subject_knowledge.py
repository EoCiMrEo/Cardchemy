"""Persist private Subject Knowledge and reserved storage capacity.

Revision ID: 20260918_0010
Revises: 20260918_0009
Create Date: 2026-09-18
"""
from alembic import op
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
revision = "20260918_0010"
down_revision = "20260918_0009"
branch_labels = None
depends_on = None

ERROR_PAIRS = "(error_code IS NULL AND error_message IS NULL) OR (error_code IS NOT NULL AND error_message IS NOT NULL AND ((error_code = 'knowledge_extraction_failed' AND error_message = 'Document extraction failed.') OR (error_code = 'knowledge_index_failed' AND error_message = 'Document indexing failed.') OR (error_code = 'knowledge_capacity_exceeded' AND error_message = 'Knowledge storage capacity was exceeded.') OR (error_code = 'knowledge_cancelled' AND error_message = 'Document processing was cancelled.') OR (error_code = 'knowledge_lease_expired' AND error_message = 'Document processing lease expired.')))"

def upgrade():
    op.create_unique_constraint("uq_subjects_owner_scope", "subjects", ["id", "instructor_id"])
    op.create_table('knowledge_storage_usage',
        Column('scope_type', String(12), primary_key=True),
        Column('scope_id', UUID(as_uuid=True), primary_key=True),
        Column('document_count', Integer, nullable=False, server_default=text('0')),
        Column('charged_bytes', BigInteger, nullable=False, server_default=text('0')),
        Column('updated_at', DateTime(timezone=True), nullable=False, server_default=func.now()),
        CheckConstraint("scope_type IN ('global', 'subject', 'uploader')", name='ck_knowledge_usage_scope'),
        CheckConstraint('document_count >= 0 AND charged_bytes >= 0', name='ck_knowledge_usage_nonnegative'),
        CheckConstraint("(scope_type = 'global' AND document_count <= 500 AND charged_bytes <= 2147483648) OR (scope_type = 'subject' AND document_count <= 50 AND charged_bytes <= 268435456) OR (scope_type = 'uploader' AND document_count <= 100 AND charged_bytes <= 536870912)", name='ck_knowledge_usage_limits'),
    )
    op.create_table('rag_embedding_spaces',
        Column('identity_hash', String(64), primary_key=True),
        Column('provider', String(32), nullable=False),
        Column('base_url', String(512), nullable=False),
        Column('model', String(128), nullable=False),
        Column('space_revision', String(64), nullable=False),
        Column('format_version', String(64), nullable=False),
        Column('dimensions', Integer, nullable=False),
        Column('representation', String(16), nullable=False),
        Column('metric', String(16), nullable=False),
        Column('created_at', DateTime(timezone=True), nullable=False, server_default=func.now()),
        CheckConstraint("length(identity_hash) = 64 AND provider = 'openai_compatible' AND length(trim(base_url)) BETWEEN 1 AND 512 AND length(trim(model)) BETWEEN 1 AND 128 AND length(trim(space_revision)) BETWEEN 1 AND 64 AND format_version = 'raw_text_v1' AND dimensions = 1536 AND representation = 'float32' AND metric = 'cosine'", name='ck_rag_embedding_spaces_identity'),
    )
    op.create_table('subject_documents',
        Column('id', UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')),
        Column('subject_id', UUID(as_uuid=True), nullable=False),
        Column('uploader_id', UUID(as_uuid=True), nullable=False),
        Column('title', String(255), nullable=False),
        Column('source_pdf_name', String(255), nullable=False),
        Column('source_sha256', String(64), nullable=False),
        Column('created_at', DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column('updated_at', DateTime(timezone=True), nullable=False, server_default=func.now()),
        ForeignKeyConstraint(['subject_id', 'uploader_id'], ['subjects.id', 'subjects.instructor_id'], ondelete='CASCADE', name='fk_subject_documents_owner'),
        UniqueConstraint('id', 'subject_id', 'uploader_id', name='uq_subject_documents_scope'),
        UniqueConstraint('id', 'subject_id', name='uq_subject_documents_subject'),
        CheckConstraint('length(trim(title)) BETWEEN 1 AND 255', name='ck_subject_documents_title'),
        CheckConstraint('length(source_pdf_name) BETWEEN 1 AND 255', name='ck_subject_documents_filename'),
        CheckConstraint('length(source_sha256) = 64', name='ck_subject_documents_hash'),
    )
    op.create_table('subject_document_content_revisions',
        Column('id', UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')),
        Column('document_id', UUID(as_uuid=True), nullable=False),
        Column('subject_id', UUID(as_uuid=True), nullable=False),
        Column('uploader_id', UUID(as_uuid=True), nullable=False),
        Column('revision_no', Integer, nullable=False),
        Column('source_sha256', String(64), nullable=False),
        Column('extraction_version', String(64), nullable=False),
        Column('status', String(24), nullable=False, server_default=text("'processing'")),
        Column('is_active', Boolean, nullable=False, server_default=text('false')),
        Column('reserved_page_count', Integer, nullable=False),
        Column('reserved_page_chars', Integer, nullable=False),
        Column('reserved_page_bytes', Integer, nullable=False),
        Column('actual_page_count', Integer, nullable=False, server_default=text('0')),
        Column('actual_page_chars', Integer, nullable=False, server_default=text('0')),
        Column('actual_page_bytes', Integer, nullable=False, server_default=text('0')),
        Column('reviewed_by_id', UUID(as_uuid=True), nullable=True),
        Column('reviewed_at', DateTime(timezone=True), nullable=True),
        Column('published_at', DateTime(timezone=True), nullable=True),
        Column('error_code', String(64), nullable=True),
        Column('error_message', String(500), nullable=True),
        Column('created_at', DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column('updated_at', DateTime(timezone=True), nullable=False, server_default=func.now()),
        ForeignKeyConstraint(['document_id', 'subject_id', 'uploader_id'], ['subject_documents.id', 'subject_documents.subject_id', 'subject_documents.uploader_id'], ondelete='CASCADE', name='fk_knowledge_content_document'),
        UniqueConstraint('document_id', 'revision_no', name='uq_knowledge_content_number'),
        UniqueConstraint('id', 'document_id', 'subject_id', 'uploader_id', name='uq_knowledge_content_scope'),
        CheckConstraint('revision_no >= 1', name='ck_knowledge_content_number'),
        CheckConstraint('length(source_sha256) = 64', name='ck_knowledge_content_hash'),
        CheckConstraint('length(trim(extraction_version)) BETWEEN 1 AND 64', name='ck_knowledge_content_extraction_version'),
        CheckConstraint("status IN ('processing', 'pending_index', 'ready', 'extraction_failed', 'cancelled')", name='ck_knowledge_content_status'),
        CheckConstraint('reserved_page_count BETWEEN 0 AND 100 AND reserved_page_chars BETWEEN 0 AND 500000 AND reserved_page_bytes BETWEEN 0 AND 2097152 AND actual_page_count BETWEEN 0 AND reserved_page_count AND actual_page_chars BETWEEN 0 AND reserved_page_chars AND actual_page_bytes BETWEEN 0 AND reserved_page_bytes', name='ck_knowledge_content_capacity'),
        CheckConstraint('published_at IS NULL OR reviewed_at IS NOT NULL', name='ck_knowledge_content_review_before_publish'),
        CheckConstraint("(reviewed_at IS NULL AND reviewed_by_id IS NULL) OR (reviewed_at IS NOT NULL AND reviewed_by_id IS NOT NULL AND reviewed_by_id = uploader_id AND status = 'ready')", name='ck_knowledge_content_owner_review'),
        CheckConstraint("status <> 'ready' OR (actual_page_count > 0 AND actual_page_count = reserved_page_count AND actual_page_chars = reserved_page_chars AND actual_page_bytes = reserved_page_bytes)", name='ck_knowledge_content_ready'),
        CheckConstraint("NOT is_active OR status = 'ready'", name='ck_knowledge_content_active_ready'),
        CheckConstraint(ERROR_PAIRS, name='ck_knowledge_content_error_pair'),
    )
    op.create_table('subject_document_pages',
        Column('id', UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')),
        Column('content_revision_id', UUID(as_uuid=True), nullable=False),
        Column('document_id', UUID(as_uuid=True), nullable=False),
        Column('subject_id', UUID(as_uuid=True), nullable=False),
        Column('uploader_id', UUID(as_uuid=True), nullable=False),
        Column('page_number', Integer, nullable=False),
        Column('content', Text, nullable=False),
        ForeignKeyConstraint(['content_revision_id', 'document_id', 'subject_id', 'uploader_id'], ['subject_document_content_revisions.id', 'subject_document_content_revisions.document_id', 'subject_document_content_revisions.subject_id', 'subject_document_content_revisions.uploader_id'], ondelete='CASCADE', name='fk_knowledge_pages_content'),
        UniqueConstraint('content_revision_id', 'page_number', name='uq_knowledge_pages_number'),
        CheckConstraint('page_number BETWEEN 1 AND 100', name='ck_knowledge_pages_number'),
        CheckConstraint('length(content) <= 500000', name='ck_knowledge_pages_chars'),
    )
    op.create_table('subject_document_index_revisions',
        Column('id', UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')),
        Column('content_revision_id', UUID(as_uuid=True), nullable=False),
        Column('document_id', UUID(as_uuid=True), nullable=False),
        Column('subject_id', UUID(as_uuid=True), nullable=False),
        Column('uploader_id', UUID(as_uuid=True), nullable=False),
        Column('revision_no', Integer, nullable=False),
        Column('chunker_version', String(64), nullable=False),
        Column('embedding_provider', String(32), nullable=False),
        Column('embedding_base_url', String(512), nullable=False),
        Column('embedding_model', String(128), nullable=False),
        Column('embedding_space_revision', String(64), nullable=False),
        Column('embedding_format_version', String(64), nullable=False),
        Column('embedding_dimensions', Integer, nullable=False),
        Column('embedding_representation', String(16), nullable=False),
        Column('embedding_metric', String(16), nullable=False),
        Column('embedding_space_hash', String(64), ForeignKey('rag_embedding_spaces.identity_hash'), nullable=False),
        Column('status', String(24), nullable=False, server_default=text("'pending_index'")),
        Column('is_active', Boolean, nullable=False, server_default=text('false')),
        Column('reserved_chunk_count', Integer, nullable=False),
        Column('reserved_index_bytes', BigInteger, nullable=False),
        Column('actual_chunk_count', Integer, nullable=False, server_default=text('0')),
        Column('actual_embedded_count', Integer, nullable=False, server_default=text('0')),
        Column('actual_index_bytes', BigInteger, nullable=False, server_default=text('0')),
        Column('error_code', String(64), nullable=True),
        Column('error_message', String(500), nullable=True),
        Column('created_at', DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column('updated_at', DateTime(timezone=True), nullable=False, server_default=func.now()),
        ForeignKeyConstraint(['content_revision_id', 'document_id', 'subject_id', 'uploader_id'], ['subject_document_content_revisions.id', 'subject_document_content_revisions.document_id', 'subject_document_content_revisions.subject_id', 'subject_document_content_revisions.uploader_id'], ondelete='CASCADE', name='fk_knowledge_index_content'),
        UniqueConstraint('content_revision_id', 'revision_no', name='uq_knowledge_index_number'),
        UniqueConstraint('id', 'content_revision_id', 'document_id', 'subject_id', 'uploader_id', name='uq_knowledge_index_scope'),
        UniqueConstraint('id', 'embedding_space_hash', name='uq_knowledge_index_space'),
        CheckConstraint('revision_no >= 1', name='ck_knowledge_index_number'),
        CheckConstraint('length(trim(chunker_version)) BETWEEN 1 AND 64 AND length(trim(embedding_provider)) BETWEEN 1 AND 32 AND length(trim(embedding_base_url)) BETWEEN 1 AND 512 AND length(trim(embedding_model)) BETWEEN 1 AND 128 AND length(trim(embedding_space_revision)) BETWEEN 1 AND 64 AND length(trim(embedding_format_version)) BETWEEN 1 AND 64 AND length(embedding_space_hash) = 64', name='ck_knowledge_index_identity'),
        CheckConstraint("embedding_dimensions = 1536 AND embedding_representation = 'float32' AND embedding_metric = 'cosine'", name='ck_knowledge_index_vector_space'),
        CheckConstraint("status IN ('pending_index', 'indexing', 'ready', 'index_failed', 'cancelled')", name='ck_knowledge_index_status'),
        CheckConstraint('reserved_chunk_count BETWEEN 0 AND 512 AND reserved_index_bytes BETWEEN 0 AND 16777216 AND actual_chunk_count BETWEEN 0 AND reserved_chunk_count AND actual_embedded_count BETWEEN 0 AND actual_chunk_count AND actual_index_bytes BETWEEN 0 AND reserved_index_bytes', name='ck_knowledge_index_capacity'),
        CheckConstraint(ERROR_PAIRS, name='ck_knowledge_index_error_pair'),
        CheckConstraint("status <> 'ready' OR (actual_chunk_count > 0 AND actual_chunk_count = reserved_chunk_count AND actual_embedded_count = actual_chunk_count)", name='ck_knowledge_index_ready'),
        CheckConstraint("NOT is_active OR status = 'ready'", name='ck_knowledge_index_active_ready'),
    )
    op.create_table('subject_document_chunks',
        Column('id', UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')),
        Column('index_revision_id', UUID(as_uuid=True), nullable=False),
        Column('content_revision_id', UUID(as_uuid=True), nullable=False),
        Column('document_id', UUID(as_uuid=True), nullable=False),
        Column('subject_id', UUID(as_uuid=True), nullable=False),
        Column('uploader_id', UUID(as_uuid=True), nullable=False),
        Column('chunk_index', Integer, nullable=False),
        Column('page_number', Integer, nullable=False),
        Column('section', String(255), nullable=True),
        Column('content', Text, nullable=False),
        Column('token_count', Integer, nullable=False),
        Column('embedding_space_hash', String(64), nullable=False),
        Column('embedding', Vector(1536), nullable=True),
        ForeignKeyConstraint(['index_revision_id', 'content_revision_id', 'document_id', 'subject_id', 'uploader_id'], ['subject_document_index_revisions.id', 'subject_document_index_revisions.content_revision_id', 'subject_document_index_revisions.document_id', 'subject_document_index_revisions.subject_id', 'subject_document_index_revisions.uploader_id'], ondelete='CASCADE', name='fk_knowledge_chunks_index'),
        ForeignKeyConstraint(['index_revision_id', 'embedding_space_hash'], ['subject_document_index_revisions.id', 'subject_document_index_revisions.embedding_space_hash'], ondelete='CASCADE', name='fk_knowledge_chunks_space'),
        ForeignKeyConstraint(['content_revision_id', 'page_number'], ['subject_document_pages.content_revision_id', 'subject_document_pages.page_number'], ondelete='CASCADE', name='fk_knowledge_chunks_page'),
        UniqueConstraint('index_revision_id', 'chunk_index', name='uq_knowledge_chunks_index'),
        CheckConstraint('chunk_index BETWEEN 0 AND 511 AND page_number BETWEEN 1 AND 100', name='ck_knowledge_chunks_position'),
        CheckConstraint('length(trim(content)) BETWEEN 1 AND 500000 AND token_count BETWEEN 1 AND 8192', name='ck_knowledge_chunks_content'),
        CheckConstraint('section IS NULL OR length(section) BETWEEN 1 AND 255', name='ck_knowledge_chunks_section'),
        CheckConstraint('length(embedding_space_hash) = 64', name='ck_knowledge_chunks_space_hash'),
    )
    op.create_table('subject_document_index_jobs',
        Column('id', UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')),
        Column('index_revision_id', UUID(as_uuid=True), nullable=False),
        Column('content_revision_id', UUID(as_uuid=True), nullable=False),
        Column('document_id', UUID(as_uuid=True), nullable=False),
        Column('subject_id', UUID(as_uuid=True), nullable=False),
        Column('uploader_id', UUID(as_uuid=True), nullable=False),
        Column('status', String(24), nullable=False, server_default=text("'queued'")),
        Column('operation_key_hash', String(64), nullable=False),
        Column('request_fingerprint', String(64), nullable=False),
        Column('corpus_revision', BigInteger, nullable=False),
        Column('attempt_count', Integer, nullable=False, server_default=text('0')),
        Column('max_attempts', Integer, nullable=False, server_default=text('3')),
        Column('available_at', DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column('deadline_at', DateTime(timezone=True), nullable=False),
        Column('worker_id', String(128), nullable=True),
        Column('claim_token', String(64), nullable=True),
        Column('heartbeat_at', DateTime(timezone=True), nullable=True),
        Column('lease_expires_at', DateTime(timezone=True), nullable=True),
        Column('cancellation_requested_at', DateTime(timezone=True), nullable=True),
        Column('completed_at', DateTime(timezone=True), nullable=True),
        Column('error_code', String(64), nullable=True),
        Column('error_message', String(500), nullable=True),
        Column('created_at', DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column('updated_at', DateTime(timezone=True), nullable=False, server_default=func.now()),
        ForeignKeyConstraint(['index_revision_id', 'content_revision_id', 'document_id', 'subject_id', 'uploader_id'], ['subject_document_index_revisions.id', 'subject_document_index_revisions.content_revision_id', 'subject_document_index_revisions.document_id', 'subject_document_index_revisions.subject_id', 'subject_document_index_revisions.uploader_id'], ondelete='CASCADE', name='fk_knowledge_jobs_index'),
        UniqueConstraint('index_revision_id', name='uq_knowledge_jobs_index_revision'),
        UniqueConstraint('uploader_id', 'operation_key_hash', name='uq_knowledge_jobs_operation'),
        CheckConstraint('length(operation_key_hash) = 64 AND length(request_fingerprint) = 64 AND corpus_revision >= 0', name='ck_knowledge_jobs_identity'),
        CheckConstraint("status IN ('queued', 'running', 'completed', 'failed', 'cancelled')", name='ck_knowledge_jobs_status'),
        CheckConstraint('attempt_count BETWEEN 0 AND max_attempts AND max_attempts BETWEEN 1 AND 10', name='ck_knowledge_jobs_attempts'),
        CheckConstraint("status <> 'running' OR (worker_id IS NOT NULL AND claim_token IS NOT NULL AND attempt_count >= 1 AND length(trim(worker_id)) BETWEEN 1 AND 128 AND length(claim_token) = 64 AND heartbeat_at IS NOT NULL AND lease_expires_at IS NOT NULL AND heartbeat_at <= lease_expires_at AND lease_expires_at <= deadline_at)", name='ck_knowledge_jobs_running_claim'),
        CheckConstraint(ERROR_PAIRS, name='ck_knowledge_jobs_error_pair'),
        CheckConstraint("(status IN ('completed','failed','cancelled') AND completed_at IS NOT NULL) OR (status IN ('queued','running') AND completed_at IS NULL)", name='ck_knowledge_jobs_terminal'),
        CheckConstraint('available_at <= deadline_at AND created_at <= deadline_at', name='ck_knowledge_jobs_deadline'),
    )
    op.create_index('ix_subject_documents_subject_created', 'subject_documents', [ 'subject_id', 'created_at', 'id'])
    op.create_index('ix_subject_documents_subject_hash', 'subject_documents', ['subject_id', 'source_sha256'])
    op.create_index('ix_subject_documents_uploader_created', 'subject_documents', [ 'uploader_id', 'created_at', 'id'])
    op.create_index('ix_knowledge_content_document_created', 'subject_document_content_revisions', [ 'document_id', 'created_at', 'id'])
    op.create_index('ix_knowledge_content_subject_hash', 'subject_document_content_revisions', ['subject_id', 'source_sha256'])
    op.create_index('uq_knowledge_content_active', 'subject_document_content_revisions', [ 'document_id'], unique=True, postgresql_where=text('is_active'))
    op.create_index('ix_knowledge_pages_document', 'subject_document_pages', [ 'document_id', 'content_revision_id', 'page_number'])
    op.create_index('ix_knowledge_index_content_created', 'subject_document_index_revisions', [ 'content_revision_id', 'created_at', 'id'])
    op.create_index('ix_knowledge_index_subject_status', 'subject_document_index_revisions', [ 'subject_id', 'status', 'id'])
    op.create_index('ix_knowledge_index_document', 'subject_document_index_revisions', [ 'document_id', 'id'])
    op.create_index('ix_knowledge_index_space', 'subject_document_index_revisions', ['embedding_space_hash', 'subject_id'])
    op.create_index('uq_knowledge_index_active', 'subject_document_index_revisions', [ 'content_revision_id'], unique=True, postgresql_where=text('is_active'))
    op.create_index('ix_knowledge_chunks_subject_revision', 'subject_document_chunks', [ 'subject_id', 'index_revision_id', 'chunk_index'])
    op.create_index('ix_knowledge_chunks_document', 'subject_document_chunks', [ 'document_id', 'index_revision_id', 'chunk_index'])
    op.create_index('ix_knowledge_chunks_content_page', 'subject_document_chunks', [ 'content_revision_id', 'page_number'])
    op.create_index('ix_knowledge_jobs_queue', 'subject_document_index_jobs', [ 'available_at', 'created_at', 'id'], postgresql_where=text("status = 'queued'"))
    op.create_index('ix_knowledge_jobs_running_lease', 'subject_document_index_jobs', [ 'lease_expires_at', 'id'], postgresql_where=text("status = 'running'"))
    op.create_index('ix_knowledge_jobs_subject', 'subject_document_index_jobs', [ 'subject_id', 'created_at', 'id'])
    op.create_index('ix_knowledge_jobs_document', 'subject_document_index_jobs', [ 'document_id', 'id'])
    op.add_column("subjects", Column("corpus_revision", BigInteger(), nullable=False, server_default=text("0")))
    op.add_column("subjects", Column("active_embedding_space_hash", String(64), nullable=True))
    op.add_column("subjects", Column("staged_embedding_space_hash", String(64), nullable=True))
    op.create_index("ix_subjects_active_space", "subjects", ["active_embedding_space_hash"])
    op.create_index("ix_subjects_staged_space", "subjects", ["staged_embedding_space_hash"])
    op.create_check_constraint("ck_subjects_corpus_revision", "subjects", "corpus_revision >= 0")
    op.create_check_constraint("ck_subjects_embedding_spaces", "subjects", "(active_embedding_space_hash IS NULL OR length(active_embedding_space_hash) = 64) AND (staged_embedding_space_hash IS NULL OR length(staged_embedding_space_hash) = 64)")
    for field in ("active_embedding_space_hash", "staged_embedding_space_hash"):
        op.create_foreign_key("fk_subjects_" + field, "subjects", "rag_embedding_spaces", [field], ["identity_hash"])
    op.add_column("generation_jobs", Column("document_id", UUID(as_uuid=True), nullable=True))
    op.add_column("generation_jobs", Column("knowledge_capture_removed", Boolean(), nullable=False, server_default=text("false")))
    op.create_foreign_key("fk_generation_jobs_document", "generation_jobs", "subject_documents", ["document_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_generation_jobs_document_scope", "generation_jobs", "subject_documents", ["document_id", "subject_id", "user_id"], ["id", "subject_id", "uploader_id"], deferrable=True, initially="DEFERRED")
    op.create_check_constraint("ck_generation_jobs_removed_capture", "generation_jobs", "NOT knowledge_capture_removed OR document_id IS NULL")
    op.create_index("ix_generation_jobs_document", "generation_jobs", ["document_id", "subject_id", "user_id"])
    op.add_column("flashcard_sets", Column("document_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_flashcard_sets_document", "flashcard_sets", "subject_documents", ["document_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_flashcard_sets_document_subject", "flashcard_sets", "subject_documents", ["document_id", "subject_id"], ["id", "subject_id"], deferrable=True, initially="DEFERRED")
    op.create_index("ix_flashcard_sets_document", "flashcard_sets", ["document_id", "subject_id"])
    op.create_check_constraint("ck_knowledge_chunks_nonzero_vector", "subject_document_chunks", "embedding IS NULL OR (embedding OPERATOR(public.<#>) embedding) < 0")
    op.create_check_constraint("ck_subject_documents_hash_format", "subject_documents", "source_sha256 ~ '^[0-9a-f]{64}$'")
    op.create_check_constraint("ck_knowledge_content_hash_format", "subject_document_content_revisions", "source_sha256 ~ '^[0-9a-f]{64}$'")
    op.create_check_constraint("ck_knowledge_jobs_hash_format", "subject_document_index_jobs", "operation_key_hash ~ '^[0-9a-f]{64}$' AND request_fingerprint ~ '^[0-9a-f]{64}$' AND (claim_token IS NULL OR claim_token ~ '^[0-9a-f]{64}$')")
    op.create_index("ix_knowledge_chunks_fts", "subject_document_chunks", [text("to_tsvector('simple'::regconfig, content)")], postgresql_using="gin")
    _install_integrity()

def downgrade():
    _remove_integrity()
    op.drop_constraint("fk_generation_jobs_document_scope", "generation_jobs", type_="foreignkey")
    op.drop_constraint("fk_generation_jobs_document", "generation_jobs", type_="foreignkey")
    op.drop_constraint("ck_generation_jobs_removed_capture", "generation_jobs", type_="check")
    op.drop_index("ix_generation_jobs_document", table_name="generation_jobs")
    op.drop_column("generation_jobs", "document_id")
    op.drop_column("generation_jobs", "knowledge_capture_removed")
    op.drop_constraint("fk_flashcard_sets_document_subject", "flashcard_sets", type_="foreignkey")
    op.drop_constraint("fk_flashcard_sets_document", "flashcard_sets", type_="foreignkey")
    op.drop_index("ix_flashcard_sets_document", table_name="flashcard_sets")
    op.drop_column("flashcard_sets", "document_id")
    op.drop_constraint("ck_subjects_embedding_spaces", "subjects", type_="check")
    op.drop_index("ix_subjects_active_space", table_name="subjects")
    op.drop_index("ix_subjects_staged_space", table_name="subjects")
    for field in ("active_embedding_space_hash", "staged_embedding_space_hash"):
        op.drop_constraint("fk_subjects_" + field, "subjects", type_="foreignkey")
        op.drop_column("subjects", field)
    op.drop_constraint("ck_subjects_corpus_revision", "subjects", type_="check")
    op.drop_column("subjects", "corpus_revision")
    op.drop_table('subject_document_index_jobs')
    op.drop_table('subject_document_chunks')
    op.drop_table('subject_document_index_revisions')
    op.drop_table('subject_document_pages')
    op.drop_table('subject_document_content_revisions')
    op.drop_table('subject_documents')
    op.drop_constraint("uq_subjects_owner_scope", "subjects", type_="unique")
    op.drop_table('rag_embedding_spaces')
    op.drop_table('knowledge_storage_usage')


KNOWLEDGE_TABLES = (
    'rag_embedding_spaces', 'knowledge_storage_usage', 'subject_documents',
    'subject_document_content_revisions', 'subject_document_pages',
    'subject_document_index_revisions', 'subject_document_chunks', 'subject_document_index_jobs',
)
# Every affected write acquires the foundation lock before PostgreSQL obtains
# row locks. Parent deletions and provenance detachment use this same order.
# This deliberately serializes writes at the initial 500-document bound;
# higher-throughput admission needs a measured, separately reviewed redesign.
PARENT_LOCK_EVENTS = {
    'users': 'DELETE OR UPDATE OF id',
    'subjects': 'DELETE OR UPDATE OF id, instructor_id, corpus_revision, active_embedding_space_hash, staged_embedding_space_hash',
    'generation_jobs': 'DELETE OR UPDATE OF document_id, subject_id, user_id, knowledge_capture_removed',
    'flashcard_sets': 'DELETE OR UPDATE OF document_id, subject_id',
}
LOCK_TABLES = KNOWLEDGE_TABLES + tuple(PARENT_LOCK_EVENTS)


FUNCTION_DDL = (
"""
CREATE FUNCTION knowledge_write_lock() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM pg_advisory_xact_lock(13013, 0);
    RETURN NULL;
END $$
""",
"""
CREATE FUNCTION knowledge_usage_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF pg_trigger_depth() < 2 THEN
        RAISE EXCEPTION 'Knowledge counters are maintained by storage admission.' USING ERRCODE = '23514';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END $$
""",
"""
CREATE FUNCTION knowledge_adjust_usage(subject_key uuid, uploader_key uuid, docs_delta integer, bytes_delta bigint)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE scope_key text; identity_key uuid;
BEGIN
    -- The statement-level global lock precedes these ordered counter rows.
    FOR scope_key, identity_key IN
        SELECT scope, identity FROM (VALUES
            (1, 'global'::text, '00000000-0000-0000-0000-000000000000'::uuid),
            (2, 'subject'::text, subject_key), (3, 'uploader'::text, uploader_key)
        ) AS scopes(position, scope, identity) ORDER BY position
    LOOP
        INSERT INTO knowledge_storage_usage(scope_type, scope_id) VALUES(scope_key, identity_key)
            ON CONFLICT DO NOTHING;
        UPDATE knowledge_storage_usage
            SET document_count = document_count + docs_delta, charged_bytes = charged_bytes + bytes_delta,
                updated_at = now()
            WHERE scope_type = scope_key AND scope_id = identity_key;
        DELETE FROM knowledge_storage_usage WHERE scope_type = scope_key AND scope_id = identity_key
            AND scope_type <> 'global' AND document_count = 0 AND charged_bytes = 0;
    END LOOP;
END $$
""",
"""
CREATE FUNCTION knowledge_space_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE framed text; computed text;
BEGIN
    IF TG_OP = 'DELETE' THEN
        -- Existing Subject/index FKs prevent dropping a referenced space.
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'Embedding spaces are immutable.' USING ERRCODE = '23514';
    END IF;
    IF (SELECT count(*) FROM rag_embedding_spaces) >= 64 THEN
        RAISE EXCEPTION 'Embedding space capacity was exceeded.' USING ERRCODE = '23514';
    END IF;
    SELECT string_agg(octet_length(value)::text || ':' || value, '' ORDER BY position)
        INTO framed FROM unnest(ARRAY[
            NEW.provider, NEW.base_url, NEW.model, NEW.space_revision, NEW.format_version,
            NEW.dimensions::text, NEW.representation, NEW.metric
        ]) WITH ORDINALITY AS identity(value, position);
    computed := encode(sha256(convert_to(framed, 'UTF8')), 'hex');
    IF NEW.identity_hash IS DISTINCT FROM computed THEN
        RAISE EXCEPTION 'Embedding space identity is incompatible.' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$
""",
"""
CREATE FUNCTION knowledge_document_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE total_bytes bigint;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF (NEW.id, NEW.subject_id, NEW.uploader_id, NEW.source_sha256, NEW.created_at)
            IS DISTINCT FROM (OLD.id, OLD.subject_id, OLD.uploader_id, OLD.source_sha256, OLD.created_at) THEN
            RAISE EXCEPTION 'Document capture identity is immutable.' USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    ELSIF TG_OP = 'INSERT' THEN
        IF NOT EXISTS (SELECT 1 FROM users WHERE id = NEW.uploader_id AND role = 'INSTRUCTOR') THEN
            RAISE EXCEPTION 'Knowledge requires instructor ownership.' USING ERRCODE = '23514';
        END IF;
        PERFORM knowledge_adjust_usage(NEW.subject_id, NEW.uploader_id, 1, 0);
        RETURN NEW;
    END IF;
    SELECT coalesce(sum(charge), 0) INTO total_bytes FROM (
        SELECT reserved_page_bytes AS charge FROM subject_document_content_revisions WHERE document_id = OLD.id
        UNION ALL
        SELECT reserved_index_bytes FROM subject_document_index_revisions WHERE document_id = OLD.id
    ) AS charges;
    PERFORM knowledge_adjust_usage(OLD.subject_id, OLD.uploader_id, -1, -total_bytes);
    UPDATE generation_jobs SET knowledge_capture_removed = true, document_id = NULL WHERE document_id = OLD.id;
    RETURN OLD;
END $$
""",
"""
CREATE FUNCTION knowledge_revision_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE document_key uuid; owner_key uuid; subject_key uuid; delta_bytes bigint;
    total_bytes bigint; retained_count integer; target_count integer; identity rag_embedding_spaces%ROWTYPE;
BEGIN
    document_key := CASE WHEN TG_OP = 'DELETE' THEN OLD.document_id ELSE NEW.document_id END;
    SELECT subject_id, uploader_id INTO subject_key, owner_key FROM subject_documents WHERE id = document_key FOR UPDATE;
    IF NOT FOUND AND TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    IF NOT FOUND THEN RAISE EXCEPTION 'Document membership is invalid.' USING ERRCODE = '23503'; END IF;
    IF TG_OP = 'UPDATE' AND
        (NEW.id, NEW.document_id, NEW.subject_id, NEW.uploader_id, NEW.revision_no, NEW.created_at)
        IS DISTINCT FROM (OLD.id, OLD.document_id, OLD.subject_id, OLD.uploader_id, OLD.revision_no, OLD.created_at) THEN
        RAISE EXCEPTION 'Knowledge revision identity is immutable.' USING ERRCODE = '23514';
    END IF;
    IF TG_TABLE_NAME = 'subject_document_content_revisions' THEN
        IF TG_OP = 'INSERT' AND (NEW.status <> 'processing' OR NEW.is_active OR
            NEW.actual_page_count <> 0 OR NEW.actual_page_chars <> 0 OR NEW.actual_page_bytes <> 0 OR
            NEW.reviewed_at IS NOT NULL OR NEW.reviewed_by_id IS NOT NULL OR NEW.published_at IS NOT NULL OR
            NEW.error_code IS NOT NULL OR NEW.error_message IS NOT NULL) THEN
            RAISE EXCEPTION 'New content must be private and unmeasured.' USING ERRCODE = '23514';
        END IF;
        IF TG_OP = 'UPDATE' AND NEW.status IS DISTINCT FROM OLD.status AND NOT (
            (OLD.status = 'processing' AND NEW.status IN ('pending_index','extraction_failed','cancelled')) OR
            (OLD.status = 'pending_index' AND NEW.status IN ('ready','cancelled'))
        ) THEN RAISE EXCEPTION 'Captured content cannot be reopened.' USING ERRCODE = '23514'; END IF;
        target_count := 4;
        SELECT count(*) INTO retained_count FROM subject_document_content_revisions WHERE document_id = document_key;
        delta_bytes := CASE WHEN TG_OP = 'DELETE' THEN -OLD.reserved_page_bytes
            WHEN TG_OP = 'INSERT' THEN NEW.reserved_page_bytes ELSE NEW.reserved_page_bytes - OLD.reserved_page_bytes END;
        IF TG_OP = 'UPDATE' AND (NEW.source_sha256, NEW.extraction_version)
            IS DISTINCT FROM (OLD.source_sha256, OLD.extraction_version) THEN
            RAISE EXCEPTION 'Content extraction identity is immutable.' USING ERRCODE = '23514';
        END IF;
        IF TG_OP = 'UPDATE' AND pg_trigger_depth() < 2 AND
            (NEW.actual_page_count, NEW.actual_page_chars, NEW.actual_page_bytes)
            IS DISTINCT FROM (OLD.actual_page_count, OLD.actual_page_chars, OLD.actual_page_bytes) THEN
            RAISE EXCEPTION 'Page measurements are maintained by storage admission.' USING ERRCODE = '23514';
        END IF;
        IF TG_OP <> 'DELETE' AND NEW.status IN ('pending_index','ready') AND
            (NEW.actual_page_count = 0 OR NEW.actual_page_count <> NEW.reserved_page_count OR
             NEW.actual_page_chars <> NEW.reserved_page_chars OR NEW.actual_page_bytes <> NEW.reserved_page_bytes) THEN
            RAISE EXCEPTION 'Content page measurements are incomplete.' USING ERRCODE = '23514';
        END IF;
        IF TG_OP <> 'DELETE' AND NEW.status = 'ready' AND NOT EXISTS(
            SELECT 1 FROM subject_document_index_revisions WHERE content_revision_id = NEW.id AND status = 'ready'
        ) THEN RAISE EXCEPTION 'Content has no ready index.' USING ERRCODE = '23514'; END IF;
    ELSE
        IF TG_OP = 'INSERT' AND (NEW.status <> 'pending_index' OR NEW.is_active OR
            NEW.actual_chunk_count <> 0 OR NEW.actual_embedded_count <> 0 OR NEW.actual_index_bytes <> 0 OR
            NEW.error_code IS NOT NULL OR NEW.error_message IS NOT NULL) THEN
            RAISE EXCEPTION 'New index must be staged and unmeasured.' USING ERRCODE = '23514';
        END IF;
        IF TG_OP = 'UPDATE' AND NEW.status IS DISTINCT FROM OLD.status AND NOT (
            (OLD.status = 'pending_index' AND NEW.status IN ('indexing','ready','index_failed','cancelled')) OR
            (OLD.status = 'indexing' AND NEW.status IN ('ready','index_failed','cancelled'))
        ) THEN RAISE EXCEPTION 'Finalized index cannot be reopened.' USING ERRCODE = '23514'; END IF;
        target_count := 8;
        SELECT count(*) INTO retained_count FROM subject_document_index_revisions WHERE document_id = document_key;
        delta_bytes := CASE WHEN TG_OP = 'DELETE' THEN -OLD.reserved_index_bytes
            WHEN TG_OP = 'INSERT' THEN NEW.reserved_index_bytes ELSE NEW.reserved_index_bytes - OLD.reserved_index_bytes END;
        IF TG_OP <> 'DELETE' THEN
            SELECT * INTO identity FROM rag_embedding_spaces WHERE identity_hash = NEW.embedding_space_hash;
            IF NOT FOUND OR
                (NEW.embedding_provider, NEW.embedding_base_url, NEW.embedding_model, NEW.embedding_space_revision,
                 NEW.embedding_format_version, NEW.embedding_dimensions, NEW.embedding_representation, NEW.embedding_metric)
                IS DISTINCT FROM
                (identity.provider, identity.base_url, identity.model, identity.space_revision, identity.format_version,
                 identity.dimensions, identity.representation, identity.metric) THEN
                RAISE EXCEPTION 'Index embedding identity is incompatible.' USING ERRCODE = '23514';
            END IF;
        END IF;
        IF TG_OP = 'INSERT' AND NOT EXISTS (
            SELECT 1 FROM subject_document_content_revisions WHERE id = NEW.content_revision_id
                AND status IN ('pending_index','ready')
        ) THEN RAISE EXCEPTION 'Content is not ready for indexing.' USING ERRCODE = '23514'; END IF;
        IF TG_OP = 'UPDATE' AND
            (NEW.content_revision_id, NEW.chunker_version, NEW.embedding_provider, NEW.embedding_base_url,
             NEW.embedding_model, NEW.embedding_space_revision, NEW.embedding_format_version, NEW.embedding_dimensions,
             NEW.embedding_representation, NEW.embedding_metric, NEW.embedding_space_hash)
            IS DISTINCT FROM
            (OLD.content_revision_id, OLD.chunker_version, OLD.embedding_provider, OLD.embedding_base_url,
             OLD.embedding_model, OLD.embedding_space_revision, OLD.embedding_format_version, OLD.embedding_dimensions,
             OLD.embedding_representation, OLD.embedding_metric, OLD.embedding_space_hash) THEN
            RAISE EXCEPTION 'Index embedding identity is immutable.' USING ERRCODE = '23514';
        END IF;
        IF TG_OP = 'UPDATE' AND pg_trigger_depth() < 2 AND
            (NEW.actual_chunk_count, NEW.actual_embedded_count, NEW.actual_index_bytes)
            IS DISTINCT FROM (OLD.actual_chunk_count, OLD.actual_embedded_count, OLD.actual_index_bytes) THEN
            RAISE EXCEPTION 'Index measurements are maintained by storage admission.' USING ERRCODE = '23514';
        END IF;
    END IF;
    IF TG_OP = 'INSERT' AND retained_count >= target_count THEN
        RAISE EXCEPTION 'Document revision capacity was exceeded.' USING ERRCODE = '23514';
    END IF;
    SELECT coalesce(sum(charge),0) INTO total_bytes FROM (
        SELECT reserved_page_bytes AS charge FROM subject_document_content_revisions WHERE document_id = document_key
        UNION ALL SELECT reserved_index_bytes FROM subject_document_index_revisions WHERE document_id = document_key
    ) AS charges;
    IF total_bytes + delta_bytes > 67108864 THEN
        RAISE EXCEPTION 'Document storage capacity was exceeded.' USING ERRCODE = '23514';
    END IF;
    PERFORM knowledge_adjust_usage(subject_key, owner_key, 0, delta_bytes);
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END $$
""",
"""
CREATE FUNCTION knowledge_page_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE revision_key uuid; parent subject_document_content_revisions%ROWTYPE;
    count_delta integer; chars_delta integer; bytes_delta integer;
BEGIN
    revision_key := CASE WHEN TG_OP = 'DELETE' THEN OLD.content_revision_id ELSE NEW.content_revision_id END;
    SELECT * INTO parent FROM subject_document_content_revisions WHERE id = revision_key FOR UPDATE;
    IF NOT FOUND AND TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    IF NOT FOUND THEN RAISE EXCEPTION 'Page content membership is invalid.' USING ERRCODE = '23503'; END IF;
    IF parent.status <> 'processing' THEN
        RAISE EXCEPTION 'Captured page text is immutable.' USING ERRCODE = '23514';
    END IF;
    IF TG_OP <> 'DELETE' AND NEW.page_number > parent.reserved_page_count THEN
        RAISE EXCEPTION 'Original page position exceeds the captured page count.' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' AND
        (NEW.id, NEW.content_revision_id, NEW.document_id, NEW.subject_id, NEW.uploader_id, NEW.page_number)
        IS DISTINCT FROM (OLD.id, OLD.content_revision_id, OLD.document_id, OLD.subject_id, OLD.uploader_id, OLD.page_number) THEN
        RAISE EXCEPTION 'Page content membership is immutable.' USING ERRCODE = '23514';
    END IF;
    count_delta := CASE WHEN TG_OP = 'INSERT' THEN 1 WHEN TG_OP = 'DELETE' THEN -1 ELSE 0 END;
    chars_delta := CASE WHEN TG_OP = 'INSERT' THEN length(NEW.content) WHEN TG_OP = 'DELETE' THEN -length(OLD.content)
        ELSE length(NEW.content) - length(OLD.content) END;
    bytes_delta := CASE WHEN TG_OP = 'INSERT' THEN octet_length(NEW.content) WHEN TG_OP = 'DELETE' THEN -octet_length(OLD.content)
        ELSE octet_length(NEW.content) - octet_length(OLD.content) END;
    UPDATE subject_document_content_revisions SET actual_page_count = actual_page_count + count_delta,
        actual_page_chars = actual_page_chars + chars_delta, actual_page_bytes = actual_page_bytes + bytes_delta
        WHERE id = revision_key;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END $$
""",
"""
CREATE FUNCTION knowledge_chunk_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE revision_key uuid; parent subject_document_index_revisions%ROWTYPE;
    count_delta integer; embedded_delta integer; bytes_delta bigint;
BEGIN
    revision_key := CASE WHEN TG_OP = 'DELETE' THEN OLD.index_revision_id ELSE NEW.index_revision_id END;
    SELECT * INTO parent FROM subject_document_index_revisions WHERE id = revision_key FOR UPDATE;
    IF NOT FOUND AND TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    IF NOT FOUND THEN RAISE EXCEPTION 'Chunk index membership is invalid.' USING ERRCODE = '23503'; END IF;
    IF TG_OP = 'DELETE' AND (NOT EXISTS(SELECT 1 FROM subject_documents WHERE id = parent.document_id) OR
        NOT EXISTS(SELECT 1 FROM subject_document_content_revisions WHERE id = parent.content_revision_id)) THEN
        RETURN OLD;
    END IF;
    IF parent.status NOT IN ('pending_index','indexing') THEN
        RAISE EXCEPTION 'Ready index chunks are immutable.' USING ERRCODE = '23514';
    END IF;
    IF TG_OP <> 'DELETE' AND NEW.chunk_index >= parent.reserved_chunk_count THEN
        RAISE EXCEPTION 'Chunk position exceeds the index chunk count.' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' AND
        (NEW.id, NEW.index_revision_id, NEW.content_revision_id, NEW.document_id, NEW.subject_id, NEW.uploader_id,
         NEW.chunk_index, NEW.page_number, NEW.embedding_space_hash)
        IS DISTINCT FROM
        (OLD.id, OLD.index_revision_id, OLD.content_revision_id, OLD.document_id, OLD.subject_id, OLD.uploader_id,
         OLD.chunk_index, OLD.page_number, OLD.embedding_space_hash) THEN
        RAISE EXCEPTION 'Chunk index membership is immutable.' USING ERRCODE = '23514';
    END IF;
    count_delta := CASE WHEN TG_OP = 'INSERT' THEN 1 WHEN TG_OP = 'DELETE' THEN -1 ELSE 0 END;
    embedded_delta := CASE WHEN TG_OP = 'INSERT' THEN (NEW.embedding IS NOT NULL)::integer
        WHEN TG_OP = 'DELETE' THEN -(OLD.embedding IS NOT NULL)::integer
        ELSE (NEW.embedding IS NOT NULL)::integer - (OLD.embedding IS NOT NULL)::integer END;
    -- Charge UTF-8 text/section, row allowance and full vector payload even
    -- before embedding. Missing vectors cannot create uncharged future growth.
    bytes_delta := CASE WHEN TG_OP = 'INSERT' THEN octet_length(NEW.content) + coalesce(octet_length(NEW.section),0) + 6408
        WHEN TG_OP = 'DELETE' THEN -(octet_length(OLD.content) + coalesce(octet_length(OLD.section),0) + 6408)
        ELSE octet_length(NEW.content) + coalesce(octet_length(NEW.section),0)
             - octet_length(OLD.content) - coalesce(octet_length(OLD.section),0) END;
    UPDATE subject_document_index_revisions SET actual_chunk_count = actual_chunk_count + count_delta,
        actual_embedded_count = actual_embedded_count + embedded_delta, actual_index_bytes = actual_index_bytes + bytes_delta
        WHERE id = revision_key;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END $$
""",
"""
CREATE FUNCTION knowledge_job_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' AND (NEW.status <> 'queued' OR NEW.attempt_count <> 0 OR NEW.worker_id IS NOT NULL OR
        NEW.claim_token IS NOT NULL OR NEW.heartbeat_at IS NOT NULL OR NEW.lease_expires_at IS NOT NULL OR
        NEW.cancellation_requested_at IS NOT NULL OR NEW.completed_at IS NOT NULL OR
        NEW.error_code IS NOT NULL OR NEW.error_message IS NOT NULL OR
        NEW.corpus_revision IS DISTINCT FROM (SELECT corpus_revision FROM subjects WHERE id = NEW.subject_id)) THEN
        RAISE EXCEPTION 'New index job snapshot is incompatible.' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.status IN ('completed','failed','cancelled') AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'Terminal index jobs are immutable.' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' AND NEW.status IS DISTINCT FROM OLD.status AND NOT (
        (OLD.status = 'queued' AND NEW.status IN ('running','failed','cancelled')) OR
        (OLD.status = 'running' AND NEW.status IN ('queued','completed','failed','cancelled'))
    ) THEN RAISE EXCEPTION 'Index job transition is invalid.' USING ERRCODE = '23514'; END IF;
    IF TG_OP = 'UPDATE' AND (NEW.attempt_count < OLD.attempt_count OR
        (NEW.attempt_count <> OLD.attempt_count AND NOT (OLD.status = 'queued' AND NEW.status = 'running'
            AND NEW.attempt_count = OLD.attempt_count + 1))) THEN
        RAISE EXCEPTION 'Index job attempts cannot be rewritten.' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.status = 'queued' AND NEW.status = 'running'
        AND NEW.attempt_count <> OLD.attempt_count + 1 THEN
        RAISE EXCEPTION 'Index job claims must charge one attempt.' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.status = 'running' AND NEW.status = 'running' AND
        (NEW.worker_id, NEW.claim_token) IS DISTINCT FROM (OLD.worker_id, OLD.claim_token) THEN
        RAISE EXCEPTION 'Running index job claim identity is immutable.' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' AND
        (NEW.id, NEW.index_revision_id, NEW.content_revision_id, NEW.document_id, NEW.subject_id, NEW.uploader_id,
         NEW.operation_key_hash, NEW.request_fingerprint, NEW.corpus_revision, NEW.created_at, NEW.deadline_at, NEW.max_attempts)
        IS DISTINCT FROM
        (OLD.id, OLD.index_revision_id, OLD.content_revision_id, OLD.document_id, OLD.subject_id, OLD.uploader_id,
         OLD.operation_key_hash, OLD.request_fingerprint, OLD.corpus_revision, OLD.created_at, OLD.deadline_at, OLD.max_attempts) THEN
        RAISE EXCEPTION 'Index job target and snapshot are immutable.' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.cancellation_requested_at IS NOT NULL AND
        NEW.cancellation_requested_at IS DISTINCT FROM OLD.cancellation_requested_at THEN
        RAISE EXCEPTION 'Index job cancellation cannot be removed.' USING ERRCODE = '23514';
    END IF;
    IF NEW.status = 'completed' AND NOT EXISTS(
        SELECT 1 FROM subject_document_index_revisions WHERE id = NEW.index_revision_id AND status = 'ready'
    ) THEN RAISE EXCEPTION 'Index job has no ready result.' USING ERRCODE = '23514'; END IF;
    RETURN NEW;
END $$
""",
"""
CREATE FUNCTION knowledge_bump_corpus() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE subject_key uuid; affects_corpus boolean := false;
BEGIN
    subject_key := CASE WHEN TG_OP = 'DELETE' THEN OLD.subject_id ELSE NEW.subject_id END;
    IF TG_TABLE_NAME = 'subject_document_content_revisions' THEN
        IF TG_OP = 'UPDATE' AND (NEW.status, NEW.is_active, NEW.reviewed_at, NEW.reviewed_by_id, NEW.published_at)
            IS NOT DISTINCT FROM (OLD.status, OLD.is_active, OLD.reviewed_at, OLD.reviewed_by_id, OLD.published_at) THEN
            RETURN NULL;
        END IF;
        affects_corpus := (TG_OP <> 'INSERT' AND OLD.is_active AND OLD.status = 'ready' AND OLD.published_at IS NOT NULL)
            OR (TG_OP <> 'DELETE' AND NEW.is_active AND NEW.status = 'ready' AND NEW.published_at IS NOT NULL);
    ELSE
        IF TG_OP = 'UPDATE' AND (NEW.status, NEW.is_active)
            IS NOT DISTINCT FROM (OLD.status, OLD.is_active) THEN RETURN NULL; END IF;
        affects_corpus := EXISTS (
            SELECT 1 FROM subject_document_content_revisions content JOIN subjects subject ON subject.id = content.subject_id
            WHERE content.id = CASE WHEN TG_OP = 'DELETE' THEN OLD.content_revision_id ELSE NEW.content_revision_id END
                AND content.is_active AND content.status = 'ready' AND content.published_at IS NOT NULL
                AND subject.active_embedding_space_hash = CASE WHEN TG_OP = 'DELETE' THEN OLD.embedding_space_hash ELSE NEW.embedding_space_hash END
        ) AND ((TG_OP <> 'INSERT' AND OLD.is_active AND OLD.status = 'ready')
            OR (TG_OP <> 'DELETE' AND NEW.is_active AND NEW.status = 'ready'));
    END IF;
    IF affects_corpus THEN UPDATE subjects SET corpus_revision = corpus_revision + 1 WHERE id = subject_key; END IF;
    RETURN NULL;
END $$
""",
"""
CREATE FUNCTION knowledge_subject_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.corpus_revision < OLD.corpus_revision THEN
        RAISE EXCEPTION 'Subject corpus revision cannot decrease.' USING ERRCODE = '23514';
    END IF;
    IF (NEW.active_embedding_space_hash, NEW.staged_embedding_space_hash)
        IS DISTINCT FROM (OLD.active_embedding_space_hash, OLD.staged_embedding_space_hash) THEN
        NEW.corpus_revision := greatest(NEW.corpus_revision, OLD.corpus_revision + 1);
    END IF;
    RETURN NEW;
END $$
""",
"""
CREATE FUNCTION knowledge_capture_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.knowledge_capture_removed AND NOT NEW.knowledge_capture_removed THEN
        RAISE EXCEPTION 'Removed Knowledge capture cannot be revived.' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$
""",
)


def _install_integrity():
    for ddl in FUNCTION_DDL:
        op.execute(sa.text(ddl))
    for table in LOCK_TABLES:
        events = PARENT_LOCK_EVENTS.get(table, 'INSERT OR UPDATE OR DELETE')
        op.execute(sa.text(f'CREATE TRIGGER knowledge_00_write_lock BEFORE {events} ON {table} FOR EACH STATEMENT EXECUTE FUNCTION knowledge_write_lock()'))
    guards = {
        'knowledge_storage_usage': 'knowledge_usage_guard', 'rag_embedding_spaces': 'knowledge_space_guard',
        'subject_documents': 'knowledge_document_guard',
        'subject_document_content_revisions': 'knowledge_revision_guard',
        'subject_document_index_revisions': 'knowledge_revision_guard',
        'subject_document_pages': 'knowledge_page_guard', 'subject_document_chunks': 'knowledge_chunk_guard',
    }
    for table, function in guards.items():
        op.execute(sa.text(f'CREATE TRIGGER knowledge_row_guard BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {function}()'))
    op.execute(sa.text('CREATE TRIGGER knowledge_row_guard BEFORE INSERT OR UPDATE ON subject_document_index_jobs FOR EACH ROW EXECUTE FUNCTION knowledge_job_guard()'))
    op.execute(sa.text('CREATE TRIGGER knowledge_subject_guard BEFORE UPDATE ON subjects FOR EACH ROW EXECUTE FUNCTION knowledge_subject_guard()'))
    op.execute(sa.text('CREATE TRIGGER knowledge_capture_guard BEFORE UPDATE ON generation_jobs FOR EACH ROW EXECUTE FUNCTION knowledge_capture_guard()'))
    for table in ('subject_document_content_revisions', 'subject_document_index_revisions'):
        op.execute(sa.text(f'CREATE TRIGGER knowledge_bump_corpus AFTER INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION knowledge_bump_corpus()'))
    op.execute(sa.text("""
        CREATE VIEW eligible_subject_knowledge_chunks AS
        SELECT chunk.*, document.title AS document_title, subject.corpus_revision
        FROM subject_document_chunks AS chunk
        JOIN subject_documents AS document ON document.id = chunk.document_id AND document.subject_id = chunk.subject_id
        JOIN subjects AS subject ON subject.id = chunk.subject_id
        JOIN subject_document_content_revisions AS content ON content.id = chunk.content_revision_id
            AND content.document_id = document.id AND content.subject_id = subject.id
        JOIN subject_document_index_revisions AS index_revision ON index_revision.id = chunk.index_revision_id
            AND index_revision.content_revision_id = content.id AND index_revision.subject_id = subject.id
        WHERE content.is_active AND content.status = 'ready' AND content.published_at IS NOT NULL
            AND content.reviewed_at IS NOT NULL AND content.reviewed_by_id = document.uploader_id
            AND index_revision.is_active AND index_revision.status = 'ready' AND chunk.embedding IS NOT NULL
            AND chunk.embedding_space_hash = index_revision.embedding_space_hash
            AND index_revision.embedding_space_hash = subject.active_embedding_space_hash
    """))


def _remove_integrity():
    op.execute(sa.text('DROP VIEW eligible_subject_knowledge_chunks'))
    for table in LOCK_TABLES:
        op.execute(sa.text(f'DROP TRIGGER knowledge_00_write_lock ON {table}'))
    for table in KNOWLEDGE_TABLES:
        op.execute(sa.text(f'DROP TRIGGER IF EXISTS knowledge_row_guard ON {table}'))
    for table in ('subject_document_content_revisions', 'subject_document_index_revisions'):
        op.execute(sa.text(f'DROP TRIGGER knowledge_bump_corpus ON {table}'))
    op.execute(sa.text('DROP TRIGGER knowledge_subject_guard ON subjects'))
    op.execute(sa.text('DROP TRIGGER knowledge_capture_guard ON generation_jobs'))
    for name in (
        'knowledge_capture_guard', 'knowledge_subject_guard', 'knowledge_bump_corpus', 'knowledge_job_guard',
        'knowledge_chunk_guard', 'knowledge_page_guard', 'knowledge_revision_guard', 'knowledge_document_guard',
        'knowledge_space_guard', 'knowledge_usage_guard', 'knowledge_write_lock',
    ):
        op.execute(sa.text(f'DROP FUNCTION {name}()'))
    op.execute(sa.text('DROP FUNCTION knowledge_adjust_usage(uuid,uuid,integer,bigint)'))
