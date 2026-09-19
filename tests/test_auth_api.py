# tests/test_auth_api.py
"""Tests for JWT authentication endpoints."""

import pytest


class TestAuthLogin:
    """Test cases for /api/auth/login endpoint."""

    def test_login_success(self, client, setup_test_user):
        """Test successful login returns valid JWT tokens."""
        response = client.post(
            '/api/auth/login',
            json={
                'username': 'testuser',
                'password': 'TestPass123!'
            }
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        assert 'data' in data
        assert 'access_token' in data['data']
        assert 'refresh_token' in data['data']
        assert data['data']['token_type'] == 'Bearer'
    
    def test_login_missing_body(self, client):
        """Test login without JSON body returns 400."""
        response = client.post('/api/auth/login')
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'
        assert 'MISSING_BODY' in data.get('error_code', '')
    
    def test_login_missing_username(self, client):
        """Test login without username returns 400."""
        response = client.post(
            '/api/auth/login',
            json={'password': 'testpassword'}
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'
        assert 'MISSING_USERNAME' in data.get('error_code', '')
    
    def test_login_missing_password(self, client):
        """Test login without password returns 400."""
        response = client.post(
            '/api/auth/login',
            json={'username': 'testuser'}
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'
        assert 'MISSING_PASSWORD' in data.get('error_code', '')
    
    def test_login_empty_username(self, client):
        """Test login with empty username returns 400."""
        response = client.post(
            '/api/auth/login',
            json={
                'username': '   ',  # whitespace only
                'password': 'testpassword'
            }
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'
    
    def test_login_empty_password(self, client):
        """Test login with empty password returns 400."""
        response = client.post(
            '/api/auth/login',
            json={
                'username': 'testuser',
                'password': '   '  # whitespace only
            }
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'


class TestTokenGeneration:
    """Test JWT token generation and validation."""

    def test_access_token_generation(self, access_token):
        """Test that access token is generated correctly."""
        assert access_token is not None
        assert isinstance(access_token, str)
        assert len(access_token) > 0

    def test_auth_headers_format(self, auth_headers):
        """Test that auth headers are formatted correctly."""
        assert 'Authorization' in auth_headers
        assert auth_headers['Authorization'].startswith('Bearer ')
        assert 'Content-Type' in auth_headers
        assert auth_headers['Content-Type'] == 'application/json'


class TestLoginRateLimiting:
    """Test rate limiting on the login endpoint."""

    def _make_failed_login(self, client, username='testuser'):
        return client.post(
            '/api/auth/login',
            json={
                'username': username,
                'password': 'wrongpassword'
            }
        )

    def test_validation_errors_do_not_count_toward_rate_limit(self, client):
        """Missing fields return 400 and must not be recorded as failed attempts."""
        response = client.post('/api/auth/login')
        assert response.status_code == 400

        # The next request with credentials should not be rate limited.
        response = self._make_failed_login(client, username='rate_limit_validation')
        assert response.status_code == 401
        assert response.get_json()['error_code'] == 'INVALID_CREDENTIALS'

    def test_login_rate_limit_blocks_after_max_failed_attempts(self, client, monkeypatch):
        """After N failed attempts the login endpoint returns 429."""
        monkeypatch.setattr('utils.config.Config.LOGIN_RATE_LIMIT_MAX_ATTEMPTS', 2)
        monkeypatch.setattr('utils.config.Config.LOGIN_RATE_LIMIT_WINDOW_SECONDS', 300)
        monkeypatch.setattr('utils.config.Config.LOGIN_RATE_LIMIT_LOCKOUT_SECONDS', 900)

        # First two failures are allowed.
        assert self._make_failed_login(client, username='rate_limit_user').status_code == 401
        assert self._make_failed_login(client, username='rate_limit_user').status_code == 401

        # Third failure triggers rate limit.
        response = self._make_failed_login(client, username='rate_limit_user')
        assert response.status_code == 429
        data = response.get_json()
        assert data['error_code'] == 'RATE_LIMIT_EXCEEDED'
        assert 'retry_after' in data
        assert data['retry_after'] > 0

    def test_login_rate_limit_allows_after_lockout_expires(self, client, monkeypatch):
        """Once the lockout window passes, login attempts are allowed again."""
        monkeypatch.setattr('utils.config.Config.LOGIN_RATE_LIMIT_MAX_ATTEMPTS', 1)
        monkeypatch.setattr('utils.config.Config.LOGIN_RATE_LIMIT_WINDOW_SECONDS', 300)
        monkeypatch.setattr('utils.config.Config.LOGIN_RATE_LIMIT_LOCKOUT_SECONDS', 1)

        # Insert an old failed attempt whose lockout has already expired.
        from datetime import datetime, timedelta
        from database.db_manager import get_db
        old_ts = (datetime.utcnow() - timedelta(seconds=2)).strftime("%Y-%m-%d %H:%M:%S")
        get_db().execute(
            """
            INSERT INTO login_attempts (ip_address, username, attempted_at, success)
            VALUES (?, ?, ?, ?)
            """,
            ("127.0.0.1", "rate_limit_expire", old_ts, False)
        )

        # The expired record should not block a new attempt.
        response = self._make_failed_login(client, username='rate_limit_expire')
        assert response.status_code == 401

    def test_login_rate_limit_resets_on_success(self, client, setup_test_user, monkeypatch):
        """A successful login clears previous failed attempts."""
        monkeypatch.setattr('utils.config.Config.LOGIN_RATE_LIMIT_MAX_ATTEMPTS', 2)
        monkeypatch.setattr('utils.config.Config.LOGIN_RATE_LIMIT_WINDOW_SECONDS', 300)
        monkeypatch.setattr('utils.config.Config.LOGIN_RATE_LIMIT_LOCKOUT_SECONDS', 900)

        # One failed attempt.
        assert self._make_failed_login(client, username='testuser').status_code == 401

        # Successful login resets the counter.
        response = client.post(
            '/api/auth/login',
            json={
                'username': 'testuser',
                'password': 'TestPass123!'
            }
        )
        assert response.status_code == 200

        # The same IP/user should be allowed again after success.
        response = self._make_failed_login(client, username='testuser')
        assert response.status_code == 401
