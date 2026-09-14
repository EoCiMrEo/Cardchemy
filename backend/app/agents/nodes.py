"""Compatibility imports for the Phase 4 pipeline.

Generation logic moved to :mod:`app.ai.pipeline`; this module intentionally has
no import-time provider client or model configuration.
"""

from app.ai.chunking import allocate_card_targets, chunk_document
from app.ai.grounding import append_if_distinct, validate_grounded_candidate

__all__ = [
    "allocate_card_targets",
    "append_if_distinct",
    "chunk_document",
    "validate_grounded_candidate",
]
