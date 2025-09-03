"""
WebSocket client implementation.

This module provides a comprehensive WebSocket client with automatic reconnection,
message queuing, and event handling capabilities.
"""

from __future__ import annotations

import asyncio
import gc
import logging
import psutil
import sys
import time
import weakref
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union

import aiohttp
from aiohttp import WSMsgType

from .exceptions import WebSocketError
from .core_models import (
    WebSocketConfig,
    WebSocketConnectionState,
    WebSocketMessage,
    WebSocketMessageType,
    WebSocketResult,
    create_message,
)
from .optimization import (
    get_message_pool_statistics,
    AdaptiveQueue,
    get_global_profiler,
)
from .callbacks import WeakCallbackManager

try:
    from ..monitoring.metrics import MetricsCollector
    METRICS_AVAILABLE = True
except ImportError:
    MetricsCollector = None  # type: ignore
    METRICS_AVAILABLE = False

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

    def __init__(self, config: WebSocketConfig, session: Optional[aiohttp.ClientSession] = None):
        """
        Initialize WebSocket client.

        Args:
            config: WebSocket configuration
            session: Optional existing aiohttp session to reuse
        """
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = session
        self._websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        self._connection_state = WebSocketConnectionState.DISCONNECTED
        self._session_reused: bool = session is not None
        self._external_session: bool = session is not None

        # Message handling with adaptive queues
        if config.enable_adaptive_queues:
            self._message_queue = AdaptiveQueue(
                initial_maxsize=config.max_queue_size,
                min_size=config.adaptive_queue_min_size,
                max_size=config.adaptive_queue_max_size,
                growth_factor=config.adaptive_queue_growth_factor,
                shrink_threshold=config.adaptive_queue_shrink_threshold
            )
            self._send_queue = AdaptiveQueue(
                initial_maxsize=min(config.max_queue_size, 100),
                min_size=config.adaptive_queue_min_size,
                max_size=config.adaptive_queue_max_size,
                growth_factor=config.adaptive_queue_growth_factor,
                shrink_threshold=config.adaptive_queue_shrink_threshold
            )
        else:
            # Fallback to standard asyncio queues
            self._message_queue = asyncio.Queue(maxsize=config.max_queue_size)  # type: ignore
            self._send_queue = asyncio.Queue()  # type: ignore

        # Tasks
        self._receive_task: Optional[asyncio.Task[None]] = None
        self._send_task: Optional[asyncio.Task[None]] = None
        self._ping_task: Optional[asyncio.Task[None]] = None
        self._reconnect_task: Optional[asyncio.Task[None]] = None

        # Statistics
        self._connect_time: Optional[float] = None
        self._messages_sent = 0
        self._messages_received = 0
        self._bytes_sent = 0
        self._bytes_received = 0
        self._reconnect_attempts = 0

        # Memory tracking
        self._initial_memory_usage: Optional[float] = None
        self._peak_memory_usage: float = 0.0
        self._last_gc_time: float = time.time()
        self._gc_interval: float = 60.0  # Run GC every 60 seconds
        self._memory_samples: List[float] = []
        self._max_memory_samples: int = 100

        # Connection health monitoring
        self._last_ping_time: Optional[float] = None
        self._last_pong_time: Optional[float] = None
        self._ping_failures: int = 0
        self._max_ping_failures: int = 3
        self._health_check_interval: float = 30.0
        self._last_health_check: float = time.time()
        self._connection_quality_score: float = 100.0
        self._latency_samples: List[float] = []
        self._max_latency_samples: int = 50

        # Metrics integration
        self._metrics_collector: Optional[MetricsCollector] = None
        if METRICS_AVAILABLE:
            try:
                self._metrics_collector = MetricsCollector()
            except Exception as e:
                logger.debug(f"Failed to initialize metrics collector: {e}")

        self._metrics_tags = {
            "websocket_url": str(config.url),
            "client_id": id(self),
        }

        # Performance profiling
        self._profiler = get_global_profiler()
        self._enable_profiling = True

        # Message batching for high-throughput scenarios
        self._batch_size = getattr(config, 'batch_size', 10)
        self._batch_timeout = getattr(config, 'batch_timeout', 0.01)  # 10ms
        self._enable_batching = getattr(config, 'enable_batching', False)

        # Event handlers with weak reference management
        self._callback_manager = WeakCallbackManager()
        self.on_message: Optional[Callable[[WebSocketMessage], None]] = None
        self.on_connect: Optional[Callable[[], None]] = None
        self.on_disconnect: Optional[Callable[[], None]] = None

        # Initialize memory tracking
        self._track_memory_usage()

    @property
    def state(self) -> WebSocketConnectionState:
        """Get the current connection state."""
        return self._connection_state

    @state.setter
    def state(self, value: WebSocketConnectionState) -> None:
        """Set the current connection state."""
        self._connection_state = value
        self.on_error: Optional[Callable[[Exception], None]] = None

    async def __aenter__(self) -> WebSocketClient:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Optional[type], exc_val: Optional[BaseException], exc_tb: Optional[object]) -> None:
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
        """Get connection statistics including message pool and adaptive queue metrics."""
        stats = {
            "connection_state": self._connection_state.value,
            "connect_time": self._connect_time,
            "messages_sent": self._messages_sent,
            "messages_received": self._messages_received,
            "bytes_sent": self._bytes_sent,
            "bytes_received": self._bytes_received,
            "reconnect_attempts": self._reconnect_attempts,
            "queue_size": self._message_queue.qsize(),
            "send_queue_size": self._send_queue.qsize(),
            "message_pool": get_message_pool_statistics(),
        }

        # Add adaptive queue statistics if available
        if hasattr(self._message_queue, 'statistics'):
            stats["adaptive_message_queue"] = self._message_queue.statistics
        if hasattr(self._send_queue, 'statistics'):
            stats["adaptive_send_queue"] = self._send_queue.statistics

        # Calculate total connection time if connected
        if self._connect_time and self._connection_state == WebSocketConnectionState.CONNECTED:
            stats["total_connection_time"] = time.time() - (time.time() - self._connect_time)

        # Add callback manager statistics
        stats["callback_manager"] = self._callback_manager.statistics

        # Add session statistics
        stats["session"] = self.session_statistics

        # Add connection health statistics
        if hasattr(self, 'get_connection_health'):
            stats["connection_health"] = self.get_connection_health()

        # Add memory statistics
        stats["memory"] = self.get_memory_statistics()

        return stats

    def add_event_handler(self, event_type: str, handler: Callable[..., Any]) -> None:
        """
        Add an event handler using weak references.

        Args:
            event_type: Type of event ('message', 'connect', 'disconnect', 'error')
            handler: Callback function to add
        """
        self._callback_manager.add_callback(event_type, handler)

        # Also set the direct property for backward compatibility
        if event_type == 'message' and hasattr(handler, '__call__'):
            self.on_message = handler
        elif event_type == 'connect' and hasattr(handler, '__call__'):
            self.on_connect = handler
        elif event_type == 'disconnect' and hasattr(handler, '__call__'):
            self.on_disconnect = handler
        elif event_type == 'error' and hasattr(handler, '__call__'):
            self.on_error = handler

    def remove_event_handler(self, event_type: str, handler: Callable[..., Any]) -> None:
        """
        Remove an event handler.

        Args:
            event_type: Type of event ('message', 'connect', 'disconnect', 'error')
            handler: Callback function to remove
        """
        self._callback_manager.remove_callback(event_type, handler)

        # Clear direct property if it matches
        if event_type == 'message' and self.on_message is handler:
            self.on_message = None
        elif event_type == 'connect' and self.on_connect is handler:
            self.on_connect = None
        elif event_type == 'disconnect' and self.on_disconnect is handler:
            self.on_disconnect = None
        elif event_type == 'error' and self.on_error is handler:
            self.on_error = None

    def clear_event_handlers(self, event_type: Optional[str] = None) -> None:
        """
        Clear event handlers.

        Args:
            event_type: Specific event type to clear, or None to clear all
        """
        self._callback_manager.clear_callbacks(event_type)

        if event_type is None or event_type == 'message':
            self.on_message = None
        if event_type is None or event_type == 'connect':
            self.on_connect = None
        if event_type is None or event_type == 'disconnect':
            self.on_disconnect = None
        if event_type is None or event_type == 'error':
            self.on_error = None

    def _track_memory_usage(self) -> None:
        """Track current memory usage."""
        try:
            process = psutil.Process()
            current_memory = process.memory_info().rss / 1024 / 1024  # MB

            if self._initial_memory_usage is None:
                self._initial_memory_usage = current_memory

            self._peak_memory_usage = max(self._peak_memory_usage, current_memory)

            # Keep a rolling window of memory samples
            self._memory_samples.append(current_memory)
            if len(self._memory_samples) > self._max_memory_samples:
                self._memory_samples.pop(0)

        except Exception as e:
            logger.debug(f"Failed to track memory usage: {e}")

    def _maybe_run_gc(self) -> None:
        """Run garbage collection if interval has passed."""
        current_time = time.time()
        if (current_time - self._last_gc_time) >= self._gc_interval:
            gc.collect()
            self._last_gc_time = current_time
            logger.debug("Performed garbage collection for WebSocket client")

    def get_memory_statistics(self) -> Dict[str, Any]:
        """Get detailed memory usage statistics."""
        self._track_memory_usage()

        if not self._memory_samples:
            return {"error": "No memory samples available"}

        current_memory = self._memory_samples[-1]
        avg_memory = sum(self._memory_samples) / len(self._memory_samples)
        min_memory = min(self._memory_samples)
        max_memory = max(self._memory_samples)

        return {
            "current_memory_mb": round(current_memory, 2),
            "initial_memory_mb": round(self._initial_memory_usage or 0, 2),
            "peak_memory_mb": round(self._peak_memory_usage, 2),
            "average_memory_mb": round(avg_memory, 2),
            "min_memory_mb": round(min_memory, 2),
            "max_memory_mb": round(max_memory, 2),
            "memory_growth_mb": round(current_memory - (self._initial_memory_usage or 0), 2),
            "memory_samples_count": len(self._memory_samples),
            "gc_collections": gc.get_count(),
        }

    def _update_connection_health(self) -> None:
        """Update connection health metrics."""
        current_time = time.time()

        # Calculate connection quality score based on various factors
        quality_score = 100.0

        # Ping/pong health
        if self._last_ping_time and self._last_pong_time:
            ping_latency = self._last_pong_time - self._last_ping_time
            self._latency_samples.append(ping_latency)
            if len(self._latency_samples) > self._max_latency_samples:
                self._latency_samples.pop(0)

            # Penalize high latency
            avg_latency = sum(self._latency_samples) / len(self._latency_samples)
            if avg_latency > 1.0:  # More than 1 second
                quality_score -= min(50, avg_latency * 10)

        # Ping failure penalty
        if self._ping_failures > 0:
            quality_score -= (self._ping_failures / self._max_ping_failures) * 30

        # Queue health
        if hasattr(self._message_queue, 'qsize'):
            queue_usage = self._message_queue.qsize()
            if hasattr(self._message_queue, 'maxsize'):
                max_size = self._message_queue.maxsize
                if max_size > 0:
                    usage_ratio = queue_usage / max_size
                    if usage_ratio > 0.8:  # Queue is 80% full
                        quality_score -= (usage_ratio - 0.8) * 100

        self._connection_quality_score = max(0.0, quality_score)
        self._last_health_check = current_time

    def get_connection_health(self) -> Dict[str, Any]:
        """Get detailed connection health information."""
        self._update_connection_health()

        avg_latency = 0.0
        if self._latency_samples:
            avg_latency = sum(self._latency_samples) / len(self._latency_samples)

        return {
            "quality_score": round(self._connection_quality_score, 2),
            "ping_failures": self._ping_failures,
            "max_ping_failures": self._max_ping_failures,
            "last_ping_time": self._last_ping_time,
            "last_pong_time": self._last_pong_time,
            "average_latency_ms": round(avg_latency * 1000, 2) if avg_latency > 0 else 0,
            "latency_samples_count": len(self._latency_samples),
            "is_healthy": self._connection_quality_score > 50.0,
            "health_status": self._get_health_status(),
            "last_health_check": self._last_health_check,
        }

    def _get_health_status(self) -> str:
        """Get human-readable health status."""
        if self._connection_quality_score >= 80:
            return "excellent"
        elif self._connection_quality_score >= 60:
            return "good"
        elif self._connection_quality_score >= 40:
            return "fair"
        elif self._connection_quality_score >= 20:
            return "poor"
        else:
            return "critical"

    def is_connection_healthy(self) -> bool:
        """Check if the connection is considered healthy."""
        self._update_connection_health()
        return (
            self._connection_quality_score > 50.0 and
            self._ping_failures < self._max_ping_failures and
            self._connection_state == WebSocketConnectionState.CONNECTED
        )

    async def _create_optimized_session(self) -> aiohttp.ClientSession:
        """Create an optimized aiohttp session for WebSocket connections."""
        timeout = aiohttp.ClientTimeout(total=self.config.connect_timeout)

        # Optimize connector settings for WebSocket connections
        connector = aiohttp.TCPConnector(
            verify_ssl=self.config.verify_ssl,
            limit=100,  # Total connection pool size
            limit_per_host=30,  # Connections per host
            ttl_dns_cache=300,  # DNS cache TTL
            use_dns_cache=True,
            enable_cleanup_closed=True,
            keepalive_timeout=30,  # Keep connections alive
            force_close=False,  # Allow connection reuse
        )

        return aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers=self.config.headers,
            raise_for_status=False
        )

    def set_session(self, session: aiohttp.ClientSession) -> None:
        """
        Set an external session for connection reuse.

        Args:
            session: aiohttp ClientSession to use
        """
        if self._connection_state != WebSocketConnectionState.DISCONNECTED:
            raise WebSocketError("Cannot change session while connected")

        # Close existing session if it's not external
        if self._session and not self._external_session:
            asyncio.create_task(self._session.close())

        self._session = session
        self._external_session = True
        self._session_reused = True
        logger.debug("Set external session for WebSocket client")

    def get_session(self) -> Optional[aiohttp.ClientSession]:
        """
        Get the current aiohttp session.

        Returns:
            Current ClientSession or None
        """
        return self._session

    @property
    def session_statistics(self) -> Dict[str, Any]:
        """Get session reuse statistics."""
        return {
            "session_reused": self._session_reused,
            "external_session": self._external_session,
            "session_available": self._session is not None,
            "session_closed": self._session.closed if self._session else True,
        }

    def _record_metrics(self, event_type: str, success: bool = True, duration: float = 0.0,
                       additional_tags: Optional[Dict[str, str]] = None) -> None:
        """Record metrics for WebSocket operations."""
        if not self._metrics_collector:
            return

        try:
            tags: Dict[str, str] = {}
            for k, v in self._metrics_tags.items():
                tags[k] = str(v)
            if additional_tags:
                for k, v in additional_tags.items():
                    tags[k] = str(v)

            tags["event_type"] = event_type
            tags["success"] = str(success)

            # Record the event
            self._metrics_collector.record_request(
                resource_kind="websocket",
                success=success,
                duration=duration,
                cache_hit=False,  # WebSocket doesn't use cache
                tags=tags
            )

            # Record specific metrics based on event type
            if event_type == "connection":
                self._metrics_collector.record_counter(
                    "websocket.connections.total", 1.0, tags
                )
                if success:
                    self._metrics_collector.record_timer(
                        "websocket.connection.duration", duration, tags
                    )
            elif event_type == "message_sent":
                self._metrics_collector.record_counter(
                    "websocket.messages.sent", 1.0, tags
                )
            elif event_type == "message_received":
                self._metrics_collector.record_counter(
                    "websocket.messages.received", 1.0, tags
                )
            elif event_type == "ping":
                self._metrics_collector.record_counter(
                    "websocket.pings.sent", 1.0, tags
                )
                if duration > 0:
                    self._metrics_collector.record_timer(
                        "websocket.ping.latency", duration, tags
                    )
            elif event_type == "error":
                self._metrics_collector.record_counter(
                    "websocket.errors.total", 1.0, tags
                )
            elif event_type == "reconnection":
                self._metrics_collector.record_counter(
                    "websocket.reconnections.total", 1.0, tags
                )

        except Exception as e:
            logger.debug(f"Failed to record metrics: {e}")

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary for this WebSocket client."""
        if not self._metrics_collector:
            return {"metrics_available": False}

        try:
            return {
                "metrics_available": True,
                "metrics_summary": self._metrics_collector.get_summary(),
                "client_tags": self._metrics_tags,
            }
        except Exception as e:
            logger.debug(f"Failed to get metrics summary: {e}")
            return {"metrics_available": False, "error": str(e)}

    async def connect(self) -> WebSocketResult:
        """
        Connect to WebSocket server.

        Returns:
            WebSocketResult with connection status

        Raises:
            WebSocketError: If connection fails
        """
        if self._connection_state in [
            WebSocketConnectionState.CONNECTED,
            WebSocketConnectionState.CONNECTING,
        ]:
            return WebSocketResult(
                success=True, connection_state=self._connection_state
            )

        try:
            self._connection_state = WebSocketConnectionState.CONNECTING
            start_time = time.time()

            # Create session if needed (optimized for reuse)
            if not self._session:
                self._session = await self._create_optimized_session()
                self._session_reused = False
            else:
                self._session_reused = True
                logger.debug("Reusing existing aiohttp session")

            # Connect to WebSocket
            # Set compression to 15 (default) if enabled, None if disabled
            compression = 15 if self.config.enable_compression else None
            self._websocket = await self._session.ws_connect(
                str(self.config.url),
                protocols=self.config.subprotocols,
                headers=self.config.headers,
                compress=compression or 0,
                max_msg_size=self.config.max_message_size,
                timeout=aiohttp.ClientWSTimeout(ws_close=self.config.close_timeout),
                heartbeat=(
                    self.config.ping_interval if self.config.enable_ping else None
                ),
            )

            self._connection_state = WebSocketConnectionState.CONNECTED
            self._connect_time = time.time() - start_time
            self._reconnect_attempts = 0

            # Record connection metrics and profiling
            self._record_metrics("connection", success=True, duration=self._connect_time)
            if self._enable_profiling:
                self._profiler.record_operation("connection", self._connect_time, success=True)

            # Track memory usage after connection
            self._track_memory_usage()

            # Start background tasks
            await self._start_tasks()

            # Call connect handlers (both weak and direct)
            self._callback_manager.call_callbacks('connect')
            if self.on_connect:
                try:
                    self.on_connect()
                except Exception as e:
                    logger.warning(f"Error in direct connect handler: {e}")

            logger.info(f"Connected to WebSocket: {self.config.url}")

            return WebSocketResult(
                success=True,
                connection_state=self._connection_state,
                connection_time=self._connect_time,
            )

        except Exception as e:
            self._connection_state = WebSocketConnectionState.DISCONNECTED
            error_msg = f"Failed to connect to WebSocket: {str(e)}"
            logger.error(error_msg)

            # Record connection error metrics
            self._record_metrics("connection", success=False, additional_tags={"error": str(e)[:100]})

            # Call error handlers (both weak and direct)
            self._callback_manager.call_callbacks('error', e)
            if self.on_error:
                try:
                    self.on_error(e)
                except Exception as handler_error:
                    logger.warning(f"Error in direct error handler: {handler_error}")

            # Try to reconnect if enabled
            if (
                self.config.auto_reconnect
                and self._reconnect_attempts < self.config.max_reconnect_attempts
            ):
                await self._schedule_reconnect()

            return WebSocketResult(
                success=False,
                connection_state=self._connection_state,
                error=error_msg
            )

    async def disconnect(self) -> WebSocketResult:
        """
        Disconnect from WebSocket server.

        Returns:
            WebSocketResult with disconnection status
        """
        if self._connection_state == WebSocketConnectionState.DISCONNECTED:
            return WebSocketResult(
                success=True, connection_state=self._connection_state
            )

        try:
            self._connection_state = WebSocketConnectionState.CLOSING

            # Stop background tasks
            await self._stop_tasks()

            # Close WebSocket connection
            if self._websocket and not self._websocket.closed:
                await self._websocket.close()

            # Close session only if it's not external
            if self._session and not self._session.closed and not self._external_session:
                await self._session.close()
                self._session = None
            elif self._external_session:
                # Keep external session alive but clear our reference
                logger.debug("Keeping external session alive")
                # Don't set session to None for external sessions

            self._connection_state = WebSocketConnectionState.DISCONNECTED
            self._websocket = None

            # Call disconnect handlers (both weak and direct)
            self._callback_manager.call_callbacks('disconnect')
            if self.on_disconnect:
                try:
                    self.on_disconnect()
                except Exception as e:
                    logger.warning(f"Error in direct disconnect handler: {e}")

            logger.info("Disconnected from WebSocket")

            return WebSocketResult(
                success=True,
                connection_state=self._connection_state,
                total_messages_sent=self._messages_sent,
                total_messages_received=self._messages_received,
                total_bytes_sent=self._bytes_sent,
                total_bytes_received=self._bytes_received,
            )

        except Exception as e:
            error_msg = f"Error during disconnect: {str(e)}"
            logger.error(error_msg)
            return WebSocketResult(
                success=False,
                connection_state=WebSocketConnectionState.ERROR,
                error=error_msg,
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

        message = create_message(WebSocketMessageType.TEXT, text)
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

        message = create_message(WebSocketMessageType.BINARY, data)
        await self._send_queue.put(message)

    async def send_message(self, message: WebSocketMessage) -> WebSocketResult:
        """
        Send a WebSocket message.

        Args:
            message: WebSocketMessage to send

        Returns:
            WebSocketResult with send status

        Raises:
            WebSocketError: If not connected or send fails
        """
        if not self.is_connected:
            return WebSocketResult(
                success=False,
                connection_state=self._connection_state,
                error="WebSocket is not connected"
            )

        try:
            # Send the message directly to the websocket
            if self._websocket:
                serialized = message.serialize()
                if message.type == WebSocketMessageType.BINARY:
                    if isinstance(serialized, bytes):
                        await self._websocket.send_bytes(serialized)
                    else:
                        await self._websocket.send_bytes(str(serialized).encode())
                else:
                    await self._websocket.send_str(str(serialized))

                self._messages_sent += 1
                self._bytes_sent += message.size

                # Record message sent metrics
                self._record_metrics("message_sent", success=True,
                                   additional_tags={"message_type": message.type.value,
                                                  "message_size": str(message.size)})

                return WebSocketResult(
                    success=True,
                    connection_state=self._connection_state
                )
            else:
                return WebSocketResult(
                    success=False,
                    connection_state=self._connection_state,
                    error="WebSocket connection not available"
                )
        except Exception as e:
            error_msg = f"Failed to send message: {str(e)}"
            logger.error(error_msg)
            return WebSocketResult(
                success=False,
                connection_state=self._connection_state,
                error=error_msg
            )

    async def receive_message(
        self, timeout: Optional[float] = None
    ) -> Optional[WebSocketMessage]:
        """
        Receive a single message.

        Args:
            timeout: Timeout in seconds (None for no timeout)

        Returns:
            WebSocketMessage or None if timeout
        """
        try:
            if timeout:
                message = await asyncio.wait_for(
                    self._message_queue.get(), timeout=timeout
                )
                return message if isinstance(message, WebSocketMessage) else None
            else:
                message = await self._message_queue.get()
                return message if isinstance(message, WebSocketMessage) else None
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
        """Start optimized background tasks for message handling."""
        # Create tasks with proper naming for debugging
        self._receive_task = asyncio.create_task(
            self._receive_loop(),
            name=f"websocket-receive-{id(self)}"
        )
        self._send_task = asyncio.create_task(
            self._send_loop(),
            name=f"websocket-send-{id(self)}"
        )

        if self.config.enable_ping:
            self._ping_task = asyncio.create_task(
                self._ping_loop(),
                name=f"websocket-ping-{id(self)}"
            )

        # Add task completion callbacks for monitoring
        self._receive_task.add_done_callback(self._on_task_done)
        self._send_task.add_done_callback(self._on_task_done)
        if self._ping_task:
            self._ping_task.add_done_callback(self._on_task_done)

    async def _stop_tasks(self) -> None:
        """Stop background tasks."""
        tasks = [
            self._receive_task,
            self._send_task,
            self._ping_task,
            self._reconnect_task,
        ]

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

    def _on_task_done(self, task: asyncio.Task[Any]) -> None:
        """Handle task completion for monitoring and cleanup."""
        try:
            if task.cancelled():
                logger.debug(f"Task {task.get_name()} was cancelled")
            elif task.exception():
                logger.error(f"Task {task.get_name()} failed: {task.exception()}")
                # Record task failure in profiler
                if self._enable_profiling:
                    self._profiler.record_operation(f"task_{task.get_name()}", 0, success=False)
            else:
                logger.debug(f"Task {task.get_name()} completed successfully")
        except Exception as e:
            logger.debug(f"Error in task completion callback: {e}")

    async def _receive_loop(self) -> None:
        """Background task for receiving messages."""
        if not self._websocket:
            return

        try:
            async for msg in self._websocket:
                if msg.type == WSMsgType.TEXT:
                    message = create_message(WebSocketMessageType.TEXT, msg.data)
                    self._messages_received += 1
                    self._bytes_received += message.size

                    # Record message received metrics
                    self._record_metrics("message_received", success=True,
                                       additional_tags={"message_type": "text",
                                                      "message_size": str(message.size)})

                elif msg.type == WSMsgType.BINARY:
                    message = create_message(WebSocketMessageType.BINARY, msg.data)
                    self._messages_received += 1
                    self._bytes_received += message.size

                    # Record message received metrics
                    self._record_metrics("message_received", success=True,
                                       additional_tags={"message_type": "binary",
                                                      "message_size": str(message.size)})

                elif msg.type == WSMsgType.PONG:
                    message = create_message(WebSocketMessageType.PONG, msg.data)
                    # Update pong timing for health monitoring
                    self._last_pong_time = time.time()
                    self._ping_failures = max(0, self._ping_failures - 1)  # Reduce failure count on successful pong

                    # Record ping latency metrics
                    if self._last_ping_time:
                        latency = self._last_pong_time - self._last_ping_time
                        self._record_metrics("ping", success=True, duration=latency)

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

                    # Call message handlers (both weak and direct)
                    self._callback_manager.call_callbacks('message', message)
                    if self.on_message:
                        try:
                            self.on_message(message)
                        except Exception as e:
                            logger.warning(f"Error in direct message handler: {e}")

                    # Periodic memory tracking and GC
                    self._maybe_run_gc()

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
                    message = await asyncio.wait_for(
                        self._send_queue.get(), timeout=1.0
                    )

                    if message.type == WebSocketMessageType.TEXT:
                        if isinstance(message.data, str):
                            await self._websocket.send_str(message.data)
                    elif message.type == WebSocketMessageType.BINARY:
                        if isinstance(message.data, bytes):
                            await self._websocket.send_bytes(message.data)
                        else:
                            await self._websocket.send_bytes(str(message.data).encode())

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
        """Background task for sending ping messages with health monitoring."""
        try:
            while self.is_connected:
                await asyncio.sleep(self.config.ping_interval)
                if self.is_connected and self._websocket:
                    try:
                        self._last_ping_time = time.time()
                        await self._websocket.ping()

                        # Wait for pong response with timeout
                        pong_timeout = min(self.config.ping_timeout, self.config.ping_interval * 0.8)
                        await asyncio.sleep(pong_timeout)

                        # Check if we received a pong
                        if (self._last_pong_time is None or
                            self._last_pong_time < self._last_ping_time):
                            self._ping_failures += 1
                            logger.warning(f"Ping timeout (failure {self._ping_failures}/{self._max_ping_failures})")

                            # Trigger reconnection if too many failures
                            if self._ping_failures >= self._max_ping_failures:
                                logger.error("Too many ping failures, triggering reconnection")
                                if self.config.auto_reconnect:
                                    await self._schedule_reconnect()
                                break

                    except Exception as e:
                        self._ping_failures += 1
                        logger.error(f"Error sending ping (failure {self._ping_failures}): {e}")
                        if self._ping_failures >= self._max_ping_failures:
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

        while (
            self._reconnect_attempts < self.config.max_reconnect_attempts
            and self._connection_state != WebSocketConnectionState.CONNECTED
        ):

            self._reconnect_attempts += 1
            self._connection_state = WebSocketConnectionState.RECONNECTING

            logger.info(
                f"Reconnection attempt {self._reconnect_attempts}/{self.config.max_reconnect_attempts}"
            )

            await asyncio.sleep(delay)

            try:
                await self.connect()
                return  # Successfully reconnected
            except Exception as e:
                logger.warning(
                    f"Reconnection attempt {self._reconnect_attempts} failed: {e}"
                )

                # Increase delay with backoff
                delay = min(
                    delay * self.config.reconnect_backoff,
                    self.config.max_reconnect_delay,
                )

        # All reconnection attempts failed
        self._connection_state = WebSocketConnectionState.ERROR
        logger.error("All reconnection attempts failed")
