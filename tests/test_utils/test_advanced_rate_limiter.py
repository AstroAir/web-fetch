"""
Comprehensive tests for the advanced rate limiter utility.
"""

import pytest
import asyncio
import time
from unittest.mock import patch, MagicMock

from web_fetch.utils.advanced_rate_limiter import (
    AdvancedRateLimiter,
    RateLimitConfig,
    RateLimitStrategy,
    TokenBucket,
    SlidingWindow,
    FixedWindow,
    RateLimitExceeded,
)


class TestRateLimitConfig:
    """Test rate limit configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = RateLimitConfig()
        
        assert config.requests_per_second == 10
        assert config.burst_size == 20
        assert config.strategy == RateLimitStrategy.TOKEN_BUCKET
        assert config.window_size == 60
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = RateLimitConfig(
            requests_per_second=50,
            burst_size=100,
            strategy=RateLimitStrategy.SLIDING_WINDOW,
            window_size=120
        )
        
        assert config.requests_per_second == 50
        assert config.burst_size == 100
        assert config.strategy == RateLimitStrategy.SLIDING_WINDOW
        assert config.window_size == 120
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Invalid requests per second
        with pytest.raises(ValueError, match="requests_per_second must be positive"):
            RateLimitConfig(requests_per_second=0)
        
        # Invalid burst size
        with pytest.raises(ValueError, match="burst_size must be positive"):
            RateLimitConfig(burst_size=0)
        
        # Invalid window size
        with pytest.raises(ValueError, match="window_size must be positive"):
            RateLimitConfig(window_size=0)


class TestTokenBucket:
    """Test token bucket rate limiting strategy."""
    
    @pytest.fixture
    def token_bucket(self):
        """Create token bucket instance."""
        return TokenBucket(capacity=10, refill_rate=5)  # 10 tokens, 5 per second
    
    def test_initial_state(self, token_bucket):
        """Test initial token bucket state."""
        assert token_bucket.capacity == 10
        assert token_bucket.refill_rate == 5
        assert token_bucket.tokens == 10  # Starts full
        assert token_bucket.last_refill is not None
    
    def test_consume_tokens(self, token_bucket):
        """Test token consumption."""
        # Consume some tokens
        assert token_bucket.consume(3) is True
        assert token_bucket.tokens == 7
        
        # Consume remaining tokens
        assert token_bucket.consume(7) is True
        assert token_bucket.tokens == 0
        
        # Try to consume when empty
        assert token_bucket.consume(1) is False
        assert token_bucket.tokens == 0
    
    def test_token_refill(self, token_bucket):
        """Test token refill mechanism."""
        # Consume all tokens
        token_bucket.consume(10)
        assert token_bucket.tokens == 0
        
        # Mock time to simulate passage of time
        with patch('time.time') as mock_time:
            # Simulate 1 second passing (should refill 5 tokens)
            mock_time.side_effect = [
                token_bucket.last_refill,  # Initial time
                token_bucket.last_refill + 1.0  # 1 second later
            ]
            
            # Trigger refill by attempting to consume
            token_bucket._refill()
            assert token_bucket.tokens == 5
    
    def test_burst_capacity(self, token_bucket):
        """Test burst capacity handling."""
        # Should be able to consume up to capacity immediately
        assert token_bucket.consume(10) is True
        assert token_bucket.tokens == 0
        
        # Cannot exceed capacity
        assert token_bucket.consume(1) is False
    
    def test_partial_refill(self, token_bucket):
        """Test partial token refill."""
        # Consume half the tokens
        token_bucket.consume(5)
        assert token_bucket.tokens == 5
        
        with patch('time.time') as mock_time:
            # Simulate 0.5 seconds (should refill 2.5 tokens, rounded down to 2)
            mock_time.side_effect = [
                token_bucket.last_refill,
                token_bucket.last_refill + 0.5
            ]
            
            token_bucket._refill()
            assert token_bucket.tokens == 7  # 5 + 2


class TestSlidingWindow:
    """Test sliding window rate limiting strategy."""
    
    @pytest.fixture
    def sliding_window(self):
        """Create sliding window instance."""
        return SlidingWindow(window_size=60, max_requests=100)  # 100 requests per minute
    
    def test_initial_state(self, sliding_window):
        """Test initial sliding window state."""
        assert sliding_window.window_size == 60
        assert sliding_window.max_requests == 100
        assert len(sliding_window.requests) == 0
    
    def test_allow_requests_within_limit(self, sliding_window):
        """Test allowing requests within rate limit."""
        current_time = time.time()
        
        # Should allow requests up to the limit
        for i in range(100):
            assert sliding_window.allow_request(current_time + i * 0.1) is True
        
        assert len(sliding_window.requests) == 100
    
    def test_reject_requests_over_limit(self, sliding_window):
        """Test rejecting requests over rate limit."""
        current_time = time.time()
        
        # Fill up to limit
        for i in range(100):
            sliding_window.allow_request(current_time + i * 0.1)
        
        # Next request should be rejected
        assert sliding_window.allow_request(current_time + 10) is False
        assert len(sliding_window.requests) == 100
    
    def test_window_sliding(self, sliding_window):
        """Test sliding window behavior."""
        current_time = time.time()
        
        # Add requests at the beginning of window
        for i in range(50):
            sliding_window.allow_request(current_time + i)
        
        # Move forward past window size
        future_time = current_time + 70  # 70 seconds later
        
        # Old requests should be cleaned up, new request should be allowed
        assert sliding_window.allow_request(future_time) is True
        assert len(sliding_window.requests) == 1  # Only the new request
    
    def test_cleanup_old_requests(self, sliding_window):
        """Test cleanup of old requests."""
        current_time = time.time()
        
        # Add requests across different time periods
        sliding_window.allow_request(current_time - 100)  # Very old
        sliding_window.allow_request(current_time - 30)   # Within window
        sliding_window.allow_request(current_time)        # Current
        
        # Cleanup should remove old requests
        sliding_window._cleanup_old_requests(current_time)
        assert len(sliding_window.requests) == 2  # Only recent requests remain


class TestFixedWindow:
    """Test fixed window rate limiting strategy."""
    
    @pytest.fixture
    def fixed_window(self):
        """Create fixed window instance."""
        return FixedWindow(window_size=60, max_requests=100)  # 100 requests per minute
    
    def test_initial_state(self, fixed_window):
        """Test initial fixed window state."""
        assert fixed_window.window_size == 60
        assert fixed_window.max_requests == 100
        assert fixed_window.current_window_start is None
        assert fixed_window.current_count == 0
    
    def test_allow_requests_within_window(self, fixed_window):
        """Test allowing requests within fixed window."""
        current_time = time.time()
        
        # Should allow requests up to the limit
        for i in range(100):
            assert fixed_window.allow_request(current_time + i * 0.1) is True
        
        assert fixed_window.current_count == 100
    
    def test_reject_requests_over_limit(self, fixed_window):
        """Test rejecting requests over limit in fixed window."""
        current_time = time.time()
        
        # Fill up to limit
        for i in range(100):
            fixed_window.allow_request(current_time + i * 0.1)
        
        # Next request should be rejected
        assert fixed_window.allow_request(current_time + 10) is False
        assert fixed_window.current_count == 100
    
    def test_window_reset(self, fixed_window):
        """Test fixed window reset."""
        current_time = time.time()
        
        # Fill current window
        for i in range(100):
            fixed_window.allow_request(current_time + i * 0.1)
        
        # Move to next window
        next_window_time = current_time + 70  # Beyond window size
        
        # Should reset and allow new requests
        assert fixed_window.allow_request(next_window_time) is True
        assert fixed_window.current_count == 1


class TestAdvancedRateLimiter:
    """Test advanced rate limiter functionality."""
    
    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter instance."""
        config = RateLimitConfig(
            requests_per_second=10,
            burst_size=20,
            strategy=RateLimitStrategy.TOKEN_BUCKET
        )
        return AdvancedRateLimiter(config)
    
    @pytest.mark.asyncio
    async def test_acquire_within_limit(self, rate_limiter):
        """Test acquiring permits within rate limit."""
        # Should be able to acquire up to burst size immediately
        for i in range(20):
            await rate_limiter.acquire()
        
        # Check internal state
        assert rate_limiter._strategy.tokens == 0
    
    @pytest.mark.asyncio
    async def test_acquire_blocks_when_limited(self, rate_limiter):
        """Test that acquire blocks when rate limited."""
        # Consume all tokens
        for i in range(20):
            await rate_limiter.acquire()
        
        # Next acquire should block (we'll timeout quickly for testing)
        start_time = time.time()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(rate_limiter.acquire(), timeout=0.1)
        
        elapsed = time.time() - start_time
        assert elapsed >= 0.1  # Should have waited for timeout
    
    @pytest.mark.asyncio
    async def test_try_acquire_immediate(self, rate_limiter):
        """Test try_acquire for immediate response."""
        # Should succeed within limit
        for i in range(20):
            assert await rate_limiter.try_acquire() is True
        
        # Should fail when over limit
        assert await rate_limiter.try_acquire() is False
    
    @pytest.mark.asyncio
    async def test_different_strategies(self):
        """Test different rate limiting strategies."""
        strategies = [
            RateLimitStrategy.TOKEN_BUCKET,
            RateLimitStrategy.SLIDING_WINDOW,
            RateLimitStrategy.FIXED_WINDOW
        ]
        
        for strategy in strategies:
            config = RateLimitConfig(
                requests_per_second=5,
                burst_size=10,
                strategy=strategy
            )
            limiter = AdvancedRateLimiter(config)
            
            # Should allow some requests
            for i in range(5):
                assert await limiter.try_acquire() is True
    
    def test_get_stats(self, rate_limiter):
        """Test rate limiter statistics."""
        stats = rate_limiter.get_stats()
        
        assert "strategy" in stats
        assert "requests_per_second" in stats
        assert "burst_size" in stats
        assert "current_tokens" in stats or "current_count" in stats
    
    @pytest.mark.asyncio
    async def test_reset_limiter(self, rate_limiter):
        """Test rate limiter reset."""
        # Consume some tokens
        for i in range(10):
            await rate_limiter.acquire()
        
        # Reset should restore full capacity
        rate_limiter.reset()
        
        # Should be able to acquire full burst again
        for i in range(20):
            assert await rate_limiter.try_acquire() is True


class TestRateLimitDecorator:
    """Test rate limit decorator functionality."""
    
    @pytest.mark.asyncio
    async def test_rate_limited_function(self):
        """Test rate limited function decorator."""
        config = RateLimitConfig(requests_per_second=5, burst_size=5)
        limiter = AdvancedRateLimiter(config)
        
        @limiter.rate_limit
        async def limited_function():
            return "success"
        
        # Should allow calls up to burst size
        for i in range(5):
            result = await limited_function()
            assert result == "success"
        
        # Next call should be rate limited
        with pytest.raises(RateLimitExceeded):
            await asyncio.wait_for(limited_function(), timeout=0.1)
    
    @pytest.mark.asyncio
    async def test_rate_limit_with_key(self):
        """Test rate limiting with different keys."""
        config = RateLimitConfig(requests_per_second=2, burst_size=2)
        limiter = AdvancedRateLimiter(config)
        
        @limiter.rate_limit_with_key
        async def keyed_function(user_id):
            return f"success_{user_id}"
        
        # Different users should have separate limits
        for user_id in ["user1", "user2"]:
            for i in range(2):
                result = await keyed_function(user_id)
                assert result == f"success_{user_id}"
