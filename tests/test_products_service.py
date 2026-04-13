"""Unit tests for catalog_service."""

from decimal import Decimal

from shared.services import catalog_service


def test_list_categories_normalizes_database_rows(monkeypatch):
    monkeypatch.setattr(
        catalog_service,
        "obtener_categorias_db",
        lambda: [
            ("bebidas", "Gaseosas y jugos"),
            ("hamburguesas", "Carne y pollo"),
        ],
    )

    result = catalog_service.list_categories()

    assert len(result) == 2
    assert result[0].name == "bebidas"
    assert result[0].description == "Gaseosas y jugos"
    assert result[1].name == "hamburguesas"


def test_list_products_by_category_returns_empty_list_without_category():
    assert catalog_service.list_products_by_category(None) == []
    assert catalog_service.list_products_by_category("") == []


def test_list_products_by_category_normalizes_products(monkeypatch):
    monkeypatch.setattr(
        catalog_service,
        "obtener_productos_por_categoria",
        lambda category_name: [
            (5, "Coca-Cola", "Bebida 500ml", "2.50"),
            (8, "Sprite", "Bebida lima-limon", Decimal("2.80")),
        ],
    )

    result = catalog_service.list_products_by_category("bebidas")

    assert len(result) == 2
    assert result[0].id == 5
    assert result[0].name == "Coca-Cola"
    assert result[0].price == Decimal("2.50")
    assert result[1].price == Decimal("2.80")


def test_list_products_by_category_page_normalizes_products_and_detects_next(monkeypatch):
    captured: dict[str, object] = {}

    def fake_paginated(category_name, limit, offset):
        captured["category_name"] = category_name
        captured["limit"] = limit
        captured["offset"] = offset
        return [
            (5, "Coca-Cola", "Bebida 500ml", "2.50"),
            (8, "Sprite", "Bebida lima-limon", Decimal("2.80")),
            (9, "Tonica", "Bebida 350ml", "3.10"),
        ]

    monkeypatch.setattr(
        catalog_service,
        "obtener_productos_por_categoria_paginados",
        fake_paginated,
    )

    result, has_next_page = catalog_service.list_products_by_category_page(
        "bebidas",
        page=2,
        page_size=2,
    )

    assert captured == {"category_name": "bebidas", "limit": 3, "offset": 2}
    assert has_next_page is True
    assert len(result) == 2
    assert result[0].price == Decimal("2.50")
    assert result[1].price == Decimal("2.80")


def test_list_products_by_category_page_returns_empty_when_missing_category():
    assert catalog_service.list_products_by_category_page(None) == ([], False)
    assert catalog_service.list_products_by_category_page("") == ([], False)


def test_get_product_by_id_returns_none_when_missing(monkeypatch):
    monkeypatch.setattr(catalog_service, "obtener_producto_por_id", lambda product_id: None)

    result = catalog_service.get_product_by_id(999)

    assert result is None


def test_get_product_by_id_normalizes_mapping_and_stock(monkeypatch):
    monkeypatch.setattr(
        catalog_service,
        "obtener_producto_por_id",
        lambda product_id: {
            "id": product_id,
            "nombre": "Hamburguesa Doble",
            "descripcion": "Doble carne y cheddar",
            "precio": "12.90",
        },
    )
    monkeypatch.setattr(catalog_service, "verificar_stock_disponible", lambda product_id: 7)

    result = catalog_service.get_product_by_id(11)

    assert result is not None
    assert result.id == 11
    assert result.name == "Hamburguesa Doble"
    assert result.description == "Doble carne y cheddar"
    assert result.price == Decimal("12.90")
    assert result.stock_available == 7