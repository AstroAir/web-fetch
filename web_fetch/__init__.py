"""
Modern async web scraping/fetching utility with AIOHTTP.

This package provides a robust, production-ready web fetching tool that demonstrates
modern Python capabilities and efficient asynchronous HTTP handling.

Features:
- Async/await syntax for concurrent requests
- Modern Python 3.11+ features (type hints, pattern matching, dataclasses)
- AIOHTTP best practices with session management and connection pooling
- Comprehensive error handling and retry logic
- Structured data models with Pydantic
- Multiple content parsing options (JSON, HTML, text, raw)
"""

from .exceptions import (
    AuthenticationError,
    ConnectionError,
    ContentError,
    FTPAuthenticationError,
    FTPConnectionError,
    FTPError,
    FTPFileNotFoundError,
    FTPPermissionError,
    FTPProtocolError,
    FTPTimeoutError,
    FTPTransferError,
    FTPVerificationError,
    HTTPError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
    TimeoutError,
    WebFetchError,
)
from .fetcher import (
    StreamingWebFetcher,
    WebFetcher,
    analyze_headers,
    analyze_url,
    detect_content_type,
    download_file,
    fetch_url,
    fetch_urls,
    fetch_with_cache,
    is_valid_url,
    normalize_url,
)
from .models import (
    BatchFetchRequest,
    BatchFetchResult,
    CacheConfig,
    ContentType,
    FetchConfig,
    FetchRequest,
    FetchResult,
    ProgressInfo,
    RateLimitConfig,
    RequestHeaders,
    RetryStrategy,
    SessionConfig,
    StreamingConfig,
    StreamRequest,
    StreamResult,
    # Resource metadata classes
    PDFMetadata,
    ImageMetadata,
    FeedMetadata,
    FeedItem,
    CSVMetadata,
    LinkInfo,
    ContentSummary,
)
from .ftp import (
    FTPAuthType,
    FTPBatchRequest,
    FTPBatchResult,
    FTPConfig,
    FTPConnectionInfo,
    FTPFileInfo,
    FTPMode,
    FTPProgressInfo,
    FTPRequest,
    FTPResult,
    FTPTransferMode,
    FTPVerificationMethod,
    FTPVerificationResult,
)
from .utils import (
    RateLimiter, ResponseAnalyzer, SimpleCache, URLValidator,
    # Enhanced utilities
    CircuitBreaker, CircuitBreakerConfig, with_circuit_breaker,
    RequestDeduplicator, deduplicate_request,
    TransformationPipeline, JSONPathExtractor, HTMLExtractor, RegexExtractor,
    MetricsCollector, record_request_metrics, get_metrics_summary
)
from .ftp import (
    FTPFetcher,
    ftp_download_batch,
    ftp_download_file,
    ftp_get_file_info,
    ftp_list_directory,
)

# Authentication support
from .auth import (
    AuthMethod,
    AuthConfig,
    AuthResult,
    APIKeyAuth,
    APIKeyConfig,
    OAuth2Auth,
    OAuth2Config,
    OAuthTokenResponse,
    JWTAuth,
    JWTConfig,
    BasicAuth,
    BasicAuthConfig,
    BearerTokenAuth,
    BearerTokenConfig,
    CustomAuth,
    CustomAuthConfig,
    AuthManager,
)

# Configuration management
from .config import (
    ConfigManager,
    config_manager,
    GlobalConfig,
    LoggingConfig,
    SecurityConfig,
    PerformanceConfig,
    FeatureFlags,
    EnvironmentConfig,
    ConfigLoader,
    ConfigValidator,
)

# Enhanced logging
from .logging import (
    LoggingManager,
    setup_logging,
    StructuredFormatter,
    ColoredFormatter,
    CompactFormatter,
    AsyncFileHandler,
    RotatingAsyncFileHandler,
    MetricsHandler,
    SensitiveDataFilter,
    RateLimitFilter,
    ComponentFilter,
)

# Enhanced batch operations
from .batch import (
    BatchManager,
    BatchRequest,
    BatchResult,
    BatchConfig,
    BatchPriority,
    BatchStatus,
    BatchMetrics,
    BatchScheduler,
    BatchProcessor,
    PriorityQueue,
)

# Enhanced HTTP support
from .http import (
    HTTPMethodHandler,
    HTTPMethod,
    FileUploadHandler,
    MultipartUploadHandler,
    DownloadHandler,
    ResumableDownloadHandler,
    PaginationHandler,
    PaginationStrategy,
    HeaderManager,
    HeaderPresets,
    CookieManager,
    CookieJar,
)

# Enhanced functionality (now integrated into main fetcher)
from .fetcher import (
    enhanced_fetch_url,
    enhanced_fetch_urls,
)

# Crawler APIs functionality
from .crawlers import (
    CrawlerType,
    CrawlerCapability,
    CrawlerConfig,
    CrawlerRequest,
    CrawlerManager,
    crawler_fetch_url,
    crawler_fetch_urls,
    crawler_search_web,
    crawler_crawl_website,
    crawler_extract_content,
    get_crawler_status,
    configure_crawler,
    set_primary_crawler,
    set_fallback_order,
)

__version__ = "0.1.0"
__author__ = "Web Fetch Team"
__email__ = "team@webfetch.dev"

__all__ = [
    # Main classes
    "WebFetcher",
    "StreamingWebFetcher",
    "FTPFetcher",

    # Convenience functions
    "fetch_url",
    "fetch_urls",
    "download_file",
    "fetch_with_cache",
    "enhanced_fetch_url",
    "enhanced_fetch_urls",
    "ftp_download_file",
    "ftp_download_batch",
    "ftp_list_directory",
    "ftp_get_file_info",

    # Crawler API functions
    "crawler_fetch_url",
    "crawler_fetch_urls",
    "crawler_search_web",
    "crawler_crawl_website",
    "crawler_extract_content",

    # URL utilities
    "is_valid_url",
    "normalize_url",
    "analyze_url",

    # Response utilities
    "analyze_headers",
    "detect_content_type",

    # Utility classes
    "URLValidator",
    "ResponseAnalyzer",
    "SimpleCache",
    "RateLimiter",

    # Crawler management
    "CrawlerType",
    "CrawlerCapability",
    "CrawlerConfig",
    "CrawlerRequest",
    "CrawlerManager",
    "get_crawler_status",
    "configure_crawler",
    "set_primary_crawler",
    "set_fallback_order",

    # Enhanced utilities
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "with_circuit_breaker",
    "RequestDeduplicator",
    "deduplicate_request",
    "TransformationPipeline",
    "JSONPathExtractor",
    "HTMLExtractor",
    "RegexExtractor",
    "MetricsCollector",
    "record_request_metrics",
    "get_metrics_summary",

    # Models and configuration
    "FetchConfig",
    "FetchRequest",
    "FetchResult",
    "BatchFetchRequest",
    "BatchFetchResult",
    "RequestHeaders",
    "StreamingConfig",
    "StreamRequest",
    "StreamResult",
    "ProgressInfo",
    "CacheConfig",
    "RateLimitConfig",
    "SessionConfig",

    # Authentication
    "AuthMethod",
    "AuthConfig",
    "AuthResult",
    "APIKeyAuth",
    "APIKeyConfig",
    "OAuth2Auth",
    "OAuth2Config",
    "OAuthTokenResponse",
    "JWTAuth",
    "JWTConfig",
    "BasicAuth",
    "BasicAuthConfig",
    "BearerTokenAuth",
    "BearerTokenConfig",
    "CustomAuth",
    "CustomAuthConfig",
    "AuthManager",

    # Configuration management
    "ConfigManager",
    "config_manager",
    "GlobalConfig",
    "LoggingConfig",
    "SecurityConfig",
    "PerformanceConfig",
    "FeatureFlags",
    "EnvironmentConfig",
    "ConfigLoader",
    "ConfigValidator",

    # Enhanced logging
    "LoggingManager",
    "setup_logging",
    "StructuredFormatter",
    "ColoredFormatter",
    "CompactFormatter",
    "AsyncFileHandler",
    "RotatingAsyncFileHandler",
    "MetricsHandler",
    "SensitiveDataFilter",
    "RateLimitFilter",
    "ComponentFilter",

    # Enhanced batch operations
    "BatchManager",
    "BatchRequest",
    "BatchResult",
    "BatchConfig",
    "BatchPriority",
    "BatchStatus",
    "BatchMetrics",
    "BatchScheduler",
    "BatchProcessor",
    "PriorityQueue",

    # Enhanced HTTP support
    "HTTPMethodHandler",
    "HTTPMethod",
    "FileUploadHandler",
    "MultipartUploadHandler",
    "DownloadHandler",
    "ResumableDownloadHandler",
    "PaginationHandler",
    "PaginationStrategy",
    "HeaderManager",
    "HeaderPresets",
    "CookieManager",
    "CookieJar",

    # Resource metadata classes
    "PDFMetadata",
    "ImageMetadata",
    "FeedMetadata",
    "FeedItem",
    "CSVMetadata",
    "LinkInfo",
    "ContentSummary",

    # Enums
    "ContentType",
    "RetryStrategy",
    "FTPMode",
    "FTPAuthType",
    "FTPTransferMode",
    "FTPVerificationMethod",

    # FTP Models
    "FTPConfig",
    "FTPRequest",
    "FTPResult",
    "FTPBatchRequest",
    "FTPBatchResult",
    "FTPFileInfo",
    "FTPProgressInfo",
    "FTPConnectionInfo",
    "FTPVerificationResult",

    # Exceptions
    "WebFetchError",
    "NetworkError",
    "TimeoutError",
    "ConnectionError",
    "HTTPError",
    "ContentError",
    "RateLimitError",
    "AuthenticationError",
    "NotFoundError",
    "ServerError",
    "FTPError",
    "FTPConnectionError",
    "FTPAuthenticationError",
    "FTPTimeoutError",
    "FTPTransferError",
    "FTPFileNotFoundError",
    "FTPPermissionError",
    "FTPVerificationError",
    "FTPProtocolError",
]
