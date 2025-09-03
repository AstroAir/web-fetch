"""
WebSocket models and data structures.

This module provides backward compatibility by re-exporting all WebSocket models
from their new dedicated modules.
"""

from __future__ import annotations

# Re-export all components from their new modules for backward compatibility
from .exceptions import WebSocketError
from .optimization import (
    get_message_pool_statistics,
    get_global_profiler,
    AdaptiveQueue,
    WebSocketProfiler,
)
from .core_models import (
    WebSocketMessageType,
    WebSocketConnectionState,
    WebSocketMessage,
    WebSocketResult,
    WebSocketConfig,
    create_message,
)

# Maintain all exports for backward compatibility
__all__ = [
    "WebSocketError",
    "WebSocketMessageType",
    "WebSocketConnectionState",
    "WebSocketMessage",
    "WebSocketResult",
    "WebSocketConfig",
    "create_message",
    "get_message_pool_statistics",
    "get_global_profiler",
    "AdaptiveQueue",
    "WebSocketProfiler",
]
