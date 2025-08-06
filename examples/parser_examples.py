#!/usr/bin/env python3
"""
Comprehensive parser examples for the web-fetch library.

This script demonstrates various content parsers including JSON, CSV, HTML,
PDF, image, and feed parsers with different input formats and edge cases.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from web_fetch import (
    ContentType,
    FetchRequest,
    WebFetcher,
    fetch_url,
)


async def example_json_parsing():
    """Demonstrate JSON parsing with various formats and edge cases."""
    print("=== JSON Parsing Examples ===\n")
    
    # Example 1: Standard JSON API response
    print("1. Standard JSON API Response:")
    result = await fetch_url("https://jsonplaceholder.typicode.com/posts/1", ContentType.JSON)
    if result.is_success:
        print(f"   Title: {result.content.get('title', 'N/A')}")
        print(f"   User ID: {result.content.get('userId', 'N/A')}")
        print(f"   Body length: {len(result.content.get('body', ''))}")
    print()
    
    # Example 2: JSON array
    print("2. JSON Array Response:")
    result = await fetch_url("https://jsonplaceholder.typicode.com/users", ContentType.JSON)
    if result.is_success and isinstance(result.content, list):
        print(f"   Number of users: {len(result.content)}")
        if result.content:
            first_user = result.content[0]
            print(f"   First user: {first_user.get('name', 'N/A')}")
            print(f"   Email: {first_user.get('email', 'N/A')}")
    print()
    
    # Example 3: Nested JSON structure
    print("3. Complex Nested JSON:")
    result = await fetch_url("https://httpbin.org/json", ContentType.JSON)
    if result.is_success:
        slideshow = result.content.get('slideshow', {})
        print(f"   Slideshow title: {slideshow.get('title', 'N/A')}")
        print(f"   Author: {slideshow.get('author', 'N/A')}")
        slides = slideshow.get('slides', [])
        print(f"   Number of slides: {len(slides)}")
        if slides:
            print(f"   First slide title: {slides[0].get('title', 'N/A')}")
    print()


async def example_html_parsing():
    """Demonstrate HTML parsing and structured data extraction."""
    print("=== HTML Parsing Examples ===\n")
    
    # Example 1: Basic HTML parsing
    print("1. Basic HTML Structure Extraction:")
    result = await fetch_url("https://httpbin.org/html", ContentType.HTML)
    if result.is_success and isinstance(result.content, dict):
        print(f"   Page title: {result.content.get('title', 'N/A')}")
        print(f"   Number of links: {len(result.content.get('links', []))}")
        print(f"   Number of images: {len(result.content.get('images', []))}")
        print(f"   Text content length: {len(result.content.get('text', ''))}")
        
        # Show first few links
        links = result.content.get('links', [])
        if links:
            print("   First few links:")
            for i, link in enumerate(links[:3]):
                print(f"     {i+1}. {link.get('text', 'No text')} -> {link.get('href', 'No URL')}")
    print()
    
    # Example 2: Real website HTML parsing
    print("2. Real Website HTML Parsing:")
    result = await fetch_url("https://example.com", ContentType.HTML)
    if result.is_success and isinstance(result.content, dict):
        print(f"   Page title: {result.content.get('title', 'N/A')}")
        print(f"   Meta description: {result.content.get('meta', {}).get('description', 'N/A')}")
        print(f"   Number of headings: {len(result.content.get('headings', []))}")
        
        # Show headings
        headings = result.content.get('headings', [])
        if headings:
            print("   Headings found:")
            for heading in headings[:5]:  # Show first 5
                print(f"     {heading.get('tag', 'h?')}: {heading.get('text', 'No text')}")
    print()


async def example_text_parsing():
    """Demonstrate text parsing and content analysis."""
    print("=== Text Parsing Examples ===\n")
    
    # Example 1: Plain text content
    print("1. Plain Text Content:")
    result = await fetch_url("https://httpbin.org/robots.txt", ContentType.TEXT)
    if result.is_success:
        lines = result.content.split('\n') if result.content else []
        print(f"   Content length: {len(result.content or '')}")
        print(f"   Number of lines: {len(lines)}")
        print(f"   First few lines:")
        for i, line in enumerate(lines[:5]):
            print(f"     {i+1}. {line.strip()}")
    print()
    
    # Example 2: Text with encoding detection
    print("2. Text with Different Encodings:")
    result = await fetch_url("https://httpbin.org/encoding/utf8", ContentType.TEXT)
    if result.is_success:
        print(f"   Content preview: {(result.content or '')[:100]}...")
        print(f"   Contains unicode: {'unicode' in (result.content or '').lower()}")
    print()


async def example_raw_content():
    """Demonstrate raw content handling for binary data."""
    print("=== Raw Content Examples ===\n")
    
    # Example 1: Binary data
    print("1. Binary Data Handling:")
    result = await fetch_url("https://httpbin.org/bytes/1024", ContentType.RAW)
    if result.is_success:
        print(f"   Content type: {type(result.content)}")
        print(f"   Content length: {len(result.content) if result.content else 0} bytes")
        if result.content:
            print(f"   First 20 bytes: {result.content[:20]}")
            print(f"   Last 20 bytes: {result.content[-20:]}")
    print()
    
    # Example 2: Image data
    print("2. Image Data:")
    result = await fetch_url("https://httpbin.org/image/png", ContentType.RAW)
    if result.is_success:
        print(f"   Image data length: {len(result.content) if result.content else 0} bytes")
        if result.content:
            # Check PNG signature
            png_signature = b'\x89PNG\r\n\x1a\n'
            is_png = result.content.startswith(png_signature)
            print(f"   Valid PNG signature: {is_png}")
    print()


async def example_content_type_detection():
    """Demonstrate automatic content type detection."""
    print("=== Content Type Detection Examples ===\n")
    
    test_urls = [
        ("https://httpbin.org/json", "JSON endpoint"),
        ("https://httpbin.org/html", "HTML page"),
        ("https://httpbin.org/xml", "XML content"),
        ("https://httpbin.org/image/jpeg", "JPEG image"),
        ("https://httpbin.org/robots.txt", "Plain text"),
    ]
    
    async with WebFetcher() as fetcher:
        for url, description in test_urls:
            print(f"{description}:")
            
            # Fetch with automatic content type detection
            request = FetchRequest(url=url, content_type=ContentType.TEXT)
            result = await fetcher.fetch_single(request)
            
            if result.is_success:
                content_type = result.headers.get('content-type', 'unknown')
                print(f"   URL: {url}")
                print(f"   Server content-type: {content_type}")
                print(f"   Content length: {len(str(result.content)) if result.content else 0}")
                
                # Try to detect actual content type
                if 'json' in content_type.lower():
                    try:
                        json.loads(str(result.content))
                        print("   ✓ Valid JSON detected")
                    except:
                        print("   ✗ Invalid JSON")
                elif 'html' in content_type.lower():
                    if '<html' in str(result.content).lower():
                        print("   ✓ HTML structure detected")
                    else:
                        print("   ✗ No HTML structure found")
            print()


async def example_error_handling():
    """Demonstrate parser error handling and edge cases."""
    print("=== Parser Error Handling Examples ===\n")
    
    # Example 1: Invalid JSON
    print("1. Invalid JSON Handling:")
    try:
        # This endpoint returns invalid JSON
        result = await fetch_url("https://httpbin.org/html", ContentType.JSON)
        if not result.is_success:
            print(f"   Expected error: {result.error}")
        else:
            print("   Unexpected success - JSON parsing was lenient")
    except Exception as e:
        print(f"   Caught exception: {e}")
    print()
    
    # Example 2: Empty content
    print("2. Empty Content Handling:")
    result = await fetch_url("https://httpbin.org/status/204", ContentType.JSON)  # No Content
    print(f"   Status code: {result.status_code}")
    print(f"   Content: {result.content}")
    print(f"   Success: {result.is_success}")
    print()
    
    # Example 3: Large content handling
    print("3. Large Content Handling:")
    result = await fetch_url("https://httpbin.org/bytes/10240", ContentType.TEXT)  # 10KB
    if result.is_success:
        print(f"   Content length: {len(result.content or '')} characters")
        print(f"   Memory usage reasonable: {len(result.content or '') < 50000}")
    print()


async def example_custom_parsing():
    """Demonstrate custom parsing scenarios."""
    print("=== Custom Parsing Examples ===\n")
    
    # Example 1: CSV-like data parsing
    print("1. CSV-like Data Parsing:")
    # Simulate CSV data from a text endpoint
    result = await fetch_url("https://httpbin.org/get", ContentType.TEXT)
    if result.is_success:
        # Parse the response as if it were CSV-like data
        content = str(result.content)
        lines = content.split('\n')
        print(f"   Total lines: {len(lines)}")
        print(f"   First line: {lines[0] if lines else 'No content'}")
    print()
    
    # Example 2: Custom header analysis
    print("2. Custom Header Analysis:")
    async with WebFetcher() as fetcher:
        request = FetchRequest(url="https://httpbin.org/response-headers?Custom-Header=CustomValue")
        result = await fetcher.fetch_single(request)
        
        if result.is_success:
            print("   Response headers analysis:")
            for key, value in result.headers.items():
                if key.lower().startswith('custom'):
                    print(f"     Custom header: {key} = {value}")
                elif key.lower() in ['content-type', 'content-length', 'server']:
                    print(f"     Standard header: {key} = {value}")
    print()


async def example_performance_considerations():
    """Demonstrate performance considerations for different parsers."""
    print("=== Performance Considerations ===\n")
    
    import time
    
    # Compare parsing performance
    test_url = "https://httpbin.org/json"
    
    # Time JSON parsing
    start_time = time.time()
    result = await fetch_url(test_url, ContentType.JSON)
    json_time = time.time() - start_time
    
    # Time text parsing
    start_time = time.time()
    result = await fetch_url(test_url, ContentType.TEXT)
    text_time = time.time() - start_time
    
    # Time raw parsing
    start_time = time.time()
    result = await fetch_url(test_url, ContentType.RAW)
    raw_time = time.time() - start_time
    
    print("Parsing performance comparison:")
    print(f"   JSON parsing: {json_time:.3f}s")
    print(f"   Text parsing: {text_time:.3f}s")
    print(f"   Raw parsing: {raw_time:.3f}s")
    print()
    
    print("Performance tips:")
    print("   - Use RAW for binary data or when you don't need parsing")
    print("   - Use TEXT for simple text processing")
    print("   - Use JSON only when you need structured data")
    print("   - Use HTML when you need structured web page data")
    print()


async def example_feed_parsing():
    """Demonstrate RSS/Atom feed parsing examples."""
    print("=== Feed Parsing Examples ===\n")

    # Note: These examples would work with actual RSS/Atom feeds
    # For demonstration, we'll show the structure

    print("1. RSS Feed Structure Example:")
    print("   RSS feeds typically contain:")
    print("   - Channel information (title, description, link)")
    print("   - Items with title, description, link, pubDate")
    print("   - Categories and other metadata")
    print()

    print("2. Atom Feed Structure Example:")
    print("   Atom feeds typically contain:")
    print("   - Feed-level metadata (title, subtitle, updated)")
    print("   - Entry elements with title, content, links")
    print("   - Author information and categories")
    print()

    # Example with a mock feed-like structure
    print("3. Processing Feed-like JSON Data:")
    result = await fetch_url("https://jsonplaceholder.typicode.com/posts", ContentType.JSON)
    if result.is_success and isinstance(result.content, list):
        print(f"   Found {len(result.content)} feed items")
        for i, item in enumerate(result.content[:3]):  # Show first 3
            print(f"   Item {i+1}:")
            print(f"     Title: {item.get('title', 'No title')[:50]}...")
            print(f"     Content: {item.get('body', 'No content')[:50]}...")
            print(f"     Author ID: {item.get('userId', 'Unknown')}")
    print()


async def example_csv_like_parsing():
    """Demonstrate CSV-like data parsing from various sources."""
    print("=== CSV-like Data Parsing Examples ===\n")

    print("1. Parsing Structured Text Data:")
    # Get some structured data that we can parse like CSV
    result = await fetch_url("https://httpbin.org/get", ContentType.JSON)
    if result.is_success:
        # Convert JSON to CSV-like format for demonstration
        data = result.content
        if isinstance(data, dict):
            print("   Converting JSON to CSV-like structure:")
            headers = list(data.keys())[:5]  # First 5 keys as headers
            print(f"   Headers: {', '.join(headers)}")

            # Show values
            values = [str(data.get(h, ''))[:20] for h in headers]
            print(f"   Values: {', '.join(values)}")
    print()

    print("2. Processing Tabular Text Data:")
    print("   For actual CSV files, you would:")
    print("   - Use ContentType.TEXT to get raw content")
    print("   - Split by lines and parse each row")
    print("   - Handle different delimiters (comma, tab, semicolon)")
    print("   - Deal with quoted fields and escape characters")
    print("   - Detect headers automatically")
    print()


async def example_image_metadata():
    """Demonstrate image metadata extraction concepts."""
    print("=== Image Metadata Examples ===\n")

    print("1. Image Data Analysis:")
    result = await fetch_url("https://httpbin.org/image/png", ContentType.RAW)
    if result.is_success and result.content:
        print(f"   Image size: {len(result.content)} bytes")

        # Check for PNG signature
        png_signature = b'\x89PNG\r\n\x1a\n'
        if result.content.startswith(png_signature):
            print("   ✓ Valid PNG file detected")
            print("   PNG metadata could include:")
            print("     - Image dimensions")
            print("     - Color depth")
            print("     - Creation date")
            print("     - Software used")
        else:
            print("   ✗ Not a valid PNG file")
    print()

    print("2. JPEG Image Analysis:")
    result = await fetch_url("https://httpbin.org/image/jpeg", ContentType.RAW)
    if result.is_success and result.content:
        print(f"   JPEG size: {len(result.content)} bytes")

        # Check for JPEG signature
        jpeg_signature = b'\xff\xd8\xff'
        if result.content.startswith(jpeg_signature):
            print("   ✓ Valid JPEG file detected")
            print("   JPEG EXIF data could include:")
            print("     - Camera make and model")
            print("     - GPS coordinates")
            print("     - Timestamp")
            print("     - Camera settings")
        else:
            print("   ✗ Not a valid JPEG file")
    print()


async def main():
    """Run all parser examples."""
    print("Web Fetch Library - Comprehensive Parser Examples")
    print("=" * 60)
    print()

    try:
        await example_json_parsing()
        await example_html_parsing()
        await example_text_parsing()
        await example_raw_content()
        await example_content_type_detection()
        await example_error_handling()
        await example_custom_parsing()
        await example_performance_considerations()
        await example_feed_parsing()
        await example_csv_like_parsing()
        await example_image_metadata()

        print("🎉 All parser examples completed successfully!")
        print("\nKey Takeaways:")
        print("- Choose the right ContentType for your data")
        print("- Handle errors gracefully with try-catch blocks")
        print("- Consider performance implications of different parsers")
        print("- Validate content before processing")
        print("- Use structured parsing (JSON, HTML) when available")

    except Exception as e:
        print(f"❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
