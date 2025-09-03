# WebFetch - Comprehensive Web Content Fetching Library

A powerful, production-ready web fetching library with advanced features including authentication, caching, batch operations, file handling, and extensive HTTP support. Built with modern Python 3.11+ features and AIOHTTP for efficient asynchronous operations.

## 🚀 Key Features

### Modern Python Capabilities
- **Async/await syntax** for concurrent request handling
- **Type hints** with Union types and Optional for better code safety
- **Context managers** for proper resource cleanup
- **Dataclasses and Pydantic models** for structured data handling
- **Comprehensive error handling** with custom exception hierarchy

### Advanced HTTP Support
- **Complete HTTP Methods**: Support for all HTTP methods including PATCH and TRACE
- **File Upload/Download**: Multipart uploads, resumable downloads with integrity verification
- **Advanced Pagination**: Automatic handling of offset/limit, page/size, cursor, and link header pagination
- **Header Management**: Intelligent header management with presets and domain-specific rules
- **Cookie Management**: Persistent cookie storage with security features

### Streaming Capabilities
- **Memory-efficient streaming** for large files and continuous data
- **Chunked reading** with configurable chunk sizes
- **Progress tracking** with real-time callbacks
- **Async file I/O** using aiofiles for non-blocking operations
- **Download resumption** and file size limits

### Content Processing
- **Multiple content types**: JSON, HTML, text, raw bytes
- **HTML parsing** with BeautifulSoup integration
- **Automatic encoding detection** for text content
- **Structured HTML data extraction** (title, links, images, text)

### Enhanced Features
- **Priority Queue System**: Intelligent batch scheduling with priority levels
- **Resource Management**: Configurable concurrency limits and memory management
- **Progress Tracking**: Real-time progress monitoring with callbacks and metrics
- **Configuration & Logging**: Centralized configuration with validation and structured logging
- **MCP Integration**: Comprehensive Model Context Protocol server support

## 📦 Quick Installation

=== "Using pip"

    ```bash
    pip install web-fetch
    ```

=== "From source"

    ```bash
    git clone https://github.com/AstroAir/web-fetch.git
    cd web-fetch
    pip install -e .
    ```

=== "With all features"

    ```bash
    pip install web-fetch[all-crawlers,mcp,caching]
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
    result = await download_file(
        url="https://httpbin.org/bytes/1048576",  # 1MB test file
        output_path=Path("downloads/large_file.bin"),
        chunk_size=8192,
        progress_callback=progress_callback
    )

    if result.is_success:
        print(f"Downloaded {result.bytes_downloaded:,} bytes")

asyncio.run(main())
```

## 🖥️ Command Line Interface

WebFetch includes a powerful CLI for quick web fetching:

```bash
# Simple URL fetch
web-fetch https://httpbin.org/json

# Fetch as JSON with custom timeout
web-fetch -t json --timeout 30 https://httpbin.org/json

# Batch fetch from file
web-fetch --batch urls.txt --concurrent 5

# POST request with data
web-fetch --method POST --data '{"key":"value"}' https://httpbin.org/post
```

!!! tip "Enhanced CLI"
    The CLI includes rich formatting with colors, progress bars, and tables. Install with `pip install rich>=13.0.0` for the best experience.

## 📚 Documentation Structure

### For Users
- **[Getting Started](getting-started/installation.md)** - Installation and quick start
- **[User Guide](user-guide/configuration.md)** - Core concepts and configuration
- **[API Reference](api/core.md)** - Complete API documentation
- **[Examples](examples/basic.md)** - Comprehensive usage examples

### For Developers
- **[Development Guide](development/contributing.md)** - Setup, testing, and contributing
- **[Architecture](development/architecture.md)** - Design principles and structure

### Advanced Topics
- **[Streaming](advanced/streaming.md)** - Large file handling and streaming
- **[Authentication](advanced/authentication.md)** - OAuth, API keys, and more
- **[Crawlers](advanced/crawlers.md)** - Web scraping integrations
- **[MCP Integration](mcp/overview.md)** - Model Context Protocol support

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](development/contributing.md) for details on how to get started.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/AstroAir/web-fetch/blob/master/LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [AIOHTTP](https://docs.aiohttp.org/) for async HTTP handling
- Uses [Pydantic](https://pydantic-docs.helpmanual.io/) for data validation
- HTML parsing powered by [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/)
- Inspired by modern Python async patterns and best practices
