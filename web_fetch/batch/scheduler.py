"""
Batch scheduler for prioritizing and ordering batch requests.

This module provides intelligent scheduling of batch requests based on
priority, dependencies, and resource availability.
"""

import asyncio
import heapq
import logging
import time
from typing import Dict, List, Optional, Set

from .models import BatchConfig, BatchPriority, BatchRequest, BatchStatus

logger = logging.getLogger(__name__)


class BatchScheduler:
    """Priority-based batch scheduler."""

    def __init__(self, config: BatchConfig):
        """
        Initialize batch scheduler.

        Args:
            config: Batch configuration
        """
        self.config = config
        self._queue: List[tuple] = (
            []
        )  # Priority queue: (priority, timestamp, batch_request)
        self._waiting_batches: Dict[str, BatchRequest] = (
            {}
        )  # Batches waiting for dependencies
        self._lock = asyncio.Lock()
        self._counter = 0  # For stable sorting

    async def add_batch(self, batch_request: BatchRequest) -> None:
        """
        Add a batch request to the scheduler.

        Args:
            batch_request: Batch request to schedule
        """
        async with self._lock:
            # Check if batch has dependencies
            if batch_request.depends_on:
                # Add to waiting queue
                self._waiting_batches[batch_request.id] = batch_request
                logger.debug(
                    f"Batch {batch_request.id} waiting for dependencies: {batch_request.depends_on}"
                )
            else:
                # Add to priority queue
                await self._add_to_queue(batch_request)

    async def get_next_batch(self) -> Optional[BatchRequest]:
        """
        Get the next batch to process based on priority.

        Returns:
            Next batch request or None if queue is empty
        """
        async with self._lock:
            # Check for ready waiting batches first
            await self._check_waiting_batches()

            # Get from priority queue
            if self._queue:
                _, _, batch_request = heapq.heappop(self._queue)
                logger.debug(f"Scheduled batch {batch_request.id} for processing")
                return batch_request

            return None

    async def remove_batch(self, batch_id: str) -> bool:
        """
        Remove a batch from the scheduler.

        Args:
            batch_id: Batch ID to remove

        Returns:
            True if removed, False if not found
        """
        async with self._lock:
            # Remove from waiting batches
            if batch_id in self._waiting_batches:
                del self._waiting_batches[batch_id]
                return True

            # Remove from priority queue (mark as removed)
            for i, (_, _, batch_request) in enumerate(self._queue):
                if batch_request.id == batch_id:
                    # Mark as removed (we can't efficiently remove from heapq)
                    self._queue[i] = (float("inf"), time.time(), None)
                    return True

            return False

    async def batch_completed(self, batch_id: str) -> None:
        """
        Notify scheduler that a batch has completed.

        Args:
            batch_id: Completed batch ID
        """
        async with self._lock:
            # Check if any waiting batches can now be scheduled
            await self._check_waiting_batches()

    async def get_queue_status(self) -> Dict[str, int]:
        """
        Get current queue status.

        Returns:
            Dictionary with queue statistics
        """
        async with self._lock:
            # Count valid entries in queue
            valid_queue_items = sum(
                1 for _, _, batch in self._queue if batch is not None
            )

            return {
                "queued_batches": valid_queue_items,
                "waiting_batches": len(self._waiting_batches),
                "total_batches": valid_queue_items + len(self._waiting_batches),
            }

    async def _add_to_queue(self, batch_request: BatchRequest) -> None:
        """Add batch to priority queue."""
        # Convert priority to negative for min-heap (higher priority = lower number)
        priority_value = -batch_request.priority.value

        # Use counter for stable sorting
        self._counter += 1
        timestamp = time.time()

        heapq.heappush(self._queue, (priority_value, timestamp, batch_request))
        logger.debug(
            f"Added batch {batch_request.id} to queue with priority {batch_request.priority}"
        )

    async def _check_waiting_batches(self) -> None:
        """Check waiting batches for resolved dependencies."""
        ready_batches = []

        for batch_id, batch_request in list(self._waiting_batches.items()):
            # Check if all dependencies are resolved
            # Note: This would need access to completed batches from the manager
            # For now, we'll assume dependencies are resolved after some time
            if self._are_dependencies_resolved(batch_request):
                ready_batches.append(batch_request)
                del self._waiting_batches[batch_id]

        # Add ready batches to queue
        for batch_request in ready_batches:
            await self._add_to_queue(batch_request)
            logger.debug(
                f"Batch {batch_request.id} dependencies resolved, added to queue"
            )

    def _are_dependencies_resolved(self, batch_request: BatchRequest) -> bool:
        """
        Check if batch dependencies are resolved.

        Args:
            batch_request: Batch request to check

        Returns:
            True if dependencies are resolved
        """
        # This is a simplified implementation
        # In a real implementation, this would check with the batch manager
        # to see if dependent batches have completed successfully

        # For now, assume dependencies are resolved after 10 seconds
        time_waiting = time.time() - batch_request.created_at
        return time_waiting > 10.0


class FairScheduler(BatchScheduler):
    """Fair scheduler that balances priority with waiting time."""

    def __init__(self, config: BatchConfig, aging_factor: float = 0.1):
        """
        Initialize fair scheduler.

        Args:
            config: Batch configuration
            aging_factor: Factor for aging priority based on wait time
        """
        super().__init__(config)
        self.aging_factor = aging_factor

    async def _add_to_queue(self, batch_request: BatchRequest) -> None:
        """Add batch to queue with aging-adjusted priority."""
        # Calculate aged priority
        wait_time = time.time() - batch_request.created_at
        age_bonus = wait_time * self.aging_factor

        # Adjust priority (higher priority = lower number for min-heap)
        adjusted_priority = -batch_request.priority.value - age_bonus

        self._counter += 1
        timestamp = time.time()

        heapq.heappush(self._queue, (adjusted_priority, timestamp, batch_request))
        logger.debug(
            f"Added batch {batch_request.id} with aged priority {adjusted_priority}"
        )


class ResourceAwareScheduler(BatchScheduler):
    """Scheduler that considers resource requirements."""

    def __init__(self, config: BatchConfig):
        """
        Initialize resource-aware scheduler.

        Args:
            config: Batch configuration
        """
        super().__init__(config)
        self._resource_usage: Dict[str, float] = {
            "cpu": 0.0,
            "memory": 0.0,
            "network": 0.0,
        }

    async def get_next_batch(self) -> Optional[BatchRequest]:
        """Get next batch considering resource availability."""
        async with self._lock:
            await self._check_waiting_batches()

            # Find a batch that fits current resource constraints
            available_batches = []

            while self._queue:
                priority, timestamp, batch_request = heapq.heappop(self._queue)

                if batch_request is None:  # Removed batch
                    continue

                # Check if batch fits resource constraints
                if self._can_schedule_batch(batch_request):
                    return batch_request
                else:
                    # Put back in queue for later
                    available_batches.append((priority, timestamp, batch_request))

            # Put back all batches that couldn't be scheduled
            for item in available_batches:
                heapq.heappush(self._queue, item)

            return None

    def _can_schedule_batch(self, batch_request: BatchRequest) -> bool:
        """
        Check if batch can be scheduled given current resource usage.

        Args:
            batch_request: Batch request to check

        Returns:
            True if batch can be scheduled
        """
        # Estimate resource requirements
        estimated_memory = len(batch_request.requests) * 10  # MB per request
        estimated_cpu = batch_request.max_concurrent * 0.1  # CPU per concurrent request

        # Check against limits
        memory_ok = (
            self._resource_usage["memory"] + estimated_memory
            < self.config.memory_limit_mb
        )
        cpu_ok = self._resource_usage["cpu"] + estimated_cpu < 1.0  # 100% CPU

        return memory_ok and cpu_ok

    async def update_resource_usage(self, usage: Dict[str, float]) -> None:
        """
        Update current resource usage.

        Args:
            usage: Current resource usage
        """
        async with self._lock:
            self._resource_usage.update(usage)
