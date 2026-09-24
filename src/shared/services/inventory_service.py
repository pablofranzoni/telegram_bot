"""Inventory management service for stock queries and adjustments."""

from dataclasses import dataclass

from database.db import DatabaseError
from database.db_manager import get_db
from shared.record_utils import get_record_value
from utils.database import (
    create_inventory_row_db,
    insert_inventory_movement,
    obtener_producto_por_id,
    _get_inventory_row,
)


@dataclass(frozen=True, slots=True)
class InventoryDTO:
    """Represents the inventory state of a single product."""

    product_id: int
    stock_actual: int
    stock_reservado: int
    stock_disponible: int
    stock_minimo: int
    ultima_compra: str | None
    ubicacion_almacen: str | None


_ALLOWED_ADD_TYPES = {"compra", "ajuste"}


def _ensure_inventory_row(product_id: int) -> bool:
    """Create an inventory row with zero stock if the product does not have one."""
    if _get_inventory_row(product_id) is not None:
        return True
    return create_inventory_row_db(product_id, 0)


def get_inventory(product_id: int) -> InventoryDTO | None:
    """Return the inventory for a product, or None if the product does not exist.

    If the product exists but has no inventory row, a zeroed DTO is returned.
    """
    if obtener_producto_por_id(product_id) is None:
        return None

    try:
        db = get_db()
        row = db.execute(
            """
            SELECT product_id, stock_actual, stock_reservado, stock_disponible,
                   stock_minimo, ultima_compra, ubicacion_almacen
            FROM product_inventory
            WHERE product_id = ?
            """,
            (product_id,),
            fetchone=True,
            param_types=["integer"],
        )
    except DatabaseError as e:
        raise InventoryError(f"Error al consultar inventario: {e}") from e

    if not row:
        return InventoryDTO(
            product_id=product_id,
            stock_actual=0,
            stock_reservado=0,
            stock_disponible=0,
            stock_minimo=0,
            ultima_compra=None,
            ubicacion_almacen=None,
        )

    return InventoryDTO(
        product_id=int(get_record_value(row, "product_id", fallback_index=0)),
        stock_actual=int(get_record_value(row, "stock_actual", fallback_index=1) or 0),
        stock_reservado=int(get_record_value(row, "stock_reservado", fallback_index=2) or 0),
        stock_disponible=int(get_record_value(row, "stock_disponible", fallback_index=3) or 0),
        stock_minimo=int(get_record_value(row, "stock_minimo", fallback_index=4) or 0),
        ultima_compra=get_record_value(row, "ultima_compra", fallback_index=5),
        ubicacion_almacen=get_record_value(row, "ubicacion_almacen", fallback_index=6),
    )


class InventoryError(Exception):
    """Raised when an inventory operation cannot be completed."""


def add_stock(
    product_id: int,
    cantidad: int,
    movement_type: str = "compra",
    costo_unitario: float | None = None,
    referencia: str | None = None,
    usuario_id: int | None = None,
) -> dict | None:
    """Add stock to an existing product and return the movement summary.

    Args:
        product_id: ID of the product to receive stock.
        cantidad: Positive amount to add.
        movement_type: Either "compra" or "ajuste" (default "compra").
        costo_unitario: Optional unit cost for purchase movements.
        referencia: Optional reference number (purchase order, invoice, etc.).
        usuario_id: Optional ID of the user recording the movement (audit).

    Returns:
        A dict with ``movement_id``, ``product_id``, ``stock_actual`` and
        ``stock_disponible`` on success, or ``None`` if the product does not
        exist or the movement cannot be recorded.

    Raises:
        ValueError: If the input is invalid.
        InventoryError: If a database error occurs.
    """
    movement_type = str(movement_type).strip().lower()
    if movement_type not in _ALLOWED_ADD_TYPES:
        raise ValueError(
            f"tipo debe ser uno de: {', '.join(sorted(_ALLOWED_ADD_TYPES))}"
        )

    if not isinstance(cantidad, int) or cantidad <= 0:
        raise ValueError("cantidad debe ser un entero positivo")

    if costo_unitario is not None:
        if not isinstance(costo_unitario, (int, float)) or costo_unitario < 0:
            raise ValueError("costo_unitario debe ser un número no negativo")
        costo_unitario = float(costo_unitario)

    if referencia is not None:
        referencia = str(referencia).strip() or None

    if obtener_producto_por_id(product_id) is None:
        return None

    if not _ensure_inventory_row(product_id):
        raise InventoryError("No se pudo crear la fila de inventario del producto")

    try:
        movement_id = insert_inventory_movement(
            product_id=product_id,
            tipo_movimiento=movement_type,
            cantidad=cantidad,
            costo_unitario=costo_unitario,
            referencia=referencia,
            usuario_id=usuario_id,
        )
    except DatabaseError as e:
        raise InventoryError(f"Error al registrar movimiento: {e}") from e

    if movement_id is None:
        return None

    inventory = get_inventory(product_id)
    return {
        "movement_id": movement_id,
        "product_id": product_id,
        "stock_actual": inventory.stock_actual,
        "stock_disponible": inventory.stock_disponible,
    }
