"""
Enhanced content parser that handles all supported resource types.

This module provides a unified interface for parsing different content types
and extracting metadata, integrating all specialized parsers.
"""

from __future__ import annotations

import json
import logging
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    TypeAlias,
    Union,
)

if TYPE_CHECKING:
    from .pdf_parser import PDFParser
    from .image_parser import ImageParser
    from .feed_parser import FeedParser
    from .csv_parser import CSVParser
    from .json_parser import JSONParser
    from .markdown_converter import MarkdownConverter
    from .content_analyzer import ContentAnalyzer
    from .link_extractor import LinkExtractor

from bs4 import BeautifulSoup

from ..exceptions import ContentError, WebFetchError
from ..models.base import ContentType
from ..models.http import FetchResult

logger = logging.getLogger(__name__)

# Type aliases for better type annotations and documentation
ParsedContent: TypeAlias = Union[str, bytes, Dict[str, Any], List[Any], None]
HTMLContent: TypeAlias = Dict[str, Union[str, List[str], None]]
JSONContent: TypeAlias = Union[Dict[str, Any], List[Any], str, int, float, bool, None]
TextContent: TypeAlias = str
BinaryContent: TypeAlias = bytes
ParseResult: TypeAlias = Tuple[ParsedContent, FetchResult]


class EnhancedContentParser:
    """Enhanced content parser supporting all resource types."""

    def __init__(self) -> None:
        """Initialize the enhanced content parser with lazy-loaded parsers."""
        self._pdf_parser: Optional["PDFParser"] = None
        self._image_parser: Optional["ImageParser"] = None
        self._feed_parser: Optional["FeedParser"] = None
        self._csv_parser: Optional["CSVParser"] = None
        self._markdown_converter: Optional["MarkdownConverter"] = None
        self._json_parser: Optional["JSONParser"] = None
        self._content_analyzer: Optional["ContentAnalyzer"] = None
        self._link_extractor: Optional["LinkExtractor"] = None

    @property
    def pdf_parser(self) -> "PDFParser":
        """Lazy load PDF parser."""
        if self._pdf_parser is None:
            from .pdf_parser import PDFParser

            self._pdf_parser = PDFParser()
        return self._pdf_parser

    @property
    def image_parser(self) -> "ImageParser":
        """Lazy load image parser."""
        if self._image_parser is None:
            from .image_parser import ImageParser

            self._image_parser = ImageParser()
        return self._image_parser

    @property
    def feed_parser(self) -> "FeedParser":
        """Lazy load feed parser."""
        if self._feed_parser is None:
            from .feed_parser import FeedParser

            self._feed_parser = FeedParser()
        return self._feed_parser

    @property
    def csv_parser(self) -> "CSVParser":
        """Lazy load CSV parser."""
        if self._csv_parser is None:
            from .csv_parser import CSVParser

            self._csv_parser = CSVParser()
        return self._csv_parser

    @property
    def markdown_converter(self) -> "MarkdownConverter":
        """Lazy load Markdown converter."""
        if self._markdown_converter is None:
            from .markdown_converter import MarkdownConverter

            self._markdown_converter = MarkdownConverter()
        return self._markdown_converter

    @property
    def json_parser(self) -> "JSONParser":
        """Lazy load JSON parser."""
        if self._json_parser is None:
            from .json_parser import JSONParser

            self._json_parser = JSONParser()
        return self._json_parser

    @property
    def content_analyzer(self) -> "ContentAnalyzer":
        """Lazy load content analyzer."""
        if self._content_analyzer is None:
            from .content_analyzer import ContentAnalyzer

            self._content_analyzer = ContentAnalyzer()
        return self._content_analyzer

    @property
    def link_extractor(self) -> "LinkExtractor":
        """Lazy load link extractor."""
        if not hasattr(self, "_link_extractor") or self._link_extractor is None:
            from .link_extractor import LinkExtractor

            self._link_extractor = LinkExtractor(
                validate_links=False
            )  # Don't validate by default for performance
        return self._link_extractor

    async def parse_content(
        self,
        content_bytes: bytes,
        requested_type: ContentType,
        url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> ParseResult:
        """
        Parse content based on requested type and return both content and metadata.

        Args:
            content_bytes: Raw response content as bytes
            requested_type: ContentType enum specifying how to parse the content
            url: Optional URL for context
            headers: Optional response headers for additional context

        Returns:
            Tuple of (parsed_content, enhanced_fetch_result)

        Raises:
            ContentError: If content cannot be parsed as requested type
            WebFetchError: If parsing fails unexpectedly
        """
        if not content_bytes:
            return None, FetchResult(url=url or "", content_type=requested_type)

        # Create base result object
        result = FetchResult(url=url or "", content_type=requested_type)

        try:
            match requested_type:
                case ContentType.RAW:
                    return content_bytes, result

                case ContentType.TEXT:
                    content = self._parse_text(content_bytes)
                    # Add content analysis for text content
                    if (
                        isinstance(content, str) and len(content) > 100
                    ):  # Only analyze substantial text
                        try:
                            result.content_summary = (
                                self.content_analyzer.analyze_content(content)
                            )
                        except Exception as e:
                            logger.warning(f"Content analysis failed: {e}")
                    return content, result

                case ContentType.JSON:
                    content = self._parse_json(content_bytes, url, headers)
                    return content, result

                case ContentType.HTML:
                    content = self._parse_html(content_bytes)
                    # Add content analysis for HTML text content
                    if (
                        isinstance(content, dict)
                        and "text" in content
                        and len(content["text"]) > 100
                    ):
                        try:
                            result.content_summary = (
                                self.content_analyzer.analyze_content(content["text"])
                            )
                        except Exception as e:
                            logger.warning(f"Content analysis failed: {e}")

                    # Extract links from HTML content
                    if isinstance(content, dict) and "raw_html" in content:
                        try:
                            links = await self.link_extractor.extract_links(
                                content["raw_html"], content_type="html", base_url=url
                            )
                            result.links = links
                        except Exception as e:
                            logger.warning(f"Link extraction failed: {e}")

                    return content, result

                case ContentType.PDF:
                    return await self._parse_pdf(content_bytes, url, result)

                case ContentType.IMAGE:
                    return await self._parse_image(content_bytes, url, headers, result)

                case ContentType.RSS:
                    return await self._parse_feed(content_bytes, url, result)

                case ContentType.CSV:
                    return await self._parse_csv(content_bytes, url, result)

                case ContentType.MARKDOWN:
                    return await self._parse_markdown(content_bytes, url, result)

                case ContentType.XML:
                    return await self._parse_xml(content_bytes, url, result)

                case _:
                    # Default to text parsing
                    content = self._parse_text(content_bytes)
                    return content, result

        except Exception as e:
            logger.error(f"Failed to parse content as {requested_type}: {e}")
            result.error = str(e)
            return None, result

    def _parse_text(self, content_bytes: bytes) -> str:
        """Parse content as plain text with encoding detection."""
        try:
            return content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            # Try common encodings
            for encoding in ["latin1", "cp1252", "iso-8859-1"]:
                try:
                    return content_bytes.decode(encoding)
                except UnicodeDecodeError:
                    continue
            return content_bytes.decode("utf-8", errors="replace")

    def _parse_json(
        self,
        content_bytes: bytes,
        url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Parse content as JSON with enhanced API standard support."""
        try:
            # Use enhanced JSON parser
            parsed_data, metadata = self.json_parser.parse(content_bytes, url, headers)

            # Return structured data that includes both parsed content and metadata
            return {
                "data": parsed_data,
                "metadata": metadata,
                "api_standard": metadata.get("api_standard", "generic"),
                "pagination": (
                    self.json_parser.extract_pagination_info(parsed_data)
                    if isinstance(parsed_data, dict)
                    else None
                ),
            }
        except Exception as e:
            # Fallback to basic JSON parsing
            try:
                text_content = content_bytes.decode("utf-8")
                basic_data = json.loads(text_content)
                return {
                    "data": basic_data,
                    "metadata": {"format": "basic_json", "fallback": True},
                    "api_standard": "generic",
                    "pagination": None,
                }
            except (UnicodeDecodeError, json.JSONDecodeError) as fallback_e:
                raise ContentError(
                    f"Failed to parse JSON content: {fallback_e}",
                    content_type="application/json",
                )

    def _parse_html(self, content_bytes: bytes) -> Dict[str, Any]:
        """Parse content as HTML using BeautifulSoup."""
        try:
            text_content = content_bytes.decode("utf-8")
            soup = BeautifulSoup(text_content, "lxml")
            return {
                "title": soup.title.string if soup.title else None,
                "text": soup.get_text(strip=True),
                "links": [
                    a.get("href")
                    for a in soup.find_all("a", href=True)
                    if hasattr(a, "get")
                ],
                "images": [
                    img.get("src")
                    for img in soup.find_all("img", src=True)
                    if hasattr(img, "get")
                ],
                "raw_html": text_content,
            }
        except Exception as e:
            raise WebFetchError(f"Failed to parse HTML content: {e}")

    async def _parse_pdf(
        self, content_bytes: bytes, url: Optional[str], result: FetchResult
    ) -> Tuple[str, FetchResult]:
        """Parse PDF content and extract metadata."""
        try:
            extracted_text, pdf_metadata = self.pdf_parser.parse(content_bytes, url)
            result.pdf_metadata = pdf_metadata
            result.extracted_text = extracted_text
            return extracted_text, result
        except Exception as e:
            logger.error(f"PDF parsing failed for {url}: {e}")
            result.error = str(e)
            return "", result

    async def _parse_image(
        self,
        content_bytes: bytes,
        url: Optional[str],
        headers: Optional[Dict[str, str]],
        result: FetchResult,
    ) -> Tuple[Dict[str, Any], FetchResult]:
        """Parse image content and extract metadata."""
        try:
            image_data, image_metadata = self.image_parser.parse(
                content_bytes, url, headers
            )
            result.image_metadata = image_metadata
            return image_data, result
        except Exception as e:
            logger.error(f"Image parsing failed for {url}: {e}")
            result.error = str(e)
            return {}, result

    async def _parse_feed(
        self, content_bytes: bytes, url: Optional[str], result: FetchResult
    ) -> Tuple[Dict[str, Any], FetchResult]:
        """Parse RSS/Atom feed content."""
        try:
            feed_data, feed_metadata, feed_items = self.feed_parser.parse(
                content_bytes, url
            )
            result.feed_metadata = feed_metadata
            result.feed_items = feed_items
            return feed_data, result
        except Exception as e:
            logger.error(f"Feed parsing failed for {url}: {e}")
            result.error = str(e)
            return {}, result

    async def _parse_csv(
        self, content_bytes: bytes, url: Optional[str], result: FetchResult
    ) -> Tuple[Dict[str, Any], FetchResult]:
        """Parse CSV content into structured data."""
        try:
            csv_data, csv_metadata = self.csv_parser.parse(content_bytes, url)
            result.csv_metadata = csv_metadata
            result.structured_data = csv_data
            return csv_data, result
        except Exception as e:
            logger.error(f"CSV parsing failed for {url}: {e}")
            result.error = str(e)
            return {}, result

    async def _parse_markdown(
        self, content_bytes: bytes, url: Optional[str], result: FetchResult
    ) -> Tuple[str, FetchResult]:
        """Convert HTML content to Markdown."""
        try:
            # First parse as HTML to get structured content
            html_content = self._parse_html(content_bytes)
            # Convert to Markdown
            markdown_content = self.markdown_converter.convert(
                html_content["raw_html"], url
            )
            return markdown_content, result
        except Exception as e:
            logger.error(f"Markdown conversion failed for {url}: {e}")
            result.error = str(e)
            # Fallback to plain text
            return self._parse_text(content_bytes), result

    async def _parse_xml(
        self, content_bytes: bytes, url: Optional[str], result: FetchResult
    ) -> Tuple[Dict[str, Any], FetchResult]:
        """Parse XML content with structure preservation."""
        try:
            text_content = content_bytes.decode("utf-8")
            soup = BeautifulSoup(text_content, "xml")

            # Extract basic XML structure
            xml_data = {
                "root_tag": soup.name if soup.name else None,
                "text_content": soup.get_text(strip=True),
                "raw_xml": text_content,
                "elements": self._extract_xml_elements(soup),
            }

            return xml_data, result
        except Exception as e:
            logger.error(f"XML parsing failed for {url}: {e}")
            result.error = str(e)
            return {}, result

    def _extract_xml_elements(self, soup) -> Dict[str, Any]:
        """Extract XML elements into a structured format."""
        elements = {}

        for element in soup.find_all():
            tag_name = element.name
            if tag_name not in elements:
                elements[tag_name] = []

            element_data = {
                "text": element.get_text(strip=True),
                "attributes": dict(element.attrs) if element.attrs else {},
            }
            elements[tag_name].append(element_data)

        return elements
