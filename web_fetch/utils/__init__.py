"""
Utility modules for the web_fetch library.

This package contains specialized utility modules for URL handling, caching,
rate limiting, response analysis, validation, and advanced features like
circuit breakers, request deduplication, response transformation, and metrics.
"""

from .advanced_rate_limiter import (
    AdvancedRateLimiter,
    RateLimitAlgorithm,
    RateLimitConfig,
    RateLimitStrategy,
)
from .cache import CacheBackend, EnhancedCache, EnhancedCacheConfig, SimpleCache

# Advanced utilities
from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    with_circuit_breaker,
)
from .content_detector import ContentTypeDetector
from .deduplication import (
    RequestDeduplicator,
    deduplicate_request,
    get_deduplication_stats,
)
from .error_handler import (
    EnhancedErrorHandler,
    ErrorCategory,
    RetryConfig,
    RetryStrategy,
)
from .js_renderer import BrowserType, JavaScriptRenderer, JSRenderConfig, WaitStrategy
from .metrics import (
    MetricsCollector,
    get_metrics_summary,
    get_recent_performance,
    record_request_metrics,
)
from .rate_limit import RateLimiter
from .response import ResponseAnalyzer
from .transformers import (
    DataValidator,
    HTMLExtractor,
    JSONPathExtractor,
    RegexExtractor,
    TransformationPipeline,
)
from .url import (
    analyze_headers,
    analyze_url,
    detect_content_type,
    is_valid_url,
    normalize_url,
)
from .validation import URLValidator

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
