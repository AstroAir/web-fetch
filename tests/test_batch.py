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
from web_fetch.models import FetchConfig, FetchResult
from web_fetch.exceptions import WebFetchError


class TestBatchRequest:
    """Test batch request model."""

    def test_batch_request_creation(self):
        """Test batch request creation."""
        request = BatchRequest(
            url="https://example.com",
            priority=BatchPriority.HIGH,
            metadata={"source": "test"}
        )
        
        assert request.url == "https://example.com"
        assert request.priority == BatchPriority.HIGH
        assert request.metadata["source"] == "test"
        assert request.id is not None
        assert request.created_at is not None

    def test_batch_request_defaults(self):
        """Test batch request default values."""
        request = BatchRequest(url="https://example.com")
        
        assert request.priority == BatchPriority.NORMAL
        assert request.metadata == {}
        assert request.retry_count == 0
        assert request.max_retries == 3

    def test_batch_request_comparison(self):
        """Test batch request priority comparison."""
        high_req = BatchRequest(url="https://example.com", priority=BatchPriority.HIGH)
        normal_req = BatchRequest(url="https://example.com", priority=BatchPriority.NORMAL)
        low_req = BatchRequest(url="https://example.com", priority=BatchPriority.LOW)
        
        # Higher priority should be "less than" for min-heap behavior
        assert high_req < normal_req
        assert normal_req < low_req
        assert not (low_req < high_req)


class TestBatchResult:
    """Test batch result model."""

    def test_batch_result_success(self):
        """Test successful batch result."""
        request = BatchRequest(url="https://example.com")
        fetch_result = FetchResult(
            url="https://example.com",
            content="test content",
            status_code=200,
            headers={},
            content_type="text/html"
        )
        
        result = BatchResult(
            request=request,
            result=fetch_result,
            status=BatchStatus.COMPLETED,
            processing_time=1.5
        )
        
        assert result.request == request
        assert result.result == fetch_result
        assert result.status == BatchStatus.COMPLETED
        assert result.processing_time == 1.5
        assert result.error is None
        assert result.is_success is True

    def test_batch_result_failure(self):
        """Test failed batch result."""
        request = BatchRequest(url="https://example.com")
        error = WebFetchError("Network error")
        
        result = BatchResult(
            request=request,
            status=BatchStatus.FAILED,
            error=error,
            processing_time=0.5
        )
        
        assert result.request == request
        assert result.result is None
        assert result.status == BatchStatus.FAILED
        assert result.error == error
        assert result.is_success is False


class TestBatchConfig:
    """Test batch configuration."""

    def test_batch_config_defaults(self):
        """Test default batch configuration."""
        config = BatchConfig()
        
        assert config.max_concurrent_requests == 10
        assert config.request_timeout == 30.0
        assert config.retry_delay == 1.0
        assert config.max_retries == 3
        assert config.enable_rate_limiting is True

    def test_batch_config_validation(self):
        """Test batch configuration validation."""
        # Valid config
        config = BatchConfig(
            max_concurrent_requests=5,
            request_timeout=60.0,
            retry_delay=2.0
        )
        
        assert config.max_concurrent_requests == 5
        assert config.request_timeout == 60.0
        assert config.retry_delay == 2.0

    def test_batch_config_invalid_values(self):
        """Test batch configuration with invalid values."""
        with pytest.raises(ValueError):
            BatchConfig(max_concurrent_requests=0)
        
        with pytest.raises(ValueError):
            BatchConfig(request_timeout=-1.0)


class TestPriorityQueue:
    """Test priority queue implementation."""

    def test_priority_queue_basic_operations(self):
        """Test basic priority queue operations."""
        queue = PriorityQueue()
        
        # Test empty queue
        assert queue.empty() is True
        assert queue.size() == 0
        
        # Add items
        high_req = BatchRequest(url="https://high.com", priority=BatchPriority.HIGH)
        normal_req = BatchRequest(url="https://normal.com", priority=BatchPriority.NORMAL)
        low_req = BatchRequest(url="https://low.com", priority=BatchPriority.LOW)
        
        queue.put(normal_req)
        queue.put(high_req)
        queue.put(low_req)
        
        assert queue.size() == 3
        assert queue.empty() is False
        
        # Items should come out in priority order (high first)
        first = queue.get()
        second = queue.get()
        third = queue.get()
        
        assert first.priority == BatchPriority.HIGH
        assert second.priority == BatchPriority.NORMAL
        assert third.priority == BatchPriority.LOW

    def test_priority_queue_thread_safety(self):
        """Test priority queue thread safety."""
        queue = PriorityQueue()
        
        def producer():
            for i in range(10):
                req = BatchRequest(url=f"https://example{i}.com")
                queue.put(req)
        
        def consumer():
            items = []
            for _ in range(10):
                items.append(queue.get())
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
        config = BatchConfig(max_concurrent_requests=5)
        scheduler = BatchScheduler(config)
        
        assert scheduler.config == config
        assert scheduler._running is False
        assert len(scheduler._active_requests) == 0

    @pytest.mark.asyncio
    async def test_scheduler_add_request(self):
        """Test adding requests to scheduler."""
        config = BatchConfig(max_concurrent_requests=2)
        scheduler = BatchScheduler(config)
        
        request1 = BatchRequest(url="https://example1.com")
        request2 = BatchRequest(url="https://example2.com", priority=BatchPriority.HIGH)
        
        await scheduler.add_request(request1)
        await scheduler.add_request(request2)
        
        assert scheduler.get_queue_size() == 2
        
        # High priority request should be first
        next_req = await scheduler.get_next_request()
        assert next_req.priority == BatchPriority.HIGH

    @pytest.mark.asyncio
    async def test_scheduler_start_stop(self):
        """Test scheduler start and stop."""
        config = BatchConfig(max_concurrent_requests=1)
        scheduler = BatchScheduler(config)
        
        # Start scheduler
        await scheduler.start()
        assert scheduler._running is True
        
        # Stop scheduler
        await scheduler.stop()
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_scheduler_request_processing(self):
        """Test scheduler request processing."""
        config = BatchConfig(max_concurrent_requests=1)
        scheduler = BatchScheduler(config)
        
        request = BatchRequest(url="https://example.com")
        await scheduler.add_request(request)
        
        # Mark request as processing
        await scheduler.mark_processing(request)
        assert request.id in scheduler._active_requests
        
        # Complete request
        result = BatchResult(
            request=request,
            status=BatchStatus.COMPLETED,
            processing_time=1.0
        )
        await scheduler.mark_completed(request, result)
        assert request.id not in scheduler._active_requests


class TestBatchProcessor:
    """Test batch processor."""

    def test_processor_creation(self):
        """Test processor creation."""
        config = BatchConfig()
        processor = BatchProcessor(config)
        
        assert processor.config == config
        assert processor._running is False

    @pytest.mark.asyncio
    async def test_processor_single_request(self):
        """Test processing single request."""
        config = BatchConfig()
        processor = BatchProcessor(config)
        
        request = BatchRequest(url="https://httpbin.org/json")
        
        with patch('web_fetch.batch.processor.WebFetcher') as mock_fetcher:
            mock_fetch_result = FetchResult(
                url="https://httpbin.org/json",
                content='{"test": "data"}',
                status_code=200,
                headers={"content-type": "application/json"},
                content_type="application/json"
            )
            
            mock_fetcher_instance = AsyncMock()
            mock_fetcher_instance.fetch.return_value = mock_fetch_result
            mock_fetcher.return_value.__aenter__.return_value = mock_fetcher_instance
            
            result = await processor.process_request(request)
            
            assert result.status == BatchStatus.COMPLETED
            assert result.result == mock_fetch_result
            assert result.error is None

    @pytest.mark.asyncio
    async def test_processor_request_failure(self):
        """Test processing failed request."""
        config = BatchConfig()
        processor = BatchProcessor(config)
        
        request = BatchRequest(url="https://invalid-url.com")
        
        with patch('web_fetch.batch.processor.WebFetcher') as mock_fetcher:
            mock_fetcher_instance = AsyncMock()
            mock_fetcher_instance.fetch.side_effect = WebFetchError("Network error")
            mock_fetcher.return_value.__aenter__.return_value = mock_fetcher_instance
            
            result = await processor.process_request(request)
            
            assert result.status == BatchStatus.FAILED
            assert result.result is None
            assert isinstance(result.error, WebFetchError)

    @pytest.mark.asyncio
    async def test_processor_retry_logic(self):
        """Test processor retry logic."""
        config = BatchConfig(max_retries=2, retry_delay=0.1)
        processor = BatchProcessor(config)
        
        request = BatchRequest(url="https://example.com", max_retries=2)
        
        with patch('web_fetch.batch.processor.WebFetcher') as mock_fetcher:
            mock_fetcher_instance = AsyncMock()
            # First two calls fail, third succeeds
            mock_fetcher_instance.fetch.side_effect = [
                WebFetchError("Temporary error"),
                WebFetchError("Another error"),
                FetchResult(
                    url="https://example.com",
                    content="success",
                    status_code=200,
                    headers={},
                    content_type="text/html"
                )
            ]
            mock_fetcher.return_value.__aenter__.return_value = mock_fetcher_instance
            
            result = await processor.process_request(request)
            
            assert result.status == BatchStatus.COMPLETED
            assert result.result.content == "success"
            assert request.retry_count == 2


class TestBatchManager:
    """Test batch manager."""

    def test_manager_creation(self):
        """Test manager creation."""
        config = BatchConfig(max_concurrent_requests=5)
        manager = BatchManager(config)
        
        assert manager.config == config
        assert manager._running is False

    @pytest.mark.asyncio
    async def test_manager_submit_requests(self):
        """Test submitting requests to manager."""
        config = BatchConfig(max_concurrent_requests=2)
        manager = BatchManager(config)
        
        urls = ["https://example1.com", "https://example2.com"]
        batch_id = await manager.submit_batch(urls)
        
        assert batch_id is not None
        assert len(manager._batches[batch_id]) == 2

    @pytest.mark.asyncio
    async def test_manager_get_results(self):
        """Test getting results from manager."""
        config = BatchConfig(max_concurrent_requests=1)
        manager = BatchManager(config)
        
        with patch('web_fetch.batch.manager.BatchProcessor') as mock_processor_class:
            mock_processor = AsyncMock()
            mock_processor_class.return_value = mock_processor
            
            # Mock successful processing
            mock_result = BatchResult(
                request=BatchRequest(url="https://example.com"),
                status=BatchStatus.COMPLETED,
                processing_time=1.0
            )
            mock_processor.process_request.return_value = mock_result
            
            urls = ["https://example.com"]
            batch_id = await manager.submit_batch(urls)
            
            await manager.start()
            
            # Wait a bit for processing
            await asyncio.sleep(0.1)
            
            results = await manager.get_results(batch_id)
            
            await manager.stop()
            
            assert len(results) == 1
            assert results[0].status == BatchStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_manager_get_metrics(self):
        """Test getting metrics from manager."""
        config = BatchConfig()
        manager = BatchManager(config)
        
        metrics = await manager.get_metrics()
        
        assert isinstance(metrics, BatchMetrics)
        assert metrics.total_requests >= 0
        assert metrics.completed_requests >= 0
        assert metrics.failed_requests >= 0

    @pytest.mark.asyncio
    async def test_manager_cancel_batch(self):
        """Test canceling a batch."""
        config = BatchConfig()
        manager = BatchManager(config)
        
        urls = ["https://example1.com", "https://example2.com"]
        batch_id = await manager.submit_batch(urls)
        
        success = await manager.cancel_batch(batch_id)
        
        assert success is True
        
        # Batch should be marked as cancelled
        results = await manager.get_results(batch_id)
        for result in results:
            if result.status != BatchStatus.PENDING:
                assert result.status == BatchStatus.CANCELLED
