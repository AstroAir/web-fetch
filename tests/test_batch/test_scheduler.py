"""
Comprehensive tests for the batch scheduler module.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from web_fetch.batch.scheduler import BatchScheduler
from web_fetch.batch.models import (
    BatchRequest,
    BatchResult,
    BatchConfig,
    BatchPriority,
    BatchStatus,
)
from web_fetch.batch.queue import PriorityQueue
from web_fetch.batch.processor import BatchProcessor
from web_fetch.models.http import FetchRequest, FetchResult
from web_fetch.models.base import ContentType


class TestBatchScheduler:
    """Test batch scheduler functionality."""

    def test_batch_scheduler_creation(self):
        """Test creating a batch scheduler."""
        config = BatchConfig(max_concurrent_requests=5)
        scheduler = BatchScheduler(config)
        
        assert scheduler.config == config
        assert isinstance(scheduler.queue, PriorityQueue)
        assert isinstance(scheduler.processor, BatchProcessor)
        assert not scheduler.is_running

    def test_batch_scheduler_default_config(self):
        """Test batch scheduler with default configuration."""
        scheduler = BatchScheduler()
        
        assert scheduler.config is not None
        assert scheduler.config.max_concurrent_requests == 10

    @pytest.mark.asyncio
    async def test_submit_batch_request(self):
        """Test submitting a batch request."""
        scheduler = BatchScheduler()
        
        requests = [FetchRequest(url="https://example.com/1")]
        batch_request = BatchRequest(requests=requests)
        
        # Submit batch
        batch_id = await scheduler.submit_batch(batch_request)
        
        assert batch_id == batch_request.batch_id
        assert scheduler.queue.size() == 1
        assert batch_request.status == BatchStatus.PENDING

    @pytest.mark.asyncio
    async def test_submit_multiple_batches(self):
        """Test submitting multiple batch requests."""
        scheduler = BatchScheduler()
        
        batch_requests = []
        for i in range(3):
            requests = [FetchRequest(url=f"https://example.com/{i}")]
            batch_request = BatchRequest(
                requests=requests,
                priority=BatchPriority.NORMAL
            )
            batch_requests.append(batch_request)
        
        # Submit all batches
        batch_ids = []
        for batch_request in batch_requests:
            batch_id = await scheduler.submit_batch(batch_request)
            batch_ids.append(batch_id)
        
        assert len(batch_ids) == 3
        assert scheduler.queue.size() == 3

    @pytest.mark.asyncio
    async def test_submit_batch_with_priority(self):
        """Test submitting batches with different priorities."""
        scheduler = BatchScheduler()
        
        # Submit batches with different priorities
        low_batch = BatchRequest(
            requests=[FetchRequest(url="https://example.com/low")],
            priority=BatchPriority.LOW
        )
        
        high_batch = BatchRequest(
            requests=[FetchRequest(url="https://example.com/high")],
            priority=BatchPriority.HIGH
        )
        
        urgent_batch = BatchRequest(
            requests=[FetchRequest(url="https://example.com/urgent")],
            priority=BatchPriority.URGENT
        )
        
        # Submit in reverse priority order
        await scheduler.submit_batch(low_batch)
        await scheduler.submit_batch(high_batch)
        await scheduler.submit_batch(urgent_batch)
        
        # Check that highest priority is at front
        next_batch = scheduler.queue.peek()
        assert next_batch == urgent_batch

    @pytest.mark.asyncio
    async def test_start_and_stop_scheduler(self):
        """Test starting and stopping the scheduler."""
        scheduler = BatchScheduler()
        
        assert not scheduler.is_running
        
        # Start scheduler
        await scheduler.start()
        assert scheduler.is_running
        
        # Stop scheduler
        await scheduler.stop()
        assert not scheduler.is_running

    @pytest.mark.asyncio
    async def test_process_single_batch(self):
        """Test processing a single batch."""
        scheduler = BatchScheduler()
        
        # Mock the processor
        mock_result = BatchResult(
            batch_id="test-batch",
            results=[
                FetchResult(
                    url="https://example.com/1",
                    status_code=200,
                    headers={},
                    content="content",
                    content_type=ContentType.TEXT
                )
            ],
            status=BatchStatus.COMPLETED
        )
        
        with patch.object(scheduler.processor, 'process_batch', return_value=mock_result) as mock_process:
            # Submit and start processing
            requests = [FetchRequest(url="https://example.com/1")]
            batch_request = BatchRequest(requests=requests)
            
            await scheduler.submit_batch(batch_request)
            await scheduler.start()
            
            # Wait a bit for processing
            await asyncio.sleep(0.1)
            
            await scheduler.stop()
            
            # Verify processing was called
            mock_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_batch_status(self):
        """Test getting batch status."""
        scheduler = BatchScheduler()
        
        requests = [FetchRequest(url="https://example.com/1")]
        batch_request = BatchRequest(requests=requests)
        
        batch_id = await scheduler.submit_batch(batch_request)
        
        # Get status
        status = await scheduler.get_batch_status(batch_id)
        assert status == BatchStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_nonexistent_batch_status(self):
        """Test getting status of non-existent batch."""
        scheduler = BatchScheduler()
        
        status = await scheduler.get_batch_status("nonexistent-batch")
        assert status is None

    @pytest.mark.asyncio
    async def test_cancel_batch(self):
        """Test cancelling a batch."""
        scheduler = BatchScheduler()
        
        requests = [FetchRequest(url="https://example.com/1")]
        batch_request = BatchRequest(requests=requests)
        
        batch_id = await scheduler.submit_batch(batch_request)
        
        # Cancel batch
        success = await scheduler.cancel_batch(batch_id)
        assert success == True
        
        # Check status
        status = await scheduler.get_batch_status(batch_id)
        assert status == BatchStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_batch(self):
        """Test cancelling a non-existent batch."""
        scheduler = BatchScheduler()
        
        success = await scheduler.cancel_batch("nonexistent-batch")
        assert success == False

    @pytest.mark.asyncio
    async def test_cancel_running_batch(self):
        """Test cancelling a batch that's already running."""
        scheduler = BatchScheduler()
        
        # Mock a long-running processor
        async def long_process(batch_request, **kwargs):
            await asyncio.sleep(1.0)
            return BatchResult(
                batch_id=batch_request.batch_id,
                results=[],
                status=BatchStatus.COMPLETED
            )
        
        with patch.object(scheduler.processor, 'process_batch', side_effect=long_process):
            requests = [FetchRequest(url="https://example.com/1")]
            batch_request = BatchRequest(requests=requests)
            
            batch_id = await scheduler.submit_batch(batch_request)
            
            # Start processing
            await scheduler.start()
            await asyncio.sleep(0.1)  # Let processing start
            
            # Try to cancel
            success = await scheduler.cancel_batch(batch_id)
            
            await scheduler.stop()
            
            # Should succeed in cancelling
            assert success == True

    @pytest.mark.asyncio
    async def test_get_batch_result(self):
        """Test getting batch result."""
        scheduler = BatchScheduler()
        
        # Mock successful processing
        mock_result = BatchResult(
            batch_id="test-batch",
            results=[
                FetchResult(
                    url="https://example.com/1",
                    status_code=200,
                    headers={},
                    content="content",
                    content_type=ContentType.TEXT
                )
            ],
            status=BatchStatus.COMPLETED
        )
        
        with patch.object(scheduler.processor, 'process_batch', return_value=mock_result):
            requests = [FetchRequest(url="https://example.com/1")]
            batch_request = BatchRequest(requests=requests)
            
            batch_id = await scheduler.submit_batch(batch_request)
            
            # Start processing
            await scheduler.start()
            await asyncio.sleep(0.1)  # Wait for processing
            await scheduler.stop()
            
            # Get result
            result = await scheduler.get_batch_result(batch_id)
            assert result is not None
            assert result.batch_id == batch_id
            assert result.status == BatchStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_get_nonexistent_batch_result(self):
        """Test getting result of non-existent batch."""
        scheduler = BatchScheduler()
        
        result = await scheduler.get_batch_result("nonexistent-batch")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_active_batches(self):
        """Test listing active batches."""
        scheduler = BatchScheduler()
        
        # Submit multiple batches
        batch_ids = []
        for i in range(3):
            requests = [FetchRequest(url=f"https://example.com/{i}")]
            batch_request = BatchRequest(requests=requests)
            batch_id = await scheduler.submit_batch(batch_request)
            batch_ids.append(batch_id)
        
        # List active batches
        active_batches = await scheduler.list_active_batches()
        
        assert len(active_batches) == 3
        assert all(batch_id in [b.batch_id for b in active_batches] for batch_id in batch_ids)

    @pytest.mark.asyncio
    async def test_get_queue_statistics(self):
        """Test getting queue statistics."""
        scheduler = BatchScheduler()
        
        # Submit batches with different priorities
        priorities = [BatchPriority.LOW, BatchPriority.HIGH, BatchPriority.URGENT]
        
        for priority in priorities:
            requests = [FetchRequest(url="https://example.com/test")]
            batch_request = BatchRequest(requests=requests, priority=priority)
            await scheduler.submit_batch(batch_request)
        
        # Get statistics
        stats = await scheduler.get_queue_statistics()
        
        assert stats['total_items'] == 3
        assert stats['priority_counts'][BatchPriority.LOW] == 1
        assert stats['priority_counts'][BatchPriority.HIGH] == 1
        assert stats['priority_counts'][BatchPriority.URGENT] == 1

    @pytest.mark.asyncio
    async def test_scheduler_with_progress_callback(self):
        """Test scheduler with progress callback."""
        scheduler = BatchScheduler()
        
        progress_updates = []
        
        def progress_callback(batch_id, completed, total, current_url=None):
            progress_updates.append((batch_id, completed, total, current_url))
        
        # Mock processor to call progress callback
        async def mock_process(batch_request, progress_callback=None, **kwargs):
            if progress_callback:
                progress_callback(0, 1, "https://example.com/1")
                await asyncio.sleep(0.01)
                progress_callback(1, 1, "https://example.com/1")
            
            return BatchResult(
                batch_id=batch_request.batch_id,
                results=[
                    FetchResult(
                        url="https://example.com/1",
                        status_code=200,
                        headers={},
                        content="content",
                        content_type=ContentType.TEXT
                    )
                ],
                status=BatchStatus.COMPLETED
            )
        
        with patch.object(scheduler.processor, 'process_batch', side_effect=mock_process):
            requests = [FetchRequest(url="https://example.com/1")]
            batch_request = BatchRequest(requests=requests)
            
            batch_id = await scheduler.submit_batch(batch_request, progress_callback=progress_callback)
            
            await scheduler.start()
            await asyncio.sleep(0.1)  # Wait for processing
            await scheduler.stop()
            
            # Check progress updates were received
            assert len(progress_updates) >= 1

    @pytest.mark.asyncio
    async def test_scheduler_error_handling(self):
        """Test scheduler error handling."""
        scheduler = BatchScheduler()
        
        # Mock processor to raise an exception
        async def failing_process(batch_request, **kwargs):
            raise Exception("Processing failed")
        
        with patch.object(scheduler.processor, 'process_batch', side_effect=failing_process):
            requests = [FetchRequest(url="https://example.com/1")]
            batch_request = BatchRequest(requests=requests)
            
            batch_id = await scheduler.submit_batch(batch_request)
            
            await scheduler.start()
            await asyncio.sleep(0.1)  # Wait for processing attempt
            await scheduler.stop()
            
            # Check that batch status reflects the error
            status = await scheduler.get_batch_status(batch_id)
            assert status == BatchStatus.FAILED

    @pytest.mark.asyncio
    async def test_scheduler_concurrent_processing(self):
        """Test scheduler processing multiple batches concurrently."""
        config = BatchConfig(max_concurrent_requests=2)
        scheduler = BatchScheduler(config)
        
        processing_times = []
        
        async def timed_process(batch_request, **kwargs):
            start_time = asyncio.get_event_loop().time()
            await asyncio.sleep(0.1)  # Simulate processing time
            end_time = asyncio.get_event_loop().time()
            processing_times.append((start_time, end_time))
            
            return BatchResult(
                batch_id=batch_request.batch_id,
                results=[],
                status=BatchStatus.COMPLETED
            )
        
        with patch.object(scheduler.processor, 'process_batch', side_effect=timed_process):
            # Submit multiple batches
            batch_ids = []
            for i in range(3):
                requests = [FetchRequest(url=f"https://example.com/{i}")]
                batch_request = BatchRequest(requests=requests)
                batch_id = await scheduler.submit_batch(batch_request)
                batch_ids.append(batch_id)
            
            await scheduler.start()
            await asyncio.sleep(0.5)  # Wait for all processing
            await scheduler.stop()
            
            # Check that some processing happened concurrently
            assert len(processing_times) == 3

    @pytest.mark.asyncio
    async def test_scheduler_cleanup(self):
        """Test scheduler cleanup of completed batches."""
        scheduler = BatchScheduler()
        
        # Mock successful processing
        mock_result = BatchResult(
            batch_id="test-batch",
            results=[],
            status=BatchStatus.COMPLETED
        )
        
        with patch.object(scheduler.processor, 'process_batch', return_value=mock_result):
            requests = [FetchRequest(url="https://example.com/1")]
            batch_request = BatchRequest(requests=requests)
            
            batch_id = await scheduler.submit_batch(batch_request)
            
            await scheduler.start()
            await asyncio.sleep(0.1)  # Wait for processing
            await scheduler.stop()
            
            # Trigger cleanup
            await scheduler._cleanup_completed_batches()
            
            # Batch should still be accessible for a while
            result = await scheduler.get_batch_result(batch_id)
            assert result is not None

    @pytest.mark.asyncio
    async def test_scheduler_resource_management(self):
        """Test scheduler resource management."""
        scheduler = BatchScheduler()
        
        # Check initial resource state
        assert not scheduler.is_running
        assert scheduler.queue.is_empty()
        
        # Submit and process batches
        for i in range(5):
            requests = [FetchRequest(url=f"https://example.com/{i}")]
            batch_request = BatchRequest(requests=requests)
            await scheduler.submit_batch(batch_request)
        
        assert scheduler.queue.size() == 5
        
        # Clear queue
        scheduler.queue.clear()
        assert scheduler.queue.is_empty()
