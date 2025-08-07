"""
Bearer token authentication implementation.

This module provides Bearer token authentication support for APIs that use
bearer tokens in the Authorization header.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import Field

from .base import AuthConfig, AuthMethod, AuthResult, AuthType
from ..exceptions import WebFetchError


class AuthenticationError(WebFetchError):
    """Authentication-specific error."""
    pass


class BearerTokenConfig(AuthConfig):
    """Configuration for Bearer token authentication."""
    
    auth_type: AuthType = Field(default=AuthType.BEARER, frozen=True)
    token: str = Field(description="Bearer token value")
    header_name: str = Field(default="Authorization", description="Header name for the token")
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True


class BearerTokenAuth(AuthMethod):
    """
    Bearer token authentication method.
    
    Implements Bearer token authentication by adding the token to the
    Authorization header with "Bearer" prefix.
    
    Example:
        ```python
        config = BearerTokenConfig(
            token="your-bearer-token"
        )
        auth = BearerTokenAuth(config)
        ```
        
        Custom header name:
        ```python
        config = BearerTokenConfig(
            token="your-token",
            header_name="X-Auth-Token"
        )
        auth = BearerTokenAuth(config)
        ```
    """
    
    def __init__(self, config: BearerTokenConfig):
        """
        Initialize Bearer token authentication.
        
        Args:
            config: Bearer token configuration
        """
        super().__init__(config)
        self.config: BearerTokenConfig = config
    
    async def authenticate(self, **kwargs: Any) -> AuthResult:
        """
        Perform Bearer token authentication.
        
        Args:
            **kwargs: Additional parameters (unused for bearer auth)
            
        Returns:
            AuthResult containing the Authorization header
            
        Raises:
            AuthenticationError: If token is missing
        """
        if not self.config.token:
            return AuthResult(
                success=False,
                error="Bearer token is required but not provided"
            )
        
        try:
            # Create auth result with Bearer token
            result = AuthResult(
                success=True,
                headers={self.config.header_name: f"Bearer {self.config.token}"}
            )
            
            return result
            
        except Exception as e:
            raise AuthenticationError(f"Bearer token authentication failed: {str(e)}")
    
    async def refresh(self) -> AuthResult:
        """
        Refresh Bearer token authentication.
        
        For Bearer tokens, this is the same as authenticate since tokens don't expire
        unless explicitly managed externally.
        
        Returns:
            AuthResult with Bearer token header
        """
        return await self.authenticate()
