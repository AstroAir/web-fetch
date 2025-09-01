"""
Comprehensive tests for the authenticated API component.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from web_fetch.components.authenticated_api_component import (
    AuthenticatedAPIComponent,
    APIAuthConfig,
    APIEndpoint,
    APIResponse,
)
from web_fetch.auth import AuthManager, APIKeyAuth, APIKeyConfig, OAuth2Auth, OAuth2Config
from web_fetch.models.resource import ResourceRequest, ResourceResult, ResourceKind
from web_fetch.exceptions import HTTPError, AuthenticationError


class TestAPIAuthConfig:
    """Test API authentication configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = APIAuthConfig()
        
        assert config.auth_method == "api_key"
        assert config.retry_on_auth_failure is True
        assert config.max_auth_retries == 3
        assert config.auth_cache_ttl == 3600
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = APIAuthConfig(
            auth_method="oauth2",
            retry_on_auth_failure=False,
            max_auth_retries=5,
            auth_cache_ttl=7200
        )
        
        assert config.auth_method == "oauth2"
        assert config.retry_on_auth_failure is False
        assert config.max_auth_retries == 5
        assert config.auth_cache_ttl == 7200


class TestAPIEndpoint:
    """Test API endpoint configuration."""
    
    def test_endpoint_creation(self):
        """Test API endpoint creation."""
        endpoint = APIEndpoint(
            name="users",
            path="/api/v1/users",
            method="GET",
            auth_required=True
        )
        
        assert endpoint.name == "users"
        assert endpoint.path == "/api/v1/users"
        assert endpoint.method == "GET"
        assert endpoint.auth_required is True
    
    def test_endpoint_url_building(self):
        """Test endpoint URL building."""
        endpoint = APIEndpoint(
            name="user_detail",
            path="/api/v1/users/{user_id}",
            method="GET"
        )
        
        url = endpoint.build_url("https://api.example.com", user_id=123)
        assert url == "https://api.example.com/api/v1/users/123"
    
    def test_endpoint_with_query_params(self):
        """Test endpoint with query parameters."""
        endpoint = APIEndpoint(
            name="search",
            path="/api/v1/search",
            method="GET",
            default_params={"limit": 10, "offset": 0}
        )
        
        url = endpoint.build_url("https://api.example.com", q="test", limit=20)
        assert "q=test" in url
        assert "limit=20" in url
        assert "offset=0" in url


class TestAuthenticatedAPIComponent:
    """Test authenticated API component functionality."""
    
    @pytest.fixture
    def auth_manager(self):
        """Create authentication manager."""
        manager = AuthManager()
        config = APIKeyConfig(api_key="test-api-key", key_name="X-API-Key")
        auth = APIKeyAuth(config)
        manager.add_auth_method("api_key", auth)
        return manager
    
    @pytest.fixture
    def api_config(self):
        """Create API configuration."""
        return APIAuthConfig(auth_method="api_key")
    
    @pytest.fixture
    def component(self, auth_manager, api_config):
        """Create authenticated API component."""
        return AuthenticatedAPIComponent(
            base_url="https://api.example.com",
            auth_manager=auth_manager,
            config=api_config
        )
    
    def test_component_initialization(self, component):
        """Test component initialization."""
        assert component.base_url == "https://api.example.com"
        assert component.auth_manager is not None
        assert component.config.auth_method == "api_key"
        assert len(component.endpoints) == 0
    
    def test_add_endpoint(self, component):
        """Test adding API endpoints."""
        endpoint = APIEndpoint(
            name="users",
            path="/api/v1/users",
            method="GET",
            auth_required=True
        )
        
        component.add_endpoint(endpoint)
        
        assert "users" in component.endpoints
        assert component.endpoints["users"] == endpoint
    
    def test_add_multiple_endpoints(self, component):
        """Test adding multiple endpoints."""
        endpoints = [
            APIEndpoint("users", "/api/v1/users", "GET"),
            APIEndpoint("create_user", "/api/v1/users", "POST"),
            APIEndpoint("user_detail", "/api/v1/users/{id}", "GET"),
        ]
        
        component.add_endpoints(endpoints)
        
        assert len(component.endpoints) == 3
        assert all(ep.name in component.endpoints for ep in endpoints)
    
    @pytest.mark.asyncio
    async def test_fetch_with_authentication(self, component):
        """Test fetching with authentication."""
        # Add endpoint
        endpoint = APIEndpoint("test", "/api/test", "GET", auth_required=True)
        component.add_endpoint(endpoint)
        
        request = ResourceRequest(
            uri="https://api.example.com/api/test",
            kind=ResourceKind.HTTP
        )
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.text.return_value = '{"success": true}'
            mock_response.json.return_value = {"success": True}
            mock_request.return_value.__aenter__.return_value = mock_response
            
            result = await component.fetch(request)
            
            assert result.status_code == 200
            assert result.content["success"] is True
            
            # Verify authentication headers were added
            call_args = mock_request.call_args
            assert "X-API-Key" in call_args[1]["headers"]
            assert call_args[1]["headers"]["X-API-Key"] == "test-api-key"
    
    @pytest.mark.asyncio
    async def test_fetch_without_authentication(self, component):
        """Test fetching without authentication for public endpoints."""
        # Add public endpoint
        endpoint = APIEndpoint("public", "/api/public", "GET", auth_required=False)
        component.add_endpoint(endpoint)
        
        request = ResourceRequest(
            uri="https://api.example.com/api/public",
            kind=ResourceKind.HTTP
        )
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.text.return_value = '{"public": true}'
            mock_response.json.return_value = {"public": True}
            mock_request.return_value.__aenter__.return_value = mock_response
            
            result = await component.fetch(request)
            
            assert result.status_code == 200
            assert result.content["public"] is True
            
            # Verify no authentication headers were added
            call_args = mock_request.call_args
            assert "X-API-Key" not in call_args[1].get("headers", {})
    
    @pytest.mark.asyncio
    async def test_authentication_failure_retry(self, component):
        """Test retry on authentication failure."""
        endpoint = APIEndpoint("protected", "/api/protected", "GET", auth_required=True)
        component.add_endpoint(endpoint)
        
        request = ResourceRequest(
            uri="https://api.example.com/api/protected",
            kind=ResourceKind.HTTP
        )
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            # First call returns 401, second call succeeds
            call_count = 0
            
            def mock_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                
                mock_response = AsyncMock()
                if call_count == 1:
                    mock_response.status = 401
                    mock_response.raise_for_status.side_effect = HTTPError("Unauthorized", 401)
                else:
                    mock_response.status = 200
                    mock_response.headers = {"content-type": "application/json"}
                    mock_response.text.return_value = '{"retry_success": true}'
                    mock_response.json.return_value = {"retry_success": True}
                
                return mock_response
            
            mock_request.side_effect = mock_side_effect
            
            # Mock auth manager to refresh credentials on retry
            with patch.object(component.auth_manager, 'authenticate') as mock_auth:
                mock_auth.return_value = MagicMock(
                    success=True,
                    headers={"X-API-Key": "refreshed-key"}
                )
                
                result = await component.fetch(request)
                
                assert result.status_code == 200
                assert result.content["retry_success"] is True
                assert call_count == 2  # Should have retried once
    
    @pytest.mark.asyncio
    async def test_oauth2_authentication(self):
        """Test OAuth2 authentication flow."""
        # Setup OAuth2 auth manager
        auth_manager = AuthManager()
        oauth_config = OAuth2Config(
            client_id="test-client",
            client_secret="test-secret",
            token_url="https://auth.example.com/token"
        )
        oauth_auth = OAuth2Auth(oauth_config)
        auth_manager.add_auth_method("oauth2", oauth_auth)
        
        api_config = APIAuthConfig(auth_method="oauth2")
        component = AuthenticatedAPIComponent(
            base_url="https://api.example.com",
            auth_manager=auth_manager,
            config=api_config
        )
        
        endpoint = APIEndpoint("oauth_test", "/api/oauth", "GET", auth_required=True)
        component.add_endpoint(endpoint)
        
        request = ResourceRequest(
            uri="https://api.example.com/api/oauth",
            kind=ResourceKind.HTTP
        )
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.text.return_value = '{"oauth_success": true}'
            mock_response.json.return_value = {"oauth_success": True}
            mock_request.return_value.__aenter__.return_value = mock_response
            
            # Mock OAuth2 token response
            with patch.object(oauth_auth, 'authenticate') as mock_oauth:
                mock_oauth.return_value = MagicMock(
                    success=True,
                    headers={"Authorization": "Bearer oauth-token"}
                )
                
                result = await component.fetch(request)
                
                assert result.status_code == 200
                assert result.content["oauth_success"] is True
                
                # Verify OAuth2 headers were added
                call_args = mock_request.call_args
                assert "Authorization" in call_args[1]["headers"]
                assert "Bearer oauth-token" in call_args[1]["headers"]["Authorization"]
    
    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self, component):
        """Test integration with rate limiting."""
        from web_fetch.utils.advanced_rate_limiter import AdvancedRateLimiter, RateLimitConfig
        
        # Setup rate limiter
        rate_config = RateLimitConfig(requests_per_second=2, burst_size=2)
        rate_limiter = AdvancedRateLimiter(rate_config)
        component.set_rate_limiter(rate_limiter)
        
        endpoint = APIEndpoint("limited", "/api/limited", "GET")
        component.add_endpoint(endpoint)
        
        request = ResourceRequest(
            uri="https://api.example.com/api/limited",
            kind=ResourceKind.HTTP
        )
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.text.return_value = '{"limited": true}'
            mock_response.json.return_value = {"limited": True}
            mock_request.return_value.__aenter__.return_value = mock_response
            
            # Should allow first two requests
            result1 = await component.fetch(request)
            result2 = await component.fetch(request)
            
            assert result1.status_code == 200
            assert result2.status_code == 200
            
            # Third request should be rate limited
            with pytest.raises(Exception):  # Rate limit exception
                await asyncio.wait_for(component.fetch(request), timeout=0.1)
    
    def test_get_endpoint_by_name(self, component):
        """Test getting endpoint by name."""
        endpoint = APIEndpoint("test_endpoint", "/api/test", "GET")
        component.add_endpoint(endpoint)
        
        retrieved = component.get_endpoint("test_endpoint")
        assert retrieved == endpoint
        
        # Non-existent endpoint
        assert component.get_endpoint("non_existent") is None
    
    def test_list_endpoints(self, component):
        """Test listing all endpoints."""
        endpoints = [
            APIEndpoint("endpoint1", "/api/1", "GET"),
            APIEndpoint("endpoint2", "/api/2", "POST"),
            APIEndpoint("endpoint3", "/api/3", "PUT"),
        ]
        
        component.add_endpoints(endpoints)
        
        listed = component.list_endpoints()
        assert len(listed) == 3
        assert all(ep.name in [e.name for e in listed] for ep in endpoints)
    
    def test_remove_endpoint(self, component):
        """Test removing endpoints."""
        endpoint = APIEndpoint("to_remove", "/api/remove", "DELETE")
        component.add_endpoint(endpoint)
        
        assert "to_remove" in component.endpoints
        
        removed = component.remove_endpoint("to_remove")
        assert removed == endpoint
        assert "to_remove" not in component.endpoints
        
        # Removing non-existent endpoint
        assert component.remove_endpoint("non_existent") is None
