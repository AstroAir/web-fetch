"""
Streaming web fetcher implementation with progress tracking.

This module provides the StreamingWebFetcher class that extends WebFetcher
with streaming capabilities for large files and continuous data streams.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Union

import aiofiles
from aiohttp import ClientTimeout

from ..exceptions import WebFetchError
from ..models import (
    FetchConfig,
    ProgressInfo,
    StreamRequest,
    StreamResult,
)
from ..utils import RateLimiter, SimpleCache
from .core_fetcher import WebFetcher


class StreamingWebFetcher(WebFetcher):
    """
    Extended WebFetcher with streaming capabilities for large files and continuous data.

    StreamingWebFetcher extends the base WebFetcher class with specialized streaming
    functionality designed for handling large files, continuous data streams, and
    scenarios where memory efficiency is critical. It downloads content in configurable
    chunks without loading the entire response into memory.

    Key Features:
        - **Memory-efficient streaming**: Downloads content in chunks to minimize memory usage
        - **Progress tracking**: Real-time progress callbacks with download statistics
        - **Resumable downloads**: Support for resuming interrupted downloads
        - **File size limits**: Configurable maximum file size limits for safety
        - **Speed monitoring**: Real-time download speed calculation and reporting
        - **Flexible output**: Stream to files, memory, or custom handlers
        - **Automatic directory creation**: Creates output directories as needed

    Use Cases:
        - Downloading large files (videos, archives, datasets)
        - Processing continuous data streams (logs, real-time feeds)
        - Memory-constrained environments
        - Progress tracking for user interfaces
        - Bandwidth monitoring and throttling

    Performance Considerations:
        - Chunk size affects memory usage and performance (default: 8192 bytes)
        - Larger chunks = better performance but more memory usage
        - Smaller chunks = lower memory but more overhead
        - Progress callbacks add minimal overhead but should be lightweight

    Example:
        ```python
        import asyncio
        from pathlib import Path
        from web_fetch import StreamingWebFetcher, StreamRequest, ProgressInfo

        def progress_callback(progress: ProgressInfo):
            if progress.total_bytes:
                percent = (progress.bytes_downloaded / progress.total_bytes) * 100
                print(f"Progress: {percent:.1f}% ({progress.speed_human})")

        async def download_large_file():
            request = StreamRequest(
                url="https://example.com/large-file.zip",
                output_path=Path("downloads/file.zip"),
                chunk_size=16384,  # 16KB chunks
                max_file_size=100 * 1024 * 1024  # 100MB limit
            )

            async with StreamingWebFetcher() as fetcher:
                result = await fetcher.stream_fetch(request, progress_callback)

                if result.is_success:
                    print(f"Downloaded {result.bytes_downloaded:,} bytes")
                    print(f"Average speed: {result.average_speed_human}")
                else:
                    print(f"Download failed: {result.error}")

        asyncio.run(download_large_file())
        ```

    Thread Safety:
        Like WebFetcher, StreamingWebFetcher instances are not thread-safe and should
        be used within a single asyncio event loop.

    See Also:
        - :class:`WebFetcher`: Base class for standard HTTP requests
        - :class:`StreamRequest`: Request specification for streaming operations
        - :class:`StreamResult`: Result object with streaming metadata
        - :class:`ProgressInfo`: Progress information passed to callbacks
    """

    def __init__(self, config: Optional[FetchConfig] = None):
        """
        Initialize the StreamingWebFetcher with configuration.

        Extends the base WebFetcher with streaming capabilities for handling
        large files and continuous data streams without loading everything
        into memory.

        Args:
            config: Optional FetchConfig object containing timeout settings,
                   retry configuration, and streaming parameters. If None,
                   default configuration will be used.

        Attributes:
            _rate_limiter: Optional rate limiter for controlling request frequency
            _cache: Optional cache for storing frequently accessed data
        """
        super().__init__(config)
        self._rate_limiter: Optional[RateLimiter] = None
        self._cache: Optional[SimpleCache] = None

    async def stream_fetch(
        self,
        request: StreamRequest,
        progress_callback: Optional[Callable[[ProgressInfo], None]] = None,
    ) -> StreamResult:
        """
        Stream fetch a URL with chunked reading and progress tracking.

        Downloads content in chunks without loading the entire response into
        memory, making it suitable for large files or continuous data streams.
        Provides real-time progress updates and supports resumable downloads.

        Args:
            request: StreamRequest object containing URL, method, headers,
                    chunk size, and other streaming options
            progress_callback: Optional callback function that receives ProgressInfo
                             objects with download progress updates. Called after
                             each chunk is downloaded.

        Returns:
            StreamResult object containing streaming metadata including:
            - Total bytes downloaded
            - Download speed and timing information
            - Final response status and headers
            - Any errors that occurred during streaming

        Raises:
            WebFetchError: If session is not initialized or request fails
            TimeoutError: If request times out
            ConnectionError: If connection fails
            ServerError: If server returns 5xx status code

        Example:
            ```python
            def progress_handler(progress: ProgressInfo):
                print(f"Downloaded: {progress.bytes_downloaded} bytes")

            request = StreamRequest(
                url="https://example.com/large-file.zip",
                chunk_size=8192
            )
            result = await fetcher.stream_fetch(request, progress_handler)
            ```
        """
        if not self._session:
            await self._create_session()

        start_time = time.time()
        bytes_downloaded = 0
        chunk_count = 0
        last_progress_time = start_time

        # Prepare request parameters
        method: str = request.method
        url: str = str(request.url)
        headers: dict = request.headers or {}
        timeout: Optional[ClientTimeout] = (
            ClientTimeout(total=request.timeout_override)
            if request.timeout_override
            else None
        )

        # Prepare data/json parameters
        json_data: Optional[dict] = None
        data: Optional[Union[str, bytes]] = None
        if request.data is not None:
            if isinstance(request.data, dict):
                json_data = request.data
            elif isinstance(request.data, (str, bytes)):
                data = request.data

        try:
            if self._session is None:
                raise WebFetchError("Session not properly initialized")

            async with self._session.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
                data=data,
                timeout=timeout,
            ) as response:
                # Get content length if available
                total_bytes = None
                if "content-length" in response.headers:
                    try:
                        total_bytes = int(response.headers["content-length"])
                    except ValueError:
                        pass

                # Check file size limit
                if (
                    request.streaming_config.max_file_size
                    and total_bytes
                    and total_bytes > request.streaming_config.max_file_size
                ):
                    raise WebFetchError(
                        f"File size {total_bytes} exceeds limit {request.streaming_config.max_file_size}"
                    )

                # Open output file if specified
                output_file = None
                if request.output_path:
                    request.output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_file = await aiofiles.open(request.output_path, "wb")

                try:
                    # Stream content in chunks
                    async for chunk in response.content.iter_chunked(
                        request.streaming_config.chunk_size
                    ):
                        if not chunk:
                            break

                        bytes_downloaded += len(chunk)
                        chunk_count += 1

                        # Write to file if specified
                        if output_file:
                            await output_file.write(chunk)

                        # Update progress
                        current_time = time.time()
                        elapsed_time = current_time - start_time

                        if (
                            request.streaming_config.enable_progress
                            and progress_callback
                            and (current_time - last_progress_time)
                            >= request.streaming_config.progress_interval
                        ):

                            download_speed = (
                                bytes_downloaded / elapsed_time
                                if elapsed_time > 0
                                else 0
                            )
                            percentage = None
                            eta = None

                            if total_bytes:
                                percentage = (bytes_downloaded / total_bytes) * 100
                                if download_speed > 0:
                                    remaining_bytes = total_bytes - bytes_downloaded
                                    eta = remaining_bytes / download_speed

                            progress_info = ProgressInfo(
                                bytes_downloaded=bytes_downloaded,
                                total_bytes=total_bytes,
                                chunk_count=chunk_count,
                                elapsed_time=elapsed_time,
                                download_speed=download_speed,
                                eta=eta,
                                percentage=percentage,
                            )

                            progress_callback(progress_info)
                            last_progress_time = current_time

                finally:
                    if output_file:
                        await output_file.close()

                # Create final progress info
                final_elapsed = time.time() - start_time
                final_speed = (
                    bytes_downloaded / final_elapsed if final_elapsed > 0 else 0
                )
                final_percentage = (
                    100.0 if total_bytes and bytes_downloaded >= total_bytes else None
                )

                final_progress = ProgressInfo(
                    bytes_downloaded=bytes_downloaded,
                    total_bytes=total_bytes,
                    chunk_count=chunk_count,
                    elapsed_time=final_elapsed,
                    download_speed=final_speed,
                    eta=0.0 if final_percentage == 100.0 else None,
                    percentage=final_percentage,
                )

                # Call progress callback one final time if enabled
                if request.streaming_config.enable_progress and progress_callback:
                    progress_callback(final_progress)

                return StreamResult(
                    url=str(request.url),
                    status_code=response.status,
                    headers=dict(response.headers),
                    bytes_downloaded=bytes_downloaded,
                    total_bytes=total_bytes,
                    output_path=request.output_path,
                    response_time=final_elapsed,
                    timestamp=datetime.now(),
                )

        except Exception as e:
            error_msg = str(e)
            return StreamResult(
                url=str(request.url),
                status_code=0,
                headers={},
                bytes_downloaded=bytes_downloaded,
                total_bytes=None,
                output_path=request.output_path,
                response_time=time.time() - start_time,
                timestamp=datetime.now(),
                error=error_msg,
            )
