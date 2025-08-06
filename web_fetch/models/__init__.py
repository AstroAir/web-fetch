"""
Data models and configuration classes for the web_fetch library.

This package contains all data models, configuration classes, and type definitions
organized by protocol and functionality.
"""

# Import all models for easy access
from .base import *
from .http import *
from .ftp import *

__all__ = [
    # Base models and types
    "ContentType",
    "RetryStrategy",
    "RequestHeaders",
    "ProgressInfo",

    # Resource metadata classes
    "PDFMetadata",
    "ImageMetadata",
    "FeedMetadata",
    "FeedItem",
    "CSVMetadata",
    "LinkInfo",
    "ContentSummary",

    # HTTP models
    "FetchConfig",
    "FetchRequest",
    "FetchResult",
    "BatchFetchRequest",
    "BatchFetchResult",
    "StreamingConfig",
    "StreamRequest",
    "StreamResult",
    "CacheConfig",
    "RateLimitConfig",
    "SessionConfig",

    # FTP models
    "FTPConfig",
    "FTPRequest",
    "FTPResult",
    "FTPBatchRequest",
    "FTPBatchResult",
    "FTPFileInfo",
    "FTPProgressInfo",
    "FTPConnectionInfo",
    "FTPVerificationResult",
    "FTPAuthType",
    "FTPMode",
    "FTPTransferMode",
    "FTPVerificationMethod",
]
