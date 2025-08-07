"""
Request deduplication utilities for the web_fetch library.

This module provides functionality to deduplicate identical concurrent requests,
reducing load on target servers and improving performance.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Optional


@dataclass
class RequestKey:
    """Unique key for identifying requests."""

    url: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    data: Optional[Any] = (
        None  # Accept str | bytes | Dict[str, Any]; kept broad for flexibility
    )
    params: Optional[Dict[str, str]] = None

    def __post_init__(self) -> None:
        """Normalize the request key for consistent hashing."""
        # Normalize method to uppercase
        self.method = self.method.upper()

        # Sort headers and params for consistent ordering
        if self.headers:
            self.headers = dict(sorted(self.headers.items()))
        if self.params:
            self.params = dict(sorted(self.params.items()))

    def to_hash(self) -> str:
        """Generate a hash string for this request key."""
        # Create a deterministic string representation
        components = [
            self.url,
            self.method,
            json.dumps(self.headers or {}, sort_keys=True),
            json.dumps(self.params or {}, sort_keys=True),
        ]

        # Handle data component
        if self.data is not None:
            if isinstance(self.data, dict):
                components.append(json.dumps(self.data, sort_keys=True))
            elif isinstance(self.data, bytes):
                components.append(self.data.hex())
            else:
                components.append(str(self.data))
        else:
            components.append("")

        # Generate hash
        content = "|".join(components)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass
class PendingRequest:
    """Represents a pending request with its future and metadata."""

    future: asyncio.Future[Any]
    created_at: float = field(default_factory=time.time)
    request_count: int = 1

    def add_waiter(self) -> None:
        """Increment the count of requests waiting for this result."""
        self.request_count += 1

    @property
    def age_seconds(self) -> float:
        """Get the age of this pending request in seconds."""
        return time.time() - self.created_at


class RequestDeduplicator:
    """
    Deduplicates identical concurrent requests to reduce server load.

    When multiple identical requests are made concurrently, only one actual
    request is sent to the server, and all callers receive the same result.
    """

    def __init__(self, max_age_seconds: float = 300.0) -> None:
        """
        Initialize the request deduplicator.

        Args:
            max_age_seconds: Maximum age for pending requests before cleanup
        """
        self.max_age_seconds = max_age_seconds
        self._pending: Dict[str, PendingRequest] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task[Any]] = None
        self._initialized = False

    def _start_cleanup_task(self) -> None:
        """Start the background cleanup task."""
        try:
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._cleanup_expired())
        except RuntimeError:
            # No event loop running, will start later when needed
            pass

    async def _cleanup_expired(self) -> None:
        """Background task to clean up expired pending requests."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                async with self._lock:
                    current_time = time.time()
                    expired_keys = [
                        key
                        for key, pending in self._pending.items()
                        if current_time - pending.created_at > self.max_age_seconds
                    ]

                    for key in expired_keys:
                        if key in self._pending:
                            pending = self._pending.pop(key)
                            if not pending.future.done():
                                pending.future.cancel()

            except asyncio.CancelledError:
                break
            except Exception:
                # Continue cleanup on errors
                continue

    async def deduplicate(
        self,
        request_key: RequestKey,
        executor_func: Callable[..., Awaitable[Any]] | Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Execute a request with deduplication.

        If an identical request is already in progress, wait for its result.
        Otherwise, execute the request and share the result with any concurrent
        identical requests.

        Args:
            request_key: Unique identifier for the request
            executor_func: Function to execute the actual request
            *args: Positional arguments for executor_func
            **kwargs: Keyword arguments for executor_func

        Returns:
            Result of the request execution
        """
        # Ensure cleanup task is started
        if not self._initialized:
            self._start_cleanup_task()
            self._initialized = True

        key_hash = request_key.to_hash()

        async with self._lock:
            # Check if identical request is already pending
            if key_hash in self._pending:
                pending = self._pending[key_hash]
                pending.add_waiter()

                # Wait for the existing request to complete
                try:
                    return await pending.future
                except asyncio.CancelledError:
                    # If the original request was cancelled, we need to retry
                    pass

            # Create new pending request
            future: asyncio.Future[Any] = asyncio.Future()
            self._pending[key_hash] = PendingRequest(future)

        # Execute the request
        try:
            if asyncio.iscoroutinefunction(executor_func):
                result = await executor_func(*args, **kwargs)
            else:
                # If executor_func is sync but returns a coroutine, await it
                res = executor_func(*args, **kwargs)
                if asyncio.iscoroutine(res):
                    result = await res
                else:
                    result = res

            # Set result for all waiters
            async with self._lock:
                if key_hash in self._pending:
                    pending = self._pending.pop(key_hash)
                    if not pending.future.done():
                        pending.future.set_result(result)

            return result

        except Exception as e:
            # Set exception for all waiters
            async with self._lock:
                if key_hash in self._pending:
                    pending = self._pending.pop(key_hash)
                    if not pending.future.done():
                        pending.future.set_exception(e)

            raise

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about current deduplication state."""
        return {
            "pending_requests": len(self._pending),
            "pending_details": [
                {
                    "key_hash": key[:16] + "...",  # Truncated hash for readability
                    "age_seconds": pending.age_seconds,
                    "request_count": pending.request_count,
                    "is_done": pending.future.done(),
                }
                for key, pending in self._pending.items()
            ],
        }

    async def clear(self) -> None:
        """Clear all pending requests and cancel cleanup task."""
        async with self._lock:
            # Cancel all pending futures
            for pending in self._pending.values():
                if not pending.future.done():
                    pending.future.cancel()

            self._pending.clear()

        # Cancel cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass


# Global deduplicator instance (lazy initialization)
_global_deduplicator: Optional[RequestDeduplicator] = None


def _get_global_deduplicator() -> RequestDeduplicator:
    """Get or create the global deduplicator instance."""
    global _global_deduplicator
    if _global_deduplicator is None:
        _global_deduplicator = RequestDeduplicator()
    return _global_deduplicator


async def deduplicate_request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Any] = None,
    params: Optional[Dict[str, str]] = None,
    executor_func: Callable[..., Awaitable[Any]] | Callable[..., Any] | None = None,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    Convenience function to deduplicate a request.

    Args:
        url: Request URL
        method: HTTP method
        headers: Request headers
        data: Request data
        params: Query parameters
        executor_func: Function to execute the actual request
        *args: Positional arguments for executor_func
        **kwargs: Keyword arguments for executor_func

    Returns:
        Result of the request execution
    """
    if executor_func is None:
        raise ValueError("executor_func must be provided")

    request_key = RequestKey(
        url=url, method=method, headers=headers, data=data, params=params
    )

    deduplicator = _get_global_deduplicator()
    return await deduplicator.deduplicate(request_key, executor_func, *args, **kwargs)


def get_deduplication_stats() -> Dict[str, Any]:
    """Get global deduplication statistics."""
    deduplicator = _get_global_deduplicator()
    return deduplicator.get_stats()


__all__ = [
    "RequestKey",
    "RequestDeduplicator",
    "PendingRequest",
    "deduplicate_request",
    "get_deduplication_stats",
]
