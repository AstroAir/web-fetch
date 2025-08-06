#!/usr/bin/env python3
"""
Basic usage examples for the web_fetch library.

This script demonstrates various ways to use the async web fetcher
with different content types and configurations.
"""

import asyncio
import json

from web_fetch import (
    ContentType,
    FetchConfig,
    FetchRequest,
    WebFetcher,
    fetch_url,
    fetch_urls,
)


async def example_single_url() -> None:
    """Example: Fetch a single URL with different content types."""
    print("=== Single URL Fetching Examples ===\n")
    
    # Example 1: Fetch as text (default)
    print("1. Fetching as text:")
    result = await fetch_url("https://httpbin.org/get", ContentType.TEXT)
    print(f"Status: {result.status_code}")
    print(f"Content length: {len(result.content) if result.content else 0}")
    print(f"Response time: {result.response_time:.2f}s")
    print(f"Success: {result.is_success}\n")
    
    # Example 2: Fetch as JSON
    print("2. Fetching as JSON:")
    result = await fetch_url("https://httpbin.org/json", ContentType.JSON)
    if result.is_success and isinstance(result.content, dict):
        print(f"JSON keys: {list(result.content.keys())}")
        print(f"Slideshow title: {result.content.get('slideshow', {}).get('title', 'N/A')}")
    print()
    
    # Example 3: Fetch HTML and parse
    print("3. Fetching and parsing HTML:")
    result = await fetch_url("https://httpbin.org/html", ContentType.HTML)
    if result.is_success and isinstance(result.content, dict):
        print(f"Page title: {result.content.get('title', 'N/A')}")
        print(f"Number of links: {len(result.content.get('links', []))}")
        print(f"Number of images: {len(result.content.get('images', []))}")
    print()


async def example_batch_fetching() -> None:
    """Example: Fetch multiple URLs concurrently."""
    print("=== Batch Fetching Example ===\n")
    
    urls = [
        "https://httpbin.org/get",
        "https://httpbin.org/json",
        "https://httpbin.org/html",
        "https://httpbin.org/status/200",
        "https://httpbin.org/delay/1",
    ]
    
    print(f"Fetching {len(urls)} URLs concurrently...")
    result = await fetch_urls(urls, ContentType.TEXT)
    
    print(f"Total requests: {result.total_requests}")
    print(f"Successful: {result.successful_requests}")
    print(f"Failed: {result.failed_requests}")
    print(f"Success rate: {result.success_rate:.1f}%")
    print(f"Total time: {result.total_time:.2f}s")
    print()
    
    # Show individual results
    for i, fetch_result in enumerate(result.results):
        print(f"URL {i+1}: {fetch_result.url}")
        print(f"  Status: {fetch_result.status_code}")
        print(f"  Time: {fetch_result.response_time:.2f}s")
        print(f"  Success: {fetch_result.is_success}")
        if fetch_result.error:
            print(f"  Error: {fetch_result.error}")
        print()


async def example_custom_configuration() -> None:
    """Example: Using custom configuration and headers."""
    print("=== Custom Configuration Example ===\n")
    
    # Create custom configuration
    config = FetchConfig(
        total_timeout=15.0,
        max_concurrent_requests=5,
        max_retries=2,
        verify_ssl=True,
    )
    
    # Custom headers
    custom_headers = {
        "User-Agent": "WebFetch-Example/1.0",
        "Accept": "application/json",
        "X-Custom-Header": "example-value"
    }
    
    # Create custom request
    from pydantic import TypeAdapter, HttpUrl
    url_adapter = TypeAdapter(HttpUrl)
    request = FetchRequest(
        url=url_adapter.validate_python("https://httpbin.org/headers"),
        content_type=ContentType.JSON,
        headers=custom_headers
    )
    
    async with WebFetcher(config) as fetcher:
        result = await fetcher.fetch_single(request)
        
        if result.is_success and isinstance(result.content, dict):
            headers_received = result.content.get('headers', {})
            print("Headers sent to server:")
            for key, value in headers_received.items():
                if key.lower().startswith(('user-agent', 'accept', 'x-custom')):
                    print(f"  {key}: {value}")
        print()


async def example_error_handling() -> None:
    """Example: Demonstrating error handling and retry logic."""
    print("=== Error Handling Example ===\n")
    
    # Configure with retries
    config = FetchConfig(
        max_retries=3,
        retry_delay=0.5,
        total_timeout=5.0
    )
    
    # Test URLs that will cause different types of errors
    test_urls = [
        "https://httpbin.org/status/404",  # Not found
        "https://httpbin.org/status/500",  # Server error
        "https://httpbin.org/delay/10",    # Timeout
        "https://invalid-domain-that-does-not-exist.com",  # DNS error
    ]
    
    async with WebFetcher(config) as fetcher:
        from pydantic import TypeAdapter, HttpUrl
        url_adapter = TypeAdapter(HttpUrl)

        for url in test_urls:
            print(f"Testing: {url}")
            request = FetchRequest(url=url_adapter.validate_python(url), content_type=ContentType.TEXT)
            result = await fetcher.fetch_single(request)
            
            print(f"  Status: {result.status_code}")
            print(f"  Success: {result.is_success}")
            print(f"  Retries: {result.retry_count}")
            if result.error:
                print(f"  Error: {result.error}")
            print()


async def example_post_request() -> None:
    """Example: Making POST requests with data."""
    print("=== POST Request Example ===\n")
    
    # JSON data
    json_data = {
        "name": "WebFetch",
        "version": "1.0",
        "features": ["async", "modern", "robust"]
    }
    
    from pydantic import TypeAdapter, HttpUrl
    url_adapter = TypeAdapter(HttpUrl)
    request = FetchRequest(
        url=url_adapter.validate_python("https://httpbin.org/post"),
        method="POST",
        data=json_data,
        content_type=ContentType.JSON
    )
    
    async with WebFetcher() as fetcher:
        result = await fetcher.fetch_single(request)
        
        if result.is_success and isinstance(result.content, dict):
            echo_data = result.content.get('json', {})
            print("Data echoed back from server:")
            print(json.dumps(echo_data, indent=2))
        print()


async def main() -> None:
    """Run all examples."""
    print("Web Fetch Library - Usage Examples")
    print("=" * 50)
    print()
    
    try:
        await example_single_url()
        await example_batch_fetching()
        await example_custom_configuration()
        await example_error_handling()
        await example_post_request()
        
        print("All examples completed successfully!")
        
    except Exception as e:
        print(f"Error running examples: {e}")


if __name__ == "__main__":
    asyncio.run(main())
