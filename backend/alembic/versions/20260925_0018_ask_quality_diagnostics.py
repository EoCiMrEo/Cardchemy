"""Add content-free Ask quality diagnostics and honest abstention reasons.

Revision ID: 20260925_0018
Revises: 20260922_0017
Create Date: 2026-09-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "20260925_0018"
down_revision = "20260922_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rag_messages", sa.Column("abstention_kind", sa.String(32), nullable=True))
    op.create_check_constraint(
        "ck_rag_messages_abstention_kind", "rag_messages",
        "abstention_kind IS NULL OR (role = 'assistant' AND outcome = 'abstained' "
        "AND abstention_kind IN ('retrieval_insufficient','model_abstained','support_rejected'))",
    )
    op.add_column("rag_answer_jobs", sa.Column("failure_reason", sa.String(64), nullable=True))
    op.create_check_constraint(
        "ck_rag_answer_jobs_failure_reason", "rag_answer_jobs",
        "failure_reason IS NULL OR failure_reason IN ("
        "'transport_timeout','transport_protocol','transport_network',"
        "'http_invalid_request','http_authentication','http_access_denied',"
        "'http_model_missing','http_rate_limited','http_server_error',"
        "'http_transient','http_rejected','sdk_unclassified',"
        "'output_empty','output_blocked','output_unfinished','json_invalid',"
        "'schema_invalid','citation_invalid','answer_too_long',"
        "'retrieval_failed','retrieval_timeout','local_support_unavailable',"
        "'local_support_timeout','rag_access_revoked','rag_corpus_changed',"
        "'internal_failure')",
    )
    for column in (
        sa.Column("failure_reason", sa.String(64), nullable=True),
        sa.Column("provider_finish_reason", sa.String(32), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("usage_estimated", sa.Boolean(), nullable=True),
        sa.Column("retrieval_ranks", JSONB(), nullable=True),
        sa.Column("support_reason", sa.String(64), nullable=True),
        sa.Column("support_entailment", sa.String(16), nullable=True),
        sa.Column("support_question_relevance", sa.String(16), nullable=True),
        sa.Column("support_equivalence", sa.String(16), nullable=True),
        sa.Column("support_contradiction", sa.String(16), nullable=True),
    ):
        op.add_column("rag_answer_stage_attempts", column)
    op.create_check_constraint(
        "ck_rag_answer_stage_quality_usage", "rag_answer_stage_attempts",
        "(input_tokens IS NULL OR input_tokens >= 0) AND "
        "(output_tokens IS NULL OR output_tokens >= 0) AND "
        "(failure_reason IS NULL OR failure_reason IN ("
        "'transport_timeout','transport_protocol','transport_network',"
        "'http_invalid_request','http_authentication','http_access_denied',"
        "'http_model_missing','http_rate_limited','http_server_error',"
        "'http_transient','http_rejected','sdk_unclassified',"
        "'output_empty','output_blocked','output_unfinished','json_invalid',"
        "'schema_invalid','citation_invalid','answer_too_long',"
        "'retrieval_failed','retrieval_timeout','local_support_unavailable',"
        "'local_support_timeout','rag_access_revoked','rag_corpus_changed',"
        "'internal_failure')) AND "
        "(provider_finish_reason IS NULL OR provider_finish_reason IN ("
        "'FINISH_REASON_UNSPECIFIED','STOP','MAX_TOKENS','SAFETY','RECITATION',"
        "'LANGUAGE','OTHER','BLOCKLIST','PROHIBITED_CONTENT','SPII',"
        "'MALFORMED_FUNCTION_CALL','IMAGE_SAFETY','UNEXPECTED_TOOL_CALL',"
        "'IMAGE_PROHIBITED_CONTENT','NO_IMAGE','IMAGE_RECITATION','IMAGE_OTHER'))",
    )
    op.create_check_constraint(
        "ck_rag_answer_stage_support_reason", "rag_answer_stage_attempts",
        "support_reason IS NULL OR support_reason IN ("
        "'supported','missing_evidence','entailment_rejected',"
        "'question_relevance_rejected','equivalence_rejected',"
        "'contradiction_detected','support_rejected')",
    )
    op.create_check_constraint(
        "ck_rag_answer_stage_support_checks", "rag_answer_stage_attempts",
        "(support_entailment IS NULL OR support_entailment IN ('pass','fail','not_run')) AND "
        "(support_question_relevance IS NULL OR support_question_relevance IN ('pass','fail','not_run')) AND "
        "(support_equivalence IS NULL OR support_equivalence IN ('pass','fail','not_run','not_required')) AND "
        "(support_contradiction IS NULL OR support_contradiction IN ('pass','fail','not_run'))",
    )
    op.create_check_constraint(
        "ck_rag_answer_stage_retrieval_ranks", "rag_answer_stage_attempts",
        "retrieval_ranks IS NULL OR (jsonb_typeof(retrieval_ranks) = 'array' "
        "AND jsonb_array_length(retrieval_ranks) <= 5)",
    )


def downgrade() -> None:
    # Do not discard diagnostics needed to interpret retained new-policy
    # abstentions or provider output failures on a populated installation.
    retained = op.get_bind().scalar(sa.text(
        "SELECT "
        "(SELECT count(*) FROM rag_messages WHERE abstention_kind IS NOT NULL) + "
        "(SELECT count(*) FROM rag_answer_jobs WHERE failure_reason IS NOT NULL) + "
        "(SELECT count(*) FROM rag_answer_stage_attempts WHERE "
        "failure_reason IS NOT NULL OR provider_finish_reason IS NOT NULL OR "
        "input_tokens IS NOT NULL OR output_tokens IS NOT NULL OR "
        "usage_estimated IS NOT NULL OR retrieval_ranks IS NOT NULL OR "
        "support_reason IS NOT NULL OR support_entailment IS NOT NULL OR "
        "support_question_relevance IS NOT NULL OR support_equivalence IS NOT NULL OR "
        "support_contradiction IS NOT NULL)"
    ))
    if retained:
        raise RuntimeError("Cannot downgrade while Lane 6 Ask diagnostics are retained")
    for name in (
        "ck_rag_answer_stage_retrieval_ranks",
        "ck_rag_answer_stage_support_checks",
        "ck_rag_answer_stage_support_reason",
        "ck_rag_answer_stage_quality_usage",
    ):
        op.drop_constraint(name, "rag_answer_stage_attempts", type_="check")
    for name in (
        "support_contradiction", "support_equivalence", "support_question_relevance",
        "support_entailment", "support_reason", "retrieval_ranks", "usage_estimated",
        "output_tokens", "input_tokens", "provider_finish_reason", "failure_reason",
    ):
        op.drop_column("rag_answer_stage_attempts", name)
    op.drop_constraint("ck_rag_answer_jobs_failure_reason", "rag_answer_jobs", type_="check")
    op.drop_column("rag_answer_jobs", "failure_reason")
    op.drop_constraint("ck_rag_messages_abstention_kind", "rag_messages", type_="check")
    op.drop_column("rag_messages", "abstention_kind")
