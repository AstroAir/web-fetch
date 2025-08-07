"""
API pagination handling for web_fetch.

This module provides comprehensive support for different pagination strategies
commonly used in REST APIs.
"""

import re
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol

from pydantic import BaseModel, Field

from ..exceptions import WebFetchError
from ..models import FetchRequest, FetchResult


class PaginationStrategy(str, Enum):
    """Pagination strategies."""

    OFFSET_LIMIT = "offset_limit"
    PAGE_SIZE = "page_size"
    CURSOR = "cursor"
    LINK_HEADER = "link_header"
    CUSTOM = "custom"


class PaginationConfig(BaseModel):
    """Pagination configuration."""

    model_config = {"arbitrary_types_allowed": True}

    strategy: PaginationStrategy
    max_pages: int = Field(default=100, description="Maximum pages to fetch")
    page_size: int = Field(default=20, description="Items per page")

    # Parameter names for different strategies
    page_param: str = Field(default="page", description="Page parameter name")
    size_param: str = Field(default="size", description="Size parameter name")
    offset_param: str = Field(default="offset", description="Offset parameter name")
    limit_param: str = Field(default="limit", description="Limit parameter name")
    cursor_param: str = Field(default="cursor", description="Cursor parameter name")

    # Response field names
    data_field: str = Field(default="data", description="Data field in response")
    total_field: Optional[str] = Field(default="total", description="Total count field")
    next_cursor_field: Optional[str] = Field(
        default="next_cursor", description="Next cursor field"
    )
    has_more_field: Optional[str] = Field(
        default="has_more", description="Has more field"
    )

    # Custom extraction functions
    custom_next_url_extractor: Optional[Callable[[Any], Optional[str]]] = Field(
        default=None, description="Custom next URL extractor"
    )
    custom_data_extractor: Optional[Callable[[Any], Any]] = Field(
        default=None, description="Custom data extractor"
    )


class PaginationResult(BaseModel):
    """Result of paginated request."""

    data: List[Any] = Field(default_factory=list, description="Collected data")
    total_items: Optional[int] = Field(
        default=None, description="Total number of items"
    )
    total_pages: int = Field(default=0, description="Total pages fetched")
    has_more: bool = Field(default=False, description="Whether more data is available")
    next_cursor: Optional[str] = Field(
        default=None, description="Next cursor for continuation"
    )
    responses: List[FetchResult] = Field(
        default_factory=list, description="Individual page responses"
    )


class BasePaginationHandler(ABC):
    """Base class for pagination handlers."""

    def __init__(self, config: PaginationConfig):
        """
        Initialize pagination handler.

        Args:
            config: Pagination configuration
        """
        self.config = config

    @abstractmethod
    async def get_next_request(
        self,
        base_request: FetchRequest,
        current_response: Optional[FetchResult] = None,
        page_number: int = 1,
    ) -> Optional[FetchRequest]:
        """
        Get the next request for pagination.
        """
        raise NotImplementedError

    @abstractmethod
    def extract_data(self, response: FetchResult) -> List[Any]:
        """
        Extract data from response.
        """
        raise NotImplementedError

    def extract_total_count(self, response: FetchResult) -> Optional[int]:
        """
        Extract total count from response.
        """
        if not self.config.total_field or not response.content:
            return None

        if isinstance(response.content, dict):
            total = response.content.get(self.config.total_field)
            return int(total) if isinstance(total, (int, str)) and str(total).isdigit() else None

        return None


class OffsetLimitHandler(BasePaginationHandler):
    """Handler for offset/limit pagination."""

    async def get_next_request(
        self,
        base_request: FetchRequest,
        current_response: Optional[FetchResult] = None,
        page_number: int = 1,
    ) -> Optional[FetchRequest]:
        """Get next request using offset/limit."""
        if page_number > self.config.max_pages:
            return None

        # Calculate offset
        offset = (page_number - 1) * self.config.page_size

        # Check if we have more data
        if current_response:
            data = self.extract_data(current_response)
            if len(data) < self.config.page_size:
                return None  # No more data

        # Create new request with updated parameters
        new_request = base_request.model_copy()
        params: Dict[str, str] = dict(new_request.params or {})
        params[self.config.offset_param] = str(offset)
        params[self.config.limit_param] = str(self.config.page_size)
        new_request.params = params

        return new_request

    def extract_data(self, response: FetchResult) -> List[Any]:
        """Extract data from offset/limit response."""
        if not response.content:
            return []

        # Handle list content directly
        content = response.content
        if hasattr(content, '__iter__') and not isinstance(content, (str, bytes, dict)):
            # This is likely a list
            return list(content)

        # Handle dict content
        if isinstance(content, dict):
            data = content.get(self.config.data_field, [])
            if hasattr(data, '__iter__') and not isinstance(data, (str, bytes, dict)):
                return list(data)

        return []


class PageSizeHandler(BasePaginationHandler):
    """Handler for page/size pagination."""

    async def get_next_request(
        self,
        base_request: FetchRequest,
        current_response: Optional[FetchResult] = None,
        page_number: int = 1,
    ) -> Optional[FetchRequest]:
        """Get next request using page/size."""
        if page_number > self.config.max_pages:
            return None

        # Check if we have more data
        if current_response:
            data = self.extract_data(current_response)
            if len(data) < self.config.page_size:
                return None  # No more data

            # Check has_more field if available
            if (
                isinstance(current_response.content, dict)
                and self.config.has_more_field
                and not bool(current_response.content.get(self.config.has_more_field, True))
            ):
                return None

        # Create new request with updated parameters
        new_request = base_request.model_copy()
        params: Dict[str, str] = dict(new_request.params or {})
        params[self.config.page_param] = str(page_number)
        params[self.config.size_param] = str(self.config.page_size)
        new_request.params = params

        return new_request

    def extract_data(self, response: FetchResult) -> List[Any]:
        """Extract data from page/size response."""
        if not response.content:
            return []

        # Handle list content directly
        content = response.content
        if hasattr(content, '__iter__') and not isinstance(content, (str, bytes, dict)):
            # This is likely a list
            return list(content)

        # Handle dict content
        if isinstance(content, dict):
            data = content.get(self.config.data_field, [])
            if hasattr(data, '__iter__') and not isinstance(data, (str, bytes, dict)):
                return list(data)

        return []


class CursorHandler(BasePaginationHandler):
    """Handler for cursor-based pagination."""

    def __init__(self, config: PaginationConfig):
        """Initialize cursor handler."""
        super().__init__(config)
        self._current_cursor: Optional[str] = None

    async def get_next_request(
        self,
        base_request: FetchRequest,
        current_response: Optional[FetchResult] = None,
        page_number: int = 1,
    ) -> Optional[FetchRequest]:
        """Get next request using cursor."""
        if page_number > self.config.max_pages:
            return None

        # Get cursor from response
        if current_response and page_number > 1:
            self._current_cursor = self._extract_next_cursor(current_response)
            if not self._current_cursor:
                return None  # No more data

        # Create new request with cursor
        new_request = base_request.model_copy()
        params: Dict[str, str] = dict(new_request.params or {})

        if self._current_cursor:
            params[self.config.cursor_param] = self._current_cursor

        params[self.config.size_param] = str(self.config.page_size)
        new_request.params = params

        return new_request

    def extract_data(self, response: FetchResult) -> List[Any]:
        """Extract data from cursor response."""
        if not response.content:
            return []

        # Handle list content directly
        content = response.content
        if hasattr(content, '__iter__') and not isinstance(content, (str, bytes, dict)):
            # This is likely a list
            return list(content)

        # Handle dict content
        if isinstance(content, dict):
            data = content.get(self.config.data_field, [])
            if hasattr(data, '__iter__') and not isinstance(data, (str, bytes, dict)):
                return list(data)

        return []

    def _extract_next_cursor(self, response: FetchResult) -> Optional[str]:
        """Extract next cursor from response."""
        if not response.content or not isinstance(response.content, dict):
            return None

        if self.config.next_cursor_field:
            next_cursor = response.content.get(self.config.next_cursor_field)
            return str(next_cursor) if next_cursor is not None else None

        return None


class LinkHeaderHandler(BasePaginationHandler):
    """Handler for Link header pagination (RFC 5988)."""

    async def get_next_request(
        self,
        base_request: FetchRequest,
        current_response: Optional[FetchResult] = None,
        page_number: int = 1,
    ) -> Optional[FetchRequest]:
        """Get next request using Link header."""
        if page_number > self.config.max_pages or not current_response:
            return None

        # Extract next URL from Link header
        next_url = self._extract_next_url(current_response)
        if not next_url:
            return None

        # Create new request with next URL (use update to enforce type validation)
        new_request = base_request.model_copy(update={"url": next_url})

        return new_request

    def extract_data(self, response: FetchResult) -> List[Any]:
        """Extract data from Link header response."""
        if not response.content:
            return []

        # Handle list content directly
        content = response.content
        if hasattr(content, '__iter__') and not isinstance(content, (str, bytes, dict)):
            # This is likely a list
            return list(content)

        # Handle dict content
        if isinstance(content, dict):
            data = content.get(self.config.data_field, [])
            if hasattr(data, '__iter__') and not isinstance(data, (str, bytes, dict)):
                return list(data)

        return []

    def _extract_next_url(self, response: FetchResult) -> Optional[str]:
        """Extract next URL from Link header."""
        link_header = response.headers.get("Link") or response.headers.get("link")
        if not link_header:
            return None

        # Parse Link header: <url>; rel="next"
        links = self._parse_link_header(link_header)
        return links.get("next")

    def _parse_link_header(self, link_header: str) -> Dict[str, str]:
        """Parse Link header into dictionary."""
        links: Dict[str, str] = {}

        # Split by comma and parse each link
        for link in link_header.split(","):
            link = link.strip()

            # Extract URL and rel
            url_match = re.search(r"<([^>]+)>", link)
            rel_match = re.search(r'rel="([^"]+)"', link)

            if url_match and rel_match:
                url = url_match.group(1)
                rel = rel_match.group(1)
                links[rel] = url

        return links


class _FetcherProto(Protocol):
    async def fetch_single(self, request: FetchRequest) -> FetchResult: ...


class PaginationHandler:
    """Main pagination handler that delegates to specific strategies."""

    def __init__(self, config: PaginationConfig):
        """
        Initialize pagination handler.

        Args:
            config: Pagination configuration
        """
        self.config = config
        self._handlers = {
            PaginationStrategy.OFFSET_LIMIT: OffsetLimitHandler(config),
            PaginationStrategy.PAGE_SIZE: PageSizeHandler(config),
            PaginationStrategy.CURSOR: CursorHandler(config),
            PaginationStrategy.LINK_HEADER: LinkHeaderHandler(config),
        }

    async def fetch_all_pages(
        self, fetcher: _FetcherProto, base_request: FetchRequest
    ) -> PaginationResult:
        """
        Fetch all pages using the configured strategy.
        """
        if self.config.strategy not in self._handlers:
            raise WebFetchError(
                f"Unsupported pagination strategy: {self.config.strategy}"
            )

        handler = self._handlers[self.config.strategy]
        result = PaginationResult()

        page_number = 1
        current_response: Optional[FetchResult] = None

        while page_number <= self.config.max_pages:
            # Get next request
            request = await handler.get_next_request(
                base_request, current_response, page_number
            )
            if not request:
                break

            # Fetch page
            response = await fetcher.fetch_single(request)
            result.responses.append(response)

            if not response.is_success:
                break

            # Extract data
            page_data = handler.extract_data(response)
            result.data.extend(page_data)

            # Extract total count (from first page)
            if page_number == 1:
                result.total_items = handler.extract_total_count(response)

            # Check if we have more data
            if len(page_data) < self.config.page_size:
                break

            current_response = response
            page_number += 1

        result.total_pages = page_number - 1
        result.has_more = page_number <= self.config.max_pages

        return result
