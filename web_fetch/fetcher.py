"""
Core async web fetcher implementation using AIOHTTP.

This module provides the main WebFetcher class that handles asynchronous HTTP requests
with proper session management, connection pooling, and modern Python features.

This is the main entry point that imports and re-exports all functionality from
the modular components in the src/ directory for backward compatibility.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from .models.base import ContentType

# Enhanced convenience functions
from .models.http import FetchConfig, FetchRequest, FetchResult
from .convenience import (
    download_file,
    fetch_url,
    fetch_urls,
    fetch_with_cache,
)

# Import all components from the modular structure
from .core_fetcher import WebFetcher
from .streaming_fetcher import StreamingWebFetcher
from .url_utils import (
    analyze_headers,
    analyze_url,
    detect_content_type,
    is_valid_url,
    normalize_url,
)
from .utils.cache import EnhancedCacheConfig
from .utils.circuit_breaker import CircuitBreakerConfig
from .utils.js_renderer import JSRenderConfig
from .utils.transformers import TransformationPipeline


async def enhanced_fetch_url(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Union[str, bytes, Dict[str, Any]]] = None,
    params: Optional[Dict[str, str]] = None,
    content_type: ContentType = ContentType.RAW,
    config: Optional[FetchConfig] = None,
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
    enable_deduplication: bool = True,
    enable_metrics: bool = True,
    transformation_pipeline: Optional[TransformationPipeline] = None,
    cache_config: Optional[EnhancedCacheConfig] = None,
    js_config: Optional[JSRenderConfig] = None,
) -> FetchResult:
    """
    Enhanced convenience function for single URL fetching with all advanced features.

    Args:
        url: URL to fetch
        method: HTTP method (default: GET)
        headers: Optional request headers
        data: Optional request data
        params: Optional query parameters
        content_type: Content type for parsing
        config: Optional fetch configuration
        circuit_breaker_config: Optional circuit breaker configuration
        enable_deduplication: Whether to enable request deduplication
        enable_metrics: Whether to collect metrics
        transformation_pipeline: Optional response transformation pipeline
        cache_config: Optional enhanced cache configuration
        js_config: Optional JavaScript rendering configuration

    Returns:
        FetchResult with response data and metadata
    """
    request = FetchRequest(
        url=url,  # Pydantic will convert string to HttpUrl
        method=method,
        headers=headers,
        data=data,
        params=params,
        content_type=content_type,
    )

    async with WebFetcher(
        config=config,
        circuit_breaker_config=circuit_breaker_config,
        enable_deduplication=enable_deduplication,
        enable_metrics=enable_metrics,
        transformation_pipeline=transformation_pipeline,
        cache_config=cache_config,
        js_config=js_config,
    ) as fetcher:
        return await fetcher.fetch_single(request)


async def enhanced_fetch_urls(
    urls: List[str],
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    content_type: ContentType = ContentType.RAW,
    config: Optional[FetchConfig] = None,
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
    enable_deduplication: bool = True,
    enable_metrics: bool = True,
    transformation_pipeline: Optional[TransformationPipeline] = None,
    cache_config: Optional[EnhancedCacheConfig] = None,
    js_config: Optional[JSRenderConfig] = None,
) -> List[FetchResult]:
    """
    Enhanced convenience function for batch URL fetching with all advanced features.

    Args:
        urls: List of URLs to fetch
        method: HTTP method (default: GET)
        headers: Optional request headers
        content_type: Content type for parsing
        config: Optional fetch configuration
        circuit_breaker_config: Optional circuit breaker configuration
        enable_deduplication: Whether to enable request deduplication
        enable_metrics: Whether to collect metrics
        transformation_pipeline: Optional response transformation pipeline
        cache_config: Optional enhanced cache configuration
        js_config: Optional JavaScript rendering configuration

    Returns:
        List of FetchResult objects
    """
    from .models.http import BatchFetchRequest

    requests = [
        FetchRequest(url=url, method=method, headers=headers, content_type=content_type)
        for url in urls
    ]

    batch_request = BatchFetchRequest(requests=requests)

    async with WebFetcher(
        config=config,
        circuit_breaker_config=circuit_breaker_config,
        enable_deduplication=enable_deduplication,
        enable_metrics=enable_metrics,
        transformation_pipeline=transformation_pipeline,
        cache_config=cache_config,
        js_config=js_config,
    ) as fetcher:
        batch_result = await fetcher.fetch_batch(batch_request)
        return batch_result.results


# Re-export all functionality for backward compatibility
__all__ = [
    # Core classes
    "WebFetcher",
    "StreamingWebFetcher",
    # Convenience functions
    "fetch_url",
    "fetch_urls",
    "download_file",
    "fetch_with_cache",
    # Enhanced convenience functions
    "enhanced_fetch_url",
    "enhanced_fetch_urls",
    # URL utilities
    "is_valid_url",
    "normalize_url",
    "analyze_url",
    "analyze_headers",
    "detect_content_type",
]
