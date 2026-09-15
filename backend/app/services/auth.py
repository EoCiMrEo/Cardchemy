"""Authentication, token, session, invitation, and password-reset services."""

from __future__ import annotations

import hashlib
import secrets
import string
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.flashcard import Enrollment
from app.models.user import AuthSession, InviteLink, PasswordResetToken, User, UserRole
from app.schemas.user import TokenData, UserCreate
from app.time_utils import as_utc, utcnow


settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated="auto")
DUMMY_PASSWORD_HASH = pwd_context.hash("timing-only-password-value")


def db_utcnow() -> datetime:
    """Return the timezone-aware timestamp used by database columns."""

    return utcnow()


def _jti_hash(jti: UUID | str) -> str:
    return hashlib.sha256(str(jti).encode("ascii")).hexdigest()


def _unauthorized(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


class AuthService:
    @staticmethod
    def normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _encode_token(
        *,
        token_type: Literal["access", "refresh", "invitation", "password_reset"],
        subject: UUID,
        expires_at: datetime,
        jti: UUID | None = None,
        session_id: UUID | None = None,
        email: str | None = None,
        role: UserRole | str | None = None,
        subject_id: UUID | None = None,
    ) -> str:
        now = utcnow()
        role_value = role.value if isinstance(role, UserRole) else role
        claims: dict[str, object] = {
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "sub": str(subject),
            "jti": str(jti or uuid4()),
            "type": token_type,
            "iat": now,
            "nbf": now,
            "exp": expires_at,
        }
        if session_id:
            claims["sid"] = str(session_id)
        if email:
            claims["email"] = email
        if role_value:
            claims["role"] = role_value
        if subject_id:
            claims["subject_id"] = str(subject_id)

        return jwt.encode(claims, settings.secret_key_value, algorithm=settings.algorithm)

    @staticmethod
    def _decode_token(
        token: str,
        expected_type: Literal["access", "refresh", "invitation", "password_reset"],
        *,
        invalid_status: int = status.HTTP_401_UNAUTHORIZED,
    ) -> TokenData:
        try:
            payload = jwt.decode(
                token,
                settings.secret_key_value,
                algorithms=[settings.algorithm],
                audience=settings.jwt_audience,
                issuer=settings.jwt_issuer,
                options={
                    "require_exp": True,
                    "require_iat": True,
                    "require_nbf": True,
                    "require_sub": True,
                    "require_jti": True,
                    "leeway": settings.jwt_clock_skew_seconds,
                },
            )
            if payload.get("type") != expected_type:
                raise ValueError("wrong token type")

            issued_at = datetime.fromtimestamp(float(payload["iat"]), UTC)
            expires_at = datetime.fromtimestamp(float(payload["exp"]), UTC)
            if issued_at > utcnow() + timedelta(seconds=settings.jwt_clock_skew_seconds):
                raise ValueError("issued-at is in the future")

            session_id = UUID(payload["sid"]) if payload.get("sid") else None
            data = TokenData(
                sub=UUID(payload["sub"]),
                jti=UUID(payload["jti"]),
                type=payload["type"],
                issued_at=issued_at,
                expires_at=expires_at,
                session_id=session_id,
                email=payload.get("email"),
                role=payload.get("role"),
                subject_id=UUID(payload["subject_id"]) if payload.get("subject_id") else None,
            )
            if expected_type in {"access", "refresh"} and not data.session_id:
                raise ValueError("missing session ID")
            if expected_type == "invitation":
                if data.role != UserRole.STUDENT.value or data.subject_id != data.sub:
                    raise ValueError("invalid invitation claims")
            return data
        except (JWTError, KeyError, TypeError, ValueError, ValidationError):
            detail = "Invalid or expired token"
            if invalid_status == status.HTTP_401_UNAUTHORIZED:
                raise _unauthorized(detail) from None
            raise HTTPException(status_code=invalid_status, detail=detail) from None

    @staticmethod
    def verify_access_token(token: str) -> TokenData:
        return AuthService._decode_token(token, "access")

    @staticmethod
    def verify_refresh_token(token: str) -> TokenData:
        return AuthService._decode_token(token, "refresh")

    @staticmethod
    def verify_invitation_token(token: str) -> TokenData:
        return AuthService._decode_token(token, "invitation", invalid_status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    def verify_password_reset_token(token: str) -> TokenData:
        return AuthService._decode_token(token, "password_reset", invalid_status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
        normalized_email = AuthService.normalize_email(email)
        result = await db.execute(
            select(User).where(func.lower(User.email) == normalized_email)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def create_user(db: AsyncSession, user_data: UserCreate, role: UserRole) -> User:
        email = AuthService.normalize_email(str(user_data.email))
        if await AuthService.get_user_by_email(db, email):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

        user = User(
            email=email,
            hashed_password=AuthService.hash_password(user_data.password),
            full_name=user_data.full_name,
            role=role,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
        user = await AuthService.get_user_by_email(db, email)
        if not user:
            AuthService.verify_password(password, DUMMY_PASSWORD_HASH)
            return None
        return user if AuthService.verify_password(password, user.hashed_password) else None

    @staticmethod
    def _access_token(user: User, session_id: UUID) -> str:
        return AuthService._encode_token(
            token_type="access",
            subject=user.id,
            session_id=session_id,
            email=user.email,
            role=user.role,
            expires_at=utcnow() + timedelta(minutes=settings.access_token_expire_minutes),
        )

    @staticmethod
    def _refresh_token(user: User, session_id: UUID, jti: UUID, expires_at: datetime) -> str:
        return AuthService._encode_token(
            token_type="refresh",
            subject=user.id,
            session_id=session_id,
            jti=jti,
            email=user.email,
            role=user.role,
            expires_at=expires_at,
        )

    @staticmethod
    async def create_session(db: AsyncSession, user: User) -> tuple[str, str]:
        now = db_utcnow()
        session_id = uuid4()
        refresh_jti = uuid4()
        session_expires = now + timedelta(days=settings.refresh_session_expire_days)
        refresh_expires = min(
            now + timedelta(days=settings.refresh_token_expire_days),
            session_expires,
        ).replace(tzinfo=UTC)
        session = AuthSession(
            id=session_id,
            user_id=user.id,
            refresh_jti_hash=_jti_hash(refresh_jti),
            created_at=now,
            last_used_at=now,
            expires_at=session_expires,
        )
        db.add(session)
        await db.flush()
        return (
            AuthService._access_token(user, session_id),
            AuthService._refresh_token(user, session_id, refresh_jti, refresh_expires),
        )

    @staticmethod
    async def session_is_active(db: AsyncSession, session_id: UUID, user_id: UUID) -> bool:
        result = await db.execute(
            select(AuthSession.id).where(
                AuthSession.id == session_id,
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > db_utcnow(),
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def rotate_refresh_token(db: AsyncSession, token: str) -> tuple[User, str, str]:
        claims = AuthService.verify_refresh_token(token)
        result = await db.execute(
            select(AuthSession).where(AuthSession.id == claims.session_id).with_for_update()
        )
        session = result.scalar_one_or_none()
        now = db_utcnow()
        if not session or session.user_id != claims.sub or as_utc(session.expires_at) <= now:
            raise _unauthorized("Refresh session is invalid or expired")
        if session.revoked_at:
            raise _unauthorized("Refresh session has been revoked")
        if not secrets.compare_digest(session.refresh_jti_hash, _jti_hash(claims.jti)):
            session.revoked_at = now
            session.reuse_detected_at = now
            await db.commit()
            raise _unauthorized("Refresh token reuse detected")

        user = await AuthService.get_user_by_id(db, claims.sub)
        if not user:
            session.revoked_at = now
            await db.commit()
            raise _unauthorized("User not found")

        new_jti = uuid4()
        session.refresh_jti_hash = _jti_hash(new_jti)
        session.last_used_at = now
        refresh_expires = min(
            now + timedelta(days=settings.refresh_token_expire_days),
            as_utc(session.expires_at),
        ).replace(tzinfo=UTC)
        await db.commit()
        return (
            user,
            AuthService._access_token(user, session.id),
            AuthService._refresh_token(user, session.id, new_jti, refresh_expires),
        )

    @staticmethod
    async def revoke_session(db: AsyncSession, session_id: UUID, user_id: UUID) -> None:
        await db.execute(
            update(AuthSession)
            .where(AuthSession.id == session_id, AuthSession.user_id == user_id)
            .values(revoked_at=db_utcnow())
        )
        await db.commit()

    @staticmethod
    def generate_invite_code(length: int = 20) -> str:
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    async def create_invitation(
        db: AsyncSession,
        instructor_id: UUID,
        subject_id: UUID,
        expires_in_hours: int,
    ) -> tuple[InviteLink, str]:
        if not settings.invitation_min_hours <= expires_in_hours <= settings.invitation_max_hours:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Invitation lifetime must be between {settings.invitation_min_hours} "
                    f"and {settings.invitation_max_hours} hours"
                ),
            )
        created_at = db_utcnow()
        expires_at = created_at + timedelta(hours=expires_in_hours)
        invite = InviteLink(
            code=AuthService.generate_invite_code(),
            instructor_id=instructor_id,
            subject_id=subject_id,
            created_at=created_at,
            expires_at=expires_at,
        )
        db.add(invite)
        await db.flush()
        token = AuthService._encode_token(
            token_type="invitation",
            subject=subject_id,
            subject_id=subject_id,
            jti=invite.id,
            role=UserRole.STUDENT,
            expires_at=expires_at.replace(tzinfo=UTC),
        )
        return invite, token

    @staticmethod
    async def consume_invitation(db: AsyncSession, token: str, student: User) -> InviteLink:
        if student.role != UserRole.STUDENT:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can join subjects")
        claims = AuthService.verify_invitation_token(token)
        result = await db.execute(
            select(InviteLink).where(InviteLink.id == claims.jti).with_for_update()
        )
        invite = result.scalar_one_or_none()
        now = db_utcnow()
        if not invite or invite.subject_id != claims.subject_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invitation")
        if invite.used_by or invite.used_at:
            if invite.used_by == student.id and invite.used_at is not None:
                enrollment = await db.scalar(
                    select(Enrollment.id).where(
                        Enrollment.student_id == student.id,
                        Enrollment.subject_id == invite.subject_id,
                    )
                )
                if enrollment is not None:
                    return invite
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invitation has already been used")
        if not invite.expires_at or as_utc(invite.expires_at) <= now:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation has expired")

        existing = await db.execute(
            select(Enrollment.id).where(
                Enrollment.student_id == student.id,
                Enrollment.subject_id == invite.subject_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already enrolled in this subject")

        db.add(Enrollment(student_id=student.id, subject_id=invite.subject_id))
        invite.used_by = student.id
        invite.used_at = now
        await db.flush()
        return invite

    @staticmethod
    async def create_password_reset_token(db: AsyncSession, user: User) -> str:
        now = db_utcnow()
        await db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
            .values(used_at=now)
        )
        reset = PasswordResetToken(
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(minutes=settings.password_reset_expire_minutes),
        )
        db.add(reset)
        await db.flush()
        return AuthService._encode_token(
            token_type="password_reset",
            subject=user.id,
            jti=reset.id,
            expires_at=reset.expires_at.replace(tzinfo=UTC),
        )

    @staticmethod
    async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
        claims = AuthService.verify_password_reset_token(token)
        result = await db.execute(
            select(PasswordResetToken)
            .where(PasswordResetToken.id == claims.jti)
            .with_for_update()
        )
        reset = result.scalar_one_or_none()
        now = db_utcnow()
        if (
            not reset
            or reset.user_id != claims.sub
            or reset.used_at is not None
            or as_utc(reset.expires_at) <= now
        ):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

        user = await AuthService.get_user_by_id(db, claims.sub)
        if not user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")
        user.hashed_password = AuthService.hash_password(new_password)
        reset.used_at = now
        await db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await db.commit()
