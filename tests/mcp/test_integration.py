"""
Integration tests for MCP server with real services.

This module contains integration tests that can be run against real services
when API keys and configurations are available.
"""

import os
import tempfile
from pathlib import Path
from typing import Optional

import pytest

from mcp_server.server import create_mcp_server


class TestMCPIntegration:
    """Integration tests for MCP server with real services."""

    @pytest.fixture
    async def mcp_server(self):
        """Create MCP server instance for testing."""
        return create_mcp_server()

    @pytest.fixture
    def temp_file(self):
        """Create a temporary file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("Test content for file operations")
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.getenv("FIRECRAWL_API_KEY"),
        reason="FIRECRAWL_API_KEY not set"
    )
    async def test_real_crawler_scrape(self, mcp_server):
        """Test crawler scraping with real Firecrawl API."""
        tools = {tool.name: tool for tool in mcp_server.tools}
        crawler_scrape = tools["crawler_scrape"]

        result = await crawler_scrape.func(
            url="https://example.com",
            crawler_type="firecrawl",
            content_format="markdown"
        )

        assert result["success"] is True
        assert result["content"]
        assert result["metadata"]["status_code"] == 200

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.getenv("TAVILY_API_KEY"),
        reason="TAVILY_API_KEY not set"
    )
    async def test_real_crawler_search(self, mcp_server):
        """Test crawler search with real Tavily API."""
        tools = {tool.name: tool for tool in mcp_server.tools}
        crawler_search = tools["crawler_search"]

        result = await crawler_search.func(
            query="Python web scraping",
            max_results=3,
            include_answer=True
        )

        assert result["success"] is True
        assert result["results"]
        assert len(result["results"]) <= 3

    @pytest.mark.integration
    async def test_real_content_parsing(self, mcp_server):
        """Test content parsing with real content."""
        tools = {tool.name: tool for tool in mcp_server.tools}
        content_parse = tools["content_parse"]

        # Test JSON parsing
        json_content = '{"name": "John", "age": 30, "city": "New York"}'
        result = await content_parse.func(
            content=json_content,
            content_type="json"
        )

        assert result["success"] is True
        assert result["content_type"] == "json"

        # Test HTML parsing
        html_content = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Welcome</h1>
                <p>This is a test page.</p>
                <a href="https://example.com">Link</a>
            </body>
        </html>
        """
        result = await content_parse.func(
            content=html_content,
            content_type="html",
            extract_links=True
        )

        assert result["success"] is True
        assert result["content_type"] == "html"

    @pytest.mark.integration
    async def test_real_metrics_collection(self, mcp_server):
        """Test metrics collection with real data."""
        tools = {tool.name: tool for tool in mcp_server.tools}
        
        # Record some metrics
        metrics_record = tools["metrics_record"]
        await metrics_record.func(
            url="https://example.com",
            method="GET",
            status_code=200,
            response_time=0.5,
            response_size=1024
        )

        # Get metrics summary
        metrics_summary = tools["metrics_summary"]
        result = await metrics_summary.func()

        assert result["success"] is True
        assert "metrics" in result

        # Get recent metrics
        metrics_recent = tools["metrics_recent"]
        result = await metrics_recent.func(minutes=5)

        assert result["success"] is True
        assert "metrics" in result

    @pytest.mark.integration
    async def test_real_authentication_flow(self, mcp_server):
        """Test authentication configuration and usage."""
        tools = {tool.name: tool for tool in mcp_server.tools}
        
        # Configure API key authentication
        auth_configure = tools["auth_configure"]
        result = await auth_configure.func(
            auth_type="api_key",
            auth_name="test-api",
            config={
                "api_key": "test-key-123",
                "header_name": "X-API-Key"
            },
            set_as_default=True
        )

        assert result["success"] is True
        assert result["auth_name"] == "test-api"
        assert result["is_default"] is True

        # Test authentication
        auth_authenticate = tools["auth_authenticate"]
        result = await auth_authenticate.func(auth_name="test-api")

        assert result["success"] is True
        assert "headers" in result

    @pytest.mark.integration
    async def test_content_transformation_pipeline(self, mcp_server):
        """Test content transformation with complex pipeline."""
        tools = {tool.name: tool for tool in mcp_server.tools}
        content_transform = tools["content_transform"]

        # Test JSON transformation
        json_content = '{"users": [{"name": "John", "email": "john@example.com"}, {"name": "Jane", "email": "jane@example.com"}]}'
        
        transformations = [
            {
                "type": "jsonpath",
                "expressions": {
                    "names": "$.users[*].name",
                    "emails": "$.users[*].email"
                }
            }
        ]

        result = await content_transform.func(
            content=json_content,
            transformations=transformations
        )

        assert result["success"] is True
        assert "transformed_data" in result

        # Test HTML transformation
        html_content = """
        <div class="article">
            <h1>Article Title</h1>
            <p class="content">Article content here.</p>
            <a href="https://example.com" class="link">Read more</a>
        </div>
        """
        
        transformations = [
            {
                "type": "html",
                "selectors": {
                    "title": "h1",
                    "content": "p.content",
                    "link": "a.link"
                },
                "extract_text": True
            }
        ]

        result = await content_transform.func(
            content=html_content,
            transformations=transformations
        )

        assert result["success"] is True
        assert "transformed_data" in result

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.getenv("TEST_FTP_SERVER"),
        reason="TEST_FTP_SERVER not set"
    )
    async def test_real_ftp_operations(self, mcp_server):
        """Test FTP operations with real FTP server."""
        ftp_server = os.getenv("TEST_FTP_SERVER", "ftp://ftp.example.com")
        
        tools = {tool.name: tool for tool in mcp_server.tools}
        
        # Test directory listing
        ftp_list = tools["ftp_list_directory"]
        result = await ftp_list.func(
            url=f"{ftp_server}/pub/",
            timeout=10.0
        )

        # Note: This might fail if server doesn't exist, but structure should be correct
        assert "success" in result
        assert "file_count" in result
        assert "files" in result

    @pytest.mark.integration
    async def test_error_handling_integration(self, mcp_server):
        """Test error handling in integration scenarios."""
        tools = {tool.name: tool for tool in mcp_server.tools}
        
        # Test invalid URL handling
        crawler_scrape = tools["crawler_scrape"]
        result = await crawler_scrape.func(
            url="not-a-valid-url",
            crawler_type="firecrawl"
        )

        assert result["success"] is False
        assert "error" in result

        # Test invalid FTP URL
        ftp_list = tools["ftp_list_directory"]
        result = await ftp_list.func(
            url="http://not-ftp-url"
        )

        assert result["success"] is False
        assert "error" in result

        # Test invalid content type
        content_parse = tools["content_parse"]
        result = await content_parse.func(
            content="invalid json {",
            content_type="json"
        )

        # Should handle gracefully
        assert "success" in result


class TestMCPPerformanceBenchmarks:
    """Performance benchmarks for MCP server tools."""

    @pytest.fixture
    async def mcp_server(self):
        """Create MCP server instance for testing."""
        return create_mcp_server()

    @pytest.mark.benchmark
    async def test_tool_execution_performance(self, mcp_server):
        """Benchmark tool execution performance."""
        import time
        
        tools = {tool.name: tool for tool in mcp_server.tools}
        
        # Benchmark metrics tools (should be fast)
        metrics_summary = tools["metrics_summary"]
        
        start_time = time.time()
        for _ in range(100):
            await metrics_summary.func()
        end_time = time.time()
        
        avg_time = (end_time - start_time) / 100
        print(f"Average metrics_summary execution time: {avg_time:.4f}s")
        
        # Should be under 10ms per call
        assert avg_time < 0.01

    @pytest.mark.benchmark
    async def test_concurrent_execution_performance(self, mcp_server):
        """Benchmark concurrent tool execution."""
        import asyncio
        import time
        
        tools = {tool.name: tool for tool in mcp_server.tools}
        metrics_summary = tools["metrics_summary"]
        
        # Test concurrent execution
        start_time = time.time()
        tasks = [metrics_summary.func() for _ in range(50)]
        await asyncio.gather(*tasks)
        end_time = time.time()
        
        total_time = end_time - start_time
        print(f"50 concurrent executions took: {total_time:.4f}s")
        
        # Should complete within reasonable time
        assert total_time < 5.0
