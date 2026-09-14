"""
subject.py - Subject and FlashcardSet Models

Subjects are like courses (e.g., "Math 101", "History").
FlashcardSets are collections of flashcards within a subject
(e.g., "Chapter 1 - Algebra Basics").

Hierarchy:
- Subject (owned by instructor)
  - FlashcardSet (from a specific PDF or topic)
    - Flashcard (individual Q&A pairs)
"""

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.time_utils import utcnow


class Subject(Base):
    """
    A subject/course created by an instructor.
    
    Attributes:
        id: Unique identifier
        name: Subject name (e.g., "Mathematics", "History 101")
        description: Optional longer description
        instructor_id: The instructor who owns this subject
        created_at: When the subject was created
    
    Relationships:
        instructor: The User who created this subject
        flashcard_sets: All flashcard sets in this subject
        enrollments: Students enrolled in this subject
        invite_links: Invites for this subject
    """
    __tablename__ = "subjects"
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Foreign key to the instructor who created this
    instructor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    
    created_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False)
    
    # Relationships
    instructor = relationship("User", back_populates="subjects")
    flashcard_sets = relationship("FlashcardSet", back_populates="subject", passive_deletes=True)
    enrollments = relationship("Enrollment", back_populates="subject", passive_deletes=True)
    invite_links = relationship("InviteLink", back_populates="subject", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("length(trim(name)) BETWEEN 1 AND 255", name="ck_subjects_name_length"),
        CheckConstraint(
            "description IS NULL OR length(trim(description)) BETWEEN 1 AND 10000",
            name="ck_subjects_description_length",
        ),
        Index("ix_subjects_instructor_id", "instructor_id"),
    )


class FlashcardSet(Base):
    """
    A set of flashcards, typically generated from one PDF.
    
    When an instructor uploads a PDF, we create a FlashcardSet
    and populate it with AI-generated flashcards.
    
    Attributes:
        id: Unique identifier
        subject_id: Which subject this set belongs to
        title: Name of the set (e.g., "Chapter 1 Notes")
        description: Optional description
        source_pdf_name: Original PDF filename (for reference)
        is_published: If True, students can see this set
        created_at: When the set was created
    
    Workflow:
        1. Instructor uploads PDF → FlashcardSet created (is_published=False)
        2. AI generates flashcards → added to set
        3. Instructor reviews and approves → is_published=True
        4. Students can now study the flashcards
    """
    __tablename__ = "flashcard_sets"
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    
    subject_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False
    )
    
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Track which PDF this came from
    source_pdf_name = Column(String(255), nullable=True)

    # One durable generation job may create at most one set. Manual sets leave
    # this null, and deleting old job history does not delete learning content.
    generation_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("generation_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Only published sets are visible to students
    is_published = Column(Boolean, default=False, server_default=text("false"), nullable=False)
    
    # Optional time limit in seconds per card
    time_limit = Column(Integer, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False)
    
    # Relationships
    subject = relationship("Subject", back_populates="flashcard_sets")
    flashcards = relationship("Flashcard", back_populates="flashcard_set", passive_deletes=True)
    generation_job = relationship("GenerationJob", back_populates="result_set")

    __table_args__ = (
        CheckConstraint("length(trim(title)) BETWEEN 1 AND 255", name="ck_flashcard_sets_title_length"),
        CheckConstraint(
            "description IS NULL OR length(trim(description)) BETWEEN 1 AND 10000",
            name="ck_flashcard_sets_description_length",
        ),
        CheckConstraint(
            "source_pdf_name IS NULL OR length(source_pdf_name) <= 255",
            name="ck_flashcard_sets_source_name_length",
        ),
        CheckConstraint(
            "time_limit IS NULL OR time_limit BETWEEN 5 AND 3600",
            name="ck_flashcard_sets_time_limit",
        ),
        UniqueConstraint("generation_job_id", name="uq_flashcard_sets_generation_job_id"),
        Index("ix_flashcard_sets_subject_id", "subject_id"),
    )
