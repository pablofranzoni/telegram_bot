"""Unit tests for the /api/products REST endpoint."""

from decimal import Decimal
from unittest.mock import patch

import pytest

from shared.dtos import ProductDTO


# --------------------------------------------------------------------------- #
#  Flask test client fixture
# --------------------------------------------------------------------------- #
@pytest.fixture
def client():
    """Creates a Flask test client with a clean app instance."""
    from flask import Flask
    from routes.products_routes import products_bp

    app = Flask(__name__)
    app.register_blueprint(products_bp, url_prefix="/api")
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# --------------------------------------------------------------------------- #
#  Sample data helpers
# --------------------------------------------------------------------------- #
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
#  GET /api/products
# ===========================================================================
class TestListProducts:
    def test_returns_200_with_products_and_pagination(self, client):
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
        response = client.get("/api/products?page=abc")
        assert response.status_code == 400

    def test_empty_list_returns_200(self, client):
        with patch("routes.products_routes.product_service.list_products", return_value=([], 0)):
            response = client.get("/api/products")
        assert response.status_code == 200
        body = response.get_json()
        assert body["products"] == []
        assert body["pagination"]["total"] == 0


# ===========================================================================
#  GET /api/products/<id>
# ===========================================================================
class TestGetProduct:
    def test_returns_product_when_found(self, client):
        dto = _make_dto(7)
        with patch("routes.products_routes.product_service.get_product", return_value=dto):
            response = client.get("/api/products/7")

        assert response.status_code == 200
        body = response.get_json()
        assert body["id"] == 7
        assert body["nombre"] == "Coca-Cola"

    def test_returns_404_when_not_found(self, client):
        with patch("routes.products_routes.product_service.get_product", return_value=None):
            response = client.get("/api/products/999")

        assert response.status_code == 404
        assert "error" in response.get_json()


# ===========================================================================
#  POST /api/products
# ===========================================================================
class TestCreateProduct:
    _valid_payload = {
        "nombre": "Agua Mineral",
        "descripcion": "Botella 1L",
        "precio": 1.50,
        "category_id": 2,
    }

    def test_creates_product_and_returns_201(self, client):
        new_dto = _make_dto(10, name="Agua Mineral", price="1.50", stock=0)
        with patch("routes.products_routes.product_service.create_product", return_value=new_dto):
            response = client.post("/api/products", json=self._valid_payload)

        assert response.status_code == 201
        body = response.get_json()
        assert body["id"] == 10
        assert body["nombre"] == "Agua Mineral"

    def test_stock_inicial_is_forwarded(self, client):
        captured: dict = {}

        def fake_create(**kwargs):
            captured.update(kwargs)
            return _make_dto(11, stock=kwargs.get("stock_inicial", 0))

        payload = {**self._valid_payload, "stock_inicial": 25}
        with patch("routes.products_routes.product_service.create_product", side_effect=fake_create):
            client.post("/api/products", json=payload)

        assert captured["stock_inicial"] == 25

    def test_missing_required_field_returns_400(self, client):
        payload = {k: v for k, v in self._valid_payload.items() if k != "precio"}
        response = client.post("/api/products", json=payload)
        assert response.status_code == 400
        assert "precio" in response.get_json()["error"]

    def test_negative_precio_returns_400(self, client):
        payload = {**self._valid_payload, "precio": -5}
        response = client.post("/api/products", json=payload)
        assert response.status_code == 400

    def test_invalid_category_id_returns_400(self, client):
        payload = {**self._valid_payload, "category_id": "abc"}
        response = client.post("/api/products", json=payload)
        assert response.status_code == 400

    def test_empty_nombre_returns_400(self, client):
        payload = {**self._valid_payload, "nombre": "   "}
        response = client.post("/api/products", json=payload)
        assert response.status_code == 400

    def test_no_body_returns_400(self, client):
        response = client.post("/api/products", data="not-json", content_type="text/plain")
        assert response.status_code == 400

    def test_service_failure_returns_500(self, client):
        with patch("routes.products_routes.product_service.create_product", return_value=None):
            response = client.post("/api/products", json=self._valid_payload)
        assert response.status_code == 500


# ===========================================================================
#  PUT /api/products/<id>
# ===========================================================================
class TestUpdateProduct:
    def test_updates_and_returns_200(self, client):
        updated_dto = _make_dto(3, name="Coca-Cola Zero")
        with patch("routes.products_routes.product_service.update_product", return_value=updated_dto):
            response = client.put("/api/products/3", json={"nombre": "Coca-Cola Zero"})

        assert response.status_code == 200
        assert response.get_json()["nombre"] == "Coca-Cola Zero"

    def test_unknown_fields_are_ignored(self, client):
        captured: dict = {}

        def fake_update(product_id, data):
            captured["data"] = data
            return _make_dto(3)

        with patch("routes.products_routes.product_service.update_product", side_effect=fake_update):
            client.put("/api/products/3", json={"nombre": "X", "unknown_field": "Y"})

        assert "unknown_field" not in captured["data"]

    def test_returns_404_when_not_found(self, client):
        with patch("routes.products_routes.product_service.update_product", return_value=None):
            response = client.put("/api/products/999", json={"nombre": "X"})
        assert response.status_code == 404

    def test_no_valid_fields_returns_400(self, client):
        response = client.put("/api/products/1", json={"unknown": "value"})
        assert response.status_code == 400

    def test_invalid_precio_returns_400(self, client):
        response = client.put("/api/products/1", json={"precio": "no-number"})
        assert response.status_code == 400

    def test_invalid_disponible_returns_400(self, client):
        response = client.put("/api/products/1", json={"disponible": "yes"})
        assert response.status_code == 400


# ===========================================================================
#  DELETE /api/products/<id>
# ===========================================================================
class TestDeactivateProduct:
    def test_deactivates_and_returns_200(self, client):
        with patch("routes.products_routes.product_service.deactivate_product", return_value=True):
            response = client.delete("/api/products/5")

        assert response.status_code == 200
        assert "desactivado" in response.get_json()["message"]

    def test_returns_404_when_not_found(self, client):
        with patch("routes.products_routes.product_service.deactivate_product", return_value=False):
            response = client.delete("/api/products/999")

        assert response.status_code == 404
