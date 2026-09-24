"""Unit tests for auth_service."""

import sqlite3

from shared.services import auth_service


def test_is_valid_email_accepts_well_formed_addresses():
    assert auth_service.is_valid_email("ana@example.com") is True
    assert auth_service.is_valid_email("user.name+shop@example.com") is True


def test_is_valid_email_rejects_invalid_values():
    assert auth_service.is_valid_email("") is False
    assert auth_service.is_valid_email("sin-arroba") is False
    assert auth_service.is_valid_email("ana@example") is False
    assert auth_service.is_valid_email(f"{'a' * 101}@example.com") is False


def test_generate_verification_code_returns_six_digits():
    code = auth_service.generate_verification_code()

    assert len(code) == 6
    assert code.isdigit() is True


def test_get_customer_with_email_returns_customer_when_email_exists(monkeypatch):
    monkeypatch.setattr(
        auth_service,
        "obtener_cliente",
        lambda telegram_id: {"id": telegram_id, "email": "ana@example.com"},
    )

    result = auth_service.get_customer_with_email(123)

    assert result == {"id": 123, "email": "ana@example.com"}


def test_get_customer_with_email_works_with_sqlite_row(monkeypatch):
    """Regression: obtener_cliente returns sqlite3.Row, which has no .get()."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE customers (id INTEGER, email TEXT)")
    conn.execute("INSERT INTO customers VALUES (?, ?)", (123, "ana@example.com"))
    row = conn.execute("SELECT * FROM customers").fetchone()

    monkeypatch.setattr(auth_service, "obtener_cliente", lambda telegram_id: row)

    result = auth_service.get_customer_with_email(123)

    assert result == row


def test_get_customer_with_email_returns_none_when_email_is_missing(monkeypatch):
    monkeypatch.setattr(auth_service, "obtener_cliente", lambda telegram_id: {"id": telegram_id, "email": None})

    result = auth_service.get_customer_with_email(123)

    assert result is None


def test_register_verified_customer_delegates_to_database(monkeypatch):
    captured: dict[str, object] = {}

    def fake_guardar_cliente(telegram_id, first_name, last_name, username, email=None):
        captured.update(
            {
                "telegram_id": telegram_id,
                "first_name": first_name,
                "last_name": last_name,
                "username": username,
                "email": email,
            }
        )

    monkeypatch.setattr(auth_service, "guardar_cliente", fake_guardar_cliente)

    auth_service.register_verified_customer(
        telegram_id=123,
        first_name="Ana",
        last_name="Perez",
        username="anap",
        email="ana@example.com",
    )

    assert captured == {
        "telegram_id": 123,
        "first_name": "Ana",
        "last_name": "Perez",
        "username": "anap",
        "email": "ana@example.com",
    }