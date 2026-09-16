"""Tests for the Excel import service."""

import os
import tempfile
from unittest.mock import patch

import pytest
from openpyxl import Workbook

from database.db_manager import db_manager, get_db
from shared.services import import_service


@pytest.fixture
def sample_xlsx_path():
    """Return a helper that writes an in-memory workbook to a temp .xlsx file."""
    def _make_file(sheet_name: str, headers: list[str], rows: list[list]):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = sheet_name
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
        fd, path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        workbook.save(path)
        return path
    return _make_file


@pytest.fixture
def upload_id(app):
    """Create an upload log entry and return its id."""
    db = get_db()
    new_id = db.execute(
        "INSERT INTO upload_logs (filename, original_filename, file_size, status) "
        "VALUES (?, ?, ?, 'processing')",
        ("test.xlsx", "test.xlsx", 1024),
    )
    return new_id


class TestImportCategories:
    """Tests for import_categories_from_xlsx."""

    def test_creates_new_categories(self, sample_xlsx_path, upload_id):
        path = sample_xlsx_path(
            "categories",
            ["codigo", "nombre", "descripcion"],
            [["PIZ", "Pizzas", "Pizzas caseras"], ["BEB", "Bebidas", "Gaseosas y agua"]],
        )

        summary = import_service.import_categories_from_xlsx(path, upload_id)

        assert summary["processed_rows"] == 2
        assert summary["created"] == 2
        assert summary["updated"] == 0
        assert summary["errors"] == 0

        db = get_db()
        row = db.execute(
            "SELECT codigo, nombre FROM categories WHERE nombre = ?",
            ("Pizzas",),
            fetchone=True,
        )
        assert row is not None
        assert row["codigo"] == "PIZ"

    def test_updates_existing_category_by_name(self, sample_xlsx_path, upload_id):
        db = get_db()
        db.execute(
            "INSERT INTO categories (codigo, nombre, descripcion) VALUES (?, ?, ?)",
            ("OLD", "Pizzas", "Descripción vieja"),
        )

        path = sample_xlsx_path(
            "categories",
            ["codigo", "nombre", "descripcion"],
            [["PIZ", "Pizzas", "Pizzas actualizadas"]],
        )

        summary = import_service.import_categories_from_xlsx(path, upload_id)

        assert summary["created"] == 0
        assert summary["updated"] == 1

        row = db.execute(
            "SELECT codigo, descripcion FROM categories WHERE nombre = ?",
            ("Pizzas",),
            fetchone=True,
        )
        assert row["codigo"] == "PIZ"
        assert row["descripcion"] == "Pizzas actualizadas"

    def test_missing_required_column_raises_error(self, sample_xlsx_path, upload_id):
        path = sample_xlsx_path(
            "categories",
            ["codigo", "nombre"],  # missing descripcion
            [["PIZ", "Pizzas"]],
        )

        with pytest.raises(ValueError):
            import_service.import_categories_from_xlsx(path, upload_id)


class TestImportProducts:
    """Tests for import_products_from_xlsx."""

    def test_creates_new_product_with_stock(self, sample_xlsx_path, upload_id):
        db = get_db()
        db.execute(
            "INSERT INTO categories (codigo, nombre, descripcion) VALUES (?, ?, ?)",
            ("PIZ", "Pizzas", "Pizzas caseras"),
        )

        path = sample_xlsx_path(
            "products",
            ["nombre", "descripcion", "precio", "category_name", "stock_inicial"],
            [["Muzzarella", "Pizza de muzzarella", 1500.50, "Pizzas", 20]],
        )

        summary = import_service.import_products_from_xlsx(path, upload_id)

        assert summary["processed_rows"] == 1
        assert summary["created"] == 1
        assert summary["updated"] == 0
        assert summary["errors"] == 0

        product = db.execute(
            "SELECT p.id, p.precio, pi.stock_actual FROM products p "
            "JOIN product_inventory pi ON pi.product_id = p.id WHERE p.nombre = ?",
            ("Muzzarella",),
            fetchone=True,
        )
        assert product is not None
        assert float(product["precio"]) == 1500.50
        assert product["stock_actual"] == 20

    def test_updates_existing_product_and_adjusts_stock(self, sample_xlsx_path, upload_id):
        db = get_db()
        db.execute(
            "INSERT INTO categories (codigo, nombre, descripcion) VALUES (?, ?, ?)",
            ("PIZ", "Pizzas", "Pizzas caseras"),
        )
        db.execute(
            "INSERT INTO products (nombre, descripcion, precio, disponible, category_id) "
            "VALUES (?, ?, ?, ?, ?)",
            ("Muzzarella", "Original", 1000.00, True, 1),
        )
        db.execute(
            "INSERT INTO product_inventory (product_id, stock_actual, stock_reservado, stock_minimo) "
            "VALUES (?, ?, 0, 0)",
            (1, 10),
        )

        path = sample_xlsx_path(
            "products",
            ["nombre", "descripcion", "precio", "category_name", "stock_inicial"],
            [["Muzzarella", "Pizza de muzzarella actualizada", 1600.00, "Pizzas", 25]],
        )

        summary = import_service.import_products_from_xlsx(path, upload_id)

        assert summary["created"] == 0
        assert summary["updated"] == 1

        product = db.execute(
            "SELECT p.precio, pi.stock_actual FROM products p "
            "JOIN product_inventory pi ON pi.product_id = p.id WHERE p.nombre = ?",
            ("Muzzarella",),
            fetchone=True,
        )
        assert float(product["precio"]) == 1600.00
        assert product["stock_actual"] == 25

        movement = db.execute(
            "SELECT tipo_movimiento, cantidad FROM inventory_movements WHERE product_id = ?",
            (1,),
            fetchone=True,
        )
        assert movement is not None
        assert movement["tipo_movimiento"] == "ajuste"
        assert movement["cantidad"] == 15

    def test_fails_when_category_does_not_exist(self, sample_xlsx_path, upload_id):
        path = sample_xlsx_path(
            "products",
            ["nombre", "descripcion", "precio", "category_name"],
            [["Muzzarella", "Pizza", 1500.00, "Inexistente"]],
        )

        summary = import_service.import_products_from_xlsx(path, upload_id)

        assert summary["processed_rows"] == 1
        assert summary["errors"] == 1
        assert summary["created"] == 0

    def test_missing_required_column_raises_before_processing(self, sample_xlsx_path, upload_id):
        path = sample_xlsx_path(
            "products",
            ["nombre", "descripcion", "precio"],  # missing category_name
            [["Muzzarella", "Pizza", 1500.00]],
        )

        with pytest.raises(ValueError):
            import_service.import_products_from_xlsx(path, upload_id)

    def test_imports_product_when_category_name_lacks_accent(self, sample_xlsx_path, upload_id):
        """Accent-insensitive lookup must match 'Categoria' to 'Categoría'."""
        db = get_db()
        db.execute(
            "INSERT INTO categories (codigo, nombre, descripcion) VALUES (?, ?, ?)",
            ("CAT", "Categoría acentuada", "Descripción"),
        )

        path = sample_xlsx_path(
            "products",
            ["nombre", "descripcion", "precio", "category_name", "stock_inicial"],
            [["Producto sin acento", "Desc", 100.0, "Categoria acentuada", 10]],
        )

        summary = import_service.import_products_from_xlsx(path, upload_id)

        assert summary["processed_rows"] == 1
        assert summary["created"] == 1
        assert summary["updated"] == 0
        assert summary["errors"] == 0

        product = db.execute(
            "SELECT p.id FROM products p WHERE p.nombre = ?",
            ("Producto sin acento",),
            fetchone=True,
        )
        assert product is not None

    def test_import_is_idempotent(self, sample_xlsx_path, upload_id):
        """Importing the same file twice must not create duplicates or errors."""
        db = get_db()
        db.execute(
            "INSERT INTO categories (codigo, nombre, descripcion) VALUES (?, ?, ?)",
            ("PIZ", "Pizzas", "Pizzas caseras"),
        )

        path = sample_xlsx_path(
            "products",
            ["nombre", "descripcion", "precio", "category_name", "stock_inicial"],
            [["Muzzarella", "Pizza de muzzarella", 1500.50, "Pizzas", 20]],
        )

        first_summary = import_service.import_products_from_xlsx(path, upload_id)
        assert first_summary["processed_rows"] == 1
        assert first_summary["created"] == 1
        assert first_summary["updated"] == 0
        assert first_summary["errors"] == 0

        second_summary = import_service.import_products_from_xlsx(path, upload_id)
        assert second_summary["processed_rows"] == 1
        assert second_summary["created"] == 0
        assert second_summary["updated"] == 1
        assert second_summary["errors"] == 0

        product = db.execute(
            "SELECT COUNT(*) AS product_count FROM products WHERE nombre = ?",
            ("Muzzarella",),
            fetchone=True,
        )
        assert product["product_count"] == 1

        inventory = db.execute(
            "SELECT pi.stock_actual FROM products p "
            "JOIN product_inventory pi ON pi.product_id = p.id WHERE p.nombre = ?",
            ("Muzzarella",),
            fetchone=True,
        )
        assert inventory is not None
        assert inventory["stock_actual"] == 20

    def test_inventory_creation_failure_is_reported(self, sample_xlsx_path, upload_id):
        """If create_inventory_row_db fails for a new product, the row must be reported as an error."""
        db = get_db()
        db.execute(
            "INSERT INTO categories (codigo, nombre, descripcion) VALUES (?, ?, ?)",
            ("PIZ", "Pizzas", "Pizzas caseras"),
        )

        path = sample_xlsx_path(
            "products",
            ["nombre", "descripcion", "precio", "category_name", "stock_inicial"],
            [["Muzzarella", "Pizza de muzzarella", 1500.50, "Pizzas", 20]],
        )

        with patch("shared.services.import_service.create_inventory_row_db", return_value=False):
            summary = import_service.import_products_from_xlsx(path, upload_id)

        assert summary["processed_rows"] == 1
        assert summary["created"] == 0
        assert summary["errors"] == 1
