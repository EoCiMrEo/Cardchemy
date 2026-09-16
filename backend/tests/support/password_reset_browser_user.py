"""Seed or remove the disposable account used by the opt-in password-reset browser test."""

import argparse
import asyncio
import os

from sqlalchemy import delete
from sqlalchemy.engine import make_url

from app.config import get_settings
from app.database import async_session_maker, engine
from app.models.user import User, UserRole
from app.schemas.user import UserCreate
from app.services.auth import AuthService


def test_inputs() -> tuple[str, str]:
    settings = get_settings()
    database_name = make_url(settings.database_url).database
    if settings.environment != "test" or database_name != "password_reset_browser_test":
        raise SystemExit("Refusing to modify a database other than the disposable password-reset test database")

    email = os.getenv("PASSWORD_RESET_LIVE_EMAIL", "").strip().lower()
    password = os.getenv("PASSWORD_RESET_LIVE_OLD_PASSWORD", "")
    if not email.startswith("password-reset-browser-") or not email.endswith("@example.com"):
        raise SystemExit("PASSWORD_RESET_LIVE_EMAIL must be a password-reset-browser-* disposable example.com address")
    UserCreate(email=email, password=password, full_name="Password Reset Browser Test")
    return email, password


async def update_user(action: str) -> None:
    email, password = test_inputs()
    async with async_session_maker() as db:
        async with db.begin():
            await db.execute(delete(User).where(User.email == email))
            if action == "seed":
                db.add(
                    User(
                        email=email,
                        hashed_password=AuthService.hash_password(password),
                        full_name="Password Reset Browser Test",
                        role=UserRole.STUDENT,
                    )
                )
    await engine.dispose()
    print(f"Disposable password-reset browser user {action} completed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("seed", "remove"))
    args = parser.parse_args()
    asyncio.run(update_user(args.action))


if __name__ == "__main__":
    main()
