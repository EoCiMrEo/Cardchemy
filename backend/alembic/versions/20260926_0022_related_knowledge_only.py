"""Add source-only Ask outcomes without changing historical answer rows.

Revision ID: 20260926_0022
Revises: 20260925_0021
Create Date: 2026-09-26
"""

from alembic import op
import sqlalchemy as sa


revision = "20260926_0022"
down_revision = "20260925_0021"
branch_labels = None
depends_on = None


_COMMON_IDENTITY = (
    "length(operation_key_hash) = 64 AND length(request_fingerprint) = 64 "
    "AND corpus_revision >= 0 AND length(embedding_space_hash) = 64 "
    "AND length(trim(retrieval_policy)) BETWEEN 1 AND 64 "
)
_LEGACY_IDENTITY = (
    "ai_provider IS NOT NULL AND ai_base_url IS NOT NULL AND ai_model IS NOT NULL "
    "AND length(trim(ai_provider)) BETWEEN 1 AND 32 "
    "AND length(trim(ai_base_url)) BETWEEN 1 AND 512 "
    "AND length(trim(ai_model)) BETWEEN 1 AND 128"
)
_SOURCE_IDENTITY = (
    "answer_policy_version = 'related_knowledge_v1' "
    "AND ai_provider IS NULL AND ai_base_url IS NULL AND ai_model IS NULL "
    "AND support_policy_version IS NULL "
    "AND embedding_provider IS NOT NULL AND embedding_base_url IS NOT NULL AND embedding_model IS NOT NULL "
    "AND length(trim(embedding_provider)) BETWEEN 1 AND 32 "
    "AND length(trim(embedding_base_url)) BETWEEN 1 AND 512 "
    "AND length(trim(embedding_model)) BETWEEN 1 AND 128"
)
_NEW_IDENTITY = (
    _COMMON_IDENTITY + "AND ((" + _SOURCE_IDENTITY + ") OR "
    "((answer_policy_version IS NULL OR answer_policy_version <> 'related_knowledge_v1') "
    "AND embedding_provider IS NULL AND embedding_base_url IS NULL AND embedding_model IS NULL "
    "AND " + _LEGACY_IDENTITY + "))"
)
_OLD_IDENTITY = _COMMON_IDENTITY + "AND " + _LEGACY_IDENTITY
_NEW_RESULT = (
    "(status = 'completed' AND answer_policy_version = 'related_knowledge_v1' "
    "AND result_kind IN ('related_knowledge','no_match') "
    "AND answer_message_id IS NULL AND error_code IS NULL) OR "
    "(status = 'completed' AND (answer_policy_version IS NULL OR answer_policy_version <> 'related_knowledge_v1') "
    "AND result_kind IS NULL AND answer_message_id IS NOT NULL AND error_code IS NULL) OR "
    "(status <> 'completed' AND result_kind IS NULL AND answer_message_id IS NULL)"
)
_OLD_RESULT = (
    "(status = 'completed' AND answer_message_id IS NOT NULL AND error_code IS NULL) OR "
    "(status <> 'completed' AND answer_message_id IS NULL)"
)


def _guard_sql(*, source_only: bool) -> str:
    snapshots = (
        "NEW.embedding_provider, NEW.embedding_base_url, NEW.embedding_model, "
        "NEW.answer_policy_version, NEW.support_policy_version, NEW.ai_catalog_version, "
        "NEW.ai_schema_policy_version, "
        if source_only else ""
    )
    old_snapshots = (
        "OLD.embedding_provider, OLD.embedding_base_url, OLD.embedding_model, "
        "OLD.answer_policy_version, OLD.support_policy_version, OLD.ai_catalog_version, "
        "OLD.ai_schema_policy_version, "
        if source_only else ""
    )
    source_completion = """
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
    """ if source_only else ""
    source_completion_end = "END IF;" if source_only else ""
    return f"""
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
            NEW.embedding_space_hash, NEW.ai_provider, NEW.ai_base_url, NEW.ai_model, {snapshots}NEW.created_at, NEW.max_attempts)
           IS DISTINCT FROM
           (OLD.id, OLD.thread_id, OLD.question_message_id, OLD.user_id, OLD.subject_id,
            OLD.operation_key_hash, OLD.request_fingerprint, OLD.document_ids, OLD.corpus_revision, OLD.retrieval_policy,
            OLD.embedding_space_hash, OLD.ai_provider, OLD.ai_base_url, OLD.ai_model, {old_snapshots}OLD.created_at, OLD.max_attempts)
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
            {source_completion}
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
            {source_completion_end}
        END IF;
        RETURN NEW;
    END $$
    """


def upgrade() -> None:
    op.add_column("rag_answer_jobs", sa.Column("embedding_provider", sa.String(32), nullable=True))
    op.add_column("rag_answer_jobs", sa.Column("embedding_base_url", sa.String(512), nullable=True))
    op.add_column("rag_answer_jobs", sa.Column("embedding_model", sa.String(128), nullable=True))
    op.add_column("rag_answer_jobs", sa.Column("result_kind", sa.String(32), nullable=True))
    for name in ("ai_provider", "ai_base_url", "ai_model"):
        op.alter_column("rag_answer_jobs", name, existing_type=sa.String(512 if name == "ai_base_url" else 128 if name == "ai_model" else 32), nullable=True)
    op.drop_constraint("ck_rag_answer_jobs_identity", "rag_answer_jobs", type_="check")
    op.create_check_constraint("ck_rag_answer_jobs_identity", "rag_answer_jobs", _NEW_IDENTITY)
    op.drop_constraint("ck_rag_answer_jobs_result", "rag_answer_jobs", type_="check")
    op.create_check_constraint("ck_rag_answer_jobs_result", "rag_answer_jobs", _NEW_RESULT)
    op.drop_constraint("ck_rag_related_evidence_order", "rag_related_evidence", type_="check")
    op.drop_constraint("ck_rag_related_evidence_bundle", "rag_related_evidence", type_="check")
    op.create_check_constraint("ck_rag_related_evidence_order", "rag_related_evidence", "excerpt_order BETWEEN 1 AND 3")
    op.create_check_constraint("ck_rag_related_evidence_bundle", "rag_related_evidence", "bundle_size BETWEEN 1 AND 3 AND excerpt_order <= bundle_size")
    op.create_check_constraint(
        "ck_rag_answer_stage_source_only_cap", "rag_answer_stage_attempts",
        "answer_policy_version IS NULL OR answer_policy_version <> 'related_knowledge_v1' "
        "OR (stage IN ('query_embedding','retrieval') AND retry_count = 0 "
        "AND ((stage = 'query_embedding' AND physical_request_count <= 1) "
        "OR (stage = 'retrieval' AND physical_request_count = 0)))",
    )
    op.create_index(
        "uq_rag_answer_stage_source_embedding_attempt", "rag_answer_stage_attempts",
        ["job_id", "manual_retry_number", "stage"], unique=True,
        postgresql_where=sa.text(
            "answer_policy_version = 'related_knowledge_v1' AND stage = 'query_embedding'"
        ),
    )
    op.execute(sa.text(_guard_sql(source_only=True)))


def downgrade() -> None:
    retained = op.get_bind().scalar(sa.text(
        "SELECT count(*) FROM rag_answer_jobs WHERE answer_policy_version = 'related_knowledge_v1'"
    ))
    if retained:
        raise RuntimeError("Cannot downgrade while source-only Ask jobs exist")
    op.execute(sa.text(_guard_sql(source_only=False)))
    op.drop_index("uq_rag_answer_stage_source_embedding_attempt", table_name="rag_answer_stage_attempts")
    op.drop_constraint("ck_rag_answer_stage_source_only_cap", "rag_answer_stage_attempts", type_="check")
    op.drop_constraint("ck_rag_related_evidence_bundle", "rag_related_evidence", type_="check")
    op.drop_constraint("ck_rag_related_evidence_order", "rag_related_evidence", type_="check")
    op.create_check_constraint("ck_rag_related_evidence_order", "rag_related_evidence", "excerpt_order BETWEEN 1 AND 2")
    op.create_check_constraint("ck_rag_related_evidence_bundle", "rag_related_evidence", "bundle_size BETWEEN 1 AND 2 AND excerpt_order <= bundle_size")
    op.drop_constraint("ck_rag_answer_jobs_result", "rag_answer_jobs", type_="check")
    op.create_check_constraint("ck_rag_answer_jobs_result", "rag_answer_jobs", _OLD_RESULT)
    op.drop_constraint("ck_rag_answer_jobs_identity", "rag_answer_jobs", type_="check")
    op.create_check_constraint("ck_rag_answer_jobs_identity", "rag_answer_jobs", _OLD_IDENTITY)
    for name in ("ai_provider", "ai_base_url", "ai_model"):
        op.alter_column("rag_answer_jobs", name, existing_type=sa.String(512 if name == "ai_base_url" else 128 if name == "ai_model" else 32), nullable=False)
    for name in ("result_kind", "embedding_model", "embedding_base_url", "embedding_provider"):
        op.drop_column("rag_answer_jobs", name)
