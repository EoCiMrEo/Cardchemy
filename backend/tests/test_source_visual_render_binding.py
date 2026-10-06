"""Current completion, raster and usage binding limits."""
import copy

import pytest

from app.ai import source_judgment_visual as visual
from tests.test_source_judgment_visual import candidates, png






@pytest.mark.parametrize("args", [(True, 100, 1, None), (1000, True, 1, None),
    (1000, 100, True, None), (1000, 100, 1, True), (1000, 100, 1, 1100),
    (0, 100, 1, None), (32769, 1, 0, None), (1000, 4097, 0, None)])
def test_malformed_or_over_budget_usage_is_rejected(args):
    inp, out, thoughts, total = args
    with pytest.raises(visual.VisualSourceJudgmentError):
        visual.validate_usage(inp, out, thinking_tokens=thoughts, total_tokens=total)




@pytest.mark.parametrize("scale", [1400, 1200, 1000])
def test_truthful_reduced_full_page_preserves_source_binding(scale):
    source = candidates(1)
    image = source[0]["image"]
    raw = png(scale, 10)
    image.update(visual.inspect_png(raw), png_bytes=raw)
    image["render"]["scale_to"] = scale
    saved = copy.deepcopy(source)
    request = visual.build_page_request("Which relation helps?", source, group_id="synthetic")
    assert request["generationConfig"]["maxOutputTokens"] == 4096 and source == saved
    assert request["contents"][0]["parts"][2]["inline_data"]["data"]


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
    with pytest.raises(visual.VisualSourceJudgmentError, match="image_source_binding_invalid"):
        visual.build_page_request("Which relation helps?", source, group_id="synthetic")
