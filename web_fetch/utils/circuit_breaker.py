"""
Circuit breaker pattern implementation for resilient web fetching.

This module provides a circuit breaker to prevent cascading failures when
external services are experiencing issues.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, Optional
from urllib.parse import urlparse


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    
    failure_threshold: int = 5  # Number of failures before opening
    recovery_timeout: float = 60.0  # Seconds before trying half-open
    success_threshold: int = 3  # Successes needed to close from half-open
    timeout: float = 30.0  # Request timeout in seconds
    
    # What constitutes a failure
    failure_exceptions: tuple = (Exception,)
    failure_status_codes: set = field(default_factory=lambda: {500, 502, 503, 504})


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring."""
    
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    blocked_requests: int = 0
    state_changes: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open and blocking requests."""
    
    def __init__(self, message: str, stats: CircuitBreakerStats) -> None:
        super().__init__(message)
        self.stats = stats


class CircuitBreaker:
    """
    Circuit breaker implementation for resilient service calls.
    
    Prevents cascading failures by temporarily blocking requests to failing services
    and allowing them to recover.
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> None:
        """
        Initialize circuit breaker.
        
        Args:
            name: Unique name for this circuit breaker
            config: Configuration options
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.stats = CircuitBreakerStats()
        
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._lock = asyncio.Lock()
    
    async def call(
        self,
        func: Callable[..., Awaitable[Any]] | Callable[..., Any],
        *args: Any,
        **kwargs: Any
    ) -> Any:
        """
        Execute a function call through the circuit breaker.
        
        Args:
            func: Function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of the function call
            
        Raises:
            CircuitBreakerError: If circuit is open
            Any exception raised by the function
        """
        # Thread-safe state management - prevent race conditions during state transitions
        async with self._lock:
            # Track total request count for monitoring and statistics
            self.stats.total_requests += 1

            # State transition logic: CLOSED -> OPEN
            # If we're in normal operation (CLOSED) but have exceeded failure threshold,
            # transition to OPEN state to start blocking requests and give service time to recover
            if self.state == CircuitState.CLOSED and self._should_open():
                await self._open_circuit()

            # State transition logic: OPEN -> HALF_OPEN
            # If we're in failure mode (OPEN) but enough time has passed since last failure,
            # transition to HALF_OPEN to test if the service has recovered
            elif self.state == CircuitState.OPEN and self._should_attempt_reset():
                await self._half_open_circuit()

            # Request blocking logic for OPEN state
            # When circuit is OPEN, immediately reject requests without calling the service
            # This prevents cascading failures and gives the failing service time to recover
            if self.state == CircuitState.OPEN:
                self.stats.blocked_requests += 1
                raise CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is OPEN. Service appears to be failing.",
                    self.stats
                )

        # Execute the actual function call outside the lock to avoid blocking other requests
        # This allows concurrent execution while maintaining thread-safe state management
        try:
            # Timeout handling - prevent hanging requests from keeping circuit in bad state
            if self.config.timeout > 0:
                # Handle both async and sync functions with timeout protection
                # Async functions are awaited directly, sync functions are run in thread pool
                if asyncio.iscoroutinefunction(func):
                    result = await asyncio.wait_for(func(*args, **kwargs), timeout=self.config.timeout)
                else:
                    # Run sync function in thread pool to avoid blocking event loop
                    result = await asyncio.wait_for(
                        asyncio.to_thread(func, *args, **kwargs),
                        timeout=self.config.timeout
                    )
            else:
                # No timeout configured - execute function directly
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    # Still use thread pool for sync functions to maintain async compatibility
                    result = await asyncio.to_thread(func, *args, **kwargs)

            # Success handling - update circuit breaker state and statistics
            # This may trigger state transitions (HALF_OPEN -> CLOSED) if enough successes occur
            await self._on_success()
            return result

        except Exception as e:
            # Failure handling - update failure counts and potentially trigger state transitions
            # This may cause CLOSED -> OPEN or HALF_OPEN -> OPEN transitions
            await self._on_failure(e)
            # Re-raise the original exception so caller can handle it appropriately
            raise
    
    def _should_open(self) -> bool:
        """Check if circuit should be opened due to failures."""
        return self._failure_count >= self.config.failure_threshold
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt to reset from open to half-open."""
        return (time.time() - self._last_failure_time) >= self.config.recovery_timeout
    
    async def _open_circuit(self) -> None:
        """Transition circuit to OPEN state."""
        self.state = CircuitState.OPEN
        self.stats.state_changes += 1
        self._last_failure_time = time.time()
    
    async def _half_open_circuit(self) -> None:
        """Transition circuit to HALF_OPEN state."""
        self.state = CircuitState.HALF_OPEN
        self.stats.state_changes += 1
        self._success_count = 0
    
    async def _close_circuit(self) -> None:
        """Transition circuit to CLOSED state."""
        self.state = CircuitState.CLOSED
        self.stats.state_changes += 1
        self._failure_count = 0
        self._success_count = 0
    
    async def _on_success(self) -> None:
        """Handle successful function call with state-specific logic."""
        async with self._lock:
            # Update success statistics for monitoring
            self.stats.successful_requests += 1
            self.stats.last_success_time = datetime.now()

            # State-specific success handling
            if self.state == CircuitState.HALF_OPEN:
                # In HALF_OPEN state, we're testing if service has recovered
                # Count consecutive successes and close circuit if threshold is met
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    # Service appears to have recovered - return to normal operation
                    await self._close_circuit()
            elif self.state == CircuitState.CLOSED:
                # In CLOSED state, successes help "heal" previous failures
                # Gradually reduce failure count to prevent premature circuit opening
                # This implements a "leaky bucket" approach where successes offset failures
                self._failure_count = max(0, self._failure_count - 1)
    
    async def _on_failure(self, exception: Exception) -> None:
        """Handle failed function call with intelligent failure classification."""
        async with self._lock:
            # Only count exceptions that indicate service problems, not client errors
            # This prevents circuit breaker from opening due to client-side issues
            if self._is_failure(exception):
                # Update failure statistics for monitoring and alerting
                self.stats.failed_requests += 1
                self.stats.last_failure_time = datetime.now()

                # Increment failure counter for circuit breaker logic
                self._failure_count += 1
                # Track timestamp for recovery timeout calculation
                self._last_failure_time = time.time()

                # State-specific failure handling
                if self.state == CircuitState.HALF_OPEN:
                    # In HALF_OPEN state, any failure means service hasn't recovered
                    # Immediately return to OPEN state to continue blocking requests
                    # This prevents flapping between HALF_OPEN and OPEN states
                    await self._open_circuit()

    def _is_failure(self, exception: Exception) -> bool:
        """
        Determine if an exception should be counted as a circuit breaker failure.

        This method implements intelligent failure classification to distinguish
        between service failures (which should trigger circuit breaker) and
        client errors (which should not affect circuit state).
        """
        # Check if exception type indicates a service failure
        # Examples: ConnectionError, TimeoutError, ServerError
        if isinstance(exception, self.config.failure_exceptions):
            return True

        # Check HTTP status codes for service-level failures
        # Only server errors (5xx) should trigger circuit breaker
        # Client errors (4xx) indicate request problems, not service failures
        status = getattr(exception, "status_code", None)
        if status is not None:
            try:
                # Convert status to integer, handling various formats
                code = int(status)
            except (TypeError, ValueError):
                # Invalid status code format - don't count as failure
                return False
            # Check if status code indicates server-side failure
            # Default: 500, 502, 503, 504 (server errors)
            return code in self.config.failure_status_codes

        # Unknown exception type without status code - don't count as failure
        # This conservative approach prevents false positives
        return False
    
    def get_stats(self) -> CircuitBreakerStats:
        """Get current circuit breaker statistics."""
        return self.stats
    
    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        self.state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self.stats.state_changes += 1


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers by service/host."""
    
    def __init__(self) -> None:
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
    
    async def get_breaker(self, url: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """
        Get or create a circuit breaker for a URL/service.
        
        Args:
            url: URL to get circuit breaker for
            config: Optional configuration for new circuit breakers
            
        Returns:
            CircuitBreaker instance for the service
        """
        # Extract host from URL for circuit breaker key
        try:
            parsed = urlparse(url)
            key = f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            key = url
        
        async with self._lock:
            if key not in self._breakers:
                self._breakers[key] = CircuitBreaker(key, config)
            return self._breakers[key]
    
    def get_all_stats(self) -> Dict[str, CircuitBreakerStats]:
        """Get statistics for all circuit breakers."""
        return {name: breaker.get_stats() for name, breaker in self._breakers.items()}


# Global registry instance
_global_registry = CircuitBreakerRegistry()


async def with_circuit_breaker(
    url: str,
    func: Callable[..., Awaitable[Any]] | Callable[..., Any],
    *args: Any,
    config: Optional[CircuitBreakerConfig] = None,
    **kwargs: Any
) -> Any:
    """
    Convenience function to execute a function with circuit breaker protection.
    
    Args:
        url: URL/service identifier for circuit breaker
        func: Function to execute
        *args: Positional arguments for function
        config: Optional circuit breaker configuration
        **kwargs: Keyword arguments for function
        
    Returns:
        Result of function execution
    """
    breaker = await _global_registry.get_breaker(url, config)
    return await breaker.call(func, *args, **kwargs)


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig", 
    "CircuitBreakerError",
    "CircuitBreakerRegistry",
    "CircuitBreakerStats",
    "CircuitState",
    "with_circuit_breaker",
]
