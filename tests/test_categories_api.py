"""Unit tests for the /api/categories REST endpoint."""

from unittest.mock import patch

import pytest

from shared.dtos import CategoryDTO


# --------------------------------------------------------------------------- #
#  Flask test client fixture
# --------------------------------------------------------------------------- #
@pytest.fixture
def client():
    """Creates a Flask test client with a clean app instance."""
    from flask import Flask
    from routes.categories_routes import categories_bp

    app = Flask(__name__)
    app.register_blueprint(categories_bp, url_prefix="/api")
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# --------------------------------------------------------------------------- #
#  Sample data helpers
# --------------------------------------------------------------------------- #
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
#  GET /api/categories
# ===========================================================================
class TestListCategories:
    def test_returns_200_with_categories(self, client):
        dtos = [_make_dto(1), _make_dto(2, codigo="HAM", name="Hamburguesas", description="Hamburguesas gourmet")]
        with patch("routes.categories_routes.category_service.list_categories", return_value=dtos):
            response = client.get("/api/categories")

        assert response.status_code == 200
        body = response.get_json()
        assert len(body["categories"]) == 2
        assert body["categories"][0]["codigo"] == "PIZ"
        assert body["categories"][1]["nombre"] == "Hamburguesas"

    def test_empty_list_returns_200(self, client):
        with patch("routes.categories_routes.category_service.list_categories", return_value=[]):
            response = client.get("/api/categories")
        assert response.status_code == 200
        assert response.get_json()["categories"] == []


# ===========================================================================
#  GET /api/categories/<id>
# ===========================================================================
class TestGetCategory:
    def test_returns_category_when_found(self, client):
        dto = _make_dto(3)
        with patch("routes.categories_routes.category_service.get_category", return_value=dto):
            response = client.get("/api/categories/3")

        assert response.status_code == 200
        body = response.get_json()
        assert body["id"] == 3
        assert body["codigo"] == "PIZ"

    def test_returns_404_when_not_found(self, client):
        with patch("routes.categories_routes.category_service.get_category", return_value=None):
            response = client.get("/api/categories/999")
        assert response.status_code == 404


# ===========================================================================
#  POST /api/categories
# ===========================================================================
class TestCreateCategory:
    def test_creates_category_successfully(self, client):
        dto = _make_dto(5)
        with patch("routes.categories_routes.category_service.create_category", return_value=dto):
            response = client.post(
                "/api/categories",
                json={"codigo": "piz", "nombre": "Pizzas", "descripcion": "Pizzas artesanales"},
            )

        assert response.status_code == 201
        body = response.get_json()
        assert body["id"] == 5
        assert body["codigo"] == "PIZ"  # normalized to uppercase

    def test_missing_required_fields_returns_400(self, client):
        response = client.post("/api/categories", json={"codigo": "PIZ"})
        assert response.status_code == 400
        assert "faltantes" in response.get_json()["error"]

    def test_no_json_body_returns_400(self, client):
        response = client.post("/api/categories")
        assert response.status_code == 400

    def test_codigo_too_long_returns_400(self, client):
        response = client.post(
            "/api/categories",
            json={"codigo": "TOOLONGCODE", "nombre": "X", "descripcion": "Y"},
        )
        assert response.status_code == 400

    def test_invalid_parent_id_returns_400(self, client):
        response = client.post(
            "/api/categories",
            json={"codigo": "PIZ", "nombre": "Pizzas", "descripcion": "X", "parent_id": "abc"},
        )
        assert response.status_code == 400

    def test_service_failure_returns_500(self, client):
        with patch("routes.categories_routes.category_service.create_category", return_value=None):
            response = client.post(
                "/api/categories",
                json={"codigo": "PIZ", "nombre": "Pizzas", "descripcion": "X"},
            )
        assert response.status_code == 500

    def test_creates_with_parent_id(self, client):
        dto = _make_dto(6, codigo="SUB", name="Subcat", description="Sub", parent_id=1)
        with patch("routes.categories_routes.category_service.create_category", return_value=dto) as mock_create:
            client.post(
                "/api/categories",
                json={"codigo": "sub", "nombre": "Subcat", "descripcion": "Sub", "parent_id": 1},
            )
        mock_create.assert_called_once_with(codigo="SUB", nombre="Subcat", descripcion="Sub", parent_id=1)


# ===========================================================================
#  PUT /api/categories/<id>
# ===========================================================================
class TestUpdateCategory:
    def test_updates_category_successfully(self, client):
        dto = _make_dto(1, description="Pizzas italianas")
        with patch("routes.categories_routes.category_service.update_category", return_value=dto):
            response = client.put("/api/categories/1", json={"descripcion": "Pizzas italianas"})

        assert response.status_code == 200
        assert response.get_json()["descripcion"] == "Pizzas italianas"

    def test_returns_404_when_not_found(self, client):
        with patch("routes.categories_routes.category_service.update_category", return_value=None):
            response = client.put("/api/categories/999", json={"nombre": "X"})
        assert response.status_code == 404

    def test_no_json_body_returns_400(self, client):
        response = client.put("/api/categories/1")
        assert response.status_code == 400

    def test_no_valid_fields_returns_400(self, client):
        response = client.put("/api/categories/1", json={"unknown_field": "value"})
        assert response.status_code == 400

    def test_codigo_is_uppercased(self, client):
        dto = _make_dto(1, codigo="HAM")
        with patch("routes.categories_routes.category_service.update_category", return_value=dto) as mock_update:
            client.put("/api/categories/1", json={"codigo": "ham"})
        _, kwargs = mock_update.call_args
        assert mock_update.call_args[0][1]["codigo"] == "HAM"

    def test_invalid_parent_id_returns_400(self, client):
        response = client.put("/api/categories/1", json={"parent_id": "bad"})
        assert response.status_code == 400


# ===========================================================================
#  DELETE /api/categories/<id>
# ===========================================================================
class TestDeleteCategory:
    def test_deletes_category_successfully(self, client):
        with patch("routes.categories_routes.category_service.delete_category", return_value=True):
            response = client.delete("/api/categories/1")

        assert response.status_code == 200
        assert "eliminada" in response.get_json()["message"]

    def test_returns_404_when_not_found(self, client):
        with patch("routes.categories_routes.category_service.delete_category", return_value=False):
            response = client.delete("/api/categories/999")
        assert response.status_code == 404
