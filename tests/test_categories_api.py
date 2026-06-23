"""Unit tests for the /api/categories REST endpoint."""

from unittest.mock import patch

import pytest

from shared.dtos import CategoryDTO


# Sample data helpers
def _make_dto(
    category_id: int = 1,
    codigo: str = "PIZ",
    name: str = "Pizzas",
    description: str = "Pizzas artesanales",
    parent_id: int | None = None,
) -> CategoryDTO:
    return CategoryDTO(
        id=category_id,
        codigo=codigo,
        name=name,
        description=description,
        parent_id=parent_id,
    )


# ===========================================================================
#  GET /api/categories (PUBLIC - No authentication required)
# ===========================================================================
class TestListCategories:
    """Test cases for GET /api/categories endpoint."""
    
    def test_returns_200_with_categories(self, client):
        """Test that listing categories returns all categories."""
        dtos = [_make_dto(1), _make_dto(2, codigo="HAM", name="Hamburguesas", description="Hamburguesas gourmet")]
        with patch("routes.categories_routes.category_service.list_categories", return_value=dtos):
            response = client.get("/api/categories")

        assert response.status_code == 200
        body = response.get_json()
        assert len(body["categories"]) == 2
        assert body["categories"][0]["codigo"] == "PIZ"
        assert body["categories"][1]["nombre"] == "Hamburguesas"

    def test_empty_list_returns_200(self, client):
        """Test that empty category list returns 200."""
        with patch("routes.categories_routes.category_service.list_categories", return_value=[]):
            response = client.get("/api/categories")
        assert response.status_code == 200
        assert response.get_json()["categories"] == []


# ===========================================================================
#  GET /api/categories/<id> (PUBLIC - No authentication required)
# ===========================================================================
class TestGetCategory:
    """Test cases for GET /api/categories/<id> endpoint."""
    
    def test_returns_category_when_found(self, client):
        """Test retrieving an existing category."""
        dto = _make_dto(3)
        with patch("routes.categories_routes.category_service.get_category", return_value=dto):
            response = client.get("/api/categories/3")

        assert response.status_code == 200
        body = response.get_json()
        assert body["id"] == 3
        assert body["codigo"] == "PIZ"

    def test_returns_404_when_category_not_found(self, client):
        """Test retrieving a non-existent category."""
        with patch("routes.categories_routes.category_service.get_category", return_value=None):
            response = client.get("/api/categories/999")

        assert response.status_code == 404
        assert response.get_json()["error"] == "Categoría no encontrada"


# ===========================================================================
#  POST /api/categories (PROTECTED - Requires JWT token)
# ===========================================================================
class TestCreateCategory:
    """Test cases for POST /api/categories endpoint."""
    
    def test_create_category_without_token_returns_401(self, client):
        """Test that creating category without JWT token returns 401."""
        response = client.post(
            "/api/categories",
            json={
                "codigo": "NEW",
                "nombre": "New Category",
                "descripcion": "Description"
            }
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data['status'] == 'error'

    def test_create_category_with_invalid_token_returns_401(self, client):
        """Test that creating category with invalid JWT token returns 401."""
        response = client.post(
            "/api/categories",
            json={
                "codigo": "NEW",
                "nombre": "New Category",
                "descripcion": "Description"
            },
            headers={"Authorization": "Bearer invalid_token"}
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data['status'] == 'error'

    def test_create_category_with_valid_token_succeeds(self, client, auth_headers):
        """Test that creating category with valid JWT token succeeds."""
        created_dto = _make_dto(5, codigo="BUR", name="Burgers")
        
        with patch("routes.categories_routes.category_service.create_category", return_value=created_dto):
            response = client.post(
                "/api/categories",
                json={
                    "codigo": "BUR",
                    "nombre": "Burgers",
                    "descripcion": "Fast food burgers"
                },
                headers=auth_headers
            )

        assert response.status_code == 201
        body = response.get_json()
        assert body["codigo"] == "BUR"
        assert body["nombre"] == "Burgers"

    def test_create_category_missing_required_fields_returns_400(self, client, auth_headers):
        """Test that missing required fields return 400."""
        response = client.post(
            "/api/categories",
            json={"codigo": "NEW"},  # Missing nombre and descripcion
            headers=auth_headers
        )

        assert response.status_code == 400

    def test_create_category_empty_body_returns_400(self, client, auth_headers):
        """Test that empty body returns 400."""
        response = client.post(
            "/api/categories",
            headers=auth_headers
        )

        assert response.status_code == 400


# ===========================================================================
#  PUT /api/categories/<id> (PROTECTED - Requires JWT token)
# ===========================================================================
class TestUpdateCategory:
    """Test cases for PUT /api/categories/<id> endpoint."""
    
    def test_update_category_without_token_returns_401(self, client):
        """Test that updating category without JWT token returns 401."""
        response = client.put(
            "/api/categories/1",
            json={"nombre": "Updated"}
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data['status'] == 'error'

    def test_update_category_with_valid_token_succeeds(self, client, auth_headers):
        """Test that updating category with valid JWT token succeeds."""
        updated_dto = _make_dto(1, name="Updated Pizzas")
        
        with patch("routes.categories_routes.category_service.update_category", return_value=updated_dto):
            response = client.put(
                "/api/categories/1",
                json={"nombre": "Updated Pizzas"},
                headers=auth_headers
            )

        assert response.status_code == 200
        body = response.get_json()
        assert body["nombre"] == "Updated Pizzas"

    def test_update_nonexistent_category_returns_404(self, client, auth_headers):
        """Test that updating non-existent category returns 404."""
        with patch("routes.categories_routes.category_service.update_category", return_value=None):
            response = client.put(
                "/api/categories/999",
                json={"nombre": "Updated"},
                headers=auth_headers
            )

        assert response.status_code == 404

    def test_update_category_empty_body_returns_400(self, client, auth_headers):
        """Test that empty body returns 400."""
        response = client.put(
            "/api/categories/1",
            headers=auth_headers
        )

        assert response.status_code == 400


# ===========================================================================
#  DELETE /api/categories/<id> (PROTECTED - Requires JWT token)
# ===========================================================================
class TestDeleteCategory:
    """Test cases for DELETE /api/categories/<id> endpoint."""
    
    def test_delete_category_without_token_returns_401(self, client):
        """Test that deleting category without JWT token returns 401."""
        response = client.delete("/api/categories/1")

        assert response.status_code == 401
        data = response.get_json()
        assert data['status'] == 'error'

    def test_delete_category_with_valid_token_succeeds(self, client, auth_headers):
        """Test that deleting category with valid JWT token succeeds."""
        with patch("routes.categories_routes.category_service.delete_category", return_value=True):
            response = client.delete(
                "/api/categories/1",
                headers=auth_headers
            )

        assert response.status_code == 200

    def test_delete_nonexistent_category_returns_404(self, client, auth_headers):
        """Test that deleting non-existent category returns 404."""
        with patch("routes.categories_routes.category_service.delete_category", return_value=False):
            response = client.delete(
                "/api/categories/999",
                headers=auth_headers
            )

        assert response.status_code == 404
