"""
Rate limiting utility module for the web_fetch library.

This module provides rate limiting functionality using token bucket algorithm.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict
from urllib.parse import urlparse

from ..models import RateLimitConfig, RateLimitState


class RateLimiter:
    """Rate limiter using token bucket algorithm."""
    
    def __init__(self, config: RateLimitConfig):
        """Initialize rate limiter with configuration."""
        self.config = config
        self._global_state = RateLimitState(
            tokens=config.burst_size,
            last_update=datetime.now()
        )
        self._host_states: Dict[str, RateLimitState] = {}
    
    def _get_host_from_url(self, url: str) -> str:
        """
        Extract host from URL.

        Parses the URL to extract the network location (host:port) component
        and normalizes it to lowercase for consistent rate limiting keys.

        Args:
            url: URL string to parse

        Returns:
            Lowercase host string, or 'unknown' if URL parsing fails
        """
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return 'unknown'
    
    async def acquire(self, url: str) -> None:
        """
        Acquire permission to make a request.

        Blocks until a token is available according to the rate limiting
        configuration. Uses token bucket algorithm with configurable
        refill rate and burst capacity.

        Args:
            url: URL for the request. Used for per-host limiting if enabled
                in configuration. The host is extracted and rate limits
                are applied per-host rather than globally.

        Note:
            This method will block (await) until a token becomes available.
            For high-frequency requests, this prevents overwhelming servers
            while allowing burst traffic up to the configured burst_size.
        """
        # Determine which rate limit state to use based on configuration
        if self.config.per_host:
            # Per-host rate limiting: each host gets its own token bucket
            # This prevents one slow/busy host from affecting requests to other hosts
            host = self._get_host_from_url(url)

            # Initialize new host state if this is the first request to this host
            if host not in self._host_states:
                # Start with full token bucket for new hosts
                self._host_states[host] = RateLimitState(
                    tokens=self.config.burst_size,
                    last_update=datetime.now()
                )
            state = self._host_states[host]
        else:
            # Global rate limiting: all requests share the same token bucket
            # Simpler but may cause head-of-line blocking between different hosts
            state = self._global_state

        # Token bucket algorithm implementation
        # Wait until we have at least one token available
        while not state.can_make_request(self.config):
            # Small sleep to prevent busy waiting and allow other coroutines to run
            # 10ms is a good balance between responsiveness and CPU usage
            await asyncio.sleep(0.01)

        # Consume one token from the bucket for this request
        # This decreases available tokens and updates request statistics
        state.consume_token()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get rate limiter statistics.

        Returns current state information for monitoring and debugging
        rate limiting behavior.

        Returns:
            Dictionary containing:
            - global_tokens: Available tokens in global bucket
            - global_requests: Total requests made globally
            - host_count: Number of tracked hosts (if per-host limiting enabled)
            - host_stats: Per-host statistics dict with tokens and request counts

        Example:
            ```python
            stats = rate_limiter.get_stats()
            print(f"Global tokens: {stats['global_tokens']}")
            print(f"Tracked hosts: {stats['host_count']}")
            for host, host_stats in stats['host_stats'].items():
                print(f"{host}: {host_stats['tokens']} tokens, {host_stats['requests']} requests")
            ```
        """
        return {
            'global_tokens': self._global_state.tokens,
            'global_requests': self._global_state.requests_made,
            'host_count': len(self._host_states),
            'host_stats': {
                host: {
                    'tokens': state.tokens,
                    'requests': state.requests_made
                }
                for host, state in self._host_states.items()
            }
        }
