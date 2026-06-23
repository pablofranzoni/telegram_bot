"""Unit tests for the /api/invoices REST endpoints (read-only)."""

from decimal import Decimal
from unittest.mock import patch

import pytest

from shared.services.invoice_service import InvoiceDTO, InvoiceItemDTO


# Helpers
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


# ===========================================================================
#  GET /api/invoices (PROTECTED - Requires JWT token)
# ===========================================================================
class TestListInvoices:
    """Test cases for GET /api/invoices endpoint."""
    
    def test_list_invoices_without_token_returns_401(self, client):
        """Test that listing invoices without JWT token returns 401."""
        response = client.get("/api/invoices")
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['status'] == 'error'
    
    def test_list_invoices_with_invalid_token_returns_401(self, client):
        """Test that listing invoices with invalid JWT token returns 401."""
        response = client.get(
            "/api/invoices",
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['status'] == 'error'

    def test_list_invoices_with_valid_token_returns_200(self, client, auth_headers):
        """Test that listing invoices with valid JWT token returns 200."""
        invoices = [_make_invoice(1), _make_invoice(2, customer_name="Ana García")]
        
        with patch("routes.invoices_routes.invoice_service.list_invoices", return_value=(invoices, 2)):
            response = client.get("/api/invoices", headers=auth_headers)

        assert response.status_code == 200
        body = response.get_json()
        assert len(body["invoices"]) == 2
        assert body["pagination"]["total"] == 2

    def test_list_invoices_with_pagination(self, client, auth_headers):
        """Test invoices list with pagination parameters."""
        invoices = [_make_invoice(1)]
        
        with patch("routes.invoices_routes.invoice_service.list_invoices", return_value=(invoices, 1)):
            response = client.get(
                "/api/invoices?page=1&per_page=10",
                headers=auth_headers
            )

        assert response.status_code == 200
        body = response.get_json()
        assert body["pagination"]["page"] == 1

    def test_list_invoices_empty_returns_200(self, client, auth_headers):
        """Test that empty invoices list returns 200."""
        with patch("routes.invoices_routes.invoice_service.list_invoices", return_value=([], 0)):
            response = client.get("/api/invoices", headers=auth_headers)

        assert response.status_code == 200
        body = response.get_json()
        assert body["invoices"] == []


# ===========================================================================
#  GET /api/invoices/<id> (PROTECTED - Requires JWT token)
# ===========================================================================
class TestGetInvoice:
    """Test cases for GET /api/invoices/<id> endpoint."""
    
    def test_get_invoice_without_token_returns_401(self, client):
        """Test that getting invoice without JWT token returns 401."""
        response = client.get("/api/invoices/1")
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['status'] == 'error'

    def test_get_invoice_with_valid_token_returns_200(self, client, auth_headers):
        """Test that getting invoice with valid JWT token returns 200."""
        invoice = _make_invoice(1)
        items = [_make_item(1), _make_item(2, product_name="Coca-Cola", subtotal=Decimal("30.00"))]
        
        with patch("routes.invoices_routes.invoice_service.get_invoice", return_value=invoice):
            with patch("routes.invoices_routes.invoice_service.get_invoice_items", return_value=items):
                response = client.get("/api/invoices/1", headers=auth_headers)

        assert response.status_code == 200
        body = response.get_json()
        assert body["id"] == 1
        assert len(body["items"]) == 2

    def test_get_nonexistent_invoice_returns_404(self, client, auth_headers):
        """Test that getting non-existent invoice returns 404."""
        with patch("routes.invoices_routes.invoice_service.get_invoice", return_value=None):
            response = client.get("/api/invoices/999", headers=auth_headers)

        assert response.status_code == 404


# ===========================================================================
#  GET /api/invoices/<id>/items (PROTECTED - Requires JWT token)
# ===========================================================================
class TestGetInvoiceItems:
    """Test cases for GET /api/invoices/<id>/items endpoint."""
    
    def test_get_invoice_items_without_token_returns_401(self, client):
        """Test that getting invoice items without JWT token returns 401."""
        response = client.get("/api/invoices/1/items")
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['status'] == 'error'

    def test_get_invoice_items_with_valid_token_returns_200(self, client, auth_headers):
        """Test that getting invoice items with valid JWT token returns 200."""
        invoice = _make_invoice(1)
        items = [_make_item(1), _make_item(2)]
        
        with patch("routes.invoices_routes.invoice_service.get_invoice", return_value=invoice):
            with patch("routes.invoices_routes.invoice_service.get_invoice_items", return_value=items):
                response = client.get("/api/invoices/1/items", headers=auth_headers)

        assert response.status_code == 200
        body = response.get_json()
        assert body["invoice_id"] == 1
        assert len(body["items"]) == 2

    def test_get_items_of_nonexistent_invoice_returns_404(self, client, auth_headers):
        """Test that getting items of non-existent invoice returns 404."""
        with patch("routes.invoices_routes.invoice_service.get_invoice", return_value=None):
            response = client.get("/api/invoices/999/items", headers=auth_headers)

        assert response.status_code == 404


# ===========================================================================
#  GET /api/invoices/by-customer/<telegram_id> (PROTECTED - Requires JWT token)
# ===========================================================================
class TestListInvoicesByCustomer:
    """Test cases for GET /api/invoices/by-customer/<telegram_id> endpoint."""
    
    def test_list_customer_invoices_without_token_returns_401(self, client):
        """Test that listing customer invoices without JWT token returns 401."""
        response = client.get("/api/invoices/by-customer/7225069015")
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['status'] == 'error'

    def test_list_customer_invoices_with_valid_token_returns_200(self, client, auth_headers):
        """Test that listing customer invoices with valid JWT token returns 200."""
        invoices = [_make_invoice(1, telegram_id="7225069015")]
        
        with patch("routes.invoices_routes.invoice_service.list_invoices_by_customer", return_value=(invoices, 1)):
            response = client.get(
                "/api/invoices/by-customer/7225069015",
                headers=auth_headers
            )

        assert response.status_code == 200
        body = response.get_json()
        assert len(body["invoices"]) == 1
        assert body["invoices"][0]["customer"]["telegram_id"] == "7225069015"

    def test_list_customer_invoices_no_results_returns_200(self, client, auth_headers):
        """Test that listing customer with no invoices returns 200."""
        with patch("routes.invoices_routes.invoice_service.list_invoices_by_customer", return_value=([], 0)):
            response = client.get(
                "/api/invoices/by-customer/9999999999",
                headers=auth_headers
            )

        assert response.status_code == 200
        body = response.get_json()
        assert body["invoices"] == []


# ===========================================================================
#  Write methods (POST, PUT, DELETE) should not be allowed
# ===========================================================================
class TestInvoiceReadOnlyConstraints:
    """Test that write operations are not allowed on invoices."""
    
    @pytest.mark.parametrize("method,url", [
        ("post", "/api/invoices"),
        ("put", "/api/invoices/1"),
        ("delete", "/api/invoices/1"),
        ("post", "/api/invoices/1/items"),
        ("delete", "/api/invoices/1/items"),
    ])
    def test_write_methods_return_405(self, client, method, url):
        """Test that write methods on invoices return 405 Method Not Allowed."""
        response = getattr(client, method)(url, json={})
        assert response.status_code == 405
