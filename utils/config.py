# config.py
import os
from dotenv import load_dotenv
from database.db_factory import DatabaseType

load_dotenv()

class Config:
    # Bot
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    # ============================================
    # 🎯 SOLO CAMBIA ESTA LÍNEA PARA CAMBIAR DE BD
    # ============================================
    DB_TYPE = DatabaseType.SQLITE  # <- Cambia aquí: SQLITE, POSTGRESQL, MYSQL
    
    # SQLite
    SQLITE_PATH = os.getenv('SQLITE_PATH', './data.db')
    
    # PostgreSQL
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    # MySQL
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.getenv('MYSQL_USER')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD')
    MYSQL_DATABASE = os.getenv('MYSQL_DATABASE')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', '3306'))