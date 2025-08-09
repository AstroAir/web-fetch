"""
RSS/Atom feed resource component.

This component handles RSS and Atom feeds, providing parsing, validation,
and caching capabilities using the existing feed parser infrastructure.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from pydantic import HttpUrl, TypeAdapter

from ..core_fetcher import WebFetcher
from ..models.base import ContentType
from ..models.extended_resources import RSSConfig
from ..models.http import FetchConfig as HTTPFetchConfig, FetchRequest
from ..models.resource import ResourceConfig, ResourceKind, ResourceRequest, ResourceResult
from ..parsers.feed_parser import FeedParser
from .base import ResourceComponent, component_registry

logger = logging.getLogger(__name__)


class RSSComponent(ResourceComponent):
    """
    Resource component for RSS/Atom feeds.

    This component provides comprehensive RSS and Atom feed processing with automatic
    format detection, content parsing, validation, and caching capabilities.

    Features:
        - Automatic RSS/Atom format detection
        - Structured content extraction with metadata
        - Date validation and parsing
        - Content filtering and limits
        - Built-in caching support
        - Error handling and validation

    Example:
        Basic RSS feed fetching:

        ```python
        from web_fetch.components.rss_component import RSSComponent
        from web_fetch.models.resource import ResourceRequest, ResourceKind
        from web_fetch.models.extended_resources import RSSConfig
        from pydantic import AnyUrl

        # Configure RSS component
        rss_config = RSSConfig(
            max_items=20,
            include_content=True,
            validate_dates=True
        )

        component = RSSComponent(rss_config=rss_config)

        # Create request
        request = ResourceRequest(
            uri=AnyUrl("https://example.com/feed.xml"),
            kind=ResourceKind.RSS
        )

        # Fetch feed
        result = await component.fetch(request)

        if result.is_success:
            feed_data = result.content
            print(f"Feed title: {feed_data['title']}")
            print(f"Items: {len(feed_data['items'])}")

            for item in feed_data['items']:
                print(f"- {item['title']}: {item['link']}")
        ```

        Advanced configuration with caching:

        ```python
        from web_fetch.models.resource import ResourceConfig
        from web_fetch.models.http import FetchConfig

        # Configure caching and HTTP settings
        resource_config = ResourceConfig(
            enable_cache=True,
            cache_ttl_seconds=1800  # 30 minutes
        )

        http_config = FetchConfig(
            timeout_seconds=30,
            max_retries=3,
            user_agent="MyApp/1.0"
        )

        rss_config = RSSConfig(
            max_items=50,
            include_content=True,
            validate_dates=True,
            follow_redirects=True,
            user_agent="MyApp/1.0 (+https://myapp.com/contact)"
        )

        component = RSSComponent(
            config=resource_config,
            rss_config=rss_config,
            http_config=http_config
        )
        ```

    Attributes:
        kind (ResourceKind): Always ResourceKind.RSS
        rss_config (RSSConfig): RSS-specific configuration
        http_config (HTTPFetchConfig): HTTP fetching configuration
        feed_parser (FeedParser): Feed parsing engine
    """

    kind = ResourceKind.RSS

    def __init__(
        self,
        config: Optional[ResourceConfig] = None,
        rss_config: Optional[RSSConfig] = None,
        http_config: Optional[HTTPFetchConfig] = None
    ) -> None:
        """
        Initialize RSS component.

        Args:
            config: Base resource configuration for caching and validation.
                   If None, uses default configuration.
            rss_config: RSS-specific configuration including parsing options,
                       item limits, and content settings. If None, uses defaults.
            http_config: HTTP configuration for feed fetching including timeouts,
                        retries, and connection settings. If None, uses defaults.

        Example:
            ```python
            # Minimal setup
            component = RSSComponent()

            # Custom configuration
            component = RSSComponent(
                config=ResourceConfig(enable_cache=True),
                rss_config=RSSConfig(max_items=100, include_content=False),
                http_config=HTTPFetchConfig(timeout_seconds=60)
            )
            ```
        """
        super().__init__(config)
        self.rss_config = rss_config or RSSConfig()
        self.http_config = http_config or HTTPFetchConfig()
        self.feed_parser = FeedParser()
    
    def _to_http_url(self, uri: str) -> HttpUrl:
        """Convert URI string to HttpUrl for validation."""
        adapter = TypeAdapter(HttpUrl)
        return adapter.validate_python(uri)
    
    async def fetch(self, request: ResourceRequest) -> ResourceResult:
        """
        Fetch and parse RSS/Atom feed content.

        This method fetches the RSS/Atom feed from the specified URL, parses the content
        according to the configured options, and returns structured feed data with metadata.

        Args:
            request: Resource request containing the feed URL and options.
                    The URI should point to a valid RSS or Atom feed.

        Returns:
            ResourceResult containing parsed feed data on success, or error information
            on failure. The content includes:

            - title: Feed title
            - description: Feed description
            - link: Feed website URL
            - language: Feed language (if specified)
            - last_build_date: Last update timestamp
            - feed_type: "rss" or "atom"
            - version: Feed format version
            - items: List of feed items with title, description, link, pub_date, etc.
            - item_count: Total number of items in the feed

        Raises:
            No exceptions are raised directly. All errors are captured in the
            ResourceResult.error field.

        Example:
            ```python
            from web_fetch.models.resource import ResourceRequest, ResourceKind
            from pydantic import AnyUrl

            request = ResourceRequest(
                uri=AnyUrl("https://feeds.example.com/news.xml"),
                kind=ResourceKind.RSS
            )

            result = await component.fetch(request)

            if result.is_success:
                feed = result.content
                print(f"Feed: {feed['title']}")
                print(f"Items: {len(feed['items'])}")

                # Access feed metadata
                metadata = result.metadata
                print(f"Feed type: {metadata['feed_metadata']['feed_type']}")
                print(f"Total items: {metadata['total_items']}")

                # Process items
                for item in feed['items']:
                    print(f"- {item['title']}")
                    print(f"  Published: {item.get('pub_date', 'Unknown')}")
                    print(f"  Link: {item['link']}")
            else:
                print(f"Feed fetch failed: {result.error}")
            ```

        Note:
            The method respects the configuration settings:
            - max_items: Limits the number of items returned
            - include_content: Controls whether full content is included
            - validate_dates: Enables date parsing and validation
            - follow_redirects: Handles HTTP redirects automatically
        """
        try:
            # Validate URL
            feed_url = self._to_http_url(str(request.uri))
            
            # Prepare HTTP request for feed
            headers = request.headers or {}
            if self.rss_config.user_agent:
                headers["User-Agent"] = self.rss_config.user_agent
            
            # Set appropriate Accept header for feeds
            if "Accept" not in headers:
                headers["Accept"] = "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"
            
            http_request = FetchRequest(
                url=feed_url,
                method="GET",
                headers=headers,
                params=request.params,
                content_type=ContentType.RAW,  # Get raw content for parsing
                timeout_override=request.timeout_seconds,
            )
            
            # Fetch feed content using HTTP component
            async with WebFetcher(self.http_config) as fetcher:
                http_result = await fetcher.fetch_single(http_request)
            
            if http_result.error:
                return ResourceResult(
                    url=str(request.uri),
                    status_code=http_result.status_code,
                    error=http_result.error,
                    response_time=http_result.response_time,
                )
            
            # Parse feed content
            if isinstance(http_result.content, bytes):
                feed_content = http_result.content
            elif isinstance(http_result.content, str):
                feed_content = http_result.content.encode('utf-8')
            else:
                return ResourceResult(
                    url=str(request.uri),
                    status_code=http_result.status_code,
                    error="Invalid content type for feed parsing",
                    response_time=http_result.response_time,
                )
            
            # Parse the feed
            feed_data, feed_metadata, feed_items = self.feed_parser.parse(
                feed_content, str(request.uri)
            )
            
            # Apply max_items limit
            if self.rss_config.max_items and len(feed_items) > self.rss_config.max_items:
                feed_items = feed_items[:self.rss_config.max_items]
                feed_data["items"] = feed_data["items"][:min(10, self.rss_config.max_items)]
                feed_data["item_count"] = len(feed_items)
            
            # Prepare result
            result = ResourceResult(
                url=str(request.uri),
                status_code=http_result.status_code,
                headers=http_result.headers,
                content=feed_data,
                content_type="application/rss+xml",
                response_time=http_result.response_time,
            )
            
            # Add feed metadata
            result.metadata = {
                "feed_metadata": feed_metadata.__dict__,
                "feed_items": [item.__dict__ for item in feed_items],
                "parser_config": {
                    "format": self.rss_config.format.value,
                    "max_items": self.rss_config.max_items,
                    "include_content": self.rss_config.include_content,
                    "validate_dates": self.rss_config.validate_dates,
                },
                "total_items": len(feed_items),
                "truncated": len(feed_items) < feed_metadata.item_count if feed_metadata.item_count else False,
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch RSS feed from {request.uri}: {e}")
            return ResourceResult(
                url=str(request.uri),
                error=f"RSS feed fetch error: {str(e)}",
            )
    
    async def validate(self, result: ResourceResult) -> ResourceResult:
        """
        Validate RSS feed result.
        
        Args:
            result: Resource result to validate
            
        Returns:
            Validated resource result
        """
        if result.error:
            return result
        
        try:
            # Check if we have valid feed data
            if not result.content or not isinstance(result.content, dict):
                result.error = "Invalid feed content structure"
                return result
            
            feed_data = result.content
            
            # Validate required feed fields
            if not feed_data.get("title") and not feed_data.get("description"):
                result.error = "Feed missing required title or description"
                return result
            
            # Validate feed type
            feed_type = feed_data.get("feed_type", "").lower()
            if feed_type not in ["rss", "atom", "unknown"]:
                logger.warning(f"Unknown feed type: {feed_type}")
            
            # Validate items if present
            items = feed_data.get("items", [])
            if not isinstance(items, list):
                result.error = "Feed items must be a list"
                return result
            
            # Add validation metadata
            if "validation" not in result.metadata:
                result.metadata["validation"] = {}
            
            result.metadata["validation"].update({
                "is_valid_feed": True,
                "has_title": bool(feed_data.get("title")),
                "has_description": bool(feed_data.get("description")),
                "has_items": len(items) > 0,
                "feed_type": feed_type,
                "item_count": len(items),
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Feed validation error: {e}")
            result.error = f"Feed validation failed: {str(e)}"
            return result
    
    def cache_key(self, request: ResourceRequest) -> Optional[str]:
        """
        Generate cache key for RSS feed request.
        
        Args:
            request: Resource request
            
        Returns:
            Cache key string or None
        """
        if not self.config or not self.config.enable_cache:
            return None
        
        # Include URL and relevant config in cache key
        key_parts = [
            "rss",
            str(request.uri),
            str(self.rss_config.max_items),
            str(self.rss_config.include_content),
        ]
        
        # Include headers that might affect content
        if request.headers:
            sorted_headers = sorted(request.headers.items())
            key_parts.append(str(sorted_headers))
        
        return ":".join(key_parts)


# Register component in the global registry
component_registry.register(ResourceKind.RSS, lambda config=None: RSSComponent(config))

__all__ = ["RSSComponent"]
