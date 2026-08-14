"""Tests for inventory management functions."""

import pytest

from database.db_manager import get_db
from utils.database import (
    confirmar_venta_inventory,
    create_inventory_row_db,
    create_product_db,
    insert_inventory_movement,
    liberar_stock,
    liberar_stock_reservado_invoice,
    registrar_compra_inventory,
    reservar_stock,
    verificar_stock_disponible,
)


@pytest.fixture
def sample_product(app):
    """Create a product with inventory for inventory tests."""
    db = get_db()
    db.execute(
        "INSERT INTO categories (nombre, descripcion, codigo) VALUES (?, ?, ?)",
        ("Test Category", "Test Description", "TEST"),
    )
    product_id = create_product_db("Test Product", "Description", 10.0, 1)
    create_inventory_row_db(product_id, 100)
    return product_id


def test_verificar_stock_disponible(app, sample_product):
    assert verificar_stock_disponible(sample_product) == 100


def test_registrar_compra_inventory(app, sample_product):
    assert registrar_compra_inventory(sample_product, 50, costo_unitario=5.0) is True
    assert verificar_stock_disponible(sample_product) == 150


def test_reservar_y_liberar_stock(app, sample_product):
    assert reservar_stock(sample_product, 20) is True
    assert verificar_stock_disponible(sample_product) == 80
    assert liberar_stock(sample_product, 20) is True
    assert verificar_stock_disponible(sample_product) == 100


def test_reservar_stock_sin_disponibilidad(app, sample_product):
    assert reservar_stock(sample_product, 200) is False
    assert verificar_stock_disponible(sample_product) == 100


def test_insert_inventory_movement_descuenta_stock(app, sample_product):
    movement_id = insert_inventory_movement(sample_product, "venta", -10)
    assert movement_id is not None
    assert verificar_stock_disponible(sample_product) == 90


def _create_test_invoice(db, customer_id, product_id, quantity, unit_price):
    """Helper to create a customer, invoice and invoice item."""
    db.execute(
        "INSERT INTO customers (customer_id, name, email) VALUES (?, ?, ?)",
        (customer_id, "Test Customer", f"{customer_id}@example.com"),
    )
    customer = db.execute(
        "SELECT id FROM customers WHERE customer_id = ?",
        (customer_id,),
        fetchone=True,
    )
    invoice_id = db.execute(
        "INSERT INTO invoices (customer_id, total) VALUES (?, ?)",
        (customer["id"], quantity * unit_price),
    )
    db.execute(
        """
        INSERT INTO invoice_items (invoice_id, product_id, cantidad, precio_unitario)
        VALUES (?, ?, ?, ?)
        """,
        (invoice_id, product_id, quantity, unit_price),
    )
    return invoice_id


def test_confirmar_venta_inventory(app, sample_product):
    db = get_db()
    invoice_id = _create_test_invoice(db, "11111", sample_product, 1, 10.0)

    assert reservar_stock(sample_product, 1) is True
    assert verificar_stock_disponible(sample_product) == 99

    assert confirmar_venta_inventory(invoice_id) is True
    assert verificar_stock_disponible(sample_product) == 99  # stock_actual=99, reservado=0

    # Idempotente: segunda confirmacion no duplica movimientos
    assert confirmar_venta_inventory(invoice_id) is True
    assert verificar_stock_disponible(sample_product) == 99


def test_liberar_stock_reservado_invoice(app, sample_product):
    db = get_db()
    invoice_id = _create_test_invoice(db, "22222", sample_product, 5, 10.0)

    assert reservar_stock(sample_product, 5) is True
    assert verificar_stock_disponible(sample_product) == 95

    assert liberar_stock_reservado_invoice(invoice_id) is True
    assert verificar_stock_disponible(sample_product) == 100
