"""Navigation SQL and outage recovery against guarded disposable PostgreSQL.

All documents and provider behavior are invented fixtures. The conftest database
guard rejects operator databases; no real provider client is created.
"""

from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from app.ai.providers import AIProviderError
from app.config import ASK_REQUIRED_RELEASE_POLICY_VERSION
from app.models.knowledge import SubjectDocumentChunk, SubjectDocumentContentRevision
from app.models.rag import RagAnswerJob, RagAnswerStageAttempt, RagMessage, RagRelatedEvidence
from app.models.user import User, UserRole
from app.services.knowledge_retrieval import KnowledgeRetriever, KnowledgeScopeUnavailable, SOURCE_NAVIGATION_RETRIEVAL_POLICY
from app.services.rag_answers import RagAnswerService
from app.time_utils import utcnow
from app.workers.rag_answer import RagAnswerWorker
from tests.postgres.test_postgres_rag_answers import (
    FakeSourceJudge, _ready_course, _student_and_current_job,
)


pytestmark = pytest.mark.postgres


@pytest.fixture(autouse=True)
def current_visual_profile(monkeypatch):
    from tests.support.visual_renderer import fake_visual_renderer
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", ASK_REQUIRED_RELEASE_POLICY_VERSION)
    fake_visual_renderer(monkeypatch)


@pytest_asyncio.fixture
async def navigation_users(postgres_session_factory):
    users = []
    yield users
    if users:
        async with postgres_session_factory() as db:
            async with db.begin():
                await db.execute(text("DELETE FROM users WHERE id=ANY(CAST(:ids AS uuid[]))"), {"ids": users})


async def _assert_no_source(retriever):
    try:
        result = await retriever.retrieve_lexical()
    except KnowledgeScopeUnavailable:
        return
    assert result.chunks == ()


async def test_lexical_sql_checks_principal_documents_publication_revision_and_space(
    postgres_engine, postgres_session_factory, navigation_users,
):
    settings, owner_id, subject_id, content_id, chunk_id = await _ready_course(
        postgres_engine, postgres_session_factory,
    )
    navigation_users.append(owner_id)
    outsider_id = uuid4()
    navigation_users.append(outsider_id)
    async with postgres_session_factory() as db:
        async with db.begin():
            db.add(User(id=outsider_id, email=f"nav-outsider-{outsider_id.hex}@example.test",
                        hashed_password="fixture", role=UserRole.STUDENT))

    async with postgres_session_factory() as db:
        owner = await db.get(User, owner_id)
        source = await db.get(SubjectDocumentChunk, chunk_id)
        assert owner is not None and source is not None
        document_id = source.document_id
        retriever = await KnowledgeRetriever.authorize(
            db, principal=owner, subject_id=subject_id, query="Explain alpha",
            document_ids=[document_id], limit=20, policy=SOURCE_NAVIGATION_RETRIEVAL_POLICY,
        )
        result = await retriever.retrieve_lexical()
        assert [item.chunk_id for item in result.chunks] == [chunk_id]
        assert all(item.vector_rank is None and item.vector_similarity is None for item in result.chunks)
        assert result.chunks[0].lexical_rank == 1
        # Exercise the SQL security boundary even with a forged caller scope.
        for scope in (
            replace(retriever.scope, principal_id=outsider_id),
            replace(retriever.scope, document_ids=(uuid4(),)),
            replace(retriever.scope, corpus_revision=retriever.scope.corpus_revision + 1),
            replace(retriever.scope, embedding_space_hash="b" * 64),
        ):
            forged = KnowledgeRetriever(db, scope, "alpha", 20, SOURCE_NAVIGATION_RETRIEVAL_POLICY)
            with pytest.raises(KnowledgeScopeUnavailable):
                await forged.retrieve_lexical()
        saved_scope = retriever.scope

    async with postgres_session_factory() as db:
        async with db.begin():
            content = await db.get(SubjectDocumentContentRevision, content_id, with_for_update=True)
            assert content is not None
            content.published_at = None
    async with postgres_session_factory() as db:
        stale = KnowledgeRetriever(db, saved_scope, "alpha", 20, SOURCE_NAVIGATION_RETRIEVAL_POLICY)
        await _assert_no_source(stale)
        owner = await db.get(User, owner_id)
        with pytest.raises(KnowledgeScopeUnavailable):
            await KnowledgeRetriever.authorize(db, principal=owner, subject_id=subject_id,
                                               query="alpha", limit=20,
                                               policy=SOURCE_NAVIGATION_RETRIEVAL_POLICY)


@pytest.mark.parametrize("category,reason", [
    ("embedding_provider_timeout", "transport_timeout"),
    ("embedding_provider_unavailable", "http_server_error"),
    ("embedding_provider_rate_limited", "http_rate_limited"),
])
async def test_one_transient_embedding_attempt_completes_local_reference_bundle(
    postgres_engine, postgres_session_factory, navigation_users, monkeypatch, category, reason,
):
    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", ASK_REQUIRED_RELEASE_POLICY_VERSION)
    settings, owner_id, subject_id, _content_id, chunk_id = await _ready_course(
        postgres_engine, postgres_session_factory,
    )
    navigation_users.append(owner_id)
    student_id, _auth_id, thread_id, job_id = await _student_and_current_job(
        postgres_session_factory, settings, subject_id, key=f"nav-local-{uuid4().hex}",
    )
    navigation_users.append(student_id)
    async with postgres_session_factory() as db:
        async with db.begin():
            job = await db.get(RagAnswerJob, job_id, with_for_update=True)
            assert job is not None
            job.available_at = utcnow() - timedelta(hours=1)

    class OfflineOutage:
        calls = 0

        async def embed_query(self, question):
            self.calls += 1
            assert question == "What does the course say about alpha?"
            raise AIProviderError(category, "Embedding search is temporarily unavailable.",
                                  retryable=True, reason_code=reason)

    provider = OfflineOutage()
    judge = FakeSourceJudge()
    worker = RagAnswerWorker(settings=settings, session_factory=postgres_session_factory,
                             embedding_provider=provider, source_judge=judge,
                             worker_id=f"nav-worker-{uuid4().hex}")
    assert not hasattr(worker, "answer_provider") and not hasattr(worker, "local_support_verifier")
    claim = await worker.claim_next()
    assert claim is not None and claim[0] == job_id
    await worker.process_claim(*claim)
    assert provider.calls == 1
    assert judge.calls == 1
    service = RagAnswerService(settings)
    async with postgres_session_factory() as db:
        job = await db.get(RagAnswerJob, job_id)
        assert job is not None
        assert (job.status, job.result_kind, job.answer_message_id) == ("completed", "related_knowledge", None)
        assert job.provider_request_count == 2 and job.provider_retry_count == 0
        assert job.failed_stage == "query_embedding" and job.provider_error_category == category
        assert job.attempt_cost_unknown and job.usage_estimated
        assert job.error_code is None and job.error_retryable is False
        stages = (await db.scalars(select(RagAnswerStageAttempt).where(
            RagAnswerStageAttempt.job_id == job_id).order_by(RagAnswerStageAttempt.started_at))).all()
        assert [(row.stage, row.physical_request_count, row.retry_count) for row in stages] == [
            ("query_embedding", 1, 0), ("retrieval", 0, 0),
            ("source_judgment", 1, 0),
        ]
        assert stages[0].error_category == category and stages[1].error_category is None
        refs = (await db.scalars(select(RagRelatedEvidence).where(RagRelatedEvidence.job_id == job_id))).all()
        assert len(refs) == 1 and refs[0].chunk_id == chunk_id and refs[0].source_kind == "canonical_page"
        messages = (await db.scalars(select(RagMessage).where(RagMessage.thread_id == thread_id))).all()
        assert [message.role for message in messages] == ["user"]
        student = await db.get(User, student_id)
        response = await service.job_response_with_related(db, job=job, user=student)
        assert response.search_mode == "lexical_fallback" and response.failure_kind is None
        assert response.actual_cost_microusd is None and response.can_retry is False
        assert len(response.related_excerpts) == 1
        assert "Alpha is the first concept" in response.related_excerpts[0].source_quote
        page = await service.related_page(db, subject_id=subject_id, thread_id=thread_id,
                                          job_id=job_id, excerpt_order=1, user=student)
        assert page.reference_start is not None and page.reference_end is not None
        assert page.page_content[page.reference_start:page.reference_end] == page.source_quote
