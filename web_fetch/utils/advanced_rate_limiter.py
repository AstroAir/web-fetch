"""
Advanced rate limiting with adaptive algorithms and circuit breaker integration.

This module provides sophisticated rate limiting with per-domain limits,
adaptive algorithms, retry with exponential backoff, jitter, and circuit breaker integration.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, Callable, List, Tuple, Deque
from urllib.parse import urlparse

from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from ..exceptions import RateLimitError

logger = logging.getLogger(__name__)


class RateLimitAlgorithm(Enum):
    """Rate limiting algorithms."""
    
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    ADAPTIVE = "adaptive"
    LEAKY_BUCKET = "leaky_bucket"


class RateLimitStrategy(Enum):
    """Rate limiting strategies for different scenarios."""
    
    CONSERVATIVE = "conservative"    # Lower limits, safer approach
    BALANCED = "balanced"           # Balanced approach
    AGGRESSIVE = "aggressive"       # Higher limits, faster processing
    ADAPTIVE = "adaptive"           # Adapts based on server responses


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.TOKEN_BUCKET
    strategy: RateLimitStrategy = RateLimitStrategy.BALANCED
    requests_per_second: float = 10.0
    burst_size: int = 20
    window_size: int = 60  # seconds
    per_domain: bool = True
    respect_server_limits: bool = True
    adaptive_factor: float = 0.1
    min_requests_per_second: float = 1.0
    max_requests_per_second: float = 100.0
    circuit_breaker_enabled: bool = True
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None


@dataclass
class DomainLimitInfo:
    """Rate limit information for a specific domain."""
    
    domain: str
    current_rps: float
    tokens: float
    last_refill: float
    request_times: Deque[float] = field(default_factory=deque)
    server_limit_rps: Optional[float] = None
    server_limit_reset: Optional[float] = None
    circuit_breaker: Optional[CircuitBreaker] = None
    consecutive_failures: int = 0
    last_success: float = 0.0
    
    def __post_init__(self):
        if not self.request_times:
            self.request_times = deque()


class AdvancedRateLimiter:
    """Advanced rate limiter with multiple algorithms and adaptive behavior."""
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        Initialize advanced rate limiter.
        
        Args:
            config: Rate limiting configuration
        """
        self.config = config or RateLimitConfig()
        self.domain_limits: Dict[str, DomainLimitInfo] = {}
        self.global_tokens = self.config.burst_size
        self.global_last_refill = time.time()
        
        # Rate limit header patterns
        self.rate_limit_headers = {
            'remaining': ['x-ratelimit-remaining', 'x-rate-limit-remaining', 'ratelimit-remaining'],
            'limit': ['x-ratelimit-limit', 'x-rate-limit-limit', 'ratelimit-limit'],
            'reset': ['x-ratelimit-reset', 'x-rate-limit-reset', 'ratelimit-reset'],
            'retry_after': ['retry-after', 'x-retry-after'],
        }
        
        # Strategy configurations
        self.strategy_configs = {
            RateLimitStrategy.CONSERVATIVE: {
                'base_rps': 5.0,
                'burst_multiplier': 1.5,
                'backoff_factor': 2.0,
            },
            RateLimitStrategy.BALANCED: {
                'base_rps': 10.0,
                'burst_multiplier': 2.0,
                'backoff_factor': 1.5,
            },
            RateLimitStrategy.AGGRESSIVE: {
                'base_rps': 20.0,
                'burst_multiplier': 3.0,
                'backoff_factor': 1.2,
            },
            RateLimitStrategy.ADAPTIVE: {
                'base_rps': 10.0,
                'burst_multiplier': 2.0,
                'backoff_factor': 1.5,
            },
        }
    
    async def acquire(self, url: str, headers: Optional[Dict[str, str]] = None) -> float:
        """
        Acquire permission to make a request.
        
        Args:
            url: URL being requested
            headers: Optional response headers from previous request
            
        Returns:
            Delay in seconds before request can be made (0 if immediate)
            
        Raises:
            RateLimitError: If rate limit is exceeded and circuit breaker is open
        """
        domain = self._extract_domain(url)
        
        # Get or create domain limit info
        if domain not in self.domain_limits:
            self.domain_limits[domain] = self._create_domain_limit_info(domain)
        
        domain_info = self.domain_limits[domain]
        
        # Update server limits from headers if available
        if headers:
            self._update_server_limits(domain_info, headers)
        
        # Check circuit breaker
        if domain_info.circuit_breaker and not await domain_info.circuit_breaker.can_execute():
            raise RateLimitError(f"Circuit breaker open for domain {domain}")
        
        # Calculate delay based on algorithm
        delay = await self._calculate_delay(domain_info, url)
        
        # Record request attempt
        current_time = time.time()
        domain_info.request_times.append(current_time)
        
        # Clean old request times
        self._clean_old_requests(domain_info, current_time)
        
        return delay
    
    async def record_response(
        self, 
        url: str, 
        status_code: int, 
        headers: Optional[Dict[str, str]] = None,
        response_time: float = 0.0
    ):
        """
        Record response for adaptive rate limiting.
        
        Args:
            url: URL that was requested
            status_code: HTTP status code
            headers: Response headers
            response_time: Response time in seconds
        """
        domain = self._extract_domain(url)
        
        if domain not in self.domain_limits:
            return
        
        domain_info = self.domain_limits[domain]
        current_time = time.time()
        
        # Update server limits from headers
        if headers:
            self._update_server_limits(domain_info, headers)
        
        # Record success/failure for circuit breaker
        if domain_info.circuit_breaker:
            if 200 <= status_code < 300:
                await domain_info.circuit_breaker.record_success()
                domain_info.consecutive_failures = 0
                domain_info.last_success = current_time
            elif status_code == 429 or status_code >= 500:
                await domain_info.circuit_breaker.record_failure()
                domain_info.consecutive_failures += 1
        
        # Adaptive rate limiting
        if self.config.strategy == RateLimitStrategy.ADAPTIVE:
            await self._adapt_rate_limit(domain_info, status_code, response_time)
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc or "default"
        except Exception:
            return "default"
    
    def _create_domain_limit_info(self, domain: str) -> DomainLimitInfo:
        """Create rate limit info for a domain."""
        current_time = time.time()
        
        # Get strategy-specific configuration
        strategy_config = self.strategy_configs[self.config.strategy]
        base_rps = strategy_config['base_rps']
        
        domain_info = DomainLimitInfo(
            domain=domain,
            current_rps=base_rps,
            tokens=self.config.burst_size,
            last_refill=current_time,
            last_success=current_time
        )
        
        # Create circuit breaker if enabled
        if self.config.circuit_breaker_enabled:
            cb_config = self.config.circuit_breaker_config or CircuitBreakerConfig(
                failure_threshold=5,
                timeout=30.0,
                expected_exception=RateLimitError
            )
            domain_info.circuit_breaker = CircuitBreaker(cb_config)
        
        return domain_info
    
    def _update_server_limits(self, domain_info: DomainLimitInfo, headers: Dict[str, str]):
        """Update rate limits based on server response headers."""
        if not self.config.respect_server_limits:
            return
        
        headers_lower = {k.lower(): v for k, v in headers.items()}
        
        # Parse rate limit headers
        remaining = None
        limit = None
        reset_time = None
        retry_after = None
        
        for header_name in self.rate_limit_headers['remaining']:
            if header_name in headers_lower:
                try:
                    remaining = int(headers_lower[header_name])
                    break
                except ValueError:
                    continue
        
        for header_name in self.rate_limit_headers['limit']:
            if header_name in headers_lower:
                try:
                    limit = int(headers_lower[header_name])
                    break
                except ValueError:
                    continue
        
        for header_name in self.rate_limit_headers['reset']:
            if header_name in headers_lower:
                try:
                    reset_time = float(headers_lower[header_name])
                    break
                except ValueError:
                    continue
        
        for header_name in self.rate_limit_headers['retry_after']:
            if header_name in headers_lower:
                try:
                    retry_after = float(headers_lower[header_name])
                    break
                except ValueError:
                    continue
        
        # Update domain limits
        current_time = time.time()
        
        if limit and reset_time:
            # Calculate server's rate limit
            time_window = reset_time - current_time if reset_time > current_time else 60
            server_rps = limit / max(time_window, 1)
            domain_info.server_limit_rps = server_rps
            domain_info.server_limit_reset = reset_time
            
            # Adjust our rate limit to be more conservative
            if server_rps > 0:
                domain_info.current_rps = min(domain_info.current_rps, server_rps * 0.8)
        
        if retry_after:
            # Server explicitly told us to wait
            domain_info.server_limit_reset = current_time + retry_after
    
    async def _calculate_delay(self, domain_info: DomainLimitInfo, url: str) -> float:
        """Calculate delay based on selected algorithm."""
        if self.config.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
            return await self._token_bucket_delay(domain_info)
        elif self.config.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
            return await self._sliding_window_delay(domain_info)
        elif self.config.algorithm == RateLimitAlgorithm.FIXED_WINDOW:
            return await self._fixed_window_delay(domain_info)
        elif self.config.algorithm == RateLimitAlgorithm.LEAKY_BUCKET:
            return await self._leaky_bucket_delay(domain_info)
        else:  # ADAPTIVE
            return await self._adaptive_delay(domain_info)
    
    async def _token_bucket_delay(self, domain_info: DomainLimitInfo) -> float:
        """Calculate delay using token bucket algorithm."""
        current_time = time.time()
        
        # Refill tokens
        time_passed = current_time - domain_info.last_refill
        tokens_to_add = time_passed * domain_info.current_rps
        domain_info.tokens = min(self.config.burst_size, domain_info.tokens + tokens_to_add)
        domain_info.last_refill = current_time
        
        # Check if we have tokens
        if domain_info.tokens >= 1.0:
            domain_info.tokens -= 1.0
            return 0.0
        else:
            # Calculate delay until next token
            delay = (1.0 - domain_info.tokens) / domain_info.current_rps
            return delay
    
    async def _sliding_window_delay(self, domain_info: DomainLimitInfo) -> float:
        """Calculate delay using sliding window algorithm."""
        current_time = time.time()
        window_start = current_time - self.config.window_size
        
        # Count requests in current window
        recent_requests = [t for t in domain_info.request_times if t > window_start]
        
        max_requests = int(domain_info.current_rps * self.config.window_size)
        
        if len(recent_requests) < max_requests:
            return 0.0
        else:
            # Calculate delay until oldest request falls out of window
            oldest_request = min(recent_requests)
            delay = (oldest_request + self.config.window_size) - current_time
            return max(0.0, delay)
    
    async def _fixed_window_delay(self, domain_info: DomainLimitInfo) -> float:
        """Calculate delay using fixed window algorithm."""
        current_time = time.time()
        window_start = int(current_time / self.config.window_size) * self.config.window_size
        
        # Count requests in current window
        window_requests = [t for t in domain_info.request_times if t >= window_start]
        
        max_requests = int(domain_info.current_rps * self.config.window_size)
        
        if len(window_requests) < max_requests:
            return 0.0
        else:
            # Wait until next window
            next_window = window_start + self.config.window_size
            delay = next_window - current_time
            return max(0.0, delay)
    
    async def _leaky_bucket_delay(self, domain_info: DomainLimitInfo) -> float:
        """Calculate delay using leaky bucket algorithm."""
        current_time = time.time()
        
        # Calculate leak rate
        time_passed = current_time - domain_info.last_refill
        leaked_requests = time_passed * domain_info.current_rps
        
        # Update bucket level
        current_level = max(0, len(domain_info.request_times) - leaked_requests)
        
        if current_level < self.config.burst_size:
            domain_info.last_refill = current_time
            return 0.0
        else:
            # Calculate delay
            delay = (current_level - self.config.burst_size + 1) / domain_info.current_rps
            return delay
    
    async def _adaptive_delay(self, domain_info: DomainLimitInfo) -> float:
        """Calculate delay using adaptive algorithm."""
        # Use token bucket as base, but adjust based on recent performance
        base_delay = await self._token_bucket_delay(domain_info)
        
        # Adjust based on recent failures
        if domain_info.consecutive_failures > 0:
            failure_multiplier = 1.5 ** domain_info.consecutive_failures
            base_delay *= failure_multiplier
        
        # Adjust based on server limits
        if domain_info.server_limit_reset:
            current_time = time.time()
            if current_time < domain_info.server_limit_reset:
                server_delay = domain_info.server_limit_reset - current_time
                base_delay = max(base_delay, server_delay)
        
        return base_delay
    
    async def _adapt_rate_limit(
        self, 
        domain_info: DomainLimitInfo, 
        status_code: int, 
        response_time: float
    ):
        """Adapt rate limit based on server response."""
        current_rps = domain_info.current_rps
        
        if status_code == 429:
            # Rate limited - decrease rate
            new_rps = current_rps * (1 - self.config.adaptive_factor)
        elif 500 <= status_code < 600:
            # Server error - decrease rate slightly
            new_rps = current_rps * (1 - self.config.adaptive_factor * 0.5)
        elif 200 <= status_code < 300:
            # Success - potentially increase rate
            if response_time < 1.0:  # Fast response
                new_rps = current_rps * (1 + self.config.adaptive_factor * 0.1)
            else:
                new_rps = current_rps  # Keep current rate
        else:
            new_rps = current_rps  # No change for other status codes
        
        # Apply bounds
        new_rps = max(self.config.min_requests_per_second, 
                     min(self.config.max_requests_per_second, new_rps))
        
        domain_info.current_rps = new_rps
        
        logger.debug(f"Adapted rate limit for {domain_info.domain}: {current_rps:.2f} -> {new_rps:.2f} RPS")
    
    def _clean_old_requests(self, domain_info: DomainLimitInfo, current_time: float):
        """Clean old request timestamps."""
        cutoff_time = current_time - self.config.window_size * 2  # Keep 2x window for safety
        
        while domain_info.request_times and domain_info.request_times[0] < cutoff_time:
            domain_info.request_times.popleft()
    
    def get_rate_limit_status(self, domain: Optional[str] = None) -> Dict[str, Any]:
        """Get current rate limit status."""
        if domain:
            if domain in self.domain_limits:
                domain_info = self.domain_limits[domain]
                return {
                    'domain': domain,
                    'current_rps': domain_info.current_rps,
                    'tokens': domain_info.tokens,
                    'recent_requests': len(domain_info.request_times),
                    'consecutive_failures': domain_info.consecutive_failures,
                    'server_limit_rps': domain_info.server_limit_rps,
                    'circuit_breaker_state': domain_info.circuit_breaker.state.value if domain_info.circuit_breaker else None,
                }
            else:
                return {'domain': domain, 'status': 'not_tracked'}
        else:
            # Return status for all domains
            return {
                domain: {
                    'current_rps': info.current_rps,
                    'tokens': info.tokens,
                    'recent_requests': len(info.request_times),
                    'consecutive_failures': info.consecutive_failures,
                    'server_limit_rps': info.server_limit_rps,
                    'circuit_breaker_state': info.circuit_breaker.state.value if info.circuit_breaker else None,
                }
                for domain, info in self.domain_limits.items()
            }
