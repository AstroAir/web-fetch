"""
Unified crawler API interface for multiple web crawling services.

This module provides a unified interface for various web crawling APIs including
Spider.cloud, Firecrawl, Tavily, and AnyCrawl. It abstracts the differences between
these services while maintaining compatibility with the existing WebFetcher patterns.

Features:
- Unified interface for multiple crawler APIs
- Automatic fallback between different services
- Compatible with existing FetchResult structure
- Support for both sync and async operations
- Comprehensive error handling and retry logic
"""

from .base import (
    BaseCrawler,
    CrawlerType,
    CrawlerConfig,
    CrawlerRequest,
    CrawlerResult,
    CrawlerError,
    CrawlerCapability,
)
from .manager import CrawlerManager
from .spider_crawler import SpiderCrawler
from .firecrawl_crawler import FirecrawlCrawler
from .tavily_crawler import TavilyCrawler
from .anycrawl_crawler import AnyCrawlCrawler
from .config import config_manager, ConfigManager
from .convenience import (
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

__all__ = [
    # Base classes and types
    "BaseCrawler",
    "CrawlerType",
    "CrawlerConfig",
    "CrawlerRequest",
    "CrawlerResult",
    "CrawlerError",
    "CrawlerCapability",

    # Manager and config
    "CrawlerManager",
    "ConfigManager",
    "config_manager",

    # Crawler implementations
    "SpiderCrawler",
    "FirecrawlCrawler",
    "TavilyCrawler",
    "AnyCrawlCrawler",

    # Convenience functions
    "crawler_fetch_url",
    "crawler_fetch_urls",
    "crawler_search_web",
    "crawler_crawl_website",
    "crawler_extract_content",
    "get_crawler_status",
    "configure_crawler",
    "set_primary_crawler",
    "set_fallback_order",
]
