"""Admit immutable source-navigation jobs without reinterpreting older policies.

Revision ID: 20260927_0027
Revises: 20260927_0026
"""
from alembic import op
import sqlalchemy as sa

revision = "20260927_0027"
down_revision = "20260927_0026"
branch_labels = None
depends_on = None

OLD_IDENTITY = "length(operation_key_hash) = 64 AND length(request_fingerprint) = 64 AND corpus_revision >= 0 AND length(embedding_space_hash) = 64 AND length(trim(retrieval_policy)) BETWEEN 1 AND 64 AND ((answer_policy_version = 'related_knowledge_v1' AND ai_provider IS NULL AND ai_base_url IS NULL AND ai_model IS NULL AND support_policy_version IS NULL AND embedding_provider IS NOT NULL AND embedding_base_url IS NOT NULL AND embedding_model IS NOT NULL AND length(trim(embedding_provider)) BETWEEN 1 AND 32 AND length(trim(embedding_base_url)) BETWEEN 1 AND 512 AND length(trim(embedding_model)) BETWEEN 1 AND 128) OR ((answer_policy_version IS NULL OR answer_policy_version <> 'related_knowledge_v1') AND embedding_provider IS NULL AND embedding_base_url IS NULL AND embedding_model IS NULL AND ai_provider IS NOT NULL AND ai_base_url IS NOT NULL AND ai_model IS NOT NULL AND length(trim(ai_provider)) BETWEEN 1 AND 32 AND length(trim(ai_base_url)) BETWEEN 1 AND 512 AND length(trim(ai_model)) BETWEEN 1 AND 128))"

NEW_IDENTITY = "length(operation_key_hash) = 64 AND length(request_fingerprint) = 64 AND corpus_revision >= 0 AND length(embedding_space_hash) = 64 AND length(trim(retrieval_policy)) BETWEEN 1 AND 64 AND ((answer_policy_version IN ('related_knowledge_v1','related_knowledge_navigation_v2') AND ai_provider IS NULL AND ai_base_url IS NULL AND ai_model IS NULL AND support_policy_version IS NULL AND embedding_provider IS NOT NULL AND embedding_base_url IS NOT NULL AND embedding_model IS NOT NULL AND length(trim(embedding_provider)) BETWEEN 1 AND 32 AND length(trim(embedding_base_url)) BETWEEN 1 AND 512 AND length(trim(embedding_model)) BETWEEN 1 AND 128) OR ((answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_v1','related_knowledge_navigation_v2')) AND embedding_provider IS NULL AND embedding_base_url IS NULL AND embedding_model IS NULL AND ai_provider IS NOT NULL AND ai_base_url IS NOT NULL AND ai_model IS NOT NULL AND length(trim(ai_provider)) BETWEEN 1 AND 32 AND length(trim(ai_base_url)) BETWEEN 1 AND 512 AND length(trim(ai_model)) BETWEEN 1 AND 128))"

OLD_RESULT = "(status = 'completed' AND answer_policy_version = 'related_knowledge_v1' AND result_kind IN ('related_knowledge','no_match') AND answer_message_id IS NULL AND error_code IS NULL) OR (status = 'completed' AND (answer_policy_version IS NULL OR answer_policy_version <> 'related_knowledge_v1') AND result_kind IS NULL AND answer_message_id IS NOT NULL AND error_code IS NULL) OR (status <> 'completed' AND result_kind IS NULL AND answer_message_id IS NULL)"

NEW_RESULT = "(status = 'completed' AND answer_policy_version IN ('related_knowledge_v1','related_knowledge_navigation_v2') AND result_kind IN ('related_knowledge','no_match') AND answer_message_id IS NULL AND error_code IS NULL) OR (status = 'completed' AND (answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_v1','related_knowledge_navigation_v2')) AND result_kind IS NULL AND answer_message_id IS NOT NULL AND error_code IS NULL) OR (status <> 'completed' AND result_kind IS NULL AND answer_message_id IS NULL)"

OLD_JOB_GUARD = """
    CREATE OR REPLACE FUNCTION rag_answer_job_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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
            NEW.embedding_space_hash, NEW.ai_provider, NEW.ai_base_url, NEW.ai_model, NEW.embedding_provider, NEW.embedding_base_url, NEW.embedding_model, NEW.answer_policy_version, NEW.support_policy_version, NEW.ai_catalog_version, NEW.ai_schema_policy_version, NEW.created_at, NEW.max_attempts)
           IS DISTINCT FROM
           (OLD.id, OLD.thread_id, OLD.question_message_id, OLD.user_id, OLD.subject_id,
            OLD.operation_key_hash, OLD.request_fingerprint, OLD.document_ids, OLD.corpus_revision, OLD.retrieval_policy,
            OLD.embedding_space_hash, OLD.ai_provider, OLD.ai_base_url, OLD.ai_model, OLD.embedding_provider, OLD.embedding_base_url, OLD.embedding_model, OLD.answer_policy_version, OLD.support_policy_version, OLD.ai_catalog_version, OLD.ai_schema_policy_version, OLD.created_at, OLD.max_attempts)
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
            
            IF NEW.answer_policy_version = 'related_knowledge_v1' THEN
                SELECT count(*), min(excerpt_order), max(excerpt_order)
                  INTO source_total, source_min, source_max
                  FROM rag_related_evidence WHERE job_id = NEW.id;
                IF NEW.answer_message_id IS NOT NULL
                   OR NOT EXISTS (SELECT 1 FROM subjects WHERE id = NEW.subject_id
                       AND corpus_revision = NEW.corpus_revision
                       AND active_embedding_space_hash = NEW.embedding_space_hash)
                   OR (NEW.result_kind = 'no_match' AND source_total <> 0)
                   OR (NEW.result_kind = 'related_knowledge' AND
                       (source_total NOT BETWEEN 1 AND 3 OR source_min <> 1 OR source_max <> source_total))
                   OR NEW.result_kind IS NULL
                THEN RAISE EXCEPTION 'Completed Knowledge references are invalid.' USING ERRCODE = '23514'; END IF;
            ELSE
    
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
        END IF;
        RETURN NEW;
    END $$
    """

NEW_JOB_GUARD = """
    CREATE OR REPLACE FUNCTION rag_answer_job_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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
            NEW.embedding_space_hash, NEW.ai_provider, NEW.ai_base_url, NEW.ai_model, NEW.embedding_provider, NEW.embedding_base_url, NEW.embedding_model, NEW.answer_policy_version, NEW.support_policy_version, NEW.ai_catalog_version, NEW.ai_schema_policy_version, NEW.created_at, NEW.max_attempts)
           IS DISTINCT FROM
           (OLD.id, OLD.thread_id, OLD.question_message_id, OLD.user_id, OLD.subject_id,
            OLD.operation_key_hash, OLD.request_fingerprint, OLD.document_ids, OLD.corpus_revision, OLD.retrieval_policy,
            OLD.embedding_space_hash, OLD.ai_provider, OLD.ai_base_url, OLD.ai_model, OLD.embedding_provider, OLD.embedding_base_url, OLD.embedding_model, OLD.answer_policy_version, OLD.support_policy_version, OLD.ai_catalog_version, OLD.ai_schema_policy_version, OLD.created_at, OLD.max_attempts)
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
            
            IF NEW.answer_policy_version IN ('related_knowledge_v1','related_knowledge_navigation_v2') THEN
                SELECT count(*), min(excerpt_order), max(excerpt_order)
                  INTO source_total, source_min, source_max
                  FROM rag_related_evidence WHERE job_id = NEW.id;
                IF NEW.answer_message_id IS NOT NULL
                   OR NOT EXISTS (SELECT 1 FROM subjects WHERE id = NEW.subject_id
                       AND corpus_revision = NEW.corpus_revision
                       AND active_embedding_space_hash = NEW.embedding_space_hash)
                   OR (NEW.result_kind = 'no_match' AND source_total <> 0)
                   OR (NEW.result_kind = 'related_knowledge' AND
                       (source_total NOT BETWEEN 1 AND 3 OR source_min <> 1 OR source_max <> source_total))
                   OR NEW.result_kind IS NULL
                THEN RAISE EXCEPTION 'Completed Knowledge references are invalid.' USING ERRCODE = '23514'; END IF;
            ELSE
    
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
        END IF;
        RETURN NEW;
    END $$
    """

OLD_REFERENCE_GUARD = """
    CREATE OR REPLACE FUNCTION rag_related_evidence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE answer_job rag_answer_jobs%ROWTYPE;
            source_content text;
            question_expiry timestamptz;
    BEGIN
        IF TG_OP <> 'INSERT' THEN
            RAISE EXCEPTION 'Related evidence is immutable.' USING ERRCODE = '23514';
        END IF;
        SELECT * INTO answer_job FROM rag_answer_jobs WHERE id = NEW.job_id;
        IF NOT FOUND OR answer_job.status <> 'running'
           OR answer_job.manual_retry_count <> NEW.manual_retry_number
           OR answer_job.retrieval_completed_at IS NULL
           OR answer_job.lease_expires_at IS NULL
           OR answer_job.lease_expires_at <= now() THEN
            RAISE EXCEPTION 'Related evidence job is not current.' USING ERRCODE = '23514';
        END IF;
        IF EXISTS (SELECT 1 FROM rag_related_evidence AS existing
                   WHERE existing.job_id = NEW.job_id
                     AND (existing.bundle_size <> NEW.bundle_size
                          OR existing.manual_retry_number <> NEW.manual_retry_number)) THEN
            RAISE EXCEPTION 'Related evidence bundle is inconsistent.' USING ERRCODE = '23514';
        END IF;
        IF answer_job.document_ids <> '[]'::jsonb
           AND NOT (answer_job.document_ids ? NEW.document_id::text) THEN
            RAISE EXCEPTION 'Related evidence document is outside the selected scope.' USING ERRCODE = '23514';
        END IF;
        SELECT expires_at INTO question_expiry FROM rag_messages
        WHERE id = answer_job.question_message_id;
        IF NOT FOUND OR question_expiry <= now() OR NEW.expires_at > question_expiry THEN
            RAISE EXCEPTION 'Related evidence has expired.' USING ERRCODE = '23514';
        END IF;
        
        IF NEW.source_kind NOT IN ('chunk','canonical_page') OR NEW.source_kind IS NULL THEN
            RAISE EXCEPTION 'Related evidence source kind is invalid.' USING ERRCODE = '23514';
        END IF;
        IF NEW.source_kind = 'canonical_page' AND
           (answer_job.retrieval_policy <> 'hybrid_source_sufficiency_v7'
            OR answer_job.answer_policy_version IS DISTINCT FROM 'related_knowledge_v1') THEN
            RAISE EXCEPTION 'Canonical page reference policy is incompatible.' USING ERRCODE = '23514';
        END IF;
        SELECT CASE WHEN NEW.source_kind = 'canonical_page' THEN page.content ELSE eligible.content END
          INTO source_content
        FROM eligible_subject_knowledge_chunks AS eligible
        JOIN subject_document_pages AS page
          ON page.content_revision_id = eligible.content_revision_id
         AND page.document_id = eligible.document_id
         AND page.subject_id = eligible.subject_id
         AND page.uploader_id = eligible.uploader_id
         AND page.page_number = eligible.page_number
        JOIN subjects AS subject ON subject.id = eligible.subject_id
        JOIN users AS principal ON principal.id = answer_job.user_id
        WHERE eligible.id = NEW.chunk_id AND eligible.index_revision_id = NEW.index_revision_id
          AND eligible.content_revision_id = NEW.content_revision_id
          AND eligible.document_id = NEW.document_id AND eligible.subject_id = NEW.subject_id
          AND eligible.corpus_revision = answer_job.corpus_revision
          AND eligible.embedding_space_hash = answer_job.embedding_space_hash
          AND ((principal.role = 'INSTRUCTOR' AND subject.instructor_id = principal.id)
               OR (principal.role = 'STUDENT' AND EXISTS (
                   SELECT 1 FROM enrollments AS enrollment
                   WHERE enrollment.student_id = principal.id AND enrollment.subject_id = subject.id)));
        IF NOT FOUND OR NEW.start_offset < 0 OR NEW.end_offset <= NEW.start_offset
           OR NEW.end_offset - NEW.start_offset > 480
           OR NEW.end_offset > char_length(source_content)
           OR btrim(substring(source_content FROM NEW.start_offset + 1 FOR NEW.end_offset - NEW.start_offset), E' \\t\\n\\r') = '' THEN
            RAISE EXCEPTION 'Related evidence source is not current.' USING ERRCODE = '23514';
        END IF;
    
        RETURN NEW;
    END $$
    """

NEW_REFERENCE_GUARD = """
    CREATE OR REPLACE FUNCTION rag_related_evidence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE answer_job rag_answer_jobs%ROWTYPE;
            source_content text;
            question_expiry timestamptz;
    BEGIN
        IF TG_OP <> 'INSERT' THEN
            RAISE EXCEPTION 'Related evidence is immutable.' USING ERRCODE = '23514';
        END IF;
        SELECT * INTO answer_job FROM rag_answer_jobs WHERE id = NEW.job_id;
        IF NOT FOUND OR answer_job.status <> 'running'
           OR answer_job.manual_retry_count <> NEW.manual_retry_number
           OR answer_job.retrieval_completed_at IS NULL
           OR answer_job.lease_expires_at IS NULL
           OR answer_job.lease_expires_at <= now() THEN
            RAISE EXCEPTION 'Related evidence job is not current.' USING ERRCODE = '23514';
        END IF;
        IF EXISTS (SELECT 1 FROM rag_related_evidence AS existing
                   WHERE existing.job_id = NEW.job_id
                     AND (existing.bundle_size <> NEW.bundle_size
                          OR existing.manual_retry_number <> NEW.manual_retry_number)) THEN
            RAISE EXCEPTION 'Related evidence bundle is inconsistent.' USING ERRCODE = '23514';
        END IF;
        IF answer_job.document_ids <> '[]'::jsonb
           AND NOT (answer_job.document_ids ? NEW.document_id::text) THEN
            RAISE EXCEPTION 'Related evidence document is outside the selected scope.' USING ERRCODE = '23514';
        END IF;
        SELECT expires_at INTO question_expiry FROM rag_messages
        WHERE id = answer_job.question_message_id;
        IF NOT FOUND OR question_expiry <= now() OR NEW.expires_at > question_expiry THEN
            RAISE EXCEPTION 'Related evidence has expired.' USING ERRCODE = '23514';
        END IF;
        
        IF NEW.source_kind NOT IN ('chunk','canonical_page') OR NEW.source_kind IS NULL THEN
            RAISE EXCEPTION 'Related evidence source kind is invalid.' USING ERRCODE = '23514';
        END IF;
        IF NEW.source_kind = 'canonical_page' AND
           NOT ((answer_job.retrieval_policy IS NOT DISTINCT FROM 'hybrid_source_sufficiency_v7' AND answer_job.answer_policy_version IS NOT DISTINCT FROM 'related_knowledge_v1') OR (answer_job.retrieval_policy IS NOT DISTINCT FROM 'hybrid_source_navigation_v8' AND answer_job.answer_policy_version IS NOT DISTINCT FROM 'related_knowledge_navigation_v2')) THEN
            RAISE EXCEPTION 'Canonical page reference policy is incompatible.' USING ERRCODE = '23514';
        END IF;
        SELECT CASE WHEN NEW.source_kind = 'canonical_page' THEN page.content ELSE eligible.content END
          INTO source_content
        FROM eligible_subject_knowledge_chunks AS eligible
        JOIN subject_document_pages AS page
          ON page.content_revision_id = eligible.content_revision_id
         AND page.document_id = eligible.document_id
         AND page.subject_id = eligible.subject_id
         AND page.uploader_id = eligible.uploader_id
         AND page.page_number = eligible.page_number
        JOIN subjects AS subject ON subject.id = eligible.subject_id
        JOIN users AS principal ON principal.id = answer_job.user_id
        WHERE eligible.id = NEW.chunk_id AND eligible.index_revision_id = NEW.index_revision_id
          AND eligible.content_revision_id = NEW.content_revision_id
          AND eligible.document_id = NEW.document_id AND eligible.subject_id = NEW.subject_id
          AND eligible.corpus_revision = answer_job.corpus_revision
          AND eligible.embedding_space_hash = answer_job.embedding_space_hash
          AND ((principal.role = 'INSTRUCTOR' AND subject.instructor_id = principal.id)
               OR (principal.role = 'STUDENT' AND EXISTS (
                   SELECT 1 FROM enrollments AS enrollment
                   WHERE enrollment.student_id = principal.id AND enrollment.subject_id = subject.id)));
        IF NOT FOUND OR NEW.start_offset < 0 OR NEW.end_offset <= NEW.start_offset
           OR NEW.end_offset - NEW.start_offset > 480
           OR NEW.end_offset > char_length(source_content)
           OR btrim(substring(source_content FROM NEW.start_offset + 1 FOR NEW.end_offset - NEW.start_offset), E' \\t\\n\\r') = '' THEN
            RAISE EXCEPTION 'Related evidence source is not current.' USING ERRCODE = '23514';
        END IF;
    
        RETURN NEW;
    END $$
    """


SOURCE_POLICIES = "('related_knowledge_v1','related_knowledge_navigation_v2')"


def _stage_guard(policies: str) -> str:
    return f"""
    CREATE OR REPLACE FUNCTION enforce_rag_source_stage_parent_policy() RETURNS trigger
    LANGUAGE plpgsql AS $$
    DECLARE parent_job record;
    BEGIN
        SELECT answer_policy_version, manual_retry_count, attempt_count INTO parent_job
          FROM rag_answer_jobs WHERE id = NEW.job_id FOR KEY SHARE;
        IF (parent_job.answer_policy_version IN {policies}
            AND (NEW.answer_policy_version IS DISTINCT FROM parent_job.answer_policy_version
                 OR NEW.manual_retry_number IS DISTINCT FROM parent_job.manual_retry_count
                 OR NEW.worker_attempt_number IS DISTINCT FROM parent_job.attempt_count))
           OR (NEW.answer_policy_version IN {policies}
               AND parent_job.answer_policy_version IS DISTINCT FROM NEW.answer_policy_version)
        THEN
            RAISE EXCEPTION 'Source-only stage policy must match its parent job.' USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END $$
    """


def _caps(policies: str) -> None:
    op.drop_constraint("ck_rag_answer_stage_source_only_cap", "rag_answer_stage_attempts", type_="check")
    op.create_check_constraint(
        "ck_rag_answer_stage_source_only_cap", "rag_answer_stage_attempts",
        f"answer_policy_version IS NULL OR answer_policy_version NOT IN {policies} "
        "OR (stage IN ('query_embedding','retrieval') AND retry_count = 0 "
        "AND ((stage = 'query_embedding' AND physical_request_count <= 1) "
        "OR (stage = 'retrieval' AND physical_request_count = 0)))",
    )
    op.drop_index("uq_rag_answer_stage_source_embedding_attempt", table_name="rag_answer_stage_attempts")
    op.create_index(
        "uq_rag_answer_stage_source_embedding_attempt", "rag_answer_stage_attempts",
        ["job_id", "manual_retry_number", "stage"], unique=True,
        postgresql_where=sa.text(f"answer_policy_version IN {policies} AND stage = 'query_embedding'"),
    )
    op.execute(sa.text(_stage_guard(policies)))


def _contracts(identity: str, result: str, job_guard: str, ref_guard: str) -> None:
    for name, value in (("ck_rag_answer_jobs_identity", identity), ("ck_rag_answer_jobs_result", result)):
        op.drop_constraint(name, "rag_answer_jobs", type_="check")
        op.create_check_constraint(name, "rag_answer_jobs", value)
    op.execute(sa.text(job_guard))
    op.execute(sa.text(ref_guard))


def upgrade() -> None:
    _contracts(NEW_IDENTITY, NEW_RESULT, NEW_JOB_GUARD, NEW_REFERENCE_GUARD)
    _caps(SOURCE_POLICIES)


def downgrade() -> None:
    retained = op.get_bind().scalar(sa.text(
        "SELECT count(*) FROM rag_answer_jobs WHERE answer_policy_version = 'related_knowledge_navigation_v2'"
    ))
    if retained:
        raise RuntimeError("Cannot downgrade while source-navigation job snapshots exist")
    _contracts(OLD_IDENTITY, OLD_RESULT, OLD_JOB_GUARD, OLD_REFERENCE_GUARD)
    _caps("('related_knowledge_v1')")
