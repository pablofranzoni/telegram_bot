---
nombre: flask-sqlalchemy-postgres-moderno
descripcion: Convenciones y patrones de diseño para usar SQLAlchemy 2.0 con PostgreSQL de forma nativa en aplicaciones Flask. Gestión correcta de sesiones por petición web (request), modelos con tipado seguro y optimizaciones para Postgres.
---

## Directrices para SQLAlchemy 2.0 + PostgreSQL en Flask

Sigue estas reglas para garantizar un tipado estricto, evitar fugas de conexiones en el pool de PostgreSQL y manejar correctamente el ciclo de vida de la base de datos dentro de Flask.

### 1. Inicialización y Ciclo de Vida de la Sesión
No utilices la extensión tradicional `Flask-SQLAlchemy` si buscas control total de SQLAlchemy 2.0. En su lugar, inicializa el `engine` globalmente y vincula la sesión al ciclo de vida de las peticiones de Flask usando `@app.teardown_appcontext`.

```python
import os
from flask import Flask, g
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, DeclarativeBase

app = Flask(__name__)

# Configuración de PostgreSQL (Usa 'postgresql+psycopg' para v3 o 'postgresql+psycopg2' para v2)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://user:password@localhost:5432/dbname")

# Configurar el Engine con un pool de conexiones optimizado para producción
engine = create_engine(
    DATABASE_URL,
    pool_size=10,          # Máximo de conexiones simultáneas persistentes
    max_overflow=20,       # Conexiones extra si se supera el pool_size
    pool_recycle=3600,     # Reciclar conexiones cada hora para evitar cortes de Postgres
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Inyectar la sesión en el contexto de Flask de forma segura
def get_db():
    if 'db' not in g:
        g.db = SessionLocal()
    return g.db

# Regla Crítica: Cerrar la sesión de Postgres al terminar cada petición HTTP
@app.teardown_appcontext
def shutdown_session(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()
```

### 2. Definición de Modelos (Estilo Moderno 2.0)
Todos los modelos deben heredar de una clase base común y definir sus columnas utilizando las anotaciones de tipo `Mapped` y `mapped_column`.

```python
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Usuario(Base):
    __tablename__ = "usuarios"
    
    # Mapped[tipo] define si el campo acepta NULL o no de forma estricta
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(120), unique=True)
    
    # Campo opcional (permite NULL en Postgres) con valor por defecto del servidor
    bio: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=text("now()")
    )
```

### 3. Operaciones y Consultas en Rutas de Flask
Usa siempre la sintaxis basada en `select()` y extrae la sesión desde el objeto `g` de Flask.

```python
from flask import jsonify, request
from sqlalchemy import select

@app.route("/usuarios", methods=["GET"])
def listar_usuarios():
    db = get_db()
    
    # Ejecutar consulta moderna de SQLAlchemy 2.0
    stmt = select(Usuario).order_by(Usuario.created_at.desc())
    usuarios = db.scalars(stmt).all()
    
    resultado = [{"id": u.id, "username": u.username} for u in usuarios]
    return jsonify(resultado), 200

@app.route("/usuarios", methods=["POST"])
def crear_usuario():
    datos = request.get_json()
    db = get_db()
    
    nuevo_usuario = Usuario(
        username=datos["username"],
        email=datos["email"],
        bio=datos.get("bio")
    )
    
    try:
        db.add(nuevo_usuario)
        db.commit()  # Confirma la transacción en PostgreSQL
        return jsonify({"mensaje": "Usuario creado", "id": nuevo_usuario.id}), 21
    except Exception as e:
        db.rollback()  # Revierte si hay error (ej: violación de unicidad)
        return jsonify({"error": "No se pudo crear el usuario"}), 400
```

### 4. Buenas Prácticas para PostgreSQL
* **Tipos de Datos Nativos**: Utiliza `sqlalchemy.dialects.postgresql` si necesitas funciones específicas de Postgres como `JSONB`, `UUID` o `ARRAY`.
* **Manejo de Transacciones**: Nunca dejes transacciones abiertas. Si una operación falla, ejecuta siempre `db.rollback()`.
* **Migraciones**: Utiliza **Alembic** para gestionar los cambios del esquema de la base de datos en lugar de ejecutar `Base.metadata.create_all(engine)` en producción.
