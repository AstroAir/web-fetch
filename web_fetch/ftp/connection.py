"""
FTP connection management and pooling for the web fetcher utility.

This module provides FTP connection handling with support for authentication,
connection pooling, and both active and passive modes.
"""

from __future__ import annotations

import asyncio
import ftplib
import ssl
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from weakref import WeakValueDictionary

import aioftp

from ..exceptions import ErrorHandler, FTPError
from .models import FTPAuthType, FTPConfig, FTPConnectionInfo, FTPMode


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
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup_task()

    def _start_cleanup_task(self) -> None:
        """Start the background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_connections())

    async def _cleanup_connections(self) -> None:
        """Background task to clean up idle connections."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_idle_connections()
            except asyncio.CancelledError:
                break
            except Exception:
                # Continue cleanup even if there's an error
                pass

    async def _cleanup_idle_connections(self) -> None:
        """Remove idle connections that have exceeded the timeout."""
        async with self._lock:
            current_time = datetime.now()
            keys_to_remove = []

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
                    del self._connection_info[key]

    def _get_connection_key(self, host: str, port: int, username: Optional[str]) -> str:
        """Generate a unique key for connection pooling."""
        return f"{host}:{port}:{username or 'anonymous'}"

    @asynccontextmanager
    async def get_connection(self, url: str) -> Any:
        """
        Get an FTP connection from the pool or create a new one.

        Args:
            url: FTP URL to connect to

        Yields:
            aioftp.Client: FTP client connection
        """
        parsed = urlparse(url)
        host = parsed.hostname or 'localhost'
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
            if connection_key in self._connections and self._connections[connection_key]:
                client = self._connections[connection_key].pop()
                self._connection_info[connection_key].last_used = datetime.now()
                self._connection_info[connection_key].connection_count += 1
            else:
                # Create new connection
                client = await self._create_connection(host, port, username, password)

                # Update connection info
                if connection_key not in self._connection_info:
                    self._connection_info[connection_key] = FTPConnectionInfo(
                        host=host,
                        port=port,
                        username=username,
                        is_secure=parsed.scheme == 'ftps',
                        created_at=datetime.now(),
                        last_used=datetime.now(),
                        connection_count=1
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
                if len(self._connections[connection_key]) < self.config.max_connections_per_host:
                    self._connections[connection_key].append(client)
                else:
                    try:
                        await client.quit()
                    except Exception:
                        pass

    async def _create_connection(
        self,
        host: str,
        port: int,
        username: Optional[str],
        password: Optional[str]
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

            # Set transfer mode
            if self.config.mode == FTPMode.PASSIVE:
                client.passive_mode = True
            else:
                client.passive_mode = False

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
            "active_connections": sum(len(conns) for conns in self._connections.values()),
            "connection_info": {
                key: {
                    "host": info.host,
                    "port": info.port,
                    "username": info.username,
                    "is_secure": info.is_secure,
                    "created_at": info.created_at.isoformat(),
                    "last_used": info.last_used.isoformat(),
                    "connection_count": info.connection_count
                }
                for key, info in self._connection_info.items()
            }
        }