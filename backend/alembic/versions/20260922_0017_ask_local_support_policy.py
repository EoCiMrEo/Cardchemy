"""Snapshot the two-request Ask policy and attempt cost provenance.

Revision ID: 20260922_0017
Revises: 20260922_0016
Create Date: 2026-09-22
"""

from alembic import op
import sqlalchemy as sa


revision = "20260922_0017"
down_revision = "20260922_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rag_answer_jobs", sa.Column("answer_policy_version", sa.String(64), nullable=True))
    op.add_column("rag_answer_jobs", sa.Column("support_policy_version", sa.String(64), nullable=True))
    op.add_column(
        "rag_answer_jobs",
        sa.Column("attempt_cost_microusd", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "rag_answer_jobs",
        sa.Column("attempt_cost_unknown", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_check_constraint(
        "ck_rag_answer_jobs_local_policy", "rag_answer_jobs",
        "(answer_policy_version IS NULL OR length(trim(answer_policy_version)) BETWEEN 1 AND 64) "
        "AND (support_policy_version IS NULL OR length(trim(support_policy_version)) BETWEEN 1 AND 64) "
        "AND attempt_cost_microusd >= 0",
    )
    op.add_column("rag_answer_stage_attempts", sa.Column("answer_policy_version", sa.String(64), nullable=True))
    op.drop_constraint("ck_rag_answer_stage_name", "rag_answer_stage_attempts", type_="check")
    op.create_check_constraint(
        "ck_rag_answer_stage_name", "rag_answer_stage_attempts",
        "stage IN ('query_embedding','retrieval','answer','support','local_support')",
    )
    op.create_check_constraint(
        "ck_rag_answer_stage_two_request_cap", "rag_answer_stage_attempts",
        "answer_policy_version IS NULL OR answer_policy_version <> 'two_request_local_support_v1' "
        "OR (stage IN ('query_embedding','retrieval','answer','local_support') "
        "AND retry_count = 0 AND ((stage IN ('query_embedding','answer') "
        "AND physical_request_count <= 1) OR (stage IN ('retrieval','local_support') "
        "AND physical_request_count = 0)))",
    )
    op.create_index(
        "uq_rag_answer_stage_local_remote_attempt", "rag_answer_stage_attempts",
        ["job_id", "manual_retry_number", "stage"], unique=True,
        postgresql_where=sa.text(
            "answer_policy_version = 'two_request_local_support_v1' "
            "AND stage IN ('query_embedding','answer')"
        ),
    )


def downgrade() -> None:
    # The older worker must never reinterpret a retained new-policy job as its
    # historical remote-support job. Require operator-led restore instead.
    active = op.get_bind().scalar(sa.text(
        "SELECT "
        "(SELECT count(*) FROM rag_answer_jobs "
        " WHERE answer_policy_version = 'two_request_local_support_v1' "
        " OR support_policy_version = 'local_nli_qa_v1') + "
        "(SELECT count(*) FROM rag_answer_stage_attempts "
        " WHERE answer_policy_version = 'two_request_local_support_v1' "
        " OR stage = 'local_support')"
    ))
    if active:
        raise RuntimeError("Cannot downgrade while two-request Ask jobs exist")
    op.drop_index("uq_rag_answer_stage_local_remote_attempt", table_name="rag_answer_stage_attempts")
    op.drop_constraint("ck_rag_answer_stage_two_request_cap", "rag_answer_stage_attempts", type_="check")
    op.drop_constraint("ck_rag_answer_stage_name", "rag_answer_stage_attempts", type_="check")
    op.create_check_constraint(
        "ck_rag_answer_stage_name", "rag_answer_stage_attempts",
        "stage IN ('query_embedding','retrieval','answer','support')",
    )
    op.drop_column("rag_answer_stage_attempts", "answer_policy_version")
    op.drop_constraint("ck_rag_answer_jobs_local_policy", "rag_answer_jobs", type_="check")
    op.drop_column("rag_answer_jobs", "attempt_cost_unknown")
    op.drop_column("rag_answer_jobs", "attempt_cost_microusd")
    op.drop_column("rag_answer_jobs", "support_policy_version")
    op.drop_column("rag_answer_jobs", "answer_policy_version")
