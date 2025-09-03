"""
WebSocket callback management.

This module provides callback management functionality for WebSocket events
using weak references to prevent memory leaks.
"""

from __future__ import annotations

import logging
import weakref
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class WeakCallbackManager:
    """
    Manager for weak reference callbacks to prevent memory leaks.

    This class manages event handlers using weak references, automatically
    cleaning up dead references and preventing memory leaks from circular
    references between the client and handler objects.
    """

    def __init__(self) -> None:
        self._callbacks: Dict[str, List[weakref.ReferenceType[Any]]] = {
            'message': [],
            'connect': [],
            'disconnect': [],
            'error': []
        }

    def add_callback(self, event_type: str, callback: Callable[..., Any]) -> None:
        """Add a callback with weak reference."""
        if event_type not in self._callbacks:
            return

        # Create weak reference with cleanup callback
        def cleanup_ref(ref: weakref.ReferenceType[Any]) -> None:
            try:
                self._callbacks[event_type].remove(ref)
            except ValueError:
                pass

        weak_ref = weakref.ref(callback, cleanup_ref)
        self._callbacks[event_type].append(weak_ref)

    def remove_callback(self, event_type: str, callback: Callable[..., Any]) -> None:
        """Remove a specific callback."""
        if event_type not in self._callbacks:
            return

        # Find and remove the weak reference
        to_remove = []
        for weak_ref in self._callbacks[event_type]:
            if weak_ref() is callback:
                to_remove.append(weak_ref)

        for ref in to_remove:
            self._callbacks[event_type].remove(ref)

    def call_callbacks(self, event_type: str, *args: Any, **kwargs: Any) -> None:
        """Call all callbacks for an event type."""
        if event_type not in self._callbacks:
            return

        # Clean up dead references and call live ones
        dead_refs = []
        for weak_ref in self._callbacks[event_type]:
            callback = weak_ref()
            if callback is None:
                dead_refs.append(weak_ref)
            else:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Error in {event_type} callback: {e}")

        # Remove dead references
        for ref in dead_refs:
            try:
                self._callbacks[event_type].remove(ref)
            except ValueError:
                pass

    def clear_callbacks(self, event_type: Optional[str] = None) -> None:
        """Clear callbacks for a specific event type or all events."""
        if event_type:
            self._callbacks[event_type].clear()
        else:
            for callbacks in self._callbacks.values():
                callbacks.clear()

    @property
    def statistics(self) -> Dict[str, Any]:
        """Get callback statistics."""
        stats = {}
        for event_type, callbacks in self._callbacks.items():
            live_count = sum(1 for ref in callbacks if ref() is not None)
            dead_count = len(callbacks) - live_count
            stats[event_type] = {
                "total_callbacks": len(callbacks),
                "live_callbacks": live_count,
                "dead_callbacks": dead_count
            }
        return stats
