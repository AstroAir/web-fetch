#!/usr/bin/env python3
"""
WebFetch MCP Server Launcher

This script provides a convenient way to launch the WebFetch MCP server
with various configuration options.

Usage:
    python run_mcp_server.py [--transport stdio|http] [--host HOST] [--port PORT]
"""

import argparse
import logging
import sys
from mcp_server import create_mcp_server

def setup_logging(level: str = "INFO"):
    """Set up logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stderr)
        ]
    )

def main():
    """Main entry point for the MCP server launcher."""
    parser = argparse.ArgumentParser(
        description="WebFetch MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run with STDIO transport (default)
    python run_mcp_server.py
    
    # Run with HTTP transport
    python run_mcp_server.py --transport http --host 127.0.0.1 --port 8080
    
    # Run with debug logging
    python run_mcp_server.py --log-level DEBUG
        """
    )
    
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport protocol to use (default: stdio)"
    )
    
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to for HTTP transport (default: 127.0.0.1)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to bind to for HTTP transport (default: 8080)"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    try:
        # Create the MCP server
        mcp = create_mcp_server()
        
        logger.info(f"Starting WebFetch MCP Server with {args.transport} transport")
        
        if args.transport == "stdio":
            logger.info("Server running on STDIO transport")
            mcp.run()
        elif args.transport == "http":
            logger.info(f"Server running on HTTP transport at http://{args.host}:{args.port}")
            mcp.run(transport="http", host=args.host, port=args.port)
            
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
