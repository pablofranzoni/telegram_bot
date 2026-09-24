import logging

from enum import Enum
from typing import Dict

from database.db import DatabaseInterface
from database.db_mysql import MySQLDatabase
from database.db_pgsql import PostgreSQLDatabase
from database.db_sqlite import SQLiteDatabase

logger = logging.getLogger(__name__)

class DatabaseType(Enum):
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    # Fácilmente extensible: ORACLE = "oracle", SQLSERVER = "sqlserver", etc.


class DatabaseFactory:
    """
    Fábrica de bases de datos - Singleton
    Crea y gestiona la instancia de base de datos según configuración
    """
    _instances = {}
    
    @classmethod
    def create_database(cls, db_type: DatabaseType, **kwargs) -> DatabaseInterface:
        """
        Crear instancia de base de datos según el tipo especificado
        
        Args:
            db_type: Tipo de base de datos (SQLITE, POSTGRESQL, MYSQL)
            **kwargs: Parámetros específicos para cada implementación
            
        Returns:
            Instancia de la base de datos
        """
        key = f"{db_type.value}_{hash(frozenset(kwargs.items()))}"
        
        if key not in cls._instances:
            if db_type == DatabaseType.SQLITE:
                cls._instances[key] = SQLiteDatabase(**kwargs)
            elif db_type == DatabaseType.POSTGRESQL:
                cls._instances[key] = PostgreSQLDatabase(**kwargs)
            elif db_type == DatabaseType.MYSQL:
                cls._instances[key] = MySQLDatabase(**kwargs)
            else:
                raise ValueError(f"Tipo de base de datos no soportado: {db_type}")
            
            logger.info(f"Base de datos {db_type.value} creada exitosamente")
        
        return cls._instances[key]
    
    @classmethod
    def from_config(cls, config: Dict) -> DatabaseInterface:
        """
        Crear instancia desde un diccionario de configuración
        
        Args:
            config: Diccionario con configuración
                   Ejemplo: {
                       'DB_TYPE': 'postgresql',
                       'DATABASE_URL': 'postgresql://...',
                       'DB_POOL_MIN': 1,
                       'DB_POOL_MAX': 10
                   }
        """
        db_type = config.get('DB_TYPE', 'sqlite').lower()
        
        if db_type == 'sqlite':
            return cls.create_database(
                DatabaseType.SQLITE,
                db_path=config.get('DATABASE_PATH')
            )
        elif db_type in ['postgresql', 'postgres']:
            return cls.create_database(
                DatabaseType.POSTGRESQL,
                db_url=config.get('DATABASE_URL'),
                DB_USER=config.get('DB_USER'),
                DB_PASSWORD=config.get('DB_PASSWORD'),
                DB_HOST=config.get('DB_HOST'),
                DB_PORT=config.get('DB_PORT', 5432),
                DB_NAME=config.get('DB_NAME'),
                min_conn=config.get('DB_POOL_MIN', 1),
                max_conn=config.get('DB_POOL_MAX', 10)
            )
        elif db_type == 'mysql':
            return cls.create_database(
                DatabaseType.MYSQL,
                host=config.get('DB_HOST', 'localhost'),
                user=config.get('DB_USER'),
                password=config.get('DB_PASSWORD'),
                database=config.get('DB_NAME'),
                port=config.get('DB_PORT', 3306),
                DB_POOL_SIZE=config.get('DB_POOL_SIZE', 5)
            )
        else:
            raise ValueError(f"Tipo de base de datos no soportado en configuración: {db_type}")
