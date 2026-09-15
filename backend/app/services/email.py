"""Typed transactional-email templates, outbox enqueueing, and SMTP transport.

Security-sensitive links and rendered message bodies are deliberately created
only when a worker owns an outbox lease. They are never persisted in the
outbox, included in API responses, or written to logs.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import format_datetime
from html import escape
import hashlib
import smtplib
import ssl
from typing import Callable, Protocol
from urllib.parse import quote
from uuid import UUID, uuid4

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models.email import EmailMessageType, EmailOutboxMessage, EmailOutboxStatus
from app.models.subject import Subject
from app.models.user import InviteLink, PasswordResetToken, User
from app.services.auth import AuthService
from app.time_utils import as_utc, utcnow


EMAIL_ADAPTER = TypeAdapter(EmailStr)


class EmailCompositionError(RuntimeError):
    """The queued domain event can no longer produce a safe message."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class EmailDeliveryError(RuntimeError):
    """Sanitized SMTP failure safe to persist and log by code only."""

    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class TransactionalEmail:
    recipient: str
    subject: str
    text_body: str
    html_body: str
    message_id: str


class EmailTransport(Protocol):
    async def send(self, message: TransactionalEmail) -> None: ...


def _validated_email(value: str) -> str:
    try:
        return str(EMAIL_ADAPTER.validate_python(value.strip())).lower()
    except (ValidationError, ValueError) as exc:
        raise EmailCompositionError("invalid_recipient") from exc


def _safe_header(value: str, *, maximum: int = 255) -> str:
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in normalized)
    ):
        raise EmailCompositionError("invalid_email_header")
    return normalized


def _plain_template(*paragraphs: str) -> str:
    return "\n\n".join(paragraph.strip() for paragraph in paragraphs if paragraph.strip()) + "\n"


def _html_template(app_name: str, heading: str, paragraphs: list[str]) -> str:
    safe_app = escape(app_name)
    safe_heading = escape(heading)
    content = "\n".join(paragraphs)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{safe_heading}</title>
  </head>
  <body style="margin:0;background:#f8fafc;color:#0f172a;font-family:Arial,sans-serif;line-height:1.6">
    <main style="max-width:640px;margin:0 auto;padding:32px 20px">
      <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:28px">
        <p style="margin:0 0 18px;font-weight:700;color:#334155">{safe_app}</p>
        <h1 style="margin:0 0 20px;font-size:24px;line-height:1.3">{safe_heading}</h1>
        {content}
      </div>
    </main>
  </body>
</html>
"""


class EmailTemplates:
    """Pure, escaped multipart templates for the supported transactional events."""

    @staticmethod
    def password_reset(
        *, app_name: str, recipient: str, reset_url: str, expires_minutes: int, message_id: str
    ) -> TransactionalEmail:
        subject = _safe_header(f"Reset your {app_name} password")
        text = _plain_template(
            f"A password reset was requested for your {app_name} account.",
            f"Reset your password within {expires_minutes} minutes:\n{reset_url}",
            "If you did not request this, you can ignore this email.",
        )
        safe_url = escape(reset_url, quote=True)
        html = _html_template(
            app_name,
            "Reset your password",
            [
                f"<p>A password reset was requested for your {escape(app_name)} account.</p>",
                (
                    f'<p><a href="{safe_url}" style="display:inline-block;background:#0f172a;'
                    'color:#ffffff;padding:12px 18px;border-radius:8px;text-decoration:none">'
                    "Reset your password</a></p>"
                ),
                f"<p>This link expires in {expires_minutes} minutes.</p>",
                f'<p>If the button does not work, copy this address:<br><a href="{safe_url}">{safe_url}</a></p>',
                "<p>If you did not request this, you can ignore this email.</p>",
            ],
        )
        return TransactionalEmail(_validated_email(recipient), subject, text, html, message_id)

    @staticmethod
    def password_changed(
        *, app_name: str, recipient: str, message_id: str
    ) -> TransactionalEmail:
        subject = _safe_header(f"Your {app_name} password was changed")
        text = _plain_template(
            f"The password for your {app_name} account was changed.",
            "If you made this change, no action is needed.",
            "If you did not make this change, contact the operator immediately.",
        )
        html = _html_template(
            app_name,
            "Your password was changed",
            [
                f"<p>The password for your {escape(app_name)} account was changed.</p>",
                "<p>If you made this change, no action is needed.</p>",
                "<p>If you did not make this change, contact the operator immediately.</p>",
            ],
        )
        return TransactionalEmail(_validated_email(recipient), subject, text, html, message_id)

    @staticmethod
    def student_invitation(
        *,
        app_name: str,
        recipient: str,
        subject_name: str,
        invitation_url: str,
        expires_at: datetime,
        message_id: str,
    ) -> TransactionalEmail:
        subject = _safe_header(f"Invitation to join {subject_name} in {app_name}")
        expiry = as_utc(expires_at).strftime("%Y-%m-%d %H:%M UTC")
        text = _plain_template(
            f"You were invited to join {subject_name} in {app_name}.",
            f"Accept the invitation before {expiry}:\n{invitation_url}",
            "If you were not expecting this invitation, you can ignore this email.",
        )
        safe_url = escape(invitation_url, quote=True)
        html = _html_template(
            app_name,
            "You have been invited",
            [
                f"<p>You were invited to join <strong>{escape(subject_name)}</strong> in {escape(app_name)}.</p>",
                (
                    f'<p><a href="{safe_url}" style="display:inline-block;background:#0f172a;'
                    'color:#ffffff;padding:12px 18px;border-radius:8px;text-decoration:none">'
                    "Accept invitation</a></p>"
                ),
                f"<p>This invitation expires at {expiry}.</p>",
                f'<p>If the button does not work, copy this address:<br><a href="{safe_url}">{safe_url}</a></p>',
                "<p>If you were not expecting this invitation, you can ignore this email.</p>",
            ],
        )
        return TransactionalEmail(_validated_email(recipient), subject, text, html, message_id)


class EmailOutboxService:
    """Create one durable outbox event in the caller-owned transaction."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def frontend_url(self, path: str, token: str) -> str:
        base = str(self.settings.frontend_base_url).rstrip("/")
        return f"{base}{path}?token={quote(token, safe='')}"

    def message_id(self, outbox_id: UUID) -> str:
        host = self.settings.frontend_base_url.host or "localhost"
        return f"<{outbox_id.hex}@{host}>"

    async def _enqueue(
        self,
        db: AsyncSession,
        *,
        message_type: EmailMessageType,
        recipient: str,
        related_id: UUID,
        expires_at: datetime,
        password_reset_token_id: UUID | None = None,
        invite_link_id: UUID | None = None,
    ) -> EmailOutboxMessage:
        normalized_recipient = _validated_email(recipient)
        raw_key = f"{message_type.value}:{related_id}"
        key_hash = hashlib.sha256(raw_key.encode("ascii")).hexdigest()
        existing = await db.scalar(
            select(EmailOutboxMessage).where(
                EmailOutboxMessage.idempotency_key_hash == key_hash
            )
        )
        if existing is not None:
            if (
                existing.message_type != message_type.value
                or existing.recipient_email != normalized_recipient
                or existing.password_reset_token_id != password_reset_token_id
                or existing.invite_link_id != invite_link_id
            ):
                raise EmailCompositionError("idempotency_conflict")
            return existing

        now = utcnow()
        outbox_id = uuid4()
        outbox = EmailOutboxMessage(
            id=outbox_id,
            message_type=message_type.value,
            recipient_email=normalized_recipient,
            message_id=self.message_id(outbox_id),
            idempotency_key_hash=key_hash,
            status=EmailOutboxStatus.PENDING.value,
            attempt_count=0,
            max_attempts=self.settings.email_max_attempts,
            available_at=now,
            expires_at=as_utc(expires_at),
            password_reset_token_id=password_reset_token_id,
            invite_link_id=invite_link_id,
            created_at=now,
            updated_at=now,
        )
        db.add(outbox)
        await db.flush()
        return outbox

    async def queue_password_reset(
        self, db: AsyncSession, *, user: User, reset: PasswordResetToken
    ) -> EmailOutboxMessage:
        return await self._enqueue(
            db,
            message_type=EmailMessageType.PASSWORD_RESET,
            recipient=user.email,
            related_id=reset.id,
            expires_at=reset.expires_at,
            password_reset_token_id=reset.id,
        )

    async def queue_password_changed(
        self, db: AsyncSession, *, user: User, reset: PasswordResetToken
    ) -> EmailOutboxMessage:
        return await self._enqueue(
            db,
            message_type=EmailMessageType.PASSWORD_CHANGED,
            recipient=user.email,
            related_id=reset.id,
            expires_at=utcnow()
            + timedelta(hours=self.settings.email_security_notification_expire_hours),
            password_reset_token_id=reset.id,
        )

    async def queue_student_invitation(
        self, db: AsyncSession, *, invite: InviteLink
    ) -> EmailOutboxMessage:
        if not invite.recipient_email:
            raise EmailCompositionError("invitation_recipient_missing")
        return await self._enqueue(
            db,
            message_type=EmailMessageType.STUDENT_INVITATION,
            recipient=invite.recipient_email,
            related_id=invite.id,
            expires_at=invite.expires_at,
            invite_link_id=invite.id,
        )


class EmailComposer:
    """Render a queued domain event after it has been safely claimed."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.outbox = EmailOutboxService(self.settings)

    async def compose(self, db: AsyncSession, outbox: EmailOutboxMessage) -> TransactionalEmail:
        now = utcnow()
        if as_utc(outbox.expires_at) <= now:
            raise EmailCompositionError("email_event_expired")

        if outbox.message_type == EmailMessageType.PASSWORD_RESET.value:
            reset = await db.get(PasswordResetToken, outbox.password_reset_token_id)
            if reset is None or reset.used_at is not None or as_utc(reset.expires_at) <= now:
                raise EmailCompositionError("password_reset_invalidated")
            token = AuthService.issue_password_reset_token(reset)
            return EmailTemplates.password_reset(
                app_name=self.settings.app_name,
                recipient=outbox.recipient_email,
                reset_url=self.outbox.frontend_url("/reset-password", token),
                expires_minutes=self.settings.password_reset_expire_minutes,
                message_id=outbox.message_id,
            )

        if outbox.message_type == EmailMessageType.PASSWORD_CHANGED.value:
            reset = await db.get(PasswordResetToken, outbox.password_reset_token_id)
            if reset is None or reset.used_at is None:
                raise EmailCompositionError("password_change_event_invalid")
            return EmailTemplates.password_changed(
                app_name=self.settings.app_name,
                recipient=outbox.recipient_email,
                message_id=outbox.message_id,
            )

        if outbox.message_type == EmailMessageType.STUDENT_INVITATION.value:
            invite = await db.get(InviteLink, outbox.invite_link_id)
            if (
                invite is None
                or invite.used_at is not None
                or as_utc(invite.expires_at) <= now
                or invite.recipient_email != outbox.recipient_email
            ):
                raise EmailCompositionError("invitation_invalidated")
            subject = await db.get(Subject, invite.subject_id)
            if subject is None:
                raise EmailCompositionError("invitation_subject_missing")
            token = AuthService.issue_invitation_token(invite)
            return EmailTemplates.student_invitation(
                app_name=self.settings.app_name,
                recipient=outbox.recipient_email,
                subject_name=subject.name,
                invitation_url=self.outbox.frontend_url("/join", token),
                expires_at=invite.expires_at,
                message_id=outbox.message_id,
            )

        raise EmailCompositionError("unsupported_email_type")


class SmtpTransport:
    """Injectable standard-SMTP transport supporting none, STARTTLS, or TLS."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        smtp_factory: Callable[..., smtplib.SMTP] = smtplib.SMTP,
        smtp_ssl_factory: Callable[..., smtplib.SMTP_SSL] = smtplib.SMTP_SSL,
    ) -> None:
        self.settings = settings or get_settings()
        self.settings.require_email_delivery_config()
        self.smtp_factory = smtp_factory
        self.smtp_ssl_factory = smtp_ssl_factory

    def _mime_message(self, message: TransactionalEmail) -> EmailMessage:
        mime = EmailMessage()
        mime["Subject"] = message.subject
        mime["From"] = Address(
            display_name=self.settings.smtp_from_name or self.settings.app_name,
            addr_spec=str(self.settings.smtp_from_email),
        )
        mime["To"] = Address(addr_spec=message.recipient)
        if self.settings.smtp_reply_to:
            mime["Reply-To"] = Address(addr_spec=str(self.settings.smtp_reply_to))
        mime["Message-ID"] = message.message_id
        mime["Date"] = format_datetime(utcnow())
        mime.set_content(message.text_body)
        mime.add_alternative(message.html_body, subtype="html")
        return mime

    async def send(self, message: TransactionalEmail) -> None:
        await asyncio.to_thread(self._send_blocking, message)

    def _send_blocking(self, message: TransactionalEmail) -> None:
        smtp: smtplib.SMTP | smtplib.SMTP_SSL | None = None
        stage = "connect"
        try:
            factory: Callable[..., smtplib.SMTP | smtplib.SMTP_SSL]
            factory = self.smtp_ssl_factory if self.settings.smtp_implicit_tls else self.smtp_factory
            if self.settings.smtp_implicit_tls:
                smtp = factory(
                    self.settings.smtp_host,
                    self.settings.smtp_port,
                    timeout=self.settings.smtp_timeout_seconds,
                    context=ssl.create_default_context(),
                )
            else:
                smtp = factory(
                    self.settings.smtp_host,
                    self.settings.smtp_port,
                    timeout=self.settings.smtp_timeout_seconds,
                )
            if self.settings.smtp_starttls:
                stage = "tls"
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            if self.settings.smtp_username and self.settings.smtp_password:
                stage = "authentication"
                smtp.login(
                    self.settings.smtp_username,
                    self.settings.smtp_password.get_secret_value(),
                )
            stage = "delivery"
            smtp.send_message(
                self._mime_message(message),
                from_addr=str(self.settings.smtp_from_email),
                to_addrs=[message.recipient],
            )
        except smtplib.SMTPAuthenticationError as exc:
            raise EmailDeliveryError("smtp_authentication_failed", retryable=False) from exc
        except ssl.SSLError as exc:
            raise EmailDeliveryError("smtp_tls_failed", retryable=False) from exc
        except smtplib.SMTPNotSupportedError as exc:
            code = "smtp_starttls_unavailable" if stage == "tls" else "smtp_feature_unsupported"
            raise EmailDeliveryError(code, retryable=False) from exc
        except smtplib.SMTPRecipientsRefused as exc:
            response_codes = [int(response[0]) for response in exc.recipients.values()]
            retryable = bool(response_codes) and all(400 <= code < 500 for code in response_codes)
            raise EmailDeliveryError(
                "smtp_temporary_rejection" if retryable else "smtp_rejected",
                retryable=retryable,
            ) from exc
        except smtplib.SMTPResponseException as exc:
            retryable = 400 <= int(exc.smtp_code) < 500
            raise EmailDeliveryError(
                "smtp_temporary_rejection" if retryable else "smtp_rejected",
                retryable=retryable,
            ) from exc
        except smtplib.SMTPServerDisconnected as exc:
            if stage == "delivery":
                raise EmailDeliveryError("smtp_delivery_ambiguous", retryable=False) from exc
            raise EmailDeliveryError("smtp_disconnected", retryable=True) from exc
        except (TimeoutError, OSError) as exc:
            if stage == "delivery":
                raise EmailDeliveryError("smtp_delivery_ambiguous", retryable=False) from exc
            raise EmailDeliveryError("smtp_connection_failed", retryable=True) from exc
        except smtplib.SMTPException as exc:
            raise EmailDeliveryError("smtp_protocol_error", retryable=stage != "delivery") from exc
        finally:
            if smtp is not None:
                try:
                    smtp.quit()
                except (OSError, smtplib.SMTPException):
                    try:
                        smtp.close()
                    except (OSError, smtplib.SMTPException):
                        pass
