"""Request and response schemas for authentication and invitations."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator


Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]


class UserCreate(BaseModel):
    email: EmailStr
    password: Password
    full_name: str | None = Field(default=None, min_length=1, max_length=255)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class UserRegister(UserCreate):
    invite_token: str = Field(min_length=20, max_length=4096)


class UserLogin(BaseModel):
    email: EmailStr
    password: Password

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    """Only the short-lived access token is readable by JavaScript."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class TokenData(BaseModel):
    sub: UUID
    jti: UUID
    type: Literal["access", "refresh", "invitation", "password_reset"]
    issued_at: datetime
    expires_at: datetime
    session_id: UUID | None = None
    email: EmailStr | None = None
    role: Literal["instructor", "student"] | None = None
    subject_id: UUID | None = None


class InviteLinkCreate(BaseModel):
    subject_id: UUID
    expires_in_hours: int = Field(default=24, ge=1, le=720)


class InvitationCreate(BaseModel):
    expires_in_hours: int = Field(default=24, ge=1, le=720)


class InviteLinkResponse(BaseModel):
    token: str
    subject_id: UUID
    expires_at: datetime


class InvitationAccept(BaseModel):
    token: str = Field(min_length=20, max_length=4096)


class PasswordForgotRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class PasswordResetRequest(BaseModel):
    token: str = Field(min_length=20, max_length=4096)
    new_password: Password


class MessageResponse(BaseModel):
    message: str
