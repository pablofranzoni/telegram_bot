"""Unit tests for the /api/invoices REST endpoints (read-only)."""

from decimal import Decimal
from unittest.mock import patch

import pytest

from shared.services.invoice_service import InvoiceDTO, InvoiceItemDTO


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #

def _make_invoice(
    invoice_id: int = 1,
    fecha: str = "2026-04-20 10:00:00",
    estado: str = "pendiente",
    total: Decimal = Decimal("250.00"),
    customer_db_id: int = 1,
    customer_name: str = "Pablo Franzoni",
    telegram_id: str = "7225069015",
) -> InvoiceDTO:
    return InvoiceDTO(
        id=invoice_id,
        fecha=fecha,
        estado=estado,
        total=total,
        customer_db_id=customer_db_id,
        customer_name=customer_name,
        telegram_id=telegram_id,
    )


def _make_item(
    item_id: int = 1,
    product_id: int = 10,
    product_name: str = "Pizza Muzzarella",
    product_description: str = "Con extra queso",
    cantidad: int = 2,
    precio_unitario: Decimal = Decimal("700.00"),
    subtotal: Decimal = Decimal("1400.00"),
) -> InvoiceItemDTO:
    return InvoiceItemDTO(
        id=item_id,
        product_id=product_id,
        product_name=product_name,
        product_description=product_description,
        cantidad=cantidad,
        precio_unitario=precio_unitario,
        subtotal=subtotal,
    )


# --------------------------------------------------------------------------- #
#  Flask test client fixture
# --------------------------------------------------------------------------- #

@pytest.fixture
def client():
    """Creates a Flask test client with a clean app instance."""
    from flask import Flask
    from routes.invoices_routes import invoices_bp

    app = Flask(__name__)
    app.register_blueprint(invoices_bp, url_prefix="/api")
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ===========================================================================
#  GET /api/invoices
# ===========================================================================

class TestListInvoices:
    def test_returns_200_with_invoices(self, client):
        dtos = [_make_invoice(1), _make_invoice(2, estado="pagado", total=Decimal("500.00"))]
        with patch("routes.invoices_routes.invoice_service.list_invoices", return_value=(dtos, 2)):
            response = client.get("/api/invoices")

        assert response.status_code == 200
        body = response.get_json()
        assert len(body["invoices"]) == 2
        assert body["invoices"][0]["id"] == 1
        assert body["invoices"][1]["estado"] == "pagado"

    def test_empty_list_returns_200(self, client):
        with patch("routes.invoices_routes.invoice_service.list_invoices", return_value=([], 0)):
            response = client.get("/api/invoices")
        assert response.status_code == 200
        body = response.get_json()
        assert body["invoices"] == []
        assert body["pagination"]["total"] == 0

    def test_pagination_params_forwarded(self, client):
        with patch("routes.invoices_routes.invoice_service.list_invoices", return_value=([], 0)) as mock_svc:
            client.get("/api/invoices?page=2&per_page=5")
        mock_svc.assert_called_once_with(page=2, per_page=5, estado=None, customer_id=None)

    def test_estado_filter_forwarded(self, client):
        dto = _make_invoice(estado="pagado")
        with patch("routes.invoices_routes.invoice_service.list_invoices", return_value=([dto], 1)) as mock_svc:
            response = client.get("/api/invoices?estado=pagado")
        assert response.status_code == 200
        mock_svc.assert_called_once_with(page=1, per_page=10, estado="pagado", customer_id=None)

    def test_invalid_estado_returns_400(self, client):
        response = client.get("/api/invoices?estado=invalido")
        assert response.status_code == 400
        assert "estado inválido" in response.get_json()["error"]

    def test_customer_id_filter_forwarded(self, client):
        with patch("routes.invoices_routes.invoice_service.list_invoices", return_value=([], 0)) as mock_svc:
            response = client.get("/api/invoices?customer_id=3")
        assert response.status_code == 200
        mock_svc.assert_called_once_with(page=1, per_page=10, estado=None, customer_id=3)

    def test_invalid_customer_id_returns_400(self, client):
        response = client.get("/api/invoices?customer_id=abc")
        assert response.status_code == 400
        assert "customer_id" in response.get_json()["error"]

    def test_invalid_page_returns_400(self, client):
        response = client.get("/api/invoices?page=nope")
        assert response.status_code == 400

    def test_pagination_shape(self, client):
        dtos = [_make_invoice(i) for i in range(1, 4)]
        with patch("routes.invoices_routes.invoice_service.list_invoices", return_value=(dtos, 3)):
            response = client.get("/api/invoices?page=1&per_page=10")

        body = response.get_json()
        pagination = body["pagination"]
        assert pagination["page"] == 1
        assert pagination["per_page"] == 10
        assert pagination["total"] == 3
        assert pagination["total_pages"] == 1


# ===========================================================================
#  GET /api/invoices/<id>
# ===========================================================================

class TestGetInvoice:
    def test_returns_invoice_with_items(self, client):
        dto = _make_invoice(5)
        items = [_make_item(1), _make_item(2, product_name="Coca Cola", cantidad=1, precio_unitario=Decimal("300.00"), subtotal=Decimal("300.00"))]
        with patch("routes.invoices_routes.invoice_service.get_invoice", return_value=dto), \
             patch("routes.invoices_routes.invoice_service.get_invoice_items", return_value=items):
            response = client.get("/api/invoices/5")

        assert response.status_code == 200
        body = response.get_json()
        assert body["id"] == 5
        assert body["customer"]["nombre"] == "Pablo Franzoni"
        assert len(body["items"]) == 2
        assert body["items"][0]["product_name"] == "Pizza Muzzarella"

    def test_returns_404_when_not_found(self, client):
        with patch("routes.invoices_routes.invoice_service.get_invoice", return_value=None):
            response = client.get("/api/invoices/999")
        assert response.status_code == 404
        assert "Invoice no encontrada" in response.get_json()["error"]

    def test_invoice_total_is_float(self, client):
        dto = _make_invoice(1, total=Decimal("123.45"))
        with patch("routes.invoices_routes.invoice_service.get_invoice", return_value=dto), \
             patch("routes.invoices_routes.invoice_service.get_invoice_items", return_value=[]):
            response = client.get("/api/invoices/1")
        assert isinstance(response.get_json()["total"], float)


# ===========================================================================
#  GET /api/invoices/<id>/items
# ===========================================================================

class TestGetInvoiceItems:
    def test_returns_items_for_existing_invoice(self, client):
        dto = _make_invoice(3)
        items = [_make_item(1), _make_item(2)]
        with patch("routes.invoices_routes.invoice_service.get_invoice", return_value=dto), \
             patch("routes.invoices_routes.invoice_service.get_invoice_items", return_value=items):
            response = client.get("/api/invoices/3/items")

        assert response.status_code == 200
        body = response.get_json()
        assert body["invoice_id"] == 3
        assert len(body["items"]) == 2

    def test_returns_empty_items_list(self, client):
        dto = _make_invoice(4)
        with patch("routes.invoices_routes.invoice_service.get_invoice", return_value=dto), \
             patch("routes.invoices_routes.invoice_service.get_invoice_items", return_value=[]):
            response = client.get("/api/invoices/4/items")

        assert response.status_code == 200
        assert response.get_json()["items"] == []

    def test_returns_404_when_invoice_not_found(self, client):
        with patch("routes.invoices_routes.invoice_service.get_invoice", return_value=None):
            response = client.get("/api/invoices/999/items")
        assert response.status_code == 404

    def test_item_fields_present(self, client):
        dto = _make_invoice(1)
        item = _make_item()
        with patch("routes.invoices_routes.invoice_service.get_invoice", return_value=dto), \
             patch("routes.invoices_routes.invoice_service.get_invoice_items", return_value=[item]):
            response = client.get("/api/invoices/1/items")

        item_body = response.get_json()["items"][0]
        assert "id" in item_body
        assert "product_id" in item_body
        assert "product_name" in item_body
        assert "product_description" in item_body
        assert "cantidad" in item_body
        assert "precio_unitario" in item_body
        assert "subtotal" in item_body


# ===========================================================================
#  GET /api/invoices/by-customer/<telegram_id>
# ===========================================================================

class TestListInvoicesByCustomer:
    def test_returns_invoices_for_existing_customer(self, client):
        dtos = [_make_invoice(1), _make_invoice(2, estado="pagado")]
        with patch("routes.invoices_routes.invoice_service.list_invoices_by_customer", return_value=(dtos, 2)):
            response = client.get("/api/invoices/by-customer/7225069015")

        assert response.status_code == 200
        body = response.get_json()
        assert body["telegram_id"] == "7225069015"
        assert len(body["invoices"]) == 2

    def test_returns_404_when_customer_not_found(self, client):
        with patch("routes.invoices_routes.invoice_service.list_invoices_by_customer", return_value=None):
            response = client.get("/api/invoices/by-customer/9999999999")
        assert response.status_code == 404
        assert "Cliente no encontrado" in response.get_json()["error"]

    def test_estado_filter_forwarded(self, client):
        with patch("routes.invoices_routes.invoice_service.list_invoices_by_customer", return_value=([], 0)) as mock_svc:
            client.get("/api/invoices/by-customer/7225069015?estado=pagado")
        mock_svc.assert_called_once_with(telegram_id="7225069015", page=1, per_page=10, estado="pagado")

    def test_invalid_estado_returns_400(self, client):
        response = client.get("/api/invoices/by-customer/7225069015?estado=roto")
        assert response.status_code == 400

    def test_pagination_params_forwarded(self, client):
        with patch("routes.invoices_routes.invoice_service.list_invoices_by_customer", return_value=([], 0)) as mock_svc:
            client.get("/api/invoices/by-customer/7225069015?page=3&per_page=5")
        mock_svc.assert_called_once_with(telegram_id="7225069015", page=3, per_page=5, estado=None)

    def test_pagination_shape_present(self, client):
        with patch("routes.invoices_routes.invoice_service.list_invoices_by_customer", return_value=([], 0)):
            response = client.get("/api/invoices/by-customer/7225069015")
        body = response.get_json()
        assert "pagination" in body
        assert body["pagination"]["total"] == 0

    def test_empty_invoice_list_returns_200(self, client):
        with patch("routes.invoices_routes.invoice_service.list_invoices_by_customer", return_value=([], 0)):
            response = client.get("/api/invoices/by-customer/7225069015")
        assert response.status_code == 200
        assert response.get_json()["invoices"] == []


# ===========================================================================
#  Verify write methods are NOT exposed
# ===========================================================================

class TestNoWriteEndpoints:
    @pytest.mark.parametrize("method,url", [
        ("post", "/api/invoices"),
        ("put", "/api/invoices/1"),
        ("patch", "/api/invoices/1"),
        ("delete", "/api/invoices/1"),
        ("post", "/api/invoices/1/items"),
        ("delete", "/api/invoices/1/items"),
    ])
    def test_write_methods_return_405(self, client, method, url):
        response = getattr(client, method)(url, json={})
        assert response.status_code == 405
