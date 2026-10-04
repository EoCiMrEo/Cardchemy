"""Provider-free contracts for the inactive per-page public source judge."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from prototype_per_page_source_verdict_v3 import (  # noqa: E402
    SOURCE_VERDICT_CANDIDATE_VERSION,
    build_per_page_public_wire,
    parse_per_page_source_verdict_output,
)
from app.ai.source_judgment import (  # noqa: E402
    MAX_WIRE_BYTES,
    SourceJudgmentError,
    canonical_bytes,
)


IDS = ["S01", "S02", "S03", "S04"]


def _candidates() -> list[dict]:
    return [
        {"id": identifier, "page": number,
         "page_text": f"Page {number} shows a reported quantity for topic.",
         "cue": "shows a reported quantity for topic"}
        for number, identifier in enumerate(IDS, start=1)
    ]


def _raw(truth: list[tuple[bool, bool]], *, order: list[int] | None = None) -> str:
    rows = [
        {"id": IDS[index], "useful_reading_page": useful,
         "requested_relation_present": relation}
        for index, (useful, relation) in enumerate(truth)
    ]
    return json.dumps({"verdicts": [rows[i] for i in (order or range(4))]})


def test_wire_preserves_bounded_cue_first_source_only_contract() -> None:
    question = "Which reported quantity does the lecture give?"
    wire = build_per_page_public_wire(question, _candidates())
    assert SOURCE_VERDICT_CANDIDATE_VERSION == "public_per_page_relation_verdict_v3"
    assert set(wire) == {"system_instruction", "user_payload", "response_schema"}
    assert wire["user_payload"] == {
        "question": question,
        "candidates": [
            {"id": row["id"], "shown_cue": row["cue"],
             "page_text": row["page_text"], "physical_page": row["page"]}
            for row in _candidates()
        ],
    }
    assert len(canonical_bytes(wire)) <= MAX_WIRE_BYTES
    assert wire["response_schema"]["properties"]["verdicts"]["minItems"] == 4
    assert "selected_ids" not in wire["response_schema"]["properties"]


def test_independent_verdicts_select_only_both_true_in_issued_order() -> None:
    assert parse_per_page_source_verdict_output(
        _raw([(True, True), (True, False), (False, True), (True, True)],
             order=[3, 1, 0, 2]), IDS) == ("S01", "S04")
    assert parse_per_page_source_verdict_output(
        _raw([(False, False)] * 4), IDS) == ()
    assert parse_per_page_source_verdict_output(
        _raw([(True, True)] * 4), IDS) == ("S01", "S02", "S03")


@pytest.mark.parametrize("raw", [
    '{"verdicts":[]}',
    '{"verdicts":[{"id":"S01","useful_reading_page":true,'
    '"requested_relation_present":true}]}',
    '{"verdicts":[{"id":"S01","useful_reading_page":true,'
    '"requested_relation_present":true},{"id":"S01",'
    '"useful_reading_page":true,"requested_relation_present":true},'
    '{"id":"S03","useful_reading_page":true,"requested_relation_present":true},'
    '{"id":"S04","useful_reading_page":true,"requested_relation_present":true}]}',
    '{"verdicts":[{"id":"S99","useful_reading_page":true,'
    '"requested_relation_present":true},{"id":"S02","useful_reading_page":true,'
    '"requested_relation_present":true},{"id":"S03","useful_reading_page":true,'
    '"requested_relation_present":true},{"id":"S04","useful_reading_page":true,'
    '"requested_relation_present":true}]}',
    '{"verdicts":[],"verdicts":[]}',
    '{"verdicts":[{"id":"S01","useful_reading_page":true,'
    '"useful_reading_page":false,"requested_relation_present":true}]}',
    '{"selected_ids":[]}',
])
def test_missing_duplicate_foreign_or_old_shape_fails_closed(raw: str) -> None:
    with pytest.raises(SourceJudgmentError):
        parse_per_page_source_verdict_output(raw, IDS)


@pytest.mark.parametrize("invalid", [1, "true", None, [], {}])
def test_non_boolean_relation_is_not_a_verdict(invalid: object) -> None:
    rows = json.loads(_raw([(True, True)] * 4))
    rows["verdicts"][0]["requested_relation_present"] = invalid
    with pytest.raises(SourceJudgmentError, match="model_output_verdicts"):
        parse_per_page_source_verdict_output(json.dumps(rows), IDS)


def test_input_and_output_bounds_are_enforced_before_selection() -> None:
    candidates = _candidates()
    candidates[0]["cue"] = "not present in page text"
    with pytest.raises(SourceJudgmentError, match="source_candidate_invalid"):
        build_per_page_public_wire("question", candidates)
    with pytest.raises(SourceJudgmentError, match="model_output_invalid"):
        parse_per_page_source_verdict_output(" " * 2_049, IDS)
    with pytest.raises(SourceJudgmentError, match="model_output_invalid"):
        parse_per_page_source_verdict_output("\ud800", IDS)
