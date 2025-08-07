"""
Basic HTTP authentication implementation.

This module provides HTTP Basic authentication support with username/password
credentials encoded in Base64.
"""

from __future__ import annotations

import base64
from typing import Any

from pydantic import Field

from .base import AuthConfig, AuthMethod, AuthResult, AuthType
from ..exceptions import WebFetchError


class AuthenticationError(WebFetchError):
    """Authentication-specific error."""
    pass


class BasicAuthConfig(AuthConfig):
    """Configuration for Basic HTTP authentication."""
    
    auth_type: AuthType = Field(default=AuthType.BASIC, frozen=True)
    username: str = Field(description="Username for basic authentication")
    password: str = Field(description="Password for basic authentication")
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True


class BasicAuth(AuthMethod):
    """
    Basic HTTP authentication method.
    
    Implements HTTP Basic authentication as defined in RFC 7617.
    Encodes username and password in Base64 and sends in Authorization header.
    
    Example:
        ```python
        config = BasicAuthConfig(
            username="your-username",
            password="your-password"
        )
        auth = BasicAuth(config)
        ```
    """
    
    def __init__(self, config: BasicAuthConfig):
        """
        Initialize Basic authentication.
        
        Args:
            config: Basic authentication configuration
        """
        super().__init__(config)
        self.config: BasicAuthConfig = config
    
    async def authenticate(self, **kwargs: Any) -> AuthResult:
        """
        Perform Basic HTTP authentication.
        
        Args:
            **kwargs: Additional parameters (unused for basic auth)
            
        Returns:
            AuthResult containing the Authorization header
            
        Raises:
            AuthenticationError: If credentials are missing
        """
        if not self.config.username or not self.config.password:
            return AuthResult(
                success=False,
                error="Username and password are required for basic authentication"
            )
        
        try:
            # Encode credentials
            credentials = f"{self.config.username}:{self.config.password}"
            encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('ascii')
            
            # Create auth result
            result = AuthResult(
                success=True,
                headers={"Authorization": f"Basic {encoded_credentials}"}
            )
            
            return result
            
        except Exception as e:
            raise AuthenticationError(f"Basic authentication failed: {str(e)}")
    
    async def refresh(self) -> AuthResult:
        """
        Refresh Basic authentication.
        
        For Basic auth, this is the same as authenticate since credentials don't expire.
        
        Returns:
            AuthResult with Basic auth header
        """
        return await self.authenticate()
