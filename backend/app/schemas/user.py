"""
user.py - User and Authentication Schemas

Pydantic schemas for request validation and response serialization.
These ensure type safety and automatic API documentation.

Key concepts:
- Schemas ending in "Create" are for POST requests (creating new resources)
- Schemas ending in "Response" are for API responses
- `model_config = {"from_attributes": True}` allows converting from SQLAlchemy models
"""

from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from uuid import UUID
from typing import Optional


# ============================================
# User Schemas
# ============================================

class UserCreate(BaseModel):
    """
    Schema for registering a new user.
    
    Fields:
        email: Valid email address (validated by EmailStr)
        password: Password (minimum 8 characters for security)
        full_name: Optional display name
    
    Example:
        {
            "email": "instructor@example.com",
            "password": "securepassword123",
            "full_name": "John Doe"
        }
    """
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    full_name: Optional[str] = None


class UserRegister(UserCreate):
    """
    Schema for registration request body.
    Includes optional fields for instructor code or invite token.
    """
    instructor_code: Optional[str] = None
    invite_token: Optional[str] = None


class UserLogin(BaseModel):
    """
    Schema for logging in.
    
    We use email as the username for simplicity.
    """
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """
    Schema for user data in API responses.
    
    Note: Never include password in responses!
    
    The `model_config` setting allows this schema to be created
    directly from a SQLAlchemy User model instance.
    """
    id: UUID
    email: str
    full_name: Optional[str]
    role: str
    created_at: datetime
    
    model_config = {"from_attributes": True}


# ============================================
# Authentication Schemas
# ============================================

class Token(BaseModel):
    """
    Schema for JWT token response after login.
    
    Fields:
        access_token: Short-lived token for API requests (30 min default)
        refresh_token: Long-lived token for getting new access tokens (7 days)
        token_type: Always "bearer" for JWT
    """
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """
    Schema for decoded JWT token data.
    
    This is what we extract from the JWT to identify the user.
    The `sub` (subject) field contains the user's email.
    """
    sub: Optional[str] = None  # User email
    user_id: Optional[UUID] = None
    role: Optional[str] = None


# ============================================
# Invite Link Schemas
# ============================================

class InviteLinkCreate(BaseModel):
    """
    Schema for creating a new invite link.
    
    The instructor specifies which subject to create the invite for.
    The code is auto-generated on the server.
    """
    subject_id: UUID
    expires_in_days: Optional[int] = Field(
        default=7,
        description="Number of days until the invite expires"
    )


class InviteLinkResponse(BaseModel):
    """
    Schema for invite link data in API responses.
    
    The `code` is what students use to join.
    """
    id: UUID
    code: str
    subject_id: UUID
    expires_at: Optional[datetime]
    created_at: datetime
    is_used: bool = False
    
    model_config = {"from_attributes": True}
