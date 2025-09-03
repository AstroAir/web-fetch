"""
WebSocket support for web_fetch.

This module provides WebSocket client capabilities for real-time communication
and streaming data with comprehensive connection management and message handling.
"""

from .client import WebSocketClient
from .manager import WebSocketManager
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
    get_global_profiler,
    AdaptiveQueue,
    WebSocketProfiler,
)

__all__ = [
    # Client
    "WebSocketClient",
    "WebSocketConfig",
    # Models
    "WebSocketMessage",
    "WebSocketMessageType",
    "WebSocketConnectionState",
    "WebSocketResult",
    "WebSocketError",
    # Manager
    "WebSocketManager",
    # Optimization features
    "create_message",
    "get_message_pool_statistics",
    "get_global_profiler",
    "AdaptiveQueue",
    "WebSocketProfiler",
]
