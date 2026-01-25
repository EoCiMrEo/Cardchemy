"""
subject.py - Subject Service

Business logic for managing subjects and flashcard sets.
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.subject import Subject, FlashcardSet
from app.models.flashcard import Enrollment, Flashcard
from app.models.user import User, UserRole
from app.schemas.subject import SubjectCreate, SubjectUpdate, FlashcardSetCreate, FlashcardSetUpdate


class SubjectService:
    """Service for subject and flashcard set operations."""
    
    # ============================================
    # Subject CRUD
    # ============================================
    
    @staticmethod
    async def create_subject(
        db: AsyncSession,
        data: SubjectCreate,
        instructor_id: UUID
    ) -> Subject:
        """Create a new subject."""
        subject = Subject(
            name=data.name,
            description=data.description,
            instructor_id=instructor_id,
        )
        
        db.add(subject)
        await db.commit()
        await db.refresh(subject)
        
        return subject
    
    @staticmethod
    async def get_subject(db: AsyncSession, subject_id: UUID) -> Optional[Subject]:
        """Get a subject by ID."""
        result = await db.execute(
            select(Subject).where(Subject.id == subject_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_instructor_subjects(
        db: AsyncSession,
        instructor_id: UUID
    ) -> List[Subject]:
        """Get all subjects created by an instructor."""
        result = await db.execute(
            select(Subject)
            .where(Subject.instructor_id == instructor_id)
            .options(selectinload(Subject.flashcard_sets), selectinload(Subject.enrollments))
            .order_by(Subject.created_at.desc())
        )
        subjects = list(result.scalars().all())
        
        for subject in subjects:
            setattr(subject, 'flashcard_set_count', len(subject.flashcard_sets))
            setattr(subject, 'student_count', len(subject.enrollments))
            
        return subjects
    
    @staticmethod
    async def get_student_subjects(
        db: AsyncSession,
        student_id: UUID
    ) -> List[Subject]:
        """Get all subjects a student is enrolled in."""
        result = await db.execute(
            select(Subject)
            .join(Enrollment, Enrollment.subject_id == Subject.id)
            .where(Enrollment.student_id == student_id)
            .options(selectinload(Subject.flashcard_sets), selectinload(Subject.enrollments))
            .order_by(Subject.name)
        )
        subjects = list(result.scalars().all())
        
        for subject in subjects:
            setattr(subject, 'flashcard_set_count', len(subject.flashcard_sets))
            setattr(subject, 'student_count', len(subject.enrollments))
            
        return subjects
    
    @staticmethod
    async def update_subject(
        db: AsyncSession,
        subject: Subject,
        data: SubjectUpdate
    ) -> Subject:
        """Update a subject."""
        if data.name is not None:
            subject.name = data.name
        if data.description is not None:
            subject.description = data.description
        
        await db.commit()
        await db.refresh(subject)
        
        return subject
    
    @staticmethod
    async def delete_subject(db: AsyncSession, subject: Subject) -> None:
        """Delete a subject and all its contents."""
        await db.delete(subject)
        await db.commit()
    
    # ============================================
    # FlashcardSet CRUD
    # ============================================
    
    @staticmethod
    async def create_flashcard_set(
        db: AsyncSession,
        data: FlashcardSetCreate,
        source_pdf_name: Optional[str] = None
    ) -> FlashcardSet:
        """Create a new flashcard set."""
        flashcard_set = FlashcardSet(
            subject_id=data.subject_id,
            title=data.title,
            description=data.description,
            source_pdf_name=source_pdf_name,
            is_published=False,  # Always start unpublished
        )
        
        db.add(flashcard_set)
        await db.commit()
        await db.refresh(flashcard_set)
        
        return flashcard_set
    
    @staticmethod
    async def get_flashcard_set(
        db: AsyncSession,
        set_id: UUID
    ) -> Optional[FlashcardSet]:
        """Get a flashcard set by ID."""
        result = await db.execute(
            select(FlashcardSet).where(FlashcardSet.id == set_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_subject_sets(
        db: AsyncSession,
        subject_id: UUID,
        include_unpublished: bool = False
    ) -> List[FlashcardSet]:
        """
        Get all flashcard sets in a subject.
        
        Args:
            db: Database session
            subject_id: Subject to get sets for
            include_unpublished: If True, include unpublished sets (for instructors)
        """
        query = select(FlashcardSet).where(FlashcardSet.subject_id == subject_id)
        
        if not include_unpublished:
            query = query.where(FlashcardSet.is_published == True)
        
        query = query.options(selectinload(FlashcardSet.flashcards)).order_by(FlashcardSet.created_at.desc())
        
        result = await db.execute(query)
        sets = list(result.scalars().all())
        
        for fset in sets:
            setattr(fset, 'flashcard_count', len(fset.flashcards))
            setattr(fset, 'approved_count', len([c for c in fset.flashcards if c.is_approved]))
            
        return sets
    
    @staticmethod
    async def update_flashcard_set(
        db: AsyncSession,
        flashcard_set: FlashcardSet,
        data: FlashcardSetUpdate
    ) -> FlashcardSet:
        """Update a flashcard set."""
        if data.title is not None:
            flashcard_set.title = data.title
        if data.description is not None:
            flashcard_set.description = data.description
        if data.is_published is not None:
            flashcard_set.is_published = data.is_published
        
        await db.commit()
        await db.refresh(flashcard_set)
        
        return flashcard_set
    
    @staticmethod
    async def delete_flashcard_set(db: AsyncSession, flashcard_set: FlashcardSet) -> None:
        """Delete a flashcard set and all its cards."""
        await db.delete(flashcard_set)
        await db.commit()
    
    # ============================================
    # Authorization Helpers
    # ============================================
    
    @staticmethod
    async def check_subject_access(
        db: AsyncSession,
        subject_id: UUID,
        user: User,
        require_owner: bool = False
    ) -> Subject:
        """
        Check if user has access to a subject.
        
        Args:
            db: Database session
            subject_id: Subject to check
            user: Current user
            require_owner: If True, only the instructor owner can access
            
        Returns:
            The subject if access is allowed
            
        Raises:
            HTTPException: If access denied or subject not found
        """
        subject = await SubjectService.get_subject(db, subject_id)
        
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subject not found"
            )
        
        # Instructors can access their own subjects
        if user.role == UserRole.INSTRUCTOR:
            if subject.instructor_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this subject"
                )
            return subject
        
        # Students need to be enrolled
        if user.role == UserRole.STUDENT:
            if require_owner:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only instructors can perform this action"
                )
            
            # Check enrollment
            result = await db.execute(
                select(Enrollment)
                .where(Enrollment.student_id == user.id)
                .where(Enrollment.subject_id == subject_id)
            )
            enrollment = result.scalar_one_or_none()
            
            if not enrollment:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not enrolled in this subject"
                )
            
            return subject
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
