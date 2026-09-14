"""
database.py - Database Connection and Session Management

This module sets up the async database connection using SQLAlchemy 2.0.
We use async for better performance - the server can handle other requests
while waiting for database operations.

Key concepts:
- `create_async_engine`: Creates async connection pool to PostgreSQL
- `async_sessionmaker`: Factory for creating database sessions
- `get_db`: Dependency injection function for FastAPI routes
"""

from pathlib import Path
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

settings = get_settings()
BACKEND_DIR = Path(__file__).resolve().parents[1]

# Create async engine
# - echo=True logs all SQL statements (useful for debugging)
# - pool_pre_ping=True checks connections before using them (handles stale connections)
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,  # Log SQL in debug mode
    pool_pre_ping=True,   # Verify connection is alive before using
)

# Session factory - creates new database sessions
# - expire_on_commit=False: Objects remain usable after commit
#   (important for returning data to API responses)
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base class for all SQLAlchemy models
# All our database models will inherit from this
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session.
    
    This is used with FastAPI's dependency injection:
    
    ```python
    @router.get("/items")
    async def get_items(db: AsyncSession = Depends(get_db)):
        # Use db here
        pass
    ```
    
    The session is automatically closed after the request completes,
    even if an error occurs (thanks to try/finally).
    
    Yields:
        AsyncSession: A database session for the current request
    """
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            if session.in_transaction():
                await session.rollback()
            await session.close()


async def verify_database_revision() -> None:
    """Fail startup unless the database is at every configured Alembic head."""

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    expected_heads = set(script.get_heads())

    async with engine.connect() as connection:
        current_heads = await connection.run_sync(
            lambda sync_connection: set(
                MigrationContext.configure(sync_connection).get_current_heads()
            )
        )

    if current_heads != expected_heads:
        current = ", ".join(sorted(current_heads)) or "unversioned"
        expected = ", ".join(sorted(expected_heads))
        raise RuntimeError(
            f"Database schema is {current}; expected {expected}. "
            "Run 'alembic upgrade head' before starting the API."
        )
