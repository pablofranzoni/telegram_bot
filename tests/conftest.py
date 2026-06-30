"""Shared pytest fixtures for the Telegram bot project."""

from decimal import Decimal
import os
import sys
import sqlite3
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

TEST_INVOICE_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_API_USER = "test_user"
TEST_API_PASSWORD = "test_password"
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


@pytest.fixture(scope="session")
def app() -> Flask:
    """Create a test Flask application with JWT configured."""
    from flask import Flask
    from flask_jwt_extended import JWTManager
    from routes.auth_routes import auth_bp
    from routes.admin_routes import admin_bp
    from routes.products_routes import products_bp
    from routes.categories_routes import categories_bp
    from routes.invoices_routes import invoices_bp
    from routes.csv_routes import csv_bp
    
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config['TESTING'] = True
    app.config['JWT_SECRET_KEY'] = 'test-secret-key'
    app.config['JWT_ALGORITHM'] = 'HS256'
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 3600
    
    # Initialize JWT
    jwt = JWTManager(app)
    
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/api')
    app.register_blueprint(products_bp, url_prefix='/api')
    app.register_blueprint(categories_bp, url_prefix='/api')
    app.register_blueprint(invoices_bp, url_prefix='/api')
    app.register_blueprint(csv_bp, url_prefix='/api')
    
    return app


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
def admin_access_token(app: Flask) -> str:
    """Generate a valid JWT access token for admin user."""
    with app.app_context():
        token = create_access_token(identity=TEST_ADMIN_USER)
    return token


@pytest.fixture
def admin_auth_headers(admin_access_token: str) -> dict[str, str]:
    """Create Authorization headers with admin JWT token."""
    return {
        "Authorization": f"Bearer {admin_access_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture
def setup_test_admin(app: Flask):
    """
    Create a test admin user in the database with email verified.
    
    Used by tests to have a verified admin to work with.
    """
    from shared.services.user_service import UserService, PasswordHasher
    from database.db_sqlite import get_db
    
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
