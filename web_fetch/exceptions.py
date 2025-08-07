"""
Comprehensive exception handling for the web fetcher utility.

This module provides custom exceptions and error handling utilities for
robust network error management, timeout handling, and HTTP status code processing.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, Type, Union

import aiohttp


class WebFetchError(Exception):
    """
    Base exception for all web fetching operations.

    This is the root exception class for all errors that can occur during
    web fetching operations. All other custom exceptions inherit from this class.

    Attributes:
        message: Human-readable error message
        url: URL that caused the error (if applicable)
        details: Additional error details as keyword arguments
    """

    def __init__(self, message: str, url: Optional[str] = None, **kwargs: Any) -> None:
        super().__init__(message)
        self.message = message
        self.url = url
        self.details = kwargs


class NetworkError(WebFetchError):
    """
    Raised for network-related errors.

    Covers general network connectivity issues, DNS resolution failures,
    and other low-level network problems that prevent establishing a connection.
    """

    pass


class TimeoutError(WebFetchError):
    """
    Raised when a request times out.

    Occurs when a request exceeds the configured timeout duration.
    Can happen during connection establishment, request sending, or response reading.

    Attributes:
        timeout_value: The timeout value that was exceeded (in seconds)
    """

    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        timeout_value: Optional[float] = None,
    ) -> None:
        super().__init__(message, url)
        self.timeout_value = timeout_value


class ConnectionError(WebFetchError):
    """
    Raised when connection fails.

    Occurs when the client cannot establish a connection to the server.
    This includes connection refused, host unreachable, and similar connection issues.
    """

    pass


class HTTPError(WebFetchError):
    """Raised for HTTP-related errors."""

    def __init__(
        self,
        message: str,
        status_code: int,
        url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        response_text: Optional[str] = None,
    ) -> None:
        super().__init__(message, url)
        self.status_code = status_code
        self.headers = headers or {}
        self.response_text = response_text


class ContentError(WebFetchError):
    """Raised when content parsing fails."""

    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        content_type: Optional[str] = None,
        content_length: Optional[int] = None,
    ) -> None:
        super().__init__(message, url)
        self.content_type = content_type
        self.content_length = content_length


class RateLimitError(HTTPError):
    """Raised when rate limiting is encountered."""

    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        retry_after: Optional[Union[int, float]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(message, 429, url, headers)
        self.retry_after = retry_after


class AuthenticationError(HTTPError):
    """Raised for authentication-related errors (401, 403)."""

    pass


class NotFoundError(HTTPError):
    """Raised when resource is not found (404)."""

    pass


class ServerError(HTTPError):
    """Raised for server errors (5xx)."""

    pass


# FTP-specific exceptions


class FTPError(WebFetchError):
    """Base exception for FTP operations."""

    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        ftp_code: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, url, **kwargs)
        self.ftp_code = ftp_code


class FTPConnectionError(FTPError):
    """Raised when FTP connection fails."""

    pass


class FTPAuthenticationError(FTPError):
    """Raised for FTP authentication failures."""

    pass


class FTPTimeoutError(FTPError):
    """Raised when FTP operations time out."""

    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        timeout_value: Optional[float] = None,
        operation: Optional[str] = None,
    ) -> None:
        super().__init__(message, url)
        self.timeout_value = timeout_value
        self.operation = operation


class FTPTransferError(FTPError):
    """Raised when file transfer fails."""

    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        bytes_transferred: int = 0,
        total_bytes: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, url, **kwargs)
        self.bytes_transferred = bytes_transferred
        self.total_bytes = total_bytes


class FTPFileNotFoundError(FTPError):
    """Raised when FTP file or directory is not found."""

    pass


class FTPPermissionError(FTPError):
    """Raised when FTP operation lacks permissions."""

    pass


class FTPVerificationError(FTPError):
    """Raised when file verification fails."""

    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        verification_method: Optional[str] = None,
        expected_value: Optional[str] = None,
        actual_value: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, url, **kwargs)
        self.verification_method = verification_method
        self.expected_value = expected_value
        self.actual_value = actual_value


class FTPProtocolError(FTPError):
    """Raised for FTP protocol-related errors."""

    pass


class ErrorHandler:
    """
    Utility class for handling and categorizing different types of errors.

    Provides methods to convert aiohttp exceptions to custom exceptions
    and determine appropriate retry strategies.
    """

    @staticmethod
    def handle_aiohttp_error(
        error: Exception, url: Optional[str] = None
    ) -> WebFetchError:
        """
        Convert aiohttp exceptions to custom WebFetchError subclasses.

        Args:
            error: The original aiohttp exception
            url: The URL that caused the error

        Returns:
            Appropriate WebFetchError subclass
        """
        if isinstance(error, asyncio.TimeoutError):
            return TimeoutError(f"Request timed out: {error}", url=url)

        elif isinstance(error, aiohttp.ClientTimeout):
            return TimeoutError(
                f"Client timeout: {error}",
                url=url,
                timeout_value=getattr(error, "total", None),
            )

        elif isinstance(error, aiohttp.ClientConnectionError):
            return ConnectionError(f"Connection error: {error}", url=url)

        elif isinstance(error, aiohttp.ClientConnectorError):
            return ConnectionError(f"Connector error: {error}", url=url)

        elif isinstance(error, aiohttp.ClientSSLError):
            return ConnectionError(f"SSL error: {error}", url=url)

        elif isinstance(error, aiohttp.ClientPayloadError):
            return ContentError(f"Payload error: {error}", url=url)

        elif isinstance(error, aiohttp.ClientResponseError):
            return ErrorHandler.handle_http_status_error(
                error.status, str(error), url, getattr(error, "headers", None)
            )

        else:
            return NetworkError(f"Unexpected network error: {error}", url=url)

    @staticmethod
    def handle_http_status_error(
        status_code: int,
        message: str,
        url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        response_text: Optional[str] = None,
    ) -> HTTPError:
        """
        Create appropriate HTTPError subclass based on status code.

        Args:
            status_code: HTTP status code
            message: Error message
            url: The URL that caused the error
            headers: Response headers
            response_text: Response body text

        Returns:
            Appropriate HTTPError subclass
        """
        if status_code == 401:
            return AuthenticationError(
                f"Authentication required: {message}",
                status_code,
                url,
                headers,
                response_text,
            )

        elif status_code == 403:
            return AuthenticationError(
                f"Access forbidden: {message}", status_code, url, headers, response_text
            )

        elif status_code == 404:
            return NotFoundError(
                f"Resource not found: {message}",
                status_code,
                url,
                headers,
                response_text,
            )

        elif status_code == 429:
            retry_after = None
            if headers:
                retry_after_header = headers.get("Retry-After") or headers.get(
                    "retry-after"
                )
                if retry_after_header:
                    try:
                        retry_after = float(retry_after_header)
                    except ValueError:
                        pass

            return RateLimitError(
                f"Rate limit exceeded: {message}", url, retry_after, headers
            )

        elif 500 <= status_code < 600:
            return ServerError(
                f"Server error: {message}", status_code, url, headers, response_text
            )

        else:
            return HTTPError(message, status_code, url, headers, response_text)

    @staticmethod
    def is_retryable_error(error: Exception) -> bool:
        """
        Determine if an error is retryable.

        Args:
            error: The exception to check

        Returns:
            True if the error should be retried, False otherwise
        """
        # Network errors are generally retryable
        if isinstance(error, (NetworkError, ConnectionError, TimeoutError)):
            return True

        # Some HTTP errors are retryable
        if isinstance(error, HTTPError):
            # Server errors (5xx) are retryable
            if isinstance(error, ServerError):
                return True

            # Rate limiting is retryable with backoff
            if isinstance(error, RateLimitError):
                return True

            # Specific status codes that might be temporary
            if error.status_code in [408, 502, 503, 504]:
                return True

        # Content errors are generally not retryable
        if isinstance(error, ContentError):
            return False

        # Authentication errors are not retryable
        if isinstance(error, AuthenticationError):
            return False

        # 404 errors are not retryable
        if isinstance(error, NotFoundError):
            return False

        return False

    @staticmethod
    def get_retry_delay(
        error: Exception, attempt: int, base_delay: float = 1.0
    ) -> float:
        """
        Calculate appropriate retry delay based on error type and attempt number.

        Args:
            error: The exception that occurred
            attempt: Current attempt number (0-based)
            base_delay: Base delay in seconds

        Returns:
            Delay in seconds before next retry
        """
        # Rate limiting has specific retry-after header
        if isinstance(error, RateLimitError) and error.retry_after:
            return float(error.retry_after)

        # Exponential backoff for most retryable errors
        if ErrorHandler.is_retryable_error(error):
            return base_delay * (2**attempt)

        return 0.0

    @staticmethod
    def handle_ftp_error(
        error: Exception, url: Optional[str] = None, operation: Optional[str] = None
    ) -> FTPError:
        """
        Convert FTP library exceptions to custom FTPError subclasses.

        Args:
            error: The original FTP exception
            url: The FTP URL that caused the error
            operation: The FTP operation being performed

        Returns:
            Appropriate FTPError subclass
        """
        import ftplib
        import socket

        error_msg = str(error)

        # Handle ftplib specific exceptions
        if isinstance(error, ftplib.error_perm):
            # Permanent errors (5xx codes)
            if "530" in error_msg or "login" in error_msg.lower():
                return FTPAuthenticationError(
                    f"FTP authentication failed: {error_msg}", url=url, ftp_code=530
                )
            elif "550" in error_msg or "not found" in error_msg.lower():
                return FTPFileNotFoundError(
                    f"FTP file not found: {error_msg}", url=url, ftp_code=550
                )
            elif "553" in error_msg or "permission" in error_msg.lower():
                return FTPPermissionError(
                    f"FTP permission denied: {error_msg}", url=url, ftp_code=553
                )
            else:
                return FTPProtocolError(f"FTP permanent error: {error_msg}", url=url)

        elif isinstance(error, ftplib.error_temp):
            # Temporary errors (4xx codes)
            return FTPTransferError(f"FTP temporary error: {error_msg}", url=url)

        elif isinstance(error, ftplib.error_proto):
            # Protocol errors
            return FTPProtocolError(f"FTP protocol error: {error_msg}", url=url)

        elif isinstance(error, (socket.timeout, TimeoutError)):
            return FTPTimeoutError(
                f"FTP operation timed out: {error_msg}", url=url, operation=operation
            )

        elif isinstance(error, (socket.error, ConnectionError)):
            return FTPConnectionError(f"FTP connection error: {error_msg}", url=url)

        else:
            return FTPError(f"Unexpected FTP error: {error_msg}", url=url)

    @staticmethod
    def is_retryable_ftp_error(error: Exception) -> bool:
        """
        Determine if an FTP error is retryable.

        Args:
            error: The FTP exception to check

        Returns:
            True if the error should be retried, False otherwise
        """
        # Connection and timeout errors are retryable
        if isinstance(error, (FTPConnectionError, FTPTimeoutError)):
            return True

        # Temporary transfer errors are retryable
        if isinstance(error, FTPTransferError):
            return True

        # Authentication errors are not retryable
        if isinstance(error, FTPAuthenticationError):
            return False

        # File not found errors are not retryable
        if isinstance(error, FTPFileNotFoundError):
            return False

        # Permission errors are not retryable
        if isinstance(error, FTPPermissionError):
            return False

        # Protocol errors might be retryable depending on the specific error
        if isinstance(error, FTPProtocolError):
            return True

        # Verification errors are not retryable
        if isinstance(error, FTPVerificationError):
            return False

        return False
