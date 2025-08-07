"""
Priority queue implementation for batch operations.

This module provides thread-safe priority queues with various scheduling
algorithms and queue management features.
"""

import asyncio
import heapq
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .models import BatchPriority


@dataclass
class QueueItem:
    """Item in the priority queue."""

    priority: int
    timestamp: float
    sequence: int
    data: Any

    def __lt__(self, other: "QueueItem") -> bool:
        """Compare queue items for priority ordering."""
        # Lower priority value = higher priority
        if self.priority != other.priority:
            return self.priority < other.priority
        # Earlier timestamp = higher priority for same priority level
        if self.timestamp != other.timestamp:
            return self.timestamp < other.timestamp
        # Lower sequence = higher priority for same timestamp
        return self.sequence < other.sequence


class PriorityQueue:
    """Thread-safe priority queue with async support."""

    def __init__(self, maxsize: int = 0):
        """
        Initialize priority queue.

        Args:
            maxsize: Maximum queue size (0 = unlimited)
        """
        self.maxsize = maxsize
        self._queue: List[QueueItem] = []
        self._sequence = 0
        self._lock = threading.RLock()
        self._not_empty = asyncio.Condition()
        self._not_full = asyncio.Condition()

    async def put(
        self,
        item: Any,
        priority: int = 0,
        block: bool = True,
        timeout: Optional[float] = None,
    ) -> None:
        """
        Put an item into the queue.

        Args:
            item: Item to add
            priority: Priority level (lower = higher priority)
            block: Whether to block if queue is full
            timeout: Timeout for blocking operations
        """
        async with self._not_full:
            # Wait for space if queue is full
            if self.maxsize > 0:
                while len(self._queue) >= self.maxsize:
                    if not block:
                        raise asyncio.QueueFull()

                    if timeout is not None:
                        await asyncio.wait_for(self._not_full.wait(), timeout)
                    else:
                        await self._not_full.wait()

            # Add item to queue
            with self._lock:
                self._sequence += 1
                queue_item = QueueItem(
                    priority=priority,
                    timestamp=time.time(),
                    sequence=self._sequence,
                    data=item,
                )
                heapq.heappush(self._queue, queue_item)

            # Notify waiting consumers
            async with self._not_empty:
                self._not_empty.notify()

    async def get(self, block: bool = True, timeout: Optional[float] = None) -> Any:
        """
        Get an item from the queue.

        Args:
            block: Whether to block if queue is empty
            timeout: Timeout for blocking operations

        Returns:
            Queue item
        """
        async with self._not_empty:
            # Wait for item if queue is empty
            while not self._queue:
                if not block:
                    raise asyncio.QueueEmpty()

                if timeout is not None:
                    await asyncio.wait_for(self._not_empty.wait(), timeout)
                else:
                    await self._not_empty.wait()

            # Get item from queue
            with self._lock:
                queue_item = heapq.heappop(self._queue)

            # Notify waiting producers
            async with self._not_full:
                self._not_full.notify()

            return queue_item.data

    def put_nowait(self, item: Any, priority: int = 0) -> None:
        """
        Put an item without blocking.

        Args:
            item: Item to add
            priority: Priority level
        """
        if self.maxsize > 0 and len(self._queue) >= self.maxsize:
            raise asyncio.QueueFull()

        with self._lock:
            self._sequence += 1
            queue_item = QueueItem(
                priority=priority,
                timestamp=time.time(),
                sequence=self._sequence,
                data=item,
            )
            heapq.heappush(self._queue, queue_item)

    def get_nowait(self) -> Any:
        """
        Get an item without blocking.

        Returns:
            Queue item
        """
        if not self._queue:
            raise asyncio.QueueEmpty()

        with self._lock:
            queue_item = heapq.heappop(self._queue)

        return queue_item.data

    def empty(self) -> bool:
        """Check if queue is empty."""
        with self._lock:
            return len(self._queue) == 0

    def full(self) -> bool:
        """Check if queue is full."""
        if self.maxsize <= 0:
            return False

        with self._lock:
            return len(self._queue) >= self.maxsize

    def qsize(self) -> int:
        """Get queue size."""
        with self._lock:
            return len(self._queue)

    def peek(self) -> Optional[Any]:
        """
        Peek at the next item without removing it.

        Returns:
            Next item or None if queue is empty
        """
        with self._lock:
            if self._queue:
                return self._queue[0].data
            return None

    def clear(self) -> None:
        """Clear all items from the queue."""
        with self._lock:
            self._queue.clear()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics.

        Returns:
            Dictionary with queue statistics
        """
        with self._lock:
            if not self._queue:
                return {
                    "size": 0,
                    "max_size": self.maxsize,
                    "is_empty": True,
                    "is_full": False,
                    "priority_distribution": {},
                }

            # Calculate priority distribution
            priority_counts: Dict[int, int] = {}
            for item in self._queue:
                priority_counts[item.priority] = (
                    priority_counts.get(item.priority, 0) + 1
                )

            return {
                "size": len(self._queue),
                "max_size": self.maxsize,
                "is_empty": False,
                "is_full": self.full(),
                "priority_distribution": priority_counts,
                "oldest_item_age": (
                    time.time() - self._queue[0].timestamp if self._queue else 0
                ),
            }


class FairQueue(PriorityQueue):
    """Fair queue that prevents starvation of low-priority items."""

    def __init__(self, maxsize: int = 0, aging_factor: float = 0.1):
        """
        Initialize fair queue.

        Args:
            maxsize: Maximum queue size
            aging_factor: Factor for aging priority
        """
        super().__init__(maxsize)
        self.aging_factor = aging_factor

    async def get(self, block: bool = True, timeout: Optional[float] = None) -> Any:
        """Get item with aging-adjusted priority."""
        async with self._not_empty:
            while not self._queue:
                if not block:
                    raise asyncio.QueueEmpty()

                if timeout is not None:
                    await asyncio.wait_for(self._not_empty.wait(), timeout)
                else:
                    await self._not_empty.wait()

            # Apply aging to priorities
            with self._lock:
                current_time = time.time()

                # Rebuild heap with aged priorities
                aged_items = []
                for item in self._queue:
                    age = current_time - item.timestamp
                    aged_priority = item.priority - (age * self.aging_factor)
                    aged_item = QueueItem(
                        priority=aged_priority,
                        timestamp=item.timestamp,
                        sequence=item.sequence,
                        data=item.data,
                    )
                    aged_items.append(aged_item)

                # Rebuild heap
                self._queue = aged_items
                heapq.heapify(self._queue)

                # Get highest priority item
                queue_item = heapq.heappop(self._queue)

            async with self._not_full:
                self._not_full.notify()

            return queue_item.data


class BatchPriorityQueue(PriorityQueue):
    """Specialized priority queue for batch operations."""

    def __init__(self, maxsize: int = 0):
        """Initialize batch priority queue."""
        super().__init__(maxsize)

    async def put_batch(
        self, batch_request, block: bool = True, timeout: Optional[float] = None
    ) -> None:
        """
        Put a batch request into the queue.

        Args:
            batch_request: Batch request to add
            block: Whether to block if queue is full
            timeout: Timeout for blocking operations
        """
        # Convert batch priority to queue priority
        priority_map = {
            BatchPriority.URGENT: 0,
            BatchPriority.HIGH: 1,
            BatchPriority.NORMAL: 2,
            BatchPriority.LOW: 3,
        }

        priority = priority_map.get(batch_request.priority, 2)
        await self.put(batch_request, priority, block, timeout)

    def get_priority_stats(self) -> Dict[str, int]:
        """
        Get statistics by batch priority.

        Returns:
            Dictionary with priority statistics
        """
        with self._lock:
            stats = {"urgent": 0, "high": 0, "normal": 0, "low": 0}

            priority_map = {0: "urgent", 1: "high", 2: "normal", 3: "low"}

            for item in self._queue:
                priority_name = priority_map.get(item.priority, "normal")
                stats[priority_name] += 1

            return stats
