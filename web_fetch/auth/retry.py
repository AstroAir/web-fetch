"""
Enhanced retry and error handling system for authentication.

This module provides comprehensive retry policies, circuit breaker patterns,
and error handling for authentication operations.
"""

from __future__ import annotations

import asyncio
import random
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union
import logging

from .config import RetryPolicy
from ..exceptions import WebFetchError


logger = logging.getLogger(__name__)


class AuthErrorType(str, Enum):
    """Types of authentication errors."""
    
    INVALID_CREDENTIALS = "invalid_credentials"
    EXPIRED_TOKEN = "expired_token"
    RATE_LIMITED = "rate_limited"
    NETWORK_ERROR = "network_error"
    SERVER_ERROR = "server_error"
    CONFIGURATION_ERROR = "configuration_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class AuthenticationError(WebFetchError):
    """Enhanced authentication error with retry information."""
    
    def __init__(
        self,
        message: str,
        error_type: AuthErrorType = AuthErrorType.UNKNOWN,
        status_code: Optional[int] = None,
        retry_after: Optional[float] = None,
        is_retryable: bool = True,
        original_error: Optional[Exception] = None
    ):
        """
        Initialize authentication error.
        
        Args:
            message: Error message
            error_type: Type of authentication error
            status_code: HTTP status code if applicable
            retry_after: Suggested retry delay in seconds
            is_retryable: Whether this error is retryable
            original_error: Original exception that caused this error
        """
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code
        self.retry_after = retry_after
        self.is_retryable = is_retryable
        self.original_error = original_error
        self.timestamp = time.time()
    
    def __str__(self) -> str:
        """String representation of the error."""
        parts = [f"AuthenticationError({self.error_type.value}): {super().__str__()}"]
        if self.status_code:
            parts.append(f"Status: {self.status_code}")
        if self.retry_after:
            parts.append(f"Retry after: {self.retry_after}s")
        return " | ".join(parts)


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""
    
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker for authentication operations."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = AuthenticationError
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before attempting recovery
            expected_exception: Exception type that triggers circuit breaker
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitBreakerState.CLOSED
    
    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit breaker."""
        return (
            self.state == CircuitBreakerState.OPEN
            and self.last_failure_time is not None
            and time.time() - self.last_failure_time >= self.recovery_timeout
        )
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            AuthenticationError: If circuit is open or function fails
        """
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                logger.info("Circuit breaker transitioning to HALF_OPEN")
            else:
                raise AuthenticationError(
                    "Circuit breaker is OPEN - authentication service unavailable",
                    error_type=AuthErrorType.SERVER_ERROR,
                    is_retryable=False
                )
        
        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            
            # Success - reset circuit breaker
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                logger.info("Circuit breaker reset to CLOSED")
            
            return result
            
        except self.expected_exception as e:
            self._record_failure()
            raise
        except Exception as e:
            # Unexpected exception - don't trigger circuit breaker
            raise AuthenticationError(
                f"Unexpected error in authentication: {str(e)}",
                error_type=AuthErrorType.UNKNOWN,
                original_error=e
            )
    
    def _record_failure(self) -> None:
        """Record a failure and update circuit breaker state."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")


class RetryHandler:
    """Handles retry logic for authentication operations."""
    
    def __init__(self, policy: RetryPolicy, circuit_breaker: Optional[CircuitBreaker] = None):
        """
        Initialize retry handler.
        
        Args:
            policy: Retry policy configuration
            circuit_breaker: Optional circuit breaker for failure protection
        """
        self.policy = policy
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt."""
        if attempt == 0:
            return 0
        
        # Exponential backoff
        delay = self.policy.initial_delay * (self.policy.exponential_base ** (attempt - 1))
        delay = min(delay, self.policy.max_delay)
        
        # Add jitter if enabled
        if self.policy.jitter:
            jitter = random.uniform(0, delay * 0.1)  # Up to 10% jitter
            delay += jitter
        
        return delay
    
    def _should_retry(self, error: AuthenticationError, attempt: int) -> bool:
        """Determine if an error should be retried."""
        if attempt >= self.policy.max_attempts:
            return False
        
        if not error.is_retryable:
            return False
        
        # Check if status code is retryable
        if error.status_code and error.status_code not in self.policy.retry_on_status_codes:
            return False
        
        # Don't retry certain error types
        non_retryable_types = {
            AuthErrorType.INVALID_CREDENTIALS,
            AuthErrorType.CONFIGURATION_ERROR
        }
        if error.error_type in non_retryable_types:
            return False
        
        return True
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        operation_name: str = "authentication",
        **kwargs
    ) -> Any:
        """
        Execute a function with retry logic.
        
        Args:
            func: Function to execute
            *args: Function arguments
            operation_name: Name of the operation for logging
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            AuthenticationError: If all retry attempts fail
        """
        last_error: Optional[AuthenticationError] = None
        
        for attempt in range(self.policy.max_attempts):
            try:
                # Calculate and apply delay
                if attempt > 0:
                    delay = self._calculate_delay(attempt)
                    logger.debug(f"Retrying {operation_name} in {delay:.2f}s (attempt {attempt + 1}/{self.policy.max_attempts})")
                    await asyncio.sleep(delay)
                
                # Execute with circuit breaker protection
                result = await self.circuit_breaker.call(func, *args, **kwargs)
                
                if attempt > 0:
                    logger.info(f"{operation_name} succeeded on attempt {attempt + 1}")
                
                return result
                
            except AuthenticationError as e:
                last_error = e
                
                # Use retry_after from error if provided
                if e.retry_after and attempt < self.policy.max_attempts - 1:
                    logger.debug(f"Server requested retry after {e.retry_after}s")
                    await asyncio.sleep(e.retry_after)
                    continue
                
                # Check if we should retry
                if not self._should_retry(e, attempt + 1):
                    logger.error(f"{operation_name} failed with non-retryable error: {e}")
                    raise
                
                logger.warning(f"{operation_name} failed on attempt {attempt + 1}: {e}")
        
        # All retries exhausted
        if last_error:
            logger.error(f"{operation_name} failed after {self.policy.max_attempts} attempts")
            raise last_error
        else:
            raise AuthenticationError(
                f"{operation_name} failed after {self.policy.max_attempts} attempts",
                error_type=AuthErrorType.UNKNOWN
            )


def classify_error(exception: Exception, status_code: Optional[int] = None) -> AuthenticationError:
    """
    Classify an exception into an AuthenticationError.
    
    Args:
        exception: Original exception
        status_code: HTTP status code if applicable
        
    Returns:
        Classified AuthenticationError
    """
    if isinstance(exception, AuthenticationError):
        return exception
    
    message = str(exception)
    error_type = AuthErrorType.UNKNOWN
    is_retryable = True
    retry_after = None
    
    # Classify based on status code
    if status_code:
        if status_code == 401:
            error_type = AuthErrorType.INVALID_CREDENTIALS
            is_retryable = False
        elif status_code == 403:
            error_type = AuthErrorType.INVALID_CREDENTIALS
            is_retryable = False
        elif status_code == 429:
            error_type = AuthErrorType.RATE_LIMITED
            # Try to extract retry-after from headers if available
            retry_after = 60.0  # Default retry after 1 minute
        elif 500 <= status_code < 600:
            error_type = AuthErrorType.SERVER_ERROR
        elif status_code == 408:
            error_type = AuthErrorType.TIMEOUT
    
    # Classify based on exception type
    elif isinstance(exception, asyncio.TimeoutError):
        error_type = AuthErrorType.TIMEOUT
    elif isinstance(exception, (ConnectionError, OSError)):
        error_type = AuthErrorType.NETWORK_ERROR
    elif "credential" in message.lower() or "auth" in message.lower():
        error_type = AuthErrorType.INVALID_CREDENTIALS
        is_retryable = False
    elif "config" in message.lower():
        error_type = AuthErrorType.CONFIGURATION_ERROR
        is_retryable = False
    
    return AuthenticationError(
        message=message,
        error_type=error_type,
        status_code=status_code,
        retry_after=retry_after,
        is_retryable=is_retryable,
        original_error=exception
    )
