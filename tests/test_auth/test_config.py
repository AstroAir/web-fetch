"""
Comprehensive tests for the authentication configuration module.
"""

import pytest
import os
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from web_fetch.auth.config import (
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
from web_fetch.auth.base import AuthType, AuthLocation


class TestCredentialConfig:
    """Test credential configuration."""

    def test_direct_credential_config(self):
        """Test direct credential configuration."""
        config = CredentialConfig(
            source=CredentialSource.DIRECT,
            value="direct-secret"
        )
        
        assert config.source == CredentialSource.DIRECT
        assert config.value == "direct-secret"
        assert config.key is None
        assert config.path is None

    def test_environment_credential_config(self):
        """Test environment variable credential configuration."""
        config = CredentialConfig(
            source=CredentialSource.ENVIRONMENT,
            key="API_KEY_ENV_VAR"
        )
        
        assert config.source == CredentialSource.ENVIRONMENT
        assert config.key == "API_KEY_ENV_VAR"
        assert config.value is None
        assert config.path is None

    def test_file_credential_config(self):
        """Test file-based credential configuration."""
        config = CredentialConfig(
            source=CredentialSource.FILE,
            path="/path/to/secret.txt"
        )
        
        assert config.source == CredentialSource.FILE
        assert config.path == "/path/to/secret.txt"
        assert config.value is None
        assert config.key is None

    def test_store_credential_config(self):
        """Test store-based credential configuration."""
        config = CredentialConfig(
            source=CredentialSource.STORE,
            key="stored-secret-key"
        )
        
        assert config.source == CredentialSource.STORE
        assert config.key == "stored-secret-key"
        assert config.value is None
        assert config.path is None

    def test_credential_config_with_cache_ttl(self):
        """Test credential configuration with cache TTL."""
        config = CredentialConfig(
            source=CredentialSource.DIRECT,
            value="cached-secret",
            cache_ttl=300
        )
        
        assert config.cache_ttl == 300

    def test_credential_config_validation(self):
        """Test credential configuration validation."""
        # Missing value for direct source
        with pytest.raises(ValueError):
            CredentialConfig(source=CredentialSource.DIRECT)
        
        # Missing key for environment source
        with pytest.raises(ValueError):
            CredentialConfig(source=CredentialSource.ENVIRONMENT)
        
        # Missing path for file source
        with pytest.raises(ValueError):
            CredentialConfig(source=CredentialSource.FILE)
        
        # Missing key for store source
        with pytest.raises(ValueError):
            CredentialConfig(source=CredentialSource.STORE)


class TestRetryPolicy:
    """Test retry policy configuration."""

    def test_default_retry_policy(self):
        """Test default retry policy."""
        policy = RetryPolicy()
        
        assert policy.max_retries == 3
        assert policy.base_delay == 1.0
        assert policy.max_delay == 60.0
        assert policy.exponential_base == 2.0
        assert policy.jitter == True
        assert policy.retryable_errors == [429, 500, 502, 503, 504]

    def test_custom_retry_policy(self):
        """Test custom retry policy."""
        policy = RetryPolicy(
            max_retries=5,
            base_delay=2.0,
            max_delay=120.0,
            exponential_base=1.5,
            jitter=False,
            retryable_errors=[429, 500]
        )
        
        assert policy.max_retries == 5
        assert policy.base_delay == 2.0
        assert policy.max_delay == 120.0
        assert policy.exponential_base == 1.5
        assert policy.jitter == False
        assert policy.retryable_errors == [429, 500]

    def test_retry_policy_validation(self):
        """Test retry policy validation."""
        # Invalid max_retries
        with pytest.raises(ValueError):
            RetryPolicy(max_retries=-1)
        
        # Invalid base_delay
        with pytest.raises(ValueError):
            RetryPolicy(base_delay=-1.0)
        
        # Invalid max_delay
        with pytest.raises(ValueError):
            RetryPolicy(max_delay=-1.0)
        
        # Invalid exponential_base
        with pytest.raises(ValueError):
            RetryPolicy(exponential_base=0.5)


class TestSecurityConfig:
    """Test security configuration."""

    def test_default_security_config(self):
        """Test default security configuration."""
        config = SecurityConfig()
        
        assert config.encrypt_credentials == True
        assert config.credential_rotation_interval is None
        assert config.require_https == True
        assert config.validate_certificates == True

    def test_custom_security_config(self):
        """Test custom security configuration."""
        config = SecurityConfig(
            encrypt_credentials=False,
            credential_rotation_interval=timedelta(days=30),
            require_https=False,
            validate_certificates=False
        )
        
        assert config.encrypt_credentials == False
        assert config.credential_rotation_interval == timedelta(days=30)
        assert config.require_https == False
        assert config.validate_certificates == False


class TestSessionConfig:
    """Test session configuration."""

    def test_default_session_config(self):
        """Test default session configuration."""
        config = SessionConfig()
        
        assert config.session_timeout == timedelta(hours=24)
        assert config.cleanup_interval == timedelta(hours=1)
        assert config.max_sessions_per_user == 10
        assert config.enable_session_refresh == True

    def test_custom_session_config(self):
        """Test custom session configuration."""
        config = SessionConfig(
            session_timeout=timedelta(hours=2),
            cleanup_interval=timedelta(minutes=30),
            max_sessions_per_user=5,
            enable_session_refresh=False
        )
        
        assert config.session_timeout == timedelta(hours=2)
        assert config.cleanup_interval == timedelta(minutes=30)
        assert config.max_sessions_per_user == 5
        assert config.enable_session_refresh == False


class TestProviderConfig:
    """Test provider configuration."""

    def test_provider_config_creation(self):
        """Test creating provider configuration."""
        config = ProviderConfig(
            name="test-provider",
            base_url="https://api.example.com",
            auth_endpoint="/oauth/token",
            default_scopes=["read", "write"],
            rate_limit=100
        )
        
        assert config.name == "test-provider"
        assert config.base_url == "https://api.example.com"
        assert config.auth_endpoint == "/oauth/token"
        assert config.default_scopes == ["read", "write"]
        assert config.rate_limit == 100


class TestEnhancedAuthConfigs:
    """Test enhanced authentication configurations."""

    def test_enhanced_api_key_config(self):
        """Test enhanced API key configuration."""
        credential_config = CredentialConfig(
            source=CredentialSource.ENVIRONMENT,
            key="API_KEY"
        )
        
        config = EnhancedAPIKeyConfig(
            credential=credential_config,
            key_name="X-API-Key",
            location=AuthLocation.HEADER,
            rotation_interval=timedelta(days=30)
        )
        
        assert config.credential == credential_config
        assert config.key_name == "X-API-Key"
        assert config.location == AuthLocation.HEADER
        assert config.rotation_interval == timedelta(days=30)
        assert config.auth_type == AuthType.API_KEY

    def test_enhanced_basic_auth_config(self):
        """Test enhanced basic authentication configuration."""
        username_config = CredentialConfig(
            source=CredentialSource.DIRECT,
            value="testuser"
        )
        password_config = CredentialConfig(
            source=CredentialSource.ENVIRONMENT,
            key="PASSWORD"
        )
        
        config = EnhancedBasicAuthConfig(
            username=username_config,
            password=password_config,
            realm="test-realm"
        )
        
        assert config.username == username_config
        assert config.password == password_config
        assert config.realm == "test-realm"
        assert config.auth_type == AuthType.BASIC

    def test_enhanced_bearer_token_config(self):
        """Test enhanced bearer token configuration."""
        token_config = CredentialConfig(
            source=CredentialSource.FILE,
            path="/path/to/token.txt"
        )
        
        config = EnhancedBearerTokenConfig(
            token=token_config,
            token_type="Bearer",
            refresh_threshold=timedelta(minutes=5)
        )
        
        assert config.token == token_config
        assert config.token_type == "Bearer"
        assert config.refresh_threshold == timedelta(minutes=5)
        assert config.auth_type == AuthType.BEARER_TOKEN

    def test_enhanced_jwt_config(self):
        """Test enhanced JWT configuration."""
        secret_config = CredentialConfig(
            source=CredentialSource.STORE,
            key="jwt-secret"
        )
        
        config = EnhancedJWTConfig(
            secret=secret_config,
            algorithm="HS256",
            issuer="test-issuer",
            audience="test-audience",
            expiration_time=timedelta(hours=1)
        )
        
        assert config.secret == secret_config
        assert config.algorithm == "HS256"
        assert config.issuer == "test-issuer"
        assert config.audience == "test-audience"
        assert config.expiration_time == timedelta(hours=1)
        assert config.auth_type == AuthType.JWT

    def test_enhanced_oauth2_config(self):
        """Test enhanced OAuth2 configuration."""
        client_id_config = CredentialConfig(
            source=CredentialSource.DIRECT,
            value="client-123"
        )
        client_secret_config = CredentialConfig(
            source=CredentialSource.ENVIRONMENT,
            key="CLIENT_SECRET"
        )
        
        config = EnhancedOAuth2Config(
            client_id=client_id_config,
            client_secret=client_secret_config,
            authorization_url="https://auth.example.com/oauth/authorize",
            token_url="https://auth.example.com/oauth/token",
            scopes=["read", "write"],
            redirect_uri="https://app.example.com/callback"
        )
        
        assert config.client_id == client_id_config
        assert config.client_secret == client_secret_config
        assert config.authorization_url == "https://auth.example.com/oauth/authorize"
        assert config.token_url == "https://auth.example.com/oauth/token"
        assert config.scopes == ["read", "write"]
        assert config.redirect_uri == "https://app.example.com/callback"
        assert config.auth_type == AuthType.OAUTH2

    def test_enhanced_custom_auth_config(self):
        """Test enhanced custom authentication configuration."""
        config = EnhancedCustomAuthConfig(
            auth_function="custom_auth_function",
            parameters={"param1": "value1", "param2": "value2"},
            headers={"Custom-Header": "custom-value"},
            validation_function="custom_validation_function"
        )
        
        assert config.auth_function == "custom_auth_function"
        assert config.parameters == {"param1": "value1", "param2": "value2"}
        assert config.headers == {"Custom-Header": "custom-value"}
        assert config.validation_function == "custom_validation_function"
        assert config.auth_type == AuthType.CUSTOM


class TestAuthenticationConfig:
    """Test main authentication configuration."""

    def test_authentication_config_creation(self):
        """Test creating authentication configuration."""
        retry_policy = RetryPolicy(max_retries=5)
        security_config = SecurityConfig(encrypt_credentials=True)
        session_config = SessionConfig(session_timeout=timedelta(hours=2))
        
        config = AuthenticationConfig(
            retry_policy=retry_policy,
            security=security_config,
            session=session_config,
            enable_circuit_breaker=True,
            circuit_breaker_threshold=10
        )
        
        assert config.retry_policy == retry_policy
        assert config.security == security_config
        assert config.session == session_config
        assert config.enable_circuit_breaker == True
        assert config.circuit_breaker_threshold == 10

    def test_authentication_config_defaults(self):
        """Test authentication configuration with defaults."""
        config = AuthenticationConfig()
        
        assert config.retry_policy is not None
        assert config.security is not None
        assert config.session is not None
        assert config.enable_circuit_breaker == False
        assert config.circuit_breaker_threshold == 5


class TestEnhancedAuthConfig:
    """Test enhanced authentication configuration."""

    def test_enhanced_auth_config_creation(self):
        """Test creating enhanced auth configuration."""
        api_key_config = EnhancedAPIKeyConfig(
            credential=CredentialConfig(
                source=CredentialSource.DIRECT,
                value="test-key"
            ),
            key_name="X-API-Key"
        )
        
        auth_config = AuthenticationConfig()
        
        config = EnhancedAuthConfig(
            primary_auth=api_key_config,
            fallback_auth=None,
            authentication_config=auth_config
        )
        
        assert config.primary_auth == api_key_config
        assert config.fallback_auth is None
        assert config.authentication_config == auth_config

    def test_enhanced_auth_config_with_fallback(self):
        """Test enhanced auth configuration with fallback."""
        primary_config = EnhancedAPIKeyConfig(
            credential=CredentialConfig(
                source=CredentialSource.ENVIRONMENT,
                key="PRIMARY_API_KEY"
            ),
            key_name="X-API-Key"
        )
        
        fallback_config = EnhancedBasicAuthConfig(
            username=CredentialConfig(
                source=CredentialSource.DIRECT,
                value="fallback_user"
            ),
            password=CredentialConfig(
                source=CredentialSource.ENVIRONMENT,
                key="FALLBACK_PASSWORD"
            )
        )
        
        config = EnhancedAuthConfig(
            primary_auth=primary_config,
            fallback_auth=fallback_config
        )
        
        assert config.primary_auth == primary_config
        assert config.fallback_auth == fallback_config
