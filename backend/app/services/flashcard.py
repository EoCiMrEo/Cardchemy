"""
flashcard.py - Flashcard Service

Business logic for flashcard CRUD and study progress tracking.
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from fastapi import HTTPException, status

from app.models.flashcard import Flashcard, StudyProgress, CardStatus
from app.schemas.flashcard import FlashcardCreate, FlashcardUpdate, StudyProgressUpdate


class FlashcardService:
    """Service for flashcard and study progress operations."""
    
    # ============================================
    # Flashcard CRUD
    # ============================================
    
    @staticmethod
    async def create_flashcard(
        db: AsyncSession,
        data: FlashcardCreate,
        confidence_score: float = 0.0,
        source_chunk: Optional[str] = None
    ) -> Flashcard:
        """
        Create a new flashcard.
        
        Args:
            db: Database session
            data: Flashcard content (front/back)
            confidence_score: AI confidence (0-1), used for auto-approval
            source_chunk: Original text the card was generated from
        """
        flashcard = Flashcard(
            set_id=data.set_id,
            front_content=data.front_content,
            back_content=data.back_content,
            options=data.options,
            confidence_score=confidence_score,
            source_chunk=source_chunk,
            is_approved=confidence_score >= 0.7,  # Auto-approve high confidence
        )
        
        db.add(flashcard)
        await db.commit()
        await db.refresh(flashcard)
        
        return flashcard
    
    @staticmethod
    async def create_flashcards_bulk(
        db: AsyncSession,
        flashcards_data: List[dict],
        set_id: UUID
    ) -> List[Flashcard]:
        """
        Create multiple flashcards at once.
        
        This is more efficient than creating one at a time
        when generating from a PDF.
        
        Args:
            db: Database session
            flashcards_data: List of dicts with front/back/confidence/source
            set_id: The flashcard set to add to
            
        Returns:
            List of created Flashcard objects
        """
        flashcards = []
        
        for data in flashcards_data:
            confidence = data.get("confidence_score", 0.0)
            flashcard = Flashcard(
                set_id=set_id,
                front_content=data["front_content"],
                back_content=data["back_content"],
                options=data.get("options"),
                confidence_score=confidence,
                source_chunk=data.get("source_chunk"),
                is_approved=confidence >= 0.7,
            )
            flashcards.append(flashcard)
        
        db.add_all(flashcards)
        await db.commit()
        
        # Refresh all to get IDs
        for flashcard in flashcards:
            await db.refresh(flashcard)
        
        return flashcards
    
    @staticmethod
    async def get_flashcard(db: AsyncSession, flashcard_id: UUID) -> Optional[Flashcard]:
        """Get a flashcard by ID."""
        result = await db.execute(
            select(Flashcard).where(Flashcard.id == flashcard_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_set_flashcards(
        db: AsyncSession,
        set_id: UUID,
        only_approved: bool = False
    ) -> List[Flashcard]:
        """
        Get all flashcards in a set.
        
        Args:
            db: Database session
            set_id: Flashcard set ID
            only_approved: If True, only return approved cards (for students)
        """
        query = select(Flashcard).where(Flashcard.set_id == set_id)
        
        if only_approved:
            query = query.where(Flashcard.is_approved == True)
        
        query = query.order_by(Flashcard.created_at)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def update_flashcard(
        db: AsyncSession,
        flashcard: Flashcard,
        data: FlashcardUpdate
    ) -> Flashcard:
        """Update a flashcard."""
        if data.front_content is not None:
            flashcard.front_content = data.front_content
        if data.back_content is not None:
            flashcard.back_content = data.back_content
        if data.options is not None:
            flashcard.options = data.options
        if data.is_approved is not None:
            flashcard.is_approved = data.is_approved
        
        await db.commit()
        await db.refresh(flashcard)
        
        return flashcard
    
    @staticmethod
    async def delete_flashcard(db: AsyncSession, flashcard: Flashcard) -> None:
        """Delete a flashcard."""
        await db.delete(flashcard)
        await db.commit()
    
    @staticmethod
    async def approve_all_flashcards(
        db: AsyncSession,
        set_id: UUID,
        min_confidence: float = 0.0
    ) -> int:
        """
        Approve all flashcards in a set above a confidence threshold.
        
        Returns:
            Number of flashcards approved
        """
        result = await db.execute(
            select(Flashcard)
            .where(Flashcard.set_id == set_id)
            .where(Flashcard.is_approved == False)
            .where(Flashcard.confidence_score >= min_confidence)
        )
        flashcards = list(result.scalars().all())
        
        for flashcard in flashcards:
            flashcard.is_approved = True
        
        await db.commit()
        
        return len(flashcards)
    
    # ============================================
    # Study Progress Management
    # ============================================
    
    @staticmethod
    async def get_or_create_progress(
        db: AsyncSession,
        student_id: UUID,
        flashcard_id: UUID
    ) -> StudyProgress:
        """
        Get existing progress or create new record for a flashcard.
        
        This is called when a student starts studying a card.
        """
        result = await db.execute(
            select(StudyProgress)
            .where(StudyProgress.student_id == student_id)
            .where(StudyProgress.flashcard_id == flashcard_id)
        )
        progress = result.scalar_one_or_none()
        
        if not progress:
            progress = StudyProgress(
                student_id=student_id,
                flashcard_id=flashcard_id,
                status=CardStatus.NEW.value,
            )
            db.add(progress)
            await db.commit()
            await db.refresh(progress)
        
        return progress
    
    @staticmethod
    async def update_progress(
        db: AsyncSession,
        student_id: UUID,
        data: StudyProgressUpdate
    ) -> StudyProgress:
        """
        Update study progress after answering a card.
        
        This implements a simplified SM-2 spaced repetition algorithm:
        
        - quality 0-2: Card was hard, reset interval
        - quality 3-4: Card was okay, increase interval moderately  
        - quality 5: Card was easy, increase interval significantly
        
        The ease_factor adjusts how quickly intervals grow.
        """
        progress = await FlashcardService.get_or_create_progress(
            db, student_id, data.flashcard_id
        )
        
        # Update statistics
        if data.is_correct:
            progress.correct_count += 1
        else:
            progress.incorrect_count += 1
        
        # SM-2 Algorithm (simplified)
        quality = data.quality
        
        if quality < 3:
            # Failed - reset to learning
            progress.interval_days = 0
            progress.status = CardStatus.LEARNING.value
        else:
            # Passed - increase interval
            if progress.interval_days == 0:
                progress.interval_days = 1
            elif progress.interval_days == 1:
                progress.interval_days = 6
            else:
                progress.interval_days = round(progress.interval_days * progress.ease_factor)
            
            # Update ease factor based on quality
            # EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
            progress.ease_factor = max(
                1.3,
                progress.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
            )
            
            # Update status based on interval
            if progress.interval_days >= 21:
                progress.status = CardStatus.MASTERED.value
            elif progress.interval_days >= 7:
                progress.status = CardStatus.REVIEW.value
            else:
                progress.status = CardStatus.LEARNING.value
        
        # Schedule next review
        progress.next_review = datetime.utcnow() + timedelta(days=progress.interval_days)
        progress.last_reviewed = datetime.utcnow()
        
        await db.commit()
        await db.refresh(progress)
        
        return progress
    
    @staticmethod
    async def get_due_cards(
        db: AsyncSession,
        student_id: UUID,
        set_id: UUID,
        limit: int = 20
    ) -> List[Flashcard]:
        """
        Get flashcards that are due for review.
        
        Includes:
        - New cards (never studied)
        - Cards with next_review <= now
        
        This powers the study session - students see a mix of
        new and review cards.
        """
        now = datetime.utcnow()
        
        # Get all approved flashcards in the set
        all_cards_result = await db.execute(
            select(Flashcard)
            .where(Flashcard.set_id == set_id)
            .where(Flashcard.is_approved == True)
        )
        all_cards = {card.id: card for card in all_cards_result.scalars().all()}
        
        # Get student's progress for these cards
        progress_result = await db.execute(
            select(StudyProgress)
            .where(StudyProgress.student_id == student_id)
            .where(StudyProgress.flashcard_id.in_(all_cards.keys()))
        )
        progress_map = {p.flashcard_id: p for p in progress_result.scalars().all()}
        
        due_cards = []
        
        for card_id, card in all_cards.items():
            progress = progress_map.get(card_id)
            
            if not progress:
                # New card - always due
                due_cards.append(card)
            elif progress.next_review is None or progress.next_review <= now:
                # Review card - due
                due_cards.append(card)
        
        # Limit results
        return due_cards[:limit]
    
    @staticmethod
    async def get_set_progress(
        db: AsyncSession,
        student_id: UUID,
        set_id: UUID
    ) -> dict:
        """
        Get overall progress statistics for a flashcard set.
        
        Returns:
            Dict with progress stats (total, new, learning, review, mastered, completion %)
        """
        # Get all approved cards
        cards_result = await db.execute(
            select(Flashcard)
            .where(Flashcard.set_id == set_id)
            .where(Flashcard.is_approved == True)
        )
        cards = list(cards_result.scalars().all())
        total_cards = len(cards)
        
        if total_cards == 0:
            return {
                "total": 0,
                "new": 0,
                "learning": 0,
                "review": 0,
                "mastered": 0,
                "completion_percentage": 0.0,
            }
        
        card_ids = [card.id for card in cards]
        
        # Get progress for all cards
        progress_result = await db.execute(
            select(StudyProgress)
            .where(StudyProgress.student_id == student_id)
            .where(StudyProgress.flashcard_id.in_(card_ids))
        )
        progress_list = list(progress_result.scalars().all())
        
        # Count by status
        status_counts = {
            CardStatus.NEW.value: 0,
            CardStatus.LEARNING.value: 0,
            CardStatus.REVIEW.value: 0,
            CardStatus.MASTERED.value: 0,
        }
        
        studied_ids = set()
        for progress in progress_list:
            status_counts[progress.status] = status_counts.get(progress.status, 0) + 1
            # Only count as "studied" if the student got at least one correct answer
            if progress.correct_count >= 1:
                studied_ids.add(progress.flashcard_id)
        
        # Cards without progress are "new"
        new_count = total_cards - len(studied_ids)
        
        # Count correct answers across all studied cards
        total_correct = sum(p.correct_count for p in progress_list)
        total_studied = len(studied_ids)
        
        # Completion = (review + mastered) / total
        completion = (status_counts[CardStatus.REVIEW.value] + status_counts[CardStatus.MASTERED.value]) / total_cards
        
        return {
            "total": total_cards,
            "new": new_count,
            "learning": status_counts[CardStatus.LEARNING.value],
            "review": status_counts[CardStatus.REVIEW.value],
            "mastered": status_counts[CardStatus.MASTERED.value],
            "studied": total_studied,  # Cards the student has seen at least once
            "correct_count": total_correct,  # Total correct answers
            "completion_percentage": round(completion * 100, 1),
        }
