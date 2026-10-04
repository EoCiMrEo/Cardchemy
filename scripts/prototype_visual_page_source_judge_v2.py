"""Inert clarity-aligned visual source wire; no provider execution.

Version 1 and its completed input/review freezes remain unchanged. This
prospective version distinguishes entity-discovery questions from dangling
referents without relaxing page usefulness or importing outside facts.
"""
from __future__ import annotations

import prototype_visual_page_source_judge_v1 as previous

VERSION = "public_visual_page_source_v2"
QUESTION_CLARITY = (
    "A question can be clear when it asks to discover a name, object or example: "
    "the question need not contain its answer or uniquely identify the unknown "
    "entity it asks the student to find. A specified category, requested relation "
    "and material conditions can identify the task. Ask for clarification only "
    "when a dangling referent, incompatible conditions or an unspecified target "
    "makes the task itself ambiguous. Missing evidence on the supplied pages is "
    "not question ambiguity. Do not infer a referent from other questions."
)
SYSTEM = previous.SYSTEM.replace(
    "If the question's required object/conditions are unresolved, set question_status\n"
    "to needs_clarification and do not qualify any page. This is not proof that the\n"
    "whole corpus lacks a source. Otherwise use clear; zero qualified pages is valid.",
    QUESTION_CLARITY + "\nIf the task itself needs clarification, set question_status to "
    "needs_clarification and do not qualify any page. This is not proof that the "
    "whole corpus lacks a source. Otherwise use clear; zero qualified pages is valid.",
)


def build_request(validated_parts: list[dict], issued_ids: list[str]) -> dict:
    request = previous.build_request(validated_parts, issued_ids)
    request["systemInstruction"] = {"parts": [{"text": SYSTEM}]}
    previous.require(len(previous.canonical(request)) <= previous.MAX_REQUEST_BYTES,
                     "request_oversize")
    return request


def build_bound_request(group_input: dict) -> dict:
    from prepare_visual_page_source_input_v1 import build_payload

    payload = build_payload(group_input)
    return build_request(payload["contents"][0]["parts"],
                         [row["id"] for row in group_input["candidates"]])


def parse_verdict(raw: str | bytes, issued_ids: list[str]) -> dict:
    value = previous.parse_verdict(raw, issued_ids)
    value["schema_version"] = VERSION
    return value
