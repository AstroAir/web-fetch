"""
WebSocket client implementation.

This module provides a comprehensive WebSocket client with automatic reconnection,
message queuing, and event handling capabilities.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union

import aiohttp
from aiohttp import WSMsgType

from .models import (
    WebSocketConfig,
    WebSocketMessage,
    WebSocketMessageType,
    WebSocketConnectionState,
    WebSocketResult,
    WebSocketError,
)

logger = logging.getLogger(__name__)


class WebSocketClient:
    """
    Comprehensive WebSocket client with automatic reconnection and message handling.
    
    The WebSocketClient provides a robust WebSocket implementation with features like:
    - Automatic reconnection with exponential backoff
    - Message queuing and buffering
    - Ping/pong handling for connection health
    - Event-driven message handling
    - Connection state management
    - SSL support for secure connections
    
    Examples:
        Basic WebSocket connection:
        ```python
        config = WebSocketConfig(
            url="wss://echo.websocket.org",
            auto_reconnect=True,
            ping_interval=30.0
        )
        
        async with WebSocketClient(config) as client:
            # Send a message
            await client.send_text("Hello WebSocket!")
            
            # Receive messages
            async for message in client.receive_messages():
                print(f"Received: {message.data}")
                if some_condition:
                    break
        ```
        
        Event-driven handling:
        ```python
        def on_message(message: WebSocketMessage):
            print(f"Message: {message.data}")
        
        def on_connect():
            print("Connected to WebSocket")
        
        def on_disconnect():
            print("Disconnected from WebSocket")
        
        client = WebSocketClient(config)
        client.on_message = on_message
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        
        await client.connect()
        await client.send_text("Hello!")
        await asyncio.sleep(10)  # Keep connection alive
        await client.disconnect()
        ```
    """
    
    def __init__(self, config: WebSocketConfig):
        """
        Initialize WebSocket client.
        
        Args:
            config: WebSocket configuration
        """
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        self._connection_state = WebSocketConnectionState.DISCONNECTED
        
        # Message handling
        self._message_queue: asyncio.Queue = asyncio.Queue(maxsize=config.max_queue_size)
        self._send_queue: asyncio.Queue = asyncio.Queue()
        
        # Tasks
        self._receive_task: Optional[asyncio.Task] = None
        self._send_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        
        # Statistics
        self._connect_time: Optional[float] = None
        self._messages_sent = 0
        self._messages_received = 0
        self._bytes_sent = 0
        self._bytes_received = 0
        self._reconnect_attempts = 0
        
        # Event handlers
        self.on_message: Optional[Callable[[WebSocketMessage], None]] = None
        self.on_connect: Optional[Callable[[], None]] = None
        self.on_disconnect: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None
    
    async def __aenter__(self) -> WebSocketClient:
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()
    
    @property
    def connection_state(self) -> WebSocketConnectionState:
        """Get current connection state."""
        return self._connection_state
    
    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._connection_state == WebSocketConnectionState.CONNECTED
    
    @property
    def statistics(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "connection_state": self._connection_state.value,
            "connect_time": self._connect_time,
            "messages_sent": self._messages_sent,
            "messages_received": self._messages_received,
            "bytes_sent": self._bytes_sent,
            "bytes_received": self._bytes_received,
            "reconnect_attempts": self._reconnect_attempts,
            "queue_size": self._message_queue.qsize(),
            "send_queue_size": self._send_queue.qsize(),
        }
    
    async def connect(self) -> WebSocketResult:
        """
        Connect to WebSocket server.
        
        Returns:
            WebSocketResult with connection status
            
        Raises:
            WebSocketError: If connection fails
        """
        if self._connection_state in [WebSocketConnectionState.CONNECTED, WebSocketConnectionState.CONNECTING]:
            return WebSocketResult(
                success=True,
                connection_state=self._connection_state
            )
        
        try:
            self._connection_state = WebSocketConnectionState.CONNECTING
            start_time = time.time()
            
            # Create session if needed
            if not self._session:
                timeout = aiohttp.ClientTimeout(total=self.config.connect_timeout)
                connector = aiohttp.TCPConnector(verify_ssl=self.config.verify_ssl)
                self._session = aiohttp.ClientSession(
                    timeout=timeout,
                    connector=connector
                )
            
            # Connect to WebSocket
            self._websocket = await self._session.ws_connect(
                str(self.config.url),
                protocols=self.config.subprotocols,
                headers=self.config.headers,
                compress=self.config.enable_compression,
                max_msg_size=self.config.max_message_size,
                timeout=self.config.connect_timeout,
                heartbeat=self.config.ping_interval if self.config.enable_ping else None
            )
            
            self._connection_state = WebSocketConnectionState.CONNECTED
            self._connect_time = time.time() - start_time
            self._reconnect_attempts = 0
            
            # Start background tasks
            await self._start_tasks()
            
            # Call connect handler
            if self.on_connect:
                try:
                    self.on_connect()
                except Exception as e:
                    logger.warning(f"Error in connect handler: {e}")
            
            logger.info(f"Connected to WebSocket: {self.config.url}")
            
            return WebSocketResult(
                success=True,
                connection_state=self._connection_state,
                connection_time=self._connect_time
            )
            
        except Exception as e:
            self._connection_state = WebSocketConnectionState.ERROR
            error_msg = f"Failed to connect to WebSocket: {str(e)}"
            logger.error(error_msg)
            
            if self.on_error:
                try:
                    self.on_error(e)
                except Exception as handler_error:
                    logger.warning(f"Error in error handler: {handler_error}")
            
            # Try to reconnect if enabled
            if self.config.auto_reconnect and self._reconnect_attempts < self.config.max_reconnect_attempts:
                await self._schedule_reconnect()
            
            raise WebSocketError(error_msg)
    
    async def disconnect(self) -> WebSocketResult:
        """
        Disconnect from WebSocket server.
        
        Returns:
            WebSocketResult with disconnection status
        """
        if self._connection_state == WebSocketConnectionState.DISCONNECTED:
            return WebSocketResult(
                success=True,
                connection_state=self._connection_state
            )
        
        try:
            self._connection_state = WebSocketConnectionState.CLOSING
            
            # Stop background tasks
            await self._stop_tasks()
            
            # Close WebSocket connection
            if self._websocket and not self._websocket.closed:
                await self._websocket.close()
            
            # Close session
            if self._session and not self._session.closed:
                await self._session.close()
                self._session = None
            
            self._connection_state = WebSocketConnectionState.DISCONNECTED
            self._websocket = None
            
            # Call disconnect handler
            if self.on_disconnect:
                try:
                    self.on_disconnect()
                except Exception as e:
                    logger.warning(f"Error in disconnect handler: {e}")
            
            logger.info("Disconnected from WebSocket")
            
            return WebSocketResult(
                success=True,
                connection_state=self._connection_state,
                total_messages_sent=self._messages_sent,
                total_messages_received=self._messages_received,
                total_bytes_sent=self._bytes_sent,
                total_bytes_received=self._bytes_received
            )
            
        except Exception as e:
            error_msg = f"Error during disconnect: {str(e)}"
            logger.error(error_msg)
            return WebSocketResult(
                success=False,
                connection_state=WebSocketConnectionState.ERROR,
                error=error_msg
            )
    
    async def send_text(self, text: str) -> None:
        """
        Send text message.
        
        Args:
            text: Text message to send
            
        Raises:
            WebSocketError: If not connected or send fails
        """
        if not self.is_connected:
            raise WebSocketError("WebSocket is not connected")
        
        message = WebSocketMessage(
            type=WebSocketMessageType.TEXT,
            data=text
        )
        await self._send_queue.put(message)
    
    async def send_binary(self, data: bytes) -> None:
        """
        Send binary message.
        
        Args:
            data: Binary data to send
            
        Raises:
            WebSocketError: If not connected or send fails
        """
        if not self.is_connected:
            raise WebSocketError("WebSocket is not connected")
        
        message = WebSocketMessage(
            type=WebSocketMessageType.BINARY,
            data=data
        )
        await self._send_queue.put(message)
    
    async def receive_message(self, timeout: Optional[float] = None) -> Optional[WebSocketMessage]:
        """
        Receive a single message.
        
        Args:
            timeout: Timeout in seconds (None for no timeout)
            
        Returns:
            WebSocketMessage or None if timeout
        """
        try:
            if timeout:
                return await asyncio.wait_for(self._message_queue.get(), timeout=timeout)
            else:
                return await self._message_queue.get()
        except asyncio.TimeoutError:
            return None
    
    async def receive_messages(self) -> AsyncIterator[WebSocketMessage]:
        """
        Async iterator for receiving messages.

        Yields:
            WebSocketMessage instances
        """
        while self.is_connected or not self._message_queue.empty():
            try:
                message = await self.receive_message(timeout=1.0)
                if message:
                    yield message
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error receiving message: {e}")
                break

    async def _start_tasks(self) -> None:
        """Start background tasks for message handling."""
        self._receive_task = asyncio.create_task(self._receive_loop())
        self._send_task = asyncio.create_task(self._send_loop())

        if self.config.enable_ping:
            self._ping_task = asyncio.create_task(self._ping_loop())

    async def _stop_tasks(self) -> None:
        """Stop background tasks."""
        tasks = [self._receive_task, self._send_task, self._ping_task, self._reconnect_task]

        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._receive_task = None
        self._send_task = None
        self._ping_task = None
        self._reconnect_task = None

    async def _receive_loop(self) -> None:
        """Background task for receiving messages."""
        if not self._websocket:
            return

        try:
            async for msg in self._websocket:
                if msg.type == WSMsgType.TEXT:
                    message = WebSocketMessage(
                        type=WebSocketMessageType.TEXT,
                        data=msg.data
                    )
                    self._messages_received += 1
                    self._bytes_received += message.size

                elif msg.type == WSMsgType.BINARY:
                    message = WebSocketMessage(
                        type=WebSocketMessageType.BINARY,
                        data=msg.data
                    )
                    self._messages_received += 1
                    self._bytes_received += message.size

                elif msg.type == WSMsgType.PONG:
                    message = WebSocketMessage(
                        type=WebSocketMessageType.PONG,
                        data=msg.data
                    )

                elif msg.type == WSMsgType.CLOSE:
                    logger.info("WebSocket connection closed by server")
                    break

                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {self._websocket.exception()}")
                    break
                else:
                    continue

                # Add message to queue
                try:
                    await self._message_queue.put(message)

                    # Call message handler
                    if self.on_message:
                        try:
                            self.on_message(message)
                        except Exception as e:
                            logger.warning(f"Error in message handler: {e}")

                except asyncio.QueueFull:
                    logger.warning("Message queue is full, dropping message")

        except Exception as e:
            logger.error(f"Error in receive loop: {e}")
            if self.config.auto_reconnect:
                await self._schedule_reconnect()

    async def _send_loop(self) -> None:
        """Background task for sending messages."""
        if not self._websocket:
            return

        try:
            while self.is_connected:
                try:
                    message = await asyncio.wait_for(self._send_queue.get(), timeout=1.0)

                    if message.type == WebSocketMessageType.TEXT:
                        await self._websocket.send_str(message.data)
                    elif message.type == WebSocketMessageType.BINARY:
                        await self._websocket.send_bytes(message.data)

                    self._messages_sent += 1
                    self._bytes_sent += message.size

                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Error sending message: {e}")
                    break

        except Exception as e:
            logger.error(f"Error in send loop: {e}")

    async def _ping_loop(self) -> None:
        """Background task for sending ping messages."""
        try:
            while self.is_connected:
                await asyncio.sleep(self.config.ping_interval)
                if self.is_connected and self._websocket:
                    try:
                        await self._websocket.ping()
                    except Exception as e:
                        logger.error(f"Error sending ping: {e}")
                        break
        except Exception as e:
            logger.error(f"Error in ping loop: {e}")

    async def _schedule_reconnect(self) -> None:
        """Schedule reconnection attempt."""
        if self._reconnect_task and not self._reconnect_task.done():
            return  # Reconnection already scheduled

        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        """Background task for reconnection attempts."""
        delay = self.config.reconnect_delay

        while (self._reconnect_attempts < self.config.max_reconnect_attempts and
               self._connection_state != WebSocketConnectionState.CONNECTED):

            self._reconnect_attempts += 1
            self._connection_state = WebSocketConnectionState.RECONNECTING

            logger.info(f"Reconnection attempt {self._reconnect_attempts}/{self.config.max_reconnect_attempts}")

            await asyncio.sleep(delay)

            try:
                await self.connect()
                return  # Successfully reconnected
            except Exception as e:
                logger.warning(f"Reconnection attempt {self._reconnect_attempts} failed: {e}")

                # Increase delay with backoff
                delay = min(delay * self.config.reconnect_backoff, self.config.max_reconnect_delay)

        # All reconnection attempts failed
        self._connection_state = WebSocketConnectionState.ERROR
        logger.error("All reconnection attempts failed")
