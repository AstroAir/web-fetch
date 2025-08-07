"""
Enhanced download handlers for web_fetch.

This module provides comprehensive download capabilities including
resumable downloads, progress tracking, and integrity verification.
"""

import asyncio
import hashlib
import time
from pathlib import Path
from typing import Callable, Optional, Union

import aiofiles
import aiohttp
from pydantic import BaseModel, Field

from ..exceptions import WebFetchError
from ..models import ProgressInfo


class DownloadConfig(BaseModel):
    """Download configuration."""
    
    chunk_size: int = Field(default=8192, description="Download chunk size")
    max_file_size: Optional[int] = Field(default=None, description="Maximum file size")
    verify_checksum: bool = Field(default=False, description="Verify file checksum")
    expected_checksum: Optional[str] = Field(default=None, description="Expected file checksum")
    checksum_algorithm: str = Field(default="sha256", description="Checksum algorithm")
    overwrite_existing: bool = Field(default=False, description="Overwrite existing files")
    create_directories: bool = Field(default=True, description="Create parent directories")
    temp_suffix: str = Field(default=".tmp", description="Temporary file suffix")


class DownloadResult(BaseModel):
    """Download result information."""
    
    success: bool = Field(description="Whether download succeeded")
    file_path: Path = Field(description="Downloaded file path")
    bytes_downloaded: int = Field(default=0, description="Bytes downloaded")
    total_bytes: Optional[int] = Field(default=None, description="Total file size")
    download_time: float = Field(default=0.0, description="Download time in seconds")
    average_speed: float = Field(default=0.0, description="Average download speed")
    checksum: Optional[str] = Field(default=None, description="File checksum")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    
    @property
    def speed_human(self) -> str:
        """Human-readable download speed."""
        if self.average_speed < 1024:
            return f"{self.average_speed:.1f} B/s"
        elif self.average_speed < 1024 * 1024:
            return f"{self.average_speed / 1024:.1f} KB/s"
        else:
            return f"{self.average_speed / (1024 * 1024):.1f} MB/s"


class DownloadHandler:
    """Handler for file downloads."""
    
    def __init__(self, config: Optional[DownloadConfig] = None):
        """
        Initialize download handler.
        
        Args:
            config: Download configuration
        """
        self.config = config or DownloadConfig()
    
    async def download_file(
        self,
        session: aiohttp.ClientSession,
        url: str,
        output_path: Union[str, Path],
        headers: Optional[dict] = None,
        progress_callback: Optional[Callable[[ProgressInfo], None]] = None
    ) -> DownloadResult:
        """
        Download a file from URL.
        
        Args:
            session: aiohttp session
            url: Download URL
            output_path: Output file path
            headers: Request headers
            progress_callback: Progress callback function
            
        Returns:
            Download result
        """
        output_path = Path(output_path)
        temp_path = output_path.with_suffix(output_path.suffix + self.config.temp_suffix)
        
        # Check if file exists
        if output_path.exists() and not self.config.overwrite_existing:
            return DownloadResult(
                success=False,
                file_path=output_path,
                error="File already exists and overwrite is disabled"
            )
        
        # Create parent directories
        if self.config.create_directories:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        
        start_time = time.time()
        bytes_downloaded = 0
        total_bytes = None
        hasher = hashlib.new(self.config.checksum_algorithm) if self.config.verify_checksum else None
        
        try:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                
                # Get content length
                content_length = response.headers.get('content-length')
                if content_length:
                    total_bytes = int(content_length)
                    
                    # Check file size limit
                    if self.config.max_file_size and total_bytes > self.config.max_file_size:
                        return DownloadResult(
                            success=False,
                            file_path=output_path,
                            error=f"File size {total_bytes} exceeds limit {self.config.max_file_size}"
                        )
                
                # Download file
                async with aiofiles.open(temp_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(self.config.chunk_size):
                        await f.write(chunk)
                        bytes_downloaded += len(chunk)
                        
                        # Update checksum
                        if hasher:
                            hasher.update(chunk)
                        
                        # Check size limit
                        if self.config.max_file_size and bytes_downloaded > self.config.max_file_size:
                            temp_path.unlink(missing_ok=True)
                            return DownloadResult(
                                success=False,
                                file_path=output_path,
                                error=f"Downloaded size {bytes_downloaded} exceeds limit {self.config.max_file_size}"
                            )
                        
                        # Progress callback
                        if progress_callback:
                            progress = ProgressInfo(
                                bytes_downloaded=bytes_downloaded,
                                total_bytes=total_bytes,
                                percentage=(bytes_downloaded / total_bytes * 100) if total_bytes else None,
                                speed_bps=bytes_downloaded / (time.time() - start_time)
                            )
                            progress_callback(progress)
            
            # Verify checksum
            if self.config.verify_checksum and self.config.expected_checksum:
                calculated_checksum = hasher.hexdigest()
                if calculated_checksum != self.config.expected_checksum:
                    temp_path.unlink(missing_ok=True)
                    return DownloadResult(
                        success=False,
                        file_path=output_path,
                        error=f"Checksum mismatch: expected {self.config.expected_checksum}, got {calculated_checksum}"
                    )
            
            # Move temp file to final location
            temp_path.rename(output_path)
            
            # Calculate metrics
            download_time = time.time() - start_time
            average_speed = bytes_downloaded / download_time if download_time > 0 else 0
            
            return DownloadResult(
                success=True,
                file_path=output_path,
                bytes_downloaded=bytes_downloaded,
                total_bytes=total_bytes,
                download_time=download_time,
                average_speed=average_speed,
                checksum=hasher.hexdigest() if hasher else None
            )
        
        except Exception as e:
            # Clean up temp file
            temp_path.unlink(missing_ok=True)
            
            return DownloadResult(
                success=False,
                file_path=output_path,
                bytes_downloaded=bytes_downloaded,
                error=str(e)
            )


class ResumableDownloadHandler(DownloadHandler):
    """Handler for resumable downloads."""
    
    async def download_file_resumable(
        self,
        session: aiohttp.ClientSession,
        url: str,
        output_path: Union[str, Path],
        headers: Optional[dict] = None,
        progress_callback: Optional[Callable[[ProgressInfo], None]] = None
    ) -> DownloadResult:
        """
        Download file with resume capability.
        
        Args:
            session: aiohttp session
            url: Download URL
            output_path: Output file path
            headers: Request headers
            progress_callback: Progress callback function
            
        Returns:
            Download result
        """
        output_path = Path(output_path)
        
        # Check if partial file exists
        existing_size = 0
        if output_path.exists():
            existing_size = output_path.stat().st_size
        
        # Prepare headers for range request
        request_headers = dict(headers or {})
        if existing_size > 0:
            request_headers['Range'] = f'bytes={existing_size}-'
        
        start_time = time.time()
        bytes_downloaded = existing_size
        total_bytes = None
        hasher = None
        
        # If resuming, we need to recalculate checksum from existing data
        if self.config.verify_checksum and existing_size > 0:
            hasher = hashlib.new(self.config.checksum_algorithm)
            async with aiofiles.open(output_path, 'rb') as f:
                while True:
                    chunk = await f.read(self.config.chunk_size)
                    if not chunk:
                        break
                    hasher.update(chunk)
        elif self.config.verify_checksum:
            hasher = hashlib.new(self.config.checksum_algorithm)
        
        try:
            async with session.get(url, headers=request_headers) as response:
                # Handle different response codes
                if response.status == 206:  # Partial content
                    # Parse content range
                    content_range = response.headers.get('content-range')
                    if content_range:
                        # Format: bytes start-end/total
                        parts = content_range.split('/')
                        if len(parts) == 2:
                            total_bytes = int(parts[1])
                elif response.status == 200:  # Full content
                    # Server doesn't support range requests, start over
                    existing_size = 0
                    bytes_downloaded = 0
                    if hasher:
                        hasher = hashlib.new(self.config.checksum_algorithm)
                    
                    content_length = response.headers.get('content-length')
                    if content_length:
                        total_bytes = int(content_length)
                else:
                    response.raise_for_status()
                
                # Open file for writing (append if resuming)
                mode = 'ab' if existing_size > 0 and response.status == 206 else 'wb'
                
                async with aiofiles.open(output_path, mode) as f:
                    async for chunk in response.content.iter_chunked(self.config.chunk_size):
                        await f.write(chunk)
                        bytes_downloaded += len(chunk)
                        
                        # Update checksum
                        if hasher:
                            hasher.update(chunk)
                        
                        # Check size limit
                        if self.config.max_file_size and bytes_downloaded > self.config.max_file_size:
                            return DownloadResult(
                                success=False,
                                file_path=output_path,
                                error=f"Downloaded size {bytes_downloaded} exceeds limit {self.config.max_file_size}"
                            )
                        
                        # Progress callback
                        if progress_callback:
                            progress = ProgressInfo(
                                bytes_downloaded=bytes_downloaded,
                                total_bytes=total_bytes,
                                percentage=(bytes_downloaded / total_bytes * 100) if total_bytes else None,
                                speed_bps=(bytes_downloaded - existing_size) / (time.time() - start_time)
                            )
                            progress_callback(progress)
            
            # Verify checksum
            if self.config.verify_checksum and self.config.expected_checksum:
                calculated_checksum = hasher.hexdigest()
                if calculated_checksum != self.config.expected_checksum:
                    return DownloadResult(
                        success=False,
                        file_path=output_path,
                        error=f"Checksum mismatch: expected {self.config.expected_checksum}, got {calculated_checksum}"
                    )
            
            # Calculate metrics
            download_time = time.time() - start_time
            new_bytes = bytes_downloaded - existing_size
            average_speed = new_bytes / download_time if download_time > 0 else 0
            
            return DownloadResult(
                success=True,
                file_path=output_path,
                bytes_downloaded=bytes_downloaded,
                total_bytes=total_bytes,
                download_time=download_time,
                average_speed=average_speed,
                checksum=hasher.hexdigest() if hasher else None
            )
        
        except Exception as e:
            return DownloadResult(
                success=False,
                file_path=output_path,
                bytes_downloaded=bytes_downloaded,
                error=str(e)
            )
    
    async def get_download_info(
        self,
        session: aiohttp.ClientSession,
        url: str,
        headers: Optional[dict] = None
    ) -> dict:
        """
        Get download information without downloading.
        
        Args:
            session: aiohttp session
            url: Download URL
            headers: Request headers
            
        Returns:
            Download information
        """
        try:
            async with session.head(url, headers=headers) as response:
                response.raise_for_status()
                
                info = {
                    'supports_range': 'accept-ranges' in response.headers,
                    'content_length': None,
                    'content_type': response.headers.get('content-type'),
                    'last_modified': response.headers.get('last-modified'),
                    'etag': response.headers.get('etag'),
                }
                
                content_length = response.headers.get('content-length')
                if content_length:
                    info['content_length'] = int(content_length)
                
                return info
        
        except Exception as e:
            return {'error': str(e)}
