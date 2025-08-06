"""
WebFetch MCP Server

An MCP (Model Context Protocol) server implementation that exposes WebFetch functionality
as tools for LLM consumption using the FastMCP framework.

This server provides web fetching capabilities including:
- Single URL fetching with various content types
- Batch URL fetching for concurrent requests  
- Enhanced fetching with advanced features like caching, circuit breakers, etc.
- Comprehensive error handling and validation
"""

__version__ = "0.1.0"
__author__ = "WebFetch MCP Team"

from .server import create_mcp_server, main

__all__ = ["create_mcp_server", "main"]
