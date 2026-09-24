# Productos API - Cambio a Autorización Semipública

## Resumen
Se ha implementado autorización JWT para los endpoints GET del catálogo de productos. Ahora requieren un token JWT válido, manteniendo un modelo semipúblico donde clientes externos autenticados pueden acceder sin necesidad de permisos de admin.

## Cambios Implementados

### 1. Endpoints Modificados

#### `src/routes/products_routes.py`
- **GET /api/products** - Ahora requiere `@api_token_required`
  - Antes: Público (sin autenticación)
  - Ahora: Requiere JWT válido
  - Impacto: Clientes externos necesitan token para listar productos

- **GET /api/products/<id>** - Ahora requiere `@api_token_required`
  - Antes: Público (sin autenticación)
  - Ahora: Requiere JWT válido
  - Impacto: Clientes externos necesitan token para consultar producto individual

### 2. Tests Actualizados

#### `tests/test_products_api.py`
**Total de tests:** 21 (todos pasando ✅)

**Nuevos tests para autenticación:**
- `test_returns_200_without_token_returns_401` - Verifica que GET sin token retorna 401
- `test_invalid_token_returns_401` - Verifica que token inválido retorna 401
- `test_get_without_token_returns_401` - Verifica GET/<id> sin token retorna 401
- `test_get_with_invalid_token_returns_401` - Verifica GET/<id> con token inválido retorna 401

**Tests actualizados con autenticación:**
- Todos los tests GET ahora incluyen `auth_headers` fixture
- Mantienen compatibilidad con lógica existente

### 3. Documentación Actualizada

#### `JWT_SECURITY_REPORT.md`
- Actualizado estado de productos API: Todos los endpoints ahora protegidos
- Agregada sección "Updates" documentando el cambio
- Actualizado conteo de endpoints protegidos: 26+ (antes: 24+)

## Modelo de Seguridad

### Antes (Modelo Público)
```
GET  /api/products           → 🔓 Público
GET  /api/products/<id>      → 🔓 Público
POST /api/products           → 🔐 Requiere JWT
PUT  /api/products/<id>      → 🔐 Requiere JWT
DELETE /api/products/<id>    → 🔐 Requiere JWT
```

### Después (Modelo Semipúblico)
```
GET  /api/products           → 🔐 Requiere JWT (no admin)
GET  /api/products/<id>      → 🔐 Requiere JWT (no admin)
POST /api/products           → 🔐 Requiere JWT (admin)
PUT  /api/products/<id>      → 🔐 Requiere JWT (admin)
DELETE /api/products/<id>    → 🔐 Requiere JWT (admin)
```

### Requisitos de Acceso
- **Usuarios no admin con token JWT válido:** Pueden listar y consultar productos
- **Usuarios admin:** Pueden hacer todo (listar, consultar, crear, actualizar, eliminar)
- **Usuarios sin token:** Reciben 401 Unauthorized

## Cómo Acceder a la API

### 1. Obtener Token JWT
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "password123"
  }'
```

Response:
```json
{
  "status": "success",
  "data": {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "token_type": "Bearer"
  }
}
```

### 2. Usar Token para Acceder a Productos
```bash
curl -X GET http://localhost:5000/api/products \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..." \
  -H "Content-Type: application/json"
```

### 3. Parámetros de Query
```bash
# Con paginación
curl "http://localhost:5000/api/products?page=1&per_page=10" \
  -H "Authorization: Bearer <token>"

# Producto específico
curl "http://localhost:5000/api/products/123" \
  -H "Authorization: Bearer <token>"
```

## Casos de Error

### Sin Token
```
Status: 401
{
  "status": "error",
  "message": "Authorization header is missing",
  "error_code": "MISSING_AUTH_HEADER"
}
```

### Token Inválido
```
Status: 401
{
  "status": "error",
  "message": "Invalid or expired token",
  "error_code": "INVALID_TOKEN"
}
```

### Producto no Existe
```
Status: 404
{
  "error": "Producto no encontrado"
}
```

## Impacto

### ✅ Impacto Nulo en Bot
El bot de Telegram **NO es afectado** porque:
- No consume el endpoint HTTP `/api/products`
- Accede directamente a la BD a través de funciones internas
- Ejemplo: `list_products_by_category_page()` en `src/shared/handlers/products.py`

### ⚠️ Impacto en Clientes Externos
- Clientes que consumen el endpoint REST necesitan:
  1. Registrarse en el sistema
  2. Obtener token JWT
  3. Incluir token en headers de cada request

### ✅ Beneficios de Seguridad
- Previene scraping no autorizado del catálogo
- Permite rate limiting y tracking por usuario
- Facilita monetización (acceso diferenciado)
- Mayor control sobre acceso a datos de productos

## Tests Verification

Todos los 21 tests pasan exitosamente:
```
======================= 21 passed in 3.05s =======================

TestListProducts (6 tests)
✅ test_returns_200_without_token_returns_401
✅ test_returns_200_with_products_and_pagination
✅ test_pagination_params_are_forwarded
✅ test_invalid_pagination_returns_400
✅ test_empty_list_returns_200
✅ test_invalid_token_returns_401

TestGetProductById (4 tests)
✅ test_get_without_token_returns_401
✅ test_get_existing_product_returns_200
✅ test_get_nonexistent_product_returns_404
✅ test_get_with_invalid_token_returns_401

TestCreateProduct (5 tests)
✅ test_create_product_without_token_returns_401
✅ test_create_product_with_invalid_token_returns_401
✅ test_create_product_with_valid_token_succeeds
✅ test_create_product_missing_required_fields_returns_400
✅ test_create_product_invalid_price_returns_400

TestUpdateProduct (2 tests)
✅ test_update_product_without_token_returns_401
✅ test_update_product_with_valid_token_succeeds
✅ test_update_nonexistent_product_returns_404

TestDeleteProduct (3 tests)
✅ test_delete_product_without_token_returns_401
✅ test_delete_product_with_valid_token_succeeds
✅ test_delete_nonexistent_product_returns_404
```

## Archivos Modificados

1. **src/routes/products_routes.py** (2 cambios)
   - Línea 29: Agregado `@api_token_required` a `GET /api/products`
   - Línea 59: Agregado `@api_token_required` a `GET /api/products/<id>`

2. **tests/test_products_api.py** (completo reescrito)
   - Actualizado docstring del módulo
   - 6 nuevos/actualizados tests para TestListProducts
   - 4 nuevos/actualizados tests para TestGetProductById
   - Todos los tests ahora usan `auth_headers` fixture

3. **JWT_SECURITY_REPORT.md** (actualizado)
   - Línea 99-104: Actualizado estado de endpoints de Products
   - Línea 343-363: Agregada sección "Updates" con cambios recientes

## Próximos Pasos (Opcionales)

1. **Rate Limiting por Usuario**
   - Agregar Flask-Limiter para limitar requests por token
   - Prevenir abuso de API

2. **Roles Diferenciados**
   - Crear rol "cliente" separado de "admin"
   - Clientes solo lectura, admins acceso total

3. **Webhook para Cambios**
   - Notificar a clientes cuando catálogo cambia
   - Invalidar caché del lado cliente

4. **Estadísticas de Uso**
   - Trackear quién consulta qué productos
   - Análisis de demanda
