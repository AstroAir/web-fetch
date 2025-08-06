#!/usr/bin/env python3
"""
Performance optimization examples for the web-fetch library.

This script demonstrates various optimization techniques including:
- Connection pooling and reuse
- Concurrent request optimization
- Memory management strategies
- Caching strategies
- Rate limiting optimization
- Batch processing optimization
"""

import asyncio
import time
import psutil
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any
from dataclasses import dataclass

from web_fetch import (
    WebFetcher,
    FetchConfig,
    FetchRequest,
    ContentType,
    CacheConfig,
    RateLimitConfig,
    fetch_url,
    fetch_urls,
)


@dataclass
class PerformanceMetrics:
    """Performance metrics container."""
    total_time: float
    requests_per_second: float
    average_response_time: float
    memory_usage_mb: float
    success_rate: float
    total_requests: int
    successful_requests: int


class PerformanceProfiler:
    """Simple performance profiler for web-fetch operations."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.initial_memory = None
        self.final_memory = None
        self.process = psutil.Process(os.getpid())
    
    def start(self):
        """Start profiling."""
        self.start_time = time.time()
        self.initial_memory = self.process.memory_info().rss
    
    def stop(self):
        """Stop profiling."""
        self.end_time = time.time()
        self.final_memory = self.process.memory_info().rss
    
    def get_metrics(self, total_requests: int, successful_requests: int) -> PerformanceMetrics:
        """Get performance metrics."""
        total_time = self.end_time - self.start_time
        memory_usage_mb = (self.final_memory - self.initial_memory) / (1024 * 1024)
        
        return PerformanceMetrics(
            total_time=total_time,
            requests_per_second=total_requests / total_time if total_time > 0 else 0,
            average_response_time=total_time / total_requests if total_requests > 0 else 0,
            memory_usage_mb=memory_usage_mb,
            success_rate=successful_requests / total_requests if total_requests > 0 else 0,
            total_requests=total_requests,
            successful_requests=successful_requests
        )


async def example_connection_pooling():
    """Demonstrate connection pooling optimization."""
    print("=== Connection Pooling Optimization ===\n")
    
    # Test URLs (same domain to benefit from connection reuse)
    urls = [f"https://httpbin.org/delay/0.1?id={i}" for i in range(20)]
    
    print("1. Without connection pooling (new connection each time):")
    
    # Simulate no connection pooling by creating new fetcher for each request
    profiler = PerformanceProfiler()
    profiler.start()
    
    results_no_pooling = []
    for url in urls:
        async with WebFetcher() as fetcher:  # New fetcher each time
            result = await fetch_url(url, ContentType.JSON)
            results_no_pooling.append(result)
    
    profiler.stop()
    successful = sum(1 for r in results_no_pooling if r.is_success)
    metrics_no_pooling = profiler.get_metrics(len(urls), successful)
    
    print(f"   Total time: {metrics_no_pooling.total_time:.2f}s")
    print(f"   Requests/sec: {metrics_no_pooling.requests_per_second:.2f}")
    print(f"   Success rate: {metrics_no_pooling.success_rate:.1%}")
    
    print("\n2. With connection pooling (reuse connections):")
    
    # Use single fetcher instance to enable connection pooling
    profiler = PerformanceProfiler()
    profiler.start()
    
    config = FetchConfig(
        max_concurrent_requests=10,
        total_timeout=30.0
    )
    
    results_with_pooling = await fetch_urls(urls, ContentType.JSON, config)
    
    profiler.stop()
    metrics_with_pooling = profiler.get_metrics(
        results_with_pooling.total_requests,
        results_with_pooling.successful_requests
    )
    
    print(f"   Total time: {metrics_with_pooling.total_time:.2f}s")
    print(f"   Requests/sec: {metrics_with_pooling.requests_per_second:.2f}")
    print(f"   Success rate: {metrics_with_pooling.success_rate:.1%}")
    
    # Compare performance
    improvement = (metrics_no_pooling.total_time - metrics_with_pooling.total_time) / metrics_no_pooling.total_time
    print(f"\n   Performance improvement: {improvement:.1%}")
    
    print()


async def example_concurrency_optimization():
    """Demonstrate concurrency optimization strategies."""
    print("=== Concurrency Optimization ===\n")
    
    urls = [f"https://httpbin.org/delay/0.5?id={i}" for i in range(15)]
    
    concurrency_levels = [1, 3, 5, 10, 15]
    
    print("Testing different concurrency levels:")
    
    for concurrency in concurrency_levels:
        print(f"\n   Concurrency level: {concurrency}")
        
        config = FetchConfig(
            max_concurrent_requests=concurrency,
            total_timeout=60.0
        )
        
        profiler = PerformanceProfiler()
        profiler.start()
        
        batch_result = await fetch_urls(urls, ContentType.JSON, config)
        
        profiler.stop()
        metrics = profiler.get_metrics(
            batch_result.total_requests,
            batch_result.successful_requests
        )
        
        print(f"     Total time: {metrics.total_time:.2f}s")
        print(f"     Requests/sec: {metrics.requests_per_second:.2f}")
        print(f"     Memory usage: {metrics.memory_usage_mb:.1f}MB")
    
    print("\n   Optimal concurrency depends on:")
    print("   - Target server capacity")
    print("   - Network latency")
    print("   - Available system resources")
    print("   - Rate limiting constraints")
    
    print()


async def example_memory_optimization():
    """Demonstrate memory optimization techniques."""
    print("=== Memory Optimization ===\n")
    
    print("1. Streaming vs. Loading Large Content:")
    
    large_content_url = "https://httpbin.org/bytes/1048576"  # 1MB
    
    # Method 1: Load entire content into memory
    print("   Loading entire content into memory:")
    profiler = PerformanceProfiler()
    profiler.start()
    
    result = await fetch_url(large_content_url, ContentType.RAW)
    
    profiler.stop()
    metrics_load_all = profiler.get_metrics(1, 1 if result.is_success else 0)
    
    print(f"     Memory usage: {metrics_load_all.memory_usage_mb:.1f}MB")
    print(f"     Content size: {len(result.content) / (1024*1024):.1f}MB")
    
    # Method 2: Process content in chunks (simulated)
    print("\n   Processing content in chunks:")
    profiler = PerformanceProfiler()
    profiler.start()
    
    # Simulate chunked processing
    config = FetchConfig(
        max_response_size=512*1024,  # 512KB limit
        total_timeout=30.0
    )
    
    try:
        result_chunked = await fetch_url(large_content_url, ContentType.RAW, config)
        success = result_chunked.is_success
    except Exception:
        success = False
    
    profiler.stop()
    metrics_chunked = profiler.get_metrics(1, 1 if success else 0)
    
    print(f"     Memory usage: {metrics_chunked.memory_usage_mb:.1f}MB")
    print(f"     Result: {'Success' if success else 'Limited by max_response_size'}")
    
    print("\n2. Memory-Efficient Batch Processing:")
    
    # Process URLs in smaller batches to control memory usage
    all_urls = [f"https://httpbin.org/json?id={i}" for i in range(50)]
    batch_size = 10
    
    profiler = PerformanceProfiler()
    profiler.start()
    
    total_successful = 0
    total_requests = 0
    
    config = FetchConfig(
        max_concurrent_requests=5,
        total_timeout=30.0
    )
    
    for i in range(0, len(all_urls), batch_size):
        batch_urls = all_urls[i:i + batch_size]
        batch_result = await fetch_urls(batch_urls, ContentType.JSON, config)
        
        total_requests += batch_result.total_requests
        total_successful += batch_result.successful_requests
        
        # Simulate processing and cleanup
        await asyncio.sleep(0.1)
    
    profiler.stop()
    metrics_batched = profiler.get_metrics(total_requests, total_successful)
    
    print(f"   Processed {total_requests} URLs in batches of {batch_size}")
    print(f"   Total time: {metrics_batched.total_time:.2f}s")
    print(f"   Memory usage: {metrics_batched.memory_usage_mb:.1f}MB")
    print(f"   Success rate: {metrics_batched.success_rate:.1%}")
    
    print()


async def example_caching_optimization():
    """Demonstrate caching optimization strategies."""
    print("=== Caching Optimization ===\n")
    
    # URLs that we'll request multiple times
    repeated_urls = [
        "https://httpbin.org/json",
        "https://httpbin.org/user-agent",
        "https://httpbin.org/headers",
    ]
    
    print("1. Without caching:")
    
    profiler = PerformanceProfiler()
    profiler.start()
    
    # Make requests multiple times without caching
    total_requests = 0
    successful_requests = 0
    
    for _ in range(3):  # Repeat 3 times
        for url in repeated_urls:
            result = await fetch_url(url, ContentType.JSON)
            total_requests += 1
            if result.is_success:
                successful_requests += 1
    
    profiler.stop()
    metrics_no_cache = profiler.get_metrics(total_requests, successful_requests)
    
    print(f"   Total requests: {total_requests}")
    print(f"   Total time: {metrics_no_cache.total_time:.2f}s")
    print(f"   Average response time: {metrics_no_cache.average_response_time:.3f}s")
    
    print("\n2. With caching:")
    
    # Configure caching
    cache_config = CacheConfig(
        ttl_seconds=300,  # 5 minutes
        max_size=100,
        enable_compression=True
    )
    
    config = FetchConfig(
        total_timeout=30.0,
        cache_config=cache_config
    )
    
    profiler = PerformanceProfiler()
    profiler.start()
    
    total_requests = 0
    successful_requests = 0
    
    async with WebFetcher(config) as fetcher:
        for _ in range(3):  # Repeat 3 times
            for url in repeated_urls:
                request = FetchRequest(url=url, content_type=ContentType.JSON)
                result = await fetcher.fetch_single(request)
                total_requests += 1
                if result.is_success:
                    successful_requests += 1
    
    profiler.stop()
    metrics_with_cache = profiler.get_metrics(total_requests, successful_requests)
    
    print(f"   Total requests: {total_requests}")
    print(f"   Total time: {metrics_with_cache.total_time:.2f}s")
    print(f"   Average response time: {metrics_with_cache.average_response_time:.3f}s")
    
    # Calculate cache effectiveness
    time_saved = metrics_no_cache.total_time - metrics_with_cache.total_time
    cache_effectiveness = time_saved / metrics_no_cache.total_time
    
    print(f"\n   Cache effectiveness: {cache_effectiveness:.1%}")
    print(f"   Time saved: {time_saved:.2f}s")
    
    print()


async def example_rate_limiting_optimization():
    """Demonstrate rate limiting optimization."""
    print("=== Rate Limiting Optimization ===\n")
    
    urls = [f"https://httpbin.org/delay/0.1?id={i}" for i in range(20)]
    
    print("1. Without rate limiting (may overwhelm server):")
    
    config_no_limit = FetchConfig(
        max_concurrent_requests=20,  # High concurrency
        total_timeout=60.0
    )
    
    profiler = PerformanceProfiler()
    profiler.start()
    
    batch_result_no_limit = await fetch_urls(urls, ContentType.JSON, config_no_limit)
    
    profiler.stop()
    metrics_no_limit = profiler.get_metrics(
        batch_result_no_limit.total_requests,
        batch_result_no_limit.successful_requests
    )
    
    print(f"   Total time: {metrics_no_limit.total_time:.2f}s")
    print(f"   Success rate: {metrics_no_limit.success_rate:.1%}")
    print(f"   Requests/sec: {metrics_no_limit.requests_per_second:.2f}")
    
    print("\n2. With rate limiting (server-friendly):")
    
    rate_limit_config = RateLimitConfig(
        requests_per_second=5.0,  # Limit to 5 req/sec
        burst_size=10
    )
    
    config_with_limit = FetchConfig(
        max_concurrent_requests=10,
        total_timeout=60.0,
        rate_limit_config=rate_limit_config
    )
    
    profiler = PerformanceProfiler()
    profiler.start()
    
    batch_result_with_limit = await fetch_urls(urls, ContentType.JSON, config_with_limit)
    
    profiler.stop()
    metrics_with_limit = profiler.get_metrics(
        batch_result_with_limit.total_requests,
        batch_result_with_limit.successful_requests
    )
    
    print(f"   Total time: {metrics_with_limit.total_time:.2f}s")
    print(f"   Success rate: {metrics_with_limit.success_rate:.1%}")
    print(f"   Requests/sec: {metrics_with_limit.requests_per_second:.2f}")
    
    print("\n   Rate limiting benefits:")
    print("   - Prevents server overload")
    print("   - Reduces chance of being blocked")
    print("   - More predictable performance")
    print("   - Better for long-running operations")
    
    print()


async def example_batch_optimization():
    """Demonstrate batch processing optimization."""
    print("=== Batch Processing Optimization ===\n")
    
    # Large number of URLs to process
    all_urls = [f"https://httpbin.org/json?id={i}" for i in range(100)]
    
    print("1. Sequential processing:")
    
    profiler = PerformanceProfiler()
    profiler.start()
    
    sequential_results = []
    for url in all_urls[:10]:  # Test with first 10 for speed
        result = await fetch_url(url, ContentType.JSON)
        sequential_results.append(result)
    
    profiler.stop()
    successful_sequential = sum(1 for r in sequential_results if r.is_success)
    metrics_sequential = profiler.get_metrics(10, successful_sequential)
    
    print(f"   Time for 10 requests: {metrics_sequential.total_time:.2f}s")
    print(f"   Requests/sec: {metrics_sequential.requests_per_second:.2f}")
    
    print("\n2. Batch processing:")
    
    profiler = PerformanceProfiler()
    profiler.start()
    
    config = FetchConfig(
        max_concurrent_requests=10,
        total_timeout=60.0
    )
    
    batch_result = await fetch_urls(all_urls[:10], ContentType.JSON, config)
    
    profiler.stop()
    metrics_batch = profiler.get_metrics(
        batch_result.total_requests,
        batch_result.successful_requests
    )
    
    print(f"   Time for 10 requests: {metrics_batch.total_time:.2f}s")
    print(f"   Requests/sec: {metrics_batch.requests_per_second:.2f}")
    
    # Calculate improvement
    speedup = metrics_sequential.total_time / metrics_batch.total_time
    print(f"\n   Speedup: {speedup:.1f}x")
    
    print("\n3. Adaptive batch sizing:")
    
    async def adaptive_batch_processing(urls: List[str], initial_batch_size: int = 10):
        """Process URLs with adaptive batch sizing based on performance."""
        
        batch_size = initial_batch_size
        processed = 0
        total_successful = 0
        
        while processed < len(urls):
            batch_urls = urls[processed:processed + batch_size]
            
            start_time = time.time()
            
            config = FetchConfig(
                max_concurrent_requests=min(batch_size, 10),
                total_timeout=30.0
            )
            
            batch_result = await fetch_urls(batch_urls, ContentType.JSON, config)
            
            end_time = time.time()
            batch_time = end_time - start_time
            
            processed += len(batch_urls)
            total_successful += batch_result.successful_requests
            
            # Adapt batch size based on performance
            if batch_time < 2.0 and batch_result.success_rate > 0.9:
                batch_size = min(batch_size + 5, 20)  # Increase batch size
            elif batch_time > 5.0 or batch_result.success_rate < 0.8:
                batch_size = max(batch_size - 5, 5)   # Decrease batch size
            
            print(f"     Processed {processed}/{len(urls)}, batch_size={batch_size}, time={batch_time:.1f}s")
        
        return total_successful
    
    profiler = PerformanceProfiler()
    profiler.start()
    
    successful_adaptive = await adaptive_batch_processing(all_urls[:30])
    
    profiler.stop()
    metrics_adaptive = profiler.get_metrics(30, successful_adaptive)
    
    print(f"\n   Adaptive processing results:")
    print(f"   Total time: {metrics_adaptive.total_time:.2f}s")
    print(f"   Success rate: {metrics_adaptive.success_rate:.1%}")
    print(f"   Requests/sec: {metrics_adaptive.requests_per_second:.2f}")
    
    print()


async def example_performance_monitoring():
    """Demonstrate performance monitoring and profiling."""
    print("=== Performance Monitoring ===\n")
    
    class PerformanceMonitor:
        """Monitor and log performance metrics."""
        
        def __init__(self):
            self.request_times = []
            self.error_count = 0
            self.total_requests = 0
        
        def record_request(self, response_time: float, success: bool):
            """Record a request's performance."""
            self.total_requests += 1
            self.request_times.append(response_time)
            if not success:
                self.error_count += 1
        
        def get_stats(self) -> Dict[str, Any]:
            """Get performance statistics."""
            if not self.request_times:
                return {}
            
            return {
                'total_requests': self.total_requests,
                'error_rate': self.error_count / self.total_requests,
                'avg_response_time': sum(self.request_times) / len(self.request_times),
                'min_response_time': min(self.request_times),
                'max_response_time': max(self.request_times),
                'p95_response_time': sorted(self.request_times)[int(len(self.request_times) * 0.95)],
                'requests_per_second': self.total_requests / sum(self.request_times) if sum(self.request_times) > 0 else 0
            }
    
    monitor = PerformanceMonitor()
    
    # Test URLs with varying response times
    test_urls = [
        "https://httpbin.org/delay/0.1",
        "https://httpbin.org/delay/0.5",
        "https://httpbin.org/delay/1.0",
        "https://httpbin.org/status/200",
        "https://httpbin.org/status/404",  # Will fail
    ]
    
    print("Monitoring performance across different scenarios:")
    
    async with WebFetcher() as fetcher:
        for url in test_urls:
            start_time = time.time()
            
            request = FetchRequest(url=url, content_type=ContentType.JSON)
            result = await fetcher.fetch_single(request)
            
            end_time = time.time()
            response_time = end_time - start_time
            
            monitor.record_request(response_time, result.is_success)
            
            status = "✅" if result.is_success else "❌"
            print(f"   {status} {url}: {response_time:.3f}s")
    
    # Display performance statistics
    stats = monitor.get_stats()
    
    print(f"\nPerformance Statistics:")
    print(f"   Total requests: {stats['total_requests']}")
    print(f"   Error rate: {stats['error_rate']:.1%}")
    print(f"   Average response time: {stats['avg_response_time']:.3f}s")
    print(f"   Min response time: {stats['min_response_time']:.3f}s")
    print(f"   Max response time: {stats['max_response_time']:.3f}s")
    print(f"   95th percentile: {stats['p95_response_time']:.3f}s")
    print(f"   Requests per second: {stats['requests_per_second']:.2f}")
    
    print()


async def main():
    """Run all performance optimization examples."""
    print("Web Fetch Library - Performance Optimization Examples")
    print("=" * 70)
    print()
    
    try:
        await example_connection_pooling()
        await example_concurrency_optimization()
        await example_memory_optimization()
        await example_caching_optimization()
        await example_rate_limiting_optimization()
        await example_batch_optimization()
        await example_performance_monitoring()
        
        print("🎉 All performance optimization examples completed!")
        print("\nKey Optimization Techniques Demonstrated:")
        print("- Connection pooling and reuse")
        print("- Optimal concurrency levels")
        print("- Memory-efficient processing")
        print("- Effective caching strategies")
        print("- Rate limiting for server protection")
        print("- Batch processing optimization")
        print("- Performance monitoring and profiling")
        
    except Exception as e:
        print(f"❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
