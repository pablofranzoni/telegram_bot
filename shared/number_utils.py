"""Helpers for numeric normalization across services."""

from decimal import Decimal
from typing import Any


def to_decimal(value: Any, default: Any | None = None) -> Decimal:
    """Convert DB values to Decimal, optionally using a fallback for empty values."""
    if isinstance(value, Decimal):
        return value

    normalized_value = default if value in (None, "") and default is not None else value
    return Decimal(str(normalized_value))