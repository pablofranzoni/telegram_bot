"""DTOs for customer-related flows exposed via the REST API."""

from dataclasses import dataclass


@dataclass(slots=True)
class CustomerDTO:
    """Represents a customer record exposed through /api/customers."""

    id: int
    name: str
    telegram_id: str | None
    email: str | None
