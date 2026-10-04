"""PostgreSQL proofs for durable repeat-upload decisions and accounting."""

import asyncio
import hashlib
import os
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.models.generation import (
    GenerationJob,
    GenerationJobSource,
    KnowledgeUploadQuotaEvent,
)
from app.models.knowledge import (
    SubjectDocumentContentRevision,
    SubjectDocumentIndexJob,
    SubjectDocumentIndexRevision,
    embedding_space_hash,
)
from app.schemas.generation import KnowledgeJobCreate
from app.services.generation import GenerationJobService


pytestmark = pytest.mark.postgres

PDF = b"%PDF-1.7\npostgres duplicate choice fixture"
CONTENT = "Synthetic duplicate upload evidence."


def choice_settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url=os.getenv(
            "POSTGRES_TEST_DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost/test",
        ),
        secret_key="test-only-secret-key-with-adequate-entropy-1234567890",
        generation_source_encryption_key=(
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        ),
        flashcard_ai_provider_enabled=True,
        generation_max_active_jobs_per_user=10,
        generation_max_active_jobs_deployment=20,
        rag_enabled=True,
        rag_embedding_provider_enabled=True,
        rag_embedding_provider="gemini",
        rag_embedding_model="gemini-embedding-001",
        rag_embedding_api_key="test-key",
        rag_embedding_quota_bucket="test-bucket",
    )


async def seed_ready_document(connection, *, published: bool = False) -> dict:
    settings = choice_settings()
    identity = settings.rag_embedding_space_identity
    values = dict(
        zip(
            (
                "provider",
                "base_url",
                "model",
                "space_revision",
                "format_version",
                "dimensions",
                "representation",
                "metric",
                "document_task_mode",
                "query_task_mode",
            ),
            identity,
        )
    )
    values.update(
        owner=uuid4(),
        subject=uuid4(),
        document=uuid4(),
        content_revision=uuid4(),
        index_revision=uuid4(),
        chunk=uuid4(),
        email=f"duplicate-{uuid4().hex}@example.test",
        source_sha=hashlib.sha256(PDF).hexdigest(),
        space_hash=embedding_space_hash(identity),
        content=CONTENT,
        chars=len(CONTENT),
        bytes=len(CONTENT.encode()),
        charged=len(CONTENT.encode()) + 6408,
    )
    await connection.execute(
        text(
            "INSERT INTO users(id,email,hashed_password,role) "
            "VALUES(:owner,:email,'fixture','INSTRUCTOR')"
        ),
        values,
    )
    await connection.execute(
        text(
            "INSERT INTO subjects(id,name,instructor_id) "
            "VALUES(:subject,'Duplicate fixture',:owner)"
        ),
        values,
    )
    await connection.execute(
        text(
            """
            INSERT INTO rag_embedding_spaces(
                identity_hash,provider,base_url,model,space_revision,
                format_version,dimensions,representation,metric,
                document_task_mode,query_task_mode
            ) VALUES(
                :space_hash,:provider,:base_url,:model,:space_revision,
                :format_version,:dimensions,:representation,:metric,
                :document_task_mode,:query_task_mode
            ) ON CONFLICT (identity_hash) DO NOTHING
            """
        ),
        values,
    )
    await connection.execute(
        text(
            """
            INSERT INTO subject_documents(
                id,subject_id,uploader_id,title,source_pdf_name,source_sha256
            ) VALUES(
                :document,:subject,:owner,'Fixture','fixture.pdf',:source_sha
            )
            """
        ),
        values,
    )
    await connection.execute(
        text(
            """
            INSERT INTO subject_document_content_revisions(
                id,document_id,subject_id,uploader_id,revision_no,
                source_sha256,extraction_version,reserved_page_count,
                reserved_page_chars,reserved_page_bytes
            ) VALUES(
                :content_revision,:document,:subject,:owner,1,
                :source_sha,'canonical_v1',2,:chars,:bytes
            )
            """
        ),
        values,
    )
    await connection.execute(
        text(
            """
            INSERT INTO subject_document_pages(
                content_revision_id,document_id,subject_id,uploader_id,
                page_number,content
            ) VALUES
                (:content_revision,:document,:subject,:owner,1,:content),
                (:content_revision,:document,:subject,:owner,2,'')
            """
        ),
        values,
    )
    await connection.execute(
        text(
            "UPDATE subject_document_content_revisions "
            "SET status='pending_index' WHERE id=:content_revision"
        ),
        values,
    )
    await connection.execute(
        text(
            """
            INSERT INTO subject_document_index_revisions(
                id,content_revision_id,document_id,subject_id,uploader_id,
                revision_no,chunker_version,embedding_provider,
                embedding_base_url,embedding_model,embedding_space_revision,
                embedding_format_version,embedding_dimensions,
                embedding_representation,embedding_metric,document_task_mode,
                query_task_mode,embedding_space_hash,reserved_chunk_count,
                reserved_index_bytes
            ) VALUES(
                :index_revision,:content_revision,:document,:subject,:owner,
                1,'bounded_v1',:provider,:base_url,:model,:space_revision,
                :format_version,:dimensions,:representation,:metric,
                :document_task_mode,:query_task_mode,:space_hash,1,:charged
            )
            """
        ),
        values,
    )
    await connection.execute(
        text(
            """
            INSERT INTO subject_document_chunks(
                id,index_revision_id,content_revision_id,document_id,
                subject_id,uploader_id,chunk_index,local_chunk_id,page_number,
                content,token_count,embedding_space_hash,embedding
            ) VALUES(
                :chunk,:index_revision,:content_revision,:document,
                :subject,:owner,0,'chunk-0001-p1',1,:content,8,:space_hash,
                array_prepend(1::real,array_fill(0::real,ARRAY[1535]))::vector
            )
            """
        ),
        values,
    )
    await connection.execute(
        text(
            "UPDATE subject_document_index_revisions "
            "SET status='ready',is_active=true WHERE id=:index_revision"
        ),
        values,
    )
    await connection.execute(
        text(
            "UPDATE subject_document_content_revisions "
            "SET status='ready',is_active=true WHERE id=:content_revision"
        ),
        values,
    )
    if published:
        await connection.execute(
            text(
                "UPDATE subject_document_content_revisions "
                "SET reviewed_at=now(),reviewed_by_id=:owner,published_at=now() "
                "WHERE id=:content_revision"
            ),
            values,
        )
    await connection.execute(
        text(
            "UPDATE subjects SET active_embedding_space_hash=:space_hash "
            "WHERE id=:subject"
        ),
        values,
    )
    return values


async def reserve_duplicate(session_factory, values: dict) -> tuple[GenerationJobService, object]:
    service = GenerationJobService(choice_settings())
    async with session_factory() as db:
        async with db.begin():
            job = await service.create_knowledge_reservation(
                db,
                user_id=values["owner"],
                data=KnowledgeJobCreate(
                    subject_id=values["subject"],
                    title="Repeated upload",
                    source_pdf_name="repeated.pdf",
                ),
                idempotency_key=f"duplicate-{uuid4().hex}",
            )
            await service.attach_source(
                db,
                job_id=job.id,
                user_id=values["owner"],
                media_type="application/pdf",
                content=PDF,
            )
            assert job.status == "awaiting_choice"
            return service, job.id


async def remove_owners(postgres_session_factory, *owner_ids) -> None:
    async with postgres_session_factory() as db:
        async with db.begin():
            await db.execute(
                text("DELETE FROM users WHERE id=ANY(CAST(:owners AS uuid[]))"),
                {"owners": list(owner_ids)},
            )


@pytest_asyncio.fixture
async def owner_cleanup(postgres_session_factory):
    owner_ids = []
    yield owner_ids
    if owner_ids:
        await remove_owners(postgres_session_factory, *owner_ids)


async def test_concurrent_opposite_choices_commit_exactly_one_decision(
    postgres_engine, postgres_session_factory, owner_cleanup
):
    async with postgres_engine.begin() as connection:
        values = await seed_ready_document(connection)
    owner_cleanup.append(values["owner"])
    service, job_id = await reserve_duplicate(postgres_session_factory, values)

    async def choose(choice: str):
        try:
            async with postgres_session_factory() as db:
                async with db.begin():
                    await db.execute(text("SET LOCAL lock_timeout='5s'"))
                    await service.submit_knowledge_choice(
                        db,
                        job_id=job_id,
                        user_id=values["owner"],
                        choice=choice,
                        idempotency_key=f"choice-{choice}-{uuid4().hex}",
                    )
            return "selected", choice
        except HTTPException as exc:
            return exc.detail["code"], choice

    results = await asyncio.gather(choose("reuse"), choose("separate_copy"))
    assert sorted(result[0] for result in results) == [
        "knowledge_choice_conflict",
        "selected",
    ]
    winner = next(choice for result, choice in results if result == "selected")

    async with postgres_session_factory() as db:
        job = await db.get(GenerationJob, job_id)
        assert job.knowledge_choice == winner
        assert job.knowledge_upload_outcome == {
            "reuse": "reused",
            "separate_copy": "separate_copy",
        }[winner]
        assert job.knowledge_choice_key_hash is not None
        assert len(job.knowledge_choice_key_hash) == 64
        assert await db.scalar(
            select(func.count(KnowledgeUploadQuotaEvent.id)).where(
                KnowledgeUploadQuotaEvent.job_id == job_id
            )
        ) == 1
        source = await db.get(GenerationJobSource, job_id)
        if winner == "reuse":
            assert job.status == "completed"
            assert job.knowledge_capture_status == "reused"
            assert job.document_id == values["document"]
            assert job.knowledge_content_revision_id == values["content_revision"]
            assert source is None
        else:
            assert job.status == "queued"
            assert job.knowledge_capture_status == "pending"
            assert job.document_id is None
            assert source is not None


async def test_candidate_scope_fk_and_owner_lookup_reject_cross_owner_subject(
    postgres_engine, postgres_session_factory, owner_cleanup
):
    async with postgres_engine.begin() as connection:
        values = await seed_ready_document(connection)
        other = await seed_ready_document(connection)
    owner_cleanup.extend((values["owner"], other["owner"]))
    service, job_id = await reserve_duplicate(postgres_session_factory, values)

    async with postgres_session_factory() as db:
        with pytest.raises(IntegrityError) as mismatch:
            async with db.begin():
                await db.execute(
                    update(GenerationJob)
                    .where(GenerationJob.id == job_id)
                    .values(knowledge_choice_candidate_id=other["document"])
                )
                await db.execute(
                    text(
                        "SET CONSTRAINTS "
                        "fk_generation_jobs_choice_candidate_scope IMMEDIATE"
                    )
                )
        assert mismatch.value.orig.sqlstate == "23503"

    async with postgres_session_factory() as db:
        async with db.begin():
            with pytest.raises(HTTPException) as hidden:
                await service.submit_knowledge_choice(
                    db,
                    job_id=job_id,
                    user_id=other["owner"],
                    choice="reuse",
                    idempotency_key="cross-owner-choice",
                )
            assert hidden.value.status_code == 404
            job = await db.get(GenerationJob, job_id)
            assert job.knowledge_choice_candidate_id == values["document"]


@pytest.mark.parametrize("published", [False, True], ids=["private", "published"])
async def test_explicit_unchanged_revision_charges_only_raw_upload_bytes(
    postgres_engine, postgres_session_factory, owner_cleanup, published
):
    async with postgres_engine.begin() as connection:
        values = await seed_ready_document(connection, published=published)
        before_usage = (
            await connection.execute(
                text(
                    "SELECT scope_type,scope_id,document_count,charged_bytes "
                    "FROM knowledge_storage_usage "
                    "WHERE scope_id IN (:subject,:owner) OR scope_type='global' "
                    "ORDER BY scope_type,scope_id"
                ),
                values,
            )
        ).all()
    owner_cleanup.append(values["owner"])

    service = GenerationJobService(choice_settings())
    async with postgres_session_factory() as db:
        async with db.begin():
            job = await service.create_knowledge_reservation(
                db,
                user_id=values["owner"],
                data=KnowledgeJobCreate(
                    subject_id=values["subject"],
                    document_id=values["document"],
                    title="Unchanged revision",
                    source_pdf_name="unchanged.pdf",
                ),
                idempotency_key=f"unchanged-{uuid4().hex}",
            )
            await service.attach_source(
                db,
                job_id=job.id,
                user_id=values["owner"],
                media_type="application/pdf",
                content=PDF,
            )
            job_id = job.id

    async with postgres_session_factory() as db:
        job = await db.get(GenerationJob, job_id)
        after_usage = (
            await db.execute(
                text(
                    "SELECT scope_type,scope_id,document_count,charged_bytes "
                    "FROM knowledge_storage_usage "
                    "WHERE scope_id IN (:subject,:owner) OR scope_type='global' "
                    "ORDER BY scope_type,scope_id"
                ),
                values,
            )
        ).all()
        assert after_usage == before_usage
        assert job.status == "completed"
        assert job.knowledge_capture_status == "unchanged"
        assert job.knowledge_upload_outcome == "no_changes"
        assert job.document_id == values["document"]
        assert job.knowledge_content_revision_id == values["content_revision"]
        assert job.provider_request_count == 0
        assert await db.get(GenerationJobSource, job_id) is None
        assert await db.scalar(
            select(func.sum(KnowledgeUploadQuotaEvent.upload_bytes)).where(
                KnowledgeUploadQuotaEvent.job_id == job_id
            )
        ) == len(PDF)
        assert await db.scalar(
            select(func.count(SubjectDocumentContentRevision.id)).where(
                SubjectDocumentContentRevision.document_id == values["document"]
            )
        ) == 1
        assert await db.scalar(
            select(func.count(SubjectDocumentIndexRevision.id)).where(
                SubjectDocumentIndexRevision.document_id == values["document"]
            )
        ) == 1
        assert await db.scalar(
            select(func.count(SubjectDocumentIndexJob.id)).where(
                SubjectDocumentIndexJob.document_id == values["document"]
            )
        ) == 0
