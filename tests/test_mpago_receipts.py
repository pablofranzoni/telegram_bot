"""Tests for receipt delivery after payment approval."""

from shared.dtos import EmailAttachmentDTO, EmailSendResult
from utils import mpago


def test_enviar_comprobante_si_corresponde_skips_when_already_sent(monkeypatch):
    service = mpago.MercadoPagoSimple.__new__(mpago.MercadoPagoSimple)
    config_module = __import__("utils.config", fromlist=["dummy"])

    monkeypatch.setattr(
        __import__("utils.database", fromlist=["dummy"]),
        "obtener_comprobante_pedido",
        lambda invoice_id: ({"email": "ana@example.com", "customer_id": "123"}, []),
    )
    monkeypatch.setattr(
        __import__("utils.database", fromlist=["dummy"]),
        "documento_ya_enviado",
        lambda invoice_id, document_type, delivery_channel, recipient_target: delivery_channel == "email",
    )
    monkeypatch.setattr(config_module.Config, "SEND_PDF_MODE", "EMAIL")

    result = service.enviar_comprobante_si_corresponde(42, "mp-123")

    assert result["success"] is True
    assert "ya enviado" in result["message"].lower()


def test_enviar_comprobante_si_corresponde_sends_email_and_registers(monkeypatch):
    service = mpago.MercadoPagoSimple.__new__(mpago.MercadoPagoSimple)
    database_module = __import__("utils.database", fromlist=["dummy"])
    document_module = __import__("shared.services.document_service", fromlist=["dummy"])
    email_module = __import__("shared.services.email_service", fromlist=["dummy"])
    config_module = __import__("utils.config", fromlist=["dummy"])

    monkeypatch.setattr(
        database_module,
        "obtener_comprobante_pedido",
        lambda invoice_id: ({"email": "ana@example.com", "customer_id": "123"}, []),
    )
    monkeypatch.setattr(
        database_module,
        "documento_ya_enviado",
        lambda invoice_id, document_type, delivery_channel, recipient_target: False,
    )
    monkeypatch.setattr(
        document_module,
        "build_receipt_pdf_attachment",
        lambda invoice_id: (
            EmailAttachmentDTO(
                filename="comprobante.pdf",
                content_bytes=b"%PDF-demo",
                mime_type="application/pdf",
            ),
            "comprobante.pdf",
            None,
        ),
    )
    monkeypatch.setattr(
        email_module,
        "send_email",
        lambda **kwargs: EmailSendResult(success=True, recipients=kwargs["to"], subject=kwargs["subject"], attachment_count=1),
    )
    monkeypatch.setattr(config_module.Config, "SEND_PDF_MODE", "EMAIL")

    recorded = []

    def fake_register(**kwargs):
        recorded.append(kwargs)
        return True

    monkeypatch.setattr(database_module, "registrar_documento_enviado", fake_register)

    result = service.enviar_comprobante_si_corresponde(42, "mp-123")

    assert result["success"] is True
    assert recorded == [{
        "invoice_id": 42,
        "document_type": "receipt_pdf",
        "delivery_channel": "email",
        "recipient_target": "ana@example.com",
        "file_name": "comprobante.pdf",
        "payment_id": "mp-123",
        "status": "sent",
        "error_message": None,
    }]


def test_enviar_comprobante_si_corresponde_sends_both_channels(monkeypatch):
    service = mpago.MercadoPagoSimple.__new__(mpago.MercadoPagoSimple)
    database_module = __import__("utils.database", fromlist=["dummy"])
    document_module = __import__("shared.services.document_service", fromlist=["dummy"])
    email_module = __import__("shared.services.email_service", fromlist=["dummy"])
    config_module = __import__("utils.config", fromlist=["dummy"])

    monkeypatch.setattr(
        database_module,
        "obtener_comprobante_pedido",
        lambda invoice_id: ({"email": "ana@example.com", "customer_id": "123"}, []),
    )
    monkeypatch.setattr(
        database_module,
        "documento_ya_enviado",
        lambda invoice_id, document_type, delivery_channel, recipient_target: False,
    )
    monkeypatch.setattr(
        document_module,
        "build_receipt_pdf_attachment",
        lambda invoice_id: (
            EmailAttachmentDTO(
                filename="comprobante.pdf",
                content_bytes=b"%PDF-demo",
                mime_type="application/pdf",
            ),
            "comprobante.pdf",
            None,
        ),
    )
    monkeypatch.setattr(
        document_module,
        "send_receipt_pdf_via_telegram",
        lambda chat_id, attachment, caption: (True, None),
    )
    monkeypatch.setattr(
        email_module,
        "send_email",
        lambda **kwargs: EmailSendResult(success=True, recipients=kwargs["to"], subject=kwargs["subject"], attachment_count=1),
    )
    monkeypatch.setattr(config_module.Config, "SEND_PDF_MODE", "BOTH")

    recorded = []

    def fake_register(**kwargs):
        recorded.append(kwargs)
        return True

    monkeypatch.setattr(database_module, "registrar_documento_enviado", fake_register)

    result = service.enviar_comprobante_si_corresponde(42, "mp-123")

    assert result["success"] is True
    assert len(recorded) == 2
    assert {entry["delivery_channel"] for entry in recorded} == {"email", "telegram"}