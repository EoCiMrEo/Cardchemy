"""Exact, bounded excerpts are browsing aids, never verified claims."""

from uuid import uuid4

from app.ai.related_evidence import (
    local_followup_query,
    select_related_excerpts,
    select_source_first_excerpts,
)
from app.services.knowledge_retrieval import RetrievedKnowledgeChunk


def _chunk(content: str, *, page: int = 1, document_id=None) -> RetrievedKnowledgeChunk:
    return RetrievedKnowledgeChunk(
        chunk_id=uuid4(), document_id=document_id or uuid4(),
        document_title="Lecture", content_revision_id=uuid4(),
        index_revision_id=uuid4(), page_number=page, section="Section",
        content=content, token_count=50, embedding_space_hash="a" * 64,
        corpus_revision=1, vector_similarity=.8, lexical_score=None,
        vector_rank=1, lexical_rank=None, fusion_score=.02,
    )


def test_selector_keeps_exact_bounds_and_prefers_question_terms():
    content = "A general introduction.\n" + "Noise. " * 65 + "\nBLEU uses n-grams in translation evaluation.\nAfterword."
    source = _chunk(content)
    selected = select_related_excerpts("What does BLEU use?", (source,))
    assert len(selected) == 1
    item = selected[0]
    assert 0 <= item.start_offset < item.end_offset <= len(content)
    assert len(item.quote) <= 480
    assert item.quote == content[item.start_offset:item.end_offset]
    assert "BLEU" in item.quote


def test_selector_caps_two_distinct_pages_and_ignores_empty():
    document_id = uuid4()
    first = _chunk("First fact.", page=1, document_id=document_id)
    same_page = _chunk("Duplicate page fact.", page=1, document_id=document_id)
    second = _chunk("Second fact.", page=2, document_id=document_id)
    third = _chunk("Third fact.", page=3, document_id=document_id)
    empty = _chunk(" \n\t", page=4, document_id=document_id)
    selected = select_related_excerpts("Unrelated question", (empty, first, same_page, second, third))
    assert [item.source for item in selected] == [first, second]
    assert all(item.quote.strip() for item in selected)


def test_selector_does_not_claim_answerability():
    source = _chunk("Possibly related context that does not answer this question.")
    selected = select_related_excerpts("What is the exact answer?", (source,))
    assert len(selected) == 1
    assert selected[0].quote in source.content


def test_source_first_returns_three_distinct_exact_source_windows():
    document_id = uuid4()
    chunks = (
        _chunk("BLEU compares translated text with a reference.", page=1, document_id=document_id),
        _chunk("BLEU uses n-grams from a reference translation.", page=2, document_id=document_id),
        _chunk("BLEU uses reference translation matching.", page=3, document_id=document_id),
        _chunk("BLEU compares a reference translation.", page=4, document_id=document_id),
    )
    selected = select_source_first_excerpts("How does BLEU use a reference translation?", chunks)
    assert len(selected) == 3
    assert len({(item.source.document_id, item.source.page_number) for item in selected}) == 3
    assert all(item.quote == item.source.content[item.start_offset:item.end_offset] for item in selected)
    assert all(0 < len(item.quote) <= 480 for item in selected)


def test_source_first_does_not_return_merely_top_ranked_irrelevant_page():
    unrelated = _chunk("BLEU is a translation evaluation metric.")
    assert select_source_first_excerpts("How many moons does BLEU have?", (unrelated,)) == ()


def test_source_first_locally_resolves_single_explicit_prior_referent():
    history = (("user", "What does BLEU measure in translation?"),)
    assert local_followup_query("What does it stand for?", history) == "BLEU"
    selected = select_source_first_excerpts(
        "What does it stand for?",
        (_chunk("BLEU means Bilingual Evaluation Understudy."),),
        history=history,
    )
    assert len(selected) == 1
    assert "Bilingual Evaluation Understudy" in selected[0].quote


def test_source_first_unresolved_referent_requires_clarification():
    assert local_followup_query("What does it stand for?", ()) is None
    assert local_followup_query(
        "What does it stand for?", (("user", "Compare BLEU and ROUGE."),)
    ) is None
    assert select_source_first_excerpts(
        "What does it stand for?", (_chunk("BLEU is a metric."),)
    ) == ()


def test_source_first_explicit_subject_remains_direct_even_with_pronoun():
    assert local_followup_query("Does BLEU lose its meaning?", ()) == "Does BLEU lose its meaning?"
