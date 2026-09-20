"""Private deterministic worker and operator setup for the disposable browser journey.

This module is never imported by shipped application entry points. Only the
generated ``journey_test`` database on loopback may be modified.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url

from app.ai.answering import ClaimSupportOutput, GroundedAnswerOutput
from app.ai.contracts import CandidateBatch
from app.ai.embeddings import EmbeddingResponse
from app.ai.pipeline import FlashcardGenerationPipeline
from app.ai.providers import ProviderAttemptTelemetry, ProviderResponse, ProviderUsage
from app.config import get_settings
from app.database import async_session_maker, close_database, engine, verify_database_revision
from app.models.email import EmailOutboxMessage
from app.models.flashcard import Enrollment, Flashcard, StudyAnswerSubmission, StudyProgress
from app.models.generation import (
    GenerationJob,
    GenerationJobSource,
    KnowledgeUploadQuotaEvent,
)
from app.models.knowledge import (
    KnowledgeStorageUsage,
    RagEmbeddingSpace,
    SubjectDocument,
    SubjectDocumentChunk,
    SubjectDocumentContentRevision,
    SubjectDocumentIndexJob,
    SubjectDocumentIndexRevision,
    SubjectDocumentPage,
)
from app.models.rag import (
    RagAnswerJob,
    RagAnswerQuotaEvent,
    RagMessage,
    RagMessageSource,
    RagThread,
)
from app.models.subject import FlashcardSet, Subject
from app.models.user import User


FACTS = (
    ("What color does chlorophyll give leaves?", "Green", "Chlorophyll gives leaves their Green color."),
    ("Which process lets plants convert light into energy?", "Photosynthesis", "Photosynthesis converts light into chemical energy."),
)


async def require_disposable_database() -> None:
    settings = get_settings()
    url = make_url(settings.database_url)
    journey_mode = os.getenv("JOURNEY_RAG_MODE")
    if (
        os.getenv("RUN_JOURNEY_TESTS") != "1"
        or journey_mode not in {"rag-off", "rag-on"}
        or settings.rag_enabled != (journey_mode == "rag-on")
        or settings.environment != "test"
        or url.database != "journey_test"
        or url.host not in {"127.0.0.1", "localhost", "::1"}
        or url.drivername != "postgresql+asyncpg"
    ):
        raise RuntimeError("Refusing to run outside the generated disposable journey database")
    async with engine.connect() as connection:
        if await connection.scalar(text("SELECT current_database()")) != "journey_test":
            raise RuntimeError("Disposable journey database identity changed")
    await verify_database_revision()


class JourneyProvider:
    """Return authored source-grounded cards without an SDK or network client."""

    async def generate_structured(self, **arguments):
        if arguments["response_model"] is not CandidateBatch:
            raise RuntimeError("The small journey fixture must use direct generation")
        payload = json.loads(arguments["user_prompt"])
        evidence = {item["source_chunk_id"]: item["text"] for item in payload["untrusted_documents"]}
        cards = []
        for chunk_id, count in payload["requested_cards_by_source_chunk_id"].items():
            if count > len(FACTS):
                raise RuntimeError("Journey fixture requested more than its authored two cards")
            for question, answer, quote in FACTS[:count]:
                if quote not in evidence[chunk_id]:
                    raise RuntimeError("Journey source facts changed")
                cards.append({
                    "front": question, "back": answer,
                    "options": [answer, "Incorrect A", "Incorrect B", "Incorrect C"],
                    "source_chunk_id": chunk_id, "source_quote": quote,
                })
        return ProviderResponse(CandidateBatch(cards=cards), ProviderUsage(100, 100, False))


class JourneyGraph:
    def __init__(self, **arguments):
        self.pipeline = FlashcardGenerationPipeline(provider=JourneyProvider(), **arguments)

    async def ainvoke(self, state, **_):
        return await self.pipeline.run(state["pdf_document"], state["target_count"])


class JourneyEmbeddingProvider:
    """One deterministic cosine space; no SDK, credentials or network calls."""

    def __init__(self) -> None:
        self.requests = 0

    async def embed_documents(self, texts):
        self.requests += 1
        return EmbeddingResponse(
            vectors=tuple(tuple([1.0, *([0.0] * 1535)]) for _ in texts),
            usage=ProviderUsage(sum(len(text.split()) for text in texts), 0, False),
        )

    async def embed_query(self, text):
        self.requests += 1
        return EmbeddingResponse(
            vectors=(tuple([1.0, *([0.0] * 1535)]),),
            usage=ProviderUsage(len(text.split()), 0, False),
        )

    def telemetry_snapshot(self):
        return ProviderAttemptTelemetry(
            request_count=self.requests,
            retry_count=0,
            rate_limit_wait_seconds=0,
            request_counts_by_stage={"journey_embedding": self.requests},
        )


class JourneyAnswerProvider:
    """Return a grounded authored answer and affirmative separate support review."""

    def __init__(self) -> None:
        self.requests = 0

    async def generate_structured(self, **arguments):
        self.requests += 1
        payload = json.loads(arguments["user_prompt"])
        response_model = arguments["response_model"]
        if response_model is GroundedAnswerOutput:
            evidence = payload["evidence_untrusted"]
            if len(evidence) != 1:
                raise RuntimeError("Journey answer requires exactly one bounded source")
            quote = evidence[0]["content"]
            statement = "Chlorophyll gives leaves their Green color."
            data = GroundedAnswerOutput.model_validate({
                "outcome": "answer",
                "answer": statement,
                "claims": [{
                    "statement": statement,
                    "source_chunk_id": UUID(evidence[0]["source_chunk_id"]),
                    "source_quote": quote,
                }],
            })
        elif response_model is ClaimSupportOutput:
            data = ClaimSupportOutput.model_validate({
                "decisions": [{
                    "claim_index": claim["claim_index"],
                    "entailed_by_quote": True,
                    "relevant_to_question": True,
                    "not_contradicted": True,
                } for claim in payload["claims_untrusted"]],
            })
        else:
            raise RuntimeError("Journey answer provider received an unexpected contract")
        return ProviderResponse(data, ProviderUsage(50, 20, False))

    def telemetry_snapshot(self):
        return ProviderAttemptTelemetry(
            request_count=self.requests,
            retry_count=0,
            rate_limit_wait_seconds=0,
            request_counts_by_stage={"journey_answer": self.requests},
        )


async def seed_instructor() -> None:
    from app import cli

    async with async_session_maker() as session:
        if await session.scalar(select(func.count(User.id))):
            raise RuntimeError("The journey requires a newly generated empty database")
    # Exercise the maintained operator creation path with generated test input.
    cli.getpass.getpass = lambda _: os.environ["JOURNEY_INSTRUCTOR_PASSWORD"]
    await cli.create_instructor(os.environ["JOURNEY_INSTRUCTOR_EMAIL"], "Journey Instructor", False)


async def verify_records() -> None:
    if os.environ.get("JOURNEY_RAG_MODE") == "rag-off":
        await verify_rag_disabled_records()
        return

    expected_counts = {User: 2, Subject: 2, FlashcardSet: 1, Flashcard: 2,
                       Enrollment: 2, StudyProgress: 2, StudyAnswerSubmission: 2,
                       GenerationJob: 1, GenerationJobSource: 0,
                       SubjectDocument: 1, SubjectDocumentContentRevision: 1,
                       SubjectDocumentPage: 1, SubjectDocumentIndexRevision: 1,
                       SubjectDocumentChunk: 1, SubjectDocumentIndexJob: 1,
                       RagThread: 3, RagMessage: 2, RagAnswerJob: 1,
                       RagMessageSource: 1}
    async with async_session_maker() as session:
        for model, count in expected_counts.items():
            if await session.scalar(select(func.count()).select_from(model)) != count:
                raise RuntimeError(f"Journey persistence check failed for {model.__tablename__}")
        job = await session.scalar(select(GenerationJob))
        if (
            job.status != "completed"
            or job.provider_request_count != 1
            or job.knowledge_capture_status != "captured"
            or job.document_id is None
        ):
            raise RuntimeError("Journey generation did not complete in one deterministic request")
        content_revision = await session.scalar(select(SubjectDocumentContentRevision))
        index_revision = await session.scalar(select(SubjectDocumentIndexRevision))
        index_job = await session.scalar(select(SubjectDocumentIndexJob))
        if (
            content_revision.status != "ready"
            or not content_revision.is_active
            or content_revision.reviewed_at is None
            or content_revision.published_at is None
            or index_revision.status != "ready"
            or not index_revision.is_active
            or index_job.status != "completed"
        ):
            raise RuntimeError("Journey independently published Knowledge state is invalid")
        cards = list((await session.scalars(select(Flashcard))).all())
        if not all(card.is_approved and card.source_page == 1 for card in cards):
            raise RuntimeError("Journey review/source provenance did not persist")
        progress = list((await session.scalars(select(StudyProgress))).all())
        if not all(row.correct_count == 1 and row.incorrect_count == 0 for row in progress):
            raise RuntimeError("Journey answers did not persist exactly once")
        delivered = await session.scalar(select(func.count()).select_from(EmailOutboxMessage).where(EmailOutboxMessage.status == "sent"))
        if delivered != 1:
            raise RuntimeError("Journey invitation was not delivered through the email worker")
        answer_job = await session.scalar(select(RagAnswerJob))
        answer = await session.scalar(select(RagMessage).where(RagMessage.role == "assistant"))
        if answer_job.status != "completed" or answer is None or answer.outcome != "answer" or answer.source_count != 1:
            raise RuntimeError("Journey grounded Ask AI answer did not persist atomically")
    print("Journey database proof passed: generation, independent Knowledge index/review/publication, enrollment, grounded Ask AI citation, email, cards and progress.")


async def verify_rag_disabled_records() -> None:
    expected_counts = {
        User: 1,
        Subject: 1,
        FlashcardSet: 1,
        Flashcard: 2,
        Enrollment: 0,
        StudyProgress: 0,
        StudyAnswerSubmission: 0,
        GenerationJob: 1,
        GenerationJobSource: 0,
        KnowledgeUploadQuotaEvent: 0,
        KnowledgeStorageUsage: 0,
        RagEmbeddingSpace: 0,
        SubjectDocument: 0,
        SubjectDocumentContentRevision: 0,
        SubjectDocumentPage: 0,
        SubjectDocumentIndexRevision: 0,
        SubjectDocumentChunk: 0,
        SubjectDocumentIndexJob: 0,
        RagThread: 0,
        RagMessage: 0,
        RagAnswerJob: 0,
        RagAnswerQuotaEvent: 0,
        RagMessageSource: 0,
        EmailOutboxMessage: 0,
    }
    async with async_session_maker() as session:
        for model, count in expected_counts.items():
            if await session.scalar(select(func.count()).select_from(model)) != count:
                raise RuntimeError(
                    f"RAG-disabled journey persistence check failed for {model.__tablename__}"
                )
        job = await session.scalar(select(GenerationJob))
        if (
            job is None
            or job.status != "completed"
            or job.provider_request_count != 1
            or job.knowledge_capture_status != "not_requested"
            or job.document_id is not None
        ):
            raise RuntimeError(
                "RAG-disabled journey did not remain an ordinary flashcard generation"
            )
        cards = list((await session.scalars(select(Flashcard))).all())
        if not all(card.is_approved and card.source_page == 1 for card in cards):
            raise RuntimeError("RAG-disabled journey card review did not persist")
    print(
        "RAG-disabled journey database proof passed: ordinary flashcards completed, "
        "source removed, and Knowledge/index/answer/provider records remained absent."
    )


async def diagnose_records() -> None:
    """Print only bounded lifecycle fields after a failed disposable journey."""

    async with async_session_maker() as session:
        answer_jobs = list((await session.scalars(select(RagAnswerJob))).all())
        contents = list((await session.scalars(select(SubjectDocumentContentRevision))).all())
        indexes = list((await session.scalars(select(SubjectDocumentIndexRevision))).all())
        print(json.dumps({
            "journey_state": {
                "rag_thread_count": int(await session.scalar(select(func.count()).select_from(RagThread)) or 0),
                "rag_message_count": int(await session.scalar(select(func.count()).select_from(RagMessage)) or 0),
                "answer_jobs": [{
                    "status": job.status,
                    "error_code": job.error_code,
                    "provider_request_count": job.provider_request_count,
                    "support_rejection_count": job.support_rejection_count,
                    "actual_input_tokens": job.actual_input_tokens,
                    "actual_output_tokens": job.actual_output_tokens,
                    "usage_estimated": job.usage_estimated,
                } for job in answer_jobs[:5]],
                "knowledge_content_states": [item.status for item in contents[:5]],
                "knowledge_index_states": [item.status for item in indexes[:5]],
            }
        }, ensure_ascii=True))


async def main(action: str) -> None:
    await require_disposable_database()
    try:
        if action == "seed":
            await seed_instructor()
        elif action == "verify":
            await verify_records()
        elif action == "diagnose":
            await diagnose_records()
        elif action == "worker":
            import app.workers.generation as generation
            from app.worker import run_worker

            generation.create_flashcard_graph = lambda **arguments: JourneyGraph(**arguments)
            await run_worker()
        elif action == "index-worker":
            from app.workers.knowledge_index import KnowledgeIndexWorker

            await KnowledgeIndexWorker(
                provider=JourneyEmbeddingProvider(), worker_id="journey-index-worker"
            ).run(asyncio.Event())
        else:
            from app.workers.rag_answer import RagAnswerWorker

            await RagAnswerWorker(
                answer_provider=JourneyAnswerProvider(),
                embedding_provider=JourneyEmbeddingProvider(),
                worker_id="journey-answer-worker",
            ).run(asyncio.Event())
    finally:
        await close_database()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["seed", "worker", "index-worker", "answer-worker", "verify", "diagnose"]
    )
    asyncio.run(main(parser.parse_args().action))
