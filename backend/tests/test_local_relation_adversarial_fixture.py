"""Frozen public controls for the isolated relation-checker experiment.

These tests check the evaluation inputs, not model accuracy or release readiness.
No inference, application database or provider is used.
"""

import json
from pathlib import Path

import pytest


FIXTURE = Path(__file__).parent / "fixtures/rag_eval/local_relation_adversarial_v1.json"
CLASSES = (
    "same-proposition-conflict-",
    "different-proposition-distractor-",
    "ambiguous-relation-",
    "negation-",
    "altered-number-",
    "mixed-claims-",
    "prompt-injection-",
    "clean-positive-",
)


@pytest.fixture
def corpus():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_relation_controls_are_frozen_separately_from_installed_policy(corpus):
    assert corpus["version"] == "local_relation_adversarial_v1"
    assert corpus["policy_version"] == "local_relation_candidate_v1"
    cases = corpus["cases"]
    assert len(cases) == 24
    assert len({case["id"] for case in cases}) == len(cases)
    required_fields = {
        "id", "question", "source_quote", "statement",
        "additional_evidence", "expected_supported",
    }
    for case in cases:
        assert set(case) == required_fields
        assert type(case["expected_supported"]) is bool
        for name in ("id", "question", "source_quote", "statement"):
            assert isinstance(case[name], str) and case[name].strip()
        assert isinstance(case["additional_evidence"], list)
        assert all(isinstance(text, str) and text.strip() for text in case["additional_evidence"])


@pytest.mark.parametrize("category", CLASSES)
def test_each_frozen_adversarial_class_has_three_cases(corpus, category):
    cases = [case for case in corpus["cases"] if case["id"].startswith(category)]
    assert len(cases) == 3
    expected = category in {"different-proposition-distractor-", "clean-positive-"}
    assert all(case["expected_supported"] is expected for case in cases)
    if category in {"different-proposition-distractor-", "same-proposition-conflict-"}:
        assert all(case["additional_evidence"] for case in cases)


@pytest.mark.parametrize("topic", ("capital", "condition", "fictional-channel"))
def test_context_controls_only_change_other_evidence_for_the_same_question(corpus, topic):
    by_id = {case["id"]: case for case in corpus["cases"]}
    positive = by_id[f"different-proposition-distractor-{topic}"]
    conflict = by_id[f"same-proposition-conflict-{topic}"]
    for field in ("question", "source_quote", "statement"):
        assert positive[field] == conflict[field]
    assert positive["additional_evidence"] != conflict["additional_evidence"]
    assert positive["expected_supported"] and not conflict["expected_supported"]
