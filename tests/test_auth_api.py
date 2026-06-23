# tests/test_auth_api.py
"""Tests for JWT authentication endpoints."""

import pytest


class TestAuthLogin:
    """Test cases for /api/auth/login endpoint."""
    
    def test_login_success(self, client):
        """Test successful login returns valid JWT tokens."""
        response = client.post(
            '/api/auth/login',
            json={
                'username': 'testuser',
                'password': 'testpassword'
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
