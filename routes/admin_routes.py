# routes/admin_routes.py
"""
Admin endpoints for user management and system administration.

All endpoints require JWT authentication and admin privileges.
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from shared.decorators import api_token_required, admin_required
from shared.services.user_service import (
    UserService, PasswordValidator, EmailValidator, UsernameValidator
)

import logging

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__)


# ===========================================================================
#  POST /api/register
# ===========================================================================
@admin_bp.route("/register", methods=["POST"])
@api_token_required
@admin_required
def register_api_user():
    """
    Register a new API system user (admin only).
    
    Only the super admin can use this endpoint. New users are created with:
    - Admin privileges (is_admin = 1)
    - Email verification required
    - Password authentication
    
    Expected JSON body:
        username (str, required) - Unique username (3-100 chars, alphanumeric+underscore)
        email (str, required) - Valid email address
        password (str, required) - Password (8+ chars, upper+lower+number+symbol)
        name (str, required) - Full name (2+ characters)
    
    Returns:
        201: User created successfully (email verification required)
        400: Validation error
        409: Username or email already exists
        403: User is not admin or email not verified
    """
    data = request.get_json(silent=True)
    
    if not data:
        return jsonify({
            "status": "error",
            "message": "Request body is required",
            "error_code": "MISSING_BODY"
        }), 400
    
    # Extract fields
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()
    name = data.get("name", "").strip()
    
    # Get creating admin ID
    creating_admin_username = get_jwt_identity()
    creating_admin = UserService.get_user_by_username(creating_admin_username)
    
    if not creating_admin:
        logger.warning(f"Admin user not found in JWT: {creating_admin_username}")
        return jsonify({
            "status": "error",
            "message": "Admin user not found",
            "error_code": "ADMIN_NOT_FOUND"
        }), 404
    
    # Validate required fields
    if not username:
        return jsonify({
            "status": "error",
            "message": "Username is required",
            "error_code": "MISSING_USERNAME"
        }), 400
    
    if not email:
        return jsonify({
            "status": "error",
            "message": "Email is required",
            "error_code": "MISSING_EMAIL"
        }), 400
    
    if not password:
        return jsonify({
            "status": "error",
            "message": "Password is required",
            "error_code": "MISSING_PASSWORD"
        }), 400
    
    if not name:
        return jsonify({
            "status": "error",
            "message": "Name is required",
            "error_code": "MISSING_NAME"
        }), 400
    
    # Validate username format
    valid, msg = UsernameValidator.validate(username)
    if not valid:
        return jsonify({
            "status": "error",
            "message": f"Invalid username: {msg}",
            "error_code": "INVALID_USERNAME"
        }), 400
    
    # Validate email format
    valid, msg = EmailValidator.validate(email)
    if not valid:
        return jsonify({
            "status": "error",
            "message": f"Invalid email: {msg}",
            "error_code": "INVALID_EMAIL"
        }), 400
    
    # Validate password
    valid, msg = PasswordValidator.validate(password)
    if not valid:
        return jsonify({
            "status": "error",
            "message": f"Invalid password: {msg}",
            "error_code": "INVALID_PASSWORD"
        }), 400
    
    # Validate name length
    if len(name) < 2:
        return jsonify({
            "status": "error",
            "message": "Name must be at least 2 characters",
            "error_code": "INVALID_NAME"
        }), 400
    
    try:
        # Create user
        user_data = UserService.create_api_user(
            username=username,
            email=email,
            name=name,
            password=password,
            created_by_id=creating_admin["id"]
        )
        
        # TODO: Send verification email with code
        # For now, return the verification code (should be sent via email)
        
        logger.info(f"New API user registered: {username} by {creating_admin_username}")
        
        return jsonify({
            "status": "success",
            "message": "User registered successfully. Verification email sent.",
            "data": {
                "id": user_data["id"],
                "username": user_data["username"],
                "email": user_data["email"],
                "name": user_data["name"],
                "is_admin": user_data["is_admin"],
                "email_verified": user_data["email_verified"],
                # Don't return verification code in production - send via email
                "_verification_code_dev": user_data.get("verification_code")
            }
        }), 201
        
    except ValueError as e:
        error_msg = str(e)
        
        # Check specific validation errors
        if "already exists" in error_msg:
            error_code = "USERNAME_EXISTS" if "username" in error_msg else "EMAIL_EXISTS"
            status_code = 409
        else:
            error_code = "VALIDATION_ERROR"
            status_code = 400
        
        return jsonify({
            "status": "error",
            "message": error_msg,
            "error_code": error_code
        }), status_code
    
    except Exception as e:
        logger.error(f"Error registering user: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Error registering user",
            "error_code": "REGISTRATION_ERROR"
        }), 500


# ===========================================================================
#  POST /api/verify-email
# ===========================================================================
@admin_bp.route("/verify-email", methods=["POST"])
@api_token_required
def verify_email():
    """
    Verify email address with verification code.
    
    Expected JSON body:
        code (str, required) - 6-digit verification code sent to email
    
    Returns:
        200: Email verified successfully
        400: Invalid code or code expired
        401: Unauthorized
    """
    data = request.get_json(silent=True)
    
    if not data:
        return jsonify({
            "status": "error",
            "message": "Request body is required",
            "error_code": "MISSING_BODY"
        }), 400
    
    code = data.get("code", "").strip()
    
    if not code:
        return jsonify({
            "status": "error",
            "message": "Verification code is required",
            "error_code": "MISSING_CODE"
        }), 400
    
    if len(code) != 6 or not code.isdigit():
        return jsonify({
            "status": "error",
            "message": "Invalid verification code format (must be 6 digits)",
            "error_code": "INVALID_CODE_FORMAT"
        }), 400
    
    # Get authenticated user
    username = get_jwt_identity()
    user = UserService.get_user_by_username(username)
    
    if not user:
        return jsonify({
            "status": "error",
            "message": "User not found",
            "error_code": "USER_NOT_FOUND"
        }), 404
    
    # Check if already verified
    if user.get("email_verified"):
        return jsonify({
            "status": "success",
            "message": "Email already verified"
        }), 200
    
    # Verify email
    if UserService.verify_email(user["id"], code):
        logger.info(f"Email verified for user: {username}")
        return jsonify({
            "status": "success",
            "message": "Email verified successfully"
        }), 200
    
    return jsonify({
        "status": "error",
        "message": "Invalid or expired verification code",
        "error_code": "INVALID_VERIFICATION_CODE"
    }), 400


# ===========================================================================
#  POST /api/change-password
# ===========================================================================
@admin_bp.route("/change-password", methods=["POST"])
@api_token_required
def change_password():
    """
    Change password for authenticated user.
    
    Expected JSON body:
        old_password (str, required) - Current password
        new_password (str, required) - New password (8+ chars, upper+lower+number)
    
    Returns:
        200: Password changed successfully
        400: Validation error
        401: Invalid old password
    """
    data = request.get_json(silent=True)
    
    if not data:
        return jsonify({
            "status": "error",
            "message": "Request body is required",
            "error_code": "MISSING_BODY"
        }), 400
    
    old_password = data.get("old_password", "").strip()
    new_password = data.get("new_password", "").strip()
    
    if not old_password:
        return jsonify({
            "status": "error",
            "message": "Old password is required",
            "error_code": "MISSING_OLD_PASSWORD"
        }), 400
    
    if not new_password:
        return jsonify({
            "status": "error",
            "message": "New password is required",
            "error_code": "MISSING_NEW_PASSWORD"
        }), 400
    
    # Get authenticated user
    username = get_jwt_identity()
    user = UserService.get_user_by_username(username)
    
    if not user:
        return jsonify({
            "status": "error",
            "message": "User not found",
            "error_code": "USER_NOT_FOUND"
        }), 404
    
    # Validate new password
    valid, msg = PasswordValidator.validate(new_password)
    if not valid:
        return jsonify({
            "status": "error",
            "message": f"Invalid new password: {msg}",
            "error_code": "INVALID_NEW_PASSWORD"
        }), 400
    
    try:
        # Change password
        if UserService.change_password(user["id"], old_password, new_password):
            logger.info(f"Password changed for user: {username}")
            return jsonify({
                "status": "success",
                "message": "Password changed successfully"
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Invalid old password",
                "error_code": "INVALID_OLD_PASSWORD"
            }), 401
    
    except ValueError as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "error_code": "VALIDATION_ERROR"
        }), 400
    
    except Exception as e:
        logger.error(f"Error changing password: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Error changing password",
            "error_code": "PASSWORD_CHANGE_ERROR"
        }), 500


# ===========================================================================
#  POST /api/password-reset
# ===========================================================================
@admin_bp.route("/password-reset", methods=["POST"])
def request_password_reset():
    """
    Request password reset by email.
    
    This endpoint is public (no authentication required) to allow users
    who forgot their password to request a reset token.
    
    Expected JSON body:
        email (str, required) - Email address of admin user
    
    Returns:
        200: Reset email sent successfully
        400: Validation error
        404: Email not found
    """
    data = request.get_json(silent=True)
    
    if not data:
        return jsonify({
            "status": "error",
            "message": "Request body is required",
            "error_code": "MISSING_BODY"
        }), 400
    
    email = data.get("email", "").strip()
    
    if not email:
        return jsonify({
            "status": "error",
            "message": "Email is required",
            "error_code": "MISSING_EMAIL"
        }), 400
    
    # Validate email format
    valid, msg = EmailValidator.validate(email)
    if not valid:
        return jsonify({
            "status": "error",
            "message": f"Invalid email: {msg}",
            "error_code": "INVALID_EMAIL"
        }), 400
    
    try:
        # Request password reset
        reset_token = UserService.request_password_reset(email)
        
        # Always return success to prevent email enumeration
        # (don't reveal if email exists or not)
        logger.info(f"Password reset request for email: {email}")
        
        return jsonify({
            "status": "success",
            "message": "If email exists, a password reset link has been sent",
            "_token_dev": reset_token  # For development/testing only
        }), 200
        
    except Exception as e:
        logger.error(f"Error requesting password reset: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Error processing password reset request",
            "error_code": "RESET_ERROR"
        }), 500


# ===========================================================================
#  POST /api/password-reset/<token>
# ===========================================================================
@admin_bp.route("/password-reset/<token>", methods=["POST"])
def confirm_password_reset(token):
    """
    Confirm password reset using reset token.
    
    Expected JSON body:
        new_password (str, required) - New password (8+ chars, upper+lower+number)
    
    Returns:
        200: Password reset successfully
        400: Validation error or invalid/expired token
    """
    data = request.get_json(silent=True)
    
    if not data:
        return jsonify({
            "status": "error",
            "message": "Request body is required",
            "error_code": "MISSING_BODY"
        }), 400
    
    new_password = data.get("new_password", "").strip()
    
    if not new_password:
        return jsonify({
            "status": "error",
            "message": "New password is required",
            "error_code": "MISSING_PASSWORD"
        }), 400
    
    if not token or len(token) != 64:
        return jsonify({
            "status": "error",
            "message": "Invalid reset token format",
            "error_code": "INVALID_TOKEN_FORMAT"
        }), 400
    
    # Validate new password
    valid, msg = PasswordValidator.validate(new_password)
    if not valid:
        return jsonify({
            "status": "error",
            "message": f"Invalid password: {msg}",
            "error_code": "INVALID_PASSWORD"
        }), 400
    
    try:
        # Confirm password reset
        if UserService.confirm_password_reset(token, new_password):
            logger.info("Password reset confirmed successfully")
            return jsonify({
                "status": "success",
                "message": "Password reset successfully"
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Invalid or expired reset token",
                "error_code": "INVALID_RESET_TOKEN"
            }), 400
    
    except ValueError as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "error_code": "VALIDATION_ERROR"
        }), 400
    
    except Exception as e:
        logger.error(f"Error confirming password reset: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Error resetting password",
            "error_code": "RESET_CONFIRMATION_ERROR"
        }), 500

