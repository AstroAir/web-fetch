"""
End-to-end integration tests for critical workflows.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from web_fetch import WebFetcher, FetchConfig
from web_fetch.auth import AuthManager, APIKeyAuth, APIKeyConfig
from web_fetch.cache import CacheManager, CacheBackend
from web_fetch.models import FetchResult, BatchFetchResult, ContentType
from web_fetch.exceptions import HTTPError, TimeoutError, NetworkError


@pytest.mark.integration
class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return FetchConfig(
            total_timeout=30.0,
            max_retries=3,
            retry_delay=0.5,
            max_concurrent_requests=10
        )
    
    @pytest.fixture
    def auth_manager(self):
        """Create authenticated manager."""
        manager = AuthManager()
        config = APIKeyConfig(api_key="test-key", key_name="X-API-Key")
        auth = APIKeyAuth(config)
        manager.add_auth_method("api", auth)
        return manager
    
    @pytest.mark.asyncio
    async def test_authenticated_api_workflow(self, config, auth_manager):
        """Test complete authenticated API workflow."""
        async with WebFetcher(config) as fetcher:
            # Configure authentication
            fetcher.set_auth_manager(auth_manager)
            
            # Mock successful API response
            with patch('aiohttp.ClientSession.request') as mock_request:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.headers = {"content-type": "application/json"}
                mock_response.text.return_value = '{"data": "success", "authenticated": true}'
                mock_response.json.return_value = {"data": "success", "authenticated": True}
                mock_request.return_value.__aenter__.return_value = mock_response
                
                result = await fetcher.fetch_single(
                    "https://api.example.com/protected",
                    content_type=ContentType.JSON
                )
                
                assert result.status_code == 200
                assert result.content["authenticated"] is True
                
                # Verify auth headers were added
                call_args = mock_request.call_args
                assert "X-API-Key" in call_args[1]["headers"]
                assert call_args[1]["headers"]["X-API-Key"] == "test-key"
    
    @pytest.mark.asyncio
    async def test_batch_processing_with_mixed_results(self, config):
        """Test batch processing with mixed success/failure results."""
        urls = [
            "https://httpbin.org/json",  # Should succeed
            "https://httpbin.org/status/404",  # Should fail
            "https://httpbin.org/delay/1",  # Should succeed
            "https://nonexistent.example.com",  # Should fail
        ]
        
        async with WebFetcher(config) as fetcher:
            with patch('aiohttp.ClientSession.request') as mock_request:
                # Mock responses for different URLs
                def mock_response_side_effect(*args, **kwargs):
                    url = str(args[1]) if len(args) > 1 else kwargs.get('url', '')
                    
                    mock_response = AsyncMock()
                    if 'json' in url:
                        mock_response.status = 200
                        mock_response.headers = {"content-type": "application/json"}
                        mock_response.text.return_value = '{"success": true}'
                        mock_response.json.return_value = {"success": True}
                    elif '404' in url:
                        mock_response.status = 404
                        mock_response.headers = {"content-type": "text/html"}
                        mock_response.text.return_value = "Not Found"
                        mock_response.raise_for_status.side_effect = HTTPError("Not Found", 404)
                    elif 'delay' in url:
                        mock_response.status = 200
                        mock_response.headers = {"content-type": "text/plain"}
                        mock_response.text.return_value = "Delayed response"
                    else:  # nonexistent domain
                        raise NetworkError("DNS resolution failed")
                    
                    return mock_response
                
                mock_request.side_effect = mock_response_side_effect
                
                result = await fetcher.fetch_batch(urls)
                
                assert isinstance(result, BatchFetchResult)
                assert result.total_requests == 4
                assert result.successful_requests >= 2  # At least json and delay should succeed
                assert result.failed_requests >= 2  # At least 404 and DNS should fail
    
    @pytest.mark.asyncio
    async def test_caching_workflow(self, config):
        """Test complete caching workflow."""
        cache_config = {"max_size": 100, "default_ttl": 300}
        
        async with WebFetcher(config) as fetcher:
            # Enable caching
            cache_manager = CacheManager(CacheBackend.MEMORY, cache_config)
            fetcher.set_cache_manager(cache_manager)
            
            with patch('aiohttp.ClientSession.request') as mock_request:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.headers = {"content-type": "application/json"}
                mock_response.text.return_value = '{"cached": true}'
                mock_response.json.return_value = {"cached": True}
                mock_request.return_value.__aenter__.return_value = mock_response
                
                url = "https://api.example.com/cacheable"
                
                # First request should hit the network
                result1 = await fetcher.fetch_single(url, content_type=ContentType.JSON)
                assert result1.status_code == 200
                assert mock_request.call_count == 1
                
                # Second request should use cache
                result2 = await fetcher.fetch_single(url, content_type=ContentType.JSON)
                assert result2.status_code == 200
                assert result2.content == result1.content
                # Should still be 1 call (cached)
                assert mock_request.call_count == 1
    
    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, config):
        """Test error recovery and retry workflow."""
        # Configure aggressive retries for testing
        config.max_retries = 3
        config.retry_delay = 0.1
        
        async with WebFetcher(config) as fetcher:
            with patch('aiohttp.ClientSession.request') as mock_request:
                # Mock to fail twice, then succeed
                call_count = 0
                
                def mock_side_effect(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    
                    if call_count <= 2:
                        raise NetworkError("Connection failed")
                    else:
                        mock_response = AsyncMock()
                        mock_response.status = 200
                        mock_response.headers = {"content-type": "text/plain"}
                        mock_response.text.return_value = "Success after retries"
                        return mock_response
                
                mock_request.side_effect = mock_side_effect
                
                result = await fetcher.fetch_single("https://flaky.example.com")
                
                assert result.status_code == 200
                assert result.content == "Success after retries"
                assert call_count == 3  # Failed twice, succeeded on third try
    
    @pytest.mark.asyncio
    async def test_timeout_handling_workflow(self, config):
        """Test timeout handling workflow."""
        # Set short timeout for testing
        config.total_timeout = 1.0
        config.connect_timeout = 0.5
        
        async with WebFetcher(config) as fetcher:
            with patch('aiohttp.ClientSession.request') as mock_request:
                # Mock to timeout
                mock_request.side_effect = asyncio.TimeoutError("Request timed out")
                
                with pytest.raises(TimeoutError):
                    await fetcher.fetch_single("https://slow.example.com")
    
    @pytest.mark.asyncio
    async def test_content_processing_workflow(self, config):
        """Test complete content processing workflow."""
        async with WebFetcher(config) as fetcher:
            test_cases = [
                ("application/json", '{"key": "value"}', ContentType.JSON),
                ("text/html", "<html><body>Test</body></html>", ContentType.HTML),
                ("text/xml", "<?xml version='1.0'?><root></root>", ContentType.XML),
                ("text/plain", "Plain text content", ContentType.TEXT),
            ]
            
            for content_type_header, content, expected_type in test_cases:
                with patch('aiohttp.ClientSession.request') as mock_request:
                    mock_response = AsyncMock()
                    mock_response.status = 200
                    mock_response.headers = {"content-type": content_type_header}
                    mock_response.text.return_value = content
                    if expected_type == ContentType.JSON:
                        mock_response.json.return_value = {"key": "value"}
                    mock_request.return_value.__aenter__.return_value = mock_response
                    
                    result = await fetcher.fetch_single(
                        f"https://example.com/{expected_type.value}",
                        content_type=expected_type
                    )
                    
                    assert result.status_code == 200
                    assert result.content_type == expected_type
                    if expected_type == ContentType.JSON:
                        assert isinstance(result.content, dict)
                    else:
                        assert isinstance(result.content, str)


@pytest.mark.integration
class TestPerformanceWorkflows:
    """Test performance-critical workflows."""
    
    @pytest.mark.asyncio
    async def test_high_concurrency_workflow(self):
        """Test high concurrency handling."""
        config = FetchConfig(
            max_concurrent_requests=50,
            total_timeout=30.0
        )
        
        # Generate many URLs
        urls = [f"https://httpbin.org/json?id={i}" for i in range(100)]
        
        async with WebFetcher(config) as fetcher:
            with patch('aiohttp.ClientSession.request') as mock_request:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.headers = {"content-type": "application/json"}
                mock_response.text.return_value = '{"id": 1}'
                mock_response.json.return_value = {"id": 1}
                mock_request.return_value.__aenter__.return_value = mock_response
                
                import time
                start_time = time.time()
                
                result = await fetcher.fetch_batch(urls)
                
                end_time = time.time()
                duration = end_time - start_time
                
                assert result.total_requests == 100
                assert result.successful_requests == 100
                assert duration < 10.0  # Should complete within 10 seconds
    
    @pytest.mark.asyncio
    async def test_memory_efficiency_workflow(self):
        """Test memory efficiency with large responses."""
        config = FetchConfig(
            max_concurrent_requests=5,
            total_timeout=60.0
        )
        
        async with WebFetcher(config) as fetcher:
            with patch('aiohttp.ClientSession.request') as mock_request:
                # Mock large response
                large_content = "x" * (1024 * 1024)  # 1MB content
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.headers = {"content-type": "text/plain"}
                mock_response.text.return_value = large_content
                mock_request.return_value.__aenter__.return_value = mock_response
                
                # Process multiple large responses
                urls = [f"https://example.com/large{i}" for i in range(10)]
                result = await fetcher.fetch_batch(urls)
                
                assert result.total_requests == 10
                assert result.successful_requests == 10
                
                # Verify content is properly handled
                for fetch_result in result.results:
                    assert len(fetch_result.content) == 1024 * 1024
