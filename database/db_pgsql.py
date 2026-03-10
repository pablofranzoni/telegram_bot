import os
import psycopg2
import psycopg2.pool
from psycopg2.extras import DictCursor
from contextlib import contextmanager

from database.db import DatabaseInterface

class PostgreSQLDatabase(DatabaseInterface):
    def __init__(self, db_url=None, min_conn=1, max_conn=10, **kwargs):
        if db_url is None:
            self.db_url = kwargs.get('DATABASE_URL') or os.environ.get('DATABASE_URL')
            if not self.db_url:
                # Construir desde parámetros individuales
                self.db_url = f"postgresql://{kwargs.get('DB_USER')}:{kwargs.get('DB_PASSWORD')}@{kwargs.get('DB_HOST')}:{kwargs.get('DB_PORT', 5432)}/{kwargs.get('DB_NAME')}"
        else:
            self.db_url = db_url
        
        self.connection_pool = psycopg2.pool.SimpleConnectionPool(
            min_conn,
            max_conn,
            self.db_url,
            cursor_factory=DictCursor
        )
    
    def _get_connection(self):
        return self.connection_pool.getconn()
    
    def _return_connection(self, conn):
        self.connection_pool.putconn(conn)
    
    def _adapt_query(self, query):
        """Convertir placeholders de SQLite/MySQL a PostgreSQL"""
        return query.replace('?', '%s').replace('%s', '%s')
    
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
                result = cursor.fetchone()
                return dict(result) if result else None
            elif fetchall:
                results = cursor.fetchall()
                return [dict(row) for row in results]
            else:
                return cursor.rowcount
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
        self.connection_pool.closeall()
