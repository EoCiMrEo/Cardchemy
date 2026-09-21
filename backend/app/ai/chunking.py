"""Structure-aware, token-bounded chunking and global card allocation."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
import unicodedata
from collections.abc import Callable

from app.ai.contracts import DocumentChunk, ExtractedDocument


_HEADING_PREFIX = re.compile(
    r"^(?:chapter|section|part|unit|lesson|module|appendix)\b|^\d+(?:\.\d+)*[.)]?\s+",
    re.IGNORECASE,
)
_SENTENCE_END = frozenset(".!?;:")


def estimate_tokens(text: str) -> int:
    """Return a deterministic, conservative text-token estimate.

    Providers report actual usage after a request. This local estimate is used
    before any paid/network call and deliberately errs high for non-ASCII text.
    """

    normalized = unicodedata.normalize("NFKC", text)
    if not normalized:
        return 0
    character_estimate = math.ceil(len(normalized) / 3)
    byte_estimate = math.ceil(len(normalized.encode("utf-8")) / 4)
    lexical_estimate = len(re.findall(r"\w+|[^\w\s]", normalized, re.UNICODE))
    return max(1, character_estimate, byte_estimate, lexical_estimate)


def _looks_like_heading(value: str) -> bool:
    text = value.strip()
    if not text or len(text) > 160 or text[-1] in _SENTENCE_END:
        return False
    if _HEADING_PREFIX.search(text):
        return True
    words = text.split()
    if not 1 <= len(words) <= 14:
        return False
    letters = [character for character in text if character.isalpha()]
    if letters and all(character.isupper() for character in letters):
        return True
    return sum(word[:1].isupper() for word in words) >= max(1, math.ceil(len(words) * 0.8))


def _page_units(text: str) -> list[tuple[str | None, str]]:
    """Return section-tagged paragraph units without crossing page boundaries."""

    blocks = [block.strip() for block in re.split(r"\n\s*\n+", text) if block.strip()]
    section: str | None = None
    units: list[tuple[str | None, str]] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if _looks_like_heading(lines[0]):
            section = lines[0][:255]
            if len(lines) == 1:
                continue
            block = "\n".join(lines[1:]).strip()
        units.append((section, block))
    return units


def _tail_within_budget(text: str, token_budget: int) -> str:
    if token_budget <= 0:
        return ""
    words = text.split()
    start = len(words)
    while start > 0:
        candidate = " ".join(words[start - 1 :])
        if estimate_tokens(candidate) > token_budget:
            break
        start -= 1
    return " ".join(words[start:])


def _split_oversized_unit(
    text: str, *, max_tokens: int, overlap_tokens: int
) -> list[str]:
    words = text.split()
    if not words:
        return []
    pieces: list[str] = []
    start = 0
    while start < len(words):
        low = start + 1
        high = len(words)
        best = low
        while low <= high:
            middle = (low + high) // 2
            candidate = " ".join(words[start:middle])
            if estimate_tokens(candidate) <= max_tokens:
                best = middle
                low = middle + 1
            else:
                high = middle - 1
        piece = " ".join(words[start:best])
        if estimate_tokens(piece) > max_tokens:
            # A single pathological token can exceed the estimator budget. It
            # is still kept intact so grounding quotes are never fabricated.
            piece = words[start]
            best = start + 1
        pieces.append(piece)
        if best >= len(words):
            break
        next_start = best
        if overlap_tokens:
            overlap_start = best
            while overlap_start > start:
                candidate = " ".join(words[overlap_start - 1 : best])
                if estimate_tokens(candidate) > overlap_tokens:
                    break
                overlap_start -= 1
            next_start = max(start + 1, overlap_start)
        start = next_start
    return pieces


@dataclass(frozen=True)
class _PendingChunk:
    text: str
    page_number: int
    section: str | None


@dataclass(frozen=True)
class PreparedDocument:
    """One immutable extraction/chunking result shared by generation and RAG.

    Callers must prepare once and pass the same object to every consumer. This
    prevents provenance drift caused by independently re-chunking a PDF.
    """

    document: ExtractedDocument
    chunks: tuple[DocumentChunk, ...]


def prepare_document(
    document: ExtractedDocument,
    *,
    max_tokens: int,
    overlap_tokens: int = 0,
) -> PreparedDocument:
    chunks = tuple(
        chunk_document(
            document,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
        )
    )
    page_numbers = {page.page_number for page in document.pages}
    if any(chunk.page_number not in page_numbers for chunk in chunks):
        raise ValueError("Prepared chunks must reference extracted pages")
    return PreparedDocument(document=document, chunks=chunks)


def chunk_document(
    document: ExtractedDocument,
    *,
    max_tokens: int,
    overlap_tokens: int = 0,
) -> list[DocumentChunk]:
    """Split by pages, headings, and paragraphs under a token ceiling."""

    if max_tokens < 1:
        raise ValueError("max_tokens must be positive")
    if overlap_tokens < 0 or overlap_tokens >= max_tokens:
        raise ValueError("overlap_tokens must be non-negative and lower than max_tokens")

    pending: list[_PendingChunk] = []
    for page in document.pages:
        current = ""
        current_section: str | None = None
        for section, unit in _page_units(page.text):
            if estimate_tokens(unit) > max_tokens:
                if current:
                    pending.append(_PendingChunk(current, page.page_number, current_section))
                    current = ""
                for piece in _split_oversized_unit(
                    unit, max_tokens=max_tokens, overlap_tokens=overlap_tokens
                ):
                    pending.append(_PendingChunk(piece, page.page_number, section))
                current_section = section
                continue

            separator = "\n\n" if current else ""
            candidate = f"{current}{separator}{unit}"
            if current and (section != current_section or estimate_tokens(candidate) > max_tokens):
                pending.append(_PendingChunk(current, page.page_number, current_section))
                overlap = _tail_within_budget(current, overlap_tokens)
                candidate = f"{overlap}\n\n{unit}" if overlap else unit
                if estimate_tokens(candidate) > max_tokens:
                    candidate = unit
            current = candidate
            current_section = section
        if current:
            pending.append(_PendingChunk(current, page.page_number, current_section))

    return [
        DocumentChunk(
            chunk_id=f"chunk-{index:04d}-p{item.page_number}",
            text=item.text,
            page_number=item.page_number,
            section=item.section,
            token_count=estimate_tokens(item.text),
        )
        for index, item in enumerate(pending, start=1)
        if item.text.strip()
    ]


def allocate_card_targets(
    chunks: list[DocumentChunk], target_count: int
) -> dict[str, int]:
    """Use Hamilton apportionment so all chunk quotas sum to the global target."""

    if target_count < 1:
        raise ValueError("target_count must be positive")
    if not chunks:
        raise ValueError("at least one non-empty chunk is required")

    total_weight = sum(max(1, chunk.token_count) for chunk in chunks)
    exact = [target_count * max(1, chunk.token_count) / total_weight for chunk in chunks]
    allocations = [math.floor(value) for value in exact]
    remaining = target_count - sum(allocations)
    remainder_order = sorted(
        range(len(chunks)),
        key=lambda index: (-(exact[index] - allocations[index]), index),
    )
    for index in remainder_order[:remaining]:
        allocations[index] += 1
    return {chunk.chunk_id: allocations[index] for index, chunk in enumerate(chunks)}


def pack_chunks_for_requests(
    chunks: list[DocumentChunk],
    *,
    max_tokens: int,
    estimate_prompt_tokens: Callable[[tuple[DocumentChunk, ...]], int],
    max_chunks: int = 500,
) -> list[tuple[DocumentChunk, ...]]:
    """Greedily pack logical chunks without changing their provenance.

    ``estimate_prompt_tokens`` receives the complete candidate pack so callers
    can include JSON, system instructions, and other request-specific overhead.
    A single logical chunk is never split merely to meet the soft request
    target; the pipeline's context-window check remains the hard safety bound.
    """

    if max_tokens < 1:
        raise ValueError("max_tokens must be positive")
    if max_chunks < 1:
        raise ValueError("max_chunks must be positive")

    packs: list[tuple[DocumentChunk, ...]] = []
    current: list[DocumentChunk] = []
    for chunk in chunks:
        candidate = tuple([*current, chunk])
        if current and (
            len(candidate) > max_chunks
            or estimate_prompt_tokens(candidate) > max_tokens
        ):
            packs.append(tuple(current))
            current = [chunk]
        else:
            current.append(chunk)
    if current:
        packs.append(tuple(current))
    return packs
