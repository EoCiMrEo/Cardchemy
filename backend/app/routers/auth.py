"""Authentication endpoints and role dependencies."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.user import (
    MessageResponse,
    PasswordForgotRequest,
    PasswordResetRequest,
    Token,
    UserRegister,
    UserResponse,
)
from app.services.auth import AuthService
from app.services.email import EmailCompositionError, EmailOutboxService
from app.services.rate_limit import (
    limit_login,
    limit_password_reset,
    limit_refresh,
    limit_registration,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
settings = get_settings()
logger = logging.getLogger(__name__)
email_outbox = EmailOutboxService(settings)


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        path="/auth",
        domain=settings.refresh_cookie_domain,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        path="/auth",
        domain=settings.refresh_cookie_domain,
    )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    claims = AuthService.verify_access_token(token)
    if not claims.session_id or not await AuthService.session_is_active(db, claims.session_id, claims.sub):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await AuthService.get_user_by_id(db, claims.sub)
    role = user.role.value if user and isinstance(user.role, UserRole) else getattr(user, "role", None)
    if not user or claims.email != user.email or claims.role != role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Durable Ask AI admission snapshots the authenticated session so its
    # worker can refuse costly work/results after logout, reset or reuse
    # detection. This transient attribute is never serialized or persisted on
    # the User row itself.
    setattr(user, "_auth_session_id", claims.session_id)
    return user


async def get_current_instructor(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.INSTRUCTOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Instructor access required")
    return user


async def get_current_student(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student access required")
    return user


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_registration)],
)
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)) -> User:
    """Register a student and consume one invitation in the same transaction."""

    try:
        async with db.begin():
            user = await AuthService.create_user(db, user_data, UserRole.STUDENT)
            await AuthService.consume_invitation(db, user_data.invite_token, user)
        return user
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Registration or enrollment conflicts with an existing record",
        ) from None


@router.post(
    "/login",
    response_model=Token,
    dependencies=[Depends(limit_login)],
)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Token:
    if not 8 <= len(form_data.password) <= 128:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    user = await AuthService.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, refresh_token = await AuthService.create_session(db, user)
    await db.commit()
    _set_refresh_cookie(response, refresh_token)
    return Token(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post(
    "/refresh",
    response_model=Token,
    dependencies=[Depends(limit_refresh)],
)
async def refresh_token(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> Token:
    refresh = request.cookies.get(settings.refresh_cookie_name)
    if not refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh cookie is missing")
    _, access_token, rotated_refresh = await AuthService.rotate_refresh_token(db, refresh)
    _set_refresh_cookie(response, rotated_refresh)
    return Token(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    token: str = Depends(oauth2_scheme),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    claims = AuthService.verify_access_token(token)
    await AuthService.revoke_session(db, claims.session_id, user.id)
    _clear_refresh_cookie(response)
    return MessageResponse(message="Signed out")


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post(
    "/password/forgot",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(limit_password_reset)],
)
async def forgot_password(
    data: PasswordForgotRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    started = asyncio.get_running_loop().time()
    generic = MessageResponse(message="If that account exists, a password-reset email has been sent")
    try:
        async with db.begin():
            user = await AuthService.get_user_by_email(
                db, str(data.email), for_update=True
            )
            if user is not None:
                reset, _ = await AuthService.create_password_reset_token(db, user)
                await email_outbox.queue_password_reset(db, user=user, reset=reset)
    except (SQLAlchemyError, EmailCompositionError):
        await db.rollback()
        logger.error("password_reset_enqueue_failed")
    finally:
        # Keep the response path substantially less dependent on account
        # existence while leaving SMTP entirely outside the request.
        elapsed = asyncio.get_running_loop().time() - started
        await asyncio.sleep(max(0.0, 0.125 - elapsed))
    return generic


@router.post(
    "/password/reset",
    response_model=MessageResponse,
    dependencies=[Depends(limit_password_reset)],
)
async def reset_password(
    data: PasswordResetRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    async with db.begin():
        user, reset = await AuthService.reset_password(db, data.token, data.new_password)
        await email_outbox.queue_password_changed(db, user=user, reset=reset)
    _clear_refresh_cookie(response)
    return MessageResponse(message="Password reset successfully. Sign in again on every device")
