# Core API Reference

This page documents the core WebFetch API classes and functions.

## Core Functions

### `fetch_url()`

Fetch a single URL with automatic content type handling.

```python
async def fetch_url(
    url: str,
    content_type: ContentType = ContentType.TEXT,
    timeout: Optional[float] = None,
    headers: Optional[Dict[str, str]] = None,
    **kwargs
) -> FetchResult
```

**Parameters:**

- `url` (str): The URL to fetch
- `content_type` (ContentType): How to parse the response content
- `timeout` (float, optional): Request timeout in seconds
- `headers` (dict, optional): Custom HTTP headers
- `**kwargs`: Additional arguments passed to the underlying fetcher

**Returns:** `FetchResult` - The fetch result with content and metadata

**Example:**

```python
import asyncio
from web_fetch import fetch_url, ContentType

async def main():
    result = await fetch_url("https://httpbin.org/json", ContentType.JSON)
    if result.is_success:
        print(result.content)

asyncio.run(main())
```

### `fetch_urls()`

Fetch multiple URLs concurrently.

```python
async def fetch_urls(
    urls: List[str],
    content_type: ContentType = ContentType.TEXT,
    max_concurrent: int = 10,
    timeout: Optional[float] = None,
    **kwargs
) -> BatchResult
```

**Parameters:**

- `urls` (List[str]): List of URLs to fetch
- `content_type` (ContentType): How to parse response content
- `max_concurrent` (int): Maximum concurrent requests
- `timeout` (float, optional): Request timeout in seconds
- `**kwargs`: Additional arguments

**Returns:** `BatchResult` - Batch operation results

**Example:**

```python
import asyncio
from web_fetch import fetch_urls, ContentType

async def main():
    urls = ["https://httpbin.org/get", "https://httpbin.org/json"]
    result = await fetch_urls(urls, ContentType.JSON)
    print(f"Success rate: {result.success_rate:.1f}%")

asyncio.run(main())
```

### `download_file()`

Download a file with progress tracking and streaming support.

```python
async def download_file(
    url: str,
    output_path: Path,
    chunk_size: int = 8192,
    progress_callback: Optional[Callable[[ProgressInfo], None]] = None,
    max_file_size: Optional[int] = None,
    **kwargs
) -> StreamResult
```

**Parameters:**

- `url` (str): URL of the file to download
- `output_path` (Path): Where to save the downloaded file
- `chunk_size` (int): Size of chunks for streaming download
- `progress_callback` (callable, optional): Function called with progress updates
- `max_file_size` (int, optional): Maximum allowed file size in bytes
- `**kwargs`: Additional arguments

**Returns:** `StreamResult` - Download result with metadata

**Example:**

```python
import asyncio
from pathlib import Path
from web_fetch import download_file, ProgressInfo

def progress_callback(progress: ProgressInfo):
    if progress.percentage:
        print(f"Progress: {progress.percentage:.1f}%")

async def main():
    result = await download_file(
        "https://httpbin.org/bytes/1048576",
        Path("downloads/file.bin"),
        progress_callback=progress_callback
    )
    print(f"Downloaded {result.bytes_downloaded} bytes")

asyncio.run(main())
```

## Core Classes

### `WebFetcher`

Main async web fetcher class with comprehensive HTTP capabilities.

```python
class WebFetcher:
    def __init__(self, config: Optional[FetchConfig] = None):
        """Initialize WebFetcher with optional configuration."""
        
    async def __aenter__(self) -> "WebFetcher":
        """Async context manager entry."""
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        
    async def fetch_single(self, request: FetchRequest) -> FetchResult:
        """Fetch a single request."""
        
    async def fetch_batch(self, batch_request: BatchRequest) -> BatchResult:
        """Fetch multiple requests concurrently."""
        
    async def fetch_with_circuit_breaker(self, request: FetchRequest) -> FetchResult:
        """Fetch with circuit breaker pattern for resilience."""
```

**Example:**

```python
import asyncio
from web_fetch import WebFetcher, FetchConfig, FetchRequest, ContentType

async def main():
    config = FetchConfig(
        total_timeout=30.0,
        max_concurrent_requests=5,
        max_retries=3
    )
    
    request = FetchRequest(
        url="https://httpbin.org/json",
        content_type=ContentType.JSON
    )
    
    async with WebFetcher(config) as fetcher:
        result = await fetcher.fetch_single(request)
        if result.is_success:
            print(result.content)

asyncio.run(main())
```

### `StreamingWebFetcher`

Extended WebFetcher with streaming capabilities for large files.

```python
class StreamingWebFetcher(WebFetcher):
    async def stream_fetch(
        self,
        request: StreamRequest,
        progress_callback: Optional[Callable[[ProgressInfo], None]] = None
    ) -> StreamResult:
        """Stream fetch a large file with progress tracking."""
        
    async def stream_to_memory(
        self,
        request: StreamRequest,
        max_size: Optional[int] = None
    ) -> StreamResult:
        """Stream content to memory with size limits."""
```

**Example:**

```python
import asyncio
from pathlib import Path
from web_fetch import StreamingWebFetcher, StreamRequest, StreamingConfig

async def main():
    config = StreamingConfig(
        chunk_size=16384,
        enable_progress=True,
        max_file_size=100*1024*1024  # 100MB
    )
    
    request = StreamRequest(
        url="https://httpbin.org/bytes/1048576",
        output_path=Path("downloads/file.bin"),
        streaming_config=config
    )
    
    async with StreamingWebFetcher() as fetcher:
        result = await fetcher.stream_fetch(request)
        print(f"Downloaded {result.bytes_downloaded} bytes")

asyncio.run(main())
```

## Configuration Classes

### `FetchConfig`

Configuration model for HTTP fetching behavior.

```python
@dataclass
class FetchConfig:
    total_timeout: float = 30.0
    connect_timeout: float = 10.0
    read_timeout: float = 20.0
    max_concurrent_requests: int = 10
    max_connections_per_host: int = 5
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    max_response_size: int = 10 * 1024 * 1024  # 10MB
    verify_ssl: bool = True
    follow_redirects: bool = True
    headers: Optional[RequestHeaders] = None
```

### `FetchRequest`

Request model with validation.

```python
@dataclass
class FetchRequest:
    url: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    data: Optional[Union[Dict, str, bytes]] = None
    files: Optional[Dict[str, Any]] = None
    content_type: ContentType = ContentType.TEXT
    timeout_override: Optional[float] = None
```

### `StreamingConfig`

Configuration for streaming operations.

```python
@dataclass
class StreamingConfig:
    chunk_size: int = 8192
    enable_progress: bool = True
    max_file_size: Optional[int] = None
    buffer_size: int = 64 * 1024  # 64KB
    enable_resume: bool = True
```

## Result Classes

### `FetchResult`

Result dataclass with response data and metadata.

```python
@dataclass
class FetchResult:
    url: str
    is_success: bool
    status_code: Optional[int]
    content: Any
    headers: Optional[Dict[str, str]]
    response_time: float
    error: Optional[str]
    content_type: Optional[str]
    encoding: Optional[str]
    size_bytes: int
```

**Properties:**

- `is_success` (bool): Whether the request was successful
- `status_code` (int): HTTP status code
- `content` (Any): Parsed content based on content_type
- `headers` (dict): Response headers
- `response_time` (float): Request duration in seconds
- `error` (str): Error message if request failed

### `BatchResult`

Result for batch operations.

```python
@dataclass
class BatchResult:
    successful_results: List[FetchResult]
    failed_results: List[FetchResult]
    total_time: float
    success_rate: float
    total_requests: int
```

### `StreamResult`

Result for streaming operations.

```python
@dataclass
class StreamResult:
    url: str
    is_success: bool
    output_path: Optional[Path]
    bytes_downloaded: int
    response_time: float
    error: Optional[str]
    checksum: Optional[str]
    resume_supported: bool
```

## Enums

### `ContentType`

Supported content types for parsing.

```python
class ContentType(Enum):
    TEXT = "text"
    JSON = "json"
    HTML = "html"
    RAW = "raw"
```

### `RetryStrategy`

Retry strategies for failed requests.

```python
class RetryStrategy(Enum):
    NONE = "none"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
```

## Utility Functions

### URL Utilities

```python
def is_valid_url(url: str) -> bool:
    """Check if a URL is valid."""

def normalize_url(url: str) -> str:
    """Normalize a URL (lowercase, sort params, etc.)."""

def analyze_url(url: str) -> URLAnalysis:
    """Analyze URL components and properties."""
```

### Caching

```python
async def fetch_with_cache(
    url: str,
    content_type: ContentType = ContentType.TEXT,
    cache_config: Optional[CacheConfig] = None
) -> FetchResult:
    """Fetch URL with caching support."""
```

### Rate Limiting

```python
class RateLimiter:
    def __init__(self, config: RateLimitConfig):
        """Initialize rate limiter."""
        
    async def acquire(self, url: str) -> None:
        """Wait for permission to make request."""
```

## Next Steps

- **[Models Reference](models.md)** - Data models and configuration classes
- **[Utilities Reference](utilities.md)** - Utility functions and helpers
- **[Exceptions Reference](exceptions.md)** - Exception hierarchy and error handling
