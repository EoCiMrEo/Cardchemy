"""Flashcard CRUD, validated answer handling, and spaced-repetition queries."""

from __future__ import annotations

from datetime import timedelta
from typing import Iterable
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flashcard import CardStatus, CardType, Enrollment, Flashcard, StudyProgress
from app.models.subject import FlashcardSet
from app.schemas.flashcard import (
    FlashcardCreate,
    FlashcardUpdate,
    StudyAnswerResponse,
    StudyProgressResponse,
    StudyProgressUpdate,
)
from app.time_utils import utcnow


class FlashcardService:
    """Service methods never commit; route-level units of work own commits."""

    @staticmethod
    async def create_flashcard(
        db: AsyncSession,
        data: FlashcardCreate,
        confidence_score: float = 0.0,
        source_chunk: str | None = None,
    ) -> Flashcard:
        if not 0 <= confidence_score <= 1:
            raise ValueError("confidence_score must be between 0 and 1")
        if source_chunk is not None and len(source_chunk) > 10_000:
            raise ValueError("source_chunk cannot exceed 10000 characters")
        flashcard = Flashcard(
            set_id=data.set_id,
            front_content=data.front_content,
            back_content=data.back_content,
            options=list(data.options),
            card_type=data.card_type,
            confidence_score=confidence_score,
            source_chunk=source_chunk,
            is_approved=confidence_score >= 0.7,
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

        validated: list[tuple[FlashcardCreate, float, str | None]] = []
        for raw in flashcards_data:
            confidence = float(raw.get("confidence_score", 0.0))
            if not 0 <= confidence <= 1:
                raise ValueError("confidence_score must be between 0 and 1")
            source = raw.get("source_chunk")
            if source is not None:
                source = str(source).strip() or None
                if source and len(source) > 10_000:
                    raise ValueError("source_chunk cannot exceed 10000 characters")
            card = FlashcardCreate(
                set_id=set_id,
                front_content=raw["front_content"],
                back_content=raw["back_content"],
                options=raw.get("options"),
                card_type=raw.get("card_type", CardType.MULTIPLE_CHOICE.value),
            )
            validated.append((card, confidence, source))

        flashcards = [
            Flashcard(
                set_id=set_id,
                front_content=card.front_content,
                back_content=card.back_content,
                options=list(card.options),
                card_type=card.card_type,
                confidence_score=confidence,
                source_chunk=source,
                is_approved=confidence >= 0.7,
            )
            for card, confidence, source in validated
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
        min_confidence: float = 0.0,
    ) -> int:
        if not 0 <= min_confidence <= 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="min_confidence must be between 0 and 1",
            )
        result = await db.execute(
            select(Flashcard).where(
                Flashcard.set_id == set_id,
                Flashcard.is_approved.is_(False),
                Flashcard.confidence_score >= min_confidence,
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
    def _resolve_answer(flashcard: Flashcard, data: StudyProgressUpdate) -> tuple[bool, int, str, int]:
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
        return is_correct, 5 if is_correct else 1, options[correct_index], correct_index

    @staticmethod
    async def update_progress(
        db: AsyncSession,
        student_id: UUID,
        flashcard: Flashcard,
        data: StudyProgressUpdate,
    ) -> StudyAnswerResponse:
        is_correct, quality, correct_option, correct_index = FlashcardService._resolve_answer(flashcard, data)
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
        return StudyAnswerResponse(
            progress=StudyProgressResponse.model_validate(progress),
            is_correct=is_correct,
            quality=quality,
            correct_option=correct_option,
            correct_option_index=correct_index,
        )

    @staticmethod
    async def get_studyable_cards(
        db: AsyncSession,
        student_id: UUID,
        flashcard_ids: Iterable[UUID],
    ) -> dict[UUID, Flashcard]:
        """Fetch and lock an authorized batch in a deterministic order."""

        unique_ids = sorted(set(flashcard_ids), key=str)
        if not unique_ids:
            return {}
        query = (
            select(Flashcard)
            .join(FlashcardSet, FlashcardSet.id == Flashcard.set_id)
            .join(
                Enrollment,
                and_(
                    Enrollment.subject_id == FlashcardSet.subject_id,
                    Enrollment.student_id == student_id,
                ),
            )
            .where(
                Flashcard.id.in_(unique_ids),
                Flashcard.is_approved.is_(True),
                FlashcardSet.is_published.is_(True),
            )
            .order_by(Flashcard.id)
        )
        if db.get_bind().dialect.name == "postgresql":
            query = query.with_for_update(of=Flashcard)
        result = await db.execute(query)
        return {card.id: card for card in result.scalars().all()}

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
