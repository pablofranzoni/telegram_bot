-- ===========================================================================
-- PostgreSQL Rollback Script - Remove Admin Authentication Fields
-- ===========================================================================
-- This script removes the admin authentication fields from the customers table.
--
-- WARNING: This will remove all admin authentication data!
-- Only use this if you need to completely revert the migration.
--
-- Usage:
--   psql -U username -d database_name -f rollback_postgresql.sql
-- ===========================================================================

BEGIN;

-- Drop indexes first
DROP INDEX IF EXISTS idx_customers_username CASCADE;
DROP INDEX IF EXISTS idx_customers_email CASCADE;
DROP INDEX IF EXISTS idx_customers_is_admin CASCADE;
DROP INDEX IF EXISTS idx_customers_email_verified CASCADE;
DROP INDEX IF EXISTS idx_customers_password_reset_token CASCADE;
DROP INDEX IF EXISTS idx_customers_email_verification_code CASCADE;

-- Drop columns
ALTER TABLE customers DROP COLUMN IF EXISTS password_hash CASCADE;
ALTER TABLE customers DROP COLUMN IF EXISTS is_admin CASCADE;
ALTER TABLE customers DROP COLUMN IF EXISTS email_verified CASCADE;
ALTER TABLE customers DROP COLUMN IF EXISTS email_verification_code CASCADE;
ALTER TABLE customers DROP COLUMN IF EXISTS email_verification_expires CASCADE;
ALTER TABLE customers DROP COLUMN IF EXISTS password_reset_token CASCADE;
ALTER TABLE customers DROP COLUMN IF EXISTS password_reset_expires CASCADE;
ALTER TABLE customers DROP COLUMN IF EXISTS created_by CASCADE;

-- Verify rollback
SELECT 'Rollback completed successfully!' as status;
SELECT COUNT(*) as total_customers FROM customers;

-- Show table structure
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'customers'
ORDER BY ordinal_position;

COMMIT;
