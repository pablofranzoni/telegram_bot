from abc import ABC, abstractmethod
from contextlib import contextmanager

class DatabaseInterface(ABC):
    """Interfaz común para todas las implementaciones de base de datos"""
    
    @abstractmethod
    @contextmanager
    def get_cursor(self):
        pass
    
    @abstractmethod
    def execute(self, query, params=(), fetchone=False, fetchall=False):
        pass
    
    @abstractmethod
    def executemany(self, query, params_list):
        pass
    
    @abstractmethod
    def close_all_connections(self):
        pass
