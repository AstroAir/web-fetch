"""
WebSocket optimization components.

This module contains performance optimization classes including object pooling,
adaptive queues, and profiling capabilities for WebSocket operations.
"""

from __future__ import annotations

import asyncio
import time
import uuid
import weakref
from collections import deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, List, Optional, Union, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .core_models import WebSocketMessage, WebSocketMessageType

import logging

logger = logging.getLogger(__name__)


class WebSocketMessagePool:
    """
    Object pool for WebSocketMessage instances to reduce garbage collection overhead.

    This pool maintains a collection of reusable WebSocketMessage instances,
    significantly reducing memory allocation and garbage collection pressure
    in high-throughput scenarios.
    """

    def __init__(self, max_pool_size: int = 1000):
        """
        Initialize the message pool.

        Args:
            max_pool_size: Maximum number of messages to keep in the pool
        """
        self.max_pool_size = max_pool_size
        self._pool: deque[WebSocketMessage] = deque()
        self._lock = Lock()
        self._created_count = 0
        self._reused_count = 0

    def get_message(self, msg_type: WebSocketMessageType, data: Union[str, bytes, None] = None) -> 'WebSocketMessage':
        """
        Get a WebSocketMessage instance from the pool or create a new one.

        Args:
            msg_type: Type of the WebSocket message
            data: Message data

        Returns:
            WebSocketMessage instance
        """
        with self._lock:
            if self._pool:
                message = self._pool.popleft()
                message._reset(msg_type, data)
                self._reused_count += 1
                return message
            else:
                # Import here to avoid circular imports
                from .core_models import WebSocketMessage
                self._created_count += 1
                return WebSocketMessage(type=msg_type, data=data, _pool=self)

    def return_message(self, message: 'WebSocketMessage') -> None:
        """
        Return a WebSocketMessage instance to the pool for reuse.

        Args:
            message: WebSocketMessage to return to pool
        """
        with self._lock:
            if len(self._pool) < self.max_pool_size:
                message._clear()
                self._pool.append(message)

    @property
    def statistics(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self._lock:
            total_requests = self._created_count + self._reused_count
            reuse_rate = (self._reused_count / total_requests * 100) if total_requests > 0 else 0

            return {
                "pool_size": len(self._pool),
                "max_pool_size": self.max_pool_size,
                "created_count": self._created_count,
                "reused_count": self._reused_count,
                "reuse_rate_percent": round(reuse_rate, 2),
                "total_requests": total_requests
            }


# Global message pool instance
_global_message_pool = WebSocketMessagePool()


class AdaptiveQueue:
    """
    Adaptive queue that adjusts its size based on usage patterns.

    This queue monitors usage patterns and automatically adjusts its maximum
    size to optimize memory usage while maintaining performance.
    """

    def __init__(self, initial_maxsize: int = 100, min_size: int = 10,
                 max_size: int = 1000, growth_factor: float = 1.5,
                 shrink_threshold: float = 0.3):
        """
        Initialize adaptive queue.

        Args:
            initial_maxsize: Initial maximum queue size
            min_size: Minimum allowed queue size
            max_size: Maximum allowed queue size
            growth_factor: Factor by which to grow when queue is full
            shrink_threshold: Usage threshold below which to shrink
        """
        self._queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=initial_maxsize)
        self._min_size = min_size
        self._max_size = max_size
        self._growth_factor = growth_factor
        self._shrink_threshold = shrink_threshold

        # Statistics for adaptive behavior
        self._put_count = 0
        self._get_count = 0
        self._full_count = 0
        self._last_resize_time = time.time()
        self._resize_interval = 30.0  # Resize evaluation interval in seconds

    async def put(self, item: Any) -> None:
        """Put an item into the queue."""
        try:
            self._queue.put_nowait(item)
            self._put_count += 1
        except asyncio.QueueFull:
            self._full_count += 1
            await self._maybe_grow()
            await self._queue.put(item)
            self._put_count += 1

    async def get(self) -> Any:
        """Get an item from the queue."""
        item = await self._queue.get()
        self._get_count += 1
        await self._maybe_shrink()
        return item

    def put_nowait(self, item: Any) -> None:
        """Put an item into the queue without waiting."""
        try:
            self._queue.put_nowait(item)
            self._put_count += 1
        except asyncio.QueueFull:
            self._full_count += 1
            raise

    def get_nowait(self) -> Any:
        """Get an item from the queue without waiting."""
        item = self._queue.get_nowait()
        self._get_count += 1
        return item

    def qsize(self) -> int:
        """Return the current queue size."""
        return self._queue.qsize()

    def empty(self) -> bool:
        """Return True if the queue is empty."""
        return self._queue.empty()

    def full(self) -> bool:
        """Return True if the queue is full."""
        return self._queue.full()

    @property
    def maxsize(self) -> int:
        """Return the current maximum queue size."""
        return self._queue.maxsize

    async def _maybe_grow(self) -> None:
        """Grow the queue if conditions are met."""
        current_time = time.time()
        if (current_time - self._last_resize_time) < self._resize_interval:
            return

        current_maxsize = self._queue.maxsize
        if current_maxsize >= self._max_size:
            return

        # Calculate new size
        new_size = min(int(current_maxsize * self._growth_factor), self._max_size)
        if new_size > current_maxsize:
            await self._resize_queue(new_size)
            logger.debug(f"Adaptive queue grown from {current_maxsize} to {new_size}")

    async def _maybe_shrink(self) -> None:
        """Shrink the queue if usage is consistently low."""
        current_time = time.time()
        if (current_time - self._last_resize_time) < self._resize_interval:
            return

        current_maxsize = self._queue.maxsize
        if current_maxsize <= self._min_size:
            return

        # Calculate usage ratio
        total_operations = self._put_count + self._get_count
        if total_operations == 0:
            return

        avg_queue_size = self._put_count / total_operations if total_operations > 0 else 0
        usage_ratio = avg_queue_size / current_maxsize

        if usage_ratio < self._shrink_threshold:
            new_size = max(int(current_maxsize / self._growth_factor), self._min_size)
            if new_size < current_maxsize:
                await self._resize_queue(new_size)
                logger.debug(f"Adaptive queue shrunk from {current_maxsize} to {new_size}")

    async def _resize_queue(self, new_maxsize: int) -> None:
        """Resize the queue to a new maximum size."""
        # Create new queue with new size
        old_queue = self._queue
        self._queue = asyncio.Queue(maxsize=new_maxsize)

        # Transfer existing items
        while not old_queue.empty():
            try:
                item = old_queue.get_nowait()
                self._queue.put_nowait(item)
            except (asyncio.QueueEmpty, asyncio.QueueFull):
                break

        self._last_resize_time = time.time()

        # Reset statistics
        self._put_count = 0
        self._get_count = 0
        self._full_count = 0

    @property
    def statistics(self) -> Dict[str, Any]:
        """Get queue statistics."""
        total_ops = self._put_count + self._get_count
        return {
            "current_size": self.qsize(),
            "max_size": self.maxsize,
            "min_size": self._min_size,
            "max_allowed_size": self._max_size,
            "put_count": self._put_count,
            "get_count": self._get_count,
            "full_count": self._full_count,
            "total_operations": total_ops,
            "usage_efficiency": (self._get_count / total_ops * 100) if total_ops > 0 else 0,
            "full_rate": (self._full_count / self._put_count * 100) if self._put_count > 0 else 0
        }


class WebSocketProfiler:
    """
    Performance profiler for WebSocket operations.

    This class provides detailed performance profiling capabilities for
    WebSocket connections, including operation timing, throughput analysis,
    and performance bottleneck identification.
    """

    def __init__(self, max_samples: int = 1000):
        """
        Initialize the profiler.

        Args:
            max_samples: Maximum number of samples to keep for each metric
        """
        self.max_samples = max_samples
        self._operation_times: Dict[str, List[float]] = {}
        self._throughput_samples: List[Tuple[float, int, int]] = []  # (timestamp, messages, bytes)
        self._error_counts: Dict[str, int] = {}
        self._start_time = time.time()
        self._lock = Lock()

    def record_operation(self, operation: str, duration: float, success: bool = True) -> None:
        """
        Record an operation timing.

        Args:
            operation: Name of the operation
            duration: Duration in seconds
            success: Whether the operation was successful
        """
        with self._lock:
            if operation not in self._operation_times:
                self._operation_times[operation] = []

            self._operation_times[operation].append(duration)

            # Keep only the most recent samples
            if len(self._operation_times[operation]) > self.max_samples:
                self._operation_times[operation].pop(0)

            # Track errors
            if not success:
                self._error_counts[operation] = self._error_counts.get(operation, 0) + 1

    def record_throughput(self, messages_count: int, bytes_count: int) -> None:
        """
        Record throughput sample.

        Args:
            messages_count: Number of messages processed
            bytes_count: Number of bytes processed
        """
        with self._lock:
            current_time = time.time()
            self._throughput_samples.append((current_time, messages_count, bytes_count))

            # Keep only recent samples (last 5 minutes)
            cutoff_time = current_time - 300
            self._throughput_samples = [
                sample for sample in self._throughput_samples
                if sample[0] > cutoff_time
            ]

    def get_operation_stats(self, operation: str) -> Dict[str, Any]:
        """
        Get statistics for a specific operation.

        Args:
            operation: Name of the operation

        Returns:
            Dictionary containing operation statistics
        """
        with self._lock:
            if operation not in self._operation_times:
                return {"error": f"No data for operation '{operation}'"}

            times = self._operation_times[operation]
            if not times:
                return {"error": f"No timing data for operation '{operation}'"}

            return {
                "operation": operation,
                "sample_count": len(times),
                "min_time": min(times),
                "max_time": max(times),
                "avg_time": sum(times) / len(times),
                "median_time": sorted(times)[len(times) // 2],
                "p95_time": sorted(times)[int(len(times) * 0.95)] if len(times) > 20 else max(times),
                "p99_time": sorted(times)[int(len(times) * 0.99)] if len(times) > 100 else max(times),
                "error_count": self._error_counts.get(operation, 0),
                "success_rate": (len(times) - self._error_counts.get(operation, 0)) / len(times) * 100,
            }

    def get_throughput_stats(self) -> Dict[str, Any]:
        """Get throughput statistics."""
        with self._lock:
            if len(self._throughput_samples) < 2:
                return {"error": "Insufficient throughput data"}

            # Calculate rates
            total_messages = sum(sample[1] for sample in self._throughput_samples)
            total_bytes = sum(sample[2] for sample in self._throughput_samples)
            time_span = self._throughput_samples[-1][0] - self._throughput_samples[0][0]

            if time_span <= 0:
                return {"error": "Invalid time span for throughput calculation"}

            return {
                "messages_per_second": total_messages / time_span,
                "bytes_per_second": total_bytes / time_span,
                "total_messages": total_messages,
                "total_bytes": total_bytes,
                "time_span_seconds": time_span,
                "sample_count": len(self._throughput_samples),
            }

    def get_comprehensive_report(self) -> Dict[str, Any]:
        """Get a comprehensive performance report."""
        with self._lock:
            report = {
                "profiler_uptime": time.time() - self._start_time,
                "operations": {},
                "throughput": self.get_throughput_stats(),
                "summary": {
                    "total_operations": len(self._operation_times),
                    "total_errors": sum(self._error_counts.values()),
                    "max_samples": self.max_samples,
                }
            }

            # Add stats for each operation
            operations_dict = report["operations"]
            if isinstance(operations_dict, dict):
                for operation in self._operation_times:
                    operations_dict[operation] = self.get_operation_stats(operation)

            return report

    def reset(self) -> None:
        """Reset all profiling data."""
        with self._lock:
            self._operation_times.clear()
            self._throughput_samples.clear()
            self._error_counts.clear()
            self._start_time = time.time()


# Global profiler instance
_global_profiler = WebSocketProfiler()


def create_message(msg_type: 'WebSocketMessageType', data: Union[str, bytes, None] = None) -> 'WebSocketMessage':
    """
    Factory function to create WebSocketMessage instances using the global pool.

    Args:
        msg_type: Type of the WebSocket message
        data: Message data

    Returns:
        WebSocketMessage instance from the pool
    """
    return _global_message_pool.get_message(msg_type, data)


def get_message_pool_statistics() -> Dict[str, Any]:
    """
    Get statistics for the global message pool.

    Returns:
        Dictionary containing pool statistics
    """
    return _global_message_pool.statistics


def get_global_profiler() -> WebSocketProfiler:
    """
    Get the global WebSocket profiler instance.

    Returns:
        Global WebSocketProfiler instance
    """
    return _global_profiler
