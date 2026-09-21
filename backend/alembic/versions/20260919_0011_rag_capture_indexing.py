"""Add durable Knowledge capture and indexing execution state.

Revision ID: 20260919_0011
Revises: 20260918_0010
Create Date: 2026-09-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20260919_0011"
down_revision = "20260918_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generation_jobs",
        sa.Column("job_kind", sa.String(24), nullable=False, server_default="flashcards"),
    )
    op.add_column(
        "generation_jobs",
        sa.Column(
            "knowledge_capture_status",
            sa.String(24),
            nullable=False,
            server_default="not_requested",
        ),
    )
    op.add_column("generation_jobs", sa.Column("knowledge_capture_error_code", sa.String(64)))
    op.add_column("generation_jobs", sa.Column("knowledge_capture_error_message", sa.String(500)))
    op.add_column(
        "generation_jobs",
        sa.Column("knowledge_created_document", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "generation_jobs",
        sa.Column("knowledge_content_revision_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_generation_jobs_knowledge_content_revision",
        "generation_jobs",
        "subject_document_content_revisions",
        ["knowledge_content_revision_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint("ck_generation_jobs_card_count", "generation_jobs", type_="check")
    op.create_check_constraint(
        "ck_generation_jobs_card_count",
        "generation_jobs",
        "(job_kind = 'flashcards' AND requested_card_count BETWEEN 1 AND 500) OR "
        "(job_kind = 'knowledge_only' AND requested_card_count = 0)",
    )
    op.create_check_constraint(
        "ck_generation_jobs_kind",
        "generation_jobs",
        "job_kind IN ('flashcards','knowledge_only')",
    )
    op.create_check_constraint(
        "ck_generation_jobs_capture_status",
        "generation_jobs",
        "knowledge_capture_status IN ('not_requested','pending','captured','failed','removed')",
    )
    op.create_check_constraint(
        "ck_generation_jobs_capture_error_pair",
        "generation_jobs",
        "(knowledge_capture_error_code IS NULL AND knowledge_capture_error_message IS NULL) OR "
        "(knowledge_capture_status = 'failed' AND knowledge_capture_error_code IS NOT NULL "
        "AND knowledge_capture_error_message IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_generation_jobs_captured_revision",
        "generation_jobs",
        "knowledge_capture_status <> 'captured' OR "
        "(document_id IS NOT NULL AND knowledge_content_revision_id IS NOT NULL)",
    )

    # The reviewed OpenAI-compatible V1 uses one shared raw-input task mode for
    # both document and query vectors. Fixed columns make that compatibility
    # explicit; the existing identity hash implicitly includes these constants.
    for table in ("rag_embedding_spaces", "subject_document_index_revisions"):
        op.add_column(table, sa.Column(
            "document_task_mode", sa.String(32), nullable=False,
            server_default="shared_input",
        ))
        op.add_column(table, sa.Column(
            "query_task_mode", sa.String(32), nullable=False,
            server_default="shared_input",
        ))
    op.drop_constraint("ck_rag_embedding_spaces_identity", "rag_embedding_spaces", type_="check")
    op.create_check_constraint(
        "ck_rag_embedding_spaces_identity", "rag_embedding_spaces",
        "length(identity_hash) = 64 AND provider = 'openai_compatible' AND "
        "length(trim(base_url)) BETWEEN 1 AND 512 AND length(trim(model)) BETWEEN 1 AND 128 AND "
        "length(trim(space_revision)) BETWEEN 1 AND 64 AND format_version = 'raw_text_v1' AND "
        "dimensions = 1536 AND representation = 'float32' AND metric = 'cosine' AND "
        "document_task_mode = 'shared_input' AND query_task_mode = 'shared_input'",
    )
    op.create_unique_constraint(
        "uq_rag_embedding_spaces_task_modes", "rag_embedding_spaces",
        ["identity_hash", "document_task_mode", "query_task_mode"],
    )
    op.drop_constraint("ck_knowledge_index_identity", "subject_document_index_revisions", type_="check")
    op.create_check_constraint(
        "ck_knowledge_index_identity", "subject_document_index_revisions",
        "length(trim(chunker_version)) BETWEEN 1 AND 64 AND "
        "length(trim(embedding_provider)) BETWEEN 1 AND 32 AND "
        "length(trim(embedding_base_url)) BETWEEN 1 AND 512 AND "
        "length(trim(embedding_model)) BETWEEN 1 AND 128 AND "
        "length(trim(embedding_space_revision)) BETWEEN 1 AND 64 AND "
        "length(trim(embedding_format_version)) BETWEEN 1 AND 64 AND "
        "length(embedding_space_hash) = 64 AND document_task_mode = 'shared_input' AND "
        "query_task_mode = 'shared_input'",
    )
    op.create_foreign_key(
        "fk_knowledge_index_task_modes",
        "subject_document_index_revisions", "rag_embedding_spaces",
        ["embedding_space_hash", "document_task_mode", "query_task_mode"],
        ["identity_hash", "document_task_mode", "query_task_mode"],
    )
    op.add_column("subject_document_chunks", sa.Column("local_chunk_id", sa.String(64), nullable=True))
    op.execute(sa.text(
        "UPDATE subject_document_chunks SET local_chunk_id = "
        "'chunk-' || lpad((chunk_index + 1)::text, 4, '0') || '-p' || page_number::text"
    ))
    op.alter_column("subject_document_chunks", "local_chunk_id", nullable=False)
    op.create_unique_constraint(
        "uq_knowledge_chunks_local_id", "subject_document_chunks",
        ["index_revision_id", "local_chunk_id"],
    )
    op.create_check_constraint(
        "ck_knowledge_chunks_local_id", "subject_document_chunks",
        "local_chunk_id ~ '^chunk-[0-9]{4,}-p[0-9]+$'",
    )

    op.create_table(
        "knowledge_upload_quota_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", UUID(as_uuid=True), nullable=True),
        sa.Column("operation_key_hash", sa.String(64), nullable=False),
        sa.Column("job_units", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("upload_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["generation_jobs.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "operation_key_hash", name="uq_knowledge_upload_quota_operation"),
        sa.CheckConstraint("length(operation_key_hash) = 64", name="ck_knowledge_upload_quota_key_hash"),
        sa.CheckConstraint("job_units = 1", name="ck_knowledge_upload_quota_job_units"),
        sa.CheckConstraint("upload_bytes >= 0", name="ck_knowledge_upload_quota_bytes"),
    )
    op.create_index("ix_knowledge_upload_quota_user_created", "knowledge_upload_quota_events", ["user_id", "created_at"])
    op.create_index("ix_knowledge_upload_quota_created", "knowledge_upload_quota_events", ["created_at"])
    op.create_index("ix_knowledge_upload_quota_job_id", "knowledge_upload_quota_events", ["job_id"])

    index_columns = (
        sa.Column("provider_call_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual_input_tokens", sa.Integer(), nullable=True),
        sa.Column("provider_request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_rate_limit_wait_milliseconds", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_microusd", sa.BigInteger(), nullable=True),
        sa.Column("actual_cost_microusd", sa.BigInteger(), nullable=True),
        sa.Column("usage_estimated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    for column in index_columns:
        op.add_column("subject_document_index_jobs", column)
    op.create_check_constraint(
        "ck_knowledge_jobs_telemetry",
        "subject_document_index_jobs",
        "estimated_input_tokens >= 0 AND (actual_input_tokens IS NULL OR actual_input_tokens >= 0) AND "
        "provider_request_count >= 0 AND provider_retry_count >= 0 AND "
        "provider_retry_count <= provider_request_count AND provider_rate_limit_wait_milliseconds >= 0 AND "
        "(estimated_cost_microusd IS NULL OR estimated_cost_microusd >= 0) AND "
        "(actual_cost_microusd IS NULL OR actual_cost_microusd >= 0)",
    )

    op.drop_constraint("ck_worker_heartbeats_kind", "worker_heartbeats", type_="check")
    op.create_check_constraint(
        "ck_worker_heartbeats_kind",
        "worker_heartbeats",
        "kind IN ('generation','email','index')",
    )

    op.execute(sa.text("""
    CREATE OR REPLACE FUNCTION knowledge_document_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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
        UPDATE generation_jobs SET knowledge_capture_removed = true,
            knowledge_capture_status = 'removed', knowledge_content_revision_id = NULL,
            knowledge_created_document = false, knowledge_capture_error_code = NULL,
            knowledge_capture_error_message = NULL, document_id = NULL
            WHERE document_id = OLD.id;
        RETURN OLD;
    END $$
    """))


def downgrade() -> None:
    # Restore the Phase-13 trigger before removing fields it references.
    op.execute(sa.text("""
    CREATE OR REPLACE FUNCTION knowledge_document_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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
            UNION ALL SELECT reserved_index_bytes FROM subject_document_index_revisions WHERE document_id = OLD.id
        ) AS charges;
        PERFORM knowledge_adjust_usage(OLD.subject_id, OLD.uploader_id, -1, -total_bytes);
        UPDATE generation_jobs SET knowledge_capture_removed = true, document_id = NULL WHERE document_id = OLD.id;
        RETURN OLD;
    END $$
    """))
    op.drop_constraint("ck_worker_heartbeats_kind", "worker_heartbeats", type_="check")
    op.create_check_constraint("ck_worker_heartbeats_kind", "worker_heartbeats", "kind IN ('generation','email')")
    op.drop_constraint("ck_knowledge_jobs_telemetry", "subject_document_index_jobs", type_="check")
    for name in (
        "usage_estimated", "actual_cost_microusd", "estimated_cost_microusd",
        "provider_rate_limit_wait_milliseconds", "provider_retry_count",
        "provider_request_count", "actual_input_tokens", "estimated_input_tokens",
        "provider_call_started_at",
    ):
        op.drop_column("subject_document_index_jobs", name)
    op.drop_constraint("ck_knowledge_chunks_local_id", "subject_document_chunks", type_="check")
    op.drop_constraint("uq_knowledge_chunks_local_id", "subject_document_chunks", type_="unique")
    op.drop_column("subject_document_chunks", "local_chunk_id")
    op.drop_constraint("fk_knowledge_index_task_modes", "subject_document_index_revisions", type_="foreignkey")
    op.drop_constraint("ck_knowledge_index_identity", "subject_document_index_revisions", type_="check")
    op.create_check_constraint(
        "ck_knowledge_index_identity", "subject_document_index_revisions",
        "length(trim(chunker_version)) BETWEEN 1 AND 64 AND "
        "length(trim(embedding_provider)) BETWEEN 1 AND 32 AND "
        "length(trim(embedding_base_url)) BETWEEN 1 AND 512 AND "
        "length(trim(embedding_model)) BETWEEN 1 AND 128 AND "
        "length(trim(embedding_space_revision)) BETWEEN 1 AND 64 AND "
        "length(trim(embedding_format_version)) BETWEEN 1 AND 64 AND length(embedding_space_hash) = 64",
    )
    op.drop_column("subject_document_index_revisions", "query_task_mode")
    op.drop_column("subject_document_index_revisions", "document_task_mode")
    op.drop_constraint("uq_rag_embedding_spaces_task_modes", "rag_embedding_spaces", type_="unique")
    op.drop_constraint("ck_rag_embedding_spaces_identity", "rag_embedding_spaces", type_="check")
    op.create_check_constraint(
        "ck_rag_embedding_spaces_identity", "rag_embedding_spaces",
        "length(identity_hash) = 64 AND provider = 'openai_compatible' AND "
        "length(trim(base_url)) BETWEEN 1 AND 512 AND length(trim(model)) BETWEEN 1 AND 128 AND "
        "length(trim(space_revision)) BETWEEN 1 AND 64 AND format_version = 'raw_text_v1' AND "
        "dimensions = 1536 AND representation = 'float32' AND metric = 'cosine'",
    )
    op.drop_column("rag_embedding_spaces", "query_task_mode")
    op.drop_column("rag_embedding_spaces", "document_task_mode")
    op.drop_table("knowledge_upload_quota_events")
    for name in (
        "ck_generation_jobs_captured_revision", "ck_generation_jobs_capture_error_pair",
        "ck_generation_jobs_capture_status", "ck_generation_jobs_kind",
    ):
        op.drop_constraint(name, "generation_jobs", type_="check")
    op.drop_constraint("ck_generation_jobs_card_count", "generation_jobs", type_="check")
    # Phase 13 has no representation for zero-card Knowledge-only operations.
    # Preserve their durable documents/revisions, but remove the queue receipts
    # before restoring the older card-only invariant.
    op.execute(sa.text("DELETE FROM generation_jobs WHERE job_kind = 'knowledge_only'"))
    op.create_check_constraint("ck_generation_jobs_card_count", "generation_jobs", "requested_card_count BETWEEN 1 AND 500")
    op.drop_constraint("fk_generation_jobs_knowledge_content_revision", "generation_jobs", type_="foreignkey")
    for name in (
        "knowledge_content_revision_id", "knowledge_created_document",
        "knowledge_capture_error_message", "knowledge_capture_error_code",
        "knowledge_capture_status", "job_kind",
    ):
        op.drop_column("generation_jobs", name)
