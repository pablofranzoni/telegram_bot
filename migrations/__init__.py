# migrations/__init__.py
"""
Database migration scripts for admin authentication.

This package contains all database migration scripts and tools for adding
JWT-secured admin authentication to the customers table.

Available Scripts:
    - migrate.py             - Main migration orchestrator (RECOMMENDED)
    - run_migration.py       - Low-level migration runner
    - verify_migration.py    - Post-migration verification
    - migration_sqlite.sql   - Raw SQL for SQLite
    - migration_postgresql.sql - Raw SQL for PostgreSQL
    - rollback_sqlite.sql    - Revert SQLite migration
    - rollback_postgresql.sql - Revert PostgreSQL migration

Quick Start:
    # SQLite
    python migrate.py --database sqlite --db-path ./instance/pedidos_bot.db
    
    # PostgreSQL
    python migrate.py --database postgresql --connection-string "postgresql://user:pass@localhost/db"

For more information, see README.md
"""
