"""
Base models and common types for the web_fetch library.

This module contains common enums, dataclasses, and base models used across
both HTTP and FTP protocols.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class ContentType(str, Enum):
    """
    Enumeration of supported content types for fetched data.

    Defines how response content should be parsed and returned by the fetcher.
    Each type determines the parsing strategy and return type.
    """

    RAW = "raw"  # Returns bytes unchanged
    JSON = "json"  # Parses as JSON, returns dict/list/primitive
    HTML = "html"  # Parses with BeautifulSoup, returns parsed object
    TEXT = "text"  # Decodes as text, returns string
    PDF = "pdf"  # Extracts text and metadata from PDF documents
    IMAGE = "image"  # Extracts metadata and descriptions from images
    RSS = "rss"  # Parses RSS/Atom feeds, returns feed items and metadata
    CSV = "csv"  # Parses CSV data into structured format
    MARKDOWN = "markdown"  # Converts HTML to Markdown format
    XML = "xml"  # Parses XML documents with structure preservation


class RetryStrategy(str, Enum):
    """
    Enumeration of retry strategies for failed requests.

    Defines how retry delays are calculated when requests fail.
    """

    NONE = "none"  # No retries, fail immediately
    LINEAR = "linear"  # Linear backoff: delay * (attempt + 1)
    EXPONENTIAL = "exponential"  # Exponential backoff: delay * (2 ** attempt)


@dataclass(frozen=True)
class RequestHeaders:
    """
    Immutable dataclass for HTTP request headers with common defaults.

    Provides sensible default headers for HTTP requests while allowing
    customization through the custom_headers field.

    Attributes:
        user_agent: User-Agent header identifying the client
        accept: Accept header specifying acceptable content types
        accept_language: Accept-Language header for content localization
        accept_encoding: Accept-Encoding header for compression support
        connection: Connection header for keep-alive behavior
        custom_headers: Additional custom headers as key-value pairs
    """

    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
    accept: str = "*/*"
    accept_language: str = "en-US,en;q=0.9"
    accept_encoding: str = "gzip, deflate, br"
    connection: str = "keep-alive"
    custom_headers: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, str]:
        """Convert headers to dictionary format."""
        headers = {
            "User-Agent": self.user_agent,
            "Accept": self.accept,
            "Accept-Language": self.accept_language,
            "Accept-Encoding": self.accept_encoding,
            "Connection": self.connection,
        }
        headers.update(self.custom_headers)
        return headers


@dataclass
class ProgressInfo:
    """Progress information for downloads and operations."""

    bytes_downloaded: int = 0
    total_bytes: Optional[int] = None
    chunk_count: int = 0
    elapsed_time: float = 0.0
    download_speed: float = 0.0
    eta: Optional[float] = None
    percentage: Optional[float] = None

    @property
    def is_complete(self) -> bool:
        """Check if download is complete."""
        if self.total_bytes is None:
            return False
        return self.bytes_downloaded >= self.total_bytes

    @property
    def speed_human(self) -> str:
        """Human-readable speed string."""
        if self.download_speed < 1024:
            return f"{self.download_speed:.1f} B/s"
        elif self.download_speed < 1024 * 1024:
            return f"{self.download_speed / 1024:.1f} KB/s"
        else:
            return f"{self.download_speed / (1024 * 1024):.1f} MB/s"


# Common configuration base classes


class BaseConfig(BaseModel):
    """Base configuration class with common validation settings."""

    model_config = ConfigDict(
        use_enum_values=True, validate_assignment=True, extra="forbid"
    )


# Common result base classes

# Resource-specific metadata classes


@dataclass
class PDFMetadata:
    """Metadata extracted from PDF documents."""

    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    creator: Optional[str] = None
    producer: Optional[str] = None
    creation_date: Optional[datetime] = None
    modification_date: Optional[datetime] = None
    page_count: int = 0
    encrypted: bool = False
    text_length: int = 0
    language: Optional[str] = None


@dataclass
class ImageMetadata:
    """Metadata extracted from images."""

    format: Optional[str] = None
    mode: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    file_size: Optional[int] = None
    color_space: Optional[str] = None
    has_transparency: bool = False
    dpi: Optional[tuple] = None
    exif_data: Dict[str, Any] = field(default_factory=dict)
    alt_text: Optional[str] = None
    caption: Optional[str] = None


@dataclass
class FeedMetadata:
    """Metadata extracted from RSS/Atom feeds."""

    title: Optional[str] = None
    description: Optional[str] = None
    link: Optional[str] = None
    language: Optional[str] = None
    copyright: Optional[str] = None
    managing_editor: Optional[str] = None
    web_master: Optional[str] = None
    pub_date: Optional[datetime] = None
    last_build_date: Optional[datetime] = None
    category: Optional[str] = None
    generator: Optional[str] = None
    docs: Optional[str] = None
    ttl: Optional[int] = None
    image: Optional[Dict[str, str]] = None
    feed_type: Optional[str] = None  # RSS, Atom, etc.
    version: Optional[str] = None
    item_count: int = 0


@dataclass
class FeedItem:
    """Individual item from RSS/Atom feed."""

    title: Optional[str] = None
    description: Optional[str] = None
    link: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None
    comments: Optional[str] = None
    enclosure: Optional[Dict[str, str]] = None
    guid: Optional[str] = None
    pub_date: Optional[datetime] = None
    source: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class CSVMetadata:
    """Metadata extracted from CSV data."""

    delimiter: str = ","
    quotechar: str = '"'
    encoding: str = "utf-8"
    has_header: bool = True
    row_count: int = 0
    column_count: int = 0
    column_names: List[str] = field(default_factory=list)
    column_types: Dict[str, str] = field(default_factory=dict)
    null_values: Dict[str, int] = field(default_factory=dict)
    file_size: Optional[int] = None


@dataclass
class LinkInfo:
    """Information about extracted links."""

    url: str
    text: Optional[str] = None
    title: Optional[str] = None
    rel: Optional[str] = None
    type: Optional[str] = None
    is_external: bool = False
    is_valid: bool = True
    status_code: Optional[int] = None
    content_type: Optional[str] = None


@dataclass
class ContentSummary:
    """Summary information for content."""

    word_count: int = 0
    sentence_count: int = 0
    paragraph_count: int = 0
    reading_time_minutes: float = 0.0
    key_phrases: List[str] = field(default_factory=list)
    summary_text: Optional[str] = None
    language: Optional[str] = None
    readability_score: Optional[float] = None


@dataclass
class BaseResult:
    """Base result class with common fields."""

    url: str
    timestamp: datetime = field(default_factory=datetime.now)
    response_time: float = 0.0
    error: Optional[str] = None
    retry_count: int = 0


__all__ = [
    "ContentType",
    "RetryStrategy",
    "RequestHeaders",
    "ProgressInfo",
    "BaseConfig",
    "BaseResult",
    # Resource metadata classes
    "PDFMetadata",
    "ImageMetadata",
    "FeedMetadata",
    "FeedItem",
    "CSVMetadata",
    "LinkInfo",
    "ContentSummary",
]
