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

    # Logging
    LOG_DIR = os.getenv('LOG_DIR', './logs')
    BOT_LOG_LEVEL = os.getenv('BOT_LOG_LEVEL', os.getenv('LOG_LEVEL', 'DEBUG')).upper()
    API_LOG_LEVEL = os.getenv('API_LOG_LEVEL', os.getenv('LOG_LEVEL', 'INFO')).upper()
    LOG_MAX_BYTES = int(os.getenv('LOG_MAX_BYTES', '10485760'))  # 10 MB
    LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', '5'))
    
    # ============================================
    # 🎯 SOLO CAMBIA ESTA LÍNEA PARA CAMBIAR DE BD
    # También se puede sobreescribir con la variable de entorno DB_TYPE.
    # ============================================
    DB_TYPE = DatabaseType.SQLITE  # <- Cambia aquí: SQLITE, POSTGRESQL, MYSQL
    #DB_TYPE = DatabaseType(os.getenv('DB_TYPE', 'postgresql').lower())

    # SQLite
    SQLITE_PATH = os.getenv('DATABASE_PATH') or os.getenv('SQLITE_PATH', './data.db')
    
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
    EMAIL_MOCK = os.getenv('EMAIL_MOCK', 'true').strip().lower() in {'1', 'true', 'yes', 'on'}

    # JWT Configuration
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
    JWT_ALGORITHM = 'HS256'
    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', '28800'))  # 8 hours in seconds (dev default)
    JWT_REFRESH_TOKEN_EXPIRES = int(os.getenv('JWT_REFRESH_TOKEN_EXPIRES', '2592000'))  # 30 days in seconds

    # Product images directory (served by the `info_<id>` callback).
    # Files are looked up as `<id>.<ext>` for each supported extension.
    PRODUCT_IMAGES_DIR = os.getenv('PRODUCT_IMAGES_DIR', './productos_images')

    # Login rate limiting
    _truthy = {'1', 'true', 'yes', 'on'}
    LOGIN_RATE_LIMIT_ENABLED = os.getenv('LOGIN_RATE_LIMIT_ENABLED', 'true').strip().lower() in _truthy
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS = int(os.getenv('LOGIN_RATE_LIMIT_MAX_ATTEMPTS', '5'))
    LOGIN_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv('LOGIN_RATE_LIMIT_WINDOW_SECONDS', '300'))
    LOGIN_RATE_LIMIT_LOCKOUT_SECONDS = int(os.getenv('LOGIN_RATE_LIMIT_LOCKOUT_SECONDS', '900'))
