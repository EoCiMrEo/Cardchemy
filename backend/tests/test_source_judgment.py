"""Provider-free contracts for the source-ID-only judgment boundary."""

import json

import pytest

from app.ai.source_judgment import (
    SourceJudgmentError,
    build_source_id_request,
    parse_source_id_output,
)


def _candidate(source_id: str) -> dict:
    return {
        "id": source_id,
        "page": 2,
        "page_text": "Heading\nThe method uses a defined update rule.",
        "cue": "The method uses a defined update rule.",
    }


def test_request_contains_only_current_question_and_exact_page_data():
    wire = build_source_id_request("How does the method update?", [_candidate("S01")])
    assert set(wire) == {"system_instruction", "user_payload", "response_schema"}
    assert set(wire["user_payload"]) == {"question", "candidates"}
    assert wire["user_payload"]["question"] == "How does the method update?"
    assert wire["response_schema"]["properties"]["selected_ids"]["items"]["enum"] == ["S01"]


def test_request_rejects_nonexact_cue_and_unexpected_metadata():
    candidate = _candidate("S01")
    candidate["cue"] = "a stitched answer"
    with pytest.raises(SourceJudgmentError, match="source_candidate_invalid"):
        build_source_id_request("Question?", [candidate])
    candidate = _candidate("S01")
    candidate["private_history"] = "not permitted"
    with pytest.raises(SourceJudgmentError, match="source_candidate_invalid"):
        build_source_id_request("Question?", [candidate])


@pytest.mark.parametrize("selected", [[], ["S01"], ["S02", "S01"]])
def test_parser_accepts_only_issued_ordered_ids(selected):
    assert parse_source_id_output(
        json.dumps({"selected_ids": selected}), ["S01", "S02"]
    ) == tuple(selected)


@pytest.mark.parametrize("payload", [
    {"selected_ids": ["S01", "S01"]},
    {"selected_ids": ["S05"]},
    {"selected_ids": ["S01", "S02", "S03", "S04"]},
    {"selected_ids": ["S01"], "explanation": "answer"},
    {"answer": "unsupported"},
])
def test_parser_rejects_duplicate_foreign_excess_and_answer_fields(payload):
    with pytest.raises(SourceJudgmentError):
        parse_source_id_output(json.dumps(payload), ["S01", "S02", "S03", "S04"])


def test_parser_rejects_non_json_and_duplicate_keys():
    with pytest.raises(SourceJudgmentError):
        parse_source_id_output("not json", ["S01"])
    # A duplicate top-level key is ambiguous even if a permissive JSON parser
    # would silently keep the last value.
    with pytest.raises(SourceJudgmentError):
        parse_source_id_output('{"selected_ids":[],"selected_ids":["S01"]}', ["S01"])
