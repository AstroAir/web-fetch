"""
JWT (JSON Web Token) authentication implementation.

This module provides JWT authentication support with token validation,
automatic refresh, and custom claims handling.
"""

from __future__ import annotations

import base64
import json
import time
from typing import Any, Dict, Optional

from pydantic import Field, ConfigDict

from ..exceptions import WebFetchError
from .base import AuthConfig, AuthMethod, AuthResult, AuthType


class AuthenticationError(WebFetchError):
    """Authentication-specific error."""

    pass


class JWTConfig(AuthConfig):
    """Configuration for JWT authentication."""

    auth_type: AuthType = Field(default=AuthType.JWT, frozen=True)

    # JWT token
    token: Optional[str] = Field(default=None, description="JWT token string")

    # Token generation parameters (if generating tokens locally)
    secret_key: Optional[str] = Field(
        default=None, description="Secret key for token signing"
    )
    algorithm: str = Field(default="HS256", description="JWT signing algorithm")

    # Claims
    issuer: Optional[str] = Field(default=None, description="Token issuer (iss claim)")
    audience: Optional[str] = Field(
        default=None, description="Token audience (aud claim)"
    )
    subject: Optional[str] = Field(
        default=None, description="Token subject (sub claim)"
    )

    # Token lifetime
    expires_in: int = Field(
        default=3600, description="Token expiration time in seconds"
    )

    # Custom claims
    custom_claims: Dict[str, Any] = Field(
        default_factory=dict, description="Custom JWT claims"
    )

    # Header configuration
    header_name: str = Field(default="Authorization", description="Header name for JWT")
    header_prefix: str = Field(default="Bearer", description="Header prefix for JWT")

    # Validation settings
    verify_signature: bool = Field(default=True, description="Verify JWT signature")
    verify_expiration: bool = Field(default=True, description="Verify JWT expiration")

    model_config = ConfigDict(use_enum_values=True)


class JWTAuth(AuthMethod):
    """
    JWT (JSON Web Token) authentication method.

    Supports JWT token validation, automatic refresh, and custom claims.
    Can work with existing tokens or generate new ones locally.

    Example:
        ```python
        # Using existing JWT token
        config = JWTConfig(
            token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            header_name="Authorization"
        )
        auth = JWTAuth(config)

        # Generating JWT token locally
        config = JWTConfig(
            secret_key="your-secret-key",
            algorithm="HS256",
            issuer="your-app",
            subject="user-123",
            custom_claims={"role": "admin"}
        )
        auth = JWTAuth(config)
        ```
    """

    def __init__(self, config: JWTConfig):
        """
        Initialize JWT authentication.

        Args:
            config: JWT configuration
        """
        super().__init__(config)
        self.config: JWTConfig = config
        self._current_token: Optional[str] = config.token

    async def authenticate(self, **kwargs: Any) -> AuthResult:
        """
        Perform JWT authentication.

        Args:
            **kwargs: Additional parameters (custom claims, etc.)

        Returns:
            AuthResult containing the JWT token

        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # Use existing token or generate new one
            if self.config.token:
                token = self.config.token
            elif self.config.secret_key:
                token = self._generate_token(**kwargs)
            else:
                return AuthResult(
                    success=False, error="Either token or secret_key must be provided"
                )

            # Validate token format and expiration
            if not self._validate_token_format(token):
                return AuthResult(success=False, error="Invalid JWT token format")

            # Check if token is expired
            if self._is_token_expired(token):
                if self.config.secret_key:
                    # Generate new token if we can
                    token = self._generate_token(**kwargs)
                else:
                    return AuthResult(
                        success=False,
                        error="JWT token is expired and cannot be refreshed",
                    )

            self._current_token = token

            # Create auth result
            result = AuthResult(
                success=True,
                headers={self.config.header_name: f"Bearer {token}"},
                expires_at=self._get_token_expiration(token),
            )

            return result

        except Exception as e:
            raise AuthenticationError(f"JWT authentication failed: {str(e)}")

    async def refresh(self) -> AuthResult:
        """
        Refresh JWT token.

        Returns:
            AuthResult with refreshed token

        Raises:
            AuthenticationError: If refresh fails
        """
        if not self.config.secret_key:
            return AuthResult(
                success=False, error="Cannot refresh JWT token without secret key"
            )

        try:
            # Generate new token
            new_token = self._generate_token()
            self._current_token = new_token

            result = AuthResult(
                success=True,
                headers={self.config.header_name: f"Bearer {new_token}"},
                expires_at=self._get_token_expiration(new_token),
            )

            return result

        except Exception as e:
            raise AuthenticationError(f"JWT token refresh failed: {str(e)}")

    def _generate_token(self, **kwargs: Any) -> str:
        """
        Generate a new JWT token.

        Args:
            **kwargs: Additional claims

        Returns:
            Generated JWT token string
        """
        # Create header
        header = {"typ": "JWT", "alg": self.config.algorithm}

        # Create payload
        current_time = int(time.time())
        payload: Dict[str, Any] = {
            "iat": current_time,  # Issued at
            "exp": current_time + self.config.expires_in,  # Expiration
        }

        # Add standard claims if configured
        if self.config.issuer:
            payload["iss"] = self.config.issuer

        if self.config.audience:
            payload["aud"] = self.config.audience

        if self.config.subject:
            payload["sub"] = self.config.subject

        # Add custom claims
        payload.update(self.config.custom_claims)
        payload.update(kwargs)

        # Encode components
        header_encoded = self._base64url_encode(
            json.dumps(header, separators=(",", ":"))
        )
        payload_encoded = self._base64url_encode(
            json.dumps(payload, separators=(",", ":"))
        )

        # Create signature (simplified - in production use proper JWT library)
        signature_input = f"{header_encoded}.{payload_encoded}"
        signature = self._create_signature(signature_input)

        return f"{header_encoded}.{payload_encoded}.{signature}"

    def _create_signature(self, message: str) -> str:
        """
        Create JWT signature.

        Note: This is a simplified implementation. In production,
        use a proper JWT library like PyJWT.
        """
        import hashlib
        import hmac

        if self.config.algorithm == "HS256":
            if not self.config.secret_key:
                raise ValueError("Secret key is required for HS256 algorithm")
            signature = hmac.new(
                self.config.secret_key.encode("utf-8"),
                message.encode("utf-8"),
                hashlib.sha256,
            ).digest()
            return self._base64url_encode(signature)
        else:
            raise ValueError(f"Unsupported algorithm: {self.config.algorithm}")

    def _base64url_encode(self, data: Any) -> str:
        """Encode data using base64url encoding."""
        if isinstance(data, str):
            data = data.encode("utf-8")

        encoded = base64.urlsafe_b64encode(data).decode("utf-8")
        return encoded.rstrip("=")

    def _base64url_decode(self, data: str) -> bytes:
        """Decode base64url encoded data."""
        # Add padding if needed
        padding = 4 - (len(data) % 4)
        if padding != 4:
            data += "=" * padding

        return base64.urlsafe_b64decode(data)

    def _validate_token_format(self, token: str) -> bool:
        """Validate JWT token format."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return False

            # Try to decode header and payload
            header = json.loads(self._base64url_decode(parts[0]))
            payload = json.loads(self._base64url_decode(parts[1]))

            return True
        except Exception:
            return False

    def _is_token_expired(self, token: str) -> bool:
        """Check if JWT token is expired."""
        try:
            parts = token.split(".")
            payload = json.loads(self._base64url_decode(parts[1]))

            exp = payload.get("exp")
            if exp is None:
                return False

            return time.time() >= exp
        except Exception:
            return True

    def _get_token_expiration(self, token: str) -> Optional[float]:
        """Get token expiration timestamp."""
        try:
            parts = token.split(".")
            payload = json.loads(self._base64url_decode(parts[1]))
            return payload.get("exp")
        except Exception:
            return None

    def get_token_claims(self, token: Optional[str] = None) -> Dict[str, Any]:
        """
        Get claims from JWT token.

        Args:
            token: JWT token (uses current token if not provided)

        Returns:
            Dictionary of token claims
        """
        token = token or self._current_token
        if not token:
            return {}

        try:
            parts = token.split(".")
            payload = json.loads(self._base64url_decode(parts[1]))
            return payload
        except Exception:
            return {}

    @property
    def current_token(self) -> Optional[str]:
        """Get current JWT token."""
        return self._current_token
