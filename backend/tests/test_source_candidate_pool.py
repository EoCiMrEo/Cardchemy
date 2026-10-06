"""Keyless worker contracts for the dormant v4 source-ID judgment stage."""

from __future__ import annotations

from dataclasses import asdict, replace
from uuid import uuid4

import pytest

from app.ai.related_evidence import RelatedExcerptSelection
from app.services.knowledge_retrieval import (
    AuthorizedKnowledgeSource, ExpandedKnowledgeNeighbor, RetrievedKnowledgeChunk,
)
from app.workers import rag_answer as module


def _chunk(page: int, content: str, *, fusion: float = 0.1) -> RetrievedKnowledgeChunk:
    return RetrievedKnowledgeChunk(
        chunk_id=uuid4(), document_id=uuid4(), document_title="Public PDF",
        content_revision_id=uuid4(), index_revision_id=uuid4(),
        page_number=page, section="Methods", content=content,
        token_count=20, embedding_space_hash="space", corpus_revision=1,
        vector_similarity=0.8, lexical_score=0.5, vector_rank=1,
        lexical_rank=1, fusion_score=fusion,
    )


def _selection(page: int) -> RelatedExcerptSelection:
    text = f"Methods page {page}. The method updates weights after each example."
    return RelatedExcerptSelection(
        _chunk(page, text), 16, len(text), "canonical_page", text,
    )


class _Retriever:
    def __init__(self, chunks: tuple[RetrievedKnowledgeChunk, ...],
                 neighbor: RetrievedKnowledgeChunk | None = None):
        self.chunks = chunks
        self.neighbor = neighbor
        self.calls = []

    async def expand_source_neighbors(self, anchors, **kwargs):
        self.calls.append(("expand", kwargs))
        return (ExpandedKnowledgeNeighbor(self.neighbor, anchors[0].chunk_id, 1),) if self.neighbor else ()

    async def read_current_sources(self, ids):
        self.calls.append(("sources", ids))
        by_id = {chunk.chunk_id: chunk for chunk in (*self.chunks, *((self.neighbor,) if self.neighbor else ())) }
        return tuple(AuthorizedKnowledgeSource(**{
            key: value for key, value in asdict(by_id[chunk_id]).items()
            if key in AuthorizedKnowledgeSource.__dataclass_fields__
        }) for chunk_id in ids)

    async def read_current_source_pages(self, ids, **kwargs):
        self.calls.append(("pages", kwargs))
        by_id = {chunk.chunk_id: chunk for chunk in (*self.chunks, *((self.neighbor,) if self.neighbor else ())) }
        return {chunk_id: by_id[chunk_id].content for chunk_id in ids}


@pytest.mark.asyncio
async def test_candidate_pool_uses_current_canonical_pages_and_bounded_neighbors():
    first = _chunk(1, "The method updates weights after each example.")
    neighbor = replace(
        _chunk(2, "A neighbor page explains the update rule in detail."),
        document_id=first.document_id,
        content_revision_id=first.content_revision_id,
        index_revision_id=first.index_revision_id,
    )
    retriever = _Retriever((first,), neighbor)
    pool = await module._source_candidate_pool("How does the method update weights?", (first,), retriever)
    assert len(pool.selections) == 2
    assert pool.examined_pages == 2
    assert all(item.source_kind == "canonical_page" for item in pool.selections)
    assert any(item.source.chunk_id == neighbor.chunk_id for item in pool.selections)
    assert retriever.calls[0] == ("expand", {
        "radius": 2, "max_chunks": 30, "max_pages": 12, "max_tokens": 8192,
    })



@pytest.mark.asyncio
async def test_candidate_pool_inspects_twelve_pages_but_sends_at_most_four():
    docs = (uuid4(), uuid4())
    chunks = tuple(
        replace(
            _chunk(page, "The method updates weights after each example."),
            document_id=docs[(page - 1) // 6],
        )
        for page in range(1, 13)
    )
    retriever = _Retriever(chunks)
    pool = await module._source_candidate_pool(
        "How does the method update weights?", chunks, retriever,
    )
    assert len(pool.selections) == 4
    assert pool.examined_pages == 12
    assert pool.examined_chunks == 12
    assert any(call[0] == "sources" and len(call[1]) == 12 for call in retriever.calls)
    assert all(item.source_kind == "canonical_page" for item in pool.selections)


@pytest.mark.asyncio
async def test_candidate_pool_rejects_a_changed_source_before_egress():
    chunk = _chunk(1, "The method updates weights after each example.")

    class _Changed(_Retriever):
        async def read_current_source_pages(self, ids, **kwargs):
            return {chunk_id: "A changed page" for chunk_id in ids}

        async def read_current_sources(self, ids):
            rows = await super().read_current_sources(ids)
            return tuple(replace(row, content="changed") for row in rows)

    retriever = _Changed((chunk,))
    with pytest.raises(module.KnowledgeSourceUnavailable):
        await module._source_candidate_pool("How are weights updated?", (chunk,), retriever)


@pytest.mark.asyncio
async def test_candidate_pool_does_not_treat_a_missing_canonical_page_as_no_match():
    chunk = _chunk(1, "The method updates weights after each example.")

    class _Missing(_Retriever):
        async def read_current_source_pages(self, ids, **kwargs):
            return {}

    with pytest.raises(module.KnowledgeSourceUnavailable):
        await module._source_candidate_pool(
            "How are weights updated?", (chunk,), _Missing((chunk,)),
        )
