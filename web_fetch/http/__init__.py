"""
Enhanced HTTP support for web_fetch.

This module provides comprehensive HTTP method support, advanced request
handling, and specialized HTTP features.
"""

from .connection_pool import OptimizedConnectionPool, ConnectionPoolConfig
from .cookies import CookieJar, CookieManager
from .download import DownloadHandler, ResumableDownloadHandler
from .error_handling import SecurityErrorHandler, SecureErrorConfig, handle_http_error
from .headers import HeaderManager, HeaderPresets
from .methods import HTTPMethod, HTTPMethodHandler
from .metrics import MetricsCollector, RequestMetrics, PerformanceStats, get_global_metrics
from .pagination import PaginationHandler, PaginationStrategy
from .security import URLValidator, SecurityMiddleware, SSRFProtectionConfig
from .session_manager import SessionManager, SessionConfig, managed_session
from .upload import FileUploadHandler, MultipartUploadHandler
from .utils import (
    BaseHTTPComponent, RequestBuilder, ResponseProcessor, RetryHandler,
    URLUtils, AsyncBatch, ResourceManager, MemoryOptimizer,
    HTTPError, ConnectionError, TimeoutError, ValidationError, SecurityError, RateLimitError,
    HTTPComponentProtocol, RequestProcessorProtocol, ResponseProcessorProtocol,
    validate_type, validate_optional_type
)
from .validation import InputValidator, ValidationConfig, get_global_validator

__all__ = [
    # Core HTTP components
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

    # Performance optimizations
    "OptimizedConnectionPool",
    "ConnectionPoolConfig",
    "SessionManager",
    "SessionConfig",
    "managed_session",
    "MetricsCollector",
    "RequestMetrics",
    "PerformanceStats",
    "get_global_metrics",

    # Security features
    "URLValidator",
    "SecurityMiddleware",
    "SSRFProtectionConfig",
    "InputValidator",
    "ValidationConfig",
    "get_global_validator",
    "SecurityErrorHandler",
    "SecureErrorConfig",
    "handle_http_error",

    # Utilities and patterns
    "BaseHTTPComponent",
    "RequestBuilder",
    "ResponseProcessor",
    "RetryHandler",
    "URLUtils",
    "AsyncBatch",
    "ResourceManager",
    "MemoryOptimizer",

    # Enhanced error types
    "HTTPError",
    "ConnectionError",
    "TimeoutError",
    "ValidationError",
    "SecurityError",
    "RateLimitError",

    # Protocols
    "HTTPComponentProtocol",
    "RequestProcessorProtocol",
    "ResponseProcessorProtocol",

    # Type validation
    "validate_type",
    "validate_optional_type",
]
