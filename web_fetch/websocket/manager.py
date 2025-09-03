"""
WebSocket connection manager.

This module provides a manager for handling multiple WebSocket connections
with connection pooling and lifecycle management.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, cast

from .client import WebSocketClient
from .core_models import WebSocketConfig, WebSocketConnectionState, WebSocketResult, WebSocketMessage

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manager for multiple WebSocket connections.

    The WebSocketManager provides centralized management of multiple WebSocket
    connections with features like connection pooling, automatic cleanup,
    and connection lifecycle management.

    Examples:
        Managing multiple connections:
        ```python
        manager = WebSocketManager()

        # Add connections
        config1 = WebSocketConfig(url="wss://api1.example.com/ws")
        config2 = WebSocketConfig(url="wss://api2.example.com/ws")

        await manager.add_connection("api1", config1)
        await manager.add_connection("api2", config2)

        # Send messages
        await manager.send_text("api1", "Hello API1!")
        await manager.send_text("api2", "Hello API2!")

        # Receive messages from all connections
        async for connection_id, message in manager.receive_all_messages():
            print(f"From {connection_id}: {message.data}")

        # Cleanup
        await manager.disconnect_all()
        ```
    """

    def __init__(self, max_connections: int = 100, cleanup_interval: float = 60.0,
                 health_check_interval: float = 30.0):
        """
        Initialize WebSocket manager.

        Args:
            max_connections: Maximum number of concurrent connections
            cleanup_interval: Interval in seconds for proactive cleanup
            health_check_interval: Interval in seconds for health checks
        """
        self.max_connections = max_connections
        self.cleanup_interval = cleanup_interval
        self.health_check_interval = health_check_interval

        self._connections: Dict[str, WebSocketClient] = {}
        self._connection_tasks: Dict[str, asyncio.Task[Any]] = {}
        self._connection_metadata: Dict[str, Dict[str, Any]] = {}

        # Alias for backward compatibility with tests
        self._clients = self._connections
        self._running = False

        # Cleanup and monitoring tasks
        self._cleanup_task: Optional[asyncio.Task[None]] = None
        self._health_monitor_task: Optional[asyncio.Task[None]] = None
        self._last_cleanup_time: float = time.time()
        self._last_health_check_time: float = time.time()

        # Statistics
        self._total_connections_created: int = 0
        self._total_connections_cleaned: int = 0
        self._unhealthy_connections_removed: int = 0

    async def add_connection(
        self, connection_id: str, config: WebSocketConfig
    ) -> WebSocketResult:
        """
        Add a new WebSocket connection.

        Args:
            connection_id: Unique identifier for the connection
            config: WebSocket configuration

        Returns:
            WebSocketResult with connection status

        Raises:
            ValueError: If connection limit exceeded or ID already exists
        """
        if len(self._connections) >= self.max_connections:
            raise ValueError(f"Maximum connections ({self.max_connections}) exceeded")

        if connection_id in self._connections:
            raise ValueError(f"Connection '{connection_id}' already exists")

        try:
            client = WebSocketClient(config)
            result = await client.connect()

            if result.success:
                self._connections[connection_id] = client
                self._connection_metadata[connection_id] = {
                    "created_at": time.time(),
                    "last_activity": time.time(),
                    "config": config,
                    "health_checks": 0,
                    "cleanup_attempts": 0
                }
                self._total_connections_created += 1
                logger.info(f"Added WebSocket connection: {connection_id}")

                # Start monitoring tasks if this is the first connection
                if len(self._connections) == 1:
                    await self._start_monitoring_tasks()

            return result

        except Exception as e:
            logger.error(f"Failed to add connection '{connection_id}': {e}")
            raise

    async def remove_connection(self, connection_id: str) -> WebSocketResult:
        """
        Remove a WebSocket connection.

        Args:
            connection_id: Connection identifier

        Returns:
            WebSocketResult with disconnection status
        """
        if connection_id not in self._connections:
            return WebSocketResult(
                success=False,
                connection_state=WebSocketConnectionState.DISCONNECTED,
                error=f"Connection '{connection_id}' not found",
            )

        try:
            client = self._connections[connection_id]
            result = await client.disconnect()

            # Remove from tracking
            del self._connections[connection_id]
            if connection_id in self._connection_metadata:
                del self._connection_metadata[connection_id]

            # Cancel any associated tasks
            if connection_id in self._connection_tasks:
                task = self._connection_tasks[connection_id]
                if not task.done():
                    task.cancel()
                del self._connection_tasks[connection_id]

            self._total_connections_cleaned += 1
            logger.info(f"Removed WebSocket connection: {connection_id}")

            # Stop monitoring tasks if no connections remain
            if len(self._connections) == 0:
                await self._stop_monitoring_tasks()

            return result

        except Exception as e:
            logger.error(f"Error removing connection '{connection_id}': {e}")
            return WebSocketResult(
                success=False,
                connection_state=WebSocketConnectionState.ERROR,
                error=str(e),
            )

    async def send_text(self, connection_id: str, text: str) -> bool:
        """
        Send text message to a specific connection.

        Args:
            connection_id: Connection identifier
            text: Text message to send

        Returns:
            True if message was sent successfully
        """
        if connection_id not in self._connections:
            logger.warning(f"Connection '{connection_id}' not found")
            return False

        try:
            client = self._connections[connection_id]
            await client.send_text(text)
            return True
        except Exception as e:
            logger.error(f"Error sending text to '{connection_id}': {e}")
            return False

    async def send_binary(self, connection_id: str, data: bytes) -> bool:
        """
        Send binary message to a specific connection.

        Args:
            connection_id: Connection identifier
            data: Binary data to send

        Returns:
            True if message was sent successfully
        """
        if connection_id not in self._connections:
            logger.warning(f"Connection '{connection_id}' not found")
            return False

        try:
            client = self._connections[connection_id]
            await client.send_binary(data)
            return True
        except Exception as e:
            logger.error(f"Error sending binary to '{connection_id}': {e}")
            return False

    async def broadcast_text(
        self, text: str, exclude: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """
        Broadcast text message to all connections.

        Args:
            text: Text message to broadcast
            exclude: List of connection IDs to exclude

        Returns:
            Dictionary mapping connection IDs to success status
        """
        exclude = exclude or []
        results = {}

        for connection_id in self._connections:
            if connection_id not in exclude:
                results[connection_id] = await self.send_text(connection_id, text)

        return results

    async def broadcast_binary(
        self, data: bytes, exclude: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """
        Broadcast binary message to all connections.

        Args:
            data: Binary data to broadcast
            exclude: List of connection IDs to exclude

        Returns:
            Dictionary mapping connection IDs to success status
        """
        exclude = exclude or []
        results = {}

        for connection_id in self._connections:
            if connection_id not in exclude:
                results[connection_id] = await self.send_binary(connection_id, data)

        return results

    async def receive_all_messages(self) -> AsyncIterator[Tuple[str, WebSocketMessage]]:
        """
        Async iterator for receiving messages from all connections.

        Yields:
            Tuple of (connection_id, WebSocketMessage)
        """
        # Create tasks for receiving from each connection
        receive_tasks = {}

        for connection_id, client in self._connections.items():
            if client.is_connected:
                task = asyncio.create_task(client.receive_message(timeout=1.0))
                receive_tasks[connection_id] = task

        while receive_tasks:
            try:
                # Wait for any message
                done, pending = await asyncio.wait(
                    receive_tasks.values(),
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=1.0,
                )

                # Process completed tasks
                for task in done:
                    # Find which connection this task belongs to
                    found_connection_id: Optional[str] = None
                    for cid, t in receive_tasks.items():
                        if t == task:
                            found_connection_id = cid
                            break

                    if found_connection_id:
                        try:
                            message = await task
                            if message:
                                yield found_connection_id, message
                        except Exception as e:
                            logger.error(f"Error receiving from '{found_connection_id}': {e}")

                        # Remove completed task and create new one if connection still active
                        del receive_tasks[found_connection_id]

                        maybe_client = self._connections.get(found_connection_id)
                        if maybe_client is not None and maybe_client.is_connected:
                            # Type guard: client is definitely not None here
                            client = maybe_client  # Type narrowed by None check
                            new_task = asyncio.create_task(
                                client.receive_message(timeout=1.0)
                            )
                            receive_tasks[found_connection_id] = new_task

                # Clean up disconnected connections
                to_remove = []
                for connection_id, client in self._connections.items():
                    if not client.is_connected and connection_id in receive_tasks:
                        receive_tasks[connection_id].cancel()
                        to_remove.append(connection_id)

                for connection_id in to_remove:
                    del receive_tasks[connection_id]

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in receive_all_messages: {e}")
                break

        # Cancel remaining tasks
        for task in receive_tasks.values():
            if not task.done():
                task.cancel()

    async def disconnect_all(self) -> Dict[str, WebSocketResult]:
        """
        Disconnect all WebSocket connections.

        Returns:
            Dictionary mapping connection IDs to disconnection results
        """
        results = {}

        # Disconnect all connections
        for connection_id in list(self._connections.keys()):
            results[connection_id] = await self.remove_connection(connection_id)

        return results

    def get_connection_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all connections.

        Returns:
            Dictionary mapping connection IDs to status information
        """
        status = {}

        for connection_id, client in self._connections.items():
            metadata = self._connection_metadata.get(connection_id, {})
            client_stats = client.statistics

            status[connection_id] = {
                "state": client.connection_state.value,
                "is_connected": client.is_connected,
                "statistics": client_stats,
                "metadata": {
                    "created_at": metadata.get("created_at"),
                    "last_activity": metadata.get("last_activity"),
                    "health_checks": metadata.get("health_checks", 0),
                    "cleanup_attempts": metadata.get("cleanup_attempts", 0),
                    "age_seconds": time.time() - metadata.get("created_at", time.time()),
                },
                "health": client.get_connection_health() if hasattr(client, 'get_connection_health') else {},
                "session_reuse": client.session_statistics if hasattr(client, 'session_statistics') else {},
            }

        return status

    def list_connections(self) -> List[str]:
        """
        Get list of connection IDs.

        Returns:
            List of connection identifiers
        """
        return list(self._connections.keys())

    async def _start_monitoring_tasks(self) -> None:
        """Start background monitoring tasks."""
        if not self._cleanup_task or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        if not self._health_monitor_task or self._health_monitor_task.done():
            self._health_monitor_task = asyncio.create_task(self._health_monitor_loop())

        logger.debug("Started WebSocket manager monitoring tasks")

    async def _stop_monitoring_tasks(self) -> None:
        """Stop background monitoring tasks."""
        tasks = [self._cleanup_task, self._health_monitor_task]

        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._cleanup_task = None
        self._health_monitor_task = None
        logger.debug("Stopped WebSocket manager monitoring tasks")

    async def _cleanup_loop(self) -> None:
        """Background task for proactive connection cleanup."""
        try:
            while len(self._connections) > 0:
                await asyncio.sleep(self.cleanup_interval)
                await self._perform_cleanup()
        except asyncio.CancelledError:
            logger.debug("Cleanup loop cancelled")
        except Exception as e:
            logger.error(f"Error in cleanup loop: {e}")

    async def _health_monitor_loop(self) -> None:
        """Background task for connection health monitoring."""
        try:
            while len(self._connections) > 0:
                await asyncio.sleep(self.health_check_interval)
                await self._perform_health_checks()
        except asyncio.CancelledError:
            logger.debug("Health monitor loop cancelled")
        except Exception as e:
            logger.error(f"Error in health monitor loop: {e}")

    async def _perform_cleanup(self) -> None:
        """Perform proactive cleanup of stale connections."""
        current_time = time.time()
        connections_to_remove = []

        for connection_id, client in self._connections.items():
            metadata = self._connection_metadata.get(connection_id, {})

            # Check if connection is in a bad state
            should_remove = False
            reason = ""

            if not client.is_connected:
                should_remove = True
                reason = "disconnected"
            elif client.connection_state in [WebSocketConnectionState.ERROR, WebSocketConnectionState.CLOSED]:
                should_remove = True
                reason = f"bad state: {client.connection_state.value}"
            elif hasattr(client, 'is_connection_healthy') and not client.is_connection_healthy():
                should_remove = True
                reason = "unhealthy"
                self._unhealthy_connections_removed += 1

            if should_remove:
                connections_to_remove.append((connection_id, reason))
                metadata["cleanup_attempts"] = metadata.get("cleanup_attempts", 0) + 1

        # Remove stale connections
        for connection_id, reason in connections_to_remove:
            logger.info(f"Proactively removing connection '{connection_id}': {reason}")
            try:
                await self.remove_connection(connection_id)
            except Exception as e:
                logger.error(f"Error during proactive cleanup of '{connection_id}': {e}")

        self._last_cleanup_time = current_time

        if connections_to_remove:
            logger.info(f"Cleanup completed: removed {len(connections_to_remove)} connections")

    async def _perform_health_checks(self) -> None:
        """Perform health checks on all connections."""
        current_time = time.time()

        for connection_id, client in self._connections.items():
            metadata = self._connection_metadata.get(connection_id, {})
            metadata["health_checks"] = metadata.get("health_checks", 0) + 1
            metadata["last_activity"] = current_time

            # Update connection health if method is available
            if hasattr(client, '_update_connection_health'):
                try:
                    client._update_connection_health()
                except Exception as e:
                    logger.debug(f"Error updating health for '{connection_id}': {e}")

        self._last_health_check_time = current_time

    def get_manager_statistics(self) -> Dict[str, Any]:
        """Get comprehensive manager statistics."""
        current_time = time.time()

        # Calculate connection statistics
        healthy_connections = 0
        unhealthy_connections = 0
        total_health_score = 0.0

        for client in self._connections.values():
            if hasattr(client, 'is_connection_healthy'):
                if client.is_connection_healthy():
                    healthy_connections += 1
                else:
                    unhealthy_connections += 1

            if hasattr(client, '_connection_quality_score'):
                total_health_score += client._connection_quality_score

        avg_health_score = (total_health_score / len(self._connections)) if self._connections else 0

        return {
            "total_connections": len(self._connections),
            "max_connections": self.max_connections,
            "healthy_connections": healthy_connections,
            "unhealthy_connections": unhealthy_connections,
            "average_health_score": round(avg_health_score, 2),
            "total_created": self._total_connections_created,
            "total_cleaned": self._total_connections_cleaned,
            "unhealthy_removed": self._unhealthy_connections_removed,
            "cleanup_interval": self.cleanup_interval,
            "health_check_interval": self.health_check_interval,
            "last_cleanup_time": self._last_cleanup_time,
            "last_health_check_time": self._last_health_check_time,
            "monitoring_active": (
                self._cleanup_task is not None and not self._cleanup_task.done() and
                self._health_monitor_task is not None and not self._health_monitor_task.done()
            )
        }

    async def add_client(self, client_id: str, config: WebSocketConfig) -> str:
        """
        Add a new WebSocket client to the manager.

        Args:
            client_id: Unique identifier for the client
            config: WebSocket configuration

        Returns:
            The client ID

        Raises:
            ValueError: If client_id already exists or max connections exceeded
        """
        if client_id in self._connections:
            raise ValueError(f"Client with ID '{client_id}' already exists")

        if len(self._connections) >= self.max_connections:
            raise ValueError(f"Maximum connections ({self.max_connections}) exceeded")

        # Create new client
        client = WebSocketClient(config)
        self._connections[client_id] = client

        logger.info(f"Added WebSocket client: {client_id}")
        return client_id

    async def remove_client(self, client_id: str) -> bool:
        """
        Remove a WebSocket client from the manager.

        Args:
            client_id: Unique identifier for the client

        Returns:
            True if client was removed, False if not found
        """
        if client_id not in self._connections:
            return False

        # Get the client and disconnect it
        client = self._connections[client_id]
        try:
            await client.disconnect()
        except Exception as e:
            logger.warning(f"Error disconnecting client {client_id}: {e}")

        # Remove from connections
        del self._connections[client_id]

        # Clean up any associated tasks
        if client_id in self._connection_tasks:
            task = self._connection_tasks[client_id]
            if not task.done():
                task.cancel()
            del self._connection_tasks[client_id]

        logger.info(f"Removed WebSocket client: {client_id}")
        return True

    def get_connection(self, connection_id: str) -> Optional[WebSocketClient]:
        """
        Get WebSocket client by connection ID.

        Args:
            connection_id: Connection identifier

        Returns:
            WebSocketClient instance or None if not found
        """
        return self._connections.get(connection_id)

    @property
    def connection_count(self) -> int:
        """Get number of active connections."""
        return len(self._connections)

    @property
    def connected_count(self) -> int:
        """Get number of connected WebSocket connections."""
        return sum(1 for client in self._connections.values() if client.is_connected)
