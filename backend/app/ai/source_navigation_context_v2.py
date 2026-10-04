"""Prospective current-question clarity repair; no runtime integration or I/O.

The literal prior-subject grammar and bindings stay at v1. An ordinary
interrogative use of the learning verb ``ignore`` must not become a missing
referent merely because v1's meta-instruction blacklist contains that verb.
The original question is never rewritten or treated as trusted instructions.
"""
from __future__ import annotations

import re
import unicodedata

from app.ai import source_navigation_context_v1 as v1

POLICY_ID = "literal_subject_anchor_v2"
_INTERROGATIVE = re.compile(r"^(?:what|which|how|why|when|where|who)\b", re.I)


def safe_current_question(question: object) -> bool:
    """Retain v1 bounds and all other exclusions; permit lexical ignore only.

    This exception requires an interrogative task and already clear raw query.
    Imperatives and instructions/credentials/prompt keywords remain rejected.
    This text check grants no source access and selects no reference.
    """
    if v1._safe_question(question, v1.MAX_CURRENT_CHARS):
        return True
    if type(question) is not str or not 0 < len(question) <= v1.MAX_CURRENT_CHARS or not question.strip():
        return False
    if _INTERROGATIVE.match(question.strip()) is None:
        return False
    meta = tuple(v1._META_INSTRUCTION.finditer(question))
    if not meta or any(match.group().casefold() != "ignore" for match in meta):
        return False
    core = question.strip().rstrip("?.!")
    return (not any(unicodedata.category(char).startswith("C") for char in question)
        and v1._ADDITIONAL_INSTRUCTION.search(question) is None
        and not any(char in core for char in ".!?") and question.count("?") <= 1
        and ("?" not in question or question.rstrip().endswith("?"))
        and v1._digest(question) is not None)


def resolve_subject_context(current_question: str, preceding_history=(), *, raw_navigation_query: str | None):
    """No new history eligibility; only repair a clear CURRENT task's blacklist.

    ``raw_navigation_query`` must be the actual production raw-only result.
    The source/SQL boundary must bind and recheck that independently.
    """
    if raw_navigation_query is not None and safe_current_question(current_question):
        valid = type(raw_navigation_query) is str and raw_navigation_query == current_question.strip()
        return v1.SubjectContextResolution(
            "clear_current_question" if valid else "needs_clarification",
            "raw_question_clear" if valid else "raw_query_invalid",
            v1._digest(current_question), policy_id=POLICY_ID)
    # Keep every unresolved-question / literal-subject safeguard unchanged.
    return v1.resolve_subject_context(current_question, preceding_history,
                                      raw_navigation_query=raw_navigation_query)
