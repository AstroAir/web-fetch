"""
Authentication module for web_fetch.

This module provides comprehensive authentication support for various methods
including API keys, OAuth 2.0, JWT tokens, and custom authentication schemes.
Enhanced with secure credential management, retry policies, session management,
and comprehensive configuration support.
"""

from .api_key import APIKeyAuth, APIKeyConfig
from .base import AuthConfig, AuthMethod, AuthResult, AuthType, AuthLocation, AuthenticationError
from .basic import BasicAuth, BasicAuthConfig
from .bearer import BearerTokenAuth, BearerTokenConfig
from .custom import CustomAuth, CustomAuthConfig
from .jwt import JWTAuth, JWTConfig
from .manager import AuthManager
from .oauth import OAuth2Auth, OAuth2Config, OAuthTokenResponse

# Enhanced configuration system
from .config import (
    AuthenticationConfig,
    CredentialConfig,
    CredentialSource,
    EnhancedAPIKeyConfig,
    EnhancedAuthConfig,
    EnhancedBasicAuthConfig,
    EnhancedBearerTokenConfig,
    EnhancedCustomAuthConfig,
    EnhancedJWTConfig,
    EnhancedOAuth2Config,
    ProviderConfig,
    RetryPolicy,
    SecurityConfig,
    SessionConfig,
)

# Secure credential management
from .credential_store import (
    CredentialManager,
    CredentialStore,
    CredentialStoreError,
    EncryptedFileStore,
    InMemoryStore,
)

# Enhanced error handling and retry (optional)
try:
    from .retry import (
        AuthErrorType,
        AuthenticationError as EnhancedAuthenticationError,
        CircuitBreaker,
        CircuitBreakerState,
        RetryHandler,
        classify_error,
    )
    RETRY_AVAILABLE = True
except ImportError:
    RETRY_AVAILABLE = False

# Session management (optional)
try:
    from .session import (
        SessionInfo,
        SessionManager,
        SessionStore,
    )
    SESSION_AVAILABLE = True
except ImportError:
    SESSION_AVAILABLE = False

__all__ = [
    # Base classes
    "AuthMethod",
    "AuthConfig",
    "AuthResult",
    "AuthType",
    "AuthLocation",
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
    "AuthenticationError",
    # Enhanced configuration
    "AuthenticationConfig",
    "CredentialConfig",
    "CredentialSource",
    "EnhancedAPIKeyConfig",
    "EnhancedAuthConfig",
    "EnhancedBasicAuthConfig",
    "EnhancedBearerTokenConfig",
    "EnhancedCustomAuthConfig",
    "EnhancedJWTConfig",
    "EnhancedOAuth2Config",
    "ProviderConfig",
    "RetryPolicy",
    "SecurityConfig",
    "SessionConfig",
    # Credential management
    "CredentialManager",
    "CredentialStore",
    "CredentialStoreError",
    "EncryptedFileStore",
    "InMemoryStore",
]

# Conditionally add enhanced features to __all__ if available
if RETRY_AVAILABLE:
    __all__.extend([
        "AuthErrorType",
        "EnhancedAuthenticationError",
        "CircuitBreaker",
        "CircuitBreakerState",
        "RetryHandler",
        "classify_error",
    ])

if SESSION_AVAILABLE:
    __all__.extend([
        "SessionInfo",
        "SessionManager",
        "SessionStore",
    ])
