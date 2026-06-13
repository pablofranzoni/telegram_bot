"""Write-capable category management service (CRUD).

This module handles administrative operations on categories.
The read-only catalog_service remains separate and is used by bot handlers.
"""

from shared.dtos import CategoryDTO
from shared.record_utils import get_record_value
from utils.database import (
    create_category_db,
    delete_category_db,
    get_all_categories_db,
    get_category_by_id_db,
    update_category_db,
)


def _row_to_dto(row: dict) -> CategoryDTO:
    """Converts a DB row dict to a CategoryDTO."""
    return CategoryDTO(
        id=int(get_record_value(row, "id", fallback_index=0)),
        codigo=str(get_record_value(row, "codigo", fallback_index=1) or ""),
        name=str(get_record_value(row, "nombre", fallback_index=2) or ""),
        description=str(get_record_value(row, "descripcion", fallback_index=3) or ""),
        parent_id=get_record_value(row, "parent_id", fallback_index=4),
    )


def list_categories() -> list[CategoryDTO]:
    """Returns all categories ordered by name."""
    rows = get_all_categories_db()
    return [_row_to_dto(row) for row in rows]


def get_category(category_id: int) -> CategoryDTO | None:
    """Returns a single category by id, or None if not found."""
    row = get_category_by_id_db(category_id)
    if not row:
        return None
    return _row_to_dto(row)


def create_category(
    codigo: str,
    nombre: str,
    descripcion: str,
    parent_id: int | None = None,
) -> CategoryDTO | None:
    """Creates a new category and returns its DTO, or None if insertion fails."""
    new_id = create_category_db(codigo, nombre, descripcion, parent_id)
    if new_id is None:
        return None
    return CategoryDTO(
        id=new_id,
        codigo=codigo,
        name=nombre,
        description=descripcion,
        parent_id=parent_id,
    )


def update_category(category_id: int, data: dict) -> CategoryDTO | None:
    """Updates allowed fields of a category and returns the refreshed DTO.

    Args:
        category_id: ID of the category to update.
        data: Dict with any subset of: codigo, nombre, descripcion, parent_id.

    Returns:
        Updated CategoryDTO, or None if category does not exist or update fails.
    """
    existing = get_category_by_id_db(category_id)
    if not existing:
        return None
    if not update_category_db(category_id, data):
        return None
    return get_category(category_id)


def delete_category(category_id: int) -> bool:
    """Deletes a category by id.

    Returns True on success, False if the category does not exist or fails.
    """
    existing = get_category_by_id_db(category_id)
    if not existing:
        return False
    return delete_category_db(category_id)
