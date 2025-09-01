"""
WebSocket connection manager.

This module provides a manager for handling multiple WebSocket connections
with connection pooling and lifecycle management.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, cast

from .client import WebSocketClient
from .models import WebSocketConfig, WebSocketConnectionState, WebSocketResult, WebSocketMessage

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

    def __init__(self, max_connections: int = 100):
        """
        Initialize WebSocket manager.

        Args:
            max_connections: Maximum number of concurrent connections
        """
        self.max_connections = max_connections
        self._connections: Dict[str, WebSocketClient] = {}
        self._connection_tasks: Dict[str, asyncio.Task] = {}
        # Alias for backward compatibility with tests
        self._clients = self._connections
        self._running = False

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
                logger.info(f"Added WebSocket connection: {connection_id}")

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

            # Cancel any associated tasks
            if connection_id in self._connection_tasks:
                task = self._connection_tasks[connection_id]
                if not task.done():
                    task.cancel()
                del self._connection_tasks[connection_id]

            logger.info(f"Removed WebSocket connection: {connection_id}")
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
            status[connection_id] = {
                "state": client.connection_state.value,
                "is_connected": client.is_connected,
                "statistics": client.statistics,
            }

        return status

    def list_connections(self) -> List[str]:
        """
        Get list of connection IDs.

        Returns:
            List of connection identifiers
        """
        return list(self._connections.keys())

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
