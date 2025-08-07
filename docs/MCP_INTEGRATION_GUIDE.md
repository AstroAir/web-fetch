# MCP Integration Guide

## Overview

This guide explains how to integrate the Web-Fetch MCP Server with various MCP-compatible clients and AI assistants.

## Supported Clients

### Claude Desktop

Claude Desktop has built-in MCP support. Add the following to your configuration:

**Location**: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)

```json
{
  "mcpServers": {
    "web-fetch": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "FIRECRAWL_API_KEY": "your-firecrawl-api-key",
        "TAVILY_API_KEY": "your-tavily-api-key",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

### Continue.dev

For Continue.dev integration:

```json
{
  "models": [...],
  "mcpServers": [
    {
      "name": "web-fetch",
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "FIRECRAWL_API_KEY": "your-api-key"
      }
    }
  ]
}
```

### Custom Python Client

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "mcp_server.server"],
        env={
            "FIRECRAWL_API_KEY": "your-api-key",
            "TAVILY_API_KEY": "your-api-key"
        }
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the session
            await session.initialize()
            
            # List available tools
            tools = await session.list_tools()
            print(f"Available tools: {[tool.name for tool in tools.tools]}")
            
            # Call a tool
            result = await session.call_tool("web_fetch", {
                "url": "https://example.com",
                "format": "markdown"
            })
            print(result.content)

if __name__ == "__main__":
    asyncio.run(main())
```

## Environment Setup

### Required Environment Variables

```bash
# Crawler API Keys (optional but recommended)
export FIRECRAWL_API_KEY="your-firecrawl-api-key"
export TAVILY_API_KEY="your-tavily-api-key"

# Optional configuration
export LOG_LEVEL="INFO"
export WEB_FETCH_TIMEOUT="30"
export WEB_FETCH_MAX_CONCURRENT="10"
```

### Installation

```bash
# Install with MCP support
pip install web-fetch[mcp]

# Or install with all features
pip install web-fetch[all-features]

# Development installation
git clone https://github.com/your-repo/web-fetch.git
cd web-fetch
pip install -e .[mcp,dev]
```

## Tool Usage Patterns

### Basic Web Scraping

```python
# Fetch a single page
result = await session.call_tool("web_fetch", {
    "url": "https://example.com",
    "format": "markdown",
    "timeout": 30
})

# Batch fetch multiple pages
result = await session.call_tool("web_fetch_batch", {
    "urls": [
        "https://example1.com",
        "https://example2.com",
        "https://example3.com"
    ],
    "max_concurrent": 3,
    "format": "text"
})
```

### Real-time Communication

```python
# Establish WebSocket connection
await session.call_tool("websocket_connect", {
    "url": "wss://echo.websocket.org",
    "connection_id": "my-connection"
})

# Send and receive messages
await session.call_tool("websocket_send", {
    "connection_id": "my-connection",
    "message": "Hello!",
    "message_type": "text"
})

messages = await session.call_tool("websocket_receive", {
    "connection_id": "my-connection",
    "timeout": 5.0
})
```

### API Integration

```python
# Configure authentication
await session.call_tool("auth_configure", {
    "auth_type": "api_key",
    "auth_name": "my-api",
    "config": {
        "api_key": "your-api-key",
        "header_name": "X-API-Key"
    }
})

# Use GraphQL APIs
result = await session.call_tool("graphql_query", {
    "endpoint": "https://api.example.com/graphql",
    "query": "{ user(id: 1) { name email } }",
    "headers": {"Authorization": "Bearer token"}
})
```

### Content Processing

```python
# Parse structured data
result = await session.call_tool("content_parse", {
    "content": json_string,
    "content_type": "json",
    "extract_links": True
})

# Transform content
result = await session.call_tool("content_transform", {
    "content": html_content,
    "transformations": [
        {
            "type": "html",
            "selectors": {
                "title": "h1",
                "content": ".article-body"
            }
        }
    ]
})
```

## Advanced Configuration

### Custom Server Configuration

```python
# Create custom MCP server
from mcp_server.server import create_mcp_server

mcp = create_mcp_server()

# Add custom configuration
mcp.settings.update({
    "default_timeout": 60,
    "max_retries": 3,
    "enable_caching": True
})

# Run the server
mcp.run()
```

### Error Handling

```python
try:
    result = await session.call_tool("web_fetch", {
        "url": "https://invalid-url"
    })
except Exception as e:
    print(f"Tool call failed: {e}")
    
# Check result success
if not result.get("success", False):
    error = result.get("error", "Unknown error")
    print(f"Tool returned error: {error}")
```

### Performance Optimization

```python
# Use batch operations for multiple URLs
urls = ["https://example1.com", "https://example2.com", ...]
result = await session.call_tool("web_fetch_batch", {
    "urls": urls,
    "max_concurrent": 5,  # Adjust based on target server limits
    "timeout": 30
})

# Monitor performance
metrics = await session.call_tool("metrics_summary")
print(f"Success rate: {metrics['metrics']['recent_success_rate']}%")
```

## Troubleshooting

### Common Issues

1. **Server Not Starting**
   - Check Python path and dependencies
   - Verify environment variables
   - Check logs for error messages

2. **Tool Call Failures**
   - Verify URL accessibility
   - Check authentication credentials
   - Monitor rate limits

3. **Performance Issues**
   - Reduce concurrent requests
   - Increase timeouts
   - Use caching where appropriate

### Debug Mode

Enable detailed logging:

```bash
export LOG_LEVEL=DEBUG
python -m mcp_server.server
```

### Health Checks

```python
# Check server health
health = await session.call_tool("metrics_summary")
if health["health_status"] != "healthy":
    print("Server health issues detected")

# Monitor recent performance
recent = await session.call_tool("metrics_recent", {"minutes": 5})
success_rate = recent["metrics"]["success_rate"]
if success_rate < 90:
    print(f"Low success rate: {success_rate}%")
```

## Best Practices

1. **Rate Limiting**: Respect target server rate limits
2. **Error Handling**: Always check tool call results
3. **Resource Management**: Close WebSocket connections when done
4. **Security**: Use environment variables for API keys
5. **Monitoring**: Track performance metrics
6. **Caching**: Use caching for repeated requests
7. **Timeouts**: Set appropriate timeouts for operations

## Examples Repository

See the `examples/` directory for complete working examples:

- `mcp_server_examples.py` - Comprehensive tool usage examples
- `integration_examples/` - Client integration examples
- `performance_examples/` - Performance optimization examples

## Support

For issues and questions:

1. Check the troubleshooting section
2. Review the examples
3. Check the GitHub issues
4. Create a new issue with detailed information

## Contributing

Contributions are welcome! Please see the main project documentation for guidelines.
