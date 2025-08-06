"""
Enhanced HTTP error handling with intelligent retry strategies.

This module provides comprehensive error handling for different HTTP status codes
with specific retry strategies, error categorization, and recovery mechanisms.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional, Callable, List, Tuple
from urllib.parse import urlparse

from ..exceptions import WebFetchError, RateLimitError, AuthenticationError, ServerError

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Categories of HTTP errors for different handling strategies."""
    
    CLIENT_ERROR = "client_error"           # 4xx errors (usually not retryable)
    SERVER_ERROR = "server_error"           # 5xx errors (often retryable)
    NETWORK_ERROR = "network_error"         # Connection/timeout errors
    RATE_LIMIT_ERROR = "rate_limit_error"   # Rate limiting (429, specific headers)
    AUTH_ERROR = "auth_error"               # Authentication/authorization errors
    REDIRECT_ERROR = "redirect_error"       # Redirect loop or too many redirects
    TIMEOUT_ERROR = "timeout_error"         # Request timeout
    DNS_ERROR = "dns_error"                 # DNS resolution errors
    SSL_ERROR = "ssl_error"                 # SSL/TLS errors
    UNKNOWN_ERROR = "unknown_error"         # Unclassified errors


class RetryStrategy(Enum):
    """Retry strategies for different error types."""
    
    NO_RETRY = "no_retry"                   # Don't retry
    IMMEDIATE = "immediate"                 # Retry immediately
    LINEAR_BACKOFF = "linear_backoff"       # Linear delay increase
    EXPONENTIAL_BACKOFF = "exponential_backoff"  # Exponential delay increase
    FIXED_DELAY = "fixed_delay"             # Fixed delay between retries
    ADAPTIVE = "adaptive"                   # Adaptive based on error type and history


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.1


@dataclass
class ErrorInfo:
    """Information about an error for analysis and retry decisions."""
    
    category: ErrorCategory
    status_code: Optional[int] = None
    error_message: str = ""
    retry_after: Optional[float] = None
    is_retryable: bool = False
    suggested_delay: float = 0.0
    headers: Dict[str, str] = None
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}


class EnhancedErrorHandler:
    """Enhanced error handler with intelligent retry strategies."""
    
    def __init__(self, default_retry_config: Optional[RetryConfig] = None):
        """
        Initialize error handler.
        
        Args:
            default_retry_config: Default retry configuration
        """
        self.default_retry_config = default_retry_config or RetryConfig()
        
        # Error categorization rules
        self.status_code_categories = {
            # 4xx Client Errors (mostly not retryable)
            400: (ErrorCategory.CLIENT_ERROR, False),  # Bad Request
            401: (ErrorCategory.AUTH_ERROR, False),    # Unauthorized
            403: (ErrorCategory.AUTH_ERROR, False),    # Forbidden
            404: (ErrorCategory.CLIENT_ERROR, False),  # Not Found
            405: (ErrorCategory.CLIENT_ERROR, False),  # Method Not Allowed
            406: (ErrorCategory.CLIENT_ERROR, False),  # Not Acceptable
            407: (ErrorCategory.AUTH_ERROR, True),     # Proxy Authentication Required
            408: (ErrorCategory.TIMEOUT_ERROR, True),  # Request Timeout
            409: (ErrorCategory.CLIENT_ERROR, False),  # Conflict
            410: (ErrorCategory.CLIENT_ERROR, False),  # Gone
            411: (ErrorCategory.CLIENT_ERROR, False),  # Length Required
            412: (ErrorCategory.CLIENT_ERROR, False),  # Precondition Failed
            413: (ErrorCategory.CLIENT_ERROR, False),  # Payload Too Large
            414: (ErrorCategory.CLIENT_ERROR, False),  # URI Too Long
            415: (ErrorCategory.CLIENT_ERROR, False),  # Unsupported Media Type
            416: (ErrorCategory.CLIENT_ERROR, False),  # Range Not Satisfiable
            417: (ErrorCategory.CLIENT_ERROR, False),  # Expectation Failed
            418: (ErrorCategory.CLIENT_ERROR, False),  # I'm a teapot
            421: (ErrorCategory.CLIENT_ERROR, False),  # Misdirected Request
            422: (ErrorCategory.CLIENT_ERROR, False),  # Unprocessable Entity
            423: (ErrorCategory.CLIENT_ERROR, False),  # Locked
            424: (ErrorCategory.CLIENT_ERROR, False),  # Failed Dependency
            425: (ErrorCategory.CLIENT_ERROR, False),  # Too Early
            426: (ErrorCategory.CLIENT_ERROR, False),  # Upgrade Required
            428: (ErrorCategory.CLIENT_ERROR, True),   # Precondition Required
            429: (ErrorCategory.RATE_LIMIT_ERROR, True),  # Too Many Requests
            431: (ErrorCategory.CLIENT_ERROR, False),  # Request Header Fields Too Large
            451: (ErrorCategory.CLIENT_ERROR, False),  # Unavailable For Legal Reasons
            
            # 5xx Server Errors (mostly retryable)
            500: (ErrorCategory.SERVER_ERROR, True),   # Internal Server Error
            501: (ErrorCategory.SERVER_ERROR, False),  # Not Implemented
            502: (ErrorCategory.SERVER_ERROR, True),   # Bad Gateway
            503: (ErrorCategory.SERVER_ERROR, True),   # Service Unavailable
            504: (ErrorCategory.SERVER_ERROR, True),   # Gateway Timeout
            505: (ErrorCategory.SERVER_ERROR, False),  # HTTP Version Not Supported
            506: (ErrorCategory.SERVER_ERROR, False),  # Variant Also Negotiates
            507: (ErrorCategory.SERVER_ERROR, True),   # Insufficient Storage
            508: (ErrorCategory.SERVER_ERROR, False),  # Loop Detected
            510: (ErrorCategory.SERVER_ERROR, False),  # Not Extended
            511: (ErrorCategory.SERVER_ERROR, True),   # Network Authentication Required
        }
        
        # Rate limiting headers to check
        self.rate_limit_headers = [
            'retry-after',
            'x-ratelimit-reset',
            'x-rate-limit-reset',
            'x-ratelimit-retry-after',
            'ratelimit-reset',
        ]
        
        # Error history for adaptive strategies
        self.error_history: Dict[str, List[Tuple[float, ErrorCategory]]] = {}
    
    def categorize_error(
        self,
        status_code: Optional[int] = None,
        exception: Optional[Exception] = None,
        headers: Optional[Dict[str, str]] = None,
        url: Optional[str] = None
    ) -> ErrorInfo:
        """
        Categorize an error and determine retry strategy.
        
        Args:
            status_code: HTTP status code
            exception: Exception that occurred
            headers: Response headers
            url: Request URL for context
            
        Returns:
            ErrorInfo with categorization and retry recommendations
        """
        headers = headers or {}
        
        # Handle HTTP status codes
        if status_code:
            category, is_retryable = self.status_code_categories.get(
                status_code, 
                (ErrorCategory.UNKNOWN_ERROR, False)
            )
            
            error_info = ErrorInfo(
                category=category,
                status_code=status_code,
                is_retryable=is_retryable,
                headers=headers
            )
            
            # Special handling for rate limiting
            if status_code == 429 or category == ErrorCategory.RATE_LIMIT_ERROR:
                retry_after = self._parse_retry_after(headers)
                error_info.retry_after = retry_after
                error_info.suggested_delay = retry_after or 60.0
                error_info.is_retryable = True
            
            # Special handling for server errors
            elif category == ErrorCategory.SERVER_ERROR:
                error_info.suggested_delay = self._calculate_server_error_delay(status_code)
            
            return error_info
        
        # Handle exceptions
        if exception:
            return self._categorize_exception(exception, url)
        
        # Unknown error
        return ErrorInfo(
            category=ErrorCategory.UNKNOWN_ERROR,
            error_message="Unknown error occurred",
            is_retryable=False
        )
    
    def _categorize_exception(self, exception: Exception, url: Optional[str]) -> ErrorInfo:
        """Categorize exceptions into error types."""
        exception_name = type(exception).__name__
        error_message = str(exception)
        
        # Network-related exceptions
        if any(name in exception_name.lower() for name in ['connection', 'network', 'socket']):
            return ErrorInfo(
                category=ErrorCategory.NETWORK_ERROR,
                error_message=error_message,
                is_retryable=True,
                suggested_delay=5.0
            )
        
        # Timeout exceptions
        if 'timeout' in exception_name.lower():
            return ErrorInfo(
                category=ErrorCategory.TIMEOUT_ERROR,
                error_message=error_message,
                is_retryable=True,
                suggested_delay=10.0
            )
        
        # DNS exceptions
        if any(name in exception_name.lower() for name in ['dns', 'resolve', 'gaierror']):
            return ErrorInfo(
                category=ErrorCategory.DNS_ERROR,
                error_message=error_message,
                is_retryable=True,
                suggested_delay=30.0
            )
        
        # SSL/TLS exceptions
        if any(name in exception_name.lower() for name in ['ssl', 'tls', 'certificate']):
            return ErrorInfo(
                category=ErrorCategory.SSL_ERROR,
                error_message=error_message,
                is_retryable=False  # SSL errors usually not retryable
            )
        
        # Rate limiting exceptions
        if isinstance(exception, RateLimitError):
            return ErrorInfo(
                category=ErrorCategory.RATE_LIMIT_ERROR,
                error_message=error_message,
                is_retryable=True,
                suggested_delay=60.0
            )
        
        # Authentication exceptions
        if isinstance(exception, AuthenticationError):
            return ErrorInfo(
                category=ErrorCategory.AUTH_ERROR,
                error_message=error_message,
                is_retryable=False
            )
        
        # Server exceptions
        if isinstance(exception, ServerError):
            return ErrorInfo(
                category=ErrorCategory.SERVER_ERROR,
                error_message=error_message,
                is_retryable=True,
                suggested_delay=5.0
            )
        
        # Default to unknown
        return ErrorInfo(
            category=ErrorCategory.UNKNOWN_ERROR,
            error_message=error_message,
            is_retryable=False
        )
    
    def _parse_retry_after(self, headers: Dict[str, str]) -> Optional[float]:
        """Parse Retry-After header value."""
        for header_name in self.rate_limit_headers:
            header_value = headers.get(header_name.lower())
            if header_value:
                try:
                    # Try parsing as seconds
                    return float(header_value)
                except ValueError:
                    # Try parsing as HTTP date (not implemented here)
                    pass
        
        return None
    
    def _calculate_server_error_delay(self, status_code: int) -> float:
        """Calculate delay for server errors based on status code."""
        if status_code == 502:  # Bad Gateway
            return 5.0
        elif status_code == 503:  # Service Unavailable
            return 10.0
        elif status_code == 504:  # Gateway Timeout
            return 15.0
        else:
            return 5.0
    
    def should_retry(
        self,
        error_info: ErrorInfo,
        attempt: int,
        retry_config: Optional[RetryConfig] = None
    ) -> bool:
        """
        Determine if a request should be retried.
        
        Args:
            error_info: Information about the error
            attempt: Current attempt number (0-based)
            retry_config: Retry configuration to use
            
        Returns:
            True if request should be retried
        """
        config = retry_config or self.default_retry_config
        
        # Check if we've exceeded max retries
        if attempt >= config.max_retries:
            return False
        
        # Check if error is retryable
        if not error_info.is_retryable:
            return False
        
        # Special handling for rate limiting
        if error_info.category == ErrorCategory.RATE_LIMIT_ERROR:
            # Always retry rate limit errors (within max retries)
            return True
        
        # Check retry strategy
        if config.strategy == RetryStrategy.NO_RETRY:
            return False
        
        return True
    
    def calculate_delay(
        self,
        error_info: ErrorInfo,
        attempt: int,
        retry_config: Optional[RetryConfig] = None
    ) -> float:
        """
        Calculate delay before next retry attempt.
        
        Args:
            error_info: Information about the error
            attempt: Current attempt number (0-based)
            retry_config: Retry configuration to use
            
        Returns:
            Delay in seconds
        """
        config = retry_config or self.default_retry_config
        
        # Use suggested delay from error info if available
        if error_info.suggested_delay > 0:
            base_delay = error_info.suggested_delay
        else:
            base_delay = config.base_delay
        
        # Calculate delay based on strategy
        if config.strategy == RetryStrategy.IMMEDIATE:
            delay = 0.0
        elif config.strategy == RetryStrategy.FIXED_DELAY:
            delay = base_delay
        elif config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = base_delay * (attempt + 1)
        elif config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = base_delay * (config.backoff_factor ** attempt)
        elif config.strategy == RetryStrategy.ADAPTIVE:
            delay = self._calculate_adaptive_delay(error_info, attempt, config)
        else:
            delay = base_delay
        
        # Apply maximum delay limit
        delay = min(delay, config.max_delay)
        
        # Add jitter if enabled
        if config.jitter and delay > 0:
            jitter_amount = delay * config.jitter_factor
            jitter = random.uniform(-jitter_amount, jitter_amount)
            delay = max(0.0, delay + jitter)
        
        return delay
    
    def _calculate_adaptive_delay(
        self,
        error_info: ErrorInfo,
        attempt: int,
        config: RetryConfig
    ) -> float:
        """Calculate adaptive delay based on error history and type."""
        base_delay = config.base_delay
        
        # Adjust based on error category
        category_multipliers = {
            ErrorCategory.RATE_LIMIT_ERROR: 2.0,
            ErrorCategory.SERVER_ERROR: 1.5,
            ErrorCategory.NETWORK_ERROR: 1.2,
            ErrorCategory.TIMEOUT_ERROR: 1.8,
            ErrorCategory.DNS_ERROR: 3.0,
        }
        
        multiplier = category_multipliers.get(error_info.category, 1.0)
        
        # Apply exponential backoff with category-specific multiplier
        delay = base_delay * multiplier * (config.backoff_factor ** attempt)
        
        return delay
    
    def record_error(self, url: str, error_info: ErrorInfo):
        """Record error for adaptive strategies."""
        domain = urlparse(url).netloc if url else "unknown"
        current_time = time.time()
        
        if domain not in self.error_history:
            self.error_history[domain] = []
        
        self.error_history[domain].append((current_time, error_info.category))
        
        # Keep only recent errors (last hour)
        cutoff_time = current_time - 3600
        self.error_history[domain] = [
            (timestamp, category) 
            for timestamp, category in self.error_history[domain]
            if timestamp > cutoff_time
        ]
    
    def get_error_statistics(self, domain: Optional[str] = None) -> Dict[str, Any]:
        """Get error statistics for analysis."""
        if domain:
            history = self.error_history.get(domain, [])
        else:
            # Aggregate all domains
            history = []
            for domain_history in self.error_history.values():
                history.extend(domain_history)
        
        if not history:
            return {}
        
        # Count errors by category
        category_counts = {}
        for _, category in history:
            category_counts[category.value] = category_counts.get(category.value, 0) + 1
        
        # Calculate error rate (errors per hour)
        current_time = time.time()
        recent_errors = [
            timestamp for timestamp, _ in history
            if current_time - timestamp <= 3600
        ]
        
        return {
            'total_errors': len(history),
            'recent_errors_1h': len(recent_errors),
            'error_rate_per_hour': len(recent_errors),
            'category_breakdown': category_counts,
            'most_common_error': max(category_counts.items(), key=lambda x: x[1])[0] if category_counts else None,
        }
