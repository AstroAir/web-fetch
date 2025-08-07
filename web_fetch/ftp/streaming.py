"""
FTP streaming and large file support for the web fetcher utility.

This module provides streaming downloads for large files with progress tracking,
resumable downloads, and memory-efficient processing.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

import aiofiles

from ..exceptions import ErrorHandler, FTPError
from .connection import FTPConnectionPool
from .models import FTPConfig, FTPProgressInfo, FTPResult, FTPTransferMode
from .operations import FTPFileOperations


class FTPStreamingDownloader:
    """
    Streaming downloader for large FTP files with progress tracking
    and resumable downloads.
    """

    def __init__(self, config: FTPConfig):
        """Initialize the streaming downloader."""
        self.config = config
        self.connection_pool = FTPConnectionPool(config)
        self.file_operations = FTPFileOperations(config)

    async def close(self) -> None:
        """Close the downloader and cleanup resources."""
        await self.connection_pool.close_all()
        await self.file_operations.close()

    async def stream_download(
        self,
        url: str,
        local_path: Path,
        progress_callback: Optional[Callable[[FTPProgressInfo], None]] = None,
        chunk_size: Optional[int] = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream download a file from FTP server with progress tracking.

        Args:
            url: FTP URL of the file to download
            local_path: Local path to save the file
            progress_callback: Optional callback for progress updates
            chunk_size: Override chunk size for this download

        Yields:
            bytes: Chunks of downloaded data
        """
        chunk_size = chunk_size or self.config.chunk_size
        start_time = time.time()
        bytes_transferred = 0

        try:
            # Get file info
            file_info = await self.file_operations.get_file_info(url)
            total_bytes = file_info.size

            # Check for resume
            resume_position = 0
            if self.config.enable_resume and local_path.exists():
                resume_position = local_path.stat().st_size
                if total_bytes and resume_position >= total_bytes:
                    return  # File already complete

            async with self.connection_pool.get_connection(url) as client:
                from urllib.parse import urlparse

                parsed = urlparse(url)
                remote_path = parsed.path

                # Set transfer mode
                if self.config.transfer_mode == FTPTransferMode.BINARY:
                    await client.command("TYPE I")
                else:
                    await client.command("TYPE A")

                # Set resume position if needed
                if resume_position > 0:
                    await client.command(f"REST {resume_position}")

                # Start streaming download
                async with client.download_stream(remote_path) as stream:
                    last_progress_time = time.time()

                    async for chunk in stream.iter_by_block(chunk_size):
                        bytes_transferred += len(chunk)

                        # Yield chunk for processing
                        yield chunk

                        # Progress callback
                        if (
                            progress_callback
                            and time.time() - last_progress_time >= 0.1
                        ):
                            elapsed_time = time.time() - start_time
                            transfer_rate = (
                                bytes_transferred / elapsed_time
                                if elapsed_time > 0
                                else 0
                            )

                            # Estimate time remaining
                            estimated_remaining = None
                            if total_bytes and transfer_rate > 0:
                                remaining_bytes = total_bytes - (
                                    bytes_transferred + resume_position
                                )
                                estimated_remaining = remaining_bytes / transfer_rate

                            progress_info = FTPProgressInfo(
                                bytes_transferred=bytes_transferred + resume_position,
                                total_bytes=total_bytes,
                                transfer_rate=transfer_rate,
                                elapsed_time=elapsed_time,
                                estimated_time_remaining=estimated_remaining,
                                current_file=str(local_path),
                            )

                            if asyncio.iscoroutinefunction(progress_callback):
                                await progress_callback(progress_info)
                            else:
                                progress_callback(progress_info)

                            last_progress_time = time.time()

                        # Rate limiting
                        if self.config.rate_limit_bytes_per_second:
                            expected_time = (
                                bytes_transferred
                                / self.config.rate_limit_bytes_per_second
                            )
                            actual_time = time.time() - start_time
                            if actual_time < expected_time:
                                await asyncio.sleep(expected_time - actual_time)

                        # Check max file size limit
                        if (
                            self.config.max_file_size
                            and (bytes_transferred + resume_position)
                            > self.config.max_file_size
                        ):
                            raise FTPError(
                                f"File size exceeds limit: {self.config.max_file_size} bytes",
                                url,
                            )

        except Exception as e:
            if not isinstance(e, FTPError):
                e = ErrorHandler.handle_ftp_error(e, url, "stream_download")
            raise e

    async def download_with_streaming(
        self,
        url: str,
        local_path: Path,
        progress_callback: Optional[Callable[[FTPProgressInfo], None]] = None,
    ) -> FTPResult:
        """
        Download a file using streaming with automatic file writing.

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

            # Get file info
            file_info = await self.file_operations.get_file_info(url)
            total_bytes = file_info.size

            # Check for resume
            resume_position = 0
            if self.config.enable_resume and local_path.exists():
                resume_position = local_path.stat().st_size
                if total_bytes and resume_position >= total_bytes:
                    # File already complete
                    return FTPResult(
                        url=url,
                        operation="stream_download",
                        status_code=200,
                        local_path=local_path,
                        bytes_transferred=total_bytes or 0,
                        total_bytes=total_bytes,
                        response_time=time.time() - start_time,
                        timestamp=datetime.now(),
                        file_info=file_info,
                    )

            # Open file for writing
            mode = "ab" if resume_position > 0 else "wb"
            async with aiofiles.open(local_path, mode) as local_file:
                # Stream download and write to file
                async for chunk in self.stream_download(
                    url, local_path, progress_callback
                ):
                    await local_file.write(chunk)
                    bytes_transferred += len(chunk)

            # Verify download if configured
            verification_result = None
            if self.config.verification_method.value != "none":
                verification_result = await self.file_operations._verify_file(
                    local_path, file_info
                )
                if not verification_result.is_valid:
                    from ..exceptions import FTPVerificationError

                    raise FTPVerificationError(
                        f"File verification failed: {verification_result.error}",
                        url,
                        verification_method=verification_result.method,
                        expected_value=verification_result.expected_value,
                        actual_value=verification_result.actual_value,
                    )

            return FTPResult(
                url=url,
                operation="stream_download",
                status_code=200,
                local_path=local_path,
                bytes_transferred=bytes_transferred + resume_position,
                total_bytes=total_bytes,
                response_time=time.time() - start_time,
                timestamp=datetime.now(),
                file_info=file_info,
                verification_result=(
                    verification_result.verification_details
                    if verification_result
                    else None
                ),
            )

        except Exception as e:
            error = str(e)
            if not isinstance(e, FTPError):
                e = ErrorHandler.handle_ftp_error(e, url, "download_with_streaming")

            return FTPResult(
                url=url,
                operation="stream_download",
                status_code=500,
                local_path=local_path,
                bytes_transferred=bytes_transferred,
                total_bytes=total_bytes,
                response_time=time.time() - start_time,
                timestamp=datetime.now(),
                error=error,
            )
