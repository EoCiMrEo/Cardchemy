"""Admit the corrected immutable navigation policy while retaining v2 rows.

Revision ID: 20260927_0028
Revises: 20260927_0027
"""

from alembic import op
import sqlalchemy as sa


revision = "20260927_0028"
down_revision = "20260927_0027"
branch_labels = None
depends_on = None

OLD_POLICIES = "('related_knowledge_v1','related_knowledge_navigation_v2')"
NEW_POLICIES = "('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3')"

# Keep the 0027 expressions here rather than importing a mutable application
# model into migration history. A v2 row remains valid after the new head.
OLD_IDENTITY = "length(operation_key_hash) = 64 AND length(request_fingerprint) = 64 AND corpus_revision >= 0 AND length(embedding_space_hash) = 64 AND length(trim(retrieval_policy)) BETWEEN 1 AND 64 AND ((answer_policy_version IN ('related_knowledge_v1','related_knowledge_navigation_v2') AND ai_provider IS NULL AND ai_base_url IS NULL AND ai_model IS NULL AND support_policy_version IS NULL AND embedding_provider IS NOT NULL AND embedding_base_url IS NOT NULL AND embedding_model IS NOT NULL AND length(trim(embedding_provider)) BETWEEN 1 AND 32 AND length(trim(embedding_base_url)) BETWEEN 1 AND 512 AND length(trim(embedding_model)) BETWEEN 1 AND 128) OR ((answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_v1','related_knowledge_navigation_v2')) AND embedding_provider IS NULL AND embedding_base_url IS NULL AND embedding_model IS NULL AND ai_provider IS NOT NULL AND ai_base_url IS NOT NULL AND ai_model IS NOT NULL AND length(trim(ai_provider)) BETWEEN 1 AND 32 AND length(trim(ai_base_url)) BETWEEN 1 AND 512 AND length(trim(ai_model)) BETWEEN 1 AND 128))"
NEW_IDENTITY = OLD_IDENTITY.replace(OLD_POLICIES, NEW_POLICIES)

OLD_RESULT = "(status = 'completed' AND answer_policy_version IN ('related_knowledge_v1','related_knowledge_navigation_v2') AND result_kind IN ('related_knowledge','no_match') AND answer_message_id IS NULL AND error_code IS NULL) OR (status = 'completed' AND (answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_v1','related_knowledge_navigation_v2')) AND result_kind IS NULL AND answer_message_id IS NOT NULL AND error_code IS NULL) OR (status <> 'completed' AND result_kind IS NULL AND answer_message_id IS NULL)"
NEW_RESULT = OLD_RESULT.replace(OLD_POLICIES, NEW_POLICIES)

OLD_JOB_CLAUSE = "IF NEW.answer_policy_version IN ('related_knowledge_v1','related_knowledge_navigation_v2') THEN"
NEW_JOB_CLAUSE = "IF NEW.answer_policy_version IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3') THEN"
OLD_REFERENCE_PAIR = "(answer_job.retrieval_policy IS NOT DISTINCT FROM 'hybrid_source_navigation_v8' AND answer_job.answer_policy_version IS NOT DISTINCT FROM 'related_knowledge_navigation_v2')"
NEW_REFERENCE_PAIR = OLD_REFERENCE_PAIR + " OR (answer_job.retrieval_policy IS NOT DISTINCT FROM 'hybrid_source_navigation_v9' AND answer_job.answer_policy_version IS NOT DISTINCT FROM 'related_knowledge_navigation_v3')"


def _replace_function(name: str, old: str, new: str, *, reject_existing: bool = True) -> None:
    """Patch one known 0027 clause, refusing a different installed function."""

    definition = op.get_bind().scalar(sa.text(
        "SELECT pg_get_functiondef(to_regprocedure(:name))"
    ).bindparams(sa.bindparam("name", name)))
    if (not isinstance(definition, str) or definition.count(old) != 1
        or reject_existing and new in definition):
        raise RuntimeError(f"Unexpected {name} guard definition")
    op.execute(sa.text(definition.replace(old, new)))


def _checks(identity: str, result: str) -> None:
    for name, expression in (
        ("ck_rag_answer_jobs_identity", identity),
        ("ck_rag_answer_jobs_result", result),
    ):
        op.drop_constraint(name, "rag_answer_jobs", type_="check")
        op.create_check_constraint(name, "rag_answer_jobs", expression)


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


def upgrade() -> None:
    _checks(NEW_IDENTITY, NEW_RESULT)
    _replace_function("rag_answer_job_guard()", OLD_JOB_CLAUSE, NEW_JOB_CLAUSE)
    _replace_function("rag_related_evidence_guard()", OLD_REFERENCE_PAIR, NEW_REFERENCE_PAIR)
    _caps(NEW_POLICIES)


def downgrade() -> None:
    if op.get_bind().scalar(sa.text(
        "SELECT count(*) FROM rag_answer_jobs WHERE answer_policy_version = 'related_knowledge_navigation_v3'"
    )):
        raise RuntimeError("Cannot downgrade while v3 source-navigation job snapshots exist")
    _checks(OLD_IDENTITY, OLD_RESULT)
    _replace_function("rag_answer_job_guard()", NEW_JOB_CLAUSE, OLD_JOB_CLAUSE)
    _replace_function(
        "rag_related_evidence_guard()", NEW_REFERENCE_PAIR, OLD_REFERENCE_PAIR,
        reject_existing=False,
    )
    _caps(OLD_POLICIES)
