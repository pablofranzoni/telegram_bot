# shared/services/jwt_service.py
"""
JWT Token service for generating and managing authentication tokens.

This service handles the creation and validation of JWT tokens for API authentication.
"""

from datetime import timedelta
from typing import Optional, Dict, Any

from flask_jwt_extended import create_access_token, create_refresh_token

import logging

logger = logging.getLogger(__name__)


class JWTService:
    """Service for managing JWT tokens."""
    
    @staticmethod
    def generate_access_token(
        identity: str,
        expires_delta: Optional[timedelta] = None,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a JWT access token.
        
        Args:
            identity: The identity (user ID, email, or username) to encode in token
            expires_delta: Custom expiration time. If None, uses default from config
            additional_claims: Additional claims to include in the token
            
        Returns:
            The JWT access token string
        """
        try:
            claims = additional_claims or {}
            token = create_access_token(
                identity=identity,
                expires_delta=expires_delta,
                additional_claims=claims
            )
            logger.debug(f"Generated access token for identity: {identity}")
            return token
        except Exception as e:
            logger.error(f"Failed to generate access token: {str(e)}")
            raise
    
    @staticmethod
    def generate_refresh_token(
        identity: str,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Generate a JWT refresh token.
        
        Args:
            identity: The identity to encode in token
            expires_delta: Custom expiration time. If None, uses default from config
            
        Returns:
            The JWT refresh token string
        """
        try:
            token = create_refresh_token(
                identity=identity,
                expires_delta=expires_delta
            )
            logger.debug(f"Generated refresh token for identity: {identity}")
            return token
        except Exception as e:
            logger.error(f"Failed to generate refresh token: {str(e)}")
            raise
    
    @staticmethod
    def generate_tokens(
        identity: str,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Generate both access and refresh tokens.
        
        Args:
            identity: The identity to encode in tokens
            additional_claims: Additional claims for access token
            
        Returns:
            Dictionary containing both access_token and refresh_token
        """
        try:
            access_token = JWTService.generate_access_token(
                identity=identity,
                additional_claims=additional_claims
            )
            refresh_token = JWTService.generate_refresh_token(identity=identity)
            
            logger.info(f"Generated token pair for identity: {identity}")
            
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer"
            }
        except Exception as e:
            logger.error(f"Failed to generate tokens: {str(e)}")
            raise
