"""
WebSocket-specific exceptions.

This module defines exception classes specific to WebSocket operations.
"""

from __future__ import annotations

from ..exceptions import WebFetchError


class WebSocketError(WebFetchError):
    """WebSocket-specific error."""

    pass
