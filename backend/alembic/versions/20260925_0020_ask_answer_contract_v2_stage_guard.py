"""Extend the two-request Ask stage guard to a future v2 answer contract.

Revision ID: 20260925_0020
Revises: 20260925_0019
Create Date: 2026-09-25

The migration does not activate a new Ask policy. Existing v1 jobs and the
deployed worker keep their original behavior until the v2 release gate passes.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260925_0020"
down_revision = "20260925_0019"
branch_labels = None
depends_on = None


_V1_CAP = (
    "answer_policy_version IS NULL OR answer_policy_version <> 'two_request_local_support_v1' "
    "OR (stage IN ('query_embedding','retrieval','answer','local_support') "
    "AND retry_count = 0 AND ((stage IN ('query_embedding','answer') "
    "AND physical_request_count <= 1) OR (stage IN ('retrieval','local_support') "
    "AND physical_request_count = 0)))"
)
_V2_CAP = (
    "answer_policy_version IS NULL OR answer_policy_version NOT IN "
    "('two_request_local_support_v1','two_request_local_support_v2') "
    "OR (stage IN ('query_embedding','retrieval','answer','local_support') "
    "AND retry_count = 0 AND ((stage IN ('query_embedding','answer') "
    "AND physical_request_count <= 1) OR (stage IN ('retrieval','local_support') "
    "AND physical_request_count = 0)))"
)
_V1_INDEX = (
    "answer_policy_version = 'two_request_local_support_v1' "
    "AND stage IN ('query_embedding','answer')"
)
_V2_INDEX = (
    "answer_policy_version IN "
    "('two_request_local_support_v1','two_request_local_support_v2') "
    "AND stage IN ('query_embedding','answer')"
)


def upgrade() -> None:
    op.drop_index("uq_rag_answer_stage_local_remote_attempt", table_name="rag_answer_stage_attempts")
    op.drop_constraint("ck_rag_answer_stage_two_request_cap", "rag_answer_stage_attempts", type_="check")
    op.create_check_constraint(
        "ck_rag_answer_stage_two_request_cap", "rag_answer_stage_attempts", _V2_CAP,
    )
    op.create_index(
        "uq_rag_answer_stage_local_remote_attempt", "rag_answer_stage_attempts",
        ["job_id", "manual_retry_number", "stage"], unique=True,
        postgresql_where=sa.text(_V2_INDEX),
    )


def downgrade() -> None:
    active = op.get_bind().scalar(sa.text(
        "SELECT (SELECT count(*) FROM rag_answer_jobs "
        "WHERE answer_policy_version = 'two_request_local_support_v2') + "
        "(SELECT count(*) FROM rag_answer_stage_attempts "
        "WHERE answer_policy_version = 'two_request_local_support_v2')"
    ))
    if active:
        raise RuntimeError("Cannot downgrade while Ask answer-contract v2 records exist")
    op.drop_index("uq_rag_answer_stage_local_remote_attempt", table_name="rag_answer_stage_attempts")
    op.drop_constraint("ck_rag_answer_stage_two_request_cap", "rag_answer_stage_attempts", type_="check")
    op.create_check_constraint(
        "ck_rag_answer_stage_two_request_cap", "rag_answer_stage_attempts", _V1_CAP,
    )
    op.create_index(
        "uq_rag_answer_stage_local_remote_attempt", "rag_answer_stage_attempts",
        ["job_id", "manual_retry_number", "stage"], unique=True,
        postgresql_where=sa.text(_V1_INDEX),
    )
