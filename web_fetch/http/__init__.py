"""
Enhanced HTTP support for web_fetch.

This module provides comprehensive HTTP method support, advanced request
handling, and specialized HTTP features.
"""

from .cookies import CookieJar, CookieManager
from .download import DownloadHandler, ResumableDownloadHandler
from .headers import HeaderManager, HeaderPresets
from .methods import HTTPMethod, HTTPMethodHandler
from .pagination import PaginationHandler, PaginationStrategy
from .upload import FileUploadHandler, MultipartUploadHandler

__all__ = [
    "HTTPMethodHandler",
    "HTTPMethod",
    "FileUploadHandler",
    "MultipartUploadHandler",
    "DownloadHandler",
    "ResumableDownloadHandler",
    "PaginationHandler",
    "PaginationStrategy",
    "HeaderManager",
    "HeaderPresets",
    "CookieManager",
    "CookieJar",
]
