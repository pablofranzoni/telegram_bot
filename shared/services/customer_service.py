"""Read-only customer service.

Exposes paginated query operations over the ``customers`` table for the
REST API. Mutations are handled separately by ``UserService``.
"""

from shared.dtos import CustomerDTO
from shared.record_utils import get_record_value
from utils.database import count_all_customers, get_all_customers_paginated


def _row_to_dto(row: dict) -> CustomerDTO:
    """Converts a DB row to a CustomerDTO."""
    return CustomerDTO(
        id=int(get_record_value(row, "id", fallback_index=0) or 0),
        name=str(get_record_value(row, "name", fallback_index=1) or ""),
        telegram_id=str(get_record_value(row, "customer_id", fallback_index=2) or "") or None,
        email=str(get_record_value(row, "email", fallback_index=3) or "") or None,
    )


def list_customers(page: int = 1, per_page: int = 10) -> tuple[list[CustomerDTO], int]:
    """Returns one page of customers and the total count.

    Args:
        page: 1-based page number.
        per_page: Records per page.

    Returns:
        Tuple of (list[CustomerDTO], total_count).
    """
    normalized_page = max(page, 1)
    normalized_per_page = max(per_page, 1)
    offset = (normalized_page - 1) * normalized_per_page

    rows = get_all_customers_paginated(normalized_per_page, offset)
    total = count_all_customers()
    return [_row_to_dto(row) for row in rows], total
