"""
Tavily API crawler implementation.

This module provides the TavilyCrawler class that integrates with the Tavily API
for web search and content extraction operations. It uses the official Tavily Python SDK
and specializes in AI-powered search functionality.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

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

try:
    from tavily import AsyncTavilyClient, TavilyClient

    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False
    logger.warning("Tavily SDK not available. Install with: pip install tavily-python")


class TavilyCrawler(BaseCrawler):
    """
    Tavily API crawler implementation.

    Provides web search and content extraction capabilities using the Tavily API,
    which specializes in AI-powered search with high-quality content extraction.
    """

    def __init__(self, config: Optional[CrawlerConfig] = None):
        """Initialize the Tavily crawler."""
        if not TAVILY_AVAILABLE:
            raise CrawlerError(
                "Tavily SDK not available. Install with: pip install tavily-python"
            )

        super().__init__(config)

        # Initialize Tavily clients
        api_key = self.config.api_key
        if not api_key:
            raise CrawlerError("Tavily API key is required")

        self.sync_client = TavilyClient(api_key=api_key)
        self.async_client = AsyncTavilyClient(api_key=api_key)

    def _get_crawler_type(self) -> CrawlerType:
        """Return the crawler type."""
        return CrawlerType.TAVILY

    def get_capabilities(self) -> List[CrawlerCapability]:
        """Return supported capabilities."""
        return [
            CrawlerCapability.SEARCH,
            CrawlerCapability.EXTRACT,
            CrawlerCapability.CRAWL,
            CrawlerCapability.MAP,
        ]

    def _prepare_search_options(self, request: CrawlerRequest) -> Dict[str, Any]:
        """Prepare search options for Tavily API."""
        options = {
            "max_results": request.max_results or 5,
            "search_depth": request.search_depth or "basic",
            "include_images": self.config.include_images,
            "include_raw_content": (
                True if self.config.return_format in ["html", "raw"] else "markdown"
            ),
            "include_answer": True,  # Get AI-generated answer
        }

        # Domain filtering
        if self.config.include_domains:
            options["include_domains"] = self.config.include_domains

        if self.config.exclude_domains:
            options["exclude_domains"] = self.config.exclude_domains

        # Country-specific search
        if self.config.proxy_country:
            options["country"] = self.config.proxy_country

        return options

    def _prepare_extract_options(self, request: CrawlerRequest) -> Dict[str, Any]:
        """Prepare extract options for Tavily API."""
        options = {
            "include_images": self.config.include_images,
            "extract_depth": "advanced" if self.config.enable_javascript else "basic",
            "format": "markdown" if self.config.return_format == "markdown" else "text",
        }

        return options

    def _prepare_crawl_options(self, request: CrawlerRequest) -> Dict[str, Any]:
        """Prepare crawl options for Tavily API."""
        options = {
            "max_depth": request.depth or self.config.max_depth or 1,
            "limit": request.limit or self.config.max_pages or 50,
            "include_images": self.config.include_images,
            "extract_depth": "advanced" if self.config.enable_javascript else "basic",
            "format": "markdown" if self.config.return_format == "markdown" else "text",
        }

        # Domain filtering
        if self.config.include_domains:
            options["select_domains"] = ",".join([
                f"^{domain}$" for domain in self.config.include_domains
            ])

        if self.config.exclude_domains:
            options["exclude_domains"] = ",".join([
                f"^{domain}$" for domain in self.config.exclude_domains
            ])

        return options

    async def search(self, request: CrawlerRequest) -> CrawlerResult:
        """Perform a search operation using Tavily."""
        start_time = datetime.now()

        try:
            if not request.query:
                raise CrawlerError("Search query is required for search operation")

            # Prepare search options
            options = self._prepare_search_options(request)

            # Execute search
            result = await self.async_client.search(query=request.query, **options)

            # Process search results
            search_results = []
            all_content = []

            for item in result.get("results", []):
                search_result = {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "score": item.get("score", 0.0),
                }
                search_results.append(search_result)

                if search_result["content"]:
                    all_content.append(search_result["content"])

            # Combine content
            combined_content = "\n\n---\n\n".join(all_content)

            # Add AI-generated answer if available
            answer = result.get("answer")
            if answer:
                combined_content = (
                    f"**AI Answer:** {answer}\n\n---\n\n{combined_content}"
                )

            return CrawlerResult(
                url=str(request.url),
                crawler_type=self.crawler_type,
                operation=CrawlerCapability.SEARCH,
                content=combined_content,
                status_code=200,
                search_results=search_results,
                answer=answer,
                images=result.get("images", []),
                response_time=(datetime.now() - start_time).total_seconds(),
                timestamp=start_time,
                pages_crawled=len(search_results),
            )

        except Exception as e:
            logger.error(f"Tavily search failed: {str(e)}")
            return self._handle_error(e, request)

    async def extract(self, request: CrawlerRequest) -> CrawlerResult:
        """Perform content extraction using Tavily."""
        start_time = datetime.now()

        try:
            # Prepare extract options
            options = self._prepare_extract_options(request)

            # Execute extraction
            result = await self.async_client.extract(urls=[str(request.url)], **options)

            # Process extraction results
            successful_results = result.get("results", [])
            failed_results = result.get("failed_results", [])

            if failed_results:
                error_msg = failed_results[0].get("error", "Extraction failed")
                raise CrawlerError(f"Tavily extraction failed: {error_msg}")

            if not successful_results:
                raise CrawlerError("No content extracted from URL")

            extracted_data = successful_results[0]
            content = extracted_data.get("raw_content", "")
            images = extracted_data.get("images", [])

            return CrawlerResult(
                url=str(request.url),
                crawler_type=self.crawler_type,
                operation=CrawlerCapability.EXTRACT,
                content=content,
                status_code=200,
                images=images,
                response_time=(datetime.now() - start_time).total_seconds(),
                timestamp=start_time,
                pages_crawled=1,
            )

        except Exception as e:
            logger.error(f"Tavily extract failed: {str(e)}")
            return self._handle_error(e, request)

    async def crawl(self, request: CrawlerRequest) -> CrawlerResult:
        """Perform a crawl operation using Tavily."""
        start_time = datetime.now()

        try:
            # Prepare crawl options
            options = self._prepare_crawl_options(request)

            # Add instructions if provided
            if request.query:
                options["instructions"] = request.query

            # Execute crawl
            result = await self.async_client.crawl(url=str(request.url), **options)

            # Process crawl results
            crawl_results = result.get("results", [])
            all_content = []
            all_links = []
            all_images = []

            for page in crawl_results:
                content = page.get("raw_content", "")
                if content:
                    all_content.append(content)

                url = page.get("url", "")
                if url:
                    all_links.append(url)

                images = page.get("images", [])
                all_images.extend(images)

            # Combine content
            combined_content = "\n\n---\n\n".join(all_content)

            return CrawlerResult(
                url=str(request.url),
                crawler_type=self.crawler_type,
                operation=CrawlerCapability.CRAWL,
                content=combined_content,
                status_code=200,
                links=all_links,
                images=all_images,
                response_time=(datetime.now() - start_time).total_seconds(),
                timestamp=start_time,
                pages_crawled=len(crawl_results),
            )

        except Exception as e:
            logger.error(f"Tavily crawl failed: {str(e)}")
            return self._handle_error(e, request)

    async def scrape(self, request: CrawlerRequest) -> CrawlerResult:
        """Perform a scrape operation using Tavily (via extract)."""
        # Tavily doesn't have a dedicated scrape endpoint, use extract instead
        return await self.extract(request)
