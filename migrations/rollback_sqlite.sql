-- ===========================================================================
-- SQLite Rollback Script - Remove Admin Authentication Fields
-- ===========================================================================
-- SQLite has limited ALTER TABLE support, so rollback requires recreating
-- the entire table. This script creates a backup and rebuilds the table.
--
-- WARNING: This is a destructive operation! Always backup your database first.
-- Only use this if you need to completely revert the migration.
--
-- The process:
-- 1. Rename existing customers table to customers_old
-- 2. Create new customers table without the new columns
-- 3. Copy data from customers_old to customers
-- 4. Drop customers_old
--
-- Usage:
--   sqlite3 your_database.db < rollback_sqlite.sql
-- ===========================================================================

BEGIN TRANSACTION;

-- IMPORTANT: If this fails, you can restore from backup
-- sqlite3 your_database.db < backup.sql

-- Step 1: Rename existing table
ALTER TABLE customers RENAME TO customers_old;

-- Step 2: Create new customers table (original schema without new columns)
CREATE TABLE IF NOT EXISTS "customers" (
	"id"	INTEGER,
	"customer_id"	TEXT NOT NULL UNIQUE,
	"name"	TEXT NOT NULL,
	"email"	TEXT,
	"phone"	TEXT,
	"address"	TEXT,
	"city"	TEXT,
	"state"	TEXT,
	"country"	TEXT,
	"postal_code"	TEXT,
	"company"	TEXT,
	"username"	TEXT,
	"created_at"	TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	"updated_at"	TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	"is_active"	BOOLEAN DEFAULT 1,
	"notes"	TEXT,
	"last_purchase_date"	TIMESTAMP,
	"total_purchases"	REAL DEFAULT 0,
	PRIMARY KEY("id" AUTOINCREMENT)
);

-- Step 3: Copy data from old table (excluding new columns)
INSERT INTO customers (
	id,
	customer_id,
	name,
	email,
	phone,
	address,
	city,
	state,
	country,
	postal_code,
	company,
	username,
	created_at,
	updated_at,
	is_active,
	notes,
	last_purchase_date,
	total_purchases
)
SELECT
	id,
	customer_id,
	name,
	email,
	phone,
	address,
	city,
	state,
	country,
	postal_code,
	company,
	username,
	created_at,
	updated_at,
	is_active,
	notes,
	last_purchase_date,
	total_purchases
FROM customers_old;

-- Step 4: Drop old table
DROP TABLE customers_old;

-- Drop indexes from migration
DROP INDEX IF EXISTS idx_customers_username;
DROP INDEX IF EXISTS idx_customers_email;
DROP INDEX IF EXISTS idx_customers_is_admin;
DROP INDEX IF EXISTS idx_customers_email_verified;
DROP INDEX IF EXISTS idx_customers_password_reset_token;
DROP INDEX IF EXISTS idx_customers_email_verification_code;

-- Verify rollback
SELECT 'Rollback completed successfully!' as status;
SELECT COUNT(*) as total_customers FROM customers;
PRAGMA table_info(customers);

COMMIT;
