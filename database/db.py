import os
import logging
import sqlite3
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class Database:
    """Clase simple para manejar conexiones SQLite en PythonAnywhere"""
    
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
            raise e
        finally:
            cursor.close()
            conn.close()
    
    def execute(self, query, params=(), fetchone=False, fetchall=False):
        """Ejecutar consulta simple"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(query, params)
            conn.commit()
            
            if fetchone:
                return cursor.fetchone()
            elif fetchall:
                return cursor.fetchall()
            else:
                return cursor.lastrowid
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
        finally:
            cursor.close()
            conn.close()

# Instancia global de la base de datos
db = None

def init_db(app):
    """Inicializar base de datos para la aplicación"""
    global db
    if db is None:
        db_path = app.config.get('DATABASE_PATH')
        db = Database(db_path)
    
    return db

def init_db_polling(db_path):
    """Inicializar base de datos para modo polling"""
    global db
    if db is None:
        db = Database(db_path)
    
    return db

def get_db():
    """Obtener instancia de la base de datos"""
    global db
    if db is None:
        raise RuntimeError("Base de datos no inicializada")
    return db