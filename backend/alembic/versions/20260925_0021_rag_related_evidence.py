"""Stage bounded, source-exact related Knowledge for private Ask jobs.

Revision ID: 20260925_0021
Revises: 20260925_0020
Create Date: 2026-09-25

The new table does not change the active Ask answer policy. Its excerpts are
not verified answers and require a separate authorized read contract.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20260925_0021"
down_revision = "20260925_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_rag_answer_jobs_scope", "rag_answer_jobs",
        ["id", "thread_id", "user_id", "subject_id"],
    )
    op.create_table(
        "rag_related_evidence",
        sa.Column("job_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("excerpt_order", sa.Integer(), primary_key=True),
        sa.Column("bundle_size", sa.Integer(), nullable=False),
        sa.Column("thread_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("content_revision_id", UUID(as_uuid=True), nullable=False),
        sa.Column("index_revision_id", UUID(as_uuid=True), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("manual_retry_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id", "thread_id", "user_id", "subject_id"],
            ["rag_answer_jobs.id", "rag_answer_jobs.thread_id", "rag_answer_jobs.user_id", "rag_answer_jobs.subject_id"],
            ondelete="CASCADE", name="fk_rag_related_evidence_job_scope",
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id", "index_revision_id", "content_revision_id", "document_id", "subject_id"],
            ["subject_document_chunks.id", "subject_document_chunks.index_revision_id",
             "subject_document_chunks.content_revision_id", "subject_document_chunks.document_id",
             "subject_document_chunks.subject_id"],
            ondelete="CASCADE", name="fk_rag_related_evidence_chunk_scope",
        ),
        sa.UniqueConstraint("job_id", "chunk_id", name="uq_rag_related_evidence_chunk"),
        sa.CheckConstraint("excerpt_order BETWEEN 1 AND 2", name="ck_rag_related_evidence_order"),
        sa.CheckConstraint("bundle_size BETWEEN 1 AND 2 AND excerpt_order <= bundle_size", name="ck_rag_related_evidence_bundle"),
        sa.CheckConstraint(
            "start_offset >= 0 AND end_offset > start_offset AND end_offset - start_offset <= 480",
            name="ck_rag_related_evidence_offsets",
        ),
        sa.CheckConstraint("manual_retry_number BETWEEN 0 AND 10", name="ck_rag_related_evidence_retry"),
        sa.CheckConstraint("expires_at > created_at", name="ck_rag_related_evidence_expiry"),
    )
    op.create_index(
        "ix_rag_related_evidence_owner_expiry", "rag_related_evidence",
        ["user_id", "expires_at", "job_id"],
    )
    op.execute(sa.text("""
    CREATE FUNCTION rag_related_evidence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE answer_job rag_answer_jobs%ROWTYPE;
            source_content text;
            question_expiry timestamptz;
    BEGIN
        IF TG_OP <> 'INSERT' THEN
            RAISE EXCEPTION 'Related evidence is immutable.' USING ERRCODE = '23514';
        END IF;
        SELECT * INTO answer_job FROM rag_answer_jobs WHERE id = NEW.job_id;
        IF NOT FOUND OR answer_job.status <> 'running'
           OR answer_job.manual_retry_count <> NEW.manual_retry_number
           OR answer_job.retrieval_completed_at IS NULL
           OR answer_job.lease_expires_at IS NULL
           OR answer_job.lease_expires_at <= now() THEN
            RAISE EXCEPTION 'Related evidence job is not current.' USING ERRCODE = '23514';
        END IF;
        IF EXISTS (SELECT 1 FROM rag_related_evidence AS existing
                   WHERE existing.job_id = NEW.job_id
                     AND (existing.bundle_size <> NEW.bundle_size
                          OR existing.manual_retry_number <> NEW.manual_retry_number)) THEN
            RAISE EXCEPTION 'Related evidence bundle is inconsistent.' USING ERRCODE = '23514';
        END IF;
        IF answer_job.document_ids <> '[]'::jsonb
           AND NOT (answer_job.document_ids ? NEW.document_id::text) THEN
            RAISE EXCEPTION 'Related evidence document is outside the selected scope.' USING ERRCODE = '23514';
        END IF;
        SELECT expires_at INTO question_expiry FROM rag_messages
        WHERE id = answer_job.question_message_id;
        IF NOT FOUND OR question_expiry <= now() OR NEW.expires_at > question_expiry THEN
            RAISE EXCEPTION 'Related evidence has expired.' USING ERRCODE = '23514';
        END IF;
        SELECT content INTO source_content FROM eligible_subject_knowledge_chunks
        WHERE id = NEW.chunk_id AND index_revision_id = NEW.index_revision_id
          AND content_revision_id = NEW.content_revision_id
          AND document_id = NEW.document_id AND subject_id = NEW.subject_id
          AND corpus_revision = answer_job.corpus_revision
          AND embedding_space_hash = answer_job.embedding_space_hash;
        IF NOT FOUND OR NEW.end_offset > char_length(source_content) THEN
            RAISE EXCEPTION 'Related evidence source is not current.' USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END $$
    """))
    op.execute(sa.text(
        "CREATE TRIGGER rag_related_evidence_guard "
        "BEFORE INSERT OR UPDATE ON rag_related_evidence "
        "FOR EACH ROW EXECUTE FUNCTION rag_related_evidence_guard()"
    ))


def downgrade() -> None:
    retained = op.get_bind().scalar(sa.text("SELECT count(*) FROM rag_related_evidence"))
    if retained:
        raise RuntimeError("Cannot downgrade while related evidence records exist")
    op.execute(sa.text("DROP TRIGGER rag_related_evidence_guard ON rag_related_evidence"))
    op.execute(sa.text("DROP FUNCTION rag_related_evidence_guard()"))
    op.drop_index("ix_rag_related_evidence_owner_expiry", table_name="rag_related_evidence")
    op.drop_table("rag_related_evidence")
    op.drop_constraint("uq_rag_answer_jobs_scope", "rag_answer_jobs", type_="unique")
