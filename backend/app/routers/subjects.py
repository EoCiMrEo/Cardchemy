"""
subjects.py - Subjects Router

API endpoints for managing subjects and flashcard sets.

Endpoints:
- GET /subjects - List subjects (instructor sees theirs, student sees enrolled)
- POST /subjects - Create new subject (instructor only)
- GET /subjects/{id} - Get subject details
- PUT /subjects/{id} - Update subject (instructor only)
- DELETE /subjects/{id} - Delete subject (instructor only)
- GET /subjects/{id}/sets - List flashcard sets in subject
- POST /subjects/{id}/sets - Create new flashcard set
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.routers.auth import get_current_user, get_current_instructor
from app.schemas.subject import (
    SubjectCreate,
    SubjectUpdate,
    SubjectResponse,
    FlashcardSetCreate,
    FlashcardSetUpdate,
    FlashcardSetResponse,
)
from app.services.subject import SubjectService

router = APIRouter(prefix="/subjects", tags=["Subjects"])


# ============================================
# Subject Endpoints
# ============================================

@router.get("", response_model=List[SubjectResponse])
async def list_subjects(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List subjects accessible to the current user.
    
    - Instructors see subjects they created
    - Students see subjects they're enrolled in
    """
    if user.role == UserRole.INSTRUCTOR:
        subjects = await SubjectService.get_instructor_subjects(db, user.id)
    else:
        subjects = await SubjectService.get_student_subjects(db, user.id)
    
    return subjects


@router.post("", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(
    data: SubjectCreate,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new subject.
    
    Only instructors can create subjects.
    """
    subject = await SubjectService.create_subject(db, data, user.id)
    return subject



@router.get("/sets/{set_id}", response_model=FlashcardSetResponse)
async def get_flashcard_set_by_id(
    set_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a flashcard set by ID directly.
    """
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
    
    return flashcard_set


@router.get("/{subject_id}", response_model=SubjectResponse)
async def get_subject(
    subject_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific subject by ID."""
    subject = await SubjectService.check_subject_access(db, subject_id, user)
    return subject


@router.put("/{subject_id}", response_model=SubjectResponse)
async def update_subject(
    subject_id: UUID,
    data: SubjectUpdate,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a subject.
    
    Only the instructor who created it can update.
    """
    subject = await SubjectService.check_subject_access(db, subject_id, user, require_owner=True)
    updated = await SubjectService.update_subject(db, subject, data)
    return updated


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(
    subject_id: UUID,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a subject and all its content.
    
    This also deletes all flashcard sets and cards in the subject.
    """
    subject = await SubjectService.check_subject_access(db, subject_id, user, require_owner=True)
    await SubjectService.delete_subject(db, subject)
    return None


@router.post("/{subject_id}/invite")
async def generate_invite_token(
    subject_id: UUID,
    expires_in_hours: int = Body(24, embed=True),
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a multi-use invite token for students.
    
    Returns a JWT that can be used to register as a student
    and auto-enroll in this subject.
    """
    await SubjectService.check_subject_access(db, subject_id, user, require_owner=True)
    
    from app.services.auth import AuthService
    from datetime import timedelta
    
    # Create Invite Token (JWT)
    # We use 'sub' for subject_id so verify_token works automatically
    invite_data = {
        "sub": str(subject_id),
        "type": "invite"
    }
    
    token = AuthService.create_access_token(
        invite_data, 
        expires_delta=timedelta(hours=expires_in_hours)
    )
    
    return {"token": token}


@router.post("/join")
async def join_course_with_token(
    token: str = Body(..., embed=True),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Join a course using an invite token.
    
    For existing users who already have an account.
    Verifies the token and enrolls the user in the subject.
    """
    from app.services.auth import AuthService
    from app.models.flashcard import Enrollment
    from sqlalchemy import select
    
    # Verify token
    try:
        token_payload = AuthService.verify_token(token)
        subject_id = token_payload.sub
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invite token"
        )
    
    # Check if subject exists
    subject = await SubjectService.get_subject(db, UUID(subject_id))
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check if already enrolled
    existing = await db.execute(
        select(Enrollment).where(
            Enrollment.student_id == user.id,
            Enrollment.subject_id == UUID(subject_id)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already enrolled in this course"
        )
    
    # Create enrollment
    enrollment = Enrollment(
        student_id=user.id,
        subject_id=UUID(subject_id)
    )
    db.add(enrollment)
    await db.commit()
    
    return {
        "message": "Successfully joined course",
        "subject_name": subject.name
    }


# ============================================
# FlashcardSet Endpoints
# ============================================

@router.get("/{subject_id}/sets", response_model=List[FlashcardSetResponse])
async def list_flashcard_sets(
    subject_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List flashcard sets in a subject.
    
    - Instructors see all sets (including unpublished)
    - Students only see published sets
    """
    await SubjectService.check_subject_access(db, subject_id, user)
    
    include_unpublished = user.role == UserRole.INSTRUCTOR
    sets = await SubjectService.get_subject_sets(db, subject_id, include_unpublished)
    
    return sets


@router.post("/{subject_id}/sets", response_model=FlashcardSetResponse, status_code=status.HTTP_201_CREATED)
async def create_flashcard_set(
    subject_id: UUID,
    data: FlashcardSetCreate,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new flashcard set.
    
    Sets are created unpublished by default. Add flashcards,
    review them, then publish for students to see.
    """
    await SubjectService.check_subject_access(db, subject_id, user, require_owner=True)
    
    # Override subject_id from path
    data.subject_id = subject_id
    
    flashcard_set = await SubjectService.create_flashcard_set(db, data)
    return flashcard_set


@router.get("/{subject_id}/sets/{set_id}", response_model=FlashcardSetResponse)
async def get_flashcard_set(
    subject_id: UUID,
    set_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific flashcard set."""
    await SubjectService.check_subject_access(db, subject_id, user)
    
    flashcard_set = await SubjectService.get_flashcard_set(db, set_id)
    
    if not flashcard_set or flashcard_set.subject_id != subject_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard set not found"
        )
    
    # Students can only see published sets
    if user.role == UserRole.STUDENT and not flashcard_set.is_published:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard set not found"
        )
    
    return flashcard_set


@router.put("/{subject_id}/sets/{set_id}", response_model=FlashcardSetResponse)
async def update_flashcard_set(
    subject_id: UUID,
    set_id: UUID,
    data: FlashcardSetUpdate,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db)
):
    """Update a flashcard set (title, description, publish status)."""
    await SubjectService.check_subject_access(db, subject_id, user, require_owner=True)
    
    flashcard_set = await SubjectService.get_flashcard_set(db, set_id)
    
    if not flashcard_set or flashcard_set.subject_id != subject_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard set not found"
        )
    
    updated = await SubjectService.update_flashcard_set(db, flashcard_set, data)
    return updated


@router.delete("/{subject_id}/sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flashcard_set(
    subject_id: UUID,
    set_id: UUID,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db)
):
    """Delete a flashcard set and all its cards."""
    await SubjectService.check_subject_access(db, subject_id, user, require_owner=True)
    
    flashcard_set = await SubjectService.get_flashcard_set(db, set_id)
    
    if not flashcard_set or flashcard_set.subject_id != subject_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard set not found"
        )
    
    await SubjectService.delete_flashcard_set(db, flashcard_set)
    return None
