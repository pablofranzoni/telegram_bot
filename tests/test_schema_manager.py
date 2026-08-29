"""Tests for the incremental schema manager."""

import os
import sqlite3

import pytest

from database.db_factory import DatabaseType
from database.schema_manager import (
    initialize_database,
    SchemaMigrationError,
    DB_AUTO_MIGRATE_ENV,
)


class _InMemoryDB:
    """Duck-typed DB with the surface used by schema_manager."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def execute(self, query, params=(), fetchone=False, fetchall=False, param_types=None):
        cur = self._conn.cursor()
        try:
            cur.execute(query, params)
            self._conn.commit()
            if fetchone:
                return cur.fetchone()
            if fetchall:
                return cur.fetchall()
            return cur.lastrowid
        finally:
            cur.close()

    def executescript(self, script: str) -> None:
        cur = self._conn.cursor()
        try:
            cur.executescript(script)
            self._conn.commit()
        finally:
            cur.close()

    def executemany(self, query, params_list):
        cur = self._conn.cursor()
        try:
            cur.executemany(query, params_list)
            self._conn.commit()
            return cur.rowcount
        finally:
            cur.close()

    def get_cursor(self):
        raise NotImplementedError

    def close_all_connections(self):
        self._conn.close()


def test_apply_mode_applies_base_schema():
    """El modo apply aplica el schema base sobre una base de datos vacía."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db = _InMemoryDB(conn)

    initialize_database(db, DatabaseType.SQLITE, mode="apply")

    tables = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
        fetchall=True,
    )
    table_names = {row["name"] for row in tables}

    expected = {
        "categories",
        "csv_processing_errors",
        "customers",
        "invoice_items",
        "invoices",
        "inventory_movements",
        "payments",
        "product_inventory",
        "products",
        "schema_migrations",
        "sent_documents",
        "upload_logs",
    }
    assert expected.issubset(table_names)

    # Verificar columnas nuevas de product_inventory (table_xinfo incluye generated columns)
    columns = db.execute(
        "PRAGMA table_xinfo(product_inventory)",
        fetchall=True,
    )
    column_names = {row["name"] for row in columns}
    assert "stock_disponible" in column_names
    assert "ultima_compra" in column_names
    assert "ubicacion_almacen" in column_names

    # Verificar trigger de inventory_movements en SQLite
    triggers = db.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND name = ?",
        ("trg_update_inventory",),
        fetchone=True,
    )
    assert triggers is not None

    migration = db.execute(
        "SELECT name FROM schema_migrations WHERE name = ?",
        ("001_base_schema.sql",),
        fetchone=True,
    )
    assert migration is not None
    assert migration["name"] == "001_base_schema.sql"


def test_apply_mode_is_idempotent():
    """Ejecutar apply dos veces no falla ni duplica registros."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db = _InMemoryDB(conn)

    initialize_database(db, DatabaseType.SQLITE, mode="apply")
    initialize_database(db, DatabaseType.SQLITE, mode="apply")

    count = db.execute(
        "SELECT COUNT(*) AS total FROM schema_migrations",
        fetchone=True,
    )
    assert count["total"] == 4


def test_verify_mode_passes_when_fully_migrated():
    """El modo verify pasa si todas las migraciones están aplicadas."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db = _InMemoryDB(conn)

    initialize_database(db, DatabaseType.SQLITE, mode="apply")
    initialize_database(db, DatabaseType.SQLITE, mode="verify")


def test_verify_mode_fails_when_pending_migrations():
    """El modo verify falla si falta alguna migración."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db = _InMemoryDB(conn)

    # Aplicamos parcialmente: solo creamos schema_migrations sin contenido.
    db.execute("""
        CREATE TABLE schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    with pytest.raises(SchemaMigrationError, match="Schema incompleto"):
        initialize_database(db, DatabaseType.SQLITE, mode="verify")


def test_default_mode_is_verify():
    """Por defecto, initialize_database opera en modo verify."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db = _InMemoryDB(conn)

    # Base vacía + sin DB_AUTO_MIGRATE => debe fallar con Schema incompleto.
    with pytest.raises(SchemaMigrationError, match="Schema incompleto"):
        initialize_database(db, DatabaseType.SQLITE)


def test_env_db_auto_migrate_true_uses_apply_mode(monkeypatch):
    """DB_AUTO_MIGRATE=true fuerza el modo apply."""
    monkeypatch.setenv(DB_AUTO_MIGRATE_ENV, "true")

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db = _InMemoryDB(conn)

    initialize_database(db, DatabaseType.SQLITE)

    migration = db.execute(
        "SELECT name FROM schema_migrations WHERE name = ?",
        ("001_base_schema.sql",),
        fetchone=True,
    )
    assert migration is not None


def test_env_db_auto_migrate_false_uses_verify_mode(monkeypatch):
    """DB_AUTO_MIGRATE=false fuerza el modo verify."""
    monkeypatch.setenv(DB_AUTO_MIGRATE_ENV, "false")

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db = _InMemoryDB(conn)

    with pytest.raises(SchemaMigrationError, match="Schema incompleto"):
        initialize_database(db, DatabaseType.SQLITE)


def test_fails_without_migrations():
    """Si no hay archivos de migración, el proceso falla."""
    conn = sqlite3.connect(":memory:")
    db = _InMemoryDB(conn)

    with pytest.raises(SchemaMigrationError):
        initialize_database(db, DatabaseType.MYSQL, mode="apply")


def test_db_auto_migrate_env_values(monkeypatch):
    """DB_AUTO_MIGRATE acepta varios valores truthy/falsy."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    for value in ("true", "1", "yes", "on", "TRUE", " True "):
        db = _InMemoryDB(conn)
        monkeypatch.setenv(DB_AUTO_MIGRATE_ENV, value)
        initialize_database(db, DatabaseType.SQLITE, mode=None)
        # Si llegamos aquí, apply funcionó; limpiamos para el siguiente ciclo.
        conn.close()
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row

    for value in ("false", "0", "no", "off", "", None):
        db = _InMemoryDB(conn)
        if value is not None:
            monkeypatch.setenv(DB_AUTO_MIGRATE_ENV, value)
        else:
            monkeypatch.delenv(DB_AUTO_MIGRATE_ENV, raising=False)
        with pytest.raises(SchemaMigrationError, match="Schema incompleto"):
            initialize_database(db, DatabaseType.SQLITE, mode=None)
        conn.close()
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
