"""
Comprehensive tests for the batch processor module.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

from web_fetch.batch.processor import BatchProcessor
from web_fetch.batch.models import (
    BatchRequest,
    BatchResult,
    BatchConfig,
    BatchPriority,
    BatchStatus,
    BatchMetrics,
)
from web_fetch.models.http import FetchRequest, FetchResult
from web_fetch.models.base import ContentType
from web_fetch.exceptions import WebFetchError, HTTPError


class TestBatchProcessor:
    """Test batch processor functionality."""

    def test_batch_processor_creation(self):
        """Test creating a batch processor."""
        config = BatchConfig(max_concurrent_requests=5)
        processor = BatchProcessor(config)
        
        assert processor.config == config
        assert processor.config.max_concurrent_requests == 5

    def test_batch_processor_default_config(self):
        """Test batch processor with default configuration."""
        processor = BatchProcessor()
        
        assert processor.config is not None
        assert processor.config.max_concurrent_requests == 10

    @pytest.mark.asyncio
    async def test_process_single_batch_success(self):
        """Test processing a single successful batch."""
        processor = BatchProcessor()
        
        # Mock the fetcher
        mock_fetcher = AsyncMock()
        mock_result = FetchResult(
            url="https://example.com/1",
            status_code=200,
            headers={"content-type": "text/plain"},
            content="test content",
            content_type=ContentType.TEXT
        )
        mock_fetcher.fetch_single.return_value = mock_result
        
        # Create batch request
        requests = [FetchRequest(url="https://example.com/1")]
        batch_request = BatchRequest(requests=requests)
        
        # Process batch
        with patch.object(processor, '_get_fetcher', return_value=mock_fetcher):
            result = await processor.process_batch(batch_request)
        
        assert isinstance(result, BatchResult)
        assert result.batch_id == batch_request.batch_id
        assert result.status == BatchStatus.COMPLETED
        assert len(result.results) == 1
        assert result.results[0] == mock_result

    @pytest.mark.asyncio
    async def test_process_multiple_requests_batch(self):
        """Test processing a batch with multiple requests."""
        processor = BatchProcessor()
        
        # Mock the fetcher
        mock_fetcher = AsyncMock()
        mock_results = [
            FetchResult(
                url=f"https://example.com/{i}",
                status_code=200,
                headers={"content-type": "text/plain"},
                content=f"content {i}",
                content_type=ContentType.TEXT
            )
            for i in range(1, 4)
        ]
        mock_fetcher.fetch_single.side_effect = mock_results
        
        # Create batch request with multiple URLs
        requests = [
            FetchRequest(url="https://example.com/1"),
            FetchRequest(url="https://example.com/2"),
            FetchRequest(url="https://example.com/3")
        ]
        batch_request = BatchRequest(requests=requests)
        
        # Process batch
        with patch.object(processor, '_get_fetcher', return_value=mock_fetcher):
            result = await processor.process_batch(batch_request)
        
        assert len(result.results) == 3
        assert result.status == BatchStatus.COMPLETED
        assert all(r.status_code == 200 for r in result.results)

    @pytest.mark.asyncio
    async def test_process_batch_with_failures(self):
        """Test processing a batch with some failures."""
        processor = BatchProcessor()
        
        # Mock the fetcher with mixed results
        mock_fetcher = AsyncMock()
        mock_results = [
            FetchResult(
                url="https://example.com/1",
                status_code=200,
                headers={"content-type": "text/plain"},
                content="success",
                content_type=ContentType.TEXT
            ),
            FetchResult(
                url="https://example.com/2",
                status_code=404,
                headers={},
                content="",
                content_type=ContentType.TEXT,
                error="Not found"
            ),
            FetchResult(
                url="https://example.com/3",
                status_code=200,
                headers={"content-type": "text/plain"},
                content="success",
                content_type=ContentType.TEXT
            )
        ]
        mock_fetcher.fetch_single.side_effect = mock_results
        
        # Create batch request
        requests = [
            FetchRequest(url="https://example.com/1"),
            FetchRequest(url="https://example.com/2"),
            FetchRequest(url="https://example.com/3")
        ]
        batch_request = BatchRequest(requests=requests)
        
        # Process batch
        with patch.object(processor, '_get_fetcher', return_value=mock_fetcher):
            result = await processor.process_batch(batch_request)
        
        assert len(result.results) == 3
        assert result.status == BatchStatus.COMPLETED
        assert result.success_count == 2
        assert result.failure_count == 1

    @pytest.mark.asyncio
    async def test_process_batch_with_exception(self):
        """Test processing a batch when an exception occurs."""
        processor = BatchProcessor()
        
        # Mock the fetcher to raise an exception
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch_single.side_effect = HTTPError("Server error", status_code=500)
        
        # Create batch request
        requests = [FetchRequest(url="https://example.com/1")]
        batch_request = BatchRequest(requests=requests)
        
        # Process batch
        with patch.object(processor, '_get_fetcher', return_value=mock_fetcher):
            result = await processor.process_batch(batch_request)
        
        assert result.status == BatchStatus.FAILED
        assert len(result.results) == 0
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_process_batch_with_timeout(self):
        """Test processing a batch with timeout."""
        config = BatchConfig(timeout=0.1)  # Very short timeout
        processor = BatchProcessor(config)
        
        # Mock the fetcher to be slow
        mock_fetcher = AsyncMock()
        
        async def slow_fetch(*args, **kwargs):
            await asyncio.sleep(0.2)  # Longer than timeout
            return FetchResult(
                url="https://example.com/1",
                status_code=200,
                headers={},
                content="content",
                content_type=ContentType.TEXT
            )
        
        mock_fetcher.fetch_single.side_effect = slow_fetch
        
        # Create batch request
        requests = [FetchRequest(url="https://example.com/1")]
        batch_request = BatchRequest(requests=requests)
        
        # Process batch
        with patch.object(processor, '_get_fetcher', return_value=mock_fetcher):
            result = await processor.process_batch(batch_request)
        
        assert result.status == BatchStatus.FAILED
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_process_batch_with_retries(self):
        """Test processing a batch with retry logic."""
        config = BatchConfig(max_retries=2, retry_delay=0.01)
        processor = BatchProcessor(config)
        
        # Mock the fetcher to fail first, then succeed
        mock_fetcher = AsyncMock()
        call_count = 0
        
        async def failing_then_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:  # Fail first 2 times
                raise HTTPError("Temporary error", status_code=500)
            return FetchResult(
                url="https://example.com/1",
                status_code=200,
                headers={},
                content="success after retry",
                content_type=ContentType.TEXT
            )
        
        mock_fetcher.fetch_single.side_effect = failing_then_success
        
        # Create batch request
        requests = [FetchRequest(url="https://example.com/1")]
        batch_request = BatchRequest(requests=requests)
        
        # Process batch
        with patch.object(processor, '_get_fetcher', return_value=mock_fetcher):
            result = await processor.process_batch(batch_request)
        
        assert result.status == BatchStatus.COMPLETED
        assert len(result.results) == 1
        assert result.results[0].content == "success after retry"
        assert call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_process_batch_max_retries_exceeded(self):
        """Test processing when max retries are exceeded."""
        config = BatchConfig(max_retries=1, retry_delay=0.01)
        processor = BatchProcessor(config)
        
        # Mock the fetcher to always fail
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch_single.side_effect = HTTPError("Persistent error", status_code=500)
        
        # Create batch request
        requests = [FetchRequest(url="https://example.com/1")]
        batch_request = BatchRequest(requests=requests)
        
        # Process batch
        with patch.object(processor, '_get_fetcher', return_value=mock_fetcher):
            result = await processor.process_batch(batch_request)
        
        assert result.status == BatchStatus.FAILED
        assert "max retries exceeded" in result.error.lower()

    @pytest.mark.asyncio
    async def test_process_batch_with_progress_callback(self):
        """Test processing a batch with progress callback."""
        processor = BatchProcessor()
        
        # Mock the fetcher
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch_single.return_value = FetchResult(
            url="https://example.com/1",
            status_code=200,
            headers={},
            content="content",
            content_type=ContentType.TEXT
        )
        
        # Create progress callback
        progress_calls = []
        
        def progress_callback(completed, total, current_url=None):
            progress_calls.append((completed, total, current_url))
        
        # Create batch request
        requests = [
            FetchRequest(url="https://example.com/1"),
            FetchRequest(url="https://example.com/2"),
            FetchRequest(url="https://example.com/3")
        ]
        batch_request = BatchRequest(requests=requests)
        
        # Process batch with progress callback
        with patch.object(processor, '_get_fetcher', return_value=mock_fetcher):
            result = await processor.process_batch(batch_request, progress_callback=progress_callback)
        
        assert result.status == BatchStatus.COMPLETED
        assert len(progress_calls) >= 3  # At least one call per request
        
        # Check that progress increased
        assert progress_calls[0][0] <= progress_calls[-1][0]
        assert all(call[1] == 3 for call in progress_calls)  # Total should always be 3

    @pytest.mark.asyncio
    async def test_process_batch_concurrency_limit(self):
        """Test that concurrency limit is respected."""
        config = BatchConfig(max_concurrent_requests=2)
        processor = BatchProcessor(config)
        
        # Track concurrent executions
        concurrent_count = 0
        max_concurrent = 0
        
        async def track_concurrency(*args, **kwargs):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            
            await asyncio.sleep(0.1)  # Simulate work
            
            concurrent_count -= 1
            return FetchResult(
                url=args[0].url,
                status_code=200,
                headers={},
                content="content",
                content_type=ContentType.TEXT
            )
        
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch_single.side_effect = track_concurrency
        
        # Create batch request with many URLs
        requests = [FetchRequest(url=f"https://example.com/{i}") for i in range(5)]
        batch_request = BatchRequest(requests=requests)
        
        # Process batch
        with patch.object(processor, '_get_fetcher', return_value=mock_fetcher):
            result = await processor.process_batch(batch_request)
        
        assert result.status == BatchStatus.COMPLETED
        assert max_concurrent <= 2  # Should not exceed concurrency limit

    @pytest.mark.asyncio
    async def test_process_batch_chunking(self):
        """Test processing large batches in chunks."""
        config = BatchConfig(chunk_size=3)
        processor = BatchProcessor(config)
        
        # Mock the fetcher
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch_single.return_value = FetchResult(
            url="https://example.com/test",
            status_code=200,
            headers={},
            content="content",
            content_type=ContentType.TEXT
        )
        
        # Create large batch request
        requests = [FetchRequest(url=f"https://example.com/{i}") for i in range(10)]
        batch_request = BatchRequest(requests=requests)
        
        # Process batch
        with patch.object(processor, '_get_fetcher', return_value=mock_fetcher):
            result = await processor.process_batch(batch_request)
        
        assert result.status == BatchStatus.COMPLETED
        assert len(result.results) == 10

    @pytest.mark.asyncio
    async def test_get_batch_metrics(self):
        """Test getting batch processing metrics."""
        processor = BatchProcessor()
        
        # Mock some processing history
        processor._total_processed = 100
        processor._total_successful = 85
        processor._total_failed = 15
        processor._total_processing_time = 150.0
        
        metrics = await processor.get_metrics()
        
        assert isinstance(metrics, BatchMetrics)
        assert metrics.total_requests == 100
        assert metrics.completed_requests == 85
        assert metrics.failed_requests == 15
        assert metrics.average_response_time == 1.5  # 150/100

    @pytest.mark.asyncio
    async def test_process_empty_batch(self):
        """Test processing an empty batch."""
        processor = BatchProcessor()
        
        # Create empty batch request
        batch_request = BatchRequest(requests=[])
        
        # Process batch
        result = await processor.process_batch(batch_request)
        
        assert result.status == BatchStatus.COMPLETED
        assert len(result.results) == 0
        assert result.success_count == 0
        assert result.failure_count == 0

    @pytest.mark.asyncio
    async def test_process_batch_cancellation(self):
        """Test cancelling batch processing."""
        processor = BatchProcessor()
        
        # Mock slow fetcher
        mock_fetcher = AsyncMock()
        
        async def slow_fetch(*args, **kwargs):
            await asyncio.sleep(1.0)  # Long operation
            return FetchResult(
                url="https://example.com/1",
                status_code=200,
                headers={},
                content="content",
                content_type=ContentType.TEXT
            )
        
        mock_fetcher.fetch_single.side_effect = slow_fetch
        
        # Create batch request
        requests = [FetchRequest(url="https://example.com/1")]
        batch_request = BatchRequest(requests=requests)
        
        # Start processing and cancel quickly
        with patch.object(processor, '_get_fetcher', return_value=mock_fetcher):
            task = asyncio.create_task(processor.process_batch(batch_request))
            await asyncio.sleep(0.1)  # Let it start
            task.cancel()
            
            with pytest.raises(asyncio.CancelledError):
                await task
