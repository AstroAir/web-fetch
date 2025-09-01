"""
Parameterized tests for comprehensive coverage of input variations.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from typing import Dict, Any, List, Tuple

from web_fetch import WebFetcher, FetchConfig
from web_fetch.models import FetchResult, ContentType
from web_fetch.auth import APIKeyAuth, APIKeyConfig, BasicAuth, BasicAuthConfig
from web_fetch.exceptions import HTTPError, NetworkError, TimeoutError
from web_fetch.url_utils import is_valid_url, normalize_url, detect_content_type


class TestParameterizedURLValidation:
    """Parameterized tests for URL validation."""
    
    @pytest.mark.parametrize("url,expected", [
        ("https://example.com", True),
        ("http://example.com", True),
        ("https://example.com/path", True),
        ("https://example.com:8080", True),
        ("https://subdomain.example.com", True),
        ("ftp://ftp.example.com", True),
        ("https://example.com/path?query=value", True),
        ("https://example.com/path#fragment", True),
        ("https://192.168.1.1", True),
        ("https://[::1]:8080", True),
        ("", False),
        ("not-a-url", False),
        ("http://", False),
        ("://example.com", False),
        ("example.com", False),
        ("http:///path", False),
        ("javascript:alert('xss')", False),
        ("data:text/html,<script>alert('xss')</script>", False),
    ])
    def test_url_validation(self, url: str, expected: bool):
        """Test URL validation with various inputs."""
        assert is_valid_url(url) == expected
    
    @pytest.mark.parametrize("input_url,expected_url", [
        ("https://EXAMPLE.COM", "https://example.com"),
        ("https://example.com//path//", "https://example.com/path/"),
        ("https://example.com:443/path", "https://example.com/path"),
        ("http://example.com:80/path", "http://example.com/path"),
        ("https://example.com/path?b=2&a=1", "https://example.com/path?a=1&b=2"),
        ("https://example.com/path/../other", "https://example.com/other"),
        ("https://example.com/path/./file", "https://example.com/path/file"),
    ])
    def test_url_normalization(self, input_url: str, expected_url: str):
        """Test URL normalization with various inputs."""
        assert normalize_url(input_url) == expected_url


class TestParameterizedContentTypeDetection:
    """Parameterized tests for content type detection."""
    
    @pytest.mark.parametrize("headers,expected", [
        ({"content-type": "application/json"}, ContentType.JSON),
        ({"content-type": "application/json; charset=utf-8"}, ContentType.JSON),
        ({"Content-Type": "text/html"}, ContentType.HTML),
        ({"CONTENT-TYPE": "text/xml"}, ContentType.XML),
        ({"content-type": "text/plain"}, ContentType.TEXT),
        ({"content-type": "application/octet-stream"}, ContentType.BINARY),
        ({"content-type": "image/jpeg"}, ContentType.BINARY),
        ({"content-type": "application/pdf"}, ContentType.BINARY),
        ({}, ContentType.TEXT),  # Default fallback
    ])
    def test_content_type_from_headers(self, headers: Dict[str, str], expected: ContentType):
        """Test content type detection from headers."""
        assert detect_content_type(headers=headers) == expected
    
    @pytest.mark.parametrize("url,expected", [
        ("https://example.com/data.json", ContentType.JSON),
        ("https://example.com/page.html", ContentType.HTML),
        ("https://example.com/page.htm", ContentType.HTML),
        ("https://example.com/document.xml", ContentType.XML),
        ("https://example.com/file.txt", ContentType.TEXT),
        ("https://example.com/image.jpg", ContentType.BINARY),
        ("https://example.com/image.png", ContentType.BINARY),
        ("https://example.com/document.pdf", ContentType.BINARY),
        ("https://example.com/archive.zip", ContentType.BINARY),
        ("https://example.com/unknown", ContentType.TEXT),  # Default fallback
    ])
    def test_content_type_from_url(self, url: str, expected: ContentType):
        """Test content type detection from URL extensions."""
        assert detect_content_type(url=url) == expected
    
    @pytest.mark.parametrize("content,expected", [
        ('{"key": "value"}', ContentType.JSON),
        ('[{"item": 1}]', ContentType.JSON),
        ("<html><body>Test</body></html>", ContentType.HTML),
        ("<!DOCTYPE html><html></html>", ContentType.HTML),
        ('<?xml version="1.0"?><root></root>', ContentType.XML),
        ("<root><item>test</item></root>", ContentType.XML),
        ("Plain text content", ContentType.TEXT),
        ("", ContentType.TEXT),  # Empty content
    ])
    def test_content_type_from_content(self, content: str, expected: ContentType):
        """Test content type detection from content analysis."""
        assert detect_content_type(content=content) == expected


class TestParameterizedHTTPStatusCodes:
    """Parameterized tests for HTTP status code handling."""
    
    @pytest.mark.parametrize("status_code,expected_success", [
        (200, True),
        (201, True),
        (202, True),
        (204, True),
        (301, True),  # Redirect, but considered success
        (302, True),
        (304, True),  # Not Modified
        (400, False),
        (401, False),
        (403, False),
        (404, False),
        (429, False),
        (500, False),
        (502, False),
        (503, False),
    ])
    @pytest.mark.asyncio
    async def test_status_code_handling(self, status_code: int, expected_success: bool):
        """Test handling of various HTTP status codes."""
        config = FetchConfig(total_timeout=10.0)
        
        async with WebFetcher(config) as fetcher:
            with patch('aiohttp.ClientSession.request') as mock_request:
                mock_response = AsyncMock()
                mock_response.status = status_code
                mock_response.headers = {"content-type": "text/plain"}
                mock_response.text.return_value = f"Status {status_code}"
                
                if not expected_success and status_code >= 400:
                    mock_response.raise_for_status.side_effect = HTTPError(
                        f"HTTP {status_code}", status_code
                    )
                
                mock_request.return_value.__aenter__.return_value = mock_response
                
                if expected_success:
                    result = await fetcher.fetch_single("https://example.com/test")
                    assert result.status_code == status_code
                else:
                    with pytest.raises(HTTPError):
                        await fetcher.fetch_single("https://example.com/test")


class TestParameterizedAuthenticationMethods:
    """Parameterized tests for authentication methods."""
    
    @pytest.mark.parametrize("auth_config,expected_header", [
        (
            APIKeyConfig(api_key="test-key", key_name="X-API-Key"),
            ("X-API-Key", "test-key")
        ),
        (
            APIKeyConfig(api_key="secret-123", key_name="Authorization", prefix="Bearer"),
            ("Authorization", "Bearer secret-123")
        ),
        (
            APIKeyConfig(api_key="custom-token", key_name="X-Custom-Auth", prefix="Token"),
            ("X-Custom-Auth", "Token custom-token")
        ),
    ])
    @pytest.mark.asyncio
    async def test_api_key_auth_variations(self, auth_config: APIKeyConfig, expected_header: Tuple[str, str]):
        """Test API key authentication with various configurations."""
        auth = APIKeyAuth(auth_config)
        result = await auth.authenticate()
        
        assert result.success is True
        header_name, expected_value = expected_header
        assert header_name in result.headers
        assert result.headers[header_name] == expected_value
    
    @pytest.mark.parametrize("username,password", [
        ("user", "pass"),
        ("admin", "secret123"),
        ("test@example.com", "complex!password#123"),
        ("user_with_underscore", "pass-with-dash"),
    ])
    @pytest.mark.asyncio
    async def test_basic_auth_variations(self, username: str, password: str):
        """Test basic authentication with various credentials."""
        import base64
        
        config = BasicAuthConfig(username=username, password=password)
        auth = BasicAuth(config)
        result = await auth.authenticate()
        
        assert result.success is True
        assert "Authorization" in result.headers
        
        # Verify credentials encoding
        auth_header = result.headers["Authorization"]
        assert auth_header.startswith("Basic ")
        
        encoded_creds = auth_header.split(" ")[1]
        decoded_creds = base64.b64decode(encoded_creds).decode("utf-8")
        assert decoded_creds == f"{username}:{password}"


class TestParameterizedErrorScenarios:
    """Parameterized tests for error scenarios."""
    
    @pytest.mark.parametrize("exception_type,exception_args,expected_error_type", [
        (ConnectionError, ("Connection refused",), NetworkError),
        (TimeoutError, ("Request timed out",), TimeoutError),
        (OSError, ("Network unreachable",), NetworkError),
        (ValueError, ("Invalid URL",), ValueError),
    ])
    @pytest.mark.asyncio
    async def test_exception_handling(
        self, 
        exception_type: type, 
        exception_args: tuple, 
        expected_error_type: type
    ):
        """Test handling of various exception types."""
        config = FetchConfig(total_timeout=10.0, max_retries=0)
        
        async with WebFetcher(config) as fetcher:
            with patch('aiohttp.ClientSession.request') as mock_request:
                mock_request.side_effect = exception_type(*exception_args)
                
                with pytest.raises(expected_error_type):
                    await fetcher.fetch_single("https://example.com/error")


class TestParameterizedRetryScenarios:
    """Parameterized tests for retry scenarios."""
    
    @pytest.mark.parametrize("max_retries,fail_count,should_succeed", [
        (0, 1, False),  # No retries, should fail
        (1, 1, True),   # 1 retry, fail once then succeed
        (2, 2, True),   # 2 retries, fail twice then succeed
        (3, 4, False),  # 3 retries, fail 4 times, should still fail
        (5, 3, True),   # 5 retries, fail 3 times then succeed
    ])
    @pytest.mark.asyncio
    async def test_retry_behavior(self, max_retries: int, fail_count: int, should_succeed: bool):
        """Test retry behavior with various configurations."""
        config = FetchConfig(
            total_timeout=30.0,
            max_retries=max_retries,
            retry_delay=0.01  # Fast retries for testing
        )
        
        async with WebFetcher(config) as fetcher:
            with patch('aiohttp.ClientSession.request') as mock_request:
                call_count = 0
                
                def mock_side_effect(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    
                    if call_count <= fail_count:
                        raise NetworkError("Simulated network error")
                    else:
                        mock_response = AsyncMock()
                        mock_response.status = 200
                        mock_response.headers = {"content-type": "text/plain"}
                        mock_response.text.return_value = "Success after retries"
                        return mock_response
                
                mock_request.side_effect = mock_side_effect
                
                if should_succeed:
                    result = await fetcher.fetch_single("https://example.com/retry")
                    assert result.status_code == 200
                    assert result.content == "Success after retries"
                    assert call_count == fail_count + 1  # Failed attempts + successful attempt
                else:
                    with pytest.raises(NetworkError):
                        await fetcher.fetch_single("https://example.com/retry")
                    assert call_count == max_retries + 1  # Initial attempt + retries


class TestParameterizedConfigurationOptions:
    """Parameterized tests for configuration options."""
    
    @pytest.mark.parametrize("config_params,expected_behavior", [
        (
            {"max_concurrent_requests": 1, "total_timeout": 10.0},
            "sequential_processing"
        ),
        (
            {"max_concurrent_requests": 10, "total_timeout": 5.0},
            "concurrent_processing"
        ),
        (
            {"verify_ssl": False, "follow_redirects": False},
            "insecure_no_redirects"
        ),
        (
            {"verify_ssl": True, "follow_redirects": True},
            "secure_with_redirects"
        ),
    ])
    @pytest.mark.asyncio
    async def test_configuration_variations(self, config_params: Dict[str, Any], expected_behavior: str):
        """Test various configuration combinations."""
        config = FetchConfig(**config_params)
        
        async with WebFetcher(config) as fetcher:
            # Verify configuration is applied
            assert fetcher.config.max_concurrent_requests == config_params.get("max_concurrent_requests", 50)
            assert fetcher.config.total_timeout == config_params.get("total_timeout", 30.0)
            
            if "verify_ssl" in config_params:
                assert fetcher.config.verify_ssl == config_params["verify_ssl"]
            
            if "follow_redirects" in config_params:
                assert fetcher.config.follow_redirects == config_params["follow_redirects"]
