"""
Comprehensive tests for the core fetcher.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from web_fetch.core_fetcher import (
    CoreFetcher,
    FetcherConfig,
    FetcherState,
    FetcherError,
    RequestQueue,
    ResponseProcessor,
)
from web_fetch.models import FetchConfig, FetchResult, BatchFetchResult, ContentType
from web_fetch.exceptions import HTTPError, NetworkError, TimeoutError


class TestFetcherConfig:
    """Test fetcher configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = FetcherConfig()
        
        assert config.max_concurrent_requests == 50
        assert config.request_queue_size == 1000
        assert config.response_timeout == 30.0
        assert config.enable_metrics is True
        assert config.enable_caching is True
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = FetcherConfig(
            max_concurrent_requests=100,
            request_queue_size=2000,
            response_timeout=60.0,
            enable_metrics=False,
            enable_caching=False
        )
        
        assert config.max_concurrent_requests == 100
        assert config.request_queue_size == 2000
        assert config.response_timeout == 60.0
        assert config.enable_metrics is False
        assert config.enable_caching is False
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Invalid max_concurrent_requests
        with pytest.raises(ValueError, match="max_concurrent_requests must be positive"):
            FetcherConfig(max_concurrent_requests=0)
        
        # Invalid queue size
        with pytest.raises(ValueError, match="request_queue_size must be positive"):
            FetcherConfig(request_queue_size=0)
        
        # Invalid timeout
        with pytest.raises(ValueError, match="response_timeout must be positive"):
            FetcherConfig(response_timeout=0)


class TestRequestQueue:
    """Test request queue functionality."""
    
    @pytest.fixture
    def queue(self):
        """Create request queue."""
        return RequestQueue(max_size=10)
    
    @pytest.mark.asyncio
    async def test_queue_basic_operations(self, queue):
        """Test basic queue operations."""
        # Queue should be empty initially
        assert queue.empty()
        assert queue.size() == 0
        
        # Add request
        request = {"url": "https://example.com", "method": "GET"}
        await queue.put(request)
        
        assert not queue.empty()
        assert queue.size() == 1
        
        # Get request
        retrieved = await queue.get()
        assert retrieved == request
        assert queue.empty()
    
    @pytest.mark.asyncio
    async def test_queue_priority(self, queue):
        """Test priority queue functionality."""
        # Add requests with different priorities
        high_priority = {"url": "https://high.com", "priority": 1}
        low_priority = {"url": "https://low.com", "priority": 10}
        medium_priority = {"url": "https://medium.com", "priority": 5}
        
        await queue.put(low_priority)
        await queue.put(high_priority)
        await queue.put(medium_priority)
        
        # Should retrieve in priority order
        first = await queue.get()
        second = await queue.get()
        third = await queue.get()
        
        assert first["priority"] == 1  # Highest priority
        assert second["priority"] == 5
        assert third["priority"] == 10  # Lowest priority
    
    @pytest.mark.asyncio
    async def test_queue_full_behavior(self, queue):
        """Test queue behavior when full."""
        # Fill queue to capacity
        for i in range(10):
            await queue.put({"url": f"https://example{i}.com"})
        
        assert queue.full()
        assert queue.size() == 10
        
        # Adding another should block or raise exception
        with pytest.raises(asyncio.QueueFull):
            queue.put_nowait({"url": "https://overflow.com"})
    
    @pytest.mark.asyncio
    async def test_queue_timeout(self, queue):
        """Test queue timeout behavior."""
        # Try to get from empty queue with timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.1)
    
    def test_queue_stats(self, queue):
        """Test queue statistics."""
        stats = queue.get_stats()
        
        assert "size" in stats
        assert "max_size" in stats
        assert "total_put" in stats
        assert "total_get" in stats
        assert stats["size"] == 0
        assert stats["max_size"] == 10


class TestResponseProcessor:
    """Test response processor functionality."""
    
    @pytest.fixture
    def processor(self):
        """Create response processor."""
        return ResponseProcessor()
    
    def test_process_json_response(self, processor):
        """Test processing JSON response."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"success": true, "data": [1, 2, 3]}'
        
        result = processor.process_response(
            mock_response,
            "https://api.example.com/data",
            ContentType.JSON
        )
        
        assert isinstance(result, FetchResult)
        assert result.status_code == 200
        assert result.content_type == ContentType.JSON
        assert result.content["success"] is True
        assert result.content["data"] == [1, 2, 3]
    
    def test_process_html_response(self, processor):
        """Test processing HTML response."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "<html><body><h1>Test Page</h1></body></html>"
        
        result = processor.process_response(
            mock_response,
            "https://example.com/page",
            ContentType.HTML
        )
        
        assert result.status_code == 200
        assert result.content_type == ContentType.HTML
        assert "<h1>Test Page</h1>" in result.content
    
    def test_process_binary_response(self, processor):
        """Test processing binary response."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"content-type": "image/jpeg"}
        mock_response.content = b'\xff\xd8\xff\xe0\x00\x10JFIF'  # JPEG header
        
        result = processor.process_response(
            mock_response,
            "https://example.com/image.jpg",
            ContentType.BINARY
        )
        
        assert result.status_code == 200
        assert result.content_type == ContentType.BINARY
        assert isinstance(result.content, bytes)
        assert result.content.startswith(b'\xff\xd8\xff\xe0')
    
    def test_process_error_response(self, processor):
        """Test processing error response."""
        mock_response = MagicMock()
        mock_response.status = 404
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "Not Found"
        
        result = processor.process_response(
            mock_response,
            "https://example.com/missing",
            ContentType.HTML
        )
        
        assert result.status_code == 404
        assert result.error is not None
        assert "Not Found" in result.error
    
    def test_extract_metadata(self, processor):
        """Test metadata extraction."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {
            "content-type": "application/json",
            "content-length": "1024",
            "last-modified": "Wed, 21 Oct 2020 07:28:00 GMT",
            "etag": '"abc123"'
        }
        mock_response.text = '{"data": "test"}'
        
        result = processor.process_response(
            mock_response,
            "https://api.example.com/data",
            ContentType.JSON
        )
        
        assert "content_length" in result.metadata
        assert "last_modified" in result.metadata
        assert "etag" in result.metadata
        assert result.metadata["content_length"] == "1024"


class TestCoreFetcher:
    """Test core fetcher functionality."""
    
    @pytest.fixture
    def fetcher_config(self):
        """Create fetcher configuration."""
        return FetcherConfig(max_concurrent_requests=10, enable_metrics=True)
    
    @pytest.fixture
    def fetch_config(self):
        """Create fetch configuration."""
        return FetchConfig(total_timeout=30.0, max_retries=3)
    
    @pytest.fixture
    def fetcher(self, fetcher_config, fetch_config):
        """Create core fetcher."""
        return CoreFetcher(fetcher_config, fetch_config)
    
    def test_fetcher_initialization(self, fetcher):
        """Test fetcher initialization."""
        assert fetcher.state == FetcherState.CREATED
        assert fetcher.config.max_concurrent_requests == 10
        assert fetcher.fetch_config.total_timeout == 30.0
        assert fetcher._session is None
    
    @pytest.mark.asyncio
    async def test_fetcher_lifecycle(self, fetcher):
        """Test fetcher lifecycle management."""
        # Start fetcher
        await fetcher.start()
        assert fetcher.state == FetcherState.RUNNING
        assert fetcher._session is not None
        
        # Stop fetcher
        await fetcher.stop()
        assert fetcher.state == FetcherState.STOPPED
        assert fetcher._session is None
    
    @pytest.mark.asyncio
    async def test_single_fetch(self, fetcher):
        """Test single URL fetch."""
        await fetcher.start()
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.text.return_value = '{"message": "success"}'
            mock_response.json.return_value = {"message": "success"}
            mock_request.return_value.__aenter__.return_value = mock_response
            
            result = await fetcher.fetch_single(
                "https://api.example.com/test",
                content_type=ContentType.JSON
            )
            
            assert isinstance(result, FetchResult)
            assert result.status_code == 200
            assert result.content["message"] == "success"
            assert result.url == "https://api.example.com/test"
        
        await fetcher.stop()
    
    @pytest.mark.asyncio
    async def test_batch_fetch(self, fetcher):
        """Test batch URL fetch."""
        await fetcher.start()
        
        urls = [
            "https://api.example.com/1",
            "https://api.example.com/2",
            "https://api.example.com/3"
        ]
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            def mock_response_factory(method, url, **kwargs):
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.headers = {"content-type": "application/json"}
                
                # Extract number from URL for unique response
                url_num = url.split('/')[-1]
                response_data = f'{{"id": {url_num}, "data": "response{url_num}"}}'
                mock_response.text.return_value = response_data
                mock_response.json.return_value = {"id": int(url_num), "data": f"response{url_num}"}
                
                return mock_response
            
            mock_request.side_effect = mock_response_factory
            
            result = await fetcher.fetch_batch(urls, content_type=ContentType.JSON)
            
            assert isinstance(result, BatchFetchResult)
            assert result.total_requests == 3
            assert result.successful_requests == 3
            assert result.failed_requests == 0
            assert len(result.results) == 3
            
            # Verify each result
            for i, fetch_result in enumerate(result.results, 1):
                assert fetch_result.status_code == 200
                assert fetch_result.content["id"] == i
                assert fetch_result.content["data"] == f"response{i}"
        
        await fetcher.stop()
    
    @pytest.mark.asyncio
    async def test_concurrent_request_limiting(self, fetcher):
        """Test concurrent request limiting."""
        fetcher.config.max_concurrent_requests = 2  # Low limit for testing
        await fetcher.start()
        
        # Create many URLs
        urls = [f"https://example.com/{i}" for i in range(10)]
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            call_times = []
            
            async def slow_response(method, url, **kwargs):
                call_times.append(asyncio.get_event_loop().time())
                await asyncio.sleep(0.1)  # Simulate slow response
                
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.headers = {"content-type": "text/plain"}
                mock_response.text.return_value = f"Response for {url}"
                return mock_response
            
            mock_request.side_effect = slow_response
            
            start_time = asyncio.get_event_loop().time()
            result = await fetcher.fetch_batch(urls)
            end_time = asyncio.get_event_loop().time()
            
            # Should take longer due to concurrency limit
            assert end_time - start_time > 0.4  # At least 5 batches * 0.1s
            assert result.total_requests == 10
            assert result.successful_requests == 10
        
        await fetcher.stop()
    
    @pytest.mark.asyncio
    async def test_error_handling(self, fetcher):
        """Test error handling in fetch operations."""
        await fetcher.start()
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.side_effect = NetworkError("Connection failed")
            
            with pytest.raises(NetworkError):
                await fetcher.fetch_single("https://failing.example.com")
        
        await fetcher.stop()
    
    @pytest.mark.asyncio
    async def test_retry_mechanism(self, fetcher):
        """Test retry mechanism for failed requests."""
        fetcher.fetch_config.max_retries = 2
        await fetcher.start()
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            call_count = 0
            
            def failing_then_success(method, url, **kwargs):
                nonlocal call_count
                call_count += 1
                
                if call_count <= 2:  # Fail first two attempts
                    raise NetworkError("Temporary failure")
                else:  # Succeed on third attempt
                    mock_response = AsyncMock()
                    mock_response.status = 200
                    mock_response.headers = {"content-type": "text/plain"}
                    mock_response.text.return_value = "Success after retries"
                    return mock_response
            
            mock_request.side_effect = failing_then_success
            
            result = await fetcher.fetch_single("https://flaky.example.com")
            
            assert result.status_code == 200
            assert result.content == "Success after retries"
            assert call_count == 3  # Initial + 2 retries
        
        await fetcher.stop()
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, fetcher):
        """Test timeout handling."""
        fetcher.fetch_config.total_timeout = 0.1  # Very short timeout
        await fetcher.start()
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            async def slow_response(method, url, **kwargs):
                await asyncio.sleep(0.2)  # Longer than timeout
                return AsyncMock()
            
            mock_request.side_effect = slow_response
            
            with pytest.raises(TimeoutError):
                await fetcher.fetch_single("https://slow.example.com")
        
        await fetcher.stop()
    
    @pytest.mark.asyncio
    async def test_metrics_collection(self, fetcher):
        """Test metrics collection."""
        await fetcher.start()
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {"content-type": "text/plain"}
            mock_response.text.return_value = "test"
            mock_request.return_value.__aenter__.return_value = mock_response
            
            # Perform some requests
            await fetcher.fetch_single("https://example.com/1")
            await fetcher.fetch_single("https://example.com/2")
            
            metrics = fetcher.get_metrics()
            
            assert metrics["total_requests"] == 2
            assert metrics["successful_requests"] == 2
            assert metrics["failed_requests"] == 0
            assert "average_response_time" in metrics
            assert "requests_per_second" in metrics
        
        await fetcher.stop()
    
    @pytest.mark.asyncio
    async def test_custom_headers(self, fetcher):
        """Test requests with custom headers."""
        await fetcher.start()
        
        custom_headers = {
            "Authorization": "Bearer token123",
            "User-Agent": "CustomAgent/1.0",
            "X-Custom-Header": "custom-value"
        }
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {"content-type": "text/plain"}
            mock_response.text.return_value = "authenticated response"
            mock_request.return_value.__aenter__.return_value = mock_response
            
            result = await fetcher.fetch_single(
                "https://api.example.com/protected",
                headers=custom_headers
            )
            
            assert result.status_code == 200
            
            # Verify headers were sent
            call_args = mock_request.call_args
            sent_headers = call_args[1]["headers"]
            assert sent_headers["Authorization"] == "Bearer token123"
            assert sent_headers["User-Agent"] == "CustomAgent/1.0"
            assert sent_headers["X-Custom-Header"] == "custom-value"
        
        await fetcher.stop()
    
    def test_get_stats(self, fetcher):
        """Test getting fetcher statistics."""
        stats = fetcher.get_stats()
        
        assert "state" in stats
        assert "config" in stats
        assert "queue_size" in stats
        assert "active_requests" in stats
        assert stats["state"] == "CREATED"
    
    @pytest.mark.asyncio
    async def test_cleanup_on_error(self, fetcher):
        """Test cleanup when errors occur."""
        await fetcher.start()
        
        # Simulate error during operation
        with patch.object(fetcher, '_process_request') as mock_process:
            mock_process.side_effect = Exception("Processing error")
            
            with pytest.raises(Exception):
                await fetcher.fetch_single("https://example.com")
        
        # Fetcher should still be in valid state
        assert fetcher.state == FetcherState.RUNNING
        
        await fetcher.stop()
        assert fetcher.state == FetcherState.STOPPED
