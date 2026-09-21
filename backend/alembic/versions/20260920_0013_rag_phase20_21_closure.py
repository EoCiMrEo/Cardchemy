"""Complete Gemini RAG identity and Phase 21 operational metadata.

Revision ID: 20260920_0013
Revises: 20260919_0012
Create Date: 2026-09-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20260920_0013"
down_revision = "20260919_0012"
branch_labels = None
depends_on = None


_EMBEDDING_SPACE_CHECK = (
    "length(identity_hash) = 64 AND provider IN ('openai_compatible','gemini') AND "
    "length(trim(base_url)) BETWEEN 1 AND 512 AND length(trim(model)) BETWEEN 1 AND 128 AND "
    "length(trim(space_revision)) BETWEEN 1 AND 64 AND format_version = 'raw_text_v1' AND "
    "dimensions = 1536 AND representation = 'float32' AND metric = 'cosine' AND "
    "((provider = 'openai_compatible' AND document_task_mode = 'shared_input' "
    "AND query_task_mode = 'shared_input') OR "
    "(provider = 'gemini' AND document_task_mode = 'RETRIEVAL_DOCUMENT' "
    "AND query_task_mode = 'QUESTION_ANSWERING'))"
)

_INDEX_IDENTITY_CHECK = (
    "length(trim(chunker_version)) BETWEEN 1 AND 64 AND "
    "length(trim(embedding_provider)) BETWEEN 1 AND 32 AND "
    "length(trim(embedding_base_url)) BETWEEN 1 AND 512 AND "
    "length(trim(embedding_model)) BETWEEN 1 AND 128 AND "
    "length(trim(embedding_space_revision)) BETWEEN 1 AND 64 AND "
    "length(trim(embedding_format_version)) BETWEEN 1 AND 64 AND "
    "length(embedding_space_hash) = 64 AND "
    "((embedding_provider = 'openai_compatible' AND document_task_mode = 'shared_input' "
    "AND query_task_mode = 'shared_input') OR "
    "(embedding_provider = 'gemini' AND document_task_mode = 'RETRIEVAL_DOCUMENT' "
    "AND query_task_mode = 'QUESTION_ANSWERING'))"
)


_TEN_FIELD_SPACE_GUARD = """
CREATE OR REPLACE FUNCTION knowledge_space_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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
            NEW.dimensions::text, NEW.representation, NEW.metric,
            NEW.document_task_mode, NEW.query_task_mode
        ]) WITH ORDINALITY AS identity(value, position);
    computed := encode(sha256(convert_to(framed, 'UTF8')), 'hex');
    IF NEW.identity_hash IS DISTINCT FROM computed THEN
        RAISE EXCEPTION 'Embedding space identity is incompatible.' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$
"""


_EIGHT_FIELD_SPACE_GUARD = """
CREATE OR REPLACE FUNCTION knowledge_space_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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
"""


def upgrade() -> None:
    # Phase 13 added task modes to the durable vector-space identity, but the
    # original database guard still recomputed the pre-task-mode eight-field
    # hash. Keep PostgreSQL and the application on the same length-framed,
    # canonical ten-field identity before admitting native Gemini spaces.
    op.execute(sa.text(_TEN_FIELD_SPACE_GUARD))

    op.drop_constraint(
        "ck_rag_embedding_spaces_identity", "rag_embedding_spaces", type_="check"
    )
    op.create_check_constraint(
        "ck_rag_embedding_spaces_identity", "rag_embedding_spaces", _EMBEDDING_SPACE_CHECK
    )
    op.drop_constraint(
        "ck_knowledge_index_identity", "subject_document_index_revisions", type_="check"
    )
    op.create_check_constraint(
        "ck_knowledge_index_identity",
        "subject_document_index_revisions",
        _INDEX_IDENTITY_CHECK,
    )

    op.add_column(
        "generation_jobs",
        sa.Column("knowledge_capture_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "generation_jobs",
        sa.Column("knowledge_capture_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_generation_jobs_capture_timing",
        "generation_jobs",
        "knowledge_capture_started_at IS NULL OR knowledge_capture_completed_at IS NULL "
        "OR knowledge_capture_completed_at >= knowledge_capture_started_at",
    )

    op.add_column(
        "subject_document_index_jobs",
        sa.Column("request_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "rag_answer_jobs", sa.Column("request_id", UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "rag_answer_jobs",
        sa.Column("retrieval_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_rag_answer_jobs_retrieval_timing",
        "rag_answer_jobs",
        "retrieval_completed_at IS NULL OR (provider_call_started_at IS NOT NULL "
        "AND retrieval_completed_at >= provider_call_started_at)",
    )
    op.execute(sa.text("""
    CREATE FUNCTION immutable_rag_request_id_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF NEW.request_id IS DISTINCT FROM OLD.request_id THEN
            RAISE EXCEPTION 'Originating request identity is immutable.' USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END $$
    """))
    for table in ("subject_document_index_jobs", "rag_answer_jobs"):
        op.execute(sa.text(
            f"CREATE TRIGGER immutable_request_id BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION immutable_rag_request_id_guard()"
        ))

    op.drop_constraint("ck_audit_events_action", "audit_events", type_="check")
    op.create_check_constraint(
        "ck_audit_events_action",
        "audit_events",
        "action IN ('invitation.created', 'card.approved', 'card.unapproved', "
        "'cards.approved', 'set.published', 'set.unpublished', "
        "'knowledge.published', 'knowledge.unpublished', 'knowledge.removed', "
        "'account.instructor_provisioned', 'account.role_changed', 'account.deleted')",
    )
    op.drop_constraint("ck_audit_events_target_type", "audit_events", type_="check")
    op.create_check_constraint(
        "ck_audit_events_target_type",
        "audit_events",
        "target_type IN ('invitation', 'card', 'set', 'knowledge', 'account')",
    )


def downgrade() -> None:
    # Native Gemini vectors and answer snapshots cannot be interpreted by the
    # OpenAI-compatible-only prior revision. Preserve extracted pages for a
    # later rebuild, but remove provider-specific indexes/conversations and
    # clear Subject cutovers before narrowing the identity constraints. Never
    # relabel vectors across providers or task modes.
    op.execute(sa.text("""
        DELETE FROM rag_threads
        WHERE id IN (
            SELECT thread_id FROM rag_answer_jobs
            WHERE embedding_space_hash IN (
                SELECT identity_hash FROM rag_embedding_spaces WHERE provider = 'gemini'
            )
        ) OR id IN (
            SELECT thread_id FROM rag_messages
            WHERE embedding_space_hash IN (
                SELECT identity_hash FROM rag_embedding_spaces WHERE provider = 'gemini'
            )
        )
    """))
    op.execute(sa.text("""
        UPDATE subjects
        SET active_embedding_space_hash = NULL,
            staged_embedding_space_hash = NULL
        WHERE active_embedding_space_hash IN (
            SELECT identity_hash FROM rag_embedding_spaces WHERE provider = 'gemini'
        ) OR staged_embedding_space_hash IN (
            SELECT identity_hash FROM rag_embedding_spaces WHERE provider = 'gemini'
        )
    """))
    op.execute(sa.text(
        "DELETE FROM subject_document_index_revisions "
        "WHERE embedding_space_hash IN ("
        "SELECT identity_hash FROM rag_embedding_spaces WHERE provider = 'gemini')"
    ))
    op.execute(sa.text("DELETE FROM rag_embedding_spaces WHERE provider = 'gemini'"))

    # The prior schema cannot represent Phase 21 Knowledge audit actions. A
    # downgrade is already a separately authorized, backup-gated operation;
    # make this narrow loss explicit instead of allowing constraint creation to
    # fail midway through rollback.
    op.execute(sa.text(
        "DELETE FROM audit_events WHERE target_type = 'knowledge' OR "
        "action IN ('knowledge.published','knowledge.unpublished','knowledge.removed')"
    ))
    op.drop_constraint("ck_audit_events_target_type", "audit_events", type_="check")
    op.create_check_constraint(
        "ck_audit_events_target_type",
        "audit_events",
        "target_type IN ('invitation', 'card', 'set', 'account')",
    )
    op.drop_constraint("ck_audit_events_action", "audit_events", type_="check")
    op.create_check_constraint(
        "ck_audit_events_action",
        "audit_events",
        "action IN ('invitation.created', 'card.approved', 'card.unapproved', "
        "'cards.approved', 'set.published', 'set.unpublished', "
        "'account.instructor_provisioned', 'account.role_changed', 'account.deleted')",
    )

    for table in ("rag_answer_jobs", "subject_document_index_jobs"):
        op.execute(sa.text(f"DROP TRIGGER immutable_request_id ON {table}"))
    op.execute(sa.text("DROP FUNCTION immutable_rag_request_id_guard()"))
    op.drop_constraint(
        "ck_rag_answer_jobs_retrieval_timing", "rag_answer_jobs", type_="check"
    )
    op.drop_column("rag_answer_jobs", "retrieval_completed_at")
    op.drop_column("rag_answer_jobs", "request_id")
    op.drop_column("subject_document_index_jobs", "request_id")
    op.drop_constraint(
        "ck_generation_jobs_capture_timing", "generation_jobs", type_="check"
    )
    op.drop_column("generation_jobs", "knowledge_capture_completed_at")
    op.drop_column("generation_jobs", "knowledge_capture_started_at")

    op.drop_constraint(
        "ck_knowledge_index_identity", "subject_document_index_revisions", type_="check"
    )
    op.create_check_constraint(
        "ck_knowledge_index_identity",
        "subject_document_index_revisions",
        "length(trim(chunker_version)) BETWEEN 1 AND 64 AND "
        "length(trim(embedding_provider)) BETWEEN 1 AND 32 AND "
        "length(trim(embedding_base_url)) BETWEEN 1 AND 512 AND "
        "length(trim(embedding_model)) BETWEEN 1 AND 128 AND "
        "length(trim(embedding_space_revision)) BETWEEN 1 AND 64 AND "
        "length(trim(embedding_format_version)) BETWEEN 1 AND 64 AND "
        "length(embedding_space_hash) = 64 AND document_task_mode = 'shared_input' AND "
        "query_task_mode = 'shared_input'",
    )
    op.drop_constraint(
        "ck_rag_embedding_spaces_identity", "rag_embedding_spaces", type_="check"
    )
    op.create_check_constraint(
        "ck_rag_embedding_spaces_identity",
        "rag_embedding_spaces",
        "length(identity_hash) = 64 AND provider = 'openai_compatible' AND "
        "length(trim(base_url)) BETWEEN 1 AND 512 AND length(trim(model)) BETWEEN 1 AND 128 AND "
        "length(trim(space_revision)) BETWEEN 1 AND 64 AND format_version = 'raw_text_v1' AND "
        "dimensions = 1536 AND representation = 'float32' AND metric = 'cosine' AND "
        "document_task_mode = 'shared_input' AND query_task_mode = 'shared_input'",
    )
    op.execute(sa.text(_EIGHT_FIELD_SPACE_GUARD))
