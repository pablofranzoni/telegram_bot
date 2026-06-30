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


def admin_required(f: Callable) -> Callable:
    """
    Decorator to require admin privileges for API endpoints.
    
    MUST be used AFTER @api_token_required decorator.
    
    Validates that the authenticated user has admin privileges (is_admin = 1).
    
    Args:
        f: The endpoint function to protect
        
    Returns:
        The wrapped function with admin validation
        
    Raises:
        403 Forbidden: If user is not an admin
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            from shared.services.user_service import UserService
            
            # Get the identity from JWT (username)
            identity = get_jwt_identity()
            
            if not identity:
                logger.warning("No identity in JWT token")
                return jsonify({
                    "status": "error",
                    "message": "Invalid authentication token",
                    "error_code": "INVALID_TOKEN"
                }), 401
            
            # Get user from database
            user = UserService.get_user_by_username(identity)
            
            if not user:
                logger.warning(f"User not found: {identity}")
                return jsonify({
                    "status": "error",
                    "message": "User not found",
                    "error_code": "USER_NOT_FOUND"
                }), 404
            
            # Check if user is admin
            if user.get("is_admin") != 1:
                logger.warning(f"Non-admin user attempted privileged operation: {identity}")
                return jsonify({
                    "status": "error",
                    "message": "Admin privileges required",
                    "error_code": "ADMIN_REQUIRED"
                }), 403
            
            # Check if user is active
            if not user.get("is_active"):
                logger.warning(f"Inactive user attempted privileged operation: {identity}")
                return jsonify({
                    "status": "error",
                    "message": "User account is inactive",
                    "error_code": "USER_INACTIVE"
                }), 403
            
            # Check if email is verified
            if not user.get("email_verified"):
                logger.warning(f"Unverified user attempted operation: {identity}")
                return jsonify({
                    "status": "error",
                    "message": "Please verify your email before using this feature",
                    "error_code": "EMAIL_NOT_VERIFIED"
                }), 403
            
            logger.debug(f"Admin operation authorized for: {identity}")
            
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Error during admin validation: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "Authorization check failed",
                "error_code": "AUTH_CHECK_FAILED"
            }), 500
    
    return decorated_function

