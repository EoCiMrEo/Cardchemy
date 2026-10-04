"""Admission-bound visual-v5 projection over unchanged authorized v2 pages."""
from __future__ import annotations

from datetime import datetime
from typing import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import source_judgment_visual_v5 as contract
from app.ai.related_evidence import RelatedExcerptSelection
from app.ai.source_navigation_context_v1 import LiteralSubjectAnchor
from app.config import Settings
from app.services.knowledge_retrieval import KnowledgeRetriever
from app.services.source_visual_preparation import PreparedVisualSources, prepare_visual_sources


async def prepare_visual_sources_v5(
    db: AsyncSession, *, settings: Settings, retriever: KnowledgeRetriever,
    subject_id: UUID, question: str, selections: Sequence[RelatedExcerptSelection],
    snapshot: contract.SubjectAdmissionSnapshot, checked_at: datetime,
    raw_navigation_query: str | None, preceding_question: str | None = None,
    anchor: LiteralSubjectAnchor | None = None,
) -> PreparedVisualSources:
    """Authenticate/render current pages, then project only the admitted subject.

    The unchanged v2 preparer owns archive authentication, current-source
    authorization, exact text/PNG provenance and finite rendering cleanup.
    The worker separately rechecks the immutable context and current grants
    after rendering and before dispatch; this supplied snapshot is not a grant.
    """
    binding = contract.bind_question_context(
        question, snapshot, checked_at=checked_at, raw_navigation_query=raw_navigation_query,
        preceding_question=preceding_question, anchor=anchor,
    )
    contract._require(binding.status != "needs_clarification", "question_context_unresolved")
    contract._require(snapshot.current.subject_id == subject_id, "admission_scope_invalid")
    prepared = await prepare_visual_sources(
        db, settings=settings, retriever=retriever, subject_id=subject_id,
        question=question, selections=selections,
    )
    # The server-created preparer returns a fresh owned request with group G01.
    # Only the first user text and trusted system context suffix change. Every
    # issued candidate, exact cue, PNG byte, generation/schema guard stays intact.
    request = prepared.request
    contract._require(request["contents"][0]["parts"][0] == {
        "text": contract.canonical({"group_id": "G01", "question": question}).decode("utf-8"),
    }, "prepared_question_binding_invalid")
    if binding.anchor is not None:
        request["contents"][0]["parts"][0]["text"] = contract.canonical({
            "group_id": "G01", "question": question,
            "referent_context": {"literal_subject": binding.anchor.subject, "purpose": contract.CONTEXT_PURPOSE},
        }).decode("utf-8")
        request["systemInstruction"]["parts"][0]["text"] += contract.CONTEXT_SYSTEM_SUFFIX
        contract._require(len(contract.canonical(request)) <= contract.MAX_REQUEST_BYTES, "request_byte_limit")
        contract._require(contract.estimate_input_tokens(request) <= contract.MAX_INPUT_TOKENS,
                          "estimated_input_budget")
    return PreparedVisualSources(request, prepared.bindings)
