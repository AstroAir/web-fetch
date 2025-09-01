"""
Performance and stress tests for critical paths.
"""

import pytest
import asyncio
import time
import psutil
import gc
from unittest.mock import patch, AsyncMock
from concurrent.futures import ThreadPoolExecutor

from web_fetch import WebFetcher, FetchConfig
from web_fetch.models import FetchResult, BatchFetchResult, ContentType
from web_fetch.cache import CacheManager, CacheBackend
from web_fetch.auth import AuthManager, APIKeyAuth, APIKeyConfig


@pytest.mark.performance
class TestPerformanceBenchmarks:
    """Performance benchmark tests."""
    
    @pytest.fixture
    def performance_config(self):
        """Configuration optimized for performance testing."""
        return FetchConfig(
            max_concurrent_requests=100,
            total_timeout=30.0,
            connect_timeout=5.0,
            read_timeout=10.0,
            max_retries=1,
            retry_delay=0.1
        )
    
    @pytest.mark.asyncio
    async def test_single_request_latency(self, performance_config):
        """Benchmark single request latency."""
        async with WebFetcher(performance_config) as fetcher:
            with patch('aiohttp.ClientSession.request') as mock_request:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.headers = {"content-type": "application/json"}
                mock_response.text.return_value = '{"benchmark": true}'
                mock_response.json.return_value = {"benchmark": True}
                mock_request.return_value.__aenter__.return_value = mock_response
                
                # Warm up
                await fetcher.fetch_single("https://example.com/warmup", ContentType.JSON)
                
                # Benchmark
                iterations = 100
                start_time = time.perf_counter()
                
                for _ in range(iterations):
                    result = await fetcher.fetch_single("https://example.com/test", ContentType.JSON)
                    assert result.status_code == 200
                
                end_time = time.perf_counter()
                total_time = end_time - start_time
                avg_latency = (total_time / iterations) * 1000  # Convert to milliseconds
                
                print(f"Average single request latency: {avg_latency:.2f}ms")
                assert avg_latency < 10.0  # Should be under 10ms per request
    
    @pytest.mark.asyncio
    async def test_batch_request_throughput(self, performance_config):
        """Benchmark batch request throughput."""
        async with WebFetcher(performance_config) as fetcher:
            with patch('aiohttp.ClientSession.request') as mock_request:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.headers = {"content-type": "application/json"}
                mock_response.text.return_value = '{"batch": true}'
                mock_response.json.return_value = {"batch": True}
                mock_request.return_value.__aenter__.return_value = mock_response
                
                # Test different batch sizes
                batch_sizes = [10, 50, 100, 200]
                
                for batch_size in batch_sizes:
                    urls = [f"https://example.com/item{i}" for i in range(batch_size)]
                    
                    start_time = time.perf_counter()
                    result = await fetcher.fetch_batch(urls)
                    end_time = time.perf_counter()
                    
                    duration = end_time - start_time
                    throughput = batch_size / duration  # requests per second
                    
                    print(f"Batch size {batch_size}: {throughput:.1f} req/s")
                    
                    assert result.successful_requests == batch_size
                    assert throughput > 50  # Should handle at least 50 req/s
    
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, performance_config):
        """Test memory usage under high load."""
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        async with WebFetcher(performance_config) as fetcher:
            with patch('aiohttp.ClientSession.request') as mock_request:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.headers = {"content-type": "text/plain"}
                mock_response.text.return_value = "x" * 1024  # 1KB response
                mock_request.return_value.__aenter__.return_value = mock_response
                
                # Process many requests
                urls = [f"https://example.com/load{i}" for i in range(1000)]
                
                result = await fetcher.fetch_batch(urls)
                
                # Force garbage collection
                gc.collect()
                
                final_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = final_memory - initial_memory
                
                print(f"Memory increase: {memory_increase:.1f}MB for 1000 requests")
                
                assert result.successful_requests == 1000
                assert memory_increase < 100  # Should not increase by more than 100MB
    
    @pytest.mark.asyncio
    async def test_cache_performance(self, performance_config):
        """Benchmark cache performance."""
        cache_config = {"max_size": 1000, "default_ttl": 300}
        cache_manager = CacheManager(CacheBackend.MEMORY, cache_config)
        
        async with WebFetcher(performance_config) as fetcher:
            fetcher.set_cache_manager(cache_manager)
            
            with patch('aiohttp.ClientSession.request') as mock_request:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.headers = {"content-type": "application/json"}
                mock_response.text.return_value = '{"cached": true}'
                mock_response.json.return_value = {"cached": True}
                mock_request.return_value.__aenter__.return_value = mock_response
                
                url = "https://example.com/cached"
                
                # First request (cache miss)
                start_time = time.perf_counter()
                result1 = await fetcher.fetch_single(url, ContentType.JSON)
                miss_time = time.perf_counter() - start_time
                
                # Subsequent requests (cache hits)
                hit_times = []
                for _ in range(100):
                    start_time = time.perf_counter()
                    result = await fetcher.fetch_single(url, ContentType.JSON)
                    hit_time = time.perf_counter() - start_time
                    hit_times.append(hit_time)
                    assert result.content == result1.content
                
                avg_hit_time = sum(hit_times) / len(hit_times)
                speedup = miss_time / avg_hit_time
                
                print(f"Cache speedup: {speedup:.1f}x")
                assert speedup > 10  # Cache should be at least 10x faster


@pytest.mark.performance
class TestStressTests:
    """Stress tests for system limits."""
    
    @pytest.fixture
    def stress_config(self):
        """Configuration for stress testing."""
        return FetchConfig(
            max_concurrent_requests=200,
            total_timeout=60.0,
            max_retries=0,  # No retries for stress tests
        )
    
    @pytest.mark.asyncio
    async def test_concurrent_connection_limit(self, stress_config):
        """Test behavior at concurrent connection limits."""
        async with WebFetcher(stress_config) as fetcher:
            with patch('aiohttp.ClientSession.request') as mock_request:
                # Simulate slow responses
                async def slow_response(*args, **kwargs):
                    await asyncio.sleep(0.1)  # 100ms delay
                    mock_response = AsyncMock()
                    mock_response.status = 200
                    mock_response.headers = {"content-type": "text/plain"}
                    mock_response.text.return_value = "slow response"
                    return mock_response
                
                mock_request.side_effect = slow_response
                
                # Create more URLs than max concurrent requests
                urls = [f"https://example.com/concurrent{i}" for i in range(500)]
                
                start_time = time.perf_counter()
                result = await fetcher.fetch_batch(urls)
                end_time = time.perf_counter()
                
                duration = end_time - start_time
                
                assert result.total_requests == 500
                assert result.successful_requests == 500
                # Should take at least 3 batches: 500 / 200 = 2.5, rounded up to 3
                # Each batch takes ~0.1s, so minimum ~0.3s
                assert duration >= 0.25
    
    @pytest.mark.asyncio
    async def test_error_rate_resilience(self, stress_config):
        """Test resilience under high error rates."""
        async with WebFetcher(stress_config) as fetcher:
            with patch('aiohttp.ClientSession.request') as mock_request:
                call_count = 0
                
                def error_prone_response(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    
                    # 50% error rate
                    if call_count % 2 == 0:
                        raise ConnectionError("Simulated connection error")
                    else:
                        mock_response = AsyncMock()
                        mock_response.status = 200
                        mock_response.headers = {"content-type": "text/plain"}
                        mock_response.text.return_value = "success"
                        return mock_response
                
                mock_request.side_effect = error_prone_response
                
                urls = [f"https://flaky.example.com/item{i}" for i in range(100)]
                
                result = await fetcher.fetch_batch(urls)
                
                # Should handle errors gracefully
                assert result.total_requests == 100
                assert result.successful_requests >= 40  # At least 40% success
                assert result.failed_requests >= 40  # At least 40% failures
                assert result.successful_requests + result.failed_requests == 100
    
    @pytest.mark.asyncio
    async def test_large_response_handling(self, stress_config):
        """Test handling of very large responses."""
        async with WebFetcher(stress_config) as fetcher:
            with patch('aiohttp.ClientSession.request') as mock_request:
                # Create 10MB response
                large_content = "x" * (10 * 1024 * 1024)
                
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.headers = {
                    "content-type": "text/plain",
                    "content-length": str(len(large_content))
                }
                mock_response.text.return_value = large_content
                mock_request.return_value.__aenter__.return_value = mock_response
                
                start_time = time.perf_counter()
                result = await fetcher.fetch_single("https://example.com/large")
                end_time = time.perf_counter()
                
                duration = end_time - start_time
                
                assert result.status_code == 200
                assert len(result.content) == 10 * 1024 * 1024
                assert duration < 5.0  # Should complete within 5 seconds
    
    @pytest.mark.asyncio
    async def test_auth_performance_under_load(self, stress_config):
        """Test authentication performance under load."""
        # Setup auth manager
        auth_manager = AuthManager()
        config = APIKeyConfig(api_key="stress-test-key", key_name="X-API-Key")
        auth = APIKeyAuth(config)
        auth_manager.add_auth_method("api", auth)
        
        async with WebFetcher(stress_config) as fetcher:
            fetcher.set_auth_manager(auth_manager)
            
            with patch('aiohttp.ClientSession.request') as mock_request:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.headers = {"content-type": "application/json"}
                mock_response.text.return_value = '{"authenticated": true}'
                mock_response.json.return_value = {"authenticated": True}
                mock_request.return_value.__aenter__.return_value = mock_response
                
                # Many authenticated requests
                urls = [f"https://api.example.com/auth{i}" for i in range(200)]
                
                start_time = time.perf_counter()
                result = await fetcher.fetch_batch(urls)
                end_time = time.perf_counter()
                
                duration = end_time - start_time
                throughput = len(urls) / duration
                
                print(f"Authenticated requests throughput: {throughput:.1f} req/s")
                
                assert result.successful_requests == 200
                assert throughput > 20  # Should handle at least 20 authenticated req/s
                
                # Verify all requests were authenticated
                for call in mock_request.call_args_list:
                    headers = call[1].get('headers', {})
                    assert 'X-API-Key' in headers
                    assert headers['X-API-Key'] == 'stress-test-key'
