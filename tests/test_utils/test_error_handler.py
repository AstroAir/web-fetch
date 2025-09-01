"""
Comprehensive tests for the error handler utility.
"""

import pytest
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Optional, Dict, Any

from web_fetch.utils.error_handler import (
    ErrorHandler,
    ErrorHandlerConfig,
    ErrorContext,
    ErrorAction,
    ErrorSeverity,
    RetryStrategy,
    ErrorPattern,
    ErrorHandlerError,
)
from web_fetch.exceptions import (
    WebFetchError,
    HTTPError,
    NetworkError,
    TimeoutError,
    AuthenticationError,
)


class TestErrorHandlerConfig:
    """Test error handler configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ErrorHandlerConfig()
        
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.exponential_backoff is True
        assert config.max_retry_delay == 60.0
        assert config.log_errors is True
        assert config.raise_on_max_retries is True
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = ErrorHandlerConfig(
            max_retries=5,
            retry_delay=2.0,
            exponential_backoff=False,
            max_retry_delay=120.0,
            log_errors=False,
            raise_on_max_retries=False
        )
        
        assert config.max_retries == 5
        assert config.retry_delay == 2.0
        assert config.exponential_backoff is False
        assert config.max_retry_delay == 120.0
        assert config.log_errors is False
        assert config.raise_on_max_retries is False
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Invalid max_retries
        with pytest.raises(ValueError, match="max_retries must be non-negative"):
            ErrorHandlerConfig(max_retries=-1)
        
        # Invalid retry_delay
        with pytest.raises(ValueError, match="retry_delay must be non-negative"):
            ErrorHandlerConfig(retry_delay=-1.0)
        
        # Invalid max_retry_delay
        with pytest.raises(ValueError, match="max_retry_delay must be positive"):
            ErrorHandlerConfig(max_retry_delay=0)


class TestErrorContext:
    """Test error context model."""
    
    def test_context_creation(self):
        """Test error context creation."""
        error = HTTPError("Not Found", 404)
        context = ErrorContext(
            error=error,
            operation="fetch_url",
            url="https://example.com/missing",
            attempt=2,
            metadata={"user_agent": "test-agent"}
        )
        
        assert context.error == error
        assert context.operation == "fetch_url"
        assert context.url == "https://example.com/missing"
        assert context.attempt == 2
        assert context.metadata["user_agent"] == "test-agent"
    
    def test_context_severity_detection(self):
        """Test automatic severity detection."""
        # High severity errors
        auth_error = AuthenticationError("Invalid credentials")
        auth_context = ErrorContext(error=auth_error, operation="login")
        assert auth_context.severity == ErrorSeverity.HIGH
        
        # Medium severity errors
        http_error = HTTPError("Server Error", 500)
        http_context = ErrorContext(error=http_error, operation="fetch")
        assert http_context.severity == ErrorSeverity.MEDIUM
        
        # Low severity errors
        timeout_error = TimeoutError("Request timeout")
        timeout_context = ErrorContext(error=timeout_error, operation="fetch")
        assert timeout_context.severity == ErrorSeverity.LOW
    
    def test_context_serialization(self):
        """Test error context serialization."""
        error = NetworkError("Connection failed")
        context = ErrorContext(
            error=error,
            operation="connect",
            attempt=1
        )
        
        data = context.to_dict()
        
        assert data["error_type"] == "NetworkError"
        assert data["error_message"] == "Connection failed"
        assert data["operation"] == "connect"
        assert data["attempt"] == 1
        assert data["severity"] == "MEDIUM"


class TestErrorPattern:
    """Test error pattern matching."""
    
    def test_pattern_creation(self):
        """Test error pattern creation."""
        pattern = ErrorPattern(
            error_type=HTTPError,
            status_codes=[404, 410],
            message_patterns=["not found", "gone"],
            action=ErrorAction.SKIP,
            max_retries=0
        )
        
        assert pattern.error_type == HTTPError
        assert pattern.status_codes == [404, 410]
        assert pattern.message_patterns == ["not found", "gone"]
        assert pattern.action == ErrorAction.SKIP
        assert pattern.max_retries == 0
    
    def test_pattern_matching(self):
        """Test error pattern matching."""
        pattern = ErrorPattern(
            error_type=HTTPError,
            status_codes=[500, 502, 503],
            action=ErrorAction.RETRY
        )
        
        # Matching error
        matching_error = HTTPError("Internal Server Error", 500)
        assert pattern.matches(matching_error) is True
        
        # Non-matching error (different status code)
        non_matching_error = HTTPError("Not Found", 404)
        assert pattern.matches(non_matching_error) is False
        
        # Non-matching error (different type)
        different_type_error = NetworkError("Connection failed")
        assert pattern.matches(different_type_error) is False
    
    def test_pattern_message_matching(self):
        """Test error pattern message matching."""
        pattern = ErrorPattern(
            error_type=NetworkError,
            message_patterns=["connection.*failed", "timeout"],
            action=ErrorAction.RETRY
        )
        
        # Matching messages
        connection_error = NetworkError("Connection to server failed")
        assert pattern.matches(connection_error) is True
        
        timeout_error = NetworkError("Request timeout occurred")
        assert pattern.matches(timeout_error) is True
        
        # Non-matching message
        other_error = NetworkError("DNS resolution failed")
        assert pattern.matches(other_error) is False


class TestRetryStrategy:
    """Test retry strategy functionality."""
    
    def test_fixed_delay_strategy(self):
        """Test fixed delay retry strategy."""
        strategy = RetryStrategy.fixed_delay(delay=2.0)
        
        assert strategy.get_delay(attempt=1) == 2.0
        assert strategy.get_delay(attempt=5) == 2.0
        assert strategy.should_retry(attempt=3, max_retries=5) is True
        assert strategy.should_retry(attempt=5, max_retries=5) is False
    
    def test_exponential_backoff_strategy(self):
        """Test exponential backoff retry strategy."""
        strategy = RetryStrategy.exponential_backoff(
            initial_delay=1.0,
            multiplier=2.0,
            max_delay=10.0
        )
        
        assert strategy.get_delay(attempt=1) == 1.0
        assert strategy.get_delay(attempt=2) == 2.0
        assert strategy.get_delay(attempt=3) == 4.0
        assert strategy.get_delay(attempt=4) == 8.0
        assert strategy.get_delay(attempt=5) == 10.0  # Capped at max_delay
    
    def test_linear_backoff_strategy(self):
        """Test linear backoff retry strategy."""
        strategy = RetryStrategy.linear_backoff(
            initial_delay=1.0,
            increment=0.5,
            max_delay=5.0
        )
        
        assert strategy.get_delay(attempt=1) == 1.0
        assert strategy.get_delay(attempt=2) == 1.5
        assert strategy.get_delay(attempt=3) == 2.0
        assert strategy.get_delay(attempt=10) == 5.0  # Capped at max_delay
    
    def test_custom_strategy(self):
        """Test custom retry strategy."""
        def custom_delay_func(attempt: int) -> float:
            return min(attempt * 0.5, 3.0)
        
        strategy = RetryStrategy.custom(
            delay_func=custom_delay_func,
            max_retries=5
        )
        
        assert strategy.get_delay(attempt=1) == 0.5
        assert strategy.get_delay(attempt=2) == 1.0
        assert strategy.get_delay(attempt=6) == 3.0
        assert strategy.should_retry(attempt=4, max_retries=5) is True
        assert strategy.should_retry(attempt=5, max_retries=5) is False


class TestErrorHandler:
    """Test error handler functionality."""
    
    @pytest.fixture
    def config(self):
        """Create error handler configuration."""
        return ErrorHandlerConfig(
            max_retries=3,
            retry_delay=0.1,  # Short delay for testing
            exponential_backoff=True
        )
    
    @pytest.fixture
    def handler(self, config):
        """Create error handler."""
        return ErrorHandler(config)
    
    def test_handler_initialization(self, handler):
        """Test error handler initialization."""
        assert handler.config.max_retries == 3
        assert handler.config.retry_delay == 0.1
        assert len(handler._patterns) == 0
        assert len(handler._custom_handlers) == 0
    
    def test_add_error_pattern(self, handler):
        """Test adding error patterns."""
        pattern = ErrorPattern(
            error_type=HTTPError,
            status_codes=[500, 502, 503],
            action=ErrorAction.RETRY,
            max_retries=5
        )
        
        handler.add_pattern(pattern)
        
        assert len(handler._patterns) == 1
        assert handler._patterns[0] == pattern
    
    def test_add_custom_handler(self, handler):
        """Test adding custom error handlers."""
        def custom_handler(context: ErrorContext) -> ErrorAction:
            if isinstance(context.error, NetworkError):
                return ErrorAction.RETRY
            return ErrorAction.RAISE
        
        handler.add_custom_handler(NetworkError, custom_handler)
        
        assert NetworkError in handler._custom_handlers
        assert handler._custom_handlers[NetworkError] == custom_handler
    
    @pytest.mark.asyncio
    async def test_handle_retryable_error(self, handler):
        """Test handling retryable errors."""
        # Add pattern for retryable errors
        pattern = ErrorPattern(
            error_type=NetworkError,
            action=ErrorAction.RETRY,
            max_retries=2
        )
        handler.add_pattern(pattern)
        
        call_count = 0
        
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise NetworkError("Connection failed")
            return "success"
        
        result = await handler.handle_with_retry(
            failing_operation,
            operation="test_operation"
        )
        
        assert result == "success"
        assert call_count == 3  # Initial + 2 retries
    
    @pytest.mark.asyncio
    async def test_handle_non_retryable_error(self, handler):
        """Test handling non-retryable errors."""
        # Add pattern for non-retryable errors
        pattern = ErrorPattern(
            error_type=AuthenticationError,
            action=ErrorAction.RAISE,
            max_retries=0
        )
        handler.add_pattern(pattern)
        
        async def failing_operation():
            raise AuthenticationError("Invalid credentials")
        
        with pytest.raises(AuthenticationError):
            await handler.handle_with_retry(
                failing_operation,
                operation="auth_operation"
            )
    
    @pytest.mark.asyncio
    async def test_handle_skip_error(self, handler):
        """Test handling errors that should be skipped."""
        # Add pattern for skippable errors
        pattern = ErrorPattern(
            error_type=HTTPError,
            status_codes=[404],
            action=ErrorAction.SKIP
        )
        handler.add_pattern(pattern)
        
        async def failing_operation():
            raise HTTPError("Not Found", 404)
        
        result = await handler.handle_with_retry(
            failing_operation,
            operation="fetch_operation",
            default_on_skip="skipped"
        )
        
        assert result == "skipped"
    
    @pytest.mark.asyncio
    async def test_exponential_backoff(self, handler):
        """Test exponential backoff retry delays."""
        handler.config.exponential_backoff = True
        handler.config.retry_delay = 0.1
        
        pattern = ErrorPattern(
            error_type=NetworkError,
            action=ErrorAction.RETRY,
            max_retries=3
        )
        handler.add_pattern(pattern)
        
        call_times = []
        
        async def failing_operation():
            call_times.append(asyncio.get_event_loop().time())
            raise NetworkError("Connection failed")
        
        with pytest.raises(NetworkError):
            await handler.handle_with_retry(
                failing_operation,
                operation="test_operation"
            )
        
        # Verify exponential backoff delays
        assert len(call_times) == 4  # Initial + 3 retries
        
        # Check that delays increase exponentially
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        delay3 = call_times[3] - call_times[2]
        
        assert delay1 >= 0.1  # First retry delay
        assert delay2 >= delay1 * 1.5  # Should be roughly double
        assert delay3 >= delay2 * 1.5  # Should be roughly double again
    
    @pytest.mark.asyncio
    async def test_custom_error_handler(self, handler):
        """Test custom error handler function."""
        def custom_handler(context: ErrorContext) -> ErrorAction:
            if context.attempt < 2:
                return ErrorAction.RETRY
            else:
                return ErrorAction.RAISE
        
        handler.add_custom_handler(TimeoutError, custom_handler)
        
        call_count = 0
        
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("Request timeout")
        
        with pytest.raises(TimeoutError):
            await handler.handle_with_retry(
                failing_operation,
                operation="timeout_operation"
            )
        
        assert call_count == 2  # Initial + 1 retry (custom handler allows only 1 retry)
    
    @pytest.mark.asyncio
    async def test_error_context_enrichment(self, handler):
        """Test error context enrichment."""
        contexts = []
        
        def context_enricher(context: ErrorContext) -> ErrorContext:
            context.metadata["enriched"] = True
            context.metadata["timestamp"] = "2023-01-01T00:00:00Z"
            contexts.append(context)
            return context
        
        handler.add_context_enricher(context_enricher)
        
        async def failing_operation():
            raise NetworkError("Connection failed")
        
        with pytest.raises(NetworkError):
            await handler.handle_with_retry(
                failing_operation,
                operation="enrichment_test",
                url="https://example.com"
            )
        
        # Verify context was enriched
        assert len(contexts) > 0
        context = contexts[0]
        assert context.metadata["enriched"] is True
        assert context.metadata["timestamp"] == "2023-01-01T00:00:00Z"
        assert context.url == "https://example.com"
    
    @pytest.mark.asyncio
    async def test_error_logging(self, handler):
        """Test error logging functionality."""
        handler.config.log_errors = True
        
        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            async def failing_operation():
                raise HTTPError("Server Error", 500)
            
            with pytest.raises(HTTPError):
                await handler.handle_with_retry(
                    failing_operation,
                    operation="logging_test"
                )
            
            # Verify error was logged
            mock_logger.error.assert_called()
    
    def test_get_error_stats(self, handler):
        """Test getting error statistics."""
        # Simulate some error handling
        handler._error_counts["NetworkError"] = 5
        handler._error_counts["HTTPError"] = 3
        handler._retry_counts["NetworkError"] = 12
        handler._retry_counts["HTTPError"] = 6
        
        stats = handler.get_error_stats()
        
        assert stats["total_errors"] == 8
        assert stats["total_retries"] == 18
        assert stats["error_types"]["NetworkError"]["count"] == 5
        assert stats["error_types"]["NetworkError"]["retries"] == 12
        assert stats["error_types"]["HTTPError"]["count"] == 3
        assert stats["error_types"]["HTTPError"]["retries"] == 6
    
    def test_reset_stats(self, handler):
        """Test resetting error statistics."""
        # Add some stats
        handler._error_counts["TestError"] = 10
        handler._retry_counts["TestError"] = 20
        
        # Reset stats
        handler.reset_stats()
        
        assert len(handler._error_counts) == 0
        assert len(handler._retry_counts) == 0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, handler):
        """Test integration with circuit breaker pattern."""
        from web_fetch.utils.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
        
        # Create circuit breaker
        cb_config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1)
        circuit_breaker = CircuitBreaker(cb_config)
        
        # Integrate with error handler
        handler.set_circuit_breaker(circuit_breaker)
        
        call_count = 0
        
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            raise NetworkError("Connection failed")
        
        # Should fail and open circuit breaker
        with pytest.raises(NetworkError):
            await handler.handle_with_retry(
                failing_operation,
                operation="circuit_breaker_test"
            )
        
        # Circuit breaker should now be open
        assert circuit_breaker.state.name == "OPEN"
