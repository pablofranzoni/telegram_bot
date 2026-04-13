"""Unit tests for cart_service."""

from decimal import Decimal

from shared.dtos import ProductDTO
from shared.services import cart_service


def test_get_current_cart_id_normalizes_int_and_mapping(monkeypatch):
    monkeypatch.setattr(cart_service, "obtener_pedido_actual", lambda user_id: 42)
    assert cart_service.get_current_cart_id(123) == 42

    monkeypatch.setattr(cart_service, "obtener_pedido_actual", lambda user_id: {"id": 99})
    assert cart_service.get_current_cart_id(123) == 99


def test_get_cart_by_invoice_normalizes_items(monkeypatch):
    monkeypatch.setattr(
        cart_service,
        "obtener_detalle_pedido",
        lambda invoice_id: (
            {"id": invoice_id, "total": Decimal("25.50")},
            [
                {
                    "id": 5,
                    "nombre": "Coca-Cola",
                    "cantidad": 2,
                    "precio_unitario": Decimal("2.50"),
                    "subtotal": Decimal("5.00"),
                }
            ],
        ),
    )
    monkeypatch.setattr(
        cart_service,
        "get_product_by_id",
        lambda product_id: ProductDTO(
            id=product_id,
            name="Coca-Cola",
            description="Bebida 500ml",
            price=Decimal("2.50"),
            stock_available=10,
        ),
    )

    result = cart_service.get_cart_by_invoice(42)

    assert result is not None
    assert result.invoice_id == 42
    assert result.total == Decimal("25.50")
    assert result.item_count == 2
    assert len(result.items) == 1
    assert result.items[0].description == "Bebida 500ml"


def test_add_product_to_cart_returns_error_when_product_does_not_exist(monkeypatch):
    monkeypatch.setattr(cart_service, "get_product_by_id", lambda product_id: None)

    result = cart_service.add_product_to_cart(user_id=123, product_id=999)

    assert result.success is False
    assert result.error_message == "❌ Producto no encontrado"


def test_add_product_to_cart_returns_quantities_when_successful(monkeypatch):
    monkeypatch.setattr(
        cart_service,
        "get_product_by_id",
        lambda product_id: ProductDTO(
            id=product_id,
            name="Hamburguesa",
            description="Doble carne",
            price=Decimal("10.00"),
            stock_available=20,
        ),
    )
    monkeypatch.setattr(cart_service, "obtener_pedido_actual_o_crear_nuevo", lambda user_id: 42)
    quantities = iter([2, 5])
    monkeypatch.setattr(cart_service, "obtener_cantidad_producto", lambda invoice_id, product_id: next(quantities))
    monkeypatch.setattr(cart_service, "agregar_producto", lambda invoice_id, product_id, quantity: True)

    result = cart_service.add_product_to_cart(user_id=123, product_id=5, quantity=3)

    assert result.success is True
    assert result.invoice_id == 42
    assert result.previous_quantity == 2
    assert result.current_quantity == 5
    assert result.product is not None
    assert result.product.name == "Hamburguesa"


def test_add_product_to_cart_rejects_when_requested_quantity_exceeds_stock(monkeypatch):
    monkeypatch.setattr(
        cart_service,
        "get_product_by_id",
        lambda product_id: ProductDTO(
            id=product_id,
            name="Hamburguesa",
            description="Doble carne",
            price=Decimal("10.00"),
            stock_available=2,
        ),
    )

    result = cart_service.add_product_to_cart(user_id=123, product_id=5, quantity=3)

    assert result.success is False
    assert result.error_message == "❌ Stock máximo: 2 unidades"


def test_increase_product_quantity_delegates_to_add_when_missing(monkeypatch):
    monkeypatch.setattr(cart_service, "obtener_pedido_actual_o_crear_nuevo", lambda user_id: 42)
    monkeypatch.setattr(cart_service, "obtener_cantidad_producto", lambda invoice_id, product_id: None)

    called: dict[str, object] = {}

    def fake_add(user_id, product_id, quantity=1):
        called.update({"user_id": user_id, "product_id": product_id, "quantity": quantity})
        return "delegated"

    monkeypatch.setattr(cart_service, "add_product_to_cart", fake_add)

    result = cart_service.increase_product_quantity(user_id=123, product_id=5, quantity=2)

    assert result == "delegated"
    assert called == {"user_id": 123, "product_id": 5, "quantity": 2}


def test_increase_product_quantity_rejects_when_stock_limit_is_exceeded(monkeypatch):
    monkeypatch.setattr(cart_service, "obtener_pedido_actual_o_crear_nuevo", lambda user_id: 42)
    monkeypatch.setattr(cart_service, "obtener_cantidad_producto", lambda invoice_id, product_id: 4)
    monkeypatch.setattr(
        cart_service,
        "get_product_by_id",
        lambda product_id: ProductDTO(
            id=product_id,
            name="Papas",
            description="Grandes",
            price=Decimal("3.50"),
            stock_available=5,
        ),
    )

    result = cart_service.increase_product_quantity(user_id=123, product_id=7, quantity=2)

    assert result.success is False
    assert result.previous_quantity == 4
    assert result.current_quantity == 4
    assert result.error_message == "❌ Stock máximo: 5 unidades"


def test_decrease_product_quantity_returns_error_when_cart_is_missing(monkeypatch):
    monkeypatch.setattr(cart_service, "get_current_cart_id", lambda user_id: None)

    result = cart_service.decrease_product_quantity(user_id=123, product_id=7)

    assert result.success is False
    assert result.error_message == "❌ No tienes productos en el carrito"


def test_decrease_product_quantity_updates_quantity_on_success(monkeypatch):
    monkeypatch.setattr(cart_service, "get_current_cart_id", lambda user_id: 42)
    monkeypatch.setattr(cart_service, "obtener_cantidad_producto", lambda invoice_id, product_id: 3)
    monkeypatch.setattr(
        cart_service,
        "get_product_by_id",
        lambda product_id: ProductDTO(
            id=product_id,
            name="Papas",
            description="Grandes",
            price=Decimal("3.50"),
            stock_available=5,
        ),
    )
    monkeypatch.setattr(cart_service, "actualizar_cantidad_producto", lambda invoice_id, product_id, quantity: True)

    result = cart_service.decrease_product_quantity(user_id=123, product_id=7, quantity=2)

    assert result.success is True
    assert result.previous_quantity == 3
    assert result.current_quantity == 1


def test_clear_cart_returns_false_without_current_invoice(monkeypatch):
    monkeypatch.setattr(cart_service, "get_current_cart_id", lambda user_id: None)

    assert cart_service.clear_cart(123) is False


def test_remove_product_from_cart_returns_success_when_database_removes_item(monkeypatch):
    monkeypatch.setattr(
        cart_service,
        "get_product_by_id",
        lambda product_id: ProductDTO(
            id=product_id,
            name="Pizza",
            description="Mozzarella",
            price=Decimal("12.00"),
            stock_available=8,
        ),
    )
    monkeypatch.setattr(cart_service, "obtener_cantidad_producto", lambda invoice_id, product_id: 2)
    monkeypatch.setattr(cart_service, "quitar_producto_del_pedido", lambda invoice_id, product_id: True)

    result = cart_service.remove_product_from_cart(invoice_id=42, product_id=8)

    assert result.success is True
    assert result.invoice_id == 42
    assert result.previous_quantity == 2
    assert result.current_quantity == 0