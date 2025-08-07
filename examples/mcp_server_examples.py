"""
Comprehensive examples for the Web-Fetch MCP Server.

This file demonstrates how to use all the tools provided by the MCP server
with practical, real-world examples.
"""

import asyncio
import json
from typing import Any, Dict

from mcp_server.server import create_mcp_server


class MCPServerExamples:
    """Examples demonstrating MCP server tool usage."""

    def __init__(self):
        """Initialize the MCP server."""
        self.mcp = create_mcp_server()

    async def call_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Helper method to call MCP tools."""
        tools = await self.mcp.get_tools()
        if tool_name not in tools:
            raise ValueError(f"Tool '{tool_name}' not found")
        
        tool = tools[tool_name]
        return await tool(**params)

    async def web_fetching_examples(self):
        """Examples of web fetching capabilities."""
        print("=== Web Fetching Examples ===")

        # Basic web fetch
        print("\n1. Basic Web Fetch:")
        result = await self.call_tool("web_fetch", {
            "url": "https://httpbin.org/json",
            "format": "json"
        })
        print(f"Success: {result['success']}")
        print(f"Content type: {result.get('content_type')}")

        # Batch web fetch
        print("\n2. Batch Web Fetch:")
        result = await self.call_tool("web_fetch_batch", {
            "urls": [
                "https://httpbin.org/json",
                "https://httpbin.org/html",
                "https://httpbin.org/xml"
            ],
            "max_concurrent": 3
        })
        print(f"Batch results: {len(result.get('results', []))} URLs processed")

        # Enhanced web fetch with AI features
        print("\n3. Enhanced Web Fetch:")
        result = await self.call_tool("web_fetch_enhanced", {
            "url": "https://example.com",
            "extract_content": True,
            "summarize": True,
            "extract_links": True
        })
        print(f"Enhanced fetch success: {result['success']}")

    async def websocket_examples(self):
        """Examples of WebSocket functionality."""
        print("\n=== WebSocket Examples ===")

        # Connect to WebSocket
        print("\n1. WebSocket Connection:")
        result = await self.call_tool("websocket_connect", {
            "url": "wss://echo.websocket.org",
            "connection_id": "example-connection",
            "auto_reconnect": True,
            "ping_interval": 30.0
        })
        print(f"Connection success: {result['success']}")

        if result['success']:
            # Send message
            print("\n2. Send WebSocket Message:")
            result = await self.call_tool("websocket_send", {
                "connection_id": "example-connection",
                "message": "Hello WebSocket!",
                "message_type": "text"
            })
            print(f"Message sent: {result['success']}")

            # Receive messages
            print("\n3. Receive WebSocket Messages:")
            result = await self.call_tool("websocket_receive", {
                "connection_id": "example-connection",
                "timeout": 5.0,
                "max_messages": 5
            })
            print(f"Messages received: {result.get('message_count', 0)}")

            # Check connection status
            print("\n4. WebSocket Status:")
            result = await self.call_tool("websocket_status", {
                "connection_id": "example-connection"
            })
            print(f"Connection state: {result.get('status', {}).get('state')}")

            # Disconnect
            print("\n5. WebSocket Disconnect:")
            result = await self.call_tool("websocket_disconnect", {
                "connection_id": "example-connection"
            })
            print(f"Disconnection success: {result['success']}")

    async def graphql_examples(self):
        """Examples of GraphQL functionality."""
        print("\n=== GraphQL Examples ===")

        # Note: These examples use a public GraphQL API
        graphql_endpoint = "https://countries.trevorblades.com/"

        # GraphQL Query
        print("\n1. GraphQL Query:")
        result = await self.call_tool("graphql_query", {
            "endpoint": graphql_endpoint,
            "query": """
                query GetCountries {
                    countries(filter: {continent: {eq: "NA"}}) {
                        name
                        code
                        capital
                    }
                }
            """,
            "timeout": 10.0
        })
        print(f"Query success: {result['success']}")
        if result['success']:
            countries = result.get('data', {}).get('countries', [])
            print(f"Found {len(countries)} North American countries")

        # GraphQL Schema Introspection
        print("\n2. GraphQL Schema Introspection:")
        result = await self.call_tool("graphql_introspect", {
            "endpoint": graphql_endpoint,
            "timeout": 10.0
        })
        print(f"Introspection success: {result['success']}")
        if result['success']:
            stats = result.get('stats', {})
            print(f"Schema has {stats.get('total_types', 0)} types")

    async def authentication_examples(self):
        """Examples of authentication functionality."""
        print("\n=== Authentication Examples ===")

        # Configure API Key Authentication
        print("\n1. Configure API Key Auth:")
        result = await self.call_tool("auth_configure", {
            "auth_type": "api_key",
            "auth_name": "example-api",
            "config": {
                "api_key": "example-key-123",
                "header_name": "X-API-Key"
            },
            "set_as_default": True
        })
        print(f"Auth configuration success: {result['success']}")

        # Authenticate
        print("\n2. Perform Authentication:")
        result = await self.call_tool("auth_authenticate", {
            "auth_name": "example-api"
        })
        print(f"Authentication success: {result['success']}")
        if result['success']:
            print(f"Headers configured: {bool(result.get('headers'))}")

        # Configure OAuth2 Authentication
        print("\n3. Configure OAuth2 Auth:")
        result = await self.call_tool("auth_configure", {
            "auth_type": "oauth2",
            "auth_name": "oauth-example",
            "config": {
                "client_id": "example-client-id",
                "client_secret": "example-client-secret",
                "authorization_url": "https://example.com/oauth/authorize",
                "token_url": "https://example.com/oauth/token"
            }
        })
        print(f"OAuth2 configuration success: {result['success']}")

    async def content_processing_examples(self):
        """Examples of content processing functionality."""
        print("\n=== Content Processing Examples ===")

        # Parse JSON content
        print("\n1. Parse JSON Content:")
        json_content = json.dumps({
            "users": [
                {"name": "Alice", "age": 30, "city": "New York"},
                {"name": "Bob", "age": 25, "city": "San Francisco"}
            ]
        })
        result = await self.call_tool("content_parse", {
            "content": json_content,
            "content_type": "json",
            "analyze_content": True
        })
        print(f"JSON parsing success: {result['success']}")

        # Parse HTML content
        print("\n2. Parse HTML Content:")
        html_content = """
        <html>
            <head><title>Example Page</title></head>
            <body>
                <h1>Welcome</h1>
                <p>This is an example page.</p>
                <a href="https://example.com">Link</a>
                <img src="image.jpg" alt="Example">
            </body>
        </html>
        """
        result = await self.call_tool("content_parse", {
            "content": html_content,
            "content_type": "html",
            "extract_links": True
        })
        print(f"HTML parsing success: {result['success']}")
        if result['success']:
            print(f"Links found: {len(result.get('links', []))}")

        # Transform content with pipeline
        print("\n3. Content Transformation:")
        result = await self.call_tool("content_transform", {
            "content": json_content,
            "transformations": [
                {
                    "type": "jsonpath",
                    "expressions": {
                        "names": "$.users[*].name",
                        "cities": "$.users[*].city"
                    }
                }
            ]
        })
        print(f"Transformation success: {result['success']}")
        if result['success']:
            data = result.get('transformed_data', {})
            print(f"Extracted names: {data.get('names', [])}")

    async def crawler_examples(self):
        """Examples of crawler integration."""
        print("\n=== Crawler Examples ===")

        # Note: These examples require API keys to be set

        # Scrape with crawler
        print("\n1. Crawler Scraping:")
        result = await self.call_tool("crawler_scrape", {
            "url": "https://example.com",
            "crawler_type": "firecrawl",
            "content_format": "markdown",
            "include_links": True
        })
        print(f"Crawler scraping success: {result['success']}")

        # Search with AI-powered crawler
        print("\n2. AI-Powered Search:")
        result = await self.call_tool("crawler_search", {
            "query": "Python web scraping best practices",
            "max_results": 3,
            "include_answer": True,
            "search_depth": "basic"
        })
        print(f"AI search success: {result['success']}")
        if result['success']:
            print(f"Results found: {len(result.get('results', []))}")
            if result.get('answer'):
                print(f"AI Answer: {result['answer'][:100]}...")

    async def monitoring_examples(self):
        """Examples of monitoring and metrics."""
        print("\n=== Monitoring Examples ===")

        # Record custom metrics
        print("\n1. Record Custom Metrics:")
        result = await self.call_tool("metrics_record", {
            "url": "https://example.com",
            "method": "GET",
            "status_code": 200,
            "response_time": 0.5,
            "response_size": 1024
        })
        print(f"Metrics recording success: {result['success']}")

        # Get system metrics summary
        print("\n2. System Metrics Summary:")
        result = await self.call_tool("metrics_summary")
        print(f"Metrics summary success: {result['success']}")
        if result['success']:
            metrics = result.get('metrics', {})
            print(f"Health status: {result.get('health_status')}")
            print(f"Recent success rate: {metrics.get('recent_success_rate', 0):.1f}%")

        # Get recent performance data
        print("\n3. Recent Performance:")
        result = await self.call_tool("metrics_recent", {
            "minutes": 5
        })
        print(f"Recent metrics success: {result['success']}")
        if result['success']:
            metrics = result.get('metrics', {})
            print(f"Total requests: {metrics.get('total_requests', 0)}")
            print(f"Average response time: {metrics.get('average_response_time', 0):.3f}s")

    async def run_all_examples(self):
        """Run all examples."""
        print("Starting MCP Server Examples...")
        
        try:
            await self.web_fetching_examples()
            await self.websocket_examples()
            await self.graphql_examples()
            await self.authentication_examples()
            await self.content_processing_examples()
            await self.crawler_examples()
            await self.monitoring_examples()
            
            print("\n=== All Examples Completed ===")
            
        except Exception as e:
            print(f"Error running examples: {e}")


async def main():
    """Main function to run examples."""
    examples = MCPServerExamples()
    await examples.run_all_examples()


if __name__ == "__main__":
    asyncio.run(main())
