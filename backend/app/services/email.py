"""Minimal SMTP delivery used for password reset messages."""

import asyncio
import smtplib
from email.message import EmailMessage

from app.config import get_settings


settings = get_settings()


class EmailDeliveryUnavailable(RuntimeError):
    pass


class EmailService:
    @staticmethod
    async def send_password_reset(recipient: str, reset_url: str) -> None:
        if not settings.smtp_host or not settings.smtp_from_email:
            raise EmailDeliveryUnavailable("SMTP is not configured")

        message = EmailMessage()
        message["Subject"] = f"Reset your {settings.app_name} password"
        message["From"] = str(settings.smtp_from_email)
        message["To"] = recipient
        message.set_content(
            "A password reset was requested for your account.\n\n"
            f"Use this link within {settings.password_reset_expire_minutes} minutes:\n{reset_url}\n\n"
            "If you did not request this, you can ignore this email."
        )

        def send() -> None:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
                if settings.smtp_starttls:
                    smtp.starttls()
                if settings.smtp_username and settings.smtp_password:
                    smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
                smtp.send_message(message)

        try:
            await asyncio.to_thread(send)
        except (OSError, smtplib.SMTPException) as exc:
            raise EmailDeliveryUnavailable("Password-reset email could not be delivered") from exc
