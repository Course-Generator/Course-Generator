"""Verification email delivery over SMTP (Gmail or Outlook)."""

from __future__ import annotations

import logging
import secrets
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr

from coursegen.config import Settings, get_settings
from coursegen.errors import ConfigurationError, ExternalServiceError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    sender: str
    password: str
    use_ssl: bool


class EmailSender:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @staticmethod
    def is_gmail(email: str) -> bool:
        return email.lower().endswith("@gmail.com")

    @staticmethod
    def is_outlook(email: str) -> bool:
        return email.lower().endswith(("@outlook.com", "@hotmail.com", "@live.com"))

    @staticmethod
    def generate_code() -> str:
        return "".join(secrets.choice("0123456789") for _ in range(6))

    def send_verification_code(self, recipient: str) -> str:
        code = self.generate_code()
        self._send(self._config_for(recipient), recipient, code)
        return code

    def _config_for(self, recipient: str) -> SmtpConfig:
        if self.is_outlook(recipient):
            return self._outlook_config()
        return self._gmail_config()

    def _gmail_config(self) -> SmtpConfig:
        if not self._settings.smtp_gmail_user or not self._settings.smtp_gmail_password:
            raise ConfigurationError(
                "Gmail SMTP is not configured. Set SMTP_GMAIL_USER and "
                "SMTP_GMAIL_APP_PASSWORD in your .env file."
            )
        return SmtpConfig(
            host="smtp.gmail.com",
            port=465,
            sender=self._settings.smtp_gmail_user,
            password=self._settings.smtp_gmail_password,
            use_ssl=True,
        )

    def _outlook_config(self) -> SmtpConfig:
        if not self._settings.smtp_outlook_user or not self._settings.smtp_outlook_password:
            raise ConfigurationError(
                "Outlook SMTP is not configured. Set SMTP_OUTLOOK_USER and "
                "SMTP_OUTLOOK_PASSWORD in your .env file."
            )
        return SmtpConfig(
            host="smtp-mail.outlook.com",
            port=587,
            sender=self._settings.smtp_outlook_user,
            password=self._settings.smtp_outlook_password,
            use_ssl=False,
        )

    def _send(self, config: SmtpConfig, recipient: str, code: str) -> None:
        message = self._build_message(config.sender, recipient, code)
        try:
            if config.use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(config.host, config.port, context=context) as server:
                    server.login(config.sender, config.password)
                    server.send_message(message)
            else:
                with smtplib.SMTP(config.host, config.port) as server:
                    server.starttls(context=ssl.create_default_context())
                    server.login(config.sender, config.password)
                    server.send_message(message)
        except (smtplib.SMTPException, OSError) as exc:
            logger.error("Sending verification email to %s failed: %s", recipient, exc)
            raise ExternalServiceError(
                "Could not send the verification email. Check the SMTP settings and try again."
            ) from exc

    @staticmethod
    def _build_message(sender: str, recipient: str, code: str) -> EmailMessage:
        message = EmailMessage()
        message["Subject"] = "The verification code"
        message["From"] = formataddr(("Course Generator Team", sender))
        message["To"] = recipient
        message.set_content(
            "I hope you are well.\n"
            f"The verification code is {code}.\n"
            "Best regards,\n"
        )
        message.add_alternative(
            "<html><body><p>I hope you are well.<br>"
            f"The verification code is <strong>{code}</strong>.<br>"
            "Best regards,</p></body></html>",
            subtype="html",
        )
        return message
