"""Malformed query vectors must fail the source-only attempt without references."""

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.ai.embeddings import EmbeddingResponse
from app.ai.providers import ProviderUsage
from app.config import ASK_REQUIRED_RELEASE_POLICY_VERSION
from app.models.knowledge import embedding_space_hash
from app.models.rag import RagAnswerJob, RagAnswerStageAttempt, RagMessage, RagRelatedEvidence
from app.schemas.rag import RagQuestionCreate
from app.services.knowledge_retrieval import (
    AuthorizedKnowledgeScope,
    KnowledgeRetriever,
    SOURCE_NAVIGATION_RETRIEVAL_POLICY,
)
from app.services.rag_answers import RagAnswerService
from app.workers.rag_answer import RagAnswerWorker
from tests.test_rag_answers import _seed, _settings


_GOOD_VECTOR = (1.0, *([0.0] * 1535))


@pytest.mark.parametrize("vectors, expected_stages", [
    ((), [("query_embedding", 1)]),
    ((_GOOD_VECTOR, _GOOD_VECTOR), [("query_embedding", 1)]),
    (((1.0, *([0.0] * 1534)),), [("query_embedding", 1), ("retrieval", 0)]),
    (((float("nan"), *([0.0] * 1535)),), [("query_embedding", 1), ("retrieval", 0)]),
    (((0.0,) * 1536,), [("query_embedding", 1), ("retrieval", 0)]),
])
async def test_malformed_embedding_fails_without_fallback_or_partial_result(
    db, session_factory, monkeypatch, vectors, expected_stages,
):
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", ASK_REQUIRED_RELEASE_POLICY_VERSION)
    settings = _settings(rag_ai_provider_enabled=False, rag_ai_api_key=None,
                         rag_local_support_enabled=False)
    _owner, student, _outsider, subject, _session = await _seed(db)
    space_hash = embedding_space_hash(settings.rag_embedding_space_identity)
    lexical_calls = 0

    async def authorize(_cls, current_db, **kwargs):
        assert kwargs["policy"] == SOURCE_NAVIGATION_RETRIEVAL_POLICY
        scope = AuthorizedKnowledgeScope(
            principal_id=student.id, subject_id=subject.id,
            corpus_revision=subject.corpus_revision, embedding_space_hash=space_hash,
            document_ids=(),
        )
        retriever = KnowledgeRetriever(
            current_db, scope, kwargs["query"], kwargs["limit"], kwargs["policy"],
        )

        async def no_lexical_fallback():
            nonlocal lexical_calls
            lexical_calls += 1
            pytest.fail("Malformed provider output must not start lexical fallback")

        retriever.retrieve_lexical = no_lexical_fallback
        return retriever

    monkeypatch.setattr(KnowledgeRetriever, "authorize", classmethod(authorize))
    service = RagAnswerService(settings)
    async with db.begin():
        thread = await service.create_thread(db, subject_id=subject.id, user=student)
        job = await service.enqueue(
            db, subject_id=subject.id, thread_id=thread.id, user=student,
            data=RagQuestionCreate(question="What does BLEU measure?"),
            idempotency_key=uuid4().hex,
        )

    class OneMalformedEmbedding:
        calls = 0

        async def embed_query(self, question):
            self.calls += 1
            assert question == "What does BLEU measure?"
            return EmbeddingResponse(vectors=vectors, usage=ProviderUsage(7, 0, False))

    embedding = OneMalformedEmbedding()
    worker = RagAnswerWorker(settings=settings, session_factory=session_factory,
                             embedding_provider=embedding, worker_id=f"malformed-{uuid4().hex}")
    claim = await worker.claim_next()
    assert claim is not None and claim[0] == job.id
    await worker.process_claim(*claim)

    async with session_factory() as read_db:
        stored = await read_db.get(RagAnswerJob, job.id)
        assert stored.status == "failed" and stored.result_kind is None
        assert stored.error_code == "rag_answer_failed" and stored.error_retryable is False
        assert stored.provider_request_count == 1 and stored.provider_retry_count == 0
        assert stored.answer_message_id is None
        stages = (await read_db.scalars(select(RagAnswerStageAttempt).where(
            RagAnswerStageAttempt.job_id == job.id,
        ))).all()
        assert [(stage.stage, stage.physical_request_count) for stage in stages] == expected_stages
        assert (await read_db.scalars(select(RagRelatedEvidence).where(
            RagRelatedEvidence.job_id == job.id,
        ))).all() == []
        messages = (await read_db.scalars(select(RagMessage).where(
            RagMessage.thread_id == thread.id,
        ))).all()
        assert [message.role for message in messages] == ["user"]
    assert embedding.calls == 1 and lexical_calls == 0
