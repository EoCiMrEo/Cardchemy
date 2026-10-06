"""Invented authorized source values shared by current navigation tests."""
from uuid import uuid4

from app.services.knowledge_retrieval import RetrievedKnowledgeChunk


def chunk(content: str, *, page: int = 1, document_id=None, rank: int = 1):
    return RetrievedKnowledgeChunk(
        chunk_id=uuid4(), document_id=document_id or uuid4(),
        document_title="Synthetic", content_revision_id=uuid4(),
        index_revision_id=uuid4(), page_number=page, section=None,
        content=content, token_count=50, embedding_space_hash="a" * 64,
        corpus_revision=1, vector_similarity=.8, lexical_score=.2,
        vector_rank=rank, lexical_rank=rank, fusion_score=.02 / rank,
    )
