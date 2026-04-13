"""DTOs for cart and cart-mutation flows."""

from dataclasses import dataclass, field
from decimal import Decimal

from .product_dto import ProductDTO


@dataclass(slots=True)
class CartItemDTO:
    """Represents one item inside the cart."""

    product_id: int
    name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    description: str = ""


@dataclass(slots=True)
class CartDTO:
    """Represents the current cart state for a user or invoice."""

    invoice_id: int
    items: list[CartItemDTO] = field(default_factory=list)
    total: Decimal = Decimal("0.00")
    item_count: int = 0

    @property
    def is_empty(self) -> bool:
        """Whether the cart has no items."""
        return not self.items


@dataclass(slots=True)
class CartMutationResult:
    """Represents the result of mutating a cart."""

    success: bool
    product: ProductDTO | None = None
    invoice_id: int | None = None
    previous_quantity: int | None = None
    current_quantity: int | None = None
    error_message: str | None = None