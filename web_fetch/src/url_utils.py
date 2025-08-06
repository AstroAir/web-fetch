"""
URL validation and analysis utilities.

This module provides utility functions for URL validation, normalization,
and analysis, as well as response header analysis and content type detection.
"""

from __future__ import annotations

from typing import Dict, Optional

from ..models.http import URLAnalysis, HeaderAnalysis


def is_valid_url(url: str) -> bool:
    """
    Check if a URL is valid.

    Validates URL format, scheme, and basic structure. Supports HTTP, HTTPS,
    FTP, and other common schemes. Does not perform network connectivity checks.

    Args:
        url: URL string to validate. Can be absolute or relative URL.

    Returns:
        True if URL has valid format and scheme, False otherwise.

    Example:
        ```python
        is_valid_url("https://example.com")  # True
        is_valid_url("http://localhost:8080/path")  # True
        is_valid_url("not-a-url")  # False
        is_valid_url("ftp://files.example.com/file.txt")  # True
        ```
    """
    from ..utils import URLValidator
    return URLValidator.is_valid_url(url)


def normalize_url(url: str, base_url: Optional[str] = None) -> str:
    """
    Normalize a URL by resolving relative paths and cleaning up.

    Performs URL normalization including scheme lowercasing, host lowercasing,
    path normalization (removing . and .. segments), query parameter sorting,
    and relative URL resolution against a base URL.

    Args:
        url: URL to normalize. Can be absolute or relative.
        base_url: Optional base URL for resolving relative URLs. If provided
                 and url is relative, the result will be an absolute URL.

    Returns:
        Normalized URL string with consistent formatting.

    Raises:
        ValueError: If url is invalid or base_url is provided but invalid.

    Example:
        ```python
        normalize_url("HTTPS://EXAMPLE.COM/Path/../Other?b=2&a=1")
        # Returns: "https://example.com/Other?a=1&b=2"

        normalize_url("../other", "https://example.com/path/")
        # Returns: "https://example.com/other"
        ```
    """
    from urllib.parse import urljoin
    from ..utils import URLValidator

    # Resolve relative URL against base_url if provided
    if base_url:
        url = urljoin(base_url, url)
    return URLValidator.normalize_url(url)


def analyze_url(url: str) -> URLAnalysis:
    """
    Perform comprehensive URL analysis.

    Extracts and analyzes all components of a URL including scheme, host,
    port, path, query parameters, and fragment. Also determines security
    characteristics and provides metadata about the URL structure.

    Args:
        url: URL string to analyze. Must be a valid absolute URL.

    Returns:
        URLAnalysis object containing:
        - scheme: URL scheme (http, https, ftp, etc.)
        - host: Hostname or IP address
        - port: Port number (explicit or default for scheme)
        - path: URL path component
        - query: Query parameters as dict
        - fragment: Fragment/anchor part
        - is_secure: Whether scheme uses encryption (https, ftps)
        - is_local: Whether host is localhost/127.0.0.1
        - domain_parts: List of domain components

    Raises:
        ValueError: If URL is invalid or malformed.

    Example:
        ```python
        analysis = analyze_url("https://api.example.com:8080/v1/data?key=value#section")
        print(f"Host: {analysis.host}")  # api.example.com
        print(f"Port: {analysis.port}")  # 8080
        print(f"Secure: {analysis.is_secure}")  # True
        print(f"Query: {analysis.query}")  # {'key': 'value'}
        ```
    """
    from ..utils import URLValidator
    return URLValidator.analyze_url(url)


def analyze_headers(headers: Dict[str, str]) -> HeaderAnalysis:
    """
    Analyze HTTP response headers.

    Parses and analyzes HTTP response headers to extract useful information
    about content type, encoding, caching directives, security headers,
    and server information.

    Args:
        headers: Dictionary of response headers with header names as keys
                and header values as strings. Header names are case-insensitive.

    Returns:
        HeaderAnalysis object containing:
        - content_type: Parsed content type and charset
        - content_length: Content length in bytes (if specified)
        - encoding: Character encoding (if specified)
        - cache_control: Cache control directives
        - security_headers: Security-related headers (HSTS, CSP, etc.)
        - server_info: Server software information
        - compression: Content compression method (gzip, deflate, etc.)

    Example:
        ```python
        headers = {
            'content-type': 'application/json; charset=utf-8',
            'content-length': '1024',
            'cache-control': 'max-age=3600',
            'server': 'nginx/1.18.0'
        }
        analysis = analyze_headers(headers)
        print(f"Content type: {analysis.content_type}")  # application/json
        print(f"Encoding: {analysis.encoding}")  # utf-8
        ```
    """
    from ..utils import ResponseAnalyzer
    return ResponseAnalyzer.analyze_headers(headers)


def detect_content_type(headers: Dict[str, str], content: bytes) -> str:
    """
    Detect content type from headers and content.

    Determines the content type by examining HTTP headers first, then falling
    back to content analysis if headers are missing or ambiguous. Uses both
    header parsing and content sniffing for accurate detection.

    Args:
        headers: Dictionary of HTTP response headers. The 'content-type' header
                is examined first for explicit content type information.
        content: Response content as bytes. Used for content sniffing if header
                information is insufficient. Only the first few bytes are examined.

    Returns:
        Detected content type string in MIME format (e.g., 'application/json',
        'text/html', 'image/png'). Returns 'application/octet-stream' if
        content type cannot be determined.

    Note:
        Content sniffing examines file signatures (magic bytes) and common
        patterns to identify file types. This is useful when servers don't
        provide accurate content-type headers.

    Example:
        ```python
        headers = {'content-type': 'application/json; charset=utf-8'}
        content = b'{"key": "value"}'
        content_type = detect_content_type(headers, content)
        print(content_type)  # application/json

        # With missing header, uses content sniffing
        headers = {}
        content = b'\\x89PNG\\r\\n\\x1a\\n'  # PNG file signature
        content_type = detect_content_type(headers, content)
        print(content_type)  # image/png
        ```
    """
    from ..utils import ResponseAnalyzer
    return ResponseAnalyzer.detect_content_type(headers, content)
