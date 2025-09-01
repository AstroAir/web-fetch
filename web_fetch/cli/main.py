#!/usr/bin/env python3
"""
Command-line interface for the web_fetch library.

This module provides a simple CLI for fetching URLs with various options
and output formats.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Callable, List, Optional

from pydantic import HttpUrl

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


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="Modern async web fetcher with AIOHTTP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
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
        """,
    )

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

    # Input/Output options
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

    # Request configuration
    parser.add_argument("--method", default="GET", help="HTTP method (default: GET)")

    parser.add_argument("--data", help="Request data (for POST/PUT requests)")

    parser.add_argument(
        "--headers",
        action="append",
        help='Custom headers in format "Key: Value" (can be used multiple times)',
    )

    # Timing and concurrency
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

    # SSL and verification
    parser.add_argument(
        "--no-verify-ssl",
        action="store_true",
        help="Disable SSL certificate verification",
    )

    # Streaming options
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

    # Caching options
    parser.add_argument("--cache", action="store_true", help="Enable response caching")

    parser.add_argument(
        "--cache-ttl", type=int, default=300, help="Cache TTL in seconds (default: 300)"
    )

    # URL utilities
    parser.add_argument(
        "--validate-urls", action="store_true", help="Validate URLs before fetching"
    )

    parser.add_argument(
        "--normalize-urls", action="store_true", help="Normalize URLs before fetching"
    )

    # Crawler API options
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

    # Verbose output
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )

    # Add subcommands
    subparsers = parser.add_subparsers(dest="command")
    try:
        from .components import add_components_subparser
        add_components_subparser(subparsers)
    except Exception:
        # Keep CLI working even if components module not present
        pass
    return parser


def parse_headers(header_strings: Optional[List[str]]) -> dict:
    """
    Parse header strings into a dictionary.

    Converts command-line header arguments in "key:value" format into
    a dictionary suitable for HTTP requests.

    Args:
        header_strings: List of header strings in "key:value" format,
                       or None if no headers provided

    Returns:
        Dictionary with header names as keys and values as strings.
        Empty dict if no valid headers provided.

    Note:
        Invalid header formats are logged to stderr but don't cause
        the function to fail. Only valid headers are included in result.

    Example:
        ```python
        headers = parse_headers(["Content-Type:application/json", "Authorization:Bearer token"])
        # Returns: {"Content-Type": "application/json", "Authorization": "Bearer token"}
        ```
    """
    headers = {}
    if header_strings:
        for header_str in header_strings:
            if ":" in header_str:
                key, value = header_str.split(":", 1)
                headers[key.strip()] = value.strip()
            else:
                print(f"Warning: Invalid header format: {header_str}", file=sys.stderr)
    return headers


def load_urls_from_file(file_path: Path) -> List[str]:
    """
    Load URLs from a text file.

    Reads URLs from a text file, one per line. Supports comments (lines
    starting with #) and automatically filters out empty lines.

    Args:
        file_path: Path to the text file containing URLs

    Returns:
        List of URL strings found in the file

    Raises:
        SystemExit: If file cannot be read or doesn't exist

    Note:
        - Empty lines are ignored
        - Lines starting with # are treated as comments and ignored
        - Leading/trailing whitespace is stripped from URLs

    Example file format:
        ```
        # API endpoints
        https://api.example.com/users
        https://api.example.com/posts

        # Static resources
        https://cdn.example.com/image.jpg
        ```
    """
    try:
        with open(file_path, "r") as f:
            urls = [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]
        return urls
    except FileNotFoundError:
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file {file_path}: {e}", file=sys.stderr)
        sys.exit(1)


def format_output(results: Any, format_type: str, verbose: bool = False) -> str:
    """Format results for output."""
    if format_type == "json":
        # Convert results to JSON-serializable format
        if hasattr(results, "results"):  # BatchFetchResult
            output = {
                "total_requests": results.total_requests,
                "successful_requests": results.successful_requests,
                "failed_requests": results.failed_requests,
                "success_rate": results.success_rate,
                "total_time": results.total_time,
                "results": [],
            }
            for result in results.results:
                output["results"].append(
                    {
                        "url": result.url,
                        "status_code": result.status_code,
                        "success": result.is_success,
                        "response_time": result.response_time,
                        "content_length": (
                            len(str(result.content)) if result.content else 0
                        ),
                        "error": result.error,
                        "retry_count": result.retry_count,
                    }
                )
        else:  # Single FetchResult
            output = {
                "url": results.url,
                "status_code": results.status_code,
                "success": results.is_success,
                "response_time": results.response_time,
                "content": results.content if verbose else None,
                "content_length": len(str(results.content)) if results.content else 0,
                "error": results.error,
                "retry_count": results.retry_count,
            }
        return json.dumps(output, indent=2)

    elif format_type == "summary":
        if hasattr(results, "results"):  # BatchFetchResult
            output_lines = []
            output_lines.append(f"Batch Results Summary:")
            output_lines.append(f"  Total requests: {results.total_requests}")
            output_lines.append(f"  Successful: {results.successful_requests}")
            output_lines.append(f"  Failed: {results.failed_requests}")
            output_lines.append(f"  Success rate: {results.success_rate:.1f}%")
            output_lines.append(f"  Total time: {results.total_time:.2f}s")
            output_lines.append("")

            for i, result in enumerate(results.results, 1):
                status = "✓" if result.is_success else "✗"
                output_lines.append(
                    f"{i:3d}. {status} {result.url} ({result.status_code}) {result.response_time:.2f}s"
                )
                if result.error:
                    output_lines.append(f"     Error: {result.error}")
            return "\n".join(output_lines)
        else:  # Single FetchResult
            status = "✓" if results.is_success else "✗"
            output_lines = [
                f"{status} {results.url}",
                f"Status: {results.status_code}",
                f"Response time: {results.response_time:.2f}s",
                f"Content length: {len(str(results.content)) if results.content else 0}",
            ]
            if results.error:
                output_lines.append(f"Error: {results.error}")
            return "\n".join(output_lines)

    elif format_type == "detailed":
        # Similar to summary but with more details
        return (
            format_output(results, "summary", verbose)
            + "\n\nContent preview:\n"
            + str(results.content)[:500]
            + "..."
        )

    else:
        # Default to summary format
        return format_output(results, "summary", verbose)


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
    """Main CLI function."""
    parser = create_parser()
    args = parser.parse_args()

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
    if args.crawler_status:
        status = get_crawler_status()
        print(json.dumps(status, indent=2))
        return

    # Handle search operation
    if args.crawler_operation == "search" and args.search_query:
        if args.verbose:
            print(f"Searching for: {args.search_query}")

        try:
            crawler_type = None
            if args.crawler_type:
                crawler_type = CrawlerType(args.crawler_type)

            result = await crawler_search_web(
                args.search_query,
                max_results=args.max_pages or 5,
                crawler_type=crawler_type,
            )

            output = format_output(result, args.format, args.verbose)

            if args.output:
                with open(args.output, "w") as f:
                    f.write(output)
                if args.verbose:
                    print(f"Search results written to {args.output}")
            else:
                print(output)
            return

        except Exception as e:
            print(f"Search failed: {e}", file=sys.stderr)
            sys.exit(1)

    # Determine URLs to fetch
    urls = []
    if args.batch:
        urls = load_urls_from_file(args.batch)
    elif args.urls:
        urls = args.urls
    else:
        parser.print_help()
        sys.exit(1)

    if not urls:
        print("Error: No URLs to fetch", file=sys.stderr)
        sys.exit(1)

    # Parse content type
    content_type_map = {
        "text": ContentType.TEXT,
        "json": ContentType.JSON,
        "html": ContentType.HTML,
        "raw": ContentType.RAW,
    }
    content_type = content_type_map[args.type]

    # Parse headers
    headers = parse_headers(args.headers)

    # Create configuration
    config = FetchConfig(
        total_timeout=args.timeout,
        max_concurrent_requests=args.concurrent,
        max_retries=args.retries,
        verify_ssl=not args.no_verify_ssl,
    )

    # URL validation and normalization
    if args.validate_urls:
        from .. import is_valid_url

        invalid_urls = [url for url in urls if not is_valid_url(url)]
        if invalid_urls:
            print(f"Error: Invalid URLs found: {invalid_urls}", file=sys.stderr)
            sys.exit(1)

    if args.normalize_urls:
        from .. import normalize_url

        urls = [normalize_url(url) for url in urls]

    if args.verbose:
        print(
            f"Fetching {len(urls)} URL(s) with {args.concurrent} max concurrent requests"
        )
        print(f"Timeout: {args.timeout}s, Retries: {args.retries}")
        if args.stream:
            print(f"Streaming mode: chunk size {args.chunk_size} bytes")
        if args.cache:
            print(f"Caching enabled: TTL {args.cache_ttl}s")
        print()

    try:
        # Initialize results variable with proper type
        results: Any = None

        # Handle crawler operations
        if args.use_crawler:
            crawler_type = None
            if args.crawler_type:
                crawler_type = CrawlerType(args.crawler_type)

            if args.crawler_operation == "crawl":
                # Website crawling
                if len(urls) > 1:
                    print(
                        "Error: Crawl operation only supports single URL",
                        file=sys.stderr,
                    )
                    sys.exit(1)

                results = await crawler_crawl_website(
                    urls[0],
                    max_pages=args.max_pages,
                    max_depth=args.max_depth,
                    crawler_type=crawler_type,
                    return_format="markdown",
                    include_metadata=True,
                    include_links=True,
                )

            elif len(urls) == 1:
                # Single URL with crawler
                results = await crawler_fetch_url(
                    urls[0],
                    use_crawler=True,
                    crawler_type=crawler_type,
                    operation=CrawlerCapability(args.crawler_operation),
                    return_format="markdown",
                    include_metadata=True,
                    timeout=args.timeout,
                    max_retries=args.retries,
                )
            else:
                # Multiple URLs with crawler
                results = await crawler_fetch_urls(
                    list(urls),
                    use_crawler=True,
                    crawler_type=crawler_type,
                    operation=CrawlerCapability(args.crawler_operation),
                    return_format="markdown",
                    include_metadata=True,
                    timeout=args.timeout,
                    max_retries=args.retries,
                )

        # Handle streaming downloads
        elif args.stream and args.output:
            if len(urls) > 1:
                print(
                    "Error: Streaming mode only supports single URL downloads",
                    file=sys.stderr,
                )
                sys.exit(1)

            output_path = Path(args.output)
            progress_callback = create_progress_callback(args.progress or args.verbose)

            streaming_config = StreamingConfig(
                chunk_size=args.chunk_size,
                enable_progress=args.progress or args.verbose,
                max_file_size=args.max_file_size,
            )

            request = StreamRequest(
                url=HttpUrl(urls[0]),
                method=args.method,
                headers=headers,
                data=args.data,
                output_path=output_path,
                streaming_config=streaming_config,
            )

            streaming_fetcher: StreamingWebFetcher = StreamingWebFetcher(config)
            async with streaming_fetcher:
                results = await streaming_fetcher.stream_fetch(
                    request, progress_callback
                )

                if args.progress or args.verbose:
                    print()  # New line after progress bar

        # Handle caching
        elif args.cache and len(urls) == 1:
            from ..models import CacheConfig

            cache_config = CacheConfig(ttl_seconds=args.cache_ttl)
            results = await fetch_with_cache(
                urls[0], content_type, cache_config, config
            )

        # Regular fetching
        elif len(urls) == 1:
            # Single URL
            fetch_request = FetchRequest(
                url=HttpUrl(urls[0]),
                method=args.method,
                headers=headers,
                data=args.data,
                content_type=content_type,
            )

            async with WebFetcher(config) as fetcher:
                results = await fetcher.fetch_single(fetch_request)
        else:
            # Multiple URLs
            requests = [
                FetchRequest(
                    url=HttpUrl(url),
                    method=args.method,
                    headers=headers,
                    data=args.data,
                    content_type=content_type,
                )
                for url in urls
            ]

            from ..models import BatchFetchRequest

            batch_request = BatchFetchRequest(requests=requests, config=config)

            async with WebFetcher(config) as fetcher:
                results = await fetcher.fetch_batch(batch_request)

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
