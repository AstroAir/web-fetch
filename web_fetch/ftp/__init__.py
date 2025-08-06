"""
FTP functionality for the web_fetch library.

This package provides comprehensive FTP support including:
- Async FTP client with connection pooling
- File upload/download with progress tracking
- Batch operations and parallel transfers
- Streaming support for large files
- File verification and integrity checking
"""

from .fetcher import (
    FTPFetcher,
    ftp_download_batch,
    ftp_download_file,
    ftp_get_file_info,
    ftp_list_directory,
)
from .models import (
    FTPAuthType,
    FTPBatchRequest,
    FTPBatchResult,
    FTPConfig,
    FTPConnectionInfo,
    FTPFileInfo,
    FTPMode,
    FTPProgressInfo,
    FTPRequest,
    FTPResult,
    FTPTransferMode,
    FTPVerificationMethod,
    FTPVerificationResult,
)

__all__ = [
    # Main FTP client
    "FTPFetcher",
    
    # Convenience functions
    "ftp_download_file",
    "ftp_download_batch",
    "ftp_list_directory",
    "ftp_get_file_info",
    
    # Models and configuration
    "FTPConfig",
    "FTPRequest",
    "FTPResult",
    "FTPBatchRequest",
    "FTPBatchResult",
    "FTPFileInfo",
    "FTPProgressInfo",
    "FTPConnectionInfo",
    "FTPVerificationResult",
    
    # Enums
    "FTPMode",
    "FTPAuthType",
    "FTPTransferMode",
    "FTPVerificationMethod",
]
