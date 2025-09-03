"""
Enhanced retry mechanisms for FTP operations.

This module provides intelligent retry strategies with exponential backoff,
jitter, and adaptive timeout handling for improved resilience.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar, Union
import logging

from .circuit_breaker import CircuitBreakerError, get_circuit_breaker
from .metrics import get_metrics_collector

T = TypeVar('T')
logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Available retry strategies."""
    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    ADAPTIVE = "adaptive"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    
    max_attempts: int = 3
    base_delay: float = 1.0  # Base delay in seconds
    max_delay: float = 60.0  # Maximum delay in seconds
    backoff_factor: float = 2.0  # Multiplier for exponential backoff
    jitter: bool = True  # Add random jitter to delays
    jitter_factor: float = 0.1  # Maximum jitter as fraction of delay
    
    # Strategy selection
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    
    # Adaptive strategy parameters
    adaptive_success_threshold: float = 0.8  # Success rate to reduce delays
    adaptive_failure_threshold: float = 0.5  # Failure rate to increase delays
    adaptive_adjustment_factor: float = 1.5  # How much to adjust delays
    
    # Timeout progression
    progressive_timeout: bool = True
    base_timeout: float = 30.0
    timeout_multiplier: float = 1.5
    max_timeout: float = 300.0
    
    # Retry conditions
    retry_on_timeout: bool = True
    retry_on_connection_error: bool = True
    retry_on_server_error: bool = True
    retry_on_rate_limit: bool = True
    retry_on_circuit_breaker: bool = False  # Usually want to respect circuit breaker


@dataclass
class RetryAttempt:
    """Information about a retry attempt."""
    
    attempt_number: int
    delay: float
    timeout: float
    error: Optional[Exception] = None
    start_time: float = 0.0
    end_time: float = 0.0
    
    @property
    def duration(self) -> float:
        """Get attempt duration."""
        if self.end_time == 0.0:
            return time.time() - self.start_time
        return self.end_time - self.start_time


class RetryableError(Exception):
    """Base class for errors that should trigger retries."""
    pass


class NonRetryableError(Exception):
    """Base class for errors that should not trigger retries."""
    pass


class FTPRetryManager:
    """
    Advanced retry manager for FTP operations.
    
    Provides intelligent retry strategies with exponential backoff,
    adaptive delays, and comprehensive error handling.
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        """Initialize the retry manager."""
        self.config = config or RetryConfig()
        self._metrics = get_metrics_collector()
        self._circuit_breaker = get_circuit_breaker()
        self._attempt_history: dict[str, list[RetryAttempt]] = {}
        self._success_rates: dict[str, float] = {}
    
    def _calculate_delay(self, attempt: int, operation_key: Optional[str] = None) -> float:
        """Calculate delay for the given attempt number."""
        if self.config.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.config.base_delay
        
        elif self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.config.base_delay * (self.config.backoff_factor ** (attempt - 1))
        
        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.base_delay * attempt
        
        elif self.config.strategy == RetryStrategy.ADAPTIVE:
            delay = self._calculate_adaptive_delay(attempt, operation_key)
        
        # Apply maximum delay limit
        delay = min(delay, self.config.max_delay)
        
        # Add jitter if enabled
        if self.config.jitter:
            jitter_amount = delay * self.config.jitter_factor
            jitter = random.uniform(-jitter_amount, jitter_amount)
            delay = max(0.1, delay + jitter)  # Ensure minimum delay
        
        return delay
    
    def _calculate_adaptive_delay(self, attempt: int, operation_key: Optional[str] = None) -> float:
        """Calculate adaptive delay based on historical success rates."""
        base_delay = self.config.base_delay * (self.config.backoff_factor ** (attempt - 1))
        
        if not operation_key or operation_key not in self._success_rates:
            return base_delay
        
        success_rate = self._success_rates[operation_key]
        
        # Adjust delay based on success rate
        if success_rate >= self.config.adaptive_success_threshold:
            # High success rate - reduce delays
            adjustment = 1.0 / self.config.adaptive_adjustment_factor
        elif success_rate <= self.config.adaptive_failure_threshold:
            # Low success rate - increase delays
            adjustment = self.config.adaptive_adjustment_factor
        else:
            # Moderate success rate - no adjustment
            adjustment = 1.0
        
        return base_delay * adjustment
    
    def _calculate_timeout(self, attempt: int) -> float:
        """Calculate timeout for the given attempt number."""
        if not self.config.progressive_timeout:
            return self.config.base_timeout
        
        timeout = self.config.base_timeout * (self.config.timeout_multiplier ** (attempt - 1))
        return min(timeout, self.config.max_timeout)
    
    def _should_retry(self, error: Exception, attempt: int) -> bool:
        """Determine if an error should trigger a retry."""
        if attempt >= self.config.max_attempts:
            return False
        
        # Check for non-retryable errors
        if isinstance(error, NonRetryableError):
            return False
        
        # Check for circuit breaker errors
        if isinstance(error, CircuitBreakerError) and not self.config.retry_on_circuit_breaker:
            return False
        
        # Check specific error types
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # Timeout errors
        if self.config.retry_on_timeout and ('timeout' in error_str or 'timeout' in error_type):
            return True
        
        # Connection errors
        if self.config.retry_on_connection_error and (
            'connection' in error_str or 'connect' in error_str or
            'network' in error_str or 'socket' in error_str
        ):
            return True
        
        # Server errors (5xx)
        if self.config.retry_on_server_error and (
            '5' in error_str and any(code in error_str for code in ['500', '501', '502', '503', '504'])
        ):
            return True
        
        # Rate limiting
        if self.config.retry_on_rate_limit and ('rate limit' in error_str or '429' in error_str):
            return True
        
        # Default to retrying for retryable errors
        if isinstance(error, RetryableError):
            return True
        
        return False
    
    def _update_success_rate(self, operation_key: str, success: bool) -> None:
        """Update success rate for an operation."""
        if operation_key not in self._success_rates:
            self._success_rates[operation_key] = 1.0 if success else 0.0
        else:
            # Exponential moving average
            alpha = 0.1  # Learning rate
            current_rate = self._success_rates[operation_key]
            new_value = 1.0 if success else 0.0
            self._success_rates[operation_key] = alpha * new_value + (1 - alpha) * current_rate
    
    async def retry(
        self,
        func: Callable[..., T],
        *args: Any,
        operation_key: Optional[str] = None,
        **kwargs: Any
    ) -> T:
        """
        Execute a function with retry logic.
        
        Args:
            func: Function to execute
            *args: Arguments to pass to the function
            operation_key: Key for tracking operation-specific metrics
            **kwargs: Keyword arguments to pass to the function
        
        Returns:
            Result of the function call
        
        Raises:
            Exception: The last exception if all retries fail
        """
        if operation_key is None:
            operation_key = func.__name__
        
        last_exception = None
        attempts = []
        
        for attempt in range(1, self.config.max_attempts + 1):
            # Calculate delay and timeout for this attempt
            delay = self._calculate_delay(attempt, operation_key) if attempt > 1 else 0.0
            timeout = self._calculate_timeout(attempt)
            
            retry_attempt = RetryAttempt(
                attempt_number=attempt,
                delay=delay,
                timeout=timeout,
                start_time=time.time()
            )
            
            # Wait before retry (except for first attempt)
            if delay > 0:
                logger.debug(f"Retrying {operation_key} in {delay:.2f}s (attempt {attempt}/{self.config.max_attempts})")
                await asyncio.sleep(delay)
            
            try:
                # Execute the function with timeout
                if asyncio.iscoroutinefunction(func):
                    result: T = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
                else:
                    result = func(*args, **kwargs)
                
                # Success - update metrics and return
                retry_attempt.end_time = time.time()
                attempts.append(retry_attempt)
                
                self._update_success_rate(operation_key, True)
                
                if operation_key not in self._attempt_history:
                    self._attempt_history[operation_key] = []
                self._attempt_history[operation_key].extend(attempts)
                
                # Keep only recent history
                if len(self._attempt_history[operation_key]) > 100:
                    self._attempt_history[operation_key] = self._attempt_history[operation_key][-50:]
                
                logger.debug(f"Operation {operation_key} succeeded on attempt {attempt}")
                return result
            
            except Exception as e:
                retry_attempt.error = e
                retry_attempt.end_time = time.time()
                attempts.append(retry_attempt)
                last_exception = e
                
                logger.debug(f"Operation {operation_key} failed on attempt {attempt}: {e}")
                
                # Check if we should retry
                if not self._should_retry(e, attempt):
                    logger.debug(f"Not retrying {operation_key} after attempt {attempt}: {type(e).__name__}")
                    break
                
                # If this is the last attempt, don't continue
                if attempt >= self.config.max_attempts:
                    break
        
        # All retries failed - update metrics and raise last exception
        self._update_success_rate(operation_key, False)
        
        if operation_key not in self._attempt_history:
            self._attempt_history[operation_key] = []
        self._attempt_history[operation_key].extend(attempts)
        
        # Keep only recent history
        if len(self._attempt_history[operation_key]) > 100:
            self._attempt_history[operation_key] = self._attempt_history[operation_key][-50:]
        
        logger.warning(f"Operation {operation_key} failed after {len(attempts)} attempts")
        if last_exception is not None:
            raise last_exception
        else:
            raise RuntimeError(f"Operation {operation_key} failed with no recorded exception")
    
    def get_stats(self, operation_key: Optional[str] = None) -> Dict[str, Any]:
        """Get retry statistics."""
        if operation_key:
            return {
                "operation_key": operation_key,
                "success_rate": self._success_rates.get(operation_key, 0.0),
                "attempt_history": len(self._attempt_history.get(operation_key, [])),
                "recent_attempts": self._attempt_history.get(operation_key, [])[-10:]  # Last 10
            }
        else:
            return {
                "total_operations": len(self._success_rates),
                "success_rates": dict(self._success_rates),
                "attempt_counts": {k: len(v) for k, v in self._attempt_history.items()}
            }
    
    def reset_stats(self, operation_key: Optional[str] = None) -> None:
        """Reset retry statistics."""
        if operation_key:
            self._success_rates.pop(operation_key, None)
            self._attempt_history.pop(operation_key, None)
        else:
            self._success_rates.clear()
            self._attempt_history.clear()


# Global retry manager instance
_global_retry_manager: Optional[FTPRetryManager] = None


def get_retry_manager() -> FTPRetryManager:
    """Get the global retry manager instance."""
    global _global_retry_manager
    if _global_retry_manager is None:
        _global_retry_manager = FTPRetryManager()
    return _global_retry_manager


def reset_retry_manager() -> None:
    """Reset the global retry manager."""
    global _global_retry_manager
    _global_retry_manager = None
