"""Admit a separately bounded source-ID judge without changing old Ask jobs.

Revision ID: 20260928_0029
Revises: 20260927_0028
"""

from alembic import op
import sqlalchemy as sa


revision = "20260928_0029"
down_revision = "20260927_0028"
branch_labels = None
depends_on = None

OLD_POLICIES = "('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3')"
NEW_POLICIES = "('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3','related_knowledge_navigation_v4')"
V4 = "related_knowledge_navigation_v4"

# Preserve the used 0028 expressions here. Migration history must not import
# mutable ORM metadata or reinterpret retained v1-v3 job snapshots.
OLD_IDENTITY = "length(operation_key_hash) = 64 AND length(request_fingerprint) = 64 AND corpus_revision >= 0 AND length(embedding_space_hash) = 64 AND length(trim(retrieval_policy)) BETWEEN 1 AND 64 AND ((answer_policy_version IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3') AND ai_provider IS NULL AND ai_base_url IS NULL AND ai_model IS NULL AND support_policy_version IS NULL AND embedding_provider IS NOT NULL AND embedding_base_url IS NOT NULL AND embedding_model IS NOT NULL AND length(trim(embedding_provider)) BETWEEN 1 AND 32 AND length(trim(embedding_base_url)) BETWEEN 1 AND 512 AND length(trim(embedding_model)) BETWEEN 1 AND 128) OR ((answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3')) AND embedding_provider IS NULL AND embedding_base_url IS NULL AND embedding_model IS NULL AND ai_provider IS NOT NULL AND ai_base_url IS NOT NULL AND ai_model IS NOT NULL AND length(trim(ai_provider)) BETWEEN 1 AND 32 AND length(trim(ai_base_url)) BETWEEN 1 AND 512 AND length(trim(ai_model)) BETWEEN 1 AND 128))"
NEW_IDENTITY = OLD_IDENTITY.replace(OLD_POLICIES, NEW_POLICIES)

OLD_RESULT = "(status = 'completed' AND answer_policy_version IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3') AND result_kind IN ('related_knowledge','no_match') AND answer_message_id IS NULL AND error_code IS NULL) OR (status = 'completed' AND (answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3')) AND result_kind IS NULL AND answer_message_id IS NOT NULL AND error_code IS NULL) OR (status <> 'completed' AND result_kind IS NULL AND answer_message_id IS NULL)"
V4_RESULT = "(status = 'completed' AND answer_policy_version = 'related_knowledge_navigation_v4' AND result_kind IN ('related_knowledge','no_match','clarification_needed') AND answer_message_id IS NULL AND error_code IS NULL)"
NEW_RESULT = OLD_RESULT.replace(
    "OR (status = 'completed' AND (answer_policy_version IS NULL OR answer_policy_version NOT IN " + OLD_POLICIES + ")",
    "OR " + V4_RESULT + " OR (status = 'completed' AND (answer_policy_version IS NULL OR answer_policy_version NOT IN " + NEW_POLICIES + ")",
)

JUDGE_COLUMNS = (
    "source_judge_provider", "source_judge_base_url", "source_judge_model",
    "source_judge_contract_version", "source_judge_input_price_microusd_per_million",
    "source_judge_output_price_microusd_per_million", "source_judge_max_input_tokens",
    "source_judge_max_output_tokens",
)
JUDGE_SNAPSHOT = (
    "(answer_policy_version IS NOT NULL "
    "AND answer_policy_version = 'related_knowledge_navigation_v4' "
    "AND ai_catalog_version IS NULL AND ai_schema_policy_version IS NULL "
    "AND source_judge_provider IS NOT NULL AND source_judge_provider = 'gemini' "
    "AND source_judge_base_url IS NOT NULL AND source_judge_model IS NOT NULL "
    "AND source_judge_contract_version IS NOT NULL "
    "AND source_judge_input_price_microusd_per_million IS NOT NULL "
    "AND source_judge_output_price_microusd_per_million IS NOT NULL "
    "AND source_judge_max_input_tokens IS NOT NULL "
    "AND source_judge_max_output_tokens IS NOT NULL "
    "AND length(trim(source_judge_base_url)) BETWEEN 1 AND 512 "
    "AND length(trim(source_judge_model)) BETWEEN 1 AND 128 "
    "AND length(trim(source_judge_contract_version)) BETWEEN 1 AND 64 "
    "AND source_judge_input_price_microusd_per_million > 0 "
    "AND source_judge_output_price_microusd_per_million > 0 "
    "AND source_judge_max_input_tokens BETWEEN 1 AND 8192 "
    "AND source_judge_max_output_tokens BETWEEN 1 AND 1024) OR "
    "((answer_policy_version IS NULL OR answer_policy_version <> 'related_knowledge_navigation_v4') "
    "AND source_judge_provider IS NULL AND source_judge_base_url IS NULL "
    "AND source_judge_model IS NULL AND source_judge_contract_version IS NULL "
    "AND source_judge_input_price_microusd_per_million IS NULL "
    "AND source_judge_output_price_microusd_per_million IS NULL "
    "AND source_judge_max_input_tokens IS NULL AND source_judge_max_output_tokens IS NULL)"
)

OLD_JOB_CLAUSE = "IF NEW.answer_policy_version IN " + OLD_POLICIES + " THEN"
NEW_JOB_CLAUSE = "IF NEW.answer_policy_version IN " + NEW_POLICIES + " THEN"
OLD_JOB_NO_MATCH = "OR (NEW.result_kind = 'no_match' AND source_total <> 0)"
NEW_JOB_NO_MATCH = "OR (NEW.result_kind IN ('no_match','clarification_needed') AND source_total <> 0)"
OLD_JOB_NULL_RESULT = "OR NEW.result_kind IS NULL"
NEW_JOB_NULL_RESULT = (
    "OR (NEW.answer_policy_version = 'related_knowledge_navigation_v4' "
    "AND NEW.result_kind = 'clarification_needed' AND EXISTS ("
    "SELECT 1 FROM rag_answer_stage_attempts WHERE job_id = NEW.id "
    "AND stage IN ('query_embedding','source_judgment'))) "
    "OR NEW.result_kind IS NULL"
)
OLD_JOB_NEW_SNAPSHOT = "NEW.ai_catalog_version, NEW.ai_schema_policy_version, NEW.created_at"
OLD_JOB_OLD_SNAPSHOT = "OLD.ai_catalog_version, OLD.ai_schema_policy_version, OLD.created_at"
NEW_JOB_NEW_SNAPSHOT = (
    "NEW.ai_catalog_version, NEW.ai_schema_policy_version, "
    + ", ".join("NEW." + name for name in JUDGE_COLUMNS) + ", NEW.created_at"
)
NEW_JOB_OLD_SNAPSHOT = (
    "OLD.ai_catalog_version, OLD.ai_schema_policy_version, "
    + ", ".join("OLD." + name for name in JUDGE_COLUMNS) + ", OLD.created_at"
)

OLD_REFERENCE_PAIR = "(answer_job.retrieval_policy IS NOT DISTINCT FROM 'hybrid_source_navigation_v8' AND answer_job.answer_policy_version IS NOT DISTINCT FROM 'related_knowledge_navigation_v2') OR (answer_job.retrieval_policy IS NOT DISTINCT FROM 'hybrid_source_navigation_v9' AND answer_job.answer_policy_version IS NOT DISTINCT FROM 'related_knowledge_navigation_v3')"
NEW_REFERENCE_PAIR = OLD_REFERENCE_PAIR + " OR (answer_job.retrieval_policy IS NOT DISTINCT FROM 'hybrid_source_navigation_v9' AND answer_job.answer_policy_version IS NOT DISTINCT FROM 'related_knowledge_navigation_v4')"
OLD_REFERENCE_KIND = "IF NEW.source_kind = 'canonical_page' AND"
NEW_REFERENCE_KIND = """IF answer_job.answer_policy_version = 'related_knowledge_navigation_v4' AND
           (NEW.source_kind <> 'canonical_page' OR NOT EXISTS (
               SELECT 1 FROM rag_answer_stage_attempts AS judged
               WHERE judged.job_id = NEW.job_id
                 AND judged.manual_retry_number = NEW.manual_retry_number
                 AND judged.worker_attempt_number = answer_job.attempt_count
                 AND judged.stage = 'source_judgment'
                 AND judged.completed_at IS NOT NULL
                 AND judged.physical_request_count = 1
                 AND judged.retry_count = 0
                 AND judged.error_category IS NULL
                 AND judged.failure_reason IS NULL
                 AND NOT judged.execution_uncertain)) THEN
            RAISE EXCEPTION 'Related evidence source judgment is unavailable.' USING ERRCODE = '23514';
        END IF;
        IF NEW.source_kind = 'canonical_page' AND"""


def _replace_function(name: str, old: str, new: str, *, reverse: bool = False) -> None:
    definition = op.get_bind().scalar(sa.text(
        "SELECT pg_get_functiondef(to_regprocedure(:name))"
    ).bindparams(sa.bindparam("name", name)))
    if not isinstance(definition, str) or definition.count(old) != 1 or (not reverse and new in definition):
        raise RuntimeError(f"Unexpected {name} guard definition")
    op.execute(sa.text(definition.replace(old, new)))


def _job_checks(identity: str, result: str) -> None:
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


def upgrade() -> None:
    for name, column_type in (
        ("source_judge_provider", sa.String(length=32)),
        ("source_judge_base_url", sa.String(length=512)),
        ("source_judge_model", sa.String(length=128)),
        ("source_judge_contract_version", sa.String(length=64)),
        ("source_judge_input_price_microusd_per_million", sa.BigInteger()),
        ("source_judge_output_price_microusd_per_million", sa.BigInteger()),
        ("source_judge_max_input_tokens", sa.Integer()),
        ("source_judge_max_output_tokens", sa.Integer()),
    ):
        op.add_column("rag_answer_jobs", sa.Column(name, column_type, nullable=True))
    _job_checks(NEW_IDENTITY, NEW_RESULT)
    op.create_check_constraint("ck_rag_answer_jobs_source_judge_snapshot", "rag_answer_jobs", JUDGE_SNAPSHOT)
    op.create_check_constraint(
        "ck_rag_answer_jobs_source_judge_retrieval_pair", "rag_answer_jobs",
        "answer_policy_version IS NULL OR answer_policy_version <> 'related_knowledge_navigation_v4' "
        "OR retrieval_policy = 'hybrid_source_navigation_v9'",
    )
    for old, new in (
        (OLD_JOB_CLAUSE, NEW_JOB_CLAUSE),
        (OLD_JOB_NO_MATCH, NEW_JOB_NO_MATCH),
        (OLD_JOB_NULL_RESULT, NEW_JOB_NULL_RESULT),
        (OLD_JOB_NEW_SNAPSHOT, NEW_JOB_NEW_SNAPSHOT),
        (OLD_JOB_OLD_SNAPSHOT, NEW_JOB_OLD_SNAPSHOT),
    ):
        _replace_function("rag_answer_job_guard()", old, new)
    _replace_function("rag_related_evidence_guard()", OLD_REFERENCE_PAIR, NEW_REFERENCE_PAIR)
    _replace_function("rag_related_evidence_guard()", OLD_REFERENCE_KIND, NEW_REFERENCE_KIND)

    op.drop_constraint("ck_rag_answer_stage_name", "rag_answer_stage_attempts", type_="check")
    op.create_check_constraint(
        "ck_rag_answer_stage_name", "rag_answer_stage_attempts",
        "stage IN ('query_embedding','retrieval','source_judgment','answer','support','local_support')",
    )
    op.create_check_constraint(
        "ck_rag_answer_stage_source_judgment_policy", "rag_answer_stage_attempts",
        "stage <> 'source_judgment' OR (answer_policy_version IS NOT NULL "
        "AND answer_policy_version = 'related_knowledge_navigation_v4')",
    )
    op.create_check_constraint(
        "ck_rag_answer_stage_source_judge_cap", "rag_answer_stage_attempts",
        "answer_policy_version IS NULL OR answer_policy_version <> 'related_knowledge_navigation_v4' "
        "OR (stage IN ('query_embedding','retrieval','source_judgment') AND retry_count = 0 "
        "AND ((stage IN ('query_embedding','source_judgment') AND physical_request_count <= 1) "
        "OR (stage = 'retrieval' AND physical_request_count = 0)))",
    )
    op.create_index(
        "uq_rag_answer_stage_source_judge_remote_attempt", "rag_answer_stage_attempts",
        ["job_id", "manual_retry_number", "stage"], unique=True,
        postgresql_where=sa.text(
            "answer_policy_version = 'related_knowledge_navigation_v4' "
            "AND stage IN ('query_embedding','source_judgment')"
        ),
    )
    op.execute(sa.text(_stage_guard(NEW_POLICIES)))


def downgrade() -> None:
    if op.get_bind().scalar(sa.text(
        "SELECT count(*) FROM rag_answer_jobs WHERE answer_policy_version = 'related_knowledge_navigation_v4'"
    )):
        raise RuntimeError("Cannot downgrade while v4 source-judgment job snapshots exist")
    op.execute(sa.text(_stage_guard(OLD_POLICIES)))
    op.drop_index("uq_rag_answer_stage_source_judge_remote_attempt", table_name="rag_answer_stage_attempts")
    op.drop_constraint("ck_rag_answer_stage_source_judge_cap", "rag_answer_stage_attempts", type_="check")
    op.drop_constraint("ck_rag_answer_stage_source_judgment_policy", "rag_answer_stage_attempts", type_="check")
    op.drop_constraint("ck_rag_answer_stage_name", "rag_answer_stage_attempts", type_="check")
    op.create_check_constraint(
        "ck_rag_answer_stage_name", "rag_answer_stage_attempts",
        "stage IN ('query_embedding','retrieval','answer','support','local_support')",
    )
    for old, new in (
        (NEW_REFERENCE_KIND, OLD_REFERENCE_KIND),
        (NEW_REFERENCE_PAIR, OLD_REFERENCE_PAIR),
    ):
        _replace_function("rag_related_evidence_guard()", old, new, reverse=True)
    for old, new in (
        (NEW_JOB_OLD_SNAPSHOT, OLD_JOB_OLD_SNAPSHOT),
        (NEW_JOB_NEW_SNAPSHOT, OLD_JOB_NEW_SNAPSHOT),
        (NEW_JOB_NULL_RESULT, OLD_JOB_NULL_RESULT),
        (NEW_JOB_NO_MATCH, OLD_JOB_NO_MATCH),
        (NEW_JOB_CLAUSE, OLD_JOB_CLAUSE),
    ):
        _replace_function("rag_answer_job_guard()", old, new, reverse=True)
    op.drop_constraint("ck_rag_answer_jobs_source_judge_retrieval_pair", "rag_answer_jobs", type_="check")
    op.drop_constraint("ck_rag_answer_jobs_source_judge_snapshot", "rag_answer_jobs", type_="check")
    _job_checks(OLD_IDENTITY, OLD_RESULT)
    for name in reversed(JUDGE_COLUMNS):
        op.drop_column("rag_answer_jobs", name)
