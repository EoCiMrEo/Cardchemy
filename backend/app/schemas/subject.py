"""
subject.py - Subject and FlashcardSet Schemas

Schemas for managing subjects (courses) and flashcard sets.
"""

from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional, List


# ============================================
# Subject Schemas
# ============================================

class SubjectCreate(BaseModel):
    """Schema for creating a new subject."""
    name: str
    description: Optional[str] = None


class SubjectUpdate(BaseModel):
    """Schema for updating an existing subject."""
    name: Optional[str] = None
    description: Optional[str] = None


class SubjectResponse(BaseModel):
    """Schema for subject data in API responses."""
    id: UUID
    name: str
    description: Optional[str]
    instructor_id: UUID
    created_at: datetime
    flashcard_set_count: Optional[int] = 0
    student_count: Optional[int] = 0
    
    model_config = {"from_attributes": True}


# ============================================
# FlashcardSet Schemas
# ============================================

class FlashcardSetCreate(BaseModel):
    """
    Schema for creating a new flashcard set.
    
    Note: Usually created automatically when uploading a PDF,
    but can also be created manually.
    """
    subject_id: UUID
    title: str
    description: Optional[str] = None


class FlashcardSetUpdate(BaseModel):
    """Schema for updating a flashcard set."""
    title: Optional[str] = None
    description: Optional[str] = None
    is_published: Optional[bool] = None


class FlashcardSetResponse(BaseModel):
    """Schema for flashcard set data in API responses."""
    id: UUID
    subject_id: UUID
    title: str
    description: Optional[str]
    source_pdf_name: Optional[str]
    is_published: bool
    created_at: datetime
    flashcard_count: Optional[int] = 0
    approved_count: Optional[int] = 0
    
    model_config = {"from_attributes": True}
