"""Synthetic encrypted archive reads for future isolated rendering."""
from types import SimpleNamespace

import pytest

from app.services.knowledge_pdf import (
    BLOCK_BYTES, KnowledgePdfError, encrypt_pdf_blocks, read_complete_pdf_archive,
)
from tests.test_knowledge_pdf import _archive, _settings


class ArchiveDb:
    def __init__(self, blocks):
        self.blocks = blocks
        self.queries = 0

    async def scalars(self, query):
        self.queries += 1
        return SimpleNamespace(all=lambda: self.blocks)


@pytest.mark.asyncio
async def test_complete_worker_read_authenticates_every_block_without_commit():
    data = b"%PDF-1.7\n" + b"a" * (2 * BLOCK_BYTES) + b"tail"
    pdf = _archive(data)
    db = ArchiveDb(encrypt_pdf_blocks(_settings(), pdf, data))
    assert await read_complete_pdf_archive(db, settings=_settings(), pdf=pdf) == data
    assert db.queries == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["interior", "missing", "reordered", "wrong_sha", "wrong_key", "over_limit"])
async def test_renderer_never_receives_partial_or_unbound_original(mutation):
    data = b"%PDF-1.7\n" + b"a" * (2 * BLOCK_BYTES) + b"tail"
    pdf = _archive(data)
    settings = _settings()
    blocks = encrypt_pdf_blocks(settings, pdf, data)
    if mutation == "interior":
        blocks[1].payload = bytes(blocks[1].payload[:-1]) + bytes([blocks[1].payload[-1] ^ 1])
    elif mutation == "missing":
        blocks.pop(1)
    elif mutation == "reordered":
        blocks.reverse()
    elif mutation == "wrong_sha":
        pdf.source_sha256 = "f" * 64
    elif mutation == "wrong_key":
        settings = settings.model_copy(update={"knowledge_pdf_encryption_key": None})
    else:
        pdf.byte_size = 101 * BLOCK_BYTES
    with pytest.raises(KnowledgePdfError):
        await read_complete_pdf_archive(ArchiveDb(blocks), settings=settings, pdf=pdf)
