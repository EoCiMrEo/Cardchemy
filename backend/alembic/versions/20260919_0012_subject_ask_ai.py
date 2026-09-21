"""Add private Subject Ask AI conversations and durable answer jobs.

Revision ID: 20260919_0012
Revises: 20260919_0011
Create Date: 2026-09-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "20260919_0012"
down_revision = "20260919_0011"
branch_labels = None
depends_on = None


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


def upgrade() -> None:
    op.create_unique_constraint("uq_auth_sessions_user_scope", "auth_sessions", ["id", "user_id"])
    op.create_unique_constraint(
        "uq_knowledge_chunks_rag_source_scope",
        "subject_document_chunks",
        ["id", "index_revision_id", "content_revision_id", "document_id", "subject_id"],
    )

    op.create_table(
        "rag_threads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("id", "user_id", "subject_id", name="uq_rag_threads_scope"),
    )
    op.create_index("ix_rag_threads_owner_updated", "rag_threads", ["user_id", "subject_id", "updated_at", "id"])
    op.create_index("ix_rag_threads_subject", "rag_threads", ["subject_id", "id"])
    op.create_index("ix_rag_threads_updated", "rag_threads", ["updated_at", "id"])

    op.create_table(
        "rag_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("thread_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("corpus_revision", sa.BigInteger(), nullable=True),
        sa.Column("embedding_space_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["thread_id", "user_id", "subject_id"],
            ["rag_threads.id", "rag_threads.user_id", "rag_threads.subject_id"],
            ondelete="CASCADE",
            name="fk_rag_messages_thread_scope",
        ),
        sa.UniqueConstraint("id", "thread_id", "user_id", "subject_id", name="uq_rag_messages_scope"),
        sa.CheckConstraint("role IN ('user','assistant')", name="ck_rag_messages_role"),
        sa.CheckConstraint(
            "(role = 'user' AND outcome IS NULL AND source_count = 0 AND corpus_revision IS NULL "
            "AND embedding_space_hash IS NULL AND length(content) BETWEEN 1 AND 4000) OR "
            "(role = 'assistant' AND outcome IN ('answer','abstained') AND length(content) BETWEEN 1 AND 12000 "
            "AND corpus_revision IS NOT NULL AND corpus_revision >= 0 "
            "AND embedding_space_hash IS NOT NULL AND length(embedding_space_hash) = 64 "
            "AND ((outcome = 'answer' AND source_count BETWEEN 1 AND 5) "
            "OR (outcome = 'abstained' AND source_count = 0)))",
            name="ck_rag_messages_shape",
        ),
        sa.CheckConstraint("expires_at > created_at", name="ck_rag_messages_expiry"),
    )
    op.create_index("ix_rag_messages_thread_created", "rag_messages", ["thread_id", "created_at", "id"])
    op.create_index("ix_rag_messages_owner_expiry", "rag_messages", ["user_id", "expires_at", "id"])
    op.create_index("ix_rag_messages_expiry", "rag_messages", ["expires_at", "id"])

    op.create_table(
        "rag_message_sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("message_id", UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("content_revision_id", UUID(as_uuid=True), nullable=False),
        sa.Column("index_revision_id", UUID(as_uuid=True), nullable=False),
        sa.Column("citation_order", sa.Integer(), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("source_quote", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["message_id", "thread_id", "user_id", "subject_id"],
            ["rag_messages.id", "rag_messages.thread_id", "rag_messages.user_id", "rag_messages.subject_id"],
            ondelete="CASCADE",
            name="fk_rag_sources_message_scope",
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id", "index_revision_id", "content_revision_id", "document_id", "subject_id"],
            ["subject_document_chunks.id", "subject_document_chunks.index_revision_id",
             "subject_document_chunks.content_revision_id", "subject_document_chunks.document_id",
             "subject_document_chunks.subject_id"],
            ondelete="CASCADE",
            name="fk_rag_sources_chunk_scope",
        ),
        sa.UniqueConstraint("message_id", "citation_order", name="uq_rag_sources_order"),
        sa.UniqueConstraint("message_id", "chunk_id", name="uq_rag_sources_chunk"),
        sa.CheckConstraint("citation_order BETWEEN 1 AND 5", name="ck_rag_sources_order"),
        sa.CheckConstraint("length(claim_text) BETWEEN 1 AND 4000", name="ck_rag_sources_claim"),
        sa.CheckConstraint("length(source_quote) BETWEEN 1 AND 12000", name="ck_rag_sources_quote"),
    )
    op.create_index("ix_rag_sources_message", "rag_message_sources", ["message_id", "citation_order"])
    op.create_index("ix_rag_sources_chunk", "rag_message_sources", ["chunk_id", "message_id"])
    op.create_index("ix_rag_sources_document", "rag_message_sources", ["document_id", "content_revision_id"])

    op.create_table(
        "rag_answer_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("thread_id", UUID(as_uuid=True), nullable=False),
        sa.Column("question_message_id", UUID(as_uuid=True), nullable=False),
        sa.Column("answer_message_id", UUID(as_uuid=True), nullable=True),
        sa.Column("auth_session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("operation_key_hash", sa.String(64), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("document_ids", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("corpus_revision", sa.BigInteger(), nullable=False),
        sa.Column("retrieval_policy", sa.String(64), nullable=False),
        sa.Column("embedding_space_hash", sa.String(64), nullable=False),
        sa.Column("ai_provider", sa.String(32), nullable=False),
        sa.Column("ai_base_url", sa.String(512), nullable=False),
        sa.Column("ai_model", sa.String(128), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("manual_retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("worker_id", sa.String(128), nullable=True),
        sa.Column("claim_token", sa.String(64), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_call_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual_input_tokens", sa.Integer(), nullable=True),
        sa.Column("actual_output_tokens", sa.Integer(), nullable=True),
        sa.Column("provider_request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_rate_limit_wait_milliseconds", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_microusd", sa.BigInteger(), nullable=True),
        sa.Column("actual_cost_microusd", sa.BigInteger(), nullable=True),
        sa.Column("usage_estimated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("support_rejection_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("error_retryable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["thread_id", "user_id", "subject_id"],
            ["rag_threads.id", "rag_threads.user_id", "rag_threads.subject_id"],
            ondelete="CASCADE", name="fk_rag_answer_jobs_thread_scope",
        ),
        sa.ForeignKeyConstraint(
            ["auth_session_id", "user_id"],
            ["auth_sessions.id", "auth_sessions.user_id"],
            ondelete="CASCADE", name="fk_rag_answer_jobs_auth_session",
        ),
        sa.ForeignKeyConstraint(
            ["question_message_id", "thread_id", "user_id", "subject_id"],
            ["rag_messages.id", "rag_messages.thread_id", "rag_messages.user_id", "rag_messages.subject_id"],
            ondelete="CASCADE", name="fk_rag_answer_jobs_question_scope",
        ),
        sa.ForeignKeyConstraint(
            ["answer_message_id", "thread_id", "user_id", "subject_id"],
            ["rag_messages.id", "rag_messages.thread_id", "rag_messages.user_id", "rag_messages.subject_id"],
            name="fk_rag_answer_jobs_answer_scope",
        ),
        sa.UniqueConstraint("question_message_id", name="uq_rag_answer_jobs_question"),
        sa.UniqueConstraint("answer_message_id", name="uq_rag_answer_jobs_answer"),
        sa.UniqueConstraint("user_id", "operation_key_hash", name="uq_rag_answer_jobs_operation"),
        sa.CheckConstraint("status IN ('queued','running','completed','failed','cancelled')", name="ck_rag_answer_jobs_status"),
        sa.CheckConstraint(
            "length(operation_key_hash) = 64 AND length(request_fingerprint) = 64 "
            "AND corpus_revision >= 0 AND length(embedding_space_hash) = 64 "
            "AND length(trim(retrieval_policy)) BETWEEN 1 AND 64 "
            "AND length(trim(ai_provider)) BETWEEN 1 AND 32 "
            "AND length(trim(ai_base_url)) BETWEEN 1 AND 512 "
            "AND length(trim(ai_model)) BETWEEN 1 AND 128",
            name="ck_rag_answer_jobs_identity",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(document_ids) = 'array' AND jsonb_array_length(document_ids) <= 50",
            name="ck_rag_answer_jobs_documents",
        ),
        sa.CheckConstraint(
            "attempt_count BETWEEN 0 AND max_attempts AND max_attempts BETWEEN 1 AND 10 "
            "AND manual_retry_count BETWEEN 0 AND 10", name="ck_rag_answer_jobs_attempts",
        ),
        sa.CheckConstraint(
            "estimated_input_tokens >= 0 AND estimated_output_tokens >= 0 "
            "AND (actual_input_tokens IS NULL OR actual_input_tokens >= 0) "
            "AND (actual_output_tokens IS NULL OR actual_output_tokens >= 0) "
            "AND provider_request_count >= 0 AND provider_retry_count >= 0 "
            "AND provider_retry_count <= provider_request_count "
            "AND provider_rate_limit_wait_milliseconds >= 0 "
            "AND (estimated_cost_microusd IS NULL OR estimated_cost_microusd >= 0) "
            "AND (actual_cost_microusd IS NULL OR actual_cost_microusd >= 0) "
            "AND support_rejection_count >= 0", name="ck_rag_answer_jobs_telemetry",
        ),
        sa.CheckConstraint(
            "status <> 'running' OR (worker_id IS NOT NULL AND claim_token IS NOT NULL "
            "AND attempt_count >= 1 AND length(trim(worker_id)) BETWEEN 1 AND 128 "
            "AND length(claim_token) = 64 AND heartbeat_at IS NOT NULL "
            "AND lease_expires_at IS NOT NULL AND heartbeat_at <= lease_expires_at "
            "AND lease_expires_at <= deadline_at)", name="ck_rag_answer_jobs_running_claim",
        ),
        sa.CheckConstraint(
            "(status IN ('completed','failed','cancelled') AND completed_at IS NOT NULL) OR "
            "(status IN ('queued','running') AND completed_at IS NULL)", name="ck_rag_answer_jobs_terminal",
        ),
        sa.CheckConstraint(
            "(status = 'completed' AND answer_message_id IS NOT NULL AND error_code IS NULL) OR "
            "(status <> 'completed' AND answer_message_id IS NULL)", name="ck_rag_answer_jobs_result",
        ),
        sa.CheckConstraint(ANSWER_ERROR_PAIRS, name="ck_rag_answer_jobs_error_pair"),
        sa.CheckConstraint("available_at <= deadline_at AND created_at <= deadline_at", name="ck_rag_answer_jobs_deadline"),
    )
    op.create_index("ix_rag_answer_jobs_queue", "rag_answer_jobs", ["available_at", "created_at", "id"], postgresql_where=sa.text("status = 'queued'"))
    op.create_index("ix_rag_answer_jobs_running_lease", "rag_answer_jobs", ["lease_expires_at", "id"], postgresql_where=sa.text("status = 'running'"))
    op.create_index("ix_rag_answer_jobs_owner_created", "rag_answer_jobs", ["user_id", "subject_id", "created_at", "id"])
    op.create_index("ix_rag_answer_jobs_thread_created", "rag_answer_jobs", ["thread_id", "created_at", "id"])
    op.create_index("ix_rag_answer_jobs_auth_session", "rag_answer_jobs", ["auth_session_id", "id"])

    op.create_table(
        "rag_answer_quota_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", UUID(as_uuid=True), nullable=True),
        sa.Column("operation_key_hash", sa.String(64), nullable=False),
        sa.Column("job_units", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["rag_answer_jobs.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "operation_key_hash", name="uq_rag_answer_quota_operation"),
        sa.CheckConstraint("length(operation_key_hash) = 64", name="ck_rag_answer_quota_key_hash"),
        sa.CheckConstraint("job_units = 1", name="ck_rag_answer_quota_job_units"),
    )
    op.create_index("ix_rag_answer_quota_user_created", "rag_answer_quota_events", ["user_id", "created_at"])
    op.create_index("ix_rag_answer_quota_created", "rag_answer_quota_events", ["created_at"])
    op.create_index("ix_rag_answer_quota_job", "rag_answer_quota_events", ["job_id"])

    op.drop_constraint("ck_worker_heartbeats_kind", "worker_heartbeats", type_="check")
    op.create_check_constraint(
        "ck_worker_heartbeats_kind", "worker_heartbeats",
        "kind IN ('generation','email','index','answer')",
    )

    op.execute(sa.text("""
    CREATE FUNCTION rag_message_source_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE answer rag_messages%ROWTYPE; source_row record;
    BEGIN
        SELECT * INTO answer FROM rag_messages WHERE id = NEW.message_id;
        IF NOT FOUND OR answer.role <> 'assistant' OR answer.outcome <> 'answer' THEN
            RAISE EXCEPTION 'Citation target is not an answer.' USING ERRCODE = '23514';
        END IF;
        SELECT * INTO source_row FROM eligible_subject_knowledge_chunks
        WHERE id = NEW.chunk_id AND index_revision_id = NEW.index_revision_id
          AND content_revision_id = NEW.content_revision_id AND document_id = NEW.document_id
          AND subject_id = NEW.subject_id AND corpus_revision = answer.corpus_revision
          AND embedding_space_hash = answer.embedding_space_hash;
        IF NOT FOUND OR position(NEW.source_quote IN source_row.content) = 0 THEN
            RAISE EXCEPTION 'Citation is not current grounded evidence.' USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END $$
    """))
    op.execute(sa.text("""
    CREATE FUNCTION rag_answer_job_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE question rag_messages%ROWTYPE; answer rag_messages%ROWTYPE;
            source_total integer; source_min integer; source_max integer;
    BEGIN
        IF TG_OP = 'INSERT' THEN
            SELECT * INTO question FROM rag_messages WHERE id = NEW.question_message_id;
            IF NOT FOUND OR question.role <> 'user' OR NEW.status <> 'queued' OR NEW.attempt_count <> 0
                OR NEW.worker_id IS NOT NULL OR NEW.claim_token IS NOT NULL OR NEW.answer_message_id IS NOT NULL
                OR NEW.completed_at IS NOT NULL OR NEW.error_code IS NOT NULL THEN
                RAISE EXCEPTION 'New answer job is incompatible.' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END IF;
        IF OLD.status IN ('completed','cancelled') AND NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'Terminal answer jobs are immutable.' USING ERRCODE = '23514';
        END IF;
        IF NEW.status IS DISTINCT FROM OLD.status AND NOT (
            (OLD.status = 'queued' AND NEW.status IN ('running','failed','cancelled')) OR
            (OLD.status = 'running' AND NEW.status IN ('queued','completed','failed','cancelled')) OR
            (OLD.status = 'failed' AND NEW.status = 'queued')
        ) THEN RAISE EXCEPTION 'Answer job transition is invalid.' USING ERRCODE = '23514'; END IF;
        IF NEW.attempt_count <> OLD.attempt_count AND NOT (
               (OLD.status = 'queued' AND NEW.status = 'running' AND NEW.attempt_count = OLD.attempt_count + 1)
               OR (OLD.status = 'failed' AND NEW.status = 'queued' AND NEW.attempt_count = 0)
           ) THEN RAISE EXCEPTION 'Answer job attempts cannot be rewritten.' USING ERRCODE = '23514'; END IF;
        IF OLD.status = 'running' AND NEW.status = 'running' AND
           (NEW.worker_id, NEW.claim_token) IS DISTINCT FROM (OLD.worker_id, OLD.claim_token) THEN
            RAISE EXCEPTION 'Running answer claim identity is immutable.' USING ERRCODE = '23514';
        END IF;
        IF (NEW.id, NEW.thread_id, NEW.question_message_id, NEW.user_id, NEW.subject_id,
            NEW.operation_key_hash, NEW.request_fingerprint, NEW.document_ids, NEW.corpus_revision, NEW.retrieval_policy,
            NEW.embedding_space_hash, NEW.ai_provider, NEW.ai_base_url, NEW.ai_model, NEW.created_at, NEW.max_attempts)
           IS DISTINCT FROM
           (OLD.id, OLD.thread_id, OLD.question_message_id, OLD.user_id, OLD.subject_id,
            OLD.operation_key_hash, OLD.request_fingerprint, OLD.document_ids, OLD.corpus_revision, OLD.retrieval_policy,
            OLD.embedding_space_hash, OLD.ai_provider, OLD.ai_base_url, OLD.ai_model, OLD.created_at, OLD.max_attempts)
        THEN RAISE EXCEPTION 'Answer target and snapshots are immutable.' USING ERRCODE = '23514'; END IF;
        IF NEW.auth_session_id IS DISTINCT FROM OLD.auth_session_id AND NOT
           (OLD.status = 'failed' AND NEW.status = 'queued') THEN
            RAISE EXCEPTION 'Answer authorization session cannot be rewritten.' USING ERRCODE = '23514';
        END IF;
        IF NEW.manual_retry_count IS DISTINCT FROM OLD.manual_retry_count AND NOT
           (OLD.status = 'failed' AND NEW.status = 'queued'
            AND NEW.manual_retry_count = OLD.manual_retry_count + 1) THEN
            RAISE EXCEPTION 'Manual answer retry count is invalid.' USING ERRCODE = '23514';
        END IF;
        IF OLD.status = 'failed' AND NEW.status = 'queued' AND
           NEW.manual_retry_count <> OLD.manual_retry_count + 1 THEN
            RAISE EXCEPTION 'Manual answer retry was not charged.' USING ERRCODE = '23514';
        END IF;
        IF NEW.status = 'completed' THEN
            SELECT * INTO answer FROM rag_messages WHERE id = NEW.answer_message_id;
            SELECT count(*), min(citation_order), max(citation_order)
              INTO source_total, source_min, source_max
              FROM rag_message_sources WHERE message_id = NEW.answer_message_id;
            IF answer.id IS NULL OR answer.role <> 'assistant' OR answer.thread_id <> NEW.thread_id
               OR answer.user_id <> NEW.user_id OR answer.subject_id <> NEW.subject_id
               OR answer.corpus_revision <> NEW.corpus_revision
               OR answer.embedding_space_hash <> NEW.embedding_space_hash
               OR answer.source_count <> source_total
               OR (answer.outcome = 'answer' AND source_total = 0)
               OR (answer.outcome = 'answer' AND (source_min <> 1 OR source_max <> source_total))
               OR (answer.outcome = 'abstained' AND source_total <> 0)
               OR NOT EXISTS (SELECT 1 FROM subjects WHERE id = NEW.subject_id
                   AND corpus_revision = NEW.corpus_revision
                   AND (answer.outcome = 'abstained' OR active_embedding_space_hash = NEW.embedding_space_hash))
            THEN RAISE EXCEPTION 'Completed answer is not current and atomic.' USING ERRCODE = '23514'; END IF;
        END IF;
        RETURN NEW;
    END $$
    """))
    op.execute(sa.text(
        "CREATE TRIGGER rag_message_source_guard BEFORE INSERT OR UPDATE ON rag_message_sources "
        "FOR EACH ROW EXECUTE FUNCTION rag_message_source_guard()"
    ))
    op.execute(sa.text(
        "CREATE TRIGGER rag_answer_job_guard BEFORE INSERT OR UPDATE ON rag_answer_jobs "
        "FOR EACH ROW EXECUTE FUNCTION rag_answer_job_guard()"
    ))


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER rag_answer_job_guard ON rag_answer_jobs"))
    op.execute(sa.text("DROP TRIGGER rag_message_source_guard ON rag_message_sources"))
    op.execute(sa.text("DROP FUNCTION rag_answer_job_guard()"))
    op.execute(sa.text("DROP FUNCTION rag_message_source_guard()"))
    op.drop_constraint("ck_worker_heartbeats_kind", "worker_heartbeats", type_="check")
    op.create_check_constraint(
        "ck_worker_heartbeats_kind", "worker_heartbeats",
        "kind IN ('generation','email','index')",
    )
    op.drop_table("rag_answer_quota_events")
    op.drop_table("rag_answer_jobs")
    op.drop_table("rag_message_sources")
    op.drop_table("rag_messages")
    op.drop_table("rag_threads")
    op.drop_constraint(
        "uq_knowledge_chunks_rag_source_scope", "subject_document_chunks", type_="unique"
    )
    op.drop_constraint("uq_auth_sessions_user_scope", "auth_sessions", type_="unique")
