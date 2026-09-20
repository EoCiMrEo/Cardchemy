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
import json
from pathlib import Path
import sys
from typing import Sequence
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, select, text

from app.observability import configure_logging

configure_logging()
try:
    from app.config import get_settings
    from app.database import async_session_maker, close_database, verify_database_revision
    from app.models.email import EmailOutboxMessage, EmailOutboxStatus
    from app.models.user import User, UserRole
    from app.schemas.user import UserCreate
    from app.services.auth import AuthService
    from app.services.privacy import PrivacyOperationError
    from app.time_utils import as_utc, utcnow
except Exception:
    raise SystemExit("Operator startup failed; validate root configuration and runtime dependencies") from None


def write_result(value: object) -> None:
    """Write requested operational data, never documents or free-form errors."""
    sys.stdout.write(json.dumps(value, default=str, separators=(",", ":")) + "\n")


async def create_instructor(email: str, full_name: str | None, allow_additional: bool) -> None:
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")

    try:
        user_data = UserCreate(email=email, password=password, full_name=full_name)
    except ValidationError:
        raise SystemExit("Invalid instructor account fields") from None

    async with async_session_maker() as db:
        if db.get_bind().dialect.name == "postgresql":
            # Serialize the existing bootstrap guard across concurrent operator
            # processes; the lock ends with the account/audit transaction.
            await db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": 7_314_159_266})
        instructor_count = await db.scalar(
            select(func.count()).select_from(User).where(User.role == UserRole.INSTRUCTOR)
        )
        if instructor_count and not allow_additional:
            raise SystemExit(
                "An instructor already exists. Re-run with --allow-additional for an explicit operator action."
            )
        user = await AuthService.create_user(db, user_data, UserRole.INSTRUCTOR)
        await db.commit()
        write_result({"event": "instructor_created", "account_id": str(user.id)})


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
        from app.observability import safe_error_code
        write_result({
            "counts": {state.value: counts.get(state.value, 0) for state in EmailOutboxStatus},
            "recent_failures": [{"id": str(outbox.id),
                                 "attempts": outbox.attempt_count,
                                 "max_attempts": outbox.max_attempts,
                                 "code": safe_error_code(outbox.last_error_code)}
                                for outbox in failures],
        })


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
        write_result({"event": "email_requeued", "outbox_id": str(outbox_id)})


async def export_account_file(user_id: UUID, destination: Path) -> None:
    """Export private data exclusively into a new owner-only file."""
    import os
    from app.services.privacy import export_account

    async with async_session_maker() as db:
        exported = await export_account(db, user_id)
    # O_EXCL prevents overwriting another user's work or following a symlink.
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        if os.name == "nt":
            import csv
            import subprocess
            identity = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"],
                                      capture_output=True, text=True, check=True)
            sid = next(csv.reader([identity.stdout.strip()]))[1]
            if not sid.startswith("S-1-") or any(part and not part.isdigit() for part in sid[2:].split("-")):
                raise OSError("Private export permissions could not be established")
            subprocess.run(["icacls", str(destination), "/inheritance:r", "/grant:r", f"*{sid}:(F)"],
                           capture_output=True, check=True)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            descriptor = -1  # fdopen owns the descriptor from this point.
            json.dump(exported, output, ensure_ascii=False, default=str)
            output.write("\n")
    except BaseException:
        if descriptor != -1:
            os.close(descriptor)
        destination.unlink(missing_ok=True)
        raise
    write_result({"event": "account_exported", "account_id": str(user_id)})


async def remove_account(user_id: UUID, *, apply: bool, writers_stopped: bool) -> None:
    from app.services.privacy import delete_account
    if not apply or not writers_stopped:
        raise SystemExit("Account deletion requires --apply --writers-stopped after backup and draining")
    async with async_session_maker() as db:
        async with db.begin():
            counts = await delete_account(db, user_id)
    write_result({"event": "account_deleted", "counts": counts})


async def retain_metadata(*, apply: bool) -> None:
    from app.services.privacy import cleanup_retention
    async with async_session_maker() as db:
        async with db.begin():
            counts = await cleanup_retention(db, get_settings(), dry_run=not apply)
    write_result({"event": "retention_completed", "applied": apply, "counts": counts})


async def stage_rag_reindex(subject_id: UUID, owner_id: UUID, *, apply: bool) -> None:
    if not apply:
        raise SystemExit("RAG reindex staging requires --apply")
    from app.services.knowledge_indexing import enqueue_subject_reindex
    async with async_session_maker() as db:
        async with db.begin():
            created = await enqueue_subject_reindex(
                db, subject_id=subject_id, owner_id=owner_id, settings=get_settings()
            )
    write_result({"event": "rag_reindex_staged", "subject_id": str(subject_id), "jobs_created": created})


async def cutover_rag_space(
    subject_id: UUID, owner_id: UUID, space_hash: str, *, apply: bool
) -> None:
    if not apply:
        raise SystemExit("RAG embedding-space cutover requires --apply")
    if len(space_hash) != 64 or any(character not in "0123456789abcdef" for character in space_hash):
        raise SystemExit("Embedding-space hash must be 64 lowercase hexadecimal characters")
    from app.services.knowledge_indexing import cutover_subject_embedding_space
    async with async_session_maker() as db:
        async with db.begin():
            revision_count = await cutover_subject_embedding_space(
                db,
                subject_id=subject_id,
                owner_id=owner_id,
                target_space_hash=space_hash,
            )
    write_result({"event": "rag_space_cutover", "subject_id": str(subject_id), "revision_count": revision_count})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cardchemy operator commands")
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
    export = subparsers.add_parser("export-account", help="Write an authorized private account export to a new file")
    export.add_argument("--id", required=True, type=UUID)
    export.add_argument("--output", required=True, type=Path)
    remove = subparsers.add_parser("delete-account", help="Explicitly delete an account and owned dependents")
    remove.add_argument("--id", required=True, type=UUID)
    remove.add_argument("--apply", action="store_true")
    remove.add_argument("--writers-stopped", action="store_true")
    retention = subparsers.add_parser("cleanup-retention", help="Preview bounded metadata cleanup; --apply commits")
    retention.add_argument("--apply", action="store_true")
    metrics = subparsers.add_parser("operations-status", help="Show private aggregate diagnostics")
    metrics.add_argument("--job-id", type=UUID, help="Include content-free diagnostics for one generation job")
    audit = subparsers.add_parser("audit-status", help="Show bounded content-free privileged-action history")
    audit.add_argument("--target-id", type=UUID)
    audit.add_argument("--limit", type=int, choices=range(1, 101), default=20)
    subparsers.add_parser("report-telemetry", help="Explicitly send numeric aggregates to the enabled HTTPS collector")
    reindex = subparsers.add_parser("rag-stage-reindex", help="Stage compatible indexes without changing the active corpus")
    reindex.add_argument("--subject-id", required=True, type=UUID)
    reindex.add_argument("--owner-id", required=True, type=UUID)
    reindex.add_argument("--apply", action="store_true")
    cutover = subparsers.add_parser("rag-cutover", help="Atomically switch a fully indexed Subject embedding space")
    cutover.add_argument("--subject-id", required=True, type=UUID)
    cutover.add_argument("--owner-id", required=True, type=UUID)
    cutover.add_argument("--space-hash", required=True)
    cutover.add_argument("--apply", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    configure_logging(get_settings().log_level)

    async def execute() -> None:
        try:
            await verify_database_revision()
            if args.command == "create-instructor":
                await create_instructor(args.email, args.full_name, args.allow_additional)
            elif args.command == "email-outbox-status":
                await email_outbox_status(args.limit)
            elif args.command == "retry-email":
                await retry_email(args.id, allow_ambiguous=args.allow_ambiguous)
            elif args.command == "export-account":
                await export_account_file(args.id, args.output)
            elif args.command == "delete-account":
                await remove_account(args.id, apply=args.apply, writers_stopped=args.writers_stopped)
            elif args.command == "cleanup-retention":
                await retain_metadata(apply=args.apply)
            elif args.command == "rag-stage-reindex":
                await stage_rag_reindex(args.subject_id, args.owner_id, apply=args.apply)
            elif args.command == "rag-cutover":
                await cutover_rag_space(
                    args.subject_id, args.owner_id, args.space_hash, apply=args.apply
                )
            elif args.command == "audit-status":
                from app.models.audit import AuditEvent
                async with async_session_maker() as db:
                    query = select(AuditEvent).order_by(AuditEvent.created_at.desc(), AuditEvent.id).limit(args.limit)
                    if args.target_id is not None:
                        query = query.where(AuditEvent.target_id == args.target_id)
                    events = (await db.scalars(query)).all()
                    write_result({"events": [{column.name: getattr(event, column.name)
                                              for column in AuditEvent.__table__.columns}
                                             for event in events]})
            elif args.command in {"operations-status", "report-telemetry"}:
                from app.services.operations import operations_status, report_telemetry
                async with async_session_maker() as db:
                    if args.command == "operations-status":
                        write_result(await operations_status(db, get_settings(), job_id=args.job_id))
                    else:
                        write_result(await report_telemetry(db, get_settings()))
        finally:
            await close_database()
    try:
        asyncio.run(execute())
    except FileExistsError:
        raise SystemExit("Export destination already exists; choose a new private file") from None
    except PrivacyOperationError as failure:
        messages = {
            "account_not_found": "Account was not found",
            "account_work_active": "Stop and drain account generation work before deletion",
            "account_email_active": "Stop and drain related email delivery before deletion",
        }
        message = messages.get(failure.code, "Privacy operation failed")
        raise SystemExit(f"{failure.code if failure.code in messages else 'privacy_operation_failed'}: {message}") from None
    except Exception:
        # Exceptions may contain SQL bind parameters, SMTP details or content.
        raise SystemExit("Operator command failed; check safe operational logs and configuration") from None


if __name__ == "__main__":
    main()
