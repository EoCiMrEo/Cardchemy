"""Prospective visual source-ID completion contract; no runtime activation.

Version 1 and its stored 2,048-token snapshots remain unchanged. This version
uses a 4,096-token thinking-inclusive output ceiling and truthful bounded
adaptive full-page raster provenance. Source, image-byte, prompt and verdict
limits are inherited; adaptive rendering changes no question or page content.
"""
from __future__ import annotations

from app.ai import source_judgment_visual as v1

CONTRACT_VERSION = "visual_source_id_v2"
MAX_OUTPUT_TOKENS = 4_096
MODEL = v1.MODEL
MAX_INPUT_TOKENS = v1.MAX_INPUT_TOKENS
MAX_REQUEST_BYTES = v1.MAX_REQUEST_BYTES
MAX_VERDICT_BYTES = v1.MAX_VERDICT_BYTES
MAX_CUE_CHARS = v1.MAX_CUE_CHARS
MAX_CONTEXT_CHARS = v1.MAX_CONTEXT_CHARS
canonical = v1.canonical
estimate_input_tokens = v1.estimate_input_tokens
_unique = v1._unique
_reject_constant = v1._reject_constant
ALLOWED_RENDER_SCALES = (1600, 1400, 1200, 1000)

VisualSourceJudgmentError = v1.VisualSourceJudgmentError


def build_request(question: str, candidates: list[dict], *, group_id: str) -> dict:
    # Validate truthful local raster provenance independently, retaining the
    # fixed v1 binding contract. Provenance is never projected into model text;
    # only the same exact candidate text and full-page PNG bytes are sent.
    v1._require(type(candidates) is list, "candidate_count_invalid")
    projected = []
    for candidate in candidates:
        v1._require(type(candidate) is dict and type(candidate.get("image")) is dict,
                    "image_fields_invalid")
        image = candidate["image"]
        render = image.get("render")
        v1._require(type(render) is dict and type(render.get("scale_to")) is int and
                    render["scale_to"] in ALLOWED_RENDER_SCALES and
                    v1.canonical(render) == v1.canonical(dict(v1.RENDER_PARAMETERS, scale_to=render["scale_to"])),
                    "image_source_binding_invalid")
        v1._require(type(image.get("width")) is int and type(image.get("height")) is int and
                    max(image["width"], image["height"]) <= render["scale_to"] and
                    (render["scale_to"] == v1.MAX_LONG_SIDE or
                     max(image["width"], image["height"]) == render["scale_to"]),
                    "image_source_binding_invalid")
        projected.append(dict(candidate, image=dict(image, render=dict(v1.RENDER_PARAMETERS))))
    request = v1.build_request(question, projected, group_id=group_id)
    request["generationConfig"]["maxOutputTokens"] = MAX_OUTPUT_TOKENS
    v1._require(len(v1.canonical(request)) <= MAX_REQUEST_BYTES, "request_byte_limit")
    return request


def parse_verdict(raw: str | bytes, issued_ids: list[str]) -> dict:
    verdict = v1.parse_verdict(raw, issued_ids)
    verdict["schema_version"] = CONTRACT_VERSION
    return verdict


def validate_usage(input_tokens: int, output_tokens: int, *, thinking_tokens: int = 0,
                   total_tokens: int | None = None) -> tuple[int, int]:
    v1._require(type(input_tokens) is int and input_tokens > 0 and
                type(output_tokens) is int and output_tokens >= 0 and
                type(thinking_tokens) is int and thinking_tokens >= 0,
                "provider_usage_invalid")
    combined = output_tokens + thinking_tokens
    v1._require(total_tokens is None or
                (type(total_tokens) is int and total_tokens >= input_tokens + combined),
                "provider_usage_invalid")
    charged = max(combined, total_tokens - input_tokens if total_tokens is not None else combined)
    v1._require(input_tokens <= MAX_INPUT_TOKENS and charged <= MAX_OUTPUT_TOKENS,
                "provider_token_limit_exceeded")
    return input_tokens, charged
