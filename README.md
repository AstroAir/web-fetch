# Web Fetch - Modern Async Web Scraping Utility

A robust, production-ready web fetching tool built with modern Python 3.11+ features and AIOHTTP for efficient asynchronous HTTP handling.

## 🚀 Features

### Modern Python Capabilities
- **Async/await syntax** for concurrent request handling
- **Type hints** with Union types and Optional for better code safety
- **Context managers** for proper resource cleanup
- **Dataclasses and Pydantic models** for structured data handling
- **Pattern matching** for content parsing (Python 3.10+)
- **Comprehensive error handling** with custom exception hierarchy

### AIOHTTP Best Practices
- **Session management** with proper connection pooling
- **Timeout configuration** (total, connect, read timeouts)
- **Retry logic** with exponential backoff
- **Concurrent request limiting** with semaphores
- **SSL verification** and custom headers support
- **Response size limits** for memory safety

### Streaming Capabilities
- **Memory-efficient streaming** for large files and continuous data
- **Chunked reading** with configurable chunk sizes
- **Progress tracking** with real-time callbacks
- **Async file I/O** using aiofiles for non-blocking operations
- **Download resumption** and file size limits
- **Streaming to memory or files** with automatic directory creation

### Content Processing
- **Multiple content types**: JSON, HTML, text, raw bytes
- **HTML parsing** with BeautifulSoup integration
- **Automatic encoding detection** for text content
- **Structured HTML data extraction** (title, links, images, text)

### Utility Functions
- **URL validation and normalization** with comprehensive analysis
- **Response header analysis** and content type detection
- **In-memory caching** with TTL and LRU eviction
- **Rate limiting** with token bucket algorithm
- **Session persistence** for cookies and authentication

## 📦 Installation

```bash
# Clone the repository
git clone <repository-url>
cd web-fetch

# Install dependencies (using uv)
uv sync

# Or install with pip
pip install -e .

# Install with test dependencies
pip install -e ".[test]"
```

## 🔧 Quick Start

### Simple URL Fetching

```python
import asyncio
from web_fetch import fetch_url, ContentType

async def main():
    # Fetch as JSON
    result = await fetch_url("https://httpbin.org/json", ContentType.JSON)
    if result.is_success:
        print(f"Status: {result.status_code}")
        print(f"Content: {result.content}")

    # Fetch as HTML with parsing
    html_result = await fetch_url("https://example.com", ContentType.HTML)
    if html_result.is_success:
        print(f"Title: {html_result.content['title']}")
        print(f"Links: {len(html_result.content['links'])}")

asyncio.run(main())
```

### Batch Fetching

```python
import asyncio
from web_fetch import fetch_urls, ContentType

async def main():
    urls = [
        "https://httpbin.org/get",
        "https://httpbin.org/json",
        "https://httpbin.org/html"
    ]

    result = await fetch_urls(urls, ContentType.TEXT)
    print(f"Success rate: {result.success_rate:.1f}%")
    print(f"Total time: {result.total_time:.2f}s")

asyncio.run(main())
```

### Streaming Downloads

```python
import asyncio
from pathlib import Path
from web_fetch import download_file, ProgressInfo

def progress_callback(progress: ProgressInfo):
    if progress.total_bytes:
        percentage = progress.percentage or 0
        print(f"Progress: {percentage:.1f}% ({progress.speed_human})")

async def main():
    # Download a large file with progress tracking
    result = await download_file(
        url="https://httpbin.org/bytes/1048576",  # 1MB test file
        output_path=Path("downloads/large_file.bin"),
        chunk_size=8192,
        progress_callback=progress_callback
    )

    if result.is_success:
        print(f"Downloaded {result.bytes_downloaded:,} bytes in {result.response_time:.2f}s")

asyncio.run(main())
```

### Caching and URL Utilities

```python
import asyncio
from web_fetch import fetch_with_cache, is_valid_url, normalize_url, analyze_url

async def main():
    # URL validation and normalization
    url = "HTTPS://EXAMPLE.COM/path/../other?b=2&a=1"

    if is_valid_url(url):
        normalized = normalize_url(url)
        analysis = analyze_url(normalized)
        print(f"Normalized: {normalized}")
        print(f"Secure: {analysis.is_secure}")

    # Cached fetching (second request will be much faster)
    result1 = await fetch_with_cache("https://httpbin.org/json")
    result2 = await fetch_with_cache("https://httpbin.org/json")  # From cache

asyncio.run(main())
```

### Advanced Usage with Custom Configuration

```python
import asyncio
from web_fetch import WebFetcher, FetchConfig, FetchRequest, ContentType

async def main():
    # Custom configuration
    config = FetchConfig(
        total_timeout=30.0,
        max_concurrent_requests=5,
        max_retries=3,
        retry_delay=1.0,
        verify_ssl=True
    )

    # Custom request with headers
    request = FetchRequest(
        url="https://api.example.com/data",
        method="POST",
        headers={"Authorization": "Bearer token"},
        data={"key": "value"},
        content_type=ContentType.JSON
    )

    async with WebFetcher(config) as fetcher:
        result = await fetcher.fetch_single(request)
        print(f"Response: {result.content}")

asyncio.run(main())
```

## 🖥️ Command Line Interface

The library includes a powerful CLI for quick web fetching:

```bash
# Simple URL fetch
web-fetch https://httpbin.org/json

# Fetch as JSON with custom timeout
web-fetch -t json --timeout 30 https://httpbin.org/json

# Batch fetch from file
web-fetch --batch urls.txt --concurrent 5

# POST request with data
web-fetch --method POST --data '{"key":"value"}' https://httpbin.org/post

# Save results to file
web-fetch -o results.json --format json https://example.com

# Custom headers
web-fetch --headers "Authorization: Bearer token" --headers "X-API-Key: key" https://api.example.com

# Streaming download with progress
web-fetch --stream --progress --chunk-size 16384 -o large_file.zip https://example.com/file.zip

# Cached requests
web-fetch --cache --cache-ttl 600 https://api.example.com/data

# URL validation and normalization
web-fetch --validate-urls --normalize-urls https://EXAMPLE.COM/path/../other
```

### CLI Options

- `-t, --type`: Content type (text, json, html, raw)
- `--batch`: File containing URLs (one per line)
- `-o, --output`: Output file for results
- `--format`: Output format (json, summary, detailed)
- `--method`: HTTP method (GET, POST, PUT, DELETE, etc.)
- `--data`: Request data for POST/PUT requests
- `--headers`: Custom headers (can be used multiple times)
- `--timeout`: Request timeout in seconds
- `--concurrent`: Maximum concurrent requests
- `--retries`: Maximum retry attempts
- `--no-verify-ssl`: Disable SSL certificate verification

**Streaming Options:**
- `--stream`: Use streaming mode for downloads
- `--chunk-size`: Chunk size for streaming (default: 8192 bytes)
- `--progress`: Show progress bar for downloads
- `--max-file-size`: Maximum file size for downloads (bytes)

**Caching Options:**
- `--cache`: Enable response caching
- `--cache-ttl`: Cache TTL in seconds (default: 300)

**URL Utilities:**
- `--validate-urls`: Validate URLs before fetching
- `--normalize-urls`: Normalize URLs before fetching

**General Options:**
- `-v, --verbose`: Enable verbose output

## 📚 Documentation

### Complete Documentation Suite

The web-fetch library includes comprehensive documentation covering all aspects of usage, configuration, and development:

- **[API Reference](docs/API.md)** - Complete API documentation with examples
- **[Configuration Guide](docs/CONFIGURATION.md)** - Environment variables, config files, and setup
- **[Advanced Examples](docs/ADVANCED_EXAMPLES.md)** - FTP, crawlers, streaming, caching, and error handling
- **[Development Guide](docs/DEVELOPMENT.md)** - Testing, contributing, and architecture overview
- **[Crawler Integration](docs/CRAWLER_INTEGRATION_SUMMARY.md)** - Multi-crawler web scraping
- **[Examples Collection](docs/EXAMPLES.md)** - Basic to advanced usage patterns

### Quick API Reference

#### Core Classes

##### `WebFetcher`
Main async web fetcher class with comprehensive HTTP capabilities, connection pooling, retry logic, circuit breakers, and advanced error handling.

```python
from web_fetch import WebFetcher, FetchConfig, FetchRequest, ContentType

async with WebFetcher(config) as fetcher:
    # Single request
    result = await fetcher.fetch_single(request)

    # Batch requests
    batch_result = await fetcher.fetch_batch(batch_request)

    # With circuit breaker
    result = await fetcher.fetch_with_circuit_breaker(request)
```

**Key Features:**
- Async/await with proper session management
- Connection pooling and intelligent timeout handling
- Retry logic with exponential backoff
- Circuit breaker pattern for resilience
- Request deduplication and comprehensive caching
- Metrics collection and performance monitoring

#### `FetchConfig`
Configuration model with validation.

```python
config = FetchConfig(
    total_timeout=30.0,           # Total request timeout
    connect_timeout=10.0,         # Connection timeout
    read_timeout=20.0,            # Read timeout
    max_concurrent_requests=10,   # Concurrency limit
    max_retries=3,                # Retry attempts
    retry_delay=1.0,              # Base retry delay
    max_response_size=10*1024*1024,  # Max response size
    verify_ssl=True,              # SSL verification
    follow_redirects=True         # Follow redirects
)
```

#### `FetchRequest`
Request model with validation.

```python
request = FetchRequest(
    url="https://example.com",
    method="GET",                 # HTTP method
    headers={"Key": "Value"},     # Custom headers
    data={"key": "value"},        # Request data
    content_type=ContentType.JSON, # Content parsing type
    timeout_override=15.0         # Override default timeout
)
```

#### `FetchResult`
Result dataclass with response data and metadata.

```python
result = await fetcher.fetch_single(request)
print(f"Success: {result.is_success}")
print(f"Status: {result.status_code}")
print(f"Content: {result.content}")
print(f"Response time: {result.response_time}")
print(f"Error: {result.error}")
```

#### `StreamingWebFetcher`
Extended WebFetcher with streaming capabilities for large files.

```python
from web_fetch import StreamingWebFetcher, StreamRequest, StreamingConfig

streaming_config = StreamingConfig(
    chunk_size=16384,           # 16KB chunks
    enable_progress=True,       # Enable progress tracking
    max_file_size=100*1024*1024 # 100MB limit
)

request = StreamRequest(
    url="https://example.com/large-file.zip",
    output_path=Path("downloads/file.zip"),
    streaming_config=streaming_config
)

async with StreamingWebFetcher() as fetcher:
    result = await fetcher.stream_fetch(request, progress_callback)
```

### Utility Functions

#### URL Utilities
```python
from web_fetch import is_valid_url, normalize_url, analyze_url

# Validate URLs
valid = is_valid_url("https://example.com")

# Normalize URLs
normalized = normalize_url("HTTPS://EXAMPLE.COM/path/../other?b=2&a=1")

# Analyze URLs
analysis = analyze_url("https://example.com:8080/path")
print(f"Domain: {analysis.domain}, Secure: {analysis.is_secure}")
```

#### Response Analysis
```python
from web_fetch import analyze_headers, detect_content_type

# Analyze response headers
header_analysis = analyze_headers(response_headers)
print(f"Cacheable: {header_analysis.is_cacheable}")
print(f"Security headers: {header_analysis.has_security_headers}")

# Detect content type
content_type = detect_content_type(headers, content_bytes)
```

#### Caching
```python
from web_fetch import fetch_with_cache, CacheConfig

cache_config = CacheConfig(
    max_size=100,              # Max 100 entries
    ttl_seconds=300,           # 5 minute TTL
    enable_compression=True    # Compress cached data
)

result = await fetch_with_cache(url, cache_config=cache_config)
```

#### Rate Limiting
```python
from web_fetch import RateLimiter, RateLimitConfig

rate_config = RateLimitConfig(
    requests_per_second=10.0,  # 10 requests per second
    burst_size=20,             # Allow bursts up to 20
    per_host=True              # Separate limits per host
)

limiter = RateLimiter(rate_config)
await limiter.acquire(url)  # Wait for permission to make request
```

### Content Types

- `ContentType.TEXT`: Parse as UTF-8 text
- `ContentType.JSON`: Parse as JSON object
- `ContentType.HTML`: Parse HTML and extract structured data
- `ContentType.RAW`: Return raw bytes

### Exception Hierarchy

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
└── ContentError
```

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=web_fetch

# Run specific test file
pytest tests/test_fetcher.py

# Run with verbose output
pytest -v
```

### Test Categories

- **Unit tests**: Test individual components and functions
- **Integration tests**: Test with real HTTP requests (marked as `@pytest.mark.integration`)
- **Error scenario tests**: Test various failure modes and error handling

## 📁 Project Structure

```
web-fetch/
├── web_fetch/                    # Main package
│   ├── __init__.py              # Package exports and public API
│   ├── fetcher.py               # Main fetcher interface
│   ├── exceptions.py            # Exception hierarchy
│   ├── models/                  # Data models and configuration
│   │   ├── base.py             # Base models and enums
│   │   ├── http.py             # HTTP-specific models
│   │   └── ftp.py              # FTP-specific models
│   ├── src/                     # Core HTTP implementation
│   │   ├── core_fetcher.py     # Main HTTP fetcher
│   │   ├── streaming_fetcher.py # Streaming functionality
│   │   ├── convenience.py      # Convenience functions
│   │   └── url_utils.py        # URL utilities
│   ├── ftp/                     # FTP functionality
│   │   ├── fetcher.py          # FTP client
│   │   ├── connection.py       # Connection management
│   │   ├── operations.py       # File operations
│   │   ├── streaming.py        # Streaming downloads
│   │   ├── parallel.py         # Parallel downloads
│   │   └── verification.py     # File verification
│   ├── utils/                   # Utility modules
│   │   ├── cache.py            # Caching implementations
│   │   ├── rate_limit.py       # Rate limiting
│   │   ├── circuit_breaker.py  # Circuit breaker pattern
│   │   ├── deduplication.py    # Request deduplication
│   │   ├── transformers.py     # Response transformers
│   │   ├── metrics.py          # Metrics collection
│   │   └── validation.py       # Input validation
│   ├── parsers/                 # Content parsers
│   │   ├── content_parser.py   # Main parser interface
│   │   ├── pdf_parser.py       # PDF parsing
│   │   ├── image_parser.py     # Image processing
│   │   ├── feed_parser.py      # RSS/Atom feeds
│   │   └── csv_parser.py       # CSV parsing
│   ├── crawlers/                # Crawler integrations
│   │   ├── base.py             # Base crawler classes
│   │   ├── manager.py          # Crawler management
│   │   ├── firecrawl_crawler.py # Firecrawl integration
│   │   ├── spider_crawler.py   # Spider.cloud integration
│   │   └── tavily_crawler.py   # Tavily integration
│   └── cli/                     # Command-line interface
│       └── main.py             # CLI implementation
├── tests/                       # Comprehensive test suite
│   ├── test_fetcher.py         # Core fetcher tests
│   ├── test_ftp.py             # FTP functionality tests
│   ├── test_models.py          # Data model tests
│   ├── test_streaming.py       # Streaming tests
│   ├── test_utils.py           # Utility tests
│   ├── test_crawlers.py        # Crawler tests
│   ├── integration/            # Integration tests
│   ├── performance/            # Performance benchmarks
│   └── fixtures/               # Test data and mocks
├── docs/                        # Comprehensive documentation
│   ├── API.md                  # Complete API reference
│   ├── CONFIGURATION.md        # Configuration guide
│   ├── ADVANCED_EXAMPLES.md    # Advanced usage examples
│   ├── DEVELOPMENT.md          # Development guide
│   ├── CRAWLER_APIS.md         # Crawler API documentation
│   └── EXAMPLES.md             # Basic usage examples
├── examples/                    # Usage examples
│   ├── basic_usage.py          # Basic HTTP operations
│   ├── advanced_usage.py       # Advanced features
│   ├── ftp_examples.py         # FTP operations
│   ├── crawler_examples.py     # Crawler integrations
│   └── streaming_examples.py   # Streaming downloads
├── scripts/                     # Development scripts
│   └── setup-dev.sh           # Development environment setup
├── pyproject.toml              # Project configuration
├── pytest.ini                 # Test configuration
├── CHANGELOG.md                # Release notes
├── CONTRIBUTING.md             # Contribution guidelines
└── README.md                   # This file
```

## 📖 Documentation Overview

### For Users

- **[Quick Start](#-quick-start)** - Get up and running in minutes
- **[Comprehensive Examples Guide](docs/COMPREHENSIVE_EXAMPLES_GUIDE.md)** - Complete guide to all examples
- **[API Reference](docs/API.md)** - Complete API documentation with examples
- **[Configuration Guide](docs/CONFIGURATION.md)** - Environment variables and config files
- **[Advanced Examples](docs/ADVANCED_EXAMPLES.md)** - FTP, crawlers, streaming, caching
- **[Examples Collection](docs/EXAMPLES.md)** - Comprehensive usage patterns

#### Specialized Guides
- **[CLI Examples](docs/CLI_EXAMPLES.md)** - Complete command-line interface usage
- **[Parser Examples](docs/PARSER_EXAMPLES.md)** - Content parsing and data extraction
- **[Configuration Examples](docs/CONFIGURATION_EXAMPLES.md)** - Configuration patterns and best practices
- **[Error Handling Examples](docs/ERROR_HANDLING_EXAMPLES.md)** - Error handling and resilience patterns

#### Example Scripts
- **[Basic Usage](examples/basic_usage.py)** - Simple examples for beginners
- **[Advanced Usage](examples/advanced_usage.py)** - Complex patterns and features
- **[CLI Examples](examples/cli_comprehensive_examples.py)** - Complete CLI usage demonstrations
- **[Parser Examples](examples/parser_examples.py)** - Content parsing and extraction examples
- **[Configuration Examples](examples/configuration_examples.py)** - Configuration patterns and validation
- **[Error Handling Examples](examples/error_handling_examples.py)** - Error handling strategies
- **[Real-World Integration](examples/real_world_integration_examples.py)** - Production use cases
- **[Testing Examples](examples/testing_examples.py)** - Testing strategies and patterns
- **[Performance Optimization](examples/performance_optimization_examples.py)** - Performance tuning and optimization

### For Developers

- **[Development Guide](docs/DEVELOPMENT.md)** - Setup, testing, and contributing
- **[Architecture Overview](docs/DEVELOPMENT.md#architecture-overview)** - Design principles and structure
- **[Contributing Guidelines](docs/DEVELOPMENT.md#contributing-guidelines)** - How to contribute
- **[Testing Guide](docs/DEVELOPMENT.md#testing)** - Running and writing tests

## 🔧 Configuration Examples

### Retry Strategies

```python
from web_fetch import FetchConfig, RetryStrategy

# Exponential backoff (default)
config = FetchConfig(
    retry_strategy=RetryStrategy.EXPONENTIAL,
    max_retries=3,
    retry_delay=1.0  # 1s, 2s, 4s delays
)

# Linear backoff
config = FetchConfig(
    retry_strategy=RetryStrategy.LINEAR,
    max_retries=3,
    retry_delay=1.0  # 1s, 2s, 3s delays
)

# No retries
config = FetchConfig(
    retry_strategy=RetryStrategy.NONE,
    max_retries=0
)
```

### Custom Headers

```python
from web_fetch import RequestHeaders, FetchConfig

# Default headers with custom additions
headers = RequestHeaders(
    user_agent="MyApp/1.0",
    custom_headers={
        "Authorization": "Bearer token",
        "X-API-Key": "secret-key"
    }
)

config = FetchConfig(headers=headers)
```

## 🚀 Performance Tips

1. **Use batch fetching** for multiple URLs to leverage concurrency
2. **Adjust concurrent request limits** based on target server capacity
3. **Configure appropriate timeouts** for your use case
4. **Use connection pooling** by reusing WebFetcher instances
5. **Choose appropriate content types** to avoid unnecessary parsing
6. **Set response size limits** to prevent memory issues

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Built with [AIOHTTP](https://docs.aiohttp.org/) for async HTTP handling
- Uses [Pydantic](https://pydantic-docs.helpmanual.io/) for data validation
- HTML parsing powered by [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/)
- Inspired by modern Python async patterns and best practices