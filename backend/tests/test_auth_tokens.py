from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from jose import jwt

from app.config import get_settings
from app.models.user import User, UserRole
from app.services.auth import AuthService, utcnow


def make_user(role: UserRole = UserRole.STUDENT) -> User:
    return User(id=uuid4(), email="student@example.com", hashed_password="unused", role=role)


def test_access_refresh_and_invitation_tokens_are_not_interchangeable():
    user = make_user()
    session_id = uuid4()
    access = AuthService._access_token(user, session_id)
    refresh = AuthService._refresh_token(user, session_id, uuid4(), utcnow() + timedelta(days=1))
    subject_id = uuid4()
    invitation = AuthService._encode_token(
        token_type="invitation",
        subject=subject_id,
        subject_id=subject_id,
        jti=uuid4(),
        role=UserRole.STUDENT,
        expires_at=utcnow() + timedelta(hours=1),
    )

    assert AuthService.verify_access_token(access).type == "access"
    assert AuthService.verify_refresh_token(refresh).type == "refresh"
    assert AuthService.verify_invitation_token(invitation).type == "invitation"

    for verifier, wrong_token in [
        (AuthService.verify_access_token, refresh),
        (AuthService.verify_access_token, invitation),
        (AuthService.verify_refresh_token, access),
        (AuthService.verify_refresh_token, invitation),
        (AuthService.verify_invitation_token, access),
        (AuthService.verify_invitation_token, refresh),
    ]:
        with pytest.raises(HTTPException):
            verifier(wrong_token)


def test_malformed_uuid_claim_is_a_controlled_unauthorized_response():
    settings = get_settings()
    now = utcnow()
    token = jwt.encode(
        {
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "sub": "not-a-uuid",
            "jti": str(uuid4()),
            "sid": str(uuid4()),
            "type": "access",
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=5),
        },
        settings.secret_key_value,
        algorithm=settings.algorithm,
    )
    with pytest.raises(HTTPException) as exc:
        AuthService.verify_access_token(token)
    assert exc.value.status_code == 401


def test_expired_access_token_is_rejected():
    user = make_user()
    token = AuthService._encode_token(
        token_type="access",
        subject=user.id,
        jti=uuid4(),
        session_id=uuid4(),
        role=user.role,
        email=user.email,
        expires_at=utcnow() - timedelta(minutes=5),
    )
    with pytest.raises(HTTPException) as exc:
        AuthService.verify_access_token(token)
    assert exc.value.status_code == 401


@pytest.mark.parametrize(
    ("issued_at", "not_before"),
    [
        (timedelta(minutes=10), timedelta(seconds=0)),
        (timedelta(seconds=0), timedelta(minutes=10)),
    ],
)
def test_future_issued_at_and_not_before_are_rejected(issued_at, not_before):
    settings = get_settings()
    user = make_user()
    now = utcnow()
    token = jwt.encode(
        {
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "sub": str(user.id),
            "jti": str(uuid4()),
            "sid": str(uuid4()),
            "type": "access",
            "role": user.role.value,
            "email": user.email,
            "iat": now + issued_at,
            "nbf": now + not_before,
            "exp": now + timedelta(minutes=20),
        },
        settings.secret_key_value,
        algorithm=settings.algorithm,
    )
    with pytest.raises(HTTPException) as exc:
        AuthService.verify_access_token(token)
    assert exc.value.status_code == 401


@pytest.mark.parametrize(
    ("role", "subject_matches"),
    [(UserRole.INSTRUCTOR, True), (UserRole.STUDENT, False)],
)
def test_invitation_role_and_subject_claims_are_validated(role, subject_matches):
    subject_id = uuid4()
    token = AuthService._encode_token(
        token_type="invitation",
        subject=subject_id,
        subject_id=subject_id if subject_matches else uuid4(),
        jti=uuid4(),
        role=role,
        expires_at=utcnow() + timedelta(hours=1),
    )
    with pytest.raises(HTTPException) as exc:
        AuthService.verify_invitation_token(token)
    assert exc.value.status_code == 400


@pytest.mark.parametrize("claim,value", [("iss", "wrong"), ("aud", "wrong")])
def test_issuer_and_audience_are_validated(claim: str, value: str):
    settings = get_settings()
    user = make_user()
    now = utcnow()
    payload = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": str(user.id),
        "jti": str(uuid4()),
        "sid": str(uuid4()),
        "type": "access",
        "role": user.role.value,
        "email": user.email,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=5),
    }
    payload[claim] = value
    token = jwt.encode(payload, settings.secret_key_value, algorithm=settings.algorithm)
    with pytest.raises(HTTPException) as exc:
        AuthService.verify_access_token(token)
    assert exc.value.status_code == 401
