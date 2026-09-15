# Schemas package - exports all Pydantic schemas
from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserResponse,
    Token,
    TokenData,
    InviteLinkCreate,
    InviteLinkResponse,
    InvitationCreate,
    InvitationAccept,
    PasswordForgotRequest,
    PasswordResetRequest,
    MessageResponse,
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
    SetProgressResponse,
    StudyAnswerResponse,
    StudyCardResponse,
    StudyProgressUpdate,
    StudyProgressResponse,
    StudySessionResponse,
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
    "InvitationCreate",
    "InvitationAccept",
    "PasswordForgotRequest",
    "PasswordResetRequest",
    "MessageResponse",
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
    "SetProgressResponse",
    "StudyAnswerResponse",
    "StudyCardResponse",
    "StudyProgressUpdate",
    "StudyProgressResponse",
    "StudySessionResponse",
]
