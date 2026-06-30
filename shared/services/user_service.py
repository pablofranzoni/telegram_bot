# shared/services/user_service.py
"""
User management service for API authentication.

Handles user registration, authentication, and password management using raw SQL.
"""

import re
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import bcrypt

from database.db_sqlite import get_db

logger = logging.getLogger(__name__)

# Validation constants
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MAX_USERNAME_LENGTH = 100
MIN_USERNAME_LENGTH = 3


class PasswordValidator:
    """Validates password against security requirements."""
    
    @staticmethod
    def validate(password: str) -> tuple[bool, str]:
        """
        Validate password meets security requirements.
        
        Requirements:
        - Minimum 8 characters
        - Must contain uppercase letter
        - Must contain lowercase letter
        - Must contain number
        - Must contain symbol or be >= 8 chars with upper+lower+number
        
        Returns:
            (is_valid, error_message)
        """
        if not password:
            return False, "Password cannot be empty"
        
        if len(password) < MIN_PASSWORD_LENGTH:
            return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
        
        if len(password) > MAX_PASSWORD_LENGTH:
            return False, f"Password cannot exceed {MAX_PASSWORD_LENGTH} characters"
        
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_symbol = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
        
        if not (has_upper and has_lower and has_digit):
            return False, "Password must contain uppercase, lowercase, and number"
        
        return True, ""


class UsernameValidator:
    """Validates username format."""
    
    @staticmethod
    def validate(username: str) -> tuple[bool, str]:
        """
        Validate username format.
        
        Requirements:
        - 3-100 characters
        - Only alphanumeric and underscores
        - Must start with letter
        
        Returns:
            (is_valid, error_message)
        """
        if not username:
            return False, "Username cannot be empty"
        
        if len(username) < MIN_USERNAME_LENGTH:
            return False, f"Username must be at least {MIN_USERNAME_LENGTH} characters"
        
        if len(username) > MAX_USERNAME_LENGTH:
            return False, f"Username cannot exceed {MAX_USERNAME_LENGTH} characters"
        
        pattern = r"^[a-zA-Z][a-zA-Z0-9_]*$"
        if not re.match(pattern, username):
            return False, "Username must start with letter and contain only letters, numbers, and underscores"
        
        return True, ""


class EmailValidator:
    """Validates email format."""
    
    @staticmethod
    def validate(email: str) -> tuple[bool, str]:
        """Validate email format."""
        if not email:
            return False, "Email cannot be empty"
        
        if len(email) > 255:
            return False, "Email cannot exceed 255 characters"
        
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, email):
            return False, "Invalid email format"
        
        return True, ""


class PasswordHasher:
    """Handles password hashing and verification."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify password against hash."""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except Exception as e:
            logger.error(f"Error verifying password: {str(e)}")
            return False


class UserService:
    """Service for user management operations."""
    
    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user by ID.
        
        Args:
            user_id: User ID
            
        Returns:
            User dict or None if not found
        """
        try:
            db = get_db()
            cursor = db.execute("""
                SELECT id, username, email, is_admin, is_active, created_at
                FROM customers
                WHERE id = ?
            """, (user_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return {
                "id": row[0],
                "username": row[1],
                "email": row[2],
                "is_admin": row[3],
                "is_active": row[4],
                "created_at": row[5],
            }
        except Exception as e:
            logger.error(f"Error fetching user by ID: {str(e)}")
            return None
    
    @staticmethod
    def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
        """
        Get user by username.
        
        Args:
            username: Username
            
        Returns:
            User dict or None if not found
        """
        try:
            db = get_db()
            cursor = db.execute("""
                SELECT id, username, email, is_admin, is_active, password_hash, created_at
                FROM customers
                WHERE username = ?
            """, (username,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return {
                "id": row[0],
                "username": row[1],
                "email": row[2],
                "is_admin": row[3],
                "is_active": row[4],
                "password_hash": row[5],
                "created_at": row[6],
            }
        except Exception as e:
            logger.error(f"Error fetching user by username: {str(e)}")
            return None
    
    @staticmethod
    def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
        """
        Get user by email.
        
        Args:
            email: Email address
            
        Returns:
            User dict or None if not found
        """
        try:
            db = get_db()
            cursor = db.execute("""
                SELECT id, username, email, is_admin, is_active, created_at
                FROM customers
                WHERE email = ?
            """, (email,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return {
                "id": row[0],
                "username": row[1],
                "email": row[2],
                "is_admin": row[3],
                "is_active": row[4],
                "created_at": row[5],
            }
        except Exception as e:
            logger.error(f"Error fetching user by email: {str(e)}")
            return None
    
    @staticmethod
    def is_admin(user_id: int) -> bool:
        """Check if user is admin."""
        try:
            db = get_db()
            cursor = db.execute("""
                SELECT is_admin FROM customers WHERE id = ?
            """, (user_id,))
            row = cursor.fetchone()
            return row and row[0] == 1
        except Exception as e:
            logger.error(f"Error checking admin status: {str(e)}")
            return False
    
    @staticmethod
    def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate user with username and password.
        
        Args:
            username: Username
            password: Password (plaintext)
            
        Returns:
            User dict if authenticated, None otherwise
        """
        if not username or not password:
            return None
        
        user = UserService.get_user_by_username(username)
        if not user:
            return None
        
        if not user.get("password_hash"):
            logger.warning(f"User {username} has no password hash set")
            return None
        
        if not PasswordHasher.verify_password(password, user["password_hash"]):
            logger.warning(f"Invalid password for user {username}")
            return None
        
        if not user.get("is_active"):
            logger.warning(f"User {username} is inactive")
            return None
        
        # Return user data without password hash
        user.pop("password_hash", None)
        return user
    
    @staticmethod
    def create_api_user(
        username: str,
        email: str,
        name: str,
        password: str,
        created_by_id: int
    ) -> Dict[str, Any]:
        """
        Create new API user (admin).
        
        Args:
            username: Username (unique)
            email: Email (unique)
            name: Full name
            password: Plaintext password (will be hashed)
            created_by_id: ID of admin creating this user
            
        Returns:
            Dict with created user data
            
        Raises:
            ValueError: If validation fails
        """
        # Validate inputs
        valid, msg = UsernameValidator.validate(username)
        if not valid:
            raise ValueError(f"Invalid username: {msg}")
        
        valid, msg = EmailValidator.validate(email)
        if not valid:
            raise ValueError(f"Invalid email: {msg}")
        
        valid, msg = PasswordValidator.validate(password)
        if not valid:
            raise ValueError(f"Invalid password: {msg}")
        
        if not name or len(name) < 2:
            raise ValueError("Name must be at least 2 characters")
        
        # Check if username exists
        if UserService.get_user_by_username(username):
            raise ValueError("Username already exists")
        
        # Check if email exists
        if UserService.get_user_by_email(email):
            raise ValueError("Email already exists")
        
        # Hash password
        password_hash = PasswordHasher.hash_password(password)
        
        # Generate verification code
        import random
        verification_code = str(random.randint(100000, 999999))
        
        try:
            db = get_db()
            cursor = db.execute("""
                INSERT INTO customers
                (customer_id, username, email, name, password_hash, is_admin, 
                 is_active, email_verified, email_verification_code,
                 email_verification_expires, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, TRUE, FALSE, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                f"api_{username}",  # customer_id for API users
                username,
                email,
                name,
                password_hash,
                verification_code,
                (datetime.utcnow() + timedelta(minutes=15)).isoformat(),
                created_by_id,
            ))
            
            db.commit()
            user_id = cursor.lastrowid
            
            logger.info(f"Created new API user: {username} (ID: {user_id})")
            
            return {
                "id": user_id,
                "username": username,
                "email": email,
                "name": name,
                "is_admin": 1,
                "email_verified": False,
                "verification_code": verification_code,  # Return for email sending
            }
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            raise ValueError(f"Error creating user: {str(e)}")
    
    @staticmethod
    def verify_email(user_id: int, verification_code: str) -> bool:
        """
        Verify user email with code.
        
        Args:
            user_id: User ID
            verification_code: 6-digit code
            
        Returns:
            True if verified successfully
        """
        try:
            db = get_db()
            cursor = db.execute("""
                SELECT email_verification_code, email_verification_expires
                FROM customers
                WHERE id = ? AND is_admin = 1
            """, (user_id,))
            row = cursor.fetchone()
            
            if not row:
                return False
            
            stored_code, expires = row
            
            # Check expiration
            if datetime.fromisoformat(expires) < datetime.utcnow():
                return False
            
            # Check code match
            if stored_code != verification_code:
                return False
            
            # Mark as verified
            db.execute("""
                UPDATE customers
                SET email_verified = 1, email_verification_code = NULL
                WHERE id = ?
            """, (user_id,))
            db.commit()
            
            logger.info(f"Email verified for user ID: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error verifying email: {str(e)}")
            return False
    
    @staticmethod
    def change_password(user_id: int, old_password: str, new_password: str) -> bool:
        """
        Change password for user.
        
        Args:
            user_id: User ID
            old_password: Current password (plaintext)
            new_password: New password (plaintext)
            
        Returns:
            True if successful
        """
        user = UserService.get_user_by_id(user_id)
        if not user:
            return False
        
        # Get full user data with hash
        db = get_db()
        cursor = db.execute("""
            SELECT password_hash FROM customers WHERE id = ?
        """, (user_id,))
        row = cursor.fetchone()
        
        if not row:
            return False
        
        # Verify old password
        if not PasswordHasher.verify_password(old_password, row[0]):
            return False
        
        # Validate new password
        valid, msg = PasswordValidator.validate(new_password)
        if not valid:
            raise ValueError(f"Invalid password: {msg}")
        
        # Hash and save new password
        new_hash = PasswordHasher.hash_password(new_password)
        db.execute("""
            UPDATE customers
            SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_hash, user_id))
        db.commit()
        
        logger.info(f"Password changed for user ID: {user_id}")
        return True
    
    @staticmethod
    def request_password_reset(email: str) -> Optional[str]:
        """
        Request password reset for user by email.
        
        Generates a secure token and stores it with 1-hour expiration.
        
        Args:
            email: User email address
            
        Returns:
            Reset token if successful, None otherwise
        """
        if not email:
            return None
        
        try:
            db = get_db()
            
            # Find user by email
            cursor = db.execute("""
                SELECT id, email, name, is_admin FROM customers WHERE email = ?
            """, (email,))
            row = cursor.fetchone()
            
            if not row:
                logger.warning(f"Password reset requested for non-existent email: {email}")
                return None
            
            user_id, user_email, user_name, is_admin = row
            
            # Only API users (admins) can reset password
            if is_admin != 1:
                logger.warning(f"Non-admin user attempted password reset: {user_id}")
                return None
            
            # Generate reset token (32 bytes = 64 hex chars)
            reset_token = secrets.token_hex(32)
            expires = datetime.utcnow() + timedelta(hours=1)
            
            # Store token
            db.execute("""
                UPDATE customers
                SET password_reset_token = ?, password_reset_expires = ?
                WHERE id = ?
            """, (reset_token, expires.isoformat(), user_id))
            db.commit()
            
            logger.info(f"Password reset token generated for user ID: {user_id}")
            
            # Send email with reset link
            from shared.services.email_service import EmailService
            EmailService.send_password_reset_email(
                email=user_email,
                token=reset_token,
                user_name=user_name
            )
            
            return reset_token
            
        except Exception as e:
            logger.error(f"Error requesting password reset: {str(e)}")
            return None
    
    @staticmethod
    def confirm_password_reset(reset_token: str, new_password: str) -> bool:
        """
        Confirm password reset using token and set new password.
        
        Args:
            reset_token: Password reset token
            new_password: New password (plaintext)
            
        Returns:
            True if successful, False otherwise
        """
        if not reset_token or not new_password:
            return False
        
        try:
            db = get_db()
            
            # Find user with valid token
            cursor = db.execute("""
                SELECT id, password_reset_expires FROM customers
                WHERE password_reset_token = ?
            """, (reset_token,))
            row = cursor.fetchone()
            
            if not row:
                logger.warning("Password reset attempted with invalid token")
                return False
            
            user_id, expires_str = row
            
            # Check token expiration (1 hour)
            if datetime.fromisoformat(expires_str) < datetime.utcnow():
                logger.warning(f"Password reset attempted with expired token for user ID: {user_id}")
                return False
            
            # Validate new password
            valid, msg = PasswordValidator.validate(new_password)
            if not valid:
                raise ValueError(f"Invalid password: {msg}")
            
            # Hash and update password, clear token
            new_hash = PasswordHasher.hash_password(new_password)
            db.execute("""
                UPDATE customers
                SET password_hash = ?, 
                    password_reset_token = NULL, 
                    password_reset_expires = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_hash, user_id))
            db.commit()
            
            logger.info(f"Password reset successful for user ID: {user_id}")
            return True
            
        except ValueError as e:
            logger.error(f"Password validation error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error confirming password reset: {str(e)}")
            return False
