"""Add content-free operational metrics, worker heartbeats and privileged audit.

Revision ID: 20260917_0008
Revises: 20260916_0007
Create Date: 2026-09-17
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260917_0008"
down_revision: str | None = "20260916_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("generation_jobs", sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index(
        "ix_generation_jobs_retention", "generation_jobs", ["completed_at", "id"],
        postgresql_where=sa.text("status IN ('completed', 'failed', 'cancelled')"),
    )
    op.create_index("ix_invite_links_retention", "invite_links", ["expires_at", "id"])
    op.create_index("ix_rate_limit_buckets_retention", "rate_limit_buckets", ["updated_at", "id"])
    op.create_table(
        "request_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("route", sa.String(160), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("latency_milliseconds", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status_code BETWEEN 100 AND 599", name="ck_request_events_status"),
        sa.CheckConstraint("latency_milliseconds >= 0", name="ck_request_events_latency"),
    )
    op.create_index("ix_request_events_created", "request_events", ["created_at", "id"])
    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_id", sa.String(128), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.CheckConstraint("kind IN ('generation', 'email')", name="ck_worker_heartbeats_kind"),
        sa.CheckConstraint("status IN ('running', 'disabled', 'draining')", name="ck_worker_heartbeats_status"),
    )
    op.create_index("ix_worker_heartbeats_kind_seen", "worker_heartbeats", ["kind", "last_seen_at"])
    op.create_index("ix_worker_heartbeats_retention", "worker_heartbeats", ["last_seen_at", "worker_id"])
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("action", sa.String(48), nullable=False),
        sa.Column("actor_kind", sa.String(24), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_type", sa.String(16), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("state_before", sa.Boolean(), nullable=True),
        sa.Column("state_after", sa.Boolean(), nullable=True),
        sa.Column("affected_count", sa.Integer(), nullable=True),
        sa.Column("role_before", sa.String(16), nullable=True),
        sa.Column("role_after", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "action IN ('invitation.created', 'card.approved', 'card.unapproved', "
            "'cards.approved', 'set.published', 'set.unpublished', "
            "'account.instructor_provisioned', 'account.role_changed', 'account.deleted')",
            name="ck_audit_events_action",
        ),
        sa.CheckConstraint("actor_kind IN ('user', 'operator', 'operator_database')", name="ck_audit_events_actor_kind"),
        sa.CheckConstraint("target_type IN ('invitation', 'card', 'set', 'account')", name="ck_audit_events_target_type"),
        sa.CheckConstraint("affected_count IS NULL OR affected_count >= 0", name="ck_audit_events_affected_count"),
        sa.CheckConstraint("role_before IS NULL OR role_before IN ('student', 'instructor')", name="ck_audit_events_role_before"),
        sa.CheckConstraint("role_after IS NULL OR role_after IN ('student', 'instructor')", name="ck_audit_events_role_after"),
    )
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])
    op.create_index("ix_audit_events_actor_created", "audit_events", ["actor_id", "created_at"])
    op.create_index("ix_audit_events_target", "audit_events", ["target_type", "target_id"])
    # Account role management is operator-owned. The trigger also covers a
    # direct SQL UPDATE; its audit insert shares the role mutation transaction.
    op.execute("""
        CREATE FUNCTION audit_account_role_change() RETURNS trigger AS $$
        BEGIN
            IF NEW.role IS DISTINCT FROM OLD.role THEN
                INSERT INTO audit_events
                    (action, actor_kind, target_type, target_id, role_before, role_after)
                VALUES
                    ('account.role_changed', 'operator_database', 'account', NEW.id,
                     lower(OLD.role::text), lower(NEW.role::text));
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER users_audit_role_change AFTER UPDATE OF role ON users
        FOR EACH ROW EXECUTE FUNCTION audit_account_role_change()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER users_audit_role_change ON users")
    op.execute("DROP FUNCTION audit_account_role_change()")
    op.drop_table("audit_events")
    op.drop_table("worker_heartbeats")
    op.drop_table("request_events")
    op.drop_index("ix_rate_limit_buckets_retention", table_name="rate_limit_buckets")
    op.drop_index("ix_invite_links_retention", table_name="invite_links")
    op.drop_index("ix_generation_jobs_retention", table_name="generation_jobs")
    op.drop_column("generation_jobs", "request_id")
