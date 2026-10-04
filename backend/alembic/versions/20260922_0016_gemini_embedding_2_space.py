"""Admit a distinct, versioned Gemini Embedding 2 text space.

Revision ID: 20260922_0016
Revises: 20260922_0015
Create Date: 2026-09-22
"""

from alembic import op
import sqlalchemy as sa


revision = "20260922_0016"
down_revision = "20260922_0015"
branch_labels = None
depends_on = None


_OLD_SPACE_CHECK = (
    "length(identity_hash) = 64 AND provider IN ('openai_compatible','gemini') AND "
    "length(trim(base_url)) BETWEEN 1 AND 512 AND length(trim(model)) BETWEEN 1 AND 128 AND "
    "length(trim(space_revision)) BETWEEN 1 AND 64 AND format_version = 'raw_text_v1' AND "
    "dimensions = 1536 AND representation = 'float32' AND metric = 'cosine' AND "
    "((provider = 'openai_compatible' AND document_task_mode = 'shared_input' "
    "AND query_task_mode = 'shared_input') OR "
    "(provider = 'gemini' AND document_task_mode = 'RETRIEVAL_DOCUMENT' "
    "AND query_task_mode = 'QUESTION_ANSWERING'))"
)

_NEW_SPACE_CHECK = (
    "length(identity_hash) = 64 AND provider IN ('openai_compatible','gemini') AND "
    "length(trim(base_url)) BETWEEN 1 AND 512 AND length(trim(model)) BETWEEN 1 AND 128 AND "
    "length(trim(space_revision)) BETWEEN 1 AND 64 AND "
    "dimensions = 1536 AND representation = 'float32' AND metric = 'cosine' AND "
    "((provider = 'openai_compatible' AND format_version = 'raw_text_v1' "
    "AND document_task_mode = 'shared_input' AND query_task_mode = 'shared_input') OR "
    "(provider = 'gemini' AND format_version = 'raw_text_v1' "
    "AND document_task_mode = 'RETRIEVAL_DOCUMENT' AND query_task_mode = 'QUESTION_ANSWERING') OR "
    "(provider = 'gemini' AND model = 'gemini-embedding-2' "
    "AND format_version = 'gemini2_qa_section_v1' "
    "AND document_task_mode = 'title_section_text_v1' "
    "AND query_task_mode = 'question_answering_query_v1'))"
)

_OLD_INDEX_CHECK = (
    "length(trim(chunker_version)) BETWEEN 1 AND 64 AND "
    "length(trim(embedding_provider)) BETWEEN 1 AND 32 AND "
    "length(trim(embedding_base_url)) BETWEEN 1 AND 512 AND "
    "length(trim(embedding_model)) BETWEEN 1 AND 128 AND "
    "length(trim(embedding_space_revision)) BETWEEN 1 AND 64 AND "
    "length(trim(embedding_format_version)) BETWEEN 1 AND 64 AND "
    "length(embedding_space_hash) = 64 AND "
    "((embedding_provider = 'openai_compatible' AND document_task_mode = 'shared_input' "
    "AND query_task_mode = 'shared_input') OR "
    "(embedding_provider = 'gemini' AND document_task_mode = 'RETRIEVAL_DOCUMENT' "
    "AND query_task_mode = 'QUESTION_ANSWERING'))"
)

_NEW_INDEX_CHECK = (
    "length(trim(chunker_version)) BETWEEN 1 AND 64 AND "
    "length(trim(embedding_provider)) BETWEEN 1 AND 32 AND "
    "length(trim(embedding_base_url)) BETWEEN 1 AND 512 AND "
    "length(trim(embedding_model)) BETWEEN 1 AND 128 AND "
    "length(trim(embedding_space_revision)) BETWEEN 1 AND 64 AND "
    "length(trim(embedding_format_version)) BETWEEN 1 AND 64 AND "
    "length(embedding_space_hash) = 64 AND "
    "((embedding_provider = 'openai_compatible' AND embedding_format_version = 'raw_text_v1' "
    "AND document_task_mode = 'shared_input' AND query_task_mode = 'shared_input') OR "
    "(embedding_provider = 'gemini' AND embedding_format_version = 'raw_text_v1' "
    "AND document_task_mode = 'RETRIEVAL_DOCUMENT' AND query_task_mode = 'QUESTION_ANSWERING') OR "
    "(embedding_provider = 'gemini' AND embedding_model = 'gemini-embedding-2' "
    "AND embedding_format_version = 'gemini2_qa_section_v1' "
    "AND document_task_mode = 'title_section_text_v1' "
    "AND query_task_mode = 'question_answering_query_v1'))"
)


def _replace_checks(space_check: str, index_check: str) -> None:
    op.drop_constraint("ck_knowledge_index_identity", "subject_document_index_revisions", type_="check")
    op.drop_constraint("ck_rag_embedding_spaces_identity", "rag_embedding_spaces", type_="check")
    op.create_check_constraint("ck_rag_embedding_spaces_identity", "rag_embedding_spaces", space_check)
    op.create_check_constraint("ck_knowledge_index_identity", "subject_document_index_revisions", index_check)


def upgrade() -> None:
    _replace_checks(_NEW_SPACE_CHECK, _NEW_INDEX_CHECK)


def downgrade() -> None:
    # Never erase staged vectors or relabel an Embedding 2 space to make the
    # older schema pass. An operator rollback keeps this additive migration.
    existing = op.get_bind().scalar(sa.text(
        "SELECT EXISTS (SELECT 1 FROM rag_embedding_spaces "
        "WHERE format_version = 'gemini2_qa_section_v1')"
    ))
    if existing:
        raise RuntimeError("Embedding 2 spaces must be retained; schema downgrade is blocked")
    _replace_checks(_OLD_SPACE_CHECK, _OLD_INDEX_CHECK)
