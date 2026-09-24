"""Read-only invoice service.

Invoices and their items are created exclusively through the Telegram bot flow;
this service exposes only query operations for the REST API.
"""

from dataclasses import dataclass
from decimal import Decimal

from shared.record_utils import get_record_value
from utils.database import (
    count_all_invoices,
    get_all_invoices_paginated,
    get_customer_db_id_by_telegram_id,
    get_invoice_by_id_db,
    get_invoice_items_db,
)


@dataclass
class InvoiceItemDTO:
    """Represents a single line item inside an invoice."""

    id: str  # Cambiar de int a str (UUID)
    product_id: int
    product_name: str
    product_description: str
    cantidad: int
    precio_unitario: Decimal
    subtotal: Decimal


@dataclass
class InvoiceDTO:
    """Represents an invoice header."""

    id: str  # Cambiar de int a str (UUID)
    fecha: str
    estado: str
    total: Decimal
    customer_db_id: int
    customer_name: str
    telegram_id: str


def _row_to_invoice_dto(row: dict) -> InvoiceDTO:
    """Converts a DB row to an InvoiceDTO."""
    return InvoiceDTO(
        id=str(get_record_value(row, "id", fallback_index=0)),
        fecha=str(get_record_value(row, "fecha", fallback_index=1) or ""),
        estado=str(get_record_value(row, "estado", fallback_index=2) or ""),
        total=Decimal(str(get_record_value(row, "total", fallback_index=3) or 0)),
        customer_db_id=int(get_record_value(row, "customer_db_id", fallback_index=4) or 0),
        customer_name=str(get_record_value(row, "customer_name", fallback_index=5) or ""),
        telegram_id=str(get_record_value(row, "telegram_id", fallback_index=6) or ""),
    )


def _row_to_item_dto(row: dict) -> InvoiceItemDTO:
    """Converts a DB row to an InvoiceItemDTO."""
    return InvoiceItemDTO(
        id=str(get_record_value(row, "id", fallback_index=0)),
        product_id=int(get_record_value(row, "product_id", fallback_index=1) or 0),
        product_name=str(get_record_value(row, "product_name", fallback_index=2) or ""),
        product_description=str(get_record_value(row, "product_description", fallback_index=3) or ""),
        cantidad=int(get_record_value(row, "cantidad", fallback_index=4) or 0),
        precio_unitario=Decimal(str(get_record_value(row, "precio_unitario", fallback_index=5) or 0)),
        subtotal=Decimal(str(get_record_value(row, "subtotal", fallback_index=6) or 0)),
    )


def list_invoices(
    page: int = 1,
    per_page: int = 10,
    estado: str | None = None,
    customer_id: int | None = None,
) -> tuple[list[InvoiceDTO], int]:
    """Returns one page of invoices and the total count.

    Args:
        page: 1-based page number.
        per_page: Records per page.
        estado: Optional filter by invoice status (e.g. 'pendiente', 'pagado').
        customer_id: Optional filter by internal customer DB id.

    Returns:
        Tuple of (list[InvoiceDTO], total_count).
    """
    normalized_page = max(page, 1)
    normalized_per_page = max(per_page, 1)
    offset = (normalized_page - 1) * normalized_per_page

    rows = get_all_invoices_paginated(normalized_per_page, offset, estado=estado, customer_id=customer_id)
    total = count_all_invoices(estado=estado, customer_id=customer_id)
    return [_row_to_invoice_dto(row) for row in rows], total


def get_invoice(invoice_id: str) -> InvoiceDTO | None:
    """Returns a single invoice by id, or None if not found."""
    row = get_invoice_by_id_db(invoice_id)
    if not row:
        return None
    return _row_to_invoice_dto(row)


def get_invoice_items(invoice_id: str) -> list[InvoiceItemDTO]:
    """Returns all line items of an invoice.

    Args:
        invoice_id: The invoice id.

    Returns:
        List of InvoiceItemDTO, empty if the invoice has no items or does not exist.
    """
    rows = get_invoice_items_db(invoice_id)
    return [_row_to_item_dto(row) for row in rows]


def list_invoices_by_customer(
    telegram_id: str,
    page: int = 1,
    per_page: int = 10,
    estado: str | None = None,
) -> tuple[list[InvoiceDTO], int] | None:
    """Returns a paginated list of invoices for a customer identified by their Telegram id.

    Args:
        telegram_id: The customer's Telegram user id (stored as customer_id in the DB).
        page: 1-based page number.
        per_page: Records per page.
        estado: Optional filter by invoice status.

    Returns:
        Tuple of (list[InvoiceDTO], total_count), or None if the customer does not exist.
    """
    customer_db_id = get_customer_db_id_by_telegram_id(telegram_id)
    if customer_db_id is None:
        return None
    return list_invoices(page=page, per_page=per_page, estado=estado, customer_id=customer_db_id)
