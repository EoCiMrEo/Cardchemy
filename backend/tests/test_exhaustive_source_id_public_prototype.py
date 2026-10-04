"""Keyless admission checks for the inactive public source-ID candidate."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from prototype_exhaustive_source_id_v2 import (  # noqa: E402
    SOURCE_ID_CANDIDATE_VERSION,
    build_exhaustive_public_wire,
)
from app.ai.source_judgment import (  # noqa: E402
    MAX_WIRE_BYTES,
    SourceJudgmentError,
    canonical_bytes,
    parse_source_id_output,
)


def _four_candidates() -> list[dict]:
    return [
        {"id": f"S0{i}", "page": i,
         "page_text": f"Lecture page {i}: term, relation, and condition {i}.",
         "cue": f"term, relation, and condition {i}"}
        for i in range(1, 5)
    ]


def test_public_prototype_emits_only_question_and_exact_cue_page_pairs() -> None:
    question = "Which relation holds under the stated condition?"
    candidates = _four_candidates()
    wire = build_exhaustive_public_wire(question, candidates)

    assert SOURCE_ID_CANDIDATE_VERSION == "public_exhaustive_page_and_cue_v2"
    assert set(wire) == {"system_instruction", "user_payload", "response_schema"}
    assert set(wire["user_payload"]) == {"question", "candidates"}
    assert wire["user_payload"]["question"] == question
    assert wire["user_payload"]["candidates"] == [
        {"id": row["id"], "shown_cue": row["cue"],
         "page_text": row["page_text"], "physical_page": row["page"]}
        for row in candidates
    ]
    assert len(canonical_bytes(wire)) <= MAX_WIRE_BYTES
    ids = [row["id"] for row in candidates]
    assert parse_source_id_output('{"selected_ids":[]}', ids) == ()
    assert parse_source_id_output('{"selected_ids":["S01","S03","S04"]}', ids) == (
        "S01", "S03", "S04")


@pytest.mark.parametrize("bad_candidates", [
    [], _four_candidates()[:3], _four_candidates() + _four_candidates()[:1],
])
def test_public_prototype_requires_exactly_four_issued_candidates(
    bad_candidates: list[dict],
) -> None:
    with pytest.raises(SourceJudgmentError, match="public_candidate_count_invalid"):
        build_exhaustive_public_wire("question", bad_candidates)


def test_public_prototype_rejects_untrusted_or_oversize_source_data() -> None:
    candidates = _four_candidates()
    candidates[0]["cue"] = "text not on the page"
    with pytest.raises(SourceJudgmentError, match="source_candidate_invalid"):
        build_exhaustive_public_wire("question", candidates)

    candidates = _four_candidates()
    candidates[0]["page_text"] = "a" * 1_201
    with pytest.raises(SourceJudgmentError, match="source_candidate_invalid"):
        build_exhaustive_public_wire("question", candidates)


def test_public_prototype_reuses_strict_id_parser() -> None:
    wire = build_exhaustive_public_wire("question", _four_candidates())
    ids = wire["response_schema"]["properties"]["selected_ids"]["items"]["enum"]
    with pytest.raises(SourceJudgmentError, match="model_output_ids"):
        parse_source_id_output('{"selected_ids":["S01","S01"]}', ids)
    with pytest.raises(SourceJudgmentError, match="model_output_ids"):
        parse_source_id_output('{"selected_ids":["S05"]}', ids)
    with pytest.raises(SourceJudgmentError, match="model_output_ids"):
        parse_source_id_output('{"selected_ids":["S01","S02","S03","S04"]}', ids)
