"""
HTTP-specific models and configuration classes for the web_fetch library.

This module contains all HTTP/HTTPS related models, configurations, and data structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from .base import (
    BaseConfig,
    BaseResult,
    ContentSummary,
    ContentType,
    CSVMetadata,
    FeedItem,
    FeedMetadata,
    ImageMetadata,
    LinkInfo,
    PDFMetadata,
    RequestHeaders,
    RetryStrategy,
)


class FetchConfig(BaseConfig):
    """
    Comprehensive configuration model for web fetching operations.

    FetchConfig defines all configurable parameters for HTTP requests including
    timeouts, concurrency limits, retry behavior, content handling, and security
    settings. All fields are validated using Pydantic for type safety and
    constraint enforcement.

    Timeout Configuration:
        Controls various timeout aspects of HTTP requests to prevent hanging
        connections and ensure responsive behavior.

    Concurrency Configuration:
        Manages connection pooling and concurrent request limits to optimize
        performance while respecting server capacity and rate limits.

    Retry Configuration:
        Defines retry behavior for failed requests including strategy, maximum
        attempts, and delay calculations for resilient operation.

    Content Configuration:
        Controls response handling including size limits, redirect behavior,
        and SSL verification for security and resource management.

    Example:
        ```python
        from web_fetch import FetchConfig, RetryStrategy, RequestHeaders

        # Basic configuration
        config = FetchConfig(
            total_timeout=60.0,
            max_concurrent_requests=20,
            max_retries=5
        )

        # Production configuration with custom headers
        prod_config = FetchConfig(
            # Timeout settings
            total_timeout=45.0,
            connect_timeout=15.0,
            read_timeout=30.0,

            # Concurrency settings
            max_concurrent_requests=25,
            max_connections_per_host=8,

            # Retry settings
            retry_strategy=RetryStrategy.LINEAR,
            max_retries=3,
            retry_delay=2.0,

            # Content settings
            max_response_size=50 * 1024 * 1024,  # 50MB
            follow_redirects=True,
            verify_ssl=True,

            # Custom headers
            headers=RequestHeaders(
                user_agent="MyApp/1.0",
                custom_headers={
                    "X-API-Key": "secret-key",
                    "Accept": "application/json"
                }
            )
        )
        ```

    Validation:
        All fields are validated for type correctness and value constraints.
        Invalid configurations will raise ValidationError during instantiation.

    Thread Safety:
        FetchConfig instances are immutable after creation and are thread-safe.
        They can be safely shared across multiple WebFetcher instances.
    """

    # Timeout settings - Control request timing behavior
    total_timeout: float = Field(
        default=30.0,
        gt=0,
        description="Maximum total time for the entire request including connection, "
        "sending data, and receiving response. Should be larger than "
        "connect_timeout + read_timeout to allow for processing time.",
    )
    connect_timeout: float = Field(
        default=10.0,
        gt=0,
        description="Maximum time to wait for initial connection establishment. "
        "Lower values fail faster for unreachable hosts but may cause "
        "issues with slow networks.",
    )
    read_timeout: float = Field(
        default=20.0,
        gt=0,
        description="Maximum time to wait for response data after connection is "
        "established. Should account for server processing time and "
        "network latency.",
    )

    # Concurrency settings - Control connection pooling and request limits
    max_concurrent_requests: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of requests that can be processed concurrently. "
        "Higher values improve throughput but increase memory usage and "
        "may overwhelm target servers.",
    )
    max_connections_per_host: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of persistent connections to maintain per host. "
        "Higher values reduce connection overhead but consume more resources. "
        "Should respect server connection limits.",
    )

    # Retry settings - Control failure recovery behavior
    retry_strategy: RetryStrategy = Field(
        default=RetryStrategy.EXPONENTIAL,
        description="Strategy for calculating retry delays. EXPONENTIAL provides "
        "better backoff for overloaded servers, LINEAR provides predictable "
        "timing, NONE disables retries.",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retry attempts for failed requests. "
        "Higher values improve reliability but increase latency for "
        "permanently failing requests.",
    )
    retry_delay: float = Field(
        default=1.0,
        ge=0.1,
        le=60.0,
        description="Base delay in seconds between retry attempts. Actual delay "
        "depends on retry_strategy. For EXPONENTIAL: delay * (2^attempt), "
        "for LINEAR: delay * attempt.",
    )

    # Content settings - Control response handling and security
    max_response_size: int = Field(
        default=10 * 1024 * 1024,
        gt=0,
        description="Maximum response size in bytes to prevent memory exhaustion. "
        "Responses larger than this limit will be truncated or rejected. "
        "Default: 10MB.",
    )
    follow_redirects: bool = Field(
        default=True,
        description="Whether to automatically follow HTTP redirects (3xx status codes). "
        "Disable for applications that need to handle redirects manually.",
    )
    verify_ssl: bool = Field(
        default=True,
        description="Whether to verify SSL/TLS certificates for HTTPS requests. "
        "Disable only for testing with self-signed certificates. "
        "SECURITY WARNING: Disabling SSL verification is dangerous in production.",
    )

    # Headers - Default headers for all requests
    headers: RequestHeaders = Field(
        default_factory=RequestHeaders,
        description="Default headers to include with all requests. Can be overridden "
        "on a per-request basis. Includes User-Agent and other standard headers.",
    )


class FetchRequest(BaseModel):
    """
    Model representing a single HTTP fetch request with comprehensive options.

    FetchRequest encapsulates all parameters needed to make an HTTP request including
    URL, method, headers, data, and content parsing preferences. It provides validation
    and type safety for request parameters.

    The request model supports all standard HTTP methods and content types, with
    automatic validation of URLs, methods, and other parameters. It integrates
    seamlessly with WebFetcher for making actual requests.

    Example:
        ```python
        from web_fetch import FetchRequest, ContentType

        # Simple GET request
        request = FetchRequest(url="https://api.example.com/data")

        # POST request with JSON data
        post_request = FetchRequest(
            url="https://api.example.com/submit",
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer token123"
            },
            data={"name": "John", "email": "john@example.com"},
            content_type=ContentType.JSON
        )

        # GET request with query parameters
        search_request = FetchRequest(
            url="https://api.example.com/search",
            params={"q": "python", "limit": "10"},
            content_type=ContentType.JSON,
            timeout_override=60.0
        )
        ```

    Validation:
        - URL must use http or https scheme
        - Method must be a valid HTTP method
        - Timeout override must be positive if specified
        - All fields are type-checked using Pydantic
    """

    url: HttpUrl = Field(
        description="Target URL to fetch. Must use http or https scheme. "
        "Automatically validated for proper format and accessibility."
    )
    method: str = Field(
        default="GET",
        pattern=r"^(GET|POST|PUT|DELETE|HEAD|OPTIONS|PATCH)$",
        description="HTTP method to use for the request. Supports all standard "
        "HTTP methods. GET for retrieving data, POST for submitting data, "
        "PUT for updating resources, DELETE for removing resources.",
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional custom headers to include with the request. "
        "These will be merged with default headers from FetchConfig. "
        "Common headers: Authorization, Content-Type, Accept, User-Agent.",
    )
    data: Optional[Union[str, bytes, Dict[str, Any]]] = Field(
        default=None,
        description="Optional request body data for POST/PUT requests. "
        "Can be a string (sent as-is), bytes (binary data), or "
        "dictionary (automatically JSON-encoded). For form data, "
        "use a dictionary with appropriate Content-Type header.",
    )
    params: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional query parameters to append to the URL. "
        "Dictionary keys and values will be URL-encoded automatically. "
        "Example: {'q': 'search term', 'page': '1'} becomes '?q=search+term&page=1'",
    )
    content_type: ContentType = Field(
        default=ContentType.RAW,
        description="Expected content type for response parsing. Determines how "
        "the response body is processed: RAW (bytes), TEXT (string), "
        "JSON (parsed object), HTML (parsed with metadata extraction).",
    )
    timeout_override: Optional[float] = Field(
        default=None,
        gt=0,
        description="Optional timeout override for this specific request in seconds. "
        "If specified, overrides the total_timeout from FetchConfig. "
        "Useful for requests that are known to take longer than usual.",
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Any) -> Any:
        """Validate URL format and scheme."""
        parsed = urlparse(str(v))
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must use http or https scheme")
        return v

    model_config = ConfigDict(use_enum_values=True)


@dataclass
class FetchResult(BaseResult):
    """Dataclass representing the result of a fetch operation."""

    status_code: int = 0
    headers: Dict[str, str] = field(default_factory=dict)
    content: Union[str, bytes, Dict[str, Any], None] = None
    content_type: ContentType = ContentType.RAW

    # Resource-specific metadata
    pdf_metadata: Optional[PDFMetadata] = None
    image_metadata: Optional[ImageMetadata] = None
    feed_metadata: Optional[FeedMetadata] = None
    feed_items: List[FeedItem] = field(default_factory=list)
    csv_metadata: Optional[CSVMetadata] = None
    links: List[LinkInfo] = field(default_factory=list)
    content_summary: Optional[ContentSummary] = None

    # Additional processing metadata
    extracted_text: Optional[str] = None  # For PDFs, images with OCR, etc.
    structured_data: Optional[Dict[str, Any]] = None  # For CSV, JSON-LD, etc.

    @property
    def is_success(self) -> bool:
        """Check if the request was successful."""
        return 200 <= self.status_code < 300 and self.error is None

    @property
    def is_client_error(self) -> bool:
        """Check if the request resulted in a client error (4xx)."""
        return 400 <= self.status_code < 500

    @property
    def is_server_error(self) -> bool:
        """Check if the request resulted in a server error (5xx)."""
        return 500 <= self.status_code < 600

    @property
    def has_metadata(self) -> bool:
        """Check if result has any resource-specific metadata."""
        return any(
            [
                self.pdf_metadata,
                self.image_metadata,
                self.feed_metadata,
                self.csv_metadata,
                self.links,
                self.content_summary,
                self.extracted_text,
                self.structured_data,
            ]
        )

    def get_metadata_summary(self) -> Dict[str, Any]:
        """Get a summary of all available metadata."""
        summary = {}

        if self.pdf_metadata:
            summary["pdf"] = {
                "title": self.pdf_metadata.title,
                "author": self.pdf_metadata.author,
                "page_count": self.pdf_metadata.page_count,
                "text_length": self.pdf_metadata.text_length,
            }

        if self.image_metadata:
            summary["image"] = {
                "format": self.image_metadata.format,
                "dimensions": f"{self.image_metadata.width}x{self.image_metadata.height}",
                "file_size": self.image_metadata.file_size,
                "has_exif": bool(self.image_metadata.exif_data),
            }

        if self.feed_metadata:
            summary["feed"] = {
                "title": self.feed_metadata.title,
                "type": self.feed_metadata.feed_type,
                "item_count": self.feed_metadata.item_count,
                "last_updated": (
                    self.feed_metadata.last_build_date.isoformat()
                    if self.feed_metadata.last_build_date
                    else None
                ),
            }

        if self.csv_metadata:
            summary["csv"] = {
                "rows": self.csv_metadata.row_count,
                "columns": self.csv_metadata.column_count,
                "encoding": self.csv_metadata.encoding,
                "has_header": self.csv_metadata.has_header,
            }

        if self.links:
            summary["links"] = {
                "total": len(self.links),
                "external": sum(1 for link in self.links if link.is_external),
                "valid": sum(1 for link in self.links if link.is_valid),
            }

        if self.content_summary:
            summary["content"] = {
                "word_count": self.content_summary.word_count,
                "reading_time": f"{self.content_summary.reading_time_minutes:.1f} min",
                "language": self.content_summary.language,
                "key_phrases": len(self.content_summary.key_phrases),
            }

        return summary


class BatchFetchRequest(BaseModel):
    """Model for batch fetching multiple URLs."""

    requests: List[FetchRequest] = Field(min_length=1, max_length=1000)
    config: Optional[FetchConfig] = Field(default=None)

    @field_validator("requests")
    @classmethod
    def validate_unique_urls(cls, v: Any) -> Any:
        """Ensure URLs are unique in batch request."""
        urls = [str(req.url) for req in v]
        if len(urls) != len(set(urls)):
            raise ValueError("Duplicate URLs found in batch request")
        return v


@dataclass
class BatchFetchResult:
    """Dataclass representing results from a batch fetch operation."""

    results: List[FetchResult]
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_time: float
    timestamp: datetime

    @classmethod
    def from_results(
        cls, results: List[FetchResult], total_time: float
    ) -> BatchFetchResult:
        """Create BatchFetchResult from a list of individual results."""
        successful = sum(1 for r in results if r.is_success)
        failed = len(results) - successful

        return cls(
            results=results,
            total_requests=len(results),
            successful_requests=successful,
            failed_requests=failed,
            total_time=total_time,
            timestamp=datetime.now(),
        )

    @property
    def success_rate(self) -> float:
        """Calculate the success rate as a percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100


# Streaming models


class StreamingConfig(BaseConfig):
    """Configuration for streaming operations."""

    chunk_size: int = Field(
        default=8192, ge=1024, le=1024 * 1024, description="Chunk size in bytes"
    )
    buffer_size: int = Field(
        default=64 * 1024, ge=8192, description="Buffer size for streaming"
    )
    enable_progress: bool = Field(default=True, description="Enable progress tracking")
    progress_interval: float = Field(
        default=0.1,
        ge=0.01,
        le=5.0,
        description="Progress callback interval in seconds",
    )
    max_file_size: Optional[int] = Field(
        default=None, ge=0, description="Maximum file size in bytes"
    )


class StreamRequest(BaseModel):
    """Request model for streaming operations."""

    url: HttpUrl = Field(description="URL to stream")
    method: str = Field(
        default="GET", pattern=r"^(GET|POST|PUT|DELETE|HEAD|OPTIONS|PATCH)$"
    )
    headers: Optional[Dict[str, str]] = Field(default=None)
    data: Optional[Union[str, bytes, Dict[str, Any]]] = Field(default=None)
    output_path: Optional[Path] = Field(
        default=None, description="Path to save streamed content"
    )
    streaming_config: StreamingConfig = Field(default_factory=StreamingConfig)
    timeout_override: Optional[float] = Field(default=None, gt=0)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Any) -> Any:
        """Validate URL format and scheme."""
        parsed = urlparse(str(v))
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must use http or https scheme")
        return v

    model_config = ConfigDict(use_enum_values=True)


@dataclass
class StreamResult(BaseResult):
    """Result of a streaming operation."""

    status_code: int = 0
    headers: Dict[str, str] = field(default_factory=dict)
    bytes_downloaded: int = 0
    total_bytes: Optional[int] = None
    output_path: Optional[Path] = None

    @property
    def is_success(self) -> bool:
        """Check if the streaming operation was successful."""
        return 200 <= self.status_code < 300 and self.error is None

    @property
    def download_complete(self) -> bool:
        """Check if download completed successfully."""
        if not self.is_success or self.total_bytes is None:
            return False
        return self.bytes_downloaded >= self.total_bytes


# Cache models


class CacheConfig(BaseConfig):
    """Configuration for caching operations."""

    max_size: int = Field(
        default=100, ge=1, le=10000, description="Maximum cache entries"
    )
    ttl_seconds: int = Field(default=300, ge=1, description="Time to live in seconds")
    enable_compression: bool = Field(
        default=True, description="Enable response compression in cache"
    )
    cache_headers: bool = Field(default=True, description="Cache response headers")


@dataclass
class CacheEntry:
    """Cache entry for storing responses."""

    url: str
    response_data: Any
    headers: Dict[str, str]
    status_code: int
    timestamp: datetime
    ttl: timedelta
    compressed: bool = False

    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return datetime.now() > (self.timestamp + self.ttl)

    @property
    def age_seconds(self) -> float:
        """Get age of cache entry in seconds."""
        return (datetime.now() - self.timestamp).total_seconds()

    def get_data(self) -> Any:
        """Get the response data, decompressing if necessary."""
        if self.compressed and isinstance(self.response_data, bytes):
            import gzip

            try:
                decompressed = gzip.decompress(self.response_data)
                return decompressed.decode("utf-8")
            except Exception:
                return self.response_data
        return self.response_data


# Rate limiting models


class RateLimitConfig(BaseConfig):
    """Configuration for rate limiting."""

    requests_per_second: float = Field(
        default=10.0, gt=0, le=1000, description="Requests per second limit"
    )
    burst_size: int = Field(
        default=10, ge=1, le=100, description="Burst size for token bucket"
    )
    per_host: bool = Field(default=True, description="Apply rate limiting per host")
    respect_retry_after: bool = Field(
        default=True, description="Respect Retry-After headers"
    )


@dataclass
class RateLimitState:
    """State for rate limiting implementation."""

    tokens: float
    last_update: datetime
    requests_made: int = 0

    def can_make_request(self, config: RateLimitConfig) -> bool:
        """Check if a request can be made based on rate limit."""
        now = datetime.now()
        time_passed = (now - self.last_update).total_seconds()

        # Add tokens based on time passed
        self.tokens = min(
            config.burst_size, self.tokens + (time_passed * config.requests_per_second)
        )
        self.last_update = now

        return self.tokens >= 1.0

    def consume_token(self) -> None:
        """Consume a token for making a request."""
        self.tokens = max(0, self.tokens - 1.0)
        self.requests_made += 1


# URL validation and analysis models


@dataclass
class URLAnalysis:
    """Analysis result for URL validation and normalization."""

    original_url: str
    normalized_url: str
    is_valid: bool
    scheme: str
    domain: str
    path: str
    query_params: Dict[str, str]
    fragment: str
    port: Optional[int]
    is_secure: bool
    issues: List[str] = field(default_factory=list)

    @property
    def is_http(self) -> bool:
        """Check if URL uses HTTP protocol."""
        return self.scheme.lower() in ("http", "https")

    @property
    def is_local(self) -> bool:
        """Check if URL points to localhost."""
        return self.domain.lower() in ("localhost", "127.0.0.1", "::1")


@dataclass
class HeaderAnalysis:
    """Analysis of HTTP response headers."""

    content_type: Optional[str]
    content_length: Optional[int]
    content_encoding: Optional[str]
    server: Optional[str]
    cache_control: Optional[str]
    etag: Optional[str]
    last_modified: Optional[str]
    expires: Optional[str]
    security_headers: Dict[str, str]
    custom_headers: Dict[str, str]

    @property
    def is_cacheable(self) -> bool:
        """Check if response appears to be cacheable."""
        if self.cache_control:
            return "no-cache" not in self.cache_control.lower()
        return self.etag is not None or self.last_modified is not None

    @property
    def has_security_headers(self) -> bool:
        """Check if response has common security headers."""
        security_header_names = {
            "strict-transport-security",
            "content-security-policy",
            "x-frame-options",
            "x-content-type-options",
        }
        return bool(security_header_names.intersection(self.security_headers.keys()))


# Session persistence models


class SessionConfig(BaseConfig):
    """Configuration for session persistence."""

    enable_cookies: bool = Field(default=True, description="Enable cookie handling")
    cookie_jar_path: Optional[Path] = Field(
        default=None, description="Path to save/load cookies"
    )
    enable_auth_persistence: bool = Field(
        default=True, description="Persist authentication"
    )
    session_timeout: int = Field(
        default=3600, ge=60, description="Session timeout in seconds"
    )


@dataclass
class SessionData:
    """Data for session persistence."""

    cookies: Dict[str, Any]
    auth_headers: Dict[str, str]
    custom_headers: Dict[str, str]
    created_at: datetime
    last_used: datetime

    def is_expired(self, timeout_seconds: int) -> bool:
        """Check if session has expired."""
        return (datetime.now() - self.last_used).total_seconds() > timeout_seconds


__all__ = [
    "FetchConfig",
    "FetchRequest",
    "FetchResult",
    "BatchFetchRequest",
    "BatchFetchResult",
    "StreamingConfig",
    "StreamRequest",
    "StreamResult",
    "CacheConfig",
    "CacheEntry",
    "RateLimitConfig",
    "RateLimitState",
    "URLAnalysis",
    "HeaderAnalysis",
    "SessionConfig",
    "SessionData",
]
