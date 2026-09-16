"""Private deterministic worker and operator setup for the disposable browser journey.

This module is never imported by shipped application entry points. Only the
generated ``journey_test`` database on loopback may be modified.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os

from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url

from app.ai.contracts import CandidateBatch
from app.ai.pipeline import FlashcardGenerationPipeline
from app.ai.providers import ProviderResponse, ProviderUsage
from app.config import get_settings
from app.database import async_session_maker, close_database, engine, verify_database_revision
from app.models.email import EmailOutboxMessage
from app.models.flashcard import Enrollment, Flashcard, StudyAnswerSubmission, StudyProgress
from app.models.generation import GenerationJob, GenerationJobSource
from app.models.subject import FlashcardSet, Subject
from app.models.user import User


FACTS = (
    ("What color does chlorophyll give leaves?", "Green", "Chlorophyll gives leaves their Green color."),
    ("Which process lets plants convert light into energy?", "Photosynthesis", "Photosynthesis converts light into chemical energy."),
)


async def require_disposable_database() -> None:
    settings = get_settings()
    url = make_url(settings.database_url)
    if (
        os.getenv("RUN_JOURNEY_TESTS") != "1"
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


async def seed_instructor() -> None:
    from app import cli

    async with async_session_maker() as session:
        if await session.scalar(select(func.count(User.id))):
            raise RuntimeError("The journey requires a newly generated empty database")
    # Exercise the maintained operator creation path with generated test input.
    cli.getpass.getpass = lambda _: os.environ["JOURNEY_INSTRUCTOR_PASSWORD"]
    await cli.create_instructor(os.environ["JOURNEY_INSTRUCTOR_EMAIL"], "Journey Instructor", False)


async def verify_records() -> None:
    expected_counts = {User: 2, Subject: 1, FlashcardSet: 1, Flashcard: 2,
                       Enrollment: 1, StudyProgress: 2, StudyAnswerSubmission: 2,
                       GenerationJob: 1, GenerationJobSource: 0}
    async with async_session_maker() as session:
        for model, count in expected_counts.items():
            if await session.scalar(select(func.count()).select_from(model)) != count:
                raise RuntimeError(f"Journey persistence check failed for {model.__tablename__}")
        job = await session.scalar(select(GenerationJob))
        if job.status != "completed" or job.provider_request_count != 1:
            raise RuntimeError("Journey generation did not complete in one deterministic request")
        cards = list((await session.scalars(select(Flashcard))).all())
        if not all(card.is_approved and card.source_page == 1 for card in cards):
            raise RuntimeError("Journey review/source provenance did not persist")
        progress = list((await session.scalars(select(StudyProgress))).all())
        if not all(row.correct_count == 1 and row.incorrect_count == 0 for row in progress):
            raise RuntimeError("Journey answers did not persist exactly once")
        delivered = await session.scalar(select(func.count()).select_from(EmailOutboxMessage).where(EmailOutboxMessage.status == "sent"))
        if delivered != 1:
            raise RuntimeError("Journey invitation was not delivered through the email worker")
    print("Journey database proof passed: generation, review, publication, enrollment, email, answers and progress.")


async def main(action: str) -> None:
    await require_disposable_database()
    try:
        if action == "seed":
            await seed_instructor()
        elif action == "verify":
            await verify_records()
        else:
            import app.workers.generation as generation
            from app.worker import run_worker

            generation.create_flashcard_graph = lambda **arguments: JourneyGraph(**arguments)
            await run_worker()
    finally:
        await close_database()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["seed", "worker", "verify"])
    asyncio.run(main(parser.parse_args().action))
