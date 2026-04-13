"""Business logic for cart management."""

from decimal import Decimal
from typing import Any

from shared.dtos import CartDTO, CartItemDTO, CartMutationResult
from shared.number_utils import to_decimal
from shared.record_utils import get_record_value
from shared.services.catalog_service import get_product_by_id
from utils.database import (
    actualizar_cantidad_producto,
    agregar_producto,
    obtener_cantidad_producto,
    obtener_detalle_pedido,
    obtener_pedido_actual,
    obtener_pedido_actual_o_crear_nuevo,
    quitar_producto_del_pedido,
    vaciar_pedido_db,
)


def _normalize_invoice_id(raw_invoice_id: Any) -> int | None:
    """Return a consistent invoice id from low-level DB results."""
    if raw_invoice_id is None:
        return None
    if isinstance(raw_invoice_id, int):
        return raw_invoice_id

    value = get_record_value(raw_invoice_id, "id", fallback_index=0)
    return int(value) if value is not None else None


def get_current_cart_id(user_id: int) -> int | None:
    """Return the current pending cart/invoice id for a user."""
    return _normalize_invoice_id(obtener_pedido_actual(user_id))


def get_cart_by_invoice(invoice_id: int) -> CartDTO | None:
    """Return a normalized cart view from an invoice id."""
    info, items = obtener_detalle_pedido(invoice_id)
    if not info:
        return None

    normalized_items: list[CartItemDTO] = []
    total = to_decimal(get_record_value(info, "total", fallback_index=3) or Decimal("0.00"))

    for item in items or []:
        product_id = int(get_record_value(item, "id", fallback_index=0))
        product = get_product_by_id(product_id)
        normalized_items.append(
            CartItemDTO(
                product_id=product_id,
                name=str(get_record_value(item, "nombre", fallback_index=1) or ""),
                quantity=int(get_record_value(item, "cantidad", fallback_index=2) or 0),
                unit_price=to_decimal(get_record_value(item, "precio_unitario", fallback_index=3) or 0),
                subtotal=to_decimal(get_record_value(item, "subtotal", fallback_index=4) or 0),
                description=product.description if product else "",
            )
        )

    item_count = sum(item.quantity for item in normalized_items)
    return CartDTO(
        invoice_id=invoice_id,
        items=normalized_items,
        total=total,
        item_count=item_count,
    )


def get_current_cart(user_id: int) -> CartDTO | None:
    """Return the current cart for a user."""
    invoice_id = get_current_cart_id(user_id)
    if invoice_id is None:
        return None
    return get_cart_by_invoice(invoice_id)


def add_product_to_cart(user_id: int, product_id: int, quantity: int = 1) -> CartMutationResult:
    """Add a product to the current cart, creating it when needed."""
    product = get_product_by_id(product_id)
    if not product:
        return CartMutationResult(success=False, error_message="❌ Producto no encontrado")

    stock_available = product.stock_available
    if isinstance(stock_available, int) and quantity > stock_available:
        return CartMutationResult(
            success=False,
            product=product,
            error_message=f"❌ Stock máximo: {stock_available} unidades",
        )

    invoice_id = _normalize_invoice_id(obtener_pedido_actual_o_crear_nuevo(user_id))
    if invoice_id is None:
        return CartMutationResult(success=False, product=product, error_message="❌ Error al obtener el pedido")

    previous_quantity = obtener_cantidad_producto(invoice_id, product_id) or 0
    success = agregar_producto(invoice_id, product_id, quantity)
    if not success:
        return CartMutationResult(
            success=False,
            product=product,
            invoice_id=invoice_id,
            error_message="❌ Error al agregar producto",
        )

    current_quantity = obtener_cantidad_producto(invoice_id, product_id) or previous_quantity + quantity
    return CartMutationResult(
        success=True,
        product=product,
        invoice_id=invoice_id,
        previous_quantity=previous_quantity,
        current_quantity=current_quantity,
    )


def increase_product_quantity(user_id: int, product_id: int, quantity: int = 1) -> CartMutationResult:
    """Increase the quantity of a product in the current cart."""
    invoice_id = _normalize_invoice_id(obtener_pedido_actual_o_crear_nuevo(user_id))
    if invoice_id is None:
        return CartMutationResult(success=False, error_message="❌ Error al obtener el pedido")

    previous_quantity = obtener_cantidad_producto(invoice_id, product_id)
    if previous_quantity is None:
        return add_product_to_cart(user_id, product_id, quantity)

    product = get_product_by_id(product_id)
    if not product:
        return CartMutationResult(success=False, error_message="❌ Producto no encontrado")

    new_quantity = previous_quantity + quantity
    stock_available = product.stock_available
    if isinstance(stock_available, int) and new_quantity > stock_available:
        return CartMutationResult(
            success=False,
            product=product,
            invoice_id=invoice_id,
            previous_quantity=previous_quantity,
            current_quantity=previous_quantity,
            error_message=f"❌ Stock máximo: {stock_available} unidades",
        )

    success = actualizar_cantidad_producto(invoice_id, product_id, new_quantity)
    if not success:
        return CartMutationResult(
            success=False,
            product=product,
            invoice_id=invoice_id,
            previous_quantity=previous_quantity,
            current_quantity=previous_quantity,
            error_message="❌ Error al actualizar cantidad",
        )

    return CartMutationResult(
        success=True,
        product=product,
        invoice_id=invoice_id,
        previous_quantity=previous_quantity,
        current_quantity=new_quantity,
    )


def decrease_product_quantity(user_id: int, product_id: int, quantity: int = 1) -> CartMutationResult:
    """Decrease the quantity of a product in the current cart."""
    invoice_id = get_current_cart_id(user_id)
    if invoice_id is None:
        return CartMutationResult(success=False, error_message="❌ No tienes productos en el carrito")

    previous_quantity = obtener_cantidad_producto(invoice_id, product_id)
    if previous_quantity is None or previous_quantity <= 0:
        return CartMutationResult(success=False, error_message="❌ No tienes este producto en el carrito")

    product = get_product_by_id(product_id)
    new_quantity = max(previous_quantity - quantity, 0)
    success = actualizar_cantidad_producto(invoice_id, product_id, new_quantity)
    if not success:
        return CartMutationResult(
            success=False,
            product=product,
            invoice_id=invoice_id,
            previous_quantity=previous_quantity,
            current_quantity=previous_quantity,
            error_message="❌ Error al actualizar cantidad",
        )

    return CartMutationResult(
        success=True,
        product=product,
        invoice_id=invoice_id,
        previous_quantity=previous_quantity,
        current_quantity=new_quantity,
    )


def clear_cart(user_id: int) -> bool:
    """Remove all items from the current cart."""
    invoice_id = get_current_cart_id(user_id)
    if invoice_id is None:
        return False
    return bool(vaciar_pedido_db(invoice_id))


def remove_product_from_cart(invoice_id: int, product_id: int) -> CartMutationResult:
    """Remove a product from a given invoice/cart."""
    product = get_product_by_id(product_id)
    previous_quantity = obtener_cantidad_producto(invoice_id, product_id)
    success = quitar_producto_del_pedido(invoice_id, product_id)
    if not success:
        return CartMutationResult(
            success=False,
            product=product,
            invoice_id=invoice_id,
            previous_quantity=previous_quantity,
            current_quantity=previous_quantity,
            error_message="❌ Error al eliminar el producto",
        )

    return CartMutationResult(
        success=True,
        product=product,
        invoice_id=invoice_id,
        previous_quantity=previous_quantity,
        current_quantity=0,
    )