"""
Common utilities and patterns for web_fetch HTTP components.

This module provides reusable utilities, base classes, and shared
functionality patterns to reduce code duplication.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Protocol, TypeVar, Union, runtime_checkable
from urllib.parse import urlparse

import aiohttp
from pydantic import BaseModel

from ..exceptions import WebFetchError


class HTTPError(WebFetchError):
    """Base HTTP error with standardized handling."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_headers: Optional[Dict[str, str]] = None,
        error_code: Optional[str] = None
    ):
        """
        Initialize HTTP error.

        Args:
            message: Error message
            status_code: HTTP status code
            response_headers: Response headers
            error_code: Application-specific error code
        """
        super().__init__(message)
        self.status_code = status_code
        self.response_headers = response_headers or {}
        self.error_code = error_code


class ConnectionError(HTTPError):
    """Connection-related errors."""
    pass


class TimeoutError(HTTPError):
    """Timeout-related errors."""
    pass


class ValidationError(HTTPError):
    """Input validation errors."""
    pass


class SecurityError(HTTPError):
    """Security-related errors."""
    pass


class RateLimitError(HTTPError):
    """Rate limiting errors."""
    pass
from .connection_pool import OptimizedConnectionPool
from .error_handling import SecurityErrorHandler, handle_http_error
from .metrics import MetricsCollector, get_global_metrics
from .security import SecurityMiddleware
from .validation import InputValidator, get_global_validator

T = TypeVar('T')


@runtime_checkable
class HTTPComponentProtocol(Protocol):
    """Protocol for HTTP components with standard interface."""

    async def close(self) -> None:
        """Close component and cleanup resources."""
        ...

    async def __aenter__(self) -> Any:
        """Async context manager entry."""
        ...

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        ...


@runtime_checkable
class RequestProcessorProtocol(Protocol):
    """Protocol for request processors."""

    async def process_request(
        self,
        method: str,
        url: str,
        **kwargs: Any
    ) -> aiohttp.ClientResponse:
        """Process HTTP request."""
        ...


@runtime_checkable
class ResponseProcessorProtocol(Protocol):
    """Protocol for response processors."""

    async def process_response(
        self,
        response: aiohttp.ClientResponse
    ) -> Any:
        """Process HTTP response."""
        ...


def validate_type(value: Any, expected_type: type, field_name: str = "value") -> Any:
    """
    Validate value type at runtime.

    Args:
        value: Value to validate
        expected_type: Expected type
        field_name: Field name for error messages

    Returns:
        Validated value

    Raises:
        ValidationError: If type validation fails
    """
    if not isinstance(value, expected_type):
        raise ValidationError(
            f"{field_name} must be of type {expected_type.__name__}, "
            f"got {type(value).__name__}"
        )
    return value


def validate_optional_type(
    value: Any,
    expected_type: type,
    field_name: str = "value"
) -> Optional[Any]:
    """
    Validate optional value type at runtime.

    Args:
        value: Value to validate
        expected_type: Expected type
        field_name: Field name for error messages

    Returns:
        Validated value or None

    Raises:
        ValidationError: If type validation fails
    """
    if value is None:
        return None
    return validate_type(value, expected_type, field_name)


class ResourceManager:
    """Enhanced resource management for HTTP components."""

    def __init__(self):
        """Initialize resource manager."""
        self._resources: List[HTTPComponentProtocol] = []
        self._cleanup_callbacks: List[Callable[[], None]] = []
        self._closed = False

    def register_resource(self, resource: HTTPComponentProtocol) -> None:
        """Register a resource for automatic cleanup."""
        if not self._closed:
            self._resources.append(resource)

    def register_cleanup_callback(self, callback: Callable[[], None]) -> None:
        """Register a cleanup callback."""
        if not self._closed:
            self._cleanup_callbacks.append(callback)

    async def cleanup_all(self) -> None:
        """Cleanup all registered resources."""
        if self._closed:
            return

        self._closed = True

        # Close all resources
        for resource in reversed(self._resources):
            try:
                await resource.close()
            except Exception as e:
                # Log error but continue cleanup
                import logging
                logging.getLogger(__name__).warning(f"Error closing resource: {e}")

        # Execute cleanup callbacks
        for callback in reversed(self._cleanup_callbacks):
            try:
                callback()
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Error in cleanup callback: {e}")

        # Clear lists
        self._resources.clear()
        self._cleanup_callbacks.clear()

    async def __aenter__(self) -> 'ResourceManager':
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.cleanup_all()


class MemoryOptimizer:
    """Memory optimization utilities."""

    @staticmethod
    def optimize_chunk_size(content_length: Optional[int], default_size: int = 8192) -> int:
        """Optimize chunk size based on content length."""
        if content_length is None:
            return default_size

        # For small files, use smaller chunks
        if content_length < 64 * 1024:  # 64KB
            return min(default_size, content_length // 4)

        # For large files, use larger chunks
        if content_length > 10 * 1024 * 1024:  # 10MB
            return min(64 * 1024, default_size * 8)  # Max 64KB chunks

        return default_size

    @staticmethod
    def should_use_streaming(content_length: Optional[int], threshold: int = 1024 * 1024) -> bool:
        """Determine if streaming should be used based on content size."""
        if content_length is None:
            return True  # Unknown size, use streaming to be safe

        return content_length > threshold


class BaseHTTPComponent(ABC):
    """Base class for HTTP components with common functionality."""
    
    def __init__(
        self,
        connection_pool: Optional[OptimizedConnectionPool] = None,
        security_middleware: Optional[SecurityMiddleware] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        error_handler: Optional[SecurityErrorHandler] = None,
        validator: Optional[InputValidator] = None
    ):
        """
        Initialize base HTTP component.
        
        Args:
            connection_pool: Optional connection pool
            security_middleware: Optional security middleware
            metrics_collector: Optional metrics collector
            error_handler: Optional error handler
            validator: Optional input validator
        """
        self._connection_pool = connection_pool
        self._security_middleware = security_middleware
        self._metrics_collector = metrics_collector
        self._error_handler = error_handler
        self._validator = validator
        self._owned_pool = connection_pool is None
    
    async def _get_connection_pool(self) -> OptimizedConnectionPool:
        """Get or create connection pool."""
        if self._connection_pool is None:
            from .connection_pool import ConnectionPoolConfig
            config = ConnectionPoolConfig()
            self._connection_pool = OptimizedConnectionPool(config)
        return self._connection_pool
    
    async def _get_security_middleware(self) -> SecurityMiddleware:
        """Get or create security middleware."""
        if self._security_middleware is None:
            self._security_middleware = SecurityMiddleware()
        return self._security_middleware
    
    async def _get_metrics_collector(self) -> MetricsCollector:
        """Get or create metrics collector."""
        if self._metrics_collector is None:
            self._metrics_collector = await get_global_metrics()
        return self._metrics_collector
    
    def _get_error_handler(self) -> SecurityErrorHandler:
        """Get or create error handler."""
        if self._error_handler is None:
            from .error_handling import get_global_error_handler
            self._error_handler = get_global_error_handler()
        return self._error_handler
    
    def _get_validator(self) -> InputValidator:
        """Get or create input validator."""
        if self._validator is None:
            self._validator = get_global_validator()
        return self._validator
    
    @asynccontextmanager
    async def _managed_session(self) -> AsyncGenerator[aiohttp.ClientSession, None]:
        """Get managed session with automatic cleanup."""
        pool = await self._get_connection_pool()
        async with pool.get_session() as session:
            yield session
    
    async def _validate_request(self, url: str, headers: Optional[Dict[str, str]] = None) -> tuple[str, Dict[str, str]]:
        """Validate request parameters."""
        # Validate URL
        validator = self._get_validator()
        validated_url = validator.validate_url(url)
        
        # Validate headers
        validated_headers = {}
        if headers:
            validated_headers = validator.validate_parameters(headers)
        
        # Security validation
        security = await self._get_security_middleware()
        final_url, final_headers = await security.validate_request(validated_url, validated_headers)
        
        return final_url, final_headers
    
    def _handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle error securely."""
        handler = self._get_error_handler()
        return handle_http_error(error, context)
    
    async def close(self) -> None:
        """Close component and cleanup resources."""
        if self._owned_pool and self._connection_pool:
            await self._connection_pool.close()
            self._connection_pool = None
    
    async def __aenter__(self) -> 'BaseHTTPComponent':
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()


class RequestBuilder:
    """Builder pattern for HTTP requests."""
    
    def __init__(self):
        """Initialize request builder."""
        self._method = "GET"
        self._url = ""
        self._headers: Dict[str, str] = {}
        self._params: Dict[str, Any] = {}
        self._data: Optional[Any] = None
        self._timeout: Optional[float] = None
        self._follow_redirects = True
    
    def method(self, method: str) -> 'RequestBuilder':
        """Set HTTP method."""
        self._method = method.upper()
        return self
    
    def url(self, url: str) -> 'RequestBuilder':
        """Set request URL."""
        self._url = url
        return self
    
    def header(self, name: str, value: str) -> 'RequestBuilder':
        """Add a header."""
        self._headers[name] = value
        return self
    
    def headers(self, headers: Dict[str, str]) -> 'RequestBuilder':
        """Set multiple headers."""
        self._headers.update(headers)
        return self
    
    def param(self, name: str, value: Any) -> 'RequestBuilder':
        """Add a parameter."""
        self._params[name] = value
        return self
    
    def params(self, params: Dict[str, Any]) -> 'RequestBuilder':
        """Set multiple parameters."""
        self._params.update(params)
        return self
    
    def data(self, data: Any) -> 'RequestBuilder':
        """Set request data."""
        self._data = data
        return self
    
    def timeout(self, timeout: float) -> 'RequestBuilder':
        """Set request timeout."""
        self._timeout = timeout
        return self
    
    def follow_redirects(self, follow: bool = True) -> 'RequestBuilder':
        """Set redirect following."""
        self._follow_redirects = follow
        return self
    
    def build(self) -> Dict[str, Any]:
        """Build request configuration."""
        config: Dict[str, Any] = {
            'method': self._method,
            'url': self._url,
            'headers': self._headers,
            'params': self._params,
        }

        if self._data is not None:
            config['data'] = self._data

        if self._timeout is not None:
            config['timeout'] = aiohttp.ClientTimeout(total=self._timeout)

        config['allow_redirects'] = self._follow_redirects

        return config


class ResponseProcessor:
    """Utility for processing HTTP responses."""
    
    @staticmethod
    async def extract_json(response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """Extract JSON from response."""
        try:
            return await response.json()
        except Exception as e:
            raise WebFetchError(f"Failed to parse JSON response: {e}")
    
    @staticmethod
    async def extract_text(response: aiohttp.ClientResponse) -> str:
        """Extract text from response."""
        try:
            return await response.text()
        except Exception as e:
            raise WebFetchError(f"Failed to read text response: {e}")
    
    @staticmethod
    async def extract_bytes(response: aiohttp.ClientResponse) -> bytes:
        """Extract bytes from response."""
        try:
            return await response.read()
        except Exception as e:
            raise WebFetchError(f"Failed to read binary response: {e}")
    
    @staticmethod
    def validate_status(response: aiohttp.ClientResponse, expected_status: Optional[int] = None) -> None:
        """Validate response status."""
        if expected_status and response.status != expected_status:
            raise WebFetchError(f"Unexpected status code: {response.status}, expected: {expected_status}")
        
        if response.status >= 400:
            raise WebFetchError(f"HTTP error {response.status}: {response.reason}")
    
    @staticmethod
    def extract_headers(response: aiohttp.ClientResponse) -> Dict[str, str]:
        """Extract headers from response."""
        return dict(response.headers)


class RetryHandler:
    """Utility for handling request retries."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        retryable_status_codes: Optional[List[int]] = None
    ):
        """
        Initialize retry handler.
        
        Args:
            max_retries: Maximum number of retries
            base_delay: Base delay between retries
            max_delay: Maximum delay between retries
            backoff_factor: Exponential backoff factor
            retryable_status_codes: HTTP status codes that should be retried
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.retryable_status_codes = retryable_status_codes or [429, 502, 503, 504]
    
    def should_retry(self, attempt: int, error: Exception) -> bool:
        """Determine if request should be retried."""
        if attempt >= self.max_retries:
            return False
        
        # Check for retryable HTTP status codes
        if hasattr(error, 'status') and error.status in self.retryable_status_codes:
            return True
        
        # Check for network errors
        if isinstance(error, (aiohttp.ClientError, asyncio.TimeoutError)):
            return True
        
        return False
    
    async def get_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt."""
        delay = self.base_delay * (self.backoff_factor ** attempt)
        return min(delay, self.max_delay)
    
    @asynccontextmanager
    async def retry_context(self) -> AsyncGenerator[None, None]:
        """Context manager for retry logic."""
        attempt = 0
        last_error = None
        
        while attempt <= self.max_retries:
            try:
                yield
                return  # Success, exit retry loop
            except Exception as e:
                last_error = e
                
                if not self.should_retry(attempt, e):
                    raise e
                
                if attempt < self.max_retries:
                    delay = await self.get_delay(attempt)
                    await asyncio.sleep(delay)
                
                attempt += 1
        
        # All retries exhausted
        if last_error:
            raise last_error


class URLUtils:
    """Utility functions for URL manipulation."""
    
    @staticmethod
    def normalize_url(url: str) -> str:
        """Normalize URL format."""
        url = url.strip()
        
        # Add scheme if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Parse and reconstruct to normalize
        parsed = urlparse(url)
        return parsed.geturl()
    
    @staticmethod
    def extract_domain(url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc
    
    @staticmethod
    def is_same_domain(url1: str, url2: str) -> bool:
        """Check if two URLs are from the same domain."""
        return URLUtils.extract_domain(url1) == URLUtils.extract_domain(url2)
    
    @staticmethod
    def build_url(base: str, path: str = "", params: Optional[Dict[str, Any]] = None) -> str:
        """Build URL from components."""
        from urllib.parse import urljoin, urlencode
        
        # Join base and path
        url = urljoin(base.rstrip('/') + '/', path.lstrip('/'))
        
        # Add parameters
        if params:
            query_string = urlencode(params)
            separator = '&' if '?' in url else '?'
            url = f"{url}{separator}{query_string}"
        
        return url


class AsyncBatch:
    """Utility for batching async operations."""
    
    def __init__(self, batch_size: int = 10, max_concurrency: int = 5):
        """
        Initialize async batch processor.
        
        Args:
            batch_size: Number of items per batch
            max_concurrency: Maximum concurrent operations
        """
        self.batch_size = batch_size
        self.semaphore = asyncio.Semaphore(max_concurrency)
    
    async def process_batch(self, items: List[T], processor: Callable[[T], Any]) -> List[Any]:
        """
        Process items in batches.
        
        Args:
            items: Items to process
            processor: Async function to process each item
            
        Returns:
            List of results
        """
        results = []
        
        # Split into batches
        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]
            
            # Process batch concurrently
            async with self.semaphore:
                batch_results = await asyncio.gather(
                    *[processor(item) for item in batch],
                    return_exceptions=True
                )
            
            results.extend(batch_results)
        
        return results
