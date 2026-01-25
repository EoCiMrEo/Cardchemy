# Schemas package - exports all Pydantic schemas
from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserResponse,
    Token,
    TokenData,
    InviteLinkCreate,
    InviteLinkResponse,
)
from app.schemas.subject import (
    SubjectCreate,
    SubjectUpdate,
    SubjectResponse,
    FlashcardSetCreate,
    FlashcardSetUpdate,
    FlashcardSetResponse,
)
from app.schemas.flashcard import (
    FlashcardCreate,
    FlashcardUpdate,
    FlashcardResponse,
    StudyProgressUpdate,
    StudyProgressResponse,
)

__all__ = [
    # User schemas
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "Token",
    "TokenData",
    "InviteLinkCreate",
    "InviteLinkResponse",
    # Subject schemas
    "SubjectCreate",
    "SubjectUpdate",
    "SubjectResponse",
    "FlashcardSetCreate",
    "FlashcardSetUpdate",
    "FlashcardSetResponse",
    # Flashcard schemas
    "FlashcardCreate",
    "FlashcardUpdate",
    "FlashcardResponse",
    "StudyProgressUpdate",
    "StudyProgressResponse",
]
