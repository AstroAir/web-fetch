"""
Comprehensive tests for the authentication module.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import base64
import json

from web_fetch.auth import (
    AuthConfig,
    AuthMethod,
    AuthResult,
    APIKeyAuth,
    APIKeyConfig,
    BasicAuth,
    BasicAuthConfig,
    BearerTokenAuth,
    BearerTokenConfig,
    CustomAuth,
    CustomAuthConfig,
    JWTAuth,
    JWTConfig,
    OAuth2Auth,
    OAuth2Config,
    AuthManager,
)
from web_fetch.auth.base import AuthType, AuthLocation
from web_fetch.exceptions import WebFetchError


class TestAPIKeyAuth:
    """Test API Key authentication."""

    def test_api_key_config_creation(self):
        """Test API key configuration creation."""
        config = APIKeyConfig(
            api_key="test-key",
            key_name="X-API-Key",
            location=AuthLocation.HEADER
        )
        assert config.api_key == "test-key"
        assert config.key_name == "X-API-Key"
        assert config.location == AuthLocation.HEADER
        assert config.auth_type == AuthType.API_KEY

    @pytest.mark.asyncio
    async def test_api_key_header_auth(self):
        """Test API key authentication in header."""
        config = APIKeyConfig(
            api_key="test-key",
            key_name="X-API-Key",
            location=AuthLocation.HEADER
        )
        auth = APIKeyAuth(config)
        
        result = await auth.authenticate()
        
        assert result.success is True
        assert result.headers == {"X-API-Key": "test-key"}
        assert result.params == {}
        assert result.body_data is None

    @pytest.mark.asyncio
    async def test_api_key_query_auth(self):
        """Test API key authentication in query parameters."""
        config = APIKeyConfig(
            api_key="test-key",
            key_name="api_key",
            location=AuthLocation.QUERY
        )
        auth = APIKeyAuth(config)
        
        result = await auth.authenticate()
        
        assert result.success is True
        assert result.params == {"api_key": "test-key"}
        assert result.headers == {}

    @pytest.mark.asyncio
    async def test_api_key_with_prefix(self):
        """Test API key authentication with prefix."""
        config = APIKeyConfig(
            api_key="test-key",
            key_name="Authorization",
            location=AuthLocation.HEADER,
            prefix="Bearer"
        )
        auth = APIKeyAuth(config)
        
        result = await auth.authenticate()
        
        assert result.success is True
        assert result.headers == {"Authorization": "Bearer test-key"}

    @pytest.mark.asyncio
    async def test_api_key_missing_key(self):
        """Test API key authentication with missing key."""
        config = APIKeyConfig(
            api_key="",
            key_name="X-API-Key",
            location=AuthLocation.HEADER
        )
        auth = APIKeyAuth(config)
        
        result = await auth.authenticate()
        
        assert result.success is False
        assert "API key is required" in result.error

    def test_api_key_validation(self):
        """Test API key configuration validation."""
        config = APIKeyConfig(
            api_key="test-key",
            key_name="X-API-Key",
            location=AuthLocation.HEADER
        )
        auth = APIKeyAuth(config)
        
        assert auth.validate_config() is True
        
        # Test invalid config
        config.api_key = ""
        assert auth.validate_config() is False


class TestBasicAuth:
    """Test Basic HTTP authentication."""

    @pytest.mark.asyncio
    async def test_basic_auth_success(self):
        """Test successful basic authentication."""
        config = BasicAuthConfig(
            username="testuser",
            password="testpass"
        )
        auth = BasicAuth(config)
        
        result = await auth.authenticate()
        
        assert result.success is True
        assert "Authorization" in result.headers
        
        # Decode and verify the credentials
        auth_header = result.headers["Authorization"]
        assert auth_header.startswith("Basic ")
        
        encoded_creds = auth_header.split(" ")[1]
        decoded_creds = base64.b64decode(encoded_creds).decode("utf-8")
        assert decoded_creds == "testuser:testpass"

    @pytest.mark.asyncio
    async def test_basic_auth_missing_credentials(self):
        """Test basic authentication with missing credentials."""
        config = BasicAuthConfig(
            username="",
            password="testpass"
        )
        auth = BasicAuth(config)
        
        result = await auth.authenticate()
        
        assert result.success is False
        assert "Username and password are required" in result.error


class TestBearerTokenAuth:
    """Test Bearer token authentication."""

    @pytest.mark.asyncio
    async def test_bearer_token_auth(self):
        """Test bearer token authentication."""
        config = BearerTokenConfig(token="test-token")
        auth = BearerTokenAuth(config)
        
        result = await auth.authenticate()
        
        assert result.success is True
        assert result.headers == {"Authorization": "Bearer test-token"}

    @pytest.mark.asyncio
    async def test_bearer_token_custom_header(self):
        """Test bearer token with custom header name."""
        config = BearerTokenConfig(
            token="test-token",
            header_name="X-Auth-Token"
        )
        auth = BearerTokenAuth(config)
        
        result = await auth.authenticate()
        
        assert result.success is True
        assert result.headers == {"X-Auth-Token": "Bearer test-token"}

    @pytest.mark.asyncio
    async def test_bearer_token_missing(self):
        """Test bearer token authentication with missing token."""
        config = BearerTokenConfig(token="")
        auth = BearerTokenAuth(config)
        
        result = await auth.authenticate()
        
        assert result.success is False
        assert "Bearer token is required" in result.error


class TestCustomAuth:
    """Test custom authentication."""

    @pytest.mark.asyncio
    async def test_custom_auth_with_function(self):
        """Test custom authentication with provided function."""
        config = CustomAuthConfig(
            auth_params={"api_key": "test-key"}
        )
        auth = CustomAuth(config)
        
        async def custom_auth_func(auth_params, **kwargs):
            return AuthResult(
                success=True,
                headers={"X-Custom-Auth": auth_params["api_key"]}
            )
        
        auth.set_auth_function(custom_auth_func)
        
        result = await auth.authenticate()
        
        assert result.success is True
        assert result.headers == {"X-Custom-Auth": "test-key"}

    @pytest.mark.asyncio
    async def test_custom_auth_no_function(self):
        """Test custom authentication without function."""
        config = CustomAuthConfig()
        auth = CustomAuth(config)
        
        result = await auth.authenticate()
        
        assert result.success is False
        assert "No custom authentication function provided" in result.error

    def test_custom_auth_param_management(self):
        """Test custom authentication parameter management."""
        config = CustomAuthConfig()
        auth = CustomAuth(config)
        
        # Test adding parameters
        auth.add_auth_param("key1", "value1")
        auth.add_auth_param("key2", "value2")
        
        assert auth.get_auth_param("key1") == "value1"
        assert auth.get_auth_param("key2") == "value2"
        assert auth.get_auth_param("nonexistent", "default") == "default"
        
        # Test removing parameters
        auth.remove_auth_param("key1")
        assert auth.get_auth_param("key1") is None


class TestAuthManager:
    """Test authentication manager."""

    def test_auth_manager_creation(self):
        """Test authentication manager creation."""
        manager = AuthManager()
        assert len(manager._auth_methods) == 0
        assert manager._default_method is None

    def test_add_auth_method(self):
        """Test adding authentication methods."""
        manager = AuthManager()
        
        config = APIKeyConfig(api_key="test-key", key_name="X-API-Key")
        auth = APIKeyAuth(config)
        
        manager.add_auth_method("api", auth)
        
        assert "api" in manager._auth_methods
        assert manager._default_method == "api"

    def test_set_default_method(self):
        """Test setting default authentication method."""
        manager = AuthManager()
        
        config1 = APIKeyConfig(api_key="key1", key_name="X-API-Key")
        config2 = BasicAuthConfig(username="user", password="pass")
        
        manager.add_auth_method("api", APIKeyAuth(config1))
        manager.add_auth_method("basic", BasicAuth(config2))
        
        manager.set_default_method("basic")
        assert manager._default_method == "basic"

    def test_url_pattern_matching(self):
        """Test URL pattern matching for authentication."""
        manager = AuthManager()
        
        config1 = APIKeyConfig(api_key="key1", key_name="X-API-Key")
        config2 = BasicAuthConfig(username="user", password="pass")
        
        manager.add_auth_method("api", APIKeyAuth(config1))
        manager.add_auth_method("basic", BasicAuth(config2))
        
        manager.add_url_pattern("api.example.com", "api")
        manager.add_url_pattern("secure.example.com", "basic")
        
        assert manager.get_auth_method_for_url("https://api.example.com/data") == "api"
        assert manager.get_auth_method_for_url("https://secure.example.com/login") == "basic"
        assert manager.get_auth_method_for_url("https://other.example.com") == "api"  # default

    @pytest.mark.asyncio
    async def test_authenticate_with_method(self):
        """Test authentication with specific method."""
        manager = AuthManager()
        
        config = APIKeyConfig(api_key="test-key", key_name="X-API-Key")
        auth = APIKeyAuth(config)
        
        manager.add_auth_method("api", auth)
        
        result = await manager.authenticate("api")
        
        assert result.success is True
        assert result.headers == {"X-API-Key": "test-key"}

    @pytest.mark.asyncio
    async def test_authenticate_for_url(self):
        """Test authentication for specific URL."""
        manager = AuthManager()
        
        config = APIKeyConfig(api_key="test-key", key_name="X-API-Key")
        auth = APIKeyAuth(config)
        
        manager.add_auth_method("api", auth)
        manager.add_url_pattern("api.example.com", "api")
        
        result = await manager.authenticate_for_url("https://api.example.com/data")
        
        assert result.success is True
        assert result.headers == {"X-API-Key": "test-key"}
