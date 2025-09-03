"""
Core WebSocket data models and configuration.

This module contains the fundamental data structures and configuration classes
for WebSocket communication.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, ConfigDict, field_validator


class WebSocketMessageType(str, Enum):
    """WebSocket message types."""

    TEXT = "text"
    BINARY = "binary"
    JSON = "json"
    PING = "ping"
    PONG = "pong"
    CLOSE = "close"


class WebSocketConnectionState(str, Enum):
    """WebSocket connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSING = "closing"
    CLOSED = "closed"
    ERROR = "error"


@dataclass
class WebSocketMessage:
    """WebSocket message data with object pooling support."""

    type: WebSocketMessageType
    data: Union[str, bytes, None] = None
    timestamp: float = field(default_factory=time.time)
    size: int = 0
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    _pool: Optional[Any] = field(default=None, repr=False)  # WebSocketMessagePool type hint causes circular import

    def __post_init__(self) -> None:
        """Calculate message size after initialization."""
        self._calculate_size()

    def _calculate_size(self) -> None:
        """Calculate and set the message size."""
        if self.data is not None:
            if isinstance(self.data, str):
                self.size = len(self.data.encode("utf-8"))
            elif isinstance(self.data, bytes):
                self.size = len(self.data)
        else:
            self.size = 0

    def _reset(self, msg_type: WebSocketMessageType, data: Union[str, bytes, None] = None) -> None:
        """Reset message for reuse from pool."""
        self.type = msg_type
        self.data = data
        self.timestamp = time.time()
        self.id = str(uuid.uuid4())
        self._calculate_size()

    def _clear(self) -> None:
        """Clear message data for pool storage."""
        self.data = None
        self.size = 0
        self.timestamp = 0.0
        self.id = ""

    def __del__(self) -> None:
        """Return message to pool when garbage collected."""
        if self._pool is not None:
            try:
                self._pool.return_message(self)
            except Exception:
                # Ignore errors during cleanup
                pass

    def serialize(self) -> Union[str, bytes]:
        """Serialize the message for transmission."""
        if self.type == WebSocketMessageType.JSON:
            # For JSON messages, serialize just the data as JSON string
            return json.dumps(self.data)
        elif self.type == WebSocketMessageType.TEXT:
            # For text messages, return the data as string
            return str(self.data) if self.data is not None else ""
        elif self.type == WebSocketMessageType.BINARY:
            # For binary messages, return the data as bytes
            if isinstance(self.data, bytes):
                return self.data
            elif isinstance(self.data, str):
                return self.data.encode("utf-8")
            else:
                return b""
        else:
            # For other message types, return as string
            return str(self.data) if self.data is not None else ""


@dataclass
class WebSocketResult:
    """Result of WebSocket operation."""

    success: bool
    connection_state: WebSocketConnectionState
    messages: List[WebSocketMessage] = field(default_factory=list)
    error: Optional[str] = None
    connection_time: Optional[float] = None
    total_messages_sent: int = 0
    total_messages_received: int = 0
    total_bytes_sent: int = 0
    total_bytes_received: int = 0

    @property
    def message_count(self) -> int:
        """Get total number of messages."""
        return len(self.messages)

    @property
    def total_bytes(self) -> int:
        """Get total bytes transferred."""
        return self.total_bytes_sent + self.total_bytes_received


class WebSocketConfig(BaseModel):
    """Configuration for WebSocket connections."""

    # Connection settings
    url: str = Field(description="WebSocket URL (ws:// or wss://)")
    subprotocols: List[str] = Field(
        default_factory=list, description="WebSocket subprotocols"
    )
    headers: Dict[str, str] = Field(
        default_factory=dict, description="Additional headers for handshake"
    )

    # Timeout settings
    connect_timeout: float = Field(
        default=10.0, ge=1.0, description="Connection timeout in seconds"
    )
    ping_timeout: float = Field(
        default=20.0, ge=1.0, description="Ping timeout in seconds"
    )
    close_timeout: float = Field(
        default=10.0, ge=1.0, description="Close timeout in seconds"
    )

    # Message settings
    max_message_size: int = Field(
        default=1024 * 1024, ge=1024, description="Maximum message size in bytes"
    )
    max_queue_size: int = Field(
        default=100, ge=1, description="Maximum message queue size"
    )

    # Reconnection settings
    auto_reconnect: bool = Field(
        default=True, description="Automatically reconnect on connection loss"
    )
    max_reconnect_attempts: int = Field(
        default=5, ge=0, description="Maximum reconnection attempts"
    )
    reconnect_delay: float = Field(
        default=1.0, ge=0.1, description="Initial reconnection delay in seconds"
    )
    reconnect_backoff: float = Field(
        default=2.0, ge=1.0, description="Reconnection delay backoff multiplier"
    )
    max_reconnect_delay: float = Field(
        default=60.0, ge=1.0, description="Maximum reconnection delay"
    )

    # Ping/pong settings
    ping_interval: float = Field(
        default=30.0, ge=1.0, description="Ping interval in seconds"
    )
    heartbeat_interval: float = Field(
        default=30.0, ge=1.0, description="Heartbeat interval in seconds"
    )
    enable_ping: bool = Field(default=True, description="Enable automatic ping/pong")

    # SSL settings
    verify_ssl: bool = Field(
        default=True, description="Verify SSL certificates for wss:// connections"
    )

    # Compression
    enable_compression: bool = Field(
        default=True, description="Enable per-message deflate compression"
    )

    # Adaptive optimization settings
    enable_adaptive_queues: bool = Field(
        default=True, description="Enable adaptive queue sizing based on usage patterns"
    )
    adaptive_queue_min_size: int = Field(
        default=10, ge=1, description="Minimum queue size for adaptive sizing"
    )
    adaptive_queue_max_size: int = Field(
        default=1000, ge=10, description="Maximum queue size for adaptive sizing"
    )
    adaptive_queue_growth_factor: float = Field(
        default=1.5, ge=1.1, le=3.0, description="Growth factor for adaptive queue sizing"
    )
    adaptive_queue_shrink_threshold: float = Field(
        default=0.3, ge=0.1, le=0.8, description="Usage threshold below which queues shrink"
    )

    # Message batching settings
    enable_batching: bool = Field(
        default=False, description="Enable message batching for high-throughput scenarios"
    )
    batch_size: int = Field(
        default=10, ge=1, le=100, description="Maximum number of messages to batch"
    )
    batch_timeout: float = Field(
        default=0.01, ge=0.001, le=1.0, description="Maximum time to wait for batch completion in seconds"
    )

    @field_validator('url')
    @classmethod
    def validate_websocket_url(cls, v: str) -> str:
        """Validate that the URL uses WebSocket scheme."""
        if not isinstance(v, str):
            raise ValueError("URL must be a string")

        if not (v.startswith('ws://') or v.startswith('wss://')):
            raise ValueError("URL must use ws:// or wss:// scheme")

        return v

    model_config = ConfigDict(use_enum_values=True)


def create_message(msg_type: WebSocketMessageType, data: Union[str, bytes, None] = None) -> WebSocketMessage:
    """
    Factory function to create WebSocketMessage instances using the global pool.

    Args:
        msg_type: Type of the WebSocket message
        data: Message data

    Returns:
        WebSocketMessage instance from the pool
    """
    # Import here to avoid circular imports
    from .optimization import _global_message_pool
    return _global_message_pool.get_message(msg_type, data)
