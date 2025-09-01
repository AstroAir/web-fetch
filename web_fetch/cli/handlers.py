"""
URL processing and request handling functions for CLI operations.

This module contains URL processing, validation, and request handling logic
extracted from main.py to improve modularity and maintainability.
"""

import sys
from typing import Any, List
from pathlib import Path

from .utils import load_urls_from_file, parse_headers
from .formatting import Formatter


def determine_urls(args, formatter: Formatter) -> List[str]:
    """
    Determine URLs to fetch from command line arguments.

    Args:
        args: Parsed command line arguments
        formatter: Formatter instance for output

    Returns:
        List of URLs to process

    Raises:
        SystemExit: If no URLs are provided or found
    """
    urls = []
    if args.batch:
        formatter.print_info(f"Loading URLs from {args.batch}")
        urls = load_urls_from_file(args.batch)
        formatter.print_success(f"Loaded {len(urls)} URLs")
    elif args.urls:
        urls = args.urls
    else:
        formatter.print_error("No URLs provided. Use positional arguments or --batch option.")
        from .formatting import print_help_footer
        print_help_footer()
        sys.exit(1)

    if not urls:
        formatter.print_error("No valid URLs found to process")
        sys.exit(1)

    return urls


def validate_and_normalize_urls(urls: List[str], args, formatter: Formatter) -> List[str]:
    """
    Validate and normalize URLs based on command line options.

    Args:
        urls: List of URLs to process
        args: Parsed command line arguments
        formatter: Formatter instance for output

    Returns:
        List of validated and normalized URLs

    Raises:
        SystemExit: If invalid URLs are found during validation
    """
    processed_urls = urls.copy()

    # URL validation
    if args.validate_urls:
        try:
            from .. import is_valid_url
            invalid_urls = [url for url in processed_urls if not is_valid_url(url)]
            if invalid_urls:
                formatter.print_error(f"Invalid URLs found: {invalid_urls}")
                sys.exit(1)
        except ImportError:
            formatter.print_warning("URL validation not available - skipping validation")

    # URL normalization
    if args.normalize_urls:
        try:
            from .. import normalize_url
            processed_urls = [normalize_url(url) for url in processed_urls]
        except ImportError:
            formatter.print_warning("URL normalization not available - skipping normalization")

    return processed_urls


def create_fetch_config(args):
    """
    Create FetchConfig from command line arguments.

    Args:
        args: Parsed command line arguments

    Returns:
        FetchConfig instance
    """
    try:
        from .. import FetchConfig
        return FetchConfig(
            total_timeout=args.timeout,
            max_concurrent_requests=args.concurrent,
            max_retries=args.retries,
            verify_ssl=not args.no_verify_ssl,
        )
    except ImportError:
        # Fallback for when core modules aren't available
        return None


def get_content_type(args):
    """
    Get ContentType enum value from command line arguments.

    Args:
        args: Parsed command line arguments

    Returns:
        ContentType enum value
    """
    try:
        from .. import ContentType
        content_type_map = {
            "text": ContentType.TEXT,
            "json": ContentType.JSON,
            "html": ContentType.HTML,
            "raw": ContentType.RAW,
        }
        return content_type_map[args.type]
    except ImportError:
        # Fallback for when core modules aren't available
        return args.type


def print_verbose_info(args, urls: List[str], formatter: Formatter) -> None:
    """
    Print verbose information about the fetch operation.

    Args:
        args: Parsed command line arguments
        urls: List of URLs to process
        formatter: Formatter instance for output
    """
    if args.verbose:
        formatter.print_info(
            f"Fetching {len(urls)} URL(s) with {args.concurrent} max concurrent requests"
        )
        formatter.print_info(f"Timeout: {args.timeout}s, Retries: {args.retries}")
        if args.stream:
            formatter.print_info(f"Streaming mode: chunk size {args.chunk_size} bytes")
        if args.cache:
            formatter.print_info(f"Caching enabled: TTL {args.cache_ttl}s")


def handle_crawler_status(args, formatter: Formatter) -> bool:
    """
    Handle crawler status command.

    Args:
        args: Parsed command line arguments
        formatter: Formatter instance for output

    Returns:
        True if crawler status was handled, False otherwise
    """
    if not args.crawler_status:
        return False

    try:
        from .. import get_crawler_status
        with formatter.create_status("Checking crawler API status..."):
            status = get_crawler_status()

        if hasattr(formatter, 'print_crawler_status'):
            formatter.print_crawler_status(status)
        else:
            formatter.print_json(status, "Crawler API Status")
        return True
    except ImportError:
        formatter.print_error("Crawler functionality not available")
        return True


def handle_search_operation(args, formatter: Formatter) -> bool:
    """
    Handle search operation.

    Args:
        args: Parsed command line arguments
        formatter: Formatter instance for output

    Returns:
        True if search was handled, False otherwise
    """
    if args.crawler_operation != "search" or not args.search_query:
        return False

    try:
        from .. import crawler_search_web, CrawlerType
        from .output import format_output

        formatter.print_info(f"Searching for: {args.search_query}")

        crawler_type = None
        if args.crawler_type:
            crawler_type = CrawlerType(args.crawler_type)

        with formatter.create_status("Performing web search..."):
            result = crawler_search_web(
                args.search_query,
                max_results=args.max_pages or 5,
                crawler_type=crawler_type,
            )

        # Display results
        if args.format == "json":
            formatter.print_json(result, "Search Results")
        else:
            # Format as table for better readability
            if result.get("results"):
                table_data = []
                for r in result.get("results", []):
                    table_data.append({
                        "title": r.get("title", "")[:60] + "..." if len(r.get("title", "")) > 60 else r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("snippet", "")[:80] + "..." if len(r.get("snippet", "")) > 80 else r.get("snippet", "")
                    })
                formatter.print_table(table_data, "Search Results")
            else:
                formatter.print_warning("No search results found")

        # Save to file if specified
        if args.output:
            output = format_output(result, args.format, args.verbose)
            with open(args.output, "w") as f:
                f.write(output)
            formatter.print_success(f"Search results written to {args.output}")

        return True
    except ImportError:
        formatter.print_error("Search functionality not available")
        return True
    except Exception as e:
        formatter.print_error(f"Search failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


async def handle_crawler_operations(args, urls: List[str], formatter: Formatter) -> Any:
    """
    Handle crawler-based operations.

    Args:
        args: Parsed command line arguments
        urls: List of URLs to process
        formatter: Formatter instance for output

    Returns:
        Results from crawler operations
    """
    try:
        from .. import (
            crawler_crawl_website, crawler_fetch_url, crawler_fetch_urls,
            CrawlerType, CrawlerCapability
        )

        crawler_type = None
        if args.crawler_type:
            crawler_type = CrawlerType(args.crawler_type)

        if args.crawler_operation == "crawl":
            # Website crawling
            if len(urls) > 1:
                formatter.print_error("Crawl operation only supports single URL")
                sys.exit(1)

            return await crawler_crawl_website(
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
            return await crawler_fetch_url(
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
            return await crawler_fetch_urls(
                list(urls),
                use_crawler=True,
                crawler_type=crawler_type,
                operation=CrawlerCapability(args.crawler_operation),
                return_format="markdown",
                include_metadata=True,
                timeout=args.timeout,
                max_retries=args.retries,
            )
    except ImportError:
        formatter.print_error("Crawler functionality not available")
        sys.exit(1)


async def handle_regular_fetching(args, urls: List[str], config, content_type, headers) -> Any:
    """
    Handle regular HTTP fetching operations.

    Args:
        args: Parsed command line arguments
        urls: List of URLs to process
        config: FetchConfig instance
        content_type: ContentType enum value
        headers: Parsed headers dictionary

    Returns:
        Results from fetch operations
    """
    try:
        from .. import WebFetcher, FetchRequest, BatchFetchRequest
        from pydantic import HttpUrl

        if len(urls) == 1:
            # Single URL
            fetch_request = FetchRequest(
                url=HttpUrl(urls[0]),
                method=args.method,
                headers=headers,
                data=args.data,
                content_type=content_type,
            )

            async with WebFetcher(config) as fetcher:
                return await fetcher.fetch_single(fetch_request)
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

            batch_request = BatchFetchRequest(requests=requests, config=config)

            async with WebFetcher(config) as fetcher:
                return await fetcher.fetch_batch(batch_request)
    except ImportError:
        # Fallback when core modules aren't available
        return {"error": "Core fetching functionality not available"}
