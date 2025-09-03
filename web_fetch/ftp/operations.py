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
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

import aiofiles
import aioftp

from ..exceptions import (
    ErrorHandler,
    FTPError,
    FTPFileNotFoundError,
    FTPVerificationError,
)
from .connection import FTPConnectionPool
from .models import (
    FTPConfig,
    FTPFileInfo,
    FTPProgressInfo,
    FTPResult,
    FTPTransferMode,
    FTPVerificationMethod,
    FTPVerificationResult,
)
from .metrics import get_metrics_collector
from .profiler import get_profiler
from .circuit_breaker import get_circuit_breaker, CircuitBreakerError
from .retry import get_retry_manager, RetryableError


# Helper types matching aioftp list/stat structures
PathWithInfo = Tuple[Any, Any]  # (PurePosixPath, BasicListInfo | UnixListInfo)


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        if isinstance(value, (int,)):
            return value
        if isinstance(value, (float,)):
            # only accept if integral
            iv = int(value)
            return iv
        if isinstance(value, str) and value.strip() != "":
            return int(value)
    except Exception:
        return None
    return None


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str) and value.strip() != "":
            return float(value)
    except Exception:
        return None
    return None


def _to_datetime_from_epoch(epoch: Optional[float]) -> Optional[datetime]:
    if epoch is None:
        return None
    try:
        return datetime.fromtimestamp(float(epoch))
    except Exception:
        return None


def _permissions_octal(mode: Optional[int]) -> Optional[str]:
    if mode is None:
        return None
    try:
        return oct(int(mode))
    except Exception:
        return None


def _normalize_stat_like(obj: Any) -> Dict[str, Any]:
    """
    Convert aioftp stat/list info object or dict to a normalized dict.
    Known fields: name, size, st_mtime, st_mode, type (dir/file), is_dir.
    """
    result: Dict[str, Any] = {}

    # If dict-like
    if isinstance(obj, dict):
        result.update(obj)
        # normalize typical aliases
        size = _safe_int(result.get("size"))
        mtime = _safe_float(result.get("st_mtime") if "st_mtime" in result else result.get("mtime"))
        mode = _safe_int(result.get("st_mode") if "st_mode" in result else result.get("mode"))
        # derive is_dir if given explicitly or from type
        is_dir = result.get("is_dir")
        if callable(is_dir):
            try:
                is_dir = bool(is_dir())
            except Exception:
                is_dir = None
        if is_dir is None:
            type_val = result.get("type")
            is_dir = True if type_val in ("dir", "directory") else False if type_val in ("file",) else None

        if size is not None:
            result["size"] = size
        if mtime is not None:
            result["st_mtime"] = mtime
        if mode is not None:
            result["st_mode"] = mode
        if is_dir is not None:
            result["is_dir"] = bool(is_dir)
        return result

    # Object with attributes
    # Try common attributes on aioftp BasicListInfo / UnixListInfo
    name = getattr(obj, "name", None)
    size = getattr(obj, "size", None)
    st_mtime = getattr(obj, "st_mtime", None)
    st_mode = getattr(obj, "st_mode", None)
    type_val = getattr(obj, "type", None)
    is_dir_attr = getattr(obj, "is_dir", None)

    result["name"] = name
    size = _safe_int(size)
    if size is not None:
        result["size"] = size

    mtime = _safe_float(st_mtime)
    if mtime is not None:
        result["st_mtime"] = mtime

    mode = _safe_int(st_mode)
    if mode is not None:
        result["st_mode"] = mode

    if callable(is_dir_attr):
        try:
            result["is_dir"] = bool(is_dir_attr())
        except Exception:
            pass
    elif isinstance(is_dir_attr, bool):
        result["is_dir"] = is_dir_attr
    elif type_val in ("dir", "directory"):
        result["is_dir"] = True
    elif type_val in ("file",):
        result["is_dir"] = False

    return result


def _from_path_with_info(pwi: PathWithInfo) -> Dict[str, Any]:
    """
    Extract normalized info from (path, info) tuple yielded by aioftp.Client.list().
    """
    path_obj, info_obj = pwi  # path_obj: PurePosixPath, info_obj: BasicListInfo|UnixListInfo
    info = _normalize_stat_like(info_obj)
    # name and path
    try:
        # Prefer info-provided name, else derive from path
        name = info.get("name")
        if not name and hasattr(path_obj, "name"):
            name = path_obj.name
        info["name"] = name
    except Exception:
        pass

    info["path"] = str(path_obj) if path_obj is not None else info.get("path")

    return info


class FTPFileOperations:
    """
    FTP file operations handler with support for listing, downloading,
    and directory traversal.
    """

    def __init__(self, config: FTPConfig):
        """Initialize FTP operations with configuration."""
        self.config = config
        self.connection_pool = FTPConnectionPool(config)
        self._metrics = get_metrics_collector() if config.performance_monitoring else None
        self._profiler = get_profiler() if config.performance_monitoring else None
        self._circuit_breaker = get_circuit_breaker() if config.performance_monitoring else None
        self._retry_manager = get_retry_manager() if config.performance_monitoring else None
        self._adaptive_chunk_sizes: Dict[str, int] = {}  # Track optimal chunk sizes per host

    async def close(self) -> None:
        """Close the operations handler and cleanup resources."""
        await self.connection_pool.close_all()

    def _get_adaptive_chunk_size(self, host: str, current_rate: float = 0.0) -> int:
        """
        Get adaptive chunk size based on transfer performance.

        Args:
            host: Target host for the transfer
            current_rate: Current transfer rate in bytes/second

        Returns:
            Optimal chunk size for the host
        """
        if not self.config.adaptive_chunk_size:
            return self.config.chunk_size

        # Get current chunk size for this host
        current_chunk = self._adaptive_chunk_sizes.get(host, self.config.chunk_size)

        # If we have performance data, adjust chunk size
        if current_rate > 0:
            # Target: 1MB/s or higher should use larger chunks
            # Lower speeds should use smaller chunks to reduce memory usage
            if current_rate > 1024 * 1024:  # > 1MB/s
                # Increase chunk size for high-speed connections
                new_chunk = min(current_chunk * 1.2, self.config.max_chunk_size)
            elif current_rate < 100 * 1024:  # < 100KB/s
                # Decrease chunk size for slow connections
                new_chunk = max(current_chunk * 0.8, self.config.min_chunk_size)
            else:
                # Keep current chunk size for moderate speeds
                new_chunk = current_chunk

            self._adaptive_chunk_sizes[host] = int(new_chunk)
            return int(new_chunk)

        return current_chunk

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
                path = parsed.path or "/"

                # Change to the directory
                if path != "/":
                    await client.change_directory(path)

                # List directory contents
                files: List[FTPFileInfo] = []
                async for pwi in client.list():  # yields (path, info)
                    info = _from_path_with_info(pwi)

                    file_info = FTPFileInfo(
                        name=str(info.get("name") or ""),
                        path=str(info.get("path") or ""),
                        size=_safe_int(info.get("size")),
                        modified_time=_to_datetime_from_epoch(_safe_float(info.get("st_mtime"))),
                        is_directory=bool(info.get("is_dir") or False),
                        permissions=_permissions_octal(_safe_int(info.get("st_mode"))),
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
                path = parsed.path or "/"

                # Get file/directory info
                try:
                    stat_raw = await client.stat(path)
                    stat_info = _normalize_stat_like(stat_raw)

                    file_info = FTPFileInfo(
                        name=os.path.basename(path),
                        path=path,
                        size=_safe_int(stat_info.get("size")),
                        modified_time=_to_datetime_from_epoch(_safe_float(stat_info.get("st_mtime"))),
                        is_directory=bool(stat_info.get("is_dir") or False),
                        permissions=_permissions_octal(_safe_int(stat_info.get("st_mode"))),
                    )

                    return file_info

                except Exception:
                    # If stat fails, try to list parent directory
                    parent_path = os.path.dirname(path)
                    filename = os.path.basename(path)

                    if parent_path != path:
                        await client.change_directory(parent_path)
                        async for pwi in client.list():
                            info = _from_path_with_info(pwi)
                            if str(info.get("name") or "") == filename:
                                return FTPFileInfo(
                                    name=str(info.get("name") or ""),
                                    path=path,
                                    size=_safe_int(info.get("size")),
                                    modified_time=_to_datetime_from_epoch(_safe_float(info.get("st_mtime"))),
                                    is_directory=bool(info.get("is_dir") or False),
                                    permissions=_permissions_octal(_safe_int(info.get("st_mode"))),
                                )

                    raise FTPFileNotFoundError(f"File not found: {path}", url)

        except Exception as e:
            if isinstance(e, FTPFileNotFoundError):
                raise
            raise ErrorHandler.handle_ftp_error(e, url, "get_file_info")

    async def download_file(
        self, url: str, local_path: Path, progress_callback: Optional[Callable] = None
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

        # Initialize metrics tracking
        transfer_id = f"download_{int(start_time * 1000)}_{hash(url) % 10000}"
        if self._metrics:
            self._metrics.start_transfer(transfer_id, url, "download", self.config.chunk_size)

        # Get host for adaptive chunk sizing
        parsed = urlparse(url)
        host = parsed.hostname or "localhost"

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
                        file_info=file_info,
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

                    # Download file with adaptive chunk sizing
                    async with client.download_stream(remote_path) as stream:
                        last_progress_time = time.time()
                        last_rate_calculation = time.time()
                        current_chunk_size = self._get_adaptive_chunk_size(host)

                        async for chunk in stream.iter_by_block(current_chunk_size):
                            await local_file.write(chunk)
                            bytes_transferred += len(chunk)

                            # Update metrics
                            if self._metrics:
                                self._metrics.update_transfer(transfer_id, bytes_transferred + resume_position, total_bytes)

                            # Calculate current transfer rate and adapt chunk size
                            current_time = time.time()
                            if current_time - last_rate_calculation >= 1.0:  # Recalculate every second
                                current_rate = bytes_transferred / (current_time - start_time) if current_time > start_time else 0
                                if self.config.adaptive_chunk_size:
                                    new_chunk_size = self._get_adaptive_chunk_size(host, current_rate)
                                    if new_chunk_size != current_chunk_size:
                                        current_chunk_size = new_chunk_size
                                last_rate_calculation = current_time

                            # Progress callback
                            if (
                                progress_callback
                                and current_time - last_progress_time >= 0.1
                            ):
                                current_rate = bytes_transferred / (current_time - start_time) if current_time > start_time else 0
                                progress_info = FTPProgressInfo(
                                    bytes_transferred=bytes_transferred + resume_position,
                                    total_bytes=total_bytes,
                                    transfer_rate=current_rate,
                                    elapsed_time=current_time - start_time,
                                    estimated_time_remaining=None,
                                    current_file=str(local_path),
                                )
                                await progress_callback(progress_info)
                                last_progress_time = current_time

                            # Rate limiting
                            if self.config.rate_limit_bytes_per_second:
                                expected_time = (
                                    bytes_transferred
                                    / self.config.rate_limit_bytes_per_second
                                )
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
                        actual_value=verification_result.actual_value,
                    )

            # Mark transfer as successful in metrics
            if self._metrics:
                self._metrics.complete_transfer(transfer_id, success=True)

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
                verification_result=(
                    verification_result.verification_details
                    if verification_result
                    else None
                ),
            )

        except Exception as e:
            error = str(e)
            if not isinstance(e, (FTPError, FTPVerificationError)):
                e = ErrorHandler.handle_ftp_error(e, url, "download_file")

            # Mark transfer as failed in metrics
            if self._metrics:
                self._metrics.complete_transfer(transfer_id, success=False, error=error)

            return FTPResult(
                url=url,
                operation="download",
                status_code=500,
                local_path=local_path,
                bytes_transferred=bytes_transferred,
                total_bytes=total_bytes,
                response_time=time.time() - start_time,
                timestamp=datetime.now(),
                error=error,
            )

    async def _verify_file(
        self, local_path: Path, file_info: FTPFileInfo
    ) -> FTPVerificationResult:
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
                        error="No expected size available, skipping verification",
                    )

                is_valid = actual_size == expected_size
                return FTPVerificationResult(
                    method=FTPVerificationMethod.SIZE,
                    expected_value=str(expected_size),
                    actual_value=str(actual_size),
                    is_valid=is_valid,
                    error=(
                        None
                        if is_valid
                        else f"Size mismatch: expected {expected_size}, got {actual_size}"
                    ),
                )

            elif self.config.verification_method in [
                FTPVerificationMethod.MD5,
                FTPVerificationMethod.SHA256,
            ]:
                # Calculate file hash
                hash_func = (
                    hashlib.md5()
                    if self.config.verification_method == FTPVerificationMethod.MD5
                    else hashlib.sha256()
                )

                async with aiofiles.open(local_path, "rb") as f:
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
                    error="Hash calculated but no expected value to compare against",
                )

            else:
                return FTPVerificationResult(
                    method=FTPVerificationMethod.NONE,
                    expected_value=None,
                    actual_value=None,
                    is_valid=True,
                    error=None,
                )

        except Exception as e:
            return FTPVerificationResult(
                method=self.config.verification_method,
                expected_value=None,
                actual_value=None,
                is_valid=False,
                error=f"Verification failed: {str(e)}",
            )
