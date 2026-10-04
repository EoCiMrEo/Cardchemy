"""Source discovery must keep provenance, disjoint pages and escaped private output."""
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import build_private_source_holdout as holdout


def test_default_preflight_does_not_import_settings_or_database():
    script = Path(holdout.__file__).resolve()
    code = ('import runpy, sys; script=sys.argv[1]; sys.argv=[script]; '
            'namespace=runpy.run_path(script); assert namespace["main"]()==0; '
            'assert "app.config" not in sys.modules; '
            'assert "app.database" not in sys.modules')
    result = subprocess.run([sys.executable, "-c", code, str(script)],
                            capture_output=True, text=True, check=True)
    assert '"database_reads": 0' in result.stdout


def chunk(text, page=40, document=None):
    return SimpleNamespace(chunk_id=uuid4(), document_id=document or uuid4(),
                           page_number=page, section=None, content=text)


def test_gold_discovery_cannot_reuse_seed_or_duplicate_page_and_requires_page_alignment():
    seed = chunk("BLEU means Bilingual Evaluation Understudy.", page=22)
    first = chunk("Tokenization splits words. <script>alert(1)</script>")
    duplicate = chunk("Stemming removes a suffix from words.", document=first.document_id)
    detached = chunk("Inverse document frequency measures document frequency.", page=41)
    pages = {seed.chunk_id: seed.content, first.chunk_id: first.content,
             duplicate.chunk_id: duplicate.content, detached.chunk_id: "Different canonical page"}
    slots = {c.document_id: n for n, c in enumerate((seed, first, duplicate, detached), 1)}
    selected = holdout.discover_gold((seed, first, duplicate, detached), pages, slots)
    assert [template.case_id for template, _, _ in selected] == ["T01"]
    html = holdout.render_gold(selected, slots)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "not actual Ask results" in html


def test_gold_can_align_only_whitespace_differences_without_fuzzy_matching():
    source = chunk("Tokenization splits text into words.")
    slots = {source.document_id: 1}
    selected = holdout.discover_gold((source,), {source.chunk_id: "Tokenization splits text\ninto words."}, slots)
    assert len(selected) == 1
    assert selected[0][2] == source.content
    assert holdout.discover_gold((source,), {source.chunk_id: "Tokenization changes the meaning of words."}, slots) == []
