"""Public synthetic controls for exact canonical-page evidence units."""

from dataclasses import replace

import pytest

from app.ai.chunking import estimate_tokens
from app.ai.related_evidence import RelatedExcerptSelection
from app.ai.source_sufficiency import (
    MAX_EXAMINED_TOKENS, describe_question, qualify_with_neighbors,
    rank_sufficient_sources,
)
from app.services.knowledge_retrieval import ExpandedKnowledgeNeighbor
from tests.test_source_sufficiency import chunk


@pytest.mark.parametrize(("question", "heading", "body"), [
    ("What does BLEU stand for?", "BLEU", "- Stands for Bilingual Evaluation Understudy."),
    ("What is tokenization?", "Tokenization", "- Is splitting text into separate tokens."),
    ("How does Logistic Regression work?", "Logistic Regression",
     "- Uses the sigmoid function to output probabilities."),
    ("What does cosine similarity measure between vectors?", "Cosine similarity",
     "- Measures the angle between vectors."),
    ("Why does stemming use suffixes?", "Stemming",
     "- Uses suffixes because related word forms can share a root."),
    ("What are the steps in text normalization?", "Text normalization",
     "1. Lowercase the text\n2. Remove punctuation from text"),
    ("What information does BOW lose?", "BOW", "- Loses word order information."),
    ("Give an application of LDA in news analysis.", "LDA",
     "Applications\n- Clustering news documents for analysis."),
])
def test_heading_loss_uses_exact_current_page_for_all_relation_families(question, heading, body):
    anchor = replace(chunk(body), section=heading)
    page = "Prior material.\n\n" + heading + "\n" + body + "\n\nNext topic"
    descriptor = describe_question(question)
    assert rank_sufficient_sources(descriptor, (anchor,)).selections == ()
    report = rank_sufficient_sources(descriptor, (anchor,), {anchor.chunk_id: page})
    assert report.selections
    selected = report.selections[0]
    assert selected.source is anchor and selected.source.content == body
    assert selected.source_kind == "canonical_page"
    assert selected.quote == heading + "\n" + body
    assert selected.quote == page[selected.start_offset:selected.end_offset]
    assert len(selected.quote) <= 480
    assert report.examined_tokens == anchor.token_count + estimate_tokens(page)


def test_whitespace_only_alignment_preserves_original_page_offsets_and_spacing():
    body = "- Stands for Bilingual Evaluation Understudy."
    anchor = replace(chunk(body), section="BLEU")
    page = "BLEU\n  - Stands\tfor Bilingual   Evaluation Understudy.\n"
    report = rank_sufficient_sources(describe_question("What does BLEU stand for?"),
                                     (anchor,), {anchor.chunk_id: page})
    assert report.selections[0].quote == page.rstrip()
    assert "\t" in report.selections[0].quote
    assert "   " in report.selections[0].quote


@pytest.mark.parametrize("page", [
    "BLEU\n- Is a metric.\nROUGE\n- Stands for Bilingual Evaluation Understudy.",
    "BLEU\n- Stands for Bilingual Evaluation Understudy.\nBLEU\n- Stands for Bilingual Evaluation Understudy.",
    "BLEU\n- Stands for Bilingual Evaluation Understudy Extra.",
    "Wrong Heading\n- Stands for Bilingual Evaluation Understudy.",
    "BLEU\n- ROUGE stands for Bilingual Evaluation Understudy.",
])
def test_wrong_owner_ambiguous_or_changed_body_does_not_gain_primary(page):
    anchor = replace(chunk("- Stands for Bilingual Evaluation Understudy."), section="BLEU")
    report = rank_sufficient_sources(describe_question("What does BLEU stand for?"),
                                     (anchor,), {anchor.chunk_id: page})
    assert report.selections == ()


def test_unknown_and_partial_evidence_remain_without_primary_on_canonical_pages():
    anchor = replace(chunk("- Is an evaluation metric."), section="BLEU")
    page = "BLEU\n" + anchor.content
    for question in ("What does BLEU stand for?", "What does BLEU stand for and how does it work?"):
        report = rank_sufficient_sources(describe_question(question), (anchor,),
                                         {anchor.chunk_id: page})
        assert report.selections == ()


def test_page_content_is_counted_once_for_multiple_anchors_and_no_overbudget_scan():
    first = replace(chunk("- Is an evaluation metric."), section="BLEU")
    second = replace(first, chunk_id=chunk("x").chunk_id)
    page = "BLEU\n" + first.content
    descriptor = describe_question("What does BLEU stand for?")
    report = rank_sufficient_sources(descriptor, (first, second),
                                     {first.chunk_id: page, second.chunk_id: page})
    assert report.examined_tokens == first.token_count + second.token_count + estimate_tokens(page)
    assert report.examined_pages == 1 and report.examined_chunks == 2
    huge = "BLEU\n- Stands for Bilingual Evaluation Understudy.\n" + "x" * (MAX_EXAMINED_TOKENS * 3)
    report = rank_sufficient_sources(descriptor, (first,), {first.chunk_id: huge})
    assert report.selections == () and report.examined_tokens == first.token_count


def test_page_mode_never_falls_back_to_chunk_when_page_is_missing_or_unproven():
    source = chunk("BLEU stands for Bilingual Evaluation Understudy.")
    descriptor = describe_question("What does BLEU stand for?")
    assert rank_sufficient_sources(descriptor, (source,)).selections
    assert rank_sufficient_sources(descriptor, (source,), {}).selections == ()
    assert rank_sufficient_sources(
        descriptor, (source,), {source.chunk_id: "Different canonical page."},
    ).selections == ()


@pytest.mark.asyncio
async def test_page_loader_omission_cannot_publish_chunk_primary():
    source = chunk("BLEU stands for Bilingual Evaluation Understudy.")

    async def no_pages(_ids, _max_pages, _max_tokens):
        return {}

    async def no_neighbors(_anchors, _radius, _max_chunks, _max_pages, _max_tokens):
        return ()

    report, _ = await qualify_with_neighbors(
        describe_question("What does BLEU stand for?"), (source,), no_neighbors, no_pages,
    )
    assert report.selections == ()


@pytest.mark.asyncio
async def test_canonical_pages_and_chunk_union_are_counted_across_neighbor_radii():
    first = replace(chunk("- Is an evaluation metric."), section="BLEU", token_count=100)
    neighbor = replace(first, chunk_id=chunk("x").chunk_id, page_number=2)
    page = "BLEU\n" + first.content
    calls = []

    async def load_pages(ids, max_pages, max_tokens):
        calls.append((ids, max_pages, max_tokens))
        return {identity: page for identity in ids}

    async def expand(_anchors, radius, _max_chunks, _max_pages, _max_tokens):
        return (ExpandedKnowledgeNeighbor(neighbor, first.chunk_id, radius),)

    report, radius = await qualify_with_neighbors(
        describe_question("What does BLEU stand for?"), (first,), expand, load_pages,
    )
    assert radius == 2 and report.selections == ()
    assert len(calls) == 2
    assert report.examined_chunks == 2 and report.examined_pages == 2
    assert report.examined_tokens == 200 + 2 * estimate_tokens(page)
    assert calls[1][2] == MAX_EXAMINED_TOKENS - 200 - estimate_tokens(page)


def test_page_selection_never_substitutes_metadata_into_chunk_content():
    anchor = chunk("literal body")
    selected = RelatedExcerptSelection(anchor, 0, 7, "canonical_page", "literal page")
    assert selected.quote == "literal" and anchor.content == "literal body"
    with pytest.raises(ValueError, match="unavailable"):
        RelatedExcerptSelection(anchor, 0, 7, "canonical_page").quote
