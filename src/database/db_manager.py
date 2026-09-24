from database.db_factory import DatabaseFactory, DatabaseType

class DatabaseManager:
    """
    Singleton manager para la base de datos global
    Similar a get_db() pero con soporte para múltiples motores
    """
    _instance = None
    _db = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def init_app(self, app):
        """Inicializar desde configuración de Flask"""
        if self._db is None:
            self._db = DatabaseFactory.from_config(app.config)
        return self._db
    
    def init_db(self, db_type: DatabaseType, **kwargs):
        """Inicializar con parámetros directos"""
        if self._db is None:
            self._db = DatabaseFactory.create_database(db_type, **kwargs)
        return self._db
    
    def get_db(self):
        """Obtener instancia de base de datos"""
        if self._db is None:
            raise RuntimeError("Base de datos no inicializada")
        return self._db
    
    def close_all(self):
        """Cerrar todas las conexiones"""
        if self._db:
            self._db.close_all_connections()


# Instancia global del manager
db_manager = DatabaseManager()  # <--- ÚNICA INSTANCIA GLOBAL

def get_db():
    """Función de conveniencia para obtener la BD"""
    return db_manager.get_db()

def init_db(db_type: DatabaseType, **kwargs):
    """Función de conveniencia para inicializar"""
    return db_manager.init_db(db_type, **kwargs)

def close_db():
    """Función de conveniencia para cerrar"""
    db_manager.close_all()