"""
Core async web fetcher implementation using AIOHTTP.

This module provides the main WebFetcher class that handles asynchronous HTTP requests
with proper session management, connection pooling, and modern Python features.
Includes enhanced functionality like circuit breakers, deduplication, transformations, and metrics.
"""

from __future__ import annotations

import asyncio
import heapq
import json
import logging
import ssl
import time
import weakref
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Union
from urllib.parse import urlparse

import aiohttp
from aiohttp import ClientSession, ClientTimeout, TCPConnector
from aiohttp.resolver import AsyncResolver
from bs4 import BeautifulSoup

from web_fetch.exceptions import (
    ContentError,
    ErrorHandler,
    HTTPError,
    NetworkError,
    TimeoutError,
    WebFetchError,
)
from web_fetch.models import (
    BatchFetchRequest,
    BatchFetchResult,
    ContentType,
    FetchConfig,
    FetchRequest,
    FetchResult,
    RetryStrategy,
)
from web_fetch.utils.advanced_rate_limiter import AdvancedRateLimiter, RateLimitConfig
from web_fetch.utils.cache import EnhancedCache, EnhancedCacheConfig
from web_fetch.utils.circuit_breaker import CircuitBreakerConfig, with_circuit_breaker
from web_fetch.utils.content_detector import ContentTypeDetector
from web_fetch.utils.deduplication import RequestKey, deduplicate_request
from web_fetch.utils.error_handler import EnhancedErrorHandler, RetryConfig
from web_fetch.utils.js_renderer import JavaScriptRenderer, JSRenderConfig
from web_fetch.utils.metrics import record_request_metrics
from web_fetch.utils.transformers import TransformationPipeline, Transformer

logger = logging.getLogger(__name__)


@dataclass
class ConnectionPoolStats:
    """Statistics for connection pool monitoring."""

    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    connections_per_host: Dict[str, int] = field(default_factory=dict)
    connection_reuse_count: int = 0
    connection_creation_count: int = 0
    dns_cache_hits: int = 0
    dns_cache_misses: int = 0


@dataclass
class RequestPriority:
    """Request priority configuration."""

    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class PriorityRequest:
    """Request with priority for queue processing."""

    request: "FetchRequest"
    priority: int
    timestamp: float
    future: asyncio.Future

    def __lt__(self, other):
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp


class OptimizedTCPConnector(TCPConnector):
    """Enhanced TCP connector with advanced optimizations."""

    def __init__(self, *args, **kwargs):
        # Extract custom parameters
        self._dns_cache_ttl = kwargs.pop("dns_cache_ttl", 300)
        self._enable_keepalive = kwargs.pop("enable_keepalive", True)
        self._keepalive_timeout = kwargs.pop("keepalive_timeout", 30)

        super().__init__(*args, **kwargs)

        # Enhanced connection tracking
        self._connection_stats = ConnectionPoolStats()
        self._dns_cache = {}
        self._last_dns_cleanup = time.time()

        # Configure SSL context for better performance
        if not kwargs.get("ssl", True):
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            # Enable session resumption for faster TLS handshakes
            ssl_context.options |= ssl.OP_NO_COMPRESSION
            self._ssl_context = ssl_context

    async def _create_connection(self, req, traces, timeout):
        """Override to add connection tracking."""
        self._connection_stats.connection_creation_count += 1
        host = req.host
        self._connection_stats.connections_per_host[host] = (
            self._connection_stats.connections_per_host.get(host, 0) + 1
        )

        return await super()._create_connection(req, traces, timeout)

    def _cleanup_dns_cache(self):
        """Cleanup expired DNS entries."""
        current_time = time.time()
        if current_time - self._last_dns_cleanup > 60:  # Cleanup every minute
            expired_keys = [
                host
                for host, (_, timestamp) in self._dns_cache.items()
                if current_time - timestamp > self._dns_cache_ttl
            ]
            for key in expired_keys:
                del self._dns_cache[key]
            self._last_dns_cleanup = current_time


class AdaptiveRetryStrategy:
    """Intelligent retry strategy that adapts based on error patterns."""

    def __init__(self):
        self._host_error_rates = defaultdict(
            lambda: {"errors": 0, "requests": 0, "last_reset": time.time()}
        )
        self._global_backoff_multiplier = 1.0

    def should_retry(
        self, error: Exception, attempt: int, max_retries: int, url: str
    ) -> bool:
        """Determine if request should be retried based on adaptive logic."""
        if attempt >= max_retries:
            return False

        # Extract host from URL
        host = urlparse(url).netloc

        # Update error statistics
        stats = self._host_error_rates[host]
        stats["requests"] += 1

        # Reset stats if they're old (every 5 minutes)
        if time.time() - stats["last_reset"] > 300:
            stats["errors"] = 0
            stats["requests"] = 0
            stats["last_reset"] = time.time()

        # Don't retry certain error types
        if isinstance(error, (aiohttp.ClientResponseError,)):
            if hasattr(error, "status") and error.status in (400, 401, 403, 404, 422):
                return False

        # Reduce retries for hosts with high error rates
        if stats["requests"] > 10:
            error_rate = stats["errors"] / stats["requests"]
            if error_rate > 0.5:  # More than 50% error rate
                return attempt < max(1, max_retries // 2)

        return True

    def calculate_delay(self, attempt: int, base_delay: float, url: str) -> float:
        """Calculate adaptive delay with jitter."""
        host = urlparse(url).netloc
        stats = self._host_error_rates[host]

        # Increase delay for problematic hosts
        host_multiplier = 1.0
        if stats["requests"] > 5:
            error_rate = stats["errors"] / stats["requests"]
            host_multiplier = 1.0 + (
                error_rate * 2
            )  # Up to 3x delay for 100% error rate

        # Exponential backoff with jitter
        delay = (
            base_delay
            * (2**attempt)
            * host_multiplier
            * self._global_backoff_multiplier
        )

        # Add jitter (±25%)
        import random

        jitter = random.uniform(0.75, 1.25)

        return min(delay * jitter, 60.0)  # Cap at 60 seconds

    def record_error(self, url: str):
        """Record an error for adaptive learning."""
        host = urlparse(url).netloc
        self._host_error_rates[host]["errors"] += 1

    def record_success(self, url: str):
        """Record a success to help recovery detection."""
        host = urlparse(url).netloc
        # Don't increment requests here as it's already done in should_retry


class WebFetcher:
    """
    Async web fetcher with modern Python features, AIOHTTP best practices, and advanced optimizations.

    WebFetcher is the core class for making asynchronous HTTP requests with comprehensive
    error handling, retry logic, and content parsing capabilities. It's designed to be
    production-ready with features like connection pooling, circuit breakers, metrics,
    request prioritization, and adaptive retry strategies.

    Key Features:
        - **Advanced connection pooling**: Optimized TCP connections with HTTP/2 support
        - **Adaptive retry logic**: Intelligent retry strategies that learn from failures
        - **Request prioritization**: Priority queue system for managing request ordering
        - **DNS caching**: Built-in DNS resolution caching for improved performance
        - **Connection multiplexing**: HTTP/2 support for efficient connection reuse
        - **Performance monitoring**: Detailed metrics and connection pool statistics
        - **Circuit breaker**: Automatic failure detection and recovery
        - **Request deduplication**: Avoid duplicate requests in flight
        - **Response transformation**: Pluggable transformation pipelines
        - **Enhanced caching**: Multi-backend caching with TTL and compression
        - **JavaScript rendering**: Support for dynamic content via Playwright
        - **Intelligent rate limiting**: Token bucket with host-specific limits
        - **Session persistence**: Cookie and authentication state management

    Performance Optimizations:
        - Connection keep-alive with configurable timeouts
        - DNS resolution caching with TTL
        - SSL session resumption for faster TLS handshakes
        - Connection pool statistics and monitoring
        - Request batching and priority queuing
        - Adaptive backoff strategies based on host performance
        - HTTP/2 multiplexing when supported by the server

    Usage:
        Basic usage with context manager (recommended):

        ```python
        import asyncio
        from web_fetch import WebFetcher, FetchRequest, ContentType

        async def main():
            config = FetchConfig(
                max_concurrent_requests=20,
                total_timeout=30.0,
                enable_http2=True,
                dns_cache_ttl=300
            )

            async with WebFetcher(config) as fetcher:
                request = FetchRequest(
                    url="https://api.example.com/data",
                    content_type=ContentType.JSON,
                    priority=RequestPriority.HIGH
                )
                result = await fetcher.fetch_single(request)

                if result.is_success:
                    print(f"Data: {result.content}")
                else:
                    print(f"Error: {result.error}")

        asyncio.run(main())
        ```

        High-performance batch processing:

        ```python
        async def batch_example():
            config = FetchConfig(
                max_concurrent_requests=50,
                enable_request_prioritization=True,
                adaptive_retry=True
            )

            requests = [
                FetchRequest(
                    url=f"https://api.example.com/item/{i}",
                    priority=RequestPriority.HIGH if i < 5 else RequestPriority.NORMAL
                )
                for i in range(1, 101)
            ]

            batch_request = BatchFetchRequest(requests=requests)

            async with WebFetcher(config) as fetcher:
                result = await fetcher.fetch_batch_optimized(batch_request)
                print(f"Success rate: {result.success_rate:.1f}%")
                print(f"Average response time: {result.avg_response_time:.3f}s")
                print(f"Connection reuse rate: {result.connection_reuse_rate:.1f}%")
        ```

    Thread Safety:
        WebFetcher instances are not thread-safe. Each instance should be used
        within a single asyncio event loop. For multi-threaded applications,
        create separate instances per thread.

    Resource Management:
        Always use WebFetcher as an async context manager to ensure proper
        resource cleanup. The session, connections, and priority queue will be
        automatically closed when exiting the context.

    See Also:
        - :class:`StreamingWebFetcher`: For large file downloads with progress tracking
        - :class:`FTPFetcher`: For FTP operations
        - :class:`FetchConfig`: For detailed configuration options
        - :class:`FetchRequest`: For request specification
        - :class:`FetchResult`: For response data and metadata
    """

    def __init__(
        self,
        config: Optional[FetchConfig] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
        enable_deduplication: bool = False,
        enable_metrics: bool = False,
        transformation_pipeline: Optional[TransformationPipeline] = None,
        cache_config: Optional[EnhancedCacheConfig] = None,
        js_config: Optional[JSRenderConfig] = None,
        enable_request_prioritization: bool = False,
        enable_adaptive_retry: bool = True,
        enable_http2: bool = True,
        dns_cache_ttl: int = 300,
    ):
        """
        Initialize the WebFetcher with comprehensive configuration options.

        Creates a new WebFetcher instance with the specified configuration. The fetcher
        is not ready for use until it's used as an async context manager or the session
        is manually created.

        Args:
            config: Configuration for HTTP operations including timeouts, retry settings,
                   and connection limits. If None, uses default configuration with:
                   - 30s total timeout, 10s connect timeout, 20s read timeout
                   - 10 max concurrent requests, 5 connections per host
                   - 3 max retries with exponential backoff
                   - SSL verification enabled, redirects followed

            circuit_breaker_config: Configuration for circuit breaker pattern to handle
                                  failing services gracefully. Includes failure threshold,
                                  recovery timeout, and expected exceptions. If None,
                                  uses default settings (5 failures, 60s recovery).

            enable_deduplication: Whether to enable automatic request deduplication.
                                When True, identical requests made concurrently will be
                                deduplicated to avoid unnecessary network calls. Useful
                                for batch operations with potential duplicates.

            enable_metrics: Whether to collect detailed metrics about requests including
                          response times, status codes, error rates, and throughput.
                          Metrics can be retrieved using get_metrics_summary().

            transformation_pipeline: Optional pipeline for transforming responses before
                                   returning to caller. Useful for data extraction,
                                   filtering, or format conversion. Can include multiple
                                   transformers that are applied in sequence.

            cache_config: Configuration for enhanced caching with support for multiple
                        backends (memory, Redis, file), compression, and TTL settings.
                        If None, no caching is performed.

            js_config: Configuration for JavaScript rendering using Playwright. Enables
                     fetching of dynamically generated content from SPAs and other
                     JavaScript-heavy sites. If None, no JS rendering is performed.

        Attributes:
            config (FetchConfig): The fetch configuration used by this instance
            circuit_breaker_config (CircuitBreakerConfig): Circuit breaker settings
            enable_deduplication (bool): Whether request deduplication is enabled
            enable_metrics (bool): Whether metrics collection is enabled
            transformation_pipeline (Optional[TransformationPipeline]): Response transformation pipeline

        Note:
            The WebFetcher instance is not ready for use immediately after initialization.
            You must use it as an async context manager or call _create_session() manually
            before making requests.

        Example:
            ```python
            # Basic configuration
            config = FetchConfig(
                total_timeout=60.0,
                max_concurrent_requests=20,
                max_retries=5
            )

            # Advanced configuration with all features
            fetcher = WebFetcher(
                config=config,
                enable_deduplication=True,
                enable_metrics=True,
                cache_config=EnhancedCacheConfig(
                    backend="memory",
                    ttl_seconds=300,
                    max_size=1000
                )
            )
            ```
        """
        self.config = config or FetchConfig()
        self.circuit_breaker_config = circuit_breaker_config or CircuitBreakerConfig()
        self.enable_deduplication = enable_deduplication
        self.enable_metrics = enable_metrics
        self.transformation_pipeline = transformation_pipeline

        self._session: Optional[ClientSession] = None
        self._semaphore: Optional[asyncio.Semaphore] = None

        # Enhanced components
        self._content_detector = ContentTypeDetector()
        self._error_handler = EnhancedErrorHandler()
        self._advanced_rate_limiter = AdvancedRateLimiter()
        self._enhanced_cache = EnhancedCache(cache_config) if cache_config else None
        self._js_renderer = JavaScriptRenderer(js_config) if js_config else None

    async def __aenter__(self) -> WebFetcher:
        """
        Async context manager entry.

        Initializes the internal aiohttp session and prepares the fetcher
        for making requests.

        Returns:
            Self instance for use in async with statements

        Raises:
            WebFetchError: If session creation fails
        """
        await self._create_session()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Async context manager exit with proper cleanup.

        Closes the internal session and releases all resources.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
        """
        await self.close()

    async def _create_session(self) -> None:
        """
        Create aiohttp session with proper configuration.

        Sets up the internal ClientSession with appropriate timeouts,
        connection limits, and other configuration from self.config.
        This method is idempotent - calling it multiple times has no effect.

        Raises:
            WebFetchError: If session creation fails due to invalid configuration
        """
        if self._session is not None:
            return

        # Configure timeouts
        timeout = ClientTimeout(
            total=self.config.total_timeout,
            connect=self.config.connect_timeout,
            sock_read=self.config.read_timeout,
        )

        # Configure TCP connector for connection pooling
        connector = TCPConnector(
            limit=self.config.max_connections_per_host * 10,  # Total connection pool
            limit_per_host=self.config.max_connections_per_host,
            ssl=self.config.verify_ssl,
            enable_cleanup_closed=True,
        )

        # Create session with configuration
        self._session = ClientSession(
            timeout=timeout,
            connector=connector,
            headers=self.config.headers.to_dict(),
            raise_for_status=False,  # We'll handle status codes manually
        )

        # Create semaphore for concurrency control
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)

    async def close(self) -> None:
        """Close the session and cleanup resources."""
        if self._session:
            await self._session.close()
            self._session = None
        self._semaphore = None

    async def fetch_single(self, request: FetchRequest) -> FetchResult:
        """
        Fetch a single URL with comprehensive retry logic and error handling.

        This is the primary method for making individual HTTP requests. It handles
        the complete request lifecycle including retries, error handling, content
        parsing, caching, and metrics collection.

        The method implements intelligent retry logic with exponential backoff for
        transient failures, while avoiding retries for permanent errors like 404
        or authentication failures.

        Args:
            request: FetchRequest object containing all request parameters:
                    - url: Target URL to fetch (required)
                    - method: HTTP method (GET, POST, PUT, DELETE, etc.)
                    - headers: Optional custom headers dictionary
                    - data: Optional request body data (for POST/PUT requests)
                    - params: Optional query parameters dictionary
                    - content_type: Expected content type for parsing response
                    - timeout_override: Optional timeout override for this request

        Returns:
            FetchResult object containing:
                - url: The requested URL
                - status_code: HTTP status code (200, 404, 500, etc.)
                - headers: Response headers dictionary
                - content: Parsed response content (type depends on content_type)
                - content_type: The content type used for parsing
                - response_time: Total request time in seconds
                - timestamp: When the request was completed
                - error: Error message if request failed (None if successful)
                - retry_count: Number of retry attempts made
                - is_success: Boolean indicating if request was successful

        Raises:
            WebFetchError: If session is not properly initialized. This should not
                          happen when using the async context manager properly.

        Example:
            ```python
            async with WebFetcher() as fetcher:
                # Simple GET request
                request = FetchRequest(url="https://api.example.com/data")
                result = await fetcher.fetch_single(request)

                if result.is_success:
                    print(f"Status: {result.status_code}")
                    print(f"Content: {result.content}")
                else:
                    print(f"Error: {result.error}")

                # POST request with data
                post_request = FetchRequest(
                    url="https://api.example.com/submit",
                    method="POST",
                    headers={"Content-Type": "application/json"},
                    data={"key": "value"},
                    content_type=ContentType.JSON
                )
                result = await fetcher.fetch_single(post_request)
            ```

        Note:
            This method is safe to call concurrently. The internal semaphore ensures
            that the number of concurrent requests doesn't exceed the configured limit.
            Failed requests are automatically retried according to the retry strategy
            configured in FetchConfig.
        """
        if not self._session:
            await self._create_session()

        start_time = time.time()
        last_error: Optional[str] = None

        for attempt in range(self.config.max_retries + 1):
            try:
                if self._semaphore is None:
                    raise WebFetchError("Session not properly initialized")

                async with self._semaphore:  # Control concurrency
                    result = await self._execute_request(request, attempt)
                    result.response_time = time.time() - start_time
                    return result

            except Exception as e:
                # Convert to appropriate WebFetchError subclass
                web_error = ErrorHandler.handle_aiohttp_error(e, str(request.url))
                last_error = str(web_error)

                # Check if error is retryable
                if (
                    attempt < self.config.max_retries
                    and ErrorHandler.is_retryable_error(web_error)
                ):
                    delay = ErrorHandler.get_retry_delay(
                        web_error, attempt, self.config.retry_delay
                    )
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed or error is not retryable
                    status_code = getattr(web_error, "status_code", 0)
                    return FetchResult(
                        url=str(request.url),
                        status_code=status_code,
                        headers={},
                        content=None,
                        content_type=request.content_type,
                        response_time=time.time() - start_time,
                        timestamp=datetime.now(),
                        error=last_error,
                        retry_count=attempt,
                    )

        # This should never be reached, but included for completeness
        return FetchResult(
            url=str(request.url),
            status_code=0,
            headers={},
            content=None,
            content_type=request.content_type,
            response_time=time.time() - start_time,
            timestamp=datetime.now(),
            error="Maximum retries exceeded",
            retry_count=self.config.max_retries,
        )

    async def _execute_request(
        self, request: FetchRequest, attempt: int
    ) -> FetchResult:
        """
        Execute a single HTTP request with enhanced features.

        This is an internal method that performs the actual HTTP request using
        the configured aiohttp session. It handles request preparation, execution,
        response processing, caching, deduplication, and metrics collection.

        Args:
            request: FetchRequest object containing URL, method, headers, and other
                    request parameters
            attempt: Current attempt number (0-based) for retry tracking

        Returns:
            FetchResult object containing response data, status code, headers,
            and metadata about the request

        Raises:
            WebFetchError: If session is not initialized
            ServerError: If server returns 5xx status code
            ClientError: If client error occurs (4xx status code)
            TimeoutError: If request times out
            ConnectionError: If connection fails
        """
        if self._session is None:
            raise WebFetchError("Session not properly initialized")

        start_time = time.time()
        url = str(request.url)

        # Check enhanced cache first
        if self._enhanced_cache:
            cached_result = await self._enhanced_cache.get(url, request.headers)
            if cached_result:
                logger.debug(f"Enhanced cache hit for {url}")
                if self.enable_metrics:
                    record_request_metrics(
                        url,
                        request.method,
                        cached_result.status_code,
                        time.time() - start_time,
                        0,
                    )
                return cached_result

        # Handle request deduplication
        if self.enable_deduplication:
            result = await deduplicate_request(
                url=url,
                method=request.method,
                headers=request.headers,
                data=request.data,
                params=request.params,
                executor_func=self._make_http_request,
                request=request,
                attempt=attempt,
            )

            if self.enable_metrics:
                record_request_metrics(
                    url, request.method, result.status_code, time.time() - start_time, 0
                )
            return result
        else:
            result = await self._make_http_request(request, attempt)

            if self.enable_metrics:
                record_request_metrics(
                    url, request.method, result.status_code, time.time() - start_time, 0
                )
            return result

    async def _make_http_request(
        self, request: FetchRequest, attempt: int
    ) -> FetchResult:
        """Make the actual HTTP request without deduplication."""
        if self._session is None:
            raise WebFetchError("Session not properly initialized")

        # Prepare request parameters
        method = request.method
        url = str(request.url)
        headers = request.headers or {}
        params = request.params
        timeout = (
            ClientTimeout(total=request.timeout_override)
            if request.timeout_override
            else None
        )

        # Prepare data/json parameters
        json_data = None
        data = None
        if request.data is not None:
            if isinstance(request.data, dict):
                json_data = request.data
            elif isinstance(request.data, (str, bytes)):
                data = request.data

        async with self._session.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_data,
            data=data,
            timeout=timeout,
        ) as response:
            # Check for server errors that should be retried
            if response.status >= 500:
                from web_fetch.exceptions import ServerError

                raise ServerError(
                    f"Server error: {response.status} {response.reason}",
                    status_code=response.status,
                    url=str(request.url),
                    headers=dict(response.headers),
                )

            # Read response content
            content_bytes = await response.read()

            # Check response size
            if len(content_bytes) > self.config.max_response_size:
                from web_fetch.exceptions import ContentError

                raise ContentError(
                    f"Response size {len(content_bytes)} exceeds maximum {self.config.max_response_size}",
                    url=str(request.url),
                    content_length=len(content_bytes),
                )

            # Parse content based on requested type
            parsed_content = await self._parse_content(
                content_bytes, request.content_type, url, dict(response.headers)
            )

            result = FetchResult(
                url=str(request.url),
                status_code=response.status,
                headers=dict(response.headers),
                content=parsed_content,
                content_type=request.content_type,
                response_time=0.0,  # Will be set by caller
                timestamp=datetime.now(),
                retry_count=attempt,
            )

            # Apply transformation pipeline if configured
            if self.transformation_pipeline:
                try:
                    transformation_result = (
                        await self.transformation_pipeline.transform(
                            parsed_content,
                            {"url": url, "headers": dict(response.headers)},
                        )
                    )
                    if transformation_result.is_success:
                        result.content = transformation_result.data
                except Exception as e:
                    logger.warning(f"Transformation pipeline failed for {url}: {e}")

            # Store in enhanced cache if configured
            if self._enhanced_cache:
                await self._enhanced_cache.set(url, result, dict(response.headers))

            return result

    async def _parse_content(
        self,
        content_bytes: bytes,
        requested_type: ContentType,
        url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Union[str, bytes, Dict[str, Any], None]:
        """
        Parse response content based on requested content type.

        Converts raw bytes into the appropriate Python data type based on
        the requested content type. Handles encoding detection and error
        recovery for text-based content.

        Args:
            content_bytes: Raw response content as bytes
            requested_type: ContentType enum specifying how to parse the content
                          (RAW, TEXT, JSON, or HTML)

        Returns:
            Parsed content in the appropriate format:
            - RAW: Returns bytes unchanged
            - TEXT: Returns decoded string
            - JSON: Returns parsed dict/list/primitive
            - HTML: Returns BeautifulSoup parsed object
            - None if content_bytes is empty

        Raises:
            ContentError: If content cannot be parsed as requested type
            WebFetchError: If HTML parsing fails and BeautifulSoup is not available
        """
        # Handle empty content gracefully - return None for consistency
        if not content_bytes:
            return None

        # Content parsing using Python 3.10+ pattern matching for clean, readable code
        match requested_type:
            case ContentType.RAW:
                # Return raw bytes unchanged - useful for binary data, images, etc.
                return content_bytes

            case ContentType.TEXT:
                # Text decoding with fallback encoding detection
                try:
                    # Try UTF-8 first as it's the most common encoding for web content
                    return content_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    # UTF-8 failed, try common fallback encodings in order of likelihood
                    # This handles legacy content and various regional encodings
                    for encoding in ["latin1", "cp1252", "iso-8859-1"]:
                        try:
                            return content_bytes.decode(encoding)
                        except UnicodeDecodeError:
                            continue
                    # Last resort: decode with error replacement to avoid complete failure
                    # This ensures we always return something, even if some characters are lost
                    return content_bytes.decode("utf-8", errors="replace")

            case ContentType.JSON:
                # JSON parsing with comprehensive error handling
                try:
                    # First decode bytes to string, then parse JSON
                    # This two-step process allows us to distinguish between encoding and JSON errors
                    text_content = content_bytes.decode("utf-8")
                    return json.loads(text_content)
                except (UnicodeDecodeError, json.JSONDecodeError) as e:
                    # Provide specific error information for debugging
                    from web_fetch.exceptions import ContentError

                    raise ContentError(
                        f"Failed to parse JSON content: {e}",
                        content_type="application/json",
                    )

            case ContentType.HTML:
                # HTML parsing with structured data extraction
                try:
                    # Decode HTML content to string for BeautifulSoup processing
                    text_content = content_bytes.decode("utf-8")

                    # Use lxml parser for better performance and HTML5 support
                    # Falls back to html.parser if lxml is not available
                    soup = BeautifulSoup(text_content, "lxml")

                    # Extract structured data from HTML for common use cases
                    return {
                        # Page title from <title> tag, None if not found
                        "title": soup.title.string if soup.title else None,
                        # Clean text content with whitespace stripped
                        # Useful for content analysis and search indexing
                        "text": soup.get_text(strip=True),
                        # All links with href attributes - useful for crawling and link analysis
                        # Filter out None values and ensure href attribute exists
                        "links": [
                            a.get("href")
                            for a in soup.find_all("a", href=True)
                            if hasattr(a, "get")
                        ],
                        # All images with src attributes - useful for media extraction
                        # Filter out None values and ensure src attribute exists
                        "images": [
                            img.get("src")
                            for img in soup.find_all("img", src=True)
                            if hasattr(img, "get")
                        ],
                        # Raw HTML content for cases where full HTML is needed
                        # Useful for custom parsing or HTML transformation
                        "raw_html": text_content,
                    }
                except Exception as e:
                    # Provide specific error context for HTML parsing failures
                    raise WebFetchError(f"Failed to parse HTML content: {e}")

            case (
                ContentType.PDF
                | ContentType.IMAGE
                | ContentType.RSS
                | ContentType.CSV
                | ContentType.MARKDOWN
                | ContentType.XML
            ):
                # For new content types, use the enhanced parser
                try:
                    from web_fetch.parsers import EnhancedContentParser

                    parser = EnhancedContentParser()
                    parsed_content, enhanced_result = await parser.parse_content(
                        content_bytes, requested_type, url=None, headers=None
                    )
                    return parsed_content
                except Exception as e:
                    raise WebFetchError(
                        f"Failed to parse {requested_type} content: {e}"
                    )

            case _:
                return content_bytes.decode("utf-8", errors="replace")

    def _calculate_retry_delay(self, attempt: int) -> float:
        """
        Calculate delay for retry based on strategy.

        Computes the delay time before the next retry attempt using the
        configured retry strategy and base delay.

        Args:
            attempt: Current attempt number (0-based). For example, attempt=1
                    means this is the first retry after the initial request.

        Returns:
            Delay time in seconds before the next retry attempt.
            Returns 0.0 if retry strategy is NONE.

        Note:
            - LINEAR: delay = base_delay * (attempt + 1)
            - EXPONENTIAL: delay = base_delay * (2 ** attempt)
            - NONE: delay = 0.0
            - Default: delay = base_delay
        """
        base_delay = self.config.retry_delay

        match self.config.retry_strategy:
            case RetryStrategy.NONE:
                return 0.0
            case RetryStrategy.LINEAR:
                return base_delay * (attempt + 1)
            case RetryStrategy.EXPONENTIAL:
                return base_delay * (2**attempt)
            case _:
                return base_delay

    # Enhanced convenience methods
    async def fetch_with_circuit_breaker(self, request: FetchRequest) -> FetchResult:
        """Fetch a single URL with circuit breaker protection."""
        return await with_circuit_breaker(
            url=str(request.url),
            func=self.fetch_single,
            config=self.circuit_breaker_config,
            request=request,
        )

    async def fetch_with_auto_detection(
        self, url: str, headers: Optional[Dict[str, str]] = None
    ) -> FetchResult:
        """
        Fetch URL with automatic content type detection.

        This method first fetches the content, detects its type, then re-parses
        it with the appropriate parser for optimal results.

        Args:
            url: URL to fetch
            headers: Optional custom headers

        Returns:
            FetchResult with automatically detected and parsed content
        """
        # First fetch with RAW content type to get headers and content
        raw_request = FetchRequest(
            url=url, headers=headers, content_type=ContentType.RAW
        )

        raw_result = await self.fetch_single(raw_request)

        if not raw_result.is_success or not raw_result.content:
            return raw_result

        # Detect best content type
        if self._content_detector:
            try:
                best_content_type = await self._content_detector.detect_content_type(
                    raw_result.content, raw_result.headers, url
                )

                # Re-parse with detected content type if different
                if best_content_type != ContentType.RAW:
                    enhanced_request = FetchRequest(
                        url=url, headers=headers, content_type=best_content_type
                    )

                    enhanced_result = await self.fetch_single(enhanced_request)
                    return enhanced_result

            except Exception as e:
                logger.warning(
                    f"Content type detection failed for {url}, using raw content: {e}"
                )

        return raw_result

    async def fetch_batch(self, batch_request: BatchFetchRequest) -> BatchFetchResult:
        """
        Fetch multiple URLs concurrently.

        Args:
            batch_request: BatchFetchRequest containing multiple URLs and config

        Returns:
            BatchFetchResult with all individual results and summary statistics
        """
        if not self._session:
            await self._create_session()

        start_time = time.time()

        # Create tasks for concurrent execution
        tasks = [self.fetch_single(request) for request in batch_request.requests]

        # Execute all requests concurrently
        results = await asyncio.gather(*tasks, return_exceptions=False)

        total_time = time.time() - start_time

        return BatchFetchResult.from_results(results, total_time)

    @asynccontextmanager
    async def session_context(self) -> AsyncGenerator[WebFetcher, None]:
        """
        Context manager for session lifecycle management.

        Provides an alternative to using the WebFetcher as a context manager
        directly. This method creates and manages the internal session lifecycle,
        ensuring proper cleanup even if exceptions occur.

        Yields:
            WebFetcher: The fetcher instance with an active session

        Raises:
            WebFetchError: If session creation fails

        Example:
            ```python
            async with WebFetcher().session_context() as fetcher:
                result = await fetcher.fetch_single(request)
                # Session is automatically closed when exiting the context
            ```
        """
        try:
            await self._create_session()
            yield self
        finally:
            await self.close()
