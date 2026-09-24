#!/usr/bin/env python3
"""Aplica el schema y migraciones con un usuario administrador.

Uso:
    SQLite:
        python database/apply_schema.py --database sqlite --db-path ./pedidos_bot.db

    PostgreSQL (connection string):
        python database/apply_schema.py --database postgresql \
            --connection-string "postgresql://admin:pass@host/db"

    PostgreSQL (parámetros separados):
        python database/apply_schema.py --database postgresql \
            --db-host localhost --db-name db --db-user admin --db-password pass

    MySQL (connection string):
        python database/apply_schema.py --database mysql \
            --connection-string "mysql://admin:pass@host/db"

    Marcar migraciones como aplicadas sin ejecutar SQL (legacy):
        python database/apply_schema.py --database postgresql \
            --connection-string "postgresql://admin:pass@host/db" --mark-applied

Este script ejecuta el schema en modo ``apply`` por defecto (``DB_AUTO_MIGRATE``
se ignora), por lo que debe ejecutarse con un usuario que tenga privilegios de
DDL sobre la base de datos.

La opción ``--mark-applied`` solo registra las migraciones existentes en
``schema_migrations`` sin ejecutar el SQL. Sirve para bases de datos que ya
contienen el schema correcto y solo necesitan sincronizar la tabla de control.
"""

import argparse
import os
import sys

# Agregar el project root al path para poder importar desde database.*
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_factory import DatabaseFactory, DatabaseType
from database.schema_manager import (
    initialize_database,
    mark_migrations_applied,
    SchemaMigrationError,
)


def _build_database(args: argparse.Namespace):
    """Construye la instancia de base de datos según los argumentos."""
    if args.database == "sqlite":
        if not args.db_path:
            raise ValueError("--db-path es requerido para sqlite")
        return DatabaseFactory.create_database(
            DatabaseType.SQLITE,
            db_path=args.db_path,
        )

    if args.database == "postgresql":
        if args.connection_string:
            return DatabaseFactory.create_database(
                DatabaseType.POSTGRESQL,
                db_url=args.connection_string,
            )
        if not all([args.db_host, args.db_name, args.db_user, args.db_password]):
            raise ValueError(
                "Para postgresql se requiere --connection-string o "
                "--db-host, --db-name, --db-user y --db-password"
            )
        return DatabaseFactory.create_database(
            DatabaseType.POSTGRESQL,
            DB_HOST=args.db_host,
            DB_NAME=args.db_name,
            DB_USER=args.db_user,
            DB_PASSWORD=args.db_password,
            DB_PORT=args.db_port or 5432,
        )

    if args.database == "mysql":
        if args.connection_string:
            return DatabaseFactory.create_database(
                DatabaseType.MYSQL,
                db_url=args.connection_string,
            )
        if not all([args.db_host, args.db_name, args.db_user, args.db_password]):
            raise ValueError(
                "Para mysql se requiere --connection-string o "
                "--db-host, --db-name, --db-user y --db-password"
            )
        return DatabaseFactory.create_database(
            DatabaseType.MYSQL,
            host=args.db_host,
            database=args.db_name,
            user=args.db_user,
            password=args.db_password,
            port=args.db_port or 3306,
        )

    raise ValueError(f"Tipo de base de datos no soportado: {args.database}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aplica el schema y migraciones de la base de datos."
    )
    parser.add_argument(
        "--database",
        choices=["sqlite", "postgresql", "mysql"],
        required=True,
        help="Tipo de base de datos",
    )
    parser.add_argument(
        "--db-path",
        help="Ruta al archivo SQLite (requerido para sqlite)",
    )
    parser.add_argument(
        "--connection-string",
        help="Connection string para postgresql o mysql",
    )
    parser.add_argument(
        "--db-host",
        help="Host de la base de datos",
    )
    parser.add_argument(
        "--db-port",
        type=int,
        help="Puerto de la base de datos",
    )
    parser.add_argument(
        "--db-name",
        help="Nombre de la base de datos",
    )
    parser.add_argument(
        "--db-user",
        help="Usuario de la base de datos",
    )
    parser.add_argument(
        "--db-password",
        help="Contraseña del usuario",
    )
    parser.add_argument(
        "--mark-applied",
        action="store_true",
        help=(
            "Solo marca las migraciones como aplicadas en schema_migrations "
            "sin ejecutar el SQL. Útil para bases de datos legacy con el "
            "schema ya existente."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Muestra qué migraciones se aplicarían o marcarían, sin tocar la "
            "base de datos."
        ),
    )

    args = parser.parse_args()

    if args.mark_applied and args.dry_run:
        print("Error: --mark-applied y --dry-run son mutuamente excluyentes.", file=sys.stderr)
        return 1

    try:
        db = _build_database(args)
        db_type = DatabaseType(args.database)

        if args.dry_run:
            from database.schema_manager import _discover_migrations
            migrations = _discover_migrations(db_type)
            print(f"Migraciones disponibles para {db_type.value}: {len(migrations)}")
            for number, name, path in migrations:
                print(f"  {number}: {name}")
            return 0

        if args.mark_applied:
            mark_migrations_applied(db, db_type)
            print("Migraciones marcadas como aplicadas correctamente.")
        else:
            initialize_database(db, db_type, mode="apply")
            print("Schema aplicado correctamente.")
    except SchemaMigrationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error de argumentos: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error inesperado: {e}", file=sys.stderr)
        return 1
    finally:
        try:
            db.close_all_connections()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
