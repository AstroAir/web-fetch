"""
Custom authentication implementation.

This module provides a flexible custom authentication method that allows
users to implement their own authentication logic.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from pydantic import Field, ConfigDict

from ..exceptions import WebFetchError
from .base import AuthConfig, AuthMethod, AuthResult, AuthType


class AuthenticationError(WebFetchError):
    """Authentication-specific error."""

    pass


class CustomAuthConfig(AuthConfig):
    """Configuration for custom authentication."""

    auth_type: AuthType = Field(default=AuthType.CUSTOM, frozen=True)

    # Custom authentication parameters
    auth_params: Dict[str, Any] = Field(
        default_factory=dict, description="Custom authentication parameters"
    )

    model_config = ConfigDict(use_enum_values=True)


class CustomAuth(AuthMethod):
    """
    Custom authentication method.

    Provides a flexible framework for implementing custom authentication logic.
    Users can provide their own authentication and refresh functions.

    Example:
        ```python
        async def my_auth_func(auth_params, **kwargs):
            # Custom authentication logic
            api_key = auth_params.get('api_key')
            signature = generate_signature(api_key, kwargs.get('timestamp'))
            return AuthResult(
                success=True,
                headers={
                    'X-API-Key': api_key,
                    'X-Signature': signature
                }
            )

        async def my_refresh_func(auth_params, **kwargs):
            # Custom refresh logic
            return await my_auth_func(auth_params, **kwargs)

        config = CustomAuthConfig(
            auth_params={'api_key': 'your-key'}
        )
        auth = CustomAuth(config)
        auth.set_auth_function(my_auth_func)
        auth.set_refresh_function(my_refresh_func)
        ```
    """

    def __init__(self, config: CustomAuthConfig):
        """
        Initialize custom authentication.

        Args:
            config: Custom authentication configuration
        """
        super().__init__(config)
        self.config: CustomAuthConfig = config
        self._auth_function: Optional[Callable] = None
        self._refresh_function: Optional[Callable] = None

    def set_auth_function(self, func: Callable[..., AuthResult]) -> None:
        """
        Set the custom authentication function.

        Args:
            func: Async function that takes auth_params and kwargs, returns AuthResult
        """
        self._auth_function = func

    def set_refresh_function(self, func: Callable[..., AuthResult]) -> None:
        """
        Set the custom refresh function.

        Args:
            func: Async function that takes auth_params and kwargs, returns AuthResult
        """
        self._refresh_function = func

    async def authenticate(self, **kwargs: Any) -> AuthResult:
        """
        Perform custom authentication.

        Args:
            **kwargs: Additional parameters for authentication

        Returns:
            AuthResult from the custom authentication function

        Raises:
            AuthenticationError: If authentication fails or no function is set
        """
        if not self._auth_function:
            return AuthResult(
                success=False, error="No custom authentication function provided"
            )

        try:
            result = await self._auth_function(self.config.auth_params, **kwargs)
            if not isinstance(result, AuthResult):
                raise AuthenticationError("Custom auth function must return AuthResult")
            return result

        except Exception as e:
            raise AuthenticationError(f"Custom authentication failed: {str(e)}")

    async def refresh(self) -> AuthResult:
        """
        Refresh custom authentication.

        Returns:
            AuthResult from the custom refresh function or authentication function

        Raises:
            AuthenticationError: If refresh fails
        """
        # Use refresh function if available, otherwise fall back to auth function
        refresh_func = self._refresh_function or self._auth_function

        if not refresh_func:
            return AuthResult(
                success=False,
                error="No custom refresh or authentication function provided",
            )

        try:
            result = await refresh_func(self.config.auth_params)
            if not isinstance(result, AuthResult):
                raise AuthenticationError(
                    "Custom refresh function must return AuthResult"
                )
            return result

        except Exception as e:
            raise AuthenticationError(f"Custom authentication refresh failed: {str(e)}")

    def add_auth_param(self, key: str, value: Any) -> None:
        """
        Add or update an authentication parameter.

        Args:
            key: Parameter name
            value: Parameter value
        """
        self.config.auth_params[key] = value

    def remove_auth_param(self, key: str) -> None:
        """
        Remove an authentication parameter.

        Args:
            key: Parameter name to remove
        """
        self.config.auth_params.pop(key, None)

    def get_auth_param(self, key: str, default: Any = None) -> Any:
        """
        Get an authentication parameter.

        Args:
            key: Parameter name
            default: Default value if parameter not found

        Returns:
            Parameter value or default
        """
        return self.config.auth_params.get(key, default)
