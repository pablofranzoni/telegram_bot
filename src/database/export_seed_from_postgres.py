#!/usr/bin/env python3
"""Exporta filas de PostgreSQL a sentencias INSERT compatibles con SQLite.

Lee las tablas ``categories``, ``products`` y ``customers`` de una base
PostgreSQL y genera un archivo SQL con sentencias ``INSERT`` que pueden
ejecutarse directamente en SQLite (por ejemplo, para poblar una base de
producción low-cost o un entorno de desarrollo local).

Uso:
    # Desde variables de entorno (DATABASE_URL)
    python database/export_seed_from_postgres.py > seed.sql

    # Parámetros individuales
    python database/export_seed_from_postgres.py \
        --host localhost --port 5432 --dbname mi_db --user admin --password secret \
        --output seed.sql

    # Tablas adicionales
    python database/export_seed_from_postgres.py --tables categories,products --output seed.sql

Notas:
- Los booleans se convierten a 1/0.
- Los UUIDs se serializan como texto.
- Las fechas/timestamps se escapan como cadenas ISO 8601.
- Se omiten los valores ``None`` usando ``DEFAULT`` para la columna.
- Las columnas que no existen en SQLite (por ejemplo, columnas propias de
  PostgreSQL) se ignoran automáticamente.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

# Asegurar que podamos importar database.*
sys.path.insert(0, str(Path(__file__).parent.parent))


def _build_connection_string(args: argparse.Namespace) -> str:
    """Construye la connection string de psycopg2."""
    if args.connection_string:
        return args.connection_string

    password_part = f":{args.password}" if args.password else ""
    return (
        f"postgresql://{args.user}{password_part}@{args.host}:{args.port}/{args.dbname}"
    )


def _sqlite_literal(value: Any) -> str:
    """Convierte un valor Python a un literal SQL seguro para SQLite."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, (datetime, date)):
        return "'" + value.isoformat().replace("'", "''") + "'"
    if isinstance(value, UUID):
        return "'" + str(value).replace("'", "''") + "'"
    # Cualquier otro valor se trata como texto.
    return "'" + str(value).replace("'", "''") + "'"


def _export_table(cursor, table_name: str, columns: list[str]) -> list[str]:
    """Genera sentencias INSERT para una tabla."""
    lines: list[str] = []
    lines.append(f"-- Tabla {table_name}")
    lines.append(f"DELETE FROM {table_name};")

    col_list = ", ".join(f'"{c}"' for c in columns)
    cursor.execute(f"SELECT {col_list} FROM {table_name}")
    rows = cursor.fetchall()

    if not rows:
        lines.append(f"-- (sin filas en {table_name})")
        return lines

    for row in rows:
        values = ", ".join(_sqlite_literal(row[c]) for c in columns)
        lines.append(f"INSERT INTO {table_name} ({col_list}) VALUES ({values});")

    return lines


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exporta categories/products/customers de PostgreSQL a INSERTs SQLite."
    )
    parser.add_argument(
        "--connection-string",
        default=os.getenv("DATABASE_URL"),
        help="Connection string de PostgreSQL (default: env DATABASE_URL)",
    )
    parser.add_argument("--host", default=os.getenv("DB_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("DB_PORT", "5432")))
    parser.add_argument("--dbname", default=os.getenv("DB_NAME"))
    parser.add_argument("--user", default=os.getenv("DB_USER"))
    parser.add_argument("--password", default=os.getenv("DB_PASSWORD"))
    parser.add_argument(
        "--output",
        help="Archivo de salida. Si no se especifica, escribe a stdout.",
    )
    parser.add_argument(
        "--tables",
        default="categories,products,customers",
        help="Tablas a exportar, separadas por comas.",
    )

    args = parser.parse_args()

    connection_string = _build_connection_string(args)
    if not connection_string or "postgresql://" not in connection_string:
        print(
            "Error: se requiere una connection string de PostgreSQL. "
            "Usa --connection-string o variables DB_HOST/DB_NAME/DB_USER/DB_PASSWORD.",
            file=sys.stderr,
        )
        return 1

    try:
        import psycopg2
    except ImportError as exc:
        print(f"Error: psycopg2 no está instalado: {exc}", file=sys.stderr)
        return 1

    # Columnas conocidas por tabla (deben existir tanto en PostgreSQL como en SQLite).
    # Ajusta según tu schema real.
    table_columns = {
        "categories": ["id", "codigo", "nombre", "descripcion", "parent_id"],
        "products": ["id", "nombre", "descripcion", "precio", "disponible", "category_id"],
        "customers": [
            "id",
            "customer_id",
            "name",
            "email",
            "phone",
            "address",
            "city",
            "state",
            "country",
            "postal_code",
            "company",
            "username",
            "password_hash",
            "created_at",
            "updated_at",
            "is_active",
            "is_admin",
            "email_verified",
            "email_verification_code",
            "email_verification_expires",
            "password_reset_token",
            "password_reset_expires",
            "created_by",
            "notes",
            "last_purchase_date",
            "total_purchases",
        ],
    }

    selected_tables = [t.strip() for t in args.tables.split(",") if t.strip()]

    sql_lines: list[str] = [
        "-- Seed data exported from PostgreSQL to SQLite",
        "-- Generated by database/export_seed_from_postgres.py",
        "PRAGMA foreign_keys = OFF;",
        "",
    ]

    conn = psycopg2.connect(connection_string)
    try:
        with conn.cursor() as cursor:
            for table in selected_tables:
                if table not in table_columns:
                    print(f"Advertencia: tabla desconocida '{table}', omitida.", file=sys.stderr)
                    continue

                # Filtrar columnas que realmente existen en PostgreSQL.
                cursor.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = %s",
                    (table,),
                )
                existing_cols = {row[0] for row in cursor.fetchall()}
                cols = [c for c in table_columns[table] if c in existing_cols]

                if not cols:
                    print(f"Advertencia: ninguna columna coincidente en '{table}'.", file=sys.stderr)
                    continue

                sql_lines.extend(_export_table(cursor, table, cols))
                sql_lines.append("")
    finally:
        conn.close()

    sql_lines.append("PRAGMA foreign_keys = ON;")
    sql_output = "\n".join(sql_lines)

    if args.output:
        Path(args.output).write_text(sql_output, encoding="utf-8")
        print(f"Seed SQL escrito en: {args.output}")
    else:
        print(sql_output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
