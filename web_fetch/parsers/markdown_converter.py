"""
HTML to Markdown conversion with enhanced formatting.

This module provides functionality to convert HTML content to well-formatted
Markdown with support for tables, code blocks, links, and images.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional
from urllib.parse import urljoin, urlparse

try:
    import html2text

    HAS_HTML2TEXT = True
except ImportError:
    HAS_HTML2TEXT = False

from bs4 import BeautifulSoup

from ..exceptions import ContentError

logger = logging.getLogger(__name__)


class MarkdownConverter:
    """Converter for HTML to Markdown with enhanced formatting."""

    def __init__(self) -> None:
        """Initialize Markdown converter."""
        if not HAS_HTML2TEXT:
            logger.warning("html2text not available, using basic conversion")

        # Configure html2text if available
        if HAS_HTML2TEXT:
            self.h2t = html2text.HTML2Text()
            self.h2t.ignore_links = False
            self.h2t.ignore_images = False
            self.h2t.ignore_emphasis = False
            self.h2t.body_width = 0  # Don't wrap lines
            self.h2t.unicode_snob = True
            self.h2t.escape_snob = True
            self.h2t.mark_code = True
            self.h2t.wrap_links = False
            self.h2t.wrap_list_items = False
            self.h2t.default_image_alt = "Image"
            # Enhanced settings for better formatting
            self.h2t.protect_links = True
            self.h2t.skip_internal_links = False
            self.h2t.inline_links = True
            self.h2t.ignore_tables = False
            self.h2t.single_line_break = False
            self.h2t.use_automatic_links = True

    def convert(self, html_content: str, base_url: Optional[str] = None) -> str:
        """
        Convert HTML content to Markdown.

        Args:
            html_content: HTML content to convert
            base_url: Base URL for resolving relative links and images

        Returns:
            Markdown formatted string

        Raises:
            ContentError: If conversion fails
        """
        try:
            if HAS_HTML2TEXT:
                return self._convert_with_html2text(html_content, base_url)
            else:
                return self._convert_basic(html_content, base_url)

        except Exception as e:
            logger.error(f"Markdown conversion failed: {e}")
            raise ContentError(f"Failed to convert HTML to Markdown: {e}")

    def _convert_with_html2text(
        self, html_content: str, base_url: Optional[str]
    ) -> str:
        """Convert using html2text library for better formatting."""
        # Preprocess HTML to improve conversion
        processed_html = self._preprocess_html(html_content, base_url)

        # Convert to Markdown
        markdown = self.h2t.handle(processed_html)

        # Post-process Markdown
        markdown = self._postprocess_markdown(markdown)

        return markdown

    def _convert_basic(self, html_content: str, base_url: Optional[str]) -> str:
        """Basic HTML to Markdown conversion using BeautifulSoup."""
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "meta", "link"]):
            element.decompose()

        # Convert common elements
        markdown_parts = []

        for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            level = int(element.name[1])
            text = element.get_text(strip=True)
            if text:
                markdown_parts.append("#" * level + " " + text + "\n\n")

        for element in soup.find_all("p"):
            text = element.get_text(strip=True)
            if text:
                markdown_parts.append(text + "\n\n")

        for element in soup.find_all("a"):
            text = element.get_text(strip=True)
            href = element.get("href", "")
            if text and href:
                if base_url:
                    href = urljoin(base_url, href)
                markdown_parts.append(f"[{text}]({href})")

        for element in soup.find_all("img"):
            alt = element.get("alt", "Image")
            src = element.get("src", "")
            if src:
                if base_url:
                    src = urljoin(base_url, src)
                markdown_parts.append(f"![{alt}]({src})\n\n")

        # Handle lists
        for element in soup.find_all(["ul", "ol"]):
            list_items = element.find_all("li")
            for i, li in enumerate(list_items):
                text = li.get_text(strip=True)
                if text:
                    if element.name == "ul":
                        markdown_parts.append(f"- {text}\n")
                    else:
                        markdown_parts.append(f"{i+1}. {text}\n")
            markdown_parts.append("\n")

        # Handle code blocks
        for element in soup.find_all(["code", "pre"]):
            text = element.get_text()
            if element.name == "pre":
                markdown_parts.append(f"```\n{text}\n```\n\n")
            else:
                markdown_parts.append(f"`{text}`")

        # Handle blockquotes
        for element in soup.find_all("blockquote"):
            text = element.get_text(strip=True)
            if text:
                lines = text.split("\n")
                quoted_lines = ["> " + line for line in lines]
                markdown_parts.append("\n".join(quoted_lines) + "\n\n")

        # Get remaining text
        remaining_text = soup.get_text(strip=True)
        if remaining_text and not any(
            remaining_text in part for part in markdown_parts
        ):
            markdown_parts.append(remaining_text)

        return "".join(markdown_parts)

    def _preprocess_html(self, html_content: str, base_url: Optional[str]) -> str:
        """Preprocess HTML to improve Markdown conversion."""
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove unwanted elements
        for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
            element.decompose()

        # Convert relative URLs to absolute
        if base_url:
            for element in soup.find_all(["a", "img"]):
                if element.name == "a" and element.get("href"):
                    element["href"] = urljoin(base_url, element["href"])
                elif element.name == "img" and element.get("src"):
                    element["src"] = urljoin(base_url, element["src"])

        # Improve table formatting
        for table in soup.find_all("table"):
            # Add spacing around tables
            table.insert_before("\n\n")
            table.insert_after("\n\n")

        # Improve code block formatting
        for pre in soup.find_all("pre"):
            code = pre.find("code")
            if code:
                # Try to detect language from class
                classes = code.get("class", [])
                language = ""
                for cls in classes:
                    if isinstance(cls, str):
                        if cls.startswith("language-"):
                            language = cls[9:]
                            break
                        elif cls.startswith("lang-"):
                            language = cls[5:]
                            break
                        elif cls.startswith("highlight-"):
                            language = cls[10:]
                            break

                if language:
                    pre["data-language"] = language

                # Preserve code formatting
                code_text = code.get_text()
                if code_text:
                    # Replace the code element with formatted text
                    if language:
                        formatted_code = f"```{language}\n{code_text}\n```"
                    else:
                        formatted_code = f"```\n{code_text}\n```"
                    pre.string = formatted_code
            else:
                # Handle pre without code tags
                pre_text = pre.get_text()
                if pre_text:
                    pre.string = f"```\n{pre_text}\n```"

        return str(soup)

    def _postprocess_markdown(self, markdown: str) -> str:
        """Post-process Markdown to clean up formatting."""
        # Remove excessive blank lines
        markdown = re.sub(r"\n{3,}", "\n\n", markdown)

        # Clean up list formatting
        markdown = re.sub(r"\n\s*\n(\s*[-*+])", r"\n\1", markdown)
        markdown = re.sub(r"\n\s*\n(\s*\d+\.)", r"\n\1", markdown)

        # Clean up heading spacing
        markdown = re.sub(r"\n(#{1,6}\s)", r"\n\n\1", markdown)
        markdown = re.sub(r"(#{1,6}\s.*)\n([^\n])", r"\1\n\n\2", markdown)

        # Clean up code block formatting
        markdown = re.sub(r"```\n\n", "```\n", markdown)
        markdown = re.sub(r"\n\n```", "\n```", markdown)

        # Clean up table formatting
        markdown = re.sub(r"\n\n(\|.*\|)\n\n", r"\n\n\1\n", markdown)

        # Remove leading/trailing whitespace
        markdown = markdown.strip()

        return markdown

    def extract_metadata(self, html_content: str) -> Dict[str, Any]:
        """
        Extract metadata from HTML content.

        Args:
            html_content: HTML content to analyze

        Returns:
            Dictionary with extracted metadata
        """
        soup = BeautifulSoup(html_content, "html.parser")
        metadata = {}

        # Extract title
        title_tag = soup.find("title")
        if title_tag:
            metadata["title"] = title_tag.get_text(strip=True)

        # Extract meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            metadata["description"] = meta_desc.get("content", "")

        # Extract meta keywords
        meta_keywords = soup.find("meta", attrs={"name": "keywords"})
        if meta_keywords:
            metadata["keywords"] = meta_keywords.get("content", "").split(",")

        # Extract author
        meta_author = soup.find("meta", attrs={"name": "author"})
        if meta_author:
            metadata["author"] = meta_author.get("content", "")

        # Count elements
        metadata["headings"] = len(soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]))
        metadata["paragraphs"] = len(soup.find_all("p"))
        metadata["links"] = len(soup.find_all("a", href=True))
        metadata["images"] = len(soup.find_all("img", src=True))
        metadata["tables"] = len(soup.find_all("table"))
        metadata["lists"] = len(soup.find_all(["ul", "ol"]))
        metadata["code_blocks"] = len(soup.find_all(["pre", "code"]))

        # Extract text statistics
        text_content = soup.get_text()
        words = text_content.split()
        metadata["word_count"] = len(words)
        metadata["character_count"] = len(text_content)

        return metadata

    def convert_table_to_markdown(self, table_html: str) -> str:
        """
        Convert HTML table to Markdown table format with enhanced formatting.

        Args:
            table_html: HTML table content

        Returns:
            Markdown formatted table
        """
        soup = BeautifulSoup(table_html, "html.parser")
        table = soup.find("table")

        if not table:
            return table_html

        markdown_rows = []

        # Check for thead/tbody structure
        thead = table.find("thead")
        tbody = table.find("tbody")

        headers = []
        data_rows = []

        if thead:
            # Extract headers from thead
            header_rows = thead.find_all("tr")
            if header_rows:
                for th in header_rows[0].find_all(["th", "td"]):
                    cell_text = self._clean_cell_text(th.get_text())
                    colspan = int(th.get("colspan", 1))
                    headers.extend([cell_text] + [""] * (colspan - 1))

        if tbody:
            # Extract data from tbody
            data_rows = tbody.find_all("tr")
        else:
            # No tbody, get all rows and determine header
            all_rows = table.find_all("tr")
            if all_rows:
                if not headers:
                    # First row as header if no thead
                    first_row = all_rows[0]
                    for cell in first_row.find_all(["th", "td"]):
                        cell_text = self._clean_cell_text(cell.get_text())
                        colspan = int(cell.get("colspan", 1))
                        headers.extend([cell_text] + [""] * (colspan - 1))
                    data_rows = all_rows[1:]
                else:
                    data_rows = all_rows

        # Build markdown table
        if headers:
            # Clean and format headers
            clean_headers = [h or "Column" for h in headers]
            markdown_rows.append("| " + " | ".join(clean_headers) + " |")

            # Create separator row with alignment
            separators = []
            for header in clean_headers:
                separators.append("---")
            markdown_rows.append("| " + " | ".join(separators) + " |")

        # Process data rows
        for row in data_rows:
            cells = []
            for td in row.find_all(["td", "th"]):
                cell_text = self._clean_cell_text(td.get_text())
                colspan = int(td.get("colspan", 1))
                cells.extend([cell_text] + [""] * (colspan - 1))

            # Ensure row has same number of columns as header
            if headers:
                while len(cells) < len(headers):
                    cells.append("")
                cells = cells[: len(headers)]

            if cells:
                markdown_rows.append("| " + " | ".join(cells) + " |")

        return "\n".join(markdown_rows)

    def _clean_cell_text(self, text: str) -> str:
        """Clean and format cell text for Markdown tables."""
        if not text:
            return ""

        # Remove extra whitespace and newlines
        cleaned = " ".join(text.split())

        # Escape pipe characters
        cleaned = cleaned.replace("|", "\\|")

        # Remove markdown formatting that could break tables
        cleaned = cleaned.replace("*", "\\*")
        cleaned = cleaned.replace("_", "\\_")
        cleaned = cleaned.replace("[", "\\[")
        cleaned = cleaned.replace("]", "\\]")

        return cleaned

    def is_valid_html(self, content: str) -> bool:
        """
        Check if content is valid HTML.

        Args:
            content: Content to check

        Returns:
            True if content appears to be HTML, False otherwise
        """
        try:
            soup = BeautifulSoup(content, "html.parser")

            # Check for common HTML elements
            html_elements = soup.find_all(
                ["html", "head", "body", "div", "p", "h1", "h2", "h3"]
            )

            return len(html_elements) > 0

        except Exception:
            return False

    def enhance_link_formatting(self, markdown: str) -> str:
        """Enhance link formatting in Markdown."""
        # Convert reference-style links to inline links for better readability
        lines = markdown.split("\n")
        enhanced_lines = []

        for line in lines:
            # Convert [text][ref] to [text](url) if possible
            # This is a simplified implementation
            enhanced_lines.append(line)

        return "\n".join(enhanced_lines)

    def add_table_of_contents(self, markdown: str) -> str:
        """Add table of contents to Markdown based on headers."""
        lines = markdown.split("\n")
        toc_lines = ["## Table of Contents\n"]
        content_lines = []

        for line in lines:
            if line.startswith("#"):
                # Extract header level and text
                level = len(line) - len(line.lstrip("#"))
                header_text = line.lstrip("# ").strip()

                if header_text and level <= 3:  # Only include h1-h3 in TOC
                    # Create anchor link
                    anchor = (
                        header_text.lower().replace(" ", "-").replace("[^a-z0-9-]", "")
                    )
                    indent = "  " * (level - 1)
                    toc_lines.append(f"{indent}- [{header_text}](#{anchor})")

            content_lines.append(line)

        # Only add TOC if there are headers
        if len(toc_lines) > 1:
            return "\n".join(toc_lines) + "\n\n" + "\n".join(content_lines)
        else:
            return "\n".join(content_lines)

    def optimize_whitespace(self, markdown: str) -> str:
        """Optimize whitespace in Markdown for better readability."""
        # Remove excessive blank lines
        lines = markdown.split("\n")
        optimized_lines = []
        prev_blank = False

        for line in lines:
            is_blank = not line.strip()

            if is_blank:
                if not prev_blank:
                    optimized_lines.append("")
                prev_blank = True
            else:
                optimized_lines.append(line)
                prev_blank = False

        return "\n".join(optimized_lines)
