"""
Authentication module for web_fetch.

This module provides comprehensive authentication support for various methods
including API keys, OAuth 2.0, JWT tokens, and custom authentication schemes.
"""

from .base import AuthMethod, AuthConfig, AuthResult
from .api_key import APIKeyAuth, APIKeyConfig
from .oauth import OAuth2Auth, OAuth2Config, OAuthTokenResponse
from .jwt import JWTAuth, JWTConfig
from .basic import BasicAuth, BasicAuthConfig
from .bearer import BearerTokenAuth, BearerTokenConfig
from .custom import CustomAuth, CustomAuthConfig
from .manager import AuthManager

__all__ = [
    # Base classes
    "AuthMethod",
    "AuthConfig", 
    "AuthResult",
    
    # API Key authentication
    "APIKeyAuth",
    "APIKeyConfig",
    
    # OAuth 2.0 authentication
    "OAuth2Auth",
    "OAuth2Config",
    "OAuthTokenResponse",
    
    # JWT authentication
    "JWTAuth",
    "JWTConfig",
    
    # Basic authentication
    "BasicAuth",
    "BasicAuthConfig",
    
    # Bearer token authentication
    "BearerTokenAuth",
    "BearerTokenConfig",
    
    # Custom authentication
    "CustomAuth",
    "CustomAuthConfig",
    
    # Authentication manager
    "AuthManager",
]
