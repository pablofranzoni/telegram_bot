"""Tests for MercadoPago processing paths used by webhook merchant_order."""

from types import SimpleNamespace

from utils import mpago


def _build_service_with_sdk(payment_response: dict):
    service = mpago.MercadoPagoSimple.__new__(mpago.MercadoPagoSimple)
    service.sdk = SimpleNamespace(
        payment=lambda: SimpleNamespace(get=lambda payment_id: payment_response)
    )
    return service


def test_procesar_pago_approved_delegates_business_logic(monkeypatch):
    payment_response = {
        "status": 200,
        "response": {
            "id": 999,
            "status": "approved",
            "transaction_amount": 100.0,
            "external_reference": "telegram_123_456_100.0",
            "metadata": {},
            "status_detail": "accredited",
            "payment_method": {"id": "visa"},
        },
    }
    service = _build_service_with_sdk(payment_response)

    called = {"count": 0, "payment": None}

    def fake_aprobado(payment):
        called["count"] += 1
        called["payment"] = payment
        return {"success": True, "action": "aprobado", "invoice_id": "456"}

    monkeypatch.setattr(service, "procesar_pago_aprobado", fake_aprobado)

    result = service.procesar_pago(999, desde_orden=True)

    assert called["count"] == 1
    assert called["payment"]["status"] == "approved"
    assert called["payment"]["monto"] == 100.0
    assert result["success"] is True
    assert result["action"] == "aprobado"


def test_procesar_pago_pending_delegates_business_logic(monkeypatch):
    payment_response = {
        "status": 200,
        "response": {
            "id": 1000,
            "status": "pending",
            "transaction_amount": 55.5,
            "external_reference": "telegram_777_888_55.5",
            "metadata": {},
            "payment_method": {"id": "master"},
        },
    }
    service = _build_service_with_sdk(payment_response)

    called = {"count": 0}

    def fake_pendiente(payment):
        called["count"] += 1
        return {"success": True, "action": "pendiente", "invoice_id": "888"}

    monkeypatch.setattr(service, "procesar_pago_pendiente", fake_pendiente)

    result = service.procesar_pago(1000, desde_orden=True)

    assert called["count"] == 1
    assert result["action"] == "pendiente"


def test_procesar_pago_returns_error_when_ids_cannot_be_extracted():
    payment_response = {
        "status": 200,
        "response": {
            "id": 1111,
            "status": "approved",
            "transaction_amount": 10.0,
            "external_reference": "",
            "metadata": {},
        },
    }
    service = _build_service_with_sdk(payment_response)

    result = service.procesar_pago(1111, desde_orden=True)

    assert result["success"] is False
    assert result["action"] == "id_no_encontrado"
