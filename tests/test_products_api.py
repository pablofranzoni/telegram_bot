"""Unit tests for the /api/products REST endpoint."""

from decimal import Decimal
from unittest.mock import patch

import pytest

from shared.dtos import ProductDTO


# Sample data helpers
def _make_dto(
    product_id: int = 1,
    name: str = "Coca-Cola",
    description: str = "Bebida 500ml",
    price: str = "2.50",
    stock: int = 10,
) -> ProductDTO:
    return ProductDTO(
        id=product_id,
        name=name,
        description=description,
        price=Decimal(price),
        stock_available=stock,
    )


# ===========================================================================
#  GET /api/products (PUBLIC - No authentication required)
# ===========================================================================
class TestListProducts:
    """Test cases for GET /api/products endpoint."""
    
    def test_returns_200_with_products_and_pagination(self, client):
        """Test that listing products returns paginated results."""
        dtos = [_make_dto(1), _make_dto(2, name="Sprite")]
        with patch("routes.products_routes.product_service.list_products", return_value=(dtos, 2)):
            response = client.get("/api/products")

        assert response.status_code == 200
        body = response.get_json()
        assert len(body["products"]) == 2
        assert body["products"][0]["nombre"] == "Coca-Cola"
        assert body["pagination"]["total"] == 2
        assert body["pagination"]["total_pages"] == 1

    def test_pagination_params_are_forwarded(self, client):
        """Test that pagination parameters are correctly forwarded."""
        captured: dict = {}

        def fake_list(page, per_page):
            captured["page"] = page
            captured["per_page"] = per_page
            return [], 0

        with patch("routes.products_routes.product_service.list_products", side_effect=fake_list):
            client.get("/api/products?page=3&per_page=5")

        assert captured["page"] == 3
        assert captured["per_page"] == 5

    def test_invalid_pagination_returns_400(self, client):
        """Test that invalid pagination parameters return 400."""
        response = client.get("/api/products?page=abc")
        assert response.status_code == 400

    def test_empty_list_returns_200(self, client):
        """Test that empty product list returns 200."""
        with patch("routes.products_routes.product_service.list_products", return_value=([], 0)):
            response = client.get("/api/products")

        assert response.status_code == 200
        body = response.get_json()
        assert body["products"] == []
        assert body["pagination"]["total"] == 0


# ===========================================================================
#  GET /api/products/<id> (PUBLIC - No authentication required)
# ===========================================================================
class TestGetProductById:
    """Test cases for GET /api/products/<id> endpoint."""
    
    def test_get_existing_product_returns_200(self, client):
        """Test retrieving an existing product."""
        dto = _make_dto(123, name="Pizza")
        with patch("routes.products_routes.product_service.get_product", return_value=dto):
            response = client.get("/api/products/123")

        assert response.status_code == 200
        body = response.get_json()
        assert body["id"] == 123
        assert body["nombre"] == "Pizza"

    def test_get_nonexistent_product_returns_404(self, client):
        """Test retrieving a non-existent product."""
        with patch("routes.products_routes.product_service.get_product", return_value=None):
            response = client.get("/api/products/999")

        assert response.status_code == 404
        assert response.get_json()["error"] == "Producto no encontrado"


# ===========================================================================
#  POST /api/products (PROTECTED - Requires JWT token)
# ===========================================================================
class TestCreateProduct:
    """Test cases for POST /api/products endpoint."""
    
    def test_create_product_without_token_returns_401(self, client):
        """Test that creating product without JWT token returns 401."""
        response = client.post(
            "/api/products",
            json={
                "nombre": "New Product",
                "descripcion": "Description",
                "precio": 10.0,
                "category_id": 1
            }
        )
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['status'] == 'error'
        assert 'MISSING_AUTH_HEADER' in data.get('error_code', '')
    
    def test_create_product_with_invalid_token_returns_401(self, client):
        """Test that creating product with invalid JWT token returns 401."""
        response = client.post(
            "/api/products",
            json={
                "nombre": "New Product",
                "descripcion": "Description",
                "precio": 10.0,
                "category_id": 1
            },
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['status'] == 'error'

    def test_create_product_with_valid_token_succeeds(self, client, auth_headers):
        """Test that creating product with valid JWT token succeeds."""
        created_dto = _make_dto(5, name="New Product")
        
        with patch("routes.products_routes.product_service.create_product", return_value=created_dto):
            response = client.post(
                "/api/products",
                json={
                    "nombre": "New Product",
                    "descripcion": "Description",
                    "precio": 2.50,
                    "category_id": 1
                },
                headers=auth_headers
            )

        assert response.status_code == 201
        body = response.get_json()
        assert body["nombre"] == "New Product"

    def test_create_product_missing_required_fields_returns_400(self, client, auth_headers):
        """Test that missing required fields return 400."""
        response = client.post(
            "/api/products",
            json={"nombre": "Product"},  # Missing other required fields
            headers=auth_headers
        )

        assert response.status_code == 400

    def test_create_product_invalid_price_returns_400(self, client, auth_headers):
        """Test that invalid price format returns 400."""
        response = client.post(
            "/api/products",
            json={
                "nombre": "Product",
                "descripcion": "Description",
                "precio": "not_a_number",
                "category_id": 1
            },
            headers=auth_headers
        )

        assert response.status_code == 400


# ===========================================================================
#  PUT /api/products/<id> (PROTECTED - Requires JWT token)
# ===========================================================================
class TestUpdateProduct:
    """Test cases for PUT /api/products/<id> endpoint."""
    
    def test_update_product_without_token_returns_401(self, client):
        """Test that updating product without JWT token returns 401."""
        response = client.put(
            "/api/products/1",
            json={"nombre": "Updated"}
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data['status'] == 'error'

    def test_update_product_with_valid_token_succeeds(self, client, auth_headers):
        """Test that updating product with valid JWT token succeeds."""
        updated_dto = _make_dto(1, name="Updated Product")
        
        with patch("routes.products_routes.product_service.update_product", return_value=updated_dto):
            response = client.put(
                "/api/products/1",
                json={"nombre": "Updated Product"},
                headers=auth_headers
            )

        assert response.status_code == 200
        body = response.get_json()
        assert body["nombre"] == "Updated Product"

    def test_update_nonexistent_product_returns_404(self, client, auth_headers):
        """Test that updating non-existent product returns 404."""
        with patch("routes.products_routes.product_service.update_product", return_value=None):
            response = client.put(
                "/api/products/999",
                json={"nombre": "Updated"},
                headers=auth_headers
            )

        assert response.status_code == 404


# ===========================================================================
#  DELETE /api/products/<id> (PROTECTED - Requires JWT token)
# ===========================================================================
class TestDeleteProduct:
    """Test cases for DELETE /api/products/<id> endpoint."""
    
    def test_delete_product_without_token_returns_401(self, client):
        """Test that deleting product without JWT token returns 401."""
        response = client.delete("/api/products/1")

        assert response.status_code == 401
        data = response.get_json()
        assert data['status'] == 'error'

    def test_delete_product_with_valid_token_succeeds(self, client, auth_headers):
        """Test that deleting product with valid JWT token succeeds."""
        with patch("routes.products_routes.product_service.deactivate_product", return_value=True):
            response = client.delete(
                "/api/products/1",
                headers=auth_headers
            )

        assert response.status_code == 200
        body = response.get_json()
        assert "message" in body

    def test_delete_nonexistent_product_returns_404(self, client, auth_headers):
        """Test that deleting non-existent product returns 404."""
        with patch("routes.products_routes.product_service.deactivate_product", return_value=False):
            response = client.delete(
                "/api/products/999",
                headers=auth_headers
            )

        assert response.status_code == 404
