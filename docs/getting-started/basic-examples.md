# Basic Examples

This page provides practical examples for common WebFetch use cases. Each example is self-contained and ready to run.

## Simple HTTP Requests

### GET Request

```python
import asyncio
from web_fetch import fetch_url, ContentType

async def simple_get():
    """Fetch JSON data from an API"""
    result = await fetch_url("https://httpbin.org/json", ContentType.JSON)
    
    if result.is_success:
        print(f"✅ Status: {result.status_code}")
        print(f"📄 Content: {result.content}")
        print(f"⏱️  Response time: {result.response_time:.2f}s")
    else:
        print(f"❌ Error: {result.error}")

asyncio.run(simple_get())
```

### POST Request with JSON Data

```python
import asyncio
from web_fetch import WebFetcher, FetchRequest, ContentType

async def post_json():
    """Send JSON data to an API"""
    data = {
        "name": "John Doe",
        "email": "john@example.com",
        "age": 30
    }
    
    request = FetchRequest(
        url="https://httpbin.org/post",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=data,
        content_type=ContentType.JSON
    )
    
    async with WebFetcher() as fetcher:
        result = await fetcher.fetch_single(request)
        
        if result.is_success:
            print("✅ POST successful!")
            # Echo service returns our data
            echo_data = result.content.get("json", {})
            print(f"📤 Sent: {echo_data}")

asyncio.run(post_json())
```

### Form Data Submission

```python
import asyncio
from web_fetch import WebFetcher, FetchRequest, ContentType

async def post_form():
    """Submit form data"""
    form_data = {
        "username": "testuser",
        "password": "secret123",
        "remember": "on"
    }
    
    request = FetchRequest(
        url="https://httpbin.org/post",
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=form_data,
        content_type=ContentType.JSON
    )
    
    async with WebFetcher() as fetcher:
        result = await fetcher.fetch_single(request)
        
        if result.is_success:
            print("✅ Form submitted!")
            form_echo = result.content.get("form", {})
            print(f"📝 Form data: {form_echo}")

asyncio.run(post_form())
```

## Working with Different Content Types

### HTML Parsing

```python
import asyncio
from web_fetch import fetch_url, ContentType

async def parse_html():
    """Parse HTML and extract structured data"""
    result = await fetch_url("https://example.com", ContentType.HTML)
    
    if result.is_success:
        html_data = result.content
        print(f"📄 Title: {html_data['title']}")
        print(f"🔗 Links found: {len(html_data['links'])}")
        print(f"🖼️  Images found: {len(html_data['images'])}")
        
        # Show first few links
        for i, link in enumerate(html_data['links'][:3]):
            print(f"  {i+1}. {link['text']} -> {link['href']}")

asyncio.run(parse_html())
```

### Text Content

```python
import asyncio
from web_fetch import fetch_url, ContentType

async def fetch_text():
    """Fetch plain text content"""
    result = await fetch_url("https://httpbin.org/robots.txt", ContentType.TEXT)
    
    if result.is_success:
        lines = result.content.split('\n')
        print(f"📄 Text content ({len(lines)} lines):")
        for line in lines[:10]:  # Show first 10 lines
            print(f"  {line}")

asyncio.run(fetch_text())
```

### Binary Data

```python
import asyncio
from web_fetch import fetch_url, ContentType

async def fetch_binary():
    """Fetch binary data"""
    result = await fetch_url("https://httpbin.org/bytes/1024", ContentType.RAW)
    
    if result.is_success:
        data = result.content
        print(f"📦 Downloaded {len(data)} bytes")
        print(f"🔢 First 20 bytes: {data[:20]}")

asyncio.run(fetch_binary())
```

## Batch Operations

### Multiple URLs

```python
import asyncio
from web_fetch import fetch_urls, ContentType

async def batch_fetch():
    """Fetch multiple URLs concurrently"""
    urls = [
        "https://httpbin.org/get",
        "https://httpbin.org/json",
        "https://httpbin.org/html",
        "https://httpbin.org/xml"
    ]
    
    result = await fetch_urls(urls, ContentType.TEXT)
    
    print(f"📊 Batch Results:")
    print(f"  Success rate: {result.success_rate:.1f}%")
    print(f"  Total time: {result.total_time:.2f}s")
    print(f"  Successful: {len(result.successful_results)}")
    print(f"  Failed: {len(result.failed_results)}")
    
    # Show details for successful requests
    for i, success in enumerate(result.successful_results[:2]):
        print(f"\n✅ Request {i+1}:")
        print(f"  URL: {success.url}")
        print(f"  Status: {success.status_code}")
        print(f"  Size: {len(str(success.content))} chars")

asyncio.run(batch_fetch())
```

### Mixed Request Types

```python
import asyncio
from web_fetch import WebFetcher, FetchRequest, ContentType, BatchRequest

async def mixed_batch():
    """Batch requests with different methods and data"""
    requests = [
        FetchRequest(
            url="https://httpbin.org/get",
            method="GET",
            content_type=ContentType.JSON
        ),
        FetchRequest(
            url="https://httpbin.org/post",
            method="POST",
            data={"key": "value"},
            content_type=ContentType.JSON
        ),
        FetchRequest(
            url="https://httpbin.org/put",
            method="PUT",
            data={"update": "data"},
            content_type=ContentType.JSON
        )
    ]
    
    batch_request = BatchRequest(
        requests=requests,
        max_concurrent=2  # Limit concurrency
    )
    
    async with WebFetcher() as fetcher:
        result = await fetcher.fetch_batch(batch_request)
        
        print(f"📊 Mixed Batch Results:")
        print(f"  Success rate: {result.success_rate:.1f}%")
        
        for i, success in enumerate(result.successful_results):
            method = requests[i].method
            print(f"  ✅ {method} request successful")

asyncio.run(mixed_batch())
```

## File Operations

### Download Files

```python
import asyncio
from pathlib import Path
from web_fetch import download_file, ProgressInfo

def show_progress(progress: ProgressInfo):
    """Progress callback function"""
    if progress.total_bytes:
        percentage = progress.percentage or 0
        speed = progress.speed_human
        print(f"\r📥 Progress: {percentage:.1f}% ({speed})", end="", flush=True)

async def download_example():
    """Download a file with progress tracking"""
    # Create downloads directory
    downloads_dir = Path("downloads")
    downloads_dir.mkdir(exist_ok=True)
    
    result = await download_file(
        url="https://httpbin.org/bytes/1048576",  # 1MB test file
        output_path=downloads_dir / "test_file.bin",
        chunk_size=8192,
        progress_callback=show_progress
    )
    
    print()  # New line after progress
    
    if result.is_success:
        print(f"✅ Download complete!")
        print(f"📁 File: {result.output_path}")
        print(f"📦 Size: {result.bytes_downloaded:,} bytes")
        print(f"⏱️  Time: {result.response_time:.2f}s")
        
        # Verify file exists
        if result.output_path.exists():
            actual_size = result.output_path.stat().st_size
            print(f"✅ File verified: {actual_size:,} bytes on disk")

asyncio.run(download_example())
```

### Upload Files

```python
import asyncio
from pathlib import Path
from web_fetch import WebFetcher, FetchRequest, ContentType

async def upload_file():
    """Upload a file using multipart form data"""
    # Create a test file
    test_file = Path("test_upload.txt")
    test_file.write_text("Hello, WebFetch!")
    
    try:
        # Prepare file upload
        with open(test_file, 'rb') as f:
            files = {'file': ('test_upload.txt', f, 'text/plain')}
            
            request = FetchRequest(
                url="https://httpbin.org/post",
                method="POST",
                files=files,
                content_type=ContentType.JSON
            )
            
            async with WebFetcher() as fetcher:
                result = await fetcher.fetch_single(request)
                
                if result.is_success:
                    print("✅ File uploaded successfully!")
                    files_info = result.content.get("files", {})
                    print(f"📁 Uploaded files: {list(files_info.keys())}")
    
    finally:
        # Clean up test file
        if test_file.exists():
            test_file.unlink()

asyncio.run(upload_file())
```

## Error Handling

### Handling Different Error Types

```python
import asyncio
from web_fetch import fetch_url, ContentType, WebFetchError, HTTPError, TimeoutError

async def error_handling_example():
    """Demonstrate different error handling scenarios"""
    
    test_cases = [
        ("https://httpbin.org/status/404", "404 Not Found"),
        ("https://httpbin.org/status/500", "500 Server Error"),
        ("https://httpbin.org/delay/10", "Timeout (with 5s timeout)"),
        ("https://invalid-domain-that-does-not-exist.com", "DNS Error")
    ]
    
    for url, description in test_cases:
        print(f"\n🧪 Testing: {description}")
        
        try:
            # Use shorter timeout for timeout test
            timeout = 5.0 if "delay" in url else 30.0
            
            result = await fetch_url(url, ContentType.JSON, timeout=timeout)
            
            if result.is_success:
                print(f"✅ Unexpected success: {result.status_code}")
            else:
                print(f"❌ Expected failure: {result.error}")
                print(f"   Status code: {result.status_code}")
                
        except TimeoutError as e:
            print(f"⏰ Timeout error: {e}")
        except HTTPError as e:
            print(f"🌐 HTTP error: {e}")
        except WebFetchError as e:
            print(f"🔧 WebFetch error: {e}")
        except Exception as e:
            print(f"💥 Unexpected error: {e}")

asyncio.run(error_handling_example())
```

## URL Utilities

### URL Validation and Normalization

```python
from web_fetch import is_valid_url, normalize_url, analyze_url

def url_utilities_example():
    """Demonstrate URL utility functions"""
    
    test_urls = [
        "https://example.com",
        "HTTPS://EXAMPLE.COM/PATH/../OTHER?b=2&a=1",
        "http://user:pass@example.com:8080/path?query=value#fragment",
        "not-a-valid-url",
        "ftp://files.example.com/file.txt"
    ]
    
    for url in test_urls:
        print(f"\n🔗 Testing URL: {url}")
        
        # Validate URL
        is_valid = is_valid_url(url)
        print(f"   Valid: {is_valid}")
        
        if is_valid:
            # Normalize URL
            normalized = normalize_url(url)
            print(f"   Normalized: {normalized}")
            
            # Analyze URL
            analysis = analyze_url(normalized)
            print(f"   Domain: {analysis.domain}")
            print(f"   Secure: {analysis.is_secure}")
            print(f"   Port: {analysis.port}")

url_utilities_example()
```

## Next Steps

These examples cover the fundamental WebFetch operations. For more advanced usage, check out:

- **[User Guide](../user-guide/configuration.md)** - Detailed configuration options
- **[Advanced Examples](../examples/advanced.md)** - Complex scenarios and patterns
- **[API Reference](../api/core.md)** - Complete API documentation
- **[CLI Tools](../cli/overview.md)** - Command-line interface usage
