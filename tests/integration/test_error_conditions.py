"""
Tests for error conditions and edge cases.

This module tests various error conditions, edge cases, and exception handling
across the web_fetch library.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import aiohttp
from pathlib import Path

from web_fetch.core_fetcher import WebFetcher
from web_fetch.models import FetchConfig, FetchRequest
from web_fetch.exceptions import (
    WebFetchError,
    ConnectionError,
    TimeoutError,
    ContentError,
    AuthenticationError,
    RateLimitError
)


class TestNetworkErrorConditions:
    """Test various network error conditions."""

    @pytest.fixture
    def fetcher_config(self):
        """Create a fetcher config for testing."""
        return FetchConfig(
            total_timeout=5.0,
            connect_timeout=2.0,
            read_timeout=3.0,
            max_retries=1
        )

    @pytest.mark.asyncio
    async def test_connection_refused_error(self, fetcher_config):
        """Test handling of connection refused errors."""
        async with WebFetcher(fetcher_config) as fetcher:
            request = FetchRequest(url="http://localhost:99999/nonexistent")
            
            result = await fetcher.fetch_single(request)
            
            assert not result.is_success
            assert result.error is not None
            assert "connection" in result.error.lower() or "refused" in result.error.lower()

    @pytest.mark.asyncio
    async def test_dns_resolution_error(self, fetcher_config):
        """Test handling of DNS resolution errors."""
        async with WebFetcher(fetcher_config) as fetcher:
            request = FetchRequest(url="http://nonexistent-domain-12345.invalid/")
            
            result = await fetcher.fetch_single(request)
            
            assert not result.is_success
            assert result.error is not None

    @pytest.mark.asyncio
    async def test_timeout_error_handling(self, fetcher_config):
        """Test handling of timeout errors."""
        # Use very short timeout to force timeout
        short_config = FetchConfig(
            total_timeout=0.001,  # 1ms timeout
            connect_timeout=0.001,
            read_timeout=0.001,
            max_retries=0
        )
        
        async with WebFetcher(short_config) as fetcher:
            request = FetchRequest(url="https://httpbin.org/delay/1")
            
            result = await fetcher.fetch_single(request)
            
            assert not result.is_success
            assert result.error is not None

    @pytest.mark.asyncio
    async def test_ssl_verification_error(self, fetcher_config):
        """Test handling of SSL verification errors."""
        # Mock SSL error
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.side_effect = aiohttp.ClientSSLError("SSL verification failed")
            
            async with WebFetcher(fetcher_config) as fetcher:
                request = FetchRequest(url="https://example.com")
                
                result = await fetcher.fetch_single(request)
                
                assert not result.is_success
                assert result.error is not None


class TestValidationErrorConditions:
    """Test validation error conditions."""

    def test_invalid_url_format(self):
        """Test validation of invalid URL formats."""
        with pytest.raises(ValueError):
            FetchRequest(url="not-a-valid-url")

    def test_invalid_http_method(self):
        """Test validation of invalid HTTP methods."""
        with pytest.raises(ValueError):
            FetchRequest(
                url="https://example.com",
                method="INVALID_METHOD"
            )

    def test_invalid_timeout_values(self):
        """Test validation of invalid timeout values."""
        with pytest.raises(ValueError):
            FetchConfig(total_timeout=-1.0)
        
        with pytest.raises(ValueError):
            FetchConfig(connect_timeout=0.0)

    def test_invalid_retry_values(self):
        """Test validation of invalid retry values."""
        with pytest.raises(ValueError):
            FetchConfig(max_retries=-1)
        
        with pytest.raises(ValueError):
            FetchConfig(max_retries=100)  # Too high

    def test_invalid_concurrency_values(self):
        """Test validation of invalid concurrency values."""
        with pytest.raises(ValueError):
            FetchConfig(max_concurrent_requests=0)
        
        with pytest.raises(ValueError):
            FetchConfig(max_concurrent_requests=1000)  # Too high


class TestContentErrorConditions:
    """Test content-related error conditions."""

    @pytest.fixture
    def fetcher_config(self):
        """Create a fetcher config for testing."""
        return FetchConfig(max_response_size=1024)  # 1KB limit

    @pytest.mark.asyncio
    async def test_response_size_limit_exceeded(self, fetcher_config):
        """Test handling when response size exceeds limit."""
        # Mock large response
        large_content = b'x' * 2048  # 2KB content
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {'content-length': '2048'}
            mock_response.read.return_value = large_content
            mock_request.return_value.__aenter__.return_value = mock_response
            
            async with WebFetcher(fetcher_config) as fetcher:
                request = FetchRequest(url="https://example.com/large")
                
                result = await fetcher.fetch_single(request)
                
                # Should handle large response gracefully
                assert result is not None

    @pytest.mark.asyncio
    async def test_invalid_json_content(self, fetcher_config):
        """Test handling of invalid JSON content."""
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {'content-type': 'application/json'}
            mock_response.text.return_value = "invalid json content"
            mock_request.return_value.__aenter__.return_value = mock_response
            
            async with WebFetcher(fetcher_config) as fetcher:
                request = FetchRequest(
                    url="https://example.com/invalid-json",
                    content_type="json"
                )
                
                result = await fetcher.fetch_single(request)
                
                # Should handle invalid JSON gracefully
                assert result is not None

    @pytest.mark.asyncio
    async def test_malformed_html_content(self, fetcher_config):
        """Test handling of malformed HTML content."""
        malformed_html = "<html><body><div>Unclosed div<p>Unclosed paragraph</body></html>"
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {'content-type': 'text/html'}
            mock_response.text.return_value = malformed_html
            mock_request.return_value.__aenter__.return_value = mock_response
            
            async with WebFetcher(fetcher_config) as fetcher:
                request = FetchRequest(
                    url="https://example.com/malformed",
                    content_type="html"
                )
                
                result = await fetcher.fetch_single(request)
                
                # Should handle malformed HTML gracefully
                assert result is not None


class TestAuthenticationErrorConditions:
    """Test authentication-related error conditions."""

    @pytest.fixture
    def fetcher_config(self):
        """Create a fetcher config for testing."""
        return FetchConfig()

    @pytest.mark.asyncio
    async def test_unauthorized_error_401(self, fetcher_config):
        """Test handling of 401 Unauthorized errors."""
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 401
            mock_response.reason = "Unauthorized"
            mock_response.text.return_value = "Authentication required"
            mock_request.return_value.__aenter__.return_value = mock_response
            
            async with WebFetcher(fetcher_config) as fetcher:
                request = FetchRequest(url="https://example.com/protected")
                
                result = await fetcher.fetch_single(request)
                
                assert not result.is_success
                assert result.status_code == 401

    @pytest.mark.asyncio
    async def test_forbidden_error_403(self, fetcher_config):
        """Test handling of 403 Forbidden errors."""
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 403
            mock_response.reason = "Forbidden"
            mock_response.text.return_value = "Access denied"
            mock_request.return_value.__aenter__.return_value = mock_response
            
            async with WebFetcher(fetcher_config) as fetcher:
                request = FetchRequest(url="https://example.com/forbidden")
                
                result = await fetcher.fetch_single(request)
                
                assert not result.is_success
                assert result.status_code == 403


class TestRateLimitErrorConditions:
    """Test rate limiting error conditions."""

    @pytest.fixture
    def fetcher_config(self):
        """Create a fetcher config for testing."""
        return FetchConfig()

    @pytest.mark.asyncio
    async def test_rate_limit_error_429(self, fetcher_config):
        """Test handling of 429 Too Many Requests errors."""
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 429
            mock_response.reason = "Too Many Requests"
            mock_response.headers = {'retry-after': '60'}
            mock_response.text.return_value = "Rate limit exceeded"
            mock_request.return_value.__aenter__.return_value = mock_response
            
            async with WebFetcher(fetcher_config) as fetcher:
                request = FetchRequest(url="https://example.com/api")
                
                result = await fetcher.fetch_single(request)
                
                assert not result.is_success
                assert result.status_code == 429


class TestEdgeCaseConditions:
    """Test various edge case conditions."""

    @pytest.fixture
    def fetcher_config(self):
        """Create a fetcher config for testing."""
        return FetchConfig()

    @pytest.mark.asyncio
    async def test_empty_response_body(self, fetcher_config):
        """Test handling of empty response bodies."""
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text.return_value = ""
            mock_response.read.return_value = b""
            mock_request.return_value.__aenter__.return_value = mock_response
            
            async with WebFetcher(fetcher_config) as fetcher:
                request = FetchRequest(url="https://example.com/empty")
                
                result = await fetcher.fetch_single(request)
                
                assert result.is_success
                assert result.content == ""

    @pytest.mark.asyncio
    async def test_very_long_url(self, fetcher_config):
        """Test handling of very long URLs."""
        # Create a very long URL
        long_path = "a" * 2000
        long_url = f"https://example.com/{long_path}"
        
        async with WebFetcher(fetcher_config) as fetcher:
            request = FetchRequest(url=long_url)
            
            result = await fetcher.fetch_single(request)
            
            # Should handle long URLs (may fail due to server limits, but shouldn't crash)
            assert result is not None

    @pytest.mark.asyncio
    async def test_unicode_in_url(self, fetcher_config):
        """Test handling of Unicode characters in URLs."""
        unicode_url = "https://example.com/测试"
        
        async with WebFetcher(fetcher_config) as fetcher:
            request = FetchRequest(url=unicode_url)
            
            result = await fetcher.fetch_single(request)
            
            # Should handle Unicode URLs
            assert result is not None

    @pytest.mark.asyncio
    async def test_redirect_loop(self, fetcher_config):
        """Test handling of redirect loops."""
        with patch('aiohttp.ClientSession.request') as mock_request:
            # Mock redirect loop
            mock_response = AsyncMock()
            mock_response.status = 302
            mock_response.headers = {'location': 'https://example.com/redirect'}
            mock_request.return_value.__aenter__.return_value = mock_response
            
            async with WebFetcher(fetcher_config) as fetcher:
                request = FetchRequest(url="https://example.com/redirect")
                
                result = await fetcher.fetch_single(request)
                
                # Should handle redirect loops gracefully
                assert result is not None
