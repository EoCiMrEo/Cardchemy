"""
user.py - User and Authentication Models

This module defines the User model and InviteLink model for authentication.

Key concepts:
- UUID primary keys: More secure than auto-increment integers
- Role-based access: 'instructor' or 'student' roles
- Invite links: Students can only join via instructor-generated links
"""

import enum
import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.time_utils import utcnow


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
    email = Column(String(255), nullable=False)
    
    # Password is hashed with bcrypt before storing
    hashed_password = Column(String(255), nullable=False)
    
    # Optional display name
    full_name = Column(String(255), nullable=True)
    
    # Role determines what the user can do
    role = Column(
        SQLEnum(UserRole),
        default=UserRole.STUDENT,
        server_default=text("'STUDENT'"),
        nullable=False
    )
    
    # Timestamp for when account was created
    created_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False)
    
    # Relationships - allows accessing related objects easily
    # back_populates creates a two-way relationship
    subjects = relationship("Subject", back_populates="instructor", passive_deletes=True)
    enrollments = relationship("Enrollment", back_populates="student", passive_deletes=True)
    study_progress = relationship("StudyProgress", back_populates="student", passive_deletes=True)
    invites_created = relationship(
        "InviteLink",
        back_populates="instructor",
        foreign_keys="InviteLink.instructor_id",
        passive_deletes=True,
    )
    auth_sessions = relationship("AuthSession", back_populates="user", passive_deletes=True)
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("length(trim(email)) BETWEEN 3 AND 255", name="ck_users_email_length"),
        CheckConstraint(
            "full_name IS NULL OR length(trim(full_name)) BETWEEN 1 AND 255",
            name="ck_users_full_name_length",
        ),
        Index("uq_users_email_normalized", func.lower(email), unique=True),
    )


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
    code = Column(String(20), nullable=False)
    
    # Who created this invite
    instructor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Which subject this invite grants access to
    subject_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # When the invite expires (optional)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Track if/when the invite was used
    used_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False)
    
    # Relationships
    instructor = relationship("User", back_populates="invites_created", foreign_keys=[instructor_id])
    subject = relationship("Subject", back_populates="invite_links")

    __table_args__ = (
        UniqueConstraint("code", name="uq_invite_links_code"),
        CheckConstraint("length(trim(code)) BETWEEN 1 AND 20", name="ck_invite_links_code_length"),
        CheckConstraint(
            "expires_at >= created_at + INTERVAL '1 hour' AND "
            "expires_at <= created_at + INTERVAL '720 hours'",
            name="ck_invite_links_lifetime",
        ).ddl_if(dialect="postgresql"),
        Index("ix_invite_links_instructor_id", "instructor_id"),
        Index("ix_invite_links_subject_id", "subject_id"),
        Index("ix_invite_links_used_by", "used_by"),
    )


class AuthSession(Base):
    """Server-side state for one rotating refresh-token family."""

    __tablename__ = "auth_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    refresh_jti_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False)
    last_used_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    reuse_detected_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="auth_sessions")

    __table_args__ = (
        UniqueConstraint("refresh_jti_hash", name="uq_auth_sessions_refresh_jti_hash"),
        CheckConstraint("length(refresh_jti_hash) = 64", name="ck_auth_sessions_jti_hash_length"),
    )


class PasswordResetToken(Base):
    """Single-use state backing a signed password-reset token."""

    __tablename__ = "password_reset_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="password_reset_tokens")


class RateLimitBucket(Base):
    """Shared fixed-window counters used by security-sensitive endpoints."""

    __tablename__ = "rate_limit_buckets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scope = Column(String(64), nullable=False)
    key_hash = Column(String(64), nullable=False)
    window_started_at = Column(DateTime(timezone=True), nullable=False)
    count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    updated_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("scope", "key_hash", name="unique_rate_limit_bucket"),
        CheckConstraint("length(trim(scope)) BETWEEN 1 AND 64", name="ck_rate_limit_scope_length"),
        CheckConstraint("length(key_hash) = 64", name="ck_rate_limit_key_hash_length"),
        CheckConstraint("count >= 0", name="ck_rate_limit_count_nonnegative"),
    )
