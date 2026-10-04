"""Prepare a local, owner-reviewed Lane 6 case packet without provider calls.

The HTML is created only with ``--create`` in a new directory under the OS temp
directory. Published Knowledge and questions stay on this computer; stdout has
only fixed status/count fields and the neutral packet path. The six previously
reviewed direct probes seed the packet, but every new label remains pending.
Separate access, provider and generation controls are presented as planned
work, never as source-selection errors or automatic quality labels.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from html import escape
import json
import os
from pathlib import Path
import tempfile
import sys


BACKEND_ROOT = (
    Path("/app") if (Path("/app") / "app").is_dir()
    else Path(__file__).resolve().parents[1] / "backend"
)
sys.path.insert(0, str(BACKEND_ROOT))

from evaluate_private_ask_support_v2 import (
    PROBES,
    ProbeUnavailable,
    _eligible_owner_chunks,
    normalize_text,
    select_probe_source,
)
from app.database import close_database


@dataclass(frozen=True, slots=True)
class ReviewCase:
    case_id: str
    category: str
    question: str
    candidate: str
    source_probe: str | None = None
    previous_turn: str = ""
    review_instruction: str = ""


_DIRECT = tuple(
    ReviewCase(
        f"D{index:02d}", "direct", probe.question, probe.positive,
        probe.label,
        review_instruction="Check whether this exact excerpt and its original PDF page support the candidate answer.",
    )
    for index, probe in enumerate(PROBES, 1)
)

_ADDITIONAL = (
    ReviewCase("P01", "paraphrase", "Expand the BLEU abbreviation used in these lectures.",
               PROBES[0].positive, "bleu_acronym"),
    ReviewCase("P02", "paraphrase", "Which aspect of vectors does cosine similarity compare rather than size?",
               PROBES[2].positive, "cosine"),
    ReviewCase("P03", "paraphrase", "What sequence information do bag-of-words and TF-IDF fail to retain?",
               PROBES[3].positive, "bag_of_words"),
    ReviewCase("P04", "paraphrase", "Give one domain application for topic modeling described in the material.",
               PROBES[5].positive, "topic_modeling"),
    ReviewCase("H01", "resolvable_followup", "What does it stand for?",
               PROBES[0].positive, "bleu_acronym",
               previous_turn=PROBES[0].question,
               review_instruction="Check the referent using the previous turn and then check the exact excerpt."),
    ReviewCase("H02", "ambiguous_followup", "Could you explain that further?",
               "No verified answer without a resolvable prior referent.",
               review_instruction="Confirm this is ambiguous with no preceding conversation; do not infer an answer from a random chunk."),
    ReviewCase("N01", "conflicting_claim", PROBES[0].question,
               PROBES[0].negative, "bleu_acronym",
               review_instruction="Check whether this exact excerpt alone rules out the candidate. Choose No if it lacks counter-evidence; do not infer from other pages."),
    ReviewCase("N02", "unsupported_question", "How many moons does BLEU have?",
               "No answer should be claimed from the selected published Knowledge.",
               review_instruction="An excerpt cannot prove corpus-wide absence. Mark this pending until the selected corpus is independently reviewed."),
    ReviewCase("B01", "unpublished_boundary", "Question using only an unpublished document.",
               "No private or unpublished source may be returned.",
               review_instruction="No unpublished source is selected by this published-only reader. Use a guarded disposable access test."),
    ReviewCase("B02", "cross_subject_boundary", "Question using only another Subject's document.",
               "No cross-Subject source may be returned.",
               review_instruction="No other Subject source is selected by this Subject-bound reader. Use a guarded disposable access test."),
    ReviewCase("F01", "provider_unavailable_control", "A supported question when the answer provider is unavailable.",
               "A safe temporary failure with no fabricated answer.",
               review_instruction="Requires a deterministic provider failure test; this packet performs no request."),
    ReviewCase("F02", "malformed_output_control", "A supported question with malformed model output.",
               "A safe schema failure with no fabricated answer.",
               review_instruction="Requires a deterministic output-shape test; this packet performs no request."),
    ReviewCase("G01", "feasible_generation_source", "Week-3-shaped 20-card source.",
               "Review distinct supported facts and card quality; prior aggregate yield alone is insufficient.",
               review_instruction="The previous 20-card diagnostic did not persist cards. No private card-content review is supplied here."),
    ReviewCase("G02", "sparse_generation_source", "Owner-nominated sparse source.",
               "Record the distinct grounded-fact capacity before choosing a target.",
               review_instruction="No source has been nominated or fact-reviewed. Do not infer sparsity from page count."),
)

CASES = _DIRECT + _ADDITIONAL
assert len(CASES) == 20 and len({case.case_id for case in CASES}) == 20
_PROBES_BY_LABEL = {probe.label: probe for probe in PROBES}
OUTPUT_ROOT_ENV = "CARDCH_LANE6_REVIEW_OUTPUT_DIR"
CONTAINER_REVIEW_MOUNT = Path("/lane6-review")
IN_ANSWER_CONTAINER = (Path("/app") / "app").is_dir()


def validated_output_root() -> Path:
    """Refuse tempfile fallback and an absent/unmounted container output path."""

    raw = os.environ.get(OUTPUT_ROOT_ENV, "")
    chosen = Path(raw)
    if not raw or not chosen.is_absolute():
        raise ProbeUnavailable("review_output_root_unavailable")
    if IN_ANSWER_CONTAINER and (
        chosen != CONTAINER_REVIEW_MOUNT
        or os.environ.get("TMPDIR") != str(CONTAINER_REVIEW_MOUNT)
    ):
        raise ProbeUnavailable("review_output_root_unavailable")
    try:
        root = chosen.resolve(strict=True)
        actual_temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
    except OSError:
        raise ProbeUnavailable("review_output_root_unavailable") from None
    if (root != actual_temp_root or not root.is_dir()
        or not os.access(root, os.W_OK | os.X_OK)
        or (IN_ANSWER_CONTAINER and not os.path.ismount(root))):
        raise ProbeUnavailable("review_output_root_unavailable")
    try:
        probe = Path(tempfile.mkdtemp(prefix=".cardchemy-lane6-output-check-", dir=root))
        if probe.resolve(strict=True).parent != root:
            raise ProbeUnavailable("review_output_root_unavailable")
        probe.rmdir()
    except OSError:
        raise ProbeUnavailable("review_output_root_unavailable") from None
    return root


def _source_for_case(case: ReviewCase, chunks, pages, document_slots) -> tuple[str, str, str]:
    """Return safe status, local owner pointer and exact source quote, if bound."""

    if case.source_probe is None:
        if case.category == "unsupported_question":
            return "corpus_wide_unsupported_pending", "Separate corpus-wide evaluation", ""
        return "planned_separate_control", "No source expected in this packet", ""
    probe = _PROBES_BY_LABEL[case.source_probe]
    selection, chunk, quote = select_probe_source(probe, chunks)
    if selection != "selected" or chunk is None or quote is None:
        return selection, "No source selected", ""
    page = pages.get(chunk.chunk_id)
    slot = document_slots.get(chunk.document_id)
    if page is None or slot is None or quote not in chunk.content:
        return "current_source_unavailable", "No source selected", ""
    if quote in page:
        alignment = "exact"
    elif normalize_text(quote) in normalize_text(page):
        alignment = "whitespace_normalized"
    else:
        return "canonical_page_mismatch", "No source selected", ""
    return alignment, f"Knowledge document slot {slot}, PDF page {chunk.page_number}", quote


def render_packet(chunks, pages, document_slots) -> tuple[str, dict[str, int]]:
    """Render only authored prompts and currently bound excerpts to local HTML."""

    cards = []
    ready = 0
    planned = 0
    source_missing = 0
    for case in CASES:
        status, pointer, quote = _source_for_case(case, chunks, pages, document_slots)
        has_source = status in {"exact", "whitespace_normalized"}
        ready += int(has_source)
        planned += int(case.source_probe is None)
        source_missing += int(case.source_probe is not None and not has_source)
        source_html = (
            "<h3>Exact eligible Knowledge excerpt</h3><pre>" + escape(quote) + "</pre>"
            if has_source else (
                '<p class="needs-evidence">Current excerpt is not available for this source-bound review.</p>'
                if case.source_probe is not None else ""
            )
        )
        previous_html = (
            "<p><strong>Previous turn:</strong> " + escape(case.previous_turn) + "</p>"
            if case.previous_turn else ""
        )
        review_html = (
            '<fieldset><legend>Owner assessment (not saved by this file)</legend>'
            + ''.join(
                '<label><input type="radio" name="' + escape(case.case_id, quote=True)
                + '" value="' + choice.lower() + '"> ' + choice + '</label>'
                for choice in ("Yes", "No", "Unsure")
            ) + '</fieldset>'
            if case.category not in {"ambiguous_followup", "unsupported_question",
                                     "unpublished_boundary", "cross_subject_boundary",
                                     "provider_unavailable_control", "malformed_output_control",
                                     "feasible_generation_source", "sparse_generation_source"}
            else (
                '<p class="planned">Corpus-wide unsupported case pending separate evaluation. '
                'No owner review needed in this packet.</p>'
                if case.category == "unsupported_question"
                else '<p class="planned">Planned separate control — no owner review needed here.</p>'
            )
        )
        cards.append(
            '<section class="case"><h2>' + escape(case.case_id + " · " + case.category.replace("_", " "))
            + '</h2><p><strong>Availability:</strong> ' + escape(status.replace("_", " "))
            + ' · ' + escape(pointer) + '</p>'
            + previous_html + '<p><strong>Question/control:</strong> ' + escape(case.question) + '</p>'
            + '<p><strong>Candidate or expected safe behavior (unverified):</strong> '
            + escape(case.candidate) + '</p>' + source_html
            + '<p><strong>Review instruction:</strong> ' + escape(case.review_instruction or
              "Check whether the excerpt and original PDF page support this question and candidate answer.")
            + '</p>' + review_html + '</section>'
        )
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="referrer" content="no-referrer">'
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; '
        'style-src &#39;unsafe-inline&#39;; form-action &#39;none&#39;; base-uri &#39;none&#39;">'
        '<title>Private Lane 6 review packet</title><style>'
        'body{font:16px/1.5 system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#172033}'
        '.case{border:1px solid #9da7b5;border-radius:8px;padding:1rem;margin:1.25rem 0}'
        '.needs-evidence{color:#8a3300}.planned{color:#325478;background:#edf4fb;padding:.5rem}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f2f5f9;padding:1rem}'
        'fieldset{border:1px solid #9da7b5}label{display:inline-block;margin:.25rem 1rem .25rem 0}'
        'h2{font-size:1.1rem}</style></head><body><main>'
        '<h1>Private Lane 6 source and behavior review</h1><p>This local file contains private '
        'Knowledge excerpts. Keep it on this computer and check the original PDF page. '
        'Six direct question templates come from a prior owner review, but this current '
        'source snapshot and all new labels require explicit review before evaluation. '
        'A related excerpt alone '
        'does not prove that an answer is correct or that a question is unsupported. '
        'Radio choices stay in this browser session and are not saved. Report only case IDs '
        'and Yes/No/Unsure decisions; do not paste source text into chat or logs.</p>'
        + ''.join(cards) + '</main></body></html>'
    )
    return html, {"case_count": len(CASES), "source_bound_case_count": ready,
                  "planned_separate_control_count": planned,
                  "source_missing_case_count": source_missing}


def write_packet(html: str, *, output_root: Path) -> Path:
    """Atomically create one neutral, local-only packet under the OS temp root."""

    if output_root != validated_output_root():
        raise ProbeUnavailable("review_output_root_unavailable")
    folder = Path(tempfile.mkdtemp(prefix="cardchemy-lane6-review-", dir=output_root)).resolve(strict=True)
    if folder.parent != output_root:
        raise ProbeUnavailable("review_write_failed")
    destination = folder / "review.html"
    try:
        try:
            os.chmod(folder, 0o700)
        except OSError:
            pass  # Windows inherits the current user's Temp ACL.
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(destination, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(html)
        return destination
    except Exception:
        try:
            destination.unlink(missing_ok=True)
            folder.rmdir()
        except OSError:
            pass
        raise ProbeUnavailable("review_write_failed") from None


async def build_packet() -> dict[str, object]:
    output_root = validated_output_root()  # Precede any private database read.
    try:
        chunks, active, pages, slots = await _eligible_owner_chunks(with_pages=True)
        if not active:
            raise ProbeUnavailable("scope_changed")
        html, counts = render_packet(chunks, pages, slots)
        destination = write_packet(html, output_root=output_root)
        return {"status": "packet_written", "path": str(destination),
                "provider_requests": 0, "database_writes": 0,
                "reviewed_new_labels": 0, **counts}
    finally:
        await close_database()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create", action="store_true", help="Read the authorized local source and create a private Temp packet")
    args = parser.parse_args()
    if not args.create:
        print(json.dumps({"status": "preflight_ready", "case_count": len(CASES),
                          "provider_requests": 0, "database_reads": 0, "database_writes": 0},
                         separators=(",", ":")))
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
