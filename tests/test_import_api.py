"""Tests for the Excel import API endpoints."""

import io
import pytest
from openpyxl import Workbook

from database.db_manager import get_db


def _make_xlsx_bytes(sheet_name: str, headers: list[str], rows: list[list]) -> io.BytesIO:
    """Build an in-memory .xlsx file and return it as a BytesIO."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


class TestLoadCategories:
    """Tests for POST /api/load_categories."""

    def test_get_returns_help(self, client, auth_headers):
        response = client.get("/api/load_categories", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["sheet_name"] == "categories"
        assert "codigo" in data["columns"]["required"]

    def test_without_token_returns_401(self, client):
        response = client.post("/api/load_categories")
        assert response.status_code == 401

    def test_with_valid_xlsx_returns_200(self, client, auth_headers):
        xlsx = _make_xlsx_bytes(
            "categories",
            ["codigo", "nombre", "descripcion"],
            [["PIZ", "Pizzas", "Pizzas caseras"]],
        )

        response = client.post(
            "/api/load_categories",
            headers={"Authorization": auth_headers["Authorization"]},
            data={"file": (xlsx, "categorias.xlsx")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["created"] == 1
        assert data["processed_rows"] == 1

    def test_invalid_extension_returns_400(self, client, auth_headers):
        response = client.post(
            "/api/load_categories",
            headers={"Authorization": auth_headers["Authorization"]},
            data={"file": (io.BytesIO(b"not excel"), "datos.txt")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 400
        assert "xlsx" in response.get_json()["error"].lower()

    def test_missing_file_returns_400(self, client, auth_headers):
        response = client.post(
            "/api/load_categories",
            headers={"Authorization": auth_headers["Authorization"]},
        )

        assert response.status_code == 400


class TestLoadProducts:
    """Tests for POST /api/load_products."""

    def test_get_returns_help(self, client, auth_headers):
        response = client.get("/api/load_products", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["sheet_name"] == "products"
        assert "category_name" in data["columns"]["required"]

    def test_without_token_returns_401(self, client):
        response = client.post("/api/load_products")
        assert response.status_code == 401

    def test_with_valid_xlsx_returns_200(self, client, auth_headers):
        db = get_db()
        db.execute(
            "INSERT INTO categories (codigo, nombre, descripcion) VALUES (?, ?, ?)",
            ("PIZ", "Pizzas", "Pizzas caseras"),
        )

        xlsx = _make_xlsx_bytes(
            "products",
            ["nombre", "descripcion", "precio", "category_name", "stock_inicial"],
            [["Muzzarella", "Pizza", 1500.00, "Pizzas", 10]],
        )

        response = client.post(
            "/api/load_products",
            headers={"Authorization": auth_headers["Authorization"]},
            data={"file": (xlsx, "productos.xlsx")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["created"] == 1
        assert data["processed_rows"] == 1

    def test_missing_category_returns_partial_status(self, client, auth_headers):
        xlsx = _make_xlsx_bytes(
            "products",
            ["nombre", "descripcion", "precio", "category_name"],
            [["Muzzarella", "Pizza", 1500.00, "Inexistente"]],
        )

        response = client.post(
            "/api/load_products",
            headers={"Authorization": auth_headers["Authorization"]},
            data={"file": (xlsx, "productos.xlsx")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["errors"] == 1

        db = get_db()
        upload = db.execute(
            "SELECT status FROM upload_logs WHERE id = ?",
            (data["upload_id"],),
            fetchone=True,
        )
        assert upload["status"] == "partial"


class TestLoginPageAndUploadAccess:
    """Tests for the HTML login page and upload form protection."""

    def test_login_page_returns_html(self, client):
        response = client.get("/api/login-page")
        assert response.status_code == 200
        assert "text/html" in response.content_type
        html = response.data.decode("utf-8")
        assert "Iniciar sesión" in html
        assert '/api/auth/login' in html

    def test_upload_page_is_public(self, client):
        response = client.get("/api/upload")
        assert response.status_code == 200
        assert "text/html" in response.content_type
        html = response.data.decode("utf-8")
        assert "Importar datos desde Excel" in html
        assert "Cerrar sesión" in html
        assert "logoutBtn" in html

    def test_root_redirects_to_login_when_no_token(self, client):
        response = client.get("/")
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "/api/login-page" in html
        assert "/api/upload" in html
