"""Integrity of independent public calibration and heldout inputs.

This freezes authored labels and source bindings, not model accuracy. No model
inference, provider, private Knowledge or application database is used.
"""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re

import pytest

FIXTURE = Path(__file__).parent / "fixtures/rag_eval/local_relation_calibration_v1.json"
FROZEN_SHA256 = "f87855899d54ce89f11979fe1876f6c5495c2803f94c886e38de293f39b51369"
POSITIVE_CATEGORIES = (
    "explicit_relation", "definition", "comparison", "heading_bullet",
    "condition_quantity", "long_context",
)
NEGATIVE_CATEGORIES = (
    "same_proposition_conflict", "unrelated_question", "ambiguity_coreference",
    "negation", "altered_number", "mixed_claim", "injection",
    "missing_facts_caveat",
)


@pytest.fixture
def corpus():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_public_corpus_identity_and_declared_holdout_policy(corpus):
    assert sha256(FIXTURE.read_bytes()).hexdigest() == FROZEN_SHA256
    assert corpus["version"] == "local_relation_calibration_v1"
    assert corpus["policy_version"] == "local_relation_candidate_v1"
    assert corpus["split_policy"] == "disjoint_authored_scenarios_and_declared_constructions_v1"
    assert corpus["source_content_joiner"] == " "
    assert "no private Knowledge or model outputs" in corpus["provenance"]
    assert len(corpus["cases"]) == 96


@pytest.mark.parametrize("split", ("calibration", "heldout"))
def test_each_split_has_balanced_labels_and_complete_relation_categories(corpus, split):
    cases = [case for case in corpus["cases"] if case["split"] == split]
    assert len(cases) == 48
    assert Counter(case["expected_supported"] for case in cases) == {True: 24, False: 24}
    assert Counter(case["category"] for case in cases if case["expected_supported"]) == {
        category: 4 for category in POSITIVE_CATEGORIES
    }
    assert Counter(case["category"] for case in cases if not case["expected_supported"]) == {
        category: 3 for category in NEGATIVE_CATEGORIES
    }


def test_each_case_has_exact_unique_public_source_binding_and_rationale(corpus):
    cases = corpus["cases"]
    fields = {
        "id", "split", "family", "category", "expected_supported", "question",
        "statement", "source_quote", "additional_evidence", "rationale",
        "source_id", "quote_start", "quote_end", "length_band",
        "source_construction", "question_construction",
    }
    for field in ("id", "family", "source_id", "question", "source_quote"):
        assert len({case[field] for case in cases}) == 96
    for case in cases:
        assert set(case) == fields
        assert type(case["expected_supported"]) is bool
        for field in fields - {"expected_supported", "additional_evidence", "quote_start", "quote_end"}:
            assert isinstance(case[field], str) and case[field].strip()
        assert re.fullmatch(r"(calibration|heldout)-(positive|negative)-[0-2][0-9]", case["id"])
        assert case["id"].startswith(case["split"] + "-")
        assert case["source_id"] == "public-" + case["id"]
        assert case["family"].startswith(case["split"] + "-")
        assert isinstance(case["additional_evidence"], list)
        assert all(isinstance(value, str) and value.strip() for value in case["additional_evidence"])
        content = " ".join([case["source_quote"], *case["additional_evidence"]])
        assert type(case["quote_start"]) is type(case["quote_end"]) is int
        assert case["quote_start"] == 0
        assert case["quote_end"] == len(case["source_quote"])
        assert content[case["quote_start"]:case["quote_end"]] == case["source_quote"]
        assert content.count(case["source_quote"]) == 1
        assert len(case["rationale"].split()) >= 6
        assert "<|" not in content and "|>" not in content


def test_declared_scenarios_and_source_constructions_do_not_cross_splits(corpus):
    def values(split, field):
        return {case[field] for case in corpus["cases"] if case["split"] == split}
    for field in ("family", "source_id", "source_construction", "question_construction"):
        assert values("calibration", field).isdisjoint(values("heldout", field))
    assert len(values("calibration", "source_construction")) == 14
    assert len(values("heldout", "source_construction")) == 14
    for case in corpus["cases"]:
        first_word = case["question"].split()[0]
        if case["split"] == "calibration":
            assert case["question_construction"] == "interrogative"
            assert first_word in {"What", "Which", "How", "Does", "Are", "Can", "Where", "Who", "When", "At"}
            assert "?" in case["question"]
        else:
            assert case["question_construction"] == "imperative_information_request"
            assert first_word in {"Name", "Identify", "Specify", "Define", "Explain", "Choose", "Select", "Describe", "State", "Give"}


@pytest.mark.parametrize("split", ("calibration", "heldout"))
def test_complete_evidence_has_declared_length_bands_without_clipping(corpus, split):
    cases = [case for case in corpus["cases"] if case["split"] == split]
    assert {case["length_band"] for case in cases} == {"short", "medium", "long"}
    for case in cases:
        content = " ".join([case["source_quote"], *case["additional_evidence"]])
        band = "short" if len(content) <= 160 else "medium" if len(content) <= 360 else "long"
        assert case["length_band"] == band
        assert len(content) <= 650
        assert not content.endswith("...")


def test_heading_forms_are_actual_source_constructions(corpus):
    for case in corpus["cases"]:
        if case["category"] != "heading_bullet":
            continue
        if case["split"] == "calibration":
            assert ":\n- " in case["source_quote"]
            assert case["source_construction"] == "colon_heading_dash_label"
        else:
            assert case["source_quote"].startswith("# ")
            assert "\n* " in case["source_quote"]
            assert case["source_construction"] == "markdown_heading_star_sentence"


def test_source_units_reconstruct_every_complete_evidence_record(corpus):
    from app.ai.answering import _source_units
    import sys
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    sys.path.insert(0, str(scripts))
    from evaluate_local_support import _chunk
    for case in corpus["cases"]:
        chunk = _chunk(case)
        units = _source_units((chunk,))
        assert "".join(unit.source.content[unit.start:unit.end] for unit in units) == chunk.content
        assert chunk.content[case["quote_start"]:case["quote_end"]] == case["source_quote"]


def test_conflict_controls_keep_same_proposition_and_exclusivity_cues(corpus):
    by_id = {case["id"]: case for case in corpus["cases"]}
    assert "only channel 4" in by_id["calibration-negative-01"]["source_quote"]
    assert "only channel 9" in by_id["calibration-negative-01"]["additional_evidence"][0]
    assert "fixed operating pressure" in by_id["calibration-negative-02"]["source_quote"]
    assert "fixed operating pressure" in by_id["calibration-negative-02"]["additional_evidence"][0]
    assert "fixed magnification" in by_id["heldout-negative-01"]["source_quote"]
    assert "fixed magnification" in by_id["heldout-negative-01"]["additional_evidence"][0]
    for case in corpus["cases"]:
        if case["category"] == "same_proposition_conflict":
            assert case["additional_evidence"]
            assert not case["expected_supported"]


def test_reviewed_conditions_are_retained_and_caveat_negatives_are_explicit(corpus):
    by_id = {case["id"]: case for case in corpus["cases"]}
    positive = by_id["heldout-positive-17"]
    assert "mature" in positive["question"]
    assert "Mature" in positive["statement"]
    assert "mature" in positive["source_quote"]
    assert "including activated tickets" in by_id["calibration-negative-22"]["statement"]
    assert "without a guide" in by_id["heldout-negative-22"]["question"]
    assert "without a guide" in by_id["heldout-negative-22"]["statement"]


def test_public_fixture_does_not_encode_the_known_private_topic_cases(corpus):
    body = json.dumps(corpus).casefold()
    for private_topic in ("bleu", "tf-idf", "bag-of-words", "logistic regression", "cosine similarity"):
        assert private_topic not in body
