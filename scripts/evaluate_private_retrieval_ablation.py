"""Read-only, provider-free retrieval ablation on owner-confirmed course pages.

The six authored questions and page pointers are fixed before evaluation. The
stored embedding of each selected source chunk (and a different-topic chunk)
is used as a *surrogate*, not a replay of an Ask query embedding. No historical
query embedding was retained. This script can expose regressions and candidate
channel behavior; it cannot justify a live retrieval-policy cutover by itself.

Run in the local self-hosted installation with ``--operator-latest``. Output is
restricted to fixed case/policy labels, page slots, ranks and aggregate metrics.
No source text, private identifier, question, vector or model response is logged.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from dataclasses import replace
import json
import math
from pathlib import Path
import re
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

from app.database import async_session_maker, close_database  # noqa: E402
from app.models.knowledge import SubjectDocument  # noqa: E402
from app.models.rag import RagAnswerJob, RagMessage  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.models.vector import EMBEDDING_DIMENSIONS  # noqa: E402
from app.services.knowledge_retrieval import (  # noqa: E402
    EXACT_V1_POLICY, KnowledgeRetriever, RetrievedKnowledgeChunk,
)
from app.time_utils import utcnow  # noqa: E402

@dataclass(frozen=True, slots=True)
class Probe:
    label: str
    page: int
    question: str
    row_terms: tuple[str, ...]


# These authored questions and selectors contain general technical terms only.
# They duplicate the independently pinned support probe labels so this script
# can run by itself in a read-only container without importing that harness.
PROBES = (
    Probe("bleu_acronym", 22, "What does BLEU stand for?",
          (r"\bbleu\b", r"bilingual\s+evaluation\s+understudy")),
    Probe("bleu_focus", 22, "What does BLEU measure against a reference translation?",
          (r"\bbleu\b", r"n[\s-]?grams?", r"referenc")),
    Probe("cosine", 13, "What does cosine similarity measure?",
          (r"cosine", r"angle", r"magnitud")),
    Probe("bag_of_words", 9, "What information do Bag-of-Words and TF-IDF ignore?",
          (r"bag[\s-]of[\s-]words|\btf[\s-]idf\b", r"word\s+order|context")),
    Probe("logistic", 30, "What function does logistic regression use to produce probabilities?",
          (r"logistic", r"sigmoid", r"probab")),
    Probe("topic_modeling", 4,
          "What is an application of topic modeling in legal or medical domains?",
          (r"topic", r"legal|medical")),
)


# The owner confirmed these page locations in the original PDFs. The exact
# chunk selectors remain machine-chosen and must not be called human labels.
EXPECTED_DOCUMENT_SLOTS = {
    "bleu_acronym": 3,
    "bleu_focus": 3,
    "cosine": 3,
    "bag_of_words": 1,
    "logistic": 3,
    "topic_modeling": 2,
}

POLICIES = (
    EXACT_V1_POLICY,
    replace(EXACT_V1_POLICY, policy_id="bounded_and_12", lexical_max_terms=12),
    replace(EXACT_V1_POLICY, policy_id="bounded_or_12", lexical_max_terms=12,
            lexical_join_or=True),
    replace(EXACT_V1_POLICY, policy_id="bounded_or_section_12", lexical_max_terms=12,
            lexical_join_or=True, lexical_include_section=True),
    replace(EXACT_V1_POLICY, policy_id="bounded_or_section_diverse_12", lexical_max_terms=12,
            lexical_join_or=True, lexical_include_section=True,
            cross_document_diversity=True),
)


class EvaluationUnavailable(RuntimeError):
    """Fixed safe refusal, never an internal database or source exception."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


_ELIGIBLE_ROWS = text("""
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
  AND (NOT :filtered OR eligible.document_id = ANY(:document_ids))
  AND (
    (principal.role = 'INSTRUCTOR' AND subject.instructor_id = principal.id)
    OR (principal.role = 'STUDENT' AND EXISTS (
      SELECT 1 FROM enrollments AS enrollment
      WHERE enrollment.subject_id = subject.id
        AND enrollment.student_id = principal.id
    ))
  )
  AND eligible.page_number IN (4, 9, 13, 22, 30)
ORDER BY eligible.document_id, eligible.page_number,
         eligible.chunk_index, eligible.id
LIMIT 501
""").bindparams(
    bindparam("principal_id", type_=PGUUID(as_uuid=True)),
    bindparam("subject_id", type_=PGUUID(as_uuid=True)),
    bindparam("document_ids", type_=ARRAY(PGUUID(as_uuid=True))),
)

_SOURCE_VECTORS = text("""
SELECT eligible.id AS chunk_id, eligible.embedding::text AS vector_text
FROM eligible_subject_knowledge_chunks AS eligible
JOIN subjects AS subject ON subject.id = eligible.subject_id
JOIN users AS principal ON principal.id = :principal_id
WHERE eligible.id = ANY(:chunk_ids)
  AND eligible.subject_id = :subject_id
  AND eligible.corpus_revision = :corpus_revision
  AND eligible.embedding_space_hash = :space_hash
  AND subject.active_embedding_space_hash = eligible.embedding_space_hash
  AND (NOT :filtered OR eligible.document_id = ANY(:document_ids))
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
    bindparam("document_ids", type_=ARRAY(PGUUID(as_uuid=True))),
    bindparam("chunk_ids", type_=ARRAY(PGUUID(as_uuid=True))),
)


def _vector(value: str) -> tuple[float, ...]:
    try:
        parsed = json.loads(value)
        if not isinstance(parsed, list) or len(parsed) != EMBEDDING_DIMENSIONS:
            raise ValueError
        vector = tuple(float(item) for item in parsed)
        if not all(math.isfinite(item) for item in vector) or not any(vector):
            raise ValueError
        return vector
    except (TypeError, ValueError, OverflowError):
        raise EvaluationUnavailable("vector_unavailable") from None


def _topic_group(label: str) -> str:
    return "bleu" if label.startswith("bleu_") else label


def _different_topic_index(index: int) -> int:
    """Select a fixed different-topic negative vector without randomness."""

    source_group = _topic_group(PROBES[index].label)
    return next(
        candidate for candidate, probe in enumerate(PROBES)
        if _topic_group(probe.label) != source_group
    )


def _chunk(row) -> RetrievedKnowledgeChunk:
    return RetrievedKnowledgeChunk(
        chunk_id=row["chunk_id"], document_id=row["document_id"],
        document_title=row["document_title"],
        content_revision_id=row["content_revision_id"],
        index_revision_id=row["index_revision_id"],
        page_number=row["page_number"], section=row["section"],
        content=row["content"], token_count=row["token_count"],
        embedding_space_hash=row["embedding_space_hash"],
        corpus_revision=int(row["corpus_revision"]),
        vector_similarity=None, lexical_score=None, vector_rank=None,
        lexical_rank=None, fusion_score=0.0,
    )


def _select_source(probe: Probe, chunks: tuple[RetrievedKnowledgeChunk, ...]
                   ) -> RetrievedKnowledgeChunk | None:
    selected = [
        chunk for chunk in chunks
        if chunk.page_number == probe.page
        and all(re.search(pattern, f"{chunk.section or ''}\n{chunk.content}", re.IGNORECASE)
                for pattern in probe.row_terms)
    ]
    return selected[0] if len(selected) == 1 else None


def _rank(chunks: tuple[RetrievedKnowledgeChunk, ...], source: RetrievedKnowledgeChunk,
          *, page_level: bool) -> int | None:
    return next((index for index, chunk in enumerate(chunks, 1) if (
        chunk.document_id == source.document_id
        and chunk.page_number == source.page_number
        and (page_level or chunk.chunk_id == source.chunk_id)
    )), None)


def _overlap_count(chunks: tuple[RetrievedKnowledgeChunk, ...]) -> int:
    """Count retained near-duplicates using the shipped 0.8 term threshold."""

    seen: list[frozenset[str]] = []
    overlapping = 0
    for chunk in chunks:
        terms = frozenset(re.findall(r"\w+", chunk.content.casefold(), re.UNICODE))
        if terms and any(
            len(terms & prior) / min(len(terms), len(prior))
            >= EXACT_V1_POLICY.overlap_threshold for prior in seen if prior
        ):
            overlapping += 1
        else:
            seen.append(terms)
    return overlapping


def _summary(rows: list[dict[str, object]], policy_id: str, mode: str) -> dict[str, object]:
    selected = [row for row in rows if row["policy"] == policy_id and row["mode"] == mode]
    latencies = sorted(float(row["query_ms"]) for row in selected)
    count = len(selected)
    page_hits = [row["page_rank"] for row in selected]
    source_hits = [row["source_chunk_rank"] for row in selected]
    return {
        "policy": policy_id,
        "mode": mode,
        "case_count": count,
        "confirmed_page_recall_at_5": round(sum(rank is not None for rank in page_hits) / count, 4)
        if count else None,
        "confirmed_page_mrr": round(sum(1 / rank if rank else 0 for rank in page_hits) / count, 4)
        if count else None,
        "auto_selected_chunk_recall_at_5": round(sum(rank is not None for rank in source_hits) / count, 4)
        if count else None,
        "overlap_rate": round(
            sum(int(row["overlap_count"]) for row in selected)
            / max(1, sum(int(row["selected_count"]) for row in selected)), 4,
        ),
        "p95_query_ms": round(latencies[math.ceil(count * .95) - 1], 3) if count else None,
        "scope_violation_count": sum(int(row["scope_violations"]) for row in selected),
    }


def _cutover_decision(_summaries: list[dict[str, object]]) -> str:
    # The page labels are owner-confirmed, but neither a real query embedding
    # nor exact selected quote/claim labels were retained/reviewed.
    return "blocked_missing_real_query_vectors_and_reviewed_answerability"


async def evaluate() -> dict[str, object]:
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
            .where(*matching).distinct().limit(2)
        )).all()
        if len(owner_ids) != 1:
            raise EvaluationUnavailable("owner_unavailable")
        job = (await db.scalars(
            select(RagAnswerJob)
            .join(RagMessage, RagMessage.id == RagAnswerJob.question_message_id)
            .where(*matching, RagAnswerJob.user_id == owner_ids[0])
            .order_by(RagAnswerJob.created_at.desc(), RagAnswerJob.id.desc())
            .limit(1)
        )).one_or_none()
        if job is None:
            raise EvaluationUnavailable("job_unavailable")
        principal = await db.get(User, job.user_id)
        if principal is None or principal.role != UserRole.INSTRUCTOR:
            raise EvaluationUnavailable("owner_unavailable")
        try:
            raw_document_ids = job.document_ids
            if isinstance(raw_document_ids, str):
                raw_document_ids = json.loads(raw_document_ids)
            document_ids = tuple(UUID(str(value)) for value in raw_document_ids)
        except (TypeError, ValueError, AttributeError):
            raise EvaluationUnavailable("job_unavailable") from None
        try:
            scope = await KnowledgeRetriever.authorize(
                db, principal=principal, subject_id=job.subject_id,
                query="BLEU evidence evaluation", document_ids=document_ids,
            )
        except Exception:
            raise EvaluationUnavailable("scope_unavailable") from None
        if (
            scope.scope.embedding_space_hash != job.embedding_space_hash
            or scope.scope.corpus_revision != job.corpus_revision
        ):
            raise EvaluationUnavailable("scope_changed")
        document_order = (await db.scalars(
            select(SubjectDocument.id).where(
                SubjectDocument.subject_id == job.subject_id,
                SubjectDocument.uploader_id == principal.id,
            ).order_by(SubjectDocument.updated_at.desc(), SubjectDocument.id).limit(501)
        )).all()
        if len(document_order) > 500:
            raise EvaluationUnavailable("document_list_unavailable")
        document_slots = {document_id: index for index, document_id in enumerate(document_order, 1)}
        params = {
            "principal_id": principal.id, "subject_id": job.subject_id,
            "corpus_revision": scope.scope.corpus_revision,
            "space_hash": scope.scope.embedding_space_hash,
            "filtered": bool(document_ids), "document_ids": list(document_ids),
        }
        chunk_rows = (await db.execute(_ELIGIBLE_ROWS, params)).mappings().all()
        if not chunk_rows or len(chunk_rows) > 500:
            raise EvaluationUnavailable("eligible_corpus_unavailable")
        chunks = tuple(_chunk(row) for row in chunk_rows)
        sources: list[RetrievedKnowledgeChunk] = []
        for probe in PROBES:
            source = _select_source(probe, chunks)
            if source is None:
                raise EvaluationUnavailable("source_selection_unavailable")
            if document_slots.get(source.document_id) != EXPECTED_DOCUMENT_SLOTS[probe.label]:
                raise EvaluationUnavailable("source_slot_changed")
            sources.append(source)
        source_ids = {source.chunk_id for source in sources}
        vector_rows = (await db.execute(_SOURCE_VECTORS, {
            **params, "chunk_ids": list(source_ids),
        })).mappings().all()
        vectors = {row["chunk_id"]: _vector(row["vector_text"]) for row in vector_rows}
        if set(vectors) != source_ids:
            raise EvaluationUnavailable("vector_unavailable")

        rows: list[dict[str, object]] = []
        for index, (probe, source) in enumerate(zip(PROBES, sources, strict=True)):
            for mode, vector_source in (
                ("source_chunk_oracle", source),
                ("different_topic_surrogate", sources[_different_topic_index(index)]),
            ):
                query_vector = vectors[vector_source.chunk_id]
                for policy in POLICIES:
                    retriever = await KnowledgeRetriever.authorize(
                        db, principal=principal, subject_id=job.subject_id,
                        query=probe.question, document_ids=document_ids,
                        policy=policy,
                    )
                    if retriever.scope != scope.scope:
                        raise EvaluationUnavailable("scope_changed")
                    start = perf_counter()
                    result = await retriever.retrieve(
                        query_vector, embedding_space_hash=scope.scope.embedding_space_hash,
                    )
                    elapsed_ms = (perf_counter() - start) * 1000
                    scope_violations = sum(
                        chunk.document_id not in document_slots
                        or (document_ids and chunk.document_id not in document_ids)
                        or chunk.embedding_space_hash != scope.scope.embedding_space_hash
                        or chunk.corpus_revision != scope.scope.corpus_revision
                        for chunk in result.chunks
                    )
                    if scope_violations:
                        raise EvaluationUnavailable("scope_violation")
                    rows.append({
                        "label": probe.label, "policy": policy.policy_id,
                        "mode": mode,
                        "page_rank": _rank(result.chunks, source, page_level=True),
                        "source_chunk_rank": _rank(result.chunks, source, page_level=False),
                        "selected_count": len(result.chunks),
                        "overlap_count": _overlap_count(result.chunks),
                        "query_ms": elapsed_ms,
                        "scope_violations": scope_violations,
                    })
        await db.rollback()
    summaries = [_summary(rows, policy.policy_id, mode)
                 for mode in ("source_chunk_oracle", "different_topic_surrogate")
                 for policy in POLICIES]
    return {
        "scope": "one_owner_one_subject_current_published_active_space",
        "label_status": "owner_confirmed_pages_auto_selected_chunks",
        "query_vector_status": "stored_source_vectors_not_real_ask_query_vectors",
        "provider_requests": 0,
        "database_writes": 0,
        "pre_registered_acceptance": {
            "confirmed_page_recall_at_5_minimum": 1.0,
            "confirmed_page_mrr_minimum": 0.8,
            "no_regression_vs_exact_baseline": True,
            "overlap_rate_maximum": 0.2,
            "p95_query_ms_maximum": 2000,
            "scope_violation_count": 0,
            "real_query_embedding_and_answerability_review_required": True,
        },
        "case_count": len(PROBES),
        "page_pointers": [
            {"label": probe.label, "document_slot": EXPECTED_DOCUMENT_SLOTS[probe.label],
             "page": probe.page}
            for probe in PROBES
        ],
        "rank_rows": [
            {key: row[key] for key in ("label", "policy", "mode", "page_rank", "source_chunk_rank")}
            for row in rows
        ],
        "metrics": summaries,
        "cutover_decision": _cutover_decision(summaries),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator-latest", action="store_true")
    args = parser.parse_args()
    if not args.operator_latest:
        print(json.dumps({"status": "unavailable", "reason": "operator_selection_required"}))
        return 1

    async def run() -> dict[str, object]:
        try:
            return await evaluate()
        finally:
            try:
                await close_database()
            except Exception:
                pass

    try:
        report = asyncio.run(run())
    except EvaluationUnavailable as exc:
        print(json.dumps({"status": "unavailable", "reason": exc.code}))
        return 1
    except Exception:
        print(json.dumps({"status": "unavailable", "reason": "private_evaluation_failed"}))
        return 1
    print(json.dumps(report, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
