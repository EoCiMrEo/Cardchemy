"""Owner-private Subject Ask AI enqueue, history and lifecycle API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import ASK_REQUIRED_RELEASE_POLICY_VERSION, Settings, get_settings
from app.models.knowledge import RagEmbeddingSpace, SubjectDocumentContentRevision, SubjectDocumentPdf, embedding_space_hash
from app.models.rag import RagRelatedEvidence
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.rag import (
    RagAnswerJobResponse,
    RagAnswerJobListResponse,
    RagHistoryResponse,
    RagQuestionCreate,
    RagProfileResponse,
    RagRelatedPageResponse,
    RagSourceResponse,
    RagThreadListResponse,
    RagThreadResponse,
)
from app.services.rag_answers import RagAnswerService
from app.services.subject import SubjectService
from app.services.knowledge_pdf import KnowledgePdfError, probe_pdf_archive, read_pdf_range
from app.services.rag_answers import rag_http_error


router = APIRouter(prefix="/subjects/{subject_id}/rag", tags=["Subject Ask AI"])
answers = RagAnswerService()


async def _prepare_mutation(db: AsyncSession, user: User) -> None:
    """Keep the authenticated principal loaded across the transaction reset."""

    if user in db.sync_session:
        db.expunge(user)
    await db.rollback()


@router.get("/profile", response_model=RagProfileResponse)
async def get_rag_profile(
    subject_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RagProfileResponse:
    """Expose only the selected non-secret processors for pre-use disclosure."""

    subject = await SubjectService.check_subject_access(db, subject_id, user)
    active_space = (
        await db.get(RagEmbeddingSpace, subject.active_embedding_space_hash)
        if subject.active_embedding_space_hash is not None
        else None
    )
    configured_space_hash = embedding_space_hash(settings.rag_embedding_space_identity)
    space_matches = (
        active_space is not None
        and active_space.identity_hash == configured_space_hash
    )
    visual_policy = ASK_REQUIRED_RELEASE_POLICY_VERSION in {"related_knowledge_navigation_v5", "related_knowledge_navigation_v6", "related_knowledge_navigation_v7", "related_knowledge_navigation_v8"}
    literal_subject_policy = (
        (ASK_REQUIRED_RELEASE_POLICY_VERSION, settings.rag_source_judge_contract_version)
        in {("related_knowledge_navigation_v7", "visual_source_id_v3"),
            ("related_knowledge_navigation_v8", "visual_source_id_v5")}
    )
    return RagProfileResponse(
        rag_enabled=settings.rag_enabled,
        ask_enabled=settings.rag_ask_effective_enabled and space_matches,
        ask_available=settings.rag_source_only_available and space_matches,
        ask_policy=ASK_REQUIRED_RELEASE_POLICY_VERSION,
        answer_available=False,
        answer_provider=None,
        answer_model=None,
        source_judge_available=settings.rag_source_only_available and space_matches,
        source_judge_provider=settings.rag_source_judge_provider,
        source_judge_model=settings.rag_source_judge_model,
        source_judge_transfers_published_content=True,
        source_judge_thinking_level=(settings.rag_source_judge_thinking_level.upper() if visual_policy else "LOW"),
        source_judge_transfers_page_images=visual_policy,
        source_judge_transfers_literal_subject_context=literal_subject_policy,
        source_judge_contract_version=(settings.rag_source_judge_contract_version if visual_policy else "source_id_only_public_v1"),
        embedding_available=settings.rag_index_available,
        embedding_provider=settings.rag_embedding_provider,
        embedding_model=settings.rag_embedding_model,
        active_embedding_provider=(active_space.provider if active_space else None),
        active_embedding_model=(active_space.model if active_space else None),
        active_embedding_space_matches=space_matches,
        chat_retention_days=settings.rag_chat_retention_days,
    )


@router.post("/threads", response_model=RagThreadResponse, status_code=status.HTTP_201_CREATED)
async def create_thread(
    subject_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RagThreadResponse:
    await _prepare_mutation(db, user)
    async with db.begin():
        thread = await answers.create_thread(db, subject_id=subject_id, user=user)
    return answers.thread_response(thread)


@router.get("/threads", response_model=RagThreadListResponse)
async def list_threads(
    subject_id: UUID,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RagThreadListResponse:
    threads = await answers.list_threads(db, subject_id=subject_id, user=user, limit=limit)
    return RagThreadListResponse(threads=[answers.thread_response(item) for item in threads])


@router.get("/threads/{thread_id}", response_model=RagHistoryResponse)
async def get_thread_history(
    subject_id: UUID,
    thread_id: UUID,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RagHistoryResponse:
    return await answers.history(
        db, subject_id=subject_id, thread_id=thread_id, user=user, limit=limit
    )


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    subject_id: UUID,
    thread_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _prepare_mutation(db, user)
    async with db.begin():
        await answers.delete_thread(
            db, subject_id=subject_id, thread_id=thread_id, user=user
        )


@router.post(
    "/threads/{thread_id}/answer-jobs",
    response_model=RagAnswerJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_answer_job(
    subject_id: UUID,
    thread_id: UUID,
    data: RagQuestionCreate,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RagAnswerJobResponse:
    await _prepare_mutation(db, user)
    async with db.begin():
        job = await answers.enqueue(
            db,
            subject_id=subject_id,
            thread_id=thread_id,
            user=user,
            data=data,
            idempotency_key=idempotency_key,
        )
    response.headers["Location"] = (
        f"/subjects/{subject_id}/rag/threads/{thread_id}/answer-jobs/{job.id}"
    )
    return answers.job_response(job)


@router.get(
    "/threads/{thread_id}/answer-jobs",
    response_model=RagAnswerJobListResponse,
)
async def list_answer_jobs(
    subject_id: UUID,
    thread_id: UUID,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RagAnswerJobListResponse:
    return await answers.list_jobs(
        db,
        subject_id=subject_id,
        thread_id=thread_id,
        user=user,
        limit=limit,
    )


@router.get(
    "/threads/{thread_id}/answer-jobs/{job_id}",
    response_model=RagAnswerJobResponse,
)
async def get_answer_job(
    subject_id: UUID,
    thread_id: UUID,
    job_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RagAnswerJobResponse:
    job = await answers.owned_job(
        db,
        subject_id=subject_id,
        thread_id=thread_id,
        job_id=job_id,
        user=user,
    )
    return await answers.job_response_with_related(db, job=job, user=user)


@router.get(
    "/threads/{thread_id}/answer-jobs/{job_id}/related-excerpts/{excerpt_order}/page",
    response_model=RagRelatedPageResponse,
)
async def get_related_page(
    subject_id: UUID,
    thread_id: UUID,
    job_id: UUID,
    excerpt_order: Annotated[int, Path(ge=1, le=3)],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RagRelatedPageResponse:
    return await answers.related_page(
        db, subject_id=subject_id, thread_id=thread_id,
        job_id=job_id, excerpt_order=excerpt_order, user=user,
    )


async def _authorized_original_pdf(
    db: AsyncSession, *, subject_id: UUID, thread_id: UUID, job_id: UUID,
    excerpt_order: int, user: User,
) -> SubjectDocumentPdf:
    # This acquires the Knowledge writer lock and reauthorizes the entire bundle
    # against the current corpus, selected sources, revision and access scope.
    await answers.related_page(
        db, subject_id=subject_id, thread_id=thread_id, job_id=job_id,
        excerpt_order=excerpt_order, user=user,
    )
    reference = await db.get(RagRelatedEvidence, (job_id, excerpt_order))
    pdf = await db.get(SubjectDocumentPdf, reference.content_revision_id) if reference is not None else None
    revision = await db.get(SubjectDocumentContentRevision, reference.content_revision_id) if reference is not None else None
    if (
        reference is None or pdf is None or revision is None
        or pdf.document_id != reference.document_id or pdf.subject_id != subject_id
        or pdf.uploader_id != revision.uploader_id or pdf.source_sha256 != revision.source_sha256
        or pdf.page_count != revision.actual_page_count
    ):
        raise rag_http_error(404, "knowledge_pdf_unavailable", "Original PDF is unavailable.")
    try:
        get_settings().knowledge_pdf_encryption_key_bytes
    except ValueError:
        raise rag_http_error(404, "knowledge_pdf_unavailable", "Original PDF is unavailable.") from None
    return pdf


@router.head("/threads/{thread_id}/answer-jobs/{job_id}/related-excerpts/{excerpt_order}/original-pdf")
async def get_related_original_pdf_metadata(
    subject_id: UUID, thread_id: UUID, job_id: UUID,
    excerpt_order: Annotated[int, Path(ge=1, le=3)],
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> Response:
    pdf = await _authorized_original_pdf(
        db, subject_id=subject_id, thread_id=thread_id, job_id=job_id,
        excerpt_order=excerpt_order, user=user,
    )
    try:
        await probe_pdf_archive(db, settings=get_settings(), pdf=pdf)
    except KnowledgePdfError:
        raise rag_http_error(404, "knowledge_pdf_unavailable", "Original PDF is unavailable.") from None
    return Response(status_code=200, media_type="application/pdf", headers={
        "Content-Length": str(pdf.byte_size), "X-PDF-Page-Count": str(pdf.page_count),
        "Accept-Ranges": "bytes", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    })


@router.get("/threads/{thread_id}/answer-jobs/{job_id}/related-excerpts/{excerpt_order}/original-pdf")
async def get_related_original_pdf(
    subject_id: UUID, thread_id: UUID, job_id: UUID,
    excerpt_order: Annotated[int, Path(ge=1, le=3)],
    range_header: Annotated[str | None, Header(alias="Range", max_length=100)] = None,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
) -> Response:
    pdf = await _authorized_original_pdf(
        db, subject_id=subject_id, thread_id=thread_id, job_id=job_id,
        excerpt_order=excerpt_order, user=user,
    )
    try:
        data, span = await read_pdf_range(db, settings=get_settings(), pdf=pdf, range_header=range_header)
    except KnowledgePdfError as exc:
        headers = {"Content-Range": f"bytes */{pdf.byte_size}"} if exc.status_code == 416 else {}
        raise rag_http_error(exc.status_code, exc.code, exc.safe_message, **headers) from None
    headers = {
        "Cache-Control": "no-store", "Accept-Ranges": "bytes", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": 'inline; filename="lecture.pdf"',
    }
    if span.partial:
        headers["Content-Range"] = f"bytes {span.start}-{span.end - 1}/{pdf.byte_size}"
    return Response(content=data, status_code=206 if span.partial else 200, media_type="application/pdf", headers=headers)


@router.post(
    "/threads/{thread_id}/answer-jobs/{job_id}/cancel",
    response_model=RagAnswerJobResponse,
)
async def cancel_answer_job(
    subject_id: UUID,
    thread_id: UUID,
    job_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RagAnswerJobResponse:
    await _prepare_mutation(db, user)
    async with db.begin():
        job = await answers.cancel(
            db,
            subject_id=subject_id,
            thread_id=thread_id,
            job_id=job_id,
            user=user,
        )
    return answers.job_response(job)


@router.post(
    "/threads/{thread_id}/answer-jobs/{job_id}/retry",
    response_model=RagAnswerJobResponse,
)
async def retry_answer_job(
    subject_id: UUID,
    thread_id: UUID,
    job_id: UUID,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RagAnswerJobResponse:
    await _prepare_mutation(db, user)
    async with db.begin():
        job = await answers.retry(
            db,
            subject_id=subject_id,
            thread_id=thread_id,
            job_id=job_id,
            user=user,
            idempotency_key=idempotency_key,
        )
    return answers.job_response(job)


@router.get(
    "/threads/{thread_id}/messages/{message_id}/sources",
    response_model=list[RagSourceResponse],
)
async def get_message_sources(
    subject_id: UUID,
    thread_id: UUID,
    message_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RagSourceResponse]:
    return await answers.message_sources(
        db,
        subject_id=subject_id,
        thread_id=thread_id,
        message_id=message_id,
        user=user,
    )


__all__ = ["router"]
