"""Reusable SMTP email service for transactional messages."""

from email.message import EmailMessage
from email.utils import formataddr
import smtplib

from shared.dtos import EmailAttachmentDTO, EmailSendResult
from utils.config import Config


def _normalize_recipients(recipients: list[str] | tuple[str, ...] | set[str] | None) -> list[str]:
    """Return a clean list of unique email addresses preserving order."""
    normalized: list[str] = []
    if not recipients:
        return normalized

    for recipient in recipients:
        candidate = recipient.strip()
        if candidate and candidate not in normalized:
            normalized.append(candidate)
    return normalized


def _build_message(
    *,
    subject: str,
    body_text: str,
    to: list[str],
    cc: list[str],
    body_html: str | None,
    attachments: list[EmailAttachmentDTO],
) -> EmailMessage:
    """Build the MIME message used for SMTP delivery."""
    message = EmailMessage()
    message["From"] = formataddr((Config.EMAIL_FROM_NAME, Config.GMAIL_USER or ""))
    message["To"] = ", ".join(to)
    if cc:
        message["Cc"] = ", ".join(cc)
    message["Subject"] = subject
    message.set_content(body_text)

    if body_html:
        message.add_alternative(body_html, subtype="html")

    for attachment in attachments:
        maintype, _, subtype = attachment.mime_type.partition("/")
        if not maintype or not subtype:
            maintype, subtype = "application", "octet-stream"
        message.add_attachment(
            attachment.content_bytes,
            maintype=maintype,
            subtype=subtype,
            filename=attachment.filename,
        )

    return message


def send_email(
    *,
    subject: str,
    body_text: str,
    to: list[str],
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    body_html: str | None = None,
    attachments: list[EmailAttachmentDTO] | None = None,
    smtp_client_factory=None,
) -> EmailSendResult:
    """Send an email using Gmail SMTP with optional CC, BCC and attachments."""
    normalized_to = _normalize_recipients(to)
    normalized_cc = _normalize_recipients(cc)
    normalized_bcc = _normalize_recipients(bcc)
    normalized_attachments = attachments or []
    all_recipients = _normalize_recipients(normalized_to + normalized_cc + normalized_bcc)

    if not normalized_to:
        return EmailSendResult(success=False, subject=subject, error_message="❌ Debes indicar al menos un destinatario.")

    if not Config.GMAIL_USER or not Config.GMAIL_APP_PASSWORD:
        return EmailSendResult(
            success=False,
            recipients=all_recipients,
            subject=subject,
            attachment_count=len(normalized_attachments),
            error_message="❌ Configuración de email incompleta.",
        )

    message = _build_message(
        subject=subject,
        body_text=body_text,
        to=normalized_to,
        cc=normalized_cc,
        body_html=body_html,
        attachments=normalized_attachments,
    )

    smtp_factory = smtp_client_factory or smtplib.SMTP_SSL

    try:
        with smtp_factory(Config.SMTP_HOST, Config.SMTP_PORT) as server:
            server.login(Config.GMAIL_USER, Config.GMAIL_APP_PASSWORD)
            server.sendmail(Config.GMAIL_USER, all_recipients, message.as_string())
    except Exception as exc:
        return EmailSendResult(
            success=False,
            recipients=all_recipients,
            subject=subject,
            attachment_count=len(normalized_attachments),
            error_message=f"❌ No se pudo enviar el email: {exc}",
        )

    return EmailSendResult(
        success=True,
        recipients=all_recipients,
        subject=subject,
        attachment_count=len(normalized_attachments),
    )


def send_verification_email(
    *,
    recipient_email: str,
    verification_code: str,
    recipient_name: str | None = None,
    smtp_client_factory=None,
) -> EmailSendResult:
    """Send the verification code used during customer onboarding."""
    greeting_name = recipient_name or "cliente"
    subject = "Tu codigo de verificacion"
    body_text = (
        f"Hola {greeting_name},\n\n"
        f"Tu codigo de verificacion es: {verification_code}\n\n"
        "Si no solicitaste este codigo, puedes ignorar este correo."
    )

    return send_email(
        subject=subject,
        body_text=body_text,
        to=[recipient_email],
        smtp_client_factory=smtp_client_factory,
    )