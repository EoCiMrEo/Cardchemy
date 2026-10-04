"""Read-only, provider-free local support comparison on one owner's Knowledge.

The six authored concept probes cover five owner-reviewed topics. They are
diagnostics, not replayed model answers or a substitute for human review. This
module keeps all selected source text and authored questions in process memory;
stdout contains only fixed labels, page pointers, verdict codes, booleans and
aggregate time. ``--owner-review-packet`` prepares a source-location checklist
without loading a model or printing the private source passage.
``--owner-review-html ABSOLUTE_PATH.html`` writes an opt-in escaped static
review sheet outside the source tree for local owner inspection; its stdout
remains content-free.

Run inside the answer-worker with this file piped to ``python -`` so the pinned
ONNX bundle and database connection are the same as the local installation.
There is deliberately no provider import or credential access.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from html import escape
import json
import os
from pathlib import Path
import re
import statistics
import sys
from time import perf_counter
from uuid import UUID


BACKEND_ROOT = (
    Path("/app") if (Path("/app") / "app").is_dir()
    else Path(__file__).resolve().parents[1] / "backend"
)
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import bindparam, select, text  # noqa: E402
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID  # noqa: E402

from app.ai.answering import (  # noqa: E402
    GroundedAnswerOutputV2, ValidatedAnswerClaim, normalize_text,
    render_answer_prompts_v2, validate_grounded_answer_v2,
)
from app.ai.local_support import create_local_support_verifier  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.database import async_session_maker, close_database  # noqa: E402
from app.models.knowledge import SubjectDocument  # noqa: E402
from app.models.rag import RagAnswerJob, RagMessage  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.services.knowledge_retrieval import (  # noqa: E402
    KnowledgeRetriever, RetrievedKnowledgeChunk,
)
from app.time_utils import utcnow  # noqa: E402


@dataclass(frozen=True, slots=True)
class Probe:
    label: str
    page: int
    row_terms: tuple[str, ...]
    quote_terms: tuple[str, ...]
    question: str
    positive: str
    negative: str


# These are authored, general-domain questions and claims, not retained user
# questions or copied private Knowledge. Page/term criteria are fixed to the
# owner's already-reviewed local corpus; changed corpora fail selection closed.
PROBES = (
    Probe(
        "bleu_acronym", 22,
        (r"\bbleu\b", r"bilingual\s+evaluation\s+understudy"),
        (r"\bbleu\b", r"bilingual\s+evaluation\s+understudy"),
        "What does BLEU stand for?",
        "BLEU stands for Bilingual Evaluation Understudy.",
        "BLEU stands for Basic Evaluation Understudy.",
    ),
    Probe(
        "bleu_focus", 22,
        (r"\bbleu\b", r"n[\s-]?grams?", r"referenc"),
        (r"\bbleu\b", r"n[\s-]?grams?", r"referenc"),
        "What does BLEU measure against a reference translation?",
        "BLEU measures n-gram overlap with a reference translation.",
        "BLEU ignores n-gram overlap with a reference translation.",
    ),
    Probe(
        "cosine", 13,
        (r"cosine", r"angle", r"magnitud"),
        (r"angle", r"magnitud"),
        "What does cosine similarity measure?",
        "Cosine similarity compares vector angles rather than magnitudes.",
        "Cosine similarity compares only vector magnitudes rather than angles.",
    ),
    Probe(
        "bag_of_words", 9,
        (r"bag[\s-]of[\s-]words|\btf[\s-]idf\b", r"word\s+order|context"),
        (r"bag[\s-]of[\s-]words|\btf[\s-]idf\b", r"word\s+order|context"),
        "What information do Bag-of-Words and TF-IDF ignore?",
        "Bag-of-Words and TF-IDF do not preserve word order.",
        "Bag-of-Words and TF-IDF preserve word order exactly.",
    ),
    Probe(
        "logistic", 30,
        (r"logistic", r"sigmoid", r"probab"),
        (r"logistic", r"sigmoid", r"probab"),
        "What function does logistic regression use to produce probabilities?",
        "Logistic regression uses the sigmoid function to output probabilities.",
        "Logistic regression uses only a linear output without a sigmoid function.",
    ),
    Probe(
        "topic_modeling", 4,
        (r"topic", r"legal|medical"),
        (r"topic", r"legal|medical"),
        "What is an application of topic modeling in legal or medical domains?",
        "Topic modeling can be used to analyze legal or medical documents.",
        "Topic modeling is used only for weather forecasts, never legal or medical documents.",
    ),
)

_SAFE_VERDICTS = frozenset({
    "supported", "missing_evidence", "entailment_rejected",
    "question_relevance_rejected", "equivalence_rejected",
    "contradiction_detected", "verifier_unavailable",
})
_SAFE_SELECTION = frozenset({
    "selected", "chunk_unavailable", "chunk_ambiguous", "quote_unavailable",
})
_TOPIC_ANCHORS = {
    "bleu_acronym": r"\bbleu\b",
    "bleu_focus": r"\bbleu\b",
    "cosine": r"\bcosine\b",
    "bag_of_words": r"bag[\s-]of[\s-]words|\btf[\s-]idf\b",
    "logistic": r"\blogistic\b",
    "topic_modeling": r"\btopic\b",
}


class ProbeUnavailable(RuntimeError):
    """A fixed, content-free failure classification."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


_CHUNKS_SQL = text("""
SELECT eligible.id AS chunk_id, eligible.document_id, eligible.document_title,
       eligible.content_revision_id, eligible.index_revision_id,
       eligible.page_number, eligible.section, eligible.content,
       eligible.token_count, eligible.embedding_space_hash,
       eligible.corpus_revision
FROM eligible_subject_knowledge_chunks AS eligible
JOIN subjects AS subject ON subject.id = eligible.subject_id
JOIN users AS principal ON principal.id = :principal_id
WHERE eligible.subject_id = :subject_id
  AND eligible.corpus_revision = :corpus_revision
  AND eligible.embedding_space_hash = :space_hash
  AND subject.active_embedding_space_hash = eligible.embedding_space_hash
  AND (NOT :has_document_filter OR eligible.document_id = ANY(:document_ids))
  AND (
      (principal.role = 'INSTRUCTOR' AND subject.instructor_id = principal.id)
      OR (principal.role = 'STUDENT' AND EXISTS (
          SELECT 1 FROM enrollments AS enrollment
          WHERE enrollment.subject_id = subject.id
            AND enrollment.student_id = principal.id
      ))
  )
  AND eligible.page_number IN (4, 9, 13, 22, 30)
ORDER BY eligible.document_id, eligible.page_number, eligible.chunk_index, eligible.id
LIMIT 501
""").bindparams(
    bindparam("principal_id", type_=PGUUID(as_uuid=True)),
    bindparam("subject_id", type_=PGUUID(as_uuid=True)),
    bindparam("document_ids", type_=ARRAY(PGUUID(as_uuid=True))),
)

_CANONICAL_PAGES_SQL = text("""
SELECT eligible.id AS chunk_id, page.content AS page_content
FROM eligible_subject_knowledge_chunks AS eligible
JOIN subject_document_pages AS page
  ON page.content_revision_id = eligible.content_revision_id
 AND page.document_id = eligible.document_id
 AND page.subject_id = eligible.subject_id
 AND page.uploader_id = eligible.uploader_id
 AND page.page_number = eligible.page_number
JOIN subjects AS subject ON subject.id = eligible.subject_id
JOIN users AS principal ON principal.id = :principal_id
WHERE eligible.id = ANY(:chunk_ids)
  AND eligible.subject_id = :subject_id
  AND eligible.corpus_revision = :corpus_revision
  AND eligible.embedding_space_hash = :space_hash
  AND subject.active_embedding_space_hash = eligible.embedding_space_hash
  AND (
      (principal.role = 'INSTRUCTOR' AND subject.instructor_id = principal.id)
      OR (principal.role = 'STUDENT' AND EXISTS (
          SELECT 1 FROM enrollments AS enrollment
          WHERE enrollment.subject_id = subject.id
            AND enrollment.student_id = principal.id
      ))
  )
ORDER BY eligible.id
LIMIT 7
""").bindparams(
    bindparam("principal_id", type_=PGUUID(as_uuid=True)),
    bindparam("subject_id", type_=PGUUID(as_uuid=True)),
    bindparam("chunk_ids", type_=ARRAY(PGUUID(as_uuid=True))),
)


def _matches_all(value: str, patterns: tuple[str, ...]) -> bool:
    return all(re.search(pattern, value, re.IGNORECASE) for pattern in patterns)


def shortest_contiguous_line_window(
    content: str, patterns: tuple[str, ...], *, max_lines: int = 8,
    max_chars: int = 950,
) -> str | None:
    """Return the shortest exact source substring covering required concepts."""

    lines = content.splitlines(keepends=True)
    best: str | None = None
    for start in range(len(lines)):
        for stop in range(start + 1, min(len(lines), start + max_lines) + 1):
            window = "".join(lines[start:stop]).strip()
            if len(window) > max_chars:
                break
            if _matches_all(window, patterns) and (
                best is None or len(window) < len(best)
            ):
                best = window
                break
    if best is not None and best in content:
        return best
    # PDF extraction sometimes stores multiple visual lines in one long line.
    # Fall back to the smallest source-contiguous sentence span containing all
    # required concepts; never synthesize a quote by joining disjoint snippets.
    matches = []
    for index, pattern in enumerate(patterns):
        found = list(re.finditer(pattern, content, re.IGNORECASE))[:40]
        if not found:
            return None
        matches.extend((hit.start(), hit.end(), index) for hit in found)
    matches.sort()
    shortest: tuple[int, int] | None = None
    for left in range(len(matches)):
        seen: set[int] = set()
        for right in range(left, len(matches)):
            seen.add(matches[right][2])
            if len(seen) == len(patterns):
                start, stop = matches[left][0], max(
                    match[1] for match in matches[left:right + 1]
                )
                if shortest is None or stop - start < shortest[1] - shortest[0]:
                    shortest = (start, stop)
                break
    if shortest is None:
        return None
    start, stop = shortest
    previous = max(content.rfind(mark, 0, start) for mark in ".!?\n")
    start = previous + 1
    next_boundaries = [
        index for mark in ".!?\n"
        if (index := content.find(mark, stop)) >= 0
    ]
    stop = min(next_boundaries) + 1 if next_boundaries else len(content)
    quote = content[start:stop].strip()
    if len(quote) <= max_chars and _matches_all(quote, patterns) and quote in content:
        return quote
    return None


def select_probe_source(
    probe: Probe, chunks: tuple[RetrievedKnowledgeChunk, ...],
) -> tuple[str, RetrievedKnowledgeChunk | None, str | None]:
    candidates = [
        chunk for chunk in chunks
        if chunk.page_number == probe.page
        and _matches_all(f"{chunk.section or ''}\n{chunk.content}", probe.row_terms)
    ]
    if not candidates:
        return "chunk_unavailable", None, None
    if len(candidates) != 1:
        return "chunk_ambiguous", None, None
    chunk = candidates[0]
    quote = shortest_contiguous_line_window(chunk.content, probe.quote_terms)
    if quote is None:
        return "quote_unavailable", chunk, None
    return "selected", chunk, quote


def nearest_heading_page_span(
    page: str, probe: Probe, chunk: RetrievedKnowledgeChunk,
    *, max_chars: int = 1400,
) -> tuple[str, str | None]:
    """Find one exact page substring from subject heading to answer line.

    The last fixed quote pattern identifies the answer-bearing line. A heading
    must precede it and name the same topic, or the probe refuses the span.
    This is a diagnostic selector, not an authorized citation policy.
    """

    lines = page.splitlines(keepends=True)
    anchor = _TOPIC_ANCHORS[probe.label]
    section = (chunk.section or "").strip().casefold()
    headings: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not re.search(anchor, stripped, re.IGNORECASE):
            continue
        if section and stripped.casefold() == section:
            headings.append((index, "section"))
        elif 0 < len(stripped) <= 120 and stripped[-1] not in ".!?;:":
            headings.append((index, "topic_heading"))
    if not headings:
        return "heading_unavailable", None
    possibilities: list[tuple[int, str, str]] = []
    for answer_index, line in enumerate(lines):
        if not re.search(probe.quote_terms[-1], line, re.IGNORECASE):
            continue
        prior = [(index, kind) for index, kind in headings if index <= answer_index]
        if not prior:
            continue
        heading_index, heading_kind = prior[-1]
        span = "".join(lines[heading_index:answer_index + 1]).strip()
        if _matches_all(span, probe.quote_terms) and span in page:
            possibilities.append((len(span), heading_kind, span))
    if not possibilities:
        return "answer_line_unavailable", None
    _length, heading_kind, span = min(possibilities, key=lambda item: item[0])
    if len(span) > max_chars:
        return "span_over_limit", None
    return heading_kind, span


def _quote_pair_probe(verifier, *, question: str, statement: str,
                      quote: str) -> dict[str, object]:
    """Run only quote entailment and QA; no full support-policy conclusion."""

    result: dict[str, object] = {
        "reason": "inference_unavailable", "nli_pair_tokens": None,
        "contradiction": None, "entailment": None, "neutral": None,
        "qa_span_present": None, "qa_span_in_claim": None,
    }
    try:
        tokens = len(verifier._nli._tokenizer.encode(quote, statement).ids)
        if not 0 < tokens <= 384:
            result["reason"] = "model_token_limit"
            return result
        result["nli_pair_tokens"] = tokens
        scores = verifier._nli.score(quote, statement)
        result["contradiction"] = round(scores.contradiction, 3)
        result["entailment"] = round(scores.entailment, 3)
        result["neutral"] = round(scores.neutral, 3)
        entailed = scores.entailment >= 0.80 and scores.entailment > max(
            scores.contradiction, scores.neutral
        )
        answer = verifier._qa.answer(question, quote)
        present = bool(answer and normalize_text(answer) in normalize_text(quote))
        result["qa_span_present"] = present
        result["qa_span_in_claim"] = bool(
            answer and normalize_text(answer) in normalize_text(statement)
        )
        result["reason"] = (
            "entailment_rejected" if not entailed else
            "question_relevance_rejected" if not present else "quote_gate_pass"
        )
    except Exception:
        result["reason"] = "inference_unavailable"
    return result


async def _eligible_owner_chunks(
    *, with_pages: bool = False, all_pages: bool = False,
) -> tuple[tuple[RetrievedKnowledgeChunk, ...], bool, dict[UUID, str], dict[UUID, int]]:
    async with async_session_maker() as db:
        await db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        matching = (
            RagMessage.role == "user",
            RagMessage.content.ilike("%BLEU%"),
            RagMessage.expires_at > utcnow(),
        )
        owner_ids = (await db.scalars(
            select(RagAnswerJob.user_id)
            .join(RagMessage, RagMessage.id == RagAnswerJob.question_message_id)
            .where(*matching)
            .distinct().limit(2)
        )).all()
        if len(owner_ids) != 1:
            raise ProbeUnavailable("owner_unavailable")
        job = (await db.scalars(
            select(RagAnswerJob)
            .join(RagMessage, RagMessage.id == RagAnswerJob.question_message_id)
            .where(*matching, RagAnswerJob.user_id == owner_ids[0])
            .order_by(RagAnswerJob.created_at.desc(), RagAnswerJob.id.desc())
            .limit(1)
        )).one_or_none()
        if job is None:
            raise ProbeUnavailable("job_unavailable")
        principal = await db.get(User, job.user_id)
        if principal is None:
            raise ProbeUnavailable("access_unavailable")
        try:
            document_ids = tuple(UUID(str(value)) for value in job.document_ids)
        except (TypeError, ValueError, AttributeError):
            raise ProbeUnavailable("job_unavailable") from None
        try:
            retriever = await KnowledgeRetriever.authorize(
                db, principal=principal, subject_id=job.subject_id,
                query="BLEU evidence review", document_ids=document_ids,
            )
        except Exception:
            raise ProbeUnavailable("access_unavailable") from None
        active_space_match = bool(
            retriever.scope.embedding_space_hash == job.embedding_space_hash
            and retriever.scope.corpus_revision == job.corpus_revision
        )
        if not active_space_match:
            raise ProbeUnavailable("scope_changed")
        chunks_sql = _CHUNKS_SQL
        if all_pages:
            if not with_pages or principal.role != UserRole.INSTRUCTOR:
                raise ProbeUnavailable("owner_unavailable")
            chunks_sql = text(_CHUNKS_SQL.text.replace(
                "  AND eligible.page_number IN (4, 9, 13, 22, 30)\n", ""
            )).bindparams(
                bindparam("principal_id", type_=PGUUID(as_uuid=True)),
                bindparam("subject_id", type_=PGUUID(as_uuid=True)),
                bindparam("document_ids", type_=ARRAY(PGUUID(as_uuid=True))),
            )
        rows = (await db.execute(chunks_sql, {
            "principal_id": principal.id,
            "subject_id": job.subject_id,
            "corpus_revision": retriever.scope.corpus_revision,
            "space_hash": retriever.scope.embedding_space_hash,
            "has_document_filter": bool(retriever.scope.document_ids),
            "document_ids": list(retriever.scope.document_ids),
        })).mappings().all()
        if not rows or len(rows) > 500:
            raise ProbeUnavailable("eligible_corpus_unavailable")
        chunks = tuple(RetrievedKnowledgeChunk(
            chunk_id=row["chunk_id"], document_id=row["document_id"],
            document_title=row["document_title"],
            content_revision_id=row["content_revision_id"],
            index_revision_id=row["index_revision_id"],
            page_number=row["page_number"], section=row["section"],
            content=row["content"], token_count=row["token_count"],
            embedding_space_hash=row["embedding_space_hash"],
            corpus_revision=int(row["corpus_revision"]),
            vector_similarity=None, lexical_score=None,
            vector_rank=None, lexical_rank=None, fusion_score=0.0,
        ) for row in rows)
        pages: dict[UUID, str] = {}
        document_slots: dict[UUID, int] = {}
        if with_pages:
            # The packet is for the Subject owner. The slot mirrors the
            # Knowledge list order while revealing neither title nor UUID.
            if principal.role != UserRole.INSTRUCTOR:
                raise ProbeUnavailable("owner_unavailable")
            ordered_ids = (await db.scalars(
                select(SubjectDocument.id)
                .where(
                    SubjectDocument.subject_id == job.subject_id,
                    SubjectDocument.uploader_id == principal.id,
                )
                .order_by(SubjectDocument.updated_at.desc(), SubjectDocument.id)
                .limit(501)
            )).all()
            if len(ordered_ids) > 500:
                raise ProbeUnavailable("document_list_unavailable")
            document_slots = {
                document_id: index for index, document_id in enumerate(ordered_ids, 1)
            }
            selected_ids = {
                chunk.chunk_id for probe in PROBES
                for selection, chunk, _quote in (select_probe_source(probe, chunks),)
                if selection == "selected" and chunk is not None
            }
            if all_pages:
                selected_ids = {chunk.chunk_id for chunk in chunks}
            if selected_ids:
                pages_sql = _CANONICAL_PAGES_SQL
                if all_pages:
                    pages_sql = text(_CANONICAL_PAGES_SQL.text.replace("LIMIT 7", "LIMIT 501")).bindparams(
                        bindparam("principal_id", type_=PGUUID(as_uuid=True)),
                        bindparam("subject_id", type_=PGUUID(as_uuid=True)),
                        bindparam("chunk_ids", type_=ARRAY(PGUUID(as_uuid=True))),
                    )
                page_rows = (await db.execute(pages_sql, {
                    "principal_id": principal.id,
                    "subject_id": job.subject_id,
                    "corpus_revision": retriever.scope.corpus_revision,
                    "space_hash": retriever.scope.embedding_space_hash,
                    "chunk_ids": list(selected_ids),
                })).mappings().all()
                pages = {row["chunk_id"]: row["page_content"] for row in page_rows}
                if len(pages) != len(selected_ids):
                    raise ProbeUnavailable("canonical_page_unavailable")
                if any(
                    chunk.document_id not in document_slots
                    for chunk in chunks if chunk.chunk_id in selected_ids
                ):
                    raise ProbeUnavailable("document_list_unavailable")
        await db.rollback()
        return chunks, active_space_match, pages, document_slots


def _safe_evaluate(verifier, *, question: str, claim: ValidatedAnswerClaim,
                   chunk: RetrievedKnowledgeChunk) -> str:
    try:
        verdict = verifier.evaluate(question=question, claims=(claim,), chunks=(chunk,))
        return verdict.reason_code if verdict.reason_code in _SAFE_VERDICTS else "verifier_unavailable"
    except Exception:
        return "verifier_unavailable"


def _answer_contract_v2_claim(
    *, chunk: RetrievedKnowledgeChunk, quote: str, statement: str,
    question: str,
) -> tuple[str, ValidatedAnswerClaim | None, int]:
    """Replay an authored claim through emitted source IDs and server binding.

    The selected window may start/end inside an emitted unit. The returned
    quote is *always* the server-derived complete unit range, not the authored
    selector's narrower text. An ambiguous repeated substring fails closed.
    """

    if not quote or chunk.content.count(quote) != 1:
        return "range_ambiguous", None, 0
    start = chunk.content.find(quote)
    stop = start + len(quote)
    try:
        _, payload = render_answer_prompts_v2(
            question=question, history=(), chunks=(chunk,),
        )
        issued = json.loads(payload)["evidence_untrusted"][0]["units"]
        cursor = 0
        first_id: int | None = None
        last_id: int | None = None
        for unit in issued:
            unit_end = cursor + len(unit["text"])
            if cursor <= start < unit_end:
                first_id = unit["unit_id"]
            if cursor < stop <= unit_end:
                last_id = unit["unit_id"]
            cursor = unit_end
        if cursor != len(chunk.content) or first_id is None or last_id is None:
            return "range_unavailable", None, 0
        unit_count = last_id - first_id + 1
        if unit_count < 1 or unit_count > 6:
            return "range_over_limit", None, unit_count
        output = GroundedAnswerOutputV2.model_validate({
            "outcome": "answer", "claims": [{
                "statement": statement,
                "start_unit_id": first_id,
                "end_unit_id": last_id,
            }],
        })
        derived = validate_grounded_answer_v2(output, (chunk,))
        if (
            len(derived.claims) != 1
            or derived.answer != statement
            or derived.claims[0].source != chunk
            or quote not in derived.claims[0].source_quote
        ):
            return "binding_rejected", None, unit_count
        return "server_derived", derived.claims[0], unit_count
    except Exception:
        # Pydantic and source-bound failures contain private content in their
        # exceptions; neither the exception nor its text reaches the report.
        return "binding_rejected", None, 0


def evaluate_answer_contract_v2_in_memory(
    chunks: tuple[RetrievedKnowledgeChunk, ...], *, model_dir: Path,
    active_space_match: bool,
) -> dict[str, object]:
    """Measure authored local claims under the unshipped server-derived shape.

    This is one selected eligible chunk per probe, not the full retrieved top
    five and not a generated-model answer replay. Every verifier call uses the
    shipped local policy returned by the factory, with no provider request.
    """

    verifier = create_local_support_verifier(model_dir)
    rows: list[dict[str, object]] = []
    for index, probe in enumerate(PROBES):
        selection, chunk, quote = select_probe_source(probe, chunks)
        assert selection in _SAFE_SELECTION
        item: dict[str, object] = {
            "topic": probe.label,
            "selection": selection,
            "contract_binding": "source_unavailable",
            "source_unit_count": 0,
            "positive": None,
            "negative": None,
            "wrong_question": None,
        }
        if chunk is not None and quote is not None:
            binding, positive, unit_count = _answer_contract_v2_claim(
                chunk=chunk, quote=quote, statement=probe.positive,
                question=probe.question,
            )
            item["contract_binding"] = binding
            item["source_unit_count"] = unit_count
            if positive is not None:
                item["positive"] = _safe_evaluate(
                    verifier, question=probe.question, claim=positive, chunk=chunk,
                )
                wrong_question = PROBES[(index + 2) % len(PROBES)].question
                item["wrong_question"] = _safe_evaluate(
                    verifier, question=wrong_question, claim=positive, chunk=chunk,
                )
            negative_binding, negative, _ = _answer_contract_v2_claim(
                chunk=chunk, quote=quote, statement=probe.negative,
                question=probe.question,
            )
            if negative_binding != binding:
                item["negative_binding"] = negative_binding
            if negative is not None:
                item["negative"] = _safe_evaluate(
                    verifier, question=probe.question, claim=negative, chunk=chunk,
                )
        rows.append(item)
    return {
        "scope": "one_current_authorized_published_subject",
        "policy": "unshipped_answer_contract_v2_with_current_local_support",
        "provider_requests": 0,
        "database_writes": 0,
        "active_space_match": active_space_match,
        "authored_case_count": len(PROBES),
        "exact_quote_claim_pairs_owner_reviewed": 0,
        "retrieval_recall_measured": False,
        "model_answer_replay_measured": False,
        "single_selected_source_per_case": True,
        "results": rows,
    }


def prepare_owner_review_packet(
    chunks: tuple[RetrievedKnowledgeChunk, ...],
    canonical_pages: dict[UUID, str],
    document_slots: dict[UUID, int],
) -> dict[str, object]:
    """Locate evidence for owner review without printing source or identifiers.

    The owner's earlier topic-level confirmation does not establish that this
    exact eligible quote supports this authored question and claim. A packet
    therefore always remains pending until a separate human review records
    those labels; it cannot by itself pass the Lane 6 quality gate.
    """

    cases: list[dict[str, object]] = []
    for case in PROBES:
        selection, chunk, quote = select_probe_source(case, chunks)
        page = canonical_pages.get(chunk.chunk_id) if chunk is not None else None
        if quote is None or page is None:
            page_alignment = "unavailable"
        elif quote in page:
            page_alignment = "exact"
        elif normalize_text(quote) in normalize_text(page):
            # Chunking can collapse page whitespace. This is only a pointer
            # for human review, never a replacement for exact chunk quoting.
            page_alignment = "whitespace_normalized"
        else:
            page_alignment = "not_found"
        cases.append({
            "topic": case.label,
            "document_slot": document_slots.get(chunk.document_id) if chunk else None,
            "page": case.page,
            "selection": selection,
            "quote_exact_in_chunk": bool(
                quote is not None and chunk is not None and quote in chunk.content
            ),
            "quote_exact_in_canonical_page": bool(
                quote is not None and page is not None and quote in page
            ),
            "canonical_page_alignment": page_alignment,
            "owner_review": "pending_exact_quote_question_claim_review",
        })
    return {
        "scope": "one_current_authorized_published_subject",
        "provider_requests": 0,
        "database_writes": 0,
        "topic_facts_owner_confirmed": 5,
        "exact_quote_claim_pairs_owner_reviewed": 0,
        "cases": cases,
    }


def render_owner_review_html(
    chunks: tuple[RetrievedKnowledgeChunk, ...],
    canonical_pages: dict[UUID, str],
    document_slots: dict[UUID, int],
) -> str:
    """Render a local-only human review sheet; never return it to stdout."""

    packet = prepare_owner_review_packet(chunks, canonical_pages, document_slots)
    cards: list[str] = []
    for probe, pointer in zip(PROBES, packet["cases"], strict=True):
        selection, chunk, quote = select_probe_source(probe, chunks)
        alignment = pointer["canonical_page_alignment"]
        if (
            selection != "selected" or chunk is None or quote is None
            or not pointer["quote_exact_in_chunk"]
            or alignment not in {"exact", "whitespace_normalized"}
            or pointer["document_slot"] is None
        ):
            raise ProbeUnavailable("review_source_unavailable")
        checks = (
            ("positive", "Does this quote support the positive answer to the question?"),
            ("negative", "Does this quote rule out the negative control?"),
            ("page", "Does the quote match the intended meaning on the original PDF page?"),
        )
        checklist = "".join(
            '<div class="check"><span>' + escape(prompt) + '</span>'
            + ''.join(
                '<label><input type="radio" name="' + escape(probe.label + "_" + key, quote=True)
                + '" value="' + choice.lower() + '"> ' + choice + '</label>'
                for choice in ("Yes", "No")
            ) + '</div>'
            for key, prompt in checks
        )
        cards.append(
            '<section class="case"><h2>' + escape(probe.label.replace("_", " ").title())
            + '</h2><p class="pointer">Knowledge document slot '
            + escape(str(pointer["document_slot"])) + ', PDF page '
            + escape(str(pointer["page"])) + '. Page alignment: '
            + escape(str(alignment).replace("_", " ")) + '.</p>'
            + '<h3>Exact selected Knowledge quote</h3><pre>' + escape(quote)
            + '</pre><h3>Authored comparison</h3><p><strong>Question:</strong> '
            + escape(probe.question) + '</p><p><strong>Positive answer:</strong> '
            + escape(probe.positive) + '</p><p><strong>Negative control:</strong> '
            + escape(probe.negative) + '</p><div class="checklist">'
            + checklist + '</div></section>'
        )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="referrer" content="no-referrer">'
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; '
        'style-src &#39;unsafe-inline&#39;; form-action &#39;none&#39;; base-uri &#39;none&#39;">'
        '<title>Private Ask AI evidence review</title><style>'
        'body{font:16px/1.5 system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#172033}'
        '.case{border:1px solid #9da7b5;border-radius:8px;padding:1rem;margin:1.25rem 0;break-inside:avoid}'
        '.pointer{color:#42536a}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f2f5f9;padding:1rem}'
        '.check{margin:.5rem 0}.check span{display:block;font-weight:600}.check label{margin-right:1.5rem}'
        'h2,h3{line-height:1.25}h3{font-size:1rem;margin-bottom:.3rem}'
        '</style></head><body><main><h1>Private Ask AI evidence review</h1>'
        '<p>This file contains private published Knowledge from one local Subject. '
        'Keep it on this machine. The selected quote is exact in an eligible Knowledge chunk; '
        'a whitespace-normalized page match may differ from PDF line breaks. '
        'Check the original PDF page before answering. The selections are not yet approved '
        'claim labels. Radio choices remain only in this browser session.</p>'
        + ''.join(cards) + '</main></body></html>'
    )


def validate_owner_review_destination(destination: Path) -> Path:
    """Resolve a caller-selected new HTML path before opening private data."""

    source_root = BACKEND_ROOT.parent if BACKEND_ROOT.name == "backend" else BACKEND_ROOT
    if not destination.is_absolute() or destination.suffix.lower() != ".html":
        raise ProbeUnavailable("invalid_output_path")
    resolved = destination.resolve()
    if resolved.is_relative_to(source_root.resolve()) or not resolved.parent.is_dir():
        raise ProbeUnavailable("invalid_output_path")
    if destination.exists() or destination.is_symlink():
        raise ProbeUnavailable("output_exists")
    return resolved


def write_owner_review_html(
    destination: Path,
    chunks: tuple[RetrievedKnowledgeChunk, ...],
    canonical_pages: dict[UUID, str],
    document_slots: dict[UUID, int],
) -> None:
    """Write a private review sheet only to a new, explicit path outside source."""

    resolved = validate_owner_review_destination(destination)
    body = render_owner_review_html(chunks, canonical_pages, document_slots)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    created = False
    try:
        descriptor = os.open(resolved, flags, 0o600)
        created = True
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(body)
    except Exception:
        if created:
            try:
                resolved.unlink(missing_ok=True)
            except OSError:
                pass
        raise ProbeUnavailable("review_write_failed") from None


def evaluate_in_memory(
    chunks: tuple[RetrievedKnowledgeChunk, ...], *, model_dir: Path,
    active_space_match: bool, canonical_pages: dict[UUID, str] | None = None,
) -> dict[str, object]:
    v1 = create_local_support_verifier(model_dir)
    # The candidate shares pinned scorers, so this comparison does not load
    # duplicate model sessions or compare different artifact identities.
    from app import ai as ai_package
    v2_type = getattr(ai_package.local_support, "LocalSupportVerifierV2", None)
    v2 = v2_type(v1._nli, v1._qa) if v2_type is not None else None
    timings: dict[str, list[float]] = {"v1": [], "v2": []}
    page_timings: list[float] = []
    rows: list[dict[str, object]] = []
    for probe in PROBES:
        selection, chunk, quote = select_probe_source(probe, chunks)
        assert selection in _SAFE_SELECTION
        item: dict[str, object] = {
            "topic": probe.label,
            "selection": selection,
            "eligible_view": chunk is not None,
            "quote_has_topic_anchor": bool(
                quote and re.search(_TOPIC_ANCHORS[probe.label], quote, re.IGNORECASE)
            ),
            "section_has_topic_anchor": bool(
                chunk and re.search(
                    _TOPIC_ANCHORS[probe.label], chunk.section or "", re.IGNORECASE,
                )
            ),
            "positive_v1": None, "negative_v1": None,
            "positive_v2": None, "negative_v2": None,
            "wrong_question_v1": None, "wrong_question_v2": None,
        }
        if chunk is not None and quote is not None:
            if canonical_pages is not None:
                started_page = perf_counter()
                page = canonical_pages.get(chunk.chunk_id)
                if page is None:
                    item["canonical_page"] = {"reason": "page_unavailable"}
                else:
                    kind, span = nearest_heading_page_span(page, probe, chunk)
                    item["canonical_page"] = {
                        "reason": kind,
                        "exact_page_substring": bool(span and span in page),
                        "span_in_current_chunk": bool(span and span in chunk.content),
                        "quote_pair": (
                            _quote_pair_probe(v1, question=probe.question,
                                              statement=probe.positive, quote=span)
                            if span is not None else None
                        ),
                    }
                composite = f"{chunk.section}\n{quote}" if chunk.section else None
                item["section_quote_composite"] = {
                    "available": composite is not None,
                    "citable_as_current_quote": False,
                    "quote_pair": (
                        _quote_pair_probe(v1, question=probe.question,
                                          statement=probe.positive, quote=composite)
                        if composite is not None else None
                    ),
                }
                item["current_quote_pair"] = _quote_pair_probe(
                    v1, question=probe.question, statement=probe.positive,
                    quote=quote,
                )
                page_timings.append((perf_counter() - started_page) * 1_000)
            # A correct, quote-supported claim answering an unrelated
            # question is unsafe even when its own words are well grounded.
            # The swap uses a different authored topic; no private question
            # is copied into the diagnostic output.
            wrong_question = PROBES[(PROBES.index(probe) + 2) % len(PROBES)].question
            for label, verifier in (("v1", v1), ("v2", v2)):
                if verifier is None:
                    item[f"positive_{label}"] = "verifier_unavailable"
                    item[f"negative_{label}"] = "verifier_unavailable"
                    item[f"wrong_question_{label}"] = "verifier_unavailable"
                    continue
                for polarity, statement in (("positive", probe.positive), ("negative", probe.negative)):
                    claim = ValidatedAnswerClaim(
                        statement=statement, source=chunk, source_quote=quote,
                    )
                    started = perf_counter()
                    item[f"{polarity}_{label}"] = _safe_evaluate(
                        verifier, question=probe.question, claim=claim, chunk=chunk,
                    )
                    timings[label].append((perf_counter() - started) * 1_000)
                claim = ValidatedAnswerClaim(
                    statement=probe.positive, source=chunk, source_quote=quote,
                )
                started = perf_counter()
                item[f"wrong_question_{label}"] = _safe_evaluate(
                    verifier, question=wrong_question, claim=claim, chunk=chunk,
                )
                timings[label].append((perf_counter() - started) * 1_000)
        rows.append(item)
    return {
        "scope": "one_current_authorized_published_subject",
        "provider_requests": 0,
        "active_space_match": active_space_match,
        "reviewed_topic_count": 5,
        "authored_case_count": len(PROBES),
        "exact_quote_claim_pairs_owner_reviewed": 0,
        "retrieval_recall_measured": False,
        "model_answer_replay_measured": False,
        "wrong_question_control_informative_only_if_positive_accepted": True,
        "results": rows,
        "aggregate_ms": {
            label: {
                "inference_count": len(values),
                "total": round(sum(values), 2),
                "median": round(statistics.median(values), 2) if values else None,
                "maximum": round(max(values), 2) if values else None,
            }
            for label, values in timings.items()
        },
        "page_ablation_aggregate_ms": {
            "case_count": len(page_timings),
            "total": round(sum(page_timings), 2),
            "maximum": round(max(page_timings), 2) if page_timings else None,
        } if canonical_pages is not None else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-v2", action="store_true")
    parser.add_argument("--compare-page-spans", action="store_true")
    parser.add_argument("--owner-review-packet", action="store_true")
    parser.add_argument("--owner-review-html", type=Path)
    parser.add_argument("--replay-answer-contract-v2", action="store_true")
    args = parser.parse_args()

    if (
        args.owner_review_packet and (
            args.require_v2 or args.compare_page_spans or args.replay_answer_contract_v2
            or args.owner_review_html is not None
        )
        or args.owner_review_html is not None and (
            args.require_v2 or args.compare_page_spans or args.replay_answer_contract_v2
        )
        or args.replay_answer_contract_v2 and (
            args.require_v2 or args.compare_page_spans
        )
    ):
        print('{"status":"unavailable","reason":"invalid_options"}')
        return 1
    if args.owner_review_html is not None:
        try:
            validate_owner_review_destination(args.owner_review_html)
        except ProbeUnavailable as exc:
            print(json.dumps({"status": "unavailable", "reason": exc.code}, separators=(",", ":")))
            return 1

    async def run() -> dict[str, object]:
        try:
            chunks, active_space_match, pages, document_slots = await _eligible_owner_chunks(
                with_pages=(
                    args.compare_page_spans or args.owner_review_packet
                    or args.owner_review_html is not None
                ),
            )
            if args.owner_review_packet:
                return prepare_owner_review_packet(chunks, pages, document_slots)
            if args.owner_review_html is not None:
                write_owner_review_html(args.owner_review_html, chunks, pages, document_slots)
                return {"status": "written", "cases": len(PROBES)}
            settings = get_settings()
            if settings.rag_local_support_model_dir is None:
                raise ProbeUnavailable("local_support_unavailable")
            if args.replay_answer_contract_v2:
                return evaluate_answer_contract_v2_in_memory(
                    chunks, model_dir=settings.rag_local_support_model_dir,
                    active_space_match=active_space_match,
                )
            return evaluate_in_memory(
                chunks, model_dir=settings.rag_local_support_model_dir,
                active_space_match=active_space_match,
                canonical_pages=pages if args.compare_page_spans else None,
            )
        finally:
            await close_database()

    try:
        report = asyncio.run(run())
        if args.require_v2 and any(
            row["positive_v2"] == "verifier_unavailable"
            for row in report["results"] if row["selection"] == "selected"
        ):
            raise ProbeUnavailable("v2_unavailable")
    except ProbeUnavailable as exc:
        print(json.dumps({"status": "unavailable", "reason": exc.code}, separators=(",", ":")))
        return 1
    except Exception:
        print('{"status":"unavailable","reason":"probe_failed"}')
        return 1
    print(json.dumps(report, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
