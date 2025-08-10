"""
Base classes and interfaces for the unified crawler system.

This module defines the abstract base classes, enums, and data models that all
crawler implementations must follow to ensure consistency and interoperability.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Dict,
    Generic,
    List,
    Literal,
    Optional,
    Protocol,
    TypeAlias,
    TypeVar,
    Union,
)

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from ..models.base import BaseConfig, BaseResult, ContentType
from ..models.http import FetchResult

# Type aliases for better type annotations and documentation
CrawlerResponse: TypeAlias = Dict[str, Any]
CrawlerMetadata: TypeAlias = Dict[str, Union[str, int, float, bool, List[str], None]]
SearchResults: TypeAlias = List[Dict[str, Any]]
CrawlResults: TypeAlias = List[Dict[str, Any]]
ExtractedContent: TypeAlias = Dict[str, Union[str, List[str], Dict[str, Any]]]

# Generic type variable for crawler implementations
T = TypeVar("T", bound="BaseCrawler")


class CrawlerType(str, Enum):
    """Enumeration of supported crawler types."""

    SPIDER = "spider"  # Spider.cloud API
    FIRECRAWL = "firecrawl"  # Firecrawl API
    TAVILY = "tavily"  # Tavily API
    ANYCRAWL = "anycrawl"  # AnyCrawl API


class CrawlerCapability(str, Enum):
    """Enumeration of crawler capabilities."""

    SCRAPE = "scrape"  # Single page scraping
    CRAWL = "crawl"  # Multi-page crawling
    SEARCH = "search"  # Web search functionality
    EXTRACT = "extract"  # Content extraction
    SCREENSHOT = "screenshot"  # Page screenshots
    MAP = "map"  # Site mapping
    JAVASCRIPT = "javascript"  # JavaScript rendering
    PROXY = "proxy"  # Proxy support


class CrawlerError(Exception):
    """Base exception for crawler-related errors."""

    def __init__(
        self,
        message: str,
        crawler_type: Optional[CrawlerType] = None,
        status_code: Optional[int] = None,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.crawler_type = crawler_type
        self.status_code = status_code
        self.original_error = original_error


class CrawlerConfig(BaseConfig):
    """Configuration model for crawler operations."""

    # API credentials
    api_key: Optional[str] = Field(
        default=None, description="API key for the crawler service"
    )

    # Request settings
    timeout: float = Field(default=60.0, gt=0, description="Request timeout in seconds")
    max_retries: int = Field(
        default=3, ge=0, le=10, description="Maximum retry attempts"
    )
    retry_delay: float = Field(
        default=1.0, ge=0.1, le=60.0, description="Delay between retries"
    )

    # Content settings
    return_format: str = Field(default="markdown", description="Content return format")
    include_metadata: bool = Field(default=True, description="Include page metadata")
    include_images: bool = Field(default=False, description="Include image URLs")
    include_links: bool = Field(default=False, description="Include page links")

    # Crawling settings
    max_pages: Optional[int] = Field(
        default=None, ge=1, description="Maximum pages to crawl"
    )
    max_depth: Optional[int] = Field(
        default=None, ge=1, description="Maximum crawl depth"
    )
    follow_redirects: bool = Field(default=True, description="Follow HTTP redirects")

    # JavaScript and rendering
    enable_javascript: bool = Field(
        default=False, description="Enable JavaScript rendering"
    )
    wait_for_selector: Optional[str] = Field(
        default=None, description="CSS selector to wait for"
    )

    # Proxy and performance
    use_proxy: bool = Field(default=False, description="Use proxy for requests")
    proxy_country: Optional[str] = Field(default=None, description="Proxy country code")

    # Domain filtering
    include_domains: List[str] = Field(
        default_factory=list, description="Domains to include"
    )
    exclude_domains: List[str] = Field(
        default_factory=list, description="Domains to exclude"
    )

    # Custom headers
    custom_headers: Dict[str, str] = Field(
        default_factory=dict, description="Custom HTTP headers"
    )


class CrawlerRequest(BaseModel):
    """Model representing a crawler request."""

    url: HttpUrl = Field(description="URL to crawl or scrape")
    operation: CrawlerCapability = Field(description="Type of operation to perform")
    config: Optional[CrawlerConfig] = Field(
        default=None, description="Operation-specific configuration"
    )

    # Search-specific parameters
    query: Optional[str] = Field(
        default=None, description="Search query (for search operations)"
    )
    search_depth: Optional[str] = Field(
        default="basic", description="Search depth (basic/advanced)"
    )
    max_results: Optional[int] = Field(
        default=5, ge=1, le=100, description="Maximum search results"
    )

    # Crawl-specific parameters
    limit: Optional[int] = Field(
        default=None, ge=1, description="Page limit for crawling"
    )
    depth: Optional[int] = Field(default=None, ge=1, description="Crawl depth limit")

    # Content extraction parameters
    css_selector: Optional[str] = Field(
        default=None, description="CSS selector for content extraction"
    )
    extract_schema: Optional[Dict[str, Any]] = Field(
        default=None, description="Schema for structured extraction"
    )

    model_config = ConfigDict(
        use_enum_values=True, validate_assignment=True, extra="forbid"
    )


@dataclass
class CrawlerResult(BaseResult):
    """Result from a crawler operation, compatible with FetchResult."""

    # Core result data
    content: Union[str, bytes, Dict[str, Any], List[Dict[str, Any]], None] = None
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)

    # Crawler-specific metadata
    crawler_type: Optional[CrawlerType] = None
    operation: Optional[CrawlerCapability] = None
    pages_crawled: int = 0
    total_cost: Optional[float] = None

    # Content metadata
    title: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    images: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)

    # Search-specific results
    search_results: List[Dict[str, Any]] = field(default_factory=list)
    answer: Optional[str] = None  # AI-generated answer for search queries

    def to_fetch_result(self) -> FetchResult:
        """Convert CrawlerResult to FetchResult for backward compatibility."""
        # Handle content type conversion - FetchResult doesn't support List[Dict[str, Any]]
        content = self.content
        if isinstance(content, list):
            # Convert list to dict format that FetchResult can handle
            content = {"results": content}

        return FetchResult(
            url=self.url,
            status_code=self.status_code,
            headers=self.headers,
            content=content,
            content_type=(
                ContentType.MARKDOWN
                if isinstance(self.content, str)
                else ContentType.RAW
            ),
            response_time=self.response_time,
            timestamp=self.timestamp,
            error=self.error,
            retry_count=self.retry_count,
        )

    @property
    def is_success(self) -> bool:
        """Check if the crawler operation was successful."""
        return self.error is None and 200 <= self.status_code < 300

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the crawler result."""
        return {
            "url": self.url,
            "crawler_type": self.crawler_type.value if self.crawler_type else None,
            "operation": self.operation.value if self.operation else None,
            "status_code": self.status_code,
            "pages_crawled": self.pages_crawled,
            "content_length": len(str(self.content)) if self.content else 0,
            "response_time": self.response_time,
            "success": self.is_success,
            "total_cost": self.total_cost,
        }


class BaseCrawler(ABC):
    """Abstract base class for all crawler implementations."""

    def __init__(self, config: Optional[CrawlerConfig] = None):
        """Initialize the crawler with configuration."""
        self.config = config or CrawlerConfig()
        self.crawler_type = self._get_crawler_type()

    @abstractmethod
    def _get_crawler_type(self) -> CrawlerType:
        """Return the crawler type for this implementation."""
        pass

    @abstractmethod
    def get_capabilities(self) -> List[CrawlerCapability]:
        """Return the list of capabilities supported by this crawler."""
        pass

    @abstractmethod
    async def crawl(self, request: CrawlerRequest) -> CrawlerResult:
        """Perform a crawl operation."""
        pass

    @abstractmethod
    async def scrape(self, request: CrawlerRequest) -> CrawlerResult:
        """Perform a scrape operation."""
        pass

    def supports_capability(self, capability: CrawlerCapability) -> bool:
        """Check if this crawler supports a specific capability."""
        return capability in self.get_capabilities()

    async def execute_request(self, request: CrawlerRequest) -> CrawlerResult:
        """Execute a crawler request based on the operation type."""
        if not self.supports_capability(request.operation):
            operation_str = request.operation.value if hasattr(request.operation, 'value') else str(request.operation)
            raise CrawlerError(
                f"{self.crawler_type.value} does not support {operation_str} operation",
                crawler_type=self.crawler_type,
            )

        # Route to appropriate method based on operation
        if request.operation == CrawlerCapability.SCRAPE:
            return await self.scrape(request)
        elif request.operation == CrawlerCapability.CRAWL:
            return await self.crawl(request)
        elif request.operation == CrawlerCapability.SEARCH:
            return await self.search(request)
        elif request.operation == CrawlerCapability.EXTRACT:
            return await self.extract(request)
        else:
            operation_str = request.operation.value if hasattr(request.operation, 'value') else str(request.operation)
            raise CrawlerError(
                f"Operation {operation_str} not implemented",
                crawler_type=self.crawler_type,
            )

    async def search(self, request: CrawlerRequest) -> CrawlerResult:
        """Perform a search operation. Override in subclasses that support search."""
        raise CrawlerError(
            f"{self.crawler_type.value} does not support search operation",
            crawler_type=self.crawler_type,
        )

    async def extract(self, request: CrawlerRequest) -> CrawlerResult:
        """Perform an extract operation. Override in subclasses that support extraction."""
        raise CrawlerError(
            f"{self.crawler_type.value} does not support extract operation",
            crawler_type=self.crawler_type,
        )

    def _handle_error(self, error: Exception, request: CrawlerRequest) -> CrawlerResult:
        """Handle errors and return a CrawlerResult with error information."""
        error_message = str(error)
        status_code = getattr(error, "status_code", 0)

        return CrawlerResult(
            url=str(request.url),
            crawler_type=self.crawler_type,
            operation=request.operation,
            status_code=status_code,
            error=error_message,
            timestamp=datetime.now(),
        )


class CrawlerProtocol(Protocol):
    """Protocol defining the interface that all crawlers must implement."""

    async def execute_request(self, request: CrawlerRequest) -> CrawlerResult:
        """Execute a crawler request."""
        ...

    def supports_capability(self, capability: CrawlerCapability) -> bool:
        """Check if the crawler supports a capability."""
        ...

    def get_capabilities(self) -> List[CrawlerCapability]:
        """Get supported capabilities."""
        ...
