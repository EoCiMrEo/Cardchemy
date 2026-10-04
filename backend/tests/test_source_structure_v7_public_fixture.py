"""Independent input integrity for the frozen public structural source contract.

This module imports no selector or application settings. Passing these tests
checks authored evidence and pair construction, not runtime or release quality.
"""

from collections import Counter, defaultdict
import json
from pathlib import Path

import pytest


FIXTURE = Path(__file__).parent / "fixtures/rag_eval/source_structure_v7_public.json"
CORPUS = json.loads(FIXTURE.read_text(encoding="utf-8"))
CASES = CORPUS["cases"]
PAIRS = defaultdict(list)
for _case in CASES:
    PAIRS[_case["pair_id"]].append(_case)

RELATIONS = {
    "acronym_expansion", "definition", "mechanism", "measurement", "reason",
    "process", "property_limitation", "application_example",
}
REQUIRED_FORMS = {
    "parenthetical_item", "multiple_entity_list", "imperative_question",
    "source_attested_alias", "followup_acronym", "domain_qualified_question",
    "definition_noun_phrase", "relation_subheading", "followup_noun_phrase",
    "heading_ownership", "contiguous_window", "worked_example",
    "explicit_connection", "conditional_question", "mechanism_explanation",
    "measurement_noun_phrase", "measurement_interpretation", "numeric_qualifier",
    "polarity_qualifier", "causal_blocks", "causal_explanation",
    "ordered_actions", "unlabeled_sequence", "property_noun_phrase",
    "heading_owned_bullet", "heading_owned_paragraph", "application_examples",
}
REQUIRED_CHALLENGES = {
    "wrong_item_expansion", "ambiguous_expansion", "topic_without_expansion",
    "wrong_domain", "definition_label_without_definition", "wrong_heading_owner",
    "unattested_alias", "clipped_definition", "another_entity_example",
    "wrong_condition", "formula_without_interpretation", "wrong_relation",
    "mention_without_interpretation", "wrong_number", "negated_condition",
    "benefit_without_cause", "disconnected_facts", "ambiguous_followup",
    "unordered_inventory", "numbered_nonactions", "clipped_numbered_sequence",
    "catalog_not_application", "wrong_alias_expansion",
}


def test_fixture_is_independent_and_balanced_public_development_evidence():
    assert CORPUS["schema"] == "source_structure_v7_public_v1"
    assert CORPUS["policy_target"] == "source_relation_units_v7"
    assert CORPUS["provenance"]["kind"] == "independent_synthetic_public_contract"
    assert "not held-out release" in CORPUS["provenance"]["purpose"]
    assert len(CASES) == 64
    assert len(PAIRS) == CORPUS["pair_count"] == 32
    assert len({case["id"] for case in CASES}) == len(CASES)
    assert len({case["source"]["document_id"] for case in CASES}) == len(CASES)
    assert set(CORPUS["relations"]) == RELATIONS
    assert Counter(case["expected_supported"] for case in CASES) == {True: 32, False: 32}
    assert CORPUS["limits"] == {
        "max_reference_characters": 480, "max_references": 3,
        "max_chunks": 30, "max_pages": 12, "max_context_tokens": 8192,
    }
    assert {form for case in CASES for form in case["structural_forms"]} == REQUIRED_FORMS
    assert {case["negative_challenge"] for case in CASES} == REQUIRED_CHALLENGES


@pytest.mark.parametrize("relation", sorted(RELATIONS))
def test_each_relation_has_four_matched_positive_and_negative_pairs(relation):
    selected = [case for case in CASES if case["relation"] == relation]
    assert len(selected) == 8
    assert Counter(case["expected_supported"] for case in selected) == {True: 4, False: 4}
    assert len({case["pair_id"] for case in selected}) == 4


@pytest.mark.parametrize("pair_id", sorted(PAIRS))
def test_pairs_isolate_evidence_or_followup_ambiguity(pair_id):
    pair = PAIRS[pair_id]
    assert len(pair) == 2
    positive = next(case for case in pair if case["expected_supported"])
    negative = next(case for case in pair if not case["expected_supported"])
    assert positive["id"] == pair_id + "-P"
    assert negative["id"] == pair_id + "-N"
    for field in ("question", "relation", "structural_forms", "negative_challenge", "rationale", "pair_mutation"):
        assert positive[field] == negative[field]
    if positive["pair_mutation"] == "prior_user_context":
        assert positive["source"]["page_text"] == negative["source"]["page_text"]
        assert positive["history"] != negative["history"]
        assert positive["question_roles"]["resolution"] == "single_prior_entity"
        assert negative["question_roles"]["resolution"] == "ambiguous"
        assert negative["question_roles"]["entity"] is None
    else:
        assert positive["pair_mutation"] == "source_text"
        assert positive["source"]["page_text"] != negative["source"]["page_text"]
        assert positive["history"] == negative["history"]
        assert positive["question_roles"] == negative["question_roles"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_case_has_exact_bounded_source_and_explicit_expected_evidence(case):
    assert type(case["expected_supported"]) is bool
    assert case["question"].strip()
    assert case["rationale"].strip()
    assert case["relation"] == case["question_roles"]["requested_relation"]
    assert all(message["role"] == "user" and message["content"].strip() for message in case["history"])
    assert len(case["history"]) <= 1
    source = case["source"]
    page = source["page_text"]
    chunk = source["anchor_chunk"]
    assert source["page_number"] > 0
    assert source["section"] == page.splitlines()[0]
    assert 0 <= chunk["start"] < chunk["end"] <= len(page)
    assert page[chunk["start"]:chunk["end"]] == chunk["text"]
    # Every test supplies a compact admitted page; budget exhaustion cannot
    # explain the semantic distinction between the matched pair.
    assert len(page) + len(chunk["text"]) < 8192
    if case["expected_supported"]:
        assert case["expected_sufficiency"] == "SUPPORTED"
        window = case["expected_window"]
        assert 0 <= window["start"] < window["end"] <= len(page)
        assert page[window["start"]:window["end"]] == window["text"]
        assert 0 < len(window["text"]) <= 480
        assert window["required_fragments"]
        assert all(fragment.casefold() in window["text"].casefold() for fragment in window["required_fragments"])
        roles = case["question_roles"]
        assert roles["entity"].casefold() in window["text"].casefold()
        for qualifier in roles["conditions"] + roles["numbers"]:
            # A step-count condition can be fulfilled structurally by three
            # separately numbered actions rather than repeating the question.
            if qualifier != "all 3 steps":
                assert qualifier.casefold() in window["text"].casefold()
        if "all 3 steps" in roles["conditions"]:
            assert all(f"{number}. " in window["text"] for number in (1, 2, 3))
        if roles["domain"]:
            assert roles["domain"].casefold() in window["text"].casefold()
    else:
        assert case["expected_sufficiency"] == "INSUFFICIENT"
        assert case["expected_window"] is None
