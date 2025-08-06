# WebFetch MCP Server

An MCP (Model Context Protocol) server implementation that exposes WebFetch functionality as tools for LLM consumption using the FastMCP framework.

## Overview

This MCP server provides comprehensive web fetching capabilities for LLMs, including:

- **Single URL fetching** with various content types and parsing options
- **Batch URL fetching** for concurrent processing of multiple URLs
- **Enhanced fetching** with advanced features like caching, circuit breakers, and retry logic
- **URL validation and analysis** for checking URL structure and properties
- **HTTP header analysis** for extracting metadata and insights
- **Content type detection** from URLs, headers, and content

## Available Tools

### 1. `web_fetch`
Fetch content from a single URL with configurable parsing and timeout options.

**Parameters:**
- `url` (string): The URL to fetch content from
- `content_type` (enum): How to parse the response content (TEXT, JSON, HTML, RAW)
- `timeout` (float): Request timeout in seconds (1-300)
- `max_retries` (int): Maximum number of retry attempts (0-10)
- `follow_redirects` (bool): Whether to follow HTTP redirects
- `verify_ssl` (bool): Whether to verify SSL certificates

### 2. `web_fetch_batch`
Fetch content from multiple URLs concurrently with shared configuration.

**Parameters:**
- `urls` (array): List of URLs to fetch concurrently (1-20 URLs)
- `content_type` (enum): How to parse the response content for all URLs
- `timeout` (float): Request timeout in seconds for each URL
- `max_retries` (int): Maximum number of retry attempts per URL
- `max_concurrent` (int): Maximum number of concurrent requests (1-20)
- `follow_redirects` (bool): Whether to follow HTTP redirects
- `verify_ssl` (bool): Whether to verify SSL certificates

### 3. `web_fetch_enhanced`
Advanced web fetching with caching, circuit breakers, deduplication, and more features.

**Parameters:**
- `url` (string): The URL to fetch content from
- `method` (enum): HTTP method to use (GET, POST, PUT, DELETE, HEAD, OPTIONS)
- `headers` (object): Custom HTTP headers to send with the request
- `data` (string/object): Request body data (for POST/PUT requests)
- `params` (object): URL query parameters
- `content_type` (enum): How to parse the response content
- `timeout` (float): Request timeout in seconds
- `max_retries` (int): Maximum number of retry attempts
- `follow_redirects` (bool): Whether to follow HTTP redirects
- `verify_ssl` (bool): Whether to verify SSL certificates
- `enable_caching` (bool): Enable response caching
- `cache_ttl` (int): Cache TTL in seconds (60-3600)
- `enable_circuit_breaker` (bool): Enable circuit breaker for fault tolerance
- `enable_deduplication` (bool): Enable request deduplication
- `enable_metrics` (bool): Enable metrics collection

### 4. `validate_url`
Validate and analyze URL structure and properties.

**Parameters:**
- `url` (string): The URL to validate and analyze

### 5. `analyze_headers`
Analyze HTTP response headers for insights and metadata.

**Parameters:**
- `headers` (object): HTTP headers to analyze (key-value pairs)

### 6. `detect_content_type`
Detect content type from URL, headers, or content.

**Parameters:**
- `url` (string, optional): URL to analyze for content type hints
- `headers` (object, optional): HTTP headers containing content-type information
- `content_sample` (string, optional): Sample of content to analyze

## Installation

1. Ensure you have the WebFetch library installed:
```bash
pip install -r requirements.txt
```

2. Install FastMCP:
```bash
pip install fastmcp
```

## Usage

### Running the Server

#### STDIO Transport (Default)
```bash
python run_mcp_server.py
```

#### HTTP Transport
```bash
python run_mcp_server.py --transport http --host 127.0.0.1 --port 8080
```

#### With Debug Logging
```bash
python run_mcp_server.py --log-level DEBUG
```

### Using as a Module
```bash
python -m mcp_server
```

### Programmatic Usage
```python
from mcp_server import create_mcp_server

# Create the server
mcp = create_mcp_server()

# Run with STDIO transport
mcp.run()

# Or run with HTTP transport
mcp.run(transport="http", host="127.0.0.1", port=8080)
```

## Configuration

The server uses the underlying WebFetch library configuration. You can customize:

- **Timeouts**: Request, connect, and read timeouts
- **Retry Logic**: Maximum retries, retry delays, and strategies
- **Concurrency**: Maximum concurrent requests and connections
- **SSL/TLS**: Certificate verification and custom SSL contexts
- **Caching**: Memory, file, or Redis-based caching
- **Circuit Breakers**: Failure thresholds and recovery timeouts

## Error Handling

The server provides comprehensive error handling:

- **Network Errors**: Connection failures, timeouts, DNS resolution issues
- **HTTP Errors**: Status code errors, redirect loops, authentication failures
- **Content Errors**: Parsing failures, encoding issues, malformed content
- **Validation Errors**: Invalid URLs, malformed headers, parameter validation

All errors are logged and returned to the client with appropriate error messages and context.

## Features

- **Async/Await**: Full asynchronous operation for high performance
- **Connection Pooling**: Efficient HTTP connection reuse
- **Request Deduplication**: Avoid duplicate requests in flight
- **Circuit Breakers**: Automatic failure detection and recovery
- **Metrics Collection**: Performance monitoring and statistics
- **Content Type Detection**: Intelligent content type identification
- **Response Transformation**: Pluggable response processing pipelines
- **Progress Reporting**: Real-time progress updates for long operations

## License

This MCP server implementation follows the same license as the WebFetch library.
