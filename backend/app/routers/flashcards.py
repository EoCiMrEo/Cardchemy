"""
flashcards.py - Flashcards Router
API endpoints for managing individual flashcards.

Endpoints:
- GET /flashcards/sets/{set_id}/cards - List cards in a set
- POST /flashcards/sets/{set_id}/cards - Create a card manually
- GET /flashcards/{id} - Get a single flashcard
- PUT /flashcards/{id} - Update a flashcard
- DELETE /flashcards/{id} - Delete a flashcard
- POST /flashcards/sets/{set_id}/approve-all - Approve all cards
- POST /flashcards/generate - Generate cards from PDF (AI)
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.routers.auth import get_current_user, get_current_instructor
from app.schemas.flashcard import (
    FlashcardCreate,
    FlashcardCreateRequest,
    FlashcardUpdate,
    FlashcardResponse,
)
from app.services.flashcard import FlashcardService
from app.services.subject import SubjectService

router = APIRouter(prefix="/flashcards", tags=["Flashcards"])


# ============================================
# CRUD Endpoints
# ============================================

@router.get("/sets/{set_id}/cards", response_model=List[FlashcardResponse])
async def list_flashcards(
    set_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all flashcards in a set.
    
    - Instructors see all cards (including unapproved)
    - Students only see approved cards
    """
    # Get the set to verify access
    flashcard_set = await SubjectService.get_flashcard_set(db, set_id)
    if not flashcard_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard set not found"
        )
    
    # Check subject access
    await SubjectService.check_subject_access(db, flashcard_set.subject_id, user)
    
    # Students can only see published sets
    if user.role == UserRole.STUDENT and not flashcard_set.is_published:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard set not found"
        )
    
    only_approved = user.role == UserRole.STUDENT
    flashcards = await FlashcardService.get_set_flashcards(db, set_id, only_approved)
    
    return flashcards


@router.post("/sets/{set_id}/cards", response_model=FlashcardResponse, status_code=status.HTTP_201_CREATED)
async def create_flashcard(
    set_id: UUID,
    data: FlashcardCreateRequest,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually create a flashcard.
    
    Manually created cards are auto-approved since the instructor
    is explicitly adding them.
    """
    # Verify access
    flashcard_set = await SubjectService.get_flashcard_set(db, set_id)
    if not flashcard_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard set not found"
        )
    
    await SubjectService.check_subject_access(db, flashcard_set.subject_id, user, require_owner=True)
    
    create_data = FlashcardCreate(set_id=set_id, **data.model_dump())
    
    # Manual instructor creation is an explicit approval action.
    flashcard = await FlashcardService.create_flashcard(
        db, create_data, quality_score=1.0, is_approved=True
    )
    await db.commit()
    return flashcard


@router.get("/{flashcard_id}", response_model=FlashcardResponse)
async def get_flashcard(
    flashcard_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a single flashcard by ID."""
    flashcard = await FlashcardService.get_flashcard(db, flashcard_id)
    
    if not flashcard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard not found"
        )
    
    # Get parent set to check access
    flashcard_set = await SubjectService.get_flashcard_set(db, flashcard.set_id)
    if not flashcard_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard not found"
        )
    await SubjectService.check_subject_access(db, flashcard_set.subject_id, user)
    
    # Students can only see approved cards from published sets.
    if user.role == UserRole.STUDENT and (not flashcard_set.is_published or not flashcard.is_approved):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard not found"
        )
    
    return flashcard


@router.put("/{flashcard_id}", response_model=FlashcardResponse)
async def update_flashcard(
    flashcard_id: UUID,
    data: FlashcardUpdate,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a flashcard.
    
    Use this to edit AI-generated cards or approve them.
    """
    flashcard = await FlashcardService.get_flashcard(db, flashcard_id)
    
    if not flashcard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard not found"
        )
    
    # Verify ownership
    flashcard_set = await SubjectService.get_flashcard_set(db, flashcard.set_id)
    await SubjectService.check_subject_access(db, flashcard_set.subject_id, user, require_owner=True)
    
    updated = await FlashcardService.update_flashcard(db, flashcard, data)
    await db.commit()
    return updated


@router.delete("/{flashcard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flashcard(
    flashcard_id: UUID,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db)
):
    """Delete a flashcard."""
    flashcard = await FlashcardService.get_flashcard(db, flashcard_id)
    
    if not flashcard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard not found"
        )
    
    # Verify ownership
    flashcard_set = await SubjectService.get_flashcard_set(db, flashcard.set_id)
    await SubjectService.check_subject_access(db, flashcard_set.subject_id, user, require_owner=True)
    
    await FlashcardService.delete_flashcard(db, flashcard)
    await db.commit()
    return None


# ============================================
# Bulk Operations
# ============================================

@router.post("/sets/{set_id}/approve-all")
async def approve_all_flashcards(
    set_id: UUID,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db)
):
    """
    Approve all flashcards in a set as an explicit instructor action.

    Returns:
        Number of cards approved
    """
    # Verify access
    flashcard_set = await SubjectService.get_flashcard_set(db, set_id)
    if not flashcard_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard set not found"
        )
    
    await SubjectService.check_subject_access(db, flashcard_set.subject_id, user, require_owner=True)
    
    count = await FlashcardService.approve_all_flashcards(db, set_id)
    await db.commit()
    return {"approved_count": count}
