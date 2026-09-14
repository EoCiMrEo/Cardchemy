"""
user.py - User and Authentication Models

This module defines the User model and InviteLink model for authentication.

Key concepts:
- UUID primary keys: More secure than auto-increment integers
- Role-based access: 'instructor' or 'student' roles
- Invite links: Students can only join via instructor-generated links
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class UserRole(str, enum.Enum):
    """
    User roles for access control.
    
    - instructor: Can create subjects, upload PDFs, generate flashcards
    - student: Can only study flashcards they're enrolled in
    """
    INSTRUCTOR = "instructor"
    STUDENT = "student"


class User(Base):
    """
    User model for both instructors and students.
    
    Attributes:
        id: Unique identifier (UUID for security)
        email: User's email address (unique, used for login)
        hashed_password: Bcrypt-hashed password (never store plain text!)
        full_name: Display name
        role: Either 'instructor' or 'student'
        created_at: When the account was created
    
    Relationships:
        subjects: Subjects created by this instructor
        enrollments: Subjects this student is enrolled in
        invites_created: Invite links created by this instructor
    """
    __tablename__ = "users"
    
    # Primary key - UUID is more secure than auto-increment
    # server_default uses PostgreSQL's gen_random_uuid() function
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    
    # Email must be unique - used for login
    email = Column(String(255), unique=True, nullable=False, index=True)
    
    # Password is hashed with bcrypt before storing
    hashed_password = Column(String(255), nullable=False)
    
    # Optional display name
    full_name = Column(String(255), nullable=True)
    
    # Role determines what the user can do
    role = Column(
        SQLEnum(UserRole),
        default=UserRole.STUDENT,
        nullable=False
    )
    
    # Timestamp for when account was created
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships - allows accessing related objects easily
    # back_populates creates a two-way relationship
    subjects = relationship("Subject", back_populates="instructor")
    enrollments = relationship("Enrollment", back_populates="student")
    invites_created = relationship("InviteLink", back_populates="instructor", foreign_keys="InviteLink.instructor_id")
    auth_sessions = relationship("AuthSession", back_populates="user", cascade="all, delete-orphan")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")


class InviteLink(Base):
    """
    Invite links for students to join subjects.
    
    Instructors generate unique codes that students can use to:
    1. Register a new account (if they don't have one)
    2. Enroll in the subject the link is for
    
    Attributes:
        id: Unique identifier
        code: The invite code (e.g., "ABC123XYZ")
        instructor_id: Who created this invite
        subject_id: Which subject the invite is for
        expires_at: When the link expires
        used_by: The student who used this invite (null if unused)
        used_at: When the invite was used
    """
    __tablename__ = "invite_links"
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    
    # Unique invite code - short and easy to share
    code = Column(String(20), unique=True, nullable=False, index=True)
    
    # Who created this invite
    instructor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )
    
    # Which subject this invite grants access to
    subject_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id"),
        nullable=False
    )
    
    # When the invite expires (optional)
    expires_at = Column(DateTime, nullable=True)
    
    # Track if/when the invite was used
    used_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    used_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    instructor = relationship("User", back_populates="invites_created", foreign_keys=[instructor_id])
    subject = relationship("Subject", back_populates="invite_links")


class AuthSession(Base):
    """Server-side state for one rotating refresh-token family."""

    __tablename__ = "auth_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    refresh_jti_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, nullable=True)
    reuse_detected_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="auth_sessions")


class PasswordResetToken(Base):
    """Single-use state backing a signed password-reset token."""

    __tablename__ = "password_reset_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    used_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="password_reset_tokens")


class RateLimitBucket(Base):
    """Shared fixed-window counters used by security-sensitive endpoints."""

    __tablename__ = "rate_limit_buckets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scope = Column(String(64), nullable=False)
    key_hash = Column(String(64), nullable=False)
    window_started_at = Column(DateTime, nullable=False)
    count = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("scope", "key_hash", name="unique_rate_limit_bucket"),
    )
