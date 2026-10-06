"""Navigation contracts use public invented text, never lecture content."""

from dataclasses import replace
from uuid import uuid4

import pytest

from app.ai.source_navigation import (
    MAX_NAVIGATION_CHUNKS, MAX_NAVIGATION_PAGES, MAX_NAVIGATION_TOKENS,
    navigation_query, navigation_query_v4, select_navigation_pages,
)
from app.ai.chunking import estimate_tokens
from app.services.knowledge_retrieval import (
    AuthorizedKnowledgeScope, KnowledgeRetriever, SOURCE_NAVIGATION_RETRIEVAL_POLICY,
    ExpandedKnowledgeNeighbor, InvalidKnowledgeRetrievalRequest, KnowledgeScopeUnavailable,
    _LEXICAL_ONLY_SQL,
)
from tests.support.rag_sources import chunk


def test_navigation_accepts_unclassified_questions_and_resolves_followup_locally():
    assert navigation_query("Tell me more about astronomy") == "Tell me more about astronomy"
    resolved = navigation_query("What does it stand for?", (("user", "What does BLEU measure?"),))
    assert resolved is not None and "BLEU" in resolved
    assert navigation_query("What does it stand for?", (("user", "Compare BLEU and ROUGE"),)) is None
    assert navigation_query("What does it stand for?", ()) is None
    assert navigation_query("What is it?") is None
    assert navigation_query("   ") is None


def test_current_comparison_acronym_does_not_hide_unresolved_prior_referent():
    question = "How does it compare to ROUGE?"
    assert navigation_query(question, ()) is None
    assert navigation_query(question, (("user", "What does BLEU measure?"),)) == f"BLEU {question}"
    assert navigation_query(question, (("user", "Compare BLEU and METEOR"),)) is None


def test_single_same_turn_acronym_before_pronoun_is_explicit_antecedent():
    question = "What does BLEU measure and how does it compare to ROUGE?"
    assert navigation_query(question, ()) == question
    assert navigation_query("How do BLEU and METEOR compare when they are used?", ()) is None


def test_single_named_same_turn_antecedent_keeps_comparison_query():
    question = "What is Euclidean distance and how does it compare to cosine similarity?"
    assert navigation_query(question, ()) == question
    assert navigation_query(
        "What is Euclidean distance and cosine similarity and how does it compare?", (),
    ) is None


def test_v4_local_query_accepts_explicit_topic_before_possessive_without_changing_v3():
    question = "How does the perceptron change its weights after a mistake?"
    assert navigation_query(question) is None
    assert navigation_query_v4(question) == question
    assert navigation_query_v4("How does it change its weights?") is None


def test_v4_current_document_topic_and_named_first_clause_need_no_history():
    questions = (
        "How do these slides describe learning features instead of choosing them by hand?",
        "Where do these slides define the training error and connect it to learning?",
        "Does this deep-network lecture work through a stock-price forecasting example?",
        "What triggers a perceptron weight update, and what update does it make?",
    )
    for question in questions:
        assert navigation_query_v4(question) == question
    assert navigation_query_v4("What do these slides say?") is None
    assert navigation_query_v4("How does this compare to BLEU?") is None


def test_v4_local_query_uses_one_specific_prior_without_sending_it_as_current_question():
    prior = "I am checking the theorem after the perceptron update rule."
    question = "When does it promise convergence?"
    assert navigation_query_v4(question, (("user", prior),)) == f"{prior} {question}"
    assert navigation_query_v4(question, (("user", "I read the notes."),)) is None
    assert navigation_query_v4(
        question, (("user", "I compared two classifier sections."),),
    ) is None


async def test_navigation_inspects_neighbors_even_when_initial_page_matches():
    document = uuid4()
    first = chunk("Orbital eccentricity is discussed next.", document_id=document)
    neighbor = replace(chunk("Orbital eccentricity describes how elongated an orbit is.",
                             document_id=document, page=2),
                       vector_rank=None, lexical_rank=None, fusion_score=0.0)
    expanded = []

    async def expand(anchors, radius, max_chunks, max_pages, max_tokens):
        expanded.append((anchors, radius))
        assert 1 <= max_chunks <= 30 and 1 <= max_pages <= 12 and 1 <= max_tokens <= 8_192
        return (ExpandedKnowledgeNeighbor(neighbor, first.chunk_id, 1),)

    pages = {first.chunk_id: first.content, neighbor.chunk_id: "Eccentricity\n" + neighbor.content}

    loaded = []

    async def load(ids, max_pages, max_tokens):
        loaded.append(set(ids))
        assert 1 <= max_pages <= 12 and 1 <= max_tokens <= 8_192
        return {chunk_id: pages[chunk_id] for chunk_id in ids}

    report, radius = await select_navigation_pages("What does orbital eccentricity describe?", (first,), expand, load)
    assert expanded == [((first,), 2)] and radius == 2
    assert loaded == [{first.chunk_id}, {neighbor.chunk_id}]
    assert len(report.selections) == 2
    assert any(item.source.chunk_id == neighbor.chunk_id for item in report.selections)
    for item in report.selections:
        assert item.source_kind == "canonical_page"
        assert item.quote == pages[item.source.chunk_id][item.start_offset:item.end_offset]
        assert 0 < len(item.quote) <= 480


async def test_neighbor_chunk_budget_cannot_displace_available_anchor_page_context():
    first = chunk("Orbital mechanics is discussed here.")
    canonical = "Orbital mechanics\nAn orbit follows an elliptical path.\n" + "More lecture detail. " * 38
    assert estimate_tokens(canonical) > 142
    neighbors = tuple(replace(chunk("Orbital mechanics appears nearby.", page=2,
                                    document_id=first.document_id),
                              content_revision_id=first.content_revision_id,
                              token_count=500, fusion_score=0.0)
                      for _ in range(20))
    calls = []

    async def expand(anchors, radius, max_chunks, max_pages, max_tokens):
        calls.append((anchors, radius))
        return tuple(ExpandedKnowledgeNeighbor(item, first.chunk_id, 1) for item in neighbors)

    async def load(ids, max_pages, max_tokens):
        return ({first.chunk_id: canonical} if first.chunk_id in ids
                and estimate_tokens(canonical) <= max_tokens else {})

    report, radius = await select_navigation_pages(
        "What does orbital mechanics describe?", (first,), expand, load,
    )
    assert calls == [((first,), 2)] and radius == 2
    assert report.examined_chunks <= MAX_NAVIGATION_CHUNKS
    assert report.examined_pages <= MAX_NAVIGATION_PAGES
    assert report.examined_tokens <= MAX_NAVIGATION_TOKENS
    anchor = next(item for item in report.selections if item.source.chunk_id == first.chunk_id)
    assert anchor.source_kind == "canonical_page"
    assert anchor.quote == canonical[anchor.start_offset:anchor.end_offset]
    assert anchor.quote.startswith("Orbital mechanics")


async def test_navigation_deduplicates_pages_caps_three_and_does_not_certify_sufficiency():
    first = chunk("Spectral index is mentioned in this introduction.")
    same = replace(first, chunk_id=uuid4())
    others = tuple(chunk("Spectral index appears on this page.", page=number) for number in range(2, 7))

    async def expand(*args):
        return ()

    async def load(ids, *_bounds):
        return {item.chunk_id: item.content for item in (first, same, *others) if item.chunk_id in ids}

    report, _radius = await select_navigation_pages("Explain spectral index", (first, same, *others), expand, load)
    assert len(report.selections) == 3 and report.status == "related_pages"
    assert len({(item.source.document_id, item.source.page_number) for item in report.selections}) == 3


async def test_unrelated_high_search_rank_cannot_create_navigation_reference():
    unrelated = chunk("A telescope records images of distant stars.")
    unrelated = replace(unrelated, fusion_score=1.0, vector_similarity=1.0)

    async def expand(*args):
        return ()

    async def load(ids, *_bounds):
        return {unrelated.chunk_id: unrelated.content}

    report, _radius = await select_navigation_pages("Define neural token embeddings", (unrelated,), expand, load)
    assert report.selections == () and report.status == "no_candidate"


async def test_metadata_only_topic_hit_cannot_create_unrelated_preview():
    unrelated = replace(chunk("A telescope records images of distant stars."), section="Token embeddings")

    async def expand(*args):
        return ()

    async def load(*args):
        return {unrelated.chunk_id: unrelated.content}

    report, _radius = await select_navigation_pages("Define token embeddings", (unrelated,), expand, load)
    assert report.selections == ()


async def test_conflicting_canonical_copies_suppress_the_entire_page():
    first = chunk("Orbital eccentricity is discussed here.")
    other = replace(first, chunk_id=uuid4())

    async def expand(*args):
        return ()

    async def load(*args):
        return {first.chunk_id: "Orbital eccentricity explains elongated orbits.",
                other.chunk_id: "Orbital eccentricity has different content."}

    report, _radius = await select_navigation_pages("orbital eccentricity", (first, other), expand, load)
    assert report.selections == ()


async def test_navigation_keeps_one_cumulative_chunk_page_and_canonical_token_budget():
    initial = tuple(replace(chunk("orbital topic", page=number), token_count=500) for number in range(1, 21))
    extra = tuple(replace(chunk("orbital neighbor", page=number), token_count=500,
                          vector_rank=None, lexical_rank=None, fusion_score=0.0) for number in range(21, 61))

    async def expand(anchors, *_bounds):
        return tuple(ExpandedKnowledgeNeighbor(item, anchors[0].chunk_id, 1) for item in extra)

    async def load(ids, *_bounds):
        return {item.chunk_id: "orbital " * 5_000 for item in (*initial, *extra) if item.chunk_id in ids}

    report, _radius = await select_navigation_pages("orbital topic", initial, expand, load)
    assert report.examined_chunks <= MAX_NAVIGATION_CHUNKS
    assert report.examined_pages <= MAX_NAVIGATION_PAGES
    assert report.examined_tokens <= MAX_NAVIGATION_TOKENS
    assert len(report.selections) <= 3
    assert all(item.source_kind == "chunk" for item in report.selections)


def test_lexical_fallback_sql_retains_authorized_current_scope_without_vector():
    sql = str(_LEXICAL_ONLY_SQL)
    assert "query_embedding" not in sql and "<=>" not in sql
    assert "principal.role = 'INSTRUCTOR'" in sql
    assert "principal.role = 'STUDENT'" in sql and "enrollments" in sql
    assert "subject.corpus_revision = :corpus_revision" in sql
    assert "subject.active_embedding_space_hash = :embedding_space_hash" in sql
    assert "eligible_subject_knowledge_chunks" in sql
    assert "eligible.corpus_revision = :corpus_revision" in sql
    assert "eligible.embedding_space_hash = :embedding_space_hash" in sql
    assert "eligible.document_id = ANY(:document_ids)" in sql
    assert "websearch_to_tsquery" in sql and "concat_ws(' ', eligible.section, eligible.content)" in sql


async def test_lexical_fallback_is_policy_fenced_and_rechecks_scope():
    scope = AuthorizedKnowledgeScope(uuid4(), uuid4(), 7, "a" * 64, ())
    queries = []

    class Result:
        def mappings(self):
            return self

        def all(self):
            return []

    class DB:
        async def execute(self, statement, values):
            queries.append(values)
            return Result()

    retriever = KnowledgeRetriever(DB(), scope=scope, query="What does BLEU mean?",
                                   limit=20, policy=SOURCE_NAVIGATION_RETRIEVAL_POLICY)
    with pytest.raises(KnowledgeScopeUnavailable):
        await retriever.retrieve_lexical()
    assert queries[0]["lexical_query"] == "bleu OR mean"
    assert queries[0]["corpus_revision"] == 7 and queries[0]["embedding_space_hash"] == "a" * 64
    retriever.policy = replace(SOURCE_NAVIGATION_RETRIEVAL_POLICY, policy_id="hybrid_source_sufficiency_v7")
    with pytest.raises(InvalidKnowledgeRetrievalRequest):
        await retriever.retrieve_lexical()
    assert len(queries) == 1
