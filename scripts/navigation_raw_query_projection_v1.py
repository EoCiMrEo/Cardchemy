"""Pure raw-only projection of caller-supplied, trusted production source bytes.

Importing source_navigation itself also imports database/settings dependencies.
This helper instead compiles only its existing query functions and constants,
without importing the application or changing consumed production source.
The caller must obtain the source SHA from its independently pinned runtime
manifest. This is trusted local code, never document/model-provided code.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from hashlib import sha256
import re
from typing import Callable


CONSTANTS = frozenset({"_WORD", "_REFERENT", "_ACRONYM", "_STOP",
    "_MULTIPLE_PRIOR_TOPICS", "_CURRENT_DOCUMENT_DEMONSTRATIVE", "_NAMED_FIRST_CLAUSE"})
FUNCTIONS = frozenset({"navigation_terms", "navigation_query", "navigation_query_v4"})


class RawQueryError(ValueError):
    """Fixed content-free refusal."""


@dataclass(frozen=True, slots=True)
class RawQueryResolver:
    source_sha256: str
    _query: Callable = field(repr=False)

    def __call__(self, question: str) -> str | None:
        # No history can be supplied through this interface.
        return self._query(question, ())


def from_production_source(raw: bytes, *, source_sha256: str) -> RawQueryResolver:
    if (type(raw) is not bytes or not 0 < len(raw) <= 256 * 1024
            or type(source_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", source_sha256) is None
            or sha256(raw).hexdigest() != source_sha256):
        raise RawQueryError("raw_query_source_changed")
    try:
        tree = ast.parse(raw)
        selected, seen = [], set()
        for node in tree.body:
            name = None
            if type(node) is ast.Assign and len(node.targets) == 1 and type(node.targets[0]) is ast.Name:
                name = node.targets[0].id
                if name not in CONSTANTS:
                    continue
            elif type(node) is ast.FunctionDef and node.name in FUNCTIONS:
                name = node.name
            else:
                continue
            if name in seen:
                raise RawQueryError("raw_query_source_invalid")
            seen.add(name)
            selected.append(node)
        if seen != CONSTANTS | FUNCTIONS:
            raise RawQueryError("raw_query_source_invalid")
        future = ast.parse("from __future__ import annotations").body[0]
        module = ast.fix_missing_locations(ast.Module(body=[future, *selected], type_ignores=[]))
        namespace = {"re": re, "__name__": "cardchemy_pinned_raw_query_projection"}
        exec(compile(module, "<pinned-production-raw-query>", "exec"), namespace)
        return RawQueryResolver(source_sha256, namespace["navigation_query_v4"])
    except (SyntaxError, UnicodeError, TypeError, KeyError):
        raise RawQueryError("raw_query_source_invalid") from None
