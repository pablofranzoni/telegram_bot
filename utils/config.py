# config.py
import os

from dotenv import load_dotenv

from database.db_factory import DatabaseType

load_dotenv()


class Config:
    # Bot
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').strip().lower() in {'1', 'true', 'yes', 'on'}
    LOG_LEVEL = os.getenv('LOG_LEVEL')
    
    # ============================================
    # 🎯 SOLO CAMBIA ESTA LÍNEA PARA CAMBIAR DE BD
    # ============================================
    #DB_TYPE = DatabaseType.SQLITE  # <- Cambia aquí: SQLITE, POSTGRESQL, MYSQL
    DB_TYPE = DatabaseType.POSTGRESQL  # <- Cambia aquí: SQLITE, POSTGRESQL, MYSQL

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

    # Email / SMTP
    GMAIL_USER = os.getenv('GMAIL_USER')
    GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD')
    SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '465'))
    EMAIL_FROM_NAME = os.getenv('EMAIL_FROM_NAME', 'Telegram Bot')
    BUSINESS_NAME = os.getenv('BUSINESS_NAME', EMAIL_FROM_NAME)
    BUSINESS_EMAIL = os.getenv('BUSINESS_EMAIL', GMAIL_USER or '')
    SEND_PDF_MODE = os.getenv('SEND_PDF_MODE', 'EMAIL').upper()