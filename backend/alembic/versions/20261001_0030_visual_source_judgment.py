"""Dormant v5 visual source judgment; retain every historical v4 contract.

Revision ID: 20261001_0030
Revises: 20260928_0029
"""
from alembic import op
import sqlalchemy as sa

revision = "20261001_0030"
down_revision = "20260928_0029"
branch_labels = None
depends_on = None
V4, V5 = "related_knowledge_navigation_v4", "related_knowledge_navigation_v5"
OLD_POLICIES = "('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3','related_knowledge_navigation_v4')"
NEW_POLICIES = OLD_POLICIES[:-1] + ",'related_knowledge_navigation_v5')"
JUDGE_POLICIES = "('related_knowledge_navigation_v4','related_knowledge_navigation_v5')"
OLD_IDENTITY = "length(operation_key_hash) = 64 AND length(request_fingerprint) = 64 AND corpus_revision >= 0 AND length(embedding_space_hash) = 64 AND length(trim(retrieval_policy)) BETWEEN 1 AND 64 AND ((answer_policy_version IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3','related_knowledge_navigation_v4') AND ai_provider IS NULL AND ai_base_url IS NULL AND ai_model IS NULL AND support_policy_version IS NULL AND embedding_provider IS NOT NULL AND embedding_base_url IS NOT NULL AND embedding_model IS NOT NULL AND length(trim(embedding_provider)) BETWEEN 1 AND 32 AND length(trim(embedding_base_url)) BETWEEN 1 AND 512 AND length(trim(embedding_model)) BETWEEN 1 AND 128) OR ((answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3','related_knowledge_navigation_v4')) AND embedding_provider IS NULL AND embedding_base_url IS NULL AND embedding_model IS NULL AND ai_provider IS NOT NULL AND ai_base_url IS NOT NULL AND ai_model IS NOT NULL AND length(trim(ai_provider)) BETWEEN 1 AND 32 AND length(trim(ai_base_url)) BETWEEN 1 AND 512 AND length(trim(ai_model)) BETWEEN 1 AND 128))"
NEW_IDENTITY = OLD_IDENTITY.replace(OLD_POLICIES, NEW_POLICIES)
OLD_RESULT = "(status = 'completed' AND answer_policy_version IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3') AND result_kind IN ('related_knowledge','no_match') AND answer_message_id IS NULL AND error_code IS NULL) OR (status = 'completed' AND answer_policy_version = 'related_knowledge_navigation_v4' AND result_kind IN ('related_knowledge','no_match','clarification_needed') AND answer_message_id IS NULL AND error_code IS NULL) OR (status = 'completed' AND (answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3','related_knowledge_navigation_v4')) AND result_kind IS NULL AND answer_message_id IS NOT NULL AND error_code IS NULL) OR (status <> 'completed' AND result_kind IS NULL AND answer_message_id IS NULL)"
NEW_RESULT = OLD_RESULT.replace(OLD_POLICIES, NEW_POLICIES).replace(
    "answer_policy_version = 'related_knowledge_navigation_v4'", "answer_policy_version IN " + JUDGE_POLICIES,
)
OLD_JUDGE_COLUMNS = (
    "source_judge_provider", "source_judge_base_url", "source_judge_model", "source_judge_contract_version",
    "source_judge_input_price_microusd_per_million", "source_judge_output_price_microusd_per_million",
    "source_judge_max_input_tokens", "source_judge_max_output_tokens",
)
VISUAL_COLUMNS = ("source_judge_thinking_level", "source_judge_timeout_seconds")
OLD_JUDGE_SNAPSHOT = (
    "(answer_policy_version IS NOT NULL AND answer_policy_version = 'related_knowledge_navigation_v4' "
    "AND ai_catalog_version IS NULL AND ai_schema_policy_version IS NULL "
    "AND source_judge_provider IS NOT NULL AND source_judge_provider = 'gemini' "
    "AND source_judge_base_url IS NOT NULL AND source_judge_model IS NOT NULL "
    "AND source_judge_contract_version IS NOT NULL "
    "AND source_judge_input_price_microusd_per_million IS NOT NULL "
    "AND source_judge_output_price_microusd_per_million IS NOT NULL "
    "AND source_judge_max_input_tokens IS NOT NULL AND source_judge_max_output_tokens IS NOT NULL "
    "AND length(trim(source_judge_base_url)) BETWEEN 1 AND 512 "
    "AND length(trim(source_judge_model)) BETWEEN 1 AND 128 "
    "AND length(trim(source_judge_contract_version)) BETWEEN 1 AND 64 "
    "AND source_judge_input_price_microusd_per_million > 0 "
    "AND source_judge_output_price_microusd_per_million > 0 "
    "AND source_judge_max_input_tokens BETWEEN 1 AND 8192 AND source_judge_max_output_tokens BETWEEN 1 AND 1024) OR "
    "((answer_policy_version IS NULL OR answer_policy_version <> 'related_knowledge_navigation_v4') "
    "AND source_judge_provider IS NULL AND source_judge_base_url IS NULL AND source_judge_model IS NULL "
    "AND source_judge_contract_version IS NULL AND source_judge_input_price_microusd_per_million IS NULL "
    "AND source_judge_output_price_microusd_per_million IS NULL "
    "AND source_judge_max_input_tokens IS NULL AND source_judge_max_output_tokens IS NULL)"
)
V5_JUDGE_SNAPSHOT = (
    "(answer_policy_version IS NOT NULL AND answer_policy_version = 'related_knowledge_navigation_v5' "
    "AND ai_catalog_version IS NULL AND ai_schema_policy_version IS NULL "
    "AND source_judge_provider IS NOT NULL AND source_judge_provider = 'gemini' "
    "AND source_judge_base_url IS NOT NULL AND source_judge_base_url = 'https://generativelanguage.googleapis.com' "
    "AND source_judge_model IS NOT NULL AND source_judge_model = 'gemini-3.5-flash-lite' "
    "AND source_judge_contract_version IS NOT NULL AND source_judge_contract_version = 'visual_source_id_v1' "
    "AND source_judge_input_price_microusd_per_million IS NOT NULL AND source_judge_input_price_microusd_per_million >= 300000 "
    "AND source_judge_output_price_microusd_per_million IS NOT NULL AND source_judge_output_price_microusd_per_million >= 2500000 "
    "AND source_judge_max_input_tokens IS NOT NULL AND source_judge_max_input_tokens BETWEEN 1 AND 32768 "
    "AND source_judge_max_output_tokens IS NOT NULL AND source_judge_max_output_tokens BETWEEN 1 AND 2048 "
    "AND source_judge_thinking_level IS NOT NULL AND source_judge_thinking_level = 'high' "
    "AND source_judge_timeout_seconds IS NOT NULL AND source_judge_timeout_seconds BETWEEN 1 AND 60)"
)
_v4_snapshot, _no_snapshot = OLD_JUDGE_SNAPSHOT.split(") OR ", 1)
JUDGE_SNAPSHOT = (
    _v4_snapshot + " AND source_judge_thinking_level IS NULL AND source_judge_timeout_seconds IS NULL) OR "
    + V5_JUDGE_SNAPSHOT + " OR "
    + _no_snapshot[:-1].replace("answer_policy_version <> 'related_knowledge_navigation_v4'",
                               "answer_policy_version NOT IN " + JUDGE_POLICIES)
    + " AND source_judge_thinking_level IS NULL AND source_judge_timeout_seconds IS NULL)"
)
OLD_RETRIEVAL_PAIR = "answer_policy_version IS NULL OR answer_policy_version <> 'related_knowledge_navigation_v4' OR retrieval_policy = 'hybrid_source_navigation_v9'"
NEW_RETRIEVAL_PAIR = "answer_policy_version IS NULL OR answer_policy_version NOT IN " + JUDGE_POLICIES + " OR retrieval_policy = 'hybrid_source_navigation_v9'"
OLD_STAGE_POLICY = "stage <> 'source_judgment' OR (answer_policy_version IS NOT NULL AND answer_policy_version = 'related_knowledge_navigation_v4')"
NEW_STAGE_POLICY = "stage <> 'source_judgment' OR (answer_policy_version IS NOT NULL AND answer_policy_version IN " + JUDGE_POLICIES + ")"
VISUAL_STAGE_CAP = (
    "answer_policy_version IS NULL OR answer_policy_version <> 'related_knowledge_navigation_v5' "
    "OR (stage IN ('query_embedding','retrieval','source_judgment') AND retry_count = 0 "
    "AND ((stage IN ('query_embedding','source_judgment') AND physical_request_count <= 1) "
    "OR (stage = 'retrieval' AND physical_request_count = 0)))"
)
OLD_JOB_CLAUSE = "IF NEW.answer_policy_version IN " + OLD_POLICIES + " THEN"
NEW_JOB_CLAUSE = "IF NEW.answer_policy_version IN " + NEW_POLICIES + " THEN"
OLD_JOB_NULL_RESULT = (
    "OR (NEW.answer_policy_version = 'related_knowledge_navigation_v4' "
    "AND NEW.result_kind = 'clarification_needed' AND EXISTS ("
    "SELECT 1 FROM rag_answer_stage_attempts WHERE job_id = NEW.id "
    "AND stage IN ('query_embedding','source_judgment'))) OR NEW.result_kind IS NULL"
)
NEW_JOB_NULL_RESULT = OLD_JOB_NULL_RESULT.replace(" OR NEW.result_kind IS NULL", "") + (
    " OR (NEW.answer_policy_version = 'related_knowledge_navigation_v5' "
    "AND NEW.result_kind = 'clarification_needed' AND EXISTS ("
    "SELECT 1 FROM rag_answer_stage_attempts WHERE job_id = NEW.id "
    "AND stage IN ('query_embedding','source_judgment')) AND NOT EXISTS ("
    "SELECT 1 FROM rag_answer_stage_attempts AS judged WHERE judged.job_id = NEW.id "
    "AND judged.answer_policy_version = 'related_knowledge_navigation_v5' "
    "AND judged.manual_retry_number = NEW.manual_retry_count "
    "AND judged.worker_attempt_number = NEW.attempt_count AND judged.stage = 'source_judgment' "
    "AND judged.completed_at IS NOT NULL AND judged.physical_request_count = 1 "
    "AND judged.retry_count = 0 AND judged.error_category IS NULL "
    "AND judged.failure_reason IS NULL AND NOT judged.execution_uncertain)) OR NEW.result_kind IS NULL"
)
OLD_JOB_NEW_SNAPSHOT = "NEW.ai_catalog_version, NEW.ai_schema_policy_version, " + ", ".join("NEW." + name for name in OLD_JUDGE_COLUMNS) + ", NEW.created_at"
OLD_JOB_OLD_SNAPSHOT = OLD_JOB_NEW_SNAPSHOT.replace("NEW.", "OLD.")
NEW_JOB_NEW_SNAPSHOT = OLD_JOB_NEW_SNAPSHOT.replace(", NEW.created_at", ", " + ", ".join("NEW." + name for name in VISUAL_COLUMNS) + ", NEW.created_at")
NEW_JOB_OLD_SNAPSHOT = NEW_JOB_NEW_SNAPSHOT.replace("NEW.", "OLD.")
OLD_REFERENCE_PAIR = "(answer_job.retrieval_policy IS NOT DISTINCT FROM 'hybrid_source_navigation_v8' AND answer_job.answer_policy_version IS NOT DISTINCT FROM 'related_knowledge_navigation_v2') OR (answer_job.retrieval_policy IS NOT DISTINCT FROM 'hybrid_source_navigation_v9' AND answer_job.answer_policy_version IS NOT DISTINCT FROM 'related_knowledge_navigation_v3') OR (answer_job.retrieval_policy IS NOT DISTINCT FROM 'hybrid_source_navigation_v9' AND answer_job.answer_policy_version IS NOT DISTINCT FROM 'related_knowledge_navigation_v4')"
NEW_REFERENCE_PAIR = OLD_REFERENCE_PAIR + " OR (answer_job.retrieval_policy IS NOT DISTINCT FROM 'hybrid_source_navigation_v9' AND answer_job.answer_policy_version IS NOT DISTINCT FROM 'related_knowledge_navigation_v5')"
OLD_REFERENCE_POLICY = "IF answer_job.answer_policy_version = 'related_knowledge_navigation_v4' AND"
NEW_REFERENCE_POLICY = "IF answer_job.answer_policy_version IN " + JUDGE_POLICIES + " AND"


def _replace_function(name: str, old: str, new: str, *, reverse: bool = False) -> None:
    definition = op.get_bind().scalar(sa.text("SELECT pg_get_functiondef(to_regprocedure(:name))").bindparams(name=name))
    if not isinstance(definition, str) or definition.count(old) != 1 or (not reverse and new in definition):
        raise RuntimeError(f"Unexpected {name} guard definition")
    op.execute(sa.text(definition.replace(old, new)))


def _checks(*, reverse: bool = False) -> None:
    for table, name, old, new in (
        ("rag_answer_jobs", "ck_rag_answer_jobs_identity", OLD_IDENTITY, NEW_IDENTITY),
        ("rag_answer_jobs", "ck_rag_answer_jobs_result", OLD_RESULT, NEW_RESULT),
        ("rag_answer_jobs", "ck_rag_answer_jobs_source_judge_snapshot", OLD_JUDGE_SNAPSHOT, JUDGE_SNAPSHOT),
        ("rag_answer_jobs", "ck_rag_answer_jobs_source_judge_retrieval_pair", OLD_RETRIEVAL_PAIR, NEW_RETRIEVAL_PAIR),
        ("rag_answer_stage_attempts", "ck_rag_answer_stage_source_judgment_policy", OLD_STAGE_POLICY, NEW_STAGE_POLICY),
    ):
        op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(name, table, old if reverse else new)


def _patches():
    return (
        ("rag_answer_job_guard()", OLD_JOB_CLAUSE, NEW_JOB_CLAUSE),
        ("rag_answer_job_guard()", OLD_JOB_NULL_RESULT, NEW_JOB_NULL_RESULT),
        ("rag_answer_job_guard()", OLD_JOB_NEW_SNAPSHOT, NEW_JOB_NEW_SNAPSHOT),
        ("rag_answer_job_guard()", OLD_JOB_OLD_SNAPSHOT, NEW_JOB_OLD_SNAPSHOT),
        ("rag_related_evidence_guard()", OLD_REFERENCE_PAIR, NEW_REFERENCE_PAIR),
        ("rag_related_evidence_guard()", OLD_REFERENCE_POLICY, NEW_REFERENCE_POLICY),
        ("enforce_rag_source_stage_parent_policy()", OLD_POLICIES, NEW_POLICIES),
    )


def _patch_parent(*, reverse: bool = False) -> None:
    name = "enforce_rag_source_stage_parent_policy()"
    old, new = (NEW_POLICIES, OLD_POLICIES) if reverse else (OLD_POLICIES, NEW_POLICIES)
    definition = op.get_bind().scalar(sa.text("SELECT pg_get_functiondef(to_regprocedure(:name))").bindparams(name=name))
    if not isinstance(definition, str) or definition.count(old) != 2:
        raise RuntimeError(f"Unexpected {name} guard definition")
    op.execute(sa.text(definition.replace(old, new)))


def upgrade() -> None:
    op.add_column("rag_answer_jobs", sa.Column("source_judge_thinking_level", sa.String(16), nullable=True))
    op.add_column("rag_answer_jobs", sa.Column("source_judge_timeout_seconds", sa.Float(), nullable=True))
    _checks()
    for name, old, new in _patches()[:-1]:
        _replace_function(name, old, new)
    _patch_parent()
    op.create_check_constraint("ck_rag_answer_stage_visual_judge_cap", "rag_answer_stage_attempts", VISUAL_STAGE_CAP)
    op.create_index("uq_rag_answer_stage_visual_remote_attempt", "rag_answer_stage_attempts",
                    ["job_id", "manual_retry_number", "stage"], unique=True,
                    postgresql_where=sa.text("answer_policy_version = 'related_knowledge_navigation_v5' AND stage IN ('query_embedding','source_judgment')"))


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM rag_answer_jobs WHERE answer_policy_version = 'related_knowledge_navigation_v5'")):
        raise RuntimeError("Cannot downgrade while v5 visual source-judgment job snapshots exist")
    _patch_parent(reverse=True)
    for name, old, new in reversed(_patches()[:-1]):
        _replace_function(name, new, old, reverse=True)
    _checks(reverse=True)
    op.drop_index("uq_rag_answer_stage_visual_remote_attempt", table_name="rag_answer_stage_attempts")
    op.drop_constraint("ck_rag_answer_stage_visual_judge_cap", "rag_answer_stage_attempts", type_="check")
    for name in reversed(VISUAL_COLUMNS):
        op.drop_column("rag_answer_jobs", name)
