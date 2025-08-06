#!/usr/bin/env python3
"""
WebFetch MCP Server Entry Point

This script provides the main entry point for running the WebFetch MCP server.
It can be run directly or imported as a module.

Usage:
    python -m mcp_server
    python mcp_server/__main__.py
"""

import sys
import logging
from .server import main

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Server error: {e}")
        sys.exit(1)
