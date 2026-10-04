"""Retain revision-bound independently encrypted original PDF blocks.

Revision ID: 20260927_0026
Revises: 20260927_0025
Create Date: 2026-09-27

Historical revisions are not given invented originals. No provider work occurs.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260927_0026"
down_revision = "20260927_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subject_document_pdfs",
        sa.Column("content_revision_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploader_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("block_count", sa.Integer(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["content_revision_id", "document_id", "subject_id", "uploader_id"],
            ["subject_document_content_revisions.id", "subject_document_content_revisions.document_id",
             "subject_document_content_revisions.subject_id", "subject_document_content_revisions.uploader_id"],
            ondelete="CASCADE", name="fk_knowledge_pdf_revision",
        ),
        sa.CheckConstraint("length(source_sha256) = 64", name="ck_knowledge_pdf_hash"),
        sa.CheckConstraint("source_sha256 ~ '^[0-9a-f]{64}$'", name="ck_knowledge_pdf_hash_format"),
        sa.CheckConstraint("byte_size BETWEEN 1 AND 104857600 AND page_count BETWEEN 1 AND 100 "
                           "AND block_count = ((byte_size + 1048575) / 1048576) AND key_version = 1",
                           name="ck_knowledge_pdf_bounds"),
    )
    op.create_index("ix_knowledge_pdf_subject", "subject_document_pdfs", ["subject_id", "content_revision_id"])
    op.create_index("ix_knowledge_pdf_uploader", "subject_document_pdfs", ["uploader_id", "content_revision_id"])
    op.create_table(
        "subject_document_pdf_blocks",
        sa.Column("content_revision_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("block_number", sa.Integer(), primary_key=True),
        sa.Column("plaintext_size", sa.Integer(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(["content_revision_id"], ["subject_document_pdfs.content_revision_id"],
                                ondelete="CASCADE", name="fk_knowledge_pdf_block_archive"),
        sa.CheckConstraint("block_number BETWEEN 0 AND 99 AND plaintext_size BETWEEN 1 AND 1048576 "
                           "AND length(nonce) = 12 AND length(payload) = plaintext_size + 16",
                           name="ck_knowledge_pdf_block_bounds"),
    )
    op.execute(sa.text("""
        CREATE FUNCTION knowledge_pdf_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE target subject_document_content_revisions%ROWTYPE;
        BEGIN
            PERFORM pg_advisory_xact_lock(13013, 0);
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'Knowledge original PDF is immutable.' USING ERRCODE='23514';
            END IF;
            SELECT * INTO target FROM subject_document_content_revisions WHERE id=NEW.content_revision_id;
            IF NOT FOUND OR target.source_sha256 <> NEW.source_sha256
               OR target.reserved_page_count <> NEW.page_count THEN
                RAISE EXCEPTION 'Knowledge original PDF revision does not match.' USING ERRCODE='23514';
            END IF;
            IF coalesce((SELECT sum(byte_size) FROM subject_document_pdfs),0)+NEW.byte_size > 2147483648
               OR coalesce((SELECT sum(byte_size) FROM subject_document_pdfs WHERE subject_id=NEW.subject_id),0)+NEW.byte_size > 268435456
               OR coalesce((SELECT sum(byte_size) FROM subject_document_pdfs WHERE uploader_id=NEW.uploader_id),0)+NEW.byte_size > 536870912 THEN
                RAISE EXCEPTION 'Knowledge original PDF storage capacity exceeded.' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$
    """))
    op.execute(sa.text("""
        CREATE FUNCTION knowledge_pdf_block_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE archive subject_document_pdfs%ROWTYPE;
        BEGIN
            PERFORM pg_advisory_xact_lock(13013, 0);
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'Knowledge original PDF block is immutable.' USING ERRCODE='23514';
            END IF;
            SELECT * INTO archive FROM subject_document_pdfs WHERE content_revision_id=NEW.content_revision_id;
            IF NOT FOUND OR NEW.block_number >= archive.block_count
               OR NEW.plaintext_size <> least(1048576,archive.byte_size-NEW.block_number*1048576) THEN
                RAISE EXCEPTION 'Knowledge original PDF block does not match.' USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END $$
    """))
    op.execute(sa.text("""
        CREATE FUNCTION knowledge_pdf_complete_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE revision_id uuid; archive subject_document_pdfs%ROWTYPE;
        BEGIN
            revision_id := CASE WHEN TG_OP='DELETE' THEN OLD.content_revision_id ELSE NEW.content_revision_id END;
            SELECT * INTO archive FROM subject_document_pdfs WHERE content_revision_id=revision_id;
            IF NOT FOUND THEN RETURN NULL; END IF;
            IF (SELECT count(*) FROM subject_document_pdf_blocks WHERE content_revision_id=revision_id) <> archive.block_count
               OR (SELECT coalesce(sum(plaintext_size),0) FROM subject_document_pdf_blocks WHERE content_revision_id=revision_id) <> archive.byte_size THEN
                RAISE EXCEPTION 'Knowledge original PDF archive is incomplete.' USING ERRCODE='23514';
            END IF;
            RETURN NULL;
        END $$
    """))
    for table, function in (("subject_document_pdfs", "knowledge_pdf_guard"),
                            ("subject_document_pdf_blocks", "knowledge_pdf_block_guard")):
        op.execute(sa.text(f"CREATE TRIGGER knowledge_00_write_lock BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION knowledge_write_lock()"))
        op.execute(sa.text(f"CREATE TRIGGER knowledge_pdf_row_guard BEFORE INSERT OR UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION {function}()"))
        op.execute(sa.text(f"CREATE CONSTRAINT TRIGGER knowledge_pdf_complete AFTER INSERT OR UPDATE OR DELETE ON {table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION knowledge_pdf_complete_guard()"))


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM subject_document_pdfs")):
        raise RuntimeError("Original PDF archive downgrade requires an empty archive; preserve the backup.")
    op.drop_table("subject_document_pdf_blocks")
    op.drop_table("subject_document_pdfs")
    for name in ("knowledge_pdf_complete_guard", "knowledge_pdf_block_guard", "knowledge_pdf_guard"):
        op.execute(sa.text(f"DROP FUNCTION {name}()"))
