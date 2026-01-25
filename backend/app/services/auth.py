"""
auth.py - Authentication Service

This service handles all authentication logic:
- Password hashing with bcrypt
- JWT token creation and verification
- User registration and login

Security concepts:
- Passwords are NEVER stored in plain text
- bcrypt adds salt automatically (protects against rainbow tables)
- JWT tokens are signed (tamper-proof) but not encrypted (don't put secrets in them)
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
import secrets
import string

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.config import get_settings
from app.models.user import User, UserRole, InviteLink
from app.schemas.user import UserCreate, TokenData

settings = get_settings()

# Password hashing context
# bcrypt is the industry standard for password hashing
# - Automatically adds random salt to each password
# - Slow by design (makes brute-force attacks impractical)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """
    Service class for authentication operations.
    
    All methods are async to work with our async database.
    """
    
    # ============================================
    # Password Hashing
    # ============================================
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password string (includes salt)
        
        Example:
            hashed = AuthService.hash_password("mypassword")
            # Returns something like: $2b$12$LQv3c1yqBWVHx...
        """
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            plain_password: Password to verify
            hashed_password: Hash to verify against
            
        Returns:
            True if password matches, False otherwise
        """
        return pwd_context.verify(plain_password, hashed_password)
    
    # ============================================
    # JWT Token Management
    # ============================================
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a JWT access token.
        
        Args:
            data: Dictionary of claims to include in the token
            expires_delta: How long until the token expires
            
        Returns:
            Encoded JWT string
        
        The token contains:
        - sub: Subject (user email)
        - user_id: User's UUID
        - role: User's role (instructor/student)
        - exp: Expiration timestamp
        """
        to_encode = data.copy()
        
        # Set expiration time
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        
        # Create the JWT
        # The algorithm (HS256) uses our secret_key to sign the token
        encoded_jwt = jwt.encode(
            to_encode,
            settings.secret_key,
            algorithm=settings.algorithm
        )
        
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: dict) -> str:
        """
        Create a longer-lived refresh token.
        
        Refresh tokens are used to get new access tokens
        without requiring the user to log in again.
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
        to_encode.update({"exp": expire, "type": "refresh"})
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.secret_key,
            algorithm=settings.algorithm
        )
        
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> TokenData:
        """
        Verify and decode a JWT token.
        
        Args:
            token: The JWT string to verify
            
        Returns:
            TokenData with the decoded claims
            
        Raises:
            HTTPException: If token is invalid or expired
        """
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            # Decode and verify the token
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.algorithm]
            )
            
            # Extract claims
            email: str = payload.get("sub")
            user_id: str = payload.get("user_id")
            role: str = payload.get("role")
            
            if email is None:
                raise credentials_exception
            
            return TokenData(
                sub=email,
                user_id=UUID(user_id) if user_id else None,
                role=role
            )
            
        except JWTError:
            raise credentials_exception
    
    # ============================================
    # User Management
    # ============================================
    
    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """
        Find a user by their email address.
        
        Args:
            db: Database session
            email: Email to search for
            
        Returns:
            User object if found, None otherwise
        """
        result = await db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: UUID) -> Optional[User]:
        """Find a user by their UUID."""
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create_user(
        db: AsyncSession,
        user_data: UserCreate,
        role: UserRole = UserRole.INSTRUCTOR
    ) -> User:
        """
        Create a new user account.
        
        Args:
            db: Database session
            user_data: Registration data (email, password, name)
            role: User role (instructor by default)
            
        Returns:
            The created User object
            
        Raises:
            HTTPException: If email is already registered
        """
        # Check if email already exists
        existing = await AuthService.get_user_by_email(db, user_data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create new user with hashed password
        user = User(
            email=user_data.email,
            hashed_password=AuthService.hash_password(user_data.password),
            full_name=user_data.full_name,
            role=role,
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        return user
    
    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        email: str,
        password: str
    ) -> Optional[User]:
        """
        Authenticate a user by email and password.
        
        Args:
            db: Database session
            email: User's email
            password: Plain text password to verify
            
        Returns:
            User object if authenticated, None otherwise
        """
        user = await AuthService.get_user_by_email(db, email)
        
        if not user:
            return None
        
        if not AuthService.verify_password(password, user.hashed_password):
            return None
        
        return user
    
    # ============================================
    # Invite Link Management
    # ============================================
    
    @staticmethod
    def generate_invite_code(length: int = 8) -> str:
        """
        Generate a random invite code.
        
        Uses cryptographically secure random for security.
        """
        alphabet = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    @staticmethod
    async def create_invite_link(
        db: AsyncSession,
        instructor_id: UUID,
        subject_id: UUID,
        expires_in_days: int = 7
    ) -> InviteLink:
        """
        Create an invite link for a subject.
        
        Args:
            db: Database session
            instructor_id: Who is creating the invite
            subject_id: Which subject the invite is for
            expires_in_days: How long the invite is valid
            
        Returns:
            The created InviteLink
        """
        code = AuthService.generate_invite_code()
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days) if expires_in_days else None
        
        invite = InviteLink(
            code=code,
            instructor_id=instructor_id,
            subject_id=subject_id,
            expires_at=expires_at,
        )
        
        db.add(invite)
        await db.commit()
        await db.refresh(invite)
        
        return invite
    
    @staticmethod
    async def get_invite_by_code(db: AsyncSession, code: str) -> Optional[InviteLink]:
        """Find an invite link by its code."""
        result = await db.execute(
            select(InviteLink).where(InviteLink.code == code)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def use_invite(
        db: AsyncSession,
        invite: InviteLink,
        student_id: UUID
    ) -> bool:
        """
        Mark an invite as used and enroll the student.
        
        Args:
            db: Database session
            invite: The invite link being used
            student_id: The student using the invite
            
        Returns:
            True if successful, False if invite is invalid/expired
        """
        # Check if already used
        if invite.used_by:
            return False
        
        # Check if expired
        if invite.expires_at and invite.expires_at < datetime.utcnow():
            return False
        
        # Mark as used
        invite.used_by = student_id
        invite.used_at = datetime.utcnow()
        
        # Create enrollment
        from app.models.flashcard import Enrollment
        enrollment = Enrollment(
            student_id=student_id,
            subject_id=invite.subject_id,
        )
        
        db.add(enrollment)
        await db.commit()
        
        return True
