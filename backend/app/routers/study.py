"""
study.py - Study Router

API endpoints for student study sessions and progress tracking.

Endpoints:
- GET /study/sets/{set_id}/session - Get cards due for study
- POST /study/progress - Submit study result for a card
- GET /study/sets/{set_id}/progress - Get progress stats for a set
- POST /study/sync - Sync offline progress (for PWA)
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_student
from app.schemas.flashcard import (
    SetProgressResponse,
    StudyAnswerResponse,
    StudyProgressUpdate,
    StudySessionResponse,
    StudySyncResponse,
)
from app.services.flashcard import FlashcardService
from app.services.subject import SubjectService

router = APIRouter(prefix="/study", tags=["Study"])


@router.get("/sets/{set_id}/session", response_model=StudySessionResponse)
async def get_study_session(
    set_id: UUID,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
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


@router.post("/progress", response_model=StudyAnswerResponse)
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
        - selected_option: The selected option text, or null for a timeout
        - selected_option_index: Alternatively, an option index from 0 to 3

    The server compares the selection with the canonical answer and assigns
    quality 5 for correct answers or 1 for incorrect answers.
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
    
    answer = await FlashcardService.update_progress(db, user.id, flashcard, data)
    await db.commit()
    return answer


@router.get("/sets/{set_id}/progress", response_model=SetProgressResponse)
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
        - completion_percentage: Percentage attempted at least once
        - mastery_percentage: Percentage in review or mastered
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


@router.post("/sync", response_model=StudySyncResponse)
async def sync_offline_progress(
    progress_updates: Annotated[list[StudyProgressUpdate], Body(min_length=1, max_length=100)],
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
    cards = await FlashcardService.get_studyable_cards(
        db,
        user.id,
        (update.flashcard_id for update in progress_updates),
    )
    missing_ids = {update.flashcard_id for update in progress_updates} - cards.keys()
    if missing_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more flashcards are not studyable")

    for update in progress_updates:
        await FlashcardService.update_progress(db, user.id, cards[update.flashcard_id], update)
    await db.commit()
    return StudySyncResponse(synced_count=len(progress_updates))
