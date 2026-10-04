"""Disposable PostgreSQL proof for encrypted card choice and race fencing."""

import asyncio

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, func, select, text

from app.models.flashcard import Flashcard
from app.models.generation import GenerationCandidateStage, GenerationJob, GenerationJobSource
from app.models.knowledge import SubjectDocument, SubjectDocumentContentRevision
from app.models.subject import FlashcardSet, Subject
from app.models.user import User
from app.services.generation import GenerationJobService
from app.services.knowledge_lock import acquire_knowledge_write_lock
from app.services.knowledge_management import KnowledgeManagementService
from app.services.subject import SubjectService
from app.time_utils import utcnow
from scripts.evaluate_private_generation import (
    EvaluationRefused, load_authorized_pages, select_latest_failed_source,
)
from tests.postgres.test_postgres_knowledge_schema import make_ready
from tests.test_generation_card_choice import pending_choice
from tests.test_generation_jobs import make_settings


pytestmark = pytest.mark.postgres


@pytest_asyncio.fixture
async def cleanup_choice_owners(postgres_session_factory):
    """Leave shared disposable Knowledge usage at its original baseline."""

    owners = []
    yield owners.append
    if owners:
        async with postgres_session_factory() as db:
            async with db.begin():
                await db.execute(delete(User).where(User.id.in_(owners)))


async def test_postgres_card_choice_schema_and_concurrent_confirm(postgres_session_factory, cleanup_choice_owners):
    settings = make_settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        generation_max_active_jobs_per_user=1,
    )
    owner_id, _subject_id, job_id, service, _worker = await pending_choice(
        postgres_session_factory, settings=settings,
    )
    cleanup_choice_owners(owner_id)
    async with postgres_session_factory() as db:
        indexes = set((await db.scalars(text(
            "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"
        ))).all())
        assert "ix_generation_candidate_stage_expires_at" in indexes
        assert "ix_generation_jobs_card_choice_expiry" in indexes

    async def confirm(key: str):
        async with postgres_session_factory() as db:
            try:
                async with db.begin():
                    await service.submit_card_choice(
                        db, job_id=job_id, user_id=owner_id,
                        card_count=1, idempotency_key=key,
                    )
                return "completed"
            except HTTPException as exc:
                return exc.status_code

    results = await asyncio.gather(confirm("choice-pg-first-abc"), confirm("choice-pg-second-abc"))
    assert sorted(results, key=str) == [409, "completed"]
    async with postgres_session_factory() as db:
        job = await db.get(GenerationJob, job_id)
        assert job.status == "completed"
        assert job.generated_card_count == job.selected_card_count == 1
        assert job.requested_card_count == 3
        assert await db.get(GenerationCandidateStage, job_id) is None
        assert await db.get(GenerationJobSource, job_id) is None
        assert await db.scalar(select(func.count(FlashcardSet.id)).where(
            FlashcardSet.generation_job_id == job_id
        )) == 1
        assert await db.scalar(select(func.count(Flashcard.id)).join(FlashcardSet).where(
            FlashcardSet.generation_job_id == job_id
        )) == 1


@pytest.mark.parametrize("delete_scope", ["subject", "knowledge"])
async def test_postgres_card_choice_serializes_with_parent_deletion(
    postgres_session_factory, cleanup_choice_owners, delete_scope,
):
    settings = make_settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        generation_max_active_jobs_per_user=1,
    )
    owner_id, subject_id, job_id, service, _worker = await pending_choice(
        postgres_session_factory, settings=settings,
    )
    cleanup_choice_owners(owner_id)
    document_id = None
    if delete_scope == "knowledge":
        async with postgres_session_factory() as db:
            async with db.begin():
                values = await make_ready(
                    await db.connection(), {"owner": owner_id, "subject": subject_id}
                )
                document_id = values["document"]
                job = await db.get(GenerationJob, job_id)
                job.document_id = document_id
                job.knowledge_content_revision_id = values["content_revision"]
                job.knowledge_capture_status = "captured"

    job_locked = asyncio.Event()
    release_choice = asyncio.Event()
    deletion_started = asyncio.Event()
    original_get_owner_job = service.get_owner_job

    async def pause_after_job_lock(db, target_job_id, target_user_id, *, for_update=False):
        job = await original_get_owner_job(
            db, target_job_id, target_user_id, for_update=for_update,
        )
        if for_update and target_job_id == job_id:
            job_locked.set()
            await release_choice.wait()
        return job

    service.get_owner_job = pause_after_job_lock

    async def confirm():
        async with postgres_session_factory() as db:
            async with db.begin():
                return await service.submit_card_choice(
                    db, job_id=job_id, user_id=owner_id, card_count=1,
                    idempotency_key=f"choice-delete-{delete_scope}-abc123",
                )

    async def delete_parent():
        await job_locked.wait()
        async with postgres_session_factory() as db:
            async with db.begin():
                deletion_started.set()
                if delete_scope == "subject":
                    subject = await db.get(Subject, subject_id)
                    await SubjectService.delete_subject(db, subject)
                else:
                    user = await db.get(User, owner_id)
                    await KnowledgeManagementService(settings).remove(
                        db, subject_id=subject_id, document_id=document_id, user=user,
                    )

    confirming = asyncio.create_task(confirm())
    deleting = asyncio.create_task(delete_parent())
    try:
        await asyncio.wait_for(deletion_started.wait(), timeout=10)
        await asyncio.sleep(0.05)
        assert not deleting.done()
    finally:
        release_choice.set()
    chosen, _ = await asyncio.wait_for(asyncio.gather(confirming, deleting), timeout=10)
    assert chosen.status == "completed"
    async with postgres_session_factory() as db:
        if delete_scope == "subject":
            assert await db.get(Subject, subject_id) is None
        else:
            assert await db.get(SubjectDocument, document_id) is None
            assert await db.scalar(select(func.count(FlashcardSet.id)).where(
                FlashcardSet.generation_job_id == job_id,
            )) == 1


async def test_postgres_published_knowledge_survives_card_choice_cancel(postgres_session_factory, cleanup_choice_owners):
    settings = make_settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        generation_max_active_jobs_per_user=1,
    )
    owner_id, subject_id, job_id, service, _worker = await pending_choice(
        postgres_session_factory, settings=settings,
    )
    cleanup_choice_owners(owner_id)
    async with postgres_session_factory() as db:
        async with db.begin():
            values = await make_ready(
                await db.connection(), {"owner": owner_id, "subject": subject_id}
            )
            doc_id = values["document"]
            revision_id = values["content_revision"]
            job = await db.get(GenerationJob, job_id)
            job.document_id = doc_id
            job.knowledge_content_revision_id = revision_id
            job.knowledge_created_document = True
            job.knowledge_capture_status = "captured"

    acquired = asyncio.Event()
    release = asyncio.Event()

    async def publish_first():
        async with postgres_session_factory() as db:
            async with db.begin():
                await acquire_knowledge_write_lock(db)
                revision = await db.scalar(select(SubjectDocumentContentRevision).where(
                    SubjectDocumentContentRevision.id == revision_id,
                ).with_for_update())
                revision.reviewed_by_id = owner_id
                revision.reviewed_at = utcnow()
                revision.published_at = utcnow()
                acquired.set()
                await release.wait()

    async def cancel_second():
        await acquired.wait()
        async with postgres_session_factory() as db:
            async with db.begin():
                await service.cancel(db, job_id=job_id, user_id=owner_id)

    publishing = asyncio.create_task(publish_first())
    cancelling = asyncio.create_task(cancel_second())
    await acquired.wait()
    release.set()
    await asyncio.gather(publishing, cancelling)
    async with postgres_session_factory() as db:
        job = await db.get(GenerationJob, job_id)
        assert job.status == "cancelled"
        assert job.knowledge_capture_status == "captured"
        assert await db.get(SubjectDocument, doc_id) is not None
        revision = await db.get(SubjectDocumentContentRevision, revision_id)
        assert revision is not None and revision.published_at is not None
        assert await db.get(GenerationCandidateStage, job_id) is None
        assert await db.get(GenerationJobSource, job_id) is None


async def test_private_generation_eval_reads_only_current_published_owner_pages(postgres_session_factory, cleanup_choice_owners):
    settings = make_settings(database_url="postgresql+asyncpg://test:test@localhost/test")
    owner_id, subject_id, _job_id, _service, _worker = await pending_choice(
        postgres_session_factory, settings=settings,
    )
    cleanup_choice_owners(owner_id)
    async with postgres_session_factory() as db:
        async with db.begin():
            values = await make_ready(
                await db.connection(), {"owner": owner_id, "subject": subject_id}
            )
        with pytest.raises(EvaluationRefused):
            await load_authorized_pages(
                db, owner_id=owner_id, subject_id=subject_id,
                document_id=values["document"], settings=settings,
            )
        await db.rollback()
        async with db.begin():
            await db.execute(text(
                "UPDATE subject_document_content_revisions "
                "SET reviewed_at=now(),reviewed_by_id=:owner,published_at=now() "
                "WHERE id=:revision"
            ), {"owner": owner_id, "revision": values["content_revision"]})
        async with db.begin():
            await db.execute(text("SET TRANSACTION READ ONLY"))
            source = await load_authorized_pages(
                db, owner_id=owner_id, subject_id=subject_id,
                document_id=values["document"], settings=settings,
            )
            assert len(source.document.pages) == 2
            with pytest.raises(EvaluationRefused):
                await load_authorized_pages(
                    db, owner_id=values["document"], subject_id=subject_id,
                    document_id=values["document"], settings=settings,
                )
        async with db.begin():
            await db.execute(text(
                "UPDATE subjects SET active_embedding_space_hash=NULL WHERE id=:subject"
            ), {"subject": subject_id})
        with pytest.raises(EvaluationRefused):
            await load_authorized_pages(
                db, owner_id=owner_id, subject_id=subject_id,
                document_id=values["document"], settings=settings,
            )


async def test_private_generation_latest_failed_selector_is_unique_and_read_only(postgres_session_factory, cleanup_choice_owners):
    settings = make_settings(database_url="postgresql+asyncpg://test:test@localhost/test")
    owner_id, subject_id, job_id, _service, _worker = await pending_choice(
        postgres_session_factory, settings=settings, requested_count=20,
    )
    cleanup_choice_owners(owner_id)
    async with postgres_session_factory() as db:
        async with db.begin():
            values = await make_ready(
                await db.connection(), {"owner": owner_id, "subject": subject_id}
            )
            job = await db.get(GenerationJob, job_id)
            job.document_id = values["document"]
            job.knowledge_content_revision_id = values["content_revision"]
            job.knowledge_capture_status = "captured"
            job.source_sha256 = "a" * 64
            job.status = "failed"
            job.stage = "failed"
            job.progress = 100
            job.completed_at = utcnow()
            job.error_code = "insufficient_grounded_cards"
            job.error_message = "Fewer validated cards are available than requested."
            await db.execute(text(
                "UPDATE subject_document_content_revisions "
                "SET reviewed_at=now(),reviewed_by_id=:owner,published_at=now() "
                "WHERE id=:revision"
            ), {"owner": owner_id, "revision": values["content_revision"]})
        async with db.begin():
            await db.execute(text("SET TRANSACTION READ ONLY"))
            assert await select_latest_failed_source(db) == (
                owner_id, subject_id, values["document"], values["content_revision"],
            )
