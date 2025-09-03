"""
Comprehensive tests for HTTP models in web_fetch.models.http module.

Tests all HTTP-specific models, configurations, and data structures.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from pydantic import ValidationError

from web_fetch.models.http import (
    FetchConfig,
    FetchRequest,
    FetchResult,
    BatchFetchRequest,
    BatchFetchResult,
    StreamingConfig,
    StreamRequest,
    StreamResult,
    CacheConfig,
    CacheEntry,
    RateLimitConfig,
    RateLimitState,
    URLAnalysis,
    HeaderAnalysis,
    SessionConfig,
    SessionData,
)
from web_fetch.models.base import (
    ContentType,
    RetryStrategy,
    RequestHeaders,
    PDFMetadata,
    ImageMetadata,
    FeedMetadata,
    FeedItem,
    CSVMetadata,
    LinkInfo,
    ContentSummary,
)


class TestFetchConfig:
    """Test FetchConfig model."""

    def test_default_config(self):
        """Test default fetch configuration."""
        config = FetchConfig()

        # Timeout settings
        assert config.total_timeout == 30.0
        assert config.connect_timeout == 10.0
        assert config.read_timeout == 20.0

        # Concurrency settings
        assert config.max_concurrent_requests == 10
        assert config.max_connections_per_host == 5

        # Retry settings
        assert config.retry_strategy == RetryStrategy.EXPONENTIAL
        assert config.max_retries == 3
        assert config.retry_delay == 1.0

        # Content settings
        assert config.max_response_size == 10 * 1024 * 1024  # 10MB
        assert config.follow_redirects is True
        assert config.verify_ssl is True

        # Headers
        assert isinstance(config.headers, RequestHeaders)

    def test_custom_config(self):
        """Test custom fetch configuration."""
        custom_headers = RequestHeaders(
            user_agent="Custom Agent",
            custom_headers={"X-API-Key": "secret"}
        )

        config = FetchConfig(
            total_timeout=60.0,
            connect_timeout=15.0,
            read_timeout=45.0,
            max_concurrent_requests=20,
            max_connections_per_host=10,
            retry_strategy=RetryStrategy.LINEAR,
            max_retries=5,
            retry_delay=2.0,
            max_response_size=50 * 1024 * 1024,  # 50MB
            follow_redirects=False,
            verify_ssl=False,
            headers=custom_headers
        )

        assert config.total_timeout == 60.0
        assert config.connect_timeout == 15.0
        assert config.read_timeout == 45.0
        assert config.max_concurrent_requests == 20
        assert config.max_connections_per_host == 10
        assert config.retry_strategy == RetryStrategy.LINEAR
        assert config.max_retries == 5
        assert config.retry_delay == 2.0
        assert config.max_response_size == 50 * 1024 * 1024
        assert config.follow_redirects is False
        assert config.verify_ssl is False
        assert config.headers == custom_headers

    def test_timeout_validation(self):
        """Test timeout validation."""
        # Valid timeouts
        FetchConfig(total_timeout=0.1, connect_timeout=0.1, read_timeout=0.1)

        # Invalid timeouts
        with pytest.raises(ValidationError):
            FetchConfig(total_timeout=0.0)

        with pytest.raises(ValidationError):
            FetchConfig(connect_timeout=-1.0)

        with pytest.raises(ValidationError):
            FetchConfig(read_timeout=0.0)

    def test_concurrency_validation(self):
        """Test concurrency validation."""
        # Valid values
        FetchConfig(max_concurrent_requests=1, max_connections_per_host=1)
        FetchConfig(max_concurrent_requests=100, max_connections_per_host=20)

        # Invalid max_concurrent_requests
        with pytest.raises(ValidationError):
            FetchConfig(max_concurrent_requests=0)

        with pytest.raises(ValidationError):
            FetchConfig(max_concurrent_requests=101)

        # Invalid max_connections_per_host
        with pytest.raises(ValidationError):
            FetchConfig(max_connections_per_host=0)

        with pytest.raises(ValidationError):
            FetchConfig(max_connections_per_host=21)

    def test_retry_validation(self):
        """Test retry validation."""
        # Valid values
        FetchConfig(max_retries=0, retry_delay=0.1)
        FetchConfig(max_retries=10, retry_delay=60.0)

        # Invalid max_retries
        with pytest.raises(ValidationError):
            FetchConfig(max_retries=-1)

        with pytest.raises(ValidationError):
            FetchConfig(max_retries=11)

        # Invalid retry_delay
        with pytest.raises(ValidationError):
            FetchConfig(retry_delay=0.05)

        with pytest.raises(ValidationError):
            FetchConfig(retry_delay=61.0)

    def test_response_size_validation(self):
        """Test response size validation."""
        # Valid size
        FetchConfig(max_response_size=1)

        # Invalid size
        with pytest.raises(ValidationError):
            FetchConfig(max_response_size=0)

        with pytest.raises(ValidationError):
            FetchConfig(max_response_size=-1)


class TestFetchRequest:
    """Test FetchRequest model."""

    def test_basic_request(self):
        """Test basic fetch request."""
        request = FetchRequest(url="https://example.com")

        assert str(request.url) == "https://example.com/"
        assert request.method == "GET"
        assert request.headers is None
        assert request.data is None
        assert request.params is None
        assert request.content_type == ContentType.RAW
        assert request.timeout_override is None

    def test_post_request(self):
        """Test POST request with data."""
        headers = {"Content-Type": "application/json", "Authorization": "Bearer token"}
        data = {"name": "John", "email": "john@example.com"}

        request = FetchRequest(
            url="https://api.example.com/users",
            method="POST",
            headers=headers,
            data=data,
            content_type=ContentType.JSON,
            timeout_override=30.0
        )

        assert request.method == "POST"
        assert request.headers == headers
        assert request.data == data
        assert request.content_type == ContentType.JSON
        assert request.timeout_override == 30.0

    def test_request_with_params(self):
        """Test request with query parameters."""
        params = {"q": "search term", "page": "1", "limit": "10"}

        request = FetchRequest(
            url="https://api.example.com/search",
            params=params,
            content_type=ContentType.JSON
        )

        assert request.params == params
        assert request.content_type == ContentType.JSON

    def test_url_validation(self):
        """Test URL validation."""
        # Valid URLs
        FetchRequest(url="https://example.com")
        FetchRequest(url="http://localhost:8080/path")
        FetchRequest(url="https://api.example.com/v1/data?param=value")

        # Invalid URLs - non-HTTP schemes should be rejected
        with pytest.raises(ValidationError):
            FetchRequest(url="ftp://example.com")

        with pytest.raises(ValidationError):
            FetchRequest(url="file:///path/to/file")

    def test_method_validation(self):
        """Test HTTP method validation."""
        valid_methods = ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH"]

        for method in valid_methods:
            request = FetchRequest(url="https://example.com", method=method)
            assert request.method == method

        # Invalid method
        with pytest.raises(ValidationError):
            FetchRequest(url="https://example.com", method="INVALID")

        with pytest.raises(ValidationError):
            FetchRequest(url="https://example.com", method="get")  # lowercase

    def test_timeout_override_validation(self):
        """Test timeout override validation."""
        # Valid timeout
        FetchRequest(url="https://example.com", timeout_override=10.5)

        # Invalid timeout
        with pytest.raises(ValidationError):
            FetchRequest(url="https://example.com", timeout_override=0.0)

        with pytest.raises(ValidationError):
            FetchRequest(url="https://example.com", timeout_override=-5.0)

    def test_data_types(self):
        """Test different data types for request body."""
        # String data
        request1 = FetchRequest(
            url="https://example.com",
            method="POST",
            data="raw string data"
        )
        assert request1.data == "raw string data"

        # Bytes data
        request2 = FetchRequest(
            url="https://example.com",
            method="POST",
            data=b"binary data"
        )
        assert request2.data == b"binary data"

        # Dictionary data (will be JSON-encoded)
        request3 = FetchRequest(
            url="https://example.com",
            method="POST",
            data={"key": "value", "number": 42}
        )
        assert request3.data == {"key": "value", "number": 42}


class TestFetchResult:
    """Test FetchResult dataclass."""

    def test_basic_result(self):
        """Test basic fetch result."""
        result = FetchResult(url="https://example.com")

        assert result.url == "https://example.com"
        assert isinstance(result.timestamp, datetime)
        assert result.response_time == 0.0
        assert result.error is None
        assert result.retry_count == 0
        assert result.status_code == 0
        assert result.headers == {}
        assert result.content is None
        assert result.content_type == ContentType.RAW

    def test_successful_result(self):
        """Test successful HTTP result."""
        headers = {"Content-Type": "application/json", "Content-Length": "100"}
        content = {"message": "success", "data": [1, 2, 3]}

        result = FetchResult(
            url="https://api.example.com/data",
            status_code=200,
            headers=headers,
            content=content,
            content_type=ContentType.JSON,
            response_time=1.5
        )

        assert result.status_code == 200
        assert result.headers == headers
        assert result.content == content
        assert result.content_type == ContentType.JSON
        assert result.response_time == 1.5
        assert result.is_success is True
        assert result.is_client_error is False
        assert result.is_server_error is False

    def test_client_error_result(self):
        """Test client error result."""
        result = FetchResult(
            url="https://api.example.com/notfound",
            status_code=404,
            headers={"Content-Type": "text/plain"},
            content="Not Found",
            error="Resource not found",
            response_time=0.5
        )

        assert result.status_code == 404
        assert result.error == "Resource not found"
        assert result.is_success is False
        assert result.is_client_error is True
        assert result.is_server_error is False

    def test_server_error_result(self):
        """Test server error result."""
        result = FetchResult(
            url="https://api.example.com/error",
            status_code=500,
            headers={},
            content=None,
            error="Internal Server Error",
            response_time=2.0
        )

        assert result.status_code == 500
        assert result.error == "Internal Server Error"
        assert result.is_success is False
        assert result.is_client_error is False
        assert result.is_server_error is True

    def test_result_with_metadata(self):
        """Test result with various metadata types."""
        pdf_metadata = PDFMetadata(title="Test PDF", page_count=10)
        image_metadata = ImageMetadata(format="JPEG", width=1920, height=1080)
        feed_metadata = FeedMetadata(title="Test Feed", item_count=5)
        feed_items = [FeedItem(title="Item 1"), FeedItem(title="Item 2")]
        csv_metadata = CSVMetadata(row_count=100, column_count=5)
        links = [LinkInfo(url="https://link1.com"), LinkInfo(url="https://link2.com")]
        content_summary = ContentSummary(word_count=500, reading_time_minutes=2.5)

        result = FetchResult(
            url="https://example.com/document",
            status_code=200,
            content="Document content",
            pdf_metadata=pdf_metadata,
            image_metadata=image_metadata,
            feed_metadata=feed_metadata,
            feed_items=feed_items,
            csv_metadata=csv_metadata,
            links=links,
            content_summary=content_summary,
            extracted_text="Extracted text content",
            structured_data={"key": "value"}
        )

        assert result.pdf_metadata == pdf_metadata
        assert result.image_metadata == image_metadata
        assert result.feed_metadata == feed_metadata
        assert result.feed_items == feed_items
        assert result.csv_metadata == csv_metadata
        assert result.links == links
        assert result.content_summary == content_summary
        assert result.extracted_text == "Extracted text content"
        assert result.structured_data == {"key": "value"}
        assert result.has_metadata is True

    def test_metadata_summary(self):
        """Test metadata summary generation."""
        pdf_metadata = PDFMetadata(title="Test PDF", author="Test Author", page_count=10, text_length=5000)
        image_metadata = ImageMetadata(format="JPEG", width=1920, height=1080, file_size=2048000, exif_data={"Camera": "Canon"})
        feed_metadata = FeedMetadata(title="Test Feed", feed_type="RSS", item_count=25, last_build_date=datetime.now())
        csv_metadata = CSVMetadata(row_count=100, column_count=5, encoding="utf-8", has_header=True)
        links = [
            LinkInfo(url="https://external.com", is_external=True, is_valid=True),
            LinkInfo(url="https://internal.com", is_external=False, is_valid=False)
        ]
        content_summary = ContentSummary(word_count=1500, reading_time_minutes=6.0, language="en", key_phrases=["ai", "ml"])

        result = FetchResult(
            url="https://example.com",
            pdf_metadata=pdf_metadata,
            image_metadata=image_metadata,
            feed_metadata=feed_metadata,
            csv_metadata=csv_metadata,
            links=links,
            content_summary=content_summary
        )

        summary = result.get_metadata_summary()

        # Check PDF summary
        assert summary["pdf"]["title"] == "Test PDF"
        assert summary["pdf"]["author"] == "Test Author"
        assert summary["pdf"]["page_count"] == 10
        assert summary["pdf"]["text_length"] == 5000

        # Check image summary
        assert summary["image"]["format"] == "JPEG"
        assert summary["image"]["dimensions"] == "1920x1080"
        assert summary["image"]["file_size"] == 2048000
        assert summary["image"]["has_exif"] is True

        # Check feed summary
        assert summary["feed"]["title"] == "Test Feed"
        assert summary["feed"]["type"] == "RSS"
        assert summary["feed"]["item_count"] == 25
        assert summary["feed"]["last_updated"] is not None

        # Check CSV summary
        assert summary["csv"]["rows"] == 100
        assert summary["csv"]["columns"] == 5
        assert summary["csv"]["encoding"] == "utf-8"
        assert summary["csv"]["has_header"] is True

        # Check links summary
        assert summary["links"]["total"] == 2
        assert summary["links"]["external"] == 1
        assert summary["links"]["valid"] == 1

        # Check content summary
        assert summary["content"]["word_count"] == 1500
        assert summary["content"]["reading_time"] == "6.0 min"
        assert summary["content"]["language"] == "en"
        assert summary["content"]["key_phrases"] == 2


class TestBatchFetchRequest:
    """Test BatchFetchRequest model."""

    def test_valid_batch(self):
        """Test valid batch request."""
        requests = [
            FetchRequest(url="https://example.com/1"),
            FetchRequest(url="https://example.com/2"),
            FetchRequest(url="https://example.com/3")
        ]

        batch = BatchFetchRequest(requests=requests)
        assert len(batch.requests) == 3
        assert batch.config is None

    def test_batch_with_config(self):
        """Test batch request with custom config."""
        requests = [
            FetchRequest(url="https://example.com/1"),
            FetchRequest(url="https://example.com/2")
        ]
        config = FetchConfig(max_concurrent_requests=5)

        batch = BatchFetchRequest(requests=requests, config=config)
        assert len(batch.requests) == 2
        assert batch.config == config

    def test_empty_batch_validation(self):
        """Test that empty batch is invalid."""
        with pytest.raises(ValidationError):
            BatchFetchRequest(requests=[])

    def test_too_many_requests_validation(self):
        """Test batch size limit."""
        requests = [
            FetchRequest(url=f"https://example.com/{i}")
            for i in range(1001)  # Exceeds limit
        ]

        with pytest.raises(ValidationError):
            BatchFetchRequest(requests=requests)

    def test_duplicate_urls_validation(self):
        """Test that duplicate URLs are rejected."""
        requests = [
            FetchRequest(url="https://example.com"),
            FetchRequest(url="https://example.com"),  # Duplicate
            FetchRequest(url="https://example.com/different")
        ]

        with pytest.raises(ValidationError):
            BatchFetchRequest(requests=requests)

    def test_unique_urls_with_different_params(self):
        """Test that URLs with different params are considered unique."""
        requests = [
            FetchRequest(url="https://example.com", params={"page": "1"}),
            FetchRequest(url="https://example.com", params={"page": "2"}),
            FetchRequest(url="https://example.com/different")
        ]

        # This should be valid since the URLs are effectively different
        # Note: This test depends on how URL normalization is implemented
        batch = BatchFetchRequest(requests=requests)
        assert len(batch.requests) == 3


class TestBatchFetchResult:
    """Test BatchFetchResult dataclass."""

    def test_from_results_all_successful(self):
        """Test creating batch result from all successful results."""
        results = [
            FetchResult(url="https://example.com/1", status_code=200),
            FetchResult(url="https://example.com/2", status_code=200),
            FetchResult(url="https://example.com/3", status_code=201)
        ]

        batch_result = BatchFetchResult.from_results(results, 5.0)

        assert batch_result.total_requests == 3
        assert batch_result.successful_requests == 3
        assert batch_result.failed_requests == 0
        assert batch_result.success_rate == 100.0
        assert batch_result.total_time == 5.0
        assert isinstance(batch_result.timestamp, datetime)
        assert batch_result.results == results

    def test_from_results_mixed(self):
        """Test creating batch result from mixed results."""
        results = [
            FetchResult(url="https://example.com/1", status_code=200),
            FetchResult(url="https://example.com/2", status_code=404, error="Not Found"),
            FetchResult(url="https://example.com/3", status_code=500, error="Server Error"),
            FetchResult(url="https://example.com/4", status_code=200)
        ]

        batch_result = BatchFetchResult.from_results(results, 10.0)

        assert batch_result.total_requests == 4
        assert batch_result.successful_requests == 2
        assert batch_result.failed_requests == 2
        assert batch_result.success_rate == 50.0
        assert batch_result.total_time == 10.0

    def test_from_results_all_failed(self):
        """Test creating batch result from all failed results."""
        results = [
            FetchResult(url="https://example.com/1", status_code=404, error="Not Found"),
            FetchResult(url="https://example.com/2", status_code=500, error="Server Error")
        ]

        batch_result = BatchFetchResult.from_results(results, 2.0)

        assert batch_result.total_requests == 2
        assert batch_result.successful_requests == 0
        assert batch_result.failed_requests == 2
        assert batch_result.success_rate == 0.0

    def test_from_results_empty(self):
        """Test creating batch result from empty results."""
        batch_result = BatchFetchResult.from_results([], 0.0)

        assert batch_result.total_requests == 0
        assert batch_result.successful_requests == 0
        assert batch_result.failed_requests == 0
        assert batch_result.success_rate == 0.0
