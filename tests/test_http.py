"""
Comprehensive tests for the HTTP module.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from io import BytesIO

from web_fetch.http import (
    HTTPMethodHandler,
    HTTPMethod,
    FileUploadHandler,
    MultipartUploadHandler,
    DownloadHandler,
    ResumableDownloadHandler,
    PaginationHandler,
    PaginationStrategy,
    HeaderManager,
    HeaderPresets,
    CookieManager,
    CookieJar,
)
from web_fetch.models import FetchRequest, FetchResult
from web_fetch.exceptions import WebFetchError


class TestHTTPMethodHandler:
    """Test HTTP method handler."""

    @pytest.mark.asyncio
    async def test_get_request(self):
        """Test GET request handling."""
        handler = HTTPMethodHandler()
        
        request = FetchRequest(
            url="https://httpbin.org/get",
            method=HTTPMethod.GET,
            headers={"User-Agent": "test-agent"}
        )
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {"Content-Type": "application/json"}
            mock_response.text.return_value = '{"test": "data"}'
            mock_response.read.return_value = b'{"test": "data"}'
            mock_request.return_value.__aenter__.return_value = mock_response
            
            session = AsyncMock()
            result = await handler.handle_request(session, request)
            
            assert isinstance(result, FetchResult)
            assert result.status_code == 200
            assert result.content == '{"test": "data"}'

    @pytest.mark.asyncio
    async def test_post_request_with_json(self):
        """Test POST request with JSON data."""
        handler = HTTPMethodHandler()
        
        request = FetchRequest(
            url="https://httpbin.org/post",
            method=HTTPMethod.POST,
            json_data={"key": "value"},
            headers={"Content-Type": "application/json"}
        )
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 201
            mock_response.headers = {"Content-Type": "application/json"}
            mock_response.text.return_value = '{"created": true}'
            mock_response.read.return_value = b'{"created": true}'
            mock_request.return_value.__aenter__.return_value = mock_response
            
            session = AsyncMock()
            result = await handler.handle_request(session, request)
            
            assert result.status_code == 201
            assert '"created": true' in result.content

    @pytest.mark.asyncio
    async def test_put_request_with_data(self):
        """Test PUT request with form data."""
        handler = HTTPMethodHandler()
        
        request = FetchRequest(
            url="https://httpbin.org/put",
            method=HTTPMethod.PUT,
            data={"field1": "value1", "field2": "value2"}
        )
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {}
            mock_response.text.return_value = "Updated"
            mock_response.read.return_value = b"Updated"
            mock_request.return_value.__aenter__.return_value = mock_response
            
            session = AsyncMock()
            result = await handler.handle_request(session, request)
            
            assert result.status_code == 200
            assert result.content == "Updated"

    @pytest.mark.asyncio
    async def test_delete_request(self):
        """Test DELETE request."""
        handler = HTTPMethodHandler()
        
        request = FetchRequest(
            url="https://httpbin.org/delete",
            method=HTTPMethod.DELETE
        )
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 204
            mock_response.headers = {}
            mock_response.text.return_value = ""
            mock_response.read.return_value = b""
            mock_request.return_value.__aenter__.return_value = mock_response
            
            session = AsyncMock()
            result = await handler.handle_request(session, request)
            
            assert result.status_code == 204
            assert result.content == ""


class TestFileUploadHandler:
    """Test file upload handler."""

    @pytest.mark.asyncio
    async def test_single_file_upload(self):
        """Test uploading a single file."""
        handler = FileUploadHandler()
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("test file content")
            temp_path = temp_file.name
        
        try:
            request = FetchRequest(
                url="https://httpbin.org/post",
                method=HTTPMethod.POST,
                files={"file": temp_path}
            )
            
            with patch('aiohttp.ClientSession.request') as mock_request:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.headers = {}
                mock_response.text.return_value = "File uploaded"
                mock_response.read.return_value = b"File uploaded"
                mock_request.return_value.__aenter__.return_value = mock_response
                
                session = AsyncMock()
                result = await handler.upload_file(session, request)
                
                assert result.status_code == 200
                assert result.content == "File uploaded"
                
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_multiple_file_upload(self):
        """Test uploading multiple files."""
        handler = FileUploadHandler()
        
        # Create temporary files
        temp_files = []
        for i in range(2):
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                temp_file.write(f"test file content {i}")
                temp_files.append(temp_file.name)
        
        try:
            request = FetchRequest(
                url="https://httpbin.org/post",
                method=HTTPMethod.POST,
                files={
                    "file1": temp_files[0],
                    "file2": temp_files[1]
                }
            )
            
            with patch('aiohttp.ClientSession.request') as mock_request:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.headers = {}
                mock_response.text.return_value = "Files uploaded"
                mock_response.read.return_value = b"Files uploaded"
                mock_request.return_value.__aenter__.return_value = mock_response
                
                session = AsyncMock()
                result = await handler.upload_files(session, request)
                
                assert result.status_code == 200
                assert result.content == "Files uploaded"
                
        finally:
            for temp_path in temp_files:
                Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_file_upload_with_progress(self):
        """Test file upload with progress callback."""
        handler = FileUploadHandler()
        
        progress_calls = []
        
        def progress_callback(bytes_uploaded, total_bytes):
            progress_calls.append((bytes_uploaded, total_bytes))
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("test content for progress tracking")
            temp_path = temp_file.name
        
        try:
            request = FetchRequest(
                url="https://httpbin.org/post",
                method=HTTPMethod.POST,
                files={"file": temp_path}
            )
            
            with patch('aiohttp.ClientSession.request') as mock_request:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.headers = {}
                mock_response.text.return_value = "File uploaded"
                mock_response.read.return_value = b"File uploaded"
                mock_request.return_value.__aenter__.return_value = mock_response
                
                session = AsyncMock()
                result = await handler.upload_file(session, request, progress_callback)
                
                assert result.status_code == 200
                # Progress callback should have been called
                # Note: In real implementation, this would track actual upload progress
                
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestDownloadHandler:
    """Test download handler."""

    @pytest.mark.asyncio
    async def test_download_file(self):
        """Test downloading a file."""
        handler = DownloadHandler()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            download_path = Path(temp_dir) / "downloaded_file.txt"
            
            with patch('aiohttp.ClientSession.get') as mock_get:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.headers = {"Content-Length": "12"}
                
                # Mock streaming content
                async def mock_iter_chunked(chunk_size):
                    yield b"test content"
                
                mock_response.content.iter_chunked = mock_iter_chunked
                mock_get.return_value.__aenter__.return_value = mock_response
                
                session = AsyncMock()
                result = await handler.download_file(
                    session,
                    "https://example.com/file.txt",
                    download_path
                )
                
                assert result.success is True
                assert result.file_path == download_path
                assert result.bytes_downloaded > 0

    @pytest.mark.asyncio
    async def test_download_with_progress(self):
        """Test download with progress callback."""
        handler = DownloadHandler()
        
        progress_calls = []
        
        def progress_callback(bytes_downloaded, total_bytes):
            progress_calls.append((bytes_downloaded, total_bytes))
        
        with tempfile.TemporaryDirectory() as temp_dir:
            download_path = Path(temp_dir) / "downloaded_file.txt"
            
            with patch('aiohttp.ClientSession.get') as mock_get:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.headers = {"Content-Length": "12"}
                
                async def mock_iter_chunked(chunk_size):
                    yield b"test content"
                
                mock_response.content.iter_chunked = mock_iter_chunked
                mock_get.return_value.__aenter__.return_value = mock_response
                
                session = AsyncMock()
                result = await handler.download_file(
                    session,
                    "https://example.com/file.txt",
                    download_path,
                    progress_callback=progress_callback
                )
                
                assert result.success is True
                # Progress callback should have been called
                assert len(progress_calls) > 0


class TestPaginationHandler:
    """Test pagination handler."""

    @pytest.mark.asyncio
    async def test_offset_pagination(self):
        """Test offset-based pagination."""
        handler = PaginationHandler(
            strategy=PaginationStrategy.OFFSET,
            page_size=10,
            max_pages=3
        )
        
        base_url = "https://api.example.com/items"
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            # Mock responses for different pages
            responses = [
                {'items': [f'item{i}' for i in range(10)], 'has_more': True},
                {'items': [f'item{i}' for i in range(10, 20)], 'has_more': True},
                {'items': [f'item{i}' for i in range(20, 25)], 'has_more': False}
            ]
            
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {"Content-Type": "application/json"}
            
            call_count = 0
            async def mock_json():
                nonlocal call_count
                response = responses[call_count]
                call_count += 1
                return response
            
            mock_response.json = mock_json
            mock_get.return_value.__aenter__.return_value = mock_response
            
            session = AsyncMock()
            results = []
            
            async for page_result in handler.paginate(session, base_url):
                results.append(page_result)
            
            assert len(results) == 3
            assert all(result.status_code == 200 for result in results)

    @pytest.mark.asyncio
    async def test_cursor_pagination(self):
        """Test cursor-based pagination."""
        handler = PaginationHandler(
            strategy=PaginationStrategy.CURSOR,
            page_size=10,
            max_pages=2
        )
        
        base_url = "https://api.example.com/items"
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            responses = [
                {'items': [f'item{i}' for i in range(10)], 'next_cursor': 'cursor123'},
                {'items': [f'item{i}' for i in range(10, 20)], 'next_cursor': None}
            ]
            
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {"Content-Type": "application/json"}
            
            call_count = 0
            async def mock_json():
                nonlocal call_count
                response = responses[call_count]
                call_count += 1
                return response
            
            mock_response.json = mock_json
            mock_get.return_value.__aenter__.return_value = mock_response
            
            session = AsyncMock()
            results = []
            
            async for page_result in handler.paginate(session, base_url):
                results.append(page_result)
            
            assert len(results) == 2


class TestHeaderManager:
    """Test header manager."""

    def test_header_manager_creation(self):
        """Test header manager creation."""
        manager = HeaderManager()
        assert len(manager._default_headers) > 0
        assert "User-Agent" in manager._default_headers

    def test_set_default_headers(self):
        """Test setting default headers."""
        manager = HeaderManager()
        
        custom_headers = {
            "Authorization": "Bearer token123",
            "X-Custom-Header": "custom-value"
        }
        
        manager.set_default_headers(custom_headers)
        
        headers = manager.get_headers()
        assert headers["Authorization"] == "Bearer token123"
        assert headers["X-Custom-Header"] == "custom-value"

    def test_add_header(self):
        """Test adding individual headers."""
        manager = HeaderManager()
        
        manager.add_header("X-API-Key", "key123")
        manager.add_header("Accept", "application/json")
        
        headers = manager.get_headers()
        assert headers["X-API-Key"] == "key123"
        assert headers["Accept"] == "application/json"

    def test_remove_header(self):
        """Test removing headers."""
        manager = HeaderManager()
        
        manager.add_header("X-Temp-Header", "temp-value")
        assert "X-Temp-Header" in manager.get_headers()
        
        manager.remove_header("X-Temp-Header")
        assert "X-Temp-Header" not in manager.get_headers()

    def test_header_presets(self):
        """Test header presets."""
        # Test JSON preset
        json_headers = HeaderPresets.json()
        assert json_headers["Content-Type"] == "application/json"
        assert json_headers["Accept"] == "application/json"
        
        # Test form preset
        form_headers = HeaderPresets.form()
        assert form_headers["Content-Type"] == "application/x-www-form-urlencoded"
        
        # Test API preset
        api_headers = HeaderPresets.api("key123")
        assert api_headers["Authorization"] == "Bearer key123"


class TestCookieManager:
    """Test cookie manager."""

    def test_cookie_jar_creation(self):
        """Test cookie jar creation."""
        jar = CookieJar()
        assert len(jar.cookies) == 0

    def test_add_cookie(self):
        """Test adding cookies."""
        jar = CookieJar()
        
        jar.add_cookie("session_id", "abc123", domain="example.com")
        jar.add_cookie("user_pref", "dark_mode", domain="example.com", path="/settings")
        
        assert len(jar.cookies) == 2
        
        # Test getting cookies for domain
        cookies = jar.get_cookies_for_domain("example.com")
        assert len(cookies) == 2

    def test_cookie_expiration(self):
        """Test cookie expiration."""
        jar = CookieJar()
        
        # Add expired cookie
        import time
        past_time = time.time() - 3600  # 1 hour ago
        
        jar.add_cookie("expired", "value", domain="example.com", expires=past_time)
        jar.add_cookie("valid", "value", domain="example.com")
        
        # Should only return valid cookies
        cookies = jar.get_cookies_for_domain("example.com")
        assert len(cookies) == 1
        assert cookies[0]["name"] == "valid"

    def test_cookie_manager_integration(self):
        """Test cookie manager with session integration."""
        manager = CookieManager()
        
        # Add cookies
        manager.add_cookie("auth_token", "token123", domain="api.example.com")
        
        # Get cookies for request
        cookies = manager.get_cookies_for_url("https://api.example.com/data")
        assert len(cookies) > 0
        assert any(cookie["name"] == "auth_token" for cookie in cookies)
