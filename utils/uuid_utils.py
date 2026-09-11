"""UUID v7 generator implemented in pure Python.

UUID v7 (RFC 9562) encodes a Unix timestamp in milliseconds in the
most significant 48 bits, followed by version and random data. This
makes the identifiers time-ordered and suitable for database primary
keys (similar to the PostgreSQL ``pg_uuidv7`` extension used by this
project).

No external dependencies are required.
"""

from __future__ import annotations

import secrets
import time
import uuid


def uuidv7() -> str:
    """Generate a UUID v7 string in canonical 8-4-4-4-12 format."""
    # 48-bit big-endian Unix timestamp in milliseconds.
    timestamp_ms = time.time_ns() // 1_000_000

    # 16-byte UUID buffer.
    uuid_bytes = bytearray(16)
    uuid_bytes[0] = (timestamp_ms >> 40) & 0xFF
    uuid_bytes[1] = (timestamp_ms >> 32) & 0xFF
    uuid_bytes[2] = (timestamp_ms >> 24) & 0xFF
    uuid_bytes[3] = (timestamp_ms >> 16) & 0xFF
    uuid_bytes[4] = (timestamp_ms >> 8) & 0xFF
    uuid_bytes[5] = timestamp_ms & 0xFF

    # 74 random bits (12 bits rand_a + 62 bits rand_b).
    rand = secrets.token_bytes(10)

    # Set version (4 bits) = 0b0111 and use the remaining 12 bits for rand_a.
    uuid_bytes[6] = 0x70 | (rand[0] & 0x0F)
    uuid_bytes[7] = rand[1]

    # Set variant (2 bits) = 0b10 and use the remaining 62 bits for rand_b.
    uuid_bytes[8] = 0x80 | (rand[2] & 0x3F)
    uuid_bytes[9:16] = rand[3:10]

    return str(uuid.UUID(bytes=bytes(uuid_bytes)))
