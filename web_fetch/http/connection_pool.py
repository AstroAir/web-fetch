"""
Optimized connection pool management for web_fetch HTTP components.

This module provides enhanced connection pooling with performance monitoring,
intelligent connection reuse, and resource optimization.
"""

import asyncio
import logging
import time
import weakref
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, Optional, Set
from urllib.parse import urlparse

import aiohttp
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ConnectionPoolConfig(BaseModel):
    """Configuration for optimized connection pool."""

    # Connection limits
    total_connections: int = Field(
        default=100, 
        ge=1, 
        le=1000,
        description="Total connection pool size"
    )
    connections_per_host: int = Field(
        default=30, 
        ge=1, 
        le=100,
        description="Maximum connections per host"
    )
    
    # Timeout settings
    connect_timeout: float = Field(
        default=10.0, 
        gt=0,
        description="Connection establishment timeout"
    )
    sock_read_timeout: float = Field(
        default=30.0, 
        gt=0,
        description="Socket read timeout"
    )
    sock_connect_timeout: float = Field(
        default=10.0, 
        gt=0,
        description="Socket connect timeout"
    )
    
    # Keep-alive settings
    keepalive_timeout: int = Field(
        default=30, 
        ge=1,
        description="Keep-alive timeout in seconds"
    )
    enable_cleanup_closed: bool = Field(
        default=True,
        description="Enable cleanup of closed connections"
    )
    
    # DNS and caching
    ttl_dns_cache: int = Field(
        default=300, 
        ge=0,
        description="DNS cache TTL in seconds"
    )
    use_dns_cache: bool = Field(
        default=True,
        description="Enable DNS caching"
    )
    
    # SSL settings
    verify_ssl: bool = Field(
        default=True,
        description="Verify SSL certificates"
    )
    ssl_context: Optional[Any] = Field(
        default=None,
        description="Custom SSL context"
    )
    
    # Performance monitoring
    enable_metrics: bool = Field(
        default=True,
        description="Enable connection pool metrics"
    )
    metrics_interval: float = Field(
        default=60.0,
        gt=0,
        description="Metrics collection interval"
    )


@dataclass
class ConnectionMetrics:
    """Connection pool performance metrics."""
    
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    connections_created: int = 0
    connections_closed: int = 0
    connection_errors: int = 0
    average_connection_time: float = 0.0
    peak_connections: int = 0
    last_updated: float = field(default_factory=time.time)
    
    def reset(self) -> None:
        """Reset counters."""
        self.connections_created = 0
        self.connections_closed = 0
        self.connection_errors = 0
        self.last_updated = time.time()


class OptimizedConnectionPool:
    """Optimized connection pool with performance monitoring."""
    
    def __init__(self, config: Optional[ConnectionPoolConfig] = None):
        """
        Initialize optimized connection pool.
        
        Args:
            config: Connection pool configuration
        """
        self.config = config or ConnectionPoolConfig()
        self._connector: Optional[aiohttp.TCPConnector] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._metrics = ConnectionMetrics()
        self._active_sessions: Set[weakref.ReferenceType[Any]] = set()
        self._lock = asyncio.Lock()
        self._closed = False
        
        # Performance monitoring
        self._connection_times: list[float] = []
        self._last_metrics_update = time.time()
        
    async def _create_connector(self) -> aiohttp.TCPConnector:
        """Create optimized TCP connector."""
        return aiohttp.TCPConnector(
            limit=self.config.total_connections,
            limit_per_host=self.config.connections_per_host,
            ttl_dns_cache=self.config.ttl_dns_cache,
            use_dns_cache=self.config.use_dns_cache,
            keepalive_timeout=self.config.keepalive_timeout,
            enable_cleanup_closed=self.config.enable_cleanup_closed,
            ssl=self.config.verify_ssl,
            ssl_context=self.config.ssl_context,
            # Performance optimizations
            force_close=False,  # Allow connection reuse
            happy_eyeballs_delay=0.25,  # IPv6/IPv4 dual-stack optimization
            interleave=1,  # Interleave IPv6/IPv4 addresses
        )
    
    async def _create_session(self) -> aiohttp.ClientSession:
        """Create optimized client session."""
        if not self._connector:
            self._connector = await self._create_connector()
        
        timeout = aiohttp.ClientTimeout(
            total=None,  # No total timeout (handled by individual requests)
            connect=self.config.connect_timeout,
            sock_read=self.config.sock_read_timeout,
            sock_connect=self.config.sock_connect_timeout,
        )
        
        return aiohttp.ClientSession(
            connector=self._connector,
            timeout=timeout,
            raise_for_status=False,
            # Performance optimizations
            skip_auto_headers={'User-Agent'},  # Let applications set their own
            read_bufsize=64 * 1024,  # 64KB read buffer
        )
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[aiohttp.ClientSession, None]:
        """
        Get an optimized session with automatic cleanup.
        
        Yields:
            Configured aiohttp ClientSession
        """
        if self._closed:
            raise RuntimeError("Connection pool is closed")
        
        async with self._lock:
            if not self._session:
                start_time = time.time()
                self._session = await self._create_session()
                connection_time = time.time() - start_time
                
                # Update metrics
                if self.config.enable_metrics:
                    self._connection_times.append(connection_time)
                    self._metrics.connections_created += 1
                    self._update_metrics()
        
        # Track active session
        session_ref = weakref.ref(self._session)
        self._active_sessions.add(session_ref)
        
        try:
            yield self._session
        finally:
            # Clean up dead references
            self._active_sessions.discard(session_ref)
    
    def _update_metrics(self) -> None:
        """Update connection pool metrics."""
        if not self.config.enable_metrics:
            return
        
        now = time.time()
        if now - self._last_metrics_update < self.config.metrics_interval:
            return
        
        # Update connection metrics
        if self._connector:
            self._metrics.total_connections = len(self._connector._conns)
            self._metrics.active_connections = len([
                ref for ref in self._active_sessions if ref() is not None
            ])
        
        # Calculate average connection time
        if self._connection_times:
            self._metrics.average_connection_time = sum(self._connection_times) / len(self._connection_times)
            # Keep only recent measurements
            if len(self._connection_times) > 100:
                self._connection_times = self._connection_times[-50:]
        
        # Update peak connections
        self._metrics.peak_connections = max(
            self._metrics.peak_connections,
            self._metrics.active_connections
        )
        
        self._metrics.last_updated = now
        self._last_metrics_update = now
        
        # Log metrics periodically
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"Connection pool metrics: "
                f"total={self._metrics.total_connections}, "
                f"active={self._metrics.active_connections}, "
                f"avg_time={self._metrics.average_connection_time:.3f}s, "
                f"peak={self._metrics.peak_connections}"
            )
    
    def get_metrics(self) -> ConnectionMetrics:
        """Get current connection pool metrics."""
        self._update_metrics()
        return self._metrics
    
    async def close(self) -> None:
        """Close connection pool and cleanup resources."""
        if self._closed:
            return
        
        self._closed = True
        
        async with self._lock:
            if self._session:
                await self._session.close()
                self._session = None
            
            if self._connector:
                await self._connector.close()
                self._connector = None
        
        # Clear references
        self._active_sessions.clear()
        
        if self.config.enable_metrics:
            logger.info(
                f"Connection pool closed. Final metrics: "
                f"created={self._metrics.connections_created}, "
                f"peak={self._metrics.peak_connections}, "
                f"avg_time={self._metrics.average_connection_time:.3f}s"
            )
    
    async def __aenter__(self) -> 'OptimizedConnectionPool':
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()


# Global connection pool instance for reuse
_global_pool: Optional[OptimizedConnectionPool] = None
_global_pool_lock = asyncio.Lock()


async def get_global_connection_pool(
    config: Optional[ConnectionPoolConfig] = None
) -> OptimizedConnectionPool:
    """
    Get or create global connection pool instance.
    
    Args:
        config: Optional configuration for new pool
        
    Returns:
        Global connection pool instance
    """
    global _global_pool
    
    async with _global_pool_lock:
        if _global_pool is None or _global_pool._closed:
            _global_pool = OptimizedConnectionPool(config)
    
    return _global_pool


async def close_global_connection_pool() -> None:
    """Close global connection pool."""
    global _global_pool
    
    async with _global_pool_lock:
        if _global_pool:
            await _global_pool.close()
            _global_pool = None
