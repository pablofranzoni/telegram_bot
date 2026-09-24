import os
import logging
import re
import sqlite3
from contextlib import contextmanager
from typing import Any

from database.db import DatabaseError, DatabaseInterface

logger = logging.getLogger(__name__)


class SQLiteDatabase(DatabaseInterface):
    """Clase simple para manejar conexiones SQLite en PythonAnywhere"""

    _INSERT_RETURNING_REGEX = re.compile(
        r"^\s*INSERT\s+(?:OR\s+(?:IGNORE|REPLACE|ROLLBACK|ABORT|FAIL)\s+)?INTO\s+(?P<table>[a-zA-Z_][a-zA-Z0-9_]*)\b",
        re.IGNORECASE,
    )

    def __init__(self, db_path=None):
        # En PythonAnywhere, la ruta debe ser absoluta
        if db_path is None:
            # Ruta típica en PythonAnywhere
            self.db_path = os.path.join(
                os.path.expanduser('~'), 
                'myapp/data/database.db'
            )
        else:
            self.db_path = db_path
        
        # Crear directorio si no existe
        #os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Inicializar base de datos
        #self._init_database()
        
    def _get_connection(self):
        """Obtener una nueva conexión SQLite"""
        # IMPORTANTE: En PythonAnywhere, check_same_thread=False
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=10.0
        )
        conn.row_factory = sqlite3.Row
        
        # Optimizaciones para SQLite
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        
        return conn
    
    @contextmanager
    def get_cursor(self):
        """Context manager para obtener cursor"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise DatabaseError("SQLite cursor error") from e
        finally:
            cursor.close()
            conn.close()
    
    def _should_return_inserted_id(self, query: str, fetchone: bool, fetchall: bool) -> bool:
        """Return whether an INSERT should fetch and return the generated key."""
        if fetchone or fetchall:
            return False
        if 'RETURNING' in query.upper():
            return False
        return self._INSERT_RETURNING_REGEX.match(query) is not None

    def _append_returning_id(self, query: str) -> str:
        """Append RETURNING id to INSERT statements needing the inserted key."""
        return f"{query.rstrip().rstrip(';')} RETURNING id"

    def execute(self, query, params=(), fetchone=False, fetchall=False, param_types=None) -> Any | list[Any] | int | None:
        """Ejecutar consulta simple"""
        # param_types se mantiene en la firma por compatibilidad con DatabaseInterface
        # y los adaptadores PostgreSQL/MySQL, pero SQLite no lo necesita.
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            should_return_inserted_id = self._should_return_inserted_id(query, fetchone, fetchall)
            if should_return_inserted_id:
                query = self._append_returning_id(query)

            cursor.execute(query, params)

            if should_return_inserted_id:
                row = cursor.fetchone()
                conn.commit()
                return row[0] if row else None

            conn.commit()

            if fetchone:
                return cursor.fetchone()
            elif fetchall:
                return cursor.fetchall()
            else:
                return cursor.lastrowid
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError("SQLite execute error") from e
        finally:
            cursor.close()
            conn.close()
    
    def executemany(self, query, params_list):
        """Ejecutar múltiples inserciones"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.executemany(query, params_list)
            conn.commit()
            return cursor.rowcount
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError("SQLite executemany error") from e
        finally:
            cursor.close()
            conn.close()

    def executescript(self, script: str) -> None:
        """Ejecuta un script SQL con múltiples sentencias."""
        conn = self._get_connection()
        try:
            conn.executescript(script)
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"SQLite executescript error: {e}") from e
        finally:
            conn.close()

    def commit(self):
        """No-op: SQLite already commits on every execute()."""
        pass

    def close_all_connections(self):
        # SQLite no necesita cerrar conexiones pool
        pass

# Instancia global de la base de datos
db = None

def init_db(app):
    """Inicializar base de datos para la aplicación"""
    global db
    if db is None:
        db_path = app.config.get('DATABASE_PATH')
        db = SQLiteDatabase(db_path)
    
    return db

def init_db_polling(db_path):
    """Inicializar base de datos para modo polling"""
    global db
    if db is None:
        db = SQLiteDatabase(db_path)
    
    return db

def get_db():
    """Obtener instancia de la base de datos"""
    global db
    if db is None:
        raise RuntimeError("Base de datos no inicializada")
    return db