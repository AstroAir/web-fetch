"""
Comprehensive tests for the batch operations module.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from web_fetch.batch import (
    BatchManager,
    BatchRequest,
    BatchResult,
    BatchConfig,
    BatchPriority,
    BatchStatus,
    BatchMetrics,
    BatchScheduler,
    BatchProcessor,
    PriorityQueue,
)
from web_fetch.models import FetchConfig, FetchRequest, FetchResult, ContentType
from web_fetch.exceptions import WebFetchError


class TestBatchRequest:
    """Test batch request model."""

    def test_batch_request_creation(self):
        """Test batch request creation."""
        fetch_request = FetchRequest(url="https://example.com")
        request = BatchRequest(
            requests=[fetch_request],
            priority=BatchPriority.HIGH,
            name="test_batch"
        )

        assert len(request.requests) == 1
        assert str(request.requests[0].url) == "https://example.com/"
        assert request.priority == BatchPriority.HIGH
        assert request.name == "test_batch"
        assert request.id is not None
        assert request.created_at is not None

    def test_batch_request_defaults(self):
        """Test batch request default values."""
        fetch_request = FetchRequest(url="https://example.com")
        request = BatchRequest(requests=[fetch_request])

        assert request.priority == BatchPriority.NORMAL
        assert request.max_concurrent == 10
        assert request.timeout == 300.0
        assert request.retry_failed is True

    def test_batch_request_comparison(self):
        """Test batch request priority comparison."""
        fetch_request = FetchRequest(url="https://example.com")
        high_req = BatchRequest(requests=[fetch_request], priority=BatchPriority.HIGH)
        normal_req = BatchRequest(requests=[fetch_request], priority=BatchPriority.NORMAL)
        low_req = BatchRequest(requests=[fetch_request], priority=BatchPriority.LOW)

        # Test that requests have different priorities
        assert high_req.priority == BatchPriority.HIGH
        assert normal_req.priority == BatchPriority.NORMAL
        assert low_req.priority == BatchPriority.LOW


class TestBatchResult:
    """Test batch result model."""

    def test_batch_result_success(self):
        """Test successful batch result."""
        fetch_result = FetchResult(
            url="https://example.com",
            content="test content",
            status_code=200,
            headers={},
            content_type="text/html"
        )

        result = BatchResult(
            id="test-batch-1",
            status=BatchStatus.COMPLETED,
            results=[fetch_result],
            total_requests=1,
            successful_requests=1,
            failed_requests=0,
            total_time=1.5
        )

        assert result.id == "test-batch-1"
        assert result.status == BatchStatus.COMPLETED
        assert len(result.results) == 1
        assert result.results[0] == fetch_result
        assert result.total_requests == 1
        assert result.successful_requests == 1
        assert result.success_rate == 1.0

    def test_batch_result_failure(self):
        """Test failed batch result."""
        result = BatchResult(
            id="test-batch-2",
            status=BatchStatus.FAILED,
            total_requests=1,
            successful_requests=0,
            failed_requests=1,
            errors=["Network error"],
            failed_urls=["https://example.com"],
            total_time=0.5
        )

        assert result.id == "test-batch-2"
        assert result.status == BatchStatus.FAILED
        assert result.total_requests == 1
        assert result.failed_requests == 1
        assert len(result.errors) == 1
        assert result.errors[0] == "Network error"
        assert result.success_rate == 0.0


class TestBatchConfig:
    """Test batch configuration."""

    def test_batch_config_defaults(self):
        """Test default batch configuration."""
        config = BatchConfig()

        assert config.max_concurrent_requests_per_batch == 10
        assert config.request_timeout == 30.0
        assert config.retry_delay == 5.0
        assert config.max_batch_retries == 3
        assert config.enable_metrics is True

    def test_batch_config_validation(self):
        """Test batch configuration validation."""
        # Valid config
        config = BatchConfig(
            max_concurrent_requests_per_batch=5,
            request_timeout=60.0,
            retry_delay=2.0
        )

        assert config.max_concurrent_requests_per_batch == 5
        assert config.request_timeout == 60.0
        assert config.retry_delay == 2.0

    def test_batch_config_invalid_values(self):
        """Test batch configuration with invalid values."""
        with pytest.raises(ValueError):
            BatchConfig(max_concurrent_requests_per_batch=0)

        with pytest.raises(ValueError):
            BatchConfig(request_timeout=-1.0)


class TestPriorityQueue:
    """Test priority queue implementation."""

    def test_priority_queue_basic_operations(self):
        """Test basic priority queue operations."""
        queue = PriorityQueue()

        # Test empty queue
        assert queue.empty() is True
        assert queue.qsize() == 0

        # Add items using put_nowait (synchronous)
        from web_fetch.models import FetchRequest
        high_req = BatchRequest(
            requests=[FetchRequest(url="https://high.com")],
            priority=BatchPriority.HIGH
        )
        normal_req = BatchRequest(
            requests=[FetchRequest(url="https://normal.com")],
            priority=BatchPriority.NORMAL
        )
        low_req = BatchRequest(
            requests=[FetchRequest(url="https://low.com")],
            priority=BatchPriority.LOW
        )

        # Use priority values for queue ordering (lower = higher priority)
        queue.put_nowait(normal_req, priority=2)  # Normal priority
        queue.put_nowait(high_req, priority=1)    # High priority
        queue.put_nowait(low_req, priority=3)     # Low priority

        assert queue.qsize() == 3
        assert queue.empty() is False

        # Items should come out in priority order (high first)
        first = queue.get_nowait()
        second = queue.get_nowait()
        third = queue.get_nowait()

        assert first.priority == BatchPriority.HIGH
        assert second.priority == BatchPriority.NORMAL
        assert third.priority == BatchPriority.LOW

    def test_priority_queue_thread_safety(self):
        """Test priority queue thread safety."""
        queue = PriorityQueue()
        
        def producer():
            for i in range(10):
                fetch_request = FetchRequest(url=f"https://example{i}.com")
                req = BatchRequest(requests=[fetch_request])
                queue.put_nowait(req)

        def consumer():
            items = []
            for _ in range(10):
                items.append(queue.get_nowait())
            return items
        
        import threading
        
        producer_thread = threading.Thread(target=producer)
        consumer_thread = threading.Thread(target=consumer)
        
        producer_thread.start()
        consumer_thread.start()
        
        producer_thread.join()
        consumer_thread.join()
        
        assert queue.empty() is True


class TestBatchScheduler:
    """Test batch scheduler."""

    def test_scheduler_creation(self):
        """Test scheduler creation."""
        config = BatchConfig(max_concurrent_batches=5)
        scheduler = BatchScheduler(config)

        assert scheduler.config == config
        assert len(scheduler._queue) == 0

    @pytest.mark.asyncio
    async def test_scheduler_add_request(self):
        """Test adding requests to scheduler."""
        config = BatchConfig(max_concurrent_batches=2)
        scheduler = BatchScheduler(config)

        from web_fetch.models import FetchRequest
        request1 = BatchRequest(requests=[FetchRequest(url="https://example1.com")])
        request2 = BatchRequest(
            requests=[FetchRequest(url="https://example2.com")],
            priority=BatchPriority.HIGH
        )

        await scheduler.add_batch(request1)
        await scheduler.add_batch(request2)

        assert len(scheduler._queue) == 2

        # High priority request should be first
        next_req = await scheduler.get_next_batch()
        assert next_req.priority == BatchPriority.HIGH

    @pytest.mark.asyncio
    async def test_scheduler_queue_operations(self):
        """Test scheduler queue operations."""
        config = BatchConfig(max_concurrent_batches=1)
        scheduler = BatchScheduler(config)

        from web_fetch.models import FetchRequest
        request = BatchRequest(requests=[FetchRequest(url="https://example.com")])

        # Add batch to scheduler
        await scheduler.add_batch(request)
        assert len(scheduler._queue) == 1

        # Get batch from scheduler
        next_batch = await scheduler.get_next_batch()
        assert next_batch is not None
        assert len(scheduler._queue) == 0

    @pytest.mark.asyncio
    async def test_scheduler_dependency_handling(self):
        """Test scheduler dependency handling."""
        config = BatchConfig(max_concurrent_batches=1)
        scheduler = BatchScheduler(config)

        from web_fetch.models import FetchRequest
        # Create a batch with dependencies
        request = BatchRequest(
            requests=[FetchRequest(url="https://example.com")],
            depends_on=["batch-1"]
        )
        await scheduler.add_batch(request)

        # Should be in waiting queue, not main queue
        assert len(scheduler._queue) == 0
        assert len(scheduler._waiting_batches) == 1


class TestBatchProcessor:
    """Test batch processor."""

    def test_processor_creation(self):
        """Test processor creation."""
        config = BatchConfig()
        processor = BatchProcessor(config)

        assert processor.config == config
        assert len(processor._active_batches) == 0

    @pytest.mark.asyncio
    async def test_processor_single_request(self):
        """Test processing single request."""
        config = BatchConfig()
        processor = BatchProcessor(config)

        from web_fetch.models import FetchRequest, ContentType
        request = BatchRequest(requests=[FetchRequest(url="https://httpbin.org/json")])

        with patch('web_fetch.batch.processor.WebFetcher') as mock_fetcher:
            mock_fetch_result = FetchResult(
                url="https://httpbin.org/json",
                content='{"test": "data"}',
                status_code=200,
                headers={"content-type": "application/json"},
                content_type=ContentType.JSON
            )

            mock_fetcher_instance = AsyncMock()
            mock_fetcher_instance.fetch_single.return_value = mock_fetch_result
            mock_fetcher.return_value.__aenter__.return_value = mock_fetcher_instance

            result = await processor.process_batch(request)

            assert result.status == BatchStatus.COMPLETED
            assert len(result.results) == 1

    @pytest.mark.asyncio
    async def test_processor_request_failure(self):
        """Test processing failed request."""
        config = BatchConfig()
        processor = BatchProcessor(config)
        
        fetch_request = FetchRequest(url="https://invalid-url.com")
        request = BatchRequest(requests=[fetch_request])
        
        with patch('web_fetch.batch.processor.WebFetcher') as mock_fetcher:
            mock_fetcher_instance = AsyncMock()
            mock_fetcher_instance.fetch_single.side_effect = WebFetchError("Network error")
            mock_fetcher.return_value.__aenter__.return_value = mock_fetcher_instance
            
            result = await processor.process_batch(request)

            assert result.status == BatchStatus.COMPLETED
            assert result.failed_requests == 1
            assert len(result.errors) > 0
            assert "Network error" in result.errors[0]

    @pytest.mark.asyncio
    async def test_processor_successful_request(self):
        """Test processor with successful request."""
        config = BatchConfig()
        processor = BatchProcessor(config)

        fetch_request = FetchRequest(url="https://example.com")
        request = BatchRequest(requests=[fetch_request])

        with patch('web_fetch.batch.processor.WebFetcher') as mock_fetcher:
            mock_fetcher_instance = AsyncMock()
            # Mock successful response
            mock_result = FetchResult(
                url="https://example.com",
                content="success",
                status_code=200,
                headers={},
                content_type=ContentType.HTML
            )
            mock_fetcher_instance.fetch_single.return_value = mock_result
            mock_fetcher.return_value.__aenter__.return_value = mock_fetcher_instance

            result = await processor.process_batch(request)

            assert result.status == BatchStatus.COMPLETED
            assert len(result.results) == 1
            assert result.successful_requests == 1
            assert result.failed_requests == 0


class TestBatchManager:
    """Test batch manager."""

    def test_manager_creation(self):
        """Test manager creation."""
        config = BatchConfig(max_concurrent_requests_per_batch=5)
        manager = BatchManager(config)

        assert manager.config == config
        assert manager._shutdown is False

    @pytest.mark.asyncio
    async def test_manager_submit_requests(self):
        """Test submitting requests to manager."""
        config = BatchConfig(max_concurrent_requests_per_batch=2)
        manager = BatchManager(config)

        fetch_requests = [
            FetchRequest(url="https://example1.com"),
            FetchRequest(url="https://example2.com")
        ]
        batch_request = BatchRequest(requests=fetch_requests)
        batch_id = await manager.submit_batch(batch_request)

        assert batch_id is not None
        assert len(manager._batches[batch_id].requests) == 2

    @pytest.mark.asyncio
    async def test_manager_get_results(self):
        """Test getting results from manager."""
        config = BatchConfig(max_concurrent_requests_per_batch=1)
        manager = BatchManager(config)
        
        with patch('web_fetch.batch.manager.BatchProcessor') as mock_processor_class:
            mock_processor = AsyncMock()
            mock_processor_class.return_value = mock_processor
            
            # Mock successful processing
            fetch_request = FetchRequest(url="https://example.com")
            batch_request = BatchRequest(requests=[fetch_request])
            mock_result = BatchResult(
                id=batch_request.id,
                status=BatchStatus.COMPLETED,
                total_requests=1
            )
            mock_processor.process_batch.return_value = mock_result
            
            fetch_requests = [FetchRequest(url="https://example.com")]
            batch_request = BatchRequest(requests=fetch_requests)
            batch_id = await manager.submit_batch(batch_request)

            await manager.start()

            # Wait a bit for processing
            await asyncio.sleep(0.1)

            result = await manager.get_batch_result(batch_id)

            # Check that the batch was submitted and is being tracked
            assert result is not None
            assert result.status in [BatchStatus.PENDING, BatchStatus.RUNNING, BatchStatus.COMPLETED]

            await manager.stop()

    @pytest.mark.asyncio
    async def test_manager_get_metrics(self):
        """Test getting metrics from manager."""
        config = BatchConfig()
        manager = BatchManager(config)

        metrics = manager.get_metrics()

        assert isinstance(metrics, BatchMetrics)
        assert metrics.uptime_seconds >= 0
        assert metrics.queued_batches >= 0
        assert metrics.running_batches >= 0

    @pytest.mark.asyncio
    async def test_manager_cancel_batch(self):
        """Test canceling a batch."""
        config = BatchConfig()
        manager = BatchManager(config)

        fetch_requests = [
            FetchRequest(url="https://example1.com"),
            FetchRequest(url="https://example2.com")
        ]
        batch_request = BatchRequest(requests=fetch_requests)
        batch_id = await manager.submit_batch(batch_request)

        success = await manager.cancel_batch(batch_id)

        assert success is True

        # Batch should be marked as cancelled
        result = await manager.get_batch_result(batch_id)
        assert result is not None
        assert result.status == BatchStatus.CANCELLED
