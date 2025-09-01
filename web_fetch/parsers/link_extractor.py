"""
Enhanced link extraction and validation utilities.

This module provides comprehensive link extraction from various content types
including HTML, text, CSS, and JavaScript, with validation and categorization.
"""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urljoin, urlparse

try:
    import aiohttp

    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

from bs4 import BeautifulSoup

from ..exceptions import ContentError
from ..models.base import LinkInfo

logger = logging.getLogger(__name__)


class LinkExtractor:
    """Enhanced link extractor with validation and categorization."""

    def __init__(
        self, validate_links: bool = False, max_concurrent_validations: int = 10
    ):
        """
        Initialize link extractor.

        Args:
            validate_links: Whether to validate extracted links
            max_concurrent_validations: Maximum concurrent link validations
        """
        self.validate_links = validate_links
        self.max_concurrent_validations = max_concurrent_validations

        # Common file extensions for categorization
        self.media_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".svg",
            ".webp",
            ".ico",
            ".mp4",
            ".avi",
            ".mov",
            ".wmv",
            ".flv",
            ".webm",
            ".mkv",
            ".mp3",
            ".wav",
            ".ogg",
            ".m4a",
            ".flac",
            ".aac",
        }

        self.document_extensions = {
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
            ".txt",
            ".rtf",
            ".odt",
            ".ods",
            ".odp",
            ".csv",
        }

        self.code_extensions = {
            ".js",
            ".css",
            ".json",
            ".xml",
            ".html",
            ".htm",
            ".php",
            ".py",
            ".java",
            ".cpp",
            ".c",
            ".h",
            ".rb",
            ".go",
            ".rs",
        }

    async def extract_links(
        self, content: str, content_type: str = "html", base_url: Optional[str] = None
    ) -> List[LinkInfo]:
        """
        Extract links from content based on content type.

        Args:
            content: Content to extract links from
            content_type: Type of content ('html', 'text', 'css', 'javascript')
            base_url: Base URL for resolving relative links

        Returns:
            List of LinkInfo objects
        """
        links = []

        try:
            if content_type.lower() == "html":
                links = await self._extract_html_links(content, base_url)
            elif content_type.lower() == "css":
                links = await self._extract_css_links(content, base_url)
            elif content_type.lower() == "javascript":
                links = await self._extract_js_links(content, base_url)
            else:  # Default to text
                links = await self._extract_text_links(content, base_url)

            # Validate links if requested
            if self.validate_links and links:
                links = await self._validate_links(links)

            return links

        except Exception as e:
            logger.error(f"Link extraction failed: {e}")
            raise ContentError(f"Failed to extract links: {e}")

    async def _extract_html_links(
        self, html_content: str, base_url: Optional[str]
    ) -> List[LinkInfo]:
        """Extract links from HTML content."""
        soup = BeautifulSoup(html_content, "html.parser")
        links = []

        # Extract links from various HTML elements
        link_selectors = [
            ("a", "href", "anchor"),
            ("img", "src", "image"),
            ("link", "href", "stylesheet"),
            ("script", "src", "script"),
            ("iframe", "src", "iframe"),
            ("embed", "src", "embed"),
            ("object", "data", "object"),
            ("source", "src", "source"),
            ("video", "src", "video"),
            ("audio", "src", "audio"),
            ("form", "action", "form"),
            ("area", "href", "area"),
            ("base", "href", "base"),
        ]

        for tag_name, attr_name, link_type in link_selectors:
            elements = soup.find_all(tag_name)
            for element in elements:
                url = element.get(attr_name)
                if url:
                    link_info = self._create_link_info(
                        url=url,
                        text=(
                            element.get_text(strip=True)
                            if hasattr(element, "get_text")
                            else None
                        ),
                        title=element.get("title"),
                        rel=element.get("rel"),
                        link_type=link_type,
                        base_url=base_url,
                    )
                    if link_info:
                        links.append(link_info)

        # Extract links from CSS within style tags
        style_tags = soup.find_all("style")
        for style_tag in style_tags:
            css_content = style_tag.get_text()
            css_links = await self._extract_css_links(css_content, base_url)
            links.extend(css_links)

        # Extract links from inline JavaScript
        script_tags = soup.find_all("script")
        for script_tag in script_tags:
            if not script_tag.get("src"):  # Only inline scripts
                js_content = script_tag.get_text()
                js_links = await self._extract_js_links(js_content, base_url)
                links.extend(js_links)

        return links

    async def _extract_css_links(
        self, css_content: str, base_url: Optional[str]
    ) -> List[LinkInfo]:
        """Extract links from CSS content."""
        links = []

        # CSS URL patterns
        url_patterns = [
            r'url\(["\']?([^"\')\s]+)["\']?\)',  # url() declarations
            r'@import\s+["\']([^"\']+)["\']',  # @import statements
        ]

        for pattern in url_patterns:
            matches = re.finditer(pattern, css_content, re.IGNORECASE)
            for match in matches:
                url = match.group(1)
                link_info = self._create_link_info(
                    url=url, link_type="css_resource", base_url=base_url
                )
                if link_info:
                    links.append(link_info)

        return links

    async def _extract_js_links(
        self, js_content: str, base_url: Optional[str]
    ) -> List[LinkInfo]:
        """Extract links from JavaScript content."""
        links = []

        # JavaScript URL patterns
        url_patterns = [
            r'["\']https?://[^"\']+["\']',  # Quoted HTTP URLs
            r'["\']//[^"\']+["\']',  # Protocol-relative URLs
            r'["\'][^"\']*\.[a-z]{2,4}[^"\']*["\']',  # Domain-like patterns
            r'fetch\(["\']([^"\']+)["\']',  # fetch() calls
            r'XMLHttpRequest.*["\']([^"\']+)["\']',  # XMLHttpRequest URLs
            r'window\.location\s*=\s*["\']([^"\']+)["\']',  # Location assignments
        ]

        for pattern in url_patterns:
            matches = re.finditer(pattern, js_content, re.IGNORECASE)
            for match in matches:
                url = match.group(1) if match.groups() else match.group(0).strip("\"'")

                # Filter out obvious non-URLs
                if self._is_likely_url(url):
                    link_info = self._create_link_info(
                        url=url, link_type="javascript_resource", base_url=base_url
                    )
                    if link_info:
                        links.append(link_info)

        return links

    async def _extract_text_links(
        self, text_content: str, base_url: Optional[str]
    ) -> List[LinkInfo]:
        """Extract links from plain text content."""
        links = []

        # Text URL patterns
        url_patterns = [
            r'https?://[^\s<>"{}|\\^`\[\]]+',  # HTTP URLs
            r'ftp://[^\s<>"{}|\\^`\[\]]+',  # FTP URLs
            r'www\.[^\s<>"{}|\\^`\[\]]+',  # www. URLs
        ]

        for pattern in url_patterns:
            matches = re.finditer(pattern, text_content, re.IGNORECASE)
            for match in matches:
                url = match.group(0)

                # Clean up URL (remove trailing punctuation)
                url = re.sub(r"[.,;:!?]+$", "", url)

                link_info = self._create_link_info(
                    url=url, link_type="text_link", base_url=base_url
                )
                if link_info:
                    links.append(link_info)

        return links

    def _create_link_info(
        self,
        url: str,
        text: Optional[str] = None,
        title: Optional[str] = None,
        rel: Optional[str] = None,
        link_type: str = "unknown",
        base_url: Optional[str] = None,
    ) -> Optional[LinkInfo]:
        """Create LinkInfo object with categorization."""
        try:
            # Resolve relative URLs
            if base_url:
                resolved_url = urljoin(base_url, url)
            else:
                resolved_url = url

            # Parse URL
            parsed = urlparse(resolved_url)

            # Skip invalid URLs
            if not parsed.scheme and not parsed.netloc:
                return None

            # Determine if external
            is_external = True
            if base_url:
                base_parsed = urlparse(base_url)
                is_external = parsed.netloc != base_parsed.netloc

            # Categorize by file extension
            path_lower = parsed.path.lower()
            content_type = None

            if any(path_lower.endswith(ext) for ext in self.media_extensions):
                content_type = "media"
            elif any(path_lower.endswith(ext) for ext in self.document_extensions):
                content_type = "document"
            elif any(path_lower.endswith(ext) for ext in self.code_extensions):
                content_type = "code"
            else:
                # Try to guess from MIME type
                mime_type, _ = mimetypes.guess_type(resolved_url)
                if mime_type:
                    if (
                        mime_type.startswith("image/")
                        or mime_type.startswith("video/")
                        or mime_type.startswith("audio/")
                    ):
                        content_type = "media"
                    elif (
                        mime_type.startswith("text/") or mime_type == "application/json"
                    ):
                        content_type = "text"
                    elif mime_type == "application/pdf":
                        content_type = "document"

            return LinkInfo(
                url=resolved_url,
                text=text,
                title=title,
                rel=rel,
                type=content_type,
                is_external=is_external,
                is_valid=True,  # Will be validated later if requested
            )

        except Exception as e:
            logger.warning(f"Failed to create link info for {url}: {e}")
            return None

    def _is_likely_url(self, text: str) -> bool:
        """Check if text is likely to be a URL."""
        if not text or len(text) < 4:
            return False

        # Skip obvious non-URLs
        if text in ["http", "https", "www", "com", "org", "net"]:
            return False

        # Must contain domain-like pattern
        if not re.search(r"[a-zA-Z0-9-]+\.[a-zA-Z]{2,}", text):
            return False

        return True

    async def _validate_links(self, links: List[LinkInfo]) -> List[LinkInfo]:
        """Validate links by checking their accessibility."""
        if not HAS_AIOHTTP:
            logger.warning("aiohttp not available, skipping link validation")
            return links

        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.max_concurrent_validations)

        async def validate_single_link(link: LinkInfo) -> LinkInfo:
            async with semaphore:
                try:
                    timeout = aiohttp.ClientTimeout(total=10)
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.head(link.url) as response:
                            link.is_valid = 200 <= response.status < 400
                            link.status_code = response.status

                            # Update content type from response
                            content_type = response.headers.get("content-type", "")
                            if content_type:
                                link.content_type = content_type.split(";")[0].strip()

                except Exception as e:
                    logger.debug(f"Link validation failed for {link.url}: {e}")
                    link.is_valid = False
                    link.status_code = None

                return link

        # Validate links concurrently
        tasks = [validate_single_link(link) for link in links]
        validated_links = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and return valid results
        result_links = []
        for result in validated_links:
            if isinstance(result, LinkInfo):
                result_links.append(result)
            elif isinstance(result, Exception):
                logger.warning(f"Link validation exception: {result}")

        return result_links

    def categorize_links(self, links: List[LinkInfo]) -> Dict[str, List[LinkInfo]]:
        """Categorize links by type and other criteria."""
        categories: Dict[str, List[LinkInfo]] = {
            "internal": [],
            "external": [],
            "media": [],
            "documents": [],
            "code": [],
            "text": [],
            "valid": [],
            "invalid": [],
            "unknown": [],
        }

        for link in links:
            # By internal/external
            if link.is_external:
                categories["external"].append(link)
            else:
                categories["internal"].append(link)

            # By content type
            if link.type:
                categories[link.type].append(link)
            else:
                categories["unknown"].append(link)

            # By validity
            if link.is_valid:
                categories["valid"].append(link)
            else:
                categories["invalid"].append(link)

        return categories

    def get_link_statistics(self, links: List[LinkInfo]) -> Dict[str, Any]:
        """Get statistics about extracted links."""
        if not links:
            return {}

        categories = self.categorize_links(links)

        # Domain analysis
        domains: Dict[str, int] = {}
        for link in links:
            parsed = urlparse(link.url)
            domain = parsed.netloc
            if domain:
                domains[domain] = domains.get(domain, 0) + 1

        # Protocol analysis
        protocols: Dict[str, int] = {}
        for link in links:
            parsed = urlparse(link.url)
            protocol = parsed.scheme
            if protocol:
                protocols[protocol] = protocols.get(protocol, 0) + 1

        return {
            "total_links": len(links),
            "internal_links": len(categories["internal"]),
            "external_links": len(categories["external"]),
            "media_links": len(categories["media"]),
            "document_links": len(categories["documents"]),
            "code_links": len(categories["code"]),
            "valid_links": len(categories["valid"]),
            "invalid_links": len(categories["invalid"]),
            "unique_domains": len(domains),
            "top_domains": sorted(domains.items(), key=lambda x: x[1], reverse=True)[
                :10
            ],
            "protocols": protocols,
        }
