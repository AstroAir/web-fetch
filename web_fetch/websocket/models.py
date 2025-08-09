"""
WebSocket models and data structures.

This module defines the data models and enums used for WebSocket communication.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, ConfigDict, HttpUrl

from ..exceptions import WebFetchError


class WebSocketError(WebFetchError):
    """WebSocket-specific error."""

    pass


class WebSocketMessageType(str, Enum):
    """WebSocket message types."""

    TEXT = "text"
    BINARY = "binary"
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
    """WebSocket message data."""

    type: WebSocketMessageType
    data: Union[str, bytes, None] = None
    timestamp: float = field(default_factory=time.time)
    size: int = 0

    def __post_init__(self) -> None:
        """Calculate message size after initialization."""
        if self.data is not None:
            if isinstance(self.data, str):
                self.size = len(self.data.encode("utf-8"))
            elif isinstance(self.data, bytes):
                self.size = len(self.data)


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
    url: HttpUrl = Field(description="WebSocket URL (ws:// or wss://)")
    subprotocols: List[str] = Field(
        default_factory=list, description="WebSocket subprotocols"
    )
    headers: Dict[str, str] = Field(
        default_factory=dict, description="Additional headers for handshake"
    )

    # Timeout settings
    connect_timeout: float = Field(
        default=30.0, ge=1.0, description="Connection timeout in seconds"
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
    enable_ping: bool = Field(default=True, description="Enable automatic ping/pong")

    # SSL settings
    verify_ssl: bool = Field(
        default=True, description="Verify SSL certificates for wss:// connections"
    )

    # Compression
    enable_compression: bool = Field(
        default=True, description="Enable per-message deflate compression"
    )

    model_config = ConfigDict(use_enum_values=True)
