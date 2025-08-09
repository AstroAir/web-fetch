# Web-Fetch API Reference

This document provides comprehensive API documentation for the web-fetch library, covering all public classes, methods, functions, and configuration options.

## Table of Contents

- [Core Classes](#core-classes)
  - [WebFetcher](#webfetcher)
  - [StreamingWebFetcher](#streamingwebfetcher)
  - [FTPFetcher](#ftpfetcher)
- [Configuration Classes](#configuration-classes)
  - [FetchConfig](#fetchconfig)
  - [FTPConfig](#ftpconfig)
  - [StreamingConfig](#streamingconfig)
- [Request and Response Models](#request-and-response-models)
- [Utility Functions](#utility-functions)
- [Exception Hierarchy](#exception-hierarchy)
- [Content Types and Parsing](#content-types-and-parsing)
- [Crawler Integration](#crawler-integration)

## Core Classes

### WebFetcher

The main async web fetcher class providing comprehensive HTTP request capabilities with modern Python features, connection pooling, retry logic, and advanced error handling.

**Class Signature:**

```python
class WebFetcher:
    def __init__(
        self,
        config: Optional[FetchConfig] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
        enable_deduplication: bool = False,
        enable_metrics: bool = False,
        transformation_pipeline: Optional[TransformationPipeline] = None,
        cache_config: Optional[EnhancedCacheConfig] = None,
        js_config: Optional[JSRenderConfig] = None
    )
```

**Key Features:**

- Async/await support with proper session management
- Connection pooling and timeout configuration
- Intelligent retry logic with exponential backoff
- Circuit breaker pattern for resilience
- Request deduplication and caching
- Comprehensive error handling and metrics collection

**Basic Usage:**

```python
from web_fetch import WebFetcher, FetchConfig, FetchRequest, ContentType

async def basic_example():
    config = FetchConfig(
        total_timeout=30.0,
        max_concurrent_requests=10,
        max_retries=3
    )

    async with WebFetcher(config) as fetcher:
        request = FetchRequest(
            url="https://api.example.com/data",
            content_type=ContentType.JSON
        )
        result = await fetcher.fetch_single(request)

        if result.is_success:
            print(f"Data: {result.content}")
            print(f"Response time: {result.response_time:.2f}s")
        else:
            print(f"Error: {result.error}")
```

**Advanced Usage with All Features:**

```python
from web_fetch import (
    WebFetcher, FetchConfig, CircuitBreakerConfig,
    EnhancedCacheConfig, TransformationPipeline
)

async def advanced_example():
    # Circuit breaker configuration
    cb_config = CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=60.0,
        success_threshold=3
    )

    # Enhanced caching configuration
    cache_config = EnhancedCacheConfig(
        backend="memory",
        ttl_seconds=300,
        max_size=1000,
        enable_compression=True
    )

    # Create fetcher with all advanced features
    async with WebFetcher(
        config=FetchConfig(max_concurrent_requests=20),
        circuit_breaker_config=cb_config,
        enable_deduplication=True,
        enable_metrics=True,
        cache_config=cache_config
    ) as fetcher:
        # Your requests here
        pass
```

#### Methods

##### `fetch_single(request: FetchRequest) -> FetchResult`

Fetch a single URL with comprehensive retry logic and error handling.

**Parameters:**

- `request` (FetchRequest): Request specification containing URL, method, headers, and parsing options

**Returns:**

- `FetchResult`: Response data with status, content, timing, and error information

**Raises:**

- `WebFetchError`: If session is not properly initialized
- `TimeoutError`: If request exceeds timeout limits
- `ConnectionError`: If connection cannot be established
- `HTTPError`: For HTTP-level errors (4xx, 5xx status codes)

**Example:**

```python
request = FetchRequest(
    url="https://api.example.com/users/123",
    method="GET",
    headers={"Authorization": "Bearer token"},
    content_type=ContentType.JSON,
    timeout_override=60.0
)

result = await fetcher.fetch_single(request)
print(f"Status: {result.status_code}")
print(f"Content: {result.content}")
print(f"Response time: {result.response_time:.2f}s")
```

##### `fetch_batch(batch_request: BatchFetchRequest) -> BatchFetchResult`

Fetch multiple URLs concurrently with intelligent batching and error handling.

**Parameters:**

- `batch_request` (BatchFetchRequest): Batch specification with multiple requests and options

**Returns:**

- `BatchFetchResult`: Aggregated results with success rate, timing, and individual responses

**Example:**

```python
from web_fetch import BatchFetchRequest

requests = [
    FetchRequest(url=f"https://api.example.com/item/{i}")
    for i in range(1, 11)
]

batch_request = BatchFetchRequest(
    requests=requests,
    fail_fast=False,
    return_exceptions=True
)

result = await fetcher.fetch_batch(batch_request)
print(f"Success rate: {result.success_rate:.1f}%")
print(f"Total time: {result.total_time:.2f}s")
print(f"Successful requests: {len(result.successful_results)}")
```

### StreamingWebFetcher

Extended WebFetcher class specialized for streaming large files and continuous data with memory-efficient chunked downloading, progress tracking, and resumable transfers.

**Class Signature:**

```python
class StreamingWebFetcher(WebFetcher):
    def __init__(self, config: Optional[FetchConfig] = None)
```

**Key Features:**

- Memory-efficient streaming for large files
- Real-time progress tracking with callbacks
- Resumable downloads for interrupted transfers
- Configurable chunk sizes for optimal performance
- Automatic directory creation for output paths
- File size limits and validation

**Basic Streaming Example:**

```python
from web_fetch import StreamingWebFetcher, StreamRequest, ProgressInfo
from pathlib import Path

def progress_callback(progress: ProgressInfo):
    if progress.total_bytes:
        percent = (progress.bytes_downloaded / progress.total_bytes) * 100
        print(f"Progress: {percent:.1f}% - {progress.speed_human}")

async def stream_example():
    async with StreamingWebFetcher() as fetcher:
        request = StreamRequest(
            url="https://example.com/large-file.zip",
            output_path=Path("downloads/file.zip"),
            chunk_size=16384,  # 16KB chunks
            max_file_size=100 * 1024 * 1024  # 100MB limit
        )

        result = await fetcher.stream_fetch(request, progress_callback)

        if result.is_success:
            print(f"Downloaded {result.bytes_downloaded:,} bytes")
            print(f"Average speed: {result.average_speed_human}")
        else:
            print(f"Download failed: {result.error}")
```

#### Methods

##### `stream_fetch(request: StreamRequest, progress_callback: Optional[Callable[[ProgressInfo], None]] = None) -> StreamResult`

Stream download content with chunked reading and progress tracking.

**Parameters:**

- `request` (StreamRequest): Streaming request specification
- `progress_callback` (Optional[Callable]): Callback function for progress updates

**Returns:**

- `StreamResult`: Streaming result with download statistics and metadata

**Example:**

```python
request = StreamRequest(
    url="https://example.com/dataset.csv",
    output_path=Path("data/dataset.csv"),
    chunk_size=32768,  # 32KB chunks
    enable_resume=True
)

result = await fetcher.stream_fetch(request, progress_callback)
```

### FTPFetcher

Async FTP client with comprehensive functionality.

```python
from web_fetch.ftp import FTPFetcher, FTPConfig, FTPRequest

config = FTPConfig(
    host="ftp.example.com",
    username="user",
    password="pass"
)

async with FTPFetcher(config) as ftp:
    request = FTPRequest(
        remote_path="/path/to/file.txt",
        local_path="downloads/file.txt"
    )
    result = await ftp.download_file(request)
```

## Configuration Classes

### FetchConfig

Comprehensive configuration model for HTTP operations with validation and intelligent defaults.

**Class Signature:**

```python
class FetchConfig(BaseConfig):
    # Timeout settings
    total_timeout: float = 30.0
    connect_timeout: float = 10.0
    read_timeout: float = 20.0

    # Concurrency settings
    max_concurrent_requests: int = 10
    max_connections_per_host: int = 5

    # Retry settings
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    max_retries: int = 3
    retry_delay: float = 1.0

    # Content and security settings
    max_response_size: int = 10 * 1024 * 1024
    follow_redirects: bool = True
    verify_ssl: bool = True

    # Headers
    headers: RequestHeaders = RequestHeaders()
```

**Field Descriptions:**

**Timeout Settings:**

- `total_timeout` (float): Maximum total time for entire request (default: 30.0s)
- `connect_timeout` (float): Maximum time for connection establishment (default: 10.0s)
- `read_timeout` (float): Maximum time for response data reading (default: 20.0s)

**Concurrency Settings:**

- `max_concurrent_requests` (int): Maximum simultaneous requests (default: 10, range: 1-100)
- `max_connections_per_host` (int): Maximum connections per host (default: 5, range: 1-20)

**Retry Settings:**

- `retry_strategy` (RetryStrategy): Retry delay calculation method (EXPONENTIAL, LINEAR, or NONE)
- `max_retries` (int): Maximum retry attempts (default: 3, range: 0-10)
- `retry_delay` (float): Base delay between retries in seconds (default: 1.0s, range: 0.1-60.0s)

**Content and Security:**

- `max_response_size` (int): Maximum response size in bytes (default: 10MB)
- `follow_redirects` (bool): Whether to follow HTTP redirects (default: True)
- `verify_ssl` (bool): Whether to verify SSL certificates (default: True)

**Usage Examples:**

```python
from web_fetch import FetchConfig, RetryStrategy, RequestHeaders

# Basic configuration
basic_config = FetchConfig(
    total_timeout=60.0,
    max_concurrent_requests=20,
    max_retries=5
)

# Production configuration with custom headers
prod_config = FetchConfig(
    # Timeout settings
    total_timeout=45.0,
    connect_timeout=15.0,
    read_timeout=30.0,

    # Performance settings
    max_concurrent_requests=25,
    max_connections_per_host=8,

    # Retry configuration
    retry_strategy=RetryStrategy.LINEAR,
    max_retries=3,
    retry_delay=2.0,

    # Content settings
    max_response_size=50 * 1024 * 1024,  # 50MB
    follow_redirects=True,
    verify_ssl=True,

    # Custom headers
    headers=RequestHeaders(
        user_agent="MyApp/1.0",
        custom_headers={
            "X-API-Key": "secret-key",
            "Accept": "application/json"
        }
    )
)

# High-performance configuration
fast_config = FetchConfig(
    total_timeout=15.0,
    max_concurrent_requests=50,
    max_connections_per_host=15,
    retry_strategy=RetryStrategy.NONE,  # No retries for speed
    max_response_size=100 * 1024 * 1024  # 100MB
)
```

### StreamingConfig

Configuration for streaming operations.

```python
from web_fetch import StreamingConfig

config = StreamingConfig(
    chunk_size=16384,           # 16KB chunks
    enable_progress=True,       # Enable progress tracking
    max_file_size=100*1024*1024 # 100MB limit
)
```

### FTPConfig

Configuration for FTP operations.

```python
from web_fetch.ftp import FTPConfig, FTPMode, FTPAuthType

config = FTPConfig(
    host="ftp.example.com",
    port=21,
    username="user",
    password="pass",
    mode=FTPMode.PASSIVE,
    auth_type=FTPAuthType.PASSWORD,
    timeout=30.0,
    max_connections=5
)
```

## Request Classes

### FetchRequest

HTTP request specification.

```python
from web_fetch import FetchRequest, ContentType

request = FetchRequest(
    url="https://api.example.com/data",
    method="POST",                 # HTTP method
    headers={"Authorization": "Bearer token"},
    data={"key": "value"},        # Request data
    content_type=ContentType.JSON, # Content parsing type
    timeout_override=15.0         # Override default timeout
)
```

### StreamRequest

Streaming request specification.

```python
from web_fetch import StreamRequest, StreamingConfig
from pathlib import Path

request = StreamRequest(
    url="https://example.com/large-file.zip",
    output_path=Path("downloads/file.zip"),
    streaming_config=StreamingConfig(chunk_size=32768),
    resume_download=True,         # Resume partial downloads
    verify_checksum=True          # Verify file integrity
)
```

### FTPRequest

FTP operation request.

```python
from web_fetch.ftp import FTPRequest, FTPTransferMode

request = FTPRequest(
    remote_path="/remote/file.txt",
    local_path="local/file.txt",
    transfer_mode=FTPTransferMode.BINARY,
    create_directories=True,      # Create local dirs if needed
    overwrite_existing=False      # Don't overwrite existing files
)
```

## Result Classes

### FetchResult

HTTP response result.

```python
result = await fetcher.fetch_single(request)

print(f"Success: {result.is_success}")
print(f"Status: {result.status_code}")
print(f"Content: {result.content}")
print(f"Headers: {result.headers}")
print(f"Response time: {result.response_time}")
print(f"Error: {result.error}")
```

### StreamResult

Streaming operation result.

```python
result = await fetcher.stream_fetch(request)

print(f"Success: {result.is_success}")
print(f"Bytes downloaded: {result.bytes_downloaded}")
print(f"File path: {result.file_path}")
print(f"Checksum: {result.checksum}")
```

### FTPResult

FTP operation result.

```python
result = await ftp.download_file(request)

print(f"Success: {result.is_success}")
print(f"Bytes transferred: {result.bytes_transferred}")
print(f"Transfer speed: {result.transfer_speed}")
print(f"File info: {result.file_info}")
```

## Utility Functions

### URL Utilities

```python
from web_fetch import is_valid_url, normalize_url, analyze_url

# Validate URLs
valid = is_valid_url("https://example.com")

# Normalize URLs
normalized = normalize_url("HTTPS://EXAMPLE.COM/path/../other?b=2&a=1")

# Analyze URLs
analysis = analyze_url("https://example.com:8080/path")
print(f"Domain: {analysis.domain}")
print(f"Secure: {analysis.is_secure}")
print(f"Port: {analysis.port}")
```

### Response Analysis

```python
from web_fetch import analyze_headers, detect_content_type

# Analyze response headers
header_analysis = analyze_headers(response_headers)
print(f"Cacheable: {header_analysis.is_cacheable}")
print(f"Security headers: {header_analysis.has_security_headers}")

# Detect content type
content_type = detect_content_type(headers, content_bytes)
```

### Caching

```python
from web_fetch import fetch_with_cache, CacheConfig

cache_config = CacheConfig(
    max_size=100,              # Max 100 entries
    ttl_seconds=300,           # 5 minute TTL
    enable_compression=True    # Compress cached data
)

result = await fetch_with_cache(url, cache_config=cache_config)
```

## Enums

### ContentType

- `ContentType.TEXT` - Parse as UTF-8 text
- `ContentType.JSON` - Parse as JSON object
- `ContentType.HTML` - Parse HTML and extract structured data
- `ContentType.RAW` - Return raw bytes

### RetryStrategy

- `RetryStrategy.EXPONENTIAL` - Exponential backoff (default)
- `RetryStrategy.LINEAR` - Linear backoff
- `RetryStrategy.NONE` - No retries

### FTPMode

- `FTPMode.ACTIVE` - Active FTP mode
- `FTPMode.PASSIVE` - Passive FTP mode (default)

### FTPAuthType

- `FTPAuthType.ANONYMOUS` - Anonymous login
- `FTPAuthType.PASSWORD` - Username/password authentication
- `FTPAuthType.KEY` - Key-based authentication

## Exception Hierarchy

```
WebFetchError
├── NetworkError
├── TimeoutError
├── ConnectionError
├── HTTPError
│   ├── AuthenticationError (401, 403)
│   ├── NotFoundError (404)
│   ├── RateLimitError (429)
│   └── ServerError (5xx)
├── ContentError
└── FTPError
    ├── FTPConnectionError
    ├── FTPAuthenticationError
    ├── FTPTimeoutError
    ├── FTPTransferError
    ├── FTPFileNotFoundError
    ├── FTPPermissionError
    ├── FTPVerificationError
    └── FTPProtocolError
```
