"""
flashcard.py - Flashcard and StudyProgress Schemas

Schemas for flashcard CRUD operations and tracking study progress.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from typing import Optional, List


# ============================================
# Flashcard Schemas
# ============================================

class FlashcardCreate(BaseModel):
    """
    Schema for creating a flashcard manually.
    
    Usually flashcards are AI-generated, but instructors
    can also create them manually.
    """
    set_id: UUID
    front_content: str = Field(..., min_length=1, description="The question (front of card)")
    back_content: str = Field(..., min_length=1, description="The answer (back of card)")


class FlashcardUpdate(BaseModel):
    """
    Schema for editing a flashcard.
    
    Instructors can edit AI-generated cards before approving.
    """
    front_content: Optional[str] = None
    back_content: Optional[str] = None
    is_approved: Optional[bool] = None


class FlashcardResponse(BaseModel):
    """Schema for flashcard data in API responses."""
    id: UUID
    set_id: UUID
    front_content: str
    back_content: str
    confidence_score: float
    is_approved: bool
    source_chunk: Optional[str]
    created_at: datetime
    
    model_config = {"from_attributes": True}


class FlashcardGenerateRequest(BaseModel):
    """
    Schema for the AI flashcard generation request.
    
    The PDF file is uploaded separately via multipart form.
    This schema contains the metadata.
    """
    subject_id: UUID
    set_title: str
    set_description: Optional[str] = None


class FlashcardGenerateResponse(BaseModel):
    """
    Schema for the AI generation response.
    
    Returns the created set with generated flashcards.
    """
    flashcard_set: "FlashcardSetResponse"
    flashcards: List[FlashcardResponse]
    total_generated: int
    auto_approved: int
    needs_review: int


# ============================================
# StudyProgress Schemas
# ============================================

class StudyProgressUpdate(BaseModel):
    """
    Schema for updating study progress after answering a card.
    
    Fields:
        flashcard_id: The card that was studied
        is_correct: Did the student get it right?
        quality: Self-rating from 0-5 (for SM-2 algorithm)
            0 = Complete blackout
            1 = Incorrect, but remembered upon seeing answer
            2 = Incorrect, but answer seemed easy to recall
            3 = Correct with serious difficulty
            4 = Correct after hesitation
            5 = Perfect response
    """
    flashcard_id: UUID
    is_correct: bool
    quality: int = Field(..., ge=0, le=5, description="Self-rating 0-5")


class StudyProgressResponse(BaseModel):
    """Schema for study progress data in API responses."""
    id: UUID
    flashcard_id: UUID
    status: str
    ease_factor: float
    interval_days: int
    next_review: Optional[datetime]
    last_reviewed: Optional[datetime]
    correct_count: int
    incorrect_count: int
    
    model_config = {"from_attributes": True}


class StudySessionResponse(BaseModel):
    """
    Schema for a study session (batch of cards to study).
    
    Returns cards that are due for review.
    """
    cards: List[FlashcardResponse]
    total_due: int
    new_cards: int
    review_cards: int


# Forward reference resolution
from app.schemas.subject import FlashcardSetResponse
FlashcardGenerateResponse.model_rebuild()
