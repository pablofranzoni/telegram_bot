-- ===========================================================================
-- PostgreSQL Migration Script - Add Admin Authentication Fields
-- ===========================================================================
-- This script migrates the customers table to support JWT-secured admin 
-- authentication with email verification and password reset functionality.
--
-- WARNING: Always backup your database before running migrations!
--
-- Usage:
--   psql -U username -d database_name -f migration_postgresql.sql
-- ===========================================================================

BEGIN;

-- Add password hash field for admin users
ALTER TABLE customers ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);

-- Add is_admin flag (0 = customer, 1 = admin)
ALTER TABLE customers ADD COLUMN IF NOT EXISTS is_admin INTEGER DEFAULT 0;

-- Add email verification fields
ALTER TABLE customers ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS email_verification_code VARCHAR(10);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS email_verification_expires TIMESTAMP;

-- Add password reset fields
ALTER TABLE customers ADD COLUMN IF NOT EXISTS password_reset_token VARCHAR(64);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS password_reset_expires TIMESTAMP;

-- Add audit field to track who created this user
ALTER TABLE customers ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES customers(id);

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_customers_username ON customers(username);
CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);
CREATE INDEX IF NOT EXISTS idx_customers_is_admin ON customers(is_admin);
CREATE INDEX IF NOT EXISTS idx_customers_email_verified ON customers(email_verified);
CREATE INDEX IF NOT EXISTS idx_customers_password_reset_token ON customers(password_reset_token);
CREATE INDEX IF NOT EXISTS idx_customers_email_verification_code ON customers(email_verification_code);

-- Verify migration
SELECT 'Migration completed successfully!' as status;
SELECT COUNT(*) as total_customers FROM customers;

-- Show table structure
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'customers'
ORDER BY ordinal_position;

COMMIT;
