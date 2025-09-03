"""
API Key authentication implementation.

This module provides API key authentication support with flexible placement
options (header, query parameter, or request body).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import Field, ConfigDict

from .base import AuthConfig, AuthLocation, AuthMethod, AuthResult, AuthType, AuthenticationError


class APIKeyConfig(AuthConfig):
    """Configuration for API key authentication."""

    auth_type: AuthType = Field(default=AuthType.API_KEY, frozen=True)
    api_key: str = Field(description="The API key value")
    key_name: str = Field(
        default="api_key", description="Name of the API key parameter"
    )
    location: AuthLocation = Field(
        default=AuthLocation.HEADER, description="Where to place the API key"
    )
    prefix: Optional[str] = Field(
        default=None, description="Optional prefix for the API key (e.g., 'Bearer')"
    )

    model_config = ConfigDict(use_enum_values=True)


class APIKeyAuth(AuthMethod):
    """
    API Key authentication method.

    Supports placing API keys in headers, query parameters, or request body.
    Can include optional prefixes for the key value.

    Example:
        ```python
        # Header authentication
        config = APIKeyConfig(
            api_key="your-api-key",
            key_name="X-API-Key",
            location=AuthLocation.HEADER
        )
        auth = APIKeyAuth(config)

        # Query parameter authentication
        config = APIKeyConfig(
            api_key="your-api-key",
            key_name="api_key",
            location=AuthLocation.QUERY
        )
        auth = APIKeyAuth(config)

        # With prefix
        config = APIKeyConfig(
            api_key="your-api-key",
            key_name="Authorization",
            location=AuthLocation.HEADER,
            prefix="Bearer"
        )
        auth = APIKeyAuth(config)
        ```
    """

    def __init__(self, config: APIKeyConfig):
        """
        Initialize API key authentication.

        Args:
            config: API key configuration
        """
        super().__init__(config)
        self.config: APIKeyConfig = config

    async def authenticate(self, **kwargs: Any) -> AuthResult:
        """
        Perform API key authentication.

        Args:
            **kwargs: Additional parameters (unused for API key auth)

        Returns:
            AuthResult containing the appropriate authentication data

        Raises:
            AuthenticationError: If API key is missing or invalid location
        """
        if not self.config.api_key:
            return AuthResult(
                success=False, error="API key is required but not provided"
            )

        try:
            # Prepare the key value with optional prefix
            key_value = self.config.api_key
            if self.config.prefix:
                key_value = f"{self.config.prefix} {key_value}"

            # Place the key according to location
            if self.config.location == AuthLocation.HEADER:
                result = AuthResult(
                    success=True, headers={self.config.key_name: key_value}
                )
            elif self.config.location == AuthLocation.QUERY:
                result = AuthResult(
                    success=True, params={self.config.key_name: key_value}
                )
            elif self.config.location == AuthLocation.BODY:
                result = AuthResult(
                    success=True, body_data={self.config.key_name: key_value}
                )
            else:
                return AuthResult(
                    success=False,
                    error=f"Unsupported API key location: {self.config.location}",
                )

            return result

        except Exception as e:
            raise AuthenticationError(f"API key authentication failed: {str(e)}")

    async def refresh(self) -> AuthResult:
        """
        Refresh API key authentication.

        For API keys, this is the same as authenticate since keys don't expire
        unless explicitly rotated externally.

        Returns:
            AuthResult with API key authentication data
        """
        return await self.authenticate()

    def validate_config(self) -> bool:
        """
        Validate the API key configuration.

        Returns:
            True if configuration is valid, False otherwise
        """
        if not self.config.api_key or not self.config.api_key.strip():
            return False

        if not self.config.key_name or not self.config.key_name.strip():
            return False

        valid_locations = [AuthLocation.HEADER, AuthLocation.QUERY, AuthLocation.BODY]
        if self.config.location not in valid_locations:
            return False

        return True
