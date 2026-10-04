"""Synthetic visual wire and local projection; no PDF, provider or persisted source."""
import base64
import copy
import importlib
import json
from pathlib import Path
import struct
import sys
import zlib

import pytest

from app.ai import source_judgment_visual as visual


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)


def png(width=2, height=2, *, data=None, depth=8, color=2):
    header = struct.pack(">IIBBBBB", width, height, depth, color, 0, 0, 0)
    raw = data if data is not None else (b"\x00" + b"\xff\xff\xff" * width) * height
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def candidates(count=4):
    raw = png()
    return [{"id": f"S{i:02d}", "pair_id": f"P{i:03d}", "document_id": "synthetic",
             "page": i, "pdf_sha256": "a" * 64, "page_text_sha256": "b" * 64,
             "context": "Exact cue explains a concrete learning step.", "context_start": 10,
             "context_end": 54, "cue": "Exact cue", "cue_start": 10, "cue_end": 19,
             "image": {"document_id": "synthetic", "pdf_sha256": "a" * 64, "physical_page": i,
                       "render": copy.deepcopy(visual.RENDER_PARAMETERS), "renderer_sha256": "c" * 64,
                       **visual.inspect_png(raw), "png_bytes": raw}} for i in range(1, count + 1)]


def verdict(count=4, labels=None, *, status="clear"):
    labels = labels or ["unrelated"] * count
    return {"question_status": status, "pages": [
        {"id": f"S{i:02d}", "usefulness": label, "cue_locates": label in visual.QUALIFYING}
        for i, label in enumerate(labels, 1)]}


def oracle():
    scripts = str(Path(__file__).resolve().parents[2] / "scripts")
    sys.path.insert(0, scripts)
    try:
        return importlib.import_module("prototype_visual_page_source_judge_v2")
    finally:
        sys.path.remove(scripts)


def test_four_page_request_is_byte_equivalent_to_frozen_wire():
    request = visual.build_request("Which relationship helps?", candidates(), group_id="Q001")
    frozen = oracle()
    expected = frozen.build_request(request["contents"][0]["parts"], [f"S{i:02d}" for i in range(1, 5)])
    assert visual.SYSTEM == frozen.SYSTEM
    assert visual.canonical(request) == frozen.previous.canonical(expected)
    assert request["store"] is False
    assert request["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "HIGH"}
    assert request["generationConfig"]["maxOutputTokens"] == 2048


@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_genuine_candidate_counts_preserve_raw_question_and_project_bound_parts(count):
    question = "  current question\n" + "q" * 3000
    source = candidates(count)
    saved = copy.deepcopy(source)
    request = visual.build_request(question, source, group_id="ephemeral")
    parts = request["contents"][0]["parts"]
    assert json.loads(parts[0]["text"]) == {"group_id": "ephemeral", "question": question}
    assert len(parts) == 1 + 2 * count
    assert request["generationConfig"]["responseJsonSchema"]["properties"]["pages"]["minItems"] == count
    for index in range(count):
        assert json.loads(parts[1 + 2 * index]["text"]) == {k: v for k, v in source[index].items() if k != "image"}
        assert base64.b64decode(parts[2 + 2 * index]["inline_data"]["data"]) == source[index]["image"]["png_bytes"]
    assert visual.estimate_input_tokens(request) <= 32768
    assert "tools" not in request and source == saved
    parsed = visual.parse_verdict(visual.canonical(verdict(count, ["direct"] * count)), [c["id"] for c in source])
    assert parsed["selected_ids"] == [c["id"] for c in source][:3]
    assert parsed["generated_answer"] is False and parsed["unverified_references"] is True


@pytest.mark.parametrize("labels,status", [
    (["direct", "concrete_learning_step", "topic_only", "uncertain"], "clear"),
    (["unrelated"] * 4, "clear"), (["uncertain"] * 4, "needs_clarification"),
    (["concrete_learning_step", "direct", "direct", "direct"], "clear"),
])
def test_four_page_verdict_is_semantically_equivalent_except_new_identity(labels, status):
    value = verdict(labels=labels, status=status)
    value["pages"].reverse()
    raw = visual.canonical(value)
    actual = visual.parse_verdict(raw, [f"S{i:02d}" for i in range(1, 5)])
    expected = oracle().parse_verdict(raw, [f"S{i:02d}" for i in range(1, 5)])
    assert actual.pop("schema_version") == "visual_source_id_v1"
    expected.pop("schema_version")
    assert actual == expected


def test_clear_empty_and_clarification_remain_distinct_without_padding():
    ids = ["S01", "S02"]
    clear = visual.parse_verdict(visual.canonical(verdict(2)), ids)
    clarification = visual.parse_verdict(visual.canonical(verdict(2, ["uncertain"] * 2, status="needs_clarification")), ids)
    assert clear["selected_ids"] == clarification["selected_ids"] == []
    assert clear["question_status"] == "clear"
    assert clarification["question_status"] == "needs_clarification"
    value = verdict(2, ["direct", "concrete_learning_step"])
    value["pages"][0]["cue_locates"] = False
    assert visual.parse_verdict(visual.canonical(value), ids)["selected_ids"] == ["S02"]


@pytest.mark.parametrize("mutation", [
    "missing_image", "extra_field", "history", "duplicate_id", "unissued_id", "duplicate_page",
    "cue_offset", "cue_type", "page_bool", "source_digest", "image_page", "image_digest",
    "image_bytes", "image_bool", "render_crop", "render_bool", "question_bool", "question_oversize",
    "no_candidates", "five_candidates", "png_invalid",
])
def test_request_rejects_missing_unsafe_or_unbound_inputs(mutation):
    source, question = candidates(), "Which relationship helps?"
    if mutation == "missing_image": del source[0]["image"]
    elif mutation == "extra_field": source[0]["answer"] = "forbidden"
    elif mutation == "history": source[0]["history"] = ["forbidden"]
    elif mutation == "duplicate_id": source[1]["id"] = "S01"
    elif mutation == "unissued_id": source[0]["id"] = "S99"
    elif mutation == "duplicate_page": source[1]["page"] = source[1]["image"]["physical_page"] = 1
    elif mutation == "cue_offset": source[0]["cue_end"] += 1
    elif mutation == "cue_type": source[0]["cue"] = True
    elif mutation == "page_bool": source[0]["page"] = True
    elif mutation == "source_digest": source[0]["pdf_sha256"] = "invalid"
    elif mutation == "image_page": source[0]["image"]["physical_page"] = 2
    elif mutation == "image_digest": source[0]["image"]["sha256"] = "d" * 64
    elif mutation == "image_bytes": source[0]["image"]["bytes"] += 1
    elif mutation == "image_bool": source[0]["image"]["width"] = True
    elif mutation == "render_crop": source[0]["image"]["render"]["crop"] = True
    elif mutation == "render_bool": source[0]["image"]["render"]["full_page"] = 1
    elif mutation == "question_bool": question = True
    elif mutation == "question_oversize": question = "x" * 4001
    elif mutation == "no_candidates": source = []
    elif mutation == "five_candidates": source = candidates(5)
    else: source[0]["image"]["png_bytes"] = b"not PNG"
    with pytest.raises(visual.VisualSourceJudgmentError):
        visual.build_request(question, source, group_id="Q001")


@pytest.mark.parametrize("raw", [
    b"", b"not PNG", png() + b"trailing", png()[:-1], png(1601, 1), png(1500, 1500),
    png(depth=16), png(color=3), png(data=b"\x05" + b"\xff" * 6 + b"\x00" + b"\xff" * 6),
    png(data=b"\x00"), b"x" * (visual.MAX_PNG_BYTES + 1),
], ids=["empty", "signature", "trailing", "truncated", "long_side", "pixels",
        "depth", "palette", "filter", "scanlines", "encoded_size"])
def test_png_bounds_and_scanlines_are_enforced(raw):
    with pytest.raises(visual.VisualSourceJudgmentError):
        visual.inspect_png(raw)


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "unissued", "id_bool", "label",
    "cue_int", "weak_cue", "clarification_qualified", "status_bool", "status_missing", "answer"])
def test_verdict_has_only_issued_categorical_pages_and_valid_clarity(mutation):
    value = verdict(2)
    if mutation == "missing": value["pages"].pop()
    elif mutation == "extra": value["pages"].append(copy.deepcopy(value["pages"][0]))
    elif mutation == "duplicate": value["pages"][1]["id"] = "S01"
    elif mutation == "unissued": value["pages"][0]["id"] = "S99"
    elif mutation == "id_bool": value["pages"][0]["id"] = True
    elif mutation == "label": value["pages"][0]["usefulness"] = "answer"
    elif mutation == "cue_int": value["pages"][0]["cue_locates"] = 1
    elif mutation == "weak_cue": value["pages"][0]["cue_locates"] = True
    elif mutation == "clarification_qualified": value = verdict(2, ["direct", "unrelated"], status="needs_clarification")
    elif mutation == "status_bool": value["question_status"] = True
    elif mutation == "status_missing": del value["question_status"]
    else: value["answer"] = "forbidden"
    with pytest.raises(visual.VisualSourceJudgmentError):
        visual.parse_verdict(visual.canonical(value), ["S01", "S02"])


@pytest.mark.parametrize("raw", [b"\xff", b"", b"NaN", b"[]", b"{}", b"x" * 2049,
    b'{"question_status":"clear","question_status":"clear","pages":[]}'],
    ids=["utf8", "empty", "nonfinite", "array", "missing", "oversize", "duplicate_key"])
def test_invalid_json_and_duplicate_keys_fail_closed(raw):
    with pytest.raises(visual.VisualSourceJudgmentError): visual.parse_verdict(raw, ["S01"])


def test_utf8_estimate_refuses_long_multibyte_question_before_a_request():
    source = candidates()
    for item in source:
        item["context"] = item["cue"] + "🧪" * (visual.MAX_CONTEXT_CHARS - len(item["cue"]))
        item["context_end"] = item["context_start"] + visual.MAX_CONTEXT_CHARS
    with pytest.raises(visual.VisualSourceJudgmentError, match="estimated_input_budget"):
        visual.build_request("🧪" * visual.MAX_QUESTION_CHARS, source, group_id="Q001")


@pytest.mark.parametrize("input_tokens,output_tokens,thinking,total", [
    (32768, 1024, 1024, 34816), (100, 1, 2, None), (100, 1, 2, 200),
])
def test_usage_includes_thinking_and_any_larger_total(input_tokens, output_tokens, thinking, total):
    actual = visual.validate_usage(input_tokens, output_tokens, thinking_tokens=thinking, total_tokens=total)
    assert actual == (input_tokens, max(output_tokens + thinking, (total - input_tokens) if total else 0))


@pytest.mark.parametrize("arguments", [
    {"input_tokens": 32769, "output_tokens": 0}, {"input_tokens": 1, "output_tokens": 2049},
    {"input_tokens": 1, "output_tokens": 1024, "thinking_tokens": 1025},
    {"input_tokens": 1, "output_tokens": 0, "total_tokens": 2050},
    {"input_tokens": 100, "output_tokens": 2, "total_tokens": 101},
    {"input_tokens": True, "output_tokens": 0}, {"input_tokens": 1, "output_tokens": False},
    {"input_tokens": 1, "output_tokens": 0, "thinking_tokens": True},
    {"input_tokens": 1, "output_tokens": 0, "total_tokens": True},
])
def test_usage_rejects_missing_or_over_budget_counts(arguments):
    with pytest.raises(visual.VisualSourceJudgmentError): visual.validate_usage(**arguments)
