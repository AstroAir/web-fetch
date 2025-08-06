# Configuration Guide

This document provides comprehensive information about configuring the web-fetch library, including environment variables, configuration files, and setup requirements.

## Table of Contents

- [Environment Variables](#environment-variables)
- [Configuration Files](#configuration-files)
- [Setup Requirements](#setup-requirements)
- [Advanced Configuration](#advanced-configuration)
- [Performance Tuning](#performance-tuning)
- [Security Configuration](#security-configuration)

## Environment Variables

The web-fetch library supports various environment variables for configuration, especially useful for deployment and CI/CD environments.

### Core HTTP Configuration

```bash
# Timeout settings (in seconds)
WEB_FETCH_TOTAL_TIMEOUT=30.0
WEB_FETCH_CONNECT_TIMEOUT=10.0
WEB_FETCH_READ_TIMEOUT=20.0

# Concurrency settings
WEB_FETCH_MAX_CONCURRENT_REQUESTS=10
WEB_FETCH_MAX_CONNECTIONS_PER_HOST=5

# Retry configuration
WEB_FETCH_MAX_RETRIES=3
WEB_FETCH_RETRY_DELAY=1.0
WEB_FETCH_RETRY_STRATEGY=exponential  # exponential, linear, none

# Content and security
WEB_FETCH_MAX_RESPONSE_SIZE=10485760  # 10MB in bytes
WEB_FETCH_FOLLOW_REDIRECTS=true
WEB_FETCH_VERIFY_SSL=true

# Default headers
WEB_FETCH_USER_AGENT="web-fetch/0.1.0"
```

### FTP Configuration

```bash
# FTP connection settings
WEB_FETCH_FTP_CONNECTION_TIMEOUT=30.0
WEB_FETCH_FTP_DATA_TIMEOUT=300.0
WEB_FETCH_FTP_KEEPALIVE_INTERVAL=30.0

# FTP mode and transfer settings
WEB_FETCH_FTP_MODE=passive  # active, passive
WEB_FETCH_FTP_TRANSFER_MODE=binary  # binary, ascii

# FTP authentication
WEB_FETCH_FTP_AUTH_TYPE=anonymous  # anonymous, user_pass
WEB_FETCH_FTP_USERNAME=""
WEB_FETCH_FTP_PASSWORD=""

# FTP performance settings
WEB_FETCH_FTP_MAX_CONCURRENT_DOWNLOADS=3
WEB_FETCH_FTP_MAX_CONNECTIONS_PER_HOST=2
WEB_FETCH_FTP_ENABLE_PARALLEL_DOWNLOADS=false

# FTP file handling
WEB_FETCH_FTP_CHUNK_SIZE=8192
WEB_FETCH_FTP_BUFFER_SIZE=65536
WEB_FETCH_FTP_MAX_FILE_SIZE=""  # Empty means no limit

# FTP verification and resume
WEB_FETCH_FTP_VERIFICATION_METHOD=size  # size, md5, sha256, none
WEB_FETCH_FTP_ENABLE_RESUME=true

# FTP rate limiting
WEB_FETCH_FTP_RATE_LIMIT_BYTES_PER_SECOND=""  # Empty means no limit
```

### Crawler API Configuration

```bash
# Firecrawl API
FIRECRAWL_API_KEY="fc-your-api-key-here"
WEB_FETCH_FIRECRAWL_ENABLED=true

# Spider.cloud API
SPIDER_API_KEY="your-spider-api-key-here"
WEB_FETCH_SPIDER_ENABLED=true

# Tavily API
TAVILY_API_KEY="tvly-your-api-key-here"
WEB_FETCH_TAVILY_ENABLED=true

# AnyCrawl API
ANYCRAWL_API_KEY="your-anycrawl-api-key-here"
WEB_FETCH_ANYCRAWL_ENABLED=true

# Crawler preferences
WEB_FETCH_PRIMARY_CRAWLER=firecrawl  # firecrawl, spider, tavily, anycrawl
WEB_FETCH_FALLBACK_ORDER="spider,tavily,anycrawl"
WEB_FETCH_CRAWLER_TIMEOUT=60.0
WEB_FETCH_CRAWLER_MAX_RETRIES=3
```

### Advanced Features Configuration

```bash
# Circuit breaker settings
WEB_FETCH_CIRCUIT_BREAKER_ENABLED=false
WEB_FETCH_CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
WEB_FETCH_CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60.0
WEB_FETCH_CIRCUIT_BREAKER_SUCCESS_THRESHOLD=3

# Request deduplication
WEB_FETCH_ENABLE_DEDUPLICATION=false

# Metrics collection
WEB_FETCH_ENABLE_METRICS=false
WEB_FETCH_METRICS_EXPORT_INTERVAL=300  # seconds

# Enhanced caching
WEB_FETCH_CACHE_ENABLED=false
WEB_FETCH_CACHE_BACKEND=memory  # memory, redis, file
WEB_FETCH_CACHE_TTL_SECONDS=300
WEB_FETCH_CACHE_MAX_SIZE=1000
WEB_FETCH_CACHE_ENABLE_COMPRESSION=true

# Redis cache settings (when using redis backend)
WEB_FETCH_REDIS_HOST=localhost
WEB_FETCH_REDIS_PORT=6379
WEB_FETCH_REDIS_DB=0
WEB_FETCH_REDIS_PASSWORD=""

# File cache settings (when using file backend)
WEB_FETCH_FILE_CACHE_DIR="./cache"
WEB_FETCH_FILE_CACHE_MAX_SIZE_MB=100

# JavaScript rendering (Playwright)
WEB_FETCH_JS_RENDERING_ENABLED=false
WEB_FETCH_JS_RENDERING_TIMEOUT=30.0
WEB_FETCH_JS_RENDERING_WAIT_FOR_SELECTOR=""
WEB_FETCH_JS_RENDERING_VIEWPORT_WIDTH=1920
WEB_FETCH_JS_RENDERING_VIEWPORT_HEIGHT=1080
```

### Logging Configuration

```bash
# Logging levels
WEB_FETCH_LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
WEB_FETCH_LOG_FORMAT=json  # json, text
WEB_FETCH_LOG_FILE=""  # Empty means stdout only

# Component-specific logging
WEB_FETCH_HTTP_LOG_LEVEL=INFO
WEB_FETCH_FTP_LOG_LEVEL=INFO
WEB_FETCH_CRAWLER_LOG_LEVEL=INFO
WEB_FETCH_PARSER_LOG_LEVEL=INFO

# Request/response logging
WEB_FETCH_LOG_REQUESTS=false
WEB_FETCH_LOG_RESPONSES=false
WEB_FETCH_LOG_REQUEST_HEADERS=false
WEB_FETCH_LOG_RESPONSE_HEADERS=false
```

## Configuration Files

### pyproject.toml Configuration

You can configure web-fetch settings in your `pyproject.toml` file:

```toml
[tool.web-fetch]
# HTTP settings
total_timeout = 30.0
max_concurrent_requests = 10
max_retries = 3
verify_ssl = true

# FTP settings
ftp_connection_timeout = 30.0
ftp_max_concurrent_downloads = 3
ftp_enable_resume = true

# Crawler settings
primary_crawler = "firecrawl"
crawler_timeout = 60.0

# Advanced features
enable_metrics = false
enable_deduplication = false
cache_enabled = false
```

### JSON Configuration File

Create a `web-fetch-config.json` file for complex configurations:

```json
{
  "http": {
    "total_timeout": 30.0,
    "connect_timeout": 10.0,
    "read_timeout": 20.0,
    "max_concurrent_requests": 10,
    "max_connections_per_host": 5,
    "retry_strategy": "exponential",
    "max_retries": 3,
    "retry_delay": 1.0,
    "max_response_size": 10485760,
    "follow_redirects": true,
    "verify_ssl": true,
    "headers": {
      "User-Agent": "web-fetch/0.1.0",
      "Accept": "application/json, text/html, */*"
    }
  },
  "ftp": {
    "connection_timeout": 30.0,
    "data_timeout": 300.0,
    "mode": "passive",
    "transfer_mode": "binary",
    "max_concurrent_downloads": 3,
    "chunk_size": 8192,
    "enable_resume": true,
    "verification_method": "size"
  },
  "crawlers": {
    "primary": "firecrawl",
    "fallback_order": ["spider", "tavily", "anycrawl"],
    "timeout": 60.0,
    "max_retries": 3,
    "apis": {
      "firecrawl": {
        "enabled": true,
        "api_key": "${FIRECRAWL_API_KEY}"
      },
      "spider": {
        "enabled": true,
        "api_key": "${SPIDER_API_KEY}"
      }
    }
  },
  "advanced": {
    "circuit_breaker": {
      "enabled": false,
      "failure_threshold": 5,
      "recovery_timeout": 60.0
    },
    "cache": {
      "enabled": false,
      "backend": "memory",
      "ttl_seconds": 300,
      "max_size": 1000
    },
    "metrics": {
      "enabled": false,
      "export_interval": 300
    }
  }
}
```

### YAML Configuration File

Alternatively, use `web-fetch-config.yaml`:

```yaml
http:
  total_timeout: 30.0
  connect_timeout: 10.0
  read_timeout: 20.0
  max_concurrent_requests: 10
  max_connections_per_host: 5
  retry_strategy: exponential
  max_retries: 3
  retry_delay: 1.0
  max_response_size: 10485760
  follow_redirects: true
  verify_ssl: true
  headers:
    User-Agent: "web-fetch/0.1.0"
    Accept: "application/json, text/html, */*"

ftp:
  connection_timeout: 30.0
  data_timeout: 300.0
  mode: passive
  transfer_mode: binary
  max_concurrent_downloads: 3
  chunk_size: 8192
  enable_resume: true
  verification_method: size

crawlers:
  primary: firecrawl
  fallback_order:
    - spider
    - tavily
    - anycrawl
  timeout: 60.0
  max_retries: 3
  apis:
    firecrawl:
      enabled: true
      api_key: "${FIRECRAWL_API_KEY}"
    spider:
      enabled: true
      api_key: "${SPIDER_API_KEY}"

advanced:
  circuit_breaker:
    enabled: false
    failure_threshold: 5
    recovery_timeout: 60.0
  cache:
    enabled: false
    backend: memory
    ttl_seconds: 300
    max_size: 1000
  metrics:
    enabled: false
    export_interval: 300
```

## Setup Requirements

### System Requirements

- **Python**: 3.11 or higher
- **Operating System**: Linux, macOS, Windows
- **Memory**: Minimum 512MB RAM, recommended 2GB+ for heavy usage
- **Disk Space**: 100MB for installation, additional space for downloads and cache

### Required Dependencies

Core dependencies (automatically installed):

```bash
aiohttp>=3.9.0          # Async HTTP client
pydantic>=2.0.0         # Data validation
beautifulsoup4>=4.12.0  # HTML parsing
lxml>=4.9.0             # XML/HTML parser
aiofiles>=23.0.0        # Async file operations
aioftp>=0.21.0          # Async FTP client
```

### Optional Dependencies

For enhanced functionality:

```bash
# Content parsing
PyPDF2>=3.0.0           # PDF parsing
Pillow>=10.0.0          # Image processing
feedparser>=6.0.0       # RSS/Atom feeds
pandas>=2.0.0           # CSV parsing
html2text>=2020.1.16    # HTML to Markdown
python-magic>=0.4.27    # Content type detection
nltk>=3.8.0             # Text processing
scikit-learn>=1.3.0     # Text analysis

# JavaScript rendering
playwright>=1.40.0      # Browser automation

# Crawler APIs
firecrawl-py>=0.0.16    # Firecrawl SDK
tavily-python>=0.3.0    # Tavily SDK
requests>=2.31.0        # For Spider/AnyCrawl

# Caching backends
redis>=4.0.0            # Redis cache
diskcache>=5.0.0        # Disk cache

# Development tools
pytest>=7.0.0           # Testing
pytest-asyncio>=0.21.0  # Async testing
black>=23.0.0           # Code formatting
mypy>=1.5.0             # Type checking
```

### Installation Commands

```bash
# Basic installation
pip install web-fetch

# With all optional dependencies
pip install "web-fetch[all]"

# With specific feature sets
pip install "web-fetch[crawlers]"     # Crawler APIs
pip install "web-fetch[parsing]"      # Enhanced parsing
pip install "web-fetch[caching]"      # Advanced caching
pip install "web-fetch[dev]"          # Development tools

# From source
git clone https://github.com/web-fetch/web-fetch.git
cd web-fetch
pip install -e ".[all]"
```

## Advanced Configuration

### Configuration Loading Priority

The library loads configuration in the following order (later sources override earlier ones):

1. **Default values** - Built-in defaults
2. **Configuration files** - `web-fetch-config.yaml` or `web-fetch-config.json`
3. **pyproject.toml** - `[tool.web-fetch]` section
4. **Environment variables** - `WEB_FETCH_*` variables
5. **Runtime configuration** - Programmatic configuration objects

### Programmatic Configuration

```python
from web_fetch import FetchConfig, FTPConfig, CrawlerConfig
from web_fetch.utils import CircuitBreakerConfig, EnhancedCacheConfig

# HTTP configuration
http_config = FetchConfig(
    total_timeout=45.0,
    max_concurrent_requests=20,
    retry_strategy=RetryStrategy.LINEAR,
    headers=RequestHeaders(
        user_agent="MyApp/2.0",
        custom_headers={
            "X-API-Version": "v2",
            "Authorization": "Bearer ${API_TOKEN}"
        }
    )
)

# FTP configuration
ftp_config = FTPConfig(
    connection_timeout=60.0,
    auth_type=FTPAuthType.USER_PASS,
    username="${FTP_USERNAME}",
    password="${FTP_PASSWORD}",
    max_concurrent_downloads=5,
    enable_parallel_downloads=True,
    verification_method=FTPVerificationMethod.SHA256
)

# Circuit breaker configuration
circuit_breaker_config = CircuitBreakerConfig(
    failure_threshold=3,
    recovery_timeout=30.0,
    success_threshold=2,
    failure_exceptions=(ConnectionError, TimeoutError),
    failure_status_codes={500, 502, 503, 504}
)

# Enhanced cache configuration
cache_config = EnhancedCacheConfig(
    backend="redis",
    ttl_seconds=600,
    max_size=5000,
    enable_compression=True,
    redis_config={
        "host": "localhost",
        "port": 6379,
        "db": 1,
        "password": "${REDIS_PASSWORD}"
    }
)
```

### Configuration Validation

All configuration objects use Pydantic for validation:

```python
from web_fetch import FetchConfig
from pydantic import ValidationError

try:
    config = FetchConfig(
        total_timeout=-1.0,  # Invalid: must be positive
        max_concurrent_requests=200  # Invalid: exceeds maximum
    )
except ValidationError as e:
    print(f"Configuration error: {e}")
    # Handle validation errors appropriately
```

### Environment Variable Substitution

Configuration supports environment variable substitution using `${VAR_NAME}` syntax:

```yaml
# web-fetch-config.yaml
http:
  headers:
    Authorization: "Bearer ${API_TOKEN}"
    X-API-Key: "${API_KEY}"

ftp:
  username: "${FTP_USER}"
  password: "${FTP_PASS}"

crawlers:
  apis:
    firecrawl:
      api_key: "${FIRECRAWL_API_KEY}"
```

## Performance Tuning

### HTTP Performance Optimization

```python
# High-throughput configuration
high_perf_config = FetchConfig(
    # Aggressive timeouts for fast failure
    total_timeout=15.0,
    connect_timeout=5.0,
    read_timeout=10.0,

    # High concurrency
    max_concurrent_requests=50,
    max_connections_per_host=20,

    # Minimal retries for speed
    max_retries=1,
    retry_delay=0.5,
    retry_strategy=RetryStrategy.NONE,

    # Large response buffer
    max_response_size=100 * 1024 * 1024,  # 100MB

    # Optimized headers
    headers=RequestHeaders(
        user_agent="HighPerfFetcher/1.0",
        custom_headers={
            "Connection": "keep-alive",
            "Accept-Encoding": "gzip, deflate",
            "Cache-Control": "no-cache"
        }
    )
)
```

### FTP Performance Optimization

```python
# High-speed FTP configuration
fast_ftp_config = FTPConfig(
    # Aggressive timeouts
    connection_timeout=15.0,
    data_timeout=120.0,

    # Maximum concurrency
    max_concurrent_downloads=10,
    max_connections_per_host=5,
    enable_parallel_downloads=True,

    # Large buffers
    chunk_size=64 * 1024,  # 64KB
    buffer_size=256 * 1024,  # 256KB

    # Minimal verification for speed
    verification_method=FTPVerificationMethod.SIZE,

    # No rate limiting
    rate_limit_bytes_per_second=None
)
```

### Memory Optimization

```python
# Memory-efficient configuration
memory_config = FetchConfig(
    # Conservative concurrency
    max_concurrent_requests=5,
    max_connections_per_host=2,

    # Small response limit
    max_response_size=10 * 1024 * 1024,  # 10MB

    # Streaming for large content
    streaming_config=StreamingConfig(
        chunk_size=4096,  # 4KB chunks
        enable_progress=False,  # Disable progress tracking
        max_file_size=50 * 1024 * 1024  # 50MB limit
    )
)
```

## Security Configuration

### SSL/TLS Configuration

```python
# Secure configuration
secure_config = FetchConfig(
    # Strict SSL verification
    verify_ssl=True,

    # Security headers
    headers=RequestHeaders(
        custom_headers={
            "Strict-Transport-Security": "max-age=31536000",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block"
        }
    )
)
```

### Credential Management

```python
import os
from web_fetch import FTPConfig, CrawlerConfig

# Secure credential loading
ftp_config = FTPConfig(
    username=os.getenv("FTP_USERNAME"),
    password=os.getenv("FTP_PASSWORD"),
    # Never hardcode credentials in source code
)

# API key management
crawler_config = CrawlerConfig(
    api_key=os.getenv("CRAWLER_API_KEY"),
    # Use environment variables or secure vaults
)
```

### Network Security

```python
# Network-restricted configuration
restricted_config = FetchConfig(
    # Disable redirects to prevent SSRF
    follow_redirects=False,

    # Strict timeouts to prevent DoS
    total_timeout=10.0,
    connect_timeout=3.0,

    # Limited response size
    max_response_size=1 * 1024 * 1024,  # 1MB

    # Conservative concurrency
    max_concurrent_requests=3
)
```

### Proxy Configuration

```python
# Proxy configuration for security/privacy
proxy_config = FetchConfig(
    headers=RequestHeaders(
        custom_headers={
            "Proxy-Authorization": "Basic ${PROXY_AUTH}",
        }
    )
)

# Configure proxy at session level
import aiohttp

connector = aiohttp.TCPConnector(
    limit=10,
    limit_per_host=5
)

# Use with custom session configuration
```

This comprehensive configuration guide covers all aspects of setting up and tuning the web-fetch library for various use cases, from development to production deployment.
