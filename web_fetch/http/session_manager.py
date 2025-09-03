"""
Enhanced session management for web_fetch HTTP components.

This module provides comprehensive session lifecycle management with
proper resource cleanup, connection pooling, and async context management.
"""

import asyncio
import logging
import weakref
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional, Set
from urllib.parse import urlparse

import aiohttp
from pydantic import BaseModel, Field

from .connection_pool import OptimizedConnectionPool, ConnectionPoolConfig

logger = logging.getLogger(__name__)


class SessionConfig(BaseModel):
    """Configuration for HTTP session management."""
    
    # Connection pool settings
    pool_config: Optional[ConnectionPoolConfig] = Field(
        default=None,
        description="Connection pool configuration"
    )
    
    # Session settings
    timeout_total: Optional[float] = Field(
        default=None,
        description="Total request timeout"
    )
    timeout_connect: float = Field(
        default=10.0,
        gt=0,
        description="Connection timeout"
    )
    timeout_sock_read: float = Field(
        default=30.0,
        gt=0,
        description="Socket read timeout"
    )
    
    # Headers and behavior
    default_headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Default headers for all requests"
    )
    raise_for_status: bool = Field(
        default=False,
        description="Automatically raise for HTTP error status"
    )
    
    # Performance settings
    read_bufsize: int = Field(
        default=64 * 1024,
        ge=1024,
        description="Read buffer size in bytes"
    )
    skip_auto_headers: Set[str] = Field(
        default_factory=lambda: {'User-Agent'},
        description="Headers to skip auto-generation"
    )
    
    # Resource management
    auto_cleanup: bool = Field(
        default=True,
        description="Enable automatic resource cleanup"
    )
    cleanup_timeout: float = Field(
        default=5.0,
        gt=0,
        description="Timeout for cleanup operations"
    )


class SessionManager:
    """Enhanced session manager with lifecycle management."""
    
    def __init__(self, config: Optional[SessionConfig] = None):
        """
        Initialize session manager.
        
        Args:
            config: Session configuration
        """
        self.config = config or SessionConfig()
        self._connection_pool: Optional[OptimizedConnectionPool] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._active_requests: Set[weakref.ReferenceType[Any]] = set()
        self._closed = False
        self._lock = asyncio.Lock()
        
        # Resource tracking
        self._request_count = 0
        self._error_count = 0
        
    async def _create_connection_pool(self) -> OptimizedConnectionPool:
        """Create optimized connection pool."""
        pool_config = self.config.pool_config or ConnectionPoolConfig()
        return OptimizedConnectionPool(pool_config)
    
    async def _create_session(self) -> aiohttp.ClientSession:
        """Create optimized HTTP session."""
        if not self._connection_pool:
            self._connection_pool = await self._create_connection_pool()
        
        # Get session from connection pool
        async with self._connection_pool.get_session() as pool_session:
            # Create timeout configuration
            timeout = aiohttp.ClientTimeout(
                total=self.config.timeout_total,
                connect=self.config.timeout_connect,
                sock_read=self.config.timeout_sock_read,
            )
            
            # Return the pool session with our timeout
            pool_session._timeout = timeout
            return pool_session
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[aiohttp.ClientSession, None]:
        """
        Get HTTP session with automatic lifecycle management.
        
        Yields:
            Configured aiohttp ClientSession
            
        Raises:
            RuntimeError: If session manager is closed
        """
        if self._closed:
            raise RuntimeError("Session manager is closed")
        
        async with self._lock:
            if not self._session:
                self._session = await self._create_session()
        
        # Track active session usage
        session_ref = weakref.ref(self._session)
        self._active_requests.add(session_ref)
        
        try:
            self._request_count += 1
            yield self._session
        except Exception as e:
            self._error_count += 1
            logger.warning(f"Session error: {e}")
            raise
        finally:
            # Clean up dead references
            self._active_requests.discard(session_ref)
    
    @asynccontextmanager
    async def request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> AsyncGenerator[aiohttp.ClientResponse, None]:
        """
        Make HTTP request with automatic session management.
        
        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request arguments
            
        Yields:
            HTTP response
        """
        async with self.get_session() as session:
            async with session.request(method, url, **kwargs) as response:
                yield response
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get session metrics."""
        pool_metrics = None
        if self._connection_pool:
            pool_metrics = self._connection_pool.get_metrics()
        
        return {
            "request_count": self._request_count,
            "error_count": self._error_count,
            "error_rate": self._error_count / max(self._request_count, 1),
            "active_requests": len([ref for ref in self._active_requests if ref() is not None]),
            "pool_metrics": pool_metrics.__dict__ if pool_metrics else None,
            "is_closed": self._closed,
        }
    
    async def close(self) -> None:
        """Close session manager and cleanup resources."""
        if self._closed:
            return
        
        self._closed = True
        
        try:
            # Wait for active requests to complete (with timeout)
            if self._active_requests:
                logger.info(f"Waiting for {len(self._active_requests)} active requests to complete")
                await asyncio.wait_for(
                    self._wait_for_requests(),
                    timeout=self.config.cleanup_timeout
                )
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for active requests to complete")
        
        async with self._lock:
            # Close session
            if self._session:
                await self._session.close()
                self._session = None
            
            # Close connection pool
            if self._connection_pool:
                await self._connection_pool.close()
                self._connection_pool = None
        
        # Clear references
        self._active_requests.clear()
        
        logger.info(
            f"Session manager closed. Final metrics: "
            f"requests={self._request_count}, errors={self._error_count}"
        )
    
    async def _wait_for_requests(self) -> None:
        """Wait for all active requests to complete."""
        while True:
            active_refs = [ref for ref in self._active_requests if ref() is not None]
            if not active_refs:
                break
            await asyncio.sleep(0.1)
    
    async def __aenter__(self) -> 'SessionManager':
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()


# Global session manager for reuse
_global_session_manager: Optional[SessionManager] = None
_global_manager_lock = asyncio.Lock()


async def get_global_session_manager(
    config: Optional[SessionConfig] = None
) -> SessionManager:
    """
    Get or create global session manager.
    
    Args:
        config: Optional configuration for new manager
        
    Returns:
        Global session manager instance
    """
    global _global_session_manager
    
    async with _global_manager_lock:
        if _global_session_manager is None or _global_session_manager._closed:
            _global_session_manager = SessionManager(config)
    
    return _global_session_manager


async def close_global_session_manager() -> None:
    """Close global session manager."""
    global _global_session_manager
    
    async with _global_manager_lock:
        if _global_session_manager:
            await _global_session_manager.close()
            _global_session_manager = None


@asynccontextmanager
async def managed_session(
    config: Optional[SessionConfig] = None
) -> AsyncGenerator[SessionManager, None]:
    """
    Create a managed session with automatic cleanup.
    
    Args:
        config: Optional session configuration
        
    Yields:
        Session manager instance
    """
    async with SessionManager(config) as manager:
        yield manager
