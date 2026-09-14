"""Owner-scoped HTTP API for durable PDF generation jobs."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_instructor
from app.schemas.generation import (
    GenerationJobCreate,
    GenerationJobListResponse,
    GenerationJobResponse,
    GenerationLimitsResponse,
)
from app.services.generation import GenerationJobService, read_bounded_pdf_body
from app.services.pdf_processor import PDFProcessingError
from app.services.rate_limit import limit_ai_generation, limit_pdf_upload
from app.services.subject import SubjectService


router = APIRouter(prefix="/flashcards", tags=["Generation jobs"])
settings = get_settings()
jobs = GenerationJobService(settings)


async def _response(db: AsyncSession, job) -> GenerationJobResponse:
    return await jobs.to_response(db, job)


@router.get("/generation-limits", response_model=GenerationLimitsResponse)
async def generation_limits(
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
) -> GenerationLimitsResponse:
    return await jobs.limits(db, user.id)


@router.post(
    "/generation-jobs",
    response_model=GenerationJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_generation_job(
    data: GenerationJobCreate,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
) -> GenerationJobResponse:
    """Reserve one job ID before sending the raw, stream-limited PDF body."""

    await SubjectService.check_subject_access(db, data.subject_id, user, require_owner=True)
    user_id = user.id
    await db.rollback()
    async with db.begin():
        job = await jobs.create_reservation(
            db,
            user_id=user_id,
            data=data,
            idempotency_key=idempotency_key,
        )
    response.headers["Location"] = f"/flashcards/generation-jobs/{job.id}"
    return await _response(db, job)


@router.put(
    "/generation-jobs/{job_id}/source",
    response_model=GenerationJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(limit_pdf_upload), Depends(limit_ai_generation)],
)
async def upload_generation_source(
    job_id: UUID,
    request: Request,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
) -> GenerationJobResponse:
    """Attach a raw PDF body; byte counting works for chunked requests too."""

    try:
        # Reject foreign or unknown job IDs before spending the bounded upload
        # budget. ``attach_source`` repeats this check while holding the row lock.
        await jobs.get_owner_job(db, job_id, user.id)
        content = await read_bounded_pdf_body(request, settings.pdf_max_upload_bytes)
        user_id = user.id
        await db.rollback()
        async with db.begin():
            job = await jobs.attach_source(
                db,
                job_id=job_id,
                user_id=user_id,
                media_type=request.headers.get("content-type"),
                content=content,
            )
    except PDFProcessingError as exc:
        from app.services.generation import generation_http_error

        http_status = (
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            if exc.code == "unsupported_media_type"
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise generation_http_error(http_status, exc.code, exc.safe_message) from None
    return await _response(db, job)


@router.get("/generation-jobs", response_model=GenerationJobListResponse)
async def list_generation_jobs(
    subject_id: UUID,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
) -> GenerationJobListResponse:
    await SubjectService.check_subject_access(db, subject_id, user, require_owner=True)
    owner_jobs = await jobs.list_owner_jobs(
        db, user_id=user.id, subject_id=subject_id, limit=limit
    )
    return GenerationJobListResponse(
        jobs=[await _response(db, job) for job in owner_jobs]
    )


@router.get("/generation-jobs/{job_id}", response_model=GenerationJobResponse)
async def get_generation_job(
    job_id: UUID,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
) -> GenerationJobResponse:
    job = await jobs.get_owner_job(db, job_id, user.id)
    return await _response(db, job)


@router.post("/generation-jobs/{job_id}/cancel", response_model=GenerationJobResponse)
async def cancel_generation_job(
    job_id: UUID,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
) -> GenerationJobResponse:
    user_id = user.id
    await db.rollback()
    async with db.begin():
        job = await jobs.cancel(db, job_id=job_id, user_id=user_id)
    return await _response(db, job)


@router.post("/generation-jobs/{job_id}/retry", response_model=GenerationJobResponse)
async def retry_generation_job(
    job_id: UUID,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db),
) -> GenerationJobResponse:
    user_id = user.id
    await db.rollback()
    async with db.begin():
        job = await jobs.retry(
            db,
            job_id=job_id,
            user_id=user_id,
            idempotency_key=idempotency_key,
        )
    return await _response(db, job)
