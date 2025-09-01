"""
Argument parsing functions for CLI operations.

This module contains argument parsing logic extracted from main.py to improve
modularity and maintainability. Functions handle CLI argument configuration
and parsing.
"""

import argparse
from pathlib import Path


def add_basic_arguments(parser: argparse.ArgumentParser) -> None:
    """Add basic URL and content type arguments."""
    # URL arguments
    parser.add_argument(
        "urls", nargs="*", help="URLs to fetch (or use --batch for file input)"
    )

    # Content type options
    parser.add_argument(
        "-t",
        "--type",
        choices=["text", "json", "html", "raw"],
        default="text",
        help="Content type for parsing (default: text)",
    )


def add_io_arguments(parser: argparse.ArgumentParser) -> None:
    """Add input/output related arguments."""
    parser.add_argument(
        "--batch", type=Path, help="File containing URLs to fetch (one per line)"
    )

    parser.add_argument(
        "-o", "--output", type=Path, help="Output file for results (default: stdout)"
    )

    parser.add_argument(
        "--format",
        choices=["json", "summary", "detailed"],
        default="summary",
        help="Output format (default: summary)",
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )


def add_request_arguments(parser: argparse.ArgumentParser) -> None:
    """Add HTTP request configuration arguments."""
    parser.add_argument("--method", default="GET", help="HTTP method (default: GET)")

    parser.add_argument("--data", help="Request data (for POST/PUT requests)")

    parser.add_argument(
        "--headers",
        action="append",
        help='Custom headers in format "Key: Value" (can be used multiple times)',
    )


def add_timing_arguments(parser: argparse.ArgumentParser) -> None:
    """Add timing and concurrency arguments."""
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Request timeout in seconds (default: 30)",
    )

    parser.add_argument(
        "--concurrent",
        type=int,
        default=10,
        help="Maximum concurrent requests (default: 10)",
    )

    parser.add_argument(
        "--retries", type=int, default=3, help="Maximum retry attempts (default: 3)"
    )


def add_ssl_arguments(parser: argparse.ArgumentParser) -> None:
    """Add SSL and verification arguments."""
    parser.add_argument(
        "--no-verify-ssl",
        action="store_true",
        help="Disable SSL certificate verification",
    )


def add_streaming_arguments(parser: argparse.ArgumentParser) -> None:
    """Add streaming and download arguments."""
    parser.add_argument(
        "--stream", action="store_true", help="Use streaming mode for downloads"
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=8192,
        help="Chunk size for streaming (default: 8192 bytes)",
    )

    parser.add_argument(
        "--progress", action="store_true", help="Show progress bar for downloads"
    )

    parser.add_argument(
        "--max-file-size", type=int, help="Maximum file size for downloads (bytes)"
    )


def add_caching_arguments(parser: argparse.ArgumentParser) -> None:
    """Add caching related arguments."""
    parser.add_argument("--cache", action="store_true", help="Enable response caching")

    parser.add_argument(
        "--cache-ttl", type=int, default=300, help="Cache TTL in seconds (default: 300)"
    )


def add_url_utility_arguments(parser: argparse.ArgumentParser) -> None:
    """Add URL utility arguments."""
    parser.add_argument(
        "--validate-urls", action="store_true", help="Validate URLs before fetching"
    )

    parser.add_argument(
        "--normalize-urls", action="store_true", help="Normalize URLs before fetching"
    )


def add_crawler_arguments(parser: argparse.ArgumentParser) -> None:
    """Add crawler API arguments."""
    parser.add_argument(
        "--use-crawler",
        action="store_true",
        help="Use crawler APIs instead of standard HTTP fetching",
    )

    parser.add_argument(
        "--crawler-type",
        choices=["firecrawl", "spider", "tavily", "anycrawl"],
        help="Specific crawler API to use",
    )

    parser.add_argument(
        "--crawler-operation",
        choices=["scrape", "crawl", "search", "extract"],
        default="scrape",
        help="Crawler operation type (default: scrape)",
    )

    parser.add_argument("--search-query", help="Search query (for search operations)")

    parser.add_argument("--max-pages", type=int, help="Maximum pages to crawl")

    parser.add_argument("--max-depth", type=int, help="Maximum crawl depth")

    parser.add_argument(
        "--crawler-status", action="store_true", help="Show crawler API status and exit"
    )


def add_subcommands(parser: argparse.ArgumentParser) -> None:
    """Add subcommands to the parser."""
    subparsers = parser.add_subparsers(dest="command")
    try:
        from .components import add_components_subparser
        add_components_subparser(subparsers)
    except Exception:
        # Keep CLI working even if components module not present
        pass


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser with enhanced formatting."""
    parser = argparse.ArgumentParser(
        description="🌐 Modern async web fetcher with enhanced formatting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
✨ Examples:
  # Standard HTTP fetching
  %(prog)s https://httpbin.org/get
  %(prog)s -t json https://httpbin.org/json
  %(prog)s -t html -o output.json https://example.com
  %(prog)s --batch urls.txt
  %(prog)s --concurrent 5 --timeout 30 https://httpbin.org/delay/5

  # Crawler API usage
  %(prog)s --use-crawler https://example.com
  %(prog)s --use-crawler --crawler-type firecrawl https://example.com
  %(prog)s --use-crawler --crawler-operation crawl --max-pages 10 https://example.com
  %(prog)s --crawler-operation search --search-query "Python web scraping"
  %(prog)s --crawler-status

💡 Use --verbose for enhanced output formatting and progress information
        """,
    )

    # Add argument groups using modular functions
    add_basic_arguments(parser)
    add_io_arguments(parser)
    add_request_arguments(parser)
    add_timing_arguments(parser)
    add_ssl_arguments(parser)
    add_streaming_arguments(parser)
    add_caching_arguments(parser)
    add_url_utility_arguments(parser)
    add_crawler_arguments(parser)
    add_subcommands(parser)

    return parser
