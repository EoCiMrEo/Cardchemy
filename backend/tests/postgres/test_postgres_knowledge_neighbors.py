"""Disposable PostgreSQL checks for authorized, bounded source neighbors."""

from dataclasses import replace
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from app.models.knowledge import (
    SubjectDocumentChunk, SubjectDocumentContentRevision, SubjectDocumentPage,
)
from app.models.user import User
from app.services.knowledge_indexing import cutover_subject_embedding_space
from app.services.knowledge_retrieval import (
    KnowledgeRetriever,
    KnowledgeSourceUnavailable,
    RetrievedKnowledgeChunk,
    SOURCE_SUFFICIENCY_RETRIEVAL_POLICY,
)
from app.time_utils import utcnow
from app.workers.knowledge_index import KnowledgeIndexWorker
from tests.postgres.test_postgres_rag_pipeline import (
    FakeEmbeddingProvider,
    seed_capture,
    settings,
)


pytestmark = pytest.mark.postgres


@pytest_asyncio.fixture
async def neighbor_owner_cleanup(postgres_session_factory):
    owner_ids = []
    yield owner_ids
    if owner_ids:
        async with postgres_session_factory() as db:
            async with db.begin():
                await db.execute(
                    text("DELETE FROM users WHERE id=ANY(CAST(:owners AS uuid[]))"),
                    {"owners": owner_ids},
                )


async def _ready_pages(engine, session_factory, owner_ids):
    configured = settings(str(engine.url))
    owner, subject, captured, _prepared = await seed_capture(
        session_factory,
        configured,
        page_texts=(
            "First section explains the opening concept and several details about it.\n\n"
            "Another paragraph on the opening page supplies distinct nearby context.",
            "Second page continues the explanation with one separate example.",
            "Third page discusses a later consequence of the same topic.",
            "Fourth page is outside the two page expansion radius.",
        ),
    )
    owner_ids.append(owner.id)
    indexer = KnowledgeIndexWorker(
        settings=configured, session_factory=session_factory,
        provider=FakeEmbeddingProvider(), worker_id=f"neighbor-index-{uuid4().hex}",
    )
    claim = await indexer.claim_next()
    assert claim and claim[0] == captured.index_job_id
    await indexer.process_claim(*claim)
    async with session_factory() as db:
        async with db.begin():
            content = await db.get(
                SubjectDocumentContentRevision, captured.content_revision_id,
                with_for_update=True,
            )
            content.reviewed_by_id = owner.id
            content.reviewed_at = utcnow()
            content.published_at = utcnow()
    async with session_factory() as db:
        async with db.begin():
            assert await cutover_subject_embedding_space(
                db, subject_id=subject.id, owner_id=owner.id,
                target_space_hash=indexer.space_hash,
            ) == 1
    return owner.id, subject.id, captured, indexer.space_hash


def _anchor(row: SubjectDocumentChunk, space_hash: str, corpus_revision: int):
    return RetrievedKnowledgeChunk(
        chunk_id=row.id, document_id=row.document_id, document_title="Synthetic lecture",
        content_revision_id=row.content_revision_id,
        index_revision_id=row.index_revision_id, page_number=row.page_number,
        section=row.section, content=row.content, token_count=row.token_count,
        embedding_space_hash=space_hash, corpus_revision=corpus_revision,
        vector_similarity=0.9, lexical_score=0.5, vector_rank=1,
        lexical_rank=1, fusion_score=0.03,
    )


async def test_neighbors_are_current_exact_chunks_and_honor_radius_and_budgets(
    postgres_engine, postgres_session_factory, neighbor_owner_cleanup,
):
    owner_id, subject_id, captured, space_hash = await _ready_pages(
        postgres_engine, postgres_session_factory, neighbor_owner_cleanup,
    )
    async with postgres_session_factory() as db:
        owner = await db.get(User, owner_id)
        retriever = await KnowledgeRetriever.authorize(
            db, principal=owner, subject_id=subject_id,
            query="opening concept", document_ids=[captured.document_id],
            policy=SOURCE_SUFFICIENCY_RETRIEVAL_POLICY,
        )
        chunks = list((await db.scalars(select(SubjectDocumentChunk).where(
            SubjectDocumentChunk.index_revision_id == captured.index_revision_id,
        ).order_by(SubjectDocumentChunk.page_number, SubjectDocumentChunk.chunk_index))).all())
        first = next(chunk for chunk in chunks if chunk.page_number == 1)
        anchor = _anchor(first, space_hash, retriever.scope.corpus_revision)
        assert len([chunk for chunk in chunks if chunk.page_number == 1]) >= 2

        near = await retriever.expand_source_neighbors((anchor,), radius=1)
        assert near
        assert {item.chunk.chunk_id for item in near}.isdisjoint({anchor.chunk_id})
        assert len({item.chunk.chunk_id for item in near}) == len(near)
        assert {item.chunk.page_number for item in near} == {1, 2}
        assert [item.page_distance for item in near] == sorted(item.page_distance for item in near)
        assert all(item.anchor_chunk_id == anchor.chunk_id for item in near)
        assert all(item.chunk.document_id == captured.document_id for item in near)
        assert all(item.chunk.content_revision_id == captured.content_revision_id for item in near)
        assert all(item.chunk.index_revision_id == captured.index_revision_id for item in near)
        assert all(item.chunk.embedding_space_hash == space_hash for item in near)
        assert all(item.chunk.vector_rank is None and item.chunk.lexical_rank is None
                   and item.chunk.vector_similarity is None and item.chunk.fusion_score == 0
                   for item in near)
        assert {item.chunk.chunk_id: item.chunk.content for item in near} == {
            chunk.id: chunk.content for chunk in chunks if chunk.id in {
                item.chunk.chunk_id for item in near
            }
        }

        wider = await retriever.expand_source_neighbors((anchor,), radius=2)
        assert 3 in {item.chunk.page_number for item in wider}
        assert 4 not in {item.chunk.page_number for item in wider}
        same_page = await retriever.expand_source_neighbors((anchor,), radius=2, max_pages=1)
        assert same_page and {item.chunk.page_number for item in same_page} == {1}
        one_extra = await retriever.expand_source_neighbors((anchor,), radius=2, max_chunks=2)
        assert len(one_extra) == 1
        no_budget = await retriever.expand_source_neighbors(
            (anchor,), max_tokens=anchor.token_count,
        )
        assert no_budget == ()


async def test_neighbor_expansion_rejects_foreign_and_withdrawn_anchors(
    postgres_engine, postgres_session_factory, neighbor_owner_cleanup,
):
    owner_id, subject_id, captured, space_hash = await _ready_pages(
        postgres_engine, postgres_session_factory, neighbor_owner_cleanup,
    )
    async with postgres_session_factory() as db:
        owner = await db.get(User, owner_id)
        retriever = await KnowledgeRetriever.authorize(
            db, principal=owner, subject_id=subject_id, query="opening concept",
            document_ids=[captured.document_id],
            policy=SOURCE_SUFFICIENCY_RETRIEVAL_POLICY,
        )
        row = await db.scalar(select(SubjectDocumentChunk).where(
            SubjectDocumentChunk.index_revision_id == captured.index_revision_id,
        ).order_by(SubjectDocumentChunk.chunk_index))
        anchor = _anchor(row, space_hash, retriever.scope.corpus_revision)
        foreign = replace(anchor, document_id=uuid4())
        with pytest.raises(KnowledgeSourceUnavailable):
            await retriever.expand_source_neighbors((foreign,))
        with pytest.raises(KnowledgeSourceUnavailable):
            await retriever.expand_source_neighbors(
                (replace(anchor, token_count=anchor.token_count + 1),),
            )
        async with postgres_session_factory() as writer:
            async with writer.begin():
                content = await writer.get(
                    SubjectDocumentContentRevision, captured.content_revision_id,
                    with_for_update=True,
                )
                content.published_at = None
        with pytest.raises(KnowledgeSourceUnavailable):
            await retriever.expand_source_neighbors((anchor,))


async def test_current_canonical_pages_are_exact_authorized_and_bounded(
    postgres_engine, postgres_session_factory, neighbor_owner_cleanup,
):
    owner_id, subject_id, captured, _space_hash = await _ready_pages(
        postgres_engine, postgres_session_factory, neighbor_owner_cleanup,
    )
    async with postgres_session_factory() as db:
        owner = await db.get(User, owner_id)
        retriever = await KnowledgeRetriever.authorize(
            db, principal=owner, subject_id=subject_id,
            query="opening concept", document_ids=[captured.document_id],
            policy=SOURCE_SUFFICIENCY_RETRIEVAL_POLICY,
        )
        chunks = (await db.scalars(select(SubjectDocumentChunk).where(
            SubjectDocumentChunk.index_revision_id == captured.index_revision_id,
            SubjectDocumentChunk.page_number == 1,
        ).order_by(SubjectDocumentChunk.chunk_index))).all()
        assert len(chunks) >= 2
        canonical = await db.scalar(select(SubjectDocumentPage).where(
            SubjectDocumentPage.content_revision_id == captured.content_revision_id,
            SubjectDocumentPage.page_number == 1,
        ))
        assert canonical is not None
        ids = tuple(item.id for item in chunks[:2])
        assert await retriever.read_current_source_pages(ids, max_pages=1) == {
            chunk_id: canonical.content for chunk_id in ids
        }
        assert await retriever.read_current_source_pages(ids, max_tokens=1) == {}
        assert await retriever.read_current_source_pages((uuid4(),)) == {}
        async with postgres_session_factory() as writer:
            async with writer.begin():
                content = await writer.get(
                    SubjectDocumentContentRevision, captured.content_revision_id,
                    with_for_update=True,
                )
                content.published_at = None
        assert await retriever.read_current_source_pages(ids) == {}
