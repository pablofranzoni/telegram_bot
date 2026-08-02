"""Gestión de schema y migraciones incrementales para SQLite, PostgreSQL y MySQL.

El directorio ``database/schema/<db_type>/`` contiene archivos SQL numerados,
ej. ``001_base_schema.sql``. El comportamiento por defecto es **verificar** que
el schema esté aplicado; el modo **apply** solo se activa mediante la variable
de entorno ``DB_AUTO_MIGRATE=true`` o llamando explícitamente con
``mode="apply"`` (por ejemplo, desde ``database/apply_schema.py``).

Si una migración falta en modo verify, la aplicación levanta
``SchemaMigrationError`` y no arranca. Si una migración falla en modo apply,
también se levanta ``SchemaMigrationError``.
"""

import os
import re
from enum import Enum
from pathlib import Path
from typing import List, Tuple

from database.db import DatabaseError, DatabaseInterface
from database.db_factory import DatabaseType
from utils.logger_factory import get_api_logger

logger = get_api_logger(__name__)

SCHEMA_DIR = Path(__file__).parent / "schema"

DB_AUTO_MIGRATE_ENV = "DB_AUTO_MIGRATE"

MIGRATION_RE = re.compile(r"^(\d+)_.*\.sql$")


class SchemaMigrationError(Exception):
    """Error irrecuperable durante la aplicación del schema o migraciones."""
    pass


class SchemaManagerMode(Enum):
    """Modos de operación del schema manager."""
    APPLY = "apply"
    VERIFY = "verify"


def _is_truthy(value: str | None) -> bool:
    """Devuelve True si el valor representa un booleano verdadero."""
    if value is None:
        return False
    return value.strip().lower() in ("true", "1", "yes", "on")


def _get_schema_directory(db_type: DatabaseType) -> Path:
    """Devuelve el directorio de migraciones para el motor de base de datos."""
    directory = SCHEMA_DIR / db_type.value
    if not directory.exists():
        raise SchemaMigrationError(
            f"No existe el directorio de migraciones: {directory}"
        )
    return directory


def _discover_migrations(db_type: DatabaseType) -> List[Tuple[int, str, Path]]:
    """Descubre y ordena los archivos de migración disponibles.

    Retorna una lista de tuplas ``(numero, nombre, path)`` ordenada por número.
    """
    directory = _get_schema_directory(db_type)
    migrations: List[Tuple[int, str, Path]] = []

    for path in directory.iterdir():
        match = MIGRATION_RE.match(path.name)
        if not path.is_file() or not match:
            continue
        migrations.append((int(match.group(1)), path.name, path))

    migrations.sort(key=lambda item: item[0])
    return migrations


def _ensure_migrations_table(db: DatabaseInterface, db_type: DatabaseType) -> None:
    """Crea la tabla de control de migraciones si no existe."""
    if db_type == DatabaseType.SQLITE:
        sql = """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    elif db_type == DatabaseType.POSTGRESQL:
        sql = """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    elif db_type == DatabaseType.MYSQL:
        sql = """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    else:
        raise SchemaMigrationError(f"Motor de base de datos no soportado: {db_type.value}")
    db.execute(sql)


def _is_applied(db: DatabaseInterface, migration_name: str) -> bool:
    """Verifica si una migración ya fue registrada como aplicada."""
    try:
        result = db.execute(
            "SELECT 1 FROM schema_migrations WHERE name = ?",
            (migration_name,),
            fetchone=True,
        )
    except DatabaseError as e:
        # Si la tabla no existe, la migración no está aplicada.
        if "no such table" in str(e).lower() or "does not exist" in str(e).lower():
            return False
        raise

    return result is not None


def _record_migration(db: DatabaseInterface, migration_name: str) -> None:
    """Registra una migración como aplicada."""
    db.execute(
        "INSERT INTO schema_migrations (name) VALUES (?)",
        (migration_name,),
    )


def _execute_sql_file(db: DatabaseInterface, path: Path) -> None:
    """Ejecuta un archivo SQL completo usando el adapter de base de datos."""
    script = path.read_text(encoding="utf-8")
    try:
        db.executescript(script)
    except DatabaseError as e:
        raise SchemaMigrationError(
            f"Error ejecutando {path.name}: {e}"
        ) from e


def _apply_database(db: DatabaseInterface, db_type: DatabaseType) -> None:
    """Aplica el schema base y todas las migraciones pendientes.

    Este modo debe ejecutarse con un usuario que tenga privilegios de DDL.
    """
    migrations = _discover_migrations(db_type)
    if not migrations:
        raise SchemaMigrationError(
            f"No se encontraron migraciones para {db_type.value} en {SCHEMA_DIR / db_type.value}"
        )

    logger.info(
        "Aplicando schema para %s (%d migraciones disponibles)",
        db_type.value,
        len(migrations),
    )

    _ensure_migrations_table(db, db_type)

    for number, name, path in migrations:
        if _is_applied(db, name):
            logger.info("Migración %s ya aplicada", name)
            continue

        logger.info("Aplicando migración %s", name)
        _execute_sql_file(db, path)
        _record_migration(db, name)
        logger.info("Migración %s aplicada correctamente", name)

    logger.info("Schema aplicado correctamente")


def _verify_database(db: DatabaseInterface, db_type: DatabaseType) -> None:
    """Verifica que el schema esté completo sin ejecutar DDL.

    Este modo está pensado para la aplicación en producción, donde el usuario
    de base de datos no tiene privilegios de DDL.
    """
    migrations = _discover_migrations(db_type)
    if not migrations:
        raise SchemaMigrationError(
            f"No se encontraron migraciones para {db_type.value} en {SCHEMA_DIR / db_type.value}"
        )

    logger.info(
        "Verificando schema para %s (%d migraciones disponibles)",
        db_type.value,
        len(migrations),
    )

    _ensure_migrations_table(db, db_type)

    pending = [name for _, name, _ in migrations if not _is_applied(db, name)]
    if pending:
        raise SchemaMigrationError(
            f"Schema incompleto: faltan {len(pending)} migración(es) pendiente(s): "
            f"{', '.join(pending)}. Aplique el schema con un usuario administrador "
            f"mediante: python database/apply_schema.py --database {db_type.value} "
            f"<opciones de conexión>"
        )

    logger.info("Schema verificado correctamente")


def mark_migrations_applied(
    db: DatabaseInterface,
    db_type: DatabaseType,
    migrations: List[Tuple[int, str, Path]] | None = None,
) -> None:
    """Marca migraciones como aplicadas sin ejecutar su SQL.

    Útil para bases de datos que ya tienen el schema correcto (legacy) y solo
    necesitan registrar las migraciones para que el verificador las reconozca.
    """
    if migrations is None:
        migrations = _discover_migrations(db_type)

    if not migrations:
        raise SchemaMigrationError(
            f"No se encontraron migraciones para {db_type.value} en {SCHEMA_DIR / db_type.value}"
        )

    logger.info(
        "Marcando migraciones como aplicadas para %s (%d migraciones)",
        db_type.value,
        len(migrations),
    )

    _ensure_migrations_table(db, db_type)

    for number, name, path in migrations:
        if _is_applied(db, name):
            logger.info("Migración %s ya registrada", name)
            continue
        _record_migration(db, name)
        logger.info("Migración %s marcada como aplicada", name)

    logger.info("Migraciones registradas correctamente")


def initialize_database(
    db: DatabaseInterface,
    db_type: DatabaseType,
    mode: SchemaManagerMode | None = None,
) -> None:
    """Inicializa o verifica el schema según el modo.

    Args:
        db: Instancia inicializada de base de datos.
        db_type: Tipo de motor (sqlite, postgresql, mysql).
        mode: Modo de operación. Si es None, se determina por la variable de
            entorno ``DB_AUTO_MIGRATE`` (default ``verify``).

    Raises:
        SchemaMigrationError: Si el schema no está completo o falla una
        migración.
    """
    if mode is None:
        mode = (
            SchemaManagerMode.APPLY
            if _is_truthy(os.getenv(DB_AUTO_MIGRATE_ENV))
            else SchemaManagerMode.VERIFY
        )
    elif isinstance(mode, str):
        mode = SchemaManagerMode(mode)

    logger.info("Modo de schema_manager: %s", mode.value)

    if mode == SchemaManagerMode.APPLY:
        _apply_database(db, db_type)
    else:
        _verify_database(db, db_type)
