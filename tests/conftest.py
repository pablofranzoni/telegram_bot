"""Shared pytest fixtures for the Telegram bot project."""

from decimal import Decimal

import pytest


@pytest.fixture
def sample_invoice_info() -> dict[str, object]:
    """Normalized invoice payload used by checkout tests."""
    return {
        "id": 42,
        "total": Decimal("25.50"),
        "estado": "pendiente",
    }


@pytest.fixture
def sample_invoice_items() -> list[dict[str, object]]:
    """Sample invoice items used by checkout tests."""
    return [
        {
            "id": 5,
            "nombre": "Coca-Cola",
            "cantidad": 1,
            "precio_unitario": Decimal("2.50"),
            "subtotal": Decimal("2.50"),
        },
        {
            "id": 11,
            "nombre": "Hamburguesa Doble",
            "cantidad": 1,
            "precio_unitario": Decimal("23.00"),
            "subtotal": Decimal("23.00"),
        },
    ]