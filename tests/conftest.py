"""Shared pytest fixtures for the Telegram bot project."""

from decimal import Decimal
import os
import sys
import sqlite3
import tempfile
from datetime import datetime, timedelta

import pytest
from flask import Flask
from flask_jwt_extended import create_access_token

# Setup environment for testing BEFORE importing app
os.environ['JWT_SECRET_KEY'] = 'test-secret-key'
os.environ['BOT_TOKEN'] = 'test-bot-token'
os.environ['TELEGRAM_WEBHOOK_PATH_TOKEN'] = 'test-webhook-path-token'
os.environ['TELEGRAM_WEBHOOK_SECRET_TOKEN'] = 'test-webhook-secret-token'
os.environ['FLASK_ENV'] = 'testing'

# Force DB to use SQLite in-memory for tests (overrides .env pointing to PostgreSQL)
os.environ['DB_TYPE'] = 'sqlite'
os.environ['DATABASE_PATH'] = ':memory:'

# Redirect log files to a temporary directory so tests never write to ./logs
os.environ['LOG_DIR'] = tempfile.mkdtemp(prefix='telegram_bot_logs_')

TEST_INVOICE_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_API_USER = "testuser"
TEST_API_PASSWORD = "TestPass123!"
TEST_ADMIN_USER = "admin_user"
TEST_ADMIN_PASSWORD = "AdminPass123!"
TEST_ADMIN_EMAIL = "admin@example.com"


@pytest.fixture
def sample_invoice_info() -> dict[str, object]:
    """Normalized invoice payload used by checkout tests."""
    return {
        "id": TEST_INVOICE_ID,
        "total": Decimal("25.50"),
        "estado": "pendiente",
    }


@pytest.fixture
def sample_invoice_items() -> list[dict[str, object]]:
    """Sample invoice items used by checkout tests."""
    return [
        {
            "id": 5,
            "nombre": "Coca-Cola",
            "cantidad": 1,
            "precio_unitario": Decimal("2.50"),
            "subtotal": Decimal("2.50"),
        },
        {
            "id": 11,
            "nombre": "Hamburguesa Doble",
            "cantidad": 1,
            "precio_unitario": Decimal("23.00"),
            "subtotal": Decimal("23.00"),
        },
    ]


@pytest.fixture
def app() -> Flask:
    """Create a test Flask application with JWT configured and a fresh in-memory DB.

    Function scope so each test gets a clean database. The global
    ``db_manager`` singleton is reset on teardown to avoid leaking state
    between tests.
    """
    from flask import Flask
    from flask_jwt_extended import JWTManager
    from routes.auth_routes import auth_bp
    from routes.admin_routes import admin_bp
    from routes.products_routes import products_bp
    from routes.categories_routes import categories_bp
    from routes.customers_routes import customers_bp
    from routes.invoices_routes import invoices_bp
    from routes.csv_routes import csv_bp
    from database.db_manager import db_manager
    from shared.services.email_service import EmailService

    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config['TESTING'] = True
    app.config['JWT_SECRET_KEY'] = 'test-secret-key'
    app.config['JWT_ALGORITHM'] = 'HS256'
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 3600
    app.config['DB_TYPE'] = 'sqlite'
    app.config['DATABASE_PATH'] = ':memory:'

    # Reset DB singleton for a clean slate
    db_manager._db = None

    # Load schema into a long-lived in-memory connection
    schema_path = os.path.join(os.path.dirname(__file__), '..', 'pedidos_bot.sql')
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.executescript(schema_sql)
    conn.commit()
    db_manager._db = _build_persistent_db(conn)

    # Clear in-memory email storage between tests
    EmailService.clear_sent_emails()

    # Initialize JWT
    jwt = JWTManager(app)

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/api')
    app.register_blueprint(products_bp, url_prefix='/api')
    app.register_blueprint(categories_bp, url_prefix='/api')
    app.register_blueprint(customers_bp, url_prefix='/api')
    app.register_blueprint(invoices_bp, url_prefix='/api')
    app.register_blueprint(csv_bp, url_prefix='/api')

    yield app

    # Teardown: close DB connection and reset singleton
    try:
        db_manager._db.close_all_connections()
    except Exception:
        pass
    db_manager._db = None


def _build_persistent_db(conn: sqlite3.Connection):
    """Wrap a persistent :memory: connection in a duck-typed DB shim.

    The SQLiteDatabase class opens a new connection per call, which loses
    schema/data for :memory:. We expose the same surface used by services
    (execute / executemany / get_cursor / close_all_connections) on top of
    a single long-lived connection.
    """
    from database.db import DatabaseInterface
    from contextlib import contextmanager

    class _InMemoryDB(DatabaseInterface):
        def __init__(self, conn: sqlite3.Connection):
            self._conn = conn

        @contextmanager
        def get_cursor(self):
            cur = self._conn.cursor()
            try:
                yield cur
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
            finally:
                cur.close()

        def execute(self, query, params=(), fetchone=False, fetchall=False, param_types=None):
            cur = self._conn.cursor()
            try:
                cur.execute(query, params)
                self._conn.commit()
                if fetchone:
                    return cur.fetchone()
                if fetchall:
                    return cur.fetchall()
                return cur.lastrowid
            finally:
                cur.close()

        def executemany(self, query, params_list):
            cur = self._conn.cursor()
            try:
                cur.executemany(query, params_list)
                self._conn.commit()
                return cur.rowcount
            finally:
                cur.close()

        def commit(self):
            self._conn.commit()

        def rollback(self):
            self._conn.rollback()

        def close_all_connections(self):
            try:
                self._conn.close()
            except Exception:
                pass

    return _InMemoryDB(conn)


@pytest.fixture
def client(app: Flask):
    """Create a test client for the Flask application."""
    return app.test_client()


@pytest.fixture
def access_token(app: Flask) -> str:
    """Generate a valid JWT access token for testing."""
    with app.app_context():
        token = create_access_token(identity=TEST_API_USER)
    return token


@pytest.fixture
def auth_headers(access_token: str) -> dict[str, str]:
    """Create Authorization headers with JWT token."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture
def admin_access_token(app: Flask, setup_test_admin) -> str:
    """Generate a valid JWT access token for admin user (after creating admin)."""
    with app.app_context():
        token = create_access_token(identity=TEST_ADMIN_USER)
    return token


@pytest.fixture
def admin_auth_headers(admin_access_token: str) -> dict[str, str]:
    """Create Authorization headers with admin JWT token (admin auto-created)."""
    return {
        "Authorization": f"Bearer {admin_access_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture
def setup_test_user(app: Flask):
    """Create a regular (non-admin) test user used by auth API tests."""
    from shared.services.user_service import UserService

    try:
        user_data = UserService.create_api_user(
            username=TEST_API_USER,
            email="testuser@example.com",
            name="Test User",
            password=TEST_API_PASSWORD,
            created_by_id=None,
        )
        from database.db_manager import get_db
        db = get_db()
        db.execute("""
            UPDATE customers
            SET email_verified = 1, is_admin = 1
            WHERE id = ?
        """, (user_data["id"],))
        db.commit()
        return user_data
    except Exception:
        return UserService.get_user_by_username(TEST_API_USER)


@pytest.fixture
def setup_test_admin(app: Flask):
    """
    Create a test admin user in the database with email verified.
    
    Used by tests to have a verified admin to work with.
    """
    from shared.services.user_service import UserService, PasswordHasher
    from database.db_manager import get_db
    
    # Create the admin user
    try:
        user_data = UserService.create_api_user(
            username=TEST_ADMIN_USER,
            email=TEST_ADMIN_EMAIL,
            name="Test Admin",
            password=TEST_ADMIN_PASSWORD,
            created_by_id=None  # First super-admin has no creator
        )
        
        # Manually verify email (skip verification code for testing)
        db = get_db()
        db.execute("""
            UPDATE customers
            SET email_verified = 1, email_verification_code = NULL, email_verification_expires = NULL
            WHERE id = ?
        """, (user_data["id"],))
        db.commit()
        
        return user_data
    except Exception as e:
        # User might already exist, that's okay
        return UserService.get_user_by_username(TEST_ADMIN_USER)
