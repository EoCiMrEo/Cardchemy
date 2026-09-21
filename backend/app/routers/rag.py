"""Owner-private Subject Ask AI enqueue, history and lifecycle API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import Settings, get_settings
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.rag import (
    RagAnswerJobResponse,
    RagAnswerJobListResponse,
    RagHistoryResponse,
    RagQuestionCreate,
    RagProfileResponse,
    RagSourceResponse,
    RagThreadListResponse,
    RagThreadResponse,
)
from app.services.rag_answers import RagAnswerService
from app.services.subject import SubjectService


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

    await SubjectService.check_subject_access(db, subject_id, user)
    return RagProfileResponse(
        rag_enabled=settings.rag_enabled,
        answer_available=settings.rag_answer_available,
        answer_provider=settings.rag_ai_provider,
        answer_model=settings.rag_ai_model,
        embedding_available=settings.rag_index_available,
        embedding_provider=settings.rag_embedding_provider,
        embedding_model=settings.rag_embedding_model,
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
    return answers.job_response(job)


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
