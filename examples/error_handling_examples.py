#!/usr/bin/env python3
"""
Comprehensive error handling examples for the web-fetch library.

This script demonstrates various error scenarios, recovery strategies,
timeout handling, retry mechanisms, and robust error handling patterns.
"""

import asyncio
import logging
from typing import List, Optional
from datetime import datetime, timedelta

from web_fetch import (
    WebFetcher,
    FetchConfig,
    FetchRequest,
    ContentType,
    RetryStrategy,
    WebFetchError,
    HTTPError,
    TimeoutError,
    ConnectionError,
    NetworkError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ContentError,
)

# Configure logging for examples
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_basic_error_handling():
    """Demonstrate basic error handling patterns."""
    print("=== Basic Error Handling Examples ===\n")
    
    # Example 1: Handling different HTTP status codes
    print("1. HTTP Status Code Handling:")
    
    test_urls = [
        ("https://httpbin.org/status/200", "Success case"),
        ("https://httpbin.org/status/404", "Not Found"),
        ("https://httpbin.org/status/401", "Unauthorized"),
        ("https://httpbin.org/status/429", "Rate Limited"),
        ("https://httpbin.org/status/500", "Server Error"),
        ("https://httpbin.org/status/503", "Service Unavailable"),
    ]
    
    async with WebFetcher() as fetcher:
        for url, description in test_urls:
            try:
                request = FetchRequest(url=url, content_type=ContentType.TEXT)
                result = await fetcher.fetch_single(request)
                
                if result.is_success:
                    print(f"   ✅ {description}: Success ({result.status_code})")
                else:
                    print(f"   ❌ {description}: Failed ({result.status_code}) - {result.error}")
                    
            except HTTPError as e:
                print(f"   ❌ {description}: HTTP Error {e.status_code} - {e}")
            except Exception as e:
                print(f"   ❌ {description}: Unexpected error - {e}")
    
    print()


async def example_specific_exception_handling():
    """Demonstrate handling specific exception types."""
    print("=== Specific Exception Handling ===\n")
    
    # Configure with short timeouts to trigger errors
    config = FetchConfig(
        total_timeout=2.0,
        connect_timeout=1.0,
        read_timeout=1.0,
        max_retries=1
    )
    
    test_cases = [
        ("https://httpbin.org/delay/5", "Timeout scenario"),
        ("https://httpbin.org/status/401", "Authentication error"),
        ("https://httpbin.org/status/404", "Not found error"),
        ("https://httpbin.org/status/429", "Rate limit error"),
        ("https://httpbin.org/status/500", "Server error"),
        ("https://invalid-domain-that-does-not-exist-12345.com", "Connection error"),
    ]
    
    async with WebFetcher(config) as fetcher:
        for url, description in test_cases:
            print(f"Testing {description}:")
            
            try:
                request = FetchRequest(url=url, content_type=ContentType.TEXT)
                result = await fetcher.fetch_single(request)
                
                if result.is_success:
                    print(f"   ✅ Unexpected success: {result.status_code}")
                else:
                    print(f"   ❌ Expected failure: {result.error}")
                    
            except TimeoutError as e:
                print(f"   ⏰ Timeout: {e}")
            except AuthenticationError as e:
                print(f"   🔐 Authentication failed: {e}")
            except NotFoundError as e:
                print(f"   🔍 Resource not found: {e}")
            except RateLimitError as e:
                print(f"   🚦 Rate limited: {e}")
            except ServerError as e:
                print(f"   🔥 Server error: {e}")
            except ConnectionError as e:
                print(f"   🔌 Connection failed: {e}")
            except NetworkError as e:
                print(f"   🌐 Network error: {e}")
            except WebFetchError as e:
                print(f"   ❌ General web fetch error: {e}")
            except Exception as e:
                print(f"   💥 Unexpected error: {e}")
            
            print()


async def example_retry_strategies():
    """Demonstrate different retry strategies and configurations."""
    print("=== Retry Strategy Examples ===\n")
    
    # Test different retry strategies
    retry_configs = [
        (RetryStrategy.EXPONENTIAL, "Exponential backoff"),
        (RetryStrategy.LINEAR, "Linear backoff"),
        (RetryStrategy.NONE, "No retries"),
    ]
    
    for strategy, description in retry_configs:
        print(f"Testing {description}:")
        
        config = FetchConfig(
            max_retries=3,
            retry_delay=0.5,
            retry_strategy=strategy,
            total_timeout=10.0
        )
        
        async with WebFetcher(config) as fetcher:
            try:
                # Use an endpoint that fails intermittently
                request = FetchRequest(
                    url="https://httpbin.org/status/500",
                    content_type=ContentType.TEXT
                )
                
                start_time = datetime.now()
                result = await fetcher.fetch_single(request)
                end_time = datetime.now()
                
                duration = (end_time - start_time).total_seconds()
                
                print(f"   Result: {result.status_code}")
                print(f"   Retries: {result.retry_count}")
                print(f"   Duration: {duration:.2f}s")
                
            except Exception as e:
                print(f"   Failed after retries: {e}")
        
        print()


async def example_timeout_handling():
    """Demonstrate timeout handling and configuration."""
    print("=== Timeout Handling Examples ===\n")
    
    timeout_configs = [
        (FetchConfig(total_timeout=1.0), "Very short timeout (1s)"),
        (FetchConfig(total_timeout=5.0), "Short timeout (5s)"),
        (FetchConfig(total_timeout=15.0), "Medium timeout (15s)"),
        (FetchConfig(connect_timeout=2.0, read_timeout=8.0, total_timeout=12.0), "Separate timeouts"),
    ]
    
    # Test with a slow endpoint
    slow_url = "https://httpbin.org/delay/3"
    
    for config, description in timeout_configs:
        print(f"Testing {description}:")
        
        async with WebFetcher(config) as fetcher:
            try:
                request = FetchRequest(url=slow_url, content_type=ContentType.TEXT)
                
                start_time = datetime.now()
                result = await fetcher.fetch_single(request)
                end_time = datetime.now()
                
                duration = (end_time - start_time).total_seconds()
                
                if result.is_success:
                    print(f"   ✅ Success in {duration:.2f}s")
                else:
                    print(f"   ❌ Failed: {result.error}")
                    
            except TimeoutError as e:
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                print(f"   ⏰ Timeout after {duration:.2f}s: {e}")
            except Exception as e:
                print(f"   ❌ Other error: {e}")
        
        print()


async def example_graceful_degradation():
    """Demonstrate graceful degradation patterns."""
    print("=== Graceful Degradation Examples ===\n")
    
    async def fetch_with_fallback(primary_url: str, fallback_urls: List[str]) -> Optional[str]:
        """Fetch from primary URL with fallback options."""
        
        all_urls = [primary_url] + fallback_urls
        
        for i, url in enumerate(all_urls):
            try:
                print(f"   Trying {'primary' if i == 0 else f'fallback {i}'} URL: {url}")
                
                config = FetchConfig(total_timeout=5.0, max_retries=1)
                async with WebFetcher(config) as fetcher:
                    request = FetchRequest(url=url, content_type=ContentType.TEXT)
                    result = await fetcher.fetch_single(request)
                    
                    if result.is_success:
                        print(f"   ✅ Success with {'primary' if i == 0 else f'fallback {i}'}")
                        return result.content
                    else:
                        print(f"   ❌ Failed: {result.error}")
                        
            except Exception as e:
                print(f"   ❌ Exception: {e}")
                continue
        
        print("   ❌ All URLs failed")
        return None
    
    # Test fallback mechanism
    print("1. URL Fallback Pattern:")
    primary = "https://httpbin.org/status/500"  # Will fail
    fallbacks = [
        "https://httpbin.org/status/503",  # Will also fail
        "https://httpbin.org/get",         # Should succeed
    ]
    
    result = await fetch_with_fallback(primary, fallbacks)
    if result:
        print(f"   Final result: {len(result)} characters received")
    
    print()


async def example_circuit_breaker_pattern():
    """Demonstrate circuit breaker pattern for error handling."""
    print("=== Circuit Breaker Pattern Example ===\n")
    
    class SimpleCircuitBreaker:
        """Simple circuit breaker implementation."""
        
        def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 10.0):
            self.failure_threshold = failure_threshold
            self.recovery_timeout = recovery_timeout
            self.failure_count = 0
            self.last_failure_time = None
            self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        
        def can_execute(self) -> bool:
            """Check if request can be executed."""
            if self.state == "CLOSED":
                return True
            elif self.state == "OPEN":
                if (datetime.now() - self.last_failure_time).total_seconds() > self.recovery_timeout:
                    self.state = "HALF_OPEN"
                    return True
                return False
            else:  # HALF_OPEN
                return True
        
        def record_success(self):
            """Record successful request."""
            self.failure_count = 0
            self.state = "CLOSED"
        
        def record_failure(self):
            """Record failed request."""
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
    
    # Test circuit breaker
    circuit_breaker = SimpleCircuitBreaker(failure_threshold=3, recovery_timeout=5.0)
    failing_url = "https://httpbin.org/status/500"
    
    config = FetchConfig(total_timeout=5.0, max_retries=0)
    
    async with WebFetcher(config) as fetcher:
        for i in range(8):  # Try 8 requests
            print(f"Request {i+1}:")
            
            if not circuit_breaker.can_execute():
                print("   🚫 Circuit breaker OPEN - request blocked")
                await asyncio.sleep(1)
                continue
            
            try:
                request = FetchRequest(url=failing_url, content_type=ContentType.TEXT)
                result = await fetcher.fetch_single(request)
                
                if result.is_success:
                    circuit_breaker.record_success()
                    print("   ✅ Success - circuit breaker reset")
                else:
                    circuit_breaker.record_failure()
                    print(f"   ❌ Failed - circuit breaker state: {circuit_breaker.state}")
                    
            except Exception as e:
                circuit_breaker.record_failure()
                print(f"   ❌ Exception - circuit breaker state: {circuit_breaker.state}")
            
            await asyncio.sleep(0.5)
    
    print()


async def example_error_recovery_strategies():
    """Demonstrate various error recovery strategies."""
    print("=== Error Recovery Strategies ===\n")
    
    async def retry_with_backoff(url: str, max_attempts: int = 3):
        """Retry with exponential backoff."""
        print(f"   Retry with backoff strategy:")
        
        for attempt in range(max_attempts):
            try:
                delay = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                if attempt > 0:
                    print(f"     Waiting {delay}s before retry {attempt + 1}")
                    await asyncio.sleep(delay)
                
                config = FetchConfig(total_timeout=5.0, max_retries=0)
                async with WebFetcher(config) as fetcher:
                    request = FetchRequest(url=url, content_type=ContentType.TEXT)
                    result = await fetcher.fetch_single(request)
                    
                    if result.is_success:
                        print(f"     ✅ Success on attempt {attempt + 1}")
                        return result
                    else:
                        print(f"     ❌ Attempt {attempt + 1} failed: {result.error}")
                        
            except Exception as e:
                print(f"     ❌ Attempt {attempt + 1} exception: {e}")
        
        print("     ❌ All retry attempts failed")
        return None
    
    async def adaptive_timeout(url: str):
        """Adaptive timeout strategy."""
        print(f"   Adaptive timeout strategy:")
        
        timeouts = [5.0, 10.0, 20.0]  # Progressively longer timeouts
        
        for i, timeout in enumerate(timeouts):
            try:
                print(f"     Attempt {i + 1} with {timeout}s timeout")
                
                config = FetchConfig(total_timeout=timeout, max_retries=0)
                async with WebFetcher(config) as fetcher:
                    request = FetchRequest(url=url, content_type=ContentType.TEXT)
                    result = await fetcher.fetch_single(request)
                    
                    if result.is_success:
                        print(f"     ✅ Success with {timeout}s timeout")
                        return result
                    else:
                        print(f"     ❌ Failed with {timeout}s timeout: {result.error}")
                        
            except TimeoutError:
                print(f"     ⏰ Timeout with {timeout}s limit")
            except Exception as e:
                print(f"     ❌ Exception: {e}")
        
        print("     ❌ All timeout strategies failed")
        return None
    
    # Test recovery strategies
    slow_url = "https://httpbin.org/delay/3"
    
    print("1. Testing retry with backoff:")
    await retry_with_backoff("https://httpbin.org/status/500")
    
    print("\n2. Testing adaptive timeout:")
    await adaptive_timeout(slow_url)
    
    print()


async def example_batch_error_handling():
    """Demonstrate error handling in batch operations."""
    print("=== Batch Error Handling Examples ===\n")

    # Mix of successful and failing URLs
    test_urls = [
        "https://httpbin.org/get",           # Should succeed
        "https://httpbin.org/status/404",    # Will fail
        "https://httpbin.org/json",          # Should succeed
        "https://httpbin.org/status/500",    # Will fail
        "https://invalid-url-12345.com",     # Will fail
        "https://httpbin.org/user-agent",    # Should succeed
    ]

    print("1. Batch processing with mixed results:")

    config = FetchConfig(
        total_timeout=10.0,
        max_retries=1,
        max_concurrent_requests=3
    )

    from web_fetch import fetch_urls

    try:
        batch_result = await fetch_urls(test_urls, ContentType.TEXT, config)

        print(f"   Total requests: {batch_result.total_requests}")
        print(f"   Successful: {batch_result.successful_requests}")
        print(f"   Failed: {batch_result.failed_requests}")
        print(f"   Success rate: {batch_result.success_rate:.1f}%")
        print(f"   Total time: {batch_result.total_time:.2f}s")

        print("\n   Individual results:")
        for i, result in enumerate(batch_result.results):
            status = "✅" if result.is_success else "❌"
            print(f"     {status} URL {i+1}: {result.status_code} - {result.url}")
            if not result.is_success and result.error:
                print(f"        Error: {result.error}")

    except Exception as e:
        print(f"   ❌ Batch operation failed: {e}")

    print()


async def example_content_parsing_errors():
    """Demonstrate handling content parsing errors."""
    print("=== Content Parsing Error Examples ===\n")

    parsing_tests = [
        ("https://httpbin.org/html", ContentType.JSON, "HTML parsed as JSON"),
        ("https://httpbin.org/json", ContentType.HTML, "JSON parsed as HTML"),
        ("https://httpbin.org/xml", ContentType.JSON, "XML parsed as JSON"),
        ("https://httpbin.org/status/204", ContentType.JSON, "Empty content as JSON"),
    ]

    async with WebFetcher() as fetcher:
        for url, content_type, description in parsing_tests:
            print(f"Testing {description}:")

            try:
                request = FetchRequest(url=url, content_type=content_type)
                result = await fetcher.fetch_single(request)

                if result.is_success:
                    print(f"   ✅ Parsing succeeded (unexpected)")
                    print(f"   Content type: {type(result.content)}")
                else:
                    print(f"   ❌ Expected parsing failure: {result.error}")

            except ContentError as e:
                print(f"   ❌ Content parsing error: {e}")
            except Exception as e:
                print(f"   ❌ Unexpected error: {e}")

            print()


async def example_resource_cleanup():
    """Demonstrate proper resource cleanup in error scenarios."""
    print("=== Resource Cleanup Examples ===\n")

    print("1. Proper cleanup with context managers:")

    try:
        async with WebFetcher() as fetcher:
            # Simulate an error during operation
            request = FetchRequest(url="https://httpbin.org/status/500")
            result = await fetcher.fetch_single(request)

            if not result.is_success:
                raise Exception("Simulated error after fetcher creation")

    except Exception as e:
        print(f"   ❌ Error occurred: {e}")
        print("   ✅ Resources automatically cleaned up by context manager")

    print("\n2. Manual cleanup in error scenarios:")

    fetcher = None
    try:
        fetcher = WebFetcher()
        await fetcher.__aenter__()

        # Simulate error
        raise Exception("Simulated error")

    except Exception as e:
        print(f"   ❌ Error occurred: {e}")
    finally:
        if fetcher:
            try:
                await fetcher.__aexit__(None, None, None)
                print("   ✅ Manual cleanup completed")
            except Exception as cleanup_error:
                print(f"   ❌ Cleanup error: {cleanup_error}")

    print()


async def main():
    """Run all error handling examples."""
    print("Web Fetch Library - Comprehensive Error Handling Examples")
    print("=" * 70)
    print()

    try:
        await example_basic_error_handling()
        await example_specific_exception_handling()
        await example_retry_strategies()
        await example_timeout_handling()
        await example_graceful_degradation()
        await example_circuit_breaker_pattern()
        await example_error_recovery_strategies()
        await example_batch_error_handling()
        await example_content_parsing_errors()
        await example_resource_cleanup()

        print("🎉 All error handling examples completed!")
        print("\nKey Takeaways:")
        print("- Always handle specific exception types")
        print("- Use appropriate retry strategies")
        print("- Configure timeouts based on use case")
        print("- Implement fallback mechanisms")
        print("- Consider circuit breaker patterns for resilience")
        print("- Handle batch operation errors gracefully")
        print("- Validate content parsing results")
        print("- Ensure proper resource cleanup")
        print("- Log errors appropriately for debugging")

    except Exception as e:
        print(f"❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
