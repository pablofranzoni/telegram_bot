from abc import ABC, abstractmethod
from contextlib import contextmanager

class DatabaseError(Exception):
    """Excepción base para errores de base de datos."""
    pass

class DatabaseInterface(ABC):
    """Interfaz común para todas las implementaciones de base de datos"""
    
    @abstractmethod
    @contextmanager
    def get_cursor(self):
        pass
    
    @abstractmethod
    def execute(self, query, params=(), fetchone=False, fetchall=False, param_types=None):
        pass
    
    @abstractmethod
    def executemany(self, query, params_list):
        pass

    @abstractmethod
    def executescript(self, script: str) -> None:
        """Ejecuta un script SQL con múltiples sentencias."""
        pass
    
    @abstractmethod
    def commit(self):
        """Commit any pending transaction.

        Each concrete adapter manages its own connection lifecycle; for
        adapters that already auto-commit on execute(), this can be a no-op.
        """
        pass

    @abstractmethod
    def close_all_connections(self):
        pass
