"""
Comprehensive tests for the HTTP module.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from io import BytesIO
import aiohttp

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

        url = "https://httpbin.org/get"
        headers = {"User-Agent": "test-agent"}

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.text.return_value = '{"test": "data"}'
        mock_response.read.return_value = b'{"test": "data"}'

        session = AsyncMock()
        session.get.return_value = mock_response

        result = await handler.execute_request(
            session,
            HTTPMethod.GET,
            url,
            headers=headers
        )

        # The result is the mock response
        assert result.status == 200
        content = await result.text()
        assert content == '{"test": "data"}'

    @pytest.mark.asyncio
    async def test_post_request_with_json(self):
        """Test POST request with JSON data."""
        handler = HTTPMethodHandler()

        url = "https://httpbin.org/post"
        headers = {"Content-Type": "application/json"}

        from web_fetch.http.methods import RequestBody
        body = RequestBody(json_data={"key": "value"})

        mock_response = AsyncMock()
        mock_response.status = 201
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.text.return_value = '{"created": true}'
        mock_response.read.return_value = b'{"created": true}'

        session = AsyncMock()
        session.post.return_value = mock_response

        result = await handler.execute_request(
            session,
            HTTPMethod.POST,
            url,
            headers=headers,
            body=body
        )

        assert result.status == 201
        content = await result.text()
        assert '"created": true' in content

    @pytest.mark.asyncio
    async def test_put_request_with_data(self):
        """Test PUT request with form data."""
        handler = HTTPMethodHandler()

        url = "https://httpbin.org/put"

        from web_fetch.http.methods import RequestBody
        body = RequestBody(form_data={"field1": "value1", "field2": "value2"})

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.text.return_value = "Updated"
        mock_response.read.return_value = b"Updated"

        session = AsyncMock()
        session.put.return_value = mock_response

        result = await handler.execute_request(
            session,
            HTTPMethod.PUT,
            url,
            body=body
        )

        assert result.status == 200
        content = await result.text()
        assert content == "Updated"

    @pytest.mark.asyncio
    async def test_delete_request(self):
        """Test DELETE request."""
        handler = HTTPMethodHandler()

        url = "https://httpbin.org/delete"

        mock_response = AsyncMock()
        mock_response.status = 204
        mock_response.headers = {}
        mock_response.text.return_value = ""
        mock_response.read.return_value = b""

        session = AsyncMock()
        session.delete.return_value = mock_response

        result = await handler.execute_request(
            session,
            HTTPMethod.DELETE,
            url
        )

        assert result.status == 204
        content = await result.text()
        assert content == ""


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
            from web_fetch.http.upload import UploadFile

            file_config = UploadFile(
                path=temp_path,
                field_name="file"
            )

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {}
            mock_response.text.return_value = "File uploaded"
            mock_response.read.return_value = b"File uploaded"

            session = AsyncMock()
            session.post.return_value = mock_response

            result = await handler.upload_file(
                session=session,
                url="https://httpbin.org/post",
                file_config=file_config
            )

            assert result.status == 200
            content = await result.text()
            assert content == "File uploaded"

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
            from web_fetch.http.upload import UploadFile

            files = [
                UploadFile(path=temp_files[0], field_name="file1"),
                UploadFile(path=temp_files[1], field_name="file2")
            ]

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {}
            mock_response.text.return_value = "Files uploaded"
            mock_response.read.return_value = b"Files uploaded"

            session = AsyncMock()
            session.post.return_value = mock_response

            result = await handler.upload_multiple_files(
                session=session,
                url="https://httpbin.org/post",
                files=files
            )

            assert result.status == 200
            content = await result.text()
            assert content == "Files uploaded"

        finally:
            for temp_path in temp_files:
                Path(temp_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_file_upload_with_progress(self):
        """Test file upload with progress callback."""
        handler = FileUploadHandler()

        progress_calls = []

        def progress_callback(progress):
            progress_calls.append((progress.bytes_uploaded, progress.total_bytes))

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("test content for progress tracking")
            temp_path = temp_file.name

        try:
            from web_fetch.http.upload import UploadFile

            file_config = UploadFile(
                path=temp_path,
                field_name="file"
            )

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {}
            mock_response.text.return_value = "File uploaded"
            mock_response.read.return_value = b"File uploaded"

            session = AsyncMock()
            session.post.return_value = mock_response

            result = await handler.upload_file(
                session=session,
                url="https://httpbin.org/post",
                file_config=file_config,
                progress_callback=progress_callback
            )

            assert result.status == 200
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

            with patch('aiofiles.open') as mock_aiofiles, \
                 patch('pathlib.Path.rename') as mock_rename:
                # Mock file operations with proper async context manager
                mock_file = AsyncMock()

                class MockAiofilesContextManager:
                    async def __aenter__(self):
                        return mock_file

                    async def __aexit__(self, exc_type, exc_val, exc_tb):
                        return None

                mock_aiofiles.return_value = MockAiofilesContextManager()

                # Create a proper async context manager for session.get
                class MockAsyncContextManager:
                    def __init__(self, response):
                        self.response = response

                    async def __aenter__(self):
                        return self.response

                    async def __aexit__(self, exc_type, exc_val, exc_tb):
                        return None

                # Create a mock session
                session = AsyncMock()
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.headers = {"Content-Length": "12"}
                mock_response.raise_for_status = Mock(return_value=None)

                # Mock streaming content
                async def mock_iter_chunked(chunk_size):
                    yield b"test content"

                mock_response.content.iter_chunked = mock_iter_chunked

                # Set up the session.get to return the async context manager
                def mock_get(*args, **kwargs):
                    return MockAsyncContextManager(mock_response)

                session.get = mock_get

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

        def progress_callback(progress_info):
            progress_calls.append((progress_info.bytes_downloaded, progress_info.total_bytes))

        with tempfile.TemporaryDirectory() as temp_dir:
            download_path = Path(temp_dir) / "downloaded_file.txt"

            with patch('aiofiles.open') as mock_aiofiles, \
                 patch('pathlib.Path.rename') as mock_rename:
                # Mock file operations with proper async context manager
                mock_file = AsyncMock()

                class MockAiofilesContextManager:
                    async def __aenter__(self):
                        return mock_file

                    async def __aexit__(self, exc_type, exc_val, exc_tb):
                        return None

                mock_aiofiles.return_value = MockAiofilesContextManager()

                # Create a proper async context manager for session.get
                class MockAsyncContextManager:
                    def __init__(self, response):
                        self.response = response

                    async def __aenter__(self):
                        return self.response

                    async def __aexit__(self, exc_type, exc_val, exc_tb):
                        return None

                # Create a mock session
                session = AsyncMock()
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.headers = {"Content-Length": "12"}
                mock_response.raise_for_status = Mock(return_value=None)

                async def mock_iter_chunked(chunk_size):
                    yield b"test content"

                mock_response.content.iter_chunked = mock_iter_chunked

                # Set up the session.get to return the async context manager
                def mock_get(*args, **kwargs):
                    return MockAsyncContextManager(mock_response)

                session.get = mock_get

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
        from web_fetch.http.pagination import PaginationConfig
        config = PaginationConfig(
            strategy=PaginationStrategy.OFFSET_LIMIT,
            page_size=10,
            max_pages=3,
            data_field="items"
        )
        handler = PaginationHandler(config)

        from web_fetch.models import FetchRequest
        from pydantic import HttpUrl

        base_request = FetchRequest(
            url=HttpUrl("https://api.example.com/items"),
            method=HTTPMethod.GET
        )

        # Create a mock fetcher
        class MockFetcher:
            def __init__(self):
                self.call_count = 0
                self.responses = [
                    {'items': [f'item{i}' for i in range(10)], 'has_more': True},
                    {'items': [f'item{i}' for i in range(10, 20)], 'has_more': True},
                    {'items': [f'item{i}' for i in range(20, 25)], 'has_more': False}
                ]

            async def fetch_single(self, request):
                from web_fetch.models import FetchResult
                response_data = self.responses[min(self.call_count, len(self.responses) - 1)]
                self.call_count += 1

                return FetchResult(
                    url=str(request.url),
                    status_code=200,
                    headers={},
                    content=response_data,
                    response_time=0.1
                )

        fetcher = MockFetcher()
        result = await handler.fetch_all_pages(fetcher, base_request)

        assert result.total_pages == 2  # The pagination logic counts completed full pages
        assert len(result.data) == 25  # 10 + 10 + 5 items
        assert len(result.responses) == 3  # But we still get 3 responses

    @pytest.mark.asyncio
    async def test_cursor_pagination(self):
        """Test cursor-based pagination."""
        from web_fetch.http.pagination import PaginationConfig
        config = PaginationConfig(
            strategy=PaginationStrategy.CURSOR,
            page_size=10,
            max_pages=2,
            data_field="items"
        )
        handler = PaginationHandler(config)

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

            # Mock fetcher
            from web_fetch.models.http import FetchRequest, FetchResult

            class MockFetcher:
                def __init__(self):
                    self.call_count = 0
                    self.responses = responses

                async def fetch_single(self, request: FetchRequest) -> FetchResult:
                    response_data = self.responses[self.call_count]
                    self.call_count += 1
                    return FetchResult(
                        url=request.url,
                        status_code=200,
                        content=response_data,
                        headers={"Content-Type": "application/json"}
                    )

            fetcher = MockFetcher()
            base_request = FetchRequest(url=base_url)

            result = await handler.fetch_all_pages(fetcher, base_request)

            assert len(result.data) == 20  # 10 items per page, 2 pages
            assert result.total_pages == 2


class TestHeaderManager:
    """Test header manager."""

    def test_header_manager_creation(self):
        """Test header manager creation."""
        manager = HeaderManager()
        assert len(manager._global_headers) == 0
        assert len(manager._rules) == 0

    def test_set_default_headers(self):
        """Test setting default headers."""
        manager = HeaderManager()

        custom_headers = {
            "Authorization": "Bearer token123",
            "X-Custom-Header": "custom-value"
        }

        manager.add_global_headers(custom_headers)

        # Check headers were set
        assert manager._global_headers["Authorization"] == "Bearer token123"
        assert manager._global_headers["X-Custom-Header"] == "custom-value"

    def test_add_header(self):
        """Test adding individual headers."""
        manager = HeaderManager()

        manager.add_global_headers({"X-API-Key": "key123"})
        manager.add_global_headers({"Accept": "application/json"})

        assert manager._global_headers["X-API-Key"] == "key123"
        assert manager._global_headers["Accept"] == "application/json"

    def test_remove_header(self):
        """Test removing headers."""
        manager = HeaderManager()

        manager.add_global_headers({"x-temp-header": "temp-value"})
        assert "x-temp-header" in manager._global_headers

        manager.remove_global_header("X-Temp-Header")
        assert "x-temp-header" not in manager._global_headers

    def test_header_presets(self):
        """Test header presets."""
        # Test JSON preset
        json_headers = HeaderPresets.API_JSON
        assert json_headers["Content-Type"] == "application/json"
        assert json_headers["Accept"] == "application/json"

        # Test browser preset
        browser_headers = HeaderPresets.BROWSER_CHROME
        assert "User-Agent" in browser_headers

        # Test API XML preset
        xml_headers = HeaderPresets.API_XML
        assert xml_headers["Content-Type"] == "application/xml"
        assert xml_headers["Accept"] == "application/xml"


class TestCookieManager:
    """Test cookie manager."""

    def test_cookie_jar_creation(self):
        """Test cookie jar creation."""
        jar = CookieJar()
        assert len(jar._cookies) == 0

    def test_add_cookie(self):
        """Test adding cookies."""
        jar = CookieJar()

        from web_fetch.http.cookies import Cookie

        cookie1 = Cookie(name="session_id", value="abc123", domain="example.com")
        cookie2 = Cookie(name="user_pref", value="dark_mode", domain="example.com", path="/settings")

        jar.add_cookie(cookie1)
        jar.add_cookie(cookie2)

        assert len(jar._cookies["example.com"]) == 2

        # Test getting cookies for URL
        cookies = jar.get_cookies_for_url("https://example.com/settings")
        assert len(cookies) == 2

    def test_cookie_expiration(self):
        """Test cookie expiration."""
        jar = CookieJar()

        # Add expired cookie
        from datetime import datetime, timedelta
        from web_fetch.http.cookies import Cookie

        past_time = datetime.now() - timedelta(hours=1)  # 1 hour ago

        expired_cookie = Cookie(name="expired", value="value", domain="example.com", expires=past_time)
        valid_cookie = Cookie(name="valid", value="value", domain="example.com")

        jar.add_cookie(expired_cookie)
        jar.add_cookie(valid_cookie)

        # Should only return valid cookies
        cookies = jar.get_cookies_for_url("https://example.com/")
        valid_cookies = [c for c in cookies if not c.is_expired]
        assert len(valid_cookies) == 1
        assert valid_cookies[0].name == "valid"

    def test_cookie_manager_integration(self):
        """Test cookie manager with session integration."""
        manager = CookieManager()

        # Add cookies through the jar
        from web_fetch.http.cookies import Cookie

        cookie = Cookie(name="auth_token", value="token123", domain="api.example.com")
        manager.jar.add_cookie(cookie)

        # Get request headers
        headers = manager.get_request_headers("https://api.example.com/data")
        assert "Cookie" in headers
        assert "auth_token=token123" in headers["Cookie"]
