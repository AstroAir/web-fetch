"""
Shared test fixtures and configuration for the web_fetch test suite.
"""

import asyncio
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import aioresponses
from aiohttp import ClientSession

from web_fetch import FetchConfig, WebFetcher
from web_fetch.ftp import FTPConfig, FTPFetcher


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def downloads_dir(temp_dir: Path) -> Path:
    """Create a downloads directory for test files."""
    downloads = temp_dir / "downloads"
    downloads.mkdir(exist_ok=True)
    return downloads


@pytest.fixture
def sample_urls() -> list[str]:
    """Sample URLs for testing."""
    return [
        "https://httpbin.org/json",
        "https://httpbin.org/get",
        "https://httpbin.org/user-agent",
        "https://httpbin.org/headers",
    ]


@pytest.fixture
def test_config() -> FetchConfig:
    """Default test configuration for WebFetcher."""
    return FetchConfig(
        total_timeout=10.0,
        connect_timeout=5.0,
        read_timeout=5.0,
        max_concurrent_requests=5,
        max_retries=2,
        retry_delay=0.1,  # Fast retries for tests
        verify_ssl=True,
        follow_redirects=True,
    )


@pytest.fixture
async def web_fetcher(test_config: FetchConfig) -> AsyncGenerator[WebFetcher, None]:
    """Create a WebFetcher instance for testing."""
    async with WebFetcher(test_config) as fetcher:
        yield fetcher


@pytest.fixture
def ftp_config() -> FTPConfig:
    """Default test configuration for FTP operations."""
    return FTPConfig(
        host="ftp.example.com",
        port=21,
        username="testuser",
        password="testpass",
        timeout=10.0,
        max_connections=2,
    )


@pytest.fixture
async def ftp_fetcher(ftp_config: FTPConfig) -> AsyncGenerator[FTPFetcher, None]:
    """Create an FTPFetcher instance for testing."""
    async with FTPFetcher(ftp_config) as fetcher:
        yield fetcher


@pytest.fixture
def mock_aiohttp():
    """Mock aiohttp responses for testing."""
    with aioresponses.aioresponses() as m:
        yield m


@pytest.fixture
def mock_session():
    """Mock aiohttp ClientSession for testing."""
    session = AsyncMock(spec=ClientSession)
    return session


@pytest.fixture
def sample_json_response():
    """Sample JSON response data."""
    return {
        "slideshow": {
            "author": "Yours Truly",
            "date": "date of publication",
            "slides": [
                {
                    "title": "Wake up to WonderWidgets!",
                    "type": "all"
                },
                {
                    "items": [
                        "Why <em>WonderWidgets</em> are great",
                        "Who <em>buys</em> WonderWidgets"
                    ],
                    "title": "Overview",
                    "type": "all"
                }
            ],
            "title": "Sample Slide Show"
        }
    }


@pytest.fixture
def sample_html_response():
    """Sample HTML response data."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Page</title>
    </head>
    <body>
        <h1>Welcome to Test Page</h1>
        <p>This is a test paragraph.</p>
        <a href="https://example.com">Example Link</a>
        <img src="https://example.com/image.jpg" alt="Test Image">
    </body>
    </html>
    """


@pytest.fixture
def sample_text_response():
    """Sample text response data."""
    return "This is a sample text response for testing purposes."


@pytest.fixture
def sample_binary_response():
    """Sample binary response data."""
    return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"


@pytest.fixture
def mock_progress_callback():
    """Mock progress callback for testing."""
    return MagicMock()


# Markers for different test categories
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.slow = pytest.mark.slow
pytest.mark.ftp = pytest.mark.ftp
pytest.mark.http = pytest.mark.http
pytest.mark.cli = pytest.mark.cli
pytest.mark.performance = pytest.mark.performance


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test (fast, no external dependencies)"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test (requires network)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "ftp: mark test as FTP-related"
    )
    config.addinivalue_line(
        "markers", "http: mark test as HTTP-related"
    )
    config.addinivalue_line(
        "markers", "cli: mark test as CLI-related"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as performance/benchmark test"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names and paths."""
    for item in items:
        # Add markers based on test file names
        if "test_ftp" in item.nodeid:
            item.add_marker(pytest.mark.ftp)
        elif "test_cli" in item.nodeid:
            item.add_marker(pytest.mark.cli)
        elif "test_fetcher" in item.nodeid or "test_streaming" in item.nodeid:
            item.add_marker(pytest.mark.http)
        
        # Add unit marker to tests that don't require network
        if not any(marker.name in ["integration", "slow"] for marker in item.iter_markers()):
            item.add_marker(pytest.mark.unit)
        
        # Add integration marker to tests that use real network requests
        if "integration" in item.name or "real_" in item.name:
            item.add_marker(pytest.mark.integration)
        
        # Add slow marker to tests that might take longer
        if "comprehensive" in item.name or "performance" in item.name:
            item.add_marker(pytest.mark.slow)
