"""Keyless adversarial checks for the unshipped exact-acronym candidate."""

from dataclasses import replace
from uuid import uuid4

import pytest

from app.ai.answering import ValidatedAnswerClaim
from app.ai.extractive_support import evaluate_acronym_candidate
from app.ai.local_support import LocalSupportUnavailable, NliScores
from app.services.knowledge_retrieval import RetrievedKnowledgeChunk


QUOTE = "- TULA (Tidal Unit Localization Algorithm)"
STATEMENT = "TULA stands for Tidal Unit Localization Algorithm."
QUESTION = "What does TULA stand for?"


def _chunk(content: str = QUOTE) -> RetrievedKnowledgeChunk:
    return RetrievedKnowledgeChunk(
        chunk_id=uuid4(), document_id=uuid4(), document_title="Synthetic lecture",
        content_revision_id=uuid4(), index_revision_id=uuid4(), page_number=4,
        section="Glossary", content=content, token_count=24,
        embedding_space_hash="a" * 64, corpus_revision=7,
        vector_similarity=0.9, lexical_score=None, vector_rank=1,
        lexical_rank=None, fusion_score=0.03,
    )


class StubNli:
    def __init__(self, scores: NliScores | None = None) -> None:
        self.scores = scores or NliScores(0.01, 0.98, 0.01)

    def score(self, _premise: str, _hypothesis: str) -> NliScores:
        return self.scores


class StubQa:
    def __init__(self, answer: str | None = "TULA") -> None:
        self._answer = answer

    def answer(self, _question: str, _context: str) -> str | None:
        return self._answer


def _evaluate(
    *, question: str = QUESTION, statement: str = STATEMENT,
    quote: str = QUOTE, content: str = QUOTE,
    extra: tuple[RetrievedKnowledgeChunk, ...] = (),
    nli: StubNli | None = None, qa: StubQa | None = None,
):
    source = _chunk(content)
    claim = ValidatedAnswerClaim(statement=statement, source=source, source_quote=quote)
    return evaluate_acronym_candidate(
        question=question, claim=claim, chunks=(source, *extra),
        nli=nli or StubNli(), qa=qa or StubQa(),
    )


def test_candidate_derives_answer_from_exact_published_line():
    verdict = _evaluate()
    assert verdict.accepted and verdict.reason_code == "supported"
    assert verdict.answer == STATEMENT
    assert "Tidal" not in repr(verdict)


@pytest.mark.parametrize("quote", [
    "TULA: Tidal Unit Localization Algorithm",
    "TULA stands for Tidal Unit Localization Algorithm.",
])
def test_explicit_alternate_source_forms_remain_bounded(quote):
    assert _evaluate(quote=quote, content=quote).accepted


@pytest.mark.parametrize("statement,question,reason", [
    ("TULA stands for Temporal Utility Learning Architecture.", QUESTION, "claim_mismatch"),
    (STATEMENT, "What does MERA stand for?", "unsupported_source_relation"),
    (STATEMENT, "What does it stand for?", "unsupported_question"),
    (STATEMENT, "What does TULA not stand for?", "unsupported_question"),
    (STATEMENT, "What does TULA measure?", "unsupported_question"),
])
def test_wrong_claim_and_unrelated_question_do_not_pass(statement, question, reason):
    assert _evaluate(statement=statement, question=question).reason_code == reason


def test_unrelated_measurement_of_same_acronym_does_not_create_false_conflict():
    verdict = _evaluate(content=QUOTE + "\nTULA measures relative tidal movement.")
    assert verdict.reason_code == "supported"


@pytest.mark.parametrize("other,reason", [
    ("TULA (Temporal Utility Learning Architecture)", "conflicting_expansion"),
    ("TULA does not stand for Tidal Unit Localization Algorithm.", "ambiguous_expansion"),
    ("TULA expands to Temporal Utility Learning Architecture.", "ambiguous_expansion"),
    ("It stands for Temporal Utility Learning Architecture.", "ambiguous_expansion"),
])
def test_conflicting_or_unresolved_expansion_abstains(other, reason):
    assert _evaluate(content=QUOTE + "\n" + other).reason_code == reason


def test_cross_source_conflict_is_not_ignored():
    other = _chunk("TULA: Temporal Utility Learning Architecture")
    assert _evaluate(extra=(other,)).reason_code == "conflicting_expansion"


@pytest.mark.parametrize("quote,reason", [
    ("TULA (Tidal Unit Localization Algorithm), which is false.", "unsupported_source_relation"),
    ("TULA (Tidal Unit Localization Algorithm) is obsolete.", "unsupported_source_relation"),
    ("It is alleged that TULA (Tidal Unit Localization Algorithm).", "unsupported_source_relation"),
    ("TULA (Tidal Unit Localization Algorithm)\nTULA measures tides.", "invalid_source"),
])
def test_non_atomic_or_caveated_quote_fails_closed(quote, reason):
    assert _evaluate(quote=quote, content=quote).reason_code == reason


def test_parenthetical_one_word_gloss_is_not_treated_as_an_expansion():
    quote = "TULA (metric)"
    assert _evaluate(quote=quote, content=quote).reason_code == "unsupported_source_relation"


def test_model_scores_and_answer_span_remain_independent_requirements():
    low_nli = StubNli(NliScores(0.04, 0.30, 0.66))
    assert _evaluate(nli=low_nli).reason_code == "local_semantic_rejected"
    assert _evaluate(qa=StubQa(None)).reason_code == "local_semantic_rejected"
    assert _evaluate(qa=StubQa("unrelated phrase")).reason_code == "local_semantic_rejected"


def test_unavailable_model_does_not_turn_into_approval():
    class UnavailableNli(StubNli):
        def score(self, _premise, _hypothesis):
            raise LocalSupportUnavailable("model unavailable")

    assert _evaluate(nli=UnavailableNli()).reason_code == "local_check_unavailable"


def test_selected_source_must_be_bound_to_exact_chunk_content():
    source = _chunk()
    stale = replace(source, content="A different revision")
    claim = ValidatedAnswerClaim(STATEMENT, source, QUOTE)
    verdict = evaluate_acronym_candidate(
        question=QUESTION, claim=claim, chunks=(stale,),
        nli=StubNli(), qa=StubQa(),
    )
    assert verdict.reason_code == "invalid_source"


def test_clipped_line_cannot_hide_a_caveat_or_negation():
    verdict = _evaluate(
        quote=QUOTE,
        content=QUOTE + " is false; the proposed expansion is obsolete.",
    )
    assert verdict.reason_code == "invalid_source"


def test_no_verifier_shortcut_for_section_only_relation():
    source = replace(_chunk("The algorithm localizes tidal units."), section="TULA")
    claim = ValidatedAnswerClaim(STATEMENT, source, source.content)
    verdict = evaluate_acronym_candidate(
        question=QUESTION, claim=claim, chunks=(source,),
        nli=StubNli(), qa=StubQa(),
    )
    assert verdict.reason_code == "unsupported_source_relation"
