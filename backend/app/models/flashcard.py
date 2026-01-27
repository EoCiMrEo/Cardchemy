"""
flashcard.py - Flashcard and Progress Models

This module contains:
- Flashcard: Individual Q&A cards (the core content)
- Enrollment: Links students to subjects
- StudyProgress: Tracks how well a student knows each card

The StudyProgress model implements a simplified spaced repetition
algorithm (similar to Anki's SM-2) to optimize learning.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Float, Boolean, Integer, DateTime, ForeignKey, UniqueConstraint, text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class CardStatus(str, enum.Enum):
    """
    Learning status for a flashcard.
    
    - new: Student hasn't seen this card yet
    - learning: Student is actively learning (seen recently, still difficult)
    - review: Student knows it but needs periodic review
    - mastered: Student knows it very well (long review intervals)
    """
    NEW = "new"
    LEARNING = "learning"
    REVIEW = "review"
    MASTERED = "mastered"


class Flashcard(Base):
    """
    An individual flashcard with a question (front) and answer (back).
    
    Attributes:
        id: Unique identifier
        set_id: Which FlashcardSet this belongs to
        front_content: The question/prompt (shown first)
        back_content: The answer (revealed when flipped)
        confidence_score: AI's confidence in the card quality (0.0-1.0)
        is_approved: Has an instructor approved this card?
        source_chunk: The text chunk this was generated from (for traceability)
        created_at: When the card was created
    
    The confidence_score is set by the AI during generation:
    - >= 0.7: High quality, can be auto-approved
    - 0.4-0.7: Medium quality, needs review
    - < 0.4: Low quality, likely needs editing or deletion
    """
    __tablename__ = "flashcards"
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    
    set_id = Column(
        UUID(as_uuid=True),
        ForeignKey("flashcard_sets.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # The question (front of card)
    front_content = Column(Text, nullable=False)
    
    # The answer (back of card)
    back_content = Column(Text, nullable=False)
    
    # Multiple choice options (JSON list of strings)
    # Example: ["Option A", "Option B", "Option C", "Option D"]
    # The back_content is the correct answer.
    options = Column(JSON, nullable=True)
    
    # AI confidence score (0.0 to 1.0)
    confidence_score = Column(Float, default=0.0)
    
    # Instructor approval status
    is_approved = Column(Boolean, default=False)
    
    # Original text this was generated from (for debugging/editing)
    source_chunk = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    flashcard_set = relationship("FlashcardSet", back_populates="flashcards")
    study_progress = relationship("StudyProgress", back_populates="flashcard", cascade="all, delete-orphan")


class Enrollment(Base):
    """
    Links a student to a subject they can study.
    
    Students are enrolled via invite links created by instructors.
    Once enrolled, they can see all published FlashcardSets in the subject.
    
    Attributes:
        id: Unique identifier
        student_id: The enrolled student
        subject_id: The subject they're enrolled in
        enrolled_at: When they enrolled
    """
    __tablename__ = "enrollments"
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    
    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )
    
    subject_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id"),
        nullable=False
    )
    
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    
    # Ensure a student can only enroll once per subject
    __table_args__ = (
        UniqueConstraint("student_id", "subject_id", name="unique_enrollment"),
    )
    
    # Relationships
    student = relationship("User", back_populates="enrollments")
    subject = relationship("Subject", back_populates="enrollments")


class StudyProgress(Base):
    """
    Tracks a student's progress on a specific flashcard.
    
    Implements a simplified SM-2 spaced repetition algorithm:
    - ease_factor: How easy this card is (2.5 is default)
    - interval_days: Days until next review
    - next_review: When the student should see this card again
    
    After each review:
    - If correct: interval increases, ease_factor may increase
    - If wrong: interval resets, ease_factor decreases
    
    Attributes:
        id: Unique identifier
        student_id: The student
        flashcard_id: The flashcard being tracked
        status: Current learning status (new/learning/review/mastered)
        ease_factor: Multiplier for interval (higher = easier)
        interval_days: Days until next review
        next_review: Datetime of next scheduled review
        last_reviewed: When the student last saw this card
        correct_count: Total correct answers
        incorrect_count: Total incorrect answers
    """
    __tablename__ = "study_progress"
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    
    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )
    
    flashcard_id = Column(
        UUID(as_uuid=True),
        ForeignKey("flashcards.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Current status
    status = Column(String(20), default=CardStatus.NEW.value)
    
    # Spaced repetition parameters
    ease_factor = Column(Float, default=2.5)  # SM-2 default
    interval_days = Column(Integer, default=0)
    next_review = Column(DateTime, nullable=True)
    last_reviewed = Column(DateTime, nullable=True)
    
    # Statistics
    correct_count = Column(Integer, default=0)
    incorrect_count = Column(Integer, default=0)
    
    # Ensure one progress record per student per card
    __table_args__ = (
        UniqueConstraint("student_id", "flashcard_id", name="unique_progress"),
    )
    
    # Relationships
    flashcard = relationship("Flashcard", back_populates="study_progress")
