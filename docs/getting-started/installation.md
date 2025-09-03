# Installation

This guide covers all the ways to install WebFetch and its dependencies.

## Requirements

- Python 3.11 or higher
- pip or uv package manager

## Basic Installation

### Using pip

=== "Core package"

    ```bash
    pip install web-fetch
    ```

=== "With development tools"

    ```bash
    pip install web-fetch[dev]
    ```

=== "With all features"

    ```bash
    pip install web-fetch[all-crawlers,mcp,caching]
    ```

### Using uv (Recommended)

[uv](https://github.com/astral-sh/uv) is a fast Python package installer and resolver.

```bash
# Install uv first
pip install uv

# Install web-fetch
uv add web-fetch

# Or with all features
uv add "web-fetch[all-crawlers,mcp,caching]"
```

## Installation from Source

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/AstroAir/web-fetch.git
cd web-fetch

# Install with uv (recommended)
uv sync

# Or install with pip
pip install -e .

# Install with development dependencies
pip install -e ".[dev]"
```

### Using Requirements Files

```bash
# Install core dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

## Optional Dependencies

WebFetch supports several optional feature sets:

### Crawler Integrations

```bash
pip install web-fetch[all-crawlers]
```

Includes:
- `firecrawl-py` - Firecrawl API integration
- `tavily-python` - Tavily search API integration

### MCP Server Support

```bash
pip install web-fetch[mcp]
```

Includes:
- `fastmcp` - Model Context Protocol server
- `websockets` - WebSocket support

### Enhanced Caching

```bash
pip install web-fetch[caching]
```

Includes:
- `redis` - Redis caching backend
- `diskcache` - Disk-based caching

### Rich CLI Interface

```bash
pip install rich>=13.0.0
```

Enables enhanced CLI formatting with:
- Colored output
- Progress bars
- Formatted tables
- Syntax highlighting

## Core Dependencies

WebFetch relies on these core packages:

### HTTP and Async
- `aiohttp` - Async HTTP client/server
- `aiofiles` - Async file operations

### Data Processing
- `pydantic` - Data validation and settings
- `beautifulsoup4` - HTML parsing
- `pypdf` - PDF processing (replaces deprecated PyPDF2)
- `Pillow` - Image processing
- `pandas` - Data analysis
- `feedparser` - RSS/Atom feed parsing

### Development Tools
- `pytest` - Testing framework
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting
- `black` - Code formatting
- `isort` - Import sorting
- `mypy` - Type checking

## Verification

After installation, verify that WebFetch is working correctly:

```python
import asyncio
from web_fetch import fetch_url, ContentType

async def test_installation():
    result = await fetch_url("https://httpbin.org/json", ContentType.JSON)
    if result.is_success:
        print("✅ WebFetch installed successfully!")
        print(f"Status: {result.status_code}")
    else:
        print("❌ Installation verification failed")
        print(f"Error: {result.error}")

# Run the test
asyncio.run(test_installation())
```

## CLI Verification

Test the command-line interface:

```bash
# Basic test
web-fetch https://httpbin.org/json

# Check version
web-fetch --version

# Get help
web-fetch --help
```

## Troubleshooting

### Common Issues

#### Import Errors

If you encounter import errors:

```bash
# Reinstall with all dependencies
pip install --force-reinstall web-fetch[all-crawlers,mcp,caching]
```

#### SSL Certificate Issues

On some systems, you might encounter SSL certificate issues:

```python
# Disable SSL verification (not recommended for production)
from web_fetch import FetchConfig

config = FetchConfig(verify_ssl=False)
```

#### Permission Errors

On Unix systems, you might need to use `sudo` or install in a virtual environment:

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install web-fetch
```

### Getting Help

If you encounter issues:

1. Check the [Troubleshooting Guide](../user-guide/error-handling.md)
2. Search [GitHub Issues](https://github.com/AstroAir/web-fetch/issues)
3. Create a new issue with:
   - Python version
   - Operating system
   - Installation method
   - Error messages

## Next Steps

After installation, continue with:

- [Quick Start Guide](quick-start.md) - Basic usage examples
- [Configuration](../user-guide/configuration.md) - Setting up WebFetch
- [Basic Examples](basic-examples.md) - Common use cases
