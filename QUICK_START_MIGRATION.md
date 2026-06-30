# QUICK_START.md
## Quick Migration Guide

### 1️⃣ Backup Your Database

**SQLite:**
```bash
cp ./instance/pedidos_bot.db ./instance/pedidos_bot.db.backup
```

**PostgreSQL:**
```bash
pg_dump -U username database_name > backup.sql
```

### 2️⃣ Run Migration (Choose One)

#### Option A: Python Script (Recommended - Easy & Safe)

**SQLite:**
```bash
python migrations/migrate.py --database sqlite --db-path ./instance/pedidos_bot.db
```

**PostgreSQL:**
```bash
python migrations/migrate.py --database postgresql \
  --connection-string "postgresql://username:password@localhost:5432/database_name"
```

#### Option B: Direct SQL Script

**SQLite:**
```bash
sqlite3 ./instance/pedidos_bot.db < migrations/migration_sqlite.sql
```

**PostgreSQL:**
```bash
psql -U username -d database_name -f migrations/migration_postgresql.sql
```

### 3️⃣ Verify Migration

```bash
python migrations/verify_migration.py --database sqlite --db-path ./instance/pedidos_bot.db
```

### 4️⃣ Test API

```bash
# Create first admin user
curl -X POST http://localhost:5000/api/register \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "email": "admin@example.com",
    "password": "AdminPass123!",
    "name": "Administrator"
  }'

# Login
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "AdminPass123!"
  }'
```

### 5️⃣ If Something Goes Wrong

**Rollback SQLite:**
```bash
# Restore from backup
cp ./instance/pedidos_bot.db.backup ./instance/pedidos_bot.db

# Or use rollback script (complex for SQLite)
sqlite3 ./instance/pedidos_bot.db < migrations/rollback_sqlite.sql
```

**Rollback PostgreSQL:**
```bash
# Restore from backup
psql -U username -d database_name < backup.sql

# Or use rollback script
psql -U username -d database_name -f migrations/rollback_postgresql.sql
```

---

## What Gets Added

| Field | Type | Purpose |
|-------|------|---------|
| `password_hash` | TEXT | bcrypt password hash for admins |
| `is_admin` | INTEGER | 0=customer, 1=admin |
| `email_verified` | BOOLEAN | Email verification status |
| `email_verification_code` | VARCHAR | 6-digit verification code |
| `email_verification_expires` | TIMESTAMP | Code expiration (15 min) |
| `password_reset_token` | VARCHAR | Password reset token |
| `password_reset_expires` | TIMESTAMP | Token expiration (1 hour) |
| `created_by` | INTEGER FK | Who created this user (audit) |

## ⚠️ Important Notes

✅ **Safe**: Migration only ADDS columns, doesn't modify existing data
✅ **Backward Compatible**: Existing customers still work normally
✅ **Idempotent**: Safe to run multiple times
✅ **Indexed**: All new fields have indexes for performance

❌ **No Data Loss**: Backup anyway for safety
❌ **Existing Customers**: Automatically get `is_admin=0, email_verified=0`
❌ **API Users Only**: New users via `/api/register` are admins

---

For detailed information, see:
- `migrations/README.md` - Complete migration guide
- `AGENTS.md` - Project overview
- `shared/services/user_service.py` - User service implementation
