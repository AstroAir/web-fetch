"""
Convenience functions for crawler APIs integration.

This module provides high-level convenience functions that integrate crawler APIs
with the existing WebFetcher patterns, maintaining backward compatibility while
adding new crawler capabilities.
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Dict, List, Optional

from pydantic import HttpUrl, TypeAdapter

from ..models.base import ContentType
from ..models.http import FetchConfig, FetchResult
from .base import CrawlerCapability, CrawlerConfig, CrawlerRequest, CrawlerType
from .config import config_manager
from .manager import CrawlerManager


def _to_http_url(url: str | HttpUrl) -> HttpUrl:
    """Validate/convert to HttpUrl using Pydantic TypeAdapter."""
    if isinstance(url, str):
        adapter = TypeAdapter(HttpUrl)
        return adapter.validate_python(url)
    return url


async def crawler_fetch_url(
    url: str | HttpUrl,
    use_crawler: bool = False,
    crawler_type: Optional[CrawlerType] = None,
    operation: CrawlerCapability = CrawlerCapability.SCRAPE,
    content_type: ContentType = ContentType.MARKDOWN,
    config: Optional[FetchConfig] = None,
    **crawler_kwargs: Any,
) -> FetchResult:
    """
    Enhanced fetch_url function with crawler API support.

    This function extends the standard fetch_url with optional crawler API
    integration while maintaining backward compatibility.

    Args:
        url: URL to fetch
        use_crawler: Whether to use crawler APIs instead of standard HTTP
        crawler_type: Specific crawler to use (None for automatic selection)
        operation: Type of crawler operation to perform
        content_type: Expected content type for parsing
        config: Standard FetchConfig for HTTP fallback
        **crawler_kwargs: Additional crawler-specific options

    Returns:
        FetchResult compatible with existing code
    """
    if not use_crawler:
        # Fall back to standard WebFetcher
        from ..convenience import fetch_url

        # Convert HttpUrl to string if needed
        url_str = str(url) if isinstance(url, HttpUrl) else url
        return await fetch_url(url_str, content_type, config)

    # Use crawler APIs
    try:
        # Get crawler configurations
        crawler_configs = config_manager.to_crawler_configs()

        # Create crawler manager
        manager = CrawlerManager(
            primary_crawler=config_manager.get_primary_crawler(),
            fallback_crawlers=config_manager.get_fallback_order(),
            crawler_configs=crawler_configs,
        )

        # Prepare crawler config from FetchConfig and kwargs
        crawler_config = _prepare_crawler_config(config, **crawler_kwargs)

        # Create crawler request
        request = CrawlerRequest(
            url=_to_http_url(url), operation=operation, config=crawler_config
        )

        # Execute request
        result = await manager.execute_request(request, force_crawler=crawler_type)

        # Convert to FetchResult for backward compatibility
        return result.to_fetch_result()

    except Exception:
        # Fall back to standard WebFetcher on crawler failure
        from ..convenience import fetch_url

        # Convert HttpUrl to string if needed
        url_str = str(url) if isinstance(url, HttpUrl) else url
        return await fetch_url(url_str, content_type, config)


async def crawler_fetch_urls(
    urls: List[str | HttpUrl],
    use_crawler: bool = False,
    crawler_type: Optional[CrawlerType] = None,
    operation: CrawlerCapability = CrawlerCapability.SCRAPE,
    content_type: ContentType = ContentType.MARKDOWN,
    config: Optional[FetchConfig] = None,
    **crawler_kwargs: Any,
) -> List[FetchResult]:
    """
    Enhanced fetch_urls function with crawler API support.

    Args:
        urls: List of URLs to fetch
        use_crawler: Whether to use crawler APIs
        crawler_type: Specific crawler to use
        operation: Type of crawler operation
        content_type: Expected content type
        config: Standard FetchConfig
        **crawler_kwargs: Additional crawler options

    Returns:
        List of FetchResult objects
    """
    if not use_crawler:
        # Fall back to standard WebFetcher
        from ..convenience import fetch_urls

        # Convert HttpUrl objects to strings if needed
        url_strings = [str(url) if isinstance(url, HttpUrl) else url for url in urls]
        batch_result = await fetch_urls(url_strings, content_type, config)
        return batch_result.results

    # Use crawler APIs for each URL
    tasks: List[Awaitable[FetchResult]] = []
    for url in urls:
        task = crawler_fetch_url(
            url=url,
            use_crawler=True,
            crawler_type=crawler_type,
            operation=operation,
            content_type=content_type,
            config=config,
            **crawler_kwargs,
        )
        tasks.append(task)

    results: List[FetchResult] = await asyncio.gather(*tasks, return_exceptions=False)
    return results


async def crawler_search_web(
    query: str,
    max_results: int = 5,
    crawler_type: Optional[CrawlerType] = None,
    **crawler_kwargs: Any,
) -> FetchResult:
    """
    Search the web using crawler APIs.

    Args:
        query: Search query
        max_results: Maximum number of results
        crawler_type: Specific crawler to use
        **crawler_kwargs: Additional crawler options

    Returns:
        FetchResult with search results
    """
    # Get crawler configurations
    crawler_configs = config_manager.to_crawler_configs()

    # Create crawler manager
    manager = CrawlerManager(
        primary_crawler=config_manager.get_primary_crawler(),
        fallback_crawlers=config_manager.get_fallback_order(),
        crawler_configs=crawler_configs,
    )

    # Prepare crawler config
    crawler_config = _prepare_crawler_config(None, **crawler_kwargs)

    # Create search request with validated placeholder HttpUrl
    adapter = TypeAdapter(HttpUrl)
    placeholder_url: HttpUrl = adapter.validate_python("https://example.com")
    request = CrawlerRequest(
        url=placeholder_url,  # Placeholder for search
        operation=CrawlerCapability.SEARCH,
        query=query,
        max_results=max_results,
        config=crawler_config,
    )

    # Execute search
    result = await manager.execute_request(request, force_crawler=crawler_type)

    # Convert to FetchResult
    return result.to_fetch_result()


async def crawler_crawl_website(
    url: str | HttpUrl,
    max_pages: Optional[int] = None,
    max_depth: Optional[int] = None,
    crawler_type: Optional[CrawlerType] = None,
    **crawler_kwargs: Any,
) -> FetchResult:
    """
    Crawl an entire website using crawler APIs.

    Args:
        url: Starting URL for crawling
        max_pages: Maximum pages to crawl
        max_depth: Maximum crawl depth
        crawler_type: Specific crawler to use
        **crawler_kwargs: Additional crawler options

    Returns:
        FetchResult with combined crawl results
    """
    # Get crawler configurations
    crawler_configs = config_manager.to_crawler_configs()

    # Create crawler manager
    manager = CrawlerManager(
        primary_crawler=config_manager.get_primary_crawler(),
        fallback_crawlers=config_manager.get_fallback_order(),
        crawler_configs=crawler_configs,
    )

    # Prepare crawler config
    crawler_config = _prepare_crawler_config(None, **crawler_kwargs)
    if max_pages is not None:
        crawler_config.max_pages = max_pages
    if max_depth is not None:
        crawler_config.max_depth = max_depth

    # Create crawl request
    request = CrawlerRequest(
        url=_to_http_url(url),
        operation=CrawlerCapability.CRAWL,
        limit=max_pages,
        depth=max_depth,
        config=crawler_config,
    )

    # Execute crawl
    result = await manager.execute_request(request, force_crawler=crawler_type)

    # Convert to FetchResult
    return result.to_fetch_result()


async def crawler_extract_content(
    url: str | HttpUrl,
    css_selector: Optional[str] = None,
    extract_schema: Optional[Dict[str, Any]] = None,
    crawler_type: Optional[CrawlerType] = None,
    **crawler_kwargs: Any,
) -> FetchResult:
    """
    Extract specific content from a URL using crawler APIs.

    Args:
        url: URL to extract content from
        css_selector: CSS selector for content extraction
        extract_schema: Schema for structured data extraction
        crawler_type: Specific crawler to use
        **crawler_kwargs: Additional crawler options

    Returns:
        FetchResult with extracted content
    """
    # Get crawler configurations
    crawler_configs = config_manager.to_crawler_configs()

    # Create crawler manager
    manager = CrawlerManager(
        primary_crawler=config_manager.get_primary_crawler(),
        fallback_crawlers=config_manager.get_fallback_order(),
        crawler_configs=crawler_configs,
    )

    # Prepare crawler config
    crawler_config = _prepare_crawler_config(None, **crawler_kwargs)

    # Create extract request
    request = CrawlerRequest(
        url=_to_http_url(url),
        operation=CrawlerCapability.EXTRACT,
        css_selector=css_selector,
        extract_schema=extract_schema,
        config=crawler_config,
    )

    # Execute extraction
    result = await manager.execute_request(request, force_crawler=crawler_type)

    # Convert to FetchResult
    return result.to_fetch_result()


def _prepare_crawler_config(
    config: Optional[FetchConfig] = None, **kwargs: Any
) -> CrawlerConfig:
    """
    Prepare CrawlerConfig from FetchConfig and additional kwargs.

    Args:
        config: Optional FetchConfig to convert
        **kwargs: Additional crawler-specific options

    Returns:
        CrawlerConfig object
    """
    crawler_config = CrawlerConfig()

    # Convert from FetchConfig if provided
    if config:
        crawler_config.timeout = config.total_timeout
        crawler_config.max_retries = config.max_retries
        crawler_config.retry_delay = config.retry_delay
        crawler_config.follow_redirects = config.follow_redirects
        crawler_config.custom_headers = config.headers.to_dict()

    # Apply additional kwargs
    for key, value in kwargs.items():
        if hasattr(crawler_config, key):
            setattr(crawler_config, key, value)

    return crawler_config


def get_crawler_status() -> Dict[str, Any]:
    """
    Get status of all crawler APIs.

    Returns:
        Dictionary with crawler status information
    """
    return config_manager.get_status()


def configure_crawler(
    crawler_type: CrawlerType,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    enabled: bool = True,
    **settings: Any,
) -> None:
    """
    Configure a specific crawler API.

    Args:
        crawler_type: Type of crawler to configure
        api_key: API key for the service
        base_url: Base URL for the API
        enabled: Whether to enable the crawler
        **settings: Additional crawler-specific settings
    """
    if api_key:
        config_manager.set_api_key(crawler_type, api_key)

    if base_url:
        config_manager.set_base_url(crawler_type, base_url)

    config_manager.enable_crawler(crawler_type, enabled)

    # Apply additional settings
    api_config = config_manager.get_config().get_crawler_config(crawler_type)
    api_config.custom_settings.update(settings)


def set_primary_crawler(crawler_type: CrawlerType) -> None:
    """Set the primary crawler for automatic selection."""
    config_manager.set_primary_crawler(crawler_type)


def set_fallback_order(crawlers: List[CrawlerType]) -> None:
    """Set the fallback order for crawler selection."""
    config_manager.set_fallback_order(crawlers)
