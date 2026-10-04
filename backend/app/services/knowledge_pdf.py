"""Revision-bound encrypted original PDFs, with bounded authenticated ranges."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import os
import re

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.knowledge import SubjectDocumentContentRevision, SubjectDocumentPdf, SubjectDocumentPdfBlock
from app.services.knowledge_lock import acquire_knowledge_write_lock

BLOCK_BYTES = 1024 * 1024
MAX_PDF_BYTES = 100 * BLOCK_BYTES
MAX_KNOWLEDGE_PAGES = 100
MAX_RANGE_BYTES = 8 * BLOCK_BYTES
MAX_SUBJECT_BYTES = 256 * BLOCK_BYTES
MAX_OWNER_BYTES = 512 * BLOCK_BYTES
MAX_DEPLOYMENT_BYTES = 2048 * BLOCK_BYTES


class KnowledgePdfError(RuntimeError):
    """Safe archive failure; never includes source bytes or crypto details."""

    def __init__(self, code: str, message: str, status_code: int = 409):
        super().__init__(message)
        self.code, self.safe_message, self.status_code = code, message, status_code


@dataclass(frozen=True)
class PdfRange:
    start: int
    end: int  # Exclusive.
    partial: bool


def parse_pdf_range(value: str | None, size: int) -> PdfRange:
    """Require exactly one byte range bounded by the public transport limit."""
    if not 0 < size <= MAX_PDF_BYTES:
        raise KnowledgePdfError("knowledge_pdf_unavailable", "Original PDF is unavailable.", 404)
    if value is None:
        raise KnowledgePdfError("knowledge_pdf_range_required", "Request a bounded PDF byte range.", 400)
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value.strip())
    if match is None or not any(match.groups()) or len(value) > 100:
        raise KnowledgePdfError("knowledge_pdf_invalid_range", "The requested PDF range is unavailable.", 416)
    left, right = match.groups()
    if not left:
        count = int(right)
        if count <= 0:
            raise KnowledgePdfError("knowledge_pdf_invalid_range", "The requested PDF range is unavailable.", 416)
        start, end = max(0, size - count), size
    else:
        start = int(left)
        end = min(size, int(right) + 1) if right else min(size, start + MAX_RANGE_BYTES)
    if start >= size or end <= start or end - start > MAX_RANGE_BYTES:
        raise KnowledgePdfError("knowledge_pdf_invalid_range", "The requested PDF range is unavailable.", 416)
    return PdfRange(start, end, True)


def _aad(pdf: SubjectDocumentPdf, number: int, plaintext_size: int) -> bytes:
    values = (
        str(pdf.content_revision_id), str(pdf.document_id), str(pdf.subject_id), str(pdf.uploader_id),
        pdf.source_sha256, str(pdf.byte_size), str(pdf.page_count), str(pdf.block_count),
        str(pdf.key_version), str(number), str(plaintext_size),
    )
    return b"cardchemy-knowledge-pdf-block:v1:" + "|".join(values).encode("ascii")


def _key(settings: Settings) -> bytes:
    try:
        return settings.knowledge_pdf_encryption_key_bytes
    except ValueError:
        raise KnowledgePdfError("knowledge_pdf_key_unavailable", "Original PDF storage is not configured.", 503) from None


def encrypt_pdf_blocks(settings: Settings, pdf: SubjectDocumentPdf, data: bytes) -> list[SubjectDocumentPdfBlock]:
    cipher = AESGCM(_key(settings))
    if (
        not 0 < len(data) <= MAX_PDF_BYTES or len(data) != pdf.byte_size
        or hashlib.sha256(data).hexdigest() != pdf.source_sha256
        or pdf.block_count != (len(data) + BLOCK_BYTES - 1) // BLOCK_BYTES
        or pdf.key_version != 1 or not 1 <= pdf.page_count <= min(settings.pdf_max_pages, MAX_KNOWLEDGE_PAGES)
    ):
        raise KnowledgePdfError("knowledge_pdf_revision_mismatch", "Original PDF does not match this Knowledge revision.")
    result = []
    for number, start in enumerate(range(0, len(data), BLOCK_BYTES)):
        part = data[start:start + BLOCK_BYTES]
        nonce = os.urandom(12)
        result.append(SubjectDocumentPdfBlock(
            content_revision_id=pdf.content_revision_id, block_number=number,
            plaintext_size=len(part), nonce=nonce,
            payload=cipher.encrypt(nonce, part, _aad(pdf, number, len(part))),
        ))
    return result


async def archive_pdf(
    db: AsyncSession, *, settings: Settings, revision: SubjectDocumentContentRevision, data: bytes,
) -> SubjectDocumentPdf:
    """Caller owns the fenced transaction; reserve and persist atomically."""
    await acquire_knowledge_write_lock(db)
    if not 0 < len(data) <= min(settings.pdf_max_upload_bytes, MAX_PDF_BYTES):
        raise KnowledgePdfError("knowledge_pdf_too_large", "Original PDF exceeds the storage limit.", 413)
    source_digest = await asyncio.to_thread(lambda: hashlib.sha256(data).hexdigest())
    if source_digest != revision.source_sha256:
        raise KnowledgePdfError("knowledge_pdf_revision_mismatch", "Original PDF does not match this Knowledge revision.")
    current = await db.get(SubjectDocumentPdf, revision.id)
    if current is not None:
        if (
            current.document_id != revision.document_id
            or current.subject_id != revision.subject_id
            or current.uploader_id != revision.uploader_id
            or current.source_sha256 != revision.source_sha256
            or current.byte_size != len(data)
            or current.page_count != revision.reserved_page_count
        ):
            raise KnowledgePdfError("knowledge_pdf_revision_mismatch", "Original PDF does not match this Knowledge revision.")
        # A matching uploaded file does not prove that the stored ciphertext can
        # still be opened with this installation's configured archive key.
        await authenticate_complete_pdf_archive(db, settings=settings, pdf=current)
        return current
    _key(settings)
    for predicate, limit in (
        (SubjectDocumentPdf.subject_id == revision.subject_id, MAX_SUBJECT_BYTES),
        (SubjectDocumentPdf.uploader_id == revision.uploader_id, MAX_OWNER_BYTES),
        (None, MAX_DEPLOYMENT_BYTES),
    ):
        query = select(func.coalesce(func.sum(SubjectDocumentPdf.byte_size), 0))
        if predicate is not None:
            query = query.where(predicate)
        if int(await db.scalar(query) or 0) + len(data) > limit:
            raise KnowledgePdfError("knowledge_pdf_capacity_exceeded", "Original PDF storage capacity is exceeded.", 503)
    pdf = SubjectDocumentPdf(
        content_revision_id=revision.id, document_id=revision.document_id,
        subject_id=revision.subject_id, uploader_id=revision.uploader_id,
        source_sha256=revision.source_sha256, byte_size=len(data),
        page_count=revision.reserved_page_count,
        block_count=(len(data) + BLOCK_BYTES - 1) // BLOCK_BYTES, key_version=1,
    )
    blocks = await asyncio.to_thread(encrypt_pdf_blocks, settings, pdf, data)
    db.add(pdf)
    await db.flush()
    db.add_all(blocks)
    await db.flush()
    return pdf


def _decrypt_range(settings: Settings, pdf: SubjectDocumentPdf,
                   blocks: list[SubjectDocumentPdfBlock], span: PdfRange) -> bytes:
    try:
        cipher = AESGCM(_key(settings))
        first, last = span.start // BLOCK_BYTES, (span.end - 1) // BLOCK_BYTES
        if [block.block_number for block in blocks] != list(range(first, last + 1)):
            raise ValueError("incomplete")
        pieces = []
        for block in blocks:
            expected = min(BLOCK_BYTES, pdf.byte_size - block.block_number * BLOCK_BYTES)
            if block.plaintext_size != expected or len(block.nonce) != 12 or len(block.payload) != expected + 16:
                raise ValueError("invalid block")
            part = cipher.decrypt(bytes(block.nonce), bytes(block.payload), _aad(pdf, block.block_number, expected))
            begin = max(0, span.start - block.block_number * BLOCK_BYTES)
            end = min(expected, span.end - block.block_number * BLOCK_BYTES)
            pieces.append(part[begin:end])
        data = b"".join(pieces)
        if len(data) != span.end - span.start:
            raise ValueError("invalid length")
        if not span.partial and hashlib.sha256(data).hexdigest() != pdf.source_sha256:
            raise ValueError("invalid digest")
        return data
    except Exception:
        raise KnowledgePdfError("knowledge_pdf_unavailable", "Original PDF is unavailable.", 404) from None


async def read_pdf_range(
    db: AsyncSession, *, settings: Settings, pdf: SubjectDocumentPdf, range_header: str | None,
) -> tuple[bytes, PdfRange]:
    """Authorization must be repeated by caller before each range read."""
    span = parse_pdf_range(range_header, pdf.byte_size)
    blocks = list((await db.scalars(select(SubjectDocumentPdfBlock).where(
        SubjectDocumentPdfBlock.content_revision_id == pdf.content_revision_id,
        SubjectDocumentPdfBlock.block_number >= span.start // BLOCK_BYTES,
        SubjectDocumentPdfBlock.block_number <= (span.end - 1) // BLOCK_BYTES,
    ).order_by(SubjectDocumentPdfBlock.block_number))).all())
    return await asyncio.to_thread(_decrypt_range, settings, pdf, blocks, span), span


def _check_archive_bounds(pdf: SubjectDocumentPdf) -> None:
    if (
        not 0 < pdf.byte_size <= MAX_PDF_BYTES
        or pdf.block_count != (pdf.byte_size + BLOCK_BYTES - 1) // BLOCK_BYTES
        or not 1 <= pdf.page_count <= MAX_KNOWLEDGE_PAGES
        or pdf.key_version != 1
    ):
        raise KnowledgePdfError("knowledge_pdf_unavailable", "Original PDF is unavailable.", 404)


async def probe_pdf_archive(
    db: AsyncSession, *, settings: Settings, pdf: SubjectDocumentPdf,
) -> None:
    """Bounded HEAD preflight for key and shape, not a scan of interior bytes."""
    _check_archive_bounds(pdf)
    shape = (await db.execute(select(
        func.count(), func.min(SubjectDocumentPdfBlock.block_number),
        func.max(SubjectDocumentPdfBlock.block_number),
    ).where(SubjectDocumentPdfBlock.content_revision_id == pdf.content_revision_id))).one()
    if tuple(shape) != (pdf.block_count, 0, pdf.block_count - 1):
        raise KnowledgePdfError("knowledge_pdf_unavailable", "Original PDF is unavailable.", 404)
    # AES-GCM authenticates the complete first/last block even though only one
    # byte is returned. This detects a wrong configured key without a 100 MiB
    # HEAD; each GET authenticates every block it actually serves.
    await read_pdf_range(db, settings=settings, pdf=pdf, range_header="bytes=0-0")
    if pdf.block_count > 1:
        last = pdf.byte_size - 1
        await read_pdf_range(db, settings=settings, pdf=pdf, range_header=f"bytes={last}-{last}")


async def authenticate_complete_pdf_archive(
    db: AsyncSession, *, settings: Settings, pdf: SubjectDocumentPdf,
) -> None:
    """Validate every stored block and the original SHA before idempotent reuse."""
    _check_archive_bounds(pdf)
    digest = hashlib.sha256()
    for first in range(0, pdf.block_count, MAX_RANGE_BYTES // BLOCK_BYTES):
        last = min(pdf.block_count - 1, first + MAX_RANGE_BYTES // BLOCK_BYTES - 1)
        blocks = list((await db.scalars(select(SubjectDocumentPdfBlock).where(
            SubjectDocumentPdfBlock.content_revision_id == pdf.content_revision_id,
            SubjectDocumentPdfBlock.block_number >= first,
            SubjectDocumentPdfBlock.block_number <= last,
        ).order_by(SubjectDocumentPdfBlock.block_number))).all())
        span = PdfRange(first * BLOCK_BYTES, min(pdf.byte_size, (last + 1) * BLOCK_BYTES), True)
        await asyncio.to_thread(lambda: digest.update(_decrypt_range(settings, pdf, blocks, span)))
    if digest.hexdigest() != pdf.source_sha256:
        raise KnowledgePdfError("knowledge_pdf_unavailable", "Original PDF is unavailable.", 404)


async def read_complete_pdf_archive(
    db: AsyncSession, *, settings: Settings, pdf: SubjectDocumentPdf,
) -> bytes:
    """Authenticate a bounded original for an isolated worker-side renderer.

    The caller must authorize the current revision before this read and again
    before any provider dispatch or persistence. This helper grants no access,
    commits nothing and never returns a partially authenticated document.
    """
    _check_archive_bounds(pdf)
    parts: list[bytes] = []
    digest = hashlib.sha256()
    for first in range(0, pdf.block_count, MAX_RANGE_BYTES // BLOCK_BYTES):
        last = min(pdf.block_count - 1, first + MAX_RANGE_BYTES // BLOCK_BYTES - 1)
        blocks = list((await db.scalars(select(SubjectDocumentPdfBlock).where(
            SubjectDocumentPdfBlock.content_revision_id == pdf.content_revision_id,
            SubjectDocumentPdfBlock.block_number >= first,
            SubjectDocumentPdfBlock.block_number <= last,
        ).order_by(SubjectDocumentPdfBlock.block_number))).all())
        span = PdfRange(first * BLOCK_BYTES, min(pdf.byte_size, (last + 1) * BLOCK_BYTES), True)
        part = await asyncio.to_thread(_decrypt_range, settings, pdf, blocks, span)
        digest.update(part)
        parts.append(part)
    if digest.hexdigest() != pdf.source_sha256:
        raise KnowledgePdfError("knowledge_pdf_unavailable", "Original PDF is unavailable.", 404)
    return await asyncio.to_thread(b"".join, parts)
