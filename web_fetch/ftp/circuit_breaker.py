"""
Circuit breaker pattern implementation for FTP operations.

This module provides circuit breaker functionality to prevent cascading failures
and improve resilience when dealing with problematic FTP servers.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar, Union
from urllib.parse import urlparse

from .metrics import get_metrics_collector

T = TypeVar('T')


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    
    failure_threshold: int = 5  # Number of failures before opening
    recovery_timeout: float = 60.0  # Seconds before trying half-open
    success_threshold: int = 3  # Successes needed to close from half-open
    timeout: float = 30.0  # Request timeout in seconds
    
    # Failure conditions
    count_timeouts: bool = True
    count_connection_errors: bool = True
    count_authentication_errors: bool = False  # Usually permanent
    count_not_found_errors: bool = False  # Usually not server issues


@dataclass
class CircuitBreakerStats:
    """Statistics for a circuit breaker."""
    
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    total_requests: int = 0
    total_failures: int = 0
    total_successes: int = 0
    state_changes: int = 0
    
    @property
    def failure_rate(self) -> float:
        """Get current failure rate."""
        if self.total_requests == 0:
            return 0.0
        return self.total_failures / self.total_requests
    
    @property
    def uptime_ratio(self) -> float:
        """Get ratio of time in closed state."""
        if self.total_requests == 0:
            return 1.0
        # Simplified calculation - in practice would track state durations
        return 1.0 - self.failure_rate


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""
    
    def __init__(self, host: str, state: CircuitBreakerState, stats: CircuitBreakerStats):
        self.host = host
        self.state = state
        self.stats = stats
        super().__init__(f"Circuit breaker is {state.value} for {host}")


class FTPCircuitBreaker:
    """
    Circuit breaker for FTP operations.
    
    Implements the circuit breaker pattern to prevent cascading failures
    when FTP servers become unreliable or unavailable.
    """
    
    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        """Initialize the circuit breaker."""
        self.config = config or CircuitBreakerConfig()
        self._breakers: Dict[str, CircuitBreakerStats] = {}
        self._lock = asyncio.Lock()
        self._metrics = get_metrics_collector()
    
    def _get_host_key(self, url: str) -> str:
        """Extract host key from URL."""
        parsed = urlparse(url)
        return f"{parsed.hostname}:{parsed.port or 21}"
    
    async def _get_breaker_stats(self, host_key: str) -> CircuitBreakerStats:
        """Get or create circuit breaker stats for a host."""
        if host_key not in self._breakers:
            self._breakers[host_key] = CircuitBreakerStats()
        return self._breakers[host_key]
    
    async def _should_allow_request(self, stats: CircuitBreakerStats) -> bool:
        """Check if request should be allowed based on circuit breaker state."""
        current_time = time.time()
        
        if stats.state == CircuitBreakerState.CLOSED:
            return True
        
        elif stats.state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has passed
            if current_time - stats.last_failure_time >= self.config.recovery_timeout:
                stats.state = CircuitBreakerState.HALF_OPEN
                stats.success_count = 0
                stats.state_changes += 1
                return True
            return False
        
        else:  # CircuitBreakerState.HALF_OPEN
            return True
    
    async def _record_success(self, stats: CircuitBreakerStats) -> None:
        """Record a successful operation."""
        current_time = time.time()
        stats.success_count += 1
        stats.total_successes += 1
        stats.total_requests += 1
        stats.last_success_time = current_time
        
        if stats.state == CircuitBreakerState.HALF_OPEN:
            if stats.success_count >= self.config.success_threshold:
                stats.state = CircuitBreakerState.CLOSED
                stats.failure_count = 0
                stats.state_changes += 1
        elif stats.state == CircuitBreakerState.CLOSED:
            # Reset failure count on success
            stats.failure_count = max(0, stats.failure_count - 1)
    
    async def _record_failure(self, stats: CircuitBreakerStats, error: Exception) -> None:
        """Record a failed operation."""
        current_time = time.time()
        
        # Check if this error type should be counted
        should_count = self._should_count_error(error)
        if not should_count:
            stats.total_requests += 1
            return
        
        stats.failure_count += 1
        stats.total_failures += 1
        stats.total_requests += 1
        stats.last_failure_time = current_time
        
        # Check if we should open the circuit breaker
        if stats.state == CircuitBreakerState.CLOSED:
            if stats.failure_count >= self.config.failure_threshold:
                stats.state = CircuitBreakerState.OPEN
                stats.state_changes += 1
        
        elif stats.state == CircuitBreakerState.HALF_OPEN:
            # Any failure in half-open state goes back to open
            stats.state = CircuitBreakerState.OPEN
            stats.failure_count = self.config.failure_threshold
            stats.state_changes += 1
    
    def _should_count_error(self, error: Exception) -> bool:
        """Determine if an error should count towards circuit breaker failures."""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # Timeout errors
        if self.config.count_timeouts and ('timeout' in error_str or 'timeout' in error_type):
            return True
        
        # Connection errors
        if self.config.count_connection_errors and (
            'connection' in error_str or 'connect' in error_str or
            'network' in error_str or 'socket' in error_str
        ):
            return True
        
        # Authentication errors (usually don't count as they're often permanent)
        if self.config.count_authentication_errors and (
            'auth' in error_str or 'login' in error_str or 'permission' in error_str
        ):
            return True
        
        # Not found errors (usually don't count as they're request-specific)
        if self.config.count_not_found_errors and (
            'not found' in error_str or '404' in error_str
        ):
            return True
        
        # Server errors (5xx) should generally count
        if '5' in error_str and any(code in error_str for code in ['500', '501', '502', '503', '504']):
            return True
        
        return False
    
    async def call(self, func: Callable[..., Any], url: str, *args: Any, **kwargs: Any) -> Any:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: Function to execute
            url: URL for determining the host
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
        
        Returns:
            Result of the function call
        
        Raises:
            CircuitBreakerError: If circuit breaker is open
            Exception: Original exception from the function
        """
        host_key = self._get_host_key(url)
        
        async with self._lock:
            stats = await self._get_breaker_stats(host_key)
            
            # Check if request should be allowed
            if not await self._should_allow_request(stats):
                raise CircuitBreakerError(host_key, stats.state, stats)
        
        # Execute the function with timeout
        try:
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(
                    func(*args, **kwargs), 
                    timeout=self.config.timeout
                )
            else:
                result = func(*args, **kwargs)
            
            # Record success
            async with self._lock:
                await self._record_success(stats)
            
            return result
        
        except Exception as e:
            # Record failure
            async with self._lock:
                await self._record_failure(stats, e)
            
            # Re-raise the original exception
            raise
    
    async def get_stats(self, url: Optional[str] = None) -> Union[CircuitBreakerStats, Dict[str, CircuitBreakerStats]]:
        """
        Get circuit breaker statistics.
        
        Args:
            url: Optional URL to get stats for specific host
        
        Returns:
            Stats for specific host or all hosts
        """
        async with self._lock:
            if url:
                host_key = self._get_host_key(url)
                return await self._get_breaker_stats(host_key)
            else:
                return dict(self._breakers)
    
    async def reset(self, url: Optional[str] = None) -> None:
        """
        Reset circuit breaker state.
        
        Args:
            url: Optional URL to reset specific host, or None to reset all
        """
        async with self._lock:
            if url:
                host_key = self._get_host_key(url)
                if host_key in self._breakers:
                    self._breakers[host_key] = CircuitBreakerStats()
            else:
                self._breakers.clear()
    
    async def force_open(self, url: str) -> None:
        """Force circuit breaker to open state for a host."""
        host_key = self._get_host_key(url)
        async with self._lock:
            stats = await self._get_breaker_stats(host_key)
            stats.state = CircuitBreakerState.OPEN
            stats.failure_count = self.config.failure_threshold
            stats.last_failure_time = time.time()
            stats.state_changes += 1
    
    async def force_close(self, url: str) -> None:
        """Force circuit breaker to closed state for a host."""
        host_key = self._get_host_key(url)
        async with self._lock:
            stats = await self._get_breaker_stats(host_key)
            stats.state = CircuitBreakerState.CLOSED
            stats.failure_count = 0
            stats.success_count = 0
            stats.state_changes += 1


# Global circuit breaker instance
_global_circuit_breaker: Optional[FTPCircuitBreaker] = None


def get_circuit_breaker() -> FTPCircuitBreaker:
    """Get the global circuit breaker instance."""
    global _global_circuit_breaker
    if _global_circuit_breaker is None:
        _global_circuit_breaker = FTPCircuitBreaker()
    return _global_circuit_breaker


def reset_circuit_breaker() -> None:
    """Reset the global circuit breaker."""
    global _global_circuit_breaker
    _global_circuit_breaker = None
