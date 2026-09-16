"""PostgreSQL proofs for Phase 3 queue races, claims, and atomic completion."""

import asyncio
import os
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings
from app.models.flashcard import Flashcard
from app.models.generation import GenerationJob, GenerationJobSource
from app.models.subject import FlashcardSet, Subject
from app.models.user import User, UserRole
from app.schemas.generation import GenerationJobCreate
from app.services.generation import GenerationJobService
from app.workers.generation import GenerationWorker, LeaseLost


pytestmark = pytest.mark.postgres


@pytest_asyncio.fixture
async def phase3_pg_factory():
    database_url = os.getenv("POSTGRES_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("POSTGRES_TEST_DATABASE_URL is not configured")
    engine = create_async_engine(database_url, pool_size=8, max_overflow=0)
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != "20260916_0007":
            pytest.fail(f"PostgreSQL test database is at Alembic revision {revision!r}")
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


def phase3_settings(**overrides) -> Settings:
    values = {
        "environment": "test",
        "database_url": os.getenv(
            "POSTGRES_TEST_DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost/test",
        ),
        "secret_key": "test-only-secret-key-with-adequate-entropy-1234567890",
        "generation_source_encryption_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "ai_provider_enabled": True,
        "generation_max_active_jobs_per_user": 10,
        "generation_max_active_jobs_deployment": 10,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def seed_owner(factory) -> tuple:
    owner = User(
        email=f"phase3-{uuid4().hex}@example.test",
        hashed_password="not-a-real-password-hash",
        role=UserRole.INSTRUCTOR,
    )
    subject = Subject(name="Phase 3", instructor=owner)
    async with factory() as db:
        async with db.begin():
            db.add_all([owner, subject])
            await db.flush()
    return owner.id, subject.id


def metadata(subject_id, index: int) -> GenerationJobCreate:
    return GenerationJobCreate(
        subject_id=subject_id,
        set_title=f"Durable {index}",
        source_pdf_name=f"source-{index}.pdf",
        card_count=5,
    )


async def reserve_and_upload(factory, service, user_id, subject_id, index: int):
    async with factory() as db:
        async with db.begin():
            job = await service.create_reservation(
                db,
                user_id=user_id,
                data=metadata(subject_id, index),
                idempotency_key=f"phase3-operation-{index}-{uuid4().hex}",
            )
        async with db.begin():
            await service.attach_source(
                db,
                job_id=job.id,
                user_id=user_id,
                media_type="application/pdf",
                content=f"%PDF-1.7\njob-{index}".encode(),
            )
        return job.id


async def test_phase3_migration_installs_queue_and_retention_indexes(phase3_pg_factory):
    async with phase3_pg_factory() as db:
        indexes = set(
            (
                await db.scalars(
                    text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
                )
            ).all()
        )
        assert {
            "uq_generation_jobs_user_idempotency",
            "ix_generation_jobs_queue",
            "ix_generation_jobs_running_lease",
            "ix_generation_job_sources_expires_at",
            "uq_flashcard_sets_generation_job_id",
        } <= indexes
        payload_columns = set(
            (
                await db.scalars(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name='generation_jobs'"
                    )
                )
            ).all()
        )
        assert "source_payload" not in payload_columns


async def test_generation_cleanup_locks_only_jobs_across_nullable_source_join(
    phase3_pg_factory,
):
    """A clean PostgreSQL worker must not lock the nullable outer-join side."""

    worker = GenerationWorker(
        settings=phase3_settings(),
        session_factory=phase3_pg_factory,
        worker_id="phase8-cleanup-regression",
    )

    await worker.recover_and_cleanup()


async def test_concurrent_idempotent_reservations_create_one_row(phase3_pg_factory):
    user_id, subject_id = await seed_owner(phase3_pg_factory)
    service = GenerationJobService(phase3_settings())
    operation_key = f"concurrent-{uuid4().hex}"

    async def reserve():
        async with phase3_pg_factory() as db:
            async with db.begin():
                job = await service.create_reservation(
                    db,
                    user_id=user_id,
                    data=metadata(subject_id, 1),
                    idempotency_key=operation_key,
                )
                return job.id

    ids = await asyncio.gather(*(reserve() for _ in range(4)))
    assert len(set(ids)) == 1
    async with phase3_pg_factory() as db:
        assert await db.scalar(
            select(func.count(GenerationJob.id)).where(GenerationJob.user_id == user_id)
        ) == 1


async def test_workers_claim_distinct_jobs_and_completion_is_exactly_once(phase3_pg_factory):
    user_id, subject_id = await seed_owner(phase3_pg_factory)
    settings = phase3_settings()
    service = GenerationJobService(settings)
    first_id, second_id = await asyncio.gather(
        reserve_and_upload(phase3_pg_factory, service, user_id, subject_id, 1),
        reserve_and_upload(phase3_pg_factory, service, user_id, subject_id, 2),
    )
    worker_a = GenerationWorker(
        settings=settings, session_factory=phase3_pg_factory, worker_id="phase3-a"
    )
    worker_b = GenerationWorker(
        settings=settings, session_factory=phase3_pg_factory, worker_id="phase3-b"
    )
    first_claim, second_claim = await asyncio.gather(
        worker_a.claim_next(), worker_b.claim_next()
    )
    assert first_claim is not None and second_claim is not None
    assert {first_claim[0], second_claim[0]} == {first_id, second_id}

    completing_worker, completing_claim = (
        (worker_a, first_claim) if first_claim[0] == first_id else (worker_b, second_claim)
    )
    cards = [
        {
            "front_content": "PostgreSQL question",
            "back_content": "Correct",
            "options": ["Correct", "B", "C", "D"],
            "quality_score": 1.0,
        }
    ]
    await completing_worker._finish_success(
        completing_claim[0], completing_claim[1], cards
    )
    with pytest.raises(LeaseLost):
        await completing_worker._finish_success(
            completing_claim[0], completing_claim[1], cards
        )

    async with phase3_pg_factory() as db:
        assert await db.scalar(
            select(func.count(FlashcardSet.id)).where(
                FlashcardSet.generation_job_id == completing_claim[0]
            )
        ) == 1
        assert await db.scalar(
            select(func.count(Flashcard.id)).join(FlashcardSet).where(
                FlashcardSet.generation_job_id == completing_claim[0]
            )
        ) == 1
        assert await db.get(GenerationJobSource, completing_claim[0]) is None
