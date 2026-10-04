"""Authorized synthetic page/archive/image bindings; no private or provider data."""
import asyncio
from dataclasses import replace
import hashlib
from types import SimpleNamespace
import threading
from uuid import uuid4

import pytest

from app.services import source_visual_preparation as preparation
from app.services.knowledge_pdf_renderer import RenderedPdfPage
from app.services.knowledge_retrieval import KnowledgeSourceUnavailable
from tests.test_source_judgment_visual import png
from tests.test_source_judgment_worker import _selection, _Retriever


def fixture():
    first, second = _selection(1), _selection(2)
    second = replace(second, source=replace(second.source,
        document_id=first.source.document_id, content_revision_id=first.source.content_revision_id))
    subject = uuid4()
    pdf = SimpleNamespace(document_id=first.source.document_id, subject_id=subject,
        source_sha256="a" * 64, page_count=2)
    revision = SimpleNamespace(document_id=pdf.document_id, subject_id=subject,
        source_sha256=pdf.source_sha256, actual_page_count=2, status="ready", is_active=True,
        reviewed_at=object(), published_at=object())
    class Db:
        async def get(self, model, identity):
            return pdf if model is preparation.SubjectDocumentPdf else revision
    return (first, second), subject, pdf, revision, Db()


@pytest.mark.asyncio
async def test_grouped_archive_render_and_opaque_provider_projection(monkeypatch):
    selections, subject, pdf, revision, db = fixture()
    reads, renders = [], []
    async def archive(_db, **kwargs):
        reads.append(kwargs["pdf"])
        return b"synthetic authenticated PDF bytes"
    async def render(data, sha, pages):
        renders.append(pages)
        raw = png()
        return tuple(RenderedPdfPage(page, sha, raw, hashlib.sha256(raw).hexdigest(), 2, 2, "c" * 64) for page in pages)
    monkeypatch.setattr(preparation, "read_complete_pdf_archive", archive)
    monkeypatch.setattr(preparation, "_render", render)
    prepared = await preparation.prepare_visual_sources(db, settings=object(),
        retriever=_Retriever(tuple(item.source for item in selections)), subject_id=subject,
        question="How does the method update weights?", selections=selections)
    assert len(reads) == 1 and renders == [[1, 2]] and len(prepared.bindings) == 1
    raw = preparation.contract.canonical(prepared.request)
    assert str(subject).encode() not in raw and str(pdf.document_id).encode() not in raw
    assert prepared.request["contents"][0]["parts"][0]["text"].find("G01") >= 0


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["subject", "revision_sha", "unpublish", "inactive", "count", "missing_pdf"])
async def test_wrong_stale_or_missing_pdf_never_reaches_archive(monkeypatch, mutation):
    selections, subject, pdf, revision, db = fixture()
    if mutation == "subject":
        pdf.subject_id = uuid4()
    elif mutation == "revision_sha":
        revision.source_sha256 = "b" * 64
    elif mutation == "unpublish":
        revision.published_at = None
    elif mutation == "inactive":
        revision.is_active = False
    elif mutation == "count":
        revision.actual_page_count = 1
    else:
        async def get(model, identity):
            return None
        db.get = get
    async def forbidden(*args, **kwargs):
        pytest.fail("source must be current before decrypt/render")
    monkeypatch.setattr(preparation, "read_complete_pdf_archive", forbidden)
    with pytest.raises(KnowledgeSourceUnavailable):
        await preparation.prepare_visual_sources(db, settings=object(),
            retriever=_Retriever(tuple(item.source for item in selections)), subject_id=subject,
            question="How does the method update weights?", selections=selections)


@pytest.mark.asyncio
async def test_cancellation_waits_for_renderer_cleanup(monkeypatch):
    entered, cleaned = threading.Event(), threading.Event()
    def render(*args, cancel_event, **kwargs):
        entered.set()
        assert cancel_event.wait(2)
        cleaned.set()
        return ()
    monkeypatch.setattr(preparation, "render_pdf_pages", render)
    task = asyncio.create_task(preparation._render(b"synthetic", "a" * 64, [1]))
    assert await asyncio.to_thread(entered.wait, 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cleaned.is_set()


@pytest.mark.asyncio
async def test_repeated_cancellation_cannot_abandon_child_cleanup(monkeypatch):
    entered, release, cleaned = threading.Event(), threading.Event(), threading.Event()
    def render(*args, cancel_event, **kwargs):
        entered.set()
        assert cancel_event.wait(2)
        assert release.wait(2)
        cleaned.set()
        return ()
    monkeypatch.setattr(preparation, "render_pdf_pages", render)
    task = asyncio.create_task(preparation._render(b"synthetic", "a" * 64, [1]))
    assert await asyncio.to_thread(entered.wait, 2)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done() and not cleaned.is_set()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cleaned.is_set()
