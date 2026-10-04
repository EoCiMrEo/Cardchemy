"""Provider-free owner review of independent source-navigation gold pages.

Sources are read only from the currently authorized published Subject corpus.
No ranking/selector measurements are made, so gold choices are independent of
the runtime candidate. Private text is written only to an owner-private temp
HTML packet. Stdout is aggregate-only. No quality label is assigned here.
"""
from __future__ import annotations

import asyncio
import argparse
from dataclasses import dataclass
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import tempfile

@dataclass(frozen=True)
class GoldTemplate:
    case_id: str
    category: str
    question: str
    patterns: tuple[str, ...]
    previous_turn: str = ""


# Authored before source discovery, not selected using retrieval performance.
TEMPLATES = (
    GoldTemplate("T01", "direct", "How does tokenization split text?", (r"tokeniz", r"word|subword|sentence|unit")),
    GoldTemplate("T02", "direct", "What does inverse document frequency measure?", (r"inverse.document.frequency|\bidf\b", r"document|frequen")),
    GoldTemplate("T03", "direct", "How does stemming transform words?", (r"stemming", r"root|suffix|stem")),
    GoldTemplate("T04", "direct", "How does Euclidean distance compare vectors?", (r"euclidean", r"distance|vector|magnitud")),
    GoldTemplate("T05", "paraphrase", "How can sentence embeddings represent the meaning of an entire sentence?", (r"sentence", r"embedd|vector", r"meaning|semantic")),
    GoldTemplate("T06", "paraphrase", "How does Word2Vec learn representations from nearby words?", (r"word2vec", r"context|neighbor|skip.gram|cbow")),
    GoldTemplate("T07", "paraphrase", "How can text be classified by positive or negative sentiment?", (r"sentiment", r"positive|negative|polarity")),
    GoldTemplate("T08", "paraphrase", "How can latent topics be discovered from a collection of documents?", (r"latent|\blda\b", r"topic", r"document")),
    GoldTemplate("T09", "followup", "What does it stand for?", (r"\bbert\b", r"bidirectional|encoder|transformer"), "Where is BERT discussed?"),
    GoldTemplate("T10", "followup", "What does it stand for?", (r"tf[ -]idf", r"term|frequency|inverse"), "Where is TF-IDF discussed?"),
    GoldTemplate("T11", "followup", "What does it stand for?", (r"\blda\b", r"latent|dirichlet|allocation"), "Where is LDA discussed?"),
    GoldTemplate("T12", "followup", "What does it stand for?", (r"\bnlp\b", r"natural|language|processing"), "Where is NLP discussed?"),
)


def discover_gold(chunks, pages, slots):
    from evaluate_private_ask_support_v2 import (
        PROBES, select_probe_source, shortest_contiguous_line_window,
    )
    from app.services.rag_answers import locate_page_reference
    seed_pages = {(source.document_id, source.page_number)
                  for probe in PROBES
                  for state, source, _ in (select_probe_source(probe, chunks),)
                  if state == "selected" and source is not None}
    used = set(seed_pages)
    chosen = []
    for template in TEMPLATES:
        candidates = []
        for chunk in chunks:
            pointer = (chunk.document_id, chunk.page_number)
            if pointer in used or chunk.chunk_id not in pages or chunk.document_id not in slots:
                continue
            quote = shortest_contiguous_line_window(chunk.content, template.patterns,
                                                   max_chars=480, max_lines=12)
            if not quote or locate_page_reference(pages[chunk.chunk_id], quote) is None:
                continue
            candidates.append((len(quote), slots[chunk.document_id], chunk.page_number, chunk, quote))
        if candidates:
            _, _, _, chunk, quote = min(candidates, key=lambda row: row[:3])
            chosen.append((template, chunk, quote))
            used.add((chunk.document_id, chunk.page_number))
    return chosen


def render_gold(chosen, slots):
    cards = []
    for template, chunk, quote in chosen:
        previous = (f"<p><strong>Previous user turn:</strong> {escape(template.previous_turn)}</p>"
                    if template.previous_turn else "")
        cards.append(f'<section><h2>{template.case_id} · {template.category}</h2>'
                     f'<p>Knowledge document slot {slots[chunk.document_id]}, PDF page {chunk.page_number}</p>'
                     f'{previous}<p><strong>Question:</strong> {escape(template.question)}</p>'
                     f'<pre>{escape(quote)}</pre><p>Does this exact passage help a student investigate the question? '
                     'For follow-ups, consider the previous turn. Compare the original PDF page too.</p>'
                     '<p>Reply Yes / No / Unsure by case ID. No label is inferred or saved automatically.</p></section>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="referrer" content="no-referrer">'
            '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; '
            'style-src &#39;unsafe-inline&#39;; form-action &#39;none&#39;; base-uri &#39;none&#39;">'
            '<title>Private source-navigation holdout</title><style>'
            'body{font:16px/1.5 system-ui;max-width:900px;margin:2rem auto;padding:1rem}'
            'section{border:1px solid #aab;padding:1rem;margin:1rem 0;border-radius:8px}'
            'pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef;padding:1rem}</style>'
            '<h1>Independent gold-page review</h1><p>Private local file. These are source-discovery '
            'windows, not actual Ask results. Approval establishes useful gold pages only. '
            'Actual displayed windows still require a separate measured review.</p>'
            + ''.join(cards) + '</html>')


async def build():
    from build_private_lane6_review_packet import validated_output_root
    from evaluate_private_ask_support_v2 import _eligible_owner_chunks
    output_root = validated_output_root()
    chunks, active, pages, slots = await _eligible_owner_chunks(with_pages=True, all_pages=True)
    if not active:
        raise RuntimeError("scope_unavailable")
    chosen = discover_gold(chunks, pages, slots)
    directory = Path(tempfile.mkdtemp(prefix="cardchemy-source-holdout-", dir=output_root))
    directory.chmod(0o700)
    target = directory / "review.html"
    target.write_text(render_gold(chosen, slots), encoding="utf-8")
    target.chmod(0o600)
    roster = {
        "version": "source_navigation_holdout_gold_v1",
        "owner_reviewed_gold": False,
        "scope": {"corpus_revision": chunks[0].corpus_revision,
                  "embedding_space_hash": chunks[0].embedding_space_hash},
        "cases": [{"case_id": template.case_id, "category": template.category,
                   "question": template.question, "previous_turn": template.previous_turn,
                   "gold_chunk_id": str(chunk.chunk_id), "gold_document_id": str(chunk.document_id),
                   "gold_page": chunk.page_number, "content_revision_id": str(chunk.content_revision_id),
                   "index_revision_id": str(chunk.index_revision_id),
                   "chunk_sha256": sha256(chunk.content.encode()).hexdigest(),
                   "page_sha256": sha256(pages[chunk.chunk_id].encode()).hexdigest(),
                   "gold_quote_start": chunk.content.index(quote),
                   "gold_quote_end": chunk.content.index(quote)+len(quote),
                   "owner_label": "unreviewed"}
                  for template, chunk, quote in chosen],
    }
    manifest = directory / "gold-roster.json"
    manifest.write_text(json.dumps(roster, indent=2), encoding="utf-8")
    manifest.chmod(0o600)
    documents = len({chunk.document_id for _, chunk, _ in chosen})
    print(json.dumps({"status": "written", "ready_cases": len(chosen),
                      "missing_cases": len(TEMPLATES)-len(chosen), "distinct_documents": documents,
                      "all_gold_unreviewed": True, "provider_requests": 0,
                      "packet_directory": directory.name}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create", action="store_true")
    if not parser.parse_args().create:
        print(json.dumps({"status": "preflight", "authored_cases": len(TEMPLATES),
                          "database_reads": 0, "provider_requests": 0}))
        return 0
    async def run():
        from evaluate_private_ask_support_v2 import close_database
        try:
            await build()
        finally:
            await close_database()
    try:
        asyncio.run(run())
    except Exception:
        print(json.dumps({"status": "failed", "provider_requests": 0}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
