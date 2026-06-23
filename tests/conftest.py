"""Shared pytest fixtures for the Telegram bot project."""

from decimal import Decimal
import os
import sys

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
