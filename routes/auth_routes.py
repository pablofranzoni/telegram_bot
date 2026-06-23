# routes/auth_routes.py
"""REST API blueprint for authentication and token management."""

from flask import Blueprint, jsonify, request
from shared.services.jwt_service import JWTService
import logging

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/auth/login", methods=["POST"])
def login():
    """
    Generate JWT tokens for API access.
    
    Expected JSON body:
        username (str, required) – API user identifier
        password (str, required) – API password (for future use)
    
    Returns:
        {
            "access_token": "JWT_TOKEN",
            "refresh_token": "JWT_REFRESH_TOKEN",
            "token_type": "Bearer"
        }
    """
    data = request.get_json(silent=True)
    
    if not data:
        return jsonify({
            "status": "error",
            "message": "Se requiere un cuerpo JSON",
            "error_code": "MISSING_BODY"
        }), 400
    
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    
    if not username:
        return jsonify({
            "status": "error",
            "message": "El campo 'username' es requerido",
            "error_code": "MISSING_USERNAME"
        }), 400
    
    if not password:
        return jsonify({
            "status": "error",
            "message": "El campo 'password' es requerido",
            "error_code": "MISSING_PASSWORD"
        }), 400
    
    # TODO: Implement actual user validation against database
    # For now, we accept any non-empty username/password
    # In production, validate credentials against user database
    
    try:
        tokens = JWTService.generate_tokens(identity=username)
        logger.info(f"Login successful for user: {username}")
        
        return jsonify({
            "status": "success",
            "data": tokens
        }), 200
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Error al generar tokens",
            "error_code": "TOKEN_GENERATION_ERROR"
        }), 500
