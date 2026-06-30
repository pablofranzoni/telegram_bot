# Database Migrations - Admin Authentication

Este directorio contiene los scripts SQL necesarios para migrar la base de datos existente y agregar soporte para autenticación JWT con administradores.

## 📋 Cambios en el Esquema

Los siguientes campos se agregan a la tabla `customers`:

### Campos de Contraseña
- `password_hash (TEXT/VARCHAR)` - Hash bcrypt de la contraseña (solo para usuarios API)
- `created_at` - Timestamp de creación (ya existe)
- `updated_at` - Timestamp de última actualización (ya existe)

### Campos de Admin
- `is_admin (INTEGER/BOOLEAN)` - Flag para identificar administradores (0=cliente, 1=admin)
- `is_active (BOOLEAN)` - Flag de estado del usuario (ya existe)

### Campos de Verificación de Email
- `email_verified (BOOLEAN)` - Indica si el email fue verificado
- `email_verification_code (VARCHAR)` - Código de 6 dígitos para verificar email
- `email_verification_expires (TIMESTAMP)` - Expira en 15 minutos

### Campos de Reset de Contraseña
- `password_reset_token (VARCHAR)` - Token para resetear contraseña
- `password_reset_expires (TIMESTAMP)` - Expira en 1 hora

### Campo de Auditoría
- `created_by (INTEGER FK)` - Referencias al admin que creó este usuario

## ⚠️ Pre-Migración

**SIEMPRE realiza un backup de tu base de datos antes de ejecutar migraciones:**

### SQLite
```bash
cp your_database.db your_database.db.backup
```

### PostgreSQL
```bash
pg_dump -U username database_name > backup.sql
```

## 🚀 Opciones de Migración

### Opción 1: Script Python (Recomendado)

**Ventajas:**
- Manejo automático de errores
- Logging detallado
- Idempotente (seguro ejecutar múltiples veces)

#### Para SQLite:
```bash
python migrations/run_migration.py --database sqlite --db-path ./instance/pedidos_bot.db
```

#### Para PostgreSQL:
```bash
python migrations/run_migration.py --database postgresql --connection-string "postgresql://user:password@localhost:5432/dbname"
```

### Opción 2: SQL Script Manual

#### Para SQLite:
```bash
sqlite3 ./instance/pedidos_bot.db < migrations/migration_sqlite.sql
```

#### Para PostgreSQL:
```bash
psql -U username -d database_name -f migrations/migration_postgresql.sql
```

### Opción 3: Cliente Gráfico (pgAdmin, DB Browser)

1. Abre el cliente de base de datos
2. Selecciona tu base de datos
3. Abre "migrations/migration_sqlite.sql" o "migrations/migration_postgresql.sql"
4. Ejecuta el script

## ✅ Verificación Post-Migración

### SQLite
```bash
sqlite3 ./instance/pedidos_bot.db "PRAGMA table_info(customers);"
```

### PostgreSQL
```bash
psql -U username -d database_name -c "\d customers"
```

### Verificar Datos Existentes
```sql
-- No se pierden datos existentes
SELECT COUNT(*) FROM customers;

-- Los nuevos campos tendrán valores por defecto:
-- is_admin = 0 (clientes del bot)
-- email_verified = 0 (sin verificar)
-- password_hash = NULL (solo tiene valor para usuarios API)
```

## 🔄 Rollback de Migración

Si necesitas revertir los cambios:

### SQLite
**Nota:** SQLite no soporta DROP COLUMN fácilmente. Opciones:

1. Restaurar desde backup
2. Usar script SQL complejo (ver `rollback_sqlite.sql`)

### PostgreSQL
```sql
ALTER TABLE customers DROP COLUMN IF EXISTS password_hash CASCADE;
ALTER TABLE customers DROP COLUMN IF EXISTS is_admin CASCADE;
ALTER TABLE customers DROP COLUMN IF EXISTS email_verified CASCADE;
ALTER TABLE customers DROP COLUMN IF EXISTS email_verification_code CASCADE;
ALTER TABLE customers DROP COLUMN IF EXISTS email_verification_expires CASCADE;
ALTER TABLE customers DROP COLUMN IF EXISTS password_reset_token CASCADE;
ALTER TABLE customers DROP COLUMN IF EXISTS password_reset_expires CASCADE;
ALTER TABLE customers DROP COLUMN IF EXISTS created_by CASCADE;

DROP INDEX IF EXISTS idx_customers_username;
DROP INDEX IF EXISTS idx_customers_email;
DROP INDEX IF EXISTS idx_customers_is_admin;
DROP INDEX IF EXISTS idx_customers_email_verified;
DROP INDEX IF EXISTS idx_customers_password_reset_token;
DROP INDEX IF EXISTS idx_customers_email_verification_code;
```

## 📊 Índices Creados

Se crean los siguientes índices para optimizar búsquedas:

```sql
idx_customers_username              -- Búsquedas por nombre de usuario
idx_customers_email                 -- Búsquedas por email
idx_customers_is_admin              -- Filtrar administradores
idx_customers_email_verified        -- Filtrar usuarios verificados
idx_customers_password_reset_token  -- Búsquedas de reset token
idx_customers_email_verification_code -- Búsquedas de código de verificación
```

## 🔒 Consideraciones de Seguridad

1. **Datos Existentes**: Los clientes del Telegram bot tendrán automáticamente `is_admin = 0` y `email_verified = 0`

2. **Usuarios API**: Solo los nuevos usuarios creados mediante `/api/register` tendrán:
   - `is_admin = 1`
   - `password_hash` con valor (bcrypt hash)
   - `email_verified = 1` (después de verificar email)

3. **Backward Compatibility**: Los clientes existentes seguirán funcionando normalmente

4. **Auditoría**: El campo `created_by` permite rastrear quién creó cada usuario API

## 📝 Archivos de Migración

- `migration_sqlite.sql` - Script SQL puro para SQLite
- `migration_postgresql.sql` - Script SQL puro para PostgreSQL
- `run_migration.py` - Script Python para ejecutar migraciones automáticamente
- `README.md` - Este archivo

## 🐛 Troubleshooting

### Error: "column already exists"
- Significa que la migración ya fue ejecutada anteriormente
- Es seguro ejecutarla nuevamente (idempotente)

### Error: "cannot open database file" (SQLite)
- Verifica la ruta a la base de datos
- Asegúrate de tener permisos de lectura/escritura

### Error: "connection refused" (PostgreSQL)
- Verifica que PostgreSQL esté corriendo
- Verifica la cadena de conexión
- Verifica credenciales de usuario

### Pérdida de Datos
- **NO ocurre** - las migraciones solo agregan columnas, no modifica datos existentes
- Todos los clientes existentes mantienen sus datos intactos

## 📞 Ayuda

Para más información sobre los cambios, ver:
- `AGENTS.md` - Descripción del proyecto y arquitectura
- `shared/services/user_service.py` - Lógica de usuarios
- `routes/admin_routes.py` - Endpoints de administración
