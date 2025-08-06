"""
Spider.cloud API crawler implementation.

This module provides the SpiderCrawler class that integrates with the Spider.cloud API
for web scraping and crawling operations. It handles authentication, request formatting,
and response parsing for the Spider.cloud service.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

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


class SpiderCrawler(BaseCrawler):
    """
    Spider.cloud API crawler implementation.
    
    Provides web scraping and crawling capabilities using the Spider.cloud API,
    which offers high-performance crawling with JavaScript rendering and proxy support.
    """
    
    BASE_URL = "https://api.spider.cloud"
    
    def __init__(self, config: Optional[CrawlerConfig] = None):
        """Initialize the Spider crawler."""
        super().__init__(config)
        
        if not self.config.api_key:
            raise CrawlerError("Spider.cloud API key is required")
        
        self.session: Optional[aiohttp.ClientSession] = None
    
    def _get_crawler_type(self) -> CrawlerType:
        """Return the crawler type."""
        return CrawlerType.SPIDER
    
    def get_capabilities(self) -> List[CrawlerCapability]:
        """Return supported capabilities."""
        return [
            CrawlerCapability.SCRAPE,
            CrawlerCapability.CRAWL,
            CrawlerCapability.SEARCH,
            CrawlerCapability.SCREENSHOT,
            CrawlerCapability.JAVASCRIPT,
            CrawlerCapability.PROXY,
        ]
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self.session is None or self.session.closed:
            headers = {
                'Authorization': f'Bearer {self.config.api_key}',
                'Content-Type': 'application/json',
            }
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self.session = aiohttp.ClientSession(headers=headers, timeout=timeout)
        return self.session
    
    async def _close_session(self) -> None:
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _prepare_spider_request(self, request: CrawlerRequest) -> Dict[str, Any]:
        """Prepare request payload for Spider.cloud API."""
        payload = {
            'url': str(request.url),
            'return_format': self.config.return_format,
            'metadata': self.config.include_metadata,
            'return_page_links': self.config.include_links,
        }
        
        # Request type (http, chrome, smart)
        if self.config.enable_javascript:
            payload['request'] = 'chrome'
        else:
            payload['request'] = 'http'
        
        # Timeout
        payload['request_timeout'] = min(int(self.config.timeout), 255)
        
        # Proxy settings
        if self.config.use_proxy:
            payload['proxy_enabled'] = True
            if self.config.proxy_country:
                payload['country_code'] = self.config.proxy_country
        
        # Custom headers
        if self.config.custom_headers:
            payload['headers'] = self.config.custom_headers
        
        # Domain filtering
        if self.config.include_domains:
            payload['include_domains'] = self.config.include_domains
        
        if self.config.exclude_domains:
            payload['exclude_domains'] = self.config.exclude_domains
        
        # Wait for selector
        if self.config.wait_for_selector:
            payload['wait_for'] = {
                'selector': {
                    'selector': self.config.wait_for_selector,
                    'timeout': {'secs': 10, 'nanos': 0}
                }
            }
        
        return payload
    
    async def scrape(self, request: CrawlerRequest) -> CrawlerResult:
        """Perform a scrape operation using Spider.cloud."""
        start_time = datetime.now()
        
        try:
            session = await self._get_session()
            payload = self._prepare_spider_request(request)
            
            # Use scrape endpoint for single page
            async with session.post(f"{self.BASE_URL}/scrape", json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise CrawlerError(
                        f"Spider.cloud API error: {response.status} - {error_text}",
                        crawler_type=self.crawler_type,
                        status_code=response.status
                    )
                
                result_data = await response.json()
                
                # Spider returns a list even for single page scrape
                if isinstance(result_data, list) and result_data:
                    page_data = result_data[0]
                else:
                    raise CrawlerError("Invalid response format from Spider.cloud")
                
                # Extract content and metadata
                content = page_data.get('content', '')
                status_code = page_data.get('status', 200)
                costs = page_data.get('costs', {})
                
                return CrawlerResult(
                    url=str(request.url),
                    crawler_type=self.crawler_type,
                    operation=CrawlerCapability.SCRAPE,
                    content=content,
                    status_code=status_code,
                    total_cost=costs.get('total_cost'),
                    response_time=(datetime.now() - start_time).total_seconds(),
                    timestamp=start_time,
                    pages_crawled=1
                )
        
        except Exception as e:
            logger.error(f"Spider scrape failed: {str(e)}")
            return self._handle_error(e, request)
        finally:
            await self._close_session()
    
    async def crawl(self, request: CrawlerRequest) -> CrawlerResult:
        """Perform a crawl operation using Spider.cloud."""
        start_time = datetime.now()
        
        try:
            session = await self._get_session()
            payload = self._prepare_spider_request(request)
            
            # Add crawl-specific parameters
            if request.limit or self.config.max_pages:
                payload['limit'] = request.limit or self.config.max_pages
            
            if request.depth or self.config.max_depth:
                payload['depth'] = request.depth or self.config.max_depth
            
            # Use crawl endpoint for multiple pages
            async with session.post(f"{self.BASE_URL}/crawl", json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise CrawlerError(
                        f"Spider.cloud API error: {response.status} - {error_text}",
                        crawler_type=self.crawler_type,
                        status_code=response.status
                    )
                
                result_data = await response.json()
                
                if not isinstance(result_data, list):
                    raise CrawlerError("Invalid response format from Spider.cloud")
                
                # Process all crawled pages
                all_content = []
                all_links = []
                total_cost = 0
                pages_crawled = 0
                
                for page_data in result_data:
                    if page_data.get('content'):
                        all_content.append(page_data['content'])
                        pages_crawled += 1
                    
                    if page_data.get('url'):
                        all_links.append(page_data['url'])
                    
                    costs = page_data.get('costs', {})
                    total_cost += costs.get('total_cost', 0)
                
                # Combine content
                combined_content = '\n\n---\n\n'.join(all_content)
                
                return CrawlerResult(
                    url=str(request.url),
                    crawler_type=self.crawler_type,
                    operation=CrawlerCapability.CRAWL,
                    content=combined_content,
                    status_code=200,
                    links=all_links,
                    total_cost=total_cost,
                    response_time=(datetime.now() - start_time).total_seconds(),
                    timestamp=start_time,
                    pages_crawled=pages_crawled
                )
        
        except Exception as e:
            logger.error(f"Spider crawl failed: {str(e)}")
            return self._handle_error(e, request)
        finally:
            await self._close_session()
    
    async def search(self, request: CrawlerRequest) -> CrawlerResult:
        """Perform a search operation using Spider.cloud."""
        start_time = datetime.now()
        
        try:
            if not request.query:
                raise CrawlerError("Search query is required for search operation")
            
            session = await self._get_session()
            payload = {
                'query': request.query,
                'limit': request.max_results or 5,
                'return_format': self.config.return_format,
            }
            
            # Use search endpoint
            async with session.post(f"{self.BASE_URL}/search", json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise CrawlerError(
                        f"Spider.cloud search API error: {response.status} - {error_text}",
                        crawler_type=self.crawler_type,
                        status_code=response.status
                    )
                
                result_data = await response.json()
                
                if not isinstance(result_data, list):
                    raise CrawlerError("Invalid search response format from Spider.cloud")
                
                # Process search results
                search_results = []
                all_content = []
                total_cost = 0
                
                for item in result_data:
                    search_result = {
                        'title': item.get('title', ''),
                        'url': item.get('url', ''),
                        'content': item.get('content', ''),
                        'score': 1.0  # Spider doesn't provide relevance scores
                    }
                    search_results.append(search_result)
                    
                    if search_result['content']:
                        all_content.append(search_result['content'])
                    
                    costs = item.get('costs', {})
                    total_cost += costs.get('total_cost', 0)
                
                # Combine content
                combined_content = '\n\n---\n\n'.join(all_content)
                
                return CrawlerResult(
                    url=str(request.url),
                    crawler_type=self.crawler_type,
                    operation=CrawlerCapability.SEARCH,
                    content=combined_content,
                    status_code=200,
                    search_results=search_results,
                    total_cost=total_cost,
                    response_time=(datetime.now() - start_time).total_seconds(),
                    timestamp=start_time,
                    pages_crawled=len(search_results)
                )
        
        except Exception as e:
            logger.error(f"Spider search failed: {str(e)}")
            return self._handle_error(e, request)
        finally:
            await self._close_session()
    
    async def extract(self, request: CrawlerRequest) -> CrawlerResult:
        """Perform content extraction using Spider.cloud."""
        # For Spider.cloud, extraction is similar to scraping with specific selectors
        start_time = datetime.now()
        
        try:
            session = await self._get_session()
            payload = self._prepare_spider_request(request)
            
            # Add CSS selector for extraction if provided
            if request.css_selector:
                payload['root_selector'] = request.css_selector
            
            # Use scrape endpoint with extraction parameters
            async with session.post(f"{self.BASE_URL}/scrape", json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise CrawlerError(
                        f"Spider.cloud extract API error: {response.status} - {error_text}",
                        crawler_type=self.crawler_type,
                        status_code=response.status
                    )
                
                result_data = await response.json()
                
                if isinstance(result_data, list) and result_data:
                    page_data = result_data[0]
                else:
                    raise CrawlerError("Invalid response format from Spider.cloud")
                
                content = page_data.get('content', '')
                status_code = page_data.get('status', 200)
                costs = page_data.get('costs', {})
                
                return CrawlerResult(
                    url=str(request.url),
                    crawler_type=self.crawler_type,
                    operation=CrawlerCapability.EXTRACT,
                    content=content,
                    status_code=status_code,
                    total_cost=costs.get('total_cost'),
                    response_time=(datetime.now() - start_time).total_seconds(),
                    timestamp=start_time,
                    pages_crawled=1
                )
        
        except Exception as e:
            logger.error(f"Spider extract failed: {str(e)}")
            return self._handle_error(e, request)
        finally:
            await self._close_session()
