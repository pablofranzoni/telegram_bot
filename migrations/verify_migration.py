# migrations/verify_migration.py
"""
Verify that migrations were applied correctly.

This script checks that all required columns and indexes exist.

Usage:
    python verify_migration.py --database sqlite --db-path ./instance/pedidos_bot.db
    python verify_migration.py --database postgresql --connection-string "postgresql://user:pass@localhost/db"
"""

import argparse
import logging
import sys
from typing import Dict, List, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


REQUIRED_COLUMNS = {
    'password_hash': 'Password hash for admin users',
    'is_admin': 'Admin flag (0=customer, 1=admin)',
    'email_verified': 'Email verification status',
    'email_verification_code': '6-digit verification code',
    'email_verification_expires': 'Verification code expiration',
    'password_reset_token': 'Password reset token',
    'password_reset_expires': 'Password reset expiration',
    'created_by': 'Audit field - who created this user',
}

REQUIRED_INDEXES = [
    'idx_customers_username',
    'idx_customers_email',
    'idx_customers_is_admin',
    'idx_customers_email_verified',
    'idx_customers_password_reset_token',
    'idx_customers_email_verification_code',
]


def verify_sqlite(db_path: str) -> bool:
    """
    Verify SQLite migration.
    
    Args:
        db_path: Path to SQLite database
        
    Returns:
        True if all checks pass
    """
    try:
        import sqlite3
        
        logger.info(f"Verifying SQLite database: {db_path}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check columns
        logger.info("Checking columns...")
        cursor.execute("PRAGMA table_info(customers)")
        columns = {row[1]: row for row in cursor.fetchall()}
        
        all_columns_exist = True
        for col_name, col_desc in REQUIRED_COLUMNS.items():
            if col_name in columns:
                logger.info(f"  ✓ {col_name:35} ({col_desc})")
            else:
                logger.error(f"  ✗ {col_name:35} MISSING!")
                all_columns_exist = False
        
        # Check indexes
        logger.info("\nChecking indexes...")
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND tbl_name='customers'
        """)
        indexes = {row[0] for row in cursor.fetchall()}
        
        all_indexes_exist = True
        for idx_name in REQUIRED_INDEXES:
            if idx_name in indexes:
                logger.info(f"  ✓ {idx_name}")
            else:
                logger.warning(f"  ⚠ {idx_name:40} (optional)")
        
        # Check data integrity
        logger.info("\nChecking data integrity...")
        cursor.execute("SELECT COUNT(*) FROM customers")
        total = cursor.fetchone()[0]
        logger.info(f"  ✓ Total customers: {total}")
        
        cursor.execute("SELECT COUNT(*) FROM customers WHERE is_admin = 1")
        admins = cursor.fetchone()[0]
        logger.info(f"  ✓ API admins: {admins}")
        
        cursor.execute("SELECT COUNT(*) FROM customers WHERE email_verified = 1")
        verified = cursor.fetchone()[0]
        logger.info(f"  ✓ Email verified: {verified}")
        
        conn.close()
        
        if all_columns_exist:
            logger.info("\n✓ SQLite migration verified successfully!")
            return True
        else:
            logger.error("\n✗ Some columns are missing!")
            return False
        
    except Exception as e:
        logger.error(f"✗ SQLite verification failed: {str(e)}")
        return False


def verify_postgresql(connection_string: str) -> bool:
    """
    Verify PostgreSQL migration.
    
    Args:
        connection_string: PostgreSQL connection string
        
    Returns:
        True if all checks pass
    """
    try:
        import psycopg2
        
        logger.info(f"Verifying PostgreSQL database...")
        
        conn = psycopg2.connect(connection_string)
        cursor = conn.cursor()
        
        # Check columns
        logger.info("Checking columns...")
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'customers'
            ORDER BY ordinal_position
        """)
        columns = {row[0]: row[1] for row in cursor.fetchall()}
        
        all_columns_exist = True
        for col_name, col_desc in REQUIRED_COLUMNS.items():
            if col_name in columns:
                logger.info(f"  ✓ {col_name:35} ({columns[col_name]})")
            else:
                logger.error(f"  ✗ {col_name:35} MISSING!")
                all_columns_exist = False
        
        # Check indexes
        logger.info("\nChecking indexes...")
        cursor.execute("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename = 'customers'
        """)
        indexes = {row[0] for row in cursor.fetchall()}
        
        for idx_name in REQUIRED_INDEXES:
            if idx_name in indexes:
                logger.info(f"  ✓ {idx_name}")
            else:
                logger.warning(f"  ⚠ {idx_name:40} (optional)")
        
        # Check data integrity
        logger.info("\nChecking data integrity...")
        cursor.execute("SELECT COUNT(*) FROM customers")
        total = cursor.fetchone()[0]
        logger.info(f"  ✓ Total customers: {total}")
        
        cursor.execute("SELECT COUNT(*) FROM customers WHERE is_admin = 1")
        admins = cursor.fetchone()[0]
        logger.info(f"  ✓ API admins: {admins}")
        
        cursor.execute("SELECT COUNT(*) FROM customers WHERE email_verified = TRUE")
        verified = cursor.fetchone()[0]
        logger.info(f"  ✓ Email verified: {verified}")
        
        conn.close()
        
        if all_columns_exist:
            logger.info("\n✓ PostgreSQL migration verified successfully!")
            return True
        else:
            logger.error("\n✗ Some columns are missing!")
            return False
        
    except Exception as e:
        logger.error(f"✗ PostgreSQL verification failed: {str(e)}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Verify database migration"
    )
    parser.add_argument(
        '--database',
        choices=['sqlite', 'postgresql'],
        required=True,
        help='Database type to verify'
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
        success = verify_sqlite(args.db_path)
    else:  # postgresql
        if not args.connection_string:
            parser.error('--connection-string is required for postgresql')
        success = verify_postgresql(args.connection_string)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
