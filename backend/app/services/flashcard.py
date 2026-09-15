"""Flashcard CRUD, validated answer handling, and spaced-repetition queries."""

from __future__ import annotations

from datetime import timedelta
import hashlib
import json
import re
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flashcard import (
    CardStatus,
    CardType,
    Flashcard,
    StudyAnswerSubmission,
    StudyProgress,
)
from app.schemas.flashcard import (
    FlashcardCreate,
    FlashcardUpdate,
    StudyAnswerResponse,
    StudyProgressResponse,
    StudyProgressUpdate,
)
from app.time_utils import utcnow


STUDY_IDEMPOTENCY_PATTERN = re.compile(r"^[\x21-\x7e]{8,128}$")


class FlashcardService:
    """Service methods never commit; route-level units of work own commits."""

    @staticmethod
    async def create_flashcard(
        db: AsyncSession,
        data: FlashcardCreate,
        quality_score: float = 0.0,
        source_snippet: str | None = None,
        source_page: int | None = None,
        source_section: str | None = None,
        is_approved: bool = False,
    ) -> Flashcard:
        if not 0 <= quality_score <= 1:
            raise ValueError("quality_score must be between 0 and 1")
        if source_snippet is not None and len(source_snippet) > 10_000:
            raise ValueError("source_snippet cannot exceed 10000 characters")
        if source_page is not None and source_page < 1:
            raise ValueError("source_page must be positive")
        if source_section is not None and len(source_section) > 255:
            raise ValueError("source_section cannot exceed 255 characters")
        flashcard = Flashcard(
            set_id=data.set_id,
            front_content=data.front_content,
            back_content=data.back_content,
            options=list(data.options),
            card_type=data.card_type,
            quality_score=quality_score,
            source_snippet=source_snippet,
            source_page=source_page,
            source_section=source_section,
            is_approved=is_approved,
        )
        db.add(flashcard)
        await db.flush()
        return flashcard

    @staticmethod
    async def create_flashcards_bulk(
        db: AsyncSession,
        flashcards_data: list[dict],
        set_id: UUID,
    ) -> list[Flashcard]:
        """Validate every generated card before staging the batch."""

        validated: list[tuple[FlashcardCreate, float, str | None, int | None, str | None]] = []
        for raw in flashcards_data:
            quality = float(raw.get("quality_score", 0.0))
            if not 0 <= quality <= 1:
                raise ValueError("quality_score must be between 0 and 1")
            source = raw.get("source_snippet")
            if source is not None:
                source = str(source).strip() or None
                if source and len(source) > 10_000:
                    raise ValueError("source_snippet cannot exceed 10000 characters")
            source_page = raw.get("source_page")
            if source_page is not None and (not isinstance(source_page, int) or source_page < 1):
                raise ValueError("source_page must be a positive integer")
            source_section = raw.get("source_section")
            if source_section is not None:
                source_section = str(source_section).strip() or None
                if source_section and len(source_section) > 255:
                    raise ValueError("source_section cannot exceed 255 characters")
            card = FlashcardCreate(
                set_id=set_id,
                front_content=raw["front_content"],
                back_content=raw["back_content"],
                options=raw.get("options"),
                card_type=raw.get("card_type", CardType.MULTIPLE_CHOICE.value),
            )
            validated.append((card, quality, source, source_page, source_section))

        flashcards = [
            Flashcard(
                set_id=set_id,
                front_content=card.front_content,
                back_content=card.back_content,
                options=list(card.options),
                card_type=card.card_type,
                quality_score=quality,
                source_snippet=source,
                source_page=source_page,
                source_section=source_section,
                is_approved=False,
            )
            for card, quality, source, source_page, source_section in validated
        ]
        db.add_all(flashcards)
        await db.flush()
        return flashcards

    @staticmethod
    async def get_flashcard(db: AsyncSession, flashcard_id: UUID) -> Flashcard | None:
        return await db.scalar(select(Flashcard).where(Flashcard.id == flashcard_id))

    @staticmethod
    async def get_set_flashcards(
        db: AsyncSession,
        set_id: UUID,
        only_approved: bool = False,
    ) -> list[Flashcard]:
        query = select(Flashcard).where(Flashcard.set_id == set_id)
        if only_approved:
            query = query.where(Flashcard.is_approved.is_(True))
        result = await db.execute(query.order_by(Flashcard.created_at, Flashcard.id))
        return list(result.scalars().all())

    @staticmethod
    async def update_flashcard(
        db: AsyncSession,
        flashcard: Flashcard,
        data: FlashcardUpdate,
    ) -> Flashcard:
        """Validate the merged card so partial edits cannot break invariants."""

        try:
            merged = FlashcardCreate(
                set_id=flashcard.set_id,
                front_content=(
                    data.front_content
                    if "front_content" in data.model_fields_set
                    else flashcard.front_content
                ),
                back_content=(
                    data.back_content
                    if "back_content" in data.model_fields_set
                    else flashcard.back_content
                ),
                options=(
                    data.options
                    if "options" in data.model_fields_set
                    else flashcard.options
                ),
                card_type=(
                    data.card_type
                    if "card_type" in data.model_fields_set
                    else flashcard.card_type
                ),
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=exc.errors(include_url=False),
            ) from exc
        flashcard.front_content = merged.front_content
        flashcard.back_content = merged.back_content
        flashcard.options = list(merged.options)
        flashcard.card_type = merged.card_type
        if "is_approved" in data.model_fields_set:
            flashcard.is_approved = data.is_approved
        await db.flush()
        return flashcard

    @staticmethod
    async def delete_flashcard(db: AsyncSession, flashcard: Flashcard) -> None:
        await db.delete(flashcard)
        await db.flush()

    @staticmethod
    async def approve_all_flashcards(
        db: AsyncSession,
        set_id: UUID,
    ) -> int:
        result = await db.execute(
            select(Flashcard).where(
                Flashcard.set_id == set_id,
                Flashcard.is_approved.is_(False),
            )
        )
        flashcards = list(result.scalars().all())
        for flashcard in flashcards:
            flashcard.is_approved = True
        await db.flush()
        return len(flashcards)

    @staticmethod
    async def _insert_progress_if_missing(
        db: AsyncSession,
        student_id: UUID,
        flashcard_id: UUID,
    ) -> None:
        values = {
            "id": uuid4(),
            "student_id": student_id,
            "flashcard_id": flashcard_id,
            "status": CardStatus.NEW.value,
            "ease_factor": 2.5,
            "interval_days": 0,
            "correct_count": 0,
            "incorrect_count": 0,
        }
        dialect = db.get_bind().dialect.name
        if dialect == "postgresql":
            statement = postgresql_insert(StudyProgress).values(**values).on_conflict_do_nothing(
                index_elements=["student_id", "flashcard_id"]
            )
        elif dialect == "sqlite":
            statement = sqlite_insert(StudyProgress).values(**values).on_conflict_do_nothing(
                index_elements=["student_id", "flashcard_id"]
            )
        else:
            raise RuntimeError(f"Unsupported database dialect for progress upsert: {dialect}")
        await db.execute(statement)

    @staticmethod
    async def get_or_create_progress(
        db: AsyncSession,
        student_id: UUID,
        flashcard_id: UUID,
    ) -> StudyProgress:
        """Race-safe UPSERT followed by a row lock for lossless updates."""

        await FlashcardService._insert_progress_if_missing(db, student_id, flashcard_id)
        query = select(StudyProgress).where(
            StudyProgress.student_id == student_id,
            StudyProgress.flashcard_id == flashcard_id,
        )
        if db.get_bind().dialect.name == "postgresql":
            query = query.with_for_update()
        progress = await db.scalar(query)
        if progress is None:
            raise RuntimeError("progress UPSERT did not produce a row")
        return progress

    @staticmethod
    def _resolve_answer(
        flashcard: Flashcard,
        data: StudyProgressUpdate,
    ) -> tuple[bool, int, str, int, int]:
        options = list(flashcard.options)
        correct_key = flashcard.back_content.strip().casefold()
        correct_index = next(
            index for index, option in enumerate(options) if option.strip().casefold() == correct_key
        )

        if data.selected_option_index is not None:
            if data.selected_option_index >= len(options):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="selected_option_index does not identify an option",
                )
            selected_index = data.selected_option_index
        elif data.selected_option is None:
            selected_index = -1
        else:
            selected_key = data.selected_option.strip().casefold()
            matches = [
                index for index, option in enumerate(options) if option.strip().casefold() == selected_key
            ]
            if len(matches) != 1:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="selected_option does not identify an option",
                )
            selected_index = matches[0]

        is_correct = selected_index == correct_index
        return (
            is_correct,
            5 if is_correct else 1,
            options[correct_index],
            correct_index,
            selected_index,
        )

    @staticmethod
    def _answer_submission_identity(
        idempotency_key: str,
        flashcard_id: UUID,
        selected_option_index: int,
    ) -> tuple[str, str]:
        if not STUDY_IDEMPOTENCY_PATTERN.fullmatch(idempotency_key):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "code": "invalid_idempotency_key",
                    "message": "Idempotency-Key must contain 8 to 128 visible ASCII characters.",
                },
            )
        key_hash = hashlib.sha256(idempotency_key.encode("ascii")).hexdigest()
        canonical_request = json.dumps(
            {
                "flashcard_id": str(flashcard_id),
                "selected_option_index": selected_option_index,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        fingerprint = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        return key_hash, fingerprint

    @staticmethod
    async def _reserve_answer_submission(
        db: AsyncSession,
        *,
        student_id: UUID,
        flashcard_id: UUID,
        key_hash: str,
        request_fingerprint: str,
    ) -> tuple[StudyAnswerSubmission, bool]:
        """Atomically reserve a key or return its completed receipt.

        PostgreSQL waits for an in-flight conflicting INSERT before returning
        from ``ON CONFLICT DO NOTHING``. Because the answer aggregate and the
        receipt are committed in one transaction, a concurrent caller then
        observes either the completed receipt or becomes the winner after a
        rollback.
        """

        receipt_id = uuid4()
        values = {
            "id": receipt_id,
            "student_id": student_id,
            "flashcard_id": flashcard_id,
            "idempotency_key_hash": key_hash,
            "request_fingerprint": request_fingerprint,
            "response_payload": {},
        }
        dialect = db.get_bind().dialect.name
        if dialect == "postgresql":
            statement = postgresql_insert(StudyAnswerSubmission).values(**values).on_conflict_do_nothing(
                index_elements=["student_id", "idempotency_key_hash"]
            )
        elif dialect == "sqlite":
            statement = sqlite_insert(StudyAnswerSubmission).values(**values).on_conflict_do_nothing(
                index_elements=["student_id", "idempotency_key_hash"]
            )
        else:
            raise RuntimeError(f"Unsupported database dialect for answer idempotency: {dialect}")

        inserted_id = await db.scalar(statement.returning(StudyAnswerSubmission.id))
        if inserted_id is not None:
            receipt = await db.get(StudyAnswerSubmission, inserted_id)
            if receipt is None:
                raise RuntimeError("answer receipt INSERT did not produce a row")
            return receipt, True

        receipt = await db.scalar(
            select(StudyAnswerSubmission).where(
                StudyAnswerSubmission.student_id == student_id,
                StudyAnswerSubmission.idempotency_key_hash == key_hash,
            )
        )
        if receipt is None:
            raise RuntimeError("conflicting answer receipt could not be loaded")
        if receipt.request_fingerprint != request_fingerprint:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "idempotency_key_reused",
                    "message": "This Idempotency-Key was already used for a different answer.",
                },
            )
        if not receipt.response_payload:
            raise RuntimeError("completed answer receipt has no response payload")
        return receipt, False

    @staticmethod
    async def update_progress(
        db: AsyncSession,
        student_id: UUID,
        flashcard: Flashcard,
        data: StudyProgressUpdate,
        idempotency_key: str,
    ) -> StudyAnswerResponse:
        (
            is_correct,
            quality,
            correct_option,
            correct_index,
            selected_index,
        ) = FlashcardService._resolve_answer(flashcard, data)
        key_hash, request_fingerprint = FlashcardService._answer_submission_identity(
            idempotency_key,
            data.flashcard_id,
            selected_index,
        )
        receipt, is_new = await FlashcardService._reserve_answer_submission(
            db,
            student_id=student_id,
            flashcard_id=data.flashcard_id,
            key_hash=key_hash,
            request_fingerprint=request_fingerprint,
        )
        if not is_new:
            return StudyAnswerResponse.model_validate(receipt.response_payload)

        progress = await FlashcardService.get_or_create_progress(db, student_id, data.flashcard_id)

        if is_correct:
            progress.correct_count += 1
        else:
            progress.incorrect_count += 1

        if quality < 3:
            progress.interval_days = 0
            progress.status = CardStatus.LEARNING.value
        else:
            if progress.interval_days == 0:
                progress.interval_days = 1
            elif progress.interval_days == 1:
                progress.interval_days = 6
            else:
                progress.interval_days = round(progress.interval_days * progress.ease_factor)
            progress.ease_factor = max(
                1.3,
                progress.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)),
            )
            if progress.interval_days >= 21:
                progress.status = CardStatus.MASTERED.value
            elif progress.interval_days >= 7:
                progress.status = CardStatus.REVIEW.value
            else:
                progress.status = CardStatus.LEARNING.value

        now = utcnow()
        progress.next_review = now + timedelta(days=progress.interval_days)
        progress.last_reviewed = now
        await db.flush()
        answer = StudyAnswerResponse(
            progress=StudyProgressResponse.model_validate(progress),
            is_correct=is_correct,
            quality=quality,
            correct_option=correct_option,
            correct_option_index=correct_index,
        )
        receipt.response_payload = answer.model_dump(mode="json")
        await db.flush()
        return answer

    @staticmethod
    async def get_due_cards(
        db: AsyncSession,
        student_id: UUID,
        set_id: UUID,
        limit: int = 20,
    ) -> list[Flashcard]:
        """Use indexed database filtering, deterministic ordering, and LIMIT."""

        now = utcnow()
        query = (
            select(Flashcard)
            .outerjoin(
                StudyProgress,
                and_(
                    StudyProgress.flashcard_id == Flashcard.id,
                    StudyProgress.student_id == student_id,
                ),
            )
            .where(
                Flashcard.set_id == set_id,
                Flashcard.is_approved.is_(True),
                or_(
                    StudyProgress.id.is_(None),
                    StudyProgress.next_review.is_(None),
                    StudyProgress.next_review <= now,
                ),
            )
            .order_by(
                case((StudyProgress.id.is_not(None), 0), else_=1),
                StudyProgress.next_review.asc().nulls_last(),
                Flashcard.created_at,
                Flashcard.id,
            )
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_review_cards(
        db: AsyncSession,
        student_id: UUID,
        set_id: UUID,
        limit: int = 20,
    ) -> list[Flashcard]:
        """Return approved cards for a deliberate review-all session.

        Least-recently reviewed cards come first, followed by stable card
        creation/ID ordering. This mode intentionally ignores ``next_review``.
        """

        query = (
            select(Flashcard)
            .outerjoin(
                StudyProgress,
                and_(
                    StudyProgress.flashcard_id == Flashcard.id,
                    StudyProgress.student_id == student_id,
                ),
            )
            .where(
                Flashcard.set_id == set_id,
                Flashcard.is_approved.is_(True),
            )
            .order_by(
                StudyProgress.last_reviewed.asc().nulls_first(),
                Flashcard.created_at,
                Flashcard.id,
            )
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_set_progress(db: AsyncSession, student_id: UUID, set_id: UUID) -> dict:
        total_cards = int(
            await db.scalar(
                select(func.count(Flashcard.id)).where(
                    Flashcard.set_id == set_id,
                    Flashcard.is_approved.is_(True),
                )
            )
            or 0
        )
        if total_cards == 0:
            return {
                "total": 0,
                "new": 0,
                "learning": 0,
                "review": 0,
                "mastered": 0,
                "studied": 0,
                "correct_count": 0,
                "completion_percentage": 0.0,
                "mastery_percentage": 0.0,
            }

        rows = await db.execute(
            select(StudyProgress.status, func.count(StudyProgress.id), func.sum(StudyProgress.correct_count))
            .join(Flashcard, Flashcard.id == StudyProgress.flashcard_id)
            .where(
                StudyProgress.student_id == student_id,
                StudyProgress.last_reviewed.is_not(None),
                Flashcard.set_id == set_id,
                Flashcard.is_approved.is_(True),
            )
            .group_by(StudyProgress.status)
        )
        counts = {status_value: 0 for status_value in CardStatus}
        studied = 0
        correct_count = 0
        for status_value, count_value, correct_value in rows:
            counts[CardStatus(status_value)] = int(count_value)
            studied += int(count_value)
            correct_count += int(correct_value or 0)

        new_count = total_cards - studied
        mastery_count = counts[CardStatus.REVIEW] + counts[CardStatus.MASTERED]
        return {
            "total": total_cards,
            "new": new_count,
            "learning": counts[CardStatus.LEARNING],
            "review": counts[CardStatus.REVIEW],
            "mastered": counts[CardStatus.MASTERED],
            "studied": studied,
            "correct_count": correct_count,
            "completion_percentage": round(studied / total_cards * 100, 1),
            "mastery_percentage": round(mastery_count / total_cards * 100, 1),
        }
