"""Unit tests for checkout_service."""

from decimal import Decimal

from shared.dtos import PaymentLinkResult
from shared.services import checkout_service


def test_finalize_checkout_requires_customer_email(monkeypatch):
    monkeypatch.setattr(checkout_service, "obtener_cliente", lambda telegram_id: {"email": None})

    result = checkout_service.finalize_checkout(telegram_id=123, invoice_id=42)

    assert result.success is False
    assert result.invoice_id == 42
    assert "email" in (result.error_message or "")


def test_finalize_checkout_requires_existing_invoice(monkeypatch):
    monkeypatch.setattr(checkout_service, "obtener_cliente", lambda telegram_id: {"email": "ana@example.com"})
    monkeypatch.setattr(checkout_service, "obtener_detalle_pedido", lambda invoice_id: (None, []))

    result = checkout_service.finalize_checkout(telegram_id=123, invoice_id=42)

    assert result.success is False
    assert result.invoice_id == 42
    assert "pedido" in (result.error_message or "").lower()


def test_finalize_checkout_propagates_payment_error(monkeypatch, sample_invoice_info, sample_invoice_items):
    monkeypatch.setattr(checkout_service, "obtener_cliente", lambda telegram_id: {"email": "ana@example.com"})
    monkeypatch.setattr(
        checkout_service,
        "obtener_detalle_pedido",
        lambda invoice_id: (sample_invoice_info, sample_invoice_items),
    )

    finalized = {"called": False}

    def fake_finalize(invoice_id):
        finalized["called"] = True

    monkeypatch.setattr(checkout_service, "finalizar_pedido_db", fake_finalize)
    monkeypatch.setattr(
        checkout_service,
        "create_payment_link",
        lambda **kwargs: PaymentLinkResult(success=False, error_message="mp down"),
    )

    saved = {"called": False}

    def fake_save(**kwargs):
        saved["called"] = True

    monkeypatch.setattr(checkout_service, "guardar_pago", fake_save)

    result = checkout_service.finalize_checkout(telegram_id=123, invoice_id=42)

    assert finalized["called"] is True
    assert saved["called"] is False
    assert result.success is False
    assert result.amount == Decimal("25.50")
    assert result.title == "Pedido #0000000042"
    assert result.error_message == "mp down"


def test_finalize_checkout_success(monkeypatch, sample_invoice_info, sample_invoice_items):
    monkeypatch.setattr(checkout_service, "obtener_cliente", lambda telegram_id: {"email": "ana@example.com"})
    monkeypatch.setattr(
        checkout_service,
        "obtener_detalle_pedido",
        lambda invoice_id: (sample_invoice_info, sample_invoice_items),
    )

    finalized = {"invoice_id": None}

    def fake_finalize(invoice_id):
        finalized["invoice_id"] = invoice_id

    monkeypatch.setattr(checkout_service, "finalizar_pedido_db", fake_finalize)
    monkeypatch.setattr(
        checkout_service,
        "create_payment_link",
        lambda **kwargs: PaymentLinkResult(
            success=True,
            preference_id="pref-123",
            init_point="https://sandbox.mercadopago.test/pay",
            external_reference="telegram_123_42_25.50",
        ),
    )

    saved = {}

    def fake_save(**kwargs):
        saved.update(kwargs)

    monkeypatch.setattr(checkout_service, "guardar_pago", fake_save)

    result = checkout_service.finalize_checkout(telegram_id=123, invoice_id=42)

    assert finalized["invoice_id"] == 42
    assert saved == {
        "telegram_id": 123,
        "mp_payment_id": None,
        "invoice_id": 42,
        "monto": 25.5,
        "concepto": "Pedido #0000000042",
    }
    assert result.success is True
    assert result.invoice_id == 42
    assert result.amount == Decimal("25.50")
    assert result.payment_preference_id == "pref-123"
    assert result.payment_url == "https://sandbox.mercadopago.test/pay"