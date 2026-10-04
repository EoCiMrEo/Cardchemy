"""Fence new canonical-page references to the structural v7 source policy.

Revision ID: 20260927_0025
Revises: 20260927_0024
Create Date: 2026-09-27

Historical v6 references remain untouched and readable. Downgrade requires that
no v7 job snapshots remain, including terminal jobs without references: silently
reinterpreting or discarding their versioned policy is not a rollback strategy.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260927_0025"
down_revision = "20260927_0024"
branch_labels = None
depends_on = None


def _guard_sql(*, retrieval_policy: str) -> str:
    if retrieval_policy not in {"hybrid_source_sufficiency_v6", "hybrid_source_sufficiency_v7"}:
        raise ValueError("Unsupported canonical reference policy")
    # Keep the v6 guard self-contained in this revision. A contract test compares
    # it with immutable 0024 so only the accepted insertion policy can change.
    source_query = f"""
        IF NEW.source_kind NOT IN ('chunk','canonical_page') OR NEW.source_kind IS NULL THEN
            RAISE EXCEPTION 'Related evidence source kind is invalid.' USING ERRCODE = '23514';
        END IF;
        IF NEW.source_kind = 'canonical_page' AND
           (answer_job.retrieval_policy <> '{retrieval_policy}'
            OR answer_job.answer_policy_version IS DISTINCT FROM 'related_knowledge_v1') THEN
            RAISE EXCEPTION 'Canonical page reference policy is incompatible.' USING ERRCODE = '23514';
        END IF;
        SELECT CASE WHEN NEW.source_kind = 'canonical_page' THEN page.content ELSE eligible.content END
          INTO source_content
        FROM eligible_subject_knowledge_chunks AS eligible
        JOIN subject_document_pages AS page
          ON page.content_revision_id = eligible.content_revision_id
         AND page.document_id = eligible.document_id
         AND page.subject_id = eligible.subject_id
         AND page.uploader_id = eligible.uploader_id
         AND page.page_number = eligible.page_number
        JOIN subjects AS subject ON subject.id = eligible.subject_id
        JOIN users AS principal ON principal.id = answer_job.user_id
        WHERE eligible.id = NEW.chunk_id AND eligible.index_revision_id = NEW.index_revision_id
          AND eligible.content_revision_id = NEW.content_revision_id
          AND eligible.document_id = NEW.document_id AND eligible.subject_id = NEW.subject_id
          AND eligible.corpus_revision = answer_job.corpus_revision
          AND eligible.embedding_space_hash = answer_job.embedding_space_hash
          AND ((principal.role = 'INSTRUCTOR' AND subject.instructor_id = principal.id)
               OR (principal.role = 'STUDENT' AND EXISTS (
                   SELECT 1 FROM enrollments AS enrollment
                   WHERE enrollment.student_id = principal.id AND enrollment.subject_id = subject.id)));
        IF NOT FOUND OR NEW.start_offset < 0 OR NEW.end_offset <= NEW.start_offset
           OR NEW.end_offset - NEW.start_offset > 480
           OR NEW.end_offset > char_length(source_content)
           OR btrim(substring(source_content FROM NEW.start_offset + 1 FOR NEW.end_offset - NEW.start_offset), E' \\t\\n\\r') = '' THEN
            RAISE EXCEPTION 'Related evidence source is not current.' USING ERRCODE = '23514';
        END IF;
    """
    return f"""
    CREATE OR REPLACE FUNCTION rag_related_evidence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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
        {source_query}
        RETURN NEW;
    END $$
    """


def upgrade() -> None:
    op.execute(sa.text(_guard_sql(retrieval_policy="hybrid_source_sufficiency_v7")))


def downgrade() -> None:
    retained = op.get_bind().scalar(sa.text(
        "SELECT count(*) FROM rag_answer_jobs "
        "WHERE retrieval_policy = 'hybrid_source_sufficiency_v7'"
    ))
    if retained:
        raise RuntimeError("Cannot downgrade while structural v7 job snapshots exist")
    op.execute(sa.text(_guard_sql(retrieval_policy="hybrid_source_sufficiency_v6")))
