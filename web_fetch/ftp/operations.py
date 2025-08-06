"""
FTP file operations for the web fetcher utility.

This module provides FTP file operations including listing, downloading,
and directory traversal with proper error handling.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import aiofiles
import aioftp

from ..exceptions import ErrorHandler, FTPError, FTPFileNotFoundError, FTPVerificationError
from .connection import FTPConnectionPool
from .models import (
    FTPConfig,
    FTPFileInfo,
    FTPProgressInfo,
    FTPRequest,
    FTPResult,
    FTPTransferMode,
    FTPVerificationMethod,
    FTPVerificationResult,
)


class FTPFileOperations:
    """
    FTP file operations handler with support for listing, downloading,
    and directory traversal.
    """

    def __init__(self, config: FTPConfig):
        """Initialize FTP operations with configuration."""
        self.config = config
        self.connection_pool = FTPConnectionPool(config)

    async def close(self) -> None:
        """Close the operations handler and cleanup resources."""
        await self.connection_pool.close_all()

    async def list_directory(self, url: str) -> List[FTPFileInfo]:
        """
        List files and directories in an FTP directory.

        Args:
            url: FTP URL of the directory to list

        Returns:
            List of FTPFileInfo objects
        """
        try:
            async with self.connection_pool.get_connection(url) as client:
                parsed = urlparse(url)
                path = parsed.path or '/'

                # Change to the directory
                if path != '/':
                    await client.change_directory(path)

                # List directory contents
                files = []
                async for path_info in client.list():
                    file_info = FTPFileInfo(
                        name=path_info.name,
                        path=str(path_info),
                        size=path_info.stat.size if hasattr(path_info.stat, 'size') else None,
                        modified_time=datetime.fromtimestamp(path_info.stat.st_mtime) if hasattr(path_info.stat, 'st_mtime') else None,
                        is_directory=path_info.is_dir(),
                        permissions=oct(path_info.stat.st_mode) if hasattr(path_info.stat, 'st_mode') else None,
                    )
                    files.append(file_info)

                return files

        except Exception as e:
            raise ErrorHandler.handle_ftp_error(e, url, "list_directory")

    async def get_file_info(self, url: str) -> FTPFileInfo:
        """
        Get information about a specific FTP file or directory.

        Args:
            url: FTP URL of the file or directory

        Returns:
            FTPFileInfo object with file details
        """
        try:
            async with self.connection_pool.get_connection(url) as client:
                parsed = urlparse(url)
                path = parsed.path or '/'

                # Get file/directory info
                try:
                    stat_info = await client.stat(path)

                    file_info = FTPFileInfo(
                        name=os.path.basename(path),
                        path=path,
                        size=stat_info.size if hasattr(stat_info, 'size') else None,
                        modified_time=datetime.fromtimestamp(stat_info.st_mtime) if hasattr(stat_info, 'st_mtime') else None,
                        is_directory=stat_info.is_dir() if hasattr(stat_info, 'is_dir') else False,
                        permissions=oct(stat_info.st_mode) if hasattr(stat_info, 'st_mode') else None,
                    )

                    return file_info

                except Exception:
                    # If stat fails, try to list parent directory
                    parent_path = os.path.dirname(path)
                    filename = os.path.basename(path)

                    if parent_path != path:
                        await client.change_directory(parent_path)
                        async for path_info in client.list():
                            if path_info.name == filename:
                                return FTPFileInfo(
                                    name=path_info.name,
                                    path=path,
                                    size=path_info.stat.size if hasattr(path_info.stat, 'size') else None,
                                    modified_time=datetime.fromtimestamp(path_info.stat.st_mtime) if hasattr(path_info.stat, 'st_mtime') else None,
                                    is_directory=path_info.is_dir(),
                                    permissions=oct(path_info.stat.st_mode) if hasattr(path_info.stat, 'st_mode') else None,
                                )

                    raise FTPFileNotFoundError(f"File not found: {path}", url)

        except Exception as e:
            if isinstance(e, FTPFileNotFoundError):
                raise
            raise ErrorHandler.handle_ftp_error(e, url, "get_file_info")

    async def download_file(
        self,
        url: str,
        local_path: Path,
        progress_callback: Optional[Callable] = None
    ) -> FTPResult:
        """
        Download a file from FTP server.

        Args:
            url: FTP URL of the file to download
            local_path: Local path to save the file
            progress_callback: Optional callback for progress updates

        Returns:
            FTPResult with download information
        """
        start_time = time.time()
        bytes_transferred = 0
        total_bytes = None
        error = None

        try:
            # Ensure local directory exists
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # Get file info first
            file_info = await self.get_file_info(url)
            total_bytes = file_info.size

            # Check if resume is needed
            resume_position = 0
            if self.config.enable_resume and local_path.exists():
                resume_position = local_path.stat().st_size
                if total_bytes and resume_position >= total_bytes:
                    # File already complete
                    return FTPResult(
                        url=url,
                        operation="download",
                        status_code=200,
                        local_path=local_path,
                        bytes_transferred=total_bytes or 0,
                        total_bytes=total_bytes,
                        response_time=time.time() - start_time,
                        timestamp=datetime.now(),
                        file_info=file_info
                    )

            async with self.connection_pool.get_connection(url) as client:
                parsed = urlparse(url)
                remote_path = parsed.path

                # Set transfer mode
                if self.config.transfer_mode == FTPTransferMode.BINARY:
                    await client.command("TYPE I")  # Binary mode
                else:
                    await client.command("TYPE A")  # ASCII mode

                # Open local file for writing
                mode = "ab" if resume_position > 0 else "wb"
                async with aiofiles.open(local_path, mode) as local_file:
                    # Start download with resume if needed
                    if resume_position > 0:
                        await client.command(f"REST {resume_position}")

                    # Download file
                    async with client.download_stream(remote_path) as stream:
                        last_progress_time = time.time()

                        async for chunk in stream.iter_by_block(self.config.chunk_size):
                            await local_file.write(chunk)
                            bytes_transferred += len(chunk)

                            # Progress callback
                            if progress_callback and time.time() - last_progress_time >= 0.1:
                                progress_info = FTPProgressInfo(
                                    bytes_transferred=bytes_transferred + resume_position,
                                    total_bytes=total_bytes,
                                    transfer_rate=bytes_transferred / (time.time() - start_time) if time.time() > start_time else 0,
                                    elapsed_time=time.time() - start_time,
                                    estimated_time_remaining=None,
                                    current_file=str(local_path)
                                )
                                await progress_callback(progress_info)
                                last_progress_time = time.time()

                            # Rate limiting
                            if self.config.rate_limit_bytes_per_second:
                                expected_time = bytes_transferred / self.config.rate_limit_bytes_per_second
                                actual_time = time.time() - start_time
                                if actual_time < expected_time:
                                    await asyncio.sleep(expected_time - actual_time)

            # Verify download if configured
            verification_result = None
            if self.config.verification_method != FTPVerificationMethod.NONE:
                verification_result = await self._verify_file(local_path, file_info)
                if not verification_result.is_valid:
                    raise FTPVerificationError(
                        f"File verification failed: {verification_result.error}",
                        url,
                        verification_method=verification_result.method,
                        expected_value=verification_result.expected_value,
                        actual_value=verification_result.actual_value
                    )

            return FTPResult(
                url=url,
                operation="download",
                status_code=200,
                local_path=local_path,
                bytes_transferred=bytes_transferred + resume_position,
                total_bytes=total_bytes,
                response_time=time.time() - start_time,
                timestamp=datetime.now(),
                file_info=file_info,
                verification_result=verification_result.verification_details if verification_result else None
            )

        except Exception as e:
            error = str(e)
            if not isinstance(e, (FTPError, FTPVerificationError)):
                e = ErrorHandler.handle_ftp_error(e, url, "download_file")

            return FTPResult(
                url=url,
                operation="download",
                status_code=500,
                local_path=local_path,
                bytes_transferred=bytes_transferred,
                total_bytes=total_bytes,
                response_time=time.time() - start_time,
                timestamp=datetime.now(),
                error=error
            )

    async def _verify_file(self, local_path: Path, file_info: FTPFileInfo) -> FTPVerificationResult:
        """
        Verify downloaded file integrity.

        Args:
            local_path: Path to the downloaded file
            file_info: Information about the original file

        Returns:
            FTPVerificationResult with verification details
        """
        try:
            if self.config.verification_method == FTPVerificationMethod.SIZE:
                actual_size = local_path.stat().st_size
                expected_size = file_info.size

                if expected_size is None:
                    return FTPVerificationResult(
                        method=FTPVerificationMethod.SIZE,
                        expected_value=None,
                        actual_value=str(actual_size),
                        is_valid=True,
                        error="No expected size available, skipping verification"
                    )

                is_valid = actual_size == expected_size
                return FTPVerificationResult(
                    method=FTPVerificationMethod.SIZE,
                    expected_value=str(expected_size),
                    actual_value=str(actual_size),
                    is_valid=is_valid,
                    error=None if is_valid else f"Size mismatch: expected {expected_size}, got {actual_size}"
                )

            elif self.config.verification_method in [FTPVerificationMethod.MD5, FTPVerificationMethod.SHA256]:
                # Calculate file hash
                hash_func = hashlib.md5() if self.config.verification_method == FTPVerificationMethod.MD5 else hashlib.sha256()

                async with aiofiles.open(local_path, 'rb') as f:
                    while chunk := await f.read(self.config.chunk_size):
                        hash_func.update(chunk)

                actual_hash = hash_func.hexdigest()

                # For now, we can't get the expected hash from FTP server
                # This would need to be provided externally or calculated on server
                return FTPVerificationResult(
                    method=self.config.verification_method,
                    expected_value=None,
                    actual_value=actual_hash,
                    is_valid=True,
                    error="Hash calculated but no expected value to compare against"
                )

            else:
                return FTPVerificationResult(
                    method=FTPVerificationMethod.NONE,
                    expected_value=None,
                    actual_value=None,
                    is_valid=True,
                    error=None
                )

        except Exception as e:
            return FTPVerificationResult(
                method=self.config.verification_method,
                expected_value=None,
                actual_value=None,
                is_valid=False,
                error=f"Verification failed: {str(e)}"
            )