"""
Comprehensive tests for the batch queue module.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from web_fetch.batch.queue import PriorityQueue
from web_fetch.batch.models import (
    BatchRequest,
    BatchPriority,
    BatchStatus,
    BatchConfig,
)
from web_fetch.models.http import FetchRequest


class TestPriorityQueue:
    """Test priority queue functionality."""

    def test_priority_queue_creation(self):
        """Test creating a priority queue."""
        queue = PriorityQueue()
        assert queue is not None
        assert queue.size() == 0
        assert queue.is_empty()

    def test_priority_queue_with_max_size(self):
        """Test creating priority queue with maximum size."""
        queue = PriorityQueue(max_size=10)
        assert queue.max_size == 10
        assert queue.size() == 0

    def test_enqueue_single_item(self):
        """Test enqueueing a single item."""
        queue = PriorityQueue()
        
        requests = [FetchRequest(url="https://example.com/1")]
        batch_request = BatchRequest(
            requests=requests,
            priority=BatchPriority.NORMAL
        )
        
        queue.enqueue(batch_request)
        
        assert queue.size() == 1
        assert not queue.is_empty()

    def test_dequeue_single_item(self):
        """Test dequeueing a single item."""
        queue = PriorityQueue()
        
        requests = [FetchRequest(url="https://example.com/1")]
        batch_request = BatchRequest(
            requests=requests,
            priority=BatchPriority.NORMAL
        )
        
        queue.enqueue(batch_request)
        dequeued = queue.dequeue()
        
        assert dequeued == batch_request
        assert queue.size() == 0
        assert queue.is_empty()

    def test_priority_ordering(self):
        """Test that items are dequeued in priority order."""
        queue = PriorityQueue()
        
        # Create batch requests with different priorities
        low_priority = BatchRequest(
            requests=[FetchRequest(url="https://example.com/low")],
            priority=BatchPriority.LOW
        )
        
        high_priority = BatchRequest(
            requests=[FetchRequest(url="https://example.com/high")],
            priority=BatchPriority.HIGH
        )
        
        normal_priority = BatchRequest(
            requests=[FetchRequest(url="https://example.com/normal")],
            priority=BatchPriority.NORMAL
        )
        
        urgent_priority = BatchRequest(
            requests=[FetchRequest(url="https://example.com/urgent")],
            priority=BatchPriority.URGENT
        )
        
        # Enqueue in random order
        queue.enqueue(low_priority)
        queue.enqueue(high_priority)
        queue.enqueue(normal_priority)
        queue.enqueue(urgent_priority)
        
        # Dequeue should return in priority order (highest first)
        assert queue.dequeue() == urgent_priority
        assert queue.dequeue() == high_priority
        assert queue.dequeue() == normal_priority
        assert queue.dequeue() == low_priority

    def test_fifo_within_same_priority(self):
        """Test FIFO ordering within the same priority level."""
        queue = PriorityQueue()
        
        # Create multiple requests with same priority
        request1 = BatchRequest(
            requests=[FetchRequest(url="https://example.com/1")],
            priority=BatchPriority.NORMAL
        )
        
        request2 = BatchRequest(
            requests=[FetchRequest(url="https://example.com/2")],
            priority=BatchPriority.NORMAL
        )
        
        request3 = BatchRequest(
            requests=[FetchRequest(url="https://example.com/3")],
            priority=BatchPriority.NORMAL
        )
        
        # Enqueue in order
        queue.enqueue(request1)
        queue.enqueue(request2)
        queue.enqueue(request3)
        
        # Should dequeue in FIFO order for same priority
        assert queue.dequeue() == request1
        assert queue.dequeue() == request2
        assert queue.dequeue() == request3

    def test_peek_without_removing(self):
        """Test peeking at the next item without removing it."""
        queue = PriorityQueue()
        
        requests = [FetchRequest(url="https://example.com/1")]
        batch_request = BatchRequest(
            requests=requests,
            priority=BatchPriority.HIGH
        )
        
        queue.enqueue(batch_request)
        
        # Peek should return the item without removing it
        peeked = queue.peek()
        assert peeked == batch_request
        assert queue.size() == 1  # Item should still be in queue
        
        # Dequeue should return the same item
        dequeued = queue.dequeue()
        assert dequeued == batch_request
        assert queue.size() == 0

    def test_peek_empty_queue(self):
        """Test peeking at an empty queue."""
        queue = PriorityQueue()
        
        peeked = queue.peek()
        assert peeked is None

    def test_dequeue_empty_queue(self):
        """Test dequeueing from an empty queue."""
        queue = PriorityQueue()
        
        dequeued = queue.dequeue()
        assert dequeued is None

    def test_max_size_enforcement(self):
        """Test that max size is enforced."""
        queue = PriorityQueue(max_size=2)
        
        request1 = BatchRequest(
            requests=[FetchRequest(url="https://example.com/1")],
            priority=BatchPriority.NORMAL
        )
        
        request2 = BatchRequest(
            requests=[FetchRequest(url="https://example.com/2")],
            priority=BatchPriority.NORMAL
        )
        
        request3 = BatchRequest(
            requests=[FetchRequest(url="https://example.com/3")],
            priority=BatchPriority.NORMAL
        )
        
        # First two should succeed
        assert queue.enqueue(request1) == True
        assert queue.enqueue(request2) == True
        assert queue.size() == 2
        
        # Third should fail due to max size
        assert queue.enqueue(request3) == False
        assert queue.size() == 2

    def test_is_full_method(self):
        """Test the is_full method."""
        queue = PriorityQueue(max_size=2)
        
        assert not queue.is_full()
        
        request1 = BatchRequest(
            requests=[FetchRequest(url="https://example.com/1")],
            priority=BatchPriority.NORMAL
        )
        
        request2 = BatchRequest(
            requests=[FetchRequest(url="https://example.com/2")],
            priority=BatchPriority.NORMAL
        )
        
        queue.enqueue(request1)
        assert not queue.is_full()
        
        queue.enqueue(request2)
        assert queue.is_full()

    def test_clear_queue(self):
        """Test clearing the queue."""
        queue = PriorityQueue()
        
        # Add some items
        for i in range(5):
            request = BatchRequest(
                requests=[FetchRequest(url=f"https://example.com/{i}")],
                priority=BatchPriority.NORMAL
            )
            queue.enqueue(request)
        
        assert queue.size() == 5
        
        # Clear the queue
        queue.clear()
        
        assert queue.size() == 0
        assert queue.is_empty()

    def test_queue_statistics(self):
        """Test queue statistics."""
        queue = PriorityQueue()
        
        # Add items with different priorities
        priorities = [
            BatchPriority.LOW,
            BatchPriority.NORMAL,
            BatchPriority.HIGH,
            BatchPriority.URGENT,
            BatchPriority.NORMAL,
            BatchPriority.HIGH
        ]
        
        for i, priority in enumerate(priorities):
            request = BatchRequest(
                requests=[FetchRequest(url=f"https://example.com/{i}")],
                priority=priority
            )
            queue.enqueue(request)
        
        stats = queue.get_statistics()
        
        assert stats['total_items'] == 6
        assert stats['priority_counts'][BatchPriority.LOW] == 1
        assert stats['priority_counts'][BatchPriority.NORMAL] == 2
        assert stats['priority_counts'][BatchPriority.HIGH] == 2
        assert stats['priority_counts'][BatchPriority.URGENT] == 1

    def test_queue_with_timestamps(self):
        """Test queue behavior with timestamps."""
        queue = PriorityQueue()
        
        # Create requests with same priority but different timestamps
        now = datetime.now()
        
        request1 = BatchRequest(
            requests=[FetchRequest(url="https://example.com/1")],
            priority=BatchPriority.NORMAL
        )
        request1.created_at = now - timedelta(seconds=10)
        
        request2 = BatchRequest(
            requests=[FetchRequest(url="https://example.com/2")],
            priority=BatchPriority.NORMAL
        )
        request2.created_at = now - timedelta(seconds=5)
        
        request3 = BatchRequest(
            requests=[FetchRequest(url="https://example.com/3")],
            priority=BatchPriority.NORMAL
        )
        request3.created_at = now
        
        # Enqueue in reverse chronological order
        queue.enqueue(request3)
        queue.enqueue(request1)
        queue.enqueue(request2)
        
        # Should dequeue in chronological order (FIFO for same priority)
        assert queue.dequeue() == request3  # First enqueued
        assert queue.dequeue() == request1  # Second enqueued
        assert queue.dequeue() == request2  # Third enqueued

    def test_queue_iteration(self):
        """Test iterating over queue items."""
        queue = PriorityQueue()
        
        requests = []
        for i in range(3):
            request = BatchRequest(
                requests=[FetchRequest(url=f"https://example.com/{i}")],
                priority=BatchPriority.NORMAL
            )
            requests.append(request)
            queue.enqueue(request)
        
        # Test iteration without modifying queue
        iterated_items = list(queue)
        assert len(iterated_items) == 3
        assert queue.size() == 3  # Queue should remain unchanged

    def test_queue_contains(self):
        """Test checking if queue contains an item."""
        queue = PriorityQueue()
        
        request1 = BatchRequest(
            requests=[FetchRequest(url="https://example.com/1")],
            priority=BatchPriority.NORMAL
        )
        
        request2 = BatchRequest(
            requests=[FetchRequest(url="https://example.com/2")],
            priority=BatchPriority.NORMAL
        )
        
        queue.enqueue(request1)
        
        assert request1 in queue
        assert request2 not in queue

    @pytest.mark.asyncio
    async def test_async_queue_operations(self):
        """Test asynchronous queue operations."""
        queue = PriorityQueue()
        
        async def producer():
            for i in range(5):
                request = BatchRequest(
                    requests=[FetchRequest(url=f"https://example.com/{i}")],
                    priority=BatchPriority.NORMAL
                )
                queue.enqueue(request)
                await asyncio.sleep(0.01)  # Small delay
        
        async def consumer():
            consumed = []
            while len(consumed) < 5:
                item = queue.dequeue()
                if item:
                    consumed.append(item)
                else:
                    await asyncio.sleep(0.01)  # Wait for items
            return consumed
        
        # Run producer and consumer concurrently
        producer_task = asyncio.create_task(producer())
        consumer_task = asyncio.create_task(consumer())
        
        await producer_task
        consumed_items = await consumer_task
        
        assert len(consumed_items) == 5
        assert queue.is_empty()

    def test_queue_thread_safety_simulation(self):
        """Test queue behavior under concurrent access simulation."""
        queue = PriorityQueue()
        
        # Simulate concurrent enqueue operations
        requests = []
        for i in range(100):
            request = BatchRequest(
                requests=[FetchRequest(url=f"https://example.com/{i}")],
                priority=BatchPriority.NORMAL
            )
            requests.append(request)
            queue.enqueue(request)
        
        # Simulate concurrent dequeue operations
        dequeued = []
        while not queue.is_empty():
            item = queue.dequeue()
            if item:
                dequeued.append(item)
        
        assert len(dequeued) == 100
        assert queue.is_empty()

    def test_queue_memory_efficiency(self):
        """Test queue memory efficiency with large number of items."""
        queue = PriorityQueue()
        
        # Add a large number of items
        num_items = 1000
        for i in range(num_items):
            request = BatchRequest(
                requests=[FetchRequest(url=f"https://example.com/{i}")],
                priority=BatchPriority.NORMAL
            )
            queue.enqueue(request)
        
        assert queue.size() == num_items
        
        # Remove half the items
        for _ in range(num_items // 2):
            queue.dequeue()
        
        assert queue.size() == num_items // 2
        
        # Clear remaining items
        queue.clear()
        assert queue.is_empty()
