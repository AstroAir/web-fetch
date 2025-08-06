"""
Firecrawl API crawler implementation.

This module provides the FirecrawlCrawler class that integrates with the Firecrawl API
for web scraping and crawling operations. It uses the official Firecrawl Python SDK
and provides markdown conversion capabilities.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import (
    BaseCrawler,
    CrawlerType,
    CrawlerConfig,
    CrawlerRequest,
    CrawlerResult,
    CrawlerError,
    CrawlerCapability,
)

logger = logging.getLogger(__name__)

try:
    from firecrawl import FirecrawlApp, AsyncFirecrawlApp
    FIRECRAWL_AVAILABLE = True
except ImportError:
    FIRECRAWL_AVAILABLE = False
    logger.warning("Firecrawl SDK not available. Install with: pip install firecrawl-py")


class FirecrawlCrawler(BaseCrawler):
    """
    Firecrawl API crawler implementation.
    
    Provides web scraping and crawling capabilities using the Firecrawl API,
    which specializes in converting web content to clean markdown format.
    """
    
    def __init__(self, config: Optional[CrawlerConfig] = None):
        """Initialize the Firecrawl crawler."""
        if not FIRECRAWL_AVAILABLE:
            raise CrawlerError("Firecrawl SDK not available. Install with: pip install firecrawl-py")
        
        super().__init__(config)
        
        # Initialize Firecrawl clients
        api_key = self.config.api_key
        if not api_key:
            raise CrawlerError("Firecrawl API key is required")
        
        self.sync_client = FirecrawlApp(api_key=api_key)
        self.async_client = AsyncFirecrawlApp(api_key=api_key)
    
    def _get_crawler_type(self) -> CrawlerType:
        """Return the crawler type."""
        return CrawlerType.FIRECRAWL
    
    def get_capabilities(self) -> List[CrawlerCapability]:
        """Return supported capabilities."""
        return [
            CrawlerCapability.SCRAPE,
            CrawlerCapability.CRAWL,
            CrawlerCapability.SEARCH,
            CrawlerCapability.EXTRACT,
            CrawlerCapability.MAP,
            CrawlerCapability.JAVASCRIPT,
        ]
    
    def _prepare_scrape_options(self, request: CrawlerRequest) -> Dict[str, Any]:
        """Prepare scrape options for Firecrawl API."""
        options = {}
        
        # Format options
        formats = ['markdown']
        if self.config.return_format == 'html':
            formats.append('html')
        elif self.config.return_format == 'text':
            formats = ['text']
        
        options['formats'] = formats
        
        # Include options
        if self.config.include_metadata:
            options['includeTags'] = ['title', 'description', 'keywords']
        
        if self.config.include_links:
            options['includeLinks'] = True
        
        if self.config.include_images:
            options['includeImages'] = True
        
        # JavaScript rendering
        if self.config.enable_javascript:
            options['waitFor'] = 2000  # Wait 2 seconds for JS
            if self.config.wait_for_selector:
                options['waitForSelector'] = self.config.wait_for_selector
        
        # Custom headers
        if self.config.custom_headers:
            options['headers'] = self.config.custom_headers
        
        return options
    
    def _prepare_crawl_options(self, request: CrawlerRequest) -> Dict[str, Any]:
        """Prepare crawl options for Firecrawl API."""
        options = self._prepare_scrape_options(request)
        
        # Crawl-specific options
        if request.limit or self.config.max_pages:
            options['limit'] = request.limit or self.config.max_pages
        
        if request.depth or self.config.max_depth:
            options['maxDepth'] = request.depth or self.config.max_depth
        
        # Domain filtering
        if self.config.include_domains:
            options['allowedDomains'] = self.config.include_domains
        
        if self.config.exclude_domains:
            options['excludedDomains'] = self.config.exclude_domains
        
        return options
    
    async def scrape(self, request: CrawlerRequest) -> CrawlerResult:
        """Perform a scrape operation using Firecrawl."""
        start_time = datetime.now()
        
        try:
            # Prepare options
            options = self._prepare_scrape_options(request)
            
            # Execute scrape
            result = await self.async_client.scrape_url(
                url=str(request.url),
                **options
            )
            
            # Process result
            content = result.get('markdown', result.get('content', ''))
            metadata = result.get('metadata', {})
            
            return CrawlerResult(
                url=str(request.url),
                crawler_type=self.crawler_type,
                operation=CrawlerCapability.SCRAPE,
                content=content,
                status_code=200,
                title=metadata.get('title'),
                description=metadata.get('description'),
                language=metadata.get('language'),
                response_time=(datetime.now() - start_time).total_seconds(),
                timestamp=start_time,
                pages_crawled=1
            )
        
        except Exception as e:
            logger.error(f"Firecrawl scrape failed: {str(e)}")
            return self._handle_error(e, request)
    
    async def crawl(self, request: CrawlerRequest) -> CrawlerResult:
        """Perform a crawl operation using Firecrawl."""
        start_time = datetime.now()
        
        try:
            # Prepare options
            options = self._prepare_crawl_options(request)
            
            # Execute crawl
            result = await self.async_client.crawl_url(
                url=str(request.url),
                **options
            )
            
            # Process results
            pages = result.get('data', [])
            all_content = []
            all_links = []
            
            for page in pages:
                if page.get('markdown'):
                    all_content.append(page['markdown'])
                if page.get('metadata', {}).get('sourceURL'):
                    all_links.append(page['metadata']['sourceURL'])
            
            # Combine content
            combined_content = '\n\n---\n\n'.join(all_content)
            
            return CrawlerResult(
                url=str(request.url),
                crawler_type=self.crawler_type,
                operation=CrawlerCapability.CRAWL,
                content=combined_content,
                status_code=200,
                links=all_links,
                response_time=(datetime.now() - start_time).total_seconds(),
                timestamp=start_time,
                pages_crawled=len(pages)
            )
        
        except Exception as e:
            logger.error(f"Firecrawl crawl failed: {str(e)}")
            return self._handle_error(e, request)
    
    async def search(self, request: CrawlerRequest) -> CrawlerResult:
        """Perform a search operation using Firecrawl."""
        start_time = datetime.now()
        
        try:
            if not request.query:
                raise CrawlerError("Search query is required for search operation")
            
            # Prepare search options
            options = {
                'limit': request.max_results or 5,
                'formats': ['markdown']
            }
            
            # Execute search
            result = await self.async_client.search(
                query=request.query,
                **options
            )
            
            # Process search results
            search_results = []
            all_content = []
            
            for item in result.get('data', []):
                search_result = {
                    'title': item.get('metadata', {}).get('title', ''),
                    'url': item.get('metadata', {}).get('sourceURL', ''),
                    'content': item.get('markdown', ''),
                    'score': 1.0  # Firecrawl doesn't provide relevance scores
                }
                search_results.append(search_result)
                if search_result['content']:
                    all_content.append(search_result['content'])
            
            # Combine content
            combined_content = '\n\n---\n\n'.join(all_content)
            
            return CrawlerResult(
                url=str(request.url),
                crawler_type=self.crawler_type,
                operation=CrawlerCapability.SEARCH,
                content=combined_content,
                status_code=200,
                search_results=search_results,
                response_time=(datetime.now() - start_time).total_seconds(),
                timestamp=start_time,
                pages_crawled=len(search_results)
            )
        
        except Exception as e:
            logger.error(f"Firecrawl search failed: {str(e)}")
            return self._handle_error(e, request)
    
    async def extract(self, request: CrawlerRequest) -> CrawlerResult:
        """Perform content extraction using Firecrawl."""
        start_time = datetime.now()
        
        try:
            # For Firecrawl, extract is similar to scrape but with specific extraction schema
            options = self._prepare_scrape_options(request)
            
            # Add extraction schema if provided
            if request.extract_schema:
                options['extractorOptions'] = {
                    'extractionSchema': request.extract_schema
                }
            
            # Execute extraction
            result = await self.async_client.scrape_url(
                url=str(request.url),
                **options
            )
            
            # Process extracted data
            content = result.get('extract', result.get('markdown', ''))
            metadata = result.get('metadata', {})
            
            return CrawlerResult(
                url=str(request.url),
                crawler_type=self.crawler_type,
                operation=CrawlerCapability.EXTRACT,
                content=content,
                status_code=200,
                title=metadata.get('title'),
                description=metadata.get('description'),
                response_time=(datetime.now() - start_time).total_seconds(),
                timestamp=start_time,
                pages_crawled=1
            )
        
        except Exception as e:
            logger.error(f"Firecrawl extract failed: {str(e)}")
            return self._handle_error(e, request)
