"""Runtime execution of independently frozen synthetic structural source cases."""
from dataclasses import replace
import json
from pathlib import Path
import pytest
from app.ai.source_sufficiency import describe_question, rank_sufficient_sources
from tests.test_source_sufficiency import chunk

CASES = json.loads((Path(__file__).parent / "fixtures/rag_eval/source_structure_v7_public.json").read_text())["cases"]

@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_frozen_public_structure_selection(case):
    source = case["source"]
    anchor = replace(chunk(source["anchor_chunk"]["text"]), section=source["section"])
    descriptor = describe_question(case["question"], tuple((item["role"], item["content"]) for item in case["history"]))
    report = rank_sufficient_sources(descriptor, (anchor,), {anchor.chunk_id: source["page_text"]})
    assert bool(report.selections) == case["expected_supported"], (descriptor, report)
    if report.selections:
        selected = report.selections[0]
        assert selected.source_kind == "canonical_page"
        assert selected.quote == source["page_text"][selected.start_offset:selected.end_offset]
        assert len(selected.quote) <= 480
        assert all(fragment.casefold() in selected.quote.casefold() for fragment in case["expected_window"]["required_fragments"]), selected.quote


@pytest.mark.parametrize(("question", "title", "body"), [
    ("Why does the amber valve remove beads?", "Amber valve", "Reason\nAdds beads because the tray requires a full load."),
    ("How does the amber valve remove beads?", "Amber valve", "Mechanism\nAdds beads by opening the supply tray."),
    ("What does the amber gauge measure when the alarm is not armed?", "Amber gauge", "When the alarm is armed, Amber gauge measures time. A separate panel is not armed."),
    ("What is the amber valve?", "Amber valve", "Definition\nThe OtherTool is a hollow cylinder used to control liquid flow."),
    ("What is the amber valve?", "Amber valve", "Definition\nDiscussed in this chapter.\nExamples\nAdding beads to a tray during a demonstration."),
])
def test_requested_operation_conditions_and_owner_cannot_be_borrowed(question, title, body):
    anchor = replace(chunk(body), section=title)
    page = title + "\n" + body
    assert not rank_sufficient_sources(describe_question(question), (anchor,), {anchor.chunk_id: page}).selections


def test_source_attested_pair_does_not_require_matching_initials():
    body = "LASER (Light Amplification by Stimulated Emission of Radiation): the source-attested full name."
    anchor = replace(chunk(body), section="Device names")
    page = "Device names\n" + body
    selected = rank_sufficient_sources(describe_question("Expand LASER."), (anchor,), {anchor.chunk_id: page}).selections
    assert selected and "Light Amplification" in selected[0].quote
