from uuid import uuid4
from dataclasses import replace

import pytest

from app.services import knowledge_retrieval as retrieval
from app.services.knowledge_retrieval import (
    EXACT_V1_POLICY,
    RetrievedKnowledgeChunk,
    reciprocal_rank_score,
    select_bounded_candidates,
)


def chunk(*, content: str, tokens: int, rank: int, document_id=None, page=1):
    return RetrievedKnowledgeChunk(
        chunk_id=uuid4(), document_id=document_id or uuid4(), document_title="Private",
        content_revision_id=uuid4(), index_revision_id=uuid4(), page_number=page,
        section=None, content=content, token_count=tokens,
        embedding_space_hash="a" * 64, corpus_revision=7,
        vector_similarity=0.9, lexical_score=0.5,
        vector_rank=rank, lexical_rank=None,
        fusion_score=reciprocal_rank_score(rank, None),
    )


def test_exact_v1_sql_keeps_authorization_and_eligibility_inside_both_channels():
    sql = str(retrieval._RETRIEVAL_SQL)
    assert "principal.role = 'INSTRUCTOR'" in sql
    assert "principal.role = 'STUDENT'" in sql and "enrollments" in sql
    assert sql.count("eligible_subject_knowledge_chunks") >= 4
    assert "subject.corpus_revision = :corpus_revision" in sql
    assert "subject.active_embedding_space_hash = :embedding_space_hash" in sql
    assert "OPERATOR(public.<=>)" in sql
    assert "to_tsvector('simple'::regconfig" in sql
    assert "ivfflat" not in sql.casefold() and "hnsw" not in sql.casefold()


def test_rrf_is_deterministic_and_not_a_confidence_score():
    vector_only = reciprocal_rank_score(1, None)
    lexical_only = reciprocal_rank_score(None, 1)
    both = reciprocal_rank_score(1, 1)
    assert vector_only == lexical_only
    assert both == vector_only * 2
    with pytest.raises(ValueError):
        reciprocal_rank_score(0, None)


def test_candidate_selection_enforces_overlap_result_and_context_bounds():
    document_id = uuid4()
    first = chunk(content="alpha beta gamma delta", tokens=4, rank=1, document_id=document_id)
    duplicate = replace(
        first, chunk_id=uuid4(), content="alpha beta gamma delta epsilon", vector_rank=2
    )
    other = chunk(content="unrelated source material", tokens=4, rank=3)
    oversized = chunk(content="too many", tokens=EXACT_V1_POLICY.context_token_limit + 1, rank=4)
    selected = select_bounded_candidates((first, duplicate, other, oversized), limit=5)
    assert selected == (first, other)
