# QUICK START - Create First Admin

## 📝 Resumen Rápido

Se ha implementado un script interactivo para crear el primer administrador del API JWT.

**Script:** `create_first_admin.py`

---

## ⚡ Uso Rápido (2 minutos)

### Paso 1: Abre PowerShell/CMD
```bash
cd C:\Users\CPU\OneDrive\Documentos\python_projects\telegram_bot
```

### Paso 2: Ejecuta el script
```bash
py create_first_admin.py
```

### Paso 3: Sigue los prompts
- **Username:** `admin`
- **Email:** `admin@example.com`
- **Password:** `AdminPass123!` (debe cumplir requisitos)
- **Verification Code:** Se muestra en consola, ingresa el código

### Resultado
```
[OK] Superadmin account created successfully!
Username: admin
Email: admin@example.com
```

---

## ✅ Requisitos

- ✅ Python 3.11+ instalado
- ✅ `requirements.txt` instalado: `pip install -r requirements.txt`
- ✅ `.env` configurado con `DATABASE_URL` (PostgreSQL) O `SQLITE_PATH` (SQLite)
- ✅ BD disponible (PostgreSQL en puerto 5432 O SQLite en ruta especificada)

---

## 🔒 Requisitos de Contraseña

La contraseña debe cumplir:
- ✅ Mínimo 8 caracteres
- ✅ Al menos una letra mayúscula (A-Z)
- ✅ Al menos una letra minúscula (a-z)
- ✅ Al menos un número (0-9)
- ✅ Opcionalmente un símbolo (!@#$%)

**Ejemplo válido:** `AdminPass123!`

---

## 📧 Email de Verificación

**En modo desarrollo (mock):**
- Email NO se envía realmente
- Código se muestra en la consola
- Copias el código y lo ingresas cuando se pide

**Ejemplo:**
```
════════════════════════════════════════════════════
 VERIFICATION CODE
════════════════════════════════════════════════════
Email: admin@example.com
════════════════════════════════════════════════════

Verification Code:

    123456

Expires in: 15 minutes
════════════════════════════════════════════════════

Enter verification code: 123456  ← Ingresas aquí
```

---

## 🚨 Errores Comunes

### ❌ Error: "Base de datos no inicializada"
```
[ERROR] Cannot proceed without database connection
```
**Solución:** 
- Verifica que `DATABASE_URL` en `.env` sea correcto
- O que `SQLITE_PATH` apunte a BD válida
- Asegúrate de que PostgreSQL está corriendo en puerto 5432

---

### ❌ Error: "An admin user already exists"
```
[ERROR] An admin user already exists in the database
```
**Solución:** 
- Ya hay un admin. Para crear más, usa el endpoint `/api/register`
- Si necesitas recrear, borra el admin de la BD manualmente:
  ```sql
  DELETE FROM customers WHERE is_admin = 1;
  ```

---

### ❌ Error: "Invalid password"
```
[ERROR] Password must contain uppercase, lowercase, number
```
**Solución:** 
- Tu contraseña no cumple los requisitos
- Intenta: `AdminPass123!`

---

### ❌ Error: "This username is already taken"
```
[ERROR] This username is already taken
```
**Solución:** 
- El usuario ya existe
- Usa otro username

---

## 🎯 Próximos Pasos

Una vez creado el admin:

### 1. Prueba Login (POST)
```bash
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "AdminPass123!"}'
```

**Respuesta esperada:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "Bearer"
}
```

### 2. Crea más admins (POST con JWT)
```bash
curl -X POST http://localhost:5000/api/register \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN_AQUI>" \
  -d {
    "username": "admin2",
    "email": "admin2@example.com",
    "password": "Admin2Pass123!"
  }
```

### 3. Accede a endpoints admin-only
Todos los endpoints que requieren `@admin_required` ahora funcionan con tu JWT

---

## 📚 Documentación Completa

Para más detalles, ver:
- `FINAL_IMPLEMENTATION_SUMMARY.md` - Documentación completa
- `EMAIL_SERVICE_IMPLEMENTATION.md` - Sistema de email
- `shared/services/user_service.py` - Lógica de usuarios

---

## 💡 Tips

1. **Guarda el username y contraseña** en lugar seguro
2. **El código de verificación expira en 15 minutos** - úsalo rápido
3. **En producción**, configura SMTP real para enviar emails
4. **Para resetear todo**, borra la fila de admin de la BD:
   ```sql
   DELETE FROM customers WHERE username = 'admin';
   ```

---

## ❓ Preguntas?

Si algo no funciona:
1. Verifica que `.env` tiene `DATABASE_URL` o `SQLITE_PATH`
2. Verifica que la BD está disponible
3. Lee el error completo - tiene pistas
4. Revisa `FINAL_IMPLEMENTATION_SUMMARY.md` para debugging

---

**¡Listo! Ahora puedes ejecutar `py create_first_admin.py` y crear tu primer admin.**

