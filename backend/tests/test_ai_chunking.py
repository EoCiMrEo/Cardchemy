from app.ai.chunking import allocate_card_targets, chunk_document, estimate_tokens
from app.ai.contracts import ExtractedDocument, ExtractedPage


def test_chunking_preserves_pages_sections_and_token_bounds():
    document = ExtractedDocument(
        pages=[
            ExtractedPage(
                page_number=1,
                text="CHAPTER ONE\n\nAlpha is the first letter.\n\nBeta is the second letter.",
            ),
            ExtractedPage(
                page_number=2,
                text="Section 2 Results\n\nGamma is the third letter. " * 12,
            ),
        ]
    )
    chunks = chunk_document(document, max_tokens=40, overlap_tokens=4)

    assert chunks
    assert {chunk.page_number for chunk in chunks} == {1, 2}
    assert any(chunk.section == "CHAPTER ONE" for chunk in chunks)
    assert all(chunk.token_count == estimate_tokens(chunk.text) for chunk in chunks)
    assert all(chunk.token_count <= 40 for chunk in chunks)
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)


def test_global_largest_remainder_allocation_is_exact_and_deterministic():
    document = ExtractedDocument(
        pages=[ExtractedPage(page_number=1, text="One fact.\n\nTwo facts here.\n\nThree facts are here.")]
    )
    chunks = chunk_document(document, max_tokens=4)

    allocation = allocate_card_targets(chunks, 2)

    assert sum(allocation.values()) == 2
    assert set(allocation) == {chunk.chunk_id for chunk in chunks}
    assert allocation == allocate_card_targets(chunks, 2)

