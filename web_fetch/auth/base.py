"""
Base authentication classes and interfaces.

This module defines the base classes and interfaces for all authentication
methods in the web_fetch library.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field, ConfigDict


class AuthType(str, Enum):
    """Supported authentication types."""

    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    JWT = "jwt"
    BASIC = "basic"
    BEARER = "bearer"
    CUSTOM = "custom"


class AuthLocation(str, Enum):
    """Where to place authentication credentials."""

    HEADER = "header"
    QUERY = "query"
    BODY = "body"
    COOKIE = "cookie"


@dataclass
class AuthResult:
    """Result of authentication operation."""

    success: bool
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, str] = field(default_factory=dict)
    cookies: Dict[str, str] = field(default_factory=dict)
    body_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    expires_at: Optional[float] = None

    @property
    def is_expired(self) -> bool:
        """Check if authentication has expired."""
        if self.expires_at is None:
            return False
        return time.time() >= self.expires_at


class AuthConfig(BaseModel):
    """Base configuration for authentication methods."""

    auth_type: AuthType
    enabled: bool = Field(default=True, description="Whether authentication is enabled")
    cache_credentials: bool = Field(
        default=True, description="Cache credentials for reuse"
    )
    auto_refresh: bool = Field(
        default=True, description="Automatically refresh expired credentials"
    )
    timeout: float = Field(
        default=30.0, ge=1.0, description="Authentication timeout in seconds"
    )

    model_config = ConfigDict(use_enum_values=True)


class AuthMethod(ABC):
    """
    Abstract base class for all authentication methods.

    This class defines the interface that all authentication methods must implement.
    It provides common functionality for credential management, caching, and refresh logic.
    """

    def __init__(self, config: AuthConfig):
        """
        Initialize the authentication method.

        Args:
            config: Authentication configuration
        """
        self.config = config
        self._cached_result: Optional[AuthResult] = None
        self._last_auth_time: Optional[float] = None

    @abstractmethod
    async def authenticate(self, **kwargs) -> AuthResult:
        """
        Perform authentication and return credentials.

        Args:
            **kwargs: Additional parameters for authentication

        Returns:
            AuthResult containing authentication credentials and metadata

        Raises:
            AuthenticationError: If authentication fails
        """
        pass

    @abstractmethod
    async def refresh(self) -> AuthResult:
        """
        Refresh authentication credentials.

        Returns:
            AuthResult with refreshed credentials

        Raises:
            AuthenticationError: If refresh fails
        """
        pass

    async def get_auth_data(self, force_refresh: bool = False, **kwargs) -> AuthResult:
        """
        Get authentication data, using cache if available and valid.

        Args:
            force_refresh: Force refresh even if cached credentials are valid
            **kwargs: Additional parameters for authentication

        Returns:
            AuthResult containing authentication data
        """
        if not self.config.enabled:
            return AuthResult(success=True)

        # Check if we have valid cached credentials
        if (
            not force_refresh
            and self.config.cache_credentials
            and self._cached_result
            and self._cached_result.success
            and not self._cached_result.is_expired
        ):
            return self._cached_result

        # Try to refresh if we have expired credentials and auto-refresh is enabled
        if (
            self._cached_result
            and self._cached_result.is_expired
            and self.config.auto_refresh
        ):
            try:
                result = await self.refresh()
                if result.success:
                    self._cached_result = result
                    self._last_auth_time = time.time()
                    return result
            except Exception:
                # Fall back to full authentication if refresh fails
                pass

        # Perform full authentication
        result = await self.authenticate(**kwargs)
        if result.success and self.config.cache_credentials:
            self._cached_result = result
            self._last_auth_time = time.time()

        return result

    def clear_cache(self) -> None:
        """Clear cached authentication data."""
        self._cached_result = None
        self._last_auth_time = None

    @property
    def is_authenticated(self) -> bool:
        """Check if currently authenticated with valid credentials."""
        return (
            self._cached_result is not None
            and self._cached_result.success
            and not self._cached_result.is_expired
        )

    @property
    def auth_type(self) -> AuthType:
        """Get the authentication type."""
        return self.config.auth_type
