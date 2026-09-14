"""
study.py - Study Router

API endpoints for student study sessions and progress tracking.

Endpoints:
- GET /study/sets/{set_id}/session - Get cards due for study
- POST /study/progress - Submit study result for a card
- GET /study/sets/{set_id}/progress - Get progress stats for a set
- POST /study/sync - Sync offline progress (for PWA)
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_student
from app.schemas.flashcard import (
    FlashcardResponse,
    StudyProgressUpdate,
    StudyProgressResponse,
    StudySessionResponse,
)
from app.services.flashcard import FlashcardService
from app.services.subject import SubjectService

router = APIRouter(prefix="/study", tags=["Study"])


@router.get("/sets/{set_id}/session", response_model=StudySessionResponse)
async def get_study_session(
    set_id: UUID,
    limit: int = 20,
    user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db)
):
    """
    Get flashcards due for study.
    
    Returns a mix of:
    - New cards (never studied before)
    - Review cards (due for review based on spaced repetition)
    
    Query params:
        - limit: Maximum number of cards to return (default 20)
    """
    # Verify access to the set
    flashcard_set = await SubjectService.get_flashcard_set(db, set_id)
    if not flashcard_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard set not found"
        )
    
    await SubjectService.check_subject_access(db, flashcard_set.subject_id, user)
    
    # Check if set is published (required for students)
    if not flashcard_set.is_published:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This flashcard set is not yet published"
        )
    
    # Get due cards
    cards = await FlashcardService.get_due_cards(db, user.id, set_id, limit)
    
    # Get stats
    progress = await FlashcardService.get_set_progress(db, user.id, set_id)
    
    return StudySessionResponse(
        cards=cards,
        total_due=len(cards),
        new_cards=progress["new"],
        review_cards=progress["learning"] + progress["review"],
        time_limit=flashcard_set.time_limit,
    )


@router.post("/progress", response_model=StudyProgressResponse)
async def update_study_progress(
    data: StudyProgressUpdate,
    user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db)
):
    """
    Submit study result for a flashcard.
    
    Call this after the student answers a card.
    This updates the spaced repetition schedule.
    
    Request body:
        - flashcard_id: The card that was studied
        - is_correct: Did the student get it right?
        - quality: Self-rating 0-5 (for SM-2 algorithm)
            - 0: Complete blackout
            - 1: Wrong, but remembered seeing answer
            - 2: Wrong, but answer seemed easy
            - 3: Correct with difficulty
            - 4: Correct after hesitation
            - 5: Perfect response
    """
    # Verify the flashcard exists and user has access
    flashcard = await FlashcardService.get_flashcard(db, data.flashcard_id)
    
    if not flashcard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard not found"
        )
    
    flashcard_set = await SubjectService.get_flashcard_set(db, flashcard.set_id)
    if not flashcard_set or not flashcard_set.is_published or not flashcard.is_approved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard not found",
        )
    await SubjectService.check_subject_access(db, flashcard_set.subject_id, user)
    
    # Update progress
    progress = await FlashcardService.update_progress(db, user.id, data)
    
    return progress


@router.get("/sets/{set_id}/progress")
async def get_set_progress(
    set_id: UUID,
    user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db)
):
    """
    Get overall progress statistics for a flashcard set.
    
    Returns:
        - total: Total number of cards
        - new: Cards never studied
        - learning: Cards being learned
        - review: Cards in review phase
        - mastered: Cards mastered
        - completion_percentage: Percentage of cards mastered/reviewed
    """
    # Verify access
    flashcard_set = await SubjectService.get_flashcard_set(db, set_id)
    if not flashcard_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard set not found"
        )
    
    await SubjectService.check_subject_access(db, flashcard_set.subject_id, user)
    if not flashcard_set.is_published:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard set not found",
        )
    
    progress = await FlashcardService.get_set_progress(db, user.id, set_id)
    
    return progress


@router.post("/sync")
async def sync_offline_progress(
    progress_updates: List[StudyProgressUpdate],
    user: User = Depends(get_current_student),
    db: AsyncSession = Depends(get_db)
):
    """
    Sync offline study progress.
    
    When the PWA is offline, it stores progress locally.
    When back online, it calls this endpoint to sync all updates.
    
    Request body:
        List of progress updates (same format as single update)
    
    Returns:
        Number of updates synced
    """
    synced = 0
    errors = []
    
    for update in progress_updates:
        try:
            flashcard = await FlashcardService.get_flashcard(db, update.flashcard_id)
            if not flashcard or not flashcard.is_approved:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard not found")
            flashcard_set = await SubjectService.get_flashcard_set(db, flashcard.set_id)
            if not flashcard_set or not flashcard_set.is_published:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard set not found")
            await SubjectService.check_subject_access(db, flashcard_set.subject_id, user)
            await FlashcardService.update_progress(db, user.id, update)
            synced += 1
        except Exception as e:
            errors.append({
                "flashcard_id": str(update.flashcard_id),
                "error": str(e)
            })
    
    return {
        "synced_count": synced,
        "error_count": len(errors),
        "errors": errors if errors else None
    }
