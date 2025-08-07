#!/usr/bin/env python3
"""
Main demonstration script for the web_fetch library.

This script showcases the key features of the modern async web fetching utility.
"""

import asyncio
import json
from pathlib import Path
from web_fetch import (
    ContentType,
    FetchConfig,
    FetchRequest,
    ProgressInfo,
    StreamingWebFetcher,
    WebFetcher,
    analyze_url,
    download_file,
    fetch_url,
    fetch_urls,
    fetch_with_cache,
    is_valid_url,
    normalize_url,
)


async def demonstrate_features():
    """Demonstrate key features of the web_fetch library."""
    print("🚀 Web Fetch Library - Enhanced Demo with Streaming & Utilities")
    print("=" * 70)
    print()

    # Create downloads directory
    Path("downloads").mkdir(exist_ok=True)

    # 1. Simple single URL fetch
    print("1️⃣  Simple URL Fetch (JSON)")
    print("-" * 30)
    result = await fetch_url("https://httpbin.org/json", ContentType.JSON)
    if result.is_success:
        print(f"✅ Success! Status: {result.status_code}")
        print(f"📊 Response time: {result.response_time:.2f}s")
        if isinstance(result.content, dict):
            slideshow = result.content.get('slideshow', {})
            print(f"📄 Slideshow title: {slideshow.get('title', 'N/A')}")
    else:
        print(f"❌ Failed: {result.error}")
    print()

    # 2. Batch fetching with concurrency
    print("2️⃣  Batch Fetching (Multiple URLs)")
    print("-" * 35)
    urls = [
        "https://httpbin.org/get",
        "https://httpbin.org/user-agent",
        "https://httpbin.org/headers",
        "https://httpbin.org/ip",
    ]

    batch_result = await fetch_urls(urls, ContentType.JSON)
    print(f"📈 Total requests: {batch_result.total_requests}")
    print(f"✅ Successful: {batch_result.successful_requests}")
    print(f"❌ Failed: {batch_result.failed_requests}")
    print(f"📊 Success rate: {batch_result.success_rate:.1f}%")
    print(f"⏱️  Total time: {batch_result.total_time:.2f}s")
    print()

    # 3. Streaming download
    await example_streaming_download()

    # 4. URL utilities
    await example_url_utilities()

    # 5. Caching
    await example_caching()

    # 6. Custom configuration and error handling
    print("6️⃣  Custom Configuration & Error Handling")
    print("-" * 42)

    config = FetchConfig(
        total_timeout=10.0,
        max_concurrent_requests=3,
        max_retries=2,
        retry_delay=0.5
    )

    # Test with a URL that will timeout
    request = FetchRequest(
        url="https://httpbin.org/delay/15",  # Will timeout
        content_type=ContentType.JSON
    )

    async with WebFetcher(config) as fetcher:
        result = await fetcher.fetch_single(request)

    print(f"🔄 Retry attempts: {result.retry_count}")
    print(f"⏱️  Response time: {result.response_time:.2f}s")
    if result.error:
        print(f"⚠️  Error handled: {result.error[:50]}...")
    print()


async def example_streaming_download():
    """Example: Demonstrate streaming download with progress."""
    print("6️⃣  Streaming Download with Progress")
    print("-" * 35)

    def progress_callback(progress: ProgressInfo):
        if progress.total_bytes:
            percentage = progress.percentage or 0
            bar_length = 30
            filled_length = int(bar_length * percentage / 100)
            bar = '█' * filled_length + '-' * (bar_length - filled_length)
            print(f'\r[{bar}] {percentage:.1f}% | {progress.speed_human}', end='', flush=True)

    # Create downloads directory
    Path("downloads").mkdir(exist_ok=True)

    # Download a test file with progress tracking
    url = "https://httpbin.org/bytes/524288"  # 512KB test file
    output_path = Path("downloads/test_download.bin")

    print(f"Downloading: {url}")
    print(f"Output: {output_path}")
    print()

    try:
        result = await download_file(
            url=url,
            output_path=output_path,
            chunk_size=8192,
            progress_callback=progress_callback
        )

        print()  # New line after progress bar

        if result.is_success:
            print(f"✅ Download completed!")
            print(f"   File size: {result.bytes_downloaded:,} bytes")
            print(f"   Time: {result.response_time:.2f}s")
            print(f"   Speed: {result.progress_info.speed_human}")
        else:
            print(f"❌ Download failed: {result.error}")

    except Exception as e:
        print(f"❌ Error: {e}")

    print()


async def example_url_utilities():
    """Example: Demonstrate URL utility functions."""
    print("7️⃣  URL Utilities and Validation")
    print("-" * 32)

    test_urls = [
        "HTTPS://EXAMPLE.COM/path/../other?b=2&a=1",
        "http://localhost:8080/api",
        "not-a-url",
        "https://test.com/"
    ]

    for url in test_urls:
        print(f"URL: {url}")

        # Validate URL
        valid = is_valid_url(url)
        print(f"  Valid: {valid}")

        if valid:
            # Normalize URL
            normalized = normalize_url(url)
            print(f"  Normalized: {normalized}")

            # Analyze URL
            analysis = analyze_url(url)
            print(f"  Domain: {analysis.domain}")
            print(f"  Secure: {analysis.is_secure}")
            if analysis.issues:
                print(f"  Issues: {', '.join(analysis.issues)}")

        print()


async def example_caching():
    """Example: Demonstrate caching functionality."""
    print("8️⃣  Response Caching")
    print("-" * 18)

    url = "https://httpbin.org/uuid"  # Returns a unique UUID each time

    print(f"First request (from network): {url}")
    start_time = asyncio.get_event_loop().time()

    result1 = await fetch_with_cache(url, ContentType.JSON)

    first_time = asyncio.get_event_loop().time() - start_time

    if result1.is_success:
        print(f"✅ First request completed in {first_time:.3f}s")
        if isinstance(result1.content, dict):
            uuid1 = result1.content.get('uuid', 'N/A')
            print(f"   UUID: {uuid1}")

    print(f"\nSecond request (from cache): {url}")
    start_time = asyncio.get_event_loop().time()

    result2 = await fetch_with_cache(url, ContentType.JSON)

    second_time = asyncio.get_event_loop().time() - start_time

    if result2.is_success:
        print(f"✅ Second request completed in {second_time:.3f}s")
        if isinstance(result2.content, dict):
            uuid2 = result2.content.get('uuid', 'N/A')
            print(f"   UUID: {uuid2}")

        if first_time > 0 and second_time > 0:
            speedup = first_time / second_time
            print(f"   Speedup: {speedup:.1f}x faster")
            print(f"   Same content: {result1.content == result2.content}")

    print()

    print("🎉 Demo completed! All features demonstrated:")
    print("   ✅ Async/await syntax")
    print("   ✅ Type hints with Union and Optional")
    print("   ✅ Context managers for resource cleanup")
    print("   ✅ Dataclasses and Pydantic models")
    print("   ✅ Pattern matching for content parsing")
    print("   ✅ Comprehensive error handling")
    print("   ✅ AIOHTTP best practices")
    print("   ✅ Streaming downloads with progress tracking")
    print("   ✅ URL validation and normalization")
    print("   ✅ Response caching with TTL")
    print("   ✅ Memory-efficient file handling")


def main():
    """Main entry point."""
    try:
        asyncio.run(demonstrate_features())
    except KeyboardInterrupt:
        print("\n👋 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")


if __name__ == "__main__":
    main()
