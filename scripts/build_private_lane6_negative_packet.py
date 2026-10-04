"""Prepare source-bound private negative cases for owner review, without AI calls.

Default invocation performs no database read. ``--create`` uses the same current
owner/Subject, publication, revision and embedding-space scope as the Lane 6
positive packet. Private excerpts appear only in a new escaped HTML file under
the explicitly mounted OS Temp root. The review controls remain unsaved until
the owner independently reports case IDs and decisions.
"""

from __future__ import annotations

import argparse
import asyncio
from html import escape
import json

from build_private_lane6_review_packet import (
    ReviewCase,
    _eligible_owner_chunks,
    _source_for_case,
    close_database,
    validated_output_root,
    write_packet,
)
from evaluate_private_ask_support_v2 import PROBES, ProbeUnavailable


# These are authored general-domain claims, not copied private source text.
# The earlier acronym control is deliberately excluded: its selected excerpt
# did not explicitly rule out the alternate expansion in the owner's review.
CASES = (
    ReviewCase(
        "N11", "explicit_contradiction", PROBES[1].question,
        PROBES[1].negative, "bleu_focus",
        review_instruction=(
            "Does this exact excerpt alone explicitly refute the candidate's "
            "claim about BLEU and n-grams? Check the original PDF page."
        ),
    ),
    ReviewCase(
        "N12", "explicit_contradiction", PROBES[3].question,
        PROBES[3].negative, "bag_of_words",
        review_instruction=(
            "Does this exact excerpt alone explicitly refute the candidate's "
            "claim about preserving word order? Check the original PDF page."
        ),
    ),
    ReviewCase(
        "U01", "unrelated_question", PROBES[4].question,
        PROBES[1].positive, "bleu_focus",
        review_instruction=(
            "Assess separately whether the BLEU excerpt supports the candidate "
            "statement and whether that statement answers the logistic-regression "
            "question. Check the original PDF page."
        ),
    ),
)


def _radio_group(name: str, prompt: str) -> str:
    return (
        "<fieldset><legend>" + escape(prompt) + "</legend>"
        + "".join(
            '<label><input type="radio" name="' + escape(name, quote=True)
            + '" value="' + choice.lower() + '"> ' + choice + "</label>"
            for choice in ("Yes", "No", "Unsure")
        ) + "</fieldset>"
    )


def render_packet(chunks, pages, document_slots) -> tuple[str, dict[str, int]]:
    """Show only current exact source slices; absent sources have no review radios."""

    cards: list[str] = []
    bound = 0
    for case in CASES:
        status, pointer, quote = _source_for_case(case, chunks, pages, document_slots)
        available = status in {"exact", "whitespace_normalized"}
        bound += int(available)
        if available and case.category == "unrelated_question":
            review = (
                _radio_group(f"{case.case_id}_source", "Does the excerpt support the candidate statement?")
                + _radio_group(f"{case.case_id}_relevance", "Does the candidate statement answer the question?")
            )
        elif available:
            review = _radio_group(f"{case.case_id}_refutes", "Does this excerpt explicitly refute the candidate?")
        else:
            review = '<p class="pending">No current source-bound negative label can be recorded.</p>'
        cards.append(
            '<section class="case"><h2>' + escape(case.case_id + " · " + case.category.replace("_", " "))
            + '</h2><p><strong>Availability:</strong> ' + escape(status.replace("_", " "))
            + " · " + escape(pointer) + "</p>"
            + '<p><strong>Question:</strong> ' + escape(case.question) + "</p>"
            + '<p><strong>Candidate claim:</strong> ' + escape(case.candidate) + "</p>"
            + ('<h3>Exact eligible Knowledge excerpt</h3><pre>' + escape(quote) + "</pre>" if available else "")
            + '<p><strong>Review instruction:</strong> ' + escape(case.review_instruction) + "</p>"
            + review + "</section>"
        )
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="referrer" content="no-referrer">'
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; '
        'style-src &#39;unsafe-inline&#39;; form-action &#39;none&#39;; base-uri &#39;none&#39;">'
        '<title>Private Lane 6 negative review</title><style>'
        'body{font:16px/1.5 system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#172033}'
        '.case{border:1px solid #9da7b5;border-radius:8px;padding:1rem;margin:1.25rem 0}'
        '.pending{color:#8a3300}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f2f5f9;padding:1rem}'
        'fieldset{border:1px solid #9da7b5}label{display:inline-block;margin:.25rem 1rem .25rem 0}'
        'h2{font-size:1.1rem}</style></head><body><main>'
        '<h1>Private Lane 6 negative-source review</h1>'
        '<p>This local file contains private Knowledge excerpts. Check the exact excerpt and original PDF page. '
        'An authored candidate does not become a validated contradiction because it sounds wrong. '
        'For U01, a source can support a true statement while that statement does not answer the question. '
        'A No or Unsure on explicit refutation remains unlabelled as a contradiction. '
        'Radio choices are not saved. Report only case IDs and Yes/No/Unsure decisions; '
        'do not paste source text into chat or logs.</p>'
        + "".join(cards) + "</main></body></html>"
    )
    return html, {"case_count": len(CASES), "source_bound_case_count": bound,
                  "source_missing_case_count": len(CASES) - bound}


async def build_packet() -> dict[str, object]:
    output_root = validated_output_root()  # Must pass before a private database read.
    try:
        chunks, active, pages, slots = await _eligible_owner_chunks(with_pages=True)
        if not active:
            raise ProbeUnavailable("scope_changed")
        html, counts = render_packet(chunks, pages, slots)
        path = write_packet(html, output_root=output_root)
        return {"status": "packet_written", "path": str(path),
                "provider_requests": 0, "database_writes": 0,
                "reviewed_new_labels": 0, **counts}
    finally:
        await close_database()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create", action="store_true", help="Write one private packet in the OS Temp mount")
    args = parser.parse_args()
    if not args.create:
        print(json.dumps({"status": "preflight_ready", "case_count": len(CASES),
                          "provider_requests": 0, "database_reads": 0,
                          "database_writes": 0}, separators=(",", ":")))
        return 0
    try:
        result = asyncio.run(build_packet())
    except Exception:
        print('{"status":"unavailable","reason":"local_source_or_packet_unavailable"}')
        return 1
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
