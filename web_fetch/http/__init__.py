"""
Enhanced HTTP support for web_fetch.

This module provides comprehensive HTTP method support, advanced request
handling, and specialized HTTP features.
"""

from .methods import HTTPMethodHandler, HTTPMethod
from .upload import FileUploadHandler, MultipartUploadHandler
from .download import DownloadHandler, ResumableDownloadHandler
from .pagination import PaginationHandler, PaginationStrategy
from .headers import HeaderManager, HeaderPresets
from .cookies import CookieManager, CookieJar

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
