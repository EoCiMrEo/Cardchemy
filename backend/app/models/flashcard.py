"""
flashcard.py - Flashcard and Progress Models

This module contains:
- Flashcard: Individual Q&A cards (the core content)
- Enrollment: Links students to subjects
- StudyProgress: Tracks how well a student knows each card

The StudyProgress model implements a simplified spaced repetition
algorithm (similar to Anki's SM-2) to optimize learning.
"""

import enum
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.time_utils import utcnow


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


class CardType(str, enum.Enum):
    """The only card representation supported in the current product."""

    MULTIPLE_CHOICE = "multiple_choice"


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
    options = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)

    card_type = Column(
        String(32),
        default=CardType.MULTIPLE_CHOICE.value,
        server_default=text("'multiple_choice'"),
        nullable=False,
    )
    
    # AI confidence score (0.0 to 1.0)
    confidence_score = Column(Float, default=0.0, server_default=text("0"), nullable=False)
    
    # Instructor approval status
    is_approved = Column(Boolean, default=False, server_default=text("false"), nullable=False)
    
    # Original text this was generated from (for debugging/editing)
    source_chunk = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False)
    
    # Relationships
    flashcard_set = relationship("FlashcardSet", back_populates="flashcards")
    study_progress = relationship("StudyProgress", back_populates="flashcard", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("length(trim(front_content)) BETWEEN 1 AND 10000", name="ck_flashcards_front_length"),
        CheckConstraint("length(trim(back_content)) BETWEEN 1 AND 10000", name="ck_flashcards_back_length"),
        CheckConstraint(
            "source_chunk IS NULL OR length(source_chunk) <= 10000",
            name="ck_flashcards_source_length",
        ),
        CheckConstraint("confidence_score BETWEEN 0 AND 1", name="ck_flashcards_confidence"),
        CheckConstraint("card_type = 'multiple_choice'", name="ck_flashcards_card_type"),
        CheckConstraint(
            "flashcard_options_valid(options, back_content)",
            name="ck_flashcards_options_valid",
        ).ddl_if(dialect="postgresql"),
        Index("ix_flashcards_set_id", "set_id"),
        Index(
            "ix_flashcards_approved_due_source",
            "set_id",
            "created_at",
            "id",
            postgresql_where=text("is_approved = true"),
        ),
    )


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
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    
    subject_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False
    )
    
    enrolled_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False)
    
    # Ensure a student can only enroll once per subject
    __table_args__ = (
        UniqueConstraint("student_id", "subject_id", name="unique_enrollment"),
        Index("ix_enrollments_subject_id", "subject_id"),
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
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    
    flashcard_id = Column(
        UUID(as_uuid=True),
        ForeignKey("flashcards.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Current status
    status = Column(String(20), default=CardStatus.NEW.value, server_default=text("'new'"), nullable=False)
    
    # Spaced repetition parameters
    ease_factor = Column(Float, default=2.5, server_default=text("2.5"), nullable=False)
    interval_days = Column(Integer, default=0, server_default=text("0"), nullable=False)
    next_review = Column(DateTime(timezone=True), nullable=True)
    last_reviewed = Column(DateTime(timezone=True), nullable=True)
    
    # Statistics
    correct_count = Column(Integer, default=0, server_default=text("0"), nullable=False)
    incorrect_count = Column(Integer, default=0, server_default=text("0"), nullable=False)
    
    # Ensure one progress record per student per card
    __table_args__ = (
        UniqueConstraint("student_id", "flashcard_id", name="unique_progress"),
        CheckConstraint(
            "status IN ('new', 'learning', 'review', 'mastered')",
            name="ck_study_progress_status",
        ),
        CheckConstraint("ease_factor >= 1.3", name="ck_study_progress_ease_factor"),
        CheckConstraint("interval_days >= 0", name="ck_study_progress_interval"),
        CheckConstraint("correct_count >= 0", name="ck_study_progress_correct_count"),
        CheckConstraint("incorrect_count >= 0", name="ck_study_progress_incorrect_count"),
        CheckConstraint(
            "(status = 'new' AND interval_days = 0) OR "
            "(status = 'learning' AND interval_days BETWEEN 0 AND 6) OR "
            "(status = 'review' AND interval_days BETWEEN 7 AND 20) OR "
            "(status = 'mastered' AND interval_days >= 21)",
            name="ck_study_progress_status_interval",
        ),
        Index("ix_study_progress_flashcard_id", "flashcard_id"),
        Index("ix_study_progress_student_due", "student_id", "next_review", "flashcard_id"),
    )
    
    # Relationships
    flashcard = relationship("Flashcard", back_populates="study_progress")
    student = relationship("User", back_populates="study_progress")
