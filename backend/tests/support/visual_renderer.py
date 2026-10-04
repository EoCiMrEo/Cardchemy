"""Deterministic raster substitute for Windows database tests; archive stays real."""
import hashlib

from app.services import source_visual_preparation
from app.services.knowledge_pdf_renderer import RenderedPdfPage
from tests.test_source_judgment_visual import png


async def fake_render(data, sha, pages):
    assert hashlib.sha256(data).hexdigest() == sha and data.startswith(b"%PDF-")
    raw = png()
    return tuple(RenderedPdfPage(page, sha, raw, hashlib.sha256(raw).hexdigest(),
                                 2, 2, "c" * 64) for page in pages)


def fake_visual_renderer(monkeypatch):
    monkeypatch.setattr(source_visual_preparation, "_render", fake_render)
