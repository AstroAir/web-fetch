"""
AnyCrawl API crawler implementation.

This module provides the AnyCrawlCrawler class that integrates with the AnyCrawl API
for web scraping and crawling operations. AnyCrawl is an open-source crawler that
provides LLM-friendly output and multi-threaded performance.
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


class AnyCrawlCrawler(BaseCrawler):
    """
    AnyCrawl API crawler implementation.
    
    Provides web scraping and crawling capabilities using the AnyCrawl API,
    which is an open-source, multi-threaded crawler optimized for LLM-friendly output.
    """
    
    def __init__(self, config: Optional[CrawlerConfig] = None):
        """Initialize the AnyCrawl crawler."""
        super().__init__(config)
        
        # AnyCrawl is typically self-hosted, so we need a base URL
        # This can be configured via the api_key field or a separate config
        self.base_url = getattr(config, 'base_url', 'http://localhost:3000') if config else 'http://localhost:3000'
        
        self.session: Optional[aiohttp.ClientSession] = None
    
    def _get_crawler_type(self) -> CrawlerType:
        """Return the crawler type."""
        return CrawlerType.ANYCRAWL
    
    def get_capabilities(self) -> List[CrawlerCapability]:
        """Return supported capabilities."""
        return [
            CrawlerCapability.SCRAPE,
            CrawlerCapability.CRAWL,
            CrawlerCapability.SEARCH,
            CrawlerCapability.EXTRACT,
        ]
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self.session is None or self.session.closed:
            headers = {
                'Content-Type': 'application/json',
            }
            
            # Add API key if provided
            if self.config.api_key:
                headers['Authorization'] = f'Bearer {self.config.api_key}'
            
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self.session = aiohttp.ClientSession(headers=headers, timeout=timeout)
        return self.session
    
    async def _close_session(self) -> None:
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _prepare_anycrawl_request(self, request: CrawlerRequest) -> Dict[str, Any]:
        """Prepare request payload for AnyCrawl API."""
        payload = {
            'url': str(request.url),
            'format': self.config.return_format,
            'include_metadata': self.config.include_metadata,
            'include_links': self.config.include_links,
            'include_images': self.config.include_images,
        }
        
        # JavaScript rendering
        if self.config.enable_javascript:
            payload['javascript'] = True
            if self.config.wait_for_selector:
                payload['wait_for_selector'] = self.config.wait_for_selector
        
        # Custom headers
        if self.config.custom_headers:
            payload['headers'] = self.config.custom_headers
        
        # Domain filtering
        if self.config.include_domains:
            payload['allowed_domains'] = self.config.include_domains
        
        if self.config.exclude_domains:
            payload['blocked_domains'] = self.config.exclude_domains
        
        return payload
    
    async def scrape(self, request: CrawlerRequest) -> CrawlerResult:
        """Perform a scrape operation using AnyCrawl."""
        start_time = datetime.now()
        
        try:
            session = await self._get_session()
            payload = self._prepare_anycrawl_request(request)
            
            # Use scrape endpoint
            async with session.post(f"{self.base_url}/api/scrape", json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise CrawlerError(
                        f"AnyCrawl API error: {response.status} - {error_text}",
                        crawler_type=self.crawler_type,
                        status_code=response.status
                    )
                
                result_data = await response.json()
                
                # Extract content and metadata
                content = result_data.get('content', '')
                metadata = result_data.get('metadata', {})
                links = result_data.get('links', [])
                images = result_data.get('images', [])
                
                return CrawlerResult(
                    url=str(request.url),
                    crawler_type=self.crawler_type,
                    operation=CrawlerCapability.SCRAPE,
                    content=content,
                    status_code=200,
                    title=metadata.get('title'),
                    description=metadata.get('description'),
                    language=metadata.get('language'),
                    links=links,
                    images=images,
                    response_time=(datetime.now() - start_time).total_seconds(),
                    timestamp=start_time,
                    pages_crawled=1
                )
        
        except Exception as e:
            logger.error(f"AnyCrawl scrape failed: {str(e)}")
            return self._handle_error(e, request)
        finally:
            await self._close_session()
    
    async def crawl(self, request: CrawlerRequest) -> CrawlerResult:
        """Perform a crawl operation using AnyCrawl."""
        start_time = datetime.now()
        
        try:
            session = await self._get_session()
            payload = self._prepare_anycrawl_request(request)
            
            # Add crawl-specific parameters
            if request.limit or self.config.max_pages:
                payload['max_pages'] = request.limit or self.config.max_pages
            
            if request.depth or self.config.max_depth:
                payload['max_depth'] = request.depth or self.config.max_depth
            
            # Use crawl endpoint
            async with session.post(f"{self.base_url}/api/crawl", json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise CrawlerError(
                        f"AnyCrawl API error: {response.status} - {error_text}",
                        crawler_type=self.crawler_type,
                        status_code=response.status
                    )
                
                result_data = await response.json()
                
                # Process crawled pages
                pages = result_data.get('pages', [])
                all_content = []
                all_links = []
                all_images = []
                
                for page in pages:
                    if page.get('content'):
                        all_content.append(page['content'])
                    
                    if page.get('url'):
                        all_links.append(page['url'])
                    
                    if page.get('images'):
                        all_images.extend(page['images'])
                
                # Combine content
                combined_content = '\n\n---\n\n'.join(all_content)
                
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
                    pages_crawled=len(pages)
                )
        
        except Exception as e:
            logger.error(f"AnyCrawl crawl failed: {str(e)}")
            return self._handle_error(e, request)
        finally:
            await self._close_session()
    
    async def search(self, request: CrawlerRequest) -> CrawlerResult:
        """Perform a search operation using AnyCrawl."""
        start_time = datetime.now()
        
        try:
            if not request.query:
                raise CrawlerError("Search query is required for search operation")
            
            session = await self._get_session()
            payload = {
                'query': request.query,
                'max_results': request.max_results or 5,
                'format': self.config.return_format,
            }
            
            # Use search endpoint
            async with session.post(f"{self.base_url}/api/search", json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise CrawlerError(
                        f"AnyCrawl search API error: {response.status} - {error_text}",
                        crawler_type=self.crawler_type,
                        status_code=response.status
                    )
                
                result_data = await response.json()
                
                # Process search results
                results = result_data.get('results', [])
                search_results = []
                all_content = []
                
                for item in results:
                    search_result = {
                        'title': item.get('title', ''),
                        'url': item.get('url', ''),
                        'content': item.get('content', ''),
                        'score': item.get('score', 1.0)
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
            logger.error(f"AnyCrawl search failed: {str(e)}")
            return self._handle_error(e, request)
        finally:
            await self._close_session()
    
    async def extract(self, request: CrawlerRequest) -> CrawlerResult:
        """Perform content extraction using AnyCrawl."""
        start_time = datetime.now()
        
        try:
            session = await self._get_session()
            payload = self._prepare_anycrawl_request(request)
            
            # Add extraction-specific parameters
            if request.css_selector:
                payload['selector'] = request.css_selector
            
            if request.extract_schema:
                payload['schema'] = request.extract_schema
            
            # Use extract endpoint
            async with session.post(f"{self.base_url}/api/extract", json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise CrawlerError(
                        f"AnyCrawl extract API error: {response.status} - {error_text}",
                        crawler_type=self.crawler_type,
                        status_code=response.status
                    )
                
                result_data = await response.json()
                
                # Extract content
                content = result_data.get('extracted_content', result_data.get('content', ''))
                metadata = result_data.get('metadata', {})
                
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
            logger.error(f"AnyCrawl extract failed: {str(e)}")
            return self._handle_error(e, request)
        finally:
            await self._close_session()
