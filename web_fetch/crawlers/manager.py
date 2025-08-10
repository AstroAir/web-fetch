"""
Crawler Manager for coordinating multiple crawler APIs with fallback logic.

This module provides the CrawlerManager class that manages multiple crawler
implementations, handles fallback mechanisms, and provides a unified interface
for web crawling operations.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Type, cast

from pydantic import HttpUrl, TypeAdapter

from .base import (
    BaseCrawler,
    CrawlerCapability,
    CrawlerConfig,
    CrawlerError,
    CrawlerRequest,
    CrawlerResult,
    CrawlerType,
)

logger = logging.getLogger(__name__)


class CrawlerManager:
    """
    Manager class for coordinating multiple crawler APIs with fallback logic.

    The CrawlerManager provides a unified interface for web crawling operations
    while managing multiple crawler implementations and handling fallback scenarios
    when primary crawlers fail or are unavailable.
    """

    def __init__(
        self,
        primary_crawler: Optional[CrawlerType] = None,
        fallback_crawlers: Optional[List[CrawlerType]] = None,
        crawler_configs: Optional[Dict[CrawlerType, CrawlerConfig]] = None,
    ):
        """
        Initialize the CrawlerManager.

        Args:
            primary_crawler: The preferred crawler to use first
            fallback_crawlers: List of fallback crawlers in order of preference
            crawler_configs: Configuration for each crawler type
        """
        self.primary_crawler = primary_crawler or CrawlerType.FIRECRAWL
        self.fallback_crawlers = fallback_crawlers or [
            CrawlerType.SPIDER,
            CrawlerType.TAVILY,
            CrawlerType.ANYCRAWL,
        ]
        self.crawler_configs = crawler_configs or {}

        # Registry of crawler implementations
        self._crawler_registry: Dict[CrawlerType, Type[BaseCrawler]] = {}
        self._crawler_instances: Dict[CrawlerType, BaseCrawler] = {}

        # Initialize crawler registry
        self._register_crawlers()

    def _register_crawlers(self) -> None:
        """Register all available crawler implementations."""
        try:
            from .spider_crawler import SpiderCrawler

            self._crawler_registry[CrawlerType.SPIDER] = SpiderCrawler
        except ImportError:
            logger.warning("Spider crawler not available")

        try:
            from .firecrawl_crawler import FirecrawlCrawler

            self._crawler_registry[CrawlerType.FIRECRAWL] = FirecrawlCrawler
        except ImportError:
            logger.warning("Firecrawl crawler not available")

        try:
            from .tavily_crawler import TavilyCrawler

            self._crawler_registry[CrawlerType.TAVILY] = TavilyCrawler
        except ImportError:
            logger.warning("Tavily crawler not available")

        try:
            from .anycrawl_crawler import AnyCrawlCrawler

            self._crawler_registry[CrawlerType.ANYCRAWL] = AnyCrawlCrawler
        except ImportError:
            logger.warning("AnyCrawl crawler not available")

    def _get_crawler_instance(self, crawler_type: CrawlerType) -> BaseCrawler:
        """Get or create a crawler instance."""
        if crawler_type not in self._crawler_instances:
            if crawler_type not in self._crawler_registry:
                raise CrawlerError(f"Crawler {crawler_type.value} not available")

            config = self.crawler_configs.get(crawler_type, CrawlerConfig())
            crawler_class = self._crawler_registry[crawler_type]
            self._crawler_instances[crawler_type] = crawler_class(config)

        return self._crawler_instances[crawler_type]

    def get_available_crawlers(self) -> List[CrawlerType]:
        """Get list of available crawler types."""
        return list(self._crawler_registry.keys())

    def get_crawler_capabilities(
        self, crawler_type: CrawlerType
    ) -> List[CrawlerCapability]:
        """Get capabilities of a specific crawler."""
        try:
            crawler = self._get_crawler_instance(crawler_type)
            return crawler.get_capabilities()
        except Exception:
            return []

    def find_capable_crawlers(self, capability: CrawlerCapability) -> List[CrawlerType]:
        """Find all crawlers that support a specific capability."""
        capable_crawlers = []
        for crawler_type in self.get_available_crawlers():
            try:
                crawler = self._get_crawler_instance(crawler_type)
                if crawler.supports_capability(capability):
                    capable_crawlers.append(crawler_type)
            except Exception:
                continue
        return capable_crawlers

    def _get_crawler_order(self, capability: CrawlerCapability) -> List[CrawlerType]:
        """Get the order of crawlers to try for a specific capability."""
        capable_crawlers = self.find_capable_crawlers(capability)

        # Start with primary crawler if it supports the capability
        crawler_order: List[CrawlerType] = []
        if self.primary_crawler in capable_crawlers:
            crawler_order.append(self.primary_crawler)

        # Add fallback crawlers that support the capability
        for crawler_type in self.fallback_crawlers:
            if crawler_type in capable_crawlers and crawler_type not in crawler_order:
                crawler_order.append(crawler_type)

        # Add any remaining capable crawlers
        for crawler_type in capable_crawlers:
            if crawler_type not in crawler_order:
                crawler_order.append(crawler_type)

        return crawler_order

    async def execute_request(
        self, request: CrawlerRequest, force_crawler: Optional[CrawlerType] = None
    ) -> CrawlerResult:
        """
        Execute a crawler request with automatic fallback.

        Args:
            request: The crawler request to execute
            force_crawler: Force use of a specific crawler (no fallback)

        Returns:
            CrawlerResult with the response data

        Raises:
            CrawlerError: If all crawlers fail or no capable crawler is found
        """
        if force_crawler:
            # Use specific crawler without fallback
            crawler = self._get_crawler_instance(force_crawler)
            return await crawler.execute_request(request)

        # Get ordered list of crawlers to try
        crawler_order = self._get_crawler_order(request.operation)

        if not crawler_order:
            operation_str = request.operation.value if hasattr(request.operation, 'value') else str(request.operation)
            raise CrawlerError(
                f"No available crawler supports {operation_str} operation"
            )

        last_error: Optional[CrawlerError] = None

        # Try each crawler in order
        for crawler_type in crawler_order:
            try:
                operation_str = request.operation.value if hasattr(request.operation, 'value') else str(request.operation)
                logger.info(
                    f"Attempting {operation_str} with {crawler_type.value}"
                )
                crawler = self._get_crawler_instance(crawler_type)
                result = await crawler.execute_request(request)

                if result.is_success:
                    operation_str = request.operation.value if hasattr(request.operation, 'value') else str(request.operation)
                    logger.info(
                        f"Successfully completed {operation_str} with {crawler_type.value}"
                    )
                    return result
                else:
                    logger.warning(
                        f"{crawler_type.value} returned error: {result.error}"
                    )
                    last_error = CrawlerError(
                        f"{crawler_type.value} failed: {result.error}",
                        crawler_type=crawler_type,
                        status_code=result.status_code,
                    )

            except Exception as e:
                logger.warning(f"{crawler_type.value} failed with exception: {str(e)}")
                last_error = CrawlerError(
                    f"{crawler_type.value} failed: {str(e)}",
                    crawler_type=crawler_type,
                    original_error=e,
                )
                continue

        # All crawlers failed
        operation_str = request.operation.value if hasattr(request.operation, 'value') else str(request.operation)
        error_msg = f"All crawlers failed for {operation_str} operation"
        if last_error:
            error_msg += f". Last error: {last_error}"

        raise CrawlerError(error_msg)

    def _to_http_url(self, url: str | HttpUrl) -> HttpUrl:
        """Validate/convert to HttpUrl using Pydantic TypeAdapter."""
        if isinstance(url, str):
            adapter = TypeAdapter(HttpUrl)
            return adapter.validate_python(url)
        return url

    async def scrape_url(self, url: str | HttpUrl, **kwargs: Any) -> CrawlerResult:
        """Convenience method to scrape a single URL."""
        config = CrawlerConfig(**kwargs) if kwargs else None
        request = CrawlerRequest(
            url=self._to_http_url(url),
            operation=CrawlerCapability.SCRAPE,
            config=config,
        )
        return await self.execute_request(request)

    async def crawl_website(self, url: str | HttpUrl, **kwargs: Any) -> CrawlerResult:
        """Convenience method to crawl a website."""
        config = CrawlerConfig(**kwargs) if kwargs else None
        request = CrawlerRequest(
            url=self._to_http_url(url), operation=CrawlerCapability.CRAWL, config=config
        )
        return await self.execute_request(request)

    async def search_web(self, query: str, **kwargs: Any) -> CrawlerResult:
        """Convenience method to search the web."""
        config = CrawlerConfig(**kwargs) if kwargs else None
        # Validate placeholder URL as HttpUrl
        adapter = TypeAdapter(HttpUrl)
        placeholder_url: HttpUrl = adapter.validate_python("https://example.com")
        request = CrawlerRequest(
            url=placeholder_url,  # Placeholder URL for search
            operation=CrawlerCapability.SEARCH,
            query=query,
            config=config,
        )
        return await self.execute_request(request)

    async def extract_content(self, url: str | HttpUrl, **kwargs: Any) -> CrawlerResult:
        """Convenience method to extract content from a URL."""
        config = CrawlerConfig(**kwargs) if kwargs else None
        request = CrawlerRequest(
            url=self._to_http_url(url),
            operation=CrawlerCapability.EXTRACT,
            config=config,
        )
        return await self.execute_request(request)

    def get_status(self) -> Dict[str, Any]:
        """Get status information about available crawlers."""
        status: Dict[str, Any] = {
            "primary_crawler": self.primary_crawler.value,
            "fallback_crawlers": [c.value for c in self.fallback_crawlers],
            "available_crawlers": [c.value for c in self.get_available_crawlers()],
            "crawler_capabilities": {},  # will be Dict[str, List[str]]
        }

        # Ensure correct type for crawler_capabilities
        capabilities_map: Dict[str, List[str]] = {}
        for crawler_type in self.get_available_crawlers():
            capabilities = self.get_crawler_capabilities(crawler_type)
            capabilities_map[crawler_type.value] = [c.value for c in capabilities]
        status["crawler_capabilities"] = capabilities_map

        return status
