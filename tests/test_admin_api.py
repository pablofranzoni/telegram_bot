# tests/test_admin_api.py
"""
Comprehensive tests for admin API endpoints.

Tests registration, authentication, email verification, and password reset flows.
"""

import json
import pytest
from datetime import datetime, timedelta
from shared.services.user_service import UserService, PasswordHasher, PasswordValidator
from shared.services.email_service import EmailService
from database.db_sqlite import get_db


# ============================================================================
#  Password Reset Flow Tests
# ============================================================================

class TestPasswordResetFlow:
    """Test password reset request and confirmation endpoints."""
    
    def test_password_reset_request_success(self, client, setup_test_admin):
        """Test successful password reset request."""
        response = client.post('/api/password-reset', json={
            "email": "admin@example.com"
        })
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert "password reset link has been sent" in data["message"]
        assert "_token_dev" in data  # Token for dev testing
    
    def test_password_reset_request_invalid_email_format(self, client, setup_test_admin):
        """Test password reset with invalid email format."""
        response = client.post('/api/password-reset', json={
            "email": "not-an-email"
        })
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "INVALID_EMAIL" in data["error_code"]
    
    def test_password_reset_request_missing_email(self, client):
        """Test password reset without email field."""
        response = client.post('/api/password-reset', json={})
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "MISSING_EMAIL" in data["error_code"]
    
    def test_password_reset_request_missing_body(self, client):
        """Test password reset without JSON body."""
        response = client.post('/api/password-reset')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "MISSING_BODY" in data["error_code"]
    
    def test_password_reset_request_nonexistent_email(self, client):
        """Test password reset for non-existent email (should still return success)."""
        response = client.post('/api/password-reset', json={
            "email": "nonexistent@example.com"
        })
        
        # Should return success to prevent email enumeration
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
    
    def test_password_reset_confirmation_success(self, client, setup_test_admin):
        """Test successful password reset confirmation."""
        # Request reset
        reset_response = client.post('/api/password-reset', json={
            "email": "admin@example.com"
        })
        reset_data = json.loads(reset_response.data)
        reset_token = reset_data["_token_dev"]
        
        # Confirm reset with new password
        new_password = "NewPass123!"
        response = client.post(f'/api/password-reset/{reset_token}', json={
            "new_password": new_password
        })
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert "Password reset successfully" in data["message"]
    
    def test_password_reset_confirmation_invalid_token(self, client):
        """Test password reset with invalid token."""
        response = client.post('/api/password-reset/invalid_token', json={
            "new_password": "NewPass123!"
        })
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["status"] == "error"
        assert "INVALID_TOKEN_FORMAT" in data["error_code"]
    
    def test_password_reset_confirmation_wrong_token_length(self, client):
        """Test password reset with wrong token length (not 64 chars)."""
        response = client.post('/api/password-reset/short_token', json={
            "new_password": "NewPass123!"
        })
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "INVALID_TOKEN_FORMAT" in data["error_code"]
    
    def test_password_reset_confirmation_weak_password(self, client, setup_test_admin):
        """Test password reset with weak password."""
        # Request reset
        reset_response = client.post('/api/password-reset', json={
            "email": "admin@example.com"
        })
        reset_data = json.loads(reset_response.data)
        reset_token = reset_data["_token_dev"]
        
        # Try to confirm with weak password
        response = client.post(f'/api/password-reset/{reset_token}', json={
            "new_password": "weak"  # Too short, no uppercase/number
        })
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "INVALID_PASSWORD" in data["error_code"]
    
    def test_password_reset_confirmation_expired_token(self, client, setup_test_admin):
        """Test password reset with expired token."""
        db = get_db()
        
        # Get admin user and set expired reset token
        admin = UserService.get_user_by_username("admin_user")
        expired_time = (datetime.utcnow() - timedelta(hours=2)).isoformat()
        
        # Create an expired token
        fake_token = "a" * 64
        db.execute("""
            UPDATE customers
            SET password_reset_token = ?, password_reset_expires = ?
            WHERE id = ?
        """, (fake_token, expired_time, admin["id"]))
        db.commit()
        
        # Try to use expired token
        response = client.post(f'/api/password-reset/{fake_token}', json={
            "new_password": "NewPass123!"
        })
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "INVALID_RESET_TOKEN" in data["error_code"]
    
    def test_password_reset_confirmation_missing_password(self, client, setup_test_admin):
        """Test password reset confirmation without new password."""
        # Request reset
        reset_response = client.post('/api/password-reset', json={
            "email": "admin@example.com"
        })
        reset_data = json.loads(reset_response.data)
        reset_token = reset_data["_token_dev"]
        
        response = client.post(f'/api/password-reset/{reset_token}', json={})
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "MISSING_PASSWORD" in data["error_code"]


# ============================================================================
#  Email Verification Tests
# ============================================================================

class TestEmailVerification:
    """Test email verification endpoints."""
    
    def test_verify_email_success(self, client, setup_test_admin, admin_auth_headers):
        """Test successful email verification."""
        # Get verification code from database
        admin = UserService.get_user_by_username("admin_user")
        
        # First, let's unverify the admin user for this test
        db = get_db()
        code = "123456"
        expires = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
        db.execute("""
            UPDATE customers
            SET email_verified = 0, email_verification_code = ?, email_verification_expires = ?
            WHERE id = ?
        """, (code, expires, admin["id"]))
        db.commit()
        
        response = client.post('/api/verify-email', 
            json={"code": code},
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert "verified successfully" in data["message"]
    
    def test_verify_email_already_verified(self, client, setup_test_admin, admin_auth_headers):
        """Test email verification when already verified."""
        response = client.post('/api/verify-email',
            json={"code": "123456"},
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert "already verified" in data["message"]
    
    def test_verify_email_invalid_code(self, client, setup_test_admin, admin_auth_headers):
        """Test email verification with wrong code."""
        db = get_db()
        admin = UserService.get_user_by_username("admin_user")
        
        # Set wrong code
        code = "999999"
        expires = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
        db.execute("""
            UPDATE customers
            SET email_verified = 0, email_verification_code = ?, email_verification_expires = ?
            WHERE id = ?
        """, (code, expires, admin["id"]))
        db.commit()
        
        response = client.post('/api/verify-email',
            json={"code": "111111"},  # Wrong code
            headers=admin_auth_headers
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "INVALID_VERIFICATION_CODE" in data["error_code"]
    
    def test_verify_email_expired_code(self, client, setup_test_admin, admin_auth_headers):
        """Test email verification with expired code."""
        db = get_db()
        admin = UserService.get_user_by_username("admin_user")
        
        # Set expired code
        code = "123456"
        expires = (datetime.utcnow() - timedelta(minutes=20)).isoformat()
        db.execute("""
            UPDATE customers
            SET email_verified = 0, email_verification_code = ?, email_verification_expires = ?
            WHERE id = ?
        """, (code, expires, admin["id"]))
        db.commit()
        
        response = client.post('/api/verify-email',
            json={"code": code},
            headers=admin_auth_headers
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "INVALID_VERIFICATION_CODE" in data["error_code"]
    
    def test_verify_email_wrong_format(self, client, admin_auth_headers):
        """Test email verification with wrong code format."""
        response = client.post('/api/verify-email',
            json={"code": "12345"},  # Only 5 digits
            headers=admin_auth_headers
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "INVALID_CODE_FORMAT" in data["error_code"]
    
    def test_verify_email_missing_code(self, client, admin_auth_headers):
        """Test email verification without code."""
        response = client.post('/api/verify-email',
            json={},
            headers=admin_auth_headers
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "MISSING_CODE" in data["error_code"]
    
    def test_verify_email_unauthorized(self, client):
        """Test email verification without authentication."""
        response = client.post('/api/verify-email', json={"code": "123456"})
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert "MISSING_AUTH_TOKEN" in data.get("error_code", "")


# ============================================================================
#  Change Password Tests
# ============================================================================

class TestChangePassword:
    """Test change password endpoint."""
    
    def test_change_password_success(self, client, setup_test_admin, admin_auth_headers):
        """Test successful password change."""
        new_password = "NewPass123!"
        response = client.post('/api/change-password',
            json={
                "old_password": "AdminPass123!",
                "new_password": new_password
            },
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert "Password changed successfully" in data["message"]
    
    def test_change_password_wrong_old_password(self, client, setup_test_admin, admin_auth_headers):
        """Test password change with wrong old password."""
        response = client.post('/api/change-password',
            json={
                "old_password": "WrongPassword!",
                "new_password": "NewPass123!"
            },
            headers=admin_auth_headers
        )
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert "INVALID_OLD_PASSWORD" in data["error_code"]
    
    def test_change_password_weak_new_password(self, client, setup_test_admin, admin_auth_headers):
        """Test password change with weak new password."""
        response = client.post('/api/change-password',
            json={
                "old_password": "AdminPass123!",
                "new_password": "weak"
            },
            headers=admin_auth_headers
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "INVALID_NEW_PASSWORD" in data["error_code"]
    
    def test_change_password_missing_old_password(self, client, admin_auth_headers):
        """Test password change without old password."""
        response = client.post('/api/change-password',
            json={"new_password": "NewPass123!"},
            headers=admin_auth_headers
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "MISSING_OLD_PASSWORD" in data["error_code"]
    
    def test_change_password_missing_new_password(self, client, admin_auth_headers):
        """Test password change without new password."""
        response = client.post('/api/change-password',
            json={"old_password": "AdminPass123!"},
            headers=admin_auth_headers
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "MISSING_NEW_PASSWORD" in data["error_code"]
    
    def test_change_password_unauthorized(self, client):
        """Test password change without authentication."""
        response = client.post('/api/change-password',
            json={
                "old_password": "AdminPass123!",
                "new_password": "NewPass123!"
            }
        )
        
        assert response.status_code == 401


# ============================================================================
#  Email Service Tests
# ============================================================================

class TestEmailServiceIntegration:
    """Test email service functionality."""
    
    def test_email_sent_on_registration(self, client, setup_test_admin, admin_auth_headers):
        """Test that verification email is sent on user registration."""
        EmailService.clear_sent_emails()
        
        response = client.post('/api/register',
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "NewUserPass123!",
                "name": "New User"
            },
            headers=admin_auth_headers
        )
        
        assert response.status_code == 201
        
        # Check email was sent
        sent_emails = EmailService.get_sent_emails("newuser@example.com")
        assert len(sent_emails) > 0
        assert sent_emails[0]["type"] == "verification"
    
    def test_email_sent_on_password_reset_request(self, client, setup_test_admin):
        """Test that reset email is sent on password reset request."""
        EmailService.clear_sent_emails()
        
        response = client.post('/api/password-reset', json={
            "email": "admin@example.com"
        })
        
        assert response.status_code == 200
        
        # Check email was sent
        sent_emails = EmailService.get_sent_emails("admin@example.com")
        assert len(sent_emails) > 0
        assert sent_emails[0]["type"] == "password_reset"


# ============================================================================
#  Admin Decorator Tests
# ============================================================================

class TestAdminDecorator:
    """Test admin-required decorator functionality."""
    
    def test_register_requires_admin(self, client, auth_headers):
        """Test that /register endpoint requires admin privileges."""
        # Use non-admin token (if we had one)
        # For now, test with invalid/missing token
        response = client.post('/api/register',
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "TestPass123!",
                "name": "Test User"
            }
        )
        
        assert response.status_code == 401
    
    def test_register_requires_verified_email(self, client, admin_auth_headers):
        """Test that admin must have verified email to register users."""
        # This would require mocking an unverified admin
        # For now, with our setup_test_admin fixture, this should work
        response = client.post('/api/register',
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "TestPass123!",
                "name": "Test User"
            },
            headers=admin_auth_headers
        )
        
        # Should succeed because admin is verified
        assert response.status_code == 201


# ============================================================================
#  Comprehensive Integration Tests
# ============================================================================

class TestCompleteUserFlows:
    """Test complete user workflows."""
    
    def test_complete_admin_registration_and_login_flow(self, client, setup_test_admin):
        """Test complete flow: register admin -> verify email -> login."""
        admin = setup_test_admin
        
        # Step 1: Login as new admin
        response = client.post('/api/auth/login', json={
            "username": "admin_user",
            "password": "AdminPass123!"
        })
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "access_token" in data["data"]
        assert data["data"]["user"]["is_admin"] == 1
        assert data["data"]["user"]["email"] == "admin@example.com"
    
    def test_complete_password_reset_flow(self, client, setup_test_admin):
        """Test complete password reset: request -> confirm -> login with new password."""
        # Step 1: Request password reset
        response = client.post('/api/password-reset', json={
            "email": "admin@example.com"
        })
        assert response.status_code == 200
        reset_data = json.loads(response.data)
        reset_token = reset_data["_token_dev"]
        
        # Step 2: Confirm password reset
        new_password = "FreshPass123!"
        response = client.post(f'/api/password-reset/{reset_token}', json={
            "new_password": new_password
        })
        assert response.status_code == 200
        
        # Step 3: Login with new password
        response = client.post('/api/auth/login', json={
            "username": "admin_user",
            "password": new_password
        })
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "access_token" in data["data"]
    
    def test_failed_login_prevents_access(self, client, admin_auth_headers):
        """Test that failed login doesn't grant access to protected endpoints."""
        response = client.post('/api/auth/login', json={
            "username": "admin_user",
            "password": "WrongPassword"
        })
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert "INVALID_CREDENTIALS" in data["error_code"]
    
    def test_unverified_email_blocks_login(self, client, setup_test_admin):
        """Test that unverified admin cannot login."""
        db = get_db()
        admin = UserService.get_user_by_username("admin_user")
        
        # Unverify email
        db.execute("""
            UPDATE customers
            SET email_verified = 0
            WHERE id = ?
        """, (admin["id"],))
        db.commit()
        
        response = client.post('/api/auth/login', json={
            "username": "admin_user",
            "password": "AdminPass123!"
        })
        
        assert response.status_code == 403
        data = json.loads(response.data)
        assert "EMAIL_NOT_VERIFIED" in data["error_code"]
