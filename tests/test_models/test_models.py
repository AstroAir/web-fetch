"""
Unit tests for the models module.

Tests for Pydantic models, dataclasses, and configuration validation.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from web_fetch.models import (
    BatchFetchRequest,
    BatchFetchResult,
    ContentType,
    FetchConfig,
    FetchRequest,
    FetchResult,
    RequestHeaders,
    RetryStrategy,
)


class TestRequestHeaders:
    """Test the RequestHeaders dataclass."""
    
    def test_default_headers(self):
        """Test default header values."""
        headers = RequestHeaders()
        assert "Mozilla/5.0" in headers.user_agent
        assert headers.accept == "*/*"
        assert headers.accept_language == "en-US,en;q=0.9"
        assert headers.connection == "keep-alive"
    
    def test_custom_headers(self):
        """Test custom headers integration."""
        custom = {"X-API-Key": "test-key", "Authorization": "Bearer token"}
        headers = RequestHeaders(custom_headers=custom)
        
        header_dict = headers.to_dict()
        assert header_dict["X-API-Key"] == "test-key"
        assert header_dict["Authorization"] == "Bearer token"
        assert "User-Agent" in header_dict
    
    def test_immutable(self):
        """Test that RequestHeaders is immutable."""
        headers = RequestHeaders()
        with pytest.raises(AttributeError):
            headers.user_agent = "new-agent"


class TestFetchConfig:
    """Test the FetchConfig Pydantic model."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = FetchConfig()
        assert config.total_timeout == 30.0
        assert config.max_concurrent_requests == 10
        assert config.retry_strategy == RetryStrategy.EXPONENTIAL
        assert config.max_retries == 3
        assert config.verify_ssl is True
    
    def test_validation_positive_timeout(self):
        """Test that timeout must be positive."""
        with pytest.raises(ValidationError):
            FetchConfig(total_timeout=-1.0)
        
        with pytest.raises(ValidationError):
            FetchConfig(connect_timeout=0.0)
    
    def test_validation_concurrent_requests(self):
        """Test concurrent request limits."""
        with pytest.raises(ValidationError):
            FetchConfig(max_concurrent_requests=0)
        
        with pytest.raises(ValidationError):
            FetchConfig(max_concurrent_requests=101)
    
    def test_validation_retries(self):
        """Test retry validation."""
        with pytest.raises(ValidationError):
            FetchConfig(max_retries=-1)
        
        with pytest.raises(ValidationError):
            FetchConfig(max_retries=11)
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = FetchConfig(
            total_timeout=60.0,
            max_concurrent_requests=5,
            max_retries=1,
            verify_ssl=False
        )
        assert config.total_timeout == 60.0
        assert config.max_concurrent_requests == 5
        assert config.max_retries == 1
        assert config.verify_ssl is False


class TestFetchRequest:
    """Test the FetchRequest Pydantic model."""
    
    def test_valid_request(self):
        """Test valid request creation."""
        request = FetchRequest(url="https://example.com")
        assert str(request.url) == "https://example.com/"
        assert request.method == "GET"
        assert request.content_type == ContentType.RAW
    
    def test_url_validation(self):
        """Test URL validation."""
        # Valid URLs
        FetchRequest(url="https://example.com")
        FetchRequest(url="http://localhost:8080/path")
        
        # Invalid URLs
        with pytest.raises(ValidationError):
            FetchRequest(url="ftp://example.com")
        
        with pytest.raises(ValidationError):
            FetchRequest(url="not-a-url")
    
    def test_method_validation(self):
        """Test HTTP method validation."""
        valid_methods = ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH"]
        for method in valid_methods:
            request = FetchRequest(url="https://example.com", method=method)
            assert request.method == method
        
        with pytest.raises(ValidationError):
            FetchRequest(url="https://example.com", method="INVALID")
    
    def test_custom_request(self):
        """Test request with custom parameters."""
        request = FetchRequest(
            url="https://api.example.com/data",
            method="POST",
            headers={"Content-Type": "application/json"},
            data={"key": "value"},
            content_type=ContentType.JSON,
            timeout_override=15.0
        )
        assert request.method == "POST"
        assert request.headers["Content-Type"] == "application/json"
        assert request.data == {"key": "value"}
        assert request.content_type == ContentType.JSON
        assert request.timeout_override == 15.0


class TestFetchResult:
    """Test the FetchResult dataclass."""
    
    def test_successful_result(self):
        """Test successful result properties."""
        result = FetchResult(
            url="https://example.com",
            status_code=200,
            headers={"Content-Type": "text/html"},
            content="<html>test</html>",
            content_type=ContentType.HTML,
            response_time=1.5,
            timestamp=datetime.now()
        )
        
        assert result.is_success is True
        assert result.is_client_error is False
        assert result.is_server_error is False
        assert result.error is None
    
    def test_client_error_result(self):
        """Test client error result properties."""
        result = FetchResult(
            url="https://example.com/notfound",
            status_code=404,
            headers={},
            content=None,
            content_type=ContentType.TEXT,
            response_time=0.5,
            timestamp=datetime.now(),
            error="Not Found"
        )
        
        assert result.is_success is False
        assert result.is_client_error is True
        assert result.is_server_error is False
    
    def test_server_error_result(self):
        """Test server error result properties."""
        result = FetchResult(
            url="https://example.com/error",
            status_code=500,
            headers={},
            content=None,
            content_type=ContentType.TEXT,
            response_time=2.0,
            timestamp=datetime.now(),
            error="Internal Server Error"
        )
        
        assert result.is_success is False
        assert result.is_client_error is False
        assert result.is_server_error is True


class TestBatchFetchRequest:
    """Test the BatchFetchRequest Pydantic model."""
    
    def test_valid_batch(self):
        """Test valid batch request."""
        requests = [
            FetchRequest(url="https://example.com/1"),
            FetchRequest(url="https://example.com/2"),
        ]
        batch = BatchFetchRequest(requests=requests)
        assert len(batch.requests) == 2
    
    def test_empty_batch(self):
        """Test that empty batch is invalid."""
        with pytest.raises(ValidationError):
            BatchFetchRequest(requests=[])
    
    def test_duplicate_urls(self):
        """Test that duplicate URLs are rejected."""
        requests = [
            FetchRequest(url="https://example.com"),
            FetchRequest(url="https://example.com"),  # Duplicate
        ]
        with pytest.raises(ValidationError):
            BatchFetchRequest(requests=requests)
    
    def test_too_many_requests(self):
        """Test batch size limit."""
        requests = [
            FetchRequest(url=f"https://example.com/{i}")
            for i in range(1001)  # Exceeds limit
        ]
        with pytest.raises(ValidationError):
            BatchFetchRequest(requests=requests)


class TestBatchFetchResult:
    """Test the BatchFetchResult dataclass."""
    
    def test_from_results(self):
        """Test creating BatchFetchResult from individual results."""
        results = [
            FetchResult(
                url="https://example.com/1",
                status_code=200,
                headers={},
                content="success",
                content_type=ContentType.TEXT,
                response_time=1.0,
                timestamp=datetime.now()
            ),
            FetchResult(
                url="https://example.com/2",
                status_code=404,
                headers={},
                content=None,
                content_type=ContentType.TEXT,
                response_time=0.5,
                timestamp=datetime.now(),
                error="Not Found"
            ),
        ]
        
        batch_result = BatchFetchResult.from_results(results, 2.5)
        
        assert batch_result.total_requests == 2
        assert batch_result.successful_requests == 1
        assert batch_result.failed_requests == 1
        assert batch_result.success_rate == 50.0
        assert batch_result.total_time == 2.5
    
    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        # All successful
        results = [
            FetchResult(
                url="url1",
                status_code=200,
                headers={},
                content="ok",
                content_type=ContentType.TEXT,
                response_time=1.0,
                timestamp=datetime.now()
            ),
            FetchResult(
                url="url2",
                status_code=200,
                headers={},
                content="ok",
                content_type=ContentType.TEXT,
                response_time=1.0,
                timestamp=datetime.now()
            ),
        ]
        batch = BatchFetchResult.from_results(results, 2.0)
        assert batch.success_rate == 100.0
        
        # All failed
        results = [
            FetchResult(
                url="url1",
                status_code=500,
                headers={},
                content=None,
                content_type=ContentType.TEXT,
                response_time=1.0,
                timestamp=datetime.now(),
                error="Error"
            ),
            FetchResult(
                url="url2",
                status_code=404,
                headers={},
                content=None,
                content_type=ContentType.TEXT,
                response_time=1.0,
                timestamp=datetime.now(),
                error="Not Found"
            ),
        ]
        batch = BatchFetchResult.from_results(results, 2.0)
        assert batch.success_rate == 0.0
        
        # Empty results
        batch = BatchFetchResult.from_results([], 0.0)
        assert batch.success_rate == 0.0
