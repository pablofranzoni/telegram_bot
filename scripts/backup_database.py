#!/usr/bin/env python3
"""
Standalone database backup script.

Supports SQLite backups using the online ``sqlite3.Connection.backup()`` API,
which produces a consistent snapshot without requiring the ``-wal``/``-shm``
sibling files to be copied manually.

The script is intended to be run from a scheduler such as PythonAnywhere's
"Scheduled Tasks", cron, or a systemd timer. It does not require the Flask
application to be running.

Environment variables
---------------------
DB_TYPE                    Database type. Only ``sqlite`` is implemented by this
                           MVP script; other values cause a clear skip message.
                           Default: sqlite.
DATABASE_PATH / SQLITE_PATH Path to the SQLite database file.
                           Default: ./data.db
BACKUP_DIR                 Directory where backups are stored.
                           Default: ./backups
BACKUP_RETENTION_DAYS      Number of days to keep compressed backups.
                           Default: 7. Set to 0 to disable rotation.
LOG_DIR                    Directory for the backup log file.
                           Default: ./logs
"""

import gzip
import logging
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


DEFAULT_DB_TYPE = "sqlite"
DEFAULT_SQLITE_PATH = "./pedidos_bot.db"
DEFAULT_BACKUP_DIR = "./backups"
DEFAULT_RETENTION_DAYS = 7
DEFAULT_LOG_DIR = "./logs"


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer, got {value!r}") from exc


def setup_logging(log_dir: str) -> logging.Logger:
    """Configure a simple file+console logger for the backup script."""
    logger = logging.getLogger("backup_database")
    logger.setLevel(logging.INFO)

    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_path = Path(log_dir) / "backup.log"
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def backup_sqlite(source_path: Path, backup_dir: Path, retention_days: int, logger: logging.Logger) -> Path:
    """Create a compressed, timestamped backup of a SQLite database."""
    if not source_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {source_path}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_name = f"{source_path.stem}_{timestamp}.db"
    backup_path = backup_dir / backup_name
    compressed_path = backup_path.with_suffix(".db.gz")

    backup_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Starting SQLite backup: %s -> %s", source_path, compressed_path)

    # Use SQLite's online backup API. This creates a consistent snapshot of the
    # main database plus any committed WAL data, without needing to copy the
    # -wal / -shm files manually.
    source = sqlite3.connect(str(source_path))
    dest = sqlite3.connect(str(backup_path))
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()

    # Compress the backup and remove the uncompressed intermediate file.
    with open(backup_path, "rb") as f_in, gzip.open(compressed_path, "wb") as f_out:
        f_out.writelines(f_in)
    backup_path.unlink()

    logger.info("Backup created successfully: %s", compressed_path)

    if retention_days > 0:
        _rotate_backups(backup_dir, source_path.stem, retention_days, logger)

    return compressed_path


def _rotate_backups(backup_dir: Path, source_stem: str, retention_days: int, logger: logging.Logger) -> None:
    """Remove compressed backups older than ``retention_days``."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    pattern = f"{source_stem}_*.db.gz"
    removed = 0

    for backup_file in backup_dir.glob(pattern):
        try:
            # The filename contains an UTC timestamp, but stat mtime is safer.
            mtime = datetime.fromtimestamp(backup_file.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                backup_file.unlink()
                logger.info("Removed old backup: %s", backup_file.name)
                removed += 1
        except OSError as exc:
            logger.warning("Could not remove old backup %s: %s", backup_file, exc)

    logger.info("Rotation complete: removed %d backup(s) older than %d day(s)", removed, retention_days)


def main() -> int:
    db_type = os.getenv("DB_TYPE", DEFAULT_DB_TYPE).strip().lower()
    sqlite_path = Path(os.getenv("DATABASE_PATH") or os.getenv("SQLITE_PATH", DEFAULT_SQLITE_PATH))
    backup_dir = Path(os.getenv("BACKUP_DIR", DEFAULT_BACKUP_DIR))
    retention_days = _env_int("BACKUP_RETENTION_DAYS", DEFAULT_RETENTION_DAYS)
    log_dir = os.getenv("LOG_DIR", DEFAULT_LOG_DIR)

    logger = setup_logging(log_dir)

    logger.info(
        "Backup job started: db_type=%s source=%s backup_dir=%s retention_days=%s",
        db_type,
        sqlite_path,
        backup_dir,
        retention_days,
    )

    try:
        if db_type != "sqlite":
            logger.warning(
                "This MVP backup script only supports SQLite. Current DB_TYPE=%s; skipping backup.",
                db_type,
            )
            return 0

        backup_path = backup_sqlite(sqlite_path, backup_dir, retention_days, logger)
        logger.info("Backup finished: %s", backup_path)
        return 0

    except FileNotFoundError as exc:
        logger.error("Backup failed: %s", exc)
        return 1
    except sqlite3.Error as exc:
        logger.error("Backup failed due to SQLite error: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Backup failed with unexpected error: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
