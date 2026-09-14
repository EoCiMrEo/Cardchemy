"""Admission, quotas, idempotency, and lifecycle operations for PDF jobs."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import PurePath
import random
import re
import secrets
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models.generation import (
    GenerationJob,
    GenerationJobSource,
    GenerationJobStatus,
    GenerationQuotaEvent,
)
from app.models.subject import FlashcardSet
from app.schemas.generation import (
    GenerationLimitReason,
    GenerationJobCreate,
    GenerationJobResponse,
    GenerationLimitsResponse,
)
from app.services.pdf_processor import PDFProcessingError, PDFProcessor
from app.services.source_storage import SourceStorage
from app.time_utils import as_utc, utcnow


ACTIVE_STATUSES = (
    GenerationJobStatus.AWAITING_UPLOAD.value,
    GenerationJobStatus.QUEUED.value,
    GenerationJobStatus.RUNNING.value,
)
PENDING_STATUSES = (
    GenerationJobStatus.AWAITING_UPLOAD.value,
    GenerationJobStatus.QUEUED.value,
)
DEPLOYMENT_ADMISSION_LOCK = 7_314_159_265
IDEMPOTENCY_PATTERN = re.compile(r"^[\x21-\x7e]{8,128}$")


def generation_http_error(status_code: int, code: str, message: str, **headers: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
        headers=headers or None,
    )


def hash_operation_key(value: str) -> str:
    if not IDEMPOTENCY_PATTERN.fullmatch(value):
        raise generation_http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_idempotency_key",
            "Idempotency-Key must contain 8 to 128 visible ASCII characters.",
        )
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def sanitize_filename(value: str) -> str:
    normalized = value.replace("\\", "/").rsplit("/", 1)[-1].strip()
    normalized = "".join(character for character in normalized if ord(character) >= 32)
    if not normalized:
        raise generation_http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_filename",
            "A PDF filename is required.",
        )
    if len(normalized) > 255:
        raise generation_http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_filename",
            "The PDF filename cannot exceed 255 characters.",
        )
    return PurePath(normalized).name


def metadata_fingerprint(data: GenerationJobCreate, sanitized_filename: str) -> str:
    canonical = json.dumps(
        {
            "subject_id": str(data.subject_id),
            "set_title": data.set_title.strip(),
            "set_description": (data.set_description or "").strip() or None,
            "source_pdf_name": sanitized_filename,
            "card_count": data.card_count,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def read_bounded_pdf_body(request: Request, maximum_bytes: int) -> bytes:
    """Read raw request chunks without trusting Content-Length."""

    content_length = request.headers.get("content-length")
    if content_length is not None:
        if not content_length.isdigit():
            raise generation_http_error(
                status.HTTP_400_BAD_REQUEST,
                "invalid_content_length",
                "Content-Length must be a non-negative integer.",
            )
        if int(content_length) > maximum_bytes:
            raise generation_http_error(
                status.HTTP_413_CONTENT_TOO_LARGE,
                "upload_too_large",
                f"The PDF exceeds the configured limit of {maximum_bytes} bytes.",
            )

    chunks = bytearray()
    async for chunk in request.stream():
        if len(chunks) + len(chunk) > maximum_bytes:
            raise generation_http_error(
                status.HTTP_413_CONTENT_TOO_LARGE,
                "upload_too_large",
                f"The PDF exceeds the configured limit of {maximum_bytes} bytes.",
            )
        chunks.extend(chunk)
    if not chunks:
        raise generation_http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "empty_upload",
            "The PDF upload is empty.",
        )
    return bytes(chunks)


class GenerationJobService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    async def _lock_admission(self, db: AsyncSession) -> None:
        if db.get_bind().dialect.name == "postgresql":
            await db.execute(
                text("SELECT pg_advisory_xact_lock(:lock_id)"),
                {"lock_id": DEPLOYMENT_ADMISSION_LOCK},
            )

    @staticmethod
    def _day_bounds() -> tuple[datetime, datetime]:
        now = utcnow()
        start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
        return start, start + timedelta(days=1)

    async def _quota_totals(
        self, db: AsyncSession, *, user_id: UUID | None = None
    ) -> tuple[int, int, int]:
        start, _ = self._day_bounds()
        query = select(
            func.coalesce(func.sum(GenerationQuotaEvent.job_units), 0),
            func.coalesce(func.sum(GenerationQuotaEvent.card_units), 0),
            func.coalesce(func.sum(GenerationQuotaEvent.upload_bytes), 0),
        ).where(GenerationQuotaEvent.created_at >= start)
        if user_id is not None:
            query = query.where(GenerationQuotaEvent.user_id == user_id)
        row = (await db.execute(query)).one()
        return int(row[0]), int(row[1]), int(row[2])

    async def _retained_bytes(self, db: AsyncSession, user_id: UUID | None = None) -> int:
        query = select(func.coalesce(func.sum(GenerationJob.source_size_bytes), 0)).join(
            GenerationJobSource, GenerationJobSource.job_id == GenerationJob.id
        )
        if user_id is not None:
            query = query.where(GenerationJob.user_id == user_id)
        return int(await db.scalar(query) or 0)

    async def _check_reservation_capacity(self, db: AsyncSession, user_id: UUID) -> None:
        await self._lock_admission(db)
        if not self.settings.ai_provider_configured:
            raise generation_http_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "ai_provider_not_configured",
                "Generation is unavailable until an AI provider is configured.",
            )
        user_active = int(
            await db.scalar(
                select(func.count(GenerationJob.id)).where(
                    GenerationJob.user_id == user_id,
                    GenerationJob.status.in_(ACTIVE_STATUSES),
                )
            )
            or 0
        )
        if user_active >= self.settings.generation_max_active_jobs_per_user:
            raise generation_http_error(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "user_active_job_limit",
                "Finish or cancel an active generation job before starting another.",
                **{"Retry-After": "30"},
            )
        pending = int(
            await db.scalar(
                select(func.count(GenerationJob.id)).where(
                    GenerationJob.status.in_(PENDING_STATUSES)
                )
            )
            or 0
        )
        if pending >= self.settings.generation_max_queued_jobs_deployment:
            raise generation_http_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "generation_queue_full",
                "The generation queue is full. Try again later.",
                **{"Retry-After": "30"},
            )

    async def _check_quota_charge(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        card_units: int,
        upload_bytes: int,
    ) -> None:
        await self._lock_admission(db)
        user_jobs, user_cards, user_bytes = await self._quota_totals(db, user_id=user_id)
        deployment_jobs, deployment_cards, deployment_bytes = await self._quota_totals(db)
        checks = (
            (user_jobs + 1, self.settings.generation_daily_jobs_per_user, "user_daily_job_limit", "Your daily generation-job limit has been reached."),
            (user_cards + card_units, self.settings.generation_daily_cards_per_user, "user_daily_card_limit", "Your daily generated-card limit has been reached."),
            (user_bytes + upload_bytes, self.settings.generation_daily_upload_bytes_per_user, "user_daily_upload_limit", "Your daily PDF upload-byte limit has been reached."),
            (deployment_jobs + 1, self.settings.generation_daily_jobs_deployment, "deployment_daily_job_limit", "The deployment daily generation-job limit has been reached."),
            (deployment_cards + card_units, self.settings.generation_daily_cards_deployment, "deployment_daily_card_limit", "The deployment daily generated-card limit has been reached."),
            (deployment_bytes + upload_bytes, self.settings.generation_daily_upload_bytes_deployment, "deployment_daily_upload_limit", "The deployment daily PDF upload-byte limit has been reached."),
        )
        for value, limit, code, message in checks:
            if value > limit:
                _, reset_at = self._day_bounds()
                retry_after = max(1, int((reset_at - utcnow()).total_seconds()))
                raise generation_http_error(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    code,
                    message,
                    **{"Retry-After": str(retry_after)},
                )

        retained_user = await self._retained_bytes(db, user_id)
        retained_deployment = await self._retained_bytes(db)
        if retained_user + upload_bytes > self.settings.generation_max_retained_source_bytes_per_user:
            raise generation_http_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "user_source_storage_limit",
                "Your retained temporary PDF storage is at capacity.",
                **{"Retry-After": "60"},
            )
        if retained_deployment + upload_bytes > self.settings.generation_max_retained_source_bytes_deployment:
            raise generation_http_error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "deployment_source_storage_limit",
                "The deployment temporary PDF storage is at capacity.",
                **{"Retry-After": "60"},
            )

    async def create_reservation(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        data: GenerationJobCreate,
        idempotency_key: str,
    ) -> GenerationJob:
        key_hash = hash_operation_key(idempotency_key)
        if not (
            self.settings.generation_min_card_count
            <= data.card_count
            <= self.settings.generation_max_card_count
        ):
            raise generation_http_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "card_count_out_of_range",
                "card_count is outside the configured generation limits.",
            )
        filename = sanitize_filename(data.source_pdf_name)
        fingerprint = metadata_fingerprint(data, filename)
        await self._lock_admission(db)
        existing = await db.scalar(
            select(GenerationJob).where(
                GenerationJob.user_id == user_id,
                GenerationJob.idempotency_key_hash == key_hash,
            )
        )
        if existing:
            if existing.request_fingerprint != fingerprint:
                raise generation_http_error(
                    status.HTTP_409_CONFLICT,
                    "idempotency_key_reused",
                    "This Idempotency-Key was already used for different job metadata.",
                )
            return existing

        await self._check_reservation_capacity(db, user_id)
        now = utcnow()
        job = GenerationJob(
            user_id=user_id,
            subject_id=data.subject_id,
            idempotency_key_hash=key_hash,
            request_fingerprint=fingerprint,
            status=GenerationJobStatus.AWAITING_UPLOAD.value,
            stage="awaiting_upload",
            progress=0,
            set_title=data.set_title.strip(),
            set_description=(data.set_description or "").strip() or None,
            requested_card_count=data.card_count,
            source_pdf_name=filename,
            ai_provider=self.settings.ai_provider,
            ai_model=self.settings.ai_model,
            max_attempts=self.settings.generation_max_attempts,
            available_at=now,
            upload_expires_at=now
            + timedelta(minutes=self.settings.generation_upload_reservation_minutes),
            created_at=now,
            updated_at=now,
        )
        db.add(job)
        await db.flush()
        return job

    async def attach_source(
        self,
        db: AsyncSession,
        *,
        job_id: UUID,
        user_id: UUID,
        media_type: str | None,
        content: bytes,
    ) -> GenerationJob:
        normalized_media_type = PDFProcessor.validate_media_type(media_type)
        PDFProcessor.validate_signature(content)
        source_hash = hashlib.sha256(content).hexdigest()
        job = await self.get_owner_job(db, job_id, user_id, for_update=True)

        if job.source_sha256 is not None:
            if (
                job.source_sha256 == source_hash
                and job.source_size_bytes == len(content)
                and job.source_media_type == normalized_media_type
            ):
                return job
            raise generation_http_error(
                status.HTTP_409_CONFLICT,
                "job_source_conflict",
                "This job already has a different source PDF.",
            )
        if job.status != GenerationJobStatus.AWAITING_UPLOAD.value:
            raise generation_http_error(
                status.HTTP_409_CONFLICT,
                "job_not_awaiting_upload",
                "This job is not accepting a source upload.",
            )
        if not job.upload_expires_at or as_utc(job.upload_expires_at) <= utcnow():
            job.status = GenerationJobStatus.CANCELLED.value
            job.stage = "upload_expired"
            job.completed_at = utcnow()
            job.updated_at = utcnow()
            raise generation_http_error(
                status.HTTP_410_GONE,
                "upload_reservation_expired",
                "The upload reservation expired. Start a new generation job.",
            )

        await self._check_quota_charge(
            db,
            user_id=user_id,
            card_units=job.requested_card_count,
            upload_bytes=len(content),
        )
        nonce, payload = SourceStorage.encrypt(content, job.request_fingerprint)
        now = utcnow()
        db.add(
            GenerationJobSource(
                job_id=job.id,
                key_version=1,
                nonce=nonce,
                payload=payload,
                expires_at=None,
                created_at=now,
            )
        )
        db.add(
            GenerationQuotaEvent(
                user_id=user_id,
                job_id=job.id,
                operation_key_hash=job.idempotency_key_hash,
                card_units=job.requested_card_count,
                upload_bytes=len(content),
                created_at=now,
            )
        )
        job.source_media_type = normalized_media_type
        job.source_size_bytes = len(content)
        job.source_sha256 = source_hash
        job.status = GenerationJobStatus.QUEUED.value
        job.stage = "queued"
        job.progress = 5
        job.available_at = now
        job.upload_expires_at = None
        job.updated_at = now
        await db.flush()
        return job

    async def get_owner_job(
        self,
        db: AsyncSession,
        job_id: UUID,
        user_id: UUID,
        *,
        for_update: bool = False,
    ) -> GenerationJob:
        query = select(GenerationJob).where(
            GenerationJob.id == job_id, GenerationJob.user_id == user_id
        )
        if for_update:
            query = query.with_for_update()
        job = await db.scalar(query)
        if job is None:
            raise generation_http_error(
                status.HTTP_404_NOT_FOUND,
                "generation_job_not_found",
                "Generation job not found.",
            )
        return job

    async def list_owner_jobs(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        subject_id: UUID,
        limit: int,
    ) -> list[GenerationJob]:
        result = await db.scalars(
            select(GenerationJob)
            .where(
                GenerationJob.user_id == user_id,
                GenerationJob.subject_id == subject_id,
            )
            .order_by(GenerationJob.created_at.desc(), GenerationJob.id.desc())
            .limit(limit)
        )
        return list(result.all())

    async def cancel(
        self, db: AsyncSession, *, job_id: UUID, user_id: UUID
    ) -> GenerationJob:
        job = await self.get_owner_job(db, job_id, user_id, for_update=True)
        now = utcnow()
        if job.status in (
            GenerationJobStatus.AWAITING_UPLOAD.value,
            GenerationJobStatus.QUEUED.value,
        ):
            await db.execute(delete(GenerationJobSource).where(GenerationJobSource.job_id == job.id))
            job.status = GenerationJobStatus.CANCELLED.value
            job.stage = "cancelled"
            job.progress = 100
            job.completed_at = now
            job.cancellation_requested_at = now
            job.error_retryable = False
        elif job.status == GenerationJobStatus.RUNNING.value:
            if job.cancellation_requested_at is None:
                job.cancellation_requested_at = now
            job.stage = "cancellation_requested"
        job.updated_at = now
        await db.flush()
        return job

    async def retry(
        self,
        db: AsyncSession,
        *,
        job_id: UUID,
        user_id: UUID,
        idempotency_key: str,
    ) -> GenerationJob:
        retry_key_hash = hash_operation_key(idempotency_key)
        await self._lock_admission(db)
        existing_charge = await db.scalar(
            select(GenerationQuotaEvent).where(
                GenerationQuotaEvent.user_id == user_id,
                GenerationQuotaEvent.operation_key_hash == retry_key_hash,
            )
        )
        if existing_charge:
            if existing_charge.job_id != job_id:
                raise generation_http_error(
                    status.HTTP_409_CONFLICT,
                    "idempotency_key_reused",
                    "This Idempotency-Key was already used for another operation.",
                )
            return await self.get_owner_job(db, job_id, user_id)

        job = await self.get_owner_job(db, job_id, user_id, for_update=True)
        source = await db.scalar(
            select(GenerationJobSource)
            .where(GenerationJobSource.job_id == job.id)
            .with_for_update()
        )
        if (
            job.status != GenerationJobStatus.FAILED.value
            or not job.error_retryable
            or source is None
            or source.expires_at is None
            or as_utc(source.expires_at) <= utcnow()
        ):
            raise generation_http_error(
                status.HTTP_409_CONFLICT,
                "job_not_retryable",
                "This generation job can no longer be retried.",
            )
        if job.manual_retry_count >= self.settings.generation_max_manual_retries:
            raise generation_http_error(
                status.HTTP_409_CONFLICT,
                "manual_retry_limit",
                "This generation job reached its manual retry limit.",
            )

        await self._check_reservation_capacity(db, user_id)
        await self._check_quota_charge(
            db,
            user_id=user_id,
            card_units=job.requested_card_count,
            upload_bytes=0,
        )
        now = utcnow()
        db.add(
            GenerationQuotaEvent(
                user_id=user_id,
                job_id=job.id,
                operation_key_hash=retry_key_hash,
                card_units=job.requested_card_count,
                upload_bytes=0,
                created_at=now,
            )
        )
        source.expires_at = None
        job.status = GenerationJobStatus.QUEUED.value
        job.stage = "queued"
        job.progress = 5
        job.attempt_count = 0
        job.manual_retry_count += 1
        job.available_at = now
        job.started_at = None
        job.heartbeat_at = None
        job.lease_expires_at = None
        job.completed_at = None
        job.error_code = None
        job.error_message = None
        job.error_retryable = False
        job.limit_reason_code = None
        job.limit_reason_message = None
        job.worker_id = None
        job.claim_token = None
        job.cancellation_requested_at = None
        job.updated_at = now
        await db.flush()
        return job

    async def to_response(self, db: AsyncSession, job: GenerationJob) -> GenerationJobResponse:
        result_set_id = await db.scalar(
            select(FlashcardSet.id).where(FlashcardSet.generation_job_id == job.id)
        )
        source_expires_at = await db.scalar(
            select(GenerationJobSource.expires_at).where(GenerationJobSource.job_id == job.id)
        )
        now = utcnow()
        can_retry = bool(
            job.status == GenerationJobStatus.FAILED.value
            and job.error_retryable
            and source_expires_at
            and as_utc(source_expires_at) > now
            and job.manual_retry_count < self.settings.generation_max_manual_retries
        )
        return GenerationJobResponse(
            id=job.id,
            subject_id=job.subject_id,
            flashcard_set_id=result_set_id,
            status=job.status,
            progress=job.progress,
            stage=job.stage,
            requested_card_count=job.requested_card_count,
            generated_card_count=job.generated_card_count,
            ai_provider=job.ai_provider,
            ai_model=job.ai_model,
            estimated_input_tokens=job.estimated_input_tokens,
            estimated_output_tokens=job.estimated_output_tokens,
            actual_input_tokens=job.actual_input_tokens,
            actual_output_tokens=job.actual_output_tokens,
            estimated_cost_microusd=job.estimated_cost_microusd,
            actual_cost_microusd=job.actual_cost_microusd,
            usage_estimated=job.usage_estimated,
            accepted_card_count=job.accepted_card_count,
            rejected_card_count=job.rejected_card_count,
            limit_reason_code=job.limit_reason_code,
            limit_reason_message=job.limit_reason_message,
            source_pdf_name=job.source_pdf_name,
            attempt_count=job.attempt_count,
            max_attempts=job.max_attempts,
            error_code=job.error_code,
            error_message=job.error_message,
            cancellation_requested_at=job.cancellation_requested_at,
            source_retry_expires_at=source_expires_at,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            updated_at=job.updated_at,
            can_cancel=job.status in ACTIVE_STATUSES and job.cancellation_requested_at is None,
            can_retry=can_retry,
        )

    async def limits(self, db: AsyncSession, user_id: UUID) -> GenerationLimitsResponse:
        jobs, cards, upload_bytes = await self._quota_totals(db, user_id=user_id)
        active = int(
            await db.scalar(
                select(func.count(GenerationJob.id)).where(
                    GenerationJob.user_id == user_id,
                    GenerationJob.status.in_(ACTIVE_STATUSES),
                )
            )
            or 0
        )
        pending = int(
            await db.scalar(
                select(func.count(GenerationJob.id)).where(
                    GenerationJob.status.in_(PENDING_STATUSES)
                )
            )
            or 0
        )
        _, reset_at = self._day_bounds()
        unavailable_reasons: list[GenerationLimitReason] = []
        if not self.settings.ai_provider_configured:
            unavailable_reasons.append(
                GenerationLimitReason(
                    code="ai_provider_not_configured",
                    message="Configure an AI provider before starting generation jobs.",
                )
            )
        if active >= self.settings.generation_max_active_jobs_per_user:
            unavailable_reasons.append(
                GenerationLimitReason(
                    code="user_active_job_limit",
                    message="Finish or cancel an active generation job first.",
                )
            )
        if pending >= self.settings.generation_max_queued_jobs_deployment:
            unavailable_reasons.append(
                GenerationLimitReason(
                    code="generation_queue_full",
                    message="The deployment generation queue is full.",
                )
            )
        if jobs >= self.settings.generation_daily_jobs_per_user:
            unavailable_reasons.append(
                GenerationLimitReason(
                    code="user_daily_job_limit",
                    message="Your daily generation-job limit has been reached.",
                )
            )
        return GenerationLimitsResponse(
            generation_available=not unavailable_reasons,
            ai_provider=self.settings.ai_provider,
            ai_model=self.settings.ai_model,
            ai_pricing_configured=self.settings.ai_pricing_configured,
            unavailable_reasons=unavailable_reasons,
            max_upload_bytes=self.settings.pdf_max_upload_bytes,
            max_pages=self.settings.pdf_max_pages,
            max_extracted_chars=self.settings.pdf_max_extracted_chars,
            min_card_count=self.settings.generation_min_card_count,
            max_card_count=self.settings.generation_max_card_count,
            daily_jobs_per_user=self.settings.generation_daily_jobs_per_user,
            daily_cards_per_user=self.settings.generation_daily_cards_per_user,
            daily_upload_bytes_per_user=self.settings.generation_daily_upload_bytes_per_user,
            max_active_jobs_per_user=self.settings.generation_max_active_jobs_per_user,
            daily_jobs_remaining=max(0, self.settings.generation_daily_jobs_per_user - jobs),
            daily_cards_remaining=max(0, self.settings.generation_daily_cards_per_user - cards),
            daily_upload_bytes_remaining=max(
                0, self.settings.generation_daily_upload_bytes_per_user - upload_bytes
            ),
            active_job_slots_remaining=max(
                0, self.settings.generation_max_active_jobs_per_user - active
            ),
            deployment_queue_slots_remaining=max(
                0, self.settings.generation_max_queued_jobs_deployment - pending
            ),
            quota_resets_at=reset_at,
            failed_source_retention_hours=self.settings.generation_source_retry_retention_hours,
            upload_reservation_minutes=self.settings.generation_upload_reservation_minutes,
            ocr_enabled=self.settings.pdf_ocr_enabled,
        )
