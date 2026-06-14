"""DTOs for checkout and payment flows."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(slots=True)
class PaymentLinkResult:
    """Represents the outcome of generating a payment link."""

    success: bool
    preference_id: str | None = None
    init_point: str | None = None
    external_reference: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class CheckoutResultDTO:
    """Represents the outcome of finalizing a checkout."""

    success: bool
    invoice_id: str  # UUID como string
    amount: Decimal | None = None
    title: str | None = None
    payment_preference_id: str | None = None
    payment_url: str | None = None
    error_message: str | None = None