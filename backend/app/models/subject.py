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
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


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
        ForeignKey("users.id"),
        nullable=False
    )
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    instructor = relationship("User", back_populates="subjects")
    flashcard_sets = relationship("FlashcardSet", back_populates="subject", cascade="all, delete-orphan")
    enrollments = relationship("Enrollment", back_populates="subject", cascade="all, delete-orphan")
    invite_links = relationship("InviteLink", back_populates="subject")


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
        ForeignKey("subjects.id"),
        nullable=False
    )
    
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Track which PDF this came from
    source_pdf_name = Column(String(255), nullable=True)
    
    # Only published sets are visible to students
    is_published = Column(Boolean, default=False)
    
    # Optional time limit in seconds per card
    time_limit = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    subject = relationship("Subject", back_populates="flashcard_sets")
    flashcards = relationship("Flashcard", back_populates="flashcard_set", cascade="all, delete-orphan")
