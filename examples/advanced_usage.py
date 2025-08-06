#!/usr/bin/env python3
"""
Advanced usage examples for the web_fetch library.

This script demonstrates the advanced features including circuit breakers,
request deduplication, response transformation pipelines, and metrics collection.
"""

import asyncio
import json

# Import the enhanced functionality
from web_fetch import WebFetcher, enhanced_fetch_url
from web_fetch.models.http import FetchConfig, FetchRequest, FetchResult
from web_fetch.models.base import ContentType
from web_fetch.utils.circuit_breaker import CircuitBreakerConfig
from web_fetch.utils.transformers import (
    TransformationPipeline,
    JSONPathExtractor,
    HTMLExtractor,
    RegexExtractor,
    DataValidator
)
from web_fetch.utils.metrics import get_metrics_summary


async def example_circuit_breaker() -> None:
    """Demonstrate circuit breaker functionality."""
    print("=== Circuit Breaker Example ===")
    
    # Configure circuit breaker to fail fast on unreliable services
    circuit_config = CircuitBreakerConfig(
        failure_threshold=3,  # Open after 3 failures
        recovery_timeout=10.0,  # Try again after 10 seconds
        success_threshold=2,  # Close after 2 successes
        timeout=5.0  # 5 second timeout per request
    )
    
    # Test with a potentially unreliable endpoint
    urls = [
        "https://httpbin.org/status/500",  # Will fail
        "https://httpbin.org/status/503",  # Will fail
        "https://httpbin.org/status/200",  # Will succeed
    ]
    
    async with WebFetcher(circuit_breaker_config=circuit_config) as fetcher:
        # Use pydantic TypeAdapter to validate URLs to HttpUrl
        from pydantic import TypeAdapter, HttpUrl
        url_adapter = TypeAdapter(HttpUrl)

        for i, url in enumerate(urls * 2):  # Try each URL twice
            try:
                request = FetchRequest(url=url_adapter.validate_python(url))
                result = await fetcher.fetch_single(request)
                print(f"Request {i+1}: {url} -> Status: {result.status_code}")
            except Exception as e:
                print(f"Request {i+1}: {url} -> Error: {e}")
    
    print()


async def example_request_deduplication() -> None:
    """Demonstrate request deduplication."""
    print("=== Request Deduplication Example ===")
    
    # Make multiple identical requests concurrently
    url = "https://httpbin.org/delay/2"  # 2-second delay endpoint
    
    async def make_request(request_id: int) -> FetchResult:
        result = await enhanced_fetch_url(
            url=url,
            enable_deduplication=True,
            enable_metrics=True
        )
        print(f"Request {request_id}: Status {result.status_code}, Response time: {result.response_time:.2f}s")
        return result
    
    # Start 5 identical requests simultaneously
    print("Starting 5 identical requests simultaneously...")
    start_time = asyncio.get_event_loop().time()
    
    tasks = [make_request(i) for i in range(1, 6)]
    await asyncio.gather(*tasks)
    
    end_time = asyncio.get_event_loop().time()
    total_time = end_time - start_time
    
    print(f"Total time for 5 requests: {total_time:.2f}s")
    print("(Should be ~2s due to deduplication, not ~10s)")
    print()


async def example_response_transformation() -> None:
    """Demonstrate response transformation pipeline."""
    print("=== Response Transformation Example ===")
    
    # Create a transformation pipeline for JSON API responses
    json_pipeline = TransformationPipeline([
        JSONPathExtractor({
            "user_id": "$.userId",
            "title": "$.title", 
            "completed": "$.completed"
        }),
        DataValidator({
            "user_id": lambda x: isinstance(x, int) and x > 0,
            "title": lambda x: isinstance(x, str) and len(x) > 0,
            "completed": lambda x: isinstance(x, bool)
        })
    ])
    
    # Fetch and transform JSON data
    result = await enhanced_fetch_url(
        url="https://jsonplaceholder.typicode.com/todos/1",
        content_type=ContentType.JSON,
        transformation_pipeline=json_pipeline
    )
    
    print("Original JSON response transformed to:")
    print(json.dumps(result.content, indent=2))
    print()
    
    # Create a transformation pipeline for HTML content
    html_pipeline = TransformationPipeline([
        HTMLExtractor({
            "title": "title",
            "headings": "h1, h2, h3",
            "links": "a[href]"
        }),
        DataValidator({
            "title": lambda x: isinstance(x, str) and len(x) > 0
        })
    ])
    
    # Fetch and transform HTML content
    result = await enhanced_fetch_url(
        url="https://httpbin.org/html",
        content_type=ContentType.HTML,
        transformation_pipeline=html_pipeline
    )
    
    print("HTML content transformed to structured data:")
    print(json.dumps(result.content, indent=2))
    print()


async def example_regex_extraction() -> None:
    """Demonstrate regex-based data extraction."""
    print("=== Regex Extraction Example ===")
    
    # Create regex extraction pipeline
    regex_pipeline = TransformationPipeline([
        RegexExtractor({
            "email_addresses": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "phone_numbers": r'\b\d{3}-\d{3}-\d{4}\b',
            "urls": r'https?://[^\s<>"{}|\\^`\[\]]+'
        })
    ])
    
    # Test with sample text content
    sample_text = """
    Contact us at support@example.com or sales@company.org
    Call us at 555-123-4567 or 555-987-6543
    Visit our website at https://example.com or https://company.org/about
    """
    
    # Simulate a response with this text
    from web_fetch.models.http import FetchResult
    from datetime import datetime
    
    mock_result = FetchResult(
        url="https://example.com/contact",
        status_code=200,
        headers={},
        content=sample_text,
        content_type=ContentType.TEXT,
        response_time=0.1,
        timestamp=datetime.now()
    )
    # Access a field to avoid "not accessed" warning in strict checkers
    if mock_result.url:
        pass
    
    # Apply transformation
    transformation_result = await regex_pipeline.transform(sample_text, {"url": "https://example.com/contact"})
    
    print("Extracted data using regex:")
    print(json.dumps(transformation_result.data, indent=2))
    print()


async def example_metrics_collection() -> None:
    """Demonstrate metrics collection and monitoring."""
    print("=== Metrics Collection Example ===")
    
    # Make several requests to collect metrics
    urls = [
        "https://httpbin.org/get",
        "https://httpbin.org/status/200",
        "https://httpbin.org/status/404",
        "https://httpbin.org/delay/1",
        "https://jsonplaceholder.typicode.com/posts/1"
    ]
    
    print("Making requests to collect metrics...")
    
    async with WebFetcher(enable_metrics=True) as fetcher:
        from pydantic import TypeAdapter, HttpUrl
        url_adapter = TypeAdapter(HttpUrl)

        for url in urls:
            try:
                request = FetchRequest(url=url_adapter.validate_python(url))
                result = await fetcher.fetch_single(request)
                print(f"✓ {url} -> {result.status_code}")
            except Exception as e:
                print(f"✗ {url} -> Error: {e}")
    
    # Get metrics summary
    metrics = get_metrics_summary()
    print("\nMetrics Summary:")
    print(f"Total requests: {metrics.get('total_requests', 0)}")
    print(f"Recent success rate: {metrics.get('recent_success_rate', 0):.1f}%")
    print(f"Average response time: {metrics.get('recent_avg_response_time', 0):.3f}s")
    
    # Get performance percentiles
    percentiles = metrics.get('performance_percentiles', {})
    if percentiles:
        print("Response time percentiles:")
        for percentile, time_val in percentiles.items():
            print(f"  {percentile}: {time_val:.3f}s")
    
    print()


async def example_comprehensive_usage() -> None:
    """Demonstrate using all features together."""
    print("=== Comprehensive Usage Example ===")
    
    # Configure all features
    config = FetchConfig(
        max_concurrent_requests=3,
        max_retries=2,
        total_timeout=10.0
    )
    
    circuit_config = CircuitBreakerConfig(
        failure_threshold=2,
        recovery_timeout=5.0
    )
    
    # Create a comprehensive transformation pipeline
    api_pipeline = TransformationPipeline([
        JSONPathExtractor({
            "id": "$.id",
            "title": "$.title",
            "body": "$.body"
        }),
        DataValidator({
            "id": lambda x: isinstance(x, int),
            "title": lambda x: isinstance(x, str) and len(x) > 0
        })
    ])
    
    # Test URLs with different characteristics
    test_urls = [
        "https://jsonplaceholder.typicode.com/posts/1",
        "https://jsonplaceholder.typicode.com/posts/2", 
        "https://jsonplaceholder.typicode.com/posts/3"
    ]
    
    print("Fetching with all enhancements enabled...")
    
    async with WebFetcher(
        config=config,
        circuit_breaker_config=circuit_config,
        enable_deduplication=True,
        enable_metrics=True,
        transformation_pipeline=api_pipeline
    ) as fetcher:
        
        from web_fetch.models.http import BatchFetchRequest
        from pydantic import TypeAdapter, HttpUrl

        url_adapter = TypeAdapter(HttpUrl)
        requests = [FetchRequest(url=url_adapter.validate_python(url), content_type=ContentType.JSON) for url in test_urls]
        batch_request = BatchFetchRequest(requests=requests)
        batch_result = await fetcher.fetch_batch(batch_request)

        for i, result in enumerate(batch_result.results):
            print(f"Post {i+1}:")
            if result.content and isinstance(result.content, dict):
                print(f"  ID: {result.content.get('id')}")
                print(f"  Title: {result.content.get('title', 'N/A')[:50]}...")
            print(f"  Status: {result.status_code}")
            print(f"  Response time: {result.response_time:.3f}s")
            print()
    
    # Final metrics
    final_metrics = get_metrics_summary()
    print(f"Final metrics - Total requests: {final_metrics.get('total_requests', 0)}")
    print(f"Overall success rate: {final_metrics.get('hourly_success_rate', 0):.1f}%")


async def main() -> None:
    """Run all examples."""
    print("Web Fetch Enhanced Features Demo")
    print("=" * 40)
    print()
    
    try:
        await example_circuit_breaker()
        await example_request_deduplication()
        await example_response_transformation()
        await example_regex_extraction()
        await example_metrics_collection()
        await example_comprehensive_usage()
        
        print("All examples completed successfully!")
        
    except Exception as e:
        print(f"Example failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
