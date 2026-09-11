"""Tests for UUID v7 generation."""

import re
import time
import uuid

import pytest

from utils.uuid_utils import uuidv7


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def test_uuidv7_returns_canonical_string():
    value = uuidv7()
    assert isinstance(value, str)
    assert _UUID_RE.match(value) is not None


def test_uuidv7_is_unique():
    values = {uuidv7() for _ in range(100)}
    assert len(values) == 100


def test_uuidv7_timestamp_is_recent():
    before = int(time.time() * 1000)
    value = uuidv7()
    after = int(time.time() * 1000)

    u = uuid.UUID(value)
    timestamp_ms = int.from_bytes(u.bytes[:6], "big")
    assert before - 1000 <= timestamp_ms <= after + 1000


def test_uuidv7_is_sortable_by_time():
    first = uuidv7()
    time.sleep(0.005)
    second = uuidv7()
    assert first < second
    assert sorted([second, first]) == [first, second]
