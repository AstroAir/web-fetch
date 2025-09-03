"""
Comprehensive tests for the authentication retry module.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import ClientResponseError, ClientConnectorError

from web_fetch.auth.retry import (
    RetryHandler,
    CircuitBreaker,
    CircuitBreakerState,
    AuthErrorType,
    EnhancedAuthenticationError,
    classify_error,
)
from web_fetch.auth.config import RetryPolicy
from web_fetch.exceptions import WebFetchError, HTTPError, ConnectionError, TimeoutError


class TestErrorClassification:
    """Test error classification for retry logic."""

    def test_classify_http_401_error(self):
        """Test classification of 401 HTTP errors."""
        error = HTTPError("Unauthorized", status_code=401)
        error_type = classify_error(error)
        assert error_type == AuthErrorType.AUTHENTICATION_FAILED

    def test_classify_http_403_error(self):
        """Test classification of 403 HTTP errors."""
        error = HTTPError("Forbidden", status_code=403)
        error_type = classify_error(error)
        assert error_type == AuthErrorType.AUTHORIZATION_FAILED

    def test_classify_http_429_error(self):
        """Test classification of 429 HTTP errors."""
        error = HTTPError("Too Many Requests", status_code=429)
        error_type = classify_error(error)
        assert error_type == AuthErrorType.RATE_LIMITED

    def test_classify_connection_error(self):
        """Test classification of connection errors."""
        error = ConnectionError("Connection failed")
        error_type = classify_error(error)
        assert error_type == AuthErrorType.NETWORK_ERROR

    def test_classify_timeout_error(self):
        """Test classification of timeout errors."""
        error = TimeoutError("Request timed out")
        error_type = classify_error(error)
        assert error_type == AuthErrorType.TIMEOUT

    def test_classify_unknown_error(self):
        """Test classification of unknown errors."""
        error = ValueError("Some other error")
        error_type = classify_error(error)
        assert error_type == AuthErrorType.UNKNOWN

    def test_classify_aiohttp_client_response_error(self):
        """Test classification of aiohttp ClientResponseError."""
        mock_request_info = MagicMock()
        mock_history = ()
        
        error = ClientResponseError(
            request_info=mock_request_info,
            history=mock_history,
            status=401,
            message="Unauthorized"
        )
        error_type = classify_error(error)
        assert error_type == AuthErrorType.AUTHENTICATION_FAILED

    def test_classify_aiohttp_connector_error(self):
        """Test classification of aiohttp ClientConnectorError."""
        error = ClientConnectorError(connection_key=None, os_error=None)
        error_type = classify_error(error)
        assert error_type == AuthErrorType.NETWORK_ERROR


class TestRetryPolicy:
    """Test retry policy configuration."""

    def test_default_retry_policy(self):
        """Test default retry policy creation."""
        policy = RetryPolicy()
        assert policy.max_retries == 3
        assert policy.base_delay == 1.0
        assert policy.max_delay == 60.0
        assert policy.exponential_base == 2.0
        assert policy.jitter == True

    def test_custom_retry_policy(self):
        """Test custom retry policy creation."""
        policy = RetryPolicy(
            max_retries=5,
            base_delay=2.0,
            max_delay=120.0,
            exponential_base=1.5,
            jitter=False
        )
        assert policy.max_retries == 5
        assert policy.base_delay == 2.0
        assert policy.max_delay == 120.0
        assert policy.exponential_base == 1.5
        assert policy.jitter == False

    def test_retry_policy_validation(self):
        """Test retry policy validation."""
        # Test invalid max_retries
        with pytest.raises(ValueError):
            RetryPolicy(max_retries=-1)
        
        # Test invalid base_delay
        with pytest.raises(ValueError):
            RetryPolicy(base_delay=-1.0)
        
        # Test invalid max_delay
        with pytest.raises(ValueError):
            RetryPolicy(max_delay=-1.0)


class TestRetryHandler:
    """Test retry handler functionality."""

    def test_retry_handler_creation(self):
        """Test creating a retry handler."""
        policy = RetryPolicy(max_retries=3)
        handler = RetryHandler(policy)
        assert handler.policy == policy

    @pytest.mark.asyncio
    async def test_successful_operation_no_retry(self):
        """Test successful operation that doesn't need retry."""
        policy = RetryPolicy(max_retries=3)
        handler = RetryHandler(policy)
        
        async def successful_operation():
            return "success"
        
        result = await handler.execute_with_retry(successful_operation)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_on_retryable_error(self):
        """Test retry on retryable errors."""
        policy = RetryPolicy(max_retries=2, base_delay=0.01)
        handler = RetryHandler(policy)
        
        call_count = 0
        
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise HTTPError("Rate limited", status_code=429)
            return "success"
        
        result = await handler.execute_with_retry(failing_operation)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_error(self):
        """Test no retry on non-retryable errors."""
        policy = RetryPolicy(max_retries=3)
        handler = RetryHandler(policy)
        
        call_count = 0
        
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            raise HTTPError("Unauthorized", status_code=401)
        
        with pytest.raises(HTTPError):
            await handler.execute_with_retry(failing_operation)
        
        assert call_count == 1  # Should not retry

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test behavior when max retries are exceeded."""
        policy = RetryPolicy(max_retries=2, base_delay=0.01)
        handler = RetryHandler(policy)
        
        call_count = 0
        
        async def always_failing_operation():
            nonlocal call_count
            call_count += 1
            raise HTTPError("Server error", status_code=500)
        
        with pytest.raises(HTTPError):
            await handler.execute_with_retry(always_failing_operation)
        
        assert call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_delay_calculation(self):
        """Test retry delay calculation."""
        policy = RetryPolicy(
            max_retries=3,
            base_delay=1.0,
            exponential_base=2.0,
            jitter=False
        )
        handler = RetryHandler(policy)
        
        # Test delay calculation
        delay1 = handler._calculate_delay(1)
        delay2 = handler._calculate_delay(2)
        delay3 = handler._calculate_delay(3)
        
        assert delay1 == 1.0  # base_delay * exponential_base^0
        assert delay2 == 2.0  # base_delay * exponential_base^1
        assert delay3 == 4.0  # base_delay * exponential_base^2

    @pytest.mark.asyncio
    async def test_delay_with_jitter(self):
        """Test retry delay with jitter."""
        policy = RetryPolicy(
            max_retries=3,
            base_delay=1.0,
            exponential_base=2.0,
            jitter=True
        )
        handler = RetryHandler(policy)
        
        # Test that jitter produces different delays
        delays = [handler._calculate_delay(1) for _ in range(10)]
        
        # All delays should be around 1.0 but with some variation
        assert all(0.5 <= delay <= 1.5 for delay in delays)
        assert len(set(delays)) > 1  # Should have some variation

    @pytest.mark.asyncio
    async def test_max_delay_limit(self):
        """Test that delays don't exceed max_delay."""
        policy = RetryPolicy(
            max_retries=10,
            base_delay=1.0,
            max_delay=5.0,
            exponential_base=2.0,
            jitter=False
        )
        handler = RetryHandler(policy)
        
        # High retry attempt should be capped at max_delay
        delay = handler._calculate_delay(10)
        assert delay <= 5.0


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_circuit_breaker_creation(self):
        """Test creating a circuit breaker."""
        breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30.0,
            expected_exception=HTTPError
        )
        assert breaker.failure_threshold == 5
        assert breaker.recovery_timeout == 30.0
        assert breaker.expected_exception == HTTPError
        assert breaker.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state."""
        breaker = CircuitBreaker(failure_threshold=3)
        
        async def successful_operation():
            return "success"
        
        result = await breaker.call(successful_operation)
        assert result == "success"
        assert breaker.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failures(self):
        """Test circuit breaker opens after threshold failures."""
        breaker = CircuitBreaker(failure_threshold=2, expected_exception=HTTPError)
        
        async def failing_operation():
            raise HTTPError("Server error", status_code=500)
        
        # First two failures should be allowed
        with pytest.raises(HTTPError):
            await breaker.call(failing_operation)
        
        with pytest.raises(HTTPError):
            await breaker.call(failing_operation)
        
        assert breaker.state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_state_blocks_calls(self):
        """Test circuit breaker blocks calls when open."""
        breaker = CircuitBreaker(failure_threshold=1, expected_exception=HTTPError)
        
        async def failing_operation():
            raise HTTPError("Server error", status_code=500)
        
        # Trigger circuit breaker to open
        with pytest.raises(HTTPError):
            await breaker.call(failing_operation)
        
        assert breaker.state == CircuitBreakerState.OPEN
        
        # Next call should be blocked
        async def any_operation():
            return "should not execute"
        
        with pytest.raises(EnhancedAuthenticationError):
            await breaker.call(any_operation)

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_transition(self):
        """Test circuit breaker transitions to half-open state."""
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.01,  # Very short for testing
            expected_exception=HTTPError
        )
        
        async def failing_operation():
            raise HTTPError("Server error", status_code=500)
        
        # Open the circuit breaker
        with pytest.raises(HTTPError):
            await breaker.call(failing_operation)
        
        assert breaker.state == CircuitBreakerState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(0.02)
        
        # Next call should transition to half-open
        async def test_operation():
            return "test"
        
        result = await breaker.call(test_operation)
        assert result == "test"
        assert breaker.state == CircuitBreakerState.CLOSED  # Should close on success

    @pytest.mark.asyncio
    async def test_circuit_breaker_reset_on_success(self):
        """Test circuit breaker resets failure count on success."""
        breaker = CircuitBreaker(failure_threshold=3, expected_exception=HTTPError)
        
        async def failing_operation():
            raise HTTPError("Server error", status_code=500)
        
        async def successful_operation():
            return "success"
        
        # One failure
        with pytest.raises(HTTPError):
            await breaker.call(failing_operation)
        
        assert breaker.failure_count == 1
        
        # Success should reset count
        result = await breaker.call(successful_operation)
        assert result == "success"
        assert breaker.failure_count == 0


class TestEnhancedAuthenticationError:
    """Test enhanced authentication error."""

    def test_enhanced_error_creation(self):
        """Test creating enhanced authentication error."""
        original_error = HTTPError("Unauthorized", status_code=401)
        error = EnhancedAuthenticationError(
            message="Authentication failed",
            error_type=AuthErrorType.AUTHENTICATION_FAILED,
            original_error=original_error,
            retry_after=30
        )
        
        assert error.message == "Authentication failed"
        assert error.error_type == AuthErrorType.AUTHENTICATION_FAILED
        assert error.original_error == original_error
        assert error.retry_after == 30

    def test_enhanced_error_string_representation(self):
        """Test string representation of enhanced error."""
        error = EnhancedAuthenticationError(
            message="Auth failed",
            error_type=AuthErrorType.AUTHENTICATION_FAILED
        )
        
        error_str = str(error)
        assert "Auth failed" in error_str
        assert "AUTHENTICATION_FAILED" in error_str
