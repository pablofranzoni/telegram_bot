"""Email service with optional real SMTP delivery and a development mock mode.

The service reads ``EMAIL_MOCK`` from ``utils.config.Config``:
- ``EMAIL_MOCK=true`` (default): logs emails in memory and to the console.
- ``EMAIL_MOCK=false``: sends emails through the configured SMTP server
  (Gmail by default).
"""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from typing import Dict, List, Optional

from shared.dtos.email_dto import EmailAttachmentDTO, EmailSendResult

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via SMTP or mocking them in development."""

    _sent_emails: Dict[str, List[Dict]] = {}

    @staticmethod
    def _load_config():
        """Lazy load config to avoid circular imports at module import time."""
        from utils.config import Config

        return Config

    @staticmethod
    def _is_mock_mode() -> bool:
        """Return whether email should be mocked instead of sent via SMTP."""
        try:
            return EmailService._load_config().EMAIL_MOCK
        except Exception as e:
            logger.warning("Could not read EMAIL_MOCK config, defaulting to mock: %s", e)
            return True

    @staticmethod
    def _build_multipart_message(
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        to: Optional[List[str]] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[EmailAttachmentDTO]] = None,
    ) -> MIMEMultipart:
        """Build a multipart email message with text, optional HTML and attachments."""
        config = EmailService._load_config()
        sender = config.BUSINESS_EMAIL or config.GMAIL_USER or "no-reply@example.com"
        from_name = config.EMAIL_FROM_NAME or "Telegram Bot"

        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{sender}>"
        msg["To"] = ", ".join(to or [])
        if cc:
            msg["Cc"] = ", ".join(cc)

        # Body part: alternative text/html
        body_part = MIMEMultipart("alternative")
        body_part.attach(MIMEText(body_text, "plain", "utf-8"))
        if body_html:
            body_part.attach(MIMEText(body_html, "html", "utf-8"))
        msg.attach(body_part)

        # Attachments
        for attachment in attachments or []:
            part = MIMEBase(*attachment.mime_type.split("/", 1))
            part.set_payload(attachment.content_bytes)
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{attachment.filename}"',
            )
            msg.attach(part)

        return msg

    @staticmethod
    def _send_via_smtp(
        msg: MIMEMultipart,
        recipients: List[str],
    ) -> EmailSendResult:
        """Send a prepared message through the configured SMTP server."""
        config = EmailService._load_config()
        host = config.SMTP_HOST or "smtp.gmail.com"
        port = config.SMTP_PORT or 465
        user = config.GMAIL_USER
        password = config.GMAIL_APP_PASSWORD
        sender = config.BUSINESS_EMAIL or config.GMAIL_USER

        if not user or not password:
            return EmailSendResult(
                success=False,
                recipients=recipients,
                subject=msg["Subject"] or "",
                attachment_count=0,
                error_message="SMTP credentials not configured (GMAIL_USER / GMAIL_APP_PASSWORD).",
            )

        try:
            with smtplib.SMTP_SSL(host, port, timeout=30) as server:
                server.login(user, password)
                server.sendmail(sender, recipients, msg.as_string())
            return EmailSendResult(
                success=True,
                recipients=recipients,
                subject=msg["Subject"] or "",
                attachment_count=0,
            )
        except smtplib.SMTPAuthenticationError as e:
            logger.error("SMTP authentication failed: %s", e)
            return EmailSendResult(
                success=False,
                recipients=recipients,
                subject=msg["Subject"] or "",
                error_message="Authentication failed. Check GMAIL_USER and GMAIL_APP_PASSWORD.",
            )
        except smtplib.SMTPConnectError as e:
            logger.error("SMTP connection error: %s", e)
            return EmailSendResult(
                success=False,
                recipients=recipients,
                subject=msg["Subject"] or "",
                error_message="Could not connect to SMTP server.",
            )
        except Exception as e:
            logger.error("SMTP send error: %s", e)
            return EmailSendResult(
                success=False,
                recipients=recipients,
                subject=msg["Subject"] or "",
                error_message=f"Failed to send email: {e}",
            )

    @staticmethod
    def _mock_send(
        subject: str,
        body_text: str,
        to: List[str],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[EmailAttachmentDTO]] = None,
        email_type: str = "general",
    ) -> EmailSendResult:
        """Mock email delivery: log in memory and return success."""
        all_recipients = list(to or [])
        if cc:
            all_recipients.extend(cc)
        if bcc:
            all_recipients.extend(bcc)

        email_body = body_text
        if attachments:
            email_body += f"\n\n--- Attachments ({len(attachments)}) ---\n"
            for att in attachments:
                email_body += f"  • {att.filename} ({att.mime_type})\n"

        EmailService._log_email(
            email=", ".join(to) if to else "no-recipients",
            subject=subject,
            body=email_body,
            email_type=email_type,
            cc=cc,
            bcc=bcc,
            attachment_count=len(attachments or []),
        )

        logger.info("[MOCK] Email to %s with %s attachments", to, len(attachments or []))

        return EmailSendResult(
            success=True,
            recipients=all_recipients,
            subject=subject,
            attachment_count=len(attachments or []),
            error_message=None,
        )

    @staticmethod
    def send_email(
        subject: str,
        body_text: str,
        to: List[str],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[EmailAttachmentDTO]] = None,
        body_html: Optional[str] = None,
        email_type: str = "general",
        smtp_client_factory=None,  # Kept for backwards compatibility
    ) -> EmailSendResult:
        """Send an email using SMTP or mock delivery depending on EMAIL_MOCK."""
        all_recipients = list(to or [])
        if cc:
            all_recipients.extend(cc)
        if bcc:
            all_recipients.extend(bcc)

        if EmailService._is_mock_mode():
            return EmailService._mock_send(
                subject=subject,
                body_text=body_text,
                to=to,
                cc=cc,
                bcc=bcc,
                attachments=attachments,
                email_type=email_type,
            )

        msg = EmailService._build_multipart_message(
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            to=to,
            cc=cc,
            bcc=bcc,
            attachments=attachments,
        )
        return EmailService._send_via_smtp(msg, all_recipients)

    @staticmethod
    def send_verification_email(email: str, code: str, user_name: Optional[str] = None) -> bool:
        """Send an email verification code."""
        name = user_name or "Usuario"
        subject = "Código de verificación"
        body_text = f"""Hola {name},

Tu código de verificación es: {code}

Este código expira en 15 minutos. No lo compartas con nadie.

Saludos,
{EmailService._load_config().EMAIL_FROM_NAME or 'Telegram Bot'}
"""
        body_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Código de verificación</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 480px; margin: 0 auto; padding: 24px; border: 1px solid #e0e0e0; border-radius: 8px;">
        <h2 style="color: #1a73e8;">Hola {name},</h2>
        <p>Tu código de verificación es:</p>
        <p style="font-size: 32px; font-weight: bold; letter-spacing: 4px; text-align: center; margin: 24px 0; color: #1a73e8;">{code}</p>
        <p>Este código expira en <strong>15 minutos</strong>. No lo compartas con nadie.</p>
        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 24px 0;">
        <p style="font-size: 12px; color: #777;">Saludos,<br>{EmailService._load_config().EMAIL_FROM_NAME or 'Telegram Bot'}</p>
    </div>
</body>
</html>"""

        result = EmailService.send_email(
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            to=[email],
            email_type="verification",
        )
        return result.success

    @staticmethod
    def send_password_reset_email(
        email: str,
        token: str,
        user_name: str,
        reset_url: Optional[str] = None,
    ) -> bool:
        """Send a password reset email with token/link."""
        name = user_name or "Usuario"
        config = EmailService._load_config()
        app_name = config.EMAIL_FROM_NAME or "Telegram Bot"
        link_or_token = reset_url or f"Usa este token: {token}"

        subject = "Restablecer contraseña"
        body_text = f"""Hola {name},

Has solicitado restablecer tu contraseña. Usa el siguiente enlace o token:

{link_or_token}

Este token expira en 1 hora. Si no solicitaste esto, ignora este email.

Saludos,
{app_name}
"""
        body_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Restablecer contraseña</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 480px; margin: 0 auto; padding: 24px; border: 1px solid #e0e0e0; border-radius: 8px;">
        <h2 style="color: #1a73e8;">Hola {name},</h2>
        <p>Has solicitado restablecer tu contraseña. Haz clic en el enlace o usa el token:</p>
        <p style="text-align: center; margin: 24px 0;">
            <a href="{reset_url or '#'}" style="background: #1a73e8; color: #fff; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">Restablecer contraseña</a>
        </p>
        <p style="word-break: break-all; background: #f5f5f5; padding: 12px; border-radius: 4px;">{link_or_token}</p>
        <p>Este token expira en <strong>1 hora</strong>. Si no solicitaste esto, ignora este email.</p>
        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 24px 0;">
        <p style="font-size: 12px; color: #777;">Saludos,<br>{app_name}</p>
    </div>
</body>
</html>"""

        result = EmailService.send_email(
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            to=[email],
            email_type="password_reset",
        )
        return result.success

    @staticmethod
    def _log_email(
        email: str,
        subject: str,
        body: str,
        email_type: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachment_count: int = 0,
    ) -> None:
        """Log email for development/debugging."""
        email_record = {
            "to": email,
            "cc": cc or [],
            "bcc": bcc or [],
            "subject": subject,
            "body": body,
            "type": email_type,
            "attachments": attachment_count,
            "timestamp": datetime.now().isoformat(),
        }

        if email not in EmailService._sent_emails:
            EmailService._sent_emails[email] = []

        EmailService._sent_emails[email].append(email_record)

        logger.debug("\n%s", "=" * 60)
        logger.debug("EMAIL TO: %s", email)
        if cc:
            logger.debug("CC: %s", ", ".join(cc))
        if bcc:
            logger.debug("BCC: %s", ", ".join(bcc))
        logger.debug("SUBJECT: %s", subject)
        if attachment_count > 0:
            logger.debug("ATTACHMENTS: %s", attachment_count)
        logger.debug("%s", "=" * 60)
        logger.debug("%s", body)
        logger.debug("%s", "=" * 60)

    @staticmethod
    def get_sent_emails(email: Optional[str] = None) -> Dict:
        """Get sent emails (for testing)."""
        if email:
            return EmailService._sent_emails.get(email, [])
        return EmailService._sent_emails

    @staticmethod
    def clear_sent_emails() -> None:
        """Clear sent emails history (for testing)."""
        EmailService._sent_emails.clear()


# Module-level wrapper functions for backwards compatibility with imports.
def send_email(
    subject: str,
    body_text: str,
    to: List[str],
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
    attachments: Optional[List[EmailAttachmentDTO]] = None,
    body_html: Optional[str] = None,
    smtp_client_factory=None,
) -> EmailSendResult:
    """Wrapper for EmailService.send_email()."""
    return EmailService.send_email(
        subject=subject,
        body_text=body_text,
        to=to,
        cc=cc,
        bcc=bcc,
        attachments=attachments,
        body_html=body_html,
        smtp_client_factory=smtp_client_factory,
    )


def send_verification_email(email: str, code: str, user_name: Optional[str] = None) -> bool:
    """Wrapper for EmailService.send_verification_email()."""
    return EmailService.send_verification_email(email=email, code=code, user_name=user_name)


def send_password_reset_email(
    email: str,
    token: str,
    user_name: str,
    reset_url: Optional[str] = None,
) -> bool:
    """Wrapper for EmailService.send_password_reset_email()."""
    return EmailService.send_password_reset_email(
        email=email,
        token=token,
        user_name=user_name,
        reset_url=reset_url,
    )
