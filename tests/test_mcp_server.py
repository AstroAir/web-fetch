"""
Comprehensive tests for the MCP server tools.

This module tests all MCP tools including WebSocket, GraphQL, authentication,
content processing, monitoring, FTP, and crawler integration.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict

import pytest
from fastmcp import FastMCP

from mcp_server.server import create_mcp_server


class TestMCPServerTools:
    """Test suite for MCP server tools."""

    @pytest.fixture
    def mcp_server(self):
        """Create MCP server instance for testing."""
        return create_mcp_server()

    @pytest.fixture
    def mock_context(self):
        """Create mock context for MCP tools."""
        context = AsyncMock()
        context.info = AsyncMock()
        context.error = AsyncMock()
        context.report_progress = AsyncMock()
        return context

    # WebSocket Tools Tests
    @pytest.mark.asyncio
    async def test_websocket_connect_tool(self, mcp_server, mock_context):
        """Test WebSocket connection tool."""
        with patch('mcp_server.server._websocket_manager') as mock_manager:
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.connection_state.value = "connected"
            mock_result.connection_time = 0.5
            mock_result.error = None

            mock_manager_instance = AsyncMock()
            mock_manager_instance.add_connection.return_value = mock_result
            mock_manager.return_value = mock_manager_instance

            # Get the tool function directly from the server
            tools = await mcp_server.get_tools()
            websocket_connect = tools["websocket_connect"]

            result = await websocket_connect(
                url="wss://echo.websocket.org",
                connection_id="test-connection",
                ctx=mock_context
            )

            assert result["success"] is True
            assert result["connection_id"] == "test-connection"
            assert result["url"] == "wss://echo.websocket.org"
            mock_context.info.assert_called()

    @pytest.mark.asyncio
    async def test_websocket_send_tool(self, mcp_server, mock_context):
        """Test WebSocket send message tool."""
        with patch('mcp_server.server._websocket_manager') as mock_manager:
            mock_manager_instance = AsyncMock()
            mock_manager_instance.send_text.return_value = True
            mock_manager.return_value = mock_manager_instance

            tools = await mcp_server.get_tools()
            websocket_send = tools["websocket_send"]

            result = await websocket_send.fn(
                connection_id="test-connection",
                message="Hello WebSocket",
                message_type="text",
                ctx=mock_context
            )

            assert result["success"] is True
            assert result["connection_id"] == "test-connection"
            assert result["message_type"] == "text"
            mock_manager_instance.send_text.assert_called_with("test-connection", "Hello WebSocket")

    # GraphQL Tools Tests
    @pytest.mark.asyncio
    async def test_graphql_query_tool(self, mcp_server, mock_context):
        """Test GraphQL query tool."""
        with patch('mcp_server.server._graphql_clients') as mock_clients:
            mock_client = AsyncMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.data = {"user": {"name": "John Doe"}}
            mock_result.errors = []
            mock_result.extensions = {}
            mock_client.execute.return_value = mock_result
            mock_clients.__setitem__ = MagicMock()
            mock_clients.__getitem__ = MagicMock(return_value=mock_client)

            with patch('mcp_server.server.GraphQLClient') as mock_gql_client:
                mock_gql_client.return_value = mock_client

                tools = await mcp_server.get_tools()
                graphql_query = tools["graphql_query"]

                result = await graphql_query.func(
                    endpoint="https://api.example.com/graphql",
                    query="{ user { name } }",
                    ctx=mock_context
                )

                assert result["success"] is True
                assert result["data"] == {"user": {"name": "John Doe"}}
                assert result["errors"] == []

    # Authentication Tools Tests
    @pytest.mark.asyncio
    async def test_auth_configure_tool(self, mcp_server, mock_context):
        """Test authentication configuration tool."""
        with patch('mcp_server.server._auth_manager') as mock_auth_manager:
            mock_auth_manager_instance = AsyncMock()
            mock_auth_manager_instance.add_auth_method = AsyncMock()
            mock_auth_manager_instance.set_default_method = AsyncMock()
            mock_auth_manager.return_value = mock_auth_manager_instance

            tools = {tool.name: tool for tool in await mcp_server.get_tools()}
            auth_configure = tools["auth_configure"]

            result = await auth_configure.func(
                auth_type="api_key",
                auth_name="test-auth",
                config={"api_key": "test-key", "header_name": "X-API-Key"},
                set_as_default=True,
                ctx=mock_context
            )

            assert result["success"] is True
            assert result["auth_name"] == "test-auth"
            assert result["auth_type"] == "api_key"
            assert result["is_default"] is True

    # Content Processing Tools Tests
    @pytest.mark.asyncio
    async def test_content_parse_tool(self, mcp_server, mock_context):
        """Test content parsing tool."""
        with patch('mcp_server.server.EnhancedContentParser') as mock_parser_class:
            mock_parser = AsyncMock()
            mock_result = MagicMock()
            mock_result.pdf_metadata = None
            mock_result.image_metadata = None
            mock_result.feed_metadata = None
            mock_result.csv_metadata = None
            mock_result.content_summary = None
            mock_result.links = []
            mock_result.feed_items = []
            
            mock_parser.parse_content.return_value = ("parsed content", mock_result)
            mock_parser_class.return_value = mock_parser

            tools = {tool.name: tool for tool in await mcp_server.get_tools()}
            content_parse = tools["content_parse"]

            result = await content_parse.func(
                content='{"key": "value"}',
                content_type="json",
                ctx=mock_context
            )

            assert result["success"] is True
            assert result["content_type"] == "json"
            assert result["parsed_content"] == "parsed content"

    # Monitoring Tools Tests
    @pytest.mark.asyncio
    async def test_metrics_summary_tool(self, mcp_server, mock_context):
        """Test metrics summary tool."""
        with patch('mcp_server.server.get_metrics_summary') as mock_get_metrics:
            mock_metrics = {
                "recent_success_rate": 95.5,
                "hourly_success_rate": 92.1,
                "recent_avg_response_time": 0.245,
                "total_requests": 1000
            }
            mock_get_metrics.return_value = mock_metrics

            tools = {tool.name: tool for tool in await mcp_server.get_tools()}
            metrics_summary = tools["metrics_summary"]

            result = await metrics_summary.func(ctx=mock_context)

            assert result["success"] is True
            assert result["metrics"] == mock_metrics
            assert result["health_status"] == "healthy"

    # FTP Tools Tests
    @pytest.mark.asyncio
    async def test_ftp_list_directory_tool(self, mcp_server, mock_context):
        """Test FTP directory listing tool."""
        with patch('mcp_server.server.ftp_list_directory') as mock_ftp_list:
            mock_file_info = MagicMock()
            mock_file_info.name = "test.txt"
            mock_file_info.path = "/test.txt"
            mock_file_info.size = 1024
            mock_file_info.modified_time = None
            mock_file_info.is_directory = False
            mock_file_info.permissions = "644"
            
            mock_ftp_list.return_value = [mock_file_info]

            tools = {tool.name: tool for tool in await mcp_server.get_tools()}
            ftp_list = tools["ftp_list_directory"]

            result = await ftp_list.func(
                url="ftp://ftp.example.com/pub/",
                ctx=mock_context
            )

            assert result["success"] is True
            assert result["file_count"] == 1
            assert len(result["files"]) == 1
            assert result["files"][0]["name"] == "test.txt"

    # Crawler Tools Tests
    @pytest.mark.asyncio
    async def test_crawler_scrape_tool(self, mcp_server, mock_context):
        """Test crawler scraping tool."""
        with patch('mcp_server.server.crawler_fetch_url') as mock_crawler_fetch:
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.content = "# Test Content\n\nThis is test content."
            mock_result.content_type.value = "markdown"
            mock_result.links = []
            mock_result.images = []
            mock_result.title = "Test Page"
            mock_result.description = "Test description"
            mock_result.status_code = 200
            mock_result.response_time = 0.5
            mock_result.error = None
            
            mock_crawler_fetch.return_value = mock_result

            tools = {tool.name: tool for tool in await mcp_server.get_tools()}
            crawler_scrape = tools["crawler_scrape"]

            result = await crawler_scrape.func(
                url="https://example.com",
                crawler_type="firecrawl",
                content_format="markdown",
                ctx=mock_context
            )

            assert result["success"] is True
            assert result["url"] == "https://example.com"
            assert result["content"] == "# Test Content\n\nThis is test content."
            assert result["metadata"]["title"] == "Test Page"

    @pytest.mark.asyncio
    async def test_crawler_search_tool(self, mcp_server, mock_context):
        """Test crawler search tool."""
        with patch('mcp_server.server.crawler_search_web') as mock_crawler_search:
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.answer = "AI-generated answer"
            mock_result.search_results = [
                {"title": "Result 1", "url": "https://example1.com", "content": "Content 1", "score": 0.9},
                {"title": "Result 2", "url": "https://example2.com", "content": "Content 2", "score": 0.8}
            ]
            mock_result.images = []
            mock_result.response_time = 1.2
            mock_result.error = None
            
            mock_crawler_search.return_value = mock_result

            tools = {tool.name: tool for tool in await mcp_server.get_tools()}
            crawler_search = tools["crawler_search"]

            result = await crawler_search.func(
                query="test search query",
                max_results=5,
                include_answer=True,
                ctx=mock_context
            )

            assert result["success"] is True
            assert result["query"] == "test search query"
            assert result["answer"] == "AI-generated answer"
            assert len(result["results"]) == 2
            assert result["results"][0]["title"] == "Result 1"

    # Error Handling Tests
    @pytest.mark.asyncio
    async def test_websocket_connect_invalid_url(self, mcp_server, mock_context):
        """Test WebSocket connection with invalid URL."""
        tools = {tool.name: tool for tool in await mcp_server.get_tools()}
        websocket_connect = tools["websocket_connect"]

        result = await websocket_connect.func(
            url="http://invalid-websocket-url",
            connection_id="test-connection",
            ctx=mock_context
        )

        assert result["success"] is False
        assert "must start with ws://" in result["error"]
        mock_context.error.assert_called()

    @pytest.mark.asyncio
    async def test_graphql_query_invalid_endpoint(self, mcp_server, mock_context):
        """Test GraphQL query with invalid endpoint."""
        tools = {tool.name: tool for tool in await mcp_server.get_tools()}
        graphql_query = tools["graphql_query"]

        result = await graphql_query.func(
            endpoint="invalid-url",
            query="{ test }",
            ctx=mock_context
        )

        assert result["success"] is False
        assert "Invalid endpoint URL" in result["error"]


class TestMCPServerIntegration:
    """Integration tests for MCP server tools."""

    @pytest.fixture
    def mcp_server(self):
        """Create MCP server instance for testing."""
        return create_mcp_server()

    @pytest.mark.asyncio
    async def test_tool_registration(self, mcp_server):
        """Test that all expected tools are registered."""
        tool_names = {tool.name for tool in await mcp_server.get_tools()}

        expected_tools = {
            # WebSocket tools
            "websocket_connect", "websocket_send", "websocket_receive",
            "websocket_disconnect", "websocket_status",
            # GraphQL tools
            "graphql_query", "graphql_mutation", "graphql_introspect",
            # Authentication tools
            "auth_configure", "auth_authenticate", "auth_refresh",
            # Content processing tools
            "content_parse", "content_transform",
            # Monitoring tools
            "metrics_summary", "metrics_recent", "metrics_record",
            # FTP tools
            "ftp_list_directory", "ftp_download_file",
            # Crawler tools
            "crawler_scrape", "crawler_search",
            # File management tools
            "upload_file", "manage_headers", "manage_cookies"
        }

        # Check that all expected tools are present
        missing_tools = expected_tools - tool_names
        assert not missing_tools, f"Missing tools: {missing_tools}"

    @pytest.mark.asyncio
    async def test_tool_schemas(self, mcp_server):
        """Test that all tools have proper schemas."""
        for tool in await mcp_server.get_tools():
            # Check that tool has required attributes
            assert hasattr(tool, 'name')
            assert hasattr(tool, 'description')
            assert hasattr(tool, 'func')

            # Check that name is not empty
            assert tool.name.strip()
            assert tool.description.strip()

    @pytest.mark.asyncio
    async def test_concurrent_tool_execution(self, mcp_server):
        """Test concurrent execution of multiple tools."""
        with patch('mcp_server.server.get_metrics_summary') as mock_metrics:
            mock_metrics.return_value = {"test": "data"}

            tools = {tool.name: tool for tool in await mcp_server.get_tools()}
            metrics_tool = tools["metrics_summary"]

            # Execute multiple tools concurrently
            tasks = [
                metrics_tool.func(),
                metrics_tool.func(),
                metrics_tool.func()
            ]

            results = await asyncio.gather(*tasks)

            # All should succeed
            for result in results:
                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_error_propagation(self, mcp_server):
        """Test that errors are properly handled and propagated."""
        with patch('mcp_server.server.get_metrics_summary') as mock_metrics:
            mock_metrics.side_effect = Exception("Test error")

            tools = {tool.name: tool for tool in await mcp_server.get_tools()}
            metrics_tool = tools["metrics_summary"]

            result = await metrics_tool.func()

            assert result["success"] is False
            assert "Test error" in result["error"]


class TestMCPServerPerformance:
    """Performance tests for MCP server tools."""

    @pytest.fixture
    def mcp_server(self):
        """Create MCP server instance for testing."""
        return create_mcp_server()

    @pytest.mark.asyncio
    async def test_tool_response_time(self, mcp_server):
        """Test that tools respond within reasonable time limits."""
        import time

        with patch('mcp_server.server.get_metrics_summary') as mock_metrics:
            mock_metrics.return_value = {"test": "data"}

            tools = {tool.name: tool for tool in await mcp_server.get_tools()}
            metrics_tool = tools["metrics_summary"]

            start_time = time.time()
            result = await metrics_tool.func()
            end_time = time.time()

            # Should complete within 1 second for simple operations
            assert (end_time - start_time) < 1.0
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_memory_usage(self, mcp_server):
        """Test that tools don't cause memory leaks."""
        import gc
        import sys

        with patch('mcp_server.server.get_metrics_summary') as mock_metrics:
            mock_metrics.return_value = {"test": "data"}

            tools = {tool.name: tool for tool in await mcp_server.get_tools()}
            metrics_tool = tools["metrics_summary"]

            # Get initial memory usage
            gc.collect()
            initial_objects = len(gc.get_objects())

            # Execute tool multiple times
            for _ in range(10):
                await metrics_tool.func()

            # Check memory usage after
            gc.collect()
            final_objects = len(gc.get_objects())

            # Should not have significant memory growth
            object_growth = final_objects - initial_objects
            assert object_growth < 100, f"Memory leak detected: {object_growth} new objects"


class TestMCPServerSecurity:
    """Security tests for MCP server tools."""

    @pytest.fixture
    def mcp_server(self):
        """Create MCP server instance for testing."""
        return create_mcp_server()

    @pytest.mark.asyncio
    async def test_input_validation(self, mcp_server):
        """Test input validation for security."""
        tools = {tool.name: tool for tool in await mcp_server.get_tools()}

        # Test WebSocket connect with malicious URL
        websocket_connect = tools["websocket_connect"]
        result = await websocket_connect.func(
            url="javascript:alert('xss')",
            connection_id="test"
        )
        assert result["success"] is False

        # Test GraphQL query with invalid endpoint
        graphql_query = tools["graphql_query"]
        result = await graphql_query.func(
            endpoint="file:///etc/passwd",
            query="{ test }"
        )
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_sensitive_data_handling(self, mcp_server):
        """Test that sensitive data is properly handled."""
        with patch('mcp_server.server._auth_manager') as mock_auth_manager:
            mock_auth_manager_instance = AsyncMock()
            mock_auth_manager_instance.add_auth_method = AsyncMock()
            mock_auth_manager.return_value = mock_auth_manager_instance

            tools = {tool.name: tool for tool in await mcp_server.get_tools()}
            auth_configure = tools["auth_configure"]

            result = await auth_configure.func(
                auth_type="api_key",
                auth_name="test",
                config={"api_key": "secret-key", "password": "secret-pass"}
            )

            # Check that sensitive data is masked in response
            config_summary = result["config_summary"]
            assert config_summary["api_key"] == "***"
            assert config_summary["password"] == "***"
