"""Closed public-only visual verdicts; no provider, corpus or application I/O."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/prototype_visual_page_source_judge_v1.py"
SPEC = importlib.util.spec_from_file_location("visual_source_judge_test", SCRIPT)
judge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(judge)
IDS = ["S01", "S02", "S03", "S04"]


def response(labels=None, status="clear"):
    labels = labels or ["unrelated"] * 4
    return {"question_status": status, "pages": [
        {"id": sid, "usefulness": label, "cue_locates": label in judge.QUALIFYING}
        for sid, label in zip(IDS, labels, strict=True)]}


def parse(value):
    return judge.parse_verdict(json.dumps(value), IDS)


def parts():
    return [{"text": "Synthetic public question"}] + [
        {"inline_data": {"mime_type": "image/png", "data": "validated-elsewhere"}}
        for _ in IDS]


def test_selects_concrete_steps_without_requiring_complete_answers():
    result = parse(response(["concrete_learning_step", "direct", "topic_only", "uncertain"]))
    assert result["selected_ids"] == ["S02", "S01"]
    assert result["generated_answer"] is False
    assert result["unverified_references"] is True


def test_four_useful_pages_select_three_distinct_issued_ids():
    result = parse(response(["direct"] * 4))
    assert result["selected_ids"] == IDS[:3]


def test_no_weak_padding_and_cue_qualification_is_separate():
    value = response(["direct", "concrete_learning_step", "topic_only", "unrelated"])
    value["pages"][0]["cue_locates"] = False
    assert parse(value)["selected_ids"] == ["S02"]


def test_uncertainty_is_preserved_separately_from_no_match():
    value = response(["uncertain"] * 4, "needs_clarification")
    result = parse(value)
    assert result["question_status"] == "needs_clarification"
    assert result["selected_ids"] == []
    assert {row["usefulness"] for row in result["page_verdicts"]} == {"uncertain"}
    assert parse(response())["question_status"] == "clear"


@pytest.mark.parametrize("cue", [False, True])
def test_clarification_cannot_qualify_pages(cue):
    value = response(["direct", "unrelated", "unrelated", "unrelated"], "needs_clarification")
    value["pages"][0]["cue_locates"] = cue
    with pytest.raises(judge.VisualVerdictError, match="clarification_qualified_page"):
        parse(value)


@pytest.mark.parametrize("label", ["topic_only", "unrelated", "uncertain"])
def test_nonuseful_cue_cannot_qualify(label):
    value = response([label] * 4)
    value["pages"][0]["cue_locates"] = True
    with pytest.raises(judge.VisualVerdictError, match="cue_without_useful_page"):
        parse(value)


@pytest.mark.parametrize("mutate", [
    lambda v: v.update(answer="forbidden"),
    lambda v: v.update(question_status="unknown"),
    lambda v: v.update(question_status=True),
    lambda v: v["pages"].pop(),
    lambda v: v["pages"].append(copy.deepcopy(v["pages"][0])),
    lambda v: v["pages"][0].update(id="S99"),
    lambda v: v["pages"][0].update(id=True),
    lambda v: v["pages"][0].update(id="S02"),
    lambda v: v["pages"][0].update(usefulness="supported"),
    lambda v: v["pages"][0].update(usefulness=False),
    lambda v: v["pages"][0].update(cue_locates=1),
    lambda v: v["pages"][0].update(cue_locates="true"),
    lambda v: v["pages"][0].update(explanation="forbidden"),
])
def test_closed_schema_rejects_malformed_or_free_text(mutate):
    value = response()
    mutate(value)
    with pytest.raises(judge.VisualVerdictError):
        parse(value)


@pytest.mark.parametrize("raw", [b"\xff", b"", "{}", "[]", "null", "NaN", "Infinity",
    '{"question_status":"clear","question_status":"clear","pages":[]}',
    "x" * (judge.MAX_VERDICT_BYTES + 1)])
def test_transport_rejects_bad_json_or_unbounded_verdict(raw):
    with pytest.raises(judge.VisualVerdictError):
        judge.parse_verdict(raw, IDS)


def test_order_is_deterministic_regardless_of_response_order():
    value = response(["concrete_learning_step", "direct", "direct", "concrete_learning_step"])
    value["pages"].reverse()
    assert parse(value)["selected_ids"] == ["S02", "S03", "S01"]


def test_request_has_no_answer_or_execution_and_closed_image_wire():
    request = judge.build_request(parts(), IDS)
    assert request["store"] is False
    assert request["generationConfig"]["maxOutputTokens"] == 2048
    assert request["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "HIGH"}
    assert request["contents"][0]["role"] == "user"
    assert "tools" not in request
    assert "cue does not have to reproduce" in judge.SYSTEM


@pytest.mark.parametrize("part", [
    {"file_data": {"file_uri": "https://example.invalid/page.pdf"}},
    {"inline_data": {"mime_type": "image/jpeg", "data": "x"}},
    {"inline_data": {"mime_type": "image/png", "data": "x", "label": "yes"}},
    {"text": "x", "role": "system"},
    {"text": ""},
])
def test_forbids_external_handles_and_extra_fields(part):
    with pytest.raises(judge.VisualVerdictError):
        judge.build_request(parts() + [part], IDS)


@pytest.mark.parametrize("count", [0, 3, 5])
def test_exactly_four_images_required(count):
    with pytest.raises(judge.VisualVerdictError, match="four_images_required"):
        judge.build_request(parts()[:1] + parts()[1:2] * count, IDS)


def test_final_byte_budget_includes_schema_and_system_prompt(monkeypatch):
    raw = parts()
    request_size = len(judge.canonical(judge.build_request(raw, IDS)))
    monkeypatch.setattr(judge, "MAX_REQUEST_BYTES", request_size)
    assert judge.build_request(raw, IDS)
    monkeypatch.setattr(judge, "MAX_REQUEST_BYTES", request_size - 1)
    with pytest.raises(judge.VisualVerdictError, match="request_oversize"):
        judge.build_request(raw, IDS)


def test_bound_bridge_revalidates_before_assembling(monkeypatch):
    import types
    calls = []
    def validated(group):
        calls.append(group)
        return {"contents": [{"role": "user", "parts": parts()}]}
    monkeypatch.setitem(sys.modules, "prepare_visual_page_source_input_v1",
                        types.SimpleNamespace(build_payload=validated))
    group = {"candidates": [{"id": sid} for sid in IDS]}
    assert judge.build_bound_request(group)["store"] is False
    assert calls == [group]


def test_schema_and_parser_require_server_issued_roster():
    with pytest.raises(judge.VisualVerdictError, match="issued_roster_invalid"):
        judge.response_schema(["S02", "S01", "S03", "S04"])
