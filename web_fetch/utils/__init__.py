"""
Utility modules for the web_fetch library.

This package contains specialized utility modules for URL handling, caching,
rate limiting, response analysis, validation, and advanced features like
circuit breakers, request deduplication, response transformation, and metrics.
"""

from .url import (
    is_valid_url,
    normalize_url,
    analyze_url,
    analyze_headers,
    detect_content_type,
)
from .cache import SimpleCache
from .rate_limit import RateLimiter
from .response import ResponseAnalyzer
from .validation import URLValidator
from .content_detector import ContentTypeDetector
from .error_handler import EnhancedErrorHandler, ErrorCategory, RetryStrategy, RetryConfig
from .advanced_rate_limiter import AdvancedRateLimiter, RateLimitConfig, RateLimitAlgorithm, RateLimitStrategy
from .cache import EnhancedCache, EnhancedCacheConfig, CacheBackend
from .js_renderer import JavaScriptRenderer, JSRenderConfig, BrowserType, WaitStrategy

# Advanced utilities
from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    with_circuit_breaker,
)
from .deduplication import (
    RequestDeduplicator,
    deduplicate_request,
    get_deduplication_stats,
)
from .transformers import (
    TransformationPipeline,
    JSONPathExtractor,
    HTMLExtractor,
    RegexExtractor,
    DataValidator,
)
from .metrics import (
    MetricsCollector,
    record_request_metrics,
    get_metrics_summary,
    get_recent_performance,
)

__all__ = [
    # URL utilities
    "is_valid_url",
    "normalize_url",
    "analyze_url",
    "analyze_headers",
    "detect_content_type",

    # Core utility classes
    "SimpleCache",
    "RateLimiter",
    "ResponseAnalyzer",
    "URLValidator",
    "ContentTypeDetector",
    "EnhancedErrorHandler",
    "ErrorCategory",
    "RetryStrategy",
    "RetryConfig",
    "AdvancedRateLimiter",
    "RateLimitConfig",
    "RateLimitAlgorithm",
    "RateLimitStrategy",
    "EnhancedCache",
    "CacheConfig",
    "CacheBackend",
    "JavaScriptRenderer",
    "JSRenderConfig",
    "BrowserType",
    "WaitStrategy",

    # Advanced utilities
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "with_circuit_breaker",
    "RequestDeduplicator",
    "deduplicate_request",
    "get_deduplication_stats",
    "TransformationPipeline",
    "JSONPathExtractor",
    "HTMLExtractor",
    "RegexExtractor",
    "DataValidator",
    "MetricsCollector",
    "record_request_metrics",
    "get_metrics_summary",
    "get_recent_performance",
]
