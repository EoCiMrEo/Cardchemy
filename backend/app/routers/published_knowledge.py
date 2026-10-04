"""Student browse/search and original-PDF reads without an Ask job."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, Query, Response
from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.flashcard import Enrollment
from app.models.knowledge import (
    SubjectDocument, SubjectDocumentContentRevision, SubjectDocumentIndexRevision,
    SubjectDocumentPage, SubjectDocumentPdf,
)
from app.models.subject import Subject
from app.models.user import User
from app.routers.auth import get_current_student
from app.schemas.published_knowledge import (
    PublishedKnowledgeDocument, PublishedKnowledgeList, PublishedKnowledgePage,
    PublishedKnowledgeSearch, PublishedKnowledgeSearchHit,
)
from app.services.knowledge_lock import acquire_knowledge_write_lock
from app.services.knowledge_management import knowledge_http_error
from app.services.knowledge_pdf import KnowledgePdfError, probe_pdf_archive, read_pdf_range
from app.services.knowledge_retrieval import bounded_lexical_query


router = APIRouter(prefix="/subjects/{subject_id}/published-knowledge", tags=["Published Knowledge"])


def _eligible_documents(subject_id: UUID, student_id: UUID):
    """Repeat enrollment/current-publication/space gates inside every SQL path."""
    return (
        select(
            SubjectDocument.id.label("document_id"),
            SubjectDocument.title.label("document_title"),
            SubjectDocumentContentRevision.id.label("content_revision_id"),
            SubjectDocumentContentRevision.actual_page_count.label("page_count"),
            SubjectDocumentContentRevision.source_sha256.label("source_sha256"),
        )
        .join(Subject, Subject.id == SubjectDocument.subject_id)
        .join(Enrollment, and_(Enrollment.subject_id == Subject.id, Enrollment.student_id == student_id))
        .join(SubjectDocumentContentRevision, and_(
            SubjectDocumentContentRevision.document_id == SubjectDocument.id,
            SubjectDocumentContentRevision.subject_id == subject_id,
            SubjectDocumentContentRevision.is_active.is_(True),
            SubjectDocumentContentRevision.status == "ready",
            SubjectDocumentContentRevision.published_at.is_not(None),
            SubjectDocumentContentRevision.reviewed_at.is_not(None),
            SubjectDocumentContentRevision.reviewed_by_id == SubjectDocument.uploader_id,
        ))
        .join(SubjectDocumentIndexRevision, and_(
            SubjectDocumentIndexRevision.content_revision_id == SubjectDocumentContentRevision.id,
            SubjectDocumentIndexRevision.subject_id == subject_id,
            SubjectDocumentIndexRevision.is_active.is_(True),
            SubjectDocumentIndexRevision.status == "ready",
            SubjectDocumentIndexRevision.embedding_space_hash == Subject.active_embedding_space_hash,
        ))
        .where(Subject.id == subject_id, Subject.instructor_id == SubjectDocument.uploader_id)
        .subquery()
    )


async def _document(db: AsyncSession, subject_id: UUID, document_id: UUID, user: User):
    await acquire_knowledge_write_lock(db)
    eligible = _eligible_documents(subject_id, user.id)
    row = (await db.execute(select(eligible).where(eligible.c.document_id == document_id))).mappings().one_or_none()
    if row is None:
        raise knowledge_http_error(404, "published_knowledge_unavailable", "Published Knowledge is unavailable.")
    return row


async def _original_pdf(db: AsyncSession, subject_id: UUID, document_id: UUID, user: User) -> SubjectDocumentPdf:
    row = await _document(db, subject_id, document_id, user)
    pdf = await db.get(SubjectDocumentPdf, row["content_revision_id"])
    if (pdf is None or pdf.subject_id != subject_id or pdf.document_id != document_id
        or pdf.source_sha256 != row["source_sha256"] or pdf.page_count != row["page_count"]):
        raise knowledge_http_error(404, "knowledge_pdf_unavailable", "Original PDF is unavailable.")
    return pdf


@router.get("/documents", response_model=PublishedKnowledgeList)
async def list_published_documents(
    subject_id: UUID, user: User = Depends(get_current_student), db: AsyncSession = Depends(get_db),
) -> PublishedKnowledgeList:
    await acquire_knowledge_write_lock(db)
    eligible = _eligible_documents(subject_id, user.id)
    rows = (await db.execute(
        select(eligible.c.document_id, eligible.c.document_title, eligible.c.page_count,
               SubjectDocumentPdf.content_revision_id)
        .outerjoin(SubjectDocumentPdf, SubjectDocumentPdf.content_revision_id == eligible.c.content_revision_id)
        .order_by(eligible.c.document_title, eligible.c.document_id).limit(100)
    )).all()
    return PublishedKnowledgeList(documents=[PublishedKnowledgeDocument(
        id=row[0], title=row[1], page_count=row[2], has_original_pdf=row[3] is not None,
    ) for row in rows])


@router.get("/search", response_model=PublishedKnowledgeSearch)
async def search_published_pages(
    subject_id: UUID, q: Annotated[str, Query(min_length=1, max_length=200)],
    user: User = Depends(get_current_student), db: AsyncSession = Depends(get_db),
) -> PublishedKnowledgeSearch:
    await acquire_knowledge_write_lock(db)
    terms = bounded_lexical_query(q, 12)
    if not terms:
        return PublishedKnowledgeSearch(pages=[])
    # The eligible view already enforces active, reviewed, published content and
    # the current embedding space. Enrollment is repeated in this SQL query.
    rows = (await db.execute(text("""
        WITH query AS (SELECT websearch_to_tsquery('simple'::regconfig, :terms) AS value),
        ranked_pages AS (
          SELECT eligible.document_id, eligible.document_title, eligible.page_number,
                 max(ts_rank_cd(to_tsvector('simple'::regconfig,
                     concat_ws(' ', eligible.document_title, eligible.section, eligible.content)),
                     query.value, 32)) AS rank
          FROM eligible_subject_knowledge_chunks AS eligible
          JOIN enrollments AS enrollment ON enrollment.subject_id = eligible.subject_id
            AND enrollment.student_id = :student_id
          CROSS JOIN query
          WHERE eligible.subject_id = :subject_id AND numnode(query.value) > 0
            AND to_tsvector('simple'::regconfig,
                concat_ws(' ', eligible.document_title, eligible.section, eligible.content)) @@ query.value
          GROUP BY eligible.document_id, eligible.document_title, eligible.page_number
        )
        SELECT document_id, document_title, page_number FROM ranked_pages
        ORDER BY rank DESC, document_id, page_number
        LIMIT 20
    """), {"terms": " OR ".join(terms.split()), "student_id": user.id, "subject_id": subject_id})).mappings().all()
    pages: list[PublishedKnowledgeSearchHit] = []
    for row in rows:
        pages.append(PublishedKnowledgeSearchHit(
            document_id=row["document_id"], document_title=row["document_title"],
            page_number=row["page_number"],
        ))
    return PublishedKnowledgeSearch(pages=pages)


@router.get("/documents/{document_id}/pages/{page_number}", response_model=PublishedKnowledgePage)
async def get_published_page(
    subject_id: UUID, document_id: UUID, page_number: Annotated[int, Path(ge=1, le=100)],
    user: User = Depends(get_current_student), db: AsyncSession = Depends(get_db),
) -> PublishedKnowledgePage:
    row = await _document(db, subject_id, document_id, user)
    page = await db.scalar(select(SubjectDocumentPage).where(
        SubjectDocumentPage.content_revision_id == row["content_revision_id"],
        SubjectDocumentPage.document_id == document_id,
        SubjectDocumentPage.subject_id == subject_id,
        SubjectDocumentPage.page_number == page_number,
    ))
    if page is None:
        raise knowledge_http_error(404, "published_knowledge_unavailable", "Published Knowledge is unavailable.")
    return PublishedKnowledgePage(document_title=row["document_title"], page_number=page_number,
                                  page_content=page.content[:20_000], truncated=len(page.content) > 20_000)


@router.head("/documents/{document_id}/original-pdf")
async def get_published_pdf_metadata(
    subject_id: UUID, document_id: UUID,
    user: User = Depends(get_current_student), db: AsyncSession = Depends(get_db),
) -> Response:
    pdf = await _original_pdf(db, subject_id, document_id, user)
    try:
        await probe_pdf_archive(db, settings=get_settings(), pdf=pdf)
    except KnowledgePdfError:
        raise knowledge_http_error(404, "knowledge_pdf_unavailable", "Original PDF is unavailable.") from None
    return Response(status_code=200, media_type="application/pdf", headers={
        "Content-Length": str(pdf.byte_size), "X-PDF-Page-Count": str(pdf.page_count),
        "Accept-Ranges": "bytes", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    })


@router.get("/documents/{document_id}/original-pdf")
async def get_published_pdf(
    subject_id: UUID, document_id: UUID,
    range_header: Annotated[str | None, Header(alias="Range", max_length=100)] = None,
    user: User = Depends(get_current_student), db: AsyncSession = Depends(get_db),
) -> Response:
    pdf = await _original_pdf(db, subject_id, document_id, user)
    try:
        data, span = await read_pdf_range(db, settings=get_settings(), pdf=pdf, range_header=range_header)
    except KnowledgePdfError as exc:
        error = knowledge_http_error(exc.status_code, exc.code, exc.safe_message)
        if exc.status_code == 416:
            error.headers = {"Content-Range": f"bytes */{pdf.byte_size}"}
        raise error from None
    headers = {"Cache-Control": "no-store", "Accept-Ranges": "bytes",
               "X-Content-Type-Options": "nosniff", "Content-Disposition": 'inline; filename="lecture.pdf"'}
    if span.partial:
        headers["Content-Range"] = f"bytes {span.start}-{span.end - 1}/{pdf.byte_size}"
    return Response(content=data, status_code=206 if span.partial else 200,
                    media_type="application/pdf", headers=headers)
