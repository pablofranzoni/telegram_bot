"""Tests for /api/products/<id>/stock REST endpoints."""

from unittest.mock import patch

import pytest
from flask_jwt_extended import create_access_token

from shared.services.inventory_service import InventoryDTO


def _make_inventory_dto(
    product_id: int = 1,
    stock_actual: int = 100,
    stock_reservado: int = 10,
    stock_disponible: int = 90,
    stock_minimo: int = 5,
    ultima_compra: str | None = "2026-08-01",
    ubicacion_almacen: str | None = "A-12",
) -> InventoryDTO:
    return InventoryDTO(
        product_id=product_id,
        stock_actual=stock_actual,
        stock_reservado=stock_reservado,
        stock_disponible=stock_disponible,
        stock_minimo=stock_minimo,
        ultima_compra=ultima_compra,
        ubicacion_almacen=ubicacion_almacen,
    )


# ===========================================================================
#  GET /api/products/<id>/stock
# ===========================================================================
class TestGetProductStock:
    """Test cases for GET /api/products/<id>/stock endpoint."""

    def test_get_stock_without_token_returns_401(self, client):
        """Listing stock without token returns 401."""
        response = client.get("/api/products/1/stock")
        assert response.status_code == 401
        data = response.get_json()
        assert data["status"] == "error"
        assert "MISSING_AUTH_TOKEN" in data.get("error_code", "")

    def test_get_stock_existing_product_returns_200(self, client, auth_headers):
        """Retrieving stock for an existing product returns inventory data."""
        dto = _make_inventory_dto()
        with patch(
            "routes.products_routes.inventory_service.get_inventory", return_value=dto
        ):
            response = client.get("/api/products/1/stock", headers=auth_headers)

        assert response.status_code == 200
        body = response.get_json()
        assert body["product_id"] == 1
        assert body["stock_actual"] == 100
        assert body["stock_reservado"] == 10
        assert body["stock_disponible"] == 90
        assert body["stock_minimo"] == 5
        assert body["ultima_compra"] == "2026-08-01"
        assert body["ubicacion_almacen"] == "A-12"

    def test_get_stock_nonexistent_product_returns_404(self, client, auth_headers):
        """Retrieving stock for a missing product returns 404."""
        with patch(
            "routes.products_routes.inventory_service.get_inventory", return_value=None
        ):
            response = client.get("/api/products/999/stock", headers=auth_headers)

        assert response.status_code == 404
        assert response.get_json()["error"] == "Producto no encontrado"


# ===========================================================================
#  POST /api/products/<id>/stock
# ===========================================================================
class TestAddProductStock:
    """Test cases for POST /api/products/<id>/stock endpoint (admin only)."""

    def test_add_stock_without_token_returns_401(self, client):
        """Adding stock without token returns 401."""
        response = client.post("/api/products/1/stock", json={"cantidad": 10})
        assert response.status_code == 401

    def test_add_stock_non_admin_returns_403(self, client, app, setup_test_admin):
        """Non-admin users cannot add stock."""
        from database.db_manager import get_db
        from shared.services.user_service import UserService

        user = UserService.create_api_user(
            username="regular_user",
            email="regular@example.com",
            name="Regular User",
            password="RegularPass123!",
            created_by_id=setup_test_admin["id"],
        )
        db = get_db()
        db.execute(
            """
            UPDATE customers
            SET is_admin = 0, email_verified = 1,
                email_verification_code = NULL,
                email_verification_expires = NULL
            WHERE id = ?
            """,
            (user["id"],),
        )
        db.commit()

        with app.app_context():
            token = create_access_token(identity="regular_user")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        response = client.post(
            "/api/products/1/stock", json={"cantidad": 10}, headers=headers
        )

        assert response.status_code == 403

    def test_add_stock_missing_cantidad_returns_400(self, client, admin_auth_headers):
        """Missing cantidad returns 400."""
        response = client.post(
            "/api/products/1/stock", json={}, headers=admin_auth_headers
        )
        assert response.status_code == 400
        assert "cantidad" in response.get_json()["error"].lower()

    def test_add_stock_invalid_cantidad_returns_400(self, client, admin_auth_headers):
        """Non-positive cantidad returns 400."""
        response = client.post(
            "/api/products/1/stock",
            json={"cantidad": -5},
            headers=admin_auth_headers,
        )
        assert response.status_code == 400

    def test_add_stock_invalid_tipo_returns_400(self, client, admin_auth_headers):
        """Invalid movement type returns 400."""
        response = client.post(
            "/api/products/1/stock",
            json={"cantidad": 5, "tipo": "venta"},
            headers=admin_auth_headers,
        )
        assert response.status_code == 400

    def test_add_stock_negative_costo_returns_400(self, client, admin_auth_headers):
        """Negative costo_unitario returns 400."""
        response = client.post(
            "/api/products/1/stock",
            json={"cantidad": 5, "costo_unitario": -1},
            headers=admin_auth_headers,
        )
        assert response.status_code == 400

    def test_add_stock_product_not_found_returns_404(self, client, admin_auth_headers):
        """Adding stock to a missing product returns 404."""
        with patch(
            "routes.products_routes.inventory_service.add_stock", return_value=None
        ):
            response = client.post(
                "/api/products/999/stock",
                json={"cantidad": 10},
                headers=admin_auth_headers,
            )

        assert response.status_code == 404
        assert response.get_json()["error"] == "Producto no encontrado"

    def test_add_stock_valid_payload_returns_201(self, client, admin_auth_headers):
        """Valid stock addition returns 201 with movement summary."""
        result = {
            "movement_id": 42,
            "product_id": 1,
            "stock_actual": 110,
            "stock_disponible": 110,
        }
        with patch(
            "routes.products_routes.inventory_service.add_stock", return_value=result
        ) as mock_add:
            response = client.post(
                "/api/products/1/stock",
                json={
                    "cantidad": 10,
                    "tipo": "compra",
                    "costo_unitario": 5.5,
                    "referencia": "OC-001",
                },
                headers=admin_auth_headers,
            )

        assert response.status_code == 201
        body = response.get_json()
        assert body["movement_id"] == 42
        assert body["stock_actual"] == 110
        assert body["stock_disponible"] == 110

        call_kwargs = mock_add.call_args.kwargs
        assert call_kwargs["cantidad"] == 10
        assert call_kwargs["movement_type"] == "compra"
        assert call_kwargs["costo_unitario"] == 5.5
        assert call_kwargs["referencia"] == "OC-001"
