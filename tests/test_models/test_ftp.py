"""
Comprehensive tests for FTP models in web_fetch.models.ftp module.

Tests all FTP-specific models, configurations, and data structures.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from pydantic import ValidationError

from web_fetch.models.ftp import (
    FTPMode,
    FTPAuthType,
    FTPTransferMode,
    FTPVerificationMethod,
    FTPConfig,
    FTPRequest,
    FTPFileInfo,
    FTPResult,
    FTPProgressInfo,
    FTPBatchRequest,
    FTPBatchResult,
    FTPConnectionInfo,
    FTPVerificationResult,
)


class TestFTPEnums:
    """Test FTP enumeration classes."""

    def test_ftp_mode(self):
        """Test FTPMode enumeration."""
        assert FTPMode.ACTIVE == "active"
        assert FTPMode.PASSIVE == "passive"

        # Test string behavior
        mode = FTPMode.PASSIVE
        assert str(mode) == "passive"
        assert mode == "passive"

    def test_ftp_auth_type(self):
        """Test FTPAuthType enumeration."""
        assert FTPAuthType.ANONYMOUS == "anonymous"
        assert FTPAuthType.USER_PASS == "user_pass"

        # Test string behavior
        auth_type = FTPAuthType.USER_PASS
        assert str(auth_type) == "user_pass"
        assert auth_type == "user_pass"

    def test_ftp_transfer_mode(self):
        """Test FTPTransferMode enumeration."""
        assert FTPTransferMode.BINARY == "binary"
        assert FTPTransferMode.ASCII == "ascii"

        # Test string behavior
        transfer_mode = FTPTransferMode.BINARY
        assert str(transfer_mode) == "binary"
        assert transfer_mode == "binary"

    def test_ftp_verification_method(self):
        """Test FTPVerificationMethod enumeration."""
        assert FTPVerificationMethod.SIZE == "size"
        assert FTPVerificationMethod.MD5 == "md5"
        assert FTPVerificationMethod.SHA256 == "sha256"
        assert FTPVerificationMethod.NONE == "none"

        # Test string behavior
        verification = FTPVerificationMethod.SHA256
        assert str(verification) == "sha256"
        assert verification == "sha256"


class TestFTPConfig:
    """Test FTPConfig model."""

    def test_default_config(self):
        """Test default FTP configuration."""
        config = FTPConfig()

        # Connection settings
        assert config.connection_timeout == 30.0
        assert config.data_timeout == 300.0
        assert config.keepalive_interval == 30.0

        # FTP specific settings
        assert config.mode == FTPMode.PASSIVE
        assert config.transfer_mode == FTPTransferMode.BINARY

        # Authentication
        assert config.auth_type == FTPAuthType.ANONYMOUS
        assert config.username is None
        assert config.password is None

        # Concurrency and performance
        assert config.max_concurrent_downloads == 3
        assert config.max_connections_per_host == 2
        assert config.enable_parallel_downloads is False

        # Retry settings
        assert config.max_retries == 3
        assert config.retry_delay == 2.0
        assert config.retry_backoff_factor == 2.0

        # File handling
        assert config.chunk_size == 8192
        assert config.buffer_size == 64 * 1024
        assert config.max_file_size is None

        # Verification
        assert config.verification_method == FTPVerificationMethod.SIZE
        assert config.enable_resume is True

        # Rate limiting
        assert config.rate_limit_bytes_per_second is None

    def test_custom_config(self):
        """Test custom FTP configuration."""
        config = FTPConfig(
            # Connection settings
            connection_timeout=60.0,
            data_timeout=600.0,
            keepalive_interval=60.0,

            # FTP specific settings
            mode=FTPMode.ACTIVE,
            transfer_mode=FTPTransferMode.ASCII,

            # Authentication
            auth_type=FTPAuthType.USER_PASS,
            username="testuser",
            password="testpass",

            # Concurrency and performance
            max_concurrent_downloads=10,
            max_connections_per_host=5,
            enable_parallel_downloads=True,

            # Retry settings
            max_retries=5,
            retry_delay=1.0,
            retry_backoff_factor=1.5,

            # File handling
            chunk_size=16384,
            buffer_size=128 * 1024,
            max_file_size=100 * 1024 * 1024,  # 100MB

            # Verification
            verification_method=FTPVerificationMethod.SHA256,
            enable_resume=False,

            # Rate limiting
            rate_limit_bytes_per_second=1024 * 1024  # 1MB/s
        )

        assert config.connection_timeout == 60.0
        assert config.data_timeout == 600.0
        assert config.keepalive_interval == 60.0
        assert config.mode == FTPMode.ACTIVE
        assert config.transfer_mode == FTPTransferMode.ASCII
        assert config.auth_type == FTPAuthType.USER_PASS
        assert config.username == "testuser"
        assert config.password == "testpass"
        assert config.max_concurrent_downloads == 10
        assert config.max_connections_per_host == 5
        assert config.enable_parallel_downloads is True
        assert config.max_retries == 5
        assert config.retry_delay == 1.0
        assert config.retry_backoff_factor == 1.5
        assert config.chunk_size == 16384
        assert config.buffer_size == 128 * 1024
        assert config.max_file_size == 100 * 1024 * 1024
        assert config.verification_method == FTPVerificationMethod.SHA256
        assert config.enable_resume is False
        assert config.rate_limit_bytes_per_second == 1024 * 1024

    def test_timeout_validation(self):
        """Test timeout validation."""
        # Valid timeouts
        FTPConfig(connection_timeout=0.1, data_timeout=0.1, keepalive_interval=0.1)

        # Invalid timeouts
        with pytest.raises(ValidationError):
            FTPConfig(connection_timeout=0.0)

        with pytest.raises(ValidationError):
            FTPConfig(data_timeout=-1.0)

        with pytest.raises(ValidationError):
            FTPConfig(keepalive_interval=0.0)

    def test_concurrency_validation(self):
        """Test concurrency validation."""
        # Valid values
        FTPConfig(max_concurrent_downloads=1, max_connections_per_host=1)
        FTPConfig(max_concurrent_downloads=20, max_connections_per_host=10)

        # Invalid max_concurrent_downloads
        with pytest.raises(ValidationError):
            FTPConfig(max_concurrent_downloads=0)

        with pytest.raises(ValidationError):
            FTPConfig(max_concurrent_downloads=21)

        # Invalid max_connections_per_host
        with pytest.raises(ValidationError):
            FTPConfig(max_connections_per_host=0)

        with pytest.raises(ValidationError):
            FTPConfig(max_connections_per_host=11)

    def test_retry_validation(self):
        """Test retry validation."""
        # Valid values
        FTPConfig(max_retries=0, retry_delay=0.1, retry_backoff_factor=1.0)
        FTPConfig(max_retries=10, retry_delay=60.0, retry_backoff_factor=10.0)

        # Invalid max_retries
        with pytest.raises(ValidationError):
            FTPConfig(max_retries=-1)

        with pytest.raises(ValidationError):
            FTPConfig(max_retries=11)

        # Invalid retry_delay
        with pytest.raises(ValidationError):
            FTPConfig(retry_delay=0.05)

        with pytest.raises(ValidationError):
            FTPConfig(retry_delay=61.0)

        # Invalid retry_backoff_factor
        with pytest.raises(ValidationError):
            FTPConfig(retry_backoff_factor=0.5)

        with pytest.raises(ValidationError):
            FTPConfig(retry_backoff_factor=11.0)

    def test_file_handling_validation(self):
        """Test file handling validation."""
        # Valid values
        FTPConfig(chunk_size=1024, buffer_size=8192, max_file_size=0)
        FTPConfig(chunk_size=1024*1024, buffer_size=1024*1024)

        # Invalid chunk_size
        with pytest.raises(ValidationError):
            FTPConfig(chunk_size=512)  # Below minimum

        with pytest.raises(ValidationError):
            FTPConfig(chunk_size=2*1024*1024)  # Above maximum

        # Invalid buffer_size
        with pytest.raises(ValidationError):
            FTPConfig(buffer_size=4096)  # Below minimum

        # Invalid max_file_size
        with pytest.raises(ValidationError):
            FTPConfig(max_file_size=-1)

    def test_rate_limit_validation(self):
        """Test rate limit validation."""
        # Valid values
        FTPConfig(rate_limit_bytes_per_second=None)
        FTPConfig(rate_limit_bytes_per_second=1024)

        # Invalid rate limit
        with pytest.raises(ValidationError):
            FTPConfig(rate_limit_bytes_per_second=512)  # Below minimum


class TestFTPRequest:
    """Test FTPRequest model."""

    def test_basic_request(self):
        """Test basic FTP request."""
        request = FTPRequest(url="ftp://ftp.example.com/file.txt")

        assert request.url == "ftp://ftp.example.com/file.txt"
        assert request.local_path is None
        assert request.operation == "download"
        assert request.config_override is None
        assert request.timeout_override is None

    def test_download_request(self):
        """Test download request with local path."""
        local_path = Path("/tmp/downloaded_file.txt")
        config_override = FTPConfig(max_retries=5)

        request = FTPRequest(
            url="ftp://ftp.example.com/path/file.txt",
            local_path=local_path,
            operation="download",
            config_override=config_override,
            timeout_override=60.0
        )

        assert request.url == "ftp://ftp.example.com/path/file.txt"
        assert request.local_path == local_path
        assert request.operation == "download"
        assert request.config_override == config_override
        assert request.timeout_override == 60.0

    def test_list_request(self):
        """Test list operation request."""
        request = FTPRequest(
            url="ftp://ftp.example.com/directory/",
            operation="list"
        )

        assert request.url == "ftp://ftp.example.com/directory/"
        assert request.operation == "list"

    def test_info_request(self):
        """Test info operation request."""
        request = FTPRequest(
            url="ftp://ftp.example.com/file.txt",
            operation="info"
        )

        assert request.url == "ftp://ftp.example.com/file.txt"
        assert request.operation == "info"

    def test_url_validation(self):
        """Test URL validation."""
        # Valid FTP URLs
        FTPRequest(url="ftp://ftp.example.com/file.txt")
        FTPRequest(url="ftps://secure.ftp.example.com/file.txt")

        # Invalid URLs - non-FTP schemes should be rejected
        with pytest.raises(ValidationError):
            FTPRequest(url="http://example.com/file.txt")

        with pytest.raises(ValidationError):
            FTPRequest(url="file:///path/to/file")

    def test_operation_validation(self):
        """Test operation validation."""
        # Valid operations
        for operation in ["download", "list", "info"]:
            request = FTPRequest(url="ftp://ftp.example.com/file.txt", operation=operation)
            assert request.operation == operation

        # Invalid operation
        with pytest.raises(ValidationError):
            FTPRequest(url="ftp://ftp.example.com/file.txt", operation="invalid")

        with pytest.raises(ValidationError):
            FTPRequest(url="ftp://ftp.example.com/file.txt", operation="upload")

    def test_timeout_override_validation(self):
        """Test timeout override validation."""
        # Valid timeout
        FTPRequest(url="ftp://ftp.example.com/file.txt", timeout_override=10.5)

        # Invalid timeout
        with pytest.raises(ValidationError):
            FTPRequest(url="ftp://ftp.example.com/file.txt", timeout_override=0.0)

        with pytest.raises(ValidationError):
            FTPRequest(url="ftp://ftp.example.com/file.txt", timeout_override=-5.0)


class TestFTPFileInfo:
    """Test FTPFileInfo dataclass."""

    def test_basic_file_info(self):
        """Test basic file information."""
        file_info = FTPFileInfo(
            name="document.pdf",
            path="/files/document.pdf",
            size=1024000,
            modified_time=datetime.now(),
            is_directory=False
        )

        assert file_info.name == "document.pdf"
        assert file_info.path == "/files/document.pdf"
        assert file_info.size == 1024000
        assert isinstance(file_info.modified_time, datetime)
        assert file_info.is_directory is False
        assert file_info.permissions is None
        assert file_info.owner is None
        assert file_info.group is None

    def test_directory_info(self):
        """Test directory information."""
        dir_info = FTPFileInfo(
            name="uploads",
            path="/uploads",
            size=None,
            modified_time=datetime.now(),
            is_directory=True,
            permissions="drwxr-xr-x",
            owner="ftpuser",
            group="ftpgroup"
        )

        assert dir_info.name == "uploads"
        assert dir_info.path == "/uploads"
        assert dir_info.size is None
        assert dir_info.is_directory is True
        assert dir_info.permissions == "drwxr-xr-x"
        assert dir_info.owner == "ftpuser"
        assert dir_info.group == "ftpgroup"

    def test_file_with_permissions(self):
        """Test file with detailed permissions."""
        file_info = FTPFileInfo(
            name="script.sh",
            path="/scripts/script.sh",
            size=2048,
            modified_time=datetime.now(),
            is_directory=False,
            permissions="-rwxr--r--",
            owner="admin",
            group="users"
        )

        assert file_info.permissions == "-rwxr--r--"
        assert file_info.owner == "admin"
        assert file_info.group == "users"


class TestFTPResult:
    """Test FTPResult dataclass."""

    def test_successful_download_result(self):
        """Test successful download result."""
        file_info = FTPFileInfo(
            name="file.txt",
            path="/file.txt",
            size=1024,
            modified_time=datetime.now(),
            is_directory=False
        )

        result = FTPResult(
            url="ftp://ftp.example.com/file.txt",
            operation="download",
            status_code=200,
            local_path=Path("/tmp/file.txt"),
            bytes_transferred=1024,
            total_bytes=1024,
            response_time=2.5,
            timestamp=datetime.now(),
            file_info=file_info
        )

        assert result.url == "ftp://ftp.example.com/file.txt"
        assert result.operation == "download"
        assert result.status_code == 200
        assert result.local_path == Path("/tmp/file.txt")
        assert result.bytes_transferred == 1024
        assert result.total_bytes == 1024
        assert result.response_time == 2.5
        assert result.error is None
        assert result.retry_count == 0
        assert result.file_info == file_info
        assert result.files_list is None
        assert result.verification_result is None
        assert result.is_success is True
        assert result.transfer_complete is True

    def test_failed_download_result(self):
        """Test failed download result."""
        result = FTPResult(
            url="ftp://ftp.example.com/nonexistent.txt",
            operation="download",
            status_code=404,
            local_path=None,
            bytes_transferred=0,
            total_bytes=None,
            response_time=1.0,
            timestamp=datetime.now(),
            error="File not found",
            retry_count=3
        )

        assert result.status_code == 404
        assert result.error == "File not found"
        assert result.retry_count == 3
        assert result.is_success is False
        assert result.transfer_complete is False

    def test_list_operation_result(self):
        """Test list operation result."""
        files_list = [
            FTPFileInfo("file1.txt", "/file1.txt", 1024, datetime.now(), False),
            FTPFileInfo("file2.txt", "/file2.txt", 2048, datetime.now(), False),
            FTPFileInfo("subdir", "/subdir", None, datetime.now(), True)
        ]

        result = FTPResult(
            url="ftp://ftp.example.com/",
            operation="list",
            status_code=200,
            local_path=None,
            bytes_transferred=0,
            total_bytes=None,
            response_time=0.5,
            timestamp=datetime.now(),
            files_list=files_list
        )

        assert result.operation == "list"
        assert result.files_list == files_list
        assert len(result.files_list) == 3
        assert result.is_success is True

    def test_transfer_rate_calculation(self):
        """Test transfer rate calculation."""
        # Normal transfer
        result = FTPResult(
            url="ftp://ftp.example.com/file.txt",
            operation="download",
            status_code=200,
            local_path=None,
            bytes_transferred=10 * 1024 * 1024,  # 10MB
            total_bytes=10 * 1024 * 1024,
            response_time=10.0,  # 10 seconds
            timestamp=datetime.now()
        )

        # 10MB in 10 seconds = 1MB/s
        assert result.transfer_rate_mbps == 1.0

        # Zero time case
        result_zero_time = FTPResult(
            url="ftp://ftp.example.com/file.txt",
            operation="download",
            status_code=200,
            local_path=None,
            bytes_transferred=1024,
            total_bytes=1024,
            response_time=0.0,
            timestamp=datetime.now()
        )

        assert result_zero_time.transfer_rate_mbps == 0.0

    def test_verification_result(self):
        """Test result with verification information."""
        verification = {
            "method": "sha256",
            "expected": "abc123",
            "actual": "abc123",
            "valid": True
        }

        result = FTPResult(
            url="ftp://ftp.example.com/file.txt",
            operation="download",
            status_code=200,
            local_path=Path("/tmp/file.txt"),
            bytes_transferred=1024,
            total_bytes=1024,
            response_time=1.0,
            timestamp=datetime.now(),
            verification_result=verification
        )

        assert result.verification_result == verification
        assert result.verification_result["valid"] is True


class TestFTPProgressInfo:
    """Test FTPProgressInfo dataclass."""

    def test_basic_progress_info(self):
        """Test basic progress information."""
        progress = FTPProgressInfo(
            bytes_transferred=5120,
            total_bytes=10240,
            transfer_rate=1024.0,  # 1KB/s
            elapsed_time=5.0,
            estimated_time_remaining=5.0,
            current_file="file.txt"
        )

        assert progress.bytes_transferred == 5120
        assert progress.total_bytes == 10240
        assert progress.transfer_rate == 1024.0
        assert progress.elapsed_time == 5.0
        assert progress.estimated_time_remaining == 5.0
        assert progress.current_file == "file.txt"

    def test_progress_percentage(self):
        """Test progress percentage calculation."""
        # 50% progress
        progress = FTPProgressInfo(
            bytes_transferred=5120,
            total_bytes=10240,
            transfer_rate=1024.0,
            elapsed_time=5.0
        )

        assert progress.progress_percentage == 50.0

        # Unknown total bytes
        progress_unknown = FTPProgressInfo(
            bytes_transferred=5120,
            total_bytes=None,
            transfer_rate=1024.0,
            elapsed_time=5.0
        )

        assert progress_unknown.progress_percentage is None

        # Zero total bytes
        progress_zero = FTPProgressInfo(
            bytes_transferred=0,
            total_bytes=0,
            transfer_rate=0.0,
            elapsed_time=0.0
        )

        assert progress_zero.progress_percentage is None

    def test_transfer_rate_mbps(self):
        """Test transfer rate in MB/s."""
        # 1MB/s transfer rate
        progress = FTPProgressInfo(
            bytes_transferred=1024*1024,
            total_bytes=10*1024*1024,
            transfer_rate=1024*1024,  # 1MB/s in bytes
            elapsed_time=1.0
        )

        assert progress.transfer_rate_mbps == 1.0

        # 0.5MB/s transfer rate
        progress_half = FTPProgressInfo(
            bytes_transferred=512*1024,
            total_bytes=1024*1024,
            transfer_rate=512*1024,  # 0.5MB/s in bytes
            elapsed_time=1.0
        )

        assert progress_half.transfer_rate_mbps == 0.5
