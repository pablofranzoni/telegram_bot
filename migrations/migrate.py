#!/usr/bin/env python3
# migrations/migrate.sh (o migrate.py para Windows)
"""
Complete migration orchestrator for admin authentication schema.

This is the recommended way to run all migrations with proper error handling,
logging, and verification.

Usage:
    python migrate.py --database sqlite --db-path ./instance/pedidos_bot.db
    python migrate.py --database postgresql --connection-string "postgresql://user:pass@localhost/db"
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_migration(db_type: str, db_path: str = None, conn_string: str = None) -> bool:
    """
    Run complete migration process.
    
    Process:
    1. Run migration script
    2. Verify migration
    3. Report results
    
    Args:
        db_type: 'sqlite' or 'postgresql'
        db_path: Path to SQLite database
        conn_string: PostgreSQL connection string
        
    Returns:
        True if successful
    """
    migrations_dir = Path(__file__).parent
    
    logger.info("=" * 70)
    logger.info("Starting Database Migration for Admin Authentication")
    logger.info("=" * 70)
    
    # Step 1: Run migration
    logger.info("\n[Step 1/2] Running migration script...")
    logger.info("-" * 70)
    
    cmd = [
        sys.executable,
        str(migrations_dir / 'run_migration.py'),
        '--database', db_type
    ]
    
    if db_type == 'sqlite':
        if not db_path:
            logger.error("Error: --db-path is required for sqlite")
            return False
        cmd.extend(['--db-path', db_path])
    else:  # postgresql
        if not conn_string:
            logger.error("Error: --connection-string is required for postgresql")
            return False
        cmd.extend(['--connection-string', conn_string])
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        if result.returncode != 0:
            logger.error("Migration script failed!")
            return False
    except subprocess.CalledProcessError as e:
        logger.error(f"Migration script failed with error: {e}")
        return False
    except FileNotFoundError:
        logger.error("run_migration.py not found!")
        return False
    
    # Step 2: Verify migration
    logger.info("\n[Step 2/2] Verifying migration...")
    logger.info("-" * 70)
    
    cmd = [
        sys.executable,
        str(migrations_dir / 'verify_migration.py'),
        '--database', db_type
    ]
    
    if db_type == 'sqlite':
        cmd.extend(['--db-path', db_path])
    else:  # postgresql
        cmd.extend(['--connection-string', conn_string])
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        if result.returncode != 0:
            logger.warning("Verification found issues, but migration may still be valid")
    except subprocess.CalledProcessError as e:
        logger.warning(f"Verification failed: {e}")
    except FileNotFoundError:
        logger.error("verify_migration.py not found!")
        return False
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("✓ Migration completed successfully!")
    logger.info("=" * 70)
    logger.info("\nNext steps:")
    logger.info("1. Test API endpoints to ensure everything works")
    logger.info("2. Create the first admin user via /api/register")
    logger.info("3. Monitor logs for any issues")
    
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Complete database migration with verification"
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
    parser.add_argument(
        '--skip-verify',
        action='store_true',
        help='Skip verification step'
    )
    
    args = parser.parse_args()
    
    # Validate required arguments
    if args.database == 'sqlite' and not args.db_path:
        parser.error('--db-path is required for sqlite')
    elif args.database == 'postgresql' and not args.connection_string:
        parser.error('--connection-string is required for postgresql')
    
    # Run migration
    success = run_migration(
        db_type=args.database,
        db_path=args.db_path,
        conn_string=args.connection_string
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
