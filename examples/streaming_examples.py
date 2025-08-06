#!/usr/bin/env python3
"""
Streaming examples for the web_fetch library.

This script demonstrates the streaming capabilities including file downloads,
progress tracking, and memory-efficient processing of large files.
"""

import asyncio
import sys
from pathlib import Path

from web_fetch import (
    ContentType,
    ProgressInfo,
    StreamingConfig,
    StreamingWebFetcher,
    StreamRequest,
    download_file,
    fetch_with_cache,
)


def progress_callback(progress: ProgressInfo) -> None:
    """Progress callback for download tracking."""
    if progress.total_bytes:
        percentage = progress.percentage or 0
        bar_length = 40
        filled_length = int(bar_length * percentage / 100)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        
        print(f'\r[{bar}] {percentage:.1f}% | '
              f'{progress.bytes_downloaded:,} / {progress.total_bytes:,} bytes | '
              f'{progress.speed_human} | '
              f'ETA: {progress.eta:.1f}s' if progress.eta else 'ETA: --',
              end='', flush=True)
    else:
        print(f'\rDownloaded: {progress.bytes_downloaded:,} bytes | '
              f'{progress.speed_human}',
              end='', flush=True)


async def example_file_download() -> None:
    """Example: Download a file with progress tracking."""
    print("=== File Download with Progress Tracking ===\n")
    
    # Download a sample file (using a small test file)
    url = "https://httpbin.org/bytes/1048576"  # 1MB test file
    output_path = Path("downloads/test_file.bin")
    
    print(f"Downloading {url}")
    print(f"Saving to: {output_path}")
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
            print(f"   Status: {result.status_code}")
            print(f"   Downloaded: {result.bytes_downloaded:,} bytes")
            print(f"   Time: {result.response_time:.2f}s")
            print(f"   Average speed: {result.progress_info.speed_human}")
            print(f"   File saved to: {result.output_path}")
        else:
            print(f"❌ Download failed: {result.error}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print()


async def example_streaming_without_file() -> None:
    """Example: Stream content without saving to file."""
    print("=== Streaming Content Processing ===\n")
    
    url = "https://httpbin.org/stream/10"  # Stream 10 JSON objects
    
    streaming_config = StreamingConfig(
        chunk_size=1024,
        enable_progress=True,
        progress_interval=0.5
    )
    
    request = StreamRequest(
        url=url,
        streaming_config=streaming_config
    )
    
    print(f"Streaming from: {url}")
    print("Processing chunks in memory...")
    print()
    
    async with StreamingWebFetcher() as fetcher:
        result = await fetcher.stream_fetch(request, progress_callback)
        
        if result.is_success:
            print()  # New line after progress
            print(f"✅ Streaming completed!")
            print(f"   Status: {result.status_code}")
            print(f"   Chunks processed: {result.progress_info.chunk_count}")
            print(f"   Total bytes: {result.bytes_downloaded:,}")
            print(f"   Time: {result.response_time:.2f}s")
        else:
            print(f"❌ Streaming failed: {result.error}")
    
    print()


async def example_large_file_streaming() -> None:
    """Example: Stream a larger file with custom configuration."""
    print("=== Large File Streaming ===\n")
    
    # Use a larger test file
    url = "https://httpbin.org/bytes/5242880"  # 5MB test file
    output_path = Path("downloads/large_file.bin")
    
    # Custom streaming configuration
    streaming_config = StreamingConfig(
        chunk_size=32768,  # 32KB chunks
        buffer_size=131072,  # 128KB buffer
        enable_progress=True,
        progress_interval=0.2,  # Update every 200ms
        max_file_size=10 * 1024 * 1024  # 10MB limit
    )
    
    request = StreamRequest(
        url=url,
        output_path=output_path,
        streaming_config=streaming_config
    )
    
    print(f"Streaming large file from: {url}")
    print(f"Chunk size: {streaming_config.chunk_size:,} bytes")
    print(f"Max file size: {streaming_config.max_file_size:,} bytes")
    print()
    
    async with StreamingWebFetcher() as fetcher:
        result = await fetcher.stream_fetch(request, progress_callback)
        
        print()  # New line after progress
        
        if result.is_success:
            print(f"✅ Large file download completed!")
            print(f"   File size: {result.bytes_downloaded:,} bytes")
            print(f"   Chunks: {result.progress_info.chunk_count}")
            print(f"   Average speed: {result.progress_info.speed_human}")
            print(f"   Efficiency: {result.bytes_downloaded / result.response_time:.0f} bytes/sec")
        else:
            print(f"❌ Download failed: {result.error}")
    
    print()


async def example_caching() -> None:
    """Example: Demonstrate caching functionality."""
    print("=== Caching Example ===\n")
    
    url = "https://httpbin.org/json"
    
    print(f"First request (from network): {url}")
    start_time = asyncio.get_event_loop().time()
    
    result1 = await fetch_with_cache(url, ContentType.JSON)
    
    first_time = asyncio.get_event_loop().time() - start_time
    
    if result1.is_success:
        print(f"✅ First request completed in {first_time:.3f}s")
        print(f"   Status: {result1.status_code}")
        print(f"   Content type: {result1.content_type}")
    
    print(f"\nSecond request (from cache): {url}")
    start_time = asyncio.get_event_loop().time()
    
    result2 = await fetch_with_cache(url, ContentType.JSON)
    
    second_time = asyncio.get_event_loop().time() - start_time
    
    if result2.is_success:
        print(f"✅ Second request completed in {second_time:.3f}s")
        print(f"   Speedup: {first_time / second_time:.1f}x faster")
        print(f"   Same content: {result1.content == result2.content}")
    
    print()


async def example_url_utilities() -> None:
    """Example: Demonstrate URL utility functions."""
    print("=== URL Utilities Example ===\n")
    
    from web_fetch import analyze_url, is_valid_url, normalize_url
    
    test_urls = [
        "https://example.com/path/../other?b=2&a=1",
        "http://EXAMPLE.COM/PATH/",
        "https://invalid-domain-12345.com",
        "not-a-url",
        "ftp://files.example.com/file.txt"
    ]
    
    for url in test_urls:
        print(f"URL: {url}")
        print(f"  Valid: {is_valid_url(url)}")
        
        if is_valid_url(url):
            normalized = normalize_url(url)
            print(f"  Normalized: {normalized}")
            
            analysis = analyze_url(url)
            print(f"  Domain: {analysis.domain}")
            print(f"  Secure: {analysis.is_secure}")
            print(f"  Issues: {analysis.issues}")
        
        print()


async def example_response_analysis() -> None:
    """Example: Demonstrate response analysis."""
    print("=== Response Analysis Example ===\n")
    
    from web_fetch import analyze_headers, detect_content_type, fetch_url
    
    url = "https://httpbin.org/response-headers?Content-Type=application/json&Server=httpbin/1.0"
    
    result = await fetch_url(url, ContentType.TEXT)
    
    if result.is_success:
        print(f"Analyzing response from: {url}")
        print()
        
        # Analyze headers
        header_analysis = analyze_headers(result.headers)
        print(f"Content Type: {header_analysis.content_type}")
        print(f"Content Length: {header_analysis.content_length}")
        print(f"Server: {header_analysis.server}")
        print(f"Cacheable: {header_analysis.is_cacheable}")
        print(f"Security Headers: {header_analysis.has_security_headers}")
        print(f"Custom Headers: {list(header_analysis.custom_headers.keys())}")
        
        print()
        
        # Detect content type
        if isinstance(result.content, str):
            content_bytes = result.content.encode('utf-8')
        else:
            content_bytes = result.content or b''
        
        detected_type = detect_content_type(result.headers, content_bytes)
        print(f"Detected Content Type: {detected_type}")
    
    print()


async def main() -> None:
    """Run all streaming examples."""
    print("Web Fetch Library - Streaming and Utilities Examples")
    print("=" * 60)
    print()
    
    # Create downloads directory
    Path("downloads").mkdir(exist_ok=True)
    
    try:
        await example_file_download()
        await example_streaming_without_file()
        await example_large_file_streaming()
        await example_caching()
        await example_url_utilities()
        await example_response_analysis()
        
        print("🎉 All streaming examples completed successfully!")
        
    except KeyboardInterrupt:
        print("\n👋 Examples interrupted by user")
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
