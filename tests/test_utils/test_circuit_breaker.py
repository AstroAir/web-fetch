"""
Comprehensive tests for the circuit breaker utility.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

from web_fetch.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerState,
    CircuitBreakerError,
    with_circuit_breaker,
)
from web_fetch.exceptions import WebFetchError, NetworkError, TimeoutError


class TestCircuitBreakerConfig:
    """Test circuit breaker configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = CircuitBreakerConfig()
        
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 60.0
        assert config.expected_exception == Exception
        assert config.name == "default"
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=120.0,
            expected_exception=NetworkError,
            name="custom_breaker"
        )
        
        assert config.failure_threshold == 10
        assert config.recovery_timeout == 120.0
        assert config.expected_exception == NetworkError
        assert config.name == "custom_breaker"
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Invalid failure threshold
        with pytest.raises(ValueError, match="failure_threshold must be positive"):
            CircuitBreakerConfig(failure_threshold=0)
        
        # Invalid recovery timeout
        with pytest.raises(ValueError, match="recovery_timeout must be positive"):
            CircuitBreakerConfig(recovery_timeout=-1.0)


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=1.0,  # Short timeout for testing
            expected_exception=NetworkError
        )
    
    @pytest.fixture
    def circuit_breaker(self, config):
        """Create circuit breaker instance."""
        return CircuitBreaker(config)
    
    def test_initial_state(self, circuit_breaker):
        """Test initial circuit breaker state."""
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.last_failure_time is None
        assert circuit_breaker.success_count == 0
    
    @pytest.mark.asyncio
    async def test_successful_calls(self, circuit_breaker):
        """Test successful function calls."""
        @circuit_breaker
        async def successful_function():
            return "success"
        
        # Multiple successful calls
        for _ in range(5):
            result = await successful_function()
            assert result == "success"
        
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.success_count == 5
    
    @pytest.mark.asyncio
    async def test_failure_threshold(self, circuit_breaker):
        """Test circuit breaker opens after failure threshold."""
        @circuit_breaker
        async def failing_function():
            raise NetworkError("Network failure")
        
        # Fail up to threshold
        for i in range(3):
            with pytest.raises(NetworkError):
                await failing_function()
            assert circuit_breaker.failure_count == i + 1
            assert circuit_breaker.state == CircuitBreakerState.CLOSED
        
        # Next failure should open the circuit
        with pytest.raises(NetworkError):
            await failing_function()
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.failure_count == 3
    
    @pytest.mark.asyncio
    async def test_open_circuit_blocks_calls(self, circuit_breaker):
        """Test that open circuit blocks calls."""
        @circuit_breaker
        async def test_function():
            return "should not execute"
        
        # Force circuit to open
        circuit_breaker._state = CircuitBreakerState.OPEN
        circuit_breaker._last_failure_time = time.time()
        
        # Call should be blocked
        with pytest.raises(CircuitBreakerError, match="Circuit breaker is OPEN"):
            await test_function()
    
    @pytest.mark.asyncio
    async def test_half_open_recovery(self, circuit_breaker):
        """Test half-open state and recovery."""
        @circuit_breaker
        async def recovery_function():
            return "recovered"
        
        # Force circuit to open
        circuit_breaker._state = CircuitBreakerState.OPEN
        circuit_breaker._last_failure_time = time.time() - 2.0  # Past recovery timeout
        
        # First call should transition to half-open
        result = await recovery_function()
        assert result == "recovered"
        assert circuit_breaker.state == CircuitBreakerState.CLOSED  # Successful call closes circuit
        assert circuit_breaker.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_half_open_failure(self, circuit_breaker):
        """Test failure in half-open state."""
        @circuit_breaker
        async def failing_recovery_function():
            raise NetworkError("Still failing")
        
        # Force circuit to half-open
        circuit_breaker._state = CircuitBreakerState.OPEN
        circuit_breaker._last_failure_time = time.time() - 2.0
        
        # Failure in half-open should reopen circuit
        with pytest.raises(NetworkError):
            await failing_recovery_function()
        
        assert circuit_breaker.state == CircuitBreakerState.OPEN
    
    @pytest.mark.asyncio
    async def test_unexpected_exception_passthrough(self, circuit_breaker):
        """Test that unexpected exceptions pass through without affecting circuit."""
        @circuit_breaker
        async def unexpected_error_function():
            raise ValueError("Unexpected error")
        
        # Unexpected exception should pass through
        with pytest.raises(ValueError, match="Unexpected error"):
            await unexpected_error_function()
        
        # Circuit should remain closed
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0
    
    def test_circuit_breaker_stats(self, circuit_breaker):
        """Test circuit breaker statistics."""
        stats = circuit_breaker.get_stats()
        
        assert stats["state"] == "CLOSED"
        assert stats["failure_count"] == 0
        assert stats["success_count"] == 0
        assert stats["total_requests"] == 0
        assert stats["last_failure_time"] is None
    
    def test_reset_circuit_breaker(self, circuit_breaker):
        """Test manual circuit breaker reset."""
        # Simulate some failures
        circuit_breaker._failure_count = 2
        circuit_breaker._success_count = 5
        circuit_breaker._last_failure_time = time.time()
        
        # Reset circuit breaker
        circuit_breaker.reset()
        
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.success_count == 0
        assert circuit_breaker.last_failure_time is None


class TestCircuitBreakerDecorator:
    """Test circuit breaker decorator functionality."""
    
    @pytest.mark.asyncio
    async def test_with_circuit_breaker_decorator(self):
        """Test with_circuit_breaker decorator."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.5)
        
        @with_circuit_breaker(config)
        async def decorated_function(should_fail=False):
            if should_fail:
                raise NetworkError("Simulated failure")
            return "success"
        
        # Successful calls
        result = await decorated_function()
        assert result == "success"
        
        # Failures to trigger circuit opening
        with pytest.raises(NetworkError):
            await decorated_function(should_fail=True)
        
        with pytest.raises(NetworkError):
            await decorated_function(should_fail=True)
        
        # Circuit should now be open
        with pytest.raises(CircuitBreakerError):
            await decorated_function()
    
    @pytest.mark.asyncio
    async def test_multiple_circuit_breakers(self):
        """Test multiple independent circuit breakers."""
        config1 = CircuitBreakerConfig(name="breaker1", failure_threshold=2)
        config2 = CircuitBreakerConfig(name="breaker2", failure_threshold=3)
        
        @with_circuit_breaker(config1)
        async def function1():
            raise NetworkError("Function 1 error")
        
        @with_circuit_breaker(config2)
        async def function2():
            raise NetworkError("Function 2 error")
        
        # Fail function1 to open its circuit
        for _ in range(2):
            with pytest.raises(NetworkError):
                await function1()
        
        # Function1 circuit should be open
        with pytest.raises(CircuitBreakerError):
            await function1()
        
        # Function2 should still work (different circuit)
        with pytest.raises(NetworkError):  # Still raises original error, not circuit breaker error
            await function2()


class TestCircuitBreakerEdgeCases:
    """Test circuit breaker edge cases."""
    
    @pytest.mark.asyncio
    async def test_concurrent_calls(self):
        """Test circuit breaker with concurrent calls."""
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=1.0)
        circuit_breaker = CircuitBreaker(config)
        
        call_count = 0
        
        @circuit_breaker
        async def concurrent_function():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # Simulate async work
            if call_count <= 3:
                raise NetworkError("Concurrent failure")
            return f"success_{call_count}"
        
        # Launch concurrent calls
        tasks = [concurrent_function() for _ in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Some should fail, some might be blocked by circuit breaker
        network_errors = sum(1 for r in results if isinstance(r, NetworkError))
        circuit_errors = sum(1 for r in results if isinstance(r, CircuitBreakerError))
        successes = sum(1 for r in results if isinstance(r, str))
        
        assert network_errors + circuit_errors + successes == 5
    
    def test_circuit_breaker_name_collision(self):
        """Test handling of circuit breaker name collisions."""
        config1 = CircuitBreakerConfig(name="test_breaker")
        config2 = CircuitBreakerConfig(name="test_breaker")
        
        breaker1 = CircuitBreaker(config1)
        breaker2 = CircuitBreaker(config2)
        
        # Should be different instances
        assert breaker1 is not breaker2
        assert breaker1.config.name == breaker2.config.name
