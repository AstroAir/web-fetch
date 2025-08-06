"""
FTP-specific data models and configuration classes for the web fetcher utility.

This module defines FTP-specific models that integrate with the existing web_fetch
architecture, providing structured data handling for FTP operations.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, ConfigDict


class FTPMode(str, Enum):
    """FTP connection modes."""

    ACTIVE = "active"
    PASSIVE = "passive"


class FTPAuthType(str, Enum):
    """FTP authentication types."""

    ANONYMOUS = "anonymous"
    USER_PASS = "user_pass"


class FTPTransferMode(str, Enum):
    """FTP transfer modes."""

    BINARY = "binary"
    ASCII = "ascii"


class FTPVerificationMethod(str, Enum):
    """File verification methods."""

    SIZE = "size"
    MD5 = "md5"
    SHA256 = "sha256"
    NONE = "none"


class FTPConfig(BaseModel):
    """
    Comprehensive configuration model for FTP operations with validation and defaults.

    FTPConfig defines all configurable parameters for FTP operations including
    connection settings, authentication, performance tuning, retry behavior,
    and file handling options. All fields are validated using Pydantic for
    type safety and constraint enforcement.

    Connection Management:
        Controls FTP connection behavior including timeouts, connection modes,
        and keepalive settings for reliable operation across various network
        conditions and server configurations.

    Authentication:
        Supports multiple authentication methods from anonymous access to
        username/password authentication, with secure credential handling.

    Performance Optimization:
        Provides extensive performance tuning options including concurrent
        downloads, connection pooling, parallel transfers, and rate limiting
        to optimize throughput while respecting server limits.

    Reliability Features:
        Includes comprehensive retry logic, file verification, resumable
        downloads, and error recovery mechanisms for robust operation.

    Example:
        ```python
        from web_fetch import FTPConfig, FTPMode, FTPTransferMode, FTPVerificationMethod

        # Basic anonymous FTP configuration
        basic_config = FTPConfig()

        # Authenticated FTP with performance tuning
        config = FTPConfig(
            # Authentication
            auth_type=FTPAuthType.USER_PASS,
            username="user",
            password="password",

            # Connection settings
            connection_timeout=60.0,
            data_timeout=600.0,
            mode=FTPMode.PASSIVE,

            # Performance settings
            max_concurrent_downloads=5,
            enable_parallel_downloads=True,
            chunk_size=16384,  # 16KB chunks

            # Reliability settings
            max_retries=5,
            verification_method=FTPVerificationMethod.SHA256,
            enable_resume=True,

            # Rate limiting (1MB/s)
            rate_limit_bytes_per_second=1024*1024
        )

        # High-performance configuration for fast networks
        fast_config = FTPConfig(
            max_concurrent_downloads=10,
            max_connections_per_host=5,
            enable_parallel_downloads=True,
            chunk_size=64*1024,  # 64KB chunks
            buffer_size=256*1024,  # 256KB buffer
            connection_timeout=15.0,
            data_timeout=120.0
        )
        ```

    Validation:
        All fields are validated for type correctness and value constraints.
        Invalid configurations will raise ValidationError during instantiation.

    Thread Safety:
        FTPConfig instances are immutable after creation and are thread-safe.
        They can be safely shared across multiple FTPFetcher instances.
    """

    # Connection settings - Control FTP connection behavior
    connection_timeout: float = Field(
        default=30.0,
        gt=0,
        description="Maximum time to wait for FTP connection establishment in seconds. "
                   "Lower values fail faster for unreachable hosts but may cause issues "
                   "with slow networks or overloaded servers."
    )
    data_timeout: float = Field(
        default=300.0,
        gt=0,
        description="Maximum time to wait for data transfer operations in seconds. "
                   "Should be set based on expected file sizes and network speed. "
                   "Large files over slow connections may need higher values."
    )
    keepalive_interval: float = Field(
        default=30.0,
        gt=0,
        description="Interval between keepalive messages in seconds to prevent "
                   "connection timeouts during long transfers. Should be less than "
                   "server timeout settings."
    )

    # FTP specific settings - Protocol-level configuration
    mode: FTPMode = Field(
        default=FTPMode.PASSIVE,
        description="FTP connection mode. PASSIVE (default) works better with "
                   "firewalls and NAT, ACTIVE may be required for some servers. "
                   "PASSIVE is recommended for most use cases."
    )
    transfer_mode: FTPTransferMode = Field(
        default=FTPTransferMode.BINARY,
        description="Data transfer mode. BINARY (default) preserves file integrity "
                   "for all file types, ASCII performs line ending conversion for "
                   "text files but may corrupt binary files."
    )

    # Authentication - Credential and access control settings
    auth_type: FTPAuthType = Field(
        default=FTPAuthType.ANONYMOUS,
        description="Authentication method. ANONYMOUS allows access without credentials, "
                   "USER_PASS requires username and password. Some servers may restrict "
                   "anonymous access."
    )
    username: Optional[str] = Field(
        default=None,
        description="Username for authentication when auth_type is USER_PASS. "
                   "Required for authenticated access, ignored for anonymous access."
    )
    password: Optional[str] = Field(
        default=None,
        description="Password for authentication when auth_type is USER_PASS. "
                   "Should be kept secure and not logged. Consider using environment "
                   "variables or secure credential storage."
    )

    # Concurrency and performance - Optimize transfer speed and resource usage
    max_concurrent_downloads: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Maximum number of files that can be downloaded concurrently. "
                   "Higher values improve throughput but increase server load and "
                   "memory usage. Respect server connection limits."
    )
    max_connections_per_host: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Maximum number of FTP connections to maintain per host. "
                   "Higher values reduce connection overhead but consume more resources. "
                   "Many FTP servers limit concurrent connections per client."
    )
    enable_parallel_downloads: bool = Field(
        default=False,
        description="Enable parallel downloading of single files using multiple "
                   "connections. Can significantly improve speed for large files "
                   "but requires server support and may be restricted by some servers."
    )

    # Retry settings - Control failure recovery behavior
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retry attempts for failed operations. "
                   "Higher values improve reliability but increase latency for "
                   "permanently failing operations."
    )
    retry_delay: float = Field(
        default=2.0,
        ge=0.1,
        le=60.0,
        description="Base delay in seconds between retry attempts. Actual delay "
                   "is calculated as: retry_delay * (retry_backoff_factor ^ attempt)."
    )
    retry_backoff_factor: float = Field(
        default=2.0,
        ge=1.0,
        le=10.0,
        description="Exponential backoff factor for retry delays. Higher values "
                   "provide more aggressive backoff to avoid overwhelming failing servers."
    )

    # File handling - Control data transfer and storage behavior
    chunk_size: int = Field(
        default=8192,
        ge=1024,
        le=1024*1024,
        description="Size of data chunks for file transfers in bytes. Larger chunks "
                   "improve performance but increase memory usage. Optimal size depends "
                   "on network conditions and available memory. Default: 8KB."
    )
    buffer_size: int = Field(
        default=64*1024,
        ge=8192,
        description="Buffer size for streaming operations in bytes. Should be larger "
                   "than chunk_size for optimal performance. Affects memory usage during "
                   "transfers. Default: 64KB."
    )
    max_file_size: Optional[int] = Field(
        default=None,
        ge=0,
        description="Maximum allowed file size in bytes. Files larger than this limit "
                   "will be rejected to prevent excessive resource usage. None means "
                   "no limit (use with caution)."
    )

    # Verification - Ensure file integrity and completeness
    verification_method: FTPVerificationMethod = Field(
        default=FTPVerificationMethod.SIZE,
        description="Method for verifying downloaded files. SIZE checks file size only "
                   "(fast), MD5/SHA256 compute cryptographic hashes (slower but more reliable), "
                   "NONE disables verification (fastest but risky)."
    )
    enable_resume: bool = Field(
        default=True,
        description="Enable resumable downloads for interrupted transfers. Allows "
                   "continuing partial downloads instead of restarting from beginning. "
                   "Requires server support for REST command."
    )

    # Rate limiting - Control bandwidth usage
    rate_limit_bytes_per_second: Optional[int] = Field(
        default=None,
        ge=1024,
        description="Maximum transfer rate in bytes per second. Useful for limiting "
                   "bandwidth usage or complying with server rate limits. None means "
                   "no rate limiting. Minimum: 1KB/s."
    )

    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True
    )


class FTPRequest(BaseModel):
    """Model representing a single FTP request."""

    url: str = Field(description="FTP URL to process")
    local_path: Optional[Path] = Field(default=None, description="Local path to save file")
    operation: str = Field(default="download", pattern=r"^(download|list|info)$", description="FTP operation")

    # Override settings
    config_override: Optional[FTPConfig] = Field(default=None, description="Override configuration")
    timeout_override: Optional[float] = Field(default=None, gt=0, description="Override timeout")

    @field_validator('url')
    @classmethod
    def validate_ftp_url(cls, v: Any) -> Any:
        """Validate FTP URL format and scheme."""
        parsed = urlparse(str(v))
        if parsed.scheme not in ('ftp', 'ftps'):
            raise ValueError('URL must use ftp or ftps scheme')
        return v

    model_config = ConfigDict(
        use_enum_values=True
    )


@dataclass
class FTPFileInfo:
    """Information about an FTP file or directory."""

    name: str
    path: str
    size: Optional[int]
    modified_time: Optional[datetime]
    is_directory: bool
    permissions: Optional[str] = None
    owner: Optional[str] = None
    group: Optional[str] = None


@dataclass
class FTPResult:
    """Result of an FTP operation."""

    url: str
    operation: str
    status_code: int  # Custom FTP status codes
    local_path: Optional[Path]
    bytes_transferred: int
    total_bytes: Optional[int]
    response_time: float
    timestamp: datetime
    error: Optional[str] = None
    retry_count: int = 0
    file_info: Optional[FTPFileInfo] = None
    files_list: Optional[List[FTPFileInfo]] = None
    verification_result: Optional[Dict[str, Any]] = None

    @property
    def is_success(self) -> bool:
        """Check if the FTP operation was successful."""
        return self.status_code == 200 and self.error is None

    @property
    def transfer_complete(self) -> bool:
        """Check if file transfer completed successfully."""
        if not self.is_success or self.total_bytes is None:
            return False
        return self.bytes_transferred >= self.total_bytes

    @property
    def transfer_rate_mbps(self) -> float:
        """Calculate transfer rate in MB/s."""
        if self.response_time <= 0:
            return 0.0
        return (self.bytes_transferred / (1024 * 1024)) / self.response_time


@dataclass
class FTPProgressInfo:
    """Progress information for FTP operations."""

    bytes_transferred: int
    total_bytes: Optional[int]
    transfer_rate: float  # bytes per second
    elapsed_time: float
    estimated_time_remaining: Optional[float]
    current_file: Optional[str] = None

    @property
    def progress_percentage(self) -> Optional[float]:
        """Calculate progress as percentage."""
        if self.total_bytes is None or self.total_bytes == 0:
            return None
        return (self.bytes_transferred / self.total_bytes) * 100

    @property
    def transfer_rate_mbps(self) -> float:
        """Transfer rate in MB/s."""
        return self.transfer_rate / (1024 * 1024)


class FTPBatchRequest(BaseModel):
    """Model for batch FTP operations."""

    requests: List[FTPRequest] = Field(min_length=1, max_length=100, description="List of FTP requests")
    config: Optional[FTPConfig] = Field(default=None, description="Batch configuration")
    parallel_execution: bool = Field(default=False, description="Execute requests in parallel")

    @field_validator('requests')
    @classmethod
    def validate_unique_urls(cls, v: Any) -> Any:
        """Ensure URLs are unique in batch request."""
        urls = [req.url for req in v]
        if len(urls) != len(set(urls)):
            raise ValueError('Duplicate URLs found in batch request')
        return v


@dataclass
class FTPBatchResult:
    """Result of a batch FTP operation."""

    results: List[FTPResult]
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_bytes_transferred: int
    total_time: float
    timestamp: datetime

    @classmethod
    def from_results(cls, results: List[FTPResult], total_time: float) -> FTPBatchResult:
        """Create FTPBatchResult from individual results."""
        successful = sum(1 for r in results if r.is_success)
        failed = len(results) - successful
        total_bytes = sum(r.bytes_transferred for r in results)

        return cls(
            results=results,
            total_requests=len(results),
            successful_requests=successful,
            failed_requests=failed,
            total_bytes_transferred=total_bytes,
            total_time=total_time,
            timestamp=datetime.now()
        )

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def average_transfer_rate_mbps(self) -> float:
        """Calculate average transfer rate in MB/s."""
        if self.total_time <= 0:
            return 0.0
        return (self.total_bytes_transferred / (1024 * 1024)) / self.total_time


# Connection pool models

@dataclass
class FTPConnectionInfo:
    """Information about an FTP connection."""

    host: str
    port: int
    username: Optional[str]
    is_secure: bool
    created_at: datetime
    last_used: datetime
    connection_count: int = 0

    @property
    def connection_key(self) -> str:
        """Generate unique key for connection pooling."""
        return f"{self.host}:{self.port}:{self.username or 'anonymous'}"


@dataclass
class FTPVerificationResult:
    """Result of file verification."""

    method: FTPVerificationMethod
    expected_value: Optional[str]
    actual_value: Optional[str]
    is_valid: bool
    error: Optional[str] = None

    @property
    def verification_details(self) -> Dict[str, Any]:
        """Get detailed verification information."""
        return {
            "method": self.method,
            "expected": self.expected_value,
            "actual": self.actual_value,
            "valid": self.is_valid,
            "error": self.error
        }