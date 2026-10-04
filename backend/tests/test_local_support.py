import os
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from app.ai.answering import ValidatedAnswerClaim
from app.ai.local_support import (
    LocalSupportUnavailable,
    LocalSupportVerifier,
    LocalSupportVerifierV2,
    LocalSupportVerifierV3,
    NliScores,
    OnnxNliScorer,
    create_local_support_verifier,
)
from app.services.knowledge_retrieval import RetrievedKnowledgeChunk


QUOTE = "Perihelion is the point of an orbit nearest to the Sun."
STATEMENT = "Perihelion is the nearest orbital point to the Sun."
REAL_MODEL_DIR = os.getenv("CARDCH_LOCAL_SUPPORT_MODEL_DIR")


def _chunk(content: str = QUOTE) -> RetrievedKnowledgeChunk:
    return RetrievedKnowledgeChunk(
        chunk_id=uuid4(), document_id=uuid4(), document_title="Orbital mechanics",
        content_revision_id=uuid4(), index_revision_id=uuid4(), page_number=1,
        section="Apsides", content=content, token_count=20,
        embedding_space_hash="a" * 64, corpus_revision=1,
        vector_similarity=1.0, lexical_score=1.0, vector_rank=1,
        lexical_rank=1, fusion_score=1.0,
    )


def _claim(chunk: RetrievedKnowledgeChunk, statement: str = STATEMENT) -> ValidatedAnswerClaim:
    return ValidatedAnswerClaim(statement=statement, source=chunk, source_quote=QUOTE)


class StubNli:
    def __init__(self, score):
        self._score = score

    def score(self, premise: str, hypothesis: str) -> NliScores:
        return self._score(premise, hypothesis) if callable(self._score) else self._score


class StubQa:
    def __init__(self, answer: str | None):
        self._answer = answer

    def answer(self, _question: str, _context: str) -> str | None:
        return self._answer


class DefinitionQa:
    def answer(self, _question: str, context: str) -> str | None:
        if context == "Perihelion is the point in an orbit nearest the Sun.":
            return "the point in an orbit nearest the Sun"
        if context == STATEMENT:
            return "the nearest orbital point to the Sun"
        return None


@pytest.mark.parametrize("statement", [STATEMENT, "The nearest orbital point is called perihelion."])
def test_local_support_accepts_direct_and_paraphrased_claims(statement):
    chunk = _chunk()
    verifier = LocalSupportVerifier(
        StubNli(NliScores(contradiction=0.02, entailment=0.96, neutral=0.02)),
        StubQa("Perihelion"),
    )
    assert verifier.supports(
        question="What is the nearest orbital point to the Sun?",
        claims=(_claim(chunk, statement),), chunks=(chunk,),
    )


@pytest.mark.parametrize("reverse_entailment,expected", [(0.96, True), (0.60, False)])
def test_definition_paraphrase_requires_bidirectional_answer_span_support(reverse_entailment, expected):
    quote = "Perihelion is the point in an orbit nearest the Sun."
    chunk = _chunk(quote)
    claim = ValidatedAnswerClaim(statement=STATEMENT, source=chunk, source_quote=quote)

    def score(premise, hypothesis):
        if premise == "the nearest orbital point to the Sun" and hypothesis == "the point in an orbit nearest the Sun":
            return NliScores(contradiction=0.01, entailment=reverse_entailment, neutral=0.99 - reverse_entailment)
        return NliScores(contradiction=0.01, entailment=0.96, neutral=0.03)

    verifier = LocalSupportVerifier(StubNli(score), DefinitionQa())
    assert verifier.supports(question="What is perihelion?", claims=(claim,), chunks=(chunk,)) is expected


@pytest.mark.parametrize(
    "scores",
    [
        NliScores(contradiction=0.05, entailment=0.30, neutral=0.65),
        NliScores(contradiction=0.85, entailment=0.10, neutral=0.05),
        NliScores(contradiction=0.10, entailment=0.79, neutral=0.11),
    ],
)
def test_local_support_rejects_neutral_contradicted_or_below_threshold_claims(scores):
    chunk = _chunk()
    verifier = LocalSupportVerifier(StubNli(scores), StubQa("Perihelion"))
    assert not verifier.supports(question="What is perihelion?", claims=(_claim(chunk),), chunks=(chunk,))


@pytest.mark.parametrize("answer", [None, "of an orbit", "   "])
def test_local_support_rejects_missing_or_unbound_question_answer_span(answer):
    chunk = _chunk()
    verifier = LocalSupportVerifier(
        StubNli(NliScores(contradiction=0.01, entailment=0.98, neutral=0.01)),
        StubQa(answer),
    )
    assert not verifier.supports(question="What is perihelion?", claims=(_claim(chunk),), chunks=(chunk,))


def test_local_support_rejects_conflicting_retrieved_evidence():
    chunk = _chunk(f"{QUOTE} Perihelion is the point farthest from the Sun.")

    def score(premise, _hypothesis):
        if "farthest" in premise:
            return NliScores(contradiction=0.91, entailment=0.04, neutral=0.05)
        return NliScores(contradiction=0.01, entailment=0.98, neutral=0.01)

    verifier = LocalSupportVerifier(StubNli(score), StubQa("Perihelion"))
    assert not verifier.supports(question="What is perihelion?", claims=(_claim(chunk),), chunks=(chunk,))


def _acronym_case(extra: str = ""):
    quote = "TULA stands for Tidal Unit Localization Algorithm."
    source = replace(
        _chunk(f"## TULA\n- {quote}\n{extra}"), section="TULA",
    )
    claim = ValidatedAnswerClaim(statement=quote, source=source, source_quote=quote)

    def score(premise: str, _hypothesis: str) -> NliScores:
        if premise == quote:
            return NliScores(contradiction=0.01, entailment=0.98, neutral=0.01)
        # Deliberately model a false NLI contradiction on an unrelated
        # fictional topic and a true contradiction on a wrong expansion.
        if "MERA" in premise or "Temporal Utility" in premise or premise.startswith("It "):
            return NliScores(contradiction=0.96, entailment=0.02, neutral=0.02)
        return NliScores(contradiction=0.01, entailment=0.98, neutral=0.01)

    return source, claim, StubNli(score), StubQa("TULA")


def test_v2_scopes_explicit_independent_heading_and_bullet_without_weakening_support():
    source, claim, nli, qa = _acronym_case(
        "## MERA\n- MERA measures recall against a reference."
    )
    question = "What does TULA stand for?"
    assert not LocalSupportVerifier(nli, qa).supports(
        question=question, claims=(claim,), chunks=(source,),
    )
    assert LocalSupportVerifierV2(nli, qa).supports(
        question=question, claims=(claim,), chunks=(source,),
    )
    assert not LocalSupportVerifierV2(nli, StubQa(None)).supports(
        question=question, claims=(claim,), chunks=(source,),
    )


@pytest.mark.parametrize(
    "extra",
    [
        "- TULA stands for Temporal Utility Learning Architecture.",
        "## MERA\n- TULA stands for Temporal Utility Learning Architecture.",
        "## MERA\n- It stands for Temporal Utility Learning Architecture.",
        "- Temporal Utility Learning Architecture should be used.",
    ],
)
def test_v2_keeps_same_topic_cross_heading_and_anaphoric_conflicts(extra):
    source, claim, nli, qa = _acronym_case(extra)
    verdict = LocalSupportVerifierV2(nli, qa).evaluate(
        question="What does TULA stand for?", claims=(claim,), chunks=(source,),
    )
    assert verdict.reason_code == "contradiction_detected"


def test_v2_keeps_cross_source_same_topic_conflicts():
    source, claim, nli, qa = _acronym_case()
    other = replace(
        _chunk("- TULA stands for Temporal Utility Learning Architecture."), section="TULA",
    )
    verdict = LocalSupportVerifierV2(nli, qa).evaluate(
        question="What does TULA stand for?", claims=(claim,), chunks=(source, other),
    )
    assert verdict.reason_code == "contradiction_detected"


def test_v2_does_not_dismiss_same_heading_ancillary_false_conflict():
    source, claim, nli, qa = _acronym_case(
        "- Bigrams compare pairs of adjacent words."
    )

    def score(premise: str, hypothesis: str) -> NliScores:
        if premise.startswith("Bigrams"):
            return NliScores(contradiction=0.96, entailment=0.02, neutral=0.02)
        return nli.score(premise, hypothesis)

    # Without an independently headed subject, this remains unresolved and
    # fails closed even when a smaller model is confidently wrong.
    verdict = LocalSupportVerifierV2(StubNli(score), qa).evaluate(
        question="What does TULA stand for?", claims=(claim,), chunks=(source,),
    )
    assert verdict.reason_code == "contradiction_detected"


def test_v3_accepts_exact_acronym_sentence_when_qa_misses_and_ancillary_fact_is_independent():
    source, claim, _nli, _qa = _acronym_case(
        "- TULA measures relative tidal movement."
    )

    def score(premise: str, _hypothesis: str) -> NliScores:
        if "measures" in premise:
            # Characterize the pinned NLI model's observed false conflict on
            # a different same-topic proposition.
            return NliScores(contradiction=0.96, entailment=0.02, neutral=0.02)
        return NliScores(contradiction=0.01, entailment=0.98, neutral=0.01)

    verifier = LocalSupportVerifierV3(StubNli(score), StubQa(None))
    assert verifier.evaluate(
        question="What does TULA stand for?", claims=(claim,), chunks=(source,),
    ).reason_code == "supported"
    assert LocalSupportVerifierV2(StubNli(score), StubQa(None)).evaluate(
        question="What does TULA stand for?", claims=(claim,), chunks=(source,),
    ).reason_code == "question_relevance_rejected"


@pytest.mark.parametrize("question", [
    "What does MERA stand for?",
    "What does TULA not stand for?",
    "What does it stand for?",
    "What does this method stand for?",
    "Does TULA stand for Tidal Unit Localization Algorithm?",
])
def test_v3_exact_fallback_rejects_wrong_or_non_direct_question(question):
    source, claim, nli, _qa = _acronym_case()
    assert LocalSupportVerifierV3(nli, StubQa(None)).evaluate(
        question=question, claims=(claim,), chunks=(source,),
    ).reason_code == "question_relevance_rejected"


@pytest.mark.parametrize("quote", [
    "It is false that TULA stands for Tidal Unit Localization Algorithm.",
    "TULA stands for Tidal Unit Localization Algorithm, but this expansion is obsolete.",
    "TULA stands for Tidal Unit Localization Algorithm?",
    "TULA stands for Tidal Unit Localization Algorithm. This is false.",
    "TULA means Tidal Unit Localization Algorithm.",
])
def test_v3_exact_fallback_rejects_non_atomic_or_paraphrased_source(quote):
    source = replace(_chunk(quote), section="TULA")
    claim = ValidatedAnswerClaim(statement="TULA stands for Tidal Unit Localization Algorithm.",
                                 source=source, source_quote=quote)
    verifier = LocalSupportVerifierV3(
        StubNli(NliScores(contradiction=0.01, entailment=0.98, neutral=0.01)),
        StubQa(None),
    )
    assert verifier.evaluate(
        question="What does TULA stand for?", claims=(claim,), chunks=(source,),
    ).reason_code == "question_relevance_rejected"


def test_v3_exact_fallback_rejects_unsupported_acronym_claim_with_caveat():
    quote = "TULA stands for Tidal Unit Localization Algorithm, which is false."
    source = replace(_chunk(quote), section="TULA")
    claim = ValidatedAnswerClaim(statement=quote, source=source, source_quote=quote)
    verifier = LocalSupportVerifierV3(
        StubNli(NliScores(contradiction=0.01, entailment=0.98, neutral=0.01)),
        StubQa(None),
    )
    assert verifier.evaluate(
        question="What does TULA stand for?", claims=(claim,), chunks=(source,),
    ).reason_code == "question_relevance_rejected"


@pytest.mark.parametrize("extra", [
    "- TULA stands for Temporal Utility Learning Architecture.",
    "- TULA does not stand for Tidal Unit Localization Algorithm.",
    "- TULA measures waves, but does not stand for Tidal Unit Localization Algorithm.",
    "## MERA\n- TULA stands for Temporal Utility Learning Architecture.",
])
def test_v3_keeps_same_proposition_and_mixed_sentence_conflicts(extra):
    source, claim, _nli, _qa = _acronym_case(extra)

    def score(premise: str, _hypothesis: str) -> NliScores:
        if "Temporal Utility" in premise or "does not stand for" in premise:
            return NliScores(contradiction=0.96, entailment=0.02, neutral=0.02)
        return NliScores(contradiction=0.01, entailment=0.98, neutral=0.01)

    verdict = LocalSupportVerifierV3(StubNli(score), StubQa(None)).evaluate(
        question="What does TULA stand for?", claims=(claim,), chunks=(source,),
    )
    assert verdict.reason_code == "contradiction_detected"


def test_v3_does_not_scope_a_paraphrased_wrong_claim_away_from_conflict():
    source, _claim_original, nli, _qa = _acronym_case(
        "- TULA measures relative tidal movement."
    )
    wrong = ValidatedAnswerClaim(
        statement="TULA stands for Temporal Utility Learning Architecture.",
        source=source,
        source_quote="TULA stands for Tidal Unit Localization Algorithm.",
    )
    assert LocalSupportVerifierV3(nli, StubQa(None)).evaluate(
        question="What does TULA stand for?", claims=(wrong,), chunks=(source,),
    ).reason_code == "question_relevance_rejected"


def test_local_support_rejects_empty_claims_or_chunks():
    verifier = LocalSupportVerifier(
        StubNli(NliScores(contradiction=0.01, entailment=0.98, neutral=0.01)),
        StubQa("Perihelion"),
    )
    chunk = _chunk()
    assert not verifier.supports(question="What is perihelion?", claims=(), chunks=(chunk,))
    assert not verifier.supports(question="What is perihelion?", claims=(_claim(chunk),), chunks=())


def test_local_support_verdict_exposes_only_fixed_check_outcomes():
    chunk = _chunk()
    supported = LocalSupportVerifier(
        StubNli(NliScores(contradiction=0.01, entailment=0.98, neutral=0.01)),
        StubQa("Perihelion"),
    ).evaluate(
        question="What is perihelion?", claims=(_claim(chunk),), chunks=(chunk,),
    )
    assert (
        supported.supported, supported.reason_code, supported.entailment,
        supported.question_relevance, supported.equivalence, supported.contradiction,
    ) == (True, "supported", "pass", "pass", "not_required", "pass")

    no_answer = LocalSupportVerifier(
        StubNli(NliScores(contradiction=0.01, entailment=0.98, neutral=0.01)),
        StubQa(None),
    ).evaluate(
        question="What is perihelion?", claims=(_claim(chunk),), chunks=(chunk,),
    )
    assert (
        no_answer.supported, no_answer.reason_code, no_answer.entailment,
        no_answer.question_relevance, no_answer.equivalence, no_answer.contradiction,
    ) == (False, "question_relevance_rejected", "pass", "fail", "not_run", "not_run")

    conflict_chunk = _chunk(f"{QUOTE} Perihelion is the point farthest from the Sun.")

    def conflicting_score(premise, _hypothesis):
        if "farthest" in premise:
            return NliScores(contradiction=0.91, entailment=0.04, neutral=0.05)
        return NliScores(contradiction=0.01, entailment=0.98, neutral=0.01)

    conflict = LocalSupportVerifier(StubNli(conflicting_score), StubQa("Perihelion")).evaluate(
        question="What is perihelion?", claims=(_claim(conflict_chunk),), chunks=(conflict_chunk,),
    )
    assert (
        conflict.reason_code, conflict.entailment, conflict.question_relevance,
        conflict.equivalence, conflict.contradiction,
    ) == ("contradiction_detected", "pass", "pass", "not_required", "fail")


@pytest.mark.skipif(not REAL_MODEL_DIR, reason="real local support artifacts are opt in")
def test_real_bundle_characterizes_long_bleu_question_false_rejection():
    """Authored evidence is clear, but the pinned QA model finds no answer."""

    verifier = create_local_support_verifier(Path(REAL_MODEL_DIR))
    question = (
        "What does BLEU primarily focus on when evaluating machine translation "
        "output against a reference?"
    )
    quote = (
        "BLEU primarily evaluates machine translation output by comparing "
        "n-gram overlap with reference translations."
    )
    source = _chunk(quote)
    claim = ValidatedAnswerClaim(
        statement=(
            "BLEU evaluates machine translation by measuring n-gram overlap "
            "with a reference translation."
        ),
        source=source, source_quote=quote,
    )
    assert verifier.evaluate(
        question=question, claims=(claim,), chunks=(source,),
    ).reason_code == "question_relevance_rejected"


@pytest.mark.skipif(not REAL_MODEL_DIR, reason="real local support artifacts are opt in")
def test_real_bundle_v3_scopes_only_exact_synthetic_acronym_case():
    real = create_local_support_verifier(Path(REAL_MODEL_DIR))
    source, claim, _nli, _qa = _acronym_case(
        "- TULA measures relative tidal movement."
    )
    args = {
        "question": "What does TULA stand for?",
        "claims": (claim,), "chunks": (source,),
    }
    assert real.evaluate(**args).reason_code == "contradiction_detected"
    assert LocalSupportVerifierV2(real._nli, real._qa).evaluate(
        **args,
    ).reason_code == "contradiction_detected"
    candidate = LocalSupportVerifierV3(real._nli, real._qa)
    assert candidate.evaluate(**args).reason_code == "supported"
    wrong = replace(claim, statement="TULA stands for Temporal Utility Learning Architecture.")
    assert candidate.evaluate(
        question=args["question"], claims=(wrong,), chunks=(source,),
    ).reason_code == "entailment_rejected"


@pytest.mark.parametrize(
    "values",
    [(-0.1, 1.0, 0.1), (0.0, 0.0, 0.0), (float("nan"), 0.5, 0.5)],
)
def test_nli_scores_fail_closed_on_invalid_probabilities(values):
    with pytest.raises(LocalSupportUnavailable, match="Invalid local support"):
        NliScores(*values)


def test_onnx_loader_rejects_missing_or_corrupt_artifacts_before_runtime(tmp_path):
    with pytest.raises(LocalSupportUnavailable, match="unavailable"):
        OnnxNliScorer(
            tmp_path,
            model_sha256="0" * 64,
            tokenizer_sha256="1" * 64,
        )
    (tmp_path / "model.onnx").write_bytes(b"wrong")
    (tmp_path / "tokenizer.json").write_bytes(b"wrong")
    with pytest.raises(LocalSupportUnavailable, match="digest mismatch"):
        OnnxNliScorer(
            tmp_path,
            model_sha256="0" * 64,
            tokenizer_sha256="1" * 64,
        )


def test_onnx_loader_rejects_symlinked_artifact_when_supported(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"model")
    model = tmp_path / "model.onnx"
    try:
        model.symlink_to(source)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    (tmp_path / "tokenizer.json").write_bytes(b"tokenizer")
    with pytest.raises(LocalSupportUnavailable, match="unavailable"):
        OnnxNliScorer(
            tmp_path,
            model_sha256="0" * 64,
            tokenizer_sha256="1" * 64,
        )


@pytest.mark.skipif(not REAL_MODEL_DIR, reason="real local support artifacts are opt in")
def test_real_local_support_bundle_supports_release_smoke_case():
    verifier = create_local_support_verifier(Path(REAL_MODEL_DIR))
    chunk = _chunk()
    assert verifier.supports(
        question="What is the point of an orbit nearest to the Sun called?",
        claims=(_claim(chunk),), chunks=(chunk,),
    )
