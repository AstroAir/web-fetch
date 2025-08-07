"""
Main FTP fetcher class that integrates all FTP functionality.

This module provides the main FTPFetcher class that combines connection management,
file operations, streaming, parallel downloads, and verification.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .connection import FTPConnectionPool
from .models import (
    FTPBatchRequest,
    FTPBatchResult,
    FTPConfig,
    FTPFileInfo,
    FTPProgressInfo,
    FTPRequest,
    FTPResult,
)
from .operations import FTPFileOperations
from .parallel import FTPParallelDownloader
from .streaming import FTPStreamingDownloader
from .verification import FTPVerificationManager


class FTPFetcher:
    """
    Comprehensive async FTP client with advanced features and connection management.

    FTPFetcher provides a modern, async-first approach to FTP operations with
    enterprise-grade features like connection pooling, parallel downloads,
    streaming capabilities, and comprehensive error handling.

    Key Features:
        - **Connection pooling**: Efficient connection reuse with automatic cleanup
        - **Multiple authentication**: Support for anonymous, password, and key-based auth
        - **File operations**: List directories, get file info, download files
        - **Batch operations**: Download multiple files concurrently with rate limiting
        - **Streaming downloads**: Memory-efficient downloads for large files
        - **Parallel downloads**: Multi-connection downloads for improved speed
        - **File verification**: Integrity checking with multiple hash algorithms
        - **Resumable downloads**: Resume interrupted downloads automatically
        - **Progress tracking**: Real-time progress callbacks with detailed statistics
        - **Error recovery**: Automatic retry with exponential backoff
        - **Transfer modes**: Support for both ASCII and binary transfer modes

    Supported Protocols:
        - FTP (File Transfer Protocol)
        - FTPS (FTP over SSL/TLS)
        - SFTP (SSH File Transfer Protocol) - via configuration

    Authentication Methods:
        - Anonymous access (no credentials required)
        - Username/password authentication
        - SSH key-based authentication (for SFTP)
        - Custom authentication handlers

    Performance Features:
        - Connection pooling reduces connection overhead
        - Parallel downloads can significantly improve throughput
        - Streaming downloads minimize memory usage
        - Configurable chunk sizes for optimal performance
        - Rate limiting prevents server overload

    Example:
        ```python
        import asyncio
        from pathlib import Path
        from web_fetch import FTPFetcher, FTPConfig, FTPRequest

        async def download_files():
            # Configure FTP connection
            config = FTPConfig(
                host="ftp.example.com",
                username="user",
                password="pass",
                max_connections=5,
                timeout=30.0
            )

            async with FTPFetcher(config) as ftp:
                # List directory contents
                files = await ftp.list_directory("ftp://ftp.example.com/pub/")
                print(f"Found {len(files)} files")

                # Download a single file
                request = FTPRequest(
                    url="ftp://ftp.example.com/pub/file.txt",
                    output_path=Path("downloads/file.txt")
                )
                result = await ftp.download_file(request)

                if result.is_success:
                    print(f"Downloaded {result.bytes_downloaded} bytes")

        asyncio.run(download_files())
        ```

    Thread Safety:
        FTPFetcher instances are not thread-safe. Each instance should be used
        within a single asyncio event loop. For multi-threaded applications,
        create separate instances per thread.

    Resource Management:
        Always use FTPFetcher as an async context manager to ensure proper
        connection cleanup. All connections will be automatically closed
        when exiting the context.

    See Also:
        - :class:`FTPConfig`: Configuration options for FTP operations
        - :class:`FTPRequest`: Request specification for FTP operations
        - :class:`FTPResult`: Result object with operation metadata
        - :class:`FTPFileInfo`: File and directory information
    """

    def __init__(self, config: Optional[FTPConfig] = None):
        """
        Initialize the FTP fetcher with comprehensive configuration.

        Creates a new FTPFetcher instance with the specified configuration and
        initializes all internal components including connection pool, file operations,
        streaming downloader, parallel downloader, and verification manager.

        Args:
            config: Optional FTP configuration object containing connection settings,
                   authentication credentials, timeout values, and operational parameters.
                   If None, uses default configuration with:
                   - Anonymous authentication
                   - 30-second timeout
                   - 5 maximum connections
                   - Binary transfer mode
                   - No SSL/TLS encryption

        Components Initialized:
            - connection_pool: Manages FTP connection lifecycle and pooling
            - file_operations: Handles basic file and directory operations
            - streaming_downloader: Provides memory-efficient streaming downloads
            - parallel_downloader: Enables multi-connection parallel downloads
            - verification_manager: Handles file integrity verification

        Example:
            ```python
            # Basic configuration
            config = FTPConfig(
                host="ftp.example.com",
                username="user",
                password="password"
            )

            # Advanced configuration
            advanced_config = FTPConfig(
                host="ftps.example.com",
                port=990,
                username="user",
                password="password",
                use_ssl=True,
                max_connections=10,
                timeout=60.0,
                transfer_mode=FTPTransferMode.BINARY,
                verify_ssl=True
            )

            fetcher = FTPFetcher(advanced_config)
            ```

        Note:
            The FTPFetcher instance is ready for use immediately after initialization,
            but connections are established lazily when operations are performed.
            Use as an async context manager for automatic resource cleanup.
        """
        self.config = config or FTPConfig()
        self.connection_pool = FTPConnectionPool(self.config)
        self.file_operations = FTPFileOperations(self.config)
        self.streaming_downloader = FTPStreamingDownloader(self.config)
        self.parallel_downloader = FTPParallelDownloader(self.config)
        self.verification_manager = FTPVerificationManager(self.config)

    async def __aenter__(self) -> FTPFetcher:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the fetcher and cleanup all resources."""
        await self.connection_pool.close_all()
        await self.file_operations.close()
        await self.streaming_downloader.close()
        await self.parallel_downloader.close()

    # File operations

    async def list_directory(self, url: str) -> List[FTPFileInfo]:
        """
        List files and directories in an FTP directory.

        Args:
            url: FTP URL of the directory to list

        Returns:
            List of FTPFileInfo objects
        """
        return await self.file_operations.list_directory(url)

    async def get_file_info(self, url: str) -> FTPFileInfo:
        """
        Get information about a specific FTP file or directory.

        Args:
            url: FTP URL of the file or directory

        Returns:
            FTPFileInfo object with file details
        """
        return await self.file_operations.get_file_info(url)

    # Single file downloads

    async def download_file(
        self,
        url: str,
        local_path: Path,
        progress_callback: Optional[Callable[[FTPProgressInfo], None]] = None,
    ) -> FTPResult:
        """
        Download a single file from FTP server.

        Args:
            url: FTP URL of the file to download
            local_path: Local path to save the file
            progress_callback: Optional callback for progress updates

        Returns:
            FTPResult with download information
        """
        return await self.file_operations.download_file(
            url, local_path, progress_callback
        )

    async def stream_download(
        self,
        url: str,
        local_path: Path,
        progress_callback: Optional[Callable[[FTPProgressInfo], None]] = None,
    ) -> FTPResult:
        """
        Download a file using streaming for large files.

        Args:
            url: FTP URL of the file to download
            local_path: Local path to save the file
            progress_callback: Optional callback for progress updates

        Returns:
            FTPResult with download information
        """
        return await self.streaming_downloader.download_with_streaming(
            url, local_path, progress_callback
        )

    # Batch operations

    async def download_batch(
        self,
        batch_request: FTPBatchRequest,
        progress_callback: Optional[Callable[[str, FTPProgressInfo], None]] = None,
    ) -> FTPBatchResult:
        """
        Download multiple files in batch.

        Args:
            batch_request: Batch request containing multiple FTP requests
            progress_callback: Optional callback for progress updates per file

        Returns:
            FTPBatchResult with results from all downloads
        """
        return await self.parallel_downloader.download_batch(
            batch_request, progress_callback
        )

    async def fetch_single(self, request: FTPRequest) -> FTPResult:
        """
        Process a single FTP request (download, list, or info).

        Args:
            request: FTP request to process

        Returns:
            FTPResult with operation result
        """
        # Lazy import once to avoid circular imports and ensure symbol binding across branches
        from ..exceptions import FTPError

        if request.operation == "download":
            if request.local_path is None:
                raise FTPError(
                    "Local path required for download operation", request.url
                )

            # Choose appropriate download method based on configuration
            if (
                self.config.max_file_size
                and self.config.max_file_size > 10 * 1024 * 1024
            ):
                return await self.stream_download(request.url, request.local_path)
            else:
                return await self.download_file(request.url, request.local_path)

        elif request.operation == "list":
            files_list = await self.list_directory(request.url)
            return FTPResult(
                url=request.url,
                operation="list",
                status_code=200,
                local_path=None,
                bytes_transferred=0,
                total_bytes=None,
                response_time=0.0,
                timestamp=datetime.now(),
                files_list=files_list,
            )

        elif request.operation == "info":
            file_info = await self.get_file_info(request.url)
            return FTPResult(
                url=request.url,
                operation="info",
                status_code=200,
                local_path=None,
                bytes_transferred=0,
                total_bytes=None,
                response_time=0.0,
                timestamp=datetime.now(),
                file_info=file_info,
            )

        else:
            # Reuse FTPError imported earlier in this function scope (line ~302)
            raise FTPError(f"Unsupported operation: {request.operation}", request.url)

    # Verification methods

    async def verify_file(
        self,
        local_path: Path,
        file_info: FTPFileInfo,
        expected_checksums: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Verify a downloaded file.

        Args:
            local_path: Path to the downloaded file
            file_info: Information about the original file
            expected_checksums: Optional dictionary of expected checksums

        Returns:
            True if verification passes, False otherwise
        """
        result = await self.verification_manager.verify_file(
            local_path, file_info, expected_checksums
        )
        return result.is_valid

    # Utility methods

    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the connection pool.

        Returns:
            Dictionary with connection pool statistics
        """
        return self.connection_pool.get_pool_stats()

    def update_config(self, **kwargs: Any) -> None:
        """
        Update configuration parameters.

        Args:
            **kwargs: Configuration parameters to update
        """
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)


# Convenience functions


async def ftp_download_file(
    url: str,
    local_path: Path,
    config: Optional[FTPConfig] = None,
    progress_callback: Optional[Callable[[FTPProgressInfo], None]] = None,
) -> FTPResult:
    """
    Convenience function to download a single FTP file.

    Args:
        url: FTP URL of the file to download
        local_path: Local path to save the file
        config: Optional FTP configuration
        progress_callback: Optional callback for progress updates

    Returns:
        FTPResult with download information
    """
    async with FTPFetcher(config) as fetcher:
        return await fetcher.download_file(url, local_path, progress_callback)


async def ftp_list_directory(
    url: str, config: Optional[FTPConfig] = None
) -> List[FTPFileInfo]:
    """
    Convenience function to list FTP directory contents.

    Args:
        url: FTP URL of the directory to list
        config: Optional FTP configuration

    Returns:
        List of FTPFileInfo objects
    """
    async with FTPFetcher(config) as fetcher:
        return await fetcher.list_directory(url)


async def ftp_get_file_info(
    url: str, config: Optional[FTPConfig] = None
) -> FTPFileInfo:
    """
    Convenience function to get FTP file information.

    Args:
        url: FTP URL of the file or directory
        config: Optional FTP configuration

    Returns:
        FTPFileInfo object with file details
    """
    async with FTPFetcher(config) as fetcher:
        return await fetcher.get_file_info(url)


async def ftp_download_batch(
    requests: List[FTPRequest],
    config: Optional[FTPConfig] = None,
    parallel: bool = False,
    progress_callback: Optional[Callable[[str, FTPProgressInfo], None]] = None,
) -> FTPBatchResult:
    """
    Convenience function to download multiple FTP files.

    Args:
        requests: List of FTP requests to process
        config: Optional FTP configuration
        parallel: Whether to execute downloads in parallel
        progress_callback: Optional callback for progress updates per file

    Returns:
        FTPBatchResult with results from all downloads
    """
    batch_request = FTPBatchRequest(
        requests=requests, config=config, parallel_execution=parallel
    )

    async with FTPFetcher(config) as fetcher:
        return await fetcher.download_batch(batch_request, progress_callback)
