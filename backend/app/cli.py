"""Operator-only account-management commands.

Usage:
    python -m app.cli create-instructor --email instructor@example.com

The first instructor can be created without an extra flag. Creating another
requires ``--allow-additional`` so there is no reusable registration secret or
public instructor-signup path.
"""

import argparse
import asyncio
import getpass
from typing import Sequence

from pydantic import ValidationError
from sqlalchemy import func, select

from app.database import async_session_maker
from app.models.user import User, UserRole
from app.schemas.user import UserCreate
from app.services.auth import AuthService


async def create_instructor(email: str, full_name: str | None, allow_additional: bool) -> None:
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")

    try:
        user_data = UserCreate(email=email, password=password, full_name=full_name)
    except ValidationError as exc:
        raise SystemExit(str(exc)) from None

    async with async_session_maker() as db:
        instructor_count = await db.scalar(
            select(func.count()).select_from(User).where(User.role == UserRole.INSTRUCTOR)
        )
        if instructor_count and not allow_additional:
            raise SystemExit(
                "An instructor already exists. Re-run with --allow-additional for an explicit operator action."
            )
        user = await AuthService.create_user(db, user_data, UserRole.INSTRUCTOR)
        await db.commit()
        print(f"Instructor created: {user.email}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Flashcard Generator operator commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create-instructor", help="Create an instructor without a public secret")
    create.add_argument("--email", required=True)
    create.add_argument("--full-name")
    create.add_argument("--allow-additional", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "create-instructor":
        asyncio.run(create_instructor(args.email, args.full_name, args.allow_additional))


if __name__ == "__main__":
    main()
