"""Bind source-only stage policy to its immutable parent job policy."""
from alembic import op
import sqlalchemy as sa

revision = "20260926_0023"
down_revision = "20260926_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Refuse inconsistent retained records rather than silently reclassifying
    # physical execution or altering its historical policy snapshot.
    incompatible = op.get_bind().scalar(sa.text("""
        SELECT count(*) FROM rag_answer_stage_attempts AS stage
        JOIN rag_answer_jobs AS job ON job.id = stage.job_id
        WHERE (job.answer_policy_version = 'related_knowledge_v1'
               AND stage.answer_policy_version IS DISTINCT FROM job.answer_policy_version)
           OR (stage.answer_policy_version = 'related_knowledge_v1'
               AND job.answer_policy_version IS DISTINCT FROM stage.answer_policy_version)
    """))
    if incompatible:
        raise RuntimeError("Source-only stage policy does not match its parent job")
    op.execute(sa.text("""
        CREATE FUNCTION enforce_rag_source_stage_parent_policy() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE parent_job record;
        BEGIN
            SELECT answer_policy_version, manual_retry_count, attempt_count INTO parent_job FROM rag_answer_jobs
                WHERE id = NEW.job_id FOR KEY SHARE;
            IF (parent_job.answer_policy_version = 'related_knowledge_v1'
                AND (NEW.answer_policy_version IS DISTINCT FROM parent_job.answer_policy_version
                     OR NEW.manual_retry_number IS DISTINCT FROM parent_job.manual_retry_count
                     OR NEW.worker_attempt_number IS DISTINCT FROM parent_job.attempt_count))
               OR (NEW.answer_policy_version = 'related_knowledge_v1'
                   AND parent_job.answer_policy_version IS DISTINCT FROM NEW.answer_policy_version)
            THEN
                RAISE EXCEPTION 'Source-only stage policy must match its parent job.'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$
    """))
    op.execute(sa.text("""
        CREATE TRIGGER guard_rag_source_stage_parent_policy
        BEFORE INSERT OR UPDATE ON rag_answer_stage_attempts
        FOR EACH ROW EXECUTE FUNCTION enforce_rag_source_stage_parent_policy();
    """))


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER guard_rag_source_stage_parent_policy ON rag_answer_stage_attempts"))
    op.execute(sa.text("DROP FUNCTION enforce_rag_source_stage_parent_policy()"))
