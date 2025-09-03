"""
Enhanced authentication configuration system.

This module provides comprehensive configuration support for authentication,
including environment variable integration, secure credential management,
and flexible provider configuration.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr, validator, model_validator
from pydantic import ConfigDict

from .base import AuthType, AuthLocation


class CredentialSource(str, Enum):
    """Sources for authentication credentials."""

    DIRECT = "direct"  # Directly provided in config
    ENVIRONMENT = "environment"  # From environment variables
    FILE = "file"  # From file system
    KEYRING = "keyring"  # From system keyring
    VAULT = "vault"  # From external vault (e.g., HashiCorp Vault)


class RetryPolicy(BaseModel):
    """Configuration for authentication retry policies."""

    max_attempts: int = Field(default=3, ge=1, le=10, description="Maximum retry attempts")
    initial_delay: float = Field(default=1.0, ge=0.1, description="Initial retry delay in seconds")
    max_delay: float = Field(default=60.0, ge=1.0, description="Maximum retry delay in seconds")
    exponential_base: float = Field(default=2.0, ge=1.1, description="Exponential backoff base")
    jitter: bool = Field(default=True, description="Add random jitter to delays")
    retry_on_status_codes: List[int] = Field(
        default=[401, 403, 429, 500, 502, 503, 504],
        description="HTTP status codes to retry on"
    )


class SessionConfig(BaseModel):
    """Configuration for session management."""

    enable_persistence: bool = Field(default=True, description="Enable session persistence")
    session_timeout: float = Field(default=3600.0, ge=60.0, description="Session timeout in seconds")
    max_sessions: int = Field(default=10, ge=1, description="Maximum concurrent sessions")
    cleanup_interval: float = Field(default=300.0, ge=60.0, description="Session cleanup interval in seconds")
    storage_path: Optional[Path] = Field(default=None, description="Path for session storage")


class SecurityConfig(BaseModel):
    """Security configuration for authentication."""

    encrypt_credentials: bool = Field(default=True, description="Encrypt stored credentials")
    credential_rotation_interval: Optional[float] = Field(
        default=None, ge=3600.0, description="Credential rotation interval in seconds"
    )
    require_https: bool = Field(default=True, description="Require HTTPS for authentication")
    validate_certificates: bool = Field(default=True, description="Validate SSL certificates")
    mask_credentials_in_logs: bool = Field(default=True, description="Mask credentials in logs")


class ProviderConfig(BaseModel):
    """Configuration for authentication providers."""

    name: str = Field(description="Provider name")
    priority: int = Field(default=1, ge=1, description="Provider priority (lower = higher priority)")
    enabled: bool = Field(default=True, description="Whether provider is enabled")
    failover_enabled: bool = Field(default=True, description="Enable failover to next provider")
    health_check_url: Optional[str] = Field(default=None, description="URL for provider health checks")
    health_check_interval: float = Field(default=300.0, ge=60.0, description="Health check interval in seconds")


class CredentialConfig(BaseModel):
    """Configuration for credential management."""

    source: CredentialSource = Field(default=CredentialSource.DIRECT, description="Credential source")
    value: Optional[Union[str, SecretStr]] = Field(default=None, description="Direct credential value")
    env_var: Optional[str] = Field(default=None, description="Environment variable name")
    file_path: Optional[Path] = Field(default=None, description="File path for credential")
    keyring_service: Optional[str] = Field(default=None, description="Keyring service name")
    keyring_username: Optional[str] = Field(default=None, description="Keyring username")
    vault_path: Optional[str] = Field(default=None, description="Vault path for credential")

    @model_validator(mode='after')
    def validate_credential_source(self):
        """Validate credential source configuration."""
        if self.source == CredentialSource.DIRECT:
            if not self.value:
                raise ValueError("Direct credential source requires 'value'")
        elif self.source == CredentialSource.ENVIRONMENT:
            if not self.env_var:
                raise ValueError("Environment credential source requires 'env_var'")
        elif self.source == CredentialSource.FILE:
            if not self.file_path:
                raise ValueError("File credential source requires 'file_path'")
        elif self.source == CredentialSource.KEYRING:
            if not self.keyring_service or not self.keyring_username:
                raise ValueError("Keyring credential source requires 'keyring_service' and 'keyring_username'")
        elif self.source == CredentialSource.VAULT:
            if not self.vault_path:
                raise ValueError("Vault credential source requires 'vault_path'")

        return self

    def get_credential_value(self) -> Optional[str]:
        """Retrieve the actual credential value based on source."""
        if self.source == CredentialSource.DIRECT:
            if isinstance(self.value, SecretStr):
                return self.value.get_secret_value()
            return self.value
        elif self.source == CredentialSource.ENVIRONMENT:
            return os.getenv(self.env_var) if self.env_var else None
        elif self.source == CredentialSource.FILE:
            if self.file_path and self.file_path.exists():
                return self.file_path.read_text().strip()
            return None
        elif self.source == CredentialSource.KEYRING:
            try:
                import keyring
                return keyring.get_password(self.keyring_service, self.keyring_username)
            except ImportError:
                raise ImportError("keyring package required for keyring credential source")
        elif self.source == CredentialSource.VAULT:
            # Placeholder for vault integration
            # In a real implementation, this would integrate with HashiCorp Vault or similar
            raise NotImplementedError("Vault credential source not yet implemented")

        return None


class EnhancedAuthConfig(BaseModel):
    """Enhanced base configuration for authentication methods."""

    # Basic configuration
    auth_type: AuthType
    enabled: bool = Field(default=True, description="Whether authentication is enabled")
    name: str = Field(description="Configuration name/identifier")
    description: Optional[str] = Field(default=None, description="Configuration description")

    # Timeout and caching
    timeout: float = Field(default=30.0, ge=1.0, description="Authentication timeout in seconds")
    cache_credentials: bool = Field(default=True, description="Cache credentials for reuse")
    cache_ttl: float = Field(default=3600.0, ge=60.0, description="Cache TTL in seconds")
    auto_refresh: bool = Field(default=True, description="Automatically refresh expired credentials")

    # Retry and error handling
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy, description="Retry policy configuration")

    # Session management
    session_config: SessionConfig = Field(default_factory=SessionConfig, description="Session configuration")

    # Security
    security_config: SecurityConfig = Field(default_factory=SecurityConfig, description="Security configuration")

    # Provider configuration
    providers: List[ProviderConfig] = Field(default_factory=list, description="Provider configurations")

    # Custom headers and parameters
    custom_headers: Dict[str, str] = Field(default_factory=dict, description="Custom headers to include")
    custom_params: Dict[str, str] = Field(default_factory=dict, description="Custom parameters to include")

    # Environment-specific overrides
    environment_overrides: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Environment-specific configuration overrides"
    )

    model_config = ConfigDict(use_enum_values=True)

    def get_effective_config(self, environment: Optional[str] = None) -> "EnhancedAuthConfig":
        """Get effective configuration with environment overrides applied."""
        if not environment or environment not in self.environment_overrides:
            return self

        # Create a copy and apply overrides
        config_dict = self.model_dump()
        overrides = self.environment_overrides[environment]

        # Deep merge overrides
        def deep_merge(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
            for key, value in overrides.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    base[key] = deep_merge(base[key], value)
                else:
                    base[key] = value
            return base

        config_dict = deep_merge(config_dict, overrides)
        return self.__class__(**config_dict)


class EnhancedAPIKeyConfig(EnhancedAuthConfig):
    """Enhanced API key authentication configuration."""

    auth_type: AuthType = Field(default=AuthType.API_KEY, frozen=True)

    # API key configuration
    api_key: CredentialConfig = Field(description="API key credential configuration")
    key_name: str = Field(default="api_key", description="Name of the API key parameter")
    location: AuthLocation = Field(default=AuthLocation.HEADER, description="Where to place the API key")
    prefix: Optional[str] = Field(default=None, description="Optional prefix for the API key")

    # Multiple API keys support
    fallback_keys: List[CredentialConfig] = Field(
        default_factory=list, description="Fallback API keys for rotation/failover"
    )


class EnhancedBasicAuthConfig(EnhancedAuthConfig):
    """Enhanced basic authentication configuration."""

    auth_type: AuthType = Field(default=AuthType.BASIC, frozen=True)

    # Basic auth credentials
    username: CredentialConfig = Field(description="Username credential configuration")
    password: CredentialConfig = Field(description="Password credential configuration")

    # Encoding options
    encoding: str = Field(default="utf-8", description="Character encoding for credentials")


class EnhancedBearerTokenConfig(EnhancedAuthConfig):
    """Enhanced bearer token authentication configuration."""

    auth_type: AuthType = Field(default=AuthType.BEARER, frozen=True)

    # Token configuration
    token: CredentialConfig = Field(description="Bearer token credential configuration")
    token_prefix: str = Field(default="Bearer", description="Token prefix")

    # Token refresh configuration
    refresh_token: Optional[CredentialConfig] = Field(
        default=None, description="Refresh token credential configuration"
    )
    refresh_url: Optional[str] = Field(default=None, description="Token refresh endpoint URL")
    refresh_threshold: float = Field(
        default=300.0, ge=60.0, description="Refresh token when expires within this many seconds"
    )


class EnhancedJWTConfig(EnhancedAuthConfig):
    """Enhanced JWT authentication configuration."""

    auth_type: AuthType = Field(default=AuthType.JWT, frozen=True)

    # JWT configuration
    secret_key: CredentialConfig = Field(description="JWT secret key credential configuration")
    algorithm: str = Field(default="HS256", description="JWT signing algorithm")

    # Token configuration
    token_header: str = Field(default="Authorization", description="Header name for JWT token")
    token_prefix: str = Field(default="Bearer", description="Token prefix")

    # Claims configuration
    issuer: Optional[str] = Field(default=None, description="JWT issuer claim")
    audience: Optional[str] = Field(default=None, description="JWT audience claim")
    subject: Optional[str] = Field(default=None, description="JWT subject claim")

    # Expiration configuration
    expires_in: float = Field(default=3600.0, ge=60.0, description="Token expiration time in seconds")
    refresh_threshold: float = Field(
        default=300.0, ge=60.0, description="Refresh token when expires within this many seconds"
    )

    # Additional claims
    custom_claims: Dict[str, Any] = Field(default_factory=dict, description="Custom JWT claims")


class EnhancedOAuth2Config(EnhancedAuthConfig):
    """Enhanced OAuth 2.0 authentication configuration."""

    auth_type: AuthType = Field(default=AuthType.OAUTH2, frozen=True)

    # OAuth 2.0 endpoints
    authorization_url: str = Field(description="OAuth 2.0 authorization endpoint URL")
    token_url: str = Field(description="OAuth 2.0 token endpoint URL")
    refresh_url: Optional[str] = Field(default=None, description="OAuth 2.0 token refresh endpoint URL")
    revoke_url: Optional[str] = Field(default=None, description="OAuth 2.0 token revocation endpoint URL")

    # Client credentials
    client_id: CredentialConfig = Field(description="OAuth 2.0 client ID credential configuration")
    client_secret: CredentialConfig = Field(description="OAuth 2.0 client secret credential configuration")

    # Grant type and flow configuration
    grant_type: str = Field(default="authorization_code", description="OAuth 2.0 grant type")
    response_type: str = Field(default="code", description="OAuth 2.0 response type")
    redirect_uri: Optional[str] = Field(default=None, description="OAuth 2.0 redirect URI")

    # Scope and permissions
    scopes: List[str] = Field(default_factory=list, description="OAuth 2.0 scopes")

    # PKCE configuration
    use_pkce: bool = Field(default=True, description="Use PKCE for authorization code flow")
    code_challenge_method: str = Field(default="S256", description="PKCE code challenge method")

    # Token configuration
    token_storage: Optional[Path] = Field(default=None, description="Path for token storage")
    auto_refresh: bool = Field(default=True, description="Automatically refresh expired tokens")
    refresh_threshold: float = Field(
        default=300.0, ge=60.0, description="Refresh token when expires within this many seconds"
    )


class EnhancedCustomAuthConfig(EnhancedAuthConfig):
    """Enhanced custom authentication configuration."""

    auth_type: AuthType = Field(default=AuthType.CUSTOM, frozen=True)

    # Custom authentication configuration
    auth_method: str = Field(description="Custom authentication method name")
    auth_params: Dict[str, Any] = Field(default_factory=dict, description="Custom authentication parameters")

    # Credential configuration
    credentials: Dict[str, CredentialConfig] = Field(
        default_factory=dict, description="Custom credential configurations"
    )

    # Custom headers and processing
    header_template: Optional[str] = Field(
        default=None, description="Template for authentication header (supports {credential_name} placeholders)"
    )
    param_template: Optional[str] = Field(
        default=None, description="Template for authentication parameters"
    )

    # Custom validation
    validation_url: Optional[str] = Field(default=None, description="URL for credential validation")
    validation_method: str = Field(default="GET", description="HTTP method for validation")
    validation_headers: Dict[str, str] = Field(
        default_factory=dict, description="Headers for validation request"
    )


class AuthenticationConfig(BaseModel):
    """Main authentication configuration container."""

    # Default configuration
    default_method: Optional[str] = Field(default=None, description="Default authentication method")

    # Authentication methods
    methods: Dict[str, Union[
        EnhancedAPIKeyConfig,
        EnhancedBasicAuthConfig,
        EnhancedBearerTokenConfig,
        EnhancedJWTConfig,
        EnhancedOAuth2Config,
        EnhancedCustomAuthConfig
    ]] = Field(default_factory=dict, description="Authentication method configurations")

    # URL pattern matching
    url_patterns: Dict[str, str] = Field(
        default_factory=dict, description="URL pattern to authentication method mapping"
    )

    # Global settings
    global_timeout: float = Field(default=30.0, ge=1.0, description="Global authentication timeout")
    global_retry_policy: RetryPolicy = Field(
        default_factory=RetryPolicy, description="Global retry policy"
    )
    global_security_config: SecurityConfig = Field(
        default_factory=SecurityConfig, description="Global security configuration"
    )

    # Environment configuration
    environment: Optional[str] = Field(default=None, description="Current environment")

    model_config = ConfigDict(use_enum_values=True)

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "AuthenticationConfig":
        """Create configuration from dictionary."""
        # Process method configurations
        methods = {}
        for name, method_config in config_dict.get("methods", {}).items():
            auth_type = method_config.get("auth_type")

            if auth_type == AuthType.API_KEY:
                methods[name] = EnhancedAPIKeyConfig(**method_config)
            elif auth_type == AuthType.BASIC:
                methods[name] = EnhancedBasicAuthConfig(**method_config)
            elif auth_type == AuthType.BEARER:
                methods[name] = EnhancedBearerTokenConfig(**method_config)
            elif auth_type == AuthType.JWT:
                methods[name] = EnhancedJWTConfig(**method_config)
            elif auth_type == AuthType.OAUTH2:
                methods[name] = EnhancedOAuth2Config(**method_config)
            elif auth_type == AuthType.CUSTOM:
                methods[name] = EnhancedCustomAuthConfig(**method_config)
            else:
                raise ValueError(f"Unsupported authentication type: {auth_type}")

        config_dict["methods"] = methods
        return cls(**config_dict)

    @classmethod
    def from_environment(cls, prefix: str = "WEBFETCH_AUTH_") -> "AuthenticationConfig":
        """Create configuration from environment variables."""
        config_dict = {}

        # Scan environment variables with the given prefix
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Convert environment variable to config path
                config_path = key[len(prefix):].lower().replace("_", ".")

                # Set nested configuration value
                keys = config_path.split(".")
                current = config_dict
                for k in keys[:-1]:
                    if k not in current:
                        current[k] = {}
                    current = current[k]
                current[keys[-1]] = value

        return cls.from_dict(config_dict)

    def get_method_config(self, method_name: str) -> Optional[EnhancedAuthConfig]:
        """Get configuration for a specific authentication method."""
        config = self.methods.get(method_name)
        if config and self.environment:
            return config.get_effective_config(self.environment)
        return config

    def get_method_for_url(self, url: str) -> Optional[str]:
        """Get authentication method for a given URL."""
        from urllib.parse import urlparse

        parsed_url = urlparse(url)
        hostname = parsed_url.hostname or ""

        # Check URL patterns
        for pattern, method_name in self.url_patterns.items():
            if pattern in hostname:
                return method_name

        # Return default method
        return self.default_method
