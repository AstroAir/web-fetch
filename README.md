# WebFetch - Comprehensive Web Content Fetching Library

A powerful, production-ready web fetching library with advanced features including authentication, caching, batch operations, file handling, and extensive HTTP support. Built with modern Python 3.11+ features and AIOHTTP for efficient asynchronous operations.

> 📚 **[Complete Documentation](https://astroair.github.io/web-fetch/)** | 🚀 **[Quick Start Guide](docs/getting-started/quick-start.md)** | 📖 **[API Reference](docs/api/core.md)**

## ✨ Key Features

- **🚀 Async/Await**: Modern Python async patterns with AIOHTTP
- **📦 Batch Operations**: Concurrent fetching with intelligent scheduling
- **🔄 Streaming**: Memory-efficient downloads with progress tracking
- **🔐 Authentication**: OAuth, API keys, JWT, and more
- **🕷️ Web Crawling**: Integrated crawler APIs (Firecrawl, Tavily, Spider)
- **💾 Caching**: Multiple backends with TTL and compression
- **🎨 Rich CLI**: Beautiful command-line interface with progress bars
- **🔧 MCP Integration**: Model Context Protocol server support
- **📊 Content Parsing**: JSON, HTML, PDF, images, RSS feeds
- **⚡ High Performance**: Connection pooling, rate limiting, circuit breakers

## 📦 Installation

```bash
# Basic installation
pip install web-fetch

# With all features
pip install "web-fetch[all-crawlers,mcp,caching]"

# From source
git clone https://github.com/AstroAir/web-fetch.git
cd web-fetch
pip install -e ".[all]"
```

> 📋 **[Complete Installation Guide](docs/getting-started/installation.md)** - Detailed installation instructions and troubleshooting

## 🔧 Quick Start

### Simple Usage

```python
import asyncio
from web_fetch import fetch_url, ContentType

async def main():
    # Fetch JSON data
    result = await fetch_url("https://httpbin.org/json", ContentType.JSON)
    if result.is_success:
        print(f"Status: {result.status_code}")
        print(f"Content: {result.content}")

asyncio.run(main())
```

### Batch Fetching

```python
from web_fetch import fetch_urls, ContentType

async def main():
    urls = ["https://httpbin.org/get", "https://httpbin.org/json"]
    result = await fetch_urls(urls, ContentType.JSON)
    print(f"Success rate: {result.success_rate:.1f}%")

asyncio.run(main())
```

### File Downloads

```python
from web_fetch import download_file
from pathlib import Path

async def main():
    result = await download_file(
        "https://httpbin.org/bytes/1048576",
        Path("downloads/file.bin")
    )
    print(f"Downloaded {result.bytes_downloaded:,} bytes")

asyncio.run(main())
```

> 🚀 **[More Examples](docs/getting-started/basic-examples.md)** - Comprehensive usage examples and patterns

## 🖥️ Command Line Interface

WebFetch includes a powerful CLI with enhanced formatting:

```bash
# Simple URL fetch
web-fetch https://httpbin.org/json

# Batch fetch from file
web-fetch --batch urls.txt --concurrent 5

# POST request with data
web-fetch --method POST --data '{"key":"value"}' https://httpbin.org/post

# Streaming download with progress
web-fetch --stream --progress https://example.com/file.zip -o file.zip
```

### Enhanced Features

- 🎨 **Colored Output** - Success (green), errors (red), warnings (yellow)
- 📊 **Progress Bars** - Visual progress for downloads and batch operations
- 📋 **Formatted Tables** - Beautiful structured data display
- 🔄 **Graceful Fallbacks** - Works with or without rich library

```bash
# Install for enhanced formatting
pip install rich>=13.0.0
```

> 🖥️ **[Complete CLI Guide](docs/cli/overview.md)** - All CLI options and examples

## 📚 Documentation

### Complete Documentation

- 📖 **[API Reference](docs/api/core.md)** - Complete API documentation
- ⚙️ **[Configuration Guide](docs/user-guide/configuration.md)** - Setup and configuration
- 🚀 **[Getting Started](docs/getting-started/quick-start.md)** - Quick start guide
- 💡 **[Examples](docs/examples/basic.md)** - Usage examples and patterns
- 🖥️ **[CLI Tools](docs/cli/overview.md)** - Command-line interface
- 🔧 **[Development](docs/development/contributing.md)** - Contributing and development

### Quick API Overview

```python
# Core classes
from web_fetch import WebFetcher, FetchConfig, FetchRequest, ContentType

# Configuration
config = FetchConfig(
    total_timeout=30.0,
    max_concurrent_requests=10,
    max_retries=3
)

# Request
request = FetchRequest(
    url="https://api.example.com",
    method="POST",
    headers={"Authorization": "Bearer token"},
    data={"key": "value"},
    content_type=ContentType.JSON
)

# Fetch
async with WebFetcher(config) as fetcher:
    result = await fetcher.fetch_single(request)
    if result.is_success:
        print(result.content)
```

### Content Types & Utilities

- `ContentType.TEXT` - UTF-8 text
- `ContentType.JSON` - JSON objects
- `ContentType.HTML` - Parsed HTML with structured data
- `ContentType.RAW` - Raw bytes

```python
# URL utilities
from web_fetch import is_valid_url, normalize_url, fetch_with_cache

# Validation and normalization
if is_valid_url(url):
    normalized = normalize_url(url)

# Caching
result = await fetch_with_cache(url)  # Automatic caching
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=web_fetch

# Run specific tests
pytest tests/test_fetcher.py -v
```

> 🧪 **[Testing Guide](docs/development/testing.md)** - Complete testing documentation

## 📁 Project Structure

```text
web-fetch/
├── web_fetch/           # Main package
│   ├── core/           # Core HTTP implementation
│   ├── ftp/            # FTP functionality
│   ├── crawlers/       # Crawler integrations
│   ├── parsers/        # Content parsers
│   ├── utils/          # Utilities and helpers
│   └── cli/            # Command-line interface
├── tests/              # Comprehensive test suite
├── docs/               # Documentation (MkDocs)
├── examples/           # Usage examples
└── scripts/            # Development scripts
```

> 🏗️ **[Architecture Guide](docs/development/architecture.md)** - Detailed architecture overview

## 🚀 Performance & Best Practices

- **Use batch fetching** for multiple URLs to leverage concurrency
- **Configure appropriate timeouts** for your use case
- **Use connection pooling** by reusing WebFetcher instances
- **Set response size limits** to prevent memory issues
- **Choose appropriate content types** to avoid unnecessary parsing

> ⚡ **[Performance Guide](docs/advanced/performance.md)** - Detailed optimization strategies

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](docs/development/contributing.md) for details.

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [AIOHTTP](https://docs.aiohttp.org/) for async HTTP handling
- Uses [Pydantic](https://pydantic-docs.helpmanual.io/) for data validation
- HTML parsing powered by [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/)
- Inspired by modern Python async patterns and best practices

---

**[📚 Full Documentation](https://astroair.github.io/web-fetch/)** | **[🐛 Report Issues](https://github.com/AstroAir/web-fetch/issues)** | **[💬 Discussions](https://github.com/AstroAir/web-fetch/discussions)**
