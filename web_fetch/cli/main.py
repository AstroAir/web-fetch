#!/usr/bin/env python3
"""
Command-line interface for the web_fetch library.

This module provides a comprehensive CLI for fetching URLs with support for
different content types, batch processing, streaming, various output formats,
and enhanced formatting when available.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Callable, List, Optional

# Import formatting utilities
from .formatting import Formatter, create_formatter, print_banner, print_help_footer
# Import utility functions
from .utils import parse_headers, load_urls_from_file
from .output import format_output
from .parsers import create_parser
from .handlers import (
    determine_urls, validate_and_normalize_urls, create_fetch_config,
    get_content_type, print_verbose_info, handle_crawler_status,
    handle_search_operation, handle_crawler_operations, handle_regular_fetching
)

try:
    from pydantic import HttpUrl
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    HttpUrl = str

try:
    from .. import (  # Crawler functionality
        ContentType,
        CrawlerCapability,
        CrawlerType,
        FetchConfig,
        FetchRequest,
        ProgressInfo,
        StreamingConfig,
        StreamingWebFetcher,
        StreamRequest,
        WebFetcher,
        configure_crawler,
        crawler_crawl_website,
        crawler_fetch_url,
        crawler_fetch_urls,
        crawler_search_web,
        download_file,
        fetch_url,
        fetch_urls,
        fetch_with_cache,
        get_crawler_status,
    )
    WEB_FETCH_AVAILABLE = True
except ImportError as e:
    WEB_FETCH_AVAILABLE = False
    print(f"Warning: Web-fetch core functionality not available: {e}")
    print("Please install missing dependencies: pip install -e .")
    sys.exit(1)









def create_progress_callback(verbose: bool = False) -> Callable[[ProgressInfo], None]:
    """Create a progress callback for streaming downloads."""

    def progress_callback(progress: ProgressInfo) -> None:
        if not verbose:
            return

        if progress.total_bytes:
            percentage = progress.percentage or 0
            bar_length = 30
            filled_length = int(bar_length * percentage / 100)
            bar = "█" * filled_length + "-" * (bar_length - filled_length)

            print(
                f"\r[{bar}] {percentage:.1f}% | "
                f"{progress.bytes_downloaded:,} / {progress.total_bytes:,} bytes | "
                f"{progress.speed_human}",
                end="",
                flush=True,
            )
        else:
            print(
                f"\rDownloaded: {progress.bytes_downloaded:,} bytes | "
                f"{progress.speed_human}",
                end="",
                flush=True,
            )

    return progress_callback


async def main() -> None:
    """Main CLI function with enhanced formatting."""
    # Print banner
    print_banner("Web-Fetch CLI")

    parser = create_parser()
    args = parser.parse_args()

    # Create formatter
    formatter = create_formatter(verbose=args.verbose)

    # Handle components subcommand
    if getattr(args, "func", None):
        # Subcommands provide an async command coroutine to run in this loop
        command = args.func
        if asyncio.iscoroutinefunction(command):
            await command(args)
        else:
            # Back-compat in case a sync function is provided
            command(args)
        return

    # Handle crawler status command
    if handle_crawler_status(args, formatter):
        return

    # Handle search operation
    if handle_search_operation(args, formatter):
        return

    # Determine URLs to fetch
    urls = determine_urls(args, formatter)

    # Parse content type and create configuration
    content_type = get_content_type(args)
    headers = parse_headers(args.headers)
    config = create_fetch_config(args)

    # URL validation and normalization
    urls = validate_and_normalize_urls(urls, args, formatter)

    # Print verbose information
    print_verbose_info(args, urls, formatter)

    try:
        # Initialize results variable with proper type
        results: Any = None

        # Handle crawler operations
        if args.use_crawler:
            results = await handle_crawler_operations(args, urls, formatter)
        else:
            results = await handle_regular_fetching(args, urls, config, content_type, headers)

        # Format and output results
        output = format_output(results, args.format, args.verbose)

        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
            if args.verbose:
                print(f"Results written to {args.output}")
        else:
            print(output)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
