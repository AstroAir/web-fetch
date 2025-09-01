"""
Comprehensive tests for the HTTP component.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import ClientTimeout, ClientError

from web_fetch.components.http_component import (
    HTTPComponent,
    HTTPConfig,
    HTTPMethod,
    HTTPResponse,
    RequestBuilder,
)
from web_fetch.models.resource import ResourceRequest, ResourceResult, ResourceKind
from web_fetch.models.base import ContentType
from web_fetch.exceptions import HTTPError, NetworkError, TimeoutError


class TestHTTPConfig:
    """Test HTTP configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = HTTPConfig()
        
        assert config.timeout == 30.0
        assert config.max_redirects == 10
        assert config.verify_ssl is True
        assert config.allow_redirects is True
        assert config.user_agent.startswith("web-fetch")
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = HTTPConfig(
            timeout=60.0,
            max_redirects=5,
            verify_ssl=False,
            allow_redirects=False,
            user_agent="Custom Agent/1.0"
        )
        
        assert config.timeout == 60.0
        assert config.max_redirects == 5
        assert config.verify_ssl is False
        assert config.allow_redirects is False
        assert config.user_agent == "Custom Agent/1.0"
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Invalid timeout
        with pytest.raises(ValueError, match="timeout must be positive"):
            HTTPConfig(timeout=0)
        
        # Invalid max_redirects
        with pytest.raises(ValueError, match="max_redirects must be non-negative"):
            HTTPConfig(max_redirects=-1)


class TestRequestBuilder:
    """Test HTTP request builder."""
    
    def test_build_basic_request(self):
        """Test building basic HTTP request."""
        builder = RequestBuilder()
        
        request_data = builder.build(
            method=HTTPMethod.GET,
            url="https://example.com/api",
            headers={"Accept": "application/json"}
        )
        
        assert request_data["method"] == "GET"
        assert request_data["url"] == "https://example.com/api"
        assert request_data["headers"]["Accept"] == "application/json"
    
    def test_build_post_request_with_json(self):
        """Test building POST request with JSON data."""
        builder = RequestBuilder()
        
        data = {"name": "test", "value": 123}
        request_data = builder.build(
            method=HTTPMethod.POST,
            url="https://example.com/api",
            json=data
        )
        
        assert request_data["method"] == "POST"
        assert request_data["json"] == data
        assert request_data["headers"]["Content-Type"] == "application/json"
    
    def test_build_request_with_form_data(self):
        """Test building request with form data."""
        builder = RequestBuilder()
        
        form_data = {"field1": "value1", "field2": "value2"}
        request_data = builder.build(
            method=HTTPMethod.POST,
            url="https://example.com/form",
            data=form_data
        )
        
        assert request_data["method"] == "POST"
        assert request_data["data"] == form_data
        assert "application/x-www-form-urlencoded" in request_data["headers"]["Content-Type"]
    
    def test_build_request_with_files(self):
        """Test building request with file uploads."""
        builder = RequestBuilder()
        
        files = {"file": ("test.txt", b"file content", "text/plain")}
        request_data = builder.build(
            method=HTTPMethod.POST,
            url="https://example.com/upload",
            files=files
        )
        
        assert request_data["method"] == "POST"
        assert "file" in request_data["data"]
        assert "multipart/form-data" in request_data["headers"]["Content-Type"]
    
    def test_build_request_with_auth(self):
        """Test building request with authentication."""
        builder = RequestBuilder()
        
        request_data = builder.build(
            method=HTTPMethod.GET,
            url="https://example.com/protected",
            auth=("username", "password")
        )
        
        assert request_data["auth"] == ("username", "password")
    
    def test_build_request_with_cookies(self):
        """Test building request with cookies."""
        builder = RequestBuilder()
        
        cookies = {"session": "abc123", "preference": "dark"}
        request_data = builder.build(
            method=HTTPMethod.GET,
            url="https://example.com",
            cookies=cookies
        )
        
        assert request_data["cookies"] == cookies
    
    def test_build_request_with_proxy(self):
        """Test building request with proxy."""
        builder = RequestBuilder()
        
        request_data = builder.build(
            method=HTTPMethod.GET,
            url="https://example.com",
            proxy="http://proxy.example.com:8080"
        )
        
        assert request_data["proxy"] == "http://proxy.example.com:8080"


class TestHTTPComponent:
    """Test HTTP component functionality."""
    
    @pytest.fixture
    def config(self):
        """Create HTTP configuration."""
        return HTTPConfig(timeout=10.0, max_redirects=5)
    
    @pytest.fixture
    def component(self, config):
        """Create HTTP component."""
        return HTTPComponent(config)
    
    def test_component_initialization(self, component):
        """Test component initialization."""
        assert component.config.timeout == 10.0
        assert component.config.max_redirects == 5
        assert component.session is None  # Lazy initialization
    
    @pytest.mark.asyncio
    async def test_session_creation(self, component):
        """Test HTTP session creation."""
        session = await component._get_session()
        
        assert session is not None
        assert isinstance(session.timeout, ClientTimeout)
        assert session.timeout.total == 10.0
        
        # Should reuse same session
        session2 = await component._get_session()
        assert session is session2
    
    @pytest.mark.asyncio
    async def test_fetch_get_request(self, component):
        """Test GET request."""
        request = ResourceRequest(
            uri="https://httpbin.org/json",
            kind=ResourceKind.HTTP,
            method="GET"
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
            assert result.content_type == ContentType.JSON
            
            # Verify request was made correctly
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[0][0] == "GET"
            assert call_args[0][1] == "https://httpbin.org/json"
    
    @pytest.mark.asyncio
    async def test_fetch_post_request_with_json(self, component):
        """Test POST request with JSON data."""
        request = ResourceRequest(
            uri="https://httpbin.org/post",
            kind=ResourceKind.HTTP,
            method="POST",
            data={"name": "test", "value": 123},
            headers={"Content-Type": "application/json"}
        )
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 201
            mock_response.headers = {"content-type": "application/json"}
            mock_response.text.return_value = '{"created": true}'
            mock_response.json.return_value = {"created": True}
            mock_request.return_value.__aenter__.return_value = mock_response
            
            result = await component.fetch(request)
            
            assert result.status_code == 201
            assert result.content["created"] is True
            
            # Verify JSON data was sent
            call_args = mock_request.call_args
            assert "json" in call_args[1]
            assert call_args[1]["json"] == {"name": "test", "value": 123}
    
    @pytest.mark.asyncio
    async def test_fetch_with_custom_headers(self, component):
        """Test request with custom headers."""
        request = ResourceRequest(
            uri="https://api.example.com/data",
            kind=ResourceKind.HTTP,
            headers={
                "Authorization": "Bearer token123",
                "X-Custom-Header": "custom-value",
                "Accept": "application/json"
            }
        )
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.text.return_value = '{"data": "response"}'
            mock_response.json.return_value = {"data": "response"}
            mock_request.return_value.__aenter__.return_value = mock_response
            
            result = await component.fetch(request)
            
            assert result.status_code == 200
            
            # Verify custom headers were sent
            call_args = mock_request.call_args
            headers = call_args[1]["headers"]
            assert headers["Authorization"] == "Bearer token123"
            assert headers["X-Custom-Header"] == "custom-value"
            assert headers["Accept"] == "application/json"
    
    @pytest.mark.asyncio
    async def test_fetch_with_query_parameters(self, component):
        """Test request with query parameters."""
        request = ResourceRequest(
            uri="https://api.example.com/search",
            kind=ResourceKind.HTTP,
            params={"q": "python", "limit": 10, "offset": 0}
        )
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.text.return_value = '{"results": []}'
            mock_response.json.return_value = {"results": []}
            mock_request.return_value.__aenter__.return_value = mock_response
            
            result = await component.fetch(request)
            
            assert result.status_code == 200
            
            # Verify query parameters were sent
            call_args = mock_request.call_args
            assert "params" in call_args[1]
            assert call_args[1]["params"]["q"] == "python"
            assert call_args[1]["params"]["limit"] == 10
    
    @pytest.mark.asyncio
    async def test_fetch_handles_redirects(self, component):
        """Test handling of HTTP redirects."""
        request = ResourceRequest(
            uri="https://example.com/redirect",
            kind=ResourceKind.HTTP
        )
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            # First response is redirect
            redirect_response = AsyncMock()
            redirect_response.status = 302
            redirect_response.headers = {"location": "https://example.com/final"}
            
            # Final response
            final_response = AsyncMock()
            final_response.status = 200
            final_response.headers = {"content-type": "text/html"}
            final_response.text.return_value = "<html>Final page</html>"
            
            mock_request.return_value.__aenter__.return_value = final_response
            
            result = await component.fetch(request)
            
            assert result.status_code == 200
            assert "Final page" in result.content
    
    @pytest.mark.asyncio
    async def test_fetch_handles_timeout(self, component):
        """Test handling of request timeout."""
        request = ResourceRequest(
            uri="https://slow.example.com",
            kind=ResourceKind.HTTP
        )
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.side_effect = asyncio.TimeoutError("Request timed out")
            
            with pytest.raises(TimeoutError):
                await component.fetch(request)
    
    @pytest.mark.asyncio
    async def test_fetch_handles_network_error(self, component):
        """Test handling of network errors."""
        request = ResourceRequest(
            uri="https://nonexistent.example.com",
            kind=ResourceKind.HTTP
        )
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.side_effect = ClientError("Connection failed")
            
            with pytest.raises(NetworkError):
                await component.fetch(request)
    
    @pytest.mark.asyncio
    async def test_fetch_handles_http_error(self, component):
        """Test handling of HTTP errors."""
        request = ResourceRequest(
            uri="https://example.com/not-found",
            kind=ResourceKind.HTTP
        )
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 404
            mock_response.headers = {"content-type": "text/html"}
            mock_response.text.return_value = "Not Found"
            mock_response.raise_for_status.side_effect = HTTPError("Not Found", 404)
            mock_request.return_value.__aenter__.return_value = mock_response
            
            with pytest.raises(HTTPError) as exc_info:
                await component.fetch(request)
            
            assert exc_info.value.status_code == 404
    
    @pytest.mark.asyncio
    async def test_fetch_different_content_types(self, component):
        """Test fetching different content types."""
        test_cases = [
            ("application/json", '{"json": true}', ContentType.JSON),
            ("text/html", "<html><body>HTML</body></html>", ContentType.HTML),
            ("text/xml", "<?xml version='1.0'?><root></root>", ContentType.XML),
            ("text/plain", "Plain text content", ContentType.TEXT),
            ("image/jpeg", b"fake-jpeg-data", ContentType.BINARY),
        ]
        
        for content_type, content, expected_type in test_cases:
            request = ResourceRequest(
                uri=f"https://example.com/{expected_type.value}",
                kind=ResourceKind.HTTP
            )
            
            with patch('aiohttp.ClientSession.request') as mock_request:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.headers = {"content-type": content_type}
                
                if expected_type == ContentType.BINARY:
                    mock_response.read.return_value = content
                else:
                    mock_response.text.return_value = content
                    if expected_type == ContentType.JSON:
                        mock_response.json.return_value = {"json": True}
                
                mock_request.return_value.__aenter__.return_value = mock_response
                
                result = await component.fetch(request)
                
                assert result.status_code == 200
                assert result.content_type == expected_type
    
    @pytest.mark.asyncio
    async def test_component_cleanup(self, component):
        """Test component cleanup."""
        # Create session
        session = await component._get_session()
        assert session is not None
        
        # Cleanup should close session
        await component.cleanup()
        assert component.session is None
    
    def test_cache_key_generation(self, component):
        """Test cache key generation."""
        request = ResourceRequest(
            uri="https://example.com/api?param=value",
            kind=ResourceKind.HTTP,
            method="GET",
            headers={"Accept": "application/json"}
        )
        
        cache_key = component.cache_key(request)
        
        assert isinstance(cache_key, str)
        assert len(cache_key) > 0
        assert "GET" in cache_key
        assert "example.com" in cache_key
    
    def test_cache_ttl(self, component):
        """Test cache TTL calculation."""
        request = ResourceRequest(
            uri="https://example.com/api",
            kind=ResourceKind.HTTP
        )
        
        ttl = component.cache_ttl(request)
        
        assert isinstance(ttl, int)
        assert ttl > 0
    
    def test_cache_tags(self, component):
        """Test cache tags generation."""
        request = ResourceRequest(
            uri="https://api.example.com/users",
            kind=ResourceKind.HTTP
        )
        
        tags = component.cache_tags(request)
        
        assert isinstance(tags, set)
        assert "http" in tags
        assert "api.example.com" in tags
