# shared/decorators.py
"""
JWT and security decorators for API endpoints.

This module provides decorators for protecting API endpoints with JWT authentication.
"""

from functools import wraps
from typing import Callable

from flask import jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from flask_jwt_extended.exceptions import JWTExtendedException

import logging

logger = logging.getLogger(__name__)


def api_token_required(f: Callable) -> Callable:
    """
    Decorator to require JWT token for API endpoints.
    
    Validates that the request contains a valid JWT token in the Authorization header.
    The token must be in the format: Authorization: Bearer <token>
    
    Args:
        f: The endpoint function to protect
        
    Returns:
        The wrapped function with JWT validation
        
    Raises:
        401 Unauthorized: If no token is provided or token is invalid
        422 Unprocessable Entity: If token format is incorrect
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Verify JWT token exists and is valid
            verify_jwt_in_request()
            
            # Get the identity (usually user ID or username)
            identity = get_jwt_identity()
            logger.debug(f"API request authenticated for identity: {identity}")
            
            return f(*args, **kwargs)
            
        except JWTExtendedException as e:
            logger.warning(f"JWT validation failed: {str(e)}")
            
            # Return appropriate error response
            if "Authorization" not in request.headers:
                return jsonify({
                    "status": "error",
                    "message": "Authorization header is missing",
                    "error_code": "MISSING_AUTH_HEADER"
                }), 401
            
            if "Bearer" not in request.headers.get("Authorization", ""):
                return jsonify({
                    "status": "error",
                    "message": "Invalid authorization header format. Use: Bearer <token>",
                    "error_code": "INVALID_AUTH_FORMAT"
                }), 422
            
            return jsonify({
                "status": "error",
                "message": "Invalid or expired token",
                "error_code": "INVALID_TOKEN"
            }), 401
            
        except Exception as e:
            logger.error(f"Unexpected error during JWT validation: {str(e)}")
            
            # Check if it's a token format error
            error_str = str(e).lower()
            if "not enough segments" in error_str or "could not deserialize" in error_str:
                return jsonify({
                    "status": "error",
                    "message": "Invalid token format",
                    "error_code": "INVALID_TOKEN_FORMAT"
                }), 401
            
            return jsonify({
                "status": "error",
                "message": "Authentication failed",
                "error_code": "AUTH_ERROR"
            }), 401
    
    return decorated_function
