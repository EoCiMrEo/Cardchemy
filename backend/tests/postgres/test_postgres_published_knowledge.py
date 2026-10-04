"""Student browsing must never cross enrollment/publication/space boundaries."""

import hashlib
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.knowledge import SubjectDocumentContentRevision
from app.routers.published_knowledge import (
    get_published_page, get_published_pdf, get_published_pdf_metadata, list_published_documents,
    search_published_pages,
)
from app.services.knowledge_pdf import archive_pdf
from tests.postgres.test_postgres_knowledge_schema import knowledge_connection, make_owner, make_ready, make_space


pytestmark = pytest.mark.postgres


async def _student(connection, subject_id, *, enrolled: bool):
    student_id = uuid4()
    await connection.execute(text("""INSERT INTO users(id,email,hashed_password,role)
        VALUES(:id,:email,'fixture','STUDENT')"""),
        {"id": student_id, "email": f"published-{student_id}@example.test"})
    if enrolled:
        await connection.execute(text("INSERT INTO enrollments(student_id,subject_id) VALUES(:id,:subject)"),
                                 {"id": student_id, "subject": subject_id})
    return SimpleNamespace(id=student_id)


async def test_student_catalog_search_page_and_original_require_current_published_scope(knowledge_connection):
    connection = knowledge_connection
    values = await make_ready(connection, await make_owner(connection))
    student = await _student(connection, values["subject"], enrolled=True)
    outsider = await _student(connection, values["subject"], enrolled=False)
    async with AsyncSession(bind=connection, expire_on_commit=False) as db:
        for principal in (student, outsider):
            assert (await list_published_documents(values["subject"], principal, db)).documents == []
        await connection.execute(text("""UPDATE subject_document_content_revisions
            SET reviewed_at=now(),reviewed_by_id=:owner,published_at=now() WHERE id=:content_revision"""), values)

        catalog = await list_published_documents(values["subject"], student, db)
        assert len(catalog.documents) == 1
        assert catalog.documents[0].id == values["document"]
        assert catalog.documents[0].page_count == 2
        assert catalog.documents[0].has_original_pdf is False
        assert (await list_published_documents(values["subject"], outsider, db)).documents == []

        results = await search_published_pages(values["subject"], "teaching evidence", student, db)
        assert [(page.document_id, page.page_number) for page in results.pages] == [(values["document"], 1)]
        assert (await search_published_pages(values["subject"], "teaching evidence", outsider, db)).pages == []
        page = await get_published_page(values["subject"], values["document"], 1, student, db)
        assert page.page_content == "Synthetic teaching evidence." and not page.truncated
        for principal, subject_id, document_id in (
            (outsider, values["subject"], values["document"]),
            (student, uuid4(), values["document"]),
            (student, values["subject"], uuid4()),
        ):
            with pytest.raises(HTTPException) as denied:
                await get_published_page(subject_id, document_id, 1, principal, db)
            assert denied.value.status_code == 404
        with pytest.raises(HTTPException) as missing_pdf:
            await get_published_pdf_metadata(values["subject"], values["document"], student, db)
        assert missing_pdf.value.status_code == 404

        await connection.execute(text("UPDATE subject_document_content_revisions SET published_at=NULL WHERE id=:content_revision"), values)
        assert (await list_published_documents(values["subject"], student, db)).documents == []
        with pytest.raises(HTTPException) as unpublished:
            await get_published_page(values["subject"], values["document"], 1, student, db)
        assert unpublished.value.status_code == 404

        await connection.execute(text("UPDATE subject_document_content_revisions SET published_at=now() WHERE id=:content_revision"), values)
        other_space = await make_space(connection, (*(
            'openai_compatible', 'https://api.openai.com/v1', 'text-embedding-3-small',
        ), 'published-browse-v2', 'raw_text_v1', 1536, 'float32', 'cosine', 'shared_input', 'shared_input'))
        await connection.execute(text("UPDATE subjects SET active_embedding_space_hash=:space_hash WHERE id=:subject"),
                                 {**values, "space_hash": other_space["space_hash"]})
        assert (await list_published_documents(values["subject"], student, db)).documents == []
        assert (await search_published_pages(values["subject"], "teaching", student, db)).pages == []


async def test_original_pdf_ranges_recheck_publication_and_enrollment(knowledge_connection):
    connection = knowledge_connection
    data = b"%PDF-1.7\nsynthetic disposable original"
    values = await make_ready(
        connection, await make_owner(connection), source_sha256=hashlib.sha256(data).hexdigest(),
    )
    student = await _student(connection, values["subject"], enrolled=True)
    outsider = await _student(connection, values["subject"], enrolled=False)
    await connection.execute(text("""UPDATE subject_document_content_revisions
        SET reviewed_at=now(),reviewed_by_id=:owner,published_at=now() WHERE id=:content_revision"""), values)
    async with AsyncSession(bind=connection, expire_on_commit=False) as db:
        revision = await db.get(SubjectDocumentContentRevision, values["content_revision"])
        await archive_pdf(db, settings=get_settings(), revision=revision, data=data)
        catalog = await list_published_documents(values["subject"], student, db)
        assert catalog.documents[0].has_original_pdf
        metadata = await get_published_pdf_metadata(values["subject"], values["document"], student, db)
        assert metadata.headers["content-length"] == str(len(data))
        assert metadata.headers["accept-ranges"] == "bytes"
        response = await get_published_pdf(
            values["subject"], values["document"], "bytes=0-7", student, db,
        )
        assert response.status_code == 206 and response.body == data[:8]
        assert response.headers["content-range"] == f"bytes 0-7/{len(data)}"
        for principal in (outsider,):
            with pytest.raises(HTTPException) as denied:
                await get_published_pdf(values["subject"], values["document"], "bytes=0-7", principal, db)
            assert denied.value.status_code == 404
        with pytest.raises(HTTPException) as no_range:
            await get_published_pdf(values["subject"], values["document"], None, student, db)
        assert no_range.value.status_code == 400
        with pytest.raises(HTTPException) as invalid_range:
            await get_published_pdf(values["subject"], values["document"], "bytes=999-", student, db)
        assert invalid_range.value.status_code == 416
        assert invalid_range.value.headers["Content-Range"] == f"bytes */{len(data)}"

        await connection.execute(text("DELETE FROM enrollments WHERE student_id=:student AND subject_id=:subject"),
                                 {"student": student.id, "subject": values["subject"]})
        with pytest.raises(HTTPException) as revoked:
            await get_published_pdf(values["subject"], values["document"], "bytes=0-7", student, db)
        assert revoked.value.status_code == 404
        await connection.execute(text("INSERT INTO enrollments(student_id,subject_id) VALUES(:student,:subject)"),
                                 {"student": student.id, "subject": values["subject"]})
        await connection.execute(text("UPDATE subject_document_content_revisions SET published_at=NULL WHERE id=:content_revision"), values)
        with pytest.raises(HTTPException) as unpublished:
            await get_published_pdf_metadata(values["subject"], values["document"], student, db)
        assert unpublished.value.status_code == 404
