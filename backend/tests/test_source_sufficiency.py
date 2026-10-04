"""Public synthetic controls for source-only relation candidate selection."""

from dataclasses import replace
from uuid import uuid4

import pytest

from app.ai.source_sufficiency import (
    MAX_EXAMINED_CHUNKS,
    MAX_EXAMINED_PAGES,
    MAX_EXAMINED_TOKENS,
    MAX_INITIAL_PAGES,
    MAX_INITIAL_TOKENS,
    MAX_PARTIAL_ANCHORS,
    MAX_PARTIAL_ANCHOR_PAGES,
    MAX_PARTIAL_ANCHOR_TOKENS,
    SOURCE_SELECTION_POLICY_ID,
    describe_question,
    qualify_with_neighbors,
    rank_sufficient_sources,
    select_initial_candidate_pool,
)
from app.services.knowledge_retrieval import ExpandedKnowledgeNeighbor, RetrievedKnowledgeChunk


def chunk(content: str, *, page: int = 1, document_id=None, rank: int = 1):
    return RetrievedKnowledgeChunk(
        chunk_id=uuid4(), document_id=document_id or uuid4(),
        document_title="Synthetic", content_revision_id=uuid4(),
        index_revision_id=uuid4(), page_number=page, section=None,
        content=content, token_count=50, embedding_space_hash="a" * 64,
        corpus_revision=1, vector_similarity=.8, lexical_score=.2,
        vector_rank=rank, lexical_rank=rank, fusion_score=.02 / rank,
    )


def test_followup_keeps_acronym_expansion_relation_and_resolves_entity_locally():
    descriptor = describe_question(
        "What does it stand for?", (("user", "What does BLEU measure?"),),
    )
    assert descriptor.original_question == "What does it stand for?"
    assert descriptor.local_query == "What does BLEU stand for?"
    assert descriptor.entity == "BLEU"
    assert descriptor.relation == "acronym"
    weak = chunk("BLEU measures overlap against a reference translation.")
    strong = chunk("BLEU stands for Bilingual Evaluation Understudy.", page=2)
    report = rank_sufficient_sources(descriptor, (weak, strong))
    assert report.status == "explicit_relation_candidate"
    assert [item.source for item in report.selections] == [strong]
    assert report.partial_found


def test_ambiguous_followup_makes_no_source_selection():
    descriptor = describe_question(
        "What does it stand for?", (("user", "Compare BLEU and ROUGE."),),
    )
    assert descriptor.ambiguous and descriptor.local_query is None
    assert rank_sufficient_sources(
        descriptor, (chunk("BLEU stands for Bilingual Evaluation Understudy."),)
    ).status == "ambiguous"


@pytest.mark.parametrize(("question", "wrong", "right"), [
    (
        "What does BLEU stand for?",
        "BLEU is a translation metric. ROUGE stands for Recall-Oriented Understudy for Gisting Evaluation.",
        "BLEU stands for Bilingual Evaluation Understudy.",
    ),
    (
        "What is tokenization?",
        "Tokenization is discussed in this lecture.",
        "Tokenization is the operation of dividing text into smaller tokens.",
    ),
    (
        "What function does Logistic Regression use to output probabilities?",
        "Logistic Regression outputs probabilities. Linear Regression uses a linear function.",
        "Logistic Regression uses the sigmoid function to output probabilities.",
    ),
    (
        "What does cosine similarity measure between vectors?",
        "Cosine similarity is a metric. Euclidean distance measures distance between vectors.",
        "Cosine similarity measures the angle between vectors.",
    ),
    (
        "Why does stemming remove suffixes?",
        "Stemming is discussed because it has applications.",
        "Stemming removes suffixes because related word forms can share a root.",
    ),
    (
        "What are the steps in text normalization?",
        "Text normalization is an important topic. First tokenize the input.",
        "Text normalization steps are first lowercasing text, then removing punctuation.",
    ),
])
def test_six_relation_families_reject_topic_only_and_choose_complete_unit(question, wrong, right):
    descriptor = describe_question(question)
    assert not descriptor.ambiguous
    report = rank_sufficient_sources(descriptor, (chunk(wrong), chunk(right, page=2, rank=2)))
    assert len(report.selections) == 1
    assert report.selections[0].quote == right


def test_nonqualified_question_does_not_invent_source_relation():
    descriptor = describe_question("Tell me anything about BLEU")
    assert descriptor.ambiguous


@pytest.mark.parametrize(("question", "relation", "entity", "right", "wrong"), [
    (
        "Which concept does tokenization describe?", "definition", "tokenization",
        "Tokenization is the operation of splitting text into smaller tokens.",
        "Tokenization is mentioned in this lecture.",
    ),
    (
        "Which idea does document clustering describe?", "definition", "document clustering",
        "Document clustering is the grouping of documents by shared features.",
        "Document clustering is a technique.",
    ),
    (
        "Which task can document clustering support?", "application", "document clustering",
        "Document clustering is used for organizing search results into groups.",
        "Document clustering is described. Tokenization is used for identifying word boundaries.",
    ),
    (
        "Which activity can document clustering support in medical research?", "application", "document clustering",
        "Document clustering is used for organizing medical research documents.",
        "Document clustering is used for organizing legal research documents.",
    ),
])
def test_relation_paraphrases_separate_intent_words_from_actual_qualifiers(question, relation, entity, right, wrong):
    descriptor = describe_question(question)
    assert not descriptor.ambiguous
    assert descriptor.relation == relation and descriptor.entity == entity
    report = rank_sufficient_sources(descriptor, (chunk(wrong), chunk(right, page=2)))
    assert [item.quote for item in report.selections] == [right]


def test_coordinated_definition_application_paraphrase_stays_ambiguous():
    descriptor = describe_question("Which concept does tokenization describe and which task can it support?")
    assert descriptor.ambiguous
    assert not rank_sufficient_sources(descriptor, (
        chunk("Tokenization is the operation of splitting text into tokens."),
    )).selections
    assert not rank_sufficient_sources(descriptor, (chunk("BLEU is a metric."),)).selections


@pytest.mark.parametrize(("question", "required", "wrong"), [
    ("What is an application of document clustering in customer support?",
     {"customer", "support"},
     "Document clustering is used for categorizing customer feedback."),
    ("What is an application of document clustering for task scheduling?",
     {"task", "scheduling"},
     "Document clustering is used for organizing scheduling documents."),
    ("Which activity can document clustering support for task scheduling?",
     {"task", "scheduling"},
     "Document clustering is used for organizing scheduling documents."),
    ("Which task can document clustering support in customer support?",
     {"customer", "support"},
     "Document clustering is used for categorizing customer feedback."),
    ("What definition describes BLEU in concept learning?",
     {"concept", "learning"},
     "BLEU\n- Is a score of translation quality used in machine learning."),
    ("Which idea does BLEU describe in concept learning?",
     {"concept", "learning"},
     "BLEU\n- Is a score of translation quality used in machine learning."),
])
def test_intent_words_in_factual_suffixes_remain_required(question, required, wrong):
    descriptor = describe_question(question)
    assert required <= set(descriptor.qualifiers)
    assert not rank_sufficient_sources(descriptor, (chunk(wrong),)).selections


@pytest.mark.parametrize(("question", "relation", "entity", "source"), [
    (
        "What does BLEU primarily focus on when evaluating translation output against a reference?",
        "measurement", "BLEU",
        "BLEU focuses on n-gram precision when evaluating translation output against a reference.",
    ),
    (
        "What does Euclidean distance primarily measure between vectors?",
        "measurement", "Euclidean distance",
        "Euclidean distance measures straight-line distance between vectors.",
    ),
    (
        "How does cosine similarity measure vector direction?",
        "measurement", "cosine similarity",
        "Cosine similarity measures vector direction by the angle between vectors.",
    ),
    (
        "What does Logistic Regression use to output probabilities?",
        "mechanism", "Logistic Regression",
        "Logistic Regression uses the sigmoid function to output probabilities.",
    ),
    (
        "What does BLEU mean?",
        "acronym", "BLEU",
        "BLEU means Bilingual Evaluation Understudy.",
    ),
    (
        "What is the definition of tokenization?",
        "definition", "tokenization",
        "Tokenization is the operation of dividing text into smaller tokens.",
    ),
])
def test_existing_relation_paraphrases_keep_exact_entity(question, relation, entity, source):
    descriptor = describe_question(question)
    assert descriptor.relation == relation
    assert descriptor.entity == entity
    assert not descriptor.ambiguous
    report = rank_sufficient_sources(descriptor, (chunk(source),))
    assert [selection.quote for selection in report.selections] == [source]


def test_acronym_parenthetical_after_abbreviation_is_an_exact_source_candidate():
    descriptor = describe_question("What does BLEU stand for?")
    source = "BLEU (Bilingual Evaluation Understudy) is used in translation evaluation."
    report = rank_sufficient_sources(descriptor, (chunk(source),))
    assert [selection.quote for selection in report.selections] == [source]


def test_application_question_is_not_misclassified_as_a_definition():
    descriptor = describe_question(
        "What is an example application of topic modeling mentioned for legal or medical domains?"
    )
    assert descriptor.relation == "application"
    assert descriptor.entity == "topic modeling"
    assert not descriptor.ambiguous
    assert not rank_sufficient_sources(
        descriptor, (chunk("Topic modeling is a method for legal or medical domains."),),
    ).selections


def test_metric_property_question_is_not_misclassified_as_measurement():
    descriptor = describe_question(
        "Which similarity metric is noted for being sensitive to scale and magnitude "
        "and not ideal for sparse text vectors?"
    )
    assert descriptor.relation == "property"
    assert descriptor.entity is None
    assert not descriptor.ambiguous
    assert not rank_sufficient_sources(
        descriptor,
        (chunk("Euclidean distance measures scale and magnitude between text vectors."),),
    ).selections


def test_entity_free_measurement_requires_all_discriminators_in_one_unit():
    descriptor = describe_question(
        "Which similarity metric measures the angle between two vectors rather than their magnitude?"
    )
    assert descriptor.relation == "measurement" and descriptor.entity is None
    wrong = chunk("Euclidean similarity measures vector magnitude between vectors.")
    right = chunk(
        "Cosine similarity measures the angle between two vectors rather than their magnitude.",
        page=2, rank=2,
    )
    assert rank_sufficient_sources(descriptor, (wrong,)).selections == ()
    assert [item.source for item in rank_sufficient_sources(descriptor, (wrong, right)).selections] == [right]


@pytest.mark.parametrize(("question", "entity", "source"), [
    (
        "What limitation of Bag-of-Words and TF-IDF models means that word order is lost?",
        "Bag-of-Words and TF-IDF",
        "Bag-of-Words and TF-IDF ignore word order.",
    ),
    (
        "What is an example application of topic modeling mentioned for legal or medical domains?",
        "topic modeling",
        "Topic modeling is used for clustering legal documents.",
    ),
    (
        "Which similarity metric is noted for being sensitive to scale and magnitude and not ideal "
        "for sparse, high-dimensional text vectors?",
        None,
        "Euclidean similarity is sensitive to scale and magnitude and not ideal for sparse, "
        "high-dimensional text vectors.",
    ),
])
def test_property_and_application_require_requested_information(question, entity, source):
    descriptor = describe_question(question)
    assert not descriptor.ambiguous and descriptor.entity == entity
    assert [item.quote for item in rank_sufficient_sources(descriptor, (chunk(source),)).selections] == [source]


@pytest.mark.parametrize(("question", "right", "wrong"), [
    (
        "What is an application of topic modeling?",
        "Topic modeling is used for clustering legal documents.",
        "Topic modeling is a technique; sentiment analysis is used for clustering legal documents.",
    ),
    (
        "What is a limitation of TF-IDF?",
        "TF-IDF ignores word order.",
        "TF-IDF is a technique; another model ignores word order.",
    ),
])
def test_unqualified_new_relation_still_requires_bound_entity_and_concrete_information(question, right, wrong):
    descriptor = describe_question(question)
    assert descriptor.entity and not descriptor.qualifiers
    report = rank_sufficient_sources(descriptor, (chunk(wrong), chunk(right, page=2, rank=2)))
    assert [item.quote for item in report.selections] == [right]


@pytest.mark.parametrize(("question", "relation", "entity", "source"), [
    (
        "What information do Bag-of-Words and TF-IDF ignore?", "property", "Bag-of-Words and TF-IDF",
        "Bag-of-Words and TF-IDF do not preserve word order.",
    ),
    (
        "What sequence information do bag-of-words and TF-IDF fail to retain?", "property", "bag-of-words and TF-IDF",
        "Bag-of-Words and TF-IDF fail to retain sequence information.",
    ),
    (
        "Give one domain application for topic modeling described in the material.", "application", "topic modeling",
        "Topic modeling can be used to analyze legal documents.",
    ),
])
def test_original_loss_and_application_seed_intents_keep_multi_entity_and_relation(question, relation, entity, source):
    descriptor = describe_question(question)
    assert not descriptor.ambiguous and descriptor.relation == relation and descriptor.entity == entity
    assert [item.quote for item in rank_sufficient_sources(descriptor, (chunk(source),)).selections] == [source]


@pytest.mark.parametrize(("question", "relation", "entity", "right", "wrong"), [
    (
        "What steps does tokenization follow?", "process", "tokenization",
        "Tokenization first splits text, then emits tokens.",
        "Tokenization is a topic; normalization first splits text, then emits tokens.",
    ),
    (
        "What limitation of Bag-of-Words means word order is lost?", "property", "Bag-of-Words",
        "Bag-of-Words ignores word order and context when it represents text.",
        "Bag-of-Words is a method; another method ignores word order and context when it represents text.",
    ),
])
def test_narrow_process_and_loss_question_shapes_keep_owner(question, relation, entity, right, wrong):
    descriptor = describe_question(question)
    assert not descriptor.ambiguous and descriptor.relation == relation and descriptor.entity == entity
    report = rank_sufficient_sources(descriptor, (chunk(wrong), chunk(right, page=2, rank=2)))
    assert [item.quote for item in report.selections] == [right]


def test_coordinated_definition_and_mechanism_request_does_not_use_a_definition_only_source():
    descriptor = describe_question("Define TF-IDF and explain how it handles word order.")
    assert descriptor.ambiguous and descriptor.local_query is None
    assert not rank_sufficient_sources(
        descriptor, (chunk("TF-IDF is a term-weighting statistic."),),
    ).selections
    single = describe_question("Define TF-IDF.")
    source = "TF-IDF is a term-weighting statistic."
    assert [item.quote for item in rank_sufficient_sources(single, (chunk(source),)).selections] == [source]


@pytest.mark.parametrize("question", [
    "Define Bag-of-Words and TF-IDF.",
    "What is the definition of Bag-of-Words and TF-IDF?",
])
def test_compound_definition_keeps_both_requested_entities(question):
    descriptor = describe_question(question)
    assert descriptor.entity == "Bag-of-Words and TF-IDF"
    wrong = chunk("TF-IDF is a term-weighting statistic.")
    right = chunk("Bag-of-Words and TF-IDF are techniques for representing text as numerical vectors.", page=2)
    report = rank_sufficient_sources(descriptor, (wrong, right))
    assert [item.quote for item in report.selections] == [right.content]


@pytest.mark.parametrize("source", [
    "Bilingual Evaluation Understudy (BLEU) is an incorrect expansion.",
    "BLEU (Bilingual Evaluation Understudy) is a false expansion.",
])
def test_explicit_wrong_acronym_parentheses_do_not_qualify(source):
    descriptor = describe_question("What does BLEU stand for?")
    right = chunk("Bilingual Evaluation Understudy (BLEU) is a translation evaluation metric.", page=2)
    report = rank_sufficient_sources(descriptor, (chunk(source), right))
    assert [item.quote for item in report.selections] == [right.content]


def test_inverse_application_cannot_borrow_title_for_another_owner():
    descriptor = describe_question("What is an application of topic modeling in legal domains?")
    wrong = chunk(
        "Applications of Topic Modeling\n- Clustering legal documents is an application of sentiment analysis."
    )
    right = chunk("Clustering legal documents is an application of topic modeling.", page=2)
    report = rank_sufficient_sources(descriptor, (wrong, right))
    assert [item.quote for item in report.selections] == [right.content]


@pytest.mark.parametrize("source", [
    "Bag-of-Words and TF-IDF are discussed in relation to word order.",
    "Bag-of-Words and TF-IDF preserve word order.",
    "Bag-of-Words and TF-IDF do not ignore word order.",
    "Bag-of-Words and TF-IDF may ignore word order.",
    "Bag-of-Words and TF-IDF are methods; recurrent networks ignore word order.",
    "Bag-of-Words and TF-IDF ignore context.",
    "Other models ignore word order.",
])
def test_information_loss_rejects_topic_only_other_entity_missing_context_and_reversed_polarity(source):
    descriptor = describe_question(
        "What limitation of Bag-of-Words and TF-IDF models means that word order is lost?"
    )
    assert rank_sufficient_sources(descriptor, (chunk(source),)).selections == ()


@pytest.mark.parametrize("source", [
    "Topic modeling is discussed for legal or medical domains.",
    "Topic modeling is used for clustering shopping documents.",
    "Topic modeling is a method; sentiment analysis is used for clustering legal documents.",
    "Topic modeling is not used for clustering legal documents.",
    "Topic modeling may be used for clustering legal documents.",
    "Topic modeling is used for legal documents.",
    "Clustering legal documents is used for topic modeling.",
])
def test_application_rejects_mentions_wrong_entity_domain_polarity_and_missing_example(source):
    descriptor = describe_question(
        "What is an example application of topic modeling mentioned for legal or medical domains?"
    )
    assert rank_sufficient_sources(descriptor, (chunk(source),)).selections == ()


@pytest.mark.parametrize("source", [
    "Euclidean similarity is sensitive to scale and magnitude and ideal for sparse, high-dimensional text vectors.",
    "Euclidean similarity is insensitive to scale and magnitude and not ideal for sparse, high-dimensional text vectors.",
    "Euclidean similarity is sensitive to scale and magnitude and not ideal for text vectors.",
    "Euclidean distance is sensitive to scale and magnitude; cosine similarity is not ideal for sparse, high-dimensional text vectors.",
    "Euclidean distance is sensitive to scale and magnitude and cosine similarity is not ideal for sparse, high-dimensional text vectors.",
    "Euclidean distance is sensitive to scale and magnitude, cosine similarity not ideal for sparse, high-dimensional text vectors.",
])
def test_metric_property_requires_all_requested_conditions_and_polarity(source):
    descriptor = describe_question(
        "Which similarity metric is noted for being sensitive to scale and magnitude and not ideal "
        "for sparse, high-dimensional text vectors?"
    )
    assert rank_sufficient_sources(descriptor, (chunk(source),)).selections == ()


@pytest.mark.parametrize(("question", "source"), [
    (
        "What limitation of Bag-of-Words and TF-IDF models means that word order is lost?",
        "Bag-of-Words and TF-IDF\nLimitations\n- Ignore word order.",
    ),
    (
        "What is an example application of topic modeling mentioned for legal or medical domains?",
        "Applications of Topic Modeling\n- Clustering legal documents.",
    ),
    (
        "What is an example application of topic modeling mentioned for legal or medical domains?",
        "Topic Modeling\nApplications\n- Clustering legal documents.",
    ),
])
def test_heading_and_bullet_are_one_exact_same_chunk_source_unit(question, source):
    descriptor = describe_question(question)
    source_chunk = chunk(source)
    selected = rank_sufficient_sources(descriptor, (source_chunk,)).selections
    assert len(selected) == 1
    assert selected[0].quote == source
    assert source[selected[0].start_offset:selected[0].end_offset] == selected[0].quote


def test_title_ownership_stops_at_other_heading_and_never_merges_chunks():
    descriptor = describe_question(
        "What is an example application of topic modeling mentioned for legal or medical domains?"
    )
    sources = (
        chunk("Applications of Topic Modeling\nNeural Networks\n- Clustering legal documents."),
        chunk("Applications of Topic Modeling"),
        chunk("- Clustering legal documents."),
    )
    assert rank_sufficient_sources(descriptor, sources).selections == ()


@pytest.mark.parametrize("title", ["Topic Modeling", "Applications of Topic Modeling"])
def test_heading_owned_bullet_does_not_borrow_another_explicit_entity_predicate(title):
    descriptor = describe_question(
        "What is an example application of topic modeling mentioned for legal or medical domains?"
    )
    source = title + "\n- Sentiment analysis is used for clustering legal documents."
    assert rank_sufficient_sources(descriptor, (chunk(source),)).selections == ()


def test_heading_context_over_display_limit_does_not_select_a_detached_bullet():
    descriptor = describe_question(
        "What is an example application of topic modeling mentioned for legal or medical domains?"
    )
    source = "Applications of Topic Modeling\n- " + "Clustering legal documents " * 24
    assert rank_sufficient_sources(descriptor, (chunk(source),)).selections == ()


def test_heading_does_not_supply_missing_requested_condition_from_its_topic_label():
    descriptor = describe_question(
        "What limitation of Bag-of-Words and TF-IDF models means that word order is lost?"
    )
    source = "Bag-of-Words and TF-IDF: Word Order\n- Ignore punctuation."
    assert rank_sufficient_sources(descriptor, (chunk(source),)).selections == ()


def test_limitation_title_owns_an_explicit_negative_bullet_only():
    descriptor = describe_question("What is a limitation of LSA?")
    right = "LSA: Limitations\n• No probabilistic interpretation (just linear algebra)."
    wrong = "LSA: Limitations\n• Sentiment analysis has no probabilistic interpretation."
    selected = rank_sufficient_sources(descriptor, (chunk(right),)).selections
    assert [item.quote for item in selected] == [right]
    assert rank_sufficient_sources(descriptor, (chunk(wrong),)).selections == ()
    assert rank_sufficient_sources(descriptor, (chunk("LSA: Limitations"),)).selections == ()


@pytest.mark.parametrize(("question", "right", "wrong"), [
    (
        "What does BLEU stand for?",
        "BLEU\n- Stands for Bilingual Evaluation Understudy.",
        "BLEU\n- ROUGE stands for Recall-Oriented Understudy for Gisting Evaluation.",
    ),
    (
        "What is tokenization?",
        "Tokenization\n- Is the process of dividing text into smaller tokens.",
        "Tokenization\n- Embedding is the process of dividing text into smaller tokens.",
    ),
    (
        "What function does Logistic Regression use to output probabilities?",
        "Logistic Regression\n- Uses the sigmoid function to output probabilities.",
        "Logistic Regression\n- A neural network uses the sigmoid function to output probabilities.",
    ),
    (
        "What does cosine similarity measure between vectors?",
        "Cosine similarity\n- Measures the angle between vectors.",
        "Cosine similarity\n- Euclidean distance measures the angle between vectors.",
    ),
    (
        "Why does stemming use suffixes?",
        "Stemming\n- Uses suffixes because related word forms share a root.",
        "Stemming\n- Lemmatization uses suffixes because related word forms share a root.",
    ),
    (
        "What steps does tokenization follow?",
        "Tokenization\n- First splits text, then emits tokens.",
        "Tokenization\n- Normalization first splits text, then emits tokens.",
    ),
])
def test_v4_six_relation_heading_bullet_ownership(question, right, wrong):
    descriptor = describe_question(question)
    selected = rank_sufficient_sources(descriptor, (chunk(right),)).selections
    assert [item.quote for item in selected] == [right]
    assert rank_sufficient_sources(descriptor, (chunk(wrong),)).selections == ()


@pytest.mark.parametrize(("question", "source"), [
    ("What does BLEU stand for?", "BLEU\n- Means a translation metric."),
    ("What is tokenization?", "Tokenization\n- Is a technique."),
    (
        "What function does Logistic Regression use to output probabilities?",
        "Logistic Regression\n- Uses probabilities to output scores.",
    ),
    ("What steps does tokenization follow?", "Tokenization\n- First splits text."),
    (
        "What does cosine similarity measure between vectors?",
        "Cosine similarity\n- May measure the angle between vectors.",
    ),
    (
        "Why does stemming use suffixes?",
        "Stemming\n- Lemmatization uses suffixes.\n- Because related word forms share a root.",
    ),
])
def test_v4_heading_relation_requires_substantive_same_bullet_evidence(question, source):
    descriptor = describe_question(question)
    assert rank_sufficient_sources(descriptor, (chunk(source),)).selections == ()


def test_v4_numbered_process_steps_need_owned_title_two_actions_and_one_chunk():
    descriptor = describe_question("What are the steps in text normalization?")
    right = "Text normalization: Steps\n1. Lowercase text.\n2. Remove punctuation."
    wrong = "Text normalization: Steps\n1. Lowercase text.\n2. Sentiment analysis removes punctuation."
    assert [item.quote for item in rank_sufficient_sources(descriptor, (chunk(right),)).selections] == [right]
    assert rank_sufficient_sources(descriptor, (chunk(wrong),)).selections == ()
    assert rank_sufficient_sources(descriptor, (chunk("Text normalization: Steps"),
                                                  chunk("1. Lowercase text.\n2. Remove punctuation."))).selections == ()


@pytest.mark.parametrize(("question", "source"), [
    ("What does BLEU stand for?", "BLEU means an automatic translation score."),
    ("What is tokenization?", "Tokenization is a technique."),
    (
        "What function does Logistic Regression use to output probabilities?",
        "Logistic Regression uses probabilities to output scores.",
    ),
    (
        "Which similarity metric measures the angle between two vectors rather than their magnitude?",
        "Cosine similarity measures angle and magnitude between two vectors.",
    ),
])
def test_v4_direct_unit_does_not_treat_a_topic_description_as_requested_relation(question, source):
    assert rank_sufficient_sources(describe_question(question), (chunk(source),)).selections == ()


def test_v4_heading_window_does_not_aggregate_sibling_bullets_or_cross_a_new_title():
    descriptor = describe_question("What function does Logistic Regression use to output probabilities?")
    split = "Logistic Regression\n- Uses a function.\n- Sigmoid outputs probabilities."
    crossed = "Logistic Regression\nNeural Network\n- Uses sigmoid function to output probabilities."
    assert rank_sufficient_sources(descriptor, (chunk(split), chunk(crossed))).selections == ()


def test_v4_entity_free_measurement_needs_a_named_metric_and_exact_contrast():
    descriptor = describe_question(
        "Which similarity metric measures the angle between two vectors rather than their magnitude?"
    )
    generic = "Similarity metrics\n- Measures the angle between two vectors rather than their magnitude."
    wrong_relation = "Cosine similarity\n- Measures the angle and magnitude between two vectors."
    two_owners = ("Cosine similarity and Euclidean distance\n- Measures similarity by the angle "
                  "between two vectors rather than their magnitude.")
    right = ("Cosine similarity\n- Measures similarity by the angle between two vectors "
             "rather than their magnitude.")
    assert rank_sufficient_sources(descriptor, (chunk(generic), chunk(wrong_relation),
                                                chunk(two_owners))).selections == ()
    assert [item.quote for item in rank_sufficient_sources(descriptor, (chunk(right),)).selections] == [right]


def test_v4_reason_does_not_borrow_question_object_from_a_different_causal_clause():
    descriptor = describe_question("Why does stemming use suffixes?")
    wrong_heading = "Stemming\n- Removes stop words because lemmatization handles suffixes."
    wrong_direct = "Stemming removes stop words because lemmatization handles suffixes."
    right = "Stemming\n- Uses suffixes because related word forms share a root."
    assert rank_sufficient_sources(descriptor, (chunk(wrong_heading), chunk(wrong_direct))).selections == ()
    assert [item.quote for item in rank_sufficient_sources(descriptor, (chunk(right),)).selections] == [right]


def test_v4_coordinated_title_cannot_assign_a_singular_bullet_to_one_entity():
    descriptor = describe_question("What is tokenization?")
    wrong = "Tokenization and Stemming\n- Is a process of splitting text into tokens."
    right = "Tokenization\n- Is a process of splitting text into tokens."
    assert rank_sufficient_sources(descriptor, (chunk(wrong),)).selections == ()
    assert [item.quote for item in rank_sufficient_sources(descriptor, (chunk(right),)).selections] == [right]


def test_v4_entity_is_a_title_object_not_the_owner_of_an_implicit_bullet():
    descriptor = describe_question("What is BLEU?")
    wrong = "Evaluation of BLEU\n- Is a method for scoring translation outputs."
    right = "BLEU: Definition\n- Is a method for scoring translation outputs."
    assert rank_sufficient_sources(descriptor, (chunk(wrong),)).selections == ()
    assert [item.quote for item in rank_sufficient_sources(descriptor, (chunk(right),)).selections] == [right]


def test_v4_entity_free_property_identifies_the_metric_before_its_predicate():
    descriptor = describe_question(
        "Which similarity metric is noted for being sensitive to scale and magnitude "
        "and not ideal for sparse, high-dimensional text vectors?"
    )
    bare = "- Sensitive to scale and magnitude and not ideal for sparse, high-dimensional text vectors."
    generic = "Similarity metrics\n" + bare
    named = "Euclidean similarity\n" + bare
    assert rank_sufficient_sources(descriptor, (chunk(bare), chunk(generic))).selections == ()
    assert [item.quote for item in rank_sufficient_sources(descriptor, (chunk(named),)).selections] == [named]


@pytest.mark.parametrize(("question", "wrong", "right"), [
    (
        "What does BLEU stand for?",
        "BLEU is a metric; ROUGE stands for Recall-Oriented Understudy for Gisting Evaluation.",
        "BLEU stands for Bilingual Evaluation Understudy.",
    ),
    (
        "What does cosine similarity measure between vectors?",
        "Cosine similarity is distinct from Euclidean distance which measures separation between vectors.",
        "Cosine similarity primarily measures the angle between vectors.",
    ),
    (
        "What function does Logistic Regression use to output probabilities?",
        "Logistic Regression is compared with Linear Regression which uses a linear function to output probabilities.",
        "Logistic Regression uses the sigmoid function to output probabilities.",
    ),
    (
        "Why does stemming use suffixes?",
        "Stemming removes suffixes; lemmatization uses dictionary entries because dictionaries contain roots.",
        "Stemming uses suffixes because related word forms can share a root.",
    ),
    (
        "What are the steps in text normalization?",
        "Text normalization is an unrelated technique and stemming steps are first identifying a suffix, then removing it.",
        "Text normalization steps are first lowercasing text, then removing punctuation.",
    ),
])
def test_same_unit_other_entity_predicate_does_not_qualify(question, wrong, right):
    descriptor = describe_question(question)
    assert rank_sufficient_sources(descriptor, (chunk(wrong),)).selections == ()
    report = rank_sufficient_sources(descriptor, (chunk(wrong), chunk(right, page=2)))
    assert [item.quote for item in report.selections] == [right]


def test_numeric_question_requirements_cannot_be_replaced_by_other_range():
    descriptor = describe_question(
        "What function does Logistic Regression use to output probabilities between 0 and 1?"
    )
    wrong = chunk("Logistic Regression uses a linear function to output probabilities between 5 and 10.")
    right = chunk("Logistic Regression uses the sigmoid function to output probabilities between 0 and 1.", page=2)
    missing = chunk("Logistic Regression uses the sigmoid function to output probabilities.")
    assert rank_sufficient_sources(descriptor, (wrong, missing)).selections == ()
    assert [item.source for item in rank_sufficient_sources(descriptor, (wrong, right)).selections] == [right]


def test_broad_course_question_locates_entity_bound_definition():
    descriptor = describe_question("What does the course say about alpha?")
    assert descriptor.relation == "definition" and descriptor.entity == "alpha"
    right = chunk("Alpha is the first concept in this synthetic lecture.")
    assert rank_sufficient_sources(descriptor, (right,)).selections[0].quote == right.content


def test_qualifier_and_modal_or_negated_statement_does_not_qualify():
    descriptor = describe_question("What does cosine similarity measure between vectors?")
    source = chunk("Cosine similarity may measure the angle between vectors.")
    assert rank_sufficient_sources(descriptor, (source,)).selections == ()
    source = chunk("Cosine similarity does not measure the angle between vectors.")
    assert rank_sufficient_sources(descriptor, (source,)).selections == ()


def test_exact_offsets_distinct_page_and_budgets():
    descriptor = describe_question("What does BLEU stand for?")
    document_id = uuid4()
    chunks = [chunk(f"Intro {i}. BLEU stands for Bilingual Evaluation Understudy.",
                    page=i, document_id=document_id, rank=i) for i in range(1, 40)]
    report = rank_sufficient_sources(descriptor, chunks)
    assert len(report.selections) == 3
    assert report.examined_chunks <= MAX_EXAMINED_CHUNKS
    assert report.examined_pages <= MAX_EXAMINED_PAGES
    assert report.examined_tokens <= MAX_EXAMINED_TOKENS
    assert len({(x.source.document_id, x.source.page_number) for x in report.selections}) == 3
    assert all(x.quote == x.source.content[x.start_offset:x.end_offset] and len(x.quote) <= 480
               for x in report.selections)
    assert SOURCE_SELECTION_POLICY_ID.endswith("_v7")


@pytest.mark.asyncio
async def test_metadata_only_pool_preserves_lexical_rank_13_partial_and_reserves_neighbor_budget():
    descriptor = describe_question("What does BLEU stand for?")
    document_id = uuid4()
    unrelated = [replace(
        chunk(f"Unrelated course topic {page}.", page=page,
              document_id=document_id, rank=page), token_count=680,
    ) for page in range(1, 13)]
    partial = replace(chunk("BLEU appears in this section.", page=13,
                            document_id=document_id, rank=13), token_count=100,
                      lexical_rank=1)
    tail = [chunk(f"Another unrelated topic {page}.", page=page,
                  document_id=document_id, rank=page) for page in range(14, 21)]
    initial = (*unrelated, partial, *tail)
    direct = rank_sufficient_sources(descriptor, initial)
    assert direct.selections == ()
    assert direct.examined_pages == MAX_EXAMINED_PAGES
    assert direct.partial_anchors == ()  # Direct calls cannot inspect past their cap.
    inspected = select_initial_candidate_pool(initial)
    assert partial in inspected
    assert len({(item.document_id, item.page_number) for item in inspected}) <= MAX_INITIAL_PAGES
    assert sum(item.token_count for item in inspected) <= MAX_INITIAL_TOKENS
    neighbor = chunk("BLEU stands for Bilingual Evaluation Understudy.",
                     page=14, document_id=document_id, rank=1)
    calls = []

    async def expand(anchors, radius, max_chunks, max_pages, max_tokens):
        calls.append((anchors, radius, max_chunks, max_pages, max_tokens))
        return (ExpandedKnowledgeNeighbor(neighbor, partial.chunk_id, 1),)

    assessment, radius = await qualify_with_neighbors(descriptor, initial, expand)
    assert radius == 1 and len(calls) == 1 and calls[0][:2] == ((partial,), 1)
    assert calls[0][2] == 1 + MAX_EXAMINED_CHUNKS - len(inspected)
    assert calls[0][3] == 1 + MAX_EXAMINED_PAGES - len({(x.document_id, x.page_number) for x in inspected})
    assert calls[0][4] == 100 + MAX_EXAMINED_TOKENS - sum(x.token_count for x in inspected)
    assert [item.source for item in assessment.selections] == [neighbor]
    assert assessment.examined_chunks <= MAX_EXAMINED_CHUNKS
    assert assessment.examined_pages <= MAX_EXAMINED_PAGES
    assert assessment.examined_tokens <= MAX_EXAMINED_TOKENS


def test_partial_anchors_have_independent_chunk_page_and_token_reserve():
    descriptor = describe_question("What does BLEU stand for?")
    document_id = uuid4()
    chunks = [replace(chunk("BLEU appears without an expansion.", page=page,
                            document_id=document_id, rank=page), token_count=1_200)
              for page in range(1, 21)]
    report = rank_sufficient_sources(descriptor, chunks)
    assert report.selections == ()
    assert len(report.partial_anchors) == 3
    assert len(report.partial_anchors) <= MAX_PARTIAL_ANCHORS
    assert len({item.page_number for item in report.partial_anchors}) <= MAX_PARTIAL_ANCHOR_PAGES
    assert sum(item.token_count for item in report.partial_anchors) <= MAX_PARTIAL_ANCHOR_TOKENS


@pytest.mark.asyncio
async def test_no_partial_anchor_does_not_expand_or_invent_a_source():
    descriptor = describe_question("What does BLEU stand for?")

    async def unexpected_expansion(_anchors, _radius, _max_chunks, _max_pages, _max_tokens):
        raise AssertionError("No related anchor was found")

    report, radius = await qualify_with_neighbors(
        descriptor, (chunk("Unrelated lecture material."),), unexpected_expansion,
    )
    assert report.selections == () and report.partial_anchors == ()
    assert radius == 0


@pytest.mark.asyncio
async def test_second_radius_reuses_same_bounded_partial_anchor_set():
    descriptor = describe_question("What does BLEU stand for?")
    document_id = uuid4()
    partial = chunk("BLEU is mentioned near a later explanation.",
                    document_id=document_id)
    strong = chunk("BLEU stands for Bilingual Evaluation Understudy.",
                   document_id=document_id, page=3)
    radii = []

    async def expand(anchors, radius, _max_chunks, _max_pages, _max_tokens):
        assert anchors == (partial,)
        radii.append(radius)
        return (() if radius == 1 else
                (ExpandedKnowledgeNeighbor(strong, partial.chunk_id, 2),))

    report, radius = await qualify_with_neighbors(descriptor, (partial,), expand)
    assert radii == [1, 2] and radius == 2
    assert [item.source for item in report.selections] == [strong]


@pytest.mark.asyncio
async def test_radius_two_counts_distinct_initial_and_first_radius_pages_and_tokens():
    descriptor = describe_question("What does BLEU stand for?")
    document_id = uuid4()
    anchor = replace(chunk("BLEU is mentioned.", page=1, document_id=document_id),
                     token_count=500)
    initial = (anchor, *(replace(chunk(f"Unrelated {page}.", page=page,
                                       document_id=document_id, rank=page), token_count=500)
                         for page in range(2, 9)))
    near = tuple(replace(chunk(f"Neighbor {page} mentions BLEU.", page=page,
                               document_id=document_id), token_count=500)
                 for page in (9, 10, 11))
    far = tuple(replace(chunk(f"Further {page} mentions BLEU.", page=page,
                              document_id=document_id), token_count=500)
                for page in (12, 13))
    calls = []

    async def expand(anchors, radius, max_chunks, max_pages, max_tokens):
        calls.append((radius, max_chunks, max_pages, max_tokens))
        source = near if radius == 1 else (*near, *far)
        return tuple(ExpandedKnowledgeNeighbor(item, anchor.chunk_id, radius) for item in source)

    report, radius = await qualify_with_neighbors(descriptor, initial, expand)
    assert radius == 2 and report.selections == ()
    assert calls == [(1, 23, 5, 4_692), (2, 20, 2, 3_192)]
    assert report.examined_chunks == 12
    assert report.examined_pages == MAX_EXAMINED_PAGES
    assert report.examined_tokens == 6_000


@pytest.mark.asyncio
async def test_cumulative_token_cap_rejects_overbudget_second_radius_neighbor():
    descriptor = describe_question("What does BLEU stand for?")
    document_id = uuid4()
    anchor = replace(chunk("BLEU is mentioned.", document_id=document_id), token_count=500)
    first = replace(chunk("BLEU appears again.", document_id=document_id, page=2),
                    token_count=7_000)
    second = replace(chunk("BLEU stands for Bilingual Evaluation Understudy.",
                           document_id=document_id, page=3), token_count=1_000)
    caps = []

    async def expand(anchors, radius, max_chunks, max_pages, max_tokens):
        caps.append((radius, max_chunks, max_pages, max_tokens))
        source = first if radius == 1 else second
        return (ExpandedKnowledgeNeighbor(source, anchor.chunk_id, radius),)

    report, radius = await qualify_with_neighbors(descriptor, (anchor,), expand)
    assert radius == 2 and report.selections == ()
    assert caps == [(1, 30, 12, 8_192), (2, 29, 11, 1_192)]
    assert report.examined_chunks == 2 and report.examined_tokens == 7_500


@pytest.mark.asyncio
async def test_oversize_initial_hits_fail_to_no_match_without_reading_content_or_expanding():
    descriptor = describe_question("What does BLEU stand for?")
    oversized = tuple(replace(chunk("BLEU stands for Bilingual Evaluation Understudy.",
                                    page=index + 1, rank=index + 1), token_count=4_097)
                      for index in range(20))

    async def unexpected(*_args):
        raise AssertionError("No in-budget partial anchor exists")

    assert select_initial_candidate_pool(oversized) == ()
    report, radius = await qualify_with_neighbors(descriptor, oversized, unexpected)
    assert radius == 0 and report.status == "no_matching_relation"
    assert report.examined_chunks == report.examined_pages == report.examined_tokens == 0


@pytest.mark.asyncio
async def test_full_first_radius_budget_does_not_report_unattempted_second_radius():
    descriptor = describe_question("What does BLEU stand for?")
    document_id = uuid4()
    anchor = replace(chunk("BLEU is mentioned.", document_id=document_id), token_count=50)
    siblings = tuple(replace(chunk("BLEU appears on this page.", document_id=document_id),
                             token_count=50) for _ in range(29))
    radii = []

    async def expand(anchors, radius, _max_chunks, _max_pages, _max_tokens):
        radii.append(radius)
        return tuple(ExpandedKnowledgeNeighbor(item, anchor.chunk_id, 0) for item in siblings)

    report, radius = await qualify_with_neighbors(descriptor, (anchor,), expand)
    assert radii == [1] and radius == 1
    assert report.examined_chunks == MAX_EXAMINED_CHUNKS
