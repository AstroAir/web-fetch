"""
Tests for the convenience functions module.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from web_fetch.convenience import (
    fetch_url,
    fetch_urls,
    download_file,
    fetch_with_cache,
    unified_fetch,
    enhanced_fetch_url,
    enhanced_fetch_urls,
)
from web_fetch.models import FetchConfig, FetchResult, BatchFetchResult, ContentType
from web_fetch.models.resource import ResourceKind, ResourceRequest


class TestConvenienceFunctions:
    """Test convenience functions for web fetching."""

    @pytest.mark.asyncio
    async def test_fetch_url_basic(self):
        """Test basic URL fetching."""
        with patch('web_fetch.convenience.WebFetcher') as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value.__aenter__.return_value = mock_fetcher

            mock_result = FetchResult(
                url="https://example.com",
                status_code=200,
                headers={"content-type": "text/html"},
                content="<html>Test</html>",
                content_type=ContentType.HTML
            )
            mock_fetcher.fetch_single.return_value = mock_result

            result = await fetch_url("https://example.com")

            assert result == mock_result
            mock_fetcher.fetch_single.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_url_with_config(self):
        """Test URL fetching with custom configuration."""
        config = FetchConfig(total_timeout=30.0, max_retries=5)

        with patch('web_fetch.convenience.WebFetcher') as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value.__aenter__.return_value = mock_fetcher

            mock_result = FetchResult(
                url="https://example.com",
                status_code=200,
                headers={},
                content="test",
                content_type=ContentType.TEXT
            )
            mock_fetcher.fetch_single.return_value = mock_result

            result = await fetch_url("https://example.com", config=config)

            assert result == mock_result
            mock_fetcher_class.assert_called_with(config)

    @pytest.mark.asyncio
    async def test_fetch_urls_batch(self):
        """Test batch URL fetching."""
        urls = ["https://example.com/1", "https://example.com/2"]

        with patch('web_fetch.convenience.WebFetcher') as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value.__aenter__.return_value = mock_fetcher

            mock_result = BatchFetchResult(
                results=[
                    FetchResult(url=urls[0], status_code=200, headers={}, content="test1", content_type=ContentType.TEXT),
                    FetchResult(url=urls[1], status_code=200, headers={}, content="test2", content_type=ContentType.TEXT)
                ],
                total_requests=2,
                successful_requests=2,
                failed_requests=0,
                total_time=1.0
            )
            mock_fetcher.fetch_batch.return_value = mock_result

            result = await fetch_urls(urls)

            assert result == mock_result
            mock_fetcher.fetch_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_file(self):
        """Test file download functionality."""
        with patch('web_fetch.convenience.WebFetcher') as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value.__aenter__.return_value = mock_fetcher

            mock_result = FetchResult(
                url="https://example.com/file.pdf",
                status_code=200,
                headers={"content-type": "application/pdf"},
                content=b"PDF content",
                content_type=ContentType.BINARY
            )
            mock_fetcher.fetch_single.return_value = mock_result

            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file

                result = await download_file("https://example.com/file.pdf", Path("/tmp/file.pdf"))

                assert result == mock_result
                mock_file.write.assert_called_once_with(b"PDF content")

    @pytest.mark.asyncio
    async def test_unified_fetch(self):
        """Test unified fetch functionality."""
        with patch('web_fetch.convenience.ResourceManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager_class.return_value = mock_manager

            mock_result = MagicMock()
            mock_manager.fetch_resource.return_value = mock_result

            request = ResourceRequest(
                uri="https://example.com/api",
                kind=ResourceKind.HTTP
            )

            result = await unified_fetch(request)

            assert result == mock_result
            mock_manager.fetch_resource.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_fetch_with_cache(self):
        """Test cached fetching functionality."""
        with patch('web_fetch.convenience.WebFetcher') as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value.__aenter__.return_value = mock_fetcher

            # Mock cache behavior
            mock_fetcher.cache = MagicMock()
            mock_fetcher.cache.get.return_value = None  # Cache miss

            mock_result = FetchResult(
                url="https://example.com",
                status_code=200,
                headers={},
                content="test",
                content_type=ContentType.TEXT
            )
            mock_fetcher.fetch_single.return_value = mock_result

            result = await fetch_with_cache("https://example.com")

            assert result == mock_result


class TestFetchUrlAdvanced:
    """Advanced tests for fetch_url function."""

    @pytest.mark.asyncio
    async def test_fetch_url_different_content_types(self):
        """Test fetch_url with different content types."""
        test_cases = [
            (ContentType.JSON, {"key": "value"}),
            (ContentType.HTML, "<html><body>Test</body></html>"),
            (ContentType.TEXT, "plain text"),
            (ContentType.XML, "<?xml version='1.0'?><root></root>"),
            (ContentType.BINARY, b"binary data"),
        ]

        for content_type, content in test_cases:
            with patch('web_fetch.convenience.WebFetcher') as mock_fetcher_class:
                mock_fetcher = AsyncMock()
                mock_fetcher_class.return_value.__aenter__.return_value = mock_fetcher

                mock_result = FetchResult(
                    url="https://example.com",
                    status_code=200,
                    headers={},
                    content=content,
                    content_type=content_type
                )
                mock_fetcher.fetch_single.return_value = mock_result

                result = await fetch_url("https://example.com", content_type=content_type)

                assert result.content_type == content_type
                assert result.content == content

    @pytest.mark.asyncio
    async def test_fetch_url_error_handling(self):
        """Test fetch_url error handling."""
        from web_fetch.exceptions import HTTPError

        with patch('web_fetch.convenience.WebFetcher') as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value.__aenter__.return_value = mock_fetcher

            # Mock fetch_single to raise an error
            mock_fetcher.fetch_single.side_effect = HTTPError("HTTP 404 Not Found")

            with pytest.raises(HTTPError, match="HTTP 404 Not Found"):
                await fetch_url("https://example.com/not-found")

    @pytest.mark.asyncio
    async def test_fetch_url_invalid_url(self):
        """Test fetch_url with invalid URL."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            await fetch_url("not-a-valid-url")

    @pytest.mark.asyncio
    async def test_fetch_url_custom_headers(self):
        """Test fetch_url with custom configuration including headers."""
        config = FetchConfig(
            total_timeout=60.0,
            max_retries=3,
            headers={"User-Agent": "TestAgent/1.0", "Authorization": "Bearer token"}
        )

        with patch('web_fetch.convenience.WebFetcher') as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value.__aenter__.return_value = mock_fetcher

            mock_result = FetchResult(
                url="https://api.example.com",
                status_code=200,
                headers={"content-type": "application/json"},
                content={"authenticated": True},
                content_type=ContentType.JSON
            )
            mock_fetcher.fetch_single.return_value = mock_result

            result = await fetch_url("https://api.example.com", ContentType.JSON, config)

            assert result == mock_result
            mock_fetcher_class.assert_called_with(config)


class TestFetchUrlsAdvanced:
    """Advanced tests for fetch_urls function."""

    @pytest.mark.asyncio
    async def test_fetch_urls_empty_list(self):
        """Test fetch_urls with empty URL list."""
        with patch('web_fetch.convenience.WebFetcher') as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value.__aenter__.return_value = mock_fetcher

            mock_result = BatchFetchResult(
                results=[],
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                total_time=0.0
            )
            mock_fetcher.fetch_batch.return_value = mock_result

            result = await fetch_urls([])

            assert result.total_requests == 0
            assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_fetch_urls_mixed_success_failure(self):
        """Test fetch_urls with mixed successful and failed requests."""
        urls = ["https://example.com/success", "https://example.com/fail"]

        with patch('web_fetch.convenience.WebFetcher') as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value.__aenter__.return_value = mock_fetcher

            mock_result = BatchFetchResult(
                results=[
                    FetchResult(url=urls[0], status_code=200, headers={}, content="success", content_type=ContentType.TEXT),
                    FetchResult(url=urls[1], status_code=404, headers={}, content=None, error="Not Found", content_type=ContentType.TEXT)
                ],
                total_requests=2,
                successful_requests=1,
                failed_requests=1,
                total_time=2.5
            )
            mock_fetcher.fetch_batch.return_value = mock_result

            result = await fetch_urls(urls)

            assert result.total_requests == 2
            assert result.successful_requests == 1
            assert result.failed_requests == 1
            assert result.success_rate == 0.5

    @pytest.mark.asyncio
    async def test_fetch_urls_large_batch(self):
        """Test fetch_urls with a large batch of URLs."""
        urls = [f"https://example.com/page{i}" for i in range(100)]

        with patch('web_fetch.convenience.WebFetcher') as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value.__aenter__.return_value = mock_fetcher

            # Create mock results for all URLs
            mock_results = [
                FetchResult(url=url, status_code=200, headers={}, content=f"content{i}", content_type=ContentType.TEXT)
                for i, url in enumerate(urls)
            ]

            mock_result = BatchFetchResult(
                results=mock_results,
                total_requests=100,
                successful_requests=100,
                failed_requests=0,
                total_time=10.0
            )
            mock_fetcher.fetch_batch.return_value = mock_result

            result = await fetch_urls(urls)

            assert result.total_requests == 100
            assert result.successful_requests == 100
            assert len(result.results) == 100


class TestDownloadFileAdvanced:
    """Advanced tests for download_file function."""

    @pytest.mark.asyncio
    async def test_download_file_binary_content(self):
        """Test downloading binary file content."""
        from web_fetch.convenience import download_file

        with patch('web_fetch.convenience.WebFetcher') as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value.__aenter__.return_value = mock_fetcher

            binary_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'  # PNG header
            mock_result = FetchResult(
                url="https://example.com/image.png",
                status_code=200,
                headers={"content-type": "image/png", "content-length": "1024"},
                content=binary_content,
                content_type=ContentType.BINARY
            )
            mock_fetcher.fetch_single.return_value = mock_result

            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file

                result = await download_file("https://example.com/image.png", Path("/tmp/image.png"))

                assert result == mock_result
                mock_file.write.assert_called_once_with(binary_content)
                mock_open.assert_called_once_with(Path("/tmp/image.png"), 'wb')

    @pytest.mark.asyncio
    async def test_download_file_text_content(self):
        """Test downloading text file content."""
        from web_fetch.convenience import download_file

        with patch('web_fetch.convenience.WebFetcher') as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value.__aenter__.return_value = mock_fetcher

            text_content = "This is a text file content"
            mock_result = FetchResult(
                url="https://example.com/document.txt",
                status_code=200,
                headers={"content-type": "text/plain"},
                content=text_content,
                content_type=ContentType.TEXT
            )
            mock_fetcher.fetch_single.return_value = mock_result

            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file

                result = await download_file("https://example.com/document.txt", Path("/tmp/document.txt"))

                assert result == mock_result
                mock_file.write.assert_called_once_with(text_content.encode('utf-8'))

    @pytest.mark.asyncio
    async def test_download_file_with_progress_callback(self):
        """Test download with progress callback."""
        from web_fetch.convenience import download_file

        progress_callback = MagicMock()

        with patch('web_fetch.convenience.WebFetcher') as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value.__aenter__.return_value = mock_fetcher

            mock_result = FetchResult(
                url="https://example.com/large-file.zip",
                status_code=200,
                headers={"content-type": "application/zip", "content-length": "10485760"},
                content=b"zip file content",
                content_type=ContentType.BINARY
            )
            mock_fetcher.fetch_single.return_value = mock_result

            with patch('builtins.open', create=True):
                result = await download_file(
                    "https://example.com/large-file.zip",
                    Path("/tmp/large-file.zip"),
                    progress_callback=progress_callback
                )

                assert result == mock_result

    @pytest.mark.asyncio
    async def test_download_file_create_directories(self):
        """Test download file creates parent directories."""
        from web_fetch.convenience import download_file

        with patch('web_fetch.convenience.WebFetcher') as mock_fetcher_class:
            mock_fetcher = AsyncMock()
            mock_fetcher_class.return_value.__aenter__.return_value = mock_fetcher

            mock_result = FetchResult(
                url="https://example.com/file.txt",
                status_code=200,
                headers={},
                content="content",
                content_type=ContentType.TEXT
            )
            mock_fetcher.fetch_single.return_value = mock_result

            with patch('builtins.open', create=True):
                with patch('pathlib.Path.mkdir') as mock_mkdir:
                    file_path = Path("/tmp/nested/dir/file.txt")

                    result = await download_file("https://example.com/file.txt", file_path)

                    assert result == mock_result
                    # Should create parent directories
                    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


class TestFetchWithCacheAdvanced:
    """Advanced tests for fetch_with_cache function."""

    @pytest.mark.asyncio
    async def test_fetch_with_cache_hit(self):
        """Test cache hit scenario."""
        from web_fetch.convenience import fetch_with_cache
        from web_fetch.models import CacheConfig

        cache_config = CacheConfig(ttl_seconds=300, max_size=100)

        with patch('web_fetch.convenience.SimpleCache') as mock_cache_class:
            mock_cache = MagicMock()
            mock_cache_class.return_value = mock_cache

            # Mock cache hit
            cached_result = FetchResult(
                url="https://example.com/cached",
                status_code=200,
                headers={},
                content="cached content",
                content_type=ContentType.TEXT
            )
            mock_cache.get.return_value = cached_result

            result = await fetch_with_cache("https://example.com/cached", cache_config=cache_config)

            assert result == cached_result
            mock_cache.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_with_cache_miss(self):
        """Test cache miss scenario."""
        from web_fetch.convenience import fetch_with_cache
        from web_fetch.models import CacheConfig

        cache_config = CacheConfig(ttl_seconds=300, max_size=100)

        with patch('web_fetch.convenience.SimpleCache') as mock_cache_class:
            mock_cache = MagicMock()
            mock_cache_class.return_value = mock_cache

            # Mock cache miss
            mock_cache.get.return_value = None

            with patch('web_fetch.convenience.fetch_url') as mock_fetch_url:
                fresh_result = FetchResult(
                    url="https://example.com/fresh",
                    status_code=200,
                    headers={},
                    content="fresh content",
                    content_type=ContentType.TEXT
                )
                mock_fetch_url.return_value = fresh_result

                result = await fetch_with_cache("https://example.com/fresh", cache_config=cache_config)

                assert result == fresh_result
                mock_cache.get.assert_called_once()
                mock_cache.set.assert_called_once()
                mock_fetch_url.assert_called_once()
