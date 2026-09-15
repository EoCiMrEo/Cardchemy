"""Operator-only account-management commands.

Usage:
    python -m app.cli create-instructor --email instructor@example.com
    python -m app.cli email-outbox-status
    python -m app.cli retry-email --id 00000000-0000-0000-0000-000000000000

The first instructor can be created without an extra flag. Creating another
requires ``--allow-additional`` so there is no reusable registration secret or
public instructor-signup path.
"""

import argparse
import asyncio
import getpass
from typing import Sequence
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, select

from app.database import async_session_maker
from app.models.email import EmailOutboxMessage, EmailOutboxStatus
from app.models.user import User, UserRole
from app.schemas.user import UserCreate
from app.services.auth import AuthService
from app.time_utils import as_utc, utcnow


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


async def email_outbox_status(limit: int) -> None:
    """Print aggregate health and a bounded recipient-free failure list."""

    async with async_session_maker() as db:
        rows = (
            await db.execute(
                select(EmailOutboxMessage.status, func.count(EmailOutboxMessage.id))
                .group_by(EmailOutboxMessage.status)
                .order_by(EmailOutboxMessage.status)
            )
        ).all()
        counts = {status: count for status, count in rows}
        for status in EmailOutboxStatus:
            print(f"{status.value}: {counts.get(status.value, 0)}")

        failures = list(
            (
                await db.scalars(
                    select(EmailOutboxMessage)
                    .where(EmailOutboxMessage.status == EmailOutboxStatus.FAILED.value)
                    .order_by(EmailOutboxMessage.failed_at.desc())
                    .limit(limit)
                )
            ).all()
        )
        if failures:
            print("recent_failures:")
        for outbox in failures:
            print(
                f"  id={outbox.id} type={outbox.message_type} "
                f"attempts={outbox.attempt_count}/{outbox.max_attempts} "
                f"code={outbox.last_error_code or 'unknown'}"
            )


async def retry_email(outbox_id: UUID, *, allow_ambiguous: bool) -> None:
    """Requeue one failed event without exposing its recipient or secret link."""

    async with async_session_maker() as db:
        async with db.begin():
            outbox = await db.scalar(
                select(EmailOutboxMessage)
                .where(EmailOutboxMessage.id == outbox_id)
                .with_for_update()
            )
            if outbox is None:
                raise SystemExit("Email outbox message was not found")
            if outbox.status != EmailOutboxStatus.FAILED.value:
                raise SystemExit("Only failed email outbox messages can be retried")
            now = utcnow()
            if as_utc(outbox.expires_at) <= now:
                raise SystemExit("Email event has expired and cannot be retried")
            if outbox.last_error_code == "smtp_delivery_ambiguous" and not allow_ambiguous:
                raise SystemExit(
                    "SMTP delivery may already have succeeded; pass --allow-ambiguous "
                    "only after accepting the duplicate-delivery risk"
                )
            if outbox.attempt_count >= outbox.max_attempts:
                if outbox.max_attempts >= 10:
                    raise SystemExit("Email event reached the hard ten-attempt ceiling")
                # Grant exactly one additional operator-controlled attempt while
                # preserving the cumulative attempt counter.
                outbox.max_attempts = outbox.attempt_count + 1

            outbox.status = EmailOutboxStatus.PENDING.value
            outbox.available_at = now
            outbox.failed_at = None
            outbox.last_error_code = None
            outbox.delivery_started_at = None
            outbox.updated_at = now
        print(f"Email outbox message requeued: {outbox_id}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Flashcard Generator operator commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create-instructor", help="Create an instructor without a public secret")
    create.add_argument("--email", required=True)
    create.add_argument("--full-name")
    create.add_argument("--allow-additional", action="store_true")
    status_parser = subparsers.add_parser(
        "email-outbox-status",
        help="Show queue counts and recent failures without recipient addresses",
    )
    status_parser.add_argument("--limit", type=int, choices=range(1, 101), default=20)
    retry = subparsers.add_parser("retry-email", help="Requeue one failed email event")
    retry.add_argument("--id", required=True, type=UUID)
    retry.add_argument(
        "--allow-ambiguous",
        action="store_true",
        help="Accept possible duplicate delivery after an ambiguous SMTP failure",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "create-instructor":
        asyncio.run(create_instructor(args.email, args.full_name, args.allow_additional))
    elif args.command == "email-outbox-status":
        asyncio.run(email_outbox_status(args.limit))
    elif args.command == "retry-email":
        asyncio.run(retry_email(args.id, allow_ambiguous=args.allow_ambiguous))


if __name__ == "__main__":
    main()
