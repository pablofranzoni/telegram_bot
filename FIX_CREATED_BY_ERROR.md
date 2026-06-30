# CORRECCIÓN - Error de Tipo INTEGER en created_by

## ❌ Error Recibido

```
psycopg2.errors.InvalidTextRepresentation: invalid input syntax for type integer: "system"
LINE 5: ..., '2026-06-27T03:53:29.853630', 'system'
                                            ^
```

## 🔍 Causa Raíz

El campo `created_by` en PostgreSQL es de tipo `INTEGER` (referencia a `customers.id`):

```sql
created_by INTEGER REFERENCES customers(id),   -- Espera INTEGER
```

Pero en el script se estaba enviando la string `'system'`, que PostgreSQL no puede convertir a INTEGER.

## ✅ Solución Implementada

Cambiar `'system'` a `None` (que se traduce a SQL `NULL`):

### Antes:
```python
(
    customer_id,
    username,
    email,
    username,
    password_hash,
    1,
    False,
    verification_code,
    expires_at.isoformat(),
    'system'               # ❌ String, no INTEGER
)
```

### Después:
```python
(
    customer_id,
    username,
    email,
    username,
    password_hash,
    1,
    False,
    verification_code,
    expires_at.isoformat(),
    None                   # ✅ NULL (primer admin, sin creador)
)
```

## 📝 Explicación

- **Para el primer admin:** No existe un usuario anterior que lo creó, por eso `created_by = NULL`
- **Para admins posteriores:** Se crea desde `/api/register` y `created_by` se establece con el ID del admin que lo registró
- **NULL en PostgreSQL:** Indica "sin valor" o "no aplicable"

## 🔧 Archivo Modificado

- `create_first_admin.py` - Línea 340: `'system'` → `None`

## ✨ Próximo Paso

Ejecuta el script nuevamente:

```bash
py create_first_admin.py
```

**Ahora debería funcionar sin errores de tipo de datos.**

