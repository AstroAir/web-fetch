"""
URL validation and analysis utilities.

This module provides utility functions for URL validation, normalization,
and analysis, as well as response header analysis and content type detection.
"""

from __future__ import annotations

from typing import Dict, Optional
from urllib.parse import urljoin

from ..models.http import HeaderAnalysis, URLAnalysis


def is_valid_url(url: str) -> bool:
    """
    Check if a URL is valid.

    Args:
        url: URL string to validate

    Returns:
        True if URL is valid, False otherwise
    """
    from .validation import URLValidator

    return URLValidator.is_valid_url(url)


def normalize_url(url: str, base_url: Optional[str] = None) -> str:
    """
    Normalize a URL by resolving relative paths and cleaning up.

    Args:
        url: URL to normalize
        base_url: Base URL for resolving relative URLs

    Returns:
        Normalized URL string
    """
    from .validation import URLValidator

    # Resolve relative URL against base_url if provided
    if base_url:
        url = urljoin(base_url, url)
    return URLValidator.normalize_url(url)


def analyze_url(url: str) -> URLAnalysis:  # Returns URLAnalysis
    """
    Perform comprehensive URL analysis.

    Args:
        url: URL to analyze

    Returns:
        URLAnalysis object with detailed information
    """
    from .validation import URLValidator

    return URLValidator.analyze_url(url)


def analyze_headers(
    headers: Dict[str, str],
) -> HeaderAnalysis:  # Returns HeaderAnalysis
    """
    Analyze HTTP response headers.

    Args:
        headers: Dictionary of response headers

    Returns:
        HeaderAnalysis object with parsed header information
    """
    from .response import ResponseAnalyzer

    return ResponseAnalyzer.analyze_headers(headers)


def detect_content_type(headers: Dict[str, str], content: bytes) -> str:
    """
    Detect content type from headers and content.

    Args:
        headers: Response headers
        content: Response content bytes

    Returns:
        Detected content type string
    """
    from .response import ResponseAnalyzer

    return ResponseAnalyzer.detect_content_type(headers, content)
