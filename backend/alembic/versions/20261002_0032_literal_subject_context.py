"""Literal admission context v7; preserve prior visual snapshots and retention.

Revision ID: 20261002_0032
Revises: 20261001_0031
Predecessor deletion removes only its context binding, not a newer Ask job.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261002_0032"
down_revision = "20261001_0031"
branch_labels = None
depends_on = None
V7 = "related_knowledge_navigation_v7"
CONTEXT_POLICY = "literal_subject_admission_v1"
OLD_ERROR_PAIRS = (
    "(status IN ('queued','running','completed') AND error_code IS NULL AND error_message IS NULL "
    "AND NOT error_retryable) OR "
    "(status IN ('failed','cancelled') AND error_code IS NOT NULL AND error_message IS NOT NULL "
    "AND (status = 'failed' OR NOT error_retryable) AND ("
    "(error_code = 'rag_answer_failed' AND error_message = 'Answer generation failed.') OR "
    "(error_code = 'rag_answer_cancelled' AND error_message = 'Answer generation was cancelled.') OR "
    "(error_code = 'rag_answer_lease_expired' AND error_message = 'Answer worker lease expired.') OR "
    "(error_code = 'rag_ask_shutdown' AND error_message = 'Ask AI was paused before this answer completed.') OR "
    "(error_code = 'rag_access_revoked' AND error_message = 'Subject access is no longer available.') OR "
    "(error_code = 'rag_corpus_changed' AND error_message = 'Course materials changed before the answer completed.') OR "
    "(error_code = 'rag_profile_mismatch' AND error_message = 'Ask AI configuration changed before execution.')))"
)
NEW_ERROR_PAIRS = OLD_ERROR_PAIRS.replace(
    "(error_code = 'rag_profile_mismatch' AND error_message = 'Ask AI configuration changed before execution.')",
    "(error_code = 'rag_profile_mismatch' AND error_message = 'Ask AI configuration changed before execution.') OR "
    "(error_code = 'rag_question_context_changed' AND error_message = 'The question context changed or expired. Start a new search.')",
)
OLD_POLICIES = "('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3','related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6')"
NEW_POLICIES = "('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3','related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6','related_knowledge_navigation_v7')"
OLD_IDENTITY = "length(operation_key_hash) = 64 AND length(request_fingerprint) = 64 AND corpus_revision >= 0 AND length(embedding_space_hash) = 64 AND length(trim(retrieval_policy)) BETWEEN 1 AND 64 AND ((answer_policy_version IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3','related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6') AND ai_provider IS NULL AND ai_base_url IS NULL AND ai_model IS NULL AND support_policy_version IS NULL AND embedding_provider IS NOT NULL AND embedding_base_url IS NOT NULL AND embedding_model IS NOT NULL AND length(trim(embedding_provider)) BETWEEN 1 AND 32 AND length(trim(embedding_base_url)) BETWEEN 1 AND 512 AND length(trim(embedding_model)) BETWEEN 1 AND 128) OR ((answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3','related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6')) AND embedding_provider IS NULL AND embedding_base_url IS NULL AND embedding_model IS NULL AND ai_provider IS NOT NULL AND ai_base_url IS NOT NULL AND ai_model IS NOT NULL AND length(trim(ai_provider)) BETWEEN 1 AND 32 AND length(trim(ai_base_url)) BETWEEN 1 AND 512 AND length(trim(ai_model)) BETWEEN 1 AND 128))"
NEW_IDENTITY = "length(operation_key_hash) = 64 AND length(request_fingerprint) = 64 AND corpus_revision >= 0 AND length(embedding_space_hash) = 64 AND length(trim(retrieval_policy)) BETWEEN 1 AND 64 AND ((answer_policy_version IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3','related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6','related_knowledge_navigation_v7') AND ai_provider IS NULL AND ai_base_url IS NULL AND ai_model IS NULL AND support_policy_version IS NULL AND embedding_provider IS NOT NULL AND embedding_base_url IS NOT NULL AND embedding_model IS NOT NULL AND length(trim(embedding_provider)) BETWEEN 1 AND 32 AND length(trim(embedding_base_url)) BETWEEN 1 AND 512 AND length(trim(embedding_model)) BETWEEN 1 AND 128) OR ((answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3','related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6','related_knowledge_navigation_v7')) AND embedding_provider IS NULL AND embedding_base_url IS NULL AND embedding_model IS NULL AND ai_provider IS NOT NULL AND ai_base_url IS NOT NULL AND ai_model IS NOT NULL AND length(trim(ai_provider)) BETWEEN 1 AND 32 AND length(trim(ai_base_url)) BETWEEN 1 AND 512 AND length(trim(ai_model)) BETWEEN 1 AND 128))"
OLD_RESULT = "(status = 'completed' AND answer_policy_version IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3') AND result_kind IN ('related_knowledge','no_match') AND answer_message_id IS NULL AND error_code IS NULL) OR (status = 'completed' AND answer_policy_version IN ('related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6') AND result_kind IN ('related_knowledge','no_match','clarification_needed') AND answer_message_id IS NULL AND error_code IS NULL) OR (status = 'completed' AND (answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3','related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6')) AND result_kind IS NULL AND answer_message_id IS NOT NULL AND error_code IS NULL) OR (status <> 'completed' AND result_kind IS NULL AND answer_message_id IS NULL)"
NEW_RESULT = "(status = 'completed' AND answer_policy_version IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3') AND result_kind IN ('related_knowledge','no_match') AND answer_message_id IS NULL AND error_code IS NULL) OR (status = 'completed' AND answer_policy_version IN ('related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6','related_knowledge_navigation_v7') AND result_kind IN ('related_knowledge','no_match','clarification_needed') AND answer_message_id IS NULL AND error_code IS NULL) OR (status = 'completed' AND (answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3','related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6','related_knowledge_navigation_v7')) AND result_kind IS NULL AND answer_message_id IS NOT NULL AND error_code IS NULL) OR (status <> 'completed' AND result_kind IS NULL AND answer_message_id IS NULL)"
OLD_JUDGE_SNAPSHOT = "(answer_policy_version IS NOT NULL AND answer_policy_version = 'related_knowledge_navigation_v4' AND ai_catalog_version IS NULL AND ai_schema_policy_version IS NULL AND source_judge_provider IS NOT NULL AND source_judge_provider = 'gemini' AND source_judge_base_url IS NOT NULL AND source_judge_model IS NOT NULL AND source_judge_contract_version IS NOT NULL AND source_judge_input_price_microusd_per_million IS NOT NULL AND source_judge_output_price_microusd_per_million IS NOT NULL AND source_judge_max_input_tokens IS NOT NULL AND source_judge_max_output_tokens IS NOT NULL AND length(trim(source_judge_base_url)) BETWEEN 1 AND 512 AND length(trim(source_judge_model)) BETWEEN 1 AND 128 AND length(trim(source_judge_contract_version)) BETWEEN 1 AND 64 AND source_judge_input_price_microusd_per_million > 0 AND source_judge_output_price_microusd_per_million > 0 AND source_judge_max_input_tokens BETWEEN 1 AND 8192 AND source_judge_max_output_tokens BETWEEN 1 AND 1024 AND source_judge_thinking_level IS NULL AND source_judge_timeout_seconds IS NULL) OR (answer_policy_version IS NOT NULL AND answer_policy_version = 'related_knowledge_navigation_v5' AND ai_catalog_version IS NULL AND ai_schema_policy_version IS NULL AND source_judge_provider IS NOT NULL AND source_judge_provider = 'gemini' AND source_judge_base_url IS NOT NULL AND source_judge_base_url = 'https://generativelanguage.googleapis.com' AND source_judge_model IS NOT NULL AND source_judge_model = 'gemini-3.5-flash-lite' AND source_judge_contract_version IS NOT NULL AND source_judge_contract_version = 'visual_source_id_v1' AND source_judge_input_price_microusd_per_million IS NOT NULL AND source_judge_input_price_microusd_per_million >= 300000 AND source_judge_output_price_microusd_per_million IS NOT NULL AND source_judge_output_price_microusd_per_million >= 2500000 AND source_judge_max_input_tokens IS NOT NULL AND source_judge_max_input_tokens BETWEEN 1 AND 32768 AND source_judge_max_output_tokens IS NOT NULL AND source_judge_max_output_tokens BETWEEN 1 AND 2048 AND source_judge_thinking_level IS NOT NULL AND source_judge_thinking_level = 'high' AND source_judge_timeout_seconds IS NOT NULL AND source_judge_timeout_seconds BETWEEN 1 AND 60) OR (answer_policy_version IS NOT NULL AND answer_policy_version = 'related_knowledge_navigation_v6' AND ai_catalog_version IS NULL AND ai_schema_policy_version IS NULL AND source_judge_provider IS NOT NULL AND source_judge_provider = 'gemini' AND source_judge_base_url IS NOT NULL AND source_judge_base_url = 'https://generativelanguage.googleapis.com' AND source_judge_model IS NOT NULL AND source_judge_model = 'gemini-3.5-flash-lite' AND source_judge_contract_version IS NOT NULL AND source_judge_contract_version = 'visual_source_id_v2' AND source_judge_input_price_microusd_per_million IS NOT NULL AND source_judge_input_price_microusd_per_million >= 300000 AND source_judge_output_price_microusd_per_million IS NOT NULL AND source_judge_output_price_microusd_per_million >= 2500000 AND source_judge_max_input_tokens IS NOT NULL AND source_judge_max_input_tokens BETWEEN 1 AND 32768 AND source_judge_max_output_tokens IS NOT NULL AND source_judge_max_output_tokens BETWEEN 1 AND 4096 AND source_judge_thinking_level IS NOT NULL AND source_judge_thinking_level = 'high' AND source_judge_timeout_seconds IS NOT NULL AND source_judge_timeout_seconds BETWEEN 1 AND 60) OR ((answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6')) AND source_judge_provider IS NULL AND source_judge_base_url IS NULL AND source_judge_model IS NULL AND source_judge_contract_version IS NULL AND source_judge_input_price_microusd_per_million IS NULL AND source_judge_output_price_microusd_per_million IS NULL AND source_judge_max_input_tokens IS NULL AND source_judge_max_output_tokens IS NULL AND source_judge_thinking_level IS NULL AND source_judge_timeout_seconds IS NULL)"
JUDGE_SNAPSHOT = "(answer_policy_version IS NOT NULL AND answer_policy_version = 'related_knowledge_navigation_v4' AND ai_catalog_version IS NULL AND ai_schema_policy_version IS NULL AND source_judge_provider IS NOT NULL AND source_judge_provider = 'gemini' AND source_judge_base_url IS NOT NULL AND source_judge_model IS NOT NULL AND source_judge_contract_version IS NOT NULL AND source_judge_input_price_microusd_per_million IS NOT NULL AND source_judge_output_price_microusd_per_million IS NOT NULL AND source_judge_max_input_tokens IS NOT NULL AND source_judge_max_output_tokens IS NOT NULL AND length(trim(source_judge_base_url)) BETWEEN 1 AND 512 AND length(trim(source_judge_model)) BETWEEN 1 AND 128 AND length(trim(source_judge_contract_version)) BETWEEN 1 AND 64 AND source_judge_input_price_microusd_per_million > 0 AND source_judge_output_price_microusd_per_million > 0 AND source_judge_max_input_tokens BETWEEN 1 AND 8192 AND source_judge_max_output_tokens BETWEEN 1 AND 1024 AND source_judge_thinking_level IS NULL AND source_judge_timeout_seconds IS NULL) OR (answer_policy_version IS NOT NULL AND answer_policy_version = 'related_knowledge_navigation_v5' AND ai_catalog_version IS NULL AND ai_schema_policy_version IS NULL AND source_judge_provider IS NOT NULL AND source_judge_provider = 'gemini' AND source_judge_base_url IS NOT NULL AND source_judge_base_url = 'https://generativelanguage.googleapis.com' AND source_judge_model IS NOT NULL AND source_judge_model = 'gemini-3.5-flash-lite' AND source_judge_contract_version IS NOT NULL AND source_judge_contract_version = 'visual_source_id_v1' AND source_judge_input_price_microusd_per_million IS NOT NULL AND source_judge_input_price_microusd_per_million >= 300000 AND source_judge_output_price_microusd_per_million IS NOT NULL AND source_judge_output_price_microusd_per_million >= 2500000 AND source_judge_max_input_tokens IS NOT NULL AND source_judge_max_input_tokens BETWEEN 1 AND 32768 AND source_judge_max_output_tokens IS NOT NULL AND source_judge_max_output_tokens BETWEEN 1 AND 2048 AND source_judge_thinking_level IS NOT NULL AND source_judge_thinking_level = 'high' AND source_judge_timeout_seconds IS NOT NULL AND source_judge_timeout_seconds BETWEEN 1 AND 60) OR (answer_policy_version IS NOT NULL AND answer_policy_version = 'related_knowledge_navigation_v6' AND ai_catalog_version IS NULL AND ai_schema_policy_version IS NULL AND source_judge_provider IS NOT NULL AND source_judge_provider = 'gemini' AND source_judge_base_url IS NOT NULL AND source_judge_base_url = 'https://generativelanguage.googleapis.com' AND source_judge_model IS NOT NULL AND source_judge_model = 'gemini-3.5-flash-lite' AND source_judge_contract_version IS NOT NULL AND source_judge_contract_version = 'visual_source_id_v2' AND source_judge_input_price_microusd_per_million IS NOT NULL AND source_judge_input_price_microusd_per_million >= 300000 AND source_judge_output_price_microusd_per_million IS NOT NULL AND source_judge_output_price_microusd_per_million >= 2500000 AND source_judge_max_input_tokens IS NOT NULL AND source_judge_max_input_tokens BETWEEN 1 AND 32768 AND source_judge_max_output_tokens IS NOT NULL AND source_judge_max_output_tokens BETWEEN 1 AND 4096 AND source_judge_thinking_level IS NOT NULL AND source_judge_thinking_level = 'high' AND source_judge_timeout_seconds IS NOT NULL AND source_judge_timeout_seconds BETWEEN 1 AND 60) OR (answer_policy_version IS NOT NULL AND answer_policy_version = 'related_knowledge_navigation_v7' AND ai_catalog_version IS NULL AND ai_schema_policy_version IS NULL AND source_judge_provider IS NOT NULL AND source_judge_provider = 'gemini' AND source_judge_base_url IS NOT NULL AND source_judge_base_url = 'https://generativelanguage.googleapis.com' AND source_judge_model IS NOT NULL AND source_judge_model = 'gemini-3.5-flash-lite' AND source_judge_contract_version IS NOT NULL AND source_judge_contract_version = 'visual_source_id_v3' AND source_judge_input_price_microusd_per_million IS NOT NULL AND source_judge_input_price_microusd_per_million >= 300000 AND source_judge_output_price_microusd_per_million IS NOT NULL AND source_judge_output_price_microusd_per_million >= 2500000 AND source_judge_max_input_tokens IS NOT NULL AND source_judge_max_input_tokens BETWEEN 1 AND 32768 AND source_judge_max_output_tokens IS NOT NULL AND source_judge_max_output_tokens BETWEEN 1 AND 4096 AND source_judge_thinking_level IS NOT NULL AND source_judge_thinking_level = 'high' AND source_judge_timeout_seconds IS NOT NULL AND source_judge_timeout_seconds BETWEEN 1 AND 120) OR ((answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6','related_knowledge_navigation_v7')) AND source_judge_provider IS NULL AND source_judge_base_url IS NULL AND source_judge_model IS NULL AND source_judge_contract_version IS NULL AND source_judge_input_price_microusd_per_million IS NULL AND source_judge_output_price_microusd_per_million IS NULL AND source_judge_max_input_tokens IS NULL AND source_judge_max_output_tokens IS NULL AND source_judge_thinking_level IS NULL AND source_judge_timeout_seconds IS NULL)"
OLD_RETRIEVAL_PAIR = "answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6') OR retrieval_policy = 'hybrid_source_navigation_v9'"
NEW_RETRIEVAL_PAIR = "answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6','related_knowledge_navigation_v7') OR retrieval_policy = 'hybrid_source_navigation_v9'"
OLD_STAGE_POLICY = "stage <> 'source_judgment' OR (answer_policy_version IS NOT NULL AND answer_policy_version IN ('related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6'))"
NEW_STAGE_POLICY = "stage <> 'source_judgment' OR (answer_policy_version IS NOT NULL AND answer_policy_version IN ('related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6','related_knowledge_navigation_v7'))"
OLD_VISUAL_STAGE_CAP = "answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_navigation_v5','related_knowledge_navigation_v6') OR (stage IN ('query_embedding','retrieval','source_judgment') AND retry_count = 0 AND ((stage IN ('query_embedding','source_judgment') AND physical_request_count <= 1) OR (stage = 'retrieval' AND physical_request_count = 0)))"
VISUAL_STAGE_CAP = "answer_policy_version IS NULL OR answer_policy_version NOT IN ('related_knowledge_navigation_v5','related_knowledge_navigation_v6','related_knowledge_navigation_v7') OR (stage IN ('query_embedding','retrieval','source_judgment') AND retry_count = 0 AND ((stage IN ('query_embedding','source_judgment') AND physical_request_count <= 1) OR (stage = 'retrieval' AND physical_request_count = 0)))"
OLD_JOB_CLAUSE = "IF NEW.answer_policy_version IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3','related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6') THEN"
NEW_JOB_CLAUSE = "IF NEW.answer_policy_version IN ('related_knowledge_v1','related_knowledge_navigation_v2','related_knowledge_navigation_v3','related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6','related_knowledge_navigation_v7') THEN"
OLD_JOB_NULL_RESULT = "OR (NEW.answer_policy_version = 'related_knowledge_navigation_v4' AND NEW.result_kind = 'clarification_needed' AND EXISTS (SELECT 1 FROM rag_answer_stage_attempts WHERE job_id = NEW.id AND stage IN ('query_embedding','source_judgment'))) OR (NEW.answer_policy_version = 'related_knowledge_navigation_v5' AND NEW.result_kind = 'clarification_needed' AND EXISTS (SELECT 1 FROM rag_answer_stage_attempts WHERE job_id = NEW.id AND stage IN ('query_embedding','source_judgment')) AND NOT EXISTS (SELECT 1 FROM rag_answer_stage_attempts AS judged WHERE judged.job_id = NEW.id AND judged.answer_policy_version = 'related_knowledge_navigation_v5' AND judged.manual_retry_number = NEW.manual_retry_count AND judged.worker_attempt_number = NEW.attempt_count AND judged.stage = 'source_judgment' AND judged.completed_at IS NOT NULL AND judged.physical_request_count = 1 AND judged.retry_count = 0 AND judged.error_category IS NULL AND judged.failure_reason IS NULL AND NOT judged.execution_uncertain)) OR (NEW.answer_policy_version = 'related_knowledge_navigation_v6' AND NEW.result_kind = 'clarification_needed' AND EXISTS (SELECT 1 FROM rag_answer_stage_attempts WHERE job_id = NEW.id AND stage IN ('query_embedding','source_judgment')) AND NOT EXISTS (SELECT 1 FROM rag_answer_stage_attempts AS judged WHERE judged.job_id = NEW.id AND judged.answer_policy_version = 'related_knowledge_navigation_v6' AND judged.manual_retry_number = NEW.manual_retry_count AND judged.worker_attempt_number = NEW.attempt_count AND judged.stage = 'source_judgment' AND judged.completed_at IS NOT NULL AND judged.physical_request_count = 1 AND judged.retry_count = 0 AND judged.error_category IS NULL AND judged.failure_reason IS NULL AND NOT judged.execution_uncertain)) OR NEW.result_kind IS NULL"
NEW_JOB_NULL_RESULT = "OR (NEW.answer_policy_version = 'related_knowledge_navigation_v4' AND NEW.result_kind = 'clarification_needed' AND EXISTS (SELECT 1 FROM rag_answer_stage_attempts WHERE job_id = NEW.id AND stage IN ('query_embedding','source_judgment'))) OR (NEW.answer_policy_version = 'related_knowledge_navigation_v5' AND NEW.result_kind = 'clarification_needed' AND EXISTS (SELECT 1 FROM rag_answer_stage_attempts WHERE job_id = NEW.id AND stage IN ('query_embedding','source_judgment')) AND NOT EXISTS (SELECT 1 FROM rag_answer_stage_attempts AS judged WHERE judged.job_id = NEW.id AND judged.answer_policy_version = 'related_knowledge_navigation_v5' AND judged.manual_retry_number = NEW.manual_retry_count AND judged.worker_attempt_number = NEW.attempt_count AND judged.stage = 'source_judgment' AND judged.completed_at IS NOT NULL AND judged.physical_request_count = 1 AND judged.retry_count = 0 AND judged.error_category IS NULL AND judged.failure_reason IS NULL AND NOT judged.execution_uncertain)) OR (NEW.answer_policy_version = 'related_knowledge_navigation_v6' AND NEW.result_kind = 'clarification_needed' AND EXISTS (SELECT 1 FROM rag_answer_stage_attempts WHERE job_id = NEW.id AND stage IN ('query_embedding','source_judgment')) AND NOT EXISTS (SELECT 1 FROM rag_answer_stage_attempts AS judged WHERE judged.job_id = NEW.id AND judged.answer_policy_version = 'related_knowledge_navigation_v6' AND judged.manual_retry_number = NEW.manual_retry_count AND judged.worker_attempt_number = NEW.attempt_count AND judged.stage = 'source_judgment' AND judged.completed_at IS NOT NULL AND judged.physical_request_count = 1 AND judged.retry_count = 0 AND judged.error_category IS NULL AND judged.failure_reason IS NULL AND NOT judged.execution_uncertain)) OR (NEW.answer_policy_version = 'related_knowledge_navigation_v7' AND NEW.result_kind = 'clarification_needed' AND EXISTS (SELECT 1 FROM rag_answer_stage_attempts WHERE job_id = NEW.id AND stage IN ('query_embedding','source_judgment')) AND NOT EXISTS (SELECT 1 FROM rag_answer_stage_attempts AS judged WHERE judged.job_id = NEW.id AND judged.answer_policy_version = 'related_knowledge_navigation_v7' AND judged.manual_retry_number = NEW.manual_retry_count AND judged.worker_attempt_number = NEW.attempt_count AND judged.stage = 'source_judgment' AND judged.completed_at IS NOT NULL AND judged.physical_request_count = 1 AND judged.retry_count = 0 AND judged.error_category IS NULL AND judged.failure_reason IS NULL AND NOT judged.execution_uncertain)) OR NEW.result_kind IS NULL"
OLD_REFERENCE_PAIR = "(answer_job.retrieval_policy IS NOT DISTINCT FROM 'hybrid_source_navigation_v8' AND answer_job.answer_policy_version IS NOT DISTINCT FROM 'related_knowledge_navigation_v2') OR (answer_job.retrieval_policy IS NOT DISTINCT FROM 'hybrid_source_navigation_v9' AND answer_job.answer_policy_version IS NOT DISTINCT FROM 'related_knowledge_navigation_v3') OR (answer_job.retrieval_policy IS NOT DISTINCT FROM 'hybrid_source_navigation_v9' AND answer_job.answer_policy_version IS NOT DISTINCT FROM 'related_knowledge_navigation_v4') OR (answer_job.retrieval_policy IS NOT DISTINCT FROM 'hybrid_source_navigation_v9' AND answer_job.answer_policy_version IS NOT DISTINCT FROM 'related_knowledge_navigation_v5') OR (answer_job.retrieval_policy IS NOT DISTINCT FROM 'hybrid_source_navigation_v9' AND answer_job.answer_policy_version IS NOT DISTINCT FROM 'related_knowledge_navigation_v6')"
NEW_REFERENCE_PAIR = "(answer_job.retrieval_policy IS NOT DISTINCT FROM 'hybrid_source_navigation_v8' AND answer_job.answer_policy_version IS NOT DISTINCT FROM 'related_knowledge_navigation_v2') OR (answer_job.retrieval_policy IS NOT DISTINCT FROM 'hybrid_source_navigation_v9' AND answer_job.answer_policy_version IS NOT DISTINCT FROM 'related_knowledge_navigation_v3') OR (answer_job.retrieval_policy IS NOT DISTINCT FROM 'hybrid_source_navigation_v9' AND answer_job.answer_policy_version IS NOT DISTINCT FROM 'related_knowledge_navigation_v4') OR (answer_job.retrieval_policy IS NOT DISTINCT FROM 'hybrid_source_navigation_v9' AND answer_job.answer_policy_version IS NOT DISTINCT FROM 'related_knowledge_navigation_v5') OR (answer_job.retrieval_policy IS NOT DISTINCT FROM 'hybrid_source_navigation_v9' AND answer_job.answer_policy_version IS NOT DISTINCT FROM 'related_knowledge_navigation_v6') OR (answer_job.retrieval_policy IS NOT DISTINCT FROM 'hybrid_source_navigation_v9' AND answer_job.answer_policy_version IS NOT DISTINCT FROM 'related_knowledge_navigation_v7')"
OLD_REFERENCE_POLICY = "IF answer_job.answer_policy_version IN ('related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6') AND"
NEW_REFERENCE_POLICY = "IF answer_job.answer_policy_version IN ('related_knowledge_navigation_v4','related_knowledge_navigation_v5','related_knowledge_navigation_v6','related_knowledge_navigation_v7') AND"
OLD_VISUAL_INDEX = "answer_policy_version IN ('related_knowledge_navigation_v5','related_knowledge_navigation_v6') AND stage IN ('query_embedding','source_judgment')"
NEW_VISUAL_INDEX = "answer_policy_version IN ('related_knowledge_navigation_v5','related_knowledge_navigation_v6','related_knowledge_navigation_v7') AND stage IN ('query_embedding','source_judgment')"

JOB_CONTEXT_CHECK = (
    "(answer_policy_version IS NOT NULL AND answer_policy_version = 'related_knowledge_navigation_v7' "
    "AND source_context_policy_version IS NOT NULL AND source_context_policy_version = 'literal_subject_admission_v1' "
    "AND source_context_admission_sha256 IS NOT NULL AND source_context_admission_sha256 ~ '^[0-9a-f]{64}$') "
    "OR ((answer_policy_version IS NULL OR answer_policy_version <> 'related_knowledge_navigation_v7') "
    "AND source_context_policy_version IS NULL AND source_context_admission_sha256 IS NULL)"
)
JOB_NEW_SNAPSHOT = "NEW.source_judge_timeout_seconds, NEW.created_at"
JOB_OLD_SNAPSHOT = JOB_NEW_SNAPSHOT.replace("NEW.", "OLD.")
JOB_NEW_CONTEXT_SNAPSHOT = "NEW.source_judge_timeout_seconds, NEW.source_context_policy_version, NEW.source_context_admission_sha256, NEW.created_at"
JOB_OLD_CONTEXT_SNAPSHOT = JOB_NEW_CONTEXT_SNAPSHOT.replace("NEW.", "OLD.")
CONTEXT_COLUMNS = (
    "job_id", "thread_id", "user_id", "subject_id", "current_message_id", "context_version",
    "raw_question_clear", "current_question_sha256", "current_created_at", "current_expires_at",
    "captured_at", "admission_sha256", "preceding_message_id", "preceding_question_sha256",
    "preceding_created_at", "preceding_expires_at", "subject_start_offset", "subject_end_offset",
    "subject_start_byte_offset", "subject_end_byte_offset", "subject_sha256",
)
PRECEDING_COLUMNS = ("preceding_message_id", "preceding_question_sha256", "preceding_created_at", "preceding_expires_at")
SUBJECT_COLUMNS = ("subject_start_offset", "subject_end_offset", "subject_start_byte_offset", "subject_end_byte_offset", "subject_sha256")
_no_preceding = " AND ".join(name + " IS NULL" for name in PRECEDING_COLUMNS)
_full_preceding = " AND ".join(name + " IS NOT NULL" for name in PRECEDING_COLUMNS)
_no_subject = " AND ".join(name + " IS NULL" for name in SUBJECT_COLUMNS)
_full_subject = " AND ".join(name + " IS NOT NULL" for name in SUBJECT_COLUMNS)
CONTEXT_SHAPE_CHECK = (
    "context_version = 'literal_subject_admission_v1' "
    "AND current_question_sha256 ~ '^[0-9a-f]{64}$' AND admission_sha256 ~ '^[0-9a-f]{64}$' "
    "AND current_created_at <= captured_at AND current_expires_at > captured_at "
    "AND current_expires_at > current_created_at "
    "AND ((" + _no_preceding + ") OR (" + _full_preceding + " AND preceding_message_id <> current_message_id "
    "AND preceding_question_sha256 ~ '^[0-9a-f]{64}$' AND preceding_created_at < current_created_at "
    "AND preceding_expires_at > captured_at AND preceding_expires_at > preceding_created_at)) "
    "AND ((" + _no_subject + ") OR (" + _full_subject + " AND " + _full_preceding +
    " AND subject_start_offset >= 0 AND subject_end_offset > subject_start_offset "
    "AND subject_end_offset - subject_start_offset <= 160 AND subject_start_byte_offset >= 0 "
    "AND subject_end_byte_offset > subject_start_byte_offset "
    "AND subject_end_byte_offset - subject_start_byte_offset <= 640 "
    "AND subject_sha256 ~ '^[0-9a-f]{64}$')) "
    "AND (NOT raw_question_clear OR (" + _no_preceding + " AND " + _no_subject + "))"
)


def _context_guard_sql() -> str:
    new_fields = ", ".join("NEW." + name for name in CONTEXT_COLUMNS)
    old_fields = new_fields.replace("NEW.", "OLD.")
    return f"""
    CREATE FUNCTION rag_answer_question_context_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE
        answer_job rag_answer_jobs%ROWTYPE;
        current_question rag_messages%ROWTYPE;
        previous_question rag_messages%ROWTYPE;
        latest_user_id uuid;
        literal_subject text;
    BEGIN
        IF TG_OP = 'UPDATE' THEN
            IF ({new_fields}) IS DISTINCT FROM ({old_fields}) THEN
                RAISE EXCEPTION 'Ask question context snapshot is immutable';
            END IF;
            RETURN NEW;
        END IF;
        SELECT * INTO answer_job FROM rag_answer_jobs WHERE id = NEW.job_id FOR KEY SHARE;
        IF NOT FOUND OR answer_job.answer_policy_version IS DISTINCT FROM '{V7}'
            OR answer_job.status <> 'queued' OR answer_job.attempt_count <> 0
            OR answer_job.question_message_id IS DISTINCT FROM NEW.current_message_id
            OR answer_job.thread_id IS DISTINCT FROM NEW.thread_id
            OR answer_job.user_id IS DISTINCT FROM NEW.user_id
            OR answer_job.subject_id IS DISTINCT FROM NEW.subject_id
            OR answer_job.source_context_policy_version IS DISTINCT FROM NEW.context_version
            OR answer_job.source_context_admission_sha256 IS DISTINCT FROM NEW.admission_sha256
            OR NEW.captured_at > answer_job.created_at THEN
            RAISE EXCEPTION 'Ask question context parent snapshot mismatch';
        END IF;
        PERFORM 1 FROM rag_threads WHERE id = NEW.thread_id AND user_id = NEW.user_id
            AND subject_id = NEW.subject_id FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Ask question context thread unavailable'; END IF;
        SELECT * INTO current_question FROM rag_messages WHERE id = NEW.current_message_id
            AND thread_id = NEW.thread_id AND user_id = NEW.user_id AND subject_id = NEW.subject_id FOR KEY SHARE;
        IF NOT FOUND OR current_question.role <> 'user'
            OR current_question.created_at IS DISTINCT FROM NEW.current_created_at
            OR current_question.expires_at IS DISTINCT FROM NEW.current_expires_at
            OR current_question.expires_at <= clock_timestamp()
            OR encode(sha256(convert_to(current_question.content, 'UTF8')), 'hex') IS DISTINCT FROM NEW.current_question_sha256
            OR NEW.captured_at > clock_timestamp() THEN
            RAISE EXCEPTION 'Ask current question context mismatch';
        END IF;
        IF NEW.preceding_message_id IS NOT NULL THEN
            SELECT id INTO latest_user_id FROM rag_messages
                WHERE thread_id = NEW.thread_id AND user_id = NEW.user_id AND subject_id = NEW.subject_id
                AND role = 'user' AND id <> NEW.current_message_id
                AND created_at < current_question.created_at
                ORDER BY created_at DESC, id DESC LIMIT 1;
            IF latest_user_id IS DISTINCT FROM NEW.preceding_message_id THEN
                RAISE EXCEPTION 'Ask preceding question is not the admission latest user';
            END IF;
        END IF;
        IF NEW.preceding_message_id IS NOT NULL THEN
            SELECT * INTO previous_question FROM rag_messages WHERE id = NEW.preceding_message_id
                AND thread_id = NEW.thread_id AND user_id = NEW.user_id AND subject_id = NEW.subject_id FOR KEY SHARE;
            IF NOT FOUND OR previous_question.role <> 'user'
                OR previous_question.created_at >= current_question.created_at
                OR previous_question.created_at IS DISTINCT FROM NEW.preceding_created_at
                OR previous_question.expires_at IS DISTINCT FROM NEW.preceding_expires_at
                OR previous_question.expires_at <= clock_timestamp()
                OR encode(sha256(convert_to(previous_question.content, 'UTF8')), 'hex') IS DISTINCT FROM NEW.preceding_question_sha256 THEN
                RAISE EXCEPTION 'Ask preceding question context mismatch';
            END IF;
            IF NEW.subject_start_offset IS NOT NULL THEN
                literal_subject := substring(previous_question.content FROM NEW.subject_start_offset + 1
                    FOR NEW.subject_end_offset - NEW.subject_start_offset);
                IF char_length(literal_subject) <> NEW.subject_end_offset - NEW.subject_start_offset
                    OR encode(sha256(convert_to(literal_subject, 'UTF8')), 'hex') IS DISTINCT FROM NEW.subject_sha256
                    OR octet_length(convert_to(substring(previous_question.content FROM 1 FOR NEW.subject_start_offset), 'UTF8')) <> NEW.subject_start_byte_offset
                    OR octet_length(convert_to(substring(previous_question.content FROM 1 FOR NEW.subject_end_offset), 'UTF8')) <> NEW.subject_end_byte_offset THEN
                    RAISE EXCEPTION 'Ask literal subject context mismatch';
                END IF;
            END IF;
        END IF;
        RETURN NEW;
    END;
    $$;
    """


CONTEXT_ADMISSION_GUARD = f"""
CREATE FUNCTION enforce_rag_question_context_admission() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE current_job rag_answer_jobs%ROWTYPE;
BEGIN
    SELECT * INTO current_job FROM rag_answer_jobs WHERE id = NEW.id;
    IF FOUND AND current_job.answer_policy_version = '{V7}' AND NOT EXISTS (
        SELECT 1 FROM rag_answer_question_context WHERE job_id = current_job.id
        AND context_version = current_job.source_context_policy_version
        AND admission_sha256 = current_job.source_context_admission_sha256
    ) THEN
        RAISE EXCEPTION 'Ask v7 requires its immutable admission context binding';
    END IF;
    RETURN NEW;
END;
$$;
"""


def _replace_function(name: str, old: str, new: str, *, reverse: bool = False) -> None:
    definition = op.get_bind().scalar(sa.text("SELECT pg_get_functiondef(to_regprocedure(:name))").bindparams(name=name))
    if not isinstance(definition, str) or definition.count(old) != 1 or (not reverse and new in definition):
        raise RuntimeError(f"Unexpected {name} guard definition")
    op.execute(sa.text(definition.replace(old, new)))


def _patches():
    return (
        ("rag_answer_job_guard()", OLD_JOB_CLAUSE, NEW_JOB_CLAUSE),
        ("rag_answer_job_guard()", OLD_JOB_NULL_RESULT, NEW_JOB_NULL_RESULT),
        ("rag_answer_job_guard()", JOB_NEW_SNAPSHOT, JOB_NEW_CONTEXT_SNAPSHOT),
        ("rag_answer_job_guard()", JOB_OLD_SNAPSHOT, JOB_OLD_CONTEXT_SNAPSHOT),
        ("rag_related_evidence_guard()", OLD_REFERENCE_PAIR, NEW_REFERENCE_PAIR),
        ("rag_related_evidence_guard()", OLD_REFERENCE_POLICY, NEW_REFERENCE_POLICY),
    )


def _patch_parent(*, reverse: bool = False) -> None:
    name = "enforce_rag_source_stage_parent_policy()"
    old, new = (NEW_POLICIES, OLD_POLICIES) if reverse else (OLD_POLICIES, NEW_POLICIES)
    definition = op.get_bind().scalar(sa.text("SELECT pg_get_functiondef(to_regprocedure(:name))").bindparams(name=name))
    if not isinstance(definition, str) or definition.count(old) != 2:
        raise RuntimeError(f"Unexpected {name} guard definition")
    op.execute(sa.text(definition.replace(old, new)))


def _checks(*, reverse: bool = False) -> None:
    for table, name, old, new in (
        ("rag_answer_jobs", "ck_rag_answer_jobs_error_pair", OLD_ERROR_PAIRS, NEW_ERROR_PAIRS),
        ("rag_answer_jobs", "ck_rag_answer_jobs_identity", OLD_IDENTITY, NEW_IDENTITY),
        ("rag_answer_jobs", "ck_rag_answer_jobs_result", OLD_RESULT, NEW_RESULT),
        ("rag_answer_jobs", "ck_rag_answer_jobs_source_judge_snapshot", OLD_JUDGE_SNAPSHOT, JUDGE_SNAPSHOT),
        ("rag_answer_jobs", "ck_rag_answer_jobs_source_judge_retrieval_pair", OLD_RETRIEVAL_PAIR, NEW_RETRIEVAL_PAIR),
        ("rag_answer_stage_attempts", "ck_rag_answer_stage_source_judgment_policy", OLD_STAGE_POLICY, NEW_STAGE_POLICY),
        ("rag_answer_stage_attempts", "ck_rag_answer_stage_visual_judge_cap", OLD_VISUAL_STAGE_CAP, VISUAL_STAGE_CAP),
    ):
        op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(name, table, old if reverse else new)


def _index(*, reverse: bool = False) -> None:
    op.drop_index("uq_rag_answer_stage_visual_remote_attempt", table_name="rag_answer_stage_attempts")
    op.create_index("uq_rag_answer_stage_visual_remote_attempt", "rag_answer_stage_attempts",
        ["job_id", "manual_retry_number", "stage"], unique=True,
        postgresql_where=sa.text(OLD_VISUAL_INDEX if reverse else NEW_VISUAL_INDEX))


def upgrade() -> None:
    op.add_column("rag_answer_jobs", sa.Column("source_context_policy_version", sa.String(64), nullable=True))
    op.add_column("rag_answer_jobs", sa.Column("source_context_admission_sha256", sa.String(64), nullable=True))
    op.create_check_constraint("ck_rag_answer_jobs_source_context_snapshot", "rag_answer_jobs", JOB_CONTEXT_CHECK)
    _checks()
    for name, old, new in _patches():
        _replace_function(name, old, new)
    _patch_parent()
    _index()
    uuid = postgresql.UUID(as_uuid=True)
    timestamp = sa.DateTime(timezone=True)
    op.create_table("rag_answer_question_context",
        sa.Column("job_id", uuid, nullable=False), sa.Column("thread_id", uuid, nullable=False),
        sa.Column("user_id", uuid, nullable=False), sa.Column("subject_id", uuid, nullable=False),
        sa.Column("current_message_id", uuid, nullable=False),
        sa.Column("context_version", sa.String(64), nullable=False),
        sa.Column("raw_question_clear", sa.Boolean(), nullable=False),
        sa.Column("current_question_sha256", sa.String(64), nullable=False),
        sa.Column("current_created_at", timestamp, nullable=False),
        sa.Column("current_expires_at", timestamp, nullable=False),
        sa.Column("captured_at", timestamp, nullable=False),
        sa.Column("admission_sha256", sa.String(64), nullable=False),
        sa.Column("preceding_message_id", uuid, nullable=True),
        sa.Column("preceding_question_sha256", sa.String(64), nullable=True),
        sa.Column("preceding_created_at", timestamp, nullable=True),
        sa.Column("preceding_expires_at", timestamp, nullable=True),
        sa.Column("subject_start_offset", sa.Integer(), nullable=True),
        sa.Column("subject_end_offset", sa.Integer(), nullable=True),
        sa.Column("subject_start_byte_offset", sa.Integer(), nullable=True),
        sa.Column("subject_end_byte_offset", sa.Integer(), nullable=True),
        sa.Column("subject_sha256", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("job_id", name="pk_rag_answer_question_context"),
        sa.ForeignKeyConstraint(["job_id", "thread_id", "user_id", "subject_id"],
            ["rag_answer_jobs.id", "rag_answer_jobs.thread_id", "rag_answer_jobs.user_id", "rag_answer_jobs.subject_id"],
            ondelete="CASCADE", name="fk_rag_question_context_job_scope"),
        sa.ForeignKeyConstraint(["current_message_id", "thread_id", "user_id", "subject_id"],
            ["rag_messages.id", "rag_messages.thread_id", "rag_messages.user_id", "rag_messages.subject_id"],
            ondelete="CASCADE", name="fk_rag_question_context_current_scope"),
        sa.ForeignKeyConstraint(["preceding_message_id", "thread_id", "user_id", "subject_id"],
            ["rag_messages.id", "rag_messages.thread_id", "rag_messages.user_id", "rag_messages.subject_id"],
            ondelete="CASCADE", name="fk_rag_question_context_preceding_scope"),
        sa.CheckConstraint(CONTEXT_SHAPE_CHECK, name="ck_rag_question_context_shape"),
    )
    op.create_index("ix_rag_question_context_preceding", "rag_answer_question_context", ["preceding_message_id", "job_id"])
    op.execute(sa.text(_context_guard_sql()))
    op.execute(sa.text("CREATE TRIGGER trg_rag_question_context_guard BEFORE INSERT OR UPDATE ON rag_answer_question_context FOR EACH ROW EXECUTE FUNCTION rag_answer_question_context_guard()"))
    op.execute(sa.text(CONTEXT_ADMISSION_GUARD))
    op.execute(sa.text("CREATE CONSTRAINT TRIGGER trg_rag_question_context_admission AFTER INSERT ON rag_answer_jobs DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION enforce_rag_question_context_admission()"))


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM rag_answer_jobs WHERE answer_policy_version = 'related_knowledge_navigation_v7'")):
        raise RuntimeError("Cannot downgrade while v7 literal-context job snapshots exist")
    op.execute(sa.text("DROP TRIGGER trg_rag_question_context_admission ON rag_answer_jobs"))
    op.execute(sa.text("DROP FUNCTION enforce_rag_question_context_admission()"))
    op.execute(sa.text("DROP TRIGGER trg_rag_question_context_guard ON rag_answer_question_context"))
    op.execute(sa.text("DROP FUNCTION rag_answer_question_context_guard()"))
    op.drop_index("ix_rag_question_context_preceding", table_name="rag_answer_question_context")
    op.drop_table("rag_answer_question_context")
    _patch_parent(reverse=True)
    for name, old, new in reversed(_patches()):
        _replace_function(name, new, old, reverse=True)
    _checks(reverse=True)
    _index(reverse=True)
    op.drop_constraint("ck_rag_answer_jobs_source_context_snapshot", "rag_answer_jobs", type_="check")
    op.drop_column("rag_answer_jobs", "source_context_admission_sha256")
    op.drop_column("rag_answer_jobs", "source_context_policy_version")
