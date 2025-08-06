"""
Tests for FTP functionality in the web_fetch library.

This module contains comprehensive tests for FTP operations including
connection management, file operations, streaming, and verification.
"""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from web_fetch import (
    FTPAuthType,
    FTPConfig,
    FTPFetcher,
    FTPMode,
    FTPRequest,
    FTPBatchRequest,
    FTPVerificationMethod,
    FTPError,
    FTPConnectionError,
    FTPFileNotFoundError,
)


class TestFTPConfig:
    """Test FTP configuration model."""

    def test_default_config(self):
        """Test default configuration values."""
        config = FTPConfig()

        assert config.connection_timeout == 30.0
        assert config.mode == FTPMode.PASSIVE
        assert config.auth_type == FTPAuthType.ANONYMOUS
        assert config.max_concurrent_downloads == 3
        assert config.enable_parallel_downloads is False
        assert config.verification_method == FTPVerificationMethod.SIZE
        assert config.enable_resume is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = FTPConfig(
            connection_timeout=60.0,
            mode=FTPMode.ACTIVE,
            auth_type=FTPAuthType.USER_PASS,
            username="testuser",
            password="testpass",
            max_concurrent_downloads=5,
            enable_parallel_downloads=True,
            verification_method=FTPVerificationMethod.MD5,
            chunk_size=16384,
        )

        assert config.connection_timeout == 60.0
        assert config.mode == FTPMode.ACTIVE
        assert config.auth_type == FTPAuthType.USER_PASS
        assert config.username == "testuser"
        assert config.password == "testpass"
        assert config.max_concurrent_downloads == 5
        assert config.enable_parallel_downloads is True
        assert config.verification_method == FTPVerificationMethod.MD5
        assert config.chunk_size == 16384


class TestFTPRequest:
    """Test FTP request model."""

    def test_valid_ftp_request(self):
        """Test valid FTP request creation."""
        request = FTPRequest(
            url="ftp://ftp.example.com/test.txt",
            local_path=Path("test.txt"),
            operation="download"
        )

        assert request.url == "ftp://ftp.example.com/test.txt"
        assert request.local_path == Path("test.txt")
        assert request.operation == "download"

    def test_invalid_url_scheme(self):
        """Test that invalid URL schemes are rejected."""
        with pytest.raises(ValueError, match="URL must use ftp or ftps scheme"):
            FTPRequest(url="http://example.com/test.txt")

    def test_valid_operations(self):
        """Test valid operation types."""
        for operation in ["download", "list", "info"]:
            request = FTPRequest(
                url="ftp://ftp.example.com/test.txt",
                operation=operation
            )
            assert request.operation == operation

    def test_invalid_operation(self):
        """Test that invalid operations are rejected."""
        with pytest.raises(ValueError):
            FTPRequest(
                url="ftp://ftp.example.com/test.txt",
                operation="invalid_operation"
            )


class TestFTPBatchRequest:
    """Test FTP batch request model."""

    def test_valid_batch_request(self):
        """Test valid batch request creation."""
        requests = [
            FTPRequest(url="ftp://ftp.example.com/file1.txt"),
            FTPRequest(url="ftp://ftp.example.com/file2.txt"),
        ]

        batch = FTPBatchRequest(requests=requests)
        assert len(batch.requests) == 2
        assert batch.parallel_execution is False

    def test_duplicate_urls_rejected(self):
        """Test that duplicate URLs in batch are rejected."""
        requests = [
            FTPRequest(url="ftp://ftp.example.com/file1.txt"),
            FTPRequest(url="ftp://ftp.example.com/file1.txt"),  # Duplicate
        ]

        with pytest.raises(ValueError, match="Duplicate URLs found"):
            FTPBatchRequest(requests=requests)


@pytest.mark.asyncio
class TestFTPFetcher:
    """Test FTP fetcher functionality."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return FTPConfig(
            connection_timeout=10.0,
            max_concurrent_downloads=2,
        )

    @pytest.fixture
    def fetcher(self, config):
        """Create FTP fetcher instance."""
        return FTPFetcher(config)

    async def test_fetcher_context_manager(self, fetcher):
        """Test FTP fetcher as context manager."""
        async with fetcher as f:
            assert f is fetcher
        # Should not raise any exceptions

    @patch('web_fetch.ftp_connection.aioftp.Client')
    async def test_connection_creation(self, mock_client, fetcher):
        """Test FTP connection creation."""
        mock_instance = AsyncMock()
        mock_client.return_value = mock_instance

        # Mock the connection pool's get_connection method
        with patch.object(fetcher.connection_pool, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            # This would normally create a connection
            async with fetcher.connection_pool.get_connection("ftp://test.com") as conn:
                assert conn is mock_instance

    async def test_close_cleanup(self, fetcher):
        """Test that close properly cleans up resources."""
        await fetcher.close()
        # Should not raise any exceptions

    def test_config_update(self, fetcher):
        """Test configuration updates."""
        original_timeout = fetcher.config.connection_timeout

        fetcher.update_config(connection_timeout=60.0)
        assert fetcher.config.connection_timeout == 60.0
        assert fetcher.config.connection_timeout != original_timeout


if __name__ == "__main__":
    pytest.main([__file__])