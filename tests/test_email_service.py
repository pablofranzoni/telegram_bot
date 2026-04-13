"""Unit tests for shared.services.email_service."""

from shared.dtos import EmailAttachmentDTO
from shared.services import email_service


class _FakeSMTP:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.login_args = None
        self.sendmail_args = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def login(self, user, password):
        self.login_args = (user, password)

    def sendmail(self, sender, recipients, message):
        self.sendmail_args = (sender, recipients, message)


def test_send_email_includes_cc_and_bcc_but_hides_bcc(monkeypatch):
    fake_smtp = _FakeSMTP("smtp.gmail.com", 465)

    monkeypatch.setattr(email_service.Config, "GMAIL_USER", "bot@example.com")
    monkeypatch.setattr(email_service.Config, "GMAIL_APP_PASSWORD", "secret")
    monkeypatch.setattr(email_service.Config, "EMAIL_FROM_NAME", "Bot")
    monkeypatch.setattr(email_service.Config, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(email_service.Config, "SMTP_PORT", 465)

    result = email_service.send_email(
        subject="Prueba",
        body_text="Hola",
        to=["destino@example.com"],
        cc=["copia@example.com"],
        bcc=["oculto@example.com"],
        smtp_client_factory=lambda host, port: fake_smtp,
    )

    assert result.success is True
    assert fake_smtp.login_args == ("bot@example.com", "secret")
    assert fake_smtp.sendmail_args is not None
    assert fake_smtp.sendmail_args[1] == [
        "destino@example.com",
        "copia@example.com",
        "oculto@example.com",
    ]
    assert "Cc: copia@example.com" in fake_smtp.sendmail_args[2]
    assert "Bcc:" not in fake_smtp.sendmail_args[2]


def test_send_email_attaches_pdf(monkeypatch):
    fake_smtp = _FakeSMTP("smtp.gmail.com", 465)

    monkeypatch.setattr(email_service.Config, "GMAIL_USER", "bot@example.com")
    monkeypatch.setattr(email_service.Config, "GMAIL_APP_PASSWORD", "secret")
    monkeypatch.setattr(email_service.Config, "EMAIL_FROM_NAME", "Bot")
    monkeypatch.setattr(email_service.Config, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(email_service.Config, "SMTP_PORT", 465)

    result = email_service.send_email(
        subject="Adjunto",
        body_text="Se adjunta PDF",
        to=["destino@example.com"],
        attachments=[
            EmailAttachmentDTO(
                filename="factura.pdf",
                content_bytes=b"%PDF-1.4 fake pdf",
                mime_type="application/pdf",
            )
        ],
        smtp_client_factory=lambda host, port: fake_smtp,
    )

    assert result.success is True
    assert result.attachment_count == 1
    assert fake_smtp.sendmail_args is not None
    assert "filename=\"factura.pdf\"" in fake_smtp.sendmail_args[2]
    assert "application/pdf" in fake_smtp.sendmail_args[2]


def test_send_email_returns_failure_when_smtp_raises(monkeypatch):
    class _BrokenSMTP(_FakeSMTP):
        def login(self, user, password):
            raise RuntimeError("auth failed")

    monkeypatch.setattr(email_service.Config, "GMAIL_USER", "bot@example.com")
    monkeypatch.setattr(email_service.Config, "GMAIL_APP_PASSWORD", "secret")
    monkeypatch.setattr(email_service.Config, "EMAIL_FROM_NAME", "Bot")
    monkeypatch.setattr(email_service.Config, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(email_service.Config, "SMTP_PORT", 465)

    result = email_service.send_email(
        subject="Prueba",
        body_text="Hola",
        to=["destino@example.com"],
        smtp_client_factory=lambda host, port: _BrokenSMTP(host, port),
    )

    assert result.success is False
    assert "auth failed" in (result.error_message or "")


def test_send_verification_email_uses_recipient_and_subject(monkeypatch):
    captured = {}

    def fake_send_email(**kwargs):
        captured.update(kwargs)
        return email_service.EmailSendResult(success=True, recipients=kwargs["to"], subject=kwargs["subject"])

    monkeypatch.setattr(email_service, "send_email", fake_send_email)

    result = email_service.send_verification_email(
        recipient_email="ana@example.com",
        verification_code="123456",
        recipient_name="Ana",
    )

    assert result.success is True
    assert captured["to"] == ["ana@example.com"]
    assert captured["subject"] == "Tu codigo de verificacion"
    assert "123456" in captured["body_text"]