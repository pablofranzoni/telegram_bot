# migrations/run_migration.py
"""
Database migration runner for admin authentication schema updates.

This script applies the ALTER TABLE migrations to add admin authentication
fields to the customers table.

Usage:
    python run_migration.py --database sqlite      # For SQLite
    python run_migration.py --database postgresql  # For PostgreSQL
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_sqlite_migration(db_path: str) -> bool:
    """
    Run SQLite migration.
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        import sqlite3
        
        logger.info(f"Connecting to SQLite database: {db_path}")
        
        if not os.path.exists(db_path):
            logger.error(f"Database file not found: {db_path}")
            return False
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        logger.info("Running SQLite migration...")
        
        # Add password hash field
        try:
            cursor.execute("ALTER TABLE customers ADD COLUMN password_hash TEXT")
            logger.info("✓ Added password_hash column")
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                logger.info("✓ password_hash column already exists")
            else:
                raise
        
        # Add is_admin flag
        try:
            cursor.execute("ALTER TABLE customers ADD COLUMN is_admin INTEGER DEFAULT 0")
            logger.info("✓ Added is_admin column")
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                logger.info("✓ is_admin column already exists")
            else:
                raise
        
        # Add email verification fields
        try:
            cursor.execute("ALTER TABLE customers ADD COLUMN email_verified BOOLEAN DEFAULT 0")
            logger.info("✓ Added email_verified column")
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                logger.info("✓ email_verified column already exists")
            else:
                raise
        
        try:
            cursor.execute("ALTER TABLE customers ADD COLUMN email_verification_code TEXT")
            logger.info("✓ Added email_verification_code column")
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                logger.info("✓ email_verification_code column already exists")
            else:
                raise
        
        try:
            cursor.execute("ALTER TABLE customers ADD COLUMN email_verification_expires TIMESTAMP")
            logger.info("✓ Added email_verification_expires column")
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                logger.info("✓ email_verification_expires column already exists")
            else:
                raise
        
        # Add password reset fields
        try:
            cursor.execute("ALTER TABLE customers ADD COLUMN password_reset_token TEXT")
            logger.info("✓ Added password_reset_token column")
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                logger.info("✓ password_reset_token column already exists")
            else:
                raise
        
        try:
            cursor.execute("ALTER TABLE customers ADD COLUMN password_reset_expires TIMESTAMP")
            logger.info("✓ Added password_reset_expires column")
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                logger.info("✓ password_reset_expires column already exists")
            else:
                raise
        
        # Add audit field
        try:
            cursor.execute("ALTER TABLE customers ADD COLUMN created_by INTEGER REFERENCES customers(id)")
            logger.info("✓ Added created_by column")
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                logger.info("✓ created_by column already exists")
            else:
                raise
        
        # Create indexes
        indexes = [
            ("idx_customers_username", "CREATE INDEX IF NOT EXISTS idx_customers_username ON customers(username)"),
            ("idx_customers_email", "CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email)"),
            ("idx_customers_is_admin", "CREATE INDEX IF NOT EXISTS idx_customers_is_admin ON customers(is_admin)"),
            ("idx_customers_email_verified", "CREATE INDEX IF NOT EXISTS idx_customers_email_verified ON customers(email_verified)"),
            ("idx_customers_password_reset_token", "CREATE INDEX IF NOT EXISTS idx_customers_password_reset_token ON customers(password_reset_token)"),
            ("idx_customers_email_verification_code", "CREATE INDEX IF NOT EXISTS idx_customers_email_verification_code ON customers(email_verification_code)"),
        ]
        
        for idx_name, idx_sql in indexes:
            cursor.execute(idx_sql)
            logger.info(f"✓ Created index: {idx_name}")
        
        conn.commit()
        
        # Verify migration
        cursor.execute("SELECT COUNT(*) FROM customers")
        total = cursor.fetchone()[0]
        logger.info(f"✓ Migration successful! Total customers: {total}")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"✗ SQLite migration failed: {str(e)}")
        return False


def run_postgresql_migration(connection_string: str) -> bool:
    """
    Run PostgreSQL migration.
    
    Args:
        connection_string: PostgreSQL connection string
        
    Returns:
        True if successful, False otherwise
    """
    try:
        import psycopg2
        
        logger.info(f"Connecting to PostgreSQL database...")
        
        conn = psycopg2.connect(connection_string)
        cursor = conn.cursor()
        
        logger.info("Running PostgreSQL migration...")
        
        migration_sql = """
        -- Add password hash field
        ALTER TABLE customers ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
        
        -- Add is_admin flag
        ALTER TABLE customers ADD COLUMN IF NOT EXISTS is_admin INTEGER DEFAULT 0;
        
        -- Add email verification fields
        ALTER TABLE customers ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE;
        ALTER TABLE customers ADD COLUMN IF NOT EXISTS email_verification_code VARCHAR(10);
        ALTER TABLE customers ADD COLUMN IF NOT EXISTS email_verification_expires TIMESTAMP;
        
        -- Add password reset fields
        ALTER TABLE customers ADD COLUMN IF NOT EXISTS password_reset_token VARCHAR(64);
        ALTER TABLE customers ADD COLUMN IF NOT EXISTS password_reset_expires TIMESTAMP;
        
        -- Add audit field
        ALTER TABLE customers ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES customers(id);
        
        -- Create indexes
        CREATE INDEX IF NOT EXISTS idx_customers_username ON customers(username);
        CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);
        CREATE INDEX IF NOT EXISTS idx_customers_is_admin ON customers(is_admin);
        CREATE INDEX IF NOT EXISTS idx_customers_email_verified ON customers(email_verified);
        CREATE INDEX IF NOT EXISTS idx_customers_password_reset_token ON customers(password_reset_token);
        CREATE INDEX IF NOT EXISTS idx_customers_email_verification_code ON customers(email_verification_code);
        """
        
        cursor.execute(migration_sql)
        conn.commit()
        
        # Verify migration
        cursor.execute("SELECT COUNT(*) FROM customers")
        total = cursor.fetchone()[0]
        logger.info(f"✓ Migration successful! Total customers: {total}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"✗ PostgreSQL migration failed: {str(e)}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run database migrations for admin authentication"
    )
    parser.add_argument(
        '--database',
        choices=['sqlite', 'postgresql'],
        required=True,
        help='Database type to migrate'
    )
    parser.add_argument(
        '--db-path',
        help='Path to SQLite database file (required for sqlite)'
    )
    parser.add_argument(
        '--connection-string',
        help='PostgreSQL connection string (required for postgresql)'
    )
    
    args = parser.parse_args()
    
    if args.database == 'sqlite':
        if not args.db_path:
            parser.error('--db-path is required for sqlite')
        
        success = run_sqlite_migration(args.db_path)
    
    else:  # postgresql
        if not args.connection_string:
            parser.error('--connection-string is required for postgresql')
        
        success = run_postgresql_migration(args.connection_string)
    
    if success:
        logger.info("✓ All migrations completed successfully!")
        sys.exit(0)
    else:
        logger.error("✗ Migration failed!")
        sys.exit(1)


if __name__ == '__main__':
    main()
