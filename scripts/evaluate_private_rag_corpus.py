"""Read-only, local-only Ask retrieval proxy evaluation on retained questions.

The questions and authorized published chunks stay in this process. Output is
limited to topic counts, aggregate metrics, and owner Knowledge page pointers.
The lexical-only results are not historical hybrid/vector replay or reviewed
relevance labels. They cannot authorize a retrieval policy cutover by themselves.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
import getpass
import json
import math
import re
from time import perf_counter
from uuid import UUID

from sqlalchemy import bindparam, select, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID

from discover_private_rag_evidence import latest_job_for_owner
from app.database import async_session_maker, close_database
from app.models.knowledge import SubjectDocument
from app.models.rag import RagAnswerJob, RagMessage
from app.models.user import User
from app.models.vector import EMBEDDING_DIMENSIONS
from app.services.knowledge_retrieval import (
    EXACT_V1_POLICY, KnowledgeRetriever, KnowledgeRetrievalError,
)


_POLICIES = (
    replace(EXACT_V1_POLICY, policy_id="lexical_full_and", minimum_vector_similarity=2.0),
    replace(EXACT_V1_POLICY, policy_id="lexical_bounded_and", minimum_vector_similarity=2.0,
            lexical_max_terms=12),
    replace(EXACT_V1_POLICY, policy_id="lexical_bounded_or", minimum_vector_similarity=2.0,
            lexical_max_terms=12, lexical_join_or=True),
    replace(EXACT_V1_POLICY, policy_id="lexical_or_section", minimum_vector_similarity=2.0,
            lexical_max_terms=12, lexical_join_or=True, lexical_include_section=True),
    replace(EXACT_V1_POLICY, policy_id="lexical_or_diversity", minimum_vector_similarity=2.0,
            lexical_max_terms=12, lexical_join_or=True, cross_document_diversity=True),
)
_TOPICS = (
    "bleu_acronym", "bleu_focus", "cosine", "bag_of_words", "logistic", "topic_modeling"
)


def _topic(question: str) -> str | None:
    value = question.casefold()
    if "bleu" in value:
        if re.search(r"\bstands?\s+for\b|\bacronym\b", value):
            return "bleu_acronym"
        if any(term in value for term in ("focus", "translation", "reference", "evaluat")):
            return "bleu_focus"
        return None
    if "cosine" in value or ("similarity" in value and "angle" in value):
        return "cosine"
    if "bag-of-words" in value or "tf-idf" in value:
        return "bag_of_words"
    if "logistic" in value or "sigmoid" in value:
        return "logistic"
    if "topic model" in value:
        return "topic_modeling"
    return None


def _source_concept(topic: str, content: str) -> bool:
    """Conservative machine proxy to narrow page review, never a human label."""

    value = content.casefold()
    if topic == "bleu_acronym":
        return "bilingual evaluation understudy" in value
    if topic == "bleu_focus":
        return "bleu" in value and bool(re.search(r"\bn[\s-]?gram", value)) and "reference" in value
    if topic == "cosine":
        return "cosine" in value and "angle" in value
    if topic == "bag_of_words":
        return ("bag-of-words" in value or "tf-idf" in value) and (
            "word order" in value or "context" in value
        )
    if topic == "logistic":
        return "logistic" in value and "sigmoid" in value and "probab" in value
    if topic == "topic_modeling":
        return "topic" in value and ("legal" in value or "medical" in value)
    return False


def _synthetic_cases(topic: str) -> tuple[tuple[str, str], ...]:
    # Authored generic controls, not copied user questions or source passages.
    anchors = {
        "bleu_acronym": "BLEU", "bleu_focus": "BLEU", "cosine": "cosine similarity",
        "bag_of_words": "bag-of-words and TF-IDF", "logistic": "logistic regression",
        "topic_modeling": "topic modeling",
    }
    anchor = anchors[topic]
    return (
        ("paraphrase_proxy", f"Explain the course definition or purpose of {anchor}."),
        ("unresolved_followup", "Could you explain that further?"),
        ("unsupported_control", f"How many moons does {anchor} have?"),
    )


_AUTHORIZED_CHUNKS = text("""
SELECT eligible.content
FROM eligible_subject_knowledge_chunks AS eligible
JOIN subjects ON subjects.id = eligible.subject_id
JOIN users AS principal ON principal.id = :principal_id
WHERE eligible.subject_id = :subject_id
  AND eligible.corpus_revision = :corpus_revision
  AND eligible.embedding_space_hash = :embedding_space_hash
  AND (NOT :filtered OR eligible.document_id = ANY(:document_ids))
  AND (
    (principal.role = 'INSTRUCTOR' AND subjects.instructor_id = principal.id)
    OR (principal.role = 'STUDENT' AND EXISTS (
        SELECT 1 FROM enrollments
        WHERE enrollments.student_id = principal.id
          AND enrollments.subject_id = subjects.id
    ))
  )
ORDER BY eligible.document_id, eligible.page_number, eligible.chunk_index, eligible.id
LIMIT 2001
""").bindparams(
    bindparam("principal_id", type_=PGUUID(as_uuid=True)),
    bindparam("subject_id", type_=PGUUID(as_uuid=True)),
    bindparam("document_ids", type_=ARRAY(PGUUID(as_uuid=True))),
)


async def evaluate(reference_job_id: UUID) -> dict[str, object]:
    vector = [1.0, *([0.0] * (EMBEDDING_DIMENSIONS - 1))]
    async with async_session_maker() as db:
        await db.execute(text("SET TRANSACTION READ ONLY"))
        reference = (await db.execute(
            select(RagAnswerJob.subject_id, RagAnswerJob.embedding_space_hash)
            .where(RagAnswerJob.id == reference_job_id)
        )).one_or_none()
        if reference is None:
            raise ValueError("Reference job unavailable")
        subject_id, space_hash = reference
        document_order = tuple((await db.scalars(
            select(SubjectDocument.id).where(SubjectDocument.subject_id == subject_id)
            .order_by(SubjectDocument.updated_at.desc(), SubjectDocument.id)
        )).all())
        candidates = (await db.execute(
            select(
                RagAnswerJob.user_id, RagAnswerJob.document_ids,
                RagAnswerJob.embedding_space_hash, RagMessage.content,
            )
            .join(RagMessage, RagMessage.id == RagAnswerJob.question_message_id)
            .where(
                RagAnswerJob.subject_id == subject_id,
                RagAnswerJob.embedding_space_hash == space_hash,
                RagMessage.user_id == RagAnswerJob.user_id,
                RagMessage.role == "user",
            )
            .order_by(RagAnswerJob.created_at.desc(), RagAnswerJob.id.desc())
            .limit(100)
        )).all()
        selected: dict[str, list] = {topic: [] for topic in _TOPICS}
        seen_questions: dict[str, set[str]] = {topic: set() for topic in _TOPICS}
        for candidate in candidates:
            topic = _topic(candidate.content)
            if topic is None or len(selected[topic]) >= 2:
                continue
            key = " ".join(candidate.content.casefold().split())
            if key not in seen_questions[topic]:
                selected[topic].append(candidate)
                seen_questions[topic].add(key)

        rows: list[dict[str, object]] = []
        review_hints: dict[str, list[dict[str, int]]] = {topic: [] for topic in _TOPICS}
        corpus_cache: dict[tuple, tuple[str, ...] | None] = {}
        for topic, jobs in selected.items():
            for index, job in enumerate(jobs):
                principal = await db.get(User, job.user_id)
                if principal is None:
                    continue
                raw_document_ids = job.document_ids
                if isinstance(raw_document_ids, str):
                    raw_document_ids = json.loads(raw_document_ids)
                document_ids = tuple(UUID(str(value)) for value in raw_document_ids)
                cases = [("direct", job.content)]
                if index == 0:
                    cases.extend(_synthetic_cases(topic))
                for kind, query in cases:
                    try:
                        retriever = await KnowledgeRetriever.authorize(
                            db, principal=principal, subject_id=subject_id,
                            query=query, document_ids=document_ids, policy=_POLICIES[0],
                        )
                    except KnowledgeRetrievalError:
                        continue
                    if retriever.scope.embedding_space_hash != space_hash:
                        continue
                    cache_key = (
                        retriever.scope.corpus_revision, space_hash, document_ids,
                    )
                    if cache_key not in corpus_cache:
                        contents = (await db.scalars(_AUTHORIZED_CHUNKS, {
                            "principal_id": principal.id,
                            "subject_id": subject_id,
                            "corpus_revision": retriever.scope.corpus_revision,
                            "embedding_space_hash": space_hash,
                            "filtered": bool(document_ids),
                            "document_ids": list(document_ids),
                        })).all()
                        corpus_cache[cache_key] = (
                            tuple(contents) if len(contents) <= 2000 else None
                        )
                    corpus = corpus_cache[cache_key]
                    source_adequate = (
                        any(_source_concept(topic, content) for content in corpus)
                        if corpus is not None and kind in ("direct", "paraphrase_proxy")
                        else None
                    )
                    for policy in _POLICIES:
                        scoped = await KnowledgeRetriever.authorize(
                            db, principal=principal, subject_id=subject_id,
                            query=query, document_ids=document_ids, policy=policy,
                        )
                        start = perf_counter()
                        result = await scoped.retrieve(vector, embedding_space_hash=space_hash)
                        elapsed_ms = (perf_counter() - start) * 1000
                        first_adequate_rank = next(
                            (rank for rank, chunk in enumerate(result.chunks, start=1)
                             if _source_concept(topic, chunk.content)), None
                        )
                        rows.append({
                            "topic": topic, "kind": kind, "policy": policy.policy_id,
                            "source_adequate": source_adequate,
                            "first_adequate_rank": first_adequate_rank,
                            "selected_count": len(result.chunks), "elapsed_ms": elapsed_ms,
                            "duplicate_count": len(result.chunks) - len({
                                " ".join(chunk.content.casefold().split()) for chunk in result.chunks
                            }),
                        })
                        if kind == "direct" and policy.policy_id == "lexical_bounded_or":
                            hints = review_hints[topic]
                            for chunk in result.chunks:
                                if not _source_concept(topic, chunk.content):
                                    continue
                                pointer = {
                                    "document_slot": document_order.index(chunk.document_id) + 1,
                                    "page": chunk.page_number,
                                }
                                if pointer not in hints and len(hints) < 5:
                                    hints.append(pointer)

    summaries = []
    for policy in _POLICIES:
        policy_rows = [row for row in rows if row["policy"] == policy.policy_id]
        positives = [row for row in policy_rows if row["source_adequate"] is True]
        latencies = sorted(row["elapsed_ms"] for row in policy_rows)
        summaries.append({
            "policy": policy.policy_id,
            "case_count": len(policy_rows),
            "source_adequate_positive_cases": len(positives),
            "proxy_recall_at_5": (
                round(sum(row["first_adequate_rank"] is not None for row in positives) / len(positives), 4)
                if positives else None
            ),
            "proxy_mrr": (
                round(sum(1 / row["first_adequate_rank"] if row["first_adequate_rank"] else 0
                          for row in positives) / len(positives), 4)
                if positives else None
            ),
            "p95_query_ms": round(latencies[math.ceil(len(latencies) * .95) - 1], 3) if latencies else None,
            "duplicate_rate": (
                round(sum(row["duplicate_count"] for row in policy_rows) /
                      sum(row["selected_count"] for row in policy_rows), 4)
                if sum(row["selected_count"] for row in policy_rows) else 0,
            )[0],
            "unresolved_followup_with_any_candidate": sum(
                row["selected_count"] > 0 for row in policy_rows
                if row["kind"] == "unresolved_followup"
            ),
            "unsupported_control_with_any_candidate": sum(
                row["selected_count"] > 0 for row in policy_rows
                if row["kind"] == "unsupported_control"
            ),
        })
    return {
        "scope": "one_subject_current_published_index_existing_owner_questions",
        "provider_requests": 0,
        "historical_hybrid_vector_top5": "unavailable_without_stored_query_embedding",
        "label_status": "machine_concept_proxy_not_human_reviewed",
        "pre_registered_cutover_requirements": {
            "human_reviewed_answerable_topics_minimum": 5,
            "positive_recall_at_5_and_mrr": "no_regression_vs_hybrid_exact_v1",
            "cross_subject_or_unpublished_exposure": 0,
            "unsupported_or_conflicting_accepted_answers": 0,
            "physical_query_embeddings_per_attempt_maximum": 1,
            "answer_requests_per_attempt_maximum": 1,
        },
        "direct_question_counts": {topic: len(selected[topic]) for topic in _TOPICS},
        "review_page_hints": review_hints,
        "lexical_only_proxy_metrics": summaries,
        "cutover_decision": "not_authorized_by_unreviewed_proxy_or_missing_hybrid_baseline",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--term", default="BLEU")
    parser.add_argument("--operator-latest", action="store_true")
    args = parser.parse_args()
    email = None if args.operator_latest else getpass.getpass("Account email (hidden): ")

    async def run() -> dict[str, object]:
        try:
            reference_job_id = await latest_job_for_owner(
                email=email, term=args.term, failed=False,
            )
            return await evaluate(reference_job_id)
        finally:
            await close_database()

    try:
        report = asyncio.run(run())
    except Exception:
        raise SystemExit("Private RAG evaluation unavailable; check local database and access") from None
    print(json.dumps(report, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
