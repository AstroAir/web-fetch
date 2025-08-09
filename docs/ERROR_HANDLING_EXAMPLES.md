# Error Handling Examples

This document provides comprehensive examples for handling errors, timeouts, retries, and failure scenarios in the web-fetch library.

## Table of Contents

- [Error Handling Examples](#error-handling-examples)
  - [Table of Contents](#table-of-contents)
  - [Exception Hierarchy](#exception-hierarchy)
  - [Basic Error Handling](#basic-error-handling)
    - [Simple Error Checking](#simple-error-checking)
    - [Exception-Based Error Handling](#exception-based-error-handling)
  - [Specific Exception Types](#specific-exception-types)
    - [Handling Different Error Types](#handling-different-error-types)
  - [Retry Strategies](#retry-strategies)
    - [Exponential Backoff](#exponential-backoff)
    - [Custom Retry Logic](#custom-retry-logic)
    - [Conditional Retries](#conditional-retries)
  - [Timeout Handling](#timeout-handling)
    - [Different Timeout Strategies](#different-timeout-strategies)
    - [Adaptive Timeouts](#adaptive-timeouts)
  - [Graceful Degradation](#graceful-degradation)
    - [Fallback URL Strategy](#fallback-url-strategy)
    - [Service Degradation](#service-degradation)
  - [Circuit Breaker Pattern](#circuit-breaker-pattern)
    - [Simple Circuit Breaker](#simple-circuit-breaker)
  - [Batch Error Handling](#batch-error-handling)
    - [Mixed Success/Failure Handling](#mixed-successfailure-handling)
    - [Partial Success Handling](#partial-success-handling)
  - [Content Parsing Errors](#content-parsing-errors)
    - [Handling Parse Failures](#handling-parse-failures)
  - [Resource Cleanup](#resource-cleanup)
    - [Proper Resource Management](#proper-resource-management)
  - [Best Practices](#best-practices)
    - [Error Handling Guidelines](#error-handling-guidelines)
  - [Summary](#summary)

## Exception Hierarchy

The web-fetch library provides a comprehensive exception hierarchy:

```
WebFetchError (base exception)
├── NetworkError
│   ├── ConnectionError
│   ├── TimeoutError
│   └── DNSError
├── HTTPError
│   ├── AuthenticationError (401, 403)
│   ├── NotFoundError (404)
│   ├── RateLimitError (429)
│   └── ServerError (5xx)
└── ContentError
    ├── ParseError
    └── ValidationError
```

## Basic Error Handling

### Simple Error Checking

```python
import asyncio
from web_fetch import fetch_url, ContentType

async def basic_error_handling():
    result = await fetch_url("https://httpbin.org/status/404", ContentType.TEXT)
    
    if result.is_success:
        print(f"Success: {result.content}")
    else:
        print(f"Failed: {result.error}")
        print(f"Status code: {result.status_code}")
        print(f"Response time: {result.response_time}")

asyncio.run(basic_error_handling())
```

### Exception-Based Error Handling

```python
from web_fetch import WebFetcher, FetchRequest, WebFetchError, HTTPError

async def exception_handling():
    async with WebFetcher() as fetcher:
        try:
            request = FetchRequest(url="https://httpbin.org/status/500")
            result = await fetcher.fetch_single(request)
            
            if result.is_success:
                print("Success!")
            else:
                print(f"Request failed: {result.error}")
                
        except HTTPError as e:
            print(f"HTTP Error {e.status_code}: {e}")
        except WebFetchError as e:
            print(f"Web fetch error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

asyncio.run(exception_handling())
```

## Specific Exception Types

### Handling Different Error Types

```python
from web_fetch import (
    WebFetcher, FetchRequest, FetchConfig,
    TimeoutError, ConnectionError, AuthenticationError,
    NotFoundError, RateLimitError, ServerError
)

async def specific_error_handling():
    # Configure with short timeout to demonstrate timeout errors
    config = FetchConfig(total_timeout=2.0, max_retries=1)
    
    test_cases = [
        ("https://httpbin.org/delay/5", "Timeout test"),
        ("https://httpbin.org/status/401", "Authentication error"),
        ("https://httpbin.org/status/404", "Not found error"),
        ("https://httpbin.org/status/429", "Rate limit error"),
        ("https://httpbin.org/status/500", "Server error"),
        ("https://invalid-domain-12345.com", "Connection error"),
    ]
    
    async with WebFetcher(config) as fetcher:
        for url, description in test_cases:
            print(f"Testing {description}:")
            
            try:
                request = FetchRequest(url=url)
                result = await fetcher.fetch_single(request)
                
                if result.is_success:
                    print("  ✅ Success")
                else:
                    print(f"  ❌ Failed: {result.error}")
                    
            except TimeoutError as e:
                print(f"  ⏰ Timeout: {e}")
            except AuthenticationError as e:
                print(f"  🔐 Authentication failed: {e}")
            except NotFoundError as e:
                print(f"  🔍 Not found: {e}")
            except RateLimitError as e:
                print(f"  🚦 Rate limited: {e}")
            except ServerError as e:
                print(f"  🔥 Server error: {e}")
            except ConnectionError as e:
                print(f"  🔌 Connection failed: {e}")

asyncio.run(specific_error_handling())
```

## Retry Strategies

### Exponential Backoff

```python
from web_fetch import FetchConfig, RetryStrategy

async def exponential_backoff_example():
    config = FetchConfig(
        max_retries=5,
        retry_delay=1.0,
        retry_strategy=RetryStrategy.EXPONENTIAL,
        total_timeout=30.0
    )
    
    async with WebFetcher(config) as fetcher:
        request = FetchRequest(url="https://httpbin.org/status/500")
        result = await fetcher.fetch_single(request)
        
        print(f"Retries attempted: {result.retry_count}")
        print(f"Total time: {result.response_time:.2f}s")

asyncio.run(exponential_backoff_example())
```

### Custom Retry Logic

```python
import asyncio
from datetime import datetime

async def custom_retry_logic(url: str, max_attempts: int = 3):
    """Custom retry implementation with exponential backoff."""
    
    for attempt in range(max_attempts):
        try:
            # Calculate delay: 1s, 2s, 4s, 8s...
            if attempt > 0:
                delay = 2 ** (attempt - 1)
                print(f"Waiting {delay}s before retry {attempt + 1}")
                await asyncio.sleep(delay)
            
            config = FetchConfig(total_timeout=10.0, max_retries=0)
            async with WebFetcher(config) as fetcher:
                request = FetchRequest(url=url)
                result = await fetcher.fetch_single(request)
                
                if result.is_success:
                    print(f"Success on attempt {attempt + 1}")
                    return result
                else:
                    print(f"Attempt {attempt + 1} failed: {result.error}")
                    
        except Exception as e:
            print(f"Attempt {attempt + 1} exception: {e}")
    
    print("All retry attempts failed")
    return None

# Usage
asyncio.run(custom_retry_logic("https://httpbin.org/status/500"))
```

### Conditional Retries

```python
async def conditional_retry_example():
    """Retry only for specific error types."""
    
    def should_retry(error: Exception) -> bool:
        """Determine if error is retryable."""
        if isinstance(error, (TimeoutError, ConnectionError)):
            return True
        if isinstance(error, ServerError) and error.status_code >= 500:
            return True
        if isinstance(error, RateLimitError):
            return True
        return False
    
    max_attempts = 3
    url = "https://httpbin.org/status/503"
    
    for attempt in range(max_attempts):
        try:
            config = FetchConfig(total_timeout=5.0, max_retries=0)
            async with WebFetcher(config) as fetcher:
                request = FetchRequest(url=url)
                result = await fetcher.fetch_single(request)
                
                if result.is_success:
                    print(f"Success on attempt {attempt + 1}")
                    break
                else:
                    print(f"Attempt {attempt + 1} failed: {result.error}")
                    
        except Exception as e:
            print(f"Attempt {attempt + 1} exception: {e}")
            
            if attempt < max_attempts - 1 and should_retry(e):
                delay = 2 ** attempt
                print(f"Retrying in {delay}s...")
                await asyncio.sleep(delay)
            else:
                print("Not retrying this error type")
                break

asyncio.run(conditional_retry_example())
```

## Timeout Handling

### Different Timeout Strategies

```python
async def timeout_strategies():
    """Demonstrate different timeout configurations."""
    
    timeout_configs = [
        (FetchConfig(total_timeout=5.0), "Short timeout"),
        (FetchConfig(total_timeout=15.0), "Medium timeout"),
        (FetchConfig(total_timeout=30.0), "Long timeout"),
        (FetchConfig(
            connect_timeout=5.0,
            read_timeout=10.0,
            total_timeout=20.0
        ), "Separate timeouts"),
    ]
    
    slow_url = "https://httpbin.org/delay/8"
    
    for config, description in timeout_configs:
        print(f"Testing {description}:")
        
        try:
            start_time = datetime.now()
            async with WebFetcher(config) as fetcher:
                request = FetchRequest(url=slow_url)
                result = await fetcher.fetch_single(request)
                
                duration = (datetime.now() - start_time).total_seconds()
                
                if result.is_success:
                    print(f"  ✅ Success in {duration:.2f}s")
                else:
                    print(f"  ❌ Failed in {duration:.2f}s: {result.error}")
                    
        except TimeoutError as e:
            duration = (datetime.now() - start_time).total_seconds()
            print(f"  ⏰ Timeout after {duration:.2f}s")

asyncio.run(timeout_strategies())
```

### Adaptive Timeouts

```python
async def adaptive_timeout_example():
    """Implement adaptive timeout based on response times."""
    
    class AdaptiveTimeout:
        def __init__(self, initial_timeout: float = 10.0):
            self.timeout = initial_timeout
            self.response_times = []
            self.max_history = 10
        
        def update_timeout(self, response_time: float, success: bool):
            """Update timeout based on recent performance."""
            if success:
                self.response_times.append(response_time)
                if len(self.response_times) > self.max_history:
                    self.response_times.pop(0)
                
                # Set timeout to 2x average response time
                avg_time = sum(self.response_times) / len(self.response_times)
                self.timeout = max(5.0, avg_time * 2)
        
        def get_timeout(self) -> float:
            return self.timeout
    
    adaptive = AdaptiveTimeout()
    urls = [
        "https://httpbin.org/delay/1",
        "https://httpbin.org/delay/2",
        "https://httpbin.org/delay/3",
    ]
    
    for url in urls:
        timeout = adaptive.get_timeout()
        print(f"Using timeout: {timeout:.1f}s for {url}")
        
        try:
            config = FetchConfig(total_timeout=timeout)
            start_time = datetime.now()
            
            async with WebFetcher(config) as fetcher:
                request = FetchRequest(url=url)
                result = await fetcher.fetch_single(request)
                
                duration = (datetime.now() - start_time).total_seconds()
                adaptive.update_timeout(duration, result.is_success)
                
                if result.is_success:
                    print(f"  ✅ Success in {duration:.2f}s")
                else:
                    print(f"  ❌ Failed: {result.error}")
                    
        except TimeoutError:
            print(f"  ⏰ Timeout after {timeout:.1f}s")

asyncio.run(adaptive_timeout_example())
```

## Graceful Degradation

### Fallback URL Strategy

```python
async def fallback_url_strategy():
    """Implement fallback URLs for resilience."""
    
    async def fetch_with_fallbacks(primary_url: str, fallback_urls: list):
        """Try primary URL, then fallbacks."""
        
        all_urls = [primary_url] + fallback_urls
        
        for i, url in enumerate(all_urls):
            url_type = "primary" if i == 0 else f"fallback {i}"
            print(f"Trying {url_type}: {url}")
            
            try:
                config = FetchConfig(total_timeout=5.0, max_retries=1)
                async with WebFetcher(config) as fetcher:
                    request = FetchRequest(url=url)
                    result = await fetcher.fetch_single(request)
                    
                    if result.is_success:
                        print(f"  ✅ Success with {url_type}")
                        return result
                    else:
                        print(f"  ❌ {url_type} failed: {result.error}")
                        
            except Exception as e:
                print(f"  ❌ {url_type} exception: {e}")
        
        print("All URLs failed")
        return None
    
    # Example usage
    primary = "https://httpbin.org/status/500"  # Will fail
    fallbacks = [
        "https://httpbin.org/status/503",  # Will also fail
        "https://httpbin.org/get",         # Should succeed
    ]
    
    result = await fetch_with_fallbacks(primary, fallbacks)
    if result:
        print(f"Final result: {len(result.content)} characters")

asyncio.run(fallback_url_strategy())
```

### Service Degradation

```python
async def service_degradation_example():
    """Demonstrate graceful service degradation."""
    
    async def fetch_with_degradation(url: str):
        """Fetch with progressive degradation."""
        
        # Try full-featured request first
        try:
            config = FetchConfig(
                total_timeout=10.0,
                max_retries=2,
                verify_ssl=True
            )
            
            async with WebFetcher(config) as fetcher:
                request = FetchRequest(url=url, content_type=ContentType.JSON)
                result = await fetcher.fetch_single(request)
                
                if result.is_success:
                    return {"status": "full", "data": result.content}
        
        except Exception as e:
            print(f"Full request failed: {e}")
        
        # Degrade to basic request
        try:
            config = FetchConfig(
                total_timeout=5.0,
                max_retries=0,
                verify_ssl=False  # Less strict
            )
            
            async with WebFetcher(config) as fetcher:
                request = FetchRequest(url=url, content_type=ContentType.TEXT)
                result = await fetcher.fetch_single(request)
                
                if result.is_success:
                    return {"status": "degraded", "data": result.content[:100]}
        
        except Exception as e:
            print(f"Degraded request failed: {e}")
        
        # Final fallback - return cached or default data
        return {"status": "fallback", "data": "Service temporarily unavailable"}
    
    # Test degradation
    result = await fetch_with_degradation("https://httpbin.org/status/500")
    print(f"Service status: {result['status']}")
    print(f"Data: {result['data']}")

asyncio.run(service_degradation_example())
```

## Circuit Breaker Pattern

### Simple Circuit Breaker

```python
from datetime import datetime, timedelta

class CircuitBreaker:
    """Simple circuit breaker implementation."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
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
            if self._should_attempt_reset():
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

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True

        time_since_failure = datetime.now() - self.last_failure_time
        return time_since_failure.total_seconds() >= self.recovery_timeout

async def circuit_breaker_example():
    """Demonstrate circuit breaker pattern."""

    circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
    failing_url = "https://httpbin.org/status/500"

    config = FetchConfig(total_timeout=5.0, max_retries=0)

    for i in range(10):
        print(f"Request {i+1}:")

        if not circuit_breaker.can_execute():
            print("  🚫 Circuit breaker OPEN - request blocked")
            await asyncio.sleep(1)
            continue

        try:
            async with WebFetcher(config) as fetcher:
                request = FetchRequest(url=failing_url)
                result = await fetcher.fetch_single(request)

                if result.is_success:
                    circuit_breaker.record_success()
                    print("  ✅ Success - circuit breaker reset")
                else:
                    circuit_breaker.record_failure()
                    print(f"  ❌ Failed - circuit breaker state: {circuit_breaker.state}")

        except Exception as e:
            circuit_breaker.record_failure()
            print(f"  ❌ Exception - circuit breaker state: {circuit_breaker.state}")

        await asyncio.sleep(0.5)

asyncio.run(circuit_breaker_example())
```

## Batch Error Handling

### Mixed Success/Failure Handling

```python
from web_fetch import fetch_urls

async def batch_error_handling():
    """Handle errors in batch operations."""

    # Mix of working and failing URLs
    urls = [
        "https://httpbin.org/get",           # Should work
        "https://httpbin.org/status/404",    # Will fail
        "https://httpbin.org/json",          # Should work
        "https://httpbin.org/status/500",    # Will fail
        "https://invalid-domain-12345.com",  # Will fail
    ]

    config = FetchConfig(
        total_timeout=10.0,
        max_retries=1,
        max_concurrent_requests=3
    )

    try:
        batch_result = await fetch_urls(urls, ContentType.TEXT, config)

        print(f"Batch Results:")
        print(f"  Total: {batch_result.total_requests}")
        print(f"  Successful: {batch_result.successful_requests}")
        print(f"  Failed: {batch_result.failed_requests}")
        print(f"  Success rate: {batch_result.success_rate:.1f}%")

        # Process individual results
        successful_results = []
        failed_results = []

        for result in batch_result.results:
            if result.is_success:
                successful_results.append(result)
            else:
                failed_results.append(result)

        print(f"\nSuccessful requests ({len(successful_results)}):")
        for result in successful_results:
            print(f"  ✅ {result.url} - {result.status_code}")

        print(f"\nFailed requests ({len(failed_results)}):")
        for result in failed_results:
            print(f"  ❌ {result.url} - {result.error}")

    except Exception as e:
        print(f"Batch operation failed: {e}")

asyncio.run(batch_error_handling())
```

### Partial Success Handling

```python
async def partial_success_handling():
    """Handle partial success in batch operations."""

    urls = [
        "https://httpbin.org/get",
        "https://httpbin.org/status/404",
        "https://httpbin.org/json",
        "https://httpbin.org/status/500",
    ]

    batch_result = await fetch_urls(urls, ContentType.JSON)

    # Define success threshold (e.g., at least 50% success)
    success_threshold = 0.5

    if batch_result.success_rate >= success_threshold:
        print(f"Batch operation acceptable: {batch_result.success_rate:.1f}% success")

        # Process successful results
        for result in batch_result.results:
            if result.is_success:
                print(f"Processing: {result.url}")
                # Process the successful result
            else:
                print(f"Skipping failed: {result.url} - {result.error}")
    else:
        print(f"Batch operation failed: {batch_result.success_rate:.1f}% success rate too low")

        # Implement fallback strategy
        print("Implementing fallback strategy...")
        # Could retry failed requests, use cached data, etc.

asyncio.run(partial_success_handling())
```

## Content Parsing Errors

### Handling Parse Failures

```python
from web_fetch import ContentError

async def content_parsing_errors():
    """Handle content parsing errors gracefully."""

    parsing_tests = [
        ("https://httpbin.org/html", ContentType.JSON, "HTML as JSON"),
        ("https://httpbin.org/json", ContentType.HTML, "JSON as HTML"),
        ("https://httpbin.org/status/204", ContentType.JSON, "Empty content"),
    ]

    async with WebFetcher() as fetcher:
        for url, content_type, description in parsing_tests:
            print(f"Testing {description}:")

            try:
                request = FetchRequest(url=url, content_type=content_type)
                result = await fetcher.fetch_single(request)

                if result.is_success:
                    print(f"  ✅ Parsed successfully: {type(result.content)}")
                else:
                    print(f"  ❌ Parse failed: {result.error}")

                    # Fallback to raw content
                    raw_request = FetchRequest(url=url, content_type=ContentType.RAW)
                    raw_result = await fetcher.fetch_single(raw_request)

                    if raw_result.is_success:
                        print(f"  📄 Raw content available: {len(raw_result.content)} bytes")

            except ContentError as e:
                print(f"  ❌ Content error: {e}")
            except Exception as e:
                print(f"  ❌ Unexpected error: {e}")

asyncio.run(content_parsing_errors())
```

## Resource Cleanup

### Proper Resource Management

```python
async def resource_cleanup_examples():
    """Demonstrate proper resource cleanup."""

    print("1. Using context managers (recommended):")
    try:
        async with WebFetcher() as fetcher:
            request = FetchRequest(url="https://httpbin.org/get")
            result = await fetcher.fetch_single(request)

            # Simulate an error
            if result.is_success:
                raise Exception("Simulated error after successful request")

    except Exception as e:
        print(f"  Error: {e}")
        print("  ✅ Resources automatically cleaned up")

    print("\n2. Manual cleanup (when context manager can't be used):")
    fetcher = None
    try:
        fetcher = WebFetcher()
        await fetcher.__aenter__()

        request = FetchRequest(url="https://httpbin.org/get")
        result = await fetcher.fetch_single(request)

        # Simulate error
        raise Exception("Simulated error")

    except Exception as e:
        print(f"  Error: {e}")
    finally:
        if fetcher:
            try:
                await fetcher.__aexit__(None, None, None)
                print("  ✅ Manual cleanup completed")
            except Exception as cleanup_error:
                print(f"  ❌ Cleanup failed: {cleanup_error}")

asyncio.run(resource_cleanup_examples())
```

## Best Practices

### Error Handling Guidelines

```python
# 1. Always use specific exception types
async def good_error_handling():
    try:
        result = await fetch_url("https://example.com")
    except TimeoutError:
        # Handle timeout specifically
        print("Request timed out - maybe retry with longer timeout")
    except ConnectionError:
        # Handle connection issues
        print("Connection failed - check network or try fallback URL")
    except HTTPError as e:
        if e.status_code == 429:
            # Handle rate limiting
            print("Rate limited - implement backoff")
        elif e.status_code >= 500:
            # Handle server errors
            print("Server error - retry might help")
        else:
            # Handle other HTTP errors
            print(f"HTTP error {e.status_code}")
    except WebFetchError:
        # Handle other web fetch errors
        print("General web fetch error")
    except Exception:
        # Handle unexpected errors
        print("Unexpected error occurred")

# 2. Implement proper logging
import logging

logger = logging.getLogger(__name__)

async def error_handling_with_logging():
    try:
        result = await fetch_url("https://example.com")
        logger.info(f"Successfully fetched {len(result.content)} bytes")
    except Exception as e:
        logger.error(f"Failed to fetch URL: {e}", exc_info=True)
        # Re-raise or handle as appropriate
        raise

# 3. Use configuration for error handling behavior
def create_resilient_config():
    return FetchConfig(
        total_timeout=30.0,
        max_retries=3,
        retry_delay=2.0,
        retry_strategy=RetryStrategy.EXPONENTIAL,
        max_concurrent_requests=10
    )

# 4. Implement health checks
async def health_check(url: str) -> bool:
    """Check if a service is healthy."""
    try:
        config = FetchConfig(total_timeout=5.0, max_retries=0)
        async with WebFetcher(config) as fetcher:
            request = FetchRequest(url=url)
            result = await fetcher.fetch_single(request)
            return result.is_success and result.status_code == 200
    except Exception:
        return False

# 5. Implement graceful shutdown
class GracefulShutdown:
    def __init__(self):
        self.shutdown_requested = False
        self.active_requests = 0

    async def fetch_with_shutdown_check(self, url: str):
        if self.shutdown_requested:
            raise Exception("Shutdown in progress")

        self.active_requests += 1
        try:
            result = await fetch_url(url)
            return result
        finally:
            self.active_requests -= 1

    async def shutdown(self, timeout: float = 30.0):
        self.shutdown_requested = True

        # Wait for active requests to complete
        start_time = datetime.now()
        while self.active_requests > 0:
            if (datetime.now() - start_time).total_seconds() > timeout:
                print(f"Timeout waiting for {self.active_requests} requests")
                break
            await asyncio.sleep(0.1)

        print("Graceful shutdown completed")
```

## Summary

Key principles for robust error handling:

1. **Use specific exception types** - Handle different errors appropriately
2. **Implement retry strategies** - Use exponential backoff for transient failures
3. **Configure timeouts properly** - Balance responsiveness with reliability
4. **Plan for graceful degradation** - Provide fallback mechanisms
5. **Use circuit breakers** - Prevent cascading failures
6. **Handle batch operations carefully** - Process partial successes
7. **Validate content parsing** - Handle parse failures gracefully
8. **Ensure resource cleanup** - Use context managers when possible
9. **Log errors appropriately** - Include context for debugging
10. **Test error scenarios** - Verify error handling works as expected
