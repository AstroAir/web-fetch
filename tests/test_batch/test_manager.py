"""
Comprehensive tests for the batch manager module.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Callable

from web_fetch.batch.manager import BatchManager
from web_fetch.batch.models import (
    BatchRequest,
    BatchResult,
    BatchConfig,
    BatchPriority,
    BatchStatus,
    BatchMetrics,
)
from web_fetch.batch.scheduler import BatchScheduler
from web_fetch.models.http import FetchRequest, FetchResult
from web_fetch.models.base import ContentType


class TestBatchManager:
    """Test batch manager functionality."""

    def test_batch_manager_creation(self):
        """Test creating a batch manager."""
        config = BatchConfig(max_concurrent_requests=5)
        manager = BatchManager(config)
        
        assert manager.config == config
        assert isinstance(manager.scheduler, BatchScheduler)

    def test_batch_manager_default_config(self):
        """Test batch manager with default configuration."""
        manager = BatchManager()
        
        assert manager.config is not None
        assert manager.config.max_concurrent_requests == 10

    @pytest.mark.asyncio
    async def test_submit_urls_as_batch(self):
        """Test submitting URLs as a batch."""
        manager = BatchManager()
        
        urls = [
            "https://example.com/1",
            "https://example.com/2",
            "https://example.com/3"
        ]
        
        # Submit URLs
        batch_id = await manager.submit_urls(urls, priority=BatchPriority.HIGH)
        
        assert batch_id is not None
        assert isinstance(batch_id, str)

    @pytest.mark.asyncio
    async def test_submit_requests_as_batch(self):
        """Test submitting fetch requests as a batch."""
        manager = BatchManager()
        
        requests = [
            FetchRequest(url="https://example.com/1"),
            FetchRequest(url="https://example.com/2"),
            FetchRequest(url="https://example.com/3")
        ]
        
        # Submit requests
        batch_id = await manager.submit_requests(requests, priority=BatchPriority.NORMAL)
        
        assert batch_id is not None
        assert isinstance(batch_id, str)

    @pytest.mark.asyncio
    async def test_submit_batch_with_metadata(self):
        """Test submitting batch with metadata."""
        manager = BatchManager()
        
        urls = ["https://example.com/1", "https://example.com/2"]
        metadata = {"source": "test", "category": "api"}
        
        batch_id = await manager.submit_urls(
            urls,
            priority=BatchPriority.HIGH,
            metadata=metadata
        )
        
        assert batch_id is not None

    @pytest.mark.asyncio
    async def test_submit_batch_with_custom_config(self):
        """Test submitting batch with custom configuration."""
        manager = BatchManager()
        
        urls = ["https://example.com/1"]
        custom_config = BatchConfig(
            max_concurrent_requests=2,
            timeout=60.0
        )
        
        batch_id = await manager.submit_urls(
            urls,
            config=custom_config
        )
        
        assert batch_id is not None

    @pytest.mark.asyncio
    async def test_get_batch_status(self):
        """Test getting batch status."""
        manager = BatchManager()
        
        # Mock scheduler
        with patch.object(manager.scheduler, 'get_batch_status', return_value=BatchStatus.PENDING) as mock_status:
            urls = ["https://example.com/1"]
            batch_id = await manager.submit_urls(urls)
            
            status = await manager.get_batch_status(batch_id)
            assert status == BatchStatus.PENDING
            mock_status.assert_called_with(batch_id)

    @pytest.mark.asyncio
    async def test_get_batch_result(self):
        """Test getting batch result."""
        manager = BatchManager()
        
        # Mock result
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
        
        with patch.object(manager.scheduler, 'get_batch_result', return_value=mock_result) as mock_get_result:
            batch_id = "test-batch"
            result = await manager.get_batch_result(batch_id)
            
            assert result == mock_result
            mock_get_result.assert_called_with(batch_id)

    @pytest.mark.asyncio
    async def test_cancel_batch(self):
        """Test cancelling a batch."""
        manager = BatchManager()
        
        with patch.object(manager.scheduler, 'cancel_batch', return_value=True) as mock_cancel:
            batch_id = "test-batch"
            success = await manager.cancel_batch(batch_id)
            
            assert success == True
            mock_cancel.assert_called_with(batch_id)

    @pytest.mark.asyncio
    async def test_wait_for_batch_completion(self):
        """Test waiting for batch completion."""
        manager = BatchManager()
        
        # Mock scheduler to return different statuses
        status_sequence = [
            BatchStatus.PENDING,
            BatchStatus.RUNNING,
            BatchStatus.COMPLETED
        ]
        
        with patch.object(manager.scheduler, 'get_batch_status', side_effect=status_sequence):
            batch_id = "test-batch"
            final_status = await manager.wait_for_batch(batch_id, poll_interval=0.01)
            
            assert final_status == BatchStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_wait_for_batch_with_timeout(self):
        """Test waiting for batch with timeout."""
        manager = BatchManager()
        
        # Mock scheduler to always return RUNNING
        with patch.object(manager.scheduler, 'get_batch_status', return_value=BatchStatus.RUNNING):
            batch_id = "test-batch"
            
            # Should timeout
            final_status = await manager.wait_for_batch(
                batch_id,
                timeout=0.05,
                poll_interval=0.01
            )
            
            assert final_status == BatchStatus.RUNNING  # Still running when timeout

    @pytest.mark.asyncio
    async def test_wait_for_batch_failure(self):
        """Test waiting for batch that fails."""
        manager = BatchManager()
        
        # Mock scheduler to return failure
        status_sequence = [
            BatchStatus.PENDING,
            BatchStatus.RUNNING,
            BatchStatus.FAILED
        ]
        
        with patch.object(manager.scheduler, 'get_batch_status', side_effect=status_sequence):
            batch_id = "test-batch"
            final_status = await manager.wait_for_batch(batch_id, poll_interval=0.01)
            
            assert final_status == BatchStatus.FAILED

    @pytest.mark.asyncio
    async def test_process_urls_and_wait(self):
        """Test processing URLs and waiting for completion."""
        manager = BatchManager()
        
        # Mock successful processing
        mock_result = BatchResult(
            batch_id="test-batch",
            results=[
                FetchResult(
                    url="https://example.com/1",
                    status_code=200,
                    headers={},
                    content="content1",
                    content_type=ContentType.TEXT
                ),
                FetchResult(
                    url="https://example.com/2",
                    status_code=200,
                    headers={},
                    content="content2",
                    content_type=ContentType.TEXT
                )
            ],
            status=BatchStatus.COMPLETED
        )
        
        with patch.object(manager.scheduler, 'get_batch_status', return_value=BatchStatus.COMPLETED), \
             patch.object(manager.scheduler, 'get_batch_result', return_value=mock_result):
            
            urls = ["https://example.com/1", "https://example.com/2"]
            result = await manager.process_urls_and_wait(urls)
            
            assert result == mock_result
            assert len(result.results) == 2

    @pytest.mark.asyncio
    async def test_process_requests_and_wait(self):
        """Test processing requests and waiting for completion."""
        manager = BatchManager()
        
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
        
        with patch.object(manager.scheduler, 'get_batch_status', return_value=BatchStatus.COMPLETED), \
             patch.object(manager.scheduler, 'get_batch_result', return_value=mock_result):
            
            requests = [FetchRequest(url="https://example.com/1")]
            result = await manager.process_requests_and_wait(requests)
            
            assert result == mock_result

    @pytest.mark.asyncio
    async def test_list_active_batches(self):
        """Test listing active batches."""
        manager = BatchManager()
        
        # Mock active batches
        mock_batches = [
            BatchRequest(
                requests=[FetchRequest(url="https://example.com/1")],
                priority=BatchPriority.HIGH
            ),
            BatchRequest(
                requests=[FetchRequest(url="https://example.com/2")],
                priority=BatchPriority.NORMAL
            )
        ]
        
        with patch.object(manager.scheduler, 'list_active_batches', return_value=mock_batches) as mock_list:
            active_batches = await manager.list_active_batches()
            
            assert active_batches == mock_batches
            mock_list.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_queue_statistics(self):
        """Test getting queue statistics."""
        manager = BatchManager()
        
        # Mock statistics
        mock_stats = {
            'total_items': 5,
            'priority_counts': {
                BatchPriority.LOW: 1,
                BatchPriority.NORMAL: 2,
                BatchPriority.HIGH: 1,
                BatchPriority.URGENT: 1
            }
        }
        
        with patch.object(manager.scheduler, 'get_queue_statistics', return_value=mock_stats) as mock_stats_call:
            stats = await manager.get_queue_statistics()
            
            assert stats == mock_stats
            mock_stats_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_processing_metrics(self):
        """Test getting processing metrics."""
        manager = BatchManager()
        
        # Mock metrics
        mock_metrics = BatchMetrics(
            total_requests=100,
            completed_requests=85,
            failed_requests=15,
            average_response_time=1.5,
            requests_per_second=10.0
        )
        
        with patch.object(manager.scheduler.processor, 'get_metrics', return_value=mock_metrics) as mock_metrics_call:
            metrics = await manager.get_processing_metrics()
            
            assert metrics == mock_metrics
            mock_metrics_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_and_stop_manager(self):
        """Test starting and stopping the manager."""
        manager = BatchManager()
        
        with patch.object(manager.scheduler, 'start') as mock_start, \
             patch.object(manager.scheduler, 'stop') as mock_stop:
            
            # Start manager
            await manager.start()
            mock_start.assert_called_once()
            
            # Stop manager
            await manager.stop()
            mock_stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_usage(self):
        """Test using manager as async context manager."""
        config = BatchConfig(max_concurrent_requests=5)
        
        with patch.object(BatchScheduler, 'start') as mock_start, \
             patch.object(BatchScheduler, 'stop') as mock_stop:
            
            async with BatchManager(config) as manager:
                assert isinstance(manager, BatchManager)
                assert manager.config == config
            
            mock_start.assert_called_once()
            mock_stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_with_progress_callback(self):
        """Test submitting batch with progress callback."""
        manager = BatchManager()
        
        progress_updates = []
        
        def progress_callback(batch_id, completed, total, current_url=None):
            progress_updates.append((batch_id, completed, total, current_url))
        
        with patch.object(manager.scheduler, 'submit_batch') as mock_submit:
            urls = ["https://example.com/1", "https://example.com/2"]
            
            batch_id = await manager.submit_urls(
                urls,
                progress_callback=progress_callback
            )
            
            mock_submit.assert_called_once()
            # Check that progress callback was passed
            call_args = mock_submit.call_args
            assert 'progress_callback' in call_args.kwargs

    @pytest.mark.asyncio
    async def test_batch_with_custom_headers(self):
        """Test submitting batch with custom headers."""
        manager = BatchManager()
        
        urls = ["https://example.com/1"]
        headers = {"Authorization": "Bearer token", "User-Agent": "test-agent"}
        
        batch_id = await manager.submit_urls(urls, headers=headers)
        
        assert batch_id is not None

    @pytest.mark.asyncio
    async def test_batch_error_handling(self):
        """Test batch error handling."""
        manager = BatchManager()
        
        # Mock scheduler to raise an exception
        with patch.object(manager.scheduler, 'submit_batch', side_effect=Exception("Submission failed")):
            urls = ["https://example.com/1"]
            
            with pytest.raises(Exception, match="Submission failed"):
                await manager.submit_urls(urls)

    @pytest.mark.asyncio
    async def test_empty_batch_handling(self):
        """Test handling of empty batches."""
        manager = BatchManager()
        
        # Submit empty URL list
        with pytest.raises(ValueError, match="empty"):
            await manager.submit_urls([])
        
        # Submit empty request list
        with pytest.raises(ValueError, match="empty"):
            await manager.submit_requests([])

    @pytest.mark.asyncio
    async def test_batch_result_filtering(self):
        """Test filtering batch results."""
        manager = BatchManager()
        
        # Mock result with mixed success/failure
        mock_result = BatchResult(
            batch_id="test-batch",
            results=[
                FetchResult(
                    url="https://example.com/1",
                    status_code=200,
                    headers={},
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
                    headers={},
                    content="success",
                    content_type=ContentType.TEXT
                )
            ],
            status=BatchStatus.COMPLETED
        )
        
        # Test filtering successful results
        successful_results = manager.filter_successful_results(mock_result)
        assert len(successful_results) == 2
        assert all(r.status_code == 200 for r in successful_results)
        
        # Test filtering failed results
        failed_results = manager.filter_failed_results(mock_result)
        assert len(failed_results) == 1
        assert failed_results[0].status_code == 404

    @pytest.mark.asyncio
    async def test_batch_statistics_calculation(self):
        """Test batch statistics calculation."""
        manager = BatchManager()
        
        # Mock result
        mock_result = BatchResult(
            batch_id="test-batch",
            results=[
                FetchResult(url="https://example.com/1", status_code=200, headers={}, content="", content_type=ContentType.TEXT),
                FetchResult(url="https://example.com/2", status_code=404, headers={}, content="", content_type=ContentType.TEXT, error="Not found"),
                FetchResult(url="https://example.com/3", status_code=200, headers={}, content="", content_type=ContentType.TEXT),
                FetchResult(url="https://example.com/4", status_code=500, headers={}, content="", content_type=ContentType.TEXT, error="Server error")
            ],
            status=BatchStatus.COMPLETED
        )
        
        stats = manager.calculate_batch_statistics(mock_result)
        
        assert stats['total_requests'] == 4
        assert stats['successful_requests'] == 2
        assert stats['failed_requests'] == 2
        assert stats['success_rate'] == 0.5
        assert stats['status_code_distribution'][200] == 2
        assert stats['status_code_distribution'][404] == 1
        assert stats['status_code_distribution'][500] == 1
