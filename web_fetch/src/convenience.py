"""
Convenience functions for quick web fetching operations.

This module provides simple, high-level functions for common web fetching tasks
without requiring explicit class instantiation or session management.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, List, Optional

from pydantic import HttpUrl

from ..models import (
    BatchFetchRequest,
    BatchFetchResult,
    ContentType,
    FetchConfig,
    FetchRequest,
    FetchResult,
    ProgressInfo,
    StreamingConfig,
    StreamRequest,
    StreamResult,
)
from .core_fetcher import WebFetcher
from .streaming_fetcher import StreamingWebFetcher


async def fetch_url(
    url: str,
    content_type: ContentType = ContentType.TEXT,
    config: Optional[FetchConfig] = None,
) -> FetchResult:
    """
    Convenience function to fetch a single URL.

    A simple, high-level interface for fetching a single URL without needing
    to manage WebFetcher instances or create FetchRequest objects manually.
    Automatically handles session lifecycle and resource cleanup.

    Args:
        url: URL to fetch as a string. Must be a valid HTTP/HTTPS URL.
        content_type: How to parse the response content. Defaults to TEXT.
                     Options: RAW (bytes), TEXT (string), JSON (dict/list), HTML (BeautifulSoup)
        config: Optional FetchConfig object for customizing timeouts, retries,
               and other request parameters. Uses defaults if None.

    Returns:
        FetchResult object containing:
        - status_code: HTTP response status code
        - headers: Response headers as dict
        - content: Parsed content based on content_type
        - response_time: Request duration in seconds
        - error: Error message if request failed, None if successful

    Raises:
        WebFetchError: If URL is invalid or request configuration is invalid
        TimeoutError: If request times out
        ConnectionError: If connection fails
        HTTPError: If server returns error status code

    Example:
        ```python
        # Fetch JSON data
        result = await fetch_url("https://api.example.com/data", ContentType.JSON)
        if result.is_success:
            data = result.content  # Already parsed as dict/list
        ```
    """
    request = FetchRequest(url=HttpUrl(url), content_type=content_type)

    async with WebFetcher(config) as fetcher:
        return await fetcher.fetch_single(request)


async def fetch_urls(
    urls: List[str],
    content_type: ContentType = ContentType.TEXT,
    config: Optional[FetchConfig] = None,
) -> BatchFetchResult:
    """
    Convenience function to fetch multiple URLs concurrently.

    Fetches multiple URLs in parallel using asyncio concurrency, with automatic
    session management and resource cleanup. All requests use the same content
    type and configuration.

    Args:
        urls: List of URL strings to fetch. All must be valid HTTP/HTTPS URLs.
        content_type: How to parse all response content. Defaults to TEXT.
                     All URLs will be parsed using the same content type.
        config: Optional FetchConfig object for customizing timeouts, retries,
               concurrency limits, and other parameters. Uses defaults if None.

    Returns:
        BatchFetchResult object containing:
        - results: List of FetchResult objects, one per URL
        - success_rate: Percentage of successful requests (0.0-1.0)
        - total_time: Total time for all requests in seconds
        - failed_count: Number of failed requests
        - successful_count: Number of successful requests

    Raises:
        WebFetchError: If any URL is invalid or configuration is invalid

    Note:
        Individual request failures don't raise exceptions - they're captured
        in the corresponding FetchResult.error field. Check each result's
        is_success property or the batch success_rate.

    Example:
        ```python
        urls = ["https://api1.com/data", "https://api2.com/data"]
        batch_result = await fetch_urls(urls, ContentType.JSON)

        print(f"Success rate: {batch_result.success_rate:.1%}")
        for i, result in enumerate(batch_result.results):
            if result.is_success:
                print(f"URL {i}: {result.status_code}")
            else:
                print(f"URL {i} failed: {result.error}")
        ```
    """
    requests = [
        FetchRequest(url=HttpUrl(url), content_type=content_type) for url in urls
    ]
    batch_request = BatchFetchRequest(requests=requests, config=config)

    async with WebFetcher(config) as fetcher:
        return await fetcher.fetch_batch(batch_request)


async def download_file(
    url: str,
    output_path: Path,
    chunk_size: int = 8192,
    progress_callback: Optional[Callable[[ProgressInfo], None]] = None,
    config: Optional[FetchConfig] = None,
) -> StreamResult:
    """
    Convenience function to download a file with progress tracking.

    Downloads a file from a URL using streaming to avoid loading the entire
    file into memory. Supports progress callbacks for real-time download
    monitoring and automatic directory creation.

    Args:
        url: URL to download as a string. Must be a valid HTTP/HTTPS URL.
        output_path: Path object specifying where to save the downloaded file.
                    Parent directories will be created if they don't exist.
        chunk_size: Size of chunks to read in bytes. Defaults to 8192 (8KB).
                   Larger chunks may be faster but use more memory.
        progress_callback: Optional callback function that receives ProgressInfo
                         objects with download progress. Called after each chunk.
        config: Optional FetchConfig object for customizing timeouts, retries,
               and other parameters. Uses defaults if None.

    Returns:
        StreamResult object containing:
        - bytes_downloaded: Total bytes downloaded
        - download_speed: Average download speed in bytes/second
        - response_time: Total download time in seconds
        - status_code: HTTP response status code
        - headers: Response headers as dict
        - error: Error message if download failed, None if successful

    Raises:
        WebFetchError: If URL is invalid or configuration is invalid
        TimeoutError: If download times out
        ConnectionError: If connection fails
        IOError: If file cannot be written to output_path

    Example:
        ```python
        def progress_handler(progress: ProgressInfo):
            if progress.total_bytes:
                percent = progress.percentage or 0
                print(f"Downloaded: {percent:.1f}% ({progress.speed_human})")

        result = await download_file(
            "https://example.com/large-file.zip",
            Path("downloads/file.zip"),
            chunk_size=16384,
            progress_callback=progress_handler
        )

        if result.is_success:
            print(f"Downloaded {result.bytes_downloaded:,} bytes")
        ```
    """
    streaming_config = StreamingConfig(
        chunk_size=chunk_size, enable_progress=progress_callback is not None
    )

    request = StreamRequest(
        url=HttpUrl(url), output_path=output_path, streaming_config=streaming_config
    )

    async with StreamingWebFetcher(config) as streaming_fetcher:
        return await streaming_fetcher.stream_fetch(request, progress_callback)


async def fetch_with_cache(
    url: str,
    content_type: ContentType = ContentType.TEXT,
    cache_config: Optional[Any] = None,  # CacheConfig from utils
    config: Optional[FetchConfig] = None,
) -> FetchResult:
    """
    Convenience function to fetch a URL with caching.

    Fetches a URL and caches the response for future requests. If the URL
    has been cached and the cache entry is still valid (not expired), returns
    the cached response instead of making a new HTTP request.

    Args:
        url: URL to fetch as a string. Must be a valid HTTP/HTTPS URL.
        content_type: How to parse the response content. Defaults to TEXT.
        cache_config: Optional CacheConfig object specifying cache behavior
                     including TTL, max size, and compression settings.
                     Uses default cache configuration if None.
        config: Optional FetchConfig object for customizing HTTP request
               parameters. Only used if cache miss occurs.

    Returns:
        FetchResult object containing either cached or freshly fetched data:
        - If cache hit: Returns cached response with original metadata
        - If cache miss: Returns fresh response and caches it for future use
        - All standard FetchResult fields are populated appropriately

    Raises:
        WebFetchError: If URL is invalid or request fails
        TimeoutError: If request times out (cache miss only)
        ConnectionError: If connection fails (cache miss only)

    Note:
        Cache keys are based on the URL string. Different URLs (even if they
        resolve to the same resource) will have separate cache entries.

    Example:
        ```python
        from web_fetch.models import CacheConfig

        cache_config = CacheConfig(
            ttl_seconds=300,  # Cache for 5 minutes
            max_size=100,     # Max 100 cached entries
            enable_compression=True
        )

        # First call: fetches from server and caches
        result1 = await fetch_with_cache(
            "https://api.example.com/data",
            ContentType.JSON,
            cache_config
        )

        # Second call: returns cached data (if within TTL)
        result2 = await fetch_with_cache(
            "https://api.example.com/data",
            ContentType.JSON,
            cache_config
        )
        ```
    """
    from ..models import CacheConfig
    from ..utils import SimpleCache

    if cache_config is None:
        cache_config = CacheConfig()

    # Create a simple cache instance
    cache = SimpleCache(cache_config)

    # Check cache first
    cached_entry = cache.get(url)
    if cached_entry:
        # Decompress if needed
        content = cached_entry.response_data
        if cached_entry.compressed:
            import gzip

            content = gzip.decompress(content)
            if content_type in (ContentType.TEXT, ContentType.JSON, ContentType.HTML):
                content = content.decode("utf-8")

        return FetchResult(
            url=url,
            status_code=cached_entry.status_code,
            headers=cached_entry.headers,
            content=content,
            content_type=content_type,
            response_time=0.0,  # Cached response
            timestamp=cached_entry.timestamp,
        )

    # Fetch from network
    request = FetchRequest(url=HttpUrl(url), content_type=content_type)

    async with WebFetcher(config) as fetcher:
        result = await fetcher.fetch_single(request)

        # Cache successful responses
        if result.is_success:
            cache.put(url, result.content, result.headers, result.status_code)

        return result
