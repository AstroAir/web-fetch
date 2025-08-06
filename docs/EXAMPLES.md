# Examples and Use Cases

This document provides comprehensive examples for using the web-fetch library in various scenarios.

## Basic HTTP Fetching

### Simple GET Request

```python
import asyncio
from web_fetch import fetch_url, ContentType

async def simple_fetch():
    result = await fetch_url("https://httpbin.org/json", ContentType.JSON)
    if result.is_success:
        print(f"Status: {result.status_code}")
        print(f"Content: {result.content}")
    else:
        print(f"Error: {result.error}")

asyncio.run(simple_fetch())
```

### POST Request with Data

```python
import asyncio
from web_fetch import WebFetcher, FetchRequest, ContentType

async def post_example():
    request = FetchRequest(
        url="https://httpbin.org/post",
        method="POST",
        data={"name": "John", "age": 30},
        content_type=ContentType.JSON
    )
    
    async with WebFetcher() as fetcher:
        result = await fetcher.fetch_single(request)
        print(result.content)

asyncio.run(post_example())
```

### Custom Headers and Authentication

```python
import asyncio
from web_fetch import WebFetcher, FetchRequest, ContentType

async def auth_example():
    request = FetchRequest(
        url="https://api.github.com/user",
        headers={
            "Authorization": "token YOUR_GITHUB_TOKEN",
            "User-Agent": "MyApp/1.0"
        },
        content_type=ContentType.JSON
    )
    
    async with WebFetcher() as fetcher:
        result = await fetcher.fetch_single(request)
        if result.is_success:
            print(f"User: {result.content['login']}")

asyncio.run(auth_example())
```

## Batch Processing

### Fetch Multiple URLs Concurrently

```python
import asyncio
from web_fetch import fetch_urls, ContentType

async def batch_fetch():
    urls = [
        "https://httpbin.org/get",
        "https://httpbin.org/json",
        "https://httpbin.org/user-agent",
        "https://httpbin.org/headers"
    ]
    
    result = await fetch_urls(urls, ContentType.JSON)
    print(f"Success rate: {result.success_rate:.1f}%")
    print(f"Total time: {result.total_time:.2f}s")
    
    for i, res in enumerate(result.results):
        if res.is_success:
            print(f"URL {i+1}: {res.status_code}")
        else:
            print(f"URL {i+1}: Failed - {res.error}")

asyncio.run(batch_fetch())
```

### Advanced Batch Configuration

```python
import asyncio
from web_fetch import WebFetcher, BatchFetchRequest, FetchRequest, FetchConfig

async def advanced_batch():
    config = FetchConfig(
        max_concurrent_requests=5,
        total_timeout=30.0,
        max_retries=2
    )
    
    requests = [
        FetchRequest(url=f"https://httpbin.org/delay/{i}")
        for i in range(1, 6)
    ]
    
    batch_request = BatchFetchRequest(
        requests=requests,
        fail_fast=False,  # Continue even if some requests fail
        return_exceptions=True
    )
    
    async with WebFetcher(config) as fetcher:
        result = await fetcher.fetch_batch(batch_request)
        print(f"Completed: {len(result.results)}")
        print(f"Success rate: {result.success_rate:.1f}%")

asyncio.run(advanced_batch())
```

## Streaming and Large Files

### Download Large File with Progress

```python
import asyncio
from pathlib import Path
from web_fetch import download_file, ProgressInfo

def progress_callback(progress: ProgressInfo):
    if progress.total_bytes:
        percentage = progress.percentage or 0
        print(f"Progress: {percentage:.1f}% ({progress.speed_human})")

async def download_example():
    result = await download_file(
        url="https://httpbin.org/bytes/1048576",  # 1MB test file
        output_path=Path("downloads/large_file.bin"),
        chunk_size=8192,
        progress_callback=progress_callback
    )
    
    if result.is_success:
        print(f"Downloaded {result.bytes_downloaded:,} bytes")
        print(f"Time: {result.response_time:.2f}s")

asyncio.run(download_example())
```

### Streaming to Memory

```python
import asyncio
from web_fetch import StreamingWebFetcher, StreamRequest

async def stream_to_memory():
    request = StreamRequest(
        url="https://httpbin.org/stream/10",
        output_path=None,  # Stream to memory
        chunk_size=1024
    )
    
    async with StreamingWebFetcher() as fetcher:
        result = await fetcher.stream_fetch(request)
        if result.is_success:
            print(f"Streamed {len(result.content)} bytes to memory")

asyncio.run(stream_to_memory())
```

## FTP Operations

### Basic FTP Download

```python
import asyncio
from web_fetch.ftp import FTPFetcher, FTPConfig, FTPRequest

async def ftp_download():
    config = FTPConfig(
        host="ftp.example.com",
        username="user",
        password="password"
    )
    
    request = FTPRequest(
        remote_path="/path/to/file.txt",
        local_path="downloads/file.txt"
    )
    
    async with FTPFetcher(config) as ftp:
        result = await ftp.download_file(request)
        if result.is_success:
            print(f"Downloaded {result.bytes_transferred} bytes")

asyncio.run(ftp_download())
```

### FTP Directory Listing

```python
import asyncio
from web_fetch.ftp import ftp_list_directory, FTPConfig

async def list_ftp_directory():
    config = FTPConfig(
        host="ftp.example.com",
        username="anonymous",
        password="guest@example.com"
    )
    
    files = await ftp_list_directory("/pub", config)
    for file_info in files:
        print(f"{file_info.name}: {file_info.size} bytes")

asyncio.run(list_ftp_directory())
```

## Error Handling and Retries

### Custom Error Handling

```python
import asyncio
from web_fetch import WebFetcher, FetchRequest, WebFetchError, HTTPError

async def error_handling_example():
    request = FetchRequest(url="https://httpbin.org/status/404")
    
    async with WebFetcher() as fetcher:
        try:
            result = await fetcher.fetch_single(request)
            if not result.is_success:
                print(f"Request failed: {result.error}")
        except HTTPError as e:
            print(f"HTTP Error: {e.status_code} - {e}")
        except WebFetchError as e:
            print(f"Fetch Error: {e}")

asyncio.run(error_handling_example())
```

### Retry Configuration

```python
import asyncio
from web_fetch import WebFetcher, FetchConfig, FetchRequest, RetryStrategy

async def retry_example():
    config = FetchConfig(
        max_retries=5,
        retry_delay=1.0,
        retry_strategy=RetryStrategy.EXPONENTIAL
    )
    
    request = FetchRequest(url="https://httpbin.org/status/500")
    
    async with WebFetcher(config) as fetcher:
        result = await fetcher.fetch_single(request)
        print(f"Retry count: {result.retry_count}")

asyncio.run(retry_example())
```

## Caching and Performance

### Response Caching

```python
import asyncio
from web_fetch import fetch_with_cache, CacheConfig

async def caching_example():
    cache_config = CacheConfig(
        max_size=100,
        ttl_seconds=300,  # 5 minutes
        enable_compression=True
    )
    
    # First request - fetched from server
    result1 = await fetch_with_cache(
        "https://httpbin.org/json",
        cache_config=cache_config
    )
    print(f"First request: {result1.response_time:.2f}s")
    
    # Second request - served from cache
    result2 = await fetch_with_cache(
        "https://httpbin.org/json",
        cache_config=cache_config
    )
    print(f"Cached request: {result2.response_time:.2f}s")

asyncio.run(caching_example())
```

### Rate Limiting

```python
import asyncio
from web_fetch import WebFetcher, FetchConfig, RateLimitConfig

async def rate_limiting_example():
    rate_config = RateLimitConfig(
        requests_per_second=2.0,  # 2 requests per second
        burst_size=5,             # Allow bursts up to 5
        per_host=True             # Separate limits per host
    )
    
    config = FetchConfig(rate_limit_config=rate_config)
    
    urls = [f"https://httpbin.org/delay/1" for _ in range(10)]
    
    async with WebFetcher(config) as fetcher:
        start_time = asyncio.get_event_loop().time()
        
        tasks = [
            fetcher.fetch_single(FetchRequest(url=url))
            for url in urls
        ]
        
        results = await asyncio.gather(*tasks)
        
        end_time = asyncio.get_event_loop().time()
        print(f"Total time: {end_time - start_time:.2f}s")
        print(f"Average rate: {len(results) / (end_time - start_time):.2f} req/s")

asyncio.run(rate_limiting_example())
```

## Advanced Features

### Circuit Breaker Pattern

```python
import asyncio
from web_fetch import EnhancedWebFetcher, FetchRequest
from web_fetch.utils import CircuitBreakerConfig

async def circuit_breaker_example():
    cb_config = CircuitBreakerConfig(
        failure_threshold=3,      # Open after 3 failures
        recovery_timeout=10.0,    # Try to recover after 10s
        expected_exception=HTTPError
    )
    
    config = FetchConfig(circuit_breaker_config=cb_config)
    
    async with EnhancedWebFetcher(config) as fetcher:
        # This will eventually trigger the circuit breaker
        for i in range(10):
            request = FetchRequest(url="https://httpbin.org/status/500")
            result = await fetcher.fetch_single(request)
            print(f"Request {i+1}: {result.is_success}")

asyncio.run(circuit_breaker_example())
```

### Response Transformation

```python
import asyncio
from web_fetch import EnhancedWebFetcher, FetchRequest
from web_fetch.utils import TransformationPipeline, JSONPathExtractor

async def transformation_example():
    # Extract specific data from JSON responses
    pipeline = TransformationPipeline([
        JSONPathExtractor("$.slideshow.title"),
        lambda x: x.upper() if x else None
    ])
    
    request = FetchRequest(
        url="https://httpbin.org/json",
        transformation_pipeline=pipeline
    )
    
    async with EnhancedWebFetcher() as fetcher:
        result = await fetcher.fetch_single(request)
        print(f"Transformed result: {result.content}")

asyncio.run(transformation_example())
```

## Integration Examples

### Web Scraping with BeautifulSoup

```python
import asyncio
from web_fetch import fetch_url, ContentType

async def scraping_example():
    result = await fetch_url("https://httpbin.org/html", ContentType.HTML)
    
    if result.is_success:
        # result.content is already parsed HTML data
        print(f"Title: {result.content['title']}")
        print(f"Links found: {len(result.content['links'])}")
        print(f"Images found: {len(result.content['images'])}")

asyncio.run(scraping_example())
```

### API Integration with Pagination

```python
import asyncio
from web_fetch import WebFetcher, FetchRequest, ContentType

async def paginated_api_example():
    async with WebFetcher() as fetcher:
        page = 1
        all_data = []
        
        while True:
            request = FetchRequest(
                url=f"https://api.example.com/data?page={page}",
                headers={"Authorization": "Bearer YOUR_TOKEN"},
                content_type=ContentType.JSON
            )
            
            result = await fetcher.fetch_single(request)
            if not result.is_success:
                break
                
            data = result.content
            all_data.extend(data.get('items', []))
            
            if not data.get('has_next', False):
                break
                
            page += 1
        
        print(f"Total items collected: {len(all_data)}")

asyncio.run(paginated_api_example())
```
