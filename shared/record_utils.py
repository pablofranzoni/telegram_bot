"""Helpers to read values from heterogeneous DB records."""

from typing import Any


def get_record_value(
    record: Any,
    key: str,
    default: Any = None,
    fallback_index: int | None = None,
) -> Any:
    """Read a value from dict-like, tuple-like, or attribute-based records."""
    if record is None:
        return default
    if isinstance(record, dict):
        return record.get(key, default)

    try:
        return record[key]
    except (KeyError, TypeError, IndexError):
        if fallback_index is not None:
            try:
                return record[fallback_index]
            except (TypeError, IndexError):
                return getattr(record, key, default)
        return getattr(record, key, default)