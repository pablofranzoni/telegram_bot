"""Write-capable product management service (CRUD).

This module is intentionally separate from catalog_service, which remains
read-only and is used by the Telegram bot handlers.
"""

from decimal import Decimal, InvalidOperation

from shared.dtos import ProductDTO
from shared.number_utils import to_decimal
from shared.record_utils import get_record_value
from utils.database import (
    count_all_products,
    create_inventory_row_db,
    create_product_db,
    deactivate_product_db,
    get_all_products_paginated,
    obtener_producto_por_id,
    update_product_db,
)


def _row_to_dto(row: dict) -> ProductDTO:
    """Converts a DB row dict to a ProductDTO."""
    return ProductDTO(
        id=int(get_record_value(row, "id", fallback_index=0)),
        name=str(get_record_value(row, "nombre", fallback_index=1) or ""),
        description=str(get_record_value(row, "descripcion", fallback_index=2) or ""),
        price=to_decimal(get_record_value(row, "precio", fallback_index=3)),
        stock_available=int(get_record_value(row, "stock_available", fallback_index=7) or 0),
    )


def list_products(page: int = 1, per_page: int = 10) -> tuple[list[ProductDTO], int]:
    """Returns one page of products and the total product count.

    Args:
        page: 1-based page number.
        per_page: Number of records per page.

    Returns:
        Tuple of (list[ProductDTO], total_count).
    """
    normalized_page = max(page, 1)
    normalized_per_page = max(per_page, 1)
    offset = (normalized_page - 1) * normalized_per_page

    rows = get_all_products_paginated(normalized_per_page, offset)
    total = count_all_products()
    return [_row_to_dto(row) for row in rows], total


def get_product(product_id: int) -> ProductDTO | None:
    """Returns a single product by id, or None if not found."""
    row = obtener_producto_por_id(product_id)
    if not row:
        return None
    return ProductDTO(
        id=int(get_record_value(row, "id", fallback_index=0)),
        name=str(get_record_value(row, "nombre", fallback_index=1) or ""),
        description=str(get_record_value(row, "descripcion", fallback_index=2) or ""),
        price=to_decimal(get_record_value(row, "precio", fallback_index=3)),
    )


def create_product(
    nombre: str,
    descripcion: str,
    precio: Decimal | float | str,
    category_id: int,
    stock_inicial: int = 0,
) -> ProductDTO | None:
    """Creates a product and its inventory row.

    Returns the new ProductDTO, or None if insertion fails.
    """
    try:
        price_value = float(to_decimal(precio))
    except (InvalidOperation, ValueError):
        return None

    new_id = create_product_db(nombre, descripcion, price_value, category_id)
    if new_id is None:
        return None

    create_inventory_row_db(new_id, stock_inicial)

    return ProductDTO(
        id=new_id,
        name=nombre,
        description=descripcion,
        price=to_decimal(precio),
        stock_available=stock_inicial,
    )


def update_product(product_id: int, data: dict) -> ProductDTO | None:
    """Updates allowed fields of a product and returns the refreshed DTO.

    Args:
        product_id: ID of the product to update.
        data: Dict with any subset of: nombre, descripcion, precio,
              disponible, category_id.

    Returns:
        Updated ProductDTO, or None if the product does not exist or update fails.
    """
    existing = obtener_producto_por_id(product_id)
    if not existing:
        return None

    if not update_product_db(product_id, data):
        return None

    return get_product(product_id)


def deactivate_product(product_id: int) -> bool:
    """Soft-deletes a product (sets disponible=False).

    Returns True on success, False if the product does not exist or fails.
    """
    existing = obtener_producto_por_id(product_id)
    if not existing:
        return False
    return deactivate_product_db(product_id)
