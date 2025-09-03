# Quick Start

Get up and running with WebFetch in minutes! This guide covers the most common use cases.

## Your First Request

Let's start with a simple HTTP GET request:

```python
import asyncio
from web_fetch import fetch_url, ContentType

async def main():
    # Fetch JSON data
    result = await fetch_url("https://httpbin.org/json", ContentType.JSON)
    
    if result.is_success:
        print(f"✅ Success! Status: {result.status_code}")
        print(f"Content: {result.content}")
    else:
        print(f"❌ Error: {result.error}")

# Run the async function
asyncio.run(main())
```

## Different Content Types

WebFetch can handle various content types automatically:

=== "JSON"

    ```python
    import asyncio
    from web_fetch import fetch_url, ContentType

    async def fetch_json():
        result = await fetch_url("https://httpbin.org/json", ContentType.JSON)
        if result.is_success:
            # result.content is a Python dict
            print(result.content["slideshow"]["title"])

    asyncio.run(fetch_json())
    ```

=== "HTML"

    ```python
    import asyncio
    from web_fetch import fetch_url, ContentType

    async def fetch_html():
        result = await fetch_url("https://example.com", ContentType.HTML)
        if result.is_success:
            # result.content contains parsed HTML data
            print(f"Title: {result.content['title']}")
            print(f"Links found: {len(result.content['links'])}")

    asyncio.run(fetch_html())
    ```

=== "Text"

    ```python
    import asyncio
    from web_fetch import fetch_url, ContentType

    async def fetch_text():
        result = await fetch_url("https://httpbin.org/robots.txt", ContentType.TEXT)
        if result.is_success:
            # result.content is a string
            print(result.content)

    asyncio.run(fetch_text())
    ```

=== "Raw Bytes"

    ```python
    import asyncio
    from web_fetch import fetch_url, ContentType

    async def fetch_raw():
        result = await fetch_url("https://httpbin.org/bytes/1024", ContentType.RAW)
        if result.is_success:
            # result.content is bytes
            print(f"Downloaded {len(result.content)} bytes")

    asyncio.run(fetch_raw())
    ```

## Batch Requests

Fetch multiple URLs concurrently:

```python
import asyncio
from web_fetch import fetch_urls, ContentType

async def batch_fetch():
    urls = [
        "https://httpbin.org/get",
        "https://httpbin.org/json",
        "https://httpbin.org/html"
    ]
    
    result = await fetch_urls(urls, ContentType.TEXT)
    
    print(f"📊 Batch Results:")
    print(f"Success rate: {result.success_rate:.1f}%")
    print(f"Total time: {result.total_time:.2f}s")
    print(f"Successful requests: {len(result.successful_results)}")
    print(f"Failed requests: {len(result.failed_results)}")

asyncio.run(batch_fetch())
```

## POST Requests with Data

Send data to APIs:

```python
import asyncio
from web_fetch import WebFetcher, FetchRequest, ContentType

async def post_data():
    request = FetchRequest(
        url="https://httpbin.org/post",
        method="POST",
        headers={"Content-Type": "application/json"},
        data={"name": "WebFetch", "version": "1.0"},
        content_type=ContentType.JSON
    )
    
    async with WebFetcher() as fetcher:
        result = await fetcher.fetch_single(request)
        
        if result.is_success:
            print("✅ POST successful!")
            print(f"Response: {result.content}")

asyncio.run(post_data())
```

## File Downloads

Download files with progress tracking:

```python
import asyncio
from pathlib import Path
from web_fetch import download_file, ProgressInfo

def progress_callback(progress: ProgressInfo):
    if progress.total_bytes:
        percentage = progress.percentage or 0
        print(f"📥 Progress: {percentage:.1f}% ({progress.speed_human})")

async def download_example():
    result = await download_file(
        url="https://httpbin.org/bytes/1048576",  # 1MB test file
        output_path=Path("downloads/test_file.bin"),
        chunk_size=8192,
        progress_callback=progress_callback
    )
    
    if result.is_success:
        print(f"✅ Downloaded {result.bytes_downloaded:,} bytes")
        print(f"⏱️  Time taken: {result.response_time:.2f}s")

asyncio.run(download_example())
```

## Using the CLI

WebFetch includes a powerful command-line interface:

```bash
# Simple GET request
web-fetch https://httpbin.org/json

# Fetch as specific content type
web-fetch -t json https://httpbin.org/json

# POST request with data
web-fetch --method POST --data '{"key":"value"}' https://httpbin.org/post

# Batch fetch from file
echo "https://httpbin.org/get" > urls.txt
echo "https://httpbin.org/json" >> urls.txt
web-fetch --batch urls.txt

# Download with progress
web-fetch --stream --progress https://httpbin.org/bytes/1048576 -o large_file.bin
```

## Error Handling

Always check for errors in your code:

```python
import asyncio
from web_fetch import fetch_url, ContentType, WebFetchError

async def safe_fetch():
    try:
        result = await fetch_url("https://httpbin.org/status/404", ContentType.JSON)
        
        if result.is_success:
            print("✅ Success!")
            print(result.content)
        else:
            print(f"❌ Request failed: {result.error}")
            print(f"Status code: {result.status_code}")
            
    except WebFetchError as e:
        print(f"💥 WebFetch error: {e}")
    except Exception as e:
        print(f"🔥 Unexpected error: {e}")

asyncio.run(safe_fetch())
```

## Configuration

Customize WebFetch behavior:

```python
import asyncio
from web_fetch import WebFetcher, FetchConfig, FetchRequest, ContentType

async def configured_fetch():
    # Custom configuration
    config = FetchConfig(
        total_timeout=30.0,           # 30 second timeout
        max_concurrent_requests=5,    # Limit concurrency
        max_retries=3,                # Retry failed requests
        retry_delay=1.0,              # Wait 1s between retries
        verify_ssl=True               # Verify SSL certificates
    )
    
    request = FetchRequest(
        url="https://httpbin.org/delay/2",
        content_type=ContentType.JSON
    )
    
    async with WebFetcher(config) as fetcher:
        result = await fetcher.fetch_single(request)
        
        if result.is_success:
            print("✅ Configured fetch successful!")

asyncio.run(configured_fetch())
```

## Next Steps

Now that you've got the basics, explore more advanced features:

- **[Basic Examples](basic-examples.md)** - More detailed examples
- **[Configuration Guide](../user-guide/configuration.md)** - Detailed configuration options
- **[API Reference](../api/core.md)** - Complete API documentation
- **[Advanced Topics](../advanced/streaming.md)** - Streaming, caching, and more

## Common Patterns

### URL Validation

```python
from web_fetch import is_valid_url, normalize_url

url = "HTTPS://EXAMPLE.COM/path/../other?b=2&a=1"

if is_valid_url(url):
    normalized = normalize_url(url)
    print(f"Normalized: {normalized}")
```

### Caching

```python
from web_fetch import fetch_with_cache

# Second request will be served from cache
result1 = await fetch_with_cache("https://httpbin.org/json")
result2 = await fetch_with_cache("https://httpbin.org/json")  # From cache!
```

### Custom Headers

```python
request = FetchRequest(
    url="https://api.example.com/data",
    headers={
        "Authorization": "Bearer your-token",
        "User-Agent": "MyApp/1.0",
        "Accept": "application/json"
    },
    content_type=ContentType.JSON
)
```

Ready to dive deeper? Check out the [User Guide](../user-guide/configuration.md) for comprehensive documentation!
