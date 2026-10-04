"""Prospective completion budget without changing historical source contracts."""
import copy

import pytest

from app.ai import source_judgment_visual as v1
from app.ai import source_judgment_visual_v2 as v2
from tests.test_source_judgment_visual import candidates, png, verdict


@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_only_completion_budget_changes_in_wire_and_original_remains_immutable(count):
    source = candidates(count)
    saved = copy.deepcopy(source)
    original = v1.build_request("Which relation helps?", source, group_id="synthetic")
    successor = v2.build_request("Which relation helps?", source, group_id="synthetic")
    assert original["generationConfig"]["maxOutputTokens"] == 2048
    assert successor["generationConfig"].pop("maxOutputTokens") == 4096
    original["generationConfig"].pop("maxOutputTokens")
    assert successor == original and source == saved


def test_output_including_thinking_exceeds_old_contract_but_fits_successor():
    assert v2.validate_usage(1000, 100, thinking_tokens=3996) == (1000, 4096)
    with pytest.raises(v1.VisualSourceJudgmentError, match="provider_token_limit_exceeded"):
        v1.validate_usage(1000, 100, thinking_tokens=3996)
    assert v2.validate_usage(1000, 100, thinking_tokens=1, total_tokens=5096) == (1000, 4096)
    with pytest.raises(v2.VisualSourceJudgmentError, match="provider_token_limit_exceeded"):
        v2.validate_usage(1000, 100, thinking_tokens=1, total_tokens=5097)


@pytest.mark.parametrize("args", [(True, 100, 1, None), (1000, True, 1, None),
    (1000, 100, True, None), (1000, 100, 1, True), (1000, 100, 1, 1100),
    (0, 100, 1, None), (32769, 1, 0, None), (1000, 4097, 0, None)])
def test_malformed_or_over_budget_usage_is_rejected(args):
    inp, out, thoughts, total = args
    with pytest.raises(v2.VisualSourceJudgmentError):
        v2.validate_usage(inp, out, thinking_tokens=thoughts, total_tokens=total)


def test_verdict_only_has_new_identity_and_zero_to_three_unverified_page_ids():
    raw = v1.canonical(verdict(labels=["concrete_learning_step", "direct", "direct", "direct"]))
    old = v1.parse_verdict(raw, ["S01", "S02", "S03", "S04"])
    new = v2.parse_verdict(raw, ["S01", "S02", "S03", "S04"])
    assert old.pop("schema_version") == "visual_source_id_v1"
    assert new.pop("schema_version") == "visual_source_id_v2"
    assert old == new and new["selected_ids"] == ["S02", "S03", "S04"]
    assert not new["generated_answer"] and new["unverified_references"]
    with pytest.raises(v2.VisualSourceJudgmentError, match="verdict_oversize"):
        v2.parse_verdict(b"x" * 2049, ["S01"])


@pytest.mark.parametrize("scale", [1400, 1200, 1000])
def test_truthful_reduced_full_page_is_allowed_only_in_successor_without_mutating_binding(scale):
    source = candidates(1)
    image = source[0]["image"]
    raw = png(scale, 10)
    image.update(v1.inspect_png(raw), png_bytes=raw)
    image["render"]["scale_to"] = scale
    saved = copy.deepcopy(source)
    request = v2.build_request("Which relation helps?", source, group_id="synthetic")
    assert request["generationConfig"]["maxOutputTokens"] == 4096 and source == saved
    assert request["contents"][0]["parts"][2]["inline_data"]["data"]
    with pytest.raises(v1.VisualSourceJudgmentError, match="image_source_binding_invalid"):
        v1.build_request("Which relation helps?", source, group_id="synthetic")


@pytest.mark.parametrize("mutation", ["scale", "boolean", "crop", "wrong_size", "extra", "integer_flag"])
def test_adaptive_binding_rejects_unapproved_or_false_render_metadata(mutation):
    source = candidates(1)
    image = source[0]["image"]
    if mutation == "scale": image["render"]["scale_to"] = 1500
    elif mutation == "boolean": image["render"]["scale_to"] = True
    elif mutation == "crop": image["render"]["crop"] = True
    elif mutation == "wrong_size": image["render"]["scale_to"] = 1400
    elif mutation == "integer_flag": image["render"]["full_page"] = 1
    else: image["render"]["unknown"] = "untrusted"
    with pytest.raises(v2.VisualSourceJudgmentError, match="image_source_binding_invalid"):
        v2.build_request("Which relation helps?", source, group_id="synthetic")
