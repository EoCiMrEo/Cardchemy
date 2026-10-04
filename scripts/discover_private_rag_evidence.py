"""Read-only, local operator aid for locating published Ask evidence pages.

Run this only in the self-hosted environment with database access. The input is
an existing answer-job UUID; the question and Knowledge text are processed
locally and never printed or persisted by this CLI. It makes no provider
request and cannot determine whether a page actually answers the question. An owner must review
the indicated canonical pages before making an evaluation label.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
import getpass
import json
import os
from pathlib import Path
import re
import sys
from time import perf_counter
from uuid import UUID

from sqlalchemy import bindparam, func, or_, select, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID


BACKEND_ROOT = (
    Path("/app")
    if (Path("/app") / "app").is_dir()
    else Path(__file__).resolve().parents[1] / "backend"
)
sys.path.insert(0, str(BACKEND_ROOT))

try:
    from app.database import async_session_maker, close_database  # noqa: E402
    from app.models.knowledge import (  # noqa: E402
        SubjectDocument, SubjectDocumentChunk, SubjectDocumentContentRevision,
        SubjectDocumentIndexRevision, SubjectDocumentPage,
    )
    from app.models.rag import RagAnswerJob, RagMessage, RagMessageSource  # noqa: E402
    from app.models.user import User  # noqa: E402
    from app.services.knowledge_retrieval import (  # noqa: E402
        EXACT_V1_POLICY,
        KnowledgeRetriever,
    )
    from app.models.vector import EMBEDDING_DIMENSIONS  # noqa: E402
except Exception:
    raise SystemExit("Evidence discovery could not load local configuration") from None


_LOCAL_POLICIES = (
    replace(EXACT_V1_POLICY, policy_id="review_full_question_lexical_v1", minimum_vector_similarity=2.0),
    replace(
        EXACT_V1_POLICY,
        policy_id="review_bounded_and_lexical_v1",
        minimum_vector_similarity=2.0,
        lexical_max_terms=12,
    ),
    replace(
        EXACT_V1_POLICY,
        policy_id="review_bounded_or_lexical_v1",
        minimum_vector_similarity=2.0,
        lexical_max_terms=12,
        lexical_join_or=True,
    ),
    replace(
        EXACT_V1_POLICY,
        policy_id="review_bounded_or_section_lexical_v1",
        minimum_vector_similarity=2.0,
        lexical_max_terms=12,
        lexical_join_or=True,
        lexical_include_section=True,
    ),
)

_TOPIC_MATCH_TERMS = {
    "bleu": ("BLEU",),
    "cosine": ("cosine", "angle"),
    "bag_of_words": ("bag-of-words", "TF-IDF"),
    "logistic": ("logistic", "sigmoid"),
    "topic_modeling": ("topic modeling",),
}


async def latest_job_for_owner(*, email: str | None, term: str, failed: bool) -> UUID:
    """Find one Ask attempt without exposing its private identifier."""

    if not re.fullmatch(r"[A-Za-z0-9]{2,32}", term):
        raise ValueError("The question term must be one bounded plain word")
    normalized_email = email.strip().casefold() if email is not None else None
    if normalized_email is not None and (not normalized_email or len(normalized_email) > 320):
        raise ValueError("An owner account is required")
    async with async_session_maker() as db:
        await db.execute(text("SET TRANSACTION READ ONLY"))
        owner = (
            await db.scalar(select(User).where(User.email == normalized_email))
            if normalized_email is not None else None
        )
        if normalized_email is not None and owner is None:
            raise ValueError("Owner account unavailable")
        query = (
            select(RagAnswerJob.id)
            .join(RagMessage, RagMessage.id == RagAnswerJob.question_message_id)
            .where(
                RagMessage.user_id == RagAnswerJob.user_id,
                RagMessage.role == "user",
                RagMessage.content.ilike(f"%{term}%"),
            )
            .order_by(RagAnswerJob.created_at.desc(), RagAnswerJob.id.desc())
            .limit(1)
        )
        if owner is not None:
            query = query.where(RagAnswerJob.user_id == owner.id)
        if failed:
            query = query.where(RagAnswerJob.status == "failed")
        else:
            query = query.where(
                RagAnswerJob.status == "completed",
                RagAnswerJob.support_rejection_count > 0,
            )
        job_id = await db.scalar(query)
        if job_id is None:
            raise ValueError("Matching answer job unavailable")
        return job_id


async def discover(
    job_id: UUID, *, probe_local_support: bool = False, week3_metadata: bool = False,
    topic_inventory: bool = False,
) -> dict[str, object]:
    """Return only per-policy page pointers, rank, and timing."""

    dummy_vector = [1.0, *([0.0] * (EMBEDDING_DIMENSIONS - 1))]
    async with async_session_maker() as db:
        await db.execute(text("SET TRANSACTION READ ONLY"))
        # Read only long-shipped columns, so this diagnostic can inspect the
        # retained installation before Lane 6 migrations are applied.
        job_query = text(
            "SELECT thread_id, question_message_id, user_id, subject_id, "
            "document_ids, embedding_space_hash FROM rag_answer_jobs WHERE id = :job_id"
        ).bindparams(bindparam("job_id", type_=PGUUID(as_uuid=True)))
        job = (await db.execute(job_query, {"job_id": job_id})).mappings().one_or_none()
        if job is None:
            raise ValueError("Answer job unavailable")
        user = await db.get(User, job["user_id"])
        question_query = text(
            "SELECT role, thread_id, content FROM rag_messages WHERE id = :question_id"
        ).bindparams(bindparam("question_id", type_=PGUUID(as_uuid=True)))
        question = (await db.execute(
            question_query, {"question_id": job["question_message_id"]}
        )).mappings().one_or_none()
        if (
            user is None or question is None or question["role"] != "user"
            or question["thread_id"] != job["thread_id"]
        ):
            raise ValueError("Answer job unavailable")
        try:
            raw_document_ids = job["document_ids"]
            if isinstance(raw_document_ids, str):
                raw_document_ids = json.loads(raw_document_ids)
            document_ids = [UUID(value) for value in raw_document_ids]
        except (TypeError, ValueError, AttributeError):
            raise ValueError("Answer job document selection unavailable") from None

        results = []
        for policy in _LOCAL_POLICIES:
            retriever = await KnowledgeRetriever.authorize(
                db,
                principal=user,
                subject_id=job["subject_id"],
                query=question["content"],
                document_ids=document_ids,
                limit=policy.max_results,
                policy=policy,
            )
            if retriever.scope.embedding_space_hash != job["embedding_space_hash"]:
                raise ValueError("Answer job embedding space is no longer current")
            started = perf_counter()
            result = await retriever.retrieve(
                dummy_vector, embedding_space_hash=job["embedding_space_hash"]
            )
            elapsed_ms = (perf_counter() - started) * 1000
            results.append((policy.policy_id, result.chunks, elapsed_ms))

        # Match the instructor Knowledge list's order so the safe slot number
        # points to a document the owner can recognize in the authenticated UI.
        document_order = tuple((await db.scalars(
            select(SubjectDocument.id)
            .where(SubjectDocument.subject_id == job["subject_id"])
            .order_by(SubjectDocument.updated_at.desc(), SubjectDocument.id)
        )).all())

        week3_report: dict[str, object] | None = None
        if week3_metadata:
            # Names and private source contents are used only within this
            # read-only process. Slots mirror the authenticated Knowledge UI.
            documents = (await db.scalars(
                select(SubjectDocument)
                .where(SubjectDocument.subject_id == job["subject_id"])
                .order_by(SubjectDocument.updated_at.desc(), SubjectDocument.id)
            )).all()
            matched_documents = [
                document for document in documents
                if re.search(
                    r"\bweek[\s_-]*0?3\b",
                    f"{document.title} {document.source_pdf_name}",
                    flags=re.IGNORECASE,
                )
            ]
            rows = []
            for document in matched_documents:
                content_revision = await db.scalar(
                    select(SubjectDocumentContentRevision).where(
                        SubjectDocumentContentRevision.document_id == document.id,
                        SubjectDocumentContentRevision.subject_id == job["subject_id"],
                        SubjectDocumentContentRevision.is_active.is_(True),
                        SubjectDocumentContentRevision.status == "ready",
                        SubjectDocumentContentRevision.reviewed_at.is_not(None),
                        SubjectDocumentContentRevision.published_at.is_not(None),
                    )
                )
                index_revision = (
                    await db.scalar(select(SubjectDocumentIndexRevision).where(
                        SubjectDocumentIndexRevision.content_revision_id == content_revision.id,
                        SubjectDocumentIndexRevision.subject_id == job["subject_id"],
                        SubjectDocumentIndexRevision.embedding_space_hash == job["embedding_space_hash"],
                        SubjectDocumentIndexRevision.is_active.is_(True),
                        SubjectDocumentIndexRevision.status == "ready",
                    )) if content_revision is not None else None
                )
                page_count = (
                    await db.scalar(select(func.count(SubjectDocumentPage.id)).where(
                        SubjectDocumentPage.content_revision_id == content_revision.id,
                        SubjectDocumentPage.subject_id == job["subject_id"],
                    )) if content_revision is not None else 0
                )
                chunk_count = (
                    await db.scalar(select(func.count(SubjectDocumentChunk.id)).where(
                        SubjectDocumentChunk.index_revision_id == index_revision.id,
                        SubjectDocumentChunk.subject_id == job["subject_id"],
                        SubjectDocumentChunk.embedding.is_not(None),
                    )) if index_revision is not None else 0
                )
                rows.append({
                    "document_slot": document_order.index(document.id) + 1,
                    "current_reviewed_published_pages": page_count,
                    "current_space_ready_embedded_chunks": chunk_count,
                })
            week3_report = {
                "scope": "same_subject_as_selected_answer_job",
                "title_or_filename_shape_matches": len(matched_documents),
                "matches": rows,
                "twenty_distinct_grounded_cards_feasible": "unknown_without_fact_review",
            }

        topic_inventory_report: dict[str, int] | None = None
        if topic_inventory:
            topic_inventory_report = {}
            for label, terms in _TOPIC_MATCH_TERMS.items():
                topic_inventory_report[label] = int(await db.scalar(
                    select(func.count(RagAnswerJob.id))
                    .join(RagMessage, RagMessage.id == RagAnswerJob.question_message_id)
                    .where(
                        RagAnswerJob.subject_id == job["subject_id"],
                        RagMessage.user_id == RagAnswerJob.user_id,
                        RagMessage.role == "user",
                        or_(*(RagMessage.content.ilike(f"%{term}%") for term in terms)),
                    )
                ) or 0)

        page_contents: dict[tuple[UUID, int], str] = {}
        for _, chunks, _ in results:
            for chunk in chunks:
                page_key = (chunk.content_revision_id, chunk.page_number)
                if page_key in page_contents:
                    continue
                page = await db.scalar(
                    select(SubjectDocumentPage.content).where(
                        SubjectDocumentPage.subject_id == job["subject_id"],
                        SubjectDocumentPage.document_id == chunk.document_id,
                        SubjectDocumentPage.content_revision_id == chunk.content_revision_id,
                        SubjectDocumentPage.page_number == chunk.page_number,
                    )
                )
                if page is not None:
                    page_contents[page_key] = page

        support_probe: dict[str, object] | None = None
        if probe_local_support:
            from app.ai.answering import ValidatedAnswerClaim
            from app.ai.local_support import (
                LocalSupportUnavailable, create_local_support_verifier,
            )

            model_dir = os.environ.get("RAG_LOCAL_SUPPORT_MODEL_DIR")
            if not model_dir:
                raise ValueError("The pinned local support bundle is unavailable")
            verifier = create_local_support_verifier(Path(model_dir))
            historical_pairs = (await db.execute(
                select(RagMessageSource.source_quote, RagMessageSource.claim_text)
                .join(RagMessage, RagMessage.id == RagMessageSource.message_id)
                .where(
                    RagMessageSource.subject_id == job["subject_id"],
                    RagMessageSource.user_id == job["user_id"],
                    RagMessage.user_id == job["user_id"],
                    RagMessage.role == "assistant",
                    RagMessage.outcome == "answer",
                )
                .order_by(RagMessageSource.created_at.desc(), RagMessageSource.id.desc())
                .limit(501)
            )).all()
            within_bound = historical_pairs[:500]
            pair_lengths = [
                len(verifier._nli._tokenizer.encode(quote, claim).ids)
                for quote, claim in within_bound
            ]
            historical_length_report = {
                "scope": "retained_answer_citations_same_owner_subject_not_current_only",
                "bounded_sample_count": len(within_bound),
                "sample_exceeded_bound": len(historical_pairs) > 500,
                "nli_pairs_over_384_tokens": sum(length > 384 for length in pair_lengths),
                "max_pair_tokens": max(pair_lengths, default=0),
            }
            selected_chunks = next(
                chunks for policy_id, chunks, _ in results
                if policy_id == "review_bounded_or_lexical_v1"
            )
            question_text = question["content"]
            question_lower = question_text.casefold()
            if re.search(r"\bstands?\s+for\b", question_lower):
                question_kind = "acronym_expansion"
                authored_claim = "BLEU stands for Bilingual Evaluation Understudy."

                def matches(sentence: str) -> bool:
                    return "bilingual evaluation understudy" in sentence.casefold()
            elif "focus" in question_lower and "bleu" in question_lower:
                question_kind = "metric_focus"
                authored_claim = (
                    "BLEU evaluates machine translation by measuring n-gram "
                    "overlap with reference translations."
                )

                def matches(sentence: str) -> bool:
                    value = sentence.casefold()
                    return bool(re.search(r"\bn[\s-]?gram", value)) and "reference" in value
            else:
                question_kind = "unsupported_question_shape"

                def matches(sentence: str) -> bool:
                    return False

                authored_claim = ""

            matched_quotes = []
            for chunk in selected_chunks:
                for sentence in re.split(r"(?<=[.!?])\s+", chunk.content):
                    quote = sentence.strip()
                    if matches(quote) and quote in chunk.content:
                        matched_quotes.append((chunk, quote))
                        break

            reason_counts: dict[str, int] = {}
            self_chunk_excluded_reason_counts: dict[str, int] = {}
            quote_has_subject_count = 0
            quote_multi_sentence_count = 0
            quote_component_conflict_count = 0
            local_unavailable = 0
            for chunk, quote in matched_quotes[:3]:
                if "bleu" in quote.casefold():
                    quote_has_subject_count += 1
                components = tuple(re.split(r"(?<=[.!?])\s+", quote))
                if len(components) > 1:
                    quote_multi_sentence_count += 1
                claim = ValidatedAnswerClaim(
                    statement=authored_claim, source=chunk, source_quote=quote,
                )
                try:
                    for component in components:
                        if component.strip().casefold() == quote.casefold():
                            continue
                        score = verifier._nli.score(component, authored_claim)
                        if score.contradiction >= 0.5 and score.contradiction > max(
                            score.entailment, score.neutral
                        ):
                            quote_component_conflict_count += 1
                    verdict = verifier.evaluate(
                        question=question_text, claims=(claim,), chunks=selected_chunks,
                    )
                    reason_counts[verdict.reason_code] = reason_counts.get(verdict.reason_code, 0) + 1
                    other_chunks = tuple(
                        candidate for candidate in selected_chunks
                        if candidate.chunk_id != chunk.chunk_id
                    )
                    if other_chunks:
                        excluded_verdict = verifier.evaluate(
                            question=question_text, claims=(claim,), chunks=other_chunks,
                        )
                        self_chunk_excluded_reason_counts[excluded_verdict.reason_code] = (
                            self_chunk_excluded_reason_counts.get(excluded_verdict.reason_code, 0) + 1
                        )
                except LocalSupportUnavailable:
                    local_unavailable += 1
            support_probe = {
                "question_kind": question_kind,
                "scope": "authored_claim_against_lexical_candidates_not_original_model_claim",
                "matched_quote_count": len(matched_quotes),
                "checked_quote_count": min(3, len(matched_quotes)),
                "reason_counts": reason_counts,
                "self_chunk_excluded_reason_counts": self_chunk_excluded_reason_counts,
                "quote_has_bleu_subject_count": quote_has_subject_count,
                "multi_sentence_quote_count": quote_multi_sentence_count,
                "quote_component_conflict_count": quote_component_conflict_count,
                "local_unavailable_count": local_unavailable,
                "historical_quote_claim_length": historical_length_report,
            }

    # Document slots mirror the current owner Knowledge list. UUIDs, titles,
    # source text, question and model output are deliberately excluded.
    slots = {
        document_id: index for index, document_id in enumerate(document_order, start=1)
    }

    def concept_flags(content: str) -> dict[str, bool]:
        value = content.casefold()
        reference = "reference" in value
        ngram = bool(re.search(r"\bn[\s-]?gram", value))
        return {
            "bleu_expansion": "bilingual evaluation understudy" in value,
            "ngram_with_reference": ngram and reference,
            "overlap_with_reference": "overlap" in value and reference,
            "precision_with_reference": "precision" in value and reference,
        }

    def combined_flags(contents: list[str]) -> dict[str, bool]:
        return {
            key: any(concept_flags(content)[key] for content in contents)
            for key in ("bleu_expansion", "ngram_with_reference",
                        "overlap_with_reference", "precision_with_reference")
        }

    report = {
        "purpose": "page_discovery_only_not_answer_correctness_or_vector_recall",
        "provider_requests": 0,
        "vector_ranks": "unavailable_without_stored_query_embedding",
        "policies": [
            {
                "policy": policy_id,
                "selected_count": len(chunks),
                "elapsed_milliseconds": round(elapsed_ms, 3),
                "selected_chunk_concepts": combined_flags([chunk.content for chunk in chunks]),
                "selected_page_concepts": combined_flags([
                    page_contents[(chunk.content_revision_id, chunk.page_number)]
                    for chunk in chunks
                    if (chunk.content_revision_id, chunk.page_number) in page_contents
                ]),
                "page_pointers": [
                    {
                        "document_slot": slots[chunk.document_id],
                        "page": chunk.page_number,
                        "lexical_rank": chunk.lexical_rank,
                    }
                    for chunk in chunks
                ],
            }
            for policy_id, chunks, elapsed_ms in results
        ],
    }
    if support_probe is not None:
        report["local_support_probe"] = support_probe
    if week3_report is not None:
        report["week3_metadata"] = week3_report
    if topic_inventory_report is not None:
        report["topic_job_inventory"] = topic_inventory_report
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--answer-job-id", type=UUID)
    selection.add_argument("--latest-support-rejected", action="store_true")
    selection.add_argument("--latest-failed", action="store_true")
    parser.add_argument(
        "--term", help="One plain question word for owner-scoped latest-job discovery"
    )
    parser.add_argument(
        "--operator-latest", action="store_true",
        help="Select latest matching job across owners; only safe page pointers are printed",
    )
    parser.add_argument(
        "--probe-local-support", action="store_true",
        help="Run pinned local NLI/QA on bounded authored BLEU claims; no provider call",
    )
    parser.add_argument(
        "--week3-metadata", action="store_true",
        help="Count current published Week-3-shaped document pages/chunks without printing names",
    )
    parser.add_argument(
        "--topic-inventory", action="store_true",
        help="Count retained Ask jobs by screenshot topic within the selected Subject",
    )
    args = parser.parse_args()
    if args.answer_job_id is None and args.term is None:
        parser.error("--term is required for latest-job discovery")
    if args.answer_job_id is not None and args.term is not None:
        parser.error("--term applies only to latest-job discovery")
    if args.answer_job_id is not None and args.operator_latest:
        parser.error("--operator-latest applies only to latest-job discovery")
    owner_email = (
        getpass.getpass("Account email (hidden): ")
        if args.answer_job_id is None and not args.operator_latest else None
    )

    async def run() -> dict[str, object]:
        try:
            job_id = args.answer_job_id or await latest_job_for_owner(
                email=owner_email,
                term=args.term,
                failed=args.latest_failed,
            )
            return await discover(
                job_id, probe_local_support=args.probe_local_support,
                week3_metadata=args.week3_metadata,
                topic_inventory=args.topic_inventory,
            )
        finally:
            await close_database()

    try:
        report = asyncio.run(run())
    except Exception:
        # SQL exceptions and private query parameters must never reach stdout
        # or a shell transcript. Operator remediation uses ordinary DB health.
        raise SystemExit("Evidence discovery unavailable; check job access and local database health") from None
    print(json.dumps(report, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
