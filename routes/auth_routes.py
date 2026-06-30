# routes/auth_routes.py
"""REST API blueprint for authentication and token management."""

from flask import Blueprint, jsonify, request
from shared.services.jwt_service import JWTService
from shared.services.user_service import UserService
import logging

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/auth/login", methods=["POST"])
def login():
    """
    Generate JWT tokens for API access.
    
    Authenticates user with username and password, returning JWT tokens if successful.
    Only API users (admin users with is_admin=1) can authenticate.
    Customers with is_admin=0 cannot use this endpoint.
    
    Expected JSON body:
        username (str, required) – API user username
        password (str, required) – API user password
    
    Returns:
        200: {
            "status": "success",
            "data": {
                "access_token": "JWT_TOKEN",
                "refresh_token": "JWT_REFRESH_TOKEN",
                "token_type": "Bearer",
                "user": {
                    "id": 1,
                    "username": "admin",
                    "email": "admin@example.com"
                }
            }
        }
        401: Authentication failed (invalid credentials)
        403: User is not admin (customers cannot use API)
    """
    data = request.get_json(silent=True)
    
    if not data:
        return jsonify({
            "status": "error",
            "message": "Request body is required",
            "error_code": "MISSING_BODY"
        }), 400
    
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    
    if not username:
        return jsonify({
            "status": "error",
            "message": "Username is required",
            "error_code": "MISSING_USERNAME"
        }), 400
    
    if not password:
        return jsonify({
            "status": "error",
            "message": "Password is required",
            "error_code": "MISSING_PASSWORD"
        }), 400
    
    try:
        # Authenticate user against database
        user = UserService.authenticate_user(username, password)
        
        if not user:
            logger.warning(f"Failed login attempt for user: {username}")
            return jsonify({
                "status": "error",
                "message": "Invalid username or password",
                "error_code": "INVALID_CREDENTIALS"
            }), 401
        
        # Check if user is admin (API users must have is_admin = 1)
        if user.get("is_admin") != 1:
            logger.warning(f"Non-admin user attempted login: {username}")
            return jsonify({
                "status": "error",
                "message": "Only API administrators can use this endpoint",
                "error_code": "NOT_AN_ADMIN"
            }), 403
        
        # Check if email is verified
        if not user.get("email_verified"):
            logger.warning(f"Unverified user attempted login: {username}")
            return jsonify({
                "status": "error",
                "message": "Please verify your email before logging in",
                "error_code": "EMAIL_NOT_VERIFIED"
            }), 403
        
        # Generate tokens
        tokens = JWTService.generate_tokens(identity=username)
        
        logger.info(f"Successful login for API user: {username}")
        
        return jsonify({
            "status": "success",
            "data": {
                **tokens,
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "email": user["email"],
                    "is_admin": user["is_admin"],
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Error during authentication",
            "error_code": "AUTH_ERROR"
        }), 500

