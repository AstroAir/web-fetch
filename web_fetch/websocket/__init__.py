"""
WebSocket support for web_fetch.

This module provides WebSocket client capabilities for real-time communication
and streaming data with comprehensive connection management and message handling.
"""

from .client import WebSocketClient, WebSocketConfig
from .manager import WebSocketManager
from .models import (
    WebSocketConnectionState,
    WebSocketError,
    WebSocketMessage,
    WebSocketMessageType,
    WebSocketResult,
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
]
