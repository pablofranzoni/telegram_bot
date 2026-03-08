import pymysql
from pymysql.cursors import DictCursor
from contextlib import contextmanager

from database.db import DatabaseInterface

class MySQLDatabase(DatabaseInterface):
    def __init__(self, host=None, user=None, password=None, database=None, port=3306, **kwargs):
        self.host = host or kwargs.get('DB_HOST', 'localhost')
        self.user = user or kwargs.get('DB_USER')
        self.password = password or kwargs.get('DB_PASSWORD')
        self.database = database or kwargs.get('DB_NAME')
        self.port = port or kwargs.get('DB_PORT', 3306)
        self.pool_size = kwargs.get('DB_POOL_SIZE', 5)
        
        # Crear pool de conexiones (simulado)
        self.connection_pool = []
        self._init_pool()
    
    def _init_pool(self):
        """Inicializar pool de conexiones MySQL"""
        for _ in range(self.pool_size):
            conn = self._create_connection()
            self.connection_pool.append(conn)
    
    def _create_connection(self):
        """Crear una nueva conexión MySQL"""
        conn = pymysql.connect(
            host=self.host,
            user=self.user,
            password=self.password,
            database=self.database,
            port=self.port,
            cursorclass=DictCursor,
            charset='utf8mb4',
            autocommit=False
        )
        return conn
    
    def _get_connection(self):
        """Obtener conexión del pool"""
        if self.connection_pool:
            return self.connection_pool.pop()
        return self._create_connection()
    
    def _return_connection(self, conn):
        """Devolver conexión al pool"""
        if len(self.connection_pool) < self.pool_size:
            self.connection_pool.append(conn)
        else:
            conn.close()
    
    def _adapt_query(self, query):
        """Convertir placeholders a %s de MySQL"""
        return query.replace('?', '%s').replace('$1', '%s')
    
    @contextmanager
    def get_cursor(self):
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
            self._return_connection(conn)
    
    def execute(self, query, params=(), fetchone=False, fetchall=False):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            query = self._adapt_query(query)
            cursor.execute(query, params)
            conn.commit()
            
            if fetchone:
                return cursor.fetchone()
            elif fetchall:
                return cursor.fetchall()
            else:
                return cursor.lastrowid
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def executemany(self, query, params_list):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            query = self._adapt_query(query)
            cursor.executemany(query, params_list)
            conn.commit()
            return cursor.rowcount
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def close_all_connections(self):
        """Cerrar todas las conexiones"""
        for conn in self.connection_pool:
            conn.close()
        self.connection_pool.clear()