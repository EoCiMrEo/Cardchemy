"""Current authorized pages to faithful visual cues; no provider or persistence."""
from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
import hashlib
import threading
from typing import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import source_judgment_visual as contract
from app.ai.related_evidence import RelatedExcerptSelection
from app.ai.source_navigation_context import LiteralSubjectAnchor
from app.config import Settings
from app.models.knowledge import SubjectDocumentContentRevision, SubjectDocumentPdf
from app.services.knowledge_pdf import read_complete_pdf_archive
from app.services.knowledge_pdf_renderer import render_pdf_pages
from app.services.knowledge_retrieval import KnowledgeRetriever, KnowledgeSourceUnavailable


@dataclass(frozen=True)
class PdfSourceBinding:
    document_id: UUID
    content_revision_id: UUID
    subject_id: UUID
    source_sha256: str
    page_count: int


@dataclass(frozen=True)
class PreparedVisualSources:
    request: dict
    bindings: tuple[PdfSourceBinding, ...]


async def check_pdf_bindings(db: AsyncSession, bindings: Sequence[PdfSourceBinding]) -> None:
    """Metadata recheck only; caller independently verifies access/session/lease."""
    for binding in bindings:
        pdf = await db.get(SubjectDocumentPdf, binding.content_revision_id)
        revision = await db.get(SubjectDocumentContentRevision, binding.content_revision_id)
        if (pdf is None or revision is None or
            pdf.document_id != binding.document_id or pdf.subject_id != binding.subject_id or
            pdf.source_sha256 != binding.source_sha256 or pdf.page_count != binding.page_count or
            revision.document_id != binding.document_id or revision.subject_id != binding.subject_id or
            revision.source_sha256 != binding.source_sha256 or revision.actual_page_count != binding.page_count or
            revision.status != "ready" or revision.is_active is not True or
            revision.reviewed_at is None or revision.published_at is None):
            raise KnowledgeSourceUnavailable()


async def _render(data: bytes, source_sha: str, pages: list[int]):
    cancel = threading.Event()
    task = asyncio.create_task(asyncio.to_thread(
        render_pdf_pages, data, source_sha256=source_sha, page_numbers=pages, cancel_event=cancel,
        adaptive=True))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        cancel.set()
        # Wait for bounded child termination and exclusive Temp cleanup before
        # allowing the worker to abandon this preparation. No dispatch follows.
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if task.done() and not task.cancelled():
            with suppress(Exception):
                task.result()
        raise


async def prepare_visual_pages(
    db: AsyncSession, *, settings: Settings, retriever: KnowledgeRetriever,
    subject_id: UUID, question: str, selections: Sequence[RelatedExcerptSelection],
) -> PreparedVisualSources:
    """Read only currently eligible anchors; worker must recheck before dispatch."""
    if not 1 <= len(selections) <= 4:
        raise KnowledgeSourceUnavailable()
    ids = tuple(item.source.chunk_id for item in selections)
    current = {source.chunk_id: source for source in await retriever.read_current_sources(ids)}
    pages = await retriever.read_current_source_pages(ids, max_pages=4, max_tokens=8192)
    if len(current) != len(selections) or len(pages) != len(selections):
        raise KnowledgeSourceUnavailable()
    groups: dict[UUID, list[RelatedExcerptSelection]] = {}
    for item in selections:
        source = current.get(item.source.chunk_id)
        if (source is None or item.source_kind != "canonical_page" or item.page_content is None or
            pages.get(item.source.chunk_id) != item.page_content or
            any(getattr(source, key) != getattr(item.source, key) for key in (
                "document_id", "content_revision_id", "index_revision_id", "page_number",
                "content", "section", "embedding_space_hash", "corpus_revision")) or
            not 0 <= item.start_offset < item.end_offset <= len(item.page_content) or
            item.end_offset - item.start_offset > contract.MAX_CUE_CHARS or
            item.page_content[item.start_offset:item.end_offset] != item.quote):
            raise KnowledgeSourceUnavailable()
        groups.setdefault(source.content_revision_id, []).append(item)
    bindings, images, aliases = [], {}, {}
    for ordinal, (revision_id, selected) in enumerate(groups.items(), 1):
        pdf = await db.get(SubjectDocumentPdf, revision_id)
        if pdf is None:
            raise KnowledgeSourceUnavailable()
        binding = PdfSourceBinding(selected[0].source.document_id, revision_id, subject_id,
                                   pdf.source_sha256, pdf.page_count)
        await check_pdf_bindings(db, (binding,))
        page_numbers = [item.source.page_number for item in selected]
        if len(set(page_numbers)) != len(page_numbers) or any(not 1 <= page <= pdf.page_count for page in page_numbers):
            raise KnowledgeSourceUnavailable()
        data = await read_complete_pdf_archive(db, settings=settings, pdf=pdf)
        rendered = await _render(data, binding.source_sha256, page_numbers)
        if tuple(page.physical_page for page in rendered) != tuple(page_numbers):
            raise KnowledgeSourceUnavailable()
        alias = f"D{ordinal:02d}"  # Provider sees no user/job/document UUID or filename.
        aliases[revision_id] = alias
        for page in rendered:
            images[(revision_id, page.physical_page)] = page.image_binding(alias)
        bindings.append(binding)
    candidates = []
    for ordinal, item in enumerate(selections, 1):
        page = item.page_content
        start = max(0, item.start_offset - min(160, max(0, contract.MAX_CONTEXT_CHARS - len(item.quote))))
        end = min(len(page), start + contract.MAX_CONTEXT_CHARS)
        if end < item.end_offset:
            start, end = item.end_offset - contract.MAX_CONTEXT_CHARS, item.end_offset
        image = images[(item.source.content_revision_id, item.source.page_number)]
        candidates.append({
            "id": f"S{ordinal:02d}", "pair_id": f"P{ordinal:02d}",
            "document_id": aliases[item.source.content_revision_id], "page": item.source.page_number,
            "pdf_sha256": image["pdf_sha256"], "page_text_sha256": hashlib.sha256(page.encode("utf-8")).hexdigest(),
            "context": page[start:end], "context_start": start, "context_end": end,
            "cue": item.quote, "cue_start": item.start_offset, "cue_end": item.end_offset,
            "image": image,
        })
    request = contract.build_page_request(question, candidates, group_id="G01")
    return PreparedVisualSources(request, tuple(bindings))


async def prepare_visual_sources(
    db: AsyncSession, *, settings: Settings, retriever: KnowledgeRetriever,
    subject_id: UUID, question: str, selections: Sequence[RelatedExcerptSelection],
    snapshot: contract.SubjectAdmissionSnapshot, checked_at: datetime,
    raw_navigation_query: str | None, preceding_question: str | None = None,
    anchor: LiteralSubjectAnchor | None = None,
) -> PreparedVisualSources:
    """Authenticate/render current pages, then project only the admitted subject.

    The page preparer owns archive authentication, current-source
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
    prepared = await prepare_visual_pages(
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
