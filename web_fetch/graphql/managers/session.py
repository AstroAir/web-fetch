"""
Session management for GraphQL operations.

This module provides HTTP session lifecycle management for GraphQL clients,
following the established patterns from web_fetch.http.session_manager.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator, Optional
from contextlib import asynccontextmanager

import aiohttp
from pydantic import Field

from ...auth import AuthManager
from ...utils.circuit_breaker import CircuitBreakerConfig
from ...utils.metrics import MetricsCollector
from ..models import GraphQLConfig
from .base import BaseGraphQLManager, GraphQLManagerConfig

logger = logging.getLogger(__name__)


class SessionManagerConfig(GraphQLManagerConfig):
    """Configuration for GraphQL session manager."""
    
    # Connection settings
    max_connections: int = Field(default=100, ge=1, description="Maximum connections")
    max_connections_per_host: int = Field(default=30, ge=1, description="Max connections per host")
    keepalive_timeout: float = Field(default=30.0, ge=1.0, description="Keep-alive timeout")
    
    # Timeout settings
    connect_timeout: float = Field(default=10.0, ge=1.0, description="Connection timeout")
    sock_read_timeout: float = Field(default=30.0, ge=1.0, description="Socket read timeout")
    
    # Session settings
    enable_cookies: bool = Field(default=True, description="Enable cookie handling")
    trust_env: bool = Field(default=True, description="Trust environment variables")
    
    class Config:
        """Pydantic configuration."""
        extra = "forbid"


class GraphQLSessionManager(BaseGraphQLManager):
    """
    HTTP session manager for GraphQL operations.
    
    Manages the lifecycle of HTTP sessions used for GraphQL requests,
    providing connection pooling, timeout management, and proper cleanup.
    
    Features:
    - Connection pooling and reuse
    - Configurable timeouts
    - Authentication integration
    - Metrics collection
    - Proper resource cleanup
    
    Examples:
        Basic usage:
        ```python
        config = SessionManagerConfig(max_connections=50)
        async with GraphQLSessionManager(config) as session_manager:
            async with session_manager.get_session() as session:
                # Use session for HTTP requests
                pass
        ```
        
        With authentication:
        ```python
        auth_manager = AuthManager()
        session_manager = GraphQLSessionManager(config, auth_manager=auth_manager)
        ```
    """
    
    def __init__(
        self,
        config: Optional[SessionManagerConfig] = None,
        graphql_config: Optional[GraphQLConfig] = None,
        auth_manager: Optional[AuthManager] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
    ):
        """
        Initialize session manager.
        
        Args:
            config: Session manager configuration
            graphql_config: GraphQL client configuration
            auth_manager: Optional authentication manager
            circuit_breaker_config: Optional circuit breaker configuration
        """
        super().__init__(config or SessionManagerConfig())
        self.graphql_config = graphql_config
        self.auth_manager = auth_manager
        self.circuit_breaker_config = circuit_breaker_config
        
        # Session state
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None
        
        # Metrics
        self._metrics_collector = MetricsCollector()
        self._request_count = 0
        self._error_count = 0
    
    @property
    def session_config(self) -> SessionManagerConfig:
        """Get typed session configuration."""
        return self.config  # type: ignore
    
    async def _initialize_impl(self) -> None:
        """Initialize session manager."""
        await self._create_session()
    
    async def _close_impl(self) -> None:
        """Close session manager and cleanup resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            # Wait a bit for connections to close properly
            await asyncio.sleep(0.1)
        
        if self._connector and not self._connector.closed:
            await self._connector.close()
        
        self._session = None
        self._connector = None
        
        self._logger.info(
            f"Session manager closed. Metrics: requests={self._request_count}, "
            f"errors={self._error_count}"
        )
    
    async def _create_session(self) -> None:
        """Create HTTP session with optimized settings."""
        if self._session and not self._session.closed:
            return
        
        # Create connector with connection pooling
        self._connector = aiohttp.TCPConnector(
            limit=self.session_config.max_connections,
            limit_per_host=self.session_config.max_connections_per_host,
            keepalive_timeout=self.session_config.keepalive_timeout,
            enable_cleanup_closed=True,
            ttl_dns_cache=300,  # 5 minutes DNS cache
            use_dns_cache=True,
        )
        
        # Create timeout configuration
        timeout = aiohttp.ClientTimeout(
            total=self.session_config.timeout,
            connect=self.session_config.connect_timeout,
            sock_read=self.session_config.sock_read_timeout,
        )
        
        # Prepare headers
        headers = {"User-Agent": "web-fetch-graphql/1.0"}
        if self.graphql_config and self.graphql_config.headers:
            headers.update(self.graphql_config.headers)
        
        # Create session
        self._session = aiohttp.ClientSession(
            connector=self._connector,
            timeout=timeout,
            headers=headers,
            cookie_jar=aiohttp.CookieJar() if self.session_config.enable_cookies else None,
            trust_env=self.session_config.trust_env,
            raise_for_status=False,  # Handle status codes manually
        )
        
        self._logger.debug("HTTP session created")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[aiohttp.ClientSession, None]:
        """
        Get HTTP session for GraphQL requests.
        
        Yields:
            Configured aiohttp ClientSession
            
        Raises:
            RuntimeError: If session manager is not initialized or closed
        """
        self._ensure_initialized()
        
        if not self._session or self._session.closed:
            await self._create_session()
        
        try:
            self._request_count += 1
            yield self._session  # type: ignore
        except Exception as e:
            self._error_count += 1
            self._logger.warning(f"Session error: {e}")
            raise
    
    async def apply_authentication(self, headers: dict) -> dict:
        """
        Apply authentication to request headers.
        
        Args:
            headers: Request headers
            
        Returns:
            Headers with authentication applied
        """
        if not self.auth_manager:
            return headers
        
        try:
            auth_result = await self.auth_manager.authenticate()
            if auth_result.headers:
                headers.update(auth_result.headers)
        except Exception as e:
            self._logger.warning(f"Authentication failed: {e}")
        
        return headers
    
    def get_metrics(self) -> dict:
        """
        Get session metrics.
        
        Returns:
            Dictionary containing session metrics
        """
        return {
            "request_count": self._request_count,
            "error_count": self._error_count,
            "error_rate": self._error_count / max(self._request_count, 1),
            "session_active": self._session is not None and not self._session.closed,
        }
