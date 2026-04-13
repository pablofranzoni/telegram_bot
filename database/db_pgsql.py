import os
import logging
import re
import psycopg2
import psycopg2.pool
from psycopg2.extras import DictCursor
from contextlib import contextmanager

from database.db import DatabaseError, DatabaseInterface

logger = logging.getLogger(__name__)

class PostgreSQLDatabase(DatabaseInterface):
    _INSERT_RETURNING_REGEX = re.compile(
        r"^\s*INSERT\s+INTO\s+(?P<table>[a-zA-Z_][a-zA-Z0-9_]*)\b",
        re.IGNORECASE,
    )

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
        adapted_query = query.replace('INSERT OR IGNORE INTO', 'INSERT INTO')
        return adapted_query.replace('?', '%s')

    def _should_return_inserted_id(self, query: str, fetchone: bool, fetchall: bool) -> bool:
        """Return whether an INSERT should fetch and return the generated primary key."""
        if fetchone or fetchall:
            return False
        if 'RETURNING' in query.upper():
            return False
        return self._INSERT_RETURNING_REGEX.match(query) is not None

    def _append_returning_id(self, query: str) -> str:
        """Append RETURNING id to INSERT statements that need sqlite/mysql-like behavior."""
        return f"{query.rstrip().rstrip(';')} RETURNING id"
    
    @contextmanager
    def get_cursor(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise DatabaseError("PostgreSQL cursor error") from e
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def execute(self, query, params=(), fetchone=False, fetchall=False, param_types=None):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            query = self._adapt_query(query)
            should_return_inserted_id = self._should_return_inserted_id(query, fetchone, fetchall)
            if should_return_inserted_id:
                query = self._append_returning_id(query)
            
            # Convertir parámetros según tipos especificados
            adapted_params = []
            for i, param in enumerate(params):
                param_type = param_types[i] if param_types and i < len(param_types) else None
                if param_type == 'boolean':
                    # Convertir 1/0 a True/False para PostgreSQL
                    if param == 1 or param == '1' or param is True:
                        adapted_params.append(True)
                    elif param == 0 or param == '0' or param is False:
                        adapted_params.append(False)
                    else:
                        adapted_params.append(param)  # Ya es boolean?
                
                elif param_type == 'text' and isinstance(param, (int, float)):
                    adapted_params.append(str(param))

                elif param_type == 'integer' and isinstance(param, str) and param.strip():
                    adapted_params.append(int(param))

                else:
                    adapted_params.append(param)
            
            cursor.execute(query, adapted_params)
            inserted_id = None

            if should_return_inserted_id:
                inserted = cursor.fetchone()
                if inserted is not None:
                    if isinstance(inserted, dict):
                        inserted_id = inserted.get('id')
                    else:
                        inserted_id = inserted[0]

            conn.commit()
            
            if fetchone:
                result = cursor.fetchone()
                return dict(result) if result else None
            elif fetchall:
                results = cursor.fetchall()
                return [dict(row) for row in results]
            elif should_return_inserted_id:
                return inserted_id
            else:
                return cursor.rowcount
        except Exception as e:
            conn.rollback()
            logger.error(
                "PostgreSQL execute error",
                extra={
                    "query_preview": query[:120],
                    "fetchone": fetchone,
                    "fetchall": fetchall,
                    "param_count": len(params),
                    "error": str(e),
                },
            )
            raise DatabaseError("PostgreSQL execute error") from e
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
            logger.error(
                "PostgreSQL executemany error",
                extra={"query_preview": query[:120], "batch_size": len(params_list), "error": str(e)},
            )
            raise DatabaseError("PostgreSQL executemany error") from e
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def close_all_connections(self):
        self.connection_pool.closeall()
