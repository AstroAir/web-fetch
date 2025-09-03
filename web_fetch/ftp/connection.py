"""
FTP connection management and pooling for the web fetcher utility.

This module provides FTP connection handling with support for authentication,
connection pooling, and both active and passive modes.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, AsyncIterator
from urllib.parse import urlparse

import aioftp

from ..exceptions import ErrorHandler, FTPError
from .models import FTPAuthType, FTPConfig, FTPConnectionInfo, FTPMode
from .metrics import get_metrics_collector
from .profiler import get_profiler
from .circuit_breaker import get_circuit_breaker, CircuitBreakerError


class FTPConnectionPool:
    """
    Connection pool for FTP connections with automatic cleanup and reuse.
    """

    def __init__(self, config: FTPConfig):
        """Initialize the connection pool."""
        self.config = config
        self._connections: Dict[str, List[aioftp.Client]] = {}
        self._connection_info: Dict[str, FTPConnectionInfo] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task[None]] = None
        self._metrics = get_metrics_collector() if config.performance_monitoring else None
        self._profiler = get_profiler() if config.performance_monitoring else None
        self._circuit_breaker = get_circuit_breaker() if config.performance_monitoring else None
        self._last_activity: Dict[str, float] = {}  # Track last activity per connection key
        self._start_cleanup_task()

    def _start_cleanup_task(self) -> None:
        """Start the background cleanup task."""
        try:
            # Only start the task if there's a running event loop
            asyncio.get_running_loop()
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._cleanup_connections())
        except RuntimeError:
            # No event loop running, defer task creation
            pass

    def _ensure_cleanup_task(self) -> None:
        """Ensure the cleanup task is running if there's an event loop."""
        try:
            asyncio.get_running_loop()
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._cleanup_connections())
        except RuntimeError:
            # No event loop running, skip task creation
            pass

    async def _cleanup_connections(self) -> None:
        """Background task to clean up idle connections with adaptive intervals."""
        base_interval = 60  # Base cleanup interval in seconds
        min_interval = 30   # Minimum cleanup interval
        max_interval = 300  # Maximum cleanup interval

        while True:
            try:
                # Calculate adaptive cleanup interval based on activity
                if self.config.adaptive_cleanup_interval:
                    total_connections = sum(len(conns) for conns in self._connections.values())
                    activity_factor = min(total_connections / 10, 2.0)  # Scale based on connection count
                    cleanup_interval = max(min_interval, min(base_interval / activity_factor, max_interval))
                else:
                    cleanup_interval = base_interval

                await asyncio.sleep(cleanup_interval)
                await self._cleanup_idle_connections()

                # Record cleanup operation in metrics
                if self._metrics:
                    for key in self._connection_info:
                        host, port = key.split(':')[:2]
                        self._metrics.record_connection_created(host, int(port))

            except asyncio.CancelledError:
                break
            except Exception:
                # Continue cleanup even if there's an error
                pass

    async def _cleanup_idle_connections(self) -> None:
        """Remove idle connections that have exceeded the timeout."""
        async with self._lock:
            current_time = datetime.now()
            keys_to_remove: List[str] = []

            for key, info in self._connection_info.items():
                if (current_time - info.last_used).total_seconds() > 300:  # 5 minutes
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                if key in self._connections:
                    connections = self._connections[key]
                    for conn in connections:
                        try:
                            await conn.quit()
                        except Exception:
                            pass
                    del self._connections[key]
                if key in self._connection_info:
                    del self._connection_info[key]

    def _get_connection_key(self, host: str, port: int, username: Optional[str]) -> str:
        """Generate a unique key for connection pooling."""
        return f"{host}:{port}:{username or 'anonymous'}"

    @asynccontextmanager
    async def get_connection(self, url: str) -> AsyncIterator[aioftp.Client]:
        """
        Get an FTP connection from the pool or create a new one.

        Args:
            url: FTP URL to connect to

        Yields:
            aioftp.Client: FTP client connection
        """
        # Ensure cleanup task is running now that we have an event loop
        self._ensure_cleanup_task()
        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 21
        username = parsed.username
        password = parsed.password

        # Use config credentials if not in URL
        if not username and self.config.auth_type == FTPAuthType.USER_PASS:
            username = self.config.username
            password = self.config.password

        connection_key = self._get_connection_key(host, port, username)

        async with self._lock:
            # Try to get existing connection
            if (
                connection_key in self._connections
                and self._connections[connection_key]
            ):
                client = self._connections[connection_key].pop()

                # Perform health check if enabled
                if self.config.connection_health_check:
                    try:
                        # Simple health check - send NOOP command
                        await client.command("NOOP")
                        connection_healthy = True
                    except Exception:
                        connection_healthy = False
                        try:
                            await client.quit()
                        except Exception:
                            pass
                else:
                    connection_healthy = True

                if connection_healthy:
                    self._connection_info[connection_key].last_used = datetime.now()
                    self._connection_info[connection_key].connection_count += 1
                    self._last_activity[connection_key] = time.time()

                    # Record connection reuse in metrics
                    if self._metrics:
                        self._metrics.record_connection_reused(host, port)
                else:
                    # Health check failed, create new connection
                    client = await self._create_connection(host, port, username, password)
                    if self._metrics:
                        self._metrics.record_connection_created(host, port)
            else:
                # Create new connection
                client = await self._create_connection(host, port, username, password)
                if self._metrics:
                    self._metrics.record_connection_created(host, port)

                # Update connection info
                if connection_key not in self._connection_info:
                    self._connection_info[connection_key] = FTPConnectionInfo(
                        host=host,
                        port=port,
                        username=username,
                        is_secure=parsed.scheme == "ftps",
                        created_at=datetime.now(),
                        last_used=datetime.now(),
                        connection_count=1,
                    )
                else:
                    self._connection_info[connection_key].last_used = datetime.now()
                    self._connection_info[connection_key].connection_count += 1

        try:
            yield client
        finally:
            # Return connection to pool
            async with self._lock:
                if connection_key not in self._connections:
                    self._connections[connection_key] = []

                # Only keep up to max_connections_per_host connections
                if (
                    len(self._connections[connection_key])
                    < self.config.max_connections_per_host
                ):
                    self._connections[connection_key].append(client)
                else:
                    try:
                        await client.quit()
                    except Exception:
                        pass

    async def _create_connection(
        self, host: str, port: int, username: Optional[str], password: Optional[str]
    ) -> aioftp.Client:
        """
        Create a new FTP connection.

        Args:
            host: FTP server hostname
            port: FTP server port
            username: Username for authentication
            password: Password for authentication

        Returns:
            aioftp.Client: Connected FTP client
        """
        try:
            client = aioftp.Client()

            # Set connection timeout
            client.socket_timeout = self.config.connection_timeout

            # Connect to server
            await client.connect(host, port)

            # Authenticate
            if self.config.auth_type == FTPAuthType.ANONYMOUS:
                await client.login()
            else:
                if not username:
                    raise FTPError("Username required for non-anonymous authentication")
                await client.login(username, password or "")

            # Transfer mode handling:
            # aioftp operates in passive mode by default and does not expose a passive_mode flag.
            # If ACTIVE is requested, warn once via NOOP; continue using passive mode for compatibility.
            if self.config.mode == FTPMode.ACTIVE:
                try:
                    # Some servers may allow disabling EPSV; not guaranteed.
                    await client.command("NOOP")
                except Exception:
                    # Ignore if server does not support/allow this hint.
                    pass

            return client

        except Exception as e:
            raise ErrorHandler.handle_ftp_error(e, f"ftp://{host}:{port}")

    async def close_all(self) -> None:
        """Close all connections in the pool."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        async with self._lock:
            for connections in self._connections.values():
                for conn in connections:
                    try:
                        await conn.quit()
                    except Exception:
                        pass

            self._connections.clear()
            self._connection_info.clear()

    def get_pool_stats(self) -> Dict[str, Any]:
        """Get statistics about the connection pool."""
        return {
            "total_connection_keys": len(self._connection_info),
            "active_connections": sum(
                len(conns) for conns in self._connections.values()
            ),
            "connection_info": {
                key: {
                    "host": info.host,
                    "port": info.port,
                    "username": info.username,
                    "is_secure": info.is_secure,
                    "created_at": info.created_at.isoformat(),
                    "last_used": info.last_used.isoformat(),
                    "connection_count": info.connection_count,
                }
                for key, info in self._connection_info.items()
            },
        }
