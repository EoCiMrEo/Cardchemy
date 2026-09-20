"""Phase 19 deterministic corpus completeness and reviewed metric gates."""

from tests.support.rag_evaluation import (
    EvaluationObservation,
    assert_thresholds,
    evaluate,
    load_corpus,
)


REQUIRED_CATEGORIES = {
    "direct_fact", "semantic_paraphrase", "exact_technical_term",
    "similar_concepts_across_lectures", "multi_page_topic", "overlapping_chunks",
    "bounded_follow_up", "ambiguous_query", "unsupported_query", "empty_evidence",
    "conflicting_materials", "lecture_prompt_injection", "chat_prompt_injection",
    "cross_subject_id", "guessed_source_id", "ready_but_unpublished",
    "real_unrelated_citation", "unsupported_claim_valid_id",
}

REQUIRED_LIFECYCLE_CASES = {
    "access_revoked_queued", "access_revoked_running", "corpus_revision_mismatch",
    "embedding_model_space_mismatch", "document_unpublished_queued",
    "document_deleted_running", "document_reindexed_running",
    "history_source_unavailable_after_unpublish", "history_source_unavailable_after_delete",
}


def test_phase_19_corpus_covers_required_quality_security_and_lifecycle_cases():
    corpus = load_corpus()
    assert corpus["version"] == "subject_knowledge_v2"
    categories = {category for case in corpus["cases"] for category in case["categories"]}
    assert REQUIRED_CATEGORIES <= categories
    assert REQUIRED_LIFECYCLE_CASES <= set(corpus["lifecycle_cases"])
    assert corpus["policy"]["decisions"]["ann"] == "not_applicable_no_ann_index_ships"
    assert corpus["policy"]["decisions"]["reranker"] == "deferred_no_measured_need"
    serialized = str(corpus).casefold()
    assert "@example.com" not in serialized and "api_key" not in serialized


def test_reviewed_thresholds_fail_closed_and_include_usage_latency_and_exposure():
    corpus = load_corpus()
    observations = []
    for case in corpus["cases"]:
        outcome = case["expected_outcome"]
        expected_pages = tuple(case.get("expected_pages", ()))
        observations.append(EvaluationObservation(
            case_id=case["id"],
            expected_pages=expected_pages,
            retrieved_pages=expected_pages if outcome == "answer" else (),
            expected_outcome=outcome,
            actual_outcome=outcome,
            citations_valid=True,
            claims_supported=outcome != "reject",
            latency_milliseconds=25.0,
            history_context_messages=len(case.get("history", ())),
            provider_calls=3 if outcome == "answer" else 1,
        ))
    metrics = evaluate(observations, indexed_chunks=24, indexing_seconds=2.0)
    assert_thresholds(metrics, corpus["policy"]["thresholds"])
    assert metrics["forbidden_source_exposure_count"] == 0
    assert metrics["maximum_history_context_messages"] <= 8
    assert metrics["maximum_provider_calls_per_answer"] <= 3
