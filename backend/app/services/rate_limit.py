"""PostgreSQL-backed fixed-window rate limiting."""

import hashlib
from collections.abc import Callable
from datetime import timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import async_session_maker
from app.models.user import RateLimitBucket
from app.time_utils import as_utc, utcnow


class RateLimitService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession] = async_session_maker):
        self.session_factory = session_factory

    @staticmethod
    def hash_identity(identity: str) -> str:
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    async def hit(self, scope: str, identity: str, limit: int, window_seconds: int) -> int:
        key_hash = self.hash_identity(identity)
        for attempt in range(2):
            try:
                async with self.session_factory() as db:
                    async with db.begin():
                        result = await db.execute(
                            select(RateLimitBucket)
                            .where(
                                RateLimitBucket.scope == scope,
                                RateLimitBucket.key_hash == key_hash,
                            )
                            .with_for_update()
                        )
                        bucket = result.scalar_one_or_none()
                        now = utcnow()
                        if not bucket:
                            bucket = RateLimitBucket(
                                scope=scope,
                                key_hash=key_hash,
                                window_started_at=now,
                                count=1,
                                updated_at=now,
                            )
                            db.add(bucket)
                            await db.flush()
                            return 1

                        if as_utc(bucket.window_started_at) <= now - timedelta(seconds=window_seconds):
                            bucket.window_started_at = now
                            bucket.count = 1
                        else:
                            bucket.count += 1
                        bucket.updated_at = now
                        await db.flush()
                        return bucket.count
            except IntegrityError:
                if attempt == 1:
                    raise
                continue
        raise RuntimeError("rate-limit counter retry exhausted")


rate_limiter = RateLimitService()


def rate_limit(scope: str, limit: int, window_seconds: int) -> Callable:
    async def dependency(request: Request) -> None:
        identity = request.client.host if request.client else "unknown"
        count = await rate_limiter.hit(scope, identity, limit, window_seconds)
        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(window_seconds)},
            )

    return dependency


limit_login = rate_limit("login", 10, 60)
limit_registration = rate_limit("registration", 5, 300)
limit_refresh = rate_limit("refresh", 30, 60)
limit_invitation = rate_limit("invitation", 20, 60)
limit_join = rate_limit("join", 10, 300)
limit_password_reset = rate_limit("password-reset", 5, 900)
limit_pdf_upload = rate_limit("pdf-upload", 10, 3600)
limit_ai_generation = rate_limit("ai-generation", 10, 3600)
