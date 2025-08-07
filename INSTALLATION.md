# Web Fetch - Installation and Setup Guide

## System Requirements

- Python 3.11 or higher
- Linux, macOS, or Windows
- Virtual environment (recommended)

## Quick Installation

### Using pip (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd web-fetch

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package
pip install -e .

# Or install with all optional dependencies
pip install -e ".[all]"
```

### Using uv (Faster)

```bash
# Install uv if you don't have it
pip install uv

# Clone and setup
git clone <repository-url>
cd web-fetch

# Install with uv
uv sync

# Activate environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

## Core Dependencies

The following dependencies are automatically installed:

### Required
- `aiohttp>=3.9.0` - Async HTTP client
- `pydantic>=2.0.0` - Data validation and settings
- `beautifulsoup4>=4.12.0` - HTML parsing
- `lxml>=4.9.0` - XML/HTML parser
- `aiofiles>=23.0.0` - Async file operations
- `aioftp>=0.21.0` - Async FTP client

### Content Processing
- `PyPDF2>=3.0.0` - PDF parsing
- `Pillow>=10.0.0` - Image processing
- `feedparser>=6.0.0` - RSS/Atom feed parsing
- `pandas>=2.0.0` - CSV and data handling
- `html2text>=2020.1.16` - HTML to Markdown conversion
- `python-magic>=0.4.27` - Content type detection
- `nltk>=3.8.0` - Text processing
- `scikit-learn>=1.3.0` - Text analysis

### Optional Dependencies

#### Crawler Services
```bash
# For Firecrawl support
pip install firecrawl-py

# For Tavily support  
pip install tavily-python

# For Playwright support (JavaScript rendering)
pip install playwright
playwright install
```

#### Advanced Caching
```bash
# For Redis caching
pip install aioredis

# For file system caching (included by default)
# No additional packages needed
```

#### Development Tools
```bash
# Testing
pip install pytest pytest-asyncio pytest-cov pytest-mock

# Linting and formatting
pip install black flake8 mypy

# Documentation
pip install sphinx sphinx-rtd-theme
```

## Environment Configuration

### Basic Configuration

Create a `.env` file in your project root:

```env
# Basic settings
WEB_FETCH_TIMEOUT=30
WEB_FETCH_MAX_RETRIES=3
WEB_FETCH_USER_AGENT="WebFetch/0.1.0"

# Cache settings
WEB_FETCH_CACHE_TTL=3600
WEB_FETCH_CACHE_MAX_SIZE=1000
WEB_FETCH_CACHE_BACKEND=memory

# Rate limiting
WEB_FETCH_RATE_LIMIT_REQUESTS=100
WEB_FETCH_RATE_LIMIT_PERIOD=60
```

### Advanced Configuration

```env
# Authentication
WEB_FETCH_API_KEY=your-api-key
WEB_FETCH_OAUTH_CLIENT_ID=your-client-id
WEB_FETCH_OAUTH_CLIENT_SECRET=your-client-secret

# Crawler services
FIRECRAWL_API_KEY=your-firecrawl-key
TAVILY_API_KEY=your-tavily-key

# Redis cache (optional)
WEB_FETCH_REDIS_URL=redis://localhost:6379
WEB_FETCH_REDIS_PREFIX=web_fetch:

# File cache (optional)
WEB_FETCH_CACHE_DIR=/tmp/web_fetch_cache

# FTP settings
WEB_FETCH_FTP_USERNAME=anonymous
WEB_FETCH_FTP_PASSWORD=guest@example.com
WEB_FETCH_FTP_MODE=passive
```

## Verification

Test your installation:

```python
import asyncio
from web_fetch import fetch_url, ContentType

async def test():
    result = await fetch_url("https://httpbin.org/json", ContentType.JSON)
    print(f"Status: {result.status_code}")
    print(f"Success: {result.is_success}")
    print(f"Content: {result.content}")

asyncio.run(test())
```

## Docker Installation

### Using Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libmagic1 \
    libmagic-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application
COPY . .
RUN pip install -e .

CMD ["python", "-m", "web_fetch"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  web-fetch:
    build: .
    environment:
      - WEB_FETCH_REDIS_URL=redis://redis:6379
    depends_on:
      - redis
    volumes:
      - ./cache:/tmp/web_fetch_cache

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Ensure virtual environment is activated
   source venv/bin/activate
   
   # Reinstall dependencies
   pip install -e ".[all]"
   ```

2. **SSL Certificate Errors**
   ```python
   # Use verify_ssl=False for development
   config = FetchConfig(verify_ssl=False)
   ```

3. **Rate Limiting Issues**
   ```python
   # Increase timeout and retries
   config = FetchConfig(
       timeout=60,
       max_retries=5,
       retry_delay=2.0
   )
   ```

4. **Memory Issues with Large Files**
   ```python
   # Use streaming for large files
   from web_fetch import StreamingWebFetcher
   
   async with StreamingWebFetcher() as fetcher:
       async for chunk in fetcher.stream_download(url):
           # Process chunk
           pass
   ```

### Platform-Specific Notes

#### Windows
```cmd
# Use Windows paths for cache directory
set WEB_FETCH_CACHE_DIR=C:\temp\web_fetch_cache

# May need to install Visual C++ Build Tools for some dependencies
```

#### macOS
```bash
# May need to install libmagic
brew install libmagic

# For ARM Macs, ensure compatibility
export ARCHFLAGS="-arch arm64"
```

#### Linux
```bash
# Install libmagic development headers
sudo apt-get install libmagic-dev  # Ubuntu/Debian
sudo yum install file-devel        # CentOS/RHEL
```

## Performance Optimization

### Connection Pooling

```python
from web_fetch import FetchConfig

config = FetchConfig(
    max_connections=100,
    max_connections_per_host=30,
    connection_timeout=30,
    dns_cache_ttl=300
)
```

### Caching Strategy

```python
from web_fetch.utils import EnhancedCacheConfig, CacheBackend

# Memory cache for development
cache_config = EnhancedCacheConfig(
    backend=CacheBackend.MEMORY,
    max_size=1000,
    default_ttl=3600
)

# Redis cache for production
cache_config = EnhancedCacheConfig(
    backend=CacheBackend.REDIS,
    redis_url="redis://localhost:6379",
    default_ttl=3600
)
```

### Concurrent Requests

```python
from web_fetch import fetch_urls

# Batch processing with concurrency control
urls = ["url1", "url2", "url3"]
results = await fetch_urls(
    urls,
    max_concurrent=10,
    timeout=30
)
```

## Next Steps

- Check out the [Examples Guide](EXAMPLES.md) for usage patterns
- Read the [API Documentation](docs/API.md) for detailed reference
- See [Advanced Examples](docs/ADVANCED_EXAMPLES.md) for complex scenarios
- Browse [Configuration Guide](docs/CONFIGURATION.md) for all options

## Support

- **Documentation**: Check the `/docs` directory
- **Examples**: See the `/examples` directory  
- **Issues**: Report bugs and feature requests on GitHub
- **Discussions**: Community support and questions
