"""Prospective candidate-local source selection; current v3 stays unchanged.

The wire, page/image/admission checks and positive selection rule are identical
to v3. A nonqualifying page with a positive cue flag is discarded locally;
it cannot invalidate otherwise well-formed independent page judgments. No
runtime provider, settings, storage or activation work occurs in this module.
"""
from __future__ import annotations

import json

from app.ai import source_judgment_visual_v3 as v3

CONTRACT_VERSION = "visual_source_id_v4"
VisualSourceJudgmentError = v3.VisualSourceJudgmentError
MAX_VERDICT_BYTES = v3.MAX_VERDICT_BYTES
build_request = v3.build_request
canonical = v3.canonical
validate_usage = v3.validate_usage


def parse_verdict(raw: str | bytes, issued_ids: list[str]) -> dict:
    """Require both positive signals; discard only a negative-page cue conflict.

    All structural validation runs through the immutable strict v3 parser.
    Unknown fields, IDs, labels, duplicate keys, wrong types, overflow and
    contradictory clarification still fail the whole response. The input is
    never mutated and no nonqualifying page can become a selected reference.
    """
    excluded = 0
    try:
        verdict = v3.parse_verdict(raw, issued_ids)
    except VisualSourceJudgmentError as error:
        if str(error) != "cue_without_useful_page":
            raise
        # Reaching this finite error proves bounded UTF-8 and unique-key JSON.
        # Reparse using the same hooks and revalidate the ENTIRE repaired object,
        # including rows that the earlier strict parse had not reached yet.
        value = json.loads(raw, object_pairs_hook=v3._unique, parse_constant=v3._reject_constant)
        for row in value["pages"]:
            if (type(row) is dict and type(row.get("usefulness")) is str
                    and row["usefulness"] in {"topic_only", "unrelated", "uncertain"}
                    and row.get("cue_locates") is True):
                row["cue_locates"] = False
                excluded += 1
        verdict = v3.parse_verdict(canonical(value), issued_ids)
    verdict["schema_version"] = CONTRACT_VERSION
    verdict["excluded_cue_conflicts"] = excluded
    return verdict
