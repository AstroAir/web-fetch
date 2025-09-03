"""
File upload handlers for web_fetch.

This module provides comprehensive file upload capabilities including
multipart uploads, progress tracking, and resumable uploads.
"""

import asyncio
import hashlib
import mimetypes
import os
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Union

import aiofiles
import aiohttp
from pydantic import BaseModel, Field

from ..exceptions import WebFetchError
from .connection_pool import OptimizedConnectionPool, ConnectionPoolConfig


class UploadFile(BaseModel):
    """File upload configuration."""

    path: Union[str, Path] = Field(description="File path")
    field_name: str = Field(description="Form field name")
    filename: Optional[str] = Field(default=None, description="Custom filename")
    content_type: Optional[str] = Field(default=None, description="Content type")
    chunk_size: int = Field(default=8192, description="Upload chunk size")


class UploadProgress(BaseModel):
    """Upload progress information."""

    file_path: str
    bytes_uploaded: int = 0
    total_bytes: int = 0
    percentage: float = 0.0
    speed_bps: float = 0.0
    eta_seconds: Optional[float] = None

    @property
    def speed_human(self) -> str:
        """Human-readable upload speed."""
        if self.speed_bps < 1024:
            return f"{self.speed_bps:.1f} B/s"
        elif self.speed_bps < 1024 * 1024:
            return f"{self.speed_bps / 1024:.1f} KB/s"
        else:
            return f"{self.speed_bps / (1024 * 1024):.1f} MB/s"


class FileUploadHandler:
    """Handler for file uploads with optimized connection pooling."""

    def __init__(
        self,
        connection_pool: Optional[OptimizedConnectionPool] = None,
        chunk_size: int = 64 * 1024  # 64KB chunks for memory efficiency
    ) -> None:
        """
        Initialize file upload handler.

        Args:
            connection_pool: Optional connection pool for reuse
            chunk_size: Upload chunk size for streaming
        """
        self._connection_pool = connection_pool
        self._owned_pool = connection_pool is None
        self.chunk_size = chunk_size

    async def _get_connection_pool(self) -> OptimizedConnectionPool:
        """Get or create connection pool."""
        if self._connection_pool is None:
            pool_config = ConnectionPoolConfig(
                total_connections=30,
                connections_per_host=8,
                keepalive_timeout=60,  # Longer keepalive for uploads
                enable_cleanup_closed=True,
            )
            self._connection_pool = OptimizedConnectionPool(pool_config)
        return self._connection_pool

    async def upload_file(
        self,
        session: Optional[aiohttp.ClientSession],
        url: str,
        file_config: UploadFile,
        headers: Optional[Dict[str, str]] = None,
        form_data: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[UploadProgress], None]] = None,
    ) -> aiohttp.ClientResponse:
        """
        Upload a single file with optimized connection pooling.

        Args:
            session: Optional aiohttp session (will create optimized one if None)
            url: Upload URL
            file_config: File upload configuration
            headers: Additional headers
            form_data: Additional form data
            progress_callback: Progress callback function

        Returns:
            HTTP response

        Raises:
            WebFetchError: If upload fails
        """
        # Use optimized connection pool if no session provided
        if session is None:
            pool = await self._get_connection_pool()
            async with pool.get_session() as optimized_session:
                return await self._upload_with_session(
                    optimized_session, url, file_config, headers, form_data, progress_callback
                )
        else:
            return await self._upload_with_session(
                session, url, file_config, headers, form_data, progress_callback
            )

    async def _upload_with_session(
        self,
        session: aiohttp.ClientSession,
        url: str,
        file_config: UploadFile,
        headers: Optional[Dict[str, str]],
        form_data: Optional[Dict[str, Any]],
        progress_callback: Optional[Callable[[UploadProgress], None]],
    ) -> aiohttp.ClientResponse:
        """Core upload logic with memory-efficient streaming."""
        file_path = Path(file_config.path)

        if not file_path.exists():
            raise WebFetchError(f"File not found: {file_path}")

        if not file_path.is_file():
            raise WebFetchError(f"Path is not a file: {file_path}")

        # Get file info
        file_size = file_path.stat().st_size
        filename = file_config.filename or file_path.name
        content_type = (
            file_config.content_type
            or mimetypes.guess_type(str(file_path))[0]
            or "application/octet-stream"
        )

        # Create progress tracker
        progress = UploadProgress(file_path=str(file_path), total_bytes=file_size)

        # Create form data
        form = aiohttp.FormData()

        # Add additional form fields
        if form_data:
            for key, value in form_data.items():
                form.add_field(key, str(value))

        # Memory-efficient file streaming
        async def file_sender() -> AsyncGenerator[bytes, None]:
            """Generator for streaming file upload with progress tracking."""
            bytes_uploaded = 0
            async with aiofiles.open(file_path, "rb") as f:
                while True:
                    chunk = await f.read(self.chunk_size)
                    if not chunk:
                        break

                    bytes_uploaded += len(chunk)

                    # Update progress
                    if progress_callback:
                        progress.bytes_uploaded = bytes_uploaded
                        progress.percentage = (bytes_uploaded / file_size * 100) if file_size > 0 else 0
                        progress_callback(progress)

                    yield chunk

        # Add file with streaming
        form.add_field(
            file_config.field_name,
            file_sender(),
            filename=filename,
            content_type=content_type,
        )

        # Upload with progress tracking
        if progress_callback:
            progress_callback(progress)

        try:
            response = await session.post(url, data=form, headers=headers)

            # Final progress update
            progress.bytes_uploaded = file_size
            progress.percentage = 100.0
            if progress_callback:
                progress_callback(progress)

            return response

        except Exception as e:
            raise WebFetchError(f"Upload failed: {e}")

    async def close(self) -> None:
        """Close connection pool if owned by this handler."""
        if self._owned_pool and self._connection_pool:
            await self._connection_pool.close()
            self._connection_pool = None

    async def __aenter__(self) -> 'FileUploadHandler':
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def upload_multiple_files(
        self,
        session: aiohttp.ClientSession,
        url: str,
        files: List[UploadFile],
        headers: Optional[Dict[str, str]] = None,
        form_data: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[str, UploadProgress], None]] = None,
    ) -> aiohttp.ClientResponse:
        """
        Upload multiple files in a single request.

        Args:
            session: aiohttp session
            url: Upload URL
            files: List of file configurations
            headers: Additional headers
            form_data: Additional form data
            progress_callback: Progress callback function

        Returns:
            HTTP response
        """
        form = aiohttp.FormData()

        # Add additional form fields
        if form_data:
            for key, value in form_data.items():
                form.add_field(key, str(value))

        # Add files
        total_size = 0
        for file_config in files:
            file_path = Path(file_config.path)

            if not file_path.exists():
                raise WebFetchError(f"File not found: {file_path}")

            total_size += file_path.stat().st_size
            filename = file_config.filename or file_path.name
            content_type = (
                file_config.content_type
                or mimetypes.guess_type(str(file_path))[0]
                or "application/octet-stream"
            )

            async with aiofiles.open(file_path, "rb") as f:
                file_content = await f.read()

            form.add_field(
                file_config.field_name,
                file_content,
                filename=filename,
                content_type=content_type,
            )

        return await session.post(url, data=form, headers=headers)


class MultipartUploadHandler:
    """Handler for multipart uploads (large files)."""

    def __init__(self, chunk_size: int = 5 * 1024 * 1024):  # 5MB chunks
        """
        Initialize multipart upload handler.

        Args:
            chunk_size: Size of each upload chunk
        """
        self.chunk_size = chunk_size

    async def upload_file_multipart(
        self,
        session: aiohttp.ClientSession,
        url: str,
        file_path: Union[str, Path],
        headers: Optional[Dict[str, str]] = None,
        progress_callback: Optional[Callable[[UploadProgress], None]] = None,
    ) -> List[aiohttp.ClientResponse]:
        """
        Upload file using multipart upload.

        Args:
            session: aiohttp session
            url: Upload URL
            file_path: Path to file
            headers: Additional headers
            progress_callback: Progress callback function

        Returns:
            List of responses for each chunk
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise WebFetchError(f"File not found: {file_path}")

        file_size = file_path.stat().st_size
        num_chunks = (file_size + self.chunk_size - 1) // self.chunk_size

        progress = UploadProgress(file_path=str(file_path), total_bytes=file_size)

        responses = []

        async with aiofiles.open(file_path, "rb") as f:
            for chunk_index in range(num_chunks):
                # Read chunk
                chunk_data = await f.read(self.chunk_size)

                # Prepare chunk headers
                chunk_headers = headers.copy() if headers else {}
                chunk_headers.update(
                    {
                        "Content-Range": f"bytes {chunk_index * self.chunk_size}-{chunk_index * self.chunk_size + len(chunk_data) - 1}/{file_size}",
                        "Content-Length": str(len(chunk_data)),
                        "X-Chunk-Index": str(chunk_index),
                        "X-Total-Chunks": str(num_chunks),
                    }
                )

                # Upload chunk
                response = await session.put(
                    f"{url}?chunk={chunk_index}", data=chunk_data, headers=chunk_headers
                )

                responses.append(response)

                # Update progress
                progress.bytes_uploaded = min(
                    (chunk_index + 1) * self.chunk_size, file_size
                )
                progress.percentage = (progress.bytes_uploaded / file_size) * 100

                if progress_callback:
                    progress_callback(progress)

        return responses

    async def upload_with_resume(
        self,
        session: aiohttp.ClientSession,
        url: str,
        file_path: Union[str, Path],
        upload_id: str,
        headers: Optional[Dict[str, str]] = None,
        progress_callback: Optional[Callable[[UploadProgress], None]] = None,
    ) -> aiohttp.ClientResponse:
        """
        Upload file with resume capability.

        Args:
            session: aiohttp session
            url: Upload URL
            file_path: Path to file
            upload_id: Unique upload identifier
            headers: Additional headers
            progress_callback: Progress callback function

        Returns:
            HTTP response
        """
        file_path = Path(file_path)
        file_size = file_path.stat().st_size

        # Check upload status
        status_response = await session.head(f"{url}?upload_id={upload_id}")

        # Get uploaded bytes from response headers
        uploaded_bytes = 0
        if "X-Uploaded-Bytes" in status_response.headers:
            uploaded_bytes = int(status_response.headers["X-Uploaded-Bytes"])

        if uploaded_bytes >= file_size:
            # Already uploaded
            return status_response

        # Resume upload from where it left off
        progress = UploadProgress(
            file_path=str(file_path),
            total_bytes=file_size,
            bytes_uploaded=uploaded_bytes,
        )

        async with aiofiles.open(file_path, "rb") as f:
            await f.seek(uploaded_bytes)
            remaining_data = await f.read()

        # Upload remaining data
        upload_headers = headers.copy() if headers else {}
        upload_headers.update(
            {
                "Content-Range": f"bytes {uploaded_bytes}-{file_size - 1}/{file_size}",
                "X-Upload-ID": upload_id,
            }
        )

        response = await session.put(url, data=remaining_data, headers=upload_headers)

        # Final progress update
        progress.bytes_uploaded = file_size
        progress.percentage = 100.0
        if progress_callback:
            progress_callback(progress)

        return response
