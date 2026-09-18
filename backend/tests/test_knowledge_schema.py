"""Portable fixtures and declaration contracts; PostgreSQL proves admission."""

from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlalchemy.dialects import postgresql, sqlite

from app.models import Subject, User
from app.models.user import UserRole
from app.models.knowledge import (
    SubjectDocument, SubjectDocumentContentRevision, SubjectDocumentIndexRevision,
    RagEmbeddingSpace, embedding_space_hash,
)


IDENTITY = ('openai_compatible', 'https://api.openai.com/v1', 'text-embedding-3-small',
            'v1', 'raw_text_v1', 1536, 'float32', 'cosine')


def test_full_embedding_identity_has_unambiguous_framing():
    baseline = embedding_space_hash(IDENTITY)
    assert len(baseline) == 64
    for position in range(len(IDENTITY)):
        changed = list(IDENTITY)
        changed[position] = 768 if position == 5 else str(changed[position]) + '-different'
        assert embedding_space_hash(tuple(changed)) != baseline
    assert embedding_space_hash(('ab', 'c', *IDENTITY[2:])) != embedding_space_hash(('a', 'bc', *IDENTITY[2:]))


def test_portable_partial_revision_indexes_and_postgres_vector_contract():
    for model in (SubjectDocumentContentRevision, SubjectDocumentIndexRevision):
        index = next(index for index in model.__table__.indexes if index.name.endswith('_active'))
        assert 'WHERE is_active' in str(CreateIndex(index).compile(dialect=sqlite.dialect()))
        assert 'WHERE is_active' in str(CreateIndex(index).compile(dialect=postgresql.dialect()))
    from app.models.knowledge import SubjectDocumentChunk
    ddl = str(CreateTable(SubjectDocumentChunk.__table__).compile(dialect=postgresql.dialect()))
    assert 'VECTOR(1536)' in ddl
    assert 'fk_knowledge_chunks_page' in ddl and 'fk_knowledge_chunks_space' in ddl


async def test_sqlite_fixture_can_retain_multiple_private_content_and_index_revisions(db):
    owner = User(email=f'knowledge-{uuid4().hex}@example.test', hashed_password='fixture', role=UserRole.INSTRUCTOR)
    subject = Subject(name='Fixture Knowledge', instructor=owner)
    db.add_all([owner, subject])
    await db.flush()
    document = SubjectDocument(subject_id=subject.id, uploader_id=owner.id, title='Fixture',
                               source_pdf_name='fixture.pdf', source_sha256='a' * 64)
    space = RagEmbeddingSpace(identity_hash=embedding_space_hash(IDENTITY), **dict(zip(
        ('provider','base_url','model','space_revision','format_version','dimensions','representation','metric'), IDENTITY)))
    db.add_all([document, space])
    await db.flush()
    revisions = [SubjectDocumentContentRevision(document_id=document.id, subject_id=subject.id, uploader_id=owner.id,
        revision_no=number, source_sha256='a'*64, extraction_version='canonical_v1',
        reserved_page_count=0, reserved_page_chars=0, reserved_page_bytes=0) for number in (1,2)]
    db.add_all(revisions)
    await db.flush()
    for number in (1,2):
        db.add(SubjectDocumentIndexRevision(content_revision_id=revisions[0].id, document_id=document.id,
            subject_id=subject.id, uploader_id=owner.id, revision_no=number, chunker_version='bounded_v1',
            **dict(zip(('embedding_provider','embedding_base_url','embedding_model','embedding_space_revision',
                'embedding_format_version','embedding_dimensions','embedding_representation','embedding_metric'), IDENTITY)),
            embedding_space_hash=space.identity_hash, reserved_chunk_count=0, reserved_index_bytes=0))
    await db.flush()
    assert len((await db.scalars(select(SubjectDocumentContentRevision))).all()) == 2
    assert len((await db.scalars(select(SubjectDocumentIndexRevision))).all()) == 2
