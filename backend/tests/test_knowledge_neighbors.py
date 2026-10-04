"""Bounded source-neighbor planning stays independent of provider execution."""

from uuid import uuid4

import pytest

from app.services.knowledge_retrieval import (
    AuthorizedKnowledgeScope,
    EXACT_V1_POLICY,
    InvalidKnowledgeRetrievalRequest,
    KnowledgeRetriever,
    _NEIGHBOR_SQL,
    _SOURCE_PAGE_SQL,
)


def test_neighbor_sql_revalidates_both_anchor_and_neighbor_scope():
    sql = str(_NEIGHBOR_SQL)
    assert "principal.role = 'INSTRUCTOR'" in sql
    assert "principal.role = 'STUDENT'" in sql and "enrollments" in sql
    assert sql.count("eligible_subject_knowledge_chunks") == 2
    assert "subject.corpus_revision = :corpus_revision" in sql
    assert "subject.active_embedding_space_hash = :embedding_space_hash" in sql
    for identity in ("document_id", "content_revision_id", "index_revision_id", "embedding_space_hash"):
        assert f"neighbor.{identity} = anchor.{identity}" in sql
    assert "anchor.document_id = ANY(:document_ids)" in sql
    assert "neighbor.document_id = ANY(:document_ids)" in sql
    assert "count(*) FROM valid_anchor) = :anchor_count" in sql
    assert "abs(neighbor.page_number - anchor.page_number) <= :radius" in sql
    assert "WHERE duplicate_rank = 1" in sql
    assert "ORDER BY page_distance, anchor_ordinal" in sql


@pytest.mark.asyncio
async def test_empty_expansion_does_not_touch_database_and_bounds_are_validated():
    class NoDatabase:
        async def execute(self, *_args, **_kwargs):
            raise AssertionError("empty neighbor expansion must not query")

    retriever = KnowledgeRetriever(
        NoDatabase(),
        AuthorizedKnowledgeScope(
            principal_id=uuid4(), subject_id=uuid4(), corpus_revision=1,
            embedding_space_hash="a" * 64, document_ids=(),
        ),
        "question", 5,
        EXACT_V1_POLICY,
    )
    assert await retriever.expand_source_neighbors(()) == ()
    for options in (
        {"radius": 0}, {"radius": 3}, {"max_chunks": 31},
        {"max_pages": 13}, {"max_tokens": 8_193},
    ):
        with pytest.raises(InvalidKnowledgeRetrievalRequest):
            await retriever.expand_source_neighbors((), **options)


def test_current_page_sql_reauthorizes_anchor_and_links_actual_revision_page():
    sql = str(_SOURCE_PAGE_SQL)
    assert "principal.role = 'INSTRUCTOR'" in sql
    assert "principal.role = 'STUDENT'" in sql and "enrollments" in sql
    assert "eligible_subject_knowledge_chunks AS anchor" in sql
    assert "subject.corpus_revision = :corpus_revision" in sql
    assert "subject.active_embedding_space_hash = :embedding_space_hash" in sql
    for identity in ("subject_id", "document_id", "content_revision_id", "page_number"):
        assert f"page.{identity} = anchor.{identity}" in sql
    assert "anchor.document_id = ANY(:document_ids)" in sql
    assert "cumulative_tokens <= :max_tokens" in sql
    assert "page_rank <= :max_pages" in sql


@pytest.mark.asyncio
async def test_current_pages_validate_bounds_and_count_one_page_for_two_anchors():
    first, second = uuid4(), uuid4()
    document_id, revision_id = uuid4(), uuid4()
    page = "BLEU\n- Stands for Bilingual Evaluation Understudy."

    class Result:
        def mappings(self):
            return ({
                "document_id": document_id, "content_revision_id": revision_id,
                "page_number": 1, "content": page, "chunk_ids": [first, second],
            },)

    class Database:
        parameters = None

        async def execute(self, statement, parameters):
            assert statement is _SOURCE_PAGE_SQL
            self.parameters = parameters
            return Result()

    database = Database()
    scope = AuthorizedKnowledgeScope(
        principal_id=uuid4(), subject_id=uuid4(), corpus_revision=5,
        embedding_space_hash="a" * 64, document_ids=(document_id,),
    )
    retriever = KnowledgeRetriever(database, scope, "question", 5, EXACT_V1_POLICY)
    assert await retriever.read_current_source_pages(()) == {}
    assert database.parameters is None
    for ids, options in (
        (tuple(uuid4() for _ in range(31)), {}), (("invalid",), {}),
        ((first,), {"max_pages": 0}), ((first,), {"max_pages": 13}),
        ((first,), {"max_tokens": 0}), ((first,), {"max_tokens": 8_193}),
    ):
        with pytest.raises(InvalidKnowledgeRetrievalRequest):
            await retriever.read_current_source_pages(ids, **options)
    assert await retriever.read_current_source_pages((first, second), max_tokens=1) == {}
    pages = await retriever.read_current_source_pages((first, second), max_pages=1, max_tokens=100)
    assert pages == {first: page, second: page}
    assert database.parameters["principal_id"] == scope.principal_id
    assert database.parameters["subject_id"] == scope.subject_id
    assert database.parameters["corpus_revision"] == scope.corpus_revision
    assert database.parameters["embedding_space_hash"] == scope.embedding_space_hash
    assert database.parameters["document_ids"] == [document_id]
    assert database.parameters["has_document_filter"] is True
    assert database.parameters["max_pages"] == 1
    assert database.parameters["max_tokens"] == 100
