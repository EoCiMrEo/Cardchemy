"""Synthetic contracts for the unshipped history-query candidate."""

from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.ai.embeddings import EmbeddingResponse
from app.ai.navigation_query_candidate import candidate_navigation_query
from app.ai.providers import ProviderUsage
from app.config import ASK_REQUIRED_RELEASE_POLICY_VERSION
from app.models.knowledge import embedding_space_hash
from app.models.rag import RagAnswerJob, RagMessage
from app.schemas.rag import RagQuestionCreate
from app.services.knowledge_retrieval import KnowledgeRetriever, bounded_lexical_query
from app.services.rag_answers import RagAnswerService
from app.time_utils import utcnow
from app.workers.rag_answer import RagAnswerWorker
from tests.test_rag_answers import _seed, _settings


@pytest.mark.parametrize(("question", "prior", "expected"), [
    ("What does it stand for?", "What does orbital eccentricity measure?",
     "orbital eccentricity What does it stand for?"),
    ("How does this work?", "Define spectral index",
     "spectral index How does this work?"),
    ("What are its limitations?", "What is spectral index?",
     "spectral index What are its limitations?"),
    ("What about its applications?", "Explain spectral index",
     "spectral index What about its applications?"),
    ("How does it compare to albedo?", "What is spectral index?",
     "spectral index How does it compare to albedo?"),
])
def test_only_a_syntactic_empty_owner_inherits_one_prior_topic(question, prior, expected):
    actual = candidate_navigation_query(question, (("user", prior),))
    assert actual == expected
    assert len(actual) <= 4_000
    assert len(bounded_lexical_query(actual, 13).split()) <= 12


@pytest.mark.parametrize("current", [
    "What does albedo measure?",
    "How does albedo compare to it?",
    "What is orbital eccentricity and how does it compare to albedo?",
])
def test_current_explicit_subject_wins_over_old_topic(current):
    assert candidate_navigation_query(current, (("user", "What is spectral index?"),)) == current


@pytest.mark.parametrize("prior", [
    "Compare spectral index and albedo",
    "What does spectral index measure with albedo?",
    "What is BLEU ROUGE?",
    "What is spectral index orbital eccentricity?",
    "What is spectral index? What is albedo?",
    "What is the result?",
    "What is it?",
    "What about it?",
])
def test_competing_or_event_level_prior_never_supplies_an_arbitrary_topic(prior):
    assert candidate_navigation_query("How does it work?", (("user", prior),)) is None


def test_latest_user_turn_is_final_even_when_an_older_turn_has_a_unique_topic():
    history = (("user", "What is spectral index?"),
               ("assistant", "The index describes a spectrum."),
               ("user", "Compare albedo and orbital eccentricity"),
               ("assistant", "Both relate to orbital observations."))
    assert candidate_navigation_query("How does it work?", history) is None
    assert candidate_navigation_query("How does it work?", (("assistant", "Spectral index"),)) is None


@pytest.mark.parametrize("question", [
    "Why did it happen?", "What does this imply?", "Can you explain it?",
    "What are their limitations?", "What about the result?",
])
def test_event_level_or_unparsed_referent_needs_clarification(question):
    assert candidate_navigation_query(question, (("user", "What is spectral index?"),)) is None


def test_expansion_fails_closed_before_character_or_fts_term_truncation():
    too_long = "How does it measure " + "a" * 3_970 + "?"
    assert len(too_long) < 4_000
    assert candidate_navigation_query(too_long, (("user", "What is spectral index?"),)) is None
    many_terms = "How does it measure alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu?"
    assert candidate_navigation_query(many_terms, (("user", "What is spectral index?"),)) is None
    assert candidate_navigation_query("Q" * 4_001) is None


async def test_current_worker_uses_admitted_literal_subject_only_for_search_and_never_sends_history(
    db, session_factory, monkeypatch,
):
    """The unshipped candidate is replaced by the admission-bound v7 contract."""

    monkeypatch.setattr("app.config.ASK_RUNTIME_POLICY_VERSION", ASK_REQUIRED_RELEASE_POLICY_VERSION)
    settings = _settings(rag_ai_provider_enabled=False, rag_ai_api_key=None,
                         rag_local_support_enabled=False)
    _owner, student, _outsider, subject, _session = await _seed(db)
    scope = SimpleNamespace(
        corpus_revision=subject.corpus_revision,
        embedding_space_hash=embedding_space_hash(settings.rag_embedding_space_identity),
    )
    seen_queries: list[str] = []

    class EmptyRetriever:
        async def retrieve(self, _vector, *, embedding_space_hash):
            assert embedding_space_hash == scope.embedding_space_hash
            return SimpleNamespace(insufficient=True, chunks=())

    retriever = EmptyRetriever()
    retriever.scope = scope

    async def authorize(_cls, _db, **kwargs):
        seen_queries.append(kwargs["query"])
        return retriever

    monkeypatch.setattr(KnowledgeRetriever, "authorize", classmethod(authorize))

    async def forbid_history(*_args, **_kwargs):
        raise AssertionError("Current source-only worker must use its admission binding")

    monkeypatch.setattr(RagAnswerWorker, "_bounded_history", forbid_history)
    service = RagAnswerService(settings)
    current = "How does it work?"
    async with db.begin():
        thread = await service.create_thread(db, subject_id=subject.id, user=student)
        now = utcnow()
        db.add(RagMessage(
            id=uuid4(), thread_id=thread.id, user_id=student.id, subject_id=subject.id,
            role="user", outcome=None, content="What is spectral index?", source_count=0,
            created_at=now - timedelta(seconds=1), expires_at=now + timedelta(days=1),
        ))
        await db.flush()
        job = await service.enqueue(
            db, subject_id=subject.id, thread_id=thread.id, user=student,
            data=RagQuestionCreate(question=current), idempotency_key=uuid4().hex,
        )

    class OneEmbedding:
        def __init__(self):
            self.questions: list[str] = []

        async def embed_query(self, text: str):
            self.questions.append(text)
            return EmbeddingResponse(
                vectors=(tuple([1.0, *([0.0] * 1535)]),),
                usage=ProviderUsage(7, 0, False),
            )

    embedding = OneEmbedding()
    worker = RagAnswerWorker(settings=settings, session_factory=session_factory,
                             embedding_provider=embedding, worker_id="candidate-spy")
    claim = await worker.claim_next()
    assert claim is not None and claim[0] == job.id
    await worker.process_claim(*claim)
    assert embedding.questions == [current]
    expanded = "How does it work? spectral index"
    assert seen_queries.count(expanded) == 1
    assert all(query == current or query == expanded for query in seen_queries)
    async with session_factory() as read_db:
        stored = await read_db.get(RagAnswerJob, job.id)
        assert stored is not None
        assert stored.status == "completed" and stored.result_kind == "no_match"
        assert stored.provider_request_count == 1 and stored.provider_retry_count == 0
        assert stored.answer_message_id is None
