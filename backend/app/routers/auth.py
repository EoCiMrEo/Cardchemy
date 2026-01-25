"""
auth.py - Authentication Router

API endpoints for user registration, login, and invite links.

Endpoints:
- POST /auth/register - Register new instructor
- POST /auth/login - Login and get tokens
- POST /auth/refresh - Refresh access token
- POST /auth/invite/generate - Create student invite (instructor only)
- POST /auth/invite/accept/{code} - Student accepts invite
- GET /auth/me - Get current user info
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserResponse,
    Token,
    InviteLinkCreate,
    InviteLinkResponse,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])

# OAuth2 scheme for extracting tokens from requests
# tokenUrl is the endpoint where tokens are obtained (for Swagger docs)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ============================================
# Dependency: Get Current User
# ============================================

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency that extracts and validates the JWT token,
    then returns the current user.
    
    Usage in endpoints:
        @router.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            return {"message": f"Hello {user.email}"}
    """
    # Verify the token and extract user data
    token_data = AuthService.verify_token(token)
    
    # Get user from database
    user = await AuthService.get_user_by_email(db, token_data.sub)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user


async def get_current_instructor(
    user: User = Depends(get_current_user)
) -> User:
    """
    Dependency that ensures the current user is an instructor.
    Use this for endpoints that only instructors should access.
    """
    if user.role != UserRole.INSTRUCTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only instructors can perform this action"
        )
    return user


# ============================================
# Registration & Login
# ============================================

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new instructor account.
    
    Students cannot self-register - they must use an invite link.
    
    Request body:
        - email: Valid email address
        - password: Minimum 8 characters
        - full_name: Optional display name
        
    Returns:
        Created user object (without password)
    """
    user = await AuthService.create_user(db, user_data, role=UserRole.INSTRUCTOR)
    return user


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    Login with email and password.
    
    Uses OAuth2 password flow for compatibility with Swagger UI.
    The 'username' field should contain the email address.
    
    Returns:
        - access_token: Short-lived token for API requests
        - refresh_token: Long-lived token for getting new access tokens
        - token_type: "bearer"
    """
    # Authenticate user
    user = await AuthService.authenticate_user(db, form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create tokens
    token_data = {
        "sub": user.email,
        "user_id": str(user.id),
        "role": user.role.value,
    }
    
    access_token = AuthService.create_access_token(token_data)
    refresh_token = AuthService.create_refresh_token(token_data)
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a new access token using a refresh token.
    
    Call this when the access token expires instead of
    asking the user to log in again.
    """
    # Verify refresh token
    token_data = AuthService.verify_token(refresh_token)
    
    # Get user
    user = await AuthService.get_user_by_email(db, token_data.sub)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Create new tokens
    new_token_data = {
        "sub": user.email,
        "user_id": str(user.id),
        "role": user.role.value,
    }
    
    new_access_token = AuthService.create_access_token(new_token_data)
    new_refresh_token = AuthService.create_refresh_token(new_token_data)
    
    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer"
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Get the current authenticated user's information."""
    return user


# ============================================
# Invite Links
# ============================================

@router.post("/invite/generate", response_model=InviteLinkResponse)
async def generate_invite(
    data: InviteLinkCreate,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate an invite link for students to join a subject.
    
    Only instructors can create invite links.
    The invite includes a unique code that students use to enroll.
    
    Request body:
        - subject_id: The subject to invite students to
        - expires_in_days: How long the invite is valid (default 7 days)
    """
    # Verify instructor owns the subject
    from app.services.subject import SubjectService
    await SubjectService.check_subject_access(db, data.subject_id, user, require_owner=True)
    
    # Create invite
    invite = await AuthService.create_invite_link(
        db,
        instructor_id=user.id,
        subject_id=data.subject_id,
        expires_in_days=data.expires_in_days or 7
    )
    
    return InviteLinkResponse(
        id=invite.id,
        code=invite.code,
        subject_id=invite.subject_id,
        expires_at=invite.expires_at,
        created_at=invite.created_at,
        is_used=invite.used_by is not None
    )


@router.post("/invite/accept/{code}", response_model=UserResponse)
async def accept_invite(
    code: str,
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Accept an invite and register as a student.
    
    This is how students join the platform:
    1. Instructor gives them an invite code
    2. Student calls this endpoint with the code + registration info
    3. A new student account is created and enrolled in the subject
    
    Path parameters:
        - code: The invite code (e.g., "ABC123XY")
        
    Request body:
        - email: Student's email
        - password: Password (min 8 chars)
        - full_name: Optional name
    """
    # Find invite
    invite = await AuthService.get_invite_by_code(db, code)
    
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invite code"
        )
    
    # Check if expired
    if invite.expires_at and invite.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invite has expired"
        )
    
    # Check if already used
    if invite.used_by:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invite has already been used"
        )
    
    # Check if email already exists
    existing = await AuthService.get_user_by_email(db, user_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered. Please login instead."
        )
    
    # Create student account
    student = await AuthService.create_user(db, user_data, role=UserRole.STUDENT)
    
    # Use the invite (enrolls student in subject)
    success = await AuthService.use_invite(db, invite, student.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to process invite"
        )
    
    return student
