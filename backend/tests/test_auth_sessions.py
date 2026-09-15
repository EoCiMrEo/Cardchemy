from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import AuthSession, User, UserRole
from app.services.auth import AuthService


async def persisted_user(db, email: str = "student@example.com") -> User:
    user = User(
        id=uuid4(),
        email=email,
        hashed_password=AuthService.hash_password("correct horse battery staple"),
        role=UserRole.STUDENT,
    )
    db.add(user)
    await db.commit()
    return user


async def test_refresh_rotation_reuse_detection_and_logout_revocation(db):
    user = await persisted_user(db)
    access, refresh = await AuthService.create_session(db, user)
    await db.commit()
    access_claims = AuthService.verify_access_token(access)
    assert await AuthService.session_is_active(db, access_claims.session_id, user.id)

    _, rotated_access, rotated_refresh = await AuthService.rotate_refresh_token(db, refresh)
    assert rotated_refresh != refresh
    assert AuthService.verify_access_token(rotated_access).session_id == access_claims.session_id

    with pytest.raises(HTTPException) as exc:
        await AuthService.rotate_refresh_token(db, refresh)
    assert exc.value.status_code == 401
    assert "reuse" in exc.value.detail.lower()
    assert not await AuthService.session_is_active(db, access_claims.session_id, user.id)

    session = await db.scalar(select(AuthSession).where(AuthSession.id == access_claims.session_id))
    assert session.reuse_detected_at is not None

    second_access, _ = await AuthService.create_session(db, user)
    await db.commit()
    second_claims = AuthService.verify_access_token(second_access)
    await AuthService.revoke_session(db, second_claims.session_id, user.id)
    assert not await AuthService.session_is_active(db, second_claims.session_id, user.id)


async def test_password_reset_is_single_use_and_revokes_sessions(db):
    user = await persisted_user(db)
    access, _ = await AuthService.create_session(db, user)
    _, reset_token = await AuthService.create_password_reset_token(db, user)
    await db.commit()

    await AuthService.reset_password(db, reset_token, "a completely new password")
    assert AuthService.verify_password("a completely new password", user.hashed_password)
    claims = AuthService.verify_access_token(access)
    assert not await AuthService.session_is_active(db, claims.session_id, user.id)

    with pytest.raises(HTTPException) as exc:
        await AuthService.reset_password(db, reset_token, "another password value")
    assert exc.value.status_code == 400
