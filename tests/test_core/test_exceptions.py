"""
Tests for the exceptions module.
"""

import pytest
from unittest.mock import MagicMock

from web_fetch.exceptions import (
    WebFetchError,
    HTTPError,
    NetworkError,
    TimeoutError,
    ConnectionError,
    AuthenticationError,
    NotFoundError,
    ServerError,
    RateLimitError,
    ContentError,
    FTPError,
    FTPConnectionError,
    FTPAuthenticationError,
    FTPTimeoutError,
    FTPFileNotFoundError,
    FTPPermissionError,
    FTPTransferError,
    FTPProtocolError,
    FTPVerificationError,
)


class TestWebFetchError:
    """Test the base WebFetchError exception."""

    def test_basic_exception(self):
        """Test basic exception creation."""
        error = WebFetchError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)

    def test_exception_with_details(self):
        """Test exception with additional details."""
        error = WebFetchError("Test error", url="https://example.com", status_code=500, retry_count=3)

        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.url == "https://example.com"
        assert error.details["status_code"] == 500
        assert error.details["retry_count"] == 3

    def test_exception_with_url(self):
        """Test exception with URL parameter."""
        url = "https://api.example.com/endpoint"
        error = WebFetchError("API error", url=url)

        assert error.url == url
        assert error.message == "API error"

    def test_exception_repr(self):
        """Test exception string representation."""
        error = WebFetchError("Test error", url="https://example.com")
        error_str = str(error)
        assert "Test error" in error_str

    def test_exception_inheritance(self):
        """Test that all exceptions inherit from WebFetchError."""
        exceptions = [
            HTTPError,
            NetworkError,
            TimeoutError,
            ConnectionError,
            AuthenticationError,
            NotFoundError,
            ServerError,
            RateLimitError,
            ContentError,
        ]

        for exc_class in exceptions:
            error = exc_class("Test message")
            assert isinstance(error, WebFetchError)
            assert isinstance(error, Exception)


class TestHTTPError:
    """Test HTTP-specific errors."""

    def test_http_error_basic(self):
        """Test basic HTTP error."""
        error = HTTPError("HTTP error occurred")
        assert str(error) == "HTTP error occurred"
        assert isinstance(error, WebFetchError)

    def test_http_error_with_status_code(self):
        """Test HTTP error with status code."""
        error = HTTPError("Bad request", status_code=400)
        assert hasattr(error, 'status_code')
        assert error.status_code == 400

    def test_http_error_with_headers_and_response_text(self):
        """Test HTTP error with headers and response text."""
        headers = {"content-type": "application/json", "x-request-id": "123"}
        response_text = '{"error": "Resource not found"}'

        error = HTTPError("Not found", 404, "https://example.com/api", headers, response_text)

        assert error.status_code == 404
        assert error.headers == headers
        assert error.response_text == response_text
        assert error.url == "https://example.com/api"

    def test_http_error_default_headers(self):
        """Test HTTP error with default empty headers."""
        error = HTTPError("Server error", 500)
        assert error.headers == {}
        assert error.response_text is None


class TestSpecificHTTPErrors:
    """Test specific HTTP error types."""

    def test_not_found_error(self):
        """Test NotFoundError (404)."""
        error = NotFoundError("Resource not found")
        assert isinstance(error, HTTPError)
        assert isinstance(error, WebFetchError)

    def test_server_error(self):
        """Test ServerError (5xx)."""
        error = ServerError("Internal server error")
        assert isinstance(error, HTTPError)
        assert isinstance(error, WebFetchError)

    def test_authentication_error(self):
        """Test AuthenticationError (401/403)."""
        error = AuthenticationError("Authentication failed")
        assert isinstance(error, HTTPError)
        assert isinstance(error, WebFetchError)

    def test_rate_limit_error(self):
        """Test RateLimitError (429)."""
        error = RateLimitError("Rate limit exceeded")
        assert isinstance(error, HTTPError)
        assert isinstance(error, WebFetchError)
        assert error.status_code == 429

        # Test with retry_after
        headers = {"retry-after": "60", "x-rate-limit-remaining": "0"}
        error_with_retry = RateLimitError(
            "Rate limit exceeded",
            url="https://api.example.com",
            retry_after=60.0,
            headers=headers
        )
        assert error_with_retry.retry_after == 60.0
        assert error_with_retry.headers == headers
        assert error_with_retry.url == "https://api.example.com"

    def test_authentication_error_variations(self):
        """Test AuthenticationError with different status codes."""
        # Test 401 Unauthorized
        error_401 = AuthenticationError("Authentication required", 401)
        assert error_401.status_code == 401
        assert isinstance(error_401, HTTPError)

        # Test 403 Forbidden
        error_403 = AuthenticationError("Access forbidden", 403)
        assert error_403.status_code == 403
        assert isinstance(error_403, HTTPError)

    def test_server_error_variations(self):
        """Test ServerError with different 5xx status codes."""
        server_errors = [
            (500, "Internal Server Error"),
            (502, "Bad Gateway"),
            (503, "Service Unavailable"),
            (504, "Gateway Timeout"),
        ]

        for status_code, message in server_errors:
            error = ServerError(message, status_code)
            assert error.status_code == status_code
            assert isinstance(error, HTTPError)
            assert isinstance(error, WebFetchError)

    def test_not_found_error_with_context(self):
        """Test NotFoundError with additional context."""
        headers = {"content-type": "application/json"}
        response_text = '{"error": "Endpoint not found", "code": "NOT_FOUND"}'

        error = NotFoundError(
            "API endpoint not found",
            404,
            "https://api.example.com/v1/missing",
            headers,
            response_text
        )

        assert error.status_code == 404
        assert error.url == "https://api.example.com/v1/missing"
        assert error.headers == headers
        assert error.response_text == response_text


class TestTimeoutError:
    """Test timeout-specific errors."""

    def test_timeout_error_basic(self):
        """Test basic TimeoutError."""
        error = TimeoutError("Request timed out")
        assert isinstance(error, WebFetchError)
        assert error.message == "Request timed out"
        assert error.timeout_value is None

    def test_timeout_error_with_value(self):
        """Test TimeoutError with timeout value."""
        error = TimeoutError(
            "Request timed out after 30 seconds",
            url="https://slow.example.com",
            timeout_value=30.0
        )
        assert error.timeout_value == 30.0
        assert error.url == "https://slow.example.com"
        assert error.message == "Request timed out after 30 seconds"

    def test_timeout_error_inheritance(self):
        """Test TimeoutError inheritance."""
        error = TimeoutError("Timeout")
        assert isinstance(error, WebFetchError)


class TestNetworkErrors:
    """Test network-related errors."""

    def test_network_error(self):
        """Test basic NetworkError."""
        error = NetworkError("Network connection failed")
        assert isinstance(error, WebFetchError)
        assert error.message == "Network connection failed"

    def test_connection_error(self):
        """Test ConnectionError."""
        error = ConnectionError("Failed to connect to host")
        assert isinstance(error, WebFetchError)
        assert error.message == "Failed to connect to host"

    def test_network_error_with_details(self):
        """Test NetworkError with additional details."""
        error = NetworkError(
            "DNS resolution failed",
            url="https://nonexistent.example.com",
            dns_server="8.8.8.8",
            error_code="NXDOMAIN"
        )
        assert error.url == "https://nonexistent.example.com"
        assert error.details["dns_server"] == "8.8.8.8"
        assert error.details["error_code"] == "NXDOMAIN"


class TestContentError:
    """Test content-related errors."""

    def test_content_error_basic(self):
        """Test basic ContentError."""
        error = ContentError("Failed to parse content")
        assert isinstance(error, WebFetchError)
        assert error.message == "Failed to parse content"
        assert error.content_type is None
        assert error.content_length is None

    def test_content_error_with_details(self):
        """Test ContentError with content type and length."""
        error = ContentError(
            "Invalid JSON format",
            url="https://api.example.com/data",
            content_type="application/json",
            content_length=1024
        )
        assert error.content_type == "application/json"
        assert error.content_length == 1024
        assert error.url == "https://api.example.com/data"

    def test_content_error_parsing_scenarios(self):
        """Test ContentError for different parsing scenarios."""
        scenarios = [
            ("JSON parsing failed: Unexpected token", "application/json", 512),
            ("XML parsing failed: Invalid syntax", "application/xml", 2048),
            ("HTML parsing failed: Malformed document", "text/html", 4096),
            ("Binary content corrupted", "application/octet-stream", 8192),
        ]

        for message, content_type, content_length in scenarios:
            error = ContentError(message, content_type=content_type, content_length=content_length)
            assert error.message == message
            assert error.content_type == content_type
            assert error.content_length == content_length


class TestFTPErrors:
    """Test FTP-specific errors."""

    def test_ftp_error_basic(self):
        """Test basic FTPError."""
        error = FTPError("FTP operation failed")
        assert str(error) == "FTP operation failed"
        assert isinstance(error, WebFetchError)

    def test_ftp_error_inheritance(self):
        """Test that all FTP exceptions inherit from FTPError."""
        ftp_exceptions = [
            FTPConnectionError,
            FTPAuthenticationError,
            FTPTimeoutError,
            FTPFileNotFoundError,
            FTPPermissionError,
            FTPTransferError,
            FTPProtocolError,
            FTPVerificationError,
        ]

        for exc_class in ftp_exceptions:
            error = exc_class("Test FTP error")
            assert isinstance(error, FTPError)
            assert isinstance(error, WebFetchError)

    def test_ftp_connection_error(self):
        """Test FTPConnectionError."""
        error = FTPConnectionError("Failed to connect to FTP server")
        assert isinstance(error, FTPError)

    def test_ftp_authentication_error(self):
        """Test FTPAuthenticationError."""
        error = FTPAuthenticationError("FTP authentication failed")
        assert isinstance(error, FTPError)

    def test_ftp_file_not_found_error(self):
        """Test FTPFileNotFoundError."""
        error = FTPFileNotFoundError("File not found on FTP server")
        assert isinstance(error, FTPError)

    def test_ftp_permission_error(self):
        """Test FTPPermissionError."""
        error = FTPPermissionError("Permission denied")
        assert isinstance(error, FTPError)

    def test_ftp_transfer_error(self):
        """Test FTPTransferError."""
        error = FTPTransferError("File transfer failed")
        assert isinstance(error, FTPError)

    def test_ftp_protocol_error(self):
        """Test FTPProtocolError."""
        error = FTPProtocolError("FTP protocol error")
        assert isinstance(error, FTPError)

    def test_ftp_verification_error(self):
        """Test FTPVerificationError."""
        error = FTPVerificationError("File verification failed")
        assert isinstance(error, FTPError)


class TestErrorHandlingUtilities:
    """Test error handling utility functions."""

    def test_handle_http_status_error_401(self):
        """Test HTTP status error handling for 401."""
        from web_fetch.exceptions import ErrorHandler

        error = ErrorHandler.handle_http_status_error(
            401, "Authentication required", "https://api.example.com"
        )

        assert isinstance(error, AuthenticationError)
        assert error.status_code == 401
        assert "Authentication required" in error.message

    def test_handle_http_status_error_404(self):
        """Test HTTP status error handling for 404."""
        from web_fetch.exceptions import ErrorHandler

        error = ErrorHandler.handle_http_status_error(
            404, "Not found", "https://api.example.com/missing"
        )

        assert isinstance(error, NotFoundError)
        assert error.status_code == 404

    def test_handle_http_status_error_429_with_retry_after(self):
        """Test HTTP status error handling for 429 with Retry-After header."""
        from web_fetch.exceptions import ErrorHandler

        headers = {"Retry-After": "120", "X-RateLimit-Remaining": "0"}
        error = ErrorHandler.handle_http_status_error(
            429, "Rate limit exceeded", "https://api.example.com", headers
        )

        assert isinstance(error, RateLimitError)
        assert error.status_code == 429
        assert error.retry_after == 120.0

    def test_handle_http_status_error_500(self):
        """Test HTTP status error handling for 500."""
        from web_fetch.exceptions import ErrorHandler

        error = ErrorHandler.handle_http_status_error(
            500, "Internal server error", "https://api.example.com"
        )

        assert isinstance(error, ServerError)
        assert error.status_code == 500

    def test_handle_http_status_error_unknown(self):
        """Test HTTP status error handling for unknown status codes."""
        from web_fetch.exceptions import ErrorHandler

        error = ErrorHandler.handle_http_status_error(
            418, "I'm a teapot", "https://api.example.com"
        )

        assert isinstance(error, HTTPError)
        assert not isinstance(error, (AuthenticationError, NotFoundError, RateLimitError, ServerError))
        assert error.status_code == 418


class TestErrorChaining:
    """Test error chaining and context."""

    def test_error_chaining_basic(self):
        """Test basic error chaining."""
        try:
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise HTTPError("HTTP error occurred", 500) from e
        except HTTPError as http_error:
            assert http_error.__cause__ is not None
            assert isinstance(http_error.__cause__, ValueError)
            assert str(http_error.__cause__) == "Original error"

    def test_error_chaining_with_context(self):
        """Test error chaining with additional context."""
        original_error = ConnectionError("Connection failed", url="https://example.com")

        try:
            raise original_error
        except ConnectionError as e:
            enhanced_error = HTTPError(
                "Request failed due to connection issue",
                503,
                url=e.url,
                headers={"retry-after": "60"}
            )
            enhanced_error.__cause__ = e

            assert enhanced_error.__cause__ == original_error
            assert enhanced_error.url == original_error.url
            assert enhanced_error.headers["retry-after"] == "60"

    def test_nested_error_chaining(self):
        """Test multiple levels of error chaining."""
        try:
            try:
                try:
                    raise OSError("Low-level OS error")
                except OSError as e:
                    raise ConnectionError("Connection failed") from e
            except ConnectionError as e:
                raise HTTPError("HTTP request failed", 503) from e
        except HTTPError as final_error:
            # Check the chain
            assert final_error.__cause__ is not None
            assert isinstance(final_error.__cause__, ConnectionError)
            assert final_error.__cause__.__cause__ is not None
            assert isinstance(final_error.__cause__.__cause__, OSError)

    def test_error_context_preservation(self):
        """Test that error context is preserved through chaining."""
        original_details = {"host": "example.com", "port": 443, "timeout": 30.0}
        original_error = TimeoutError(
            "Connection timed out",
            url="https://example.com/api",
            timeout_value=30.0,
            **original_details
        )

        try:
            raise original_error
        except TimeoutError as e:
            # Create enhanced error preserving context
            enhanced_error = HTTPError(
                f"Request failed: {e.message}",
                408,  # Request Timeout
                url=e.url,
                headers={"connection": "close"}
            )
            enhanced_error.__cause__ = e

            # Verify context preservation
            assert enhanced_error.__cause__ == original_error
            assert enhanced_error.url == original_error.url
            assert enhanced_error.__cause__.timeout_value == 30.0
            assert enhanced_error.__cause__.details == original_details
