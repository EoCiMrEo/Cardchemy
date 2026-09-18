"""Lease-based PostgreSQL worker for durable flashcard generation."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import timedelta
from functools import partial
import logging
import os
import random
import socket
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.graph import create_flashcard_graph
from app.ai.pipeline import PipelineError
from app.ai.rate_limit import ProviderRateGovernor
from app.config import Settings, get_settings
from app.database import async_session_maker
from app.models.generation import GenerationJob, GenerationJobSource, GenerationJobStatus
from app.observability import job_context, safe_error_code
from app.schemas.subject import FlashcardSetCreate
from app.services.flashcard import FlashcardService
from app.services.generation import GenerationJobService
from app.services.operations import pulse_worker
from app.services.pdf_processor import PDFProcessingError, PDFProcessor
from app.services.source_storage import SourceStorage, SourceStorageError
from app.services.subject import SubjectService
from app.time_utils import as_utc, utcnow
from app.workers.shutdown import drain_active_tasks


logger = logging.getLogger(__name__)


class LeaseLost(RuntimeError):
    pass


class JobCancellationRequested(RuntimeError):
    pass


class ModelGenerationFailure(RuntimeError):
    pass


class GenerationWorker:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        session_factory: async_sessionmaker[AsyncSession] = async_session_maker,
        worker_id: str | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session_factory = session_factory
        self.job_service = GenerationJobService(self.settings)
        # One gate per worker process prevents concurrent jobs from multiplying
        # the configured provider-request concurrency.
        self.provider_semaphore = asyncio.Semaphore(self.settings.flashcard_ai_concurrency)
        # One rolling quota window is shared by every job in this worker
        # process. Provider retries reserve through this same governor.
        self.provider_rate_governor = ProviderRateGovernor.from_settings(
            self.settings
        )
        self.worker_id = worker_id or (
            f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:12]}"
        )

    async def run(self, stop_event: asyncio.Event) -> None:
        """Poll with bounded local concurrency until shutdown is requested."""

        if not self.settings.flashcard_ai_provider_enabled:
            logger.info("worker_disabled", extra={"kind": "generation"})
            try:
                while not stop_event.is_set():
                    await self._pulse("disabled")
                    try:
                        await asyncio.wait_for(stop_event.wait(), timeout=min(5, self.settings.worker_health_stale_seconds / 3))
                    except TimeoutError:
                        pass
            finally:
                await self._pulse("draining")
            return

        tasks: set[asyncio.Task[None]] = set()
        last_cleanup = 0.0
        loop = asyncio.get_running_loop()
        logger.info("worker_started", extra={"kind": "generation"})
        try:
            while not stop_event.is_set():
                await self._pulse("running")
                now_monotonic = loop.time()
                if now_monotonic - last_cleanup >= self.settings.generation_cleanup_interval_seconds:
                    await self.recover_and_cleanup()
                    last_cleanup = now_monotonic

                while (
                    len(tasks) < self.settings.generation_worker_concurrency
                    and not stop_event.is_set()
                ):
                    claim = await self.claim_next()
                    if claim is None:
                        break
                    job_id, claim_token = claim
                    task = asyncio.create_task(
                        self.process_claim(job_id, claim_token),
                        name=f"generation-{job_id}",
                    )
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)

                if tasks:
                    await asyncio.wait(
                        tasks,
                        timeout=self.settings.generation_worker_poll_seconds,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in tuple(tasks):
                        if task.done():
                            with suppress(Exception, asyncio.CancelledError):
                                task.result()
                else:
                    try:
                        await asyncio.wait_for(
                            stop_event.wait(),
                            timeout=self.settings.generation_worker_poll_seconds,
                        )
                    except TimeoutError:
                        pass
        finally:
            await self._pulse("draining")
            forced_cancellations = await drain_active_tasks(
                tasks, self.settings.worker_shutdown_grace_seconds
            )
            if forced_cancellations:
                logger.warning(
                    "worker_shutdown_expired",
                    extra={"kind": "generation", "active_count": forced_cancellations},
                )
            logger.info("worker_stopped", extra={"kind": "generation"})

    async def _pulse(self, status: str) -> None:
        await pulse_worker(self.session_factory, worker_id=self.worker_id, kind="generation", status=status, stale_seconds=self.settings.worker_health_stale_seconds)

    async def claim_next(self) -> tuple[UUID, str] | None:
        async with self.session_factory() as db:
            async with db.begin():
                await self.job_service._lock_admission(db)
                running = int(
                    await db.scalar(
                        select(func.count(GenerationJob.id)).where(
                            GenerationJob.status == GenerationJobStatus.RUNNING.value,
                            GenerationJob.lease_expires_at > utcnow(),
                        )
                    )
                    or 0
                )
                if running >= self.settings.generation_max_active_jobs_deployment:
                    return None

                query = (
                    select(GenerationJob)
                    .join(GenerationJobSource, GenerationJobSource.job_id == GenerationJob.id)
                    .where(
                        GenerationJob.status == GenerationJobStatus.QUEUED.value,
                        GenerationJob.available_at <= utcnow(),
                    )
                    .order_by(
                        GenerationJob.available_at,
                        GenerationJob.created_at,
                        GenerationJob.id,
                    )
                    .limit(1)
                )
                if db.get_bind().dialect.name == "postgresql":
                    query = query.with_for_update(of=GenerationJob, skip_locked=True)
                else:
                    query = query.with_for_update()
                job = await db.scalar(query)
                if job is None:
                    return None

                now = utcnow()
                token = uuid4().hex
                job.status = GenerationJobStatus.RUNNING.value
                job.stage = "starting"
                job.progress = max(job.progress, 10)
                job.attempt_count += 1
                job.started_at = job.started_at or now
                job.heartbeat_at = now
                job.lease_expires_at = now + timedelta(seconds=self.settings.generation_lease_seconds)
                job.worker_id = self.worker_id
                job.claim_token = token
                job.updated_at = now
                await db.flush()
                return job.id, token

    async def _claimed_job(
        self,
        db: AsyncSession,
        job_id: UUID,
        claim_token: str,
        *,
        for_update: bool = False,
    ) -> GenerationJob:
        query = select(GenerationJob).where(GenerationJob.id == job_id)
        if for_update:
            query = query.with_for_update()
        job = await db.scalar(query)
        if (
            job is None
            or job.status != GenerationJobStatus.RUNNING.value
            or job.claim_token != claim_token
            or job.worker_id != self.worker_id
            or job.lease_expires_at is None
            or as_utc(job.lease_expires_at) <= utcnow()
        ):
            raise LeaseLost("generation-job lease is no longer valid")
        if job.cancellation_requested_at is not None:
            raise JobCancellationRequested("generation cancellation requested")
        return job

    async def _update_stage(
        self, job_id: UUID, claim_token: str, stage: str, progress: int
    ) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                job = await self._claimed_job(db, job_id, claim_token, for_update=True)
                job.stage = stage
                job.progress = progress
                job.updated_at = utcnow()
        logger.info("generation_stage", extra={"stage": stage})

    async def _heartbeat(
        self,
        job_id: UUID,
        claim_token: str,
        pipeline: asyncio.Task[None],
        user_cancelled: asyncio.Event,
        stop_heartbeat: asyncio.Event,
    ) -> None:
        while not stop_heartbeat.is_set():
            try:
                await asyncio.wait_for(
                    stop_heartbeat.wait(),
                    timeout=self.settings.generation_heartbeat_seconds,
                )
                return
            except TimeoutError:
                pass
            try:
                async with self.session_factory() as db:
                    async with db.begin():
                        job = await self._claimed_job(
                            db, job_id, claim_token, for_update=True
                        )
                        now = utcnow()
                        job.heartbeat_at = now
                        job.lease_expires_at = now + timedelta(
                            seconds=self.settings.generation_lease_seconds
                        )
                        job.updated_at = now
            except JobCancellationRequested:
                user_cancelled.set()
                pipeline.cancel()
                return
            except LeaseLost:
                pipeline.cancel()
                return
            except Exception:
                # Finalization also verifies the unexpired lease, so a database
                # outage cannot let stale work commit.
                logger.warning("generation_heartbeat_failed")

    async def process_claim(self, job_id: UUID, claim_token: str) -> None:
        origin = None
        try:
            async with asyncio.timeout(0.25):
                async with self.session_factory() as db:
                    origin = await db.scalar(select(GenerationJob.request_id).where(GenerationJob.id == job_id))
        except Exception:
            pass
        with job_context(job_id, request_id=origin):
            logger.info("generation_started")
            await self._process_claim(job_id, claim_token)

    async def _process_claim(self, job_id: UUID, claim_token: str) -> None:
        user_cancelled = asyncio.Event()
        stop_heartbeat = asyncio.Event()
        pipeline = asyncio.create_task(self._pipeline(job_id, claim_token))
        heartbeat = asyncio.create_task(
            self._heartbeat(
                job_id,
                claim_token,
                pipeline,
                user_cancelled,
                stop_heartbeat,
            )
        )
        try:
            await pipeline
        except asyncio.CancelledError:
            if user_cancelled.is_set():
                await self._finish_cancelled(job_id, claim_token)
            else:
                raise
        except JobCancellationRequested:
            await self._finish_cancelled(job_id, claim_token)
        except LeaseLost:
            logger.warning("generation_lease_lost")
            return
        except PDFProcessingError as exc:
            await self._finish_failure(
                job_id,
                claim_token,
                code=exc.code,
                message=exc.safe_message,
                retryable=False,
            )
        except SourceStorageError:
            await self._finish_failure(
                job_id,
                claim_token,
                code="source_decryption_failed",
                message="The retained PDF could not be read. Upload it again.",
                retryable=False,
            )
        except ModelGenerationFailure:
            await self._finish_failure(
                job_id,
                claim_token,
                code="generation_temporarily_unavailable",
                message="Flashcard generation was temporarily unavailable.",
                retryable=True,
            )
        except TimeoutError:
            # A timeout must not replay an expensive provider pipeline. Normal
            # job timeouts are mapped below with telemetry; this is a safe
            # fallback for an unexpected timeout at another worker boundary.
            await self._finish_failure(
                job_id,
                claim_token,
                code="generation_job_timeout",
                message="Generation reached the configured job time limit. Retry later or reduce the requested cards.",
                retryable=True,
                auto_retry=False,
            )
        except PipelineError as exc:
            await self._finish_failure(
                job_id,
                claim_token,
                code=exc.code,
                message=exc.safe_message,
                retryable=exc.retryable,
                auto_retry=False,
                telemetry={
                    "estimated_input_tokens": exc.estimated_input_tokens,
                    "estimated_output_tokens": exc.estimated_output_tokens,
                    "estimated_cost_microusd": exc.estimated_cost_microusd,
                    "actual_input_tokens": exc.actual_input_tokens,
                    "actual_output_tokens": exc.actual_output_tokens,
                    "actual_cost_microusd": exc.actual_cost_microusd,
                    "usage_estimated": exc.usage_estimated,
                    "rejected_card_count": exc.rejected_card_count,
                    "estimated_request_count": exc.estimated_request_count,
                    "provider_request_count": exc.provider_request_count,
                    "provider_retry_count": exc.provider_retry_count,
                    "provider_rate_limit_wait_milliseconds": (
                        exc.provider_rate_limit_wait_milliseconds
                    ),
                    "cached_input_tokens": exc.cached_input_tokens,
                    "provider_request_counts_by_stage": (
                        exc.provider_request_counts_by_stage
                    ),
                },
            )
        except (KeyError, TypeError, ValueError, ValidationError):
            await self._finish_failure(
                job_id,
                claim_token,
                code="invalid_generated_cards",
                message="The generated cards did not pass validation.",
                retryable=False,
            )
        except Exception:
            logger.warning("generation_failed", extra={"error_code": "generation_internal_error"})
            await self._finish_failure(
                job_id,
                claim_token,
                code="generation_internal_error",
                message="Generation failed because of a temporary internal error.",
                retryable=True,
            )
        finally:
            stop_heartbeat.set()
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)

    async def _pipeline(self, job_id: UUID, claim_token: str) -> None:
        graph_holder: dict = {}
        try:
            await self._pipeline_with_graph(job_id, claim_token, graph_holder)
        except TimeoutError as exc:
            graph = graph_holder.get("graph")
            if graph is not None:
                raise graph.pipeline.job_timeout_error() from exc
            raise PipelineError(
                "generation_job_timeout",
                "Generation reached the configured job time limit. Retry later or reduce the requested cards.",
                retryable=True,
            ) from exc

    async def _pipeline_with_graph(
        self, job_id: UUID, claim_token: str, graph_holder: dict
    ) -> None:
        async with asyncio.timeout(self.settings.generation_job_timeout_seconds):
            await self._update_stage(job_id, claim_token, "validating_pdf", 12)
            async with self.session_factory() as db:
                job = await self._claimed_job(db, job_id, claim_token)
                source = await db.scalar(
                    select(GenerationJobSource).where(GenerationJobSource.job_id == job_id)
                )
                if source is None:
                    raise SourceStorageError("generation source is missing")
                encrypted_nonce = bytes(source.nonce)
                encrypted_payload = bytes(source.payload)
                fingerprint = job.request_fingerprint
                requested_card_count = job.requested_card_count
                job_provider = job.ai_provider
                job_model = job.ai_model

            source_bytes = SourceStorage.decrypt(
                encrypted_nonce, encrypted_payload, fingerprint
            )
            await self._update_stage(job_id, claim_token, "extracting_text", 20)
            extract = partial(
                PDFProcessor.extract_text_in_subprocess,
                source_bytes,
                max_pages=self.settings.pdf_max_pages,
                max_extracted_chars=self.settings.pdf_max_extracted_chars,
                timeout_seconds=self.settings.pdf_extraction_timeout_seconds,
                memory_limit_mb=self.settings.pdf_extraction_memory_limit_mb,
                ocr_enabled=self.settings.pdf_ocr_enabled,
                ocr_language=self.settings.pdf_ocr_language,
                ocr_dpi=self.settings.pdf_ocr_dpi,
                ocr_page_timeout_seconds=self.settings.pdf_ocr_page_timeout_seconds,
            )
            document = await asyncio.to_thread(extract)
            del source_bytes

            await self._update_stage(job_id, claim_token, "generating_cards", 40)
            job_settings = self.settings.model_copy(
                update={"flashcard_ai_provider": job_provider, "flashcard_ai_model": job_model}
            )
            graph = create_flashcard_graph(
                settings=job_settings,
                provider_semaphore=self.provider_semaphore,
                rate_governor=self.provider_rate_governor,
            )
            graph_holder["graph"] = graph
            result = await graph.ainvoke(
                {
                    "pdf_document": document,
                    "target_count": requested_card_count,
                },
            )
            cards_data = result.get("final_cards") or []
            if len(cards_data) != requested_card_count:
                raise ModelGenerationFailure("the pipeline returned an incomplete card set")
            await self._update_stage(job_id, claim_token, "persisting", 90)
            await self._finish_success(job_id, claim_token, cards_data, telemetry=result)

    async def _finish_success(
        self,
        job_id: UUID,
        claim_token: str,
        cards_data: list[dict],
        telemetry: dict | None = None,
    ) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                job = await self._claimed_job(db, job_id, claim_token, for_update=True)
                set_data = FlashcardSetCreate(
                    subject_id=job.subject_id,
                    title=job.set_title,
                    description=job.set_description,
                )
                flashcard_set = await SubjectService.create_flashcard_set(
                    db,
                    set_data,
                    source_pdf_name=job.source_pdf_name,
                    generation_job_id=job.id,
                )
                created_cards = await FlashcardService.create_flashcards_bulk(
                    db, cards_data, flashcard_set.id
                )
                await db.execute(
                    delete(GenerationJobSource).where(GenerationJobSource.job_id == job.id)
                )
                now = utcnow()
                job.status = GenerationJobStatus.COMPLETED.value
                job.stage = "completed"
                job.progress = 100
                job.generated_card_count = len(created_cards)
                job.accepted_card_count = len(created_cards)
                self._apply_telemetry(job, telemetry or {})
                job.limit_reason_code = None
                job.limit_reason_message = None
                job.completed_at = now
                job.heartbeat_at = now
                job.lease_expires_at = None
                job.worker_id = None
                job.claim_token = None
                job.error_code = None
                job.error_message = None
                job.error_retryable = False
                job.updated_at = now

        logger.info("generation_completed", extra={"job_id": job_id, "card_count": len(created_cards), "input_tokens": int((telemetry or {}).get("actual_input_tokens") or 0), "output_tokens": int((telemetry or {}).get("actual_output_tokens") or 0), "cost_microusd": int((telemetry or {}).get("actual_cost_microusd") or 0)})

    async def _finish_cancelled(self, job_id: UUID, claim_token: str) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                try:
                    job = await self._claimed_job(db, job_id, claim_token, for_update=True)
                except JobCancellationRequested:
                    job = await db.scalar(
                        select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()
                    )
                    if job is None or job.claim_token != claim_token:
                        return
                except LeaseLost:
                    return
                await db.execute(
                    delete(GenerationJobSource).where(GenerationJobSource.job_id == job.id)
                )
                now = utcnow()
                job.status = GenerationJobStatus.CANCELLED.value
                job.stage = "cancelled"
                job.progress = 100
                job.completed_at = now
                job.lease_expires_at = None
                job.worker_id = None
                job.claim_token = None
                job.error_code = None
                job.error_message = None
                job.error_retryable = False
                job.updated_at = now

        logger.info("generation_cancelled", extra={"job_id": job_id})

    async def _finish_failure(
        self,
        job_id: UUID,
        claim_token: str,
        *,
        code: str,
        message: str,
        retryable: bool,
        auto_retry: bool = True,
        telemetry: dict | None = None,
    ) -> None:
        async with self.session_factory() as db:
            async with db.begin():
                try:
                    job = await self._claimed_job(db, job_id, claim_token, for_update=True)
                except JobCancellationRequested:
                    job = await db.scalar(
                        select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()
                    )
                    if job is None or job.claim_token != claim_token:
                        return
                    await db.execute(
                        delete(GenerationJobSource).where(
                            GenerationJobSource.job_id == job.id
                        )
                    )
                    now = utcnow()
                    job.status = GenerationJobStatus.CANCELLED.value
                    job.stage = "cancelled"
                    job.progress = 100
                    job.completed_at = now
                    job.error_retryable = False
                except LeaseLost:
                    return
                else:
                    now = utcnow()
                    self._apply_telemetry(job, telemetry or {})
                    if code in {
                        "ai_input_token_limit",
                        "ai_output_token_limit",
                        "ai_context_window_limit",
                        "ai_estimated_cost_limit",
                        "ai_cost_limit",
                        "insufficient_grounded_cards",
                    }:
                        job.limit_reason_code = code
                        job.limit_reason_message = message
                    if auto_retry and retryable and job.attempt_count < job.max_attempts:
                        cap = min(
                            self.settings.generation_retry_max_seconds,
                            self.settings.generation_retry_base_seconds
                            * (2 ** max(0, job.attempt_count - 1)),
                        )
                        job.status = GenerationJobStatus.QUEUED.value
                        job.stage = "retry_wait"
                        job.available_at = now + timedelta(seconds=random.uniform(0, cap))
                        job.error_code = code
                        job.error_message = message
                        job.error_retryable = True
                    else:
                        job.status = GenerationJobStatus.FAILED.value
                        job.stage = "failed"
                        job.progress = 100
                        job.completed_at = now
                        job.error_code = code
                        job.error_message = message
                        job.error_retryable = retryable
                        source = await db.scalar(
                            select(GenerationJobSource)
                            .where(GenerationJobSource.job_id == job.id)
                            .with_for_update()
                        )
                        if retryable and source is not None:
                            source.expires_at = now + timedelta(
                                hours=self.settings.generation_source_retry_retention_hours
                            )
                        else:
                            await db.execute(
                                delete(GenerationJobSource).where(
                                    GenerationJobSource.job_id == job.id
                                )
                            )
                job.lease_expires_at = None
                job.worker_id = None
                job.claim_token = None
                job.updated_at = utcnow()

        logger.warning("generation_failed", extra={"job_id": job_id, "error_code": safe_error_code(code)})

    @staticmethod
    def _apply_telemetry(job: GenerationJob, telemetry: dict) -> None:
        job.estimated_input_tokens = max(
            job.estimated_input_tokens, int(telemetry.get("estimated_input_tokens") or 0)
        )
        job.estimated_output_tokens = max(
            job.estimated_output_tokens, int(telemetry.get("estimated_output_tokens") or 0)
        )
        job.estimated_request_count = max(
            job.estimated_request_count or 0,
            int(telemetry.get("estimated_request_count") or 0),
        )
        job.provider_request_count = (job.provider_request_count or 0) + int(
            telemetry.get("provider_request_count") or 0
        )
        job.provider_retry_count = (job.provider_retry_count or 0) + int(
            telemetry.get("provider_retry_count") or 0
        )
        job.provider_rate_limit_wait_milliseconds = (
            job.provider_rate_limit_wait_milliseconds or 0
        ) + int(
            telemetry.get("provider_rate_limit_wait_milliseconds") or 0
        )
        job.cached_input_tokens = (job.cached_input_tokens or 0) + int(
            telemetry.get("cached_input_tokens") or 0
        )
        stage_counts = dict(job.provider_request_counts_by_stage or {})
        for stage, raw_count in (
            telemetry.get("provider_request_counts_by_stage") or {}
        ).items():
            if stage not in {"summary_map", "summary_reduce", "card_generation"}:
                continue
            if not isinstance(raw_count, int) or isinstance(raw_count, bool):
                continue
            count = raw_count
            if count < 0:
                continue
            stage_counts[stage] = int(stage_counts.get(stage, 0)) + count
        job.provider_request_counts_by_stage = stage_counts
        estimated_cost = telemetry.get("estimated_cost_microusd")
        if estimated_cost is not None:
            job.estimated_cost_microusd = max(
                job.estimated_cost_microusd or 0, int(estimated_cost)
            )
        input_tokens = int(telemetry.get("actual_input_tokens") or 0)
        output_tokens = int(telemetry.get("actual_output_tokens") or 0)
        if input_tokens or job.actual_input_tokens is not None:
            job.actual_input_tokens = (job.actual_input_tokens or 0) + input_tokens
        if output_tokens or job.actual_output_tokens is not None:
            job.actual_output_tokens = (job.actual_output_tokens or 0) + output_tokens
        actual_cost = telemetry.get("actual_cost_microusd")
        if actual_cost is not None:
            job.actual_cost_microusd = (job.actual_cost_microusd or 0) + int(actual_cost)
        job.usage_estimated = job.usage_estimated or bool(telemetry.get("usage_estimated"))
        job.rejected_card_count += int(telemetry.get("rejected_card_count") or 0)

    async def recover_and_cleanup(self) -> None:
        """Expire abandoned uploads/sources and recover dead worker leases."""

        async with self.session_factory() as db:
            async with db.begin():
                now = utcnow()
                awaiting = list(
                    (
                        await db.scalars(
                            select(GenerationJob)
                            .where(
                                GenerationJob.status
                                == GenerationJobStatus.AWAITING_UPLOAD.value,
                                GenerationJob.upload_expires_at <= now,
                            )
                            .with_for_update()
                            .limit(100)
                        )
                    ).all()
                )
                for job in awaiting:
                    job.status = GenerationJobStatus.CANCELLED.value
                    job.stage = "upload_expired"
                    job.progress = 100
                    job.completed_at = now
                    job.error_code = "upload_reservation_expired"
                    job.error_message = "The PDF upload reservation expired."
                    job.error_retryable = False
                    job.updated_at = now

                expired_query = (
                    select(GenerationJob)
                    .where(
                        GenerationJob.status == GenerationJobStatus.RUNNING.value,
                        GenerationJob.lease_expires_at <= now,
                    )
                    .limit(100)
                )
                if db.get_bind().dialect.name == "postgresql":
                    expired_query = expired_query.with_for_update(skip_locked=True)
                else:
                    expired_query = expired_query.with_for_update()
                expired = list((await db.scalars(expired_query)).all())
                for job in expired:
                    source = await db.scalar(
                        select(GenerationJobSource)
                        .where(GenerationJobSource.job_id == job.id)
                        .with_for_update()
                    )
                    if job.cancellation_requested_at is not None:
                        job.status = GenerationJobStatus.CANCELLED.value
                        job.stage = "cancelled"
                        job.progress = 100
                        job.completed_at = now
                        if source is not None:
                            await db.delete(source)
                        job.error_retryable = False
                    elif job.attempt_count < job.max_attempts and source is not None:
                        cap = min(
                            self.settings.generation_retry_max_seconds,
                            self.settings.generation_retry_base_seconds
                            * (2 ** max(0, job.attempt_count - 1)),
                        )
                        job.status = GenerationJobStatus.QUEUED.value
                        job.stage = "retry_wait"
                        job.available_at = now + timedelta(seconds=random.uniform(0, cap))
                        job.error_code = "worker_lease_expired"
                        job.error_message = "The worker stopped; the job will be retried."
                        job.error_retryable = True
                    else:
                        job.status = GenerationJobStatus.FAILED.value
                        job.stage = "failed"
                        job.progress = 100
                        job.completed_at = now
                        job.error_code = "worker_lease_expired"
                        job.error_message = "The worker stopped before the job completed."
                        job.error_retryable = source is not None
                        if source is not None:
                            source.expires_at = now + timedelta(
                                hours=self.settings.generation_source_retry_retention_hours
                            )
                    job.lease_expires_at = None
                    job.worker_id = None
                    job.claim_token = None
                    job.updated_at = now

                expired_sources = list(
                    (
                        await db.scalars(
                            select(GenerationJobSource)
                            .where(
                                GenerationJobSource.expires_at.is_not(None),
                                GenerationJobSource.expires_at <= now,
                            )
                            .with_for_update()
                            .limit(100)
                        )
                    ).all()
                )
                for source in expired_sources:
                    job = await db.get(GenerationJob, source.job_id)
                    if job is not None:
                        job.error_retryable = False
                        job.updated_at = now
                    await db.delete(source)

                missing_source_query = (
                    select(GenerationJob)
                    .outerjoin(
                        GenerationJobSource,
                        GenerationJobSource.job_id == GenerationJob.id,
                    )
                    .where(
                        GenerationJob.status == GenerationJobStatus.QUEUED.value,
                        GenerationJobSource.job_id.is_(None),
                    )
                    .limit(100)
                )
                if db.get_bind().dialect.name == "postgresql":
                    # PostgreSQL rejects an unqualified FOR UPDATE across a
                    # LEFT JOIN because the nullable source side cannot be
                    # locked. Only the generation job is mutated here.
                    missing_source_query = missing_source_query.with_for_update(
                        of=GenerationJob, skip_locked=True
                    )
                else:
                    missing_source_query = missing_source_query.with_for_update()
                missing_source_jobs = list(
                    (await db.scalars(missing_source_query)).all()
                )
                for job in missing_source_jobs:
                    job.status = GenerationJobStatus.FAILED.value
                    job.stage = "failed"
                    job.progress = 100
                    job.completed_at = now
                    job.error_code = "source_missing"
                    job.error_message = "The temporary PDF is no longer available."
                    job.error_retryable = False
                    job.updated_at = now
