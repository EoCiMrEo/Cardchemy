from app.ai.contracts import DocumentChunk, GeneratedCardCandidate, ValidatedCard
from app.ai.grounding import append_if_distinct, duplicate_similarity, validate_grounded_candidate


def candidate(**updates) -> GeneratedCardCandidate:
    values = {
        "front": "What is Alpha?",
        "back": "Alpha",
        "options": ["Beta", "Alpha", "Gamma", "Delta"],
        "source_chunk_id": "chunk-0001-p1",
        "source_quote": "Alpha is the first letter.",
    }
    values.update(updates)
    return GeneratedCardCandidate(**values)


def test_grounding_derives_server_provenance_and_rejects_unsupported_values():
    chunk = DocumentChunk(
        chunk_id="chunk-0001-p1",
        text="Section One\nAlpha is the first letter.",
        page_number=1,
        section="Section One",
        token_count=10,
    )
    validated = validate_grounded_candidate(candidate(), {chunk.chunk_id: chunk})

    assert validated is not None
    assert validated.source_page == 1
    assert validated.source_section == "Section One"
    assert validate_grounded_candidate(
        candidate(source_quote="Invented quote containing Alpha"), {chunk.chunk_id: chunk}
    ) is None
    assert validate_grounded_candidate(
        candidate(back="Beta", options=["Beta", "Alpha", "Gamma", "Delta"]),
        {chunk.chunk_id: chunk},
    ) is None


def test_near_duplicate_detection_handles_question_boilerplate_and_punctuation():
    first = ValidatedCard(
        front_content="What is Alpha?",
        back_content="Alpha",
        options=["Alpha", "Beta", "Gamma", "Delta"],
        quality_score=1,
        source_snippet="Alpha is the first letter.",
        source_page=1,
    )
    paraphrase = first.model_copy(update={"front_content": "Define: alpha!"})
    distinct = first.model_copy(update={"front_content": "What is Beta?", "back_content": "Beta"})

    assert duplicate_similarity(first, paraphrase) >= 0.88
    assert duplicate_similarity(first, distinct) < 0.88
    accepted = [first]
    assert not append_if_distinct(accepted, paraphrase, threshold=0.88)
    assert append_if_distinct(accepted, distinct, threshold=0.88)

