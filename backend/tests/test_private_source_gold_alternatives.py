"""Offline discovery controls, not assertions of private passage usefulness."""
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import refine_private_source_holdout as alternatives


def source(text, page=1):
    return SimpleNamespace(chunk_id=uuid4(), document_id=uuid4(), page_number=page,
                           content_revision_id=uuid4(), index_revision_id=uuid4(), content=text)


def original_case(chunk):
    return {"case_id": "T01", "question": alternatives.TEMPLATES[0].question,
            "previous_turn": "", "category": "direct", "gold_chunk_id": str(chunk.chunk_id),
            "chunk_sha256": sha256(chunk.content.encode()).hexdigest(),
            "page_sha256": sha256(chunk.content.encode()).hexdigest(),
            "gold_quote_start": 0, "gold_quote_end": 17}


def test_alternatives_keep_context_exact_and_bounded_without_relabelling():
    old = source("Word tokenization\nTokenization splits text into word units. <script>bad</script>")
    other = source("Tokenization uses subword units to split unfamiliar words.", page=2)
    seed = source("Tokenization is discussed using word and subword units.", page=3)
    chunks = (old, other, seed)
    pages = {chunk.chunk_id: chunk.content for chunk in chunks}
    slots = {chunk.document_id: index for index, chunk in enumerate(chunks, 1)}
    original = {"cases": [original_case(old)]}
    labels = {"T01": "No"}
    result = alternatives.choose_alternatives(chunks, pages, slots, original, labels,
                                             {(seed.document_id, seed.page_number)})
    assert len(result) == 2
    assert {row["candidate_id"] for row in result} == {"T01-C01", "T01-C02"}
    assert all(row["excerpt_label"] == row["page_label"] == "unreviewed" for row in result)
    assert all(len(row["quote"]) <= 480 and len(row["page_context"]) <= 1200 for row in result)
    assert all(row["quote"] in pages[next(c.chunk_id for c in chunks if str(c.chunk_id) == row["gold_chunk_id"])] for row in result)
    assert labels == {"T01": "No"}
    html = alternatives.render(result)
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "not Ask results" in html
    assert alternatives.choose_alternatives(chunks, pages, slots, original, {"T01": "Yes"}, set()) == []


def test_context_does_not_synthesize_missing_explanation_and_rejects_source_drift():
    assert alternatives.contextual_window("Heading only", (r"tokenization", r"word")) is None
    text = "Word tokenization\nTokenization splits text into word units."
    start, end, quote = alternatives.contextual_window(text, alternatives.TEMPLATES[0].patterns)
    assert quote == text[start:end] and "splits text" in quote
    chunk = source(text)
    case = original_case(chunk)
    chunk.content += " changed"
    with pytest.raises(ValueError, match="original_source_changed"):
        alternatives.choose_alternatives((chunk,), {chunk.chunk_id: chunk.content}, {chunk.document_id: 1},
                                         {"cases": [case]}, {"T01": "No"}, set())


def test_alternative_preflight_has_no_settings_or_database_imports():
    code = ('import runpy, sys; from pathlib import Path; script=sys.argv[1]; sys.argv=[script]; '
            'sys.path.insert(0,str(Path(script).parent)); '
            'namespace=runpy.run_path(script); assert namespace["main"]()==0; '
            'assert "app.config" not in sys.modules; assert "app.database" not in sys.modules')
    result = subprocess.run([sys.executable, "-c", code, str(Path(alternatives.__file__).resolve())],
                            check=True, capture_output=True, text=True)
    assert '"provider_calls": 0' in result.stdout
