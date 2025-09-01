"""
Authentication manager for coordinating multiple authentication methods.

This module provides a centralized manager for handling different authentication
methods and applying them to requests.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from ..exceptions import WebFetchError
from .api_key import APIKeyAuth, APIKeyConfig
from .base import AuthMethod, AuthResult, AuthType
from .basic import BasicAuth, BasicAuthConfig
from .bearer import BearerTokenAuth, BearerTokenConfig
from .custom import CustomAuth, CustomAuthConfig
from .jwt import JWTAuth, JWTConfig
from .oauth import OAuth2Auth, OAuth2Config


class AuthenticationError(WebFetchError):
    """Authentication-specific error."""

    pass


class AuthManager:
    """
    Authentication manager for coordinating multiple authentication methods.

    The AuthManager provides a centralized way to manage and apply different
    authentication methods to HTTP requests. It supports multiple authentication
    methods and can automatically select the appropriate method based on URL
    patterns or other criteria.

    Examples:
        Single authentication method:
        ```python
        # API key authentication
        api_config = APIKeyConfig(
            api_key="your-api-key",
            key_name="X-API-Key"
        )

        manager = AuthManager()
        manager.add_auth_method("api", APIKeyAuth(api_config))

        # Apply authentication to request
        auth_data = await manager.authenticate("api")
        ```

        Multiple authentication methods:
        ```python
        # OAuth for main API
        oauth_config = OAuth2Config(
            token_url="https://api.example.com/oauth/token",
            client_id="client-id",
            client_secret="client-secret"
        )

        # API key for legacy endpoints
        api_config = APIKeyConfig(
            api_key="legacy-key",
            key_name="api_key",
            location=AuthLocation.QUERY
        )

        manager = AuthManager()
        manager.add_auth_method("oauth", OAuth2Auth(oauth_config))
        manager.add_auth_method("legacy", APIKeyAuth(api_config))

        # Use different auth for different endpoints
        oauth_data = await manager.authenticate("oauth")
        legacy_data = await manager.authenticate("legacy")
        ```
    """

    def __init__(self) -> None:
        """Initialize the authentication manager."""
        self._auth_methods: Dict[str, AuthMethod] = {}
        self._default_method: Optional[str] = None
        self._url_patterns: Dict[str, str] = {}  # URL pattern -> auth method name

    def add_auth_method(self, name: str, auth_method: AuthMethod) -> None:
        """
        Add an authentication method.

        Args:
            name: Unique name for the authentication method
            auth_method: Authentication method instance
        """
        self._auth_methods[name] = auth_method

        # Set as default if it's the first method
        if self._default_method is None:
            self._default_method = name

    def remove_auth_method(self, name: str) -> None:
        """
        Remove an authentication method.

        Args:
            name: Name of the authentication method to remove
        """
        if name in self._auth_methods:
            del self._auth_methods[name]

            # Update default if removed method was default
            if self._default_method == name:
                self._default_method = next(iter(self._auth_methods.keys()), None)

    def set_default_method(self, name: str) -> None:
        """
        Set the default authentication method.

        Args:
            name: Name of the authentication method to use as default

        Raises:
            AuthenticationError: If the method doesn't exist
        """
        if name not in self._auth_methods:
            raise AuthenticationError(f"Authentication method '{name}' not found")

        self._default_method = name

    def add_url_pattern(self, pattern: str, auth_method_name: str) -> None:
        """
        Associate a URL pattern with an authentication method.

        Args:
            pattern: URL pattern (simple string matching for now)
            auth_method_name: Name of the authentication method

        Raises:
            AuthenticationError: If the authentication method doesn't exist
        """
        if auth_method_name not in self._auth_methods:
            raise AuthenticationError(
                f"Authentication method '{auth_method_name}' not found"
            )

        self._url_patterns[pattern] = auth_method_name

    def get_auth_method_for_url(self, url: str) -> Optional[str]:
        """
        Get the appropriate authentication method for a URL.

        Args:
            url: URL to check

        Returns:
            Authentication method name or None if no pattern matches
        """
        for pattern, method_name in self._url_patterns.items():
            if pattern in url:
                return method_name

        return self._default_method

    async def authenticate(
        self, method_name: Optional[str] = None, **kwargs: Any
    ) -> AuthResult:
        """
        Perform authentication using the specified or default method.

        Args:
            method_name: Name of the authentication method to use (uses default if None)
            **kwargs: Additional parameters for authentication

        Returns:
            AuthResult containing authentication data

        Raises:
            AuthenticationError: If authentication fails or method not found
        """
        # Use default method if none specified
        if method_name is None:
            method_name = self._default_method

        if method_name is None:
            return AuthResult(success=True)  # No authentication configured

        if method_name not in self._auth_methods:
            raise AuthenticationError(
                f"Authentication method '{method_name}' not found"
            )

        auth_method = self._auth_methods[method_name]
        return await auth_method.get_auth_data(**kwargs)

    async def authenticate_for_url(self, url: str, **kwargs: Any) -> AuthResult:
        """
        Perform authentication for a specific URL.

        Args:
            url: URL to authenticate for
            **kwargs: Additional parameters for authentication

        Returns:
            AuthResult containing authentication data
        """
        method_name = self.get_auth_method_for_url(url)
        return await self.authenticate(method_name, **kwargs)

    async def refresh(self, method_name: Optional[str] = None) -> AuthResult:
        """
        Refresh authentication for the specified or default method.

        Args:
            method_name: Name of the authentication method to refresh

        Returns:
            AuthResult with refreshed authentication data

        Raises:
            AuthenticationError: If refresh fails or method not found
        """
        if method_name is None:
            method_name = self._default_method

        if method_name is None:
            return AuthResult(success=True)

        if method_name not in self._auth_methods:
            raise AuthenticationError(
                f"Authentication method '{method_name}' not found"
            )

        auth_method = self._auth_methods[method_name]
        return await auth_method.refresh()

    def clear_cache(self, method_name: Optional[str] = None) -> None:
        """
        Clear cached authentication data.

        Args:
            method_name: Name of the method to clear cache for (clears all if None)
        """
        if method_name is None:
            # Clear cache for all methods
            for auth_method in self._auth_methods.values():
                auth_method.clear_cache()
        else:
            if method_name in self._auth_methods:
                self._auth_methods[method_name].clear_cache()

    def list_methods(self) -> List[str]:
        """
        Get list of available authentication method names.

        Returns:
            List of authentication method names
        """
        return list(self._auth_methods.keys())

    def get_method_info(self, method_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about an authentication method.

        Args:
            method_name: Name of the authentication method

        Returns:
            Dictionary with method information or None if not found
        """
        if method_name not in self._auth_methods:
            return None

        auth_method = self._auth_methods[method_name]
        return {
            "name": method_name,
            "type": auth_method.auth_type.value,
            "enabled": auth_method.config.enabled,
            "is_authenticated": auth_method.is_authenticated,
            "auto_refresh": auth_method.config.auto_refresh,
            "cache_credentials": auth_method.config.cache_credentials,
        }

    @classmethod
    def create_from_config(cls, config: Dict[str, Any]) -> "AuthManager":
        """
        Create an AuthManager from configuration dictionary.

        Args:
            config: Configuration dictionary with auth method definitions

        Returns:
            Configured AuthManager instance

        Example config:
            ```python
            config = {
                "methods": {
                    "api_key": {
                        "type": "api_key",
                        "api_key": "your-key",
                        "key_name": "X-API-Key"
                    },
                    "oauth": {
                        "type": "oauth2",
                        "token_url": "https://api.example.com/token",
                        "client_id": "client-id",
                        "client_secret": "client-secret"
                    }
                },
                "default": "api_key",
                "url_patterns": {
                    "api.example.com": "oauth",
                    "legacy.example.com": "api_key"
                }
            }
            ```
        """
        manager = cls()

        # Create authentication methods
        methods_config = config.get("methods", {})
        for name, method_config in methods_config.items():
            auth_type = method_config.get("type")

            auth_method: AuthMethod
            if auth_type == "api_key":
                auth_config = APIKeyConfig(**method_config)
                auth_method = APIKeyAuth(auth_config)
            elif auth_type == "oauth2":
                oauth_config = OAuth2Config(**method_config)
                auth_method = OAuth2Auth(oauth_config)
            elif auth_type == "jwt":
                jwt_config = JWTConfig(**method_config)
                auth_method = JWTAuth(jwt_config)
            elif auth_type == "basic":
                basic_config = BasicAuthConfig(**method_config)
                auth_method = BasicAuth(basic_config)
            elif auth_type == "bearer":
                bearer_config = BearerTokenConfig(**method_config)
                auth_method = BearerTokenAuth(bearer_config)
            elif auth_type == "custom":
                custom_config = CustomAuthConfig(**method_config)
                auth_method = CustomAuth(custom_config)
            else:
                raise AuthenticationError(
                    f"Unsupported authentication type: {auth_type}"
                )

            manager.add_auth_method(name, auth_method)

        # Set default method
        default_method = config.get("default")
        if default_method:
            manager.set_default_method(default_method)

        # Add URL patterns
        url_patterns = config.get("url_patterns", {})
        for pattern, method_name in url_patterns.items():
            manager.add_url_pattern(pattern, method_name)

        return manager
