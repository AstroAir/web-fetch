# MCP Integration Overview

WebFetch includes comprehensive support for the Model Context Protocol (MCP), allowing AI models to interact with web content fetching capabilities through a standardized interface.

## What is MCP?

The Model Context Protocol (MCP) is a standardized way for AI models to interact with external tools and services. WebFetch's MCP server provides AI models with powerful web fetching capabilities.

## Features

### Core Web Fetching
- **Single URL fetching** with content type handling
- **Batch operations** for multiple URLs
- **Streaming downloads** for large files
- **Progress tracking** for long-running operations

### Advanced Capabilities
- **Content parsing** (JSON, HTML, text, raw)
- **Authentication support** (OAuth, API keys, JWT)
- **Caching mechanisms** for improved performance
- **Rate limiting** and error handling
- **File operations** (upload/download)

### Configuration Management
- **Environment-based configuration**
- **Validation and error reporting**
- **Security best practices**
- **Performance optimization**

## Quick Start

### Installation

```bash
# Install WebFetch with MCP support
pip install "web-fetch[mcp]"

# Or install all features
pip install "web-fetch[all]"
```

### Running the MCP Server

```bash
# Start the MCP server
python -m web_fetch.mcp_server

# Or use the convenience script
python run_mcp_server.py

# With custom configuration
python -m web_fetch.mcp_server --config mcp-config.json
```

### Basic Configuration

Create an `mcp-config.json` file:

```json
{
  "server": {
    "host": "localhost",
    "port": 8000,
    "debug": false
  },
  "web_fetch": {
    "total_timeout": 30.0,
    "max_concurrent_requests": 10,
    "max_retries": 3,
    "verify_ssl": true
  },
  "logging": {
    "level": "INFO",
    "format": "json"
  }
}
```

## Available Tools

The MCP server exposes these tools to AI models:

### `fetch_url`
Fetch a single URL with content type handling.

**Parameters:**
- `url` (string): URL to fetch
- `content_type` (string): How to parse content (text, json, html, raw)
- `timeout` (number, optional): Request timeout in seconds
- `headers` (object, optional): Custom HTTP headers

**Example:**
```json
{
  "name": "fetch_url",
  "arguments": {
    "url": "https://api.example.com/data",
    "content_type": "json",
    "headers": {
      "Authorization": "Bearer token"
    }
  }
}
```

### `fetch_urls`
Fetch multiple URLs concurrently.

**Parameters:**
- `urls` (array): List of URLs to fetch
- `content_type` (string): Content parsing type
- `max_concurrent` (number, optional): Maximum concurrent requests
- `timeout` (number, optional): Request timeout

### `download_file`
Download a file with progress tracking.

**Parameters:**
- `url` (string): File URL
- `output_path` (string): Where to save the file
- `chunk_size` (number, optional): Download chunk size
- `max_file_size` (number, optional): Maximum file size limit

### `upload_file`
Upload a file to a URL.

**Parameters:**
- `url` (string): Upload endpoint
- `file_path` (string): Path to file to upload
- `field_name` (string, optional): Form field name
- `additional_data` (object, optional): Additional form data

## Integration Examples

### With Claude/ChatGPT

```python
# Example of how an AI model might use the MCP server
import json

# Fetch API data
response = mcp_client.call_tool("fetch_url", {
    "url": "https://api.github.com/repos/microsoft/vscode",
    "content_type": "json"
})

if response["success"]:
    repo_data = response["content"]
    print(f"Repository: {repo_data['name']}")
    print(f"Stars: {repo_data['stargazers_count']}")
```

### Batch Web Scraping

```python
# Fetch multiple pages for analysis
urls = [
    "https://example.com/page1",
    "https://example.com/page2", 
    "https://example.com/page3"
]

response = mcp_client.call_tool("fetch_urls", {
    "urls": urls,
    "content_type": "html",
    "max_concurrent": 3
})

for result in response["successful_results"]:
    title = result["content"]["title"]
    print(f"Page title: {title}")
```

### File Operations

```python
# Download a file
download_response = mcp_client.call_tool("download_file", {
    "url": "https://example.com/data.csv",
    "output_path": "/tmp/data.csv",
    "chunk_size": 8192
})

# Upload processed file
upload_response = mcp_client.call_tool("upload_file", {
    "url": "https://api.example.com/upload",
    "file_path": "/tmp/processed_data.csv",
    "field_name": "data_file"
})
```

## Configuration

### Server Configuration

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8000,
    "debug": false,
    "cors_enabled": true,
    "max_request_size": 10485760
  }
}
```

### WebFetch Configuration

```json
{
  "web_fetch": {
    "total_timeout": 30.0,
    "connect_timeout": 10.0,
    "read_timeout": 20.0,
    "max_concurrent_requests": 10,
    "max_retries": 3,
    "retry_delay": 1.0,
    "verify_ssl": true,
    "follow_redirects": true,
    "max_response_size": 10485760
  }
}
```

### Security Configuration

```json
{
  "security": {
    "allowed_domains": ["api.example.com", "data.example.org"],
    "blocked_domains": ["malicious.com"],
    "require_https": true,
    "max_file_size": 104857600,
    "allowed_file_types": [".csv", ".json", ".txt", ".pdf"]
  }
}
```

## Error Handling

The MCP server provides comprehensive error handling:

```json
{
  "success": false,
  "error": {
    "type": "NetworkError",
    "message": "Connection timeout",
    "details": {
      "url": "https://slow.example.com",
      "timeout": 30.0,
      "retry_count": 3
    }
  }
}
```

### Error Types

- **NetworkError**: Connection and network issues
- **HTTPError**: HTTP status code errors (4xx, 5xx)
- **ContentError**: Content parsing failures
- **ValidationError**: Invalid parameters or configuration
- **SecurityError**: Security policy violations

## Monitoring and Logging

### Structured Logging

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "component": "mcp_server",
  "operation": "fetch_url",
  "url": "https://api.example.com/data",
  "status_code": 200,
  "response_time": 0.45,
  "content_type": "application/json",
  "size_bytes": 1024
}
```

### Metrics

The server tracks:
- Request counts and success rates
- Response times and throughput
- Error rates by type
- Cache hit rates
- File transfer statistics

## Security Considerations

### Best Practices

1. **Domain Restrictions**: Configure allowed/blocked domains
2. **HTTPS Enforcement**: Require secure connections
3. **File Size Limits**: Prevent resource exhaustion
4. **Rate Limiting**: Control request frequency
5. **Input Validation**: Validate all parameters
6. **Logging**: Monitor all operations

### Example Security Config

```json
{
  "security": {
    "allowed_domains": ["*.api.example.com", "data.trusted.org"],
    "blocked_domains": ["*.malicious.com"],
    "require_https": true,
    "max_file_size": 100000000,
    "rate_limit": {
      "requests_per_minute": 60,
      "burst_size": 10
    }
  }
}
```

## Next Steps

- **[Server Setup](server.md)** - Detailed server configuration
- **[Integration Guide](integration.md)** - Integrating with AI models
- **[API Reference](../api/core.md)** - Complete API documentation
- **[Examples](../examples/advanced.md)** - Advanced usage examples
