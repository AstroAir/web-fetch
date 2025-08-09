# Web-Fetch MCP Server Documentation

## Overview

The Web-Fetch MCP (Model Context Protocol) Server provides a comprehensive set of tools for web scraping, content processing, authentication, monitoring, and more. It's designed to be used with MCP-compatible clients and AI assistants.

## Features

### Core Web Fetching

- **web_fetch**: Fetch web content with advanced options
- **web_fetch_batch**: Batch processing of multiple URLs
- **web_fetch_enhanced**: Enhanced fetching with AI-powered features
- **validate_url**: URL validation and analysis
- **analyze_headers**: HTTP header analysis

### WebSocket Support

- **websocket_connect**: Establish WebSocket connections
- **websocket_send**: Send messages through WebSocket
- **websocket_receive**: Receive messages from WebSocket
- **websocket_disconnect**: Close WebSocket connections
- **websocket_status**: Monitor WebSocket connection status

### GraphQL Integration

- **graphql_query**: Execute GraphQL queries
- **graphql_mutation**: Perform GraphQL mutations
- **graphql_introspect**: Introspect GraphQL schemas

### Authentication Management

- **auth_configure**: Configure authentication methods
- **auth_authenticate**: Perform authentication
- **auth_refresh**: Refresh authentication tokens

### Content Processing

- **content_parse**: Parse various content types
- **content_transform**: Transform content using pipelines

### File Operations

- **upload_file**: Upload files with progress tracking
- **manage_headers**: Advanced header management
- **manage_cookies**: Cookie management and persistence

### FTP Support

- **ftp_list_directory**: List FTP directory contents
- **ftp_download_file**: Download files from FTP servers

### Crawler Integration

- **crawler_scrape**: Scrape content using external crawlers
- **crawler_search**: Search the web using AI-powered crawlers

### Monitoring & Analytics

- **metrics_summary**: Get system performance metrics
- **metrics_recent**: Get recent performance data
- **metrics_record**: Record custom metrics

## Installation

```bash
# Install with MCP support
pip install web-fetch[mcp]

# Or install with all features
pip install web-fetch[all-features]
```

## Quick Start

### Starting the MCP Server

```python
from mcp_server.server import create_mcp_server

# Create and run the server
mcp = create_mcp_server()
mcp.run()
```

### Using with MCP Clients

The server can be used with any MCP-compatible client. Here's how to configure it:

```json
{
  "mcpServers": {
    "web-fetch": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "FIRECRAWL_API_KEY": "your-api-key",
        "TAVILY_API_KEY": "your-api-key"
      }
    }
  }
}
```

## Tool Usage Examples

### Web Fetching

```python
# Basic web fetch
result = await mcp.call_tool("web_fetch", {
    "url": "https://example.com",
    "format": "markdown"
})

# Batch fetching
result = await mcp.call_tool("web_fetch_batch", {
    "urls": ["https://example1.com", "https://example2.com"],
    "max_concurrent": 5
})
```

### WebSocket Communication

```python
# Connect to WebSocket
result = await mcp.call_tool("websocket_connect", {
    "url": "wss://echo.websocket.org",
    "connection_id": "my-connection"
})

# Send message
result = await mcp.call_tool("websocket_send", {
    "connection_id": "my-connection",
    "message": "Hello WebSocket!",
    "message_type": "text"
})

# Receive messages
result = await mcp.call_tool("websocket_receive", {
    "connection_id": "my-connection",
    "timeout": 5.0,
    "max_messages": 10
})
```

### GraphQL Operations

```python
# Execute GraphQL query
result = await mcp.call_tool("graphql_query", {
    "endpoint": "https://api.example.com/graphql",
    "query": "{ user(id: 1) { name email } }",
    "variables": {"id": 1}
})

# Introspect schema
result = await mcp.call_tool("graphql_introspect", {
    "endpoint": "https://api.example.com/graphql"
})
```

### Authentication

```python
# Configure API key authentication
result = await mcp.call_tool("auth_configure", {
    "auth_type": "api_key",
    "auth_name": "my-api",
    "config": {
        "api_key": "your-api-key",
        "header_name": "X-API-Key"
    },
    "set_as_default": True
})

# Authenticate
result = await mcp.call_tool("auth_authenticate", {
    "auth_name": "my-api"
})
```

### Content Processing

```python
# Parse JSON content
result = await mcp.call_tool("content_parse", {
    "content": '{"name": "John", "age": 30}',
    "content_type": "json"
})

# Transform content with pipeline
result = await mcp.call_tool("content_transform", {
    "content": html_content,
    "transformations": [
        {
            "type": "html",
            "selectors": {
                "title": "h1",
                "content": "p"
            }
        }
    ]
})
```

### Crawler Integration

```python
# Scrape with Firecrawl
result = await mcp.call_tool("crawler_scrape", {
    "url": "https://example.com",
    "crawler_type": "firecrawl",
    "content_format": "markdown"
})

# Search with Tavily
result = await mcp.call_tool("crawler_search", {
    "query": "Python web scraping",
    "max_results": 5,
    "include_answer": True
})
```

### FTP Operations

```python
# List FTP directory
result = await mcp.call_tool("ftp_list_directory", {
    "url": "ftp://ftp.example.com/pub/",
    "username": "user",
    "password": "pass"
})

# Download FTP file
result = await mcp.call_tool("ftp_download_file", {
    "url": "ftp://ftp.example.com/file.txt",
    "local_path": "/tmp/file.txt",
    "username": "user",
    "password": "pass"
})
```

### Monitoring

```python
# Get system metrics
result = await mcp.call_tool("metrics_summary")

# Get recent performance
result = await mcp.call_tool("metrics_recent", {
    "minutes": 5
})

# Record custom metrics
result = await mcp.call_tool("metrics_record", {
    "url": "https://example.com",
    "method": "GET",
    "status_code": 200,
    "response_time": 0.5
})
```

## Configuration

### Environment Variables

- `FIRECRAWL_API_KEY`: API key for Firecrawl service
- `TAVILY_API_KEY`: API key for Tavily service
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

### Server Configuration

The server can be configured with various options:

```python
mcp = create_mcp_server()

# Configure with custom settings
mcp.settings.timeout = 30.0
mcp.settings.max_concurrent = 10
```

## Error Handling

All tools return a consistent error format:

```json
{
    "success": false,
    "error": "Error description",
    "error_type": "ErrorType",
    "additional_context": {}
}
```

## Performance Considerations

- Use batch operations for multiple URLs
- Configure appropriate timeouts
- Monitor metrics for performance optimization
- Use caching where appropriate
- Consider rate limiting for external APIs

## Security

- API keys are masked in responses
- Input validation on all parameters
- Secure handling of authentication data
- Protection against common web vulnerabilities

## Troubleshooting

### Common Issues

1. **Connection Timeouts**: Increase timeout values
2. **Rate Limiting**: Implement delays between requests
3. **Authentication Failures**: Verify API keys and credentials
4. **Memory Issues**: Use streaming for large files

### Debug Mode

Enable debug logging for detailed information:

```bash
export LOG_LEVEL=DEBUG
python -m mcp_server.server
```

## API Reference

### Tool Categories

#### Web Fetching Tools

- `web_fetch(url, format, headers, timeout, ...)` - Fetch web content
- `web_fetch_batch(urls, max_concurrent, ...)` - Batch fetch multiple URLs
- `web_fetch_enhanced(url, extract_content, summarize, ...)` - Enhanced fetching
- `validate_url(url)` - Validate URL format and accessibility
- `analyze_headers(headers)` - Analyze HTTP headers

#### WebSocket Tools

- `websocket_connect(url, connection_id, ...)` - Establish WebSocket connection
- `websocket_send(connection_id, message, message_type)` - Send message
- `websocket_receive(connection_id, timeout, max_messages)` - Receive messages
- `websocket_disconnect(connection_id)` - Close connection
- `websocket_status(connection_id)` - Get connection status

#### GraphQL Tools

- `graphql_query(endpoint, query, variables, ...)` - Execute GraphQL query
- `graphql_mutation(endpoint, mutation, variables, ...)` - Execute mutation
- `graphql_introspect(endpoint, ...)` - Introspect schema

#### Authentication Tools

- `auth_configure(auth_type, auth_name, config, ...)` - Configure auth method
- `auth_authenticate(auth_name, ...)` - Perform authentication
- `auth_refresh(auth_name)` - Refresh authentication tokens

#### Content Processing Tools

- `content_parse(content, content_type, ...)` - Parse various content types
- `content_transform(content, transformations)` - Transform content

#### File Operation Tools

- `upload_file(url, file_path, ...)` - Upload files with progress
- `manage_headers(action, ...)` - Advanced header management
- `manage_cookies(action, ...)` - Cookie management

#### FTP Tools

- `ftp_list_directory(url, username, password, ...)` - List FTP directory
- `ftp_download_file(url, local_path, ...)` - Download FTP file

#### Crawler Tools

- `crawler_scrape(url, crawler_type, ...)` - Scrape with external crawlers
- `crawler_search(query, max_results, ...)` - AI-powered web search

#### Monitoring Tools

- `metrics_summary()` - Get system performance metrics
- `metrics_recent(minutes)` - Get recent performance data
- `metrics_record(url, method, status_code, ...)` - Record custom metrics

### Response Format

All tools return a consistent response format:

```json
{
    "success": boolean,
    "data": object,
    "error": string,
    "metadata": object
}
```

### Error Codes

- `ValidationError`: Invalid input parameters
- `NetworkError`: Network connectivity issues
- `AuthenticationError`: Authentication failures
- `TimeoutError`: Request timeouts
- `ServerError`: Server-side errors

## Integration Examples

### Claude Desktop Integration

Add to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "web-fetch": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "FIRECRAWL_API_KEY": "your-key",
        "TAVILY_API_KEY": "your-key"
      }
    }
  }
}
```

### Custom Client Integration

```python
import asyncio
from mcp_client import MCPClient

async def use_web_fetch():
    client = MCPClient("web-fetch")
    await client.connect()

    result = await client.call_tool("web_fetch", {
        "url": "https://example.com",
        "format": "markdown"
    })

    print(result)
    await client.disconnect()

asyncio.run(use_web_fetch())
```

## Contributing

See the main project documentation for contribution guidelines.

## License

This project is licensed under the MIT License.
