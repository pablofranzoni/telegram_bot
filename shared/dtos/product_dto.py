"""DTOs for catalog and product-related flows."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(slots=True)
class CategoryDTO:
    """Represents a visible catalog category."""

    name: str
    description: str


@dataclass(slots=True)
class ProductDTO:
    """Represents a product visible to bot users."""

    id: int
    name: str
    description: str
    price: Decimal
    stock_available: int | None = None