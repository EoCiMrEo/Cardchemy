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
from app.models.generation import GenerationJob
from app.models.knowledge import SubjectDocumentIndexJob
from app.models.rag import RagAnswerJob
from app.models.user import User, UserRole
from app.schemas.subject import SubjectCreate, SubjectUpdate, FlashcardSetCreate, FlashcardSetUpdate
from app.services.knowledge_lock import acquire_knowledge_write_lock


def subject_work_active_error() -> HTTPException:
    error = HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "subject_work_active",
            "message": "Stop or cancel active Subject work before deletion.",
        },
    )
    error.safe_detail = error.detail
    return error


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
        await db.flush()
        
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
        if "name" in data.model_fields_set:
            subject.name = data.name
        if "description" in data.model_fields_set:
            subject.description = data.description
        await db.flush()
        
        return subject
    
    @staticmethod
    async def delete_subject(db: AsyncSession, subject: Subject) -> None:
        """Delete a Subject after fencing active capture/index/answer claims."""
        await acquire_knowledge_write_lock(db)
        locked_subject = await db.scalar(
            select(Subject).where(Subject.id == subject.id).with_for_update()
        )
        if locked_subject is None:
            return
        generation_jobs = list(
            (
                await db.scalars(
                    select(GenerationJob)
                    .where(GenerationJob.subject_id == locked_subject.id)
                    .order_by(GenerationJob.id)
                    .with_for_update()
                )
            ).all()
        )
        index_jobs = list(
            (
                await db.scalars(
                    select(SubjectDocumentIndexJob)
                    .where(SubjectDocumentIndexJob.subject_id == locked_subject.id)
                    .order_by(SubjectDocumentIndexJob.id)
                    .with_for_update()
                )
            ).all()
        )
        answer_jobs = list(
            (
                await db.scalars(
                    select(RagAnswerJob)
                    .where(RagAnswerJob.subject_id == locked_subject.id)
                    .order_by(RagAnswerJob.id)
                    .with_for_update()
                )
            ).all()
        )
        if any(
            job.status == "running"
            for job in (*generation_jobs, *index_jobs, *answer_jobs)
        ):
            raise subject_work_active_error()
        await db.delete(locked_subject)
        await db.flush()
    
    # ============================================
    # FlashcardSet CRUD
    # ============================================
    
    @staticmethod
    async def create_flashcard_set(
        db: AsyncSession,
        data: FlashcardSetCreate,
        source_pdf_name: Optional[str] = None,
        generation_job_id: UUID | None = None,
        document_id: UUID | None = None,
    ) -> FlashcardSet:
        """Create a new flashcard set."""
        flashcard_set = FlashcardSet(
            subject_id=data.subject_id,
            title=data.title,
            description=data.description,
            source_pdf_name=source_pdf_name,
            generation_job_id=generation_job_id,
            document_id=document_id,
            is_published=False,  # Always start unpublished
        )
        
        db.add(flashcard_set)
        await db.flush()
        
        return flashcard_set
    
    @staticmethod
    async def get_flashcard_set(
        db: AsyncSession,
        set_id: UUID,
        *,
        for_update: bool = False,
    ) -> Optional[FlashcardSet]:
        """Get a flashcard set by ID."""
        query = select(FlashcardSet).where(FlashcardSet.id == set_id)
        if for_update:
            query = query.with_for_update()
        result = await db.execute(query)
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
        if "title" in data.model_fields_set:
            flashcard_set.title = data.title
        if "description" in data.model_fields_set:
            flashcard_set.description = data.description
        if "is_published" in data.model_fields_set and data.is_published:
            approved_count = await db.scalar(
                select(func.count(Flashcard.id)).where(
                    Flashcard.set_id == flashcard_set.id,
                    Flashcard.is_approved.is_(True),
                )
            )
            if not approved_count:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A flashcard set must contain at least one approved card before publication",
                )
        if "is_published" in data.model_fields_set:
            flashcard_set.is_published = data.is_published
        if "time_limit" in data.model_fields_set:
            flashcard_set.time_limit = data.time_limit
        await db.flush()
        
        return flashcard_set
    
    @staticmethod
    async def delete_flashcard_set(db: AsyncSession, flashcard_set: FlashcardSet) -> None:
        """Delete a flashcard set and all its cards."""
        await db.delete(flashcard_set)
        await db.flush()
    
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
