"""
Parallel FTP downloads with rate limiting and connection pooling.

This module provides parallel download capabilities for FTP operations
with configurable concurrency, rate limiting, and connection management.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ..exceptions import ErrorHandler, FTPError
from .models import (
    FTPBatchRequest,
    FTPBatchResult,
    FTPConfig,
    FTPProgressInfo,
    FTPRequest,
    FTPResult,
)
from .operations import FTPFileOperations
from .streaming import FTPStreamingDownloader


class FTPParallelDownloader:
    """
    Parallel FTP downloader with rate limiting and connection pooling.
    """

    def __init__(self, config: FTPConfig):
        """Initialize the parallel downloader."""
        self.config = config
        self.file_operations = FTPFileOperations(config)
        self.streaming_downloader = FTPStreamingDownloader(config)
        self._semaphore = asyncio.Semaphore(config.max_concurrent_downloads)
        self._rate_limiter = asyncio.Semaphore(1)  # For global rate limiting

    async def close(self) -> None:
        """Close the downloader and cleanup resources."""
        await self.file_operations.close()
        await self.streaming_downloader.close()

    async def download_batch(
        self,
        batch_request: FTPBatchRequest,
        progress_callback: Optional[Callable[[str, FTPProgressInfo], None]] = None
    ) -> FTPBatchResult:
        """
        Download multiple files in parallel.

        Args:
            batch_request: Batch request containing multiple FTP requests
            progress_callback: Optional callback for progress updates per file

        Returns:
            FTPBatchResult with results from all downloads
        """
        start_time = time.time()

        if batch_request.parallel_execution and self.config.enable_parallel_downloads:
            results = await self._download_parallel(batch_request.requests, progress_callback)
        else:
            results = await self._download_sequential(batch_request.requests, progress_callback)

        total_time = time.time() - start_time
        return FTPBatchResult.from_results(results, total_time)

    async def _download_parallel(
        self,
        requests: List[FTPRequest],
        progress_callback: Optional[Callable[[str, FTPProgressInfo], None]] = None
    ) -> List[FTPResult]:
        """
        Download files in parallel with concurrency control.

        Args:
            requests: List of FTP requests to process
            progress_callback: Optional progress callback

        Returns:
            List of FTPResult objects
        """
        tasks = []

        for request in requests:
            task = asyncio.create_task(
                self._download_single_with_semaphore(request, progress_callback)
            )
            tasks.append(task)

        # Wait for all downloads to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        final_results: List[FTPResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_result = FTPResult(
                    url=requests[i].url,
                    operation=requests[i].operation,
                    status_code=500,
                    local_path=requests[i].local_path,
                    bytes_transferred=0,
                    total_bytes=None,
                    response_time=0.0,
                    timestamp=datetime.now(),
                    error=str(result)
                )
                final_results.append(error_result)
            elif isinstance(result, FTPResult):
                final_results.append(result)

        return final_results

    async def _download_sequential(
        self,
        requests: List[FTPRequest],
        progress_callback: Optional[Callable[[str, FTPProgressInfo], None]] = None
    ) -> List[FTPResult]:
        """
        Download files sequentially.

        Args:
            requests: List of FTP requests to process
            progress_callback: Optional progress callback

        Returns:
            List of FTPResult objects
        """
        results = []

        for request in requests:
            try:
                result = await self._download_single(request, progress_callback)
                results.append(result)
            except Exception as e:
                error_result = FTPResult(
                    url=request.url,
                    operation=request.operation,
                    status_code=500,
                    local_path=request.local_path,
                    bytes_transferred=0,
                    total_bytes=None,
                    response_time=0.0,
                    timestamp=datetime.now(),
                    error=str(e)
                )
                results.append(error_result)

        return results

    async def _download_single_with_semaphore(
        self,
        request: FTPRequest,
        progress_callback: Optional[Callable[[str, FTPProgressInfo], None]] = None
    ) -> FTPResult:
        """
        Download a single file with semaphore control for concurrency.

        Args:
            request: FTP request to process
            progress_callback: Optional progress callback

        Returns:
            FTPResult object
        """
        async with self._semaphore:
            return await self._download_single(request, progress_callback)

    async def _download_single(
        self,
        request: FTPRequest,
        progress_callback: Optional[Callable[[str, FTPProgressInfo], None]] = None
    ) -> FTPResult:
        """
        Download a single file with retry logic.

        Args:
            request: FTP request to process
            progress_callback: Optional progress callback

        Returns:
            FTPResult object
        """
        # Use request-specific config if provided
        config = request.config_override or self.config

        # Create progress callback wrapper for this specific file
        file_progress_callback = None
        if progress_callback:
            def wrapped_callback(progress_info: FTPProgressInfo) -> None:
                if asyncio.iscoroutinefunction(progress_callback):
                    asyncio.create_task(progress_callback(request.url, progress_info))
                else:
                    progress_callback(request.url, progress_info)
            file_progress_callback = wrapped_callback

        # Retry logic
        last_error = None
        for attempt in range(config.max_retries + 1):
            try:
                if request.operation == "download":
                    if request.local_path is None:
                        raise FTPError("Local path required for download operation", request.url)

                    # Use streaming downloader for large files or if configured
                    if config.max_file_size and config.max_file_size > 10 * 1024 * 1024:  # 10MB threshold
                        result = await self.streaming_downloader.download_with_streaming(
                            request.url,
                            request.local_path,
                            file_progress_callback
                        )
                    else:
                        result = await self.file_operations.download_file(
                            request.url,
                            request.local_path,
                            file_progress_callback
                        )

                    return result

                elif request.operation == "list":
                    files_list = await self.file_operations.list_directory(request.url)
                    return FTPResult(
                        url=request.url,
                        operation="list",
                        status_code=200,
                        local_path=None,
                        bytes_transferred=0,
                        total_bytes=None,
                        response_time=0.0,
                        timestamp=datetime.now(),
                        files_list=files_list
                    )

                elif request.operation == "info":
                    file_info = await self.file_operations.get_file_info(request.url)
                    return FTPResult(
                        url=request.url,
                        operation="info",
                        status_code=200,
                        local_path=None,
                        bytes_transferred=0,
                        total_bytes=None,
                        response_time=0.0,
                        timestamp=datetime.now(),
                        file_info=file_info
                    )

                else:
                    raise FTPError(f"Unsupported operation: {request.operation}", request.url)

            except Exception as e:
                last_error = e

                # Check if error is retryable
                if attempt < config.max_retries and ErrorHandler.is_retryable_ftp_error(e):
                    # Calculate retry delay with exponential backoff
                    delay = config.retry_delay * (config.retry_backoff_factor ** attempt)
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed or error is not retryable
                    error_msg = str(last_error)
                    if not isinstance(last_error, FTPError):
                        last_error = ErrorHandler.handle_ftp_error(last_error, request.url, request.operation)
                        error_msg = str(last_error)

                    return FTPResult(
                        url=request.url,
                        operation=request.operation,
                        status_code=500,
                        local_path=request.local_path,
                        bytes_transferred=0,
                        total_bytes=None,
                        response_time=0.0,
                        timestamp=datetime.now(),
                        error=error_msg,
                        retry_count=attempt
                    )

        # This should never be reached, but just in case
        return FTPResult(
            url=request.url,
            operation=request.operation,
            status_code=500,
            local_path=request.local_path,
            bytes_transferred=0,
            total_bytes=None,
            response_time=0.0,
            timestamp=datetime.now(),
            error="Unexpected error in retry logic",
            retry_count=config.max_retries
        )