"""
Modular web fetch components.

This package contains the refactored components of the web_fetch library,
organized into logical modules for better maintainability and code organization.
"""

# Re-export all components for easy access
from .core_fetcher import WebFetcher
from .streaming_fetcher import StreamingWebFetcher
from .convenience import (
    fetch_url,
    fetch_urls,
    download_file,
    fetch_with_cache,
)
from .url_utils import (
    is_valid_url,
    normalize_url,
    analyze_url,
    analyze_headers,
    detect_content_type,
)

__all__ = [
    # Core classes
    "WebFetcher",
    "StreamingWebFetcher",
    
    # Convenience functions
    "fetch_url",
    "fetch_urls", 
    "download_file",
    "fetch_with_cache",
    
    # URL utilities
    "is_valid_url",
    "normalize_url",
    "analyze_url",
    "analyze_headers",
    "detect_content_type",
]
