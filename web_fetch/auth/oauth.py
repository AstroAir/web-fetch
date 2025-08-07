"""
OAuth 2.0 authentication implementation.

This module provides OAuth 2.0 authentication support with various grant types
and automatic token refresh capabilities.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import aiohttp
from pydantic import Field, HttpUrl

from ..exceptions import WebFetchError
from .base import AuthConfig, AuthMethod, AuthResult, AuthType


class AuthenticationError(WebFetchError):
    """Authentication-specific error."""

    pass


class GrantType(str):
    """OAuth 2.0 grant types."""

    AUTHORIZATION_CODE = "authorization_code"
    CLIENT_CREDENTIALS = "client_credentials"
    REFRESH_TOKEN = "refresh_token"
    PASSWORD = "password"  # Resource Owner Password Credentials


@dataclass
class OAuthTokenResponse:
    """OAuth token response data."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: Optional[int] = None
    refresh_token: Optional[str] = None
    scope: Optional[str] = None

    @property
    def expires_at(self) -> Optional[float]:
        """Calculate expiration timestamp."""
        if self.expires_in is None:
            return None
        return time.time() + self.expires_in


class OAuth2Config(AuthConfig):
    """Configuration for OAuth 2.0 authentication."""

    auth_type: AuthType = Field(default=AuthType.OAUTH2, frozen=True)

    # OAuth endpoints
    token_url: HttpUrl = Field(description="OAuth token endpoint URL")
    authorization_url: Optional[HttpUrl] = Field(
        default=None, description="OAuth authorization endpoint URL"
    )

    # Client credentials
    client_id: str = Field(description="OAuth client ID")
    client_secret: str = Field(description="OAuth client secret")

    # Grant type and parameters
    grant_type: str = Field(
        default=GrantType.CLIENT_CREDENTIALS, description="OAuth grant type"
    )
    scope: Optional[str] = Field(default=None, description="OAuth scope")

    # For authorization code flow
    redirect_uri: Optional[str] = Field(
        default=None, description="Redirect URI for authorization code flow"
    )
    authorization_code: Optional[str] = Field(
        default=None, description="Authorization code"
    )

    # For password flow
    username: Optional[str] = Field(
        default=None, description="Username for password grant"
    )
    password: Optional[str] = Field(
        default=None, description="Password for password grant"
    )

    # Token management
    refresh_token: Optional[str] = Field(
        default=None, description="Refresh token for token renewal"
    )
    token_refresh_threshold: float = Field(
        default=300.0, description="Refresh token when expires within this many seconds"
    )

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class OAuth2Auth(AuthMethod):
    """
    OAuth 2.0 authentication method.

    Supports multiple OAuth 2.0 grant types:
    - Client Credentials (most common for API access)
    - Authorization Code (for user authorization)
    - Resource Owner Password Credentials
    - Refresh Token (for token renewal)

    Examples:
        Client credentials flow:
        ```python
        config = OAuth2Config(
            token_url="https://api.example.com/oauth/token",
            client_id="your-client-id",
            client_secret="your-client-secret",
            grant_type=GrantType.CLIENT_CREDENTIALS,
            scope="read write"
        )
        auth = OAuth2Auth(config)
        ```

        Authorization code flow:
        ```python
        config = OAuth2Config(
            token_url="https://api.example.com/oauth/token",
            authorization_url="https://api.example.com/oauth/authorize",
            client_id="your-client-id",
            client_secret="your-client-secret",
            grant_type=GrantType.AUTHORIZATION_CODE,
            redirect_uri="https://yourapp.com/callback",
            authorization_code="received-auth-code"
        )
        auth = OAuth2Auth(config)
        ```
    """

    def __init__(self, config: OAuth2Config):
        """
        Initialize OAuth 2.0 authentication.

        Args:
            config: OAuth 2.0 configuration
        """
        super().__init__(config)
        self.config: OAuth2Config = config
        self._token_response: Optional[OAuthTokenResponse] = None

    async def authenticate(self, **kwargs: Any) -> AuthResult:
        """
        Perform OAuth 2.0 authentication.

        Args:
            **kwargs: Additional parameters for authentication

        Returns:
            AuthResult containing the access token

        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # Prepare token request data
            token_data = await self._prepare_token_request(**kwargs)

            # Make token request
            token_response = await self._request_token(token_data)

            # Store token response
            self._token_response = token_response

            # Create auth result
            result = AuthResult(
                success=True,
                headers={
                    "Authorization": f"{token_response.token_type} {token_response.access_token}"
                },
                expires_at=token_response.expires_at,
            )

            return result

        except Exception as e:
            raise AuthenticationError(f"OAuth 2.0 authentication failed: {str(e)}")

    async def refresh(self) -> AuthResult:
        """
        Refresh OAuth 2.0 access token.

        Returns:
            AuthResult with refreshed token

        Raises:
            AuthenticationError: If refresh fails
        """
        if not self._token_response or not self._token_response.refresh_token:
            # No refresh token available, perform full authentication
            return await self.authenticate()

        try:
            # Prepare refresh token request
            refresh_data = {
                "grant_type": GrantType.REFRESH_TOKEN,
                "refresh_token": self._token_response.refresh_token,
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
            }

            if self.config.scope:
                refresh_data["scope"] = self.config.scope

            # Make refresh request
            token_response = await self._request_token(refresh_data)

            # Update stored token
            self._token_response = token_response

            # Create auth result
            result = AuthResult(
                success=True,
                headers={
                    "Authorization": f"{token_response.token_type} {token_response.access_token}"
                },
                expires_at=token_response.expires_at,
            )

            return result

        except Exception as e:
            raise AuthenticationError(f"OAuth 2.0 token refresh failed: {str(e)}")

    async def _prepare_token_request(self, **kwargs: Any) -> Dict[str, str]:
        """Prepare token request data based on grant type."""
        data = {
            "grant_type": self.config.grant_type,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }

        if self.config.scope:
            data["scope"] = self.config.scope

        if self.config.grant_type == GrantType.AUTHORIZATION_CODE:
            if not self.config.authorization_code:
                raise AuthenticationError(
                    "Authorization code is required for authorization_code grant"
                )
            data["code"] = self.config.authorization_code
            if self.config.redirect_uri:
                data["redirect_uri"] = self.config.redirect_uri

        elif self.config.grant_type == GrantType.PASSWORD:
            if not self.config.username or not self.config.password:
                raise AuthenticationError(
                    "Username and password are required for password grant"
                )
            data["username"] = self.config.username
            data["password"] = self.config.password

        # Add any additional parameters from kwargs
        data.update(kwargs)

        return data

    async def _request_token(self, data: Dict[str, str]) -> OAuthTokenResponse:
        """Make token request to OAuth server."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                str(self.config.token_url),
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise AuthenticationError(
                        f"Token request failed: {response.status} - {error_text}"
                    )

                response_data = await response.json()

                # Validate required fields
                if "access_token" not in response_data:
                    raise AuthenticationError("Access token not found in response")

                return OAuthTokenResponse(
                    access_token=response_data["access_token"],
                    token_type=response_data.get("token_type", "Bearer"),
                    expires_in=response_data.get("expires_in"),
                    refresh_token=response_data.get("refresh_token"),
                    scope=response_data.get("scope"),
                )

    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Generate authorization URL for authorization code flow.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Authorization URL

        Raises:
            AuthenticationError: If authorization URL is not configured
        """
        if not self.config.authorization_url:
            raise AuthenticationError("Authorization URL not configured")

        params = {
            "response_type": "code",
            "client_id": self.config.client_id,
        }

        if self.config.redirect_uri:
            params["redirect_uri"] = self.config.redirect_uri

        if self.config.scope:
            params["scope"] = self.config.scope

        if state:
            params["state"] = state

        return f"{self.config.authorization_url}?{urlencode(params)}"

    @property
    def access_token(self) -> Optional[str]:
        """Get current access token."""
        return self._token_response.access_token if self._token_response else None

    @property
    def token_type(self) -> Optional[str]:
        """Get current token type."""
        return self._token_response.token_type if self._token_response else None
