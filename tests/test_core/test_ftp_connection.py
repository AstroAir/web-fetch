"""
Comprehensive tests for the FTP connection module.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from web_fetch.ftp_connection import (
    FTPConnection,
    FTPConfig,
    FTPConnectionPool,
    FTPConnectionError,
    FTPAuthenticationError,
    FTPTimeoutError,
)
from web_fetch.models.ftp import FTPCredentials, FTPServerInfo, FTPTransferMode


class TestFTPConfig:
    """Test FTP configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = FTPConfig()
        
        assert config.timeout == 30.0
        assert config.passive_mode is True
        assert config.transfer_mode == FTPTransferMode.BINARY
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = FTPConfig(
            timeout=60.0,
            passive_mode=False,
            transfer_mode=FTPTransferMode.ASCII,
            max_retries=5,
            retry_delay=2.0
        )
        
        assert config.timeout == 60.0
        assert config.passive_mode is False
        assert config.transfer_mode == FTPTransferMode.ASCII
        assert config.max_retries == 5
        assert config.retry_delay == 2.0
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Invalid timeout
        with pytest.raises(ValueError, match="timeout must be positive"):
            FTPConfig(timeout=0)
        
        # Invalid max_retries
        with pytest.raises(ValueError, match="max_retries must be non-negative"):
            FTPConfig(max_retries=-1)
        
        # Invalid retry_delay
        with pytest.raises(ValueError, match="retry_delay must be non-negative"):
            FTPConfig(retry_delay=-1.0)


class TestFTPCredentials:
    """Test FTP credentials model."""
    
    def test_credentials_creation(self):
        """Test FTP credentials creation."""
        creds = FTPCredentials(
            username="testuser",
            password="testpass",
            account="testaccount"
        )
        
        assert creds.username == "testuser"
        assert creds.password == "testpass"
        assert creds.account == "testaccount"
    
    def test_anonymous_credentials(self):
        """Test anonymous FTP credentials."""
        creds = FTPCredentials.anonymous()
        
        assert creds.username == "anonymous"
        assert creds.password == "guest@example.com"
        assert creds.account is None
    
    def test_credentials_validation(self):
        """Test credentials validation."""
        # Empty username
        with pytest.raises(ValueError, match="username cannot be empty"):
            FTPCredentials(username="", password="pass")
        
        # Empty password
        with pytest.raises(ValueError, match="password cannot be empty"):
            FTPCredentials(username="user", password="")


class TestFTPServerInfo:
    """Test FTP server info model."""
    
    def test_server_info_creation(self):
        """Test FTP server info creation."""
        server = FTPServerInfo(
            host="ftp.example.com",
            port=21,
            use_tls=False
        )
        
        assert server.host == "ftp.example.com"
        assert server.port == 21
        assert server.use_tls is False
    
    def test_server_info_with_tls(self):
        """Test FTP server info with TLS."""
        server = FTPServerInfo(
            host="ftps.example.com",
            port=990,
            use_tls=True
        )
        
        assert server.host == "ftps.example.com"
        assert server.port == 990
        assert server.use_tls is True
    
    def test_server_info_validation(self):
        """Test server info validation."""
        # Empty host
        with pytest.raises(ValueError, match="host cannot be empty"):
            FTPServerInfo(host="", port=21)
        
        # Invalid port
        with pytest.raises(ValueError, match="port must be between 1 and 65535"):
            FTPServerInfo(host="ftp.example.com", port=0)
        
        with pytest.raises(ValueError, match="port must be between 1 and 65535"):
            FTPServerInfo(host="ftp.example.com", port=70000)


class TestFTPConnection:
    """Test FTP connection functionality."""
    
    @pytest.fixture
    def server_info(self):
        """Create FTP server info."""
        return FTPServerInfo(host="ftp.example.com", port=21)
    
    @pytest.fixture
    def credentials(self):
        """Create FTP credentials."""
        return FTPCredentials(username="testuser", password="testpass")
    
    @pytest.fixture
    def config(self):
        """Create FTP configuration."""
        return FTPConfig(timeout=30.0, passive_mode=True)
    
    @pytest.fixture
    def connection(self, server_info, credentials, config):
        """Create FTP connection."""
        return FTPConnection(server_info, credentials, config)
    
    def test_connection_initialization(self, connection):
        """Test connection initialization."""
        assert connection.server_info.host == "ftp.example.com"
        assert connection.credentials.username == "testuser"
        assert connection.config.timeout == 30.0
        assert connection._ftp is None
        assert connection.is_connected is False
    
    @pytest.mark.asyncio
    async def test_connect_success(self, connection):
        """Test successful FTP connection."""
        with patch('ftplib.FTP') as mock_ftp_class:
            mock_ftp = MagicMock()
            mock_ftp_class.return_value = mock_ftp
            
            # Mock successful connection
            mock_ftp.connect.return_value = None
            mock_ftp.login.return_value = "230 Login successful"
            mock_ftp.set_pasv.return_value = None
            
            await connection.connect()
            
            assert connection.is_connected is True
            mock_ftp.connect.assert_called_once_with("ftp.example.com", 21, 30.0)
            mock_ftp.login.assert_called_once_with("testuser", "testpass")
            mock_ftp.set_pasv.assert_called_once_with(True)
    
    @pytest.mark.asyncio
    async def test_connect_with_tls(self):
        """Test FTP connection with TLS."""
        server_info = FTPServerInfo(host="ftps.example.com", port=990, use_tls=True)
        credentials = FTPCredentials(username="user", password="pass")
        config = FTPConfig()
        connection = FTPConnection(server_info, credentials, config)
        
        with patch('ftplib.FTP_TLS') as mock_ftp_tls_class:
            mock_ftp = MagicMock()
            mock_ftp_tls_class.return_value = mock_ftp
            
            mock_ftp.connect.return_value = None
            mock_ftp.auth.return_value = None
            mock_ftp.prot_p.return_value = None
            mock_ftp.login.return_value = "230 Login successful"
            
            await connection.connect()
            
            assert connection.is_connected is True
            mock_ftp.connect.assert_called_once_with("ftps.example.com", 990, 30.0)
            mock_ftp.auth.assert_called_once()
            mock_ftp.prot_p.assert_called_once()
            mock_ftp.login.assert_called_once_with("user", "pass")
    
    @pytest.mark.asyncio
    async def test_connect_authentication_failure(self, connection):
        """Test FTP connection authentication failure."""
        with patch('ftplib.FTP') as mock_ftp_class:
            mock_ftp = MagicMock()
            mock_ftp_class.return_value = mock_ftp
            
            # Mock authentication failure
            mock_ftp.connect.return_value = None
            mock_ftp.login.side_effect = Exception("530 Login incorrect")
            
            with pytest.raises(FTPAuthenticationError):
                await connection.connect()
            
            assert connection.is_connected is False
    
    @pytest.mark.asyncio
    async def test_connect_timeout(self, connection):
        """Test FTP connection timeout."""
        with patch('ftplib.FTP') as mock_ftp_class:
            mock_ftp = MagicMock()
            mock_ftp_class.return_value = mock_ftp
            
            # Mock connection timeout
            mock_ftp.connect.side_effect = TimeoutError("Connection timed out")
            
            with pytest.raises(FTPTimeoutError):
                await connection.connect()
            
            assert connection.is_connected is False
    
    @pytest.mark.asyncio
    async def test_disconnect(self, connection):
        """Test FTP disconnection."""
        # First connect
        with patch('ftplib.FTP') as mock_ftp_class:
            mock_ftp = MagicMock()
            mock_ftp_class.return_value = mock_ftp
            connection._ftp = mock_ftp
            connection._connected = True
            
            await connection.disconnect()
            
            assert connection.is_connected is False
            mock_ftp.quit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_directory(self, connection):
        """Test listing directory contents."""
        with patch('ftplib.FTP') as mock_ftp_class:
            mock_ftp = MagicMock()
            mock_ftp_class.return_value = mock_ftp
            connection._ftp = mock_ftp
            connection._connected = True
            
            # Mock directory listing
            mock_files = [
                "drwxr-xr-x   2 user group     4096 Jan 01 12:00 subdir",
                "-rw-r--r--   1 user group     1024 Jan 01 12:00 file1.txt",
                "-rw-r--r--   1 user group     2048 Jan 01 12:00 file2.txt"
            ]
            mock_ftp.nlst.return_value = ["subdir", "file1.txt", "file2.txt"]
            mock_ftp.dir.side_effect = lambda path, callback: [callback(line) for line in mock_files]
            
            files = await connection.list_directory("/remote/path")
            
            assert len(files) == 3
            assert "subdir" in [f.name for f in files]
            assert "file1.txt" in [f.name for f in files]
            assert "file2.txt" in [f.name for f in files]
    
    @pytest.mark.asyncio
    async def test_download_file(self, connection):
        """Test downloading a file."""
        with patch('ftplib.FTP') as mock_ftp_class:
            mock_ftp = MagicMock()
            mock_ftp_class.return_value = mock_ftp
            connection._ftp = mock_ftp
            connection._connected = True
            
            # Mock file download
            file_content = b"This is test file content"
            
            def mock_retrbinary(cmd, callback):
                callback(file_content)
                return "226 Transfer complete"
            
            mock_ftp.retrbinary.side_effect = mock_retrbinary
            
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file
                
                result = await connection.download_file(
                    "/remote/file.txt",
                    "/local/file.txt"
                )
                
                assert result is True
                mock_ftp.retrbinary.assert_called_once()
                mock_file.write.assert_called_once_with(file_content)
    
    @pytest.mark.asyncio
    async def test_upload_file(self, connection):
        """Test uploading a file."""
        with patch('ftplib.FTP') as mock_ftp_class:
            mock_ftp = MagicMock()
            mock_ftp_class.return_value = mock_ftp
            connection._ftp = mock_ftp
            connection._connected = True
            
            # Mock file upload
            mock_ftp.storbinary.return_value = "226 Transfer complete"
            
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_file.read.return_value = b"File content to upload"
                mock_open.return_value.__enter__.return_value = mock_file
                
                result = await connection.upload_file(
                    "/local/file.txt",
                    "/remote/file.txt"
                )
                
                assert result is True
                mock_ftp.storbinary.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_change_directory(self, connection):
        """Test changing directory."""
        with patch('ftplib.FTP') as mock_ftp_class:
            mock_ftp = MagicMock()
            mock_ftp_class.return_value = mock_ftp
            connection._ftp = mock_ftp
            connection._connected = True
            
            mock_ftp.cwd.return_value = "250 Directory changed"
            
            result = await connection.change_directory("/remote/subdir")
            
            assert result is True
            mock_ftp.cwd.assert_called_once_with("/remote/subdir")
    
    @pytest.mark.asyncio
    async def test_get_current_directory(self, connection):
        """Test getting current directory."""
        with patch('ftplib.FTP') as mock_ftp_class:
            mock_ftp = MagicMock()
            mock_ftp_class.return_value = mock_ftp
            connection._ftp = mock_ftp
            connection._connected = True
            
            mock_ftp.pwd.return_value = "/remote/current"
            
            current_dir = await connection.get_current_directory()
            
            assert current_dir == "/remote/current"
            mock_ftp.pwd.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_file_exists(self, connection):
        """Test checking if file exists."""
        with patch('ftplib.FTP') as mock_ftp_class:
            mock_ftp = MagicMock()
            mock_ftp_class.return_value = mock_ftp
            connection._ftp = mock_ftp
            connection._connected = True
            
            # Mock file exists
            mock_ftp.size.return_value = 1024
            
            exists = await connection.file_exists("/remote/file.txt")
            
            assert exists is True
            mock_ftp.size.assert_called_once_with("/remote/file.txt")
    
    @pytest.mark.asyncio
    async def test_file_not_exists(self, connection):
        """Test checking if file doesn't exist."""
        with patch('ftplib.FTP') as mock_ftp_class:
            mock_ftp = MagicMock()
            mock_ftp_class.return_value = mock_ftp
            connection._ftp = mock_ftp
            connection._connected = True
            
            # Mock file doesn't exist
            mock_ftp.size.side_effect = Exception("550 File not found")
            
            exists = await connection.file_exists("/remote/missing.txt")
            
            assert exists is False
    
    @pytest.mark.asyncio
    async def test_get_file_size(self, connection):
        """Test getting file size."""
        with patch('ftplib.FTP') as mock_ftp_class:
            mock_ftp = MagicMock()
            mock_ftp_class.return_value = mock_ftp
            connection._ftp = mock_ftp
            connection._connected = True
            
            mock_ftp.size.return_value = 2048
            
            size = await connection.get_file_size("/remote/file.txt")
            
            assert size == 2048
            mock_ftp.size.assert_called_once_with("/remote/file.txt")
    
    @pytest.mark.asyncio
    async def test_context_manager(self, connection):
        """Test using connection as context manager."""
        with patch('ftplib.FTP') as mock_ftp_class:
            mock_ftp = MagicMock()
            mock_ftp_class.return_value = mock_ftp
            
            mock_ftp.connect.return_value = None
            mock_ftp.login.return_value = "230 Login successful"
            mock_ftp.set_pasv.return_value = None
            
            async with connection:
                assert connection.is_connected is True
            
            # Should disconnect automatically
            mock_ftp.quit.assert_called_once()


class TestFTPConnectionPool:
    """Test FTP connection pool functionality."""
    
    @pytest.fixture
    def server_info(self):
        """Create FTP server info."""
        return FTPServerInfo(host="ftp.example.com", port=21)
    
    @pytest.fixture
    def credentials(self):
        """Create FTP credentials."""
        return FTPCredentials(username="testuser", password="testpass")
    
    @pytest.fixture
    def config(self):
        """Create FTP configuration."""
        return FTPConfig()
    
    @pytest.fixture
    def pool(self, server_info, credentials, config):
        """Create FTP connection pool."""
        return FTPConnectionPool(
            server_info=server_info,
            credentials=credentials,
            config=config,
            max_connections=5
        )
    
    def test_pool_initialization(self, pool):
        """Test connection pool initialization."""
        assert pool.max_connections == 5
        assert pool.active_connections == 0
        assert len(pool._available_connections) == 0
        assert len(pool._active_connections) == 0
    
    @pytest.mark.asyncio
    async def test_acquire_connection(self, pool):
        """Test acquiring connection from pool."""
        with patch('web_fetch.ftp_connection.FTPConnection') as mock_conn_class:
            mock_connection = AsyncMock()
            mock_connection.is_connected = True
            mock_conn_class.return_value = mock_connection
            
            connection = await pool.acquire()
            
            assert connection == mock_connection
            assert pool.active_connections == 1
            assert len(pool._active_connections) == 1
    
    @pytest.mark.asyncio
    async def test_release_connection(self, pool):
        """Test releasing connection back to pool."""
        with patch('web_fetch.ftp_connection.FTPConnection') as mock_conn_class:
            mock_connection = AsyncMock()
            mock_connection.is_connected = True
            mock_conn_class.return_value = mock_connection
            
            # Acquire and release
            connection = await pool.acquire()
            await pool.release(connection)
            
            assert pool.active_connections == 0
            assert len(pool._available_connections) == 1
            assert len(pool._active_connections) == 0
    
    @pytest.mark.asyncio
    async def test_pool_max_connections(self, pool):
        """Test connection pool maximum connections limit."""
        pool.max_connections = 2  # Set low limit for testing
        
        with patch('web_fetch.ftp_connection.FTPConnection') as mock_conn_class:
            mock_conn_class.side_effect = lambda *args, **kwargs: AsyncMock(is_connected=True)
            
            # Acquire maximum connections
            conn1 = await pool.acquire()
            conn2 = await pool.acquire()
            
            assert pool.active_connections == 2
            
            # Trying to acquire another should block or raise exception
            with pytest.raises(Exception):  # Pool exhausted
                await asyncio.wait_for(pool.acquire(), timeout=0.1)
    
    @pytest.mark.asyncio
    async def test_pool_cleanup(self, pool):
        """Test connection pool cleanup."""
        with patch('web_fetch.ftp_connection.FTPConnection') as mock_conn_class:
            mock_connections = [AsyncMock(is_connected=True) for _ in range(3)]
            mock_conn_class.side_effect = mock_connections
            
            # Acquire some connections
            for _ in range(3):
                await pool.acquire()
            
            # Cleanup should close all connections
            await pool.cleanup()
            
            for mock_conn in mock_connections:
                mock_conn.disconnect.assert_called_once()
            
            assert pool.active_connections == 0
    
    @pytest.mark.asyncio
    async def test_pool_context_manager(self, pool):
        """Test using pool as context manager."""
        with patch('web_fetch.ftp_connection.FTPConnection') as mock_conn_class:
            mock_connection = AsyncMock(is_connected=True)
            mock_conn_class.return_value = mock_connection
            
            async with pool.acquire_connection() as connection:
                assert connection == mock_connection
                assert pool.active_connections == 1
            
            # Should be released automatically
            assert pool.active_connections == 0
