"""Offer bounded source-context alternatives for rejected private gold pairs.

Default preflight imports no application/settings/database modules. Explicit
creation reads the current authorized corpus locally, never calls a provider,
preserves the fixed questions and original review, and assigns no new labels.
These candidates are not runtime retrieval results or automatic quality passes.
"""
from __future__ import annotations

import argparse
import asyncio
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re
import tempfile

from build_private_source_holdout import TEMPLATES

PREPARATION_STAGE = "preflight"


def contextual_window(text: str, patterns: tuple[str, ...], *, cap: int = 480):
    """Keep nearby text around a topic occurrence, never synthesize a sentence."""
    matches = [list(re.finditer(pattern, text, re.I)) for pattern in patterns]
    if any(not group for group in matches):
        return None
    candidates = []
    for anchor in matches[0]:
        start = max(0, anchor.start() - cap // 3)
        end = min(len(text), start + cap)
        start = max(0, end - cap)
        quote = text[start:end]
        if not all(re.search(pattern, quote, re.I) for pattern in patterns):
            continue
        # Prioritize actual surrounding prose over bare headings. This is a
        # discovery heuristic only; an owner still decides whether it helps.
        prose = len(re.findall(r"\b(?:is|are|uses?|measures?|splits?|removes?|learns?|represents?|means?|stands?|into|because|by)\b", quote, re.I))
        candidates.append((prose, len(quote), -start, start, end))
    if not candidates:
        return None
    _, _, _, start, end = max(candidates)
    return start, end, text[start:end]


def choose_alternatives(chunks, pages, slots, original, labels, seed_pages):
    from app.services.rag_answers import locate_page_reference
    templates = {item.case_id: item for item in TEMPLATES}
    rows = []
    by_id = {str(chunk.chunk_id): chunk for chunk in chunks}
    for case in original["cases"]:
        template = templates.get(case["case_id"])
        if template is None or (case["question"], case["previous_turn"], case["category"]) != (
                template.question, template.previous_turn, template.category):
            raise ValueError("fixed_question_changed")
        source = by_id.get(case["gold_chunk_id"])
        if source is None or sha256(source.content.encode()).hexdigest() != case["chunk_sha256"]:
            raise ValueError("original_source_changed")
        if sha256(pages[source.chunk_id].encode()).hexdigest() != case["page_sha256"]:
            raise ValueError("original_page_changed")
        old_quote = source.content[case["gold_quote_start"]:case["gold_quote_end"]]
        if labels[template.case_id] != "No":
            continue
        candidates = []
        for chunk in chunks:
            pointer = (chunk.document_id, chunk.page_number)
            if pointer in seed_pages or chunk.chunk_id not in pages or chunk.document_id not in slots:
                continue
            found = contextual_window(chunk.content, template.patterns)
            if found is None:
                continue
            start, end, quote = found
            span = locate_page_reference(pages[chunk.chunk_id], quote)
            if span is None or (chunk.chunk_id == source.chunk_id and quote == old_quote):
                continue
            prose = len(re.findall(r"\b(?:is|are|uses?|measures?|splits?|removes?|learns?|represents?|means?|stands?|into|because|by)\b", quote, re.I))
            candidates.append((-prose, -len(quote), slots[chunk.document_id], chunk.page_number,
                               str(chunk.chunk_id), start, end, quote, span, chunk))
        seen_pages = set()
        selected = []
        for candidate in sorted(candidates, key=lambda item: item[:6]):
            chunk = candidate[-1]
            pointer = (chunk.document_id, chunk.page_number)
            if pointer in seen_pages:
                continue
            seen_pages.add(pointer)
            selected.append(candidate)
            if len(selected) == 2:
                break
        for index, candidate in enumerate(selected, 1):
            _, _, slot, _, _, start, end, quote, span, chunk = candidate
            page = pages[chunk.chunk_id]
            context_start = max(0, span[0] - 360)
            context_end = min(len(page), span[1] + 360)
            rows.append({"candidate_id": f"{template.case_id}-C{index:02d}",
                         "case_id": template.case_id, "category": template.category,
                         "question": template.question, "previous_turn": template.previous_turn,
                         "slot": slot, "page": chunk.page_number, "quote": quote,
                         "page_context": page[context_start:context_end], "rejected_quote": old_quote,
                         "gold_chunk_id": str(chunk.chunk_id), "gold_document_id": str(chunk.document_id),
                         "content_revision_id": str(chunk.content_revision_id),
                         "index_revision_id": str(chunk.index_revision_id),
                         "gold_quote_start": start, "gold_quote_end": end,
                         "chunk_sha256": sha256(chunk.content.encode()).hexdigest(),
                         "page_sha256": sha256(page.encode()).hexdigest(),
                         "excerpt_label": "unreviewed", "page_label": "unreviewed"})
    return rows


def render(rows):
    cards = []
    for row in rows:
        previous = f'<p>Previous question: {escape(row["previous_turn"])}</p>' if row["previous_turn"] else ""
        cards.append(f'<section><h2>{escape(row["candidate_id"])}</h2>'
                     f'<p>Knowledge document slot {row["slot"]}, PDF page {row["page"]}</p>'
                     f'{previous}<p><strong>{escape(row["question"])}</strong></p>'
                     f'<h3>Proposed exact excerpt (at most 480 characters)</h3><pre>{escape(row["quote"])}</pre>'
                     '<p>Excerpt: Yes / No / Unsure — does this passage help investigate the fixed question?</p>'
                     f'<details><summary>More current page context</summary><pre>{escape(row["page_context"])}</pre></details>'
                     '<p>Page: Yes / No / Unsure — does this original PDF page help investigate it?</p>'
                     f'<details><summary>Rejected v1 excerpt (label remains No)</summary><pre>{escape(row["rejected_quote"])}</pre></details>'
                     '</section>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="referrer" content="no-referrer">'
            '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; '
            'form-action &#39;none&#39;; base-uri &#39;none&#39;">'
            '<title>Source gold alternatives</title><style>body{font:16px/1.5 system-ui;max-width:900px;margin:2rem auto;padding:1rem}'
            'section{border:1px solid #aab;padding:1rem;margin:1rem 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef;padding:1rem}</style>'
            '<h1>Source gold alternatives</h1><p>Private local review, zero provider calls. Fixed questions and v1 labels are unchanged. '
            'These are unreviewed source candidates, not Ask results. Reply by candidate ID with excerpt and page labels. '
            'One useful candidate per question is sufficient; unresolved cases stay missing.</p>' + ''.join(cards) + '</html>')


async def build(original_directory: Path):
    global PREPARATION_STAGE
    PREPARATION_STAGE = "load_reader"
    from build_private_lane6_review_packet import validated_output_root
    from evaluate_private_ask_support_v2 import PROBES, _eligible_owner_chunks, select_probe_source
    root = validated_output_root().resolve()
    PREPARATION_STAGE = "read_review"
    directory = original_directory.resolve()
    if directory == root or not directory.is_relative_to(root) or original_directory.is_symlink():
        raise ValueError("private_input_invalid")
    original_bytes = (directory / "gold-roster.json").read_bytes()
    original = json.loads(original_bytes)
    review = json.loads((directory / "owner-review-v1.json").read_bytes())
    if review["gold_roster_sha256"] != sha256(original_bytes).hexdigest():
        raise ValueError("original_review_changed")
    labels = review["labels"]
    if set(labels) != {item.case_id for item in TEMPLATES} or any(value not in ("Yes", "No", "Unsure") for value in labels.values()):
        raise ValueError("review_invalid")
    PREPARATION_STAGE = "read_corpus"
    chunks, active, pages, slots = await _eligible_owner_chunks(with_pages=True, all_pages=True)
    if not active or not chunks or chunks[0].corpus_revision != original["scope"]["corpus_revision"] or chunks[0].embedding_space_hash != original["scope"]["embedding_space_hash"]:
        raise ValueError("scope_changed")
    seed_pages = set()
    PREPARATION_STAGE = "freeze_seed_pages"
    for probe in PROBES:
        state, source, _ = select_probe_source(probe, chunks)
        if state != "selected" or source is None:
            raise ValueError("seed_identity_unavailable")
        seed_pages.add((source.document_id, source.page_number))
    PREPARATION_STAGE = "choose_context"
    rows = choose_alternatives(chunks, pages, slots, original, labels, seed_pages)
    PREPARATION_STAGE = "write_packet"
    destination = Path(tempfile.mkdtemp(prefix="cardchemy-source-alternatives-", dir=root))
    destination.chmod(0o700)
    for name, body in (("review.html", render(rows)), ("candidate-roster.json", json.dumps({
        "version": "source_gold_context_alternatives_v1", "original_roster_sha256": sha256(original_bytes).hexdigest(),
        "original_review_sha256": sha256((directory / "owner-review-v1.json").read_bytes()).hexdigest(),
        "scope": original["scope"], "candidates": rows, "provider_calls": 0}, indent=2))):
        target = destination / name
        target.write_text(body, encoding="utf-8")
        target.chmod(0o600)
    print(json.dumps({"status": "unreviewed_alternatives_written", "candidate_count": len(rows),
                      "rejected_cases_with_alternatives": len({row["case_id"] for row in rows}),
                      "provider_calls": 0, "labels_changed": False, "packet_directory": destination.name}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create", action="store_true")
    parser.add_argument("--original-directory", type=Path)
    arguments = parser.parse_args()
    if not arguments.create:
        print(json.dumps({"status": "preflight", "database_reads": 0, "provider_calls": 0}))
        return 0
    if arguments.original_directory is None:
        parser.error("--original-directory is required for creation")
    async def run():
        from evaluate_private_ask_support_v2 import close_database
        try:
            await build(arguments.original_directory)
        finally:
            await close_database()
    try:
        asyncio.run(run())
    except Exception as error:
        codes = {"private_input_invalid", "original_review_changed", "review_invalid", "scope_changed",
                 "seed_identity_unavailable", "fixed_question_changed", "original_source_changed", "original_page_changed"}
        code = error.args[0] if isinstance(error, ValueError) and error.args and error.args[0] in codes else "preparation_failed"
        if isinstance(error, PermissionError):
            code = "private_file_permissions"
        elif isinstance(error, AttributeError):
            code = "discovery_contract_invalid"
        elif isinstance(error, KeyError):
            code = "manifest_field_missing"
        elif isinstance(error, ImportError):
            code = "reader_import_unavailable"
        print(json.dumps({"status": "source_alternatives_failed", "failure_code": code,
                          "failure_stage": PREPARATION_STAGE, "provider_calls": 0, "labels_changed": False}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
