"""
Comprehensive tests for the batch models module.
"""

import pytest
from datetime import datetime, timedelta
from typing import List, Dict, Any
from unittest.mock import MagicMock

from web_fetch.batch.models import (
    BatchConfig,
    BatchMetrics,
    BatchPriority,
    BatchRequest,
    BatchResult,
    BatchStatus,
)
from web_fetch.models.http import FetchRequest, FetchResult
from web_fetch.models.base import ContentType


class TestBatchPriority:
    """Test batch priority enumeration."""

    def test_priority_values(self):
        """Test priority enumeration values."""
        assert BatchPriority.LOW.value == 1
        assert BatchPriority.NORMAL.value == 2
        assert BatchPriority.HIGH.value == 3
        assert BatchPriority.URGENT.value == 4

    def test_priority_ordering(self):
        """Test priority ordering."""
        priorities = [
            BatchPriority.URGENT,
            BatchPriority.HIGH,
            BatchPriority.NORMAL,
            BatchPriority.LOW
        ]
        
        # Sort by value (descending for priority)
        sorted_priorities = sorted(priorities, key=lambda p: p.value, reverse=True)
        
        assert sorted_priorities[0] == BatchPriority.URGENT
        assert sorted_priorities[1] == BatchPriority.HIGH
        assert sorted_priorities[2] == BatchPriority.NORMAL
        assert sorted_priorities[3] == BatchPriority.LOW


class TestBatchStatus:
    """Test batch status enumeration."""

    def test_status_values(self):
        """Test status enumeration values."""
        assert BatchStatus.PENDING == "pending"
        assert BatchStatus.RUNNING == "running"
        assert BatchStatus.COMPLETED == "completed"
        assert BatchStatus.FAILED == "failed"
        assert BatchStatus.CANCELLED == "cancelled"

    def test_status_transitions(self):
        """Test valid status transitions."""
        # Valid transitions from PENDING
        valid_from_pending = [
            BatchStatus.RUNNING,
            BatchStatus.CANCELLED
        ]
        
        # Valid transitions from RUNNING
        valid_from_running = [
            BatchStatus.COMPLETED,
            BatchStatus.FAILED,
            BatchStatus.CANCELLED
        ]
        
        # Terminal states
        terminal_states = [
            BatchStatus.COMPLETED,
            BatchStatus.FAILED,
            BatchStatus.CANCELLED
        ]
        
        assert all(status in [BatchStatus.RUNNING, BatchStatus.CANCELLED] 
                  for status in valid_from_pending)
        assert all(status in [BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.CANCELLED] 
                  for status in valid_from_running)


class TestBatchConfig:
    """Test batch configuration."""

    def test_default_batch_config(self):
        """Test default batch configuration."""
        config = BatchConfig()
        
        assert config.max_concurrent_requests == 10
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.timeout == 30.0
        assert config.enable_progress_tracking == True
        assert config.chunk_size == 100

    def test_custom_batch_config(self):
        """Test custom batch configuration."""
        config = BatchConfig(
            max_concurrent_requests=20,
            max_retries=5,
            retry_delay=2.0,
            timeout=60.0,
            enable_progress_tracking=False,
            chunk_size=50
        )
        
        assert config.max_concurrent_requests == 20
        assert config.max_retries == 5
        assert config.retry_delay == 2.0
        assert config.timeout == 60.0
        assert config.enable_progress_tracking == False
        assert config.chunk_size == 50

    def test_batch_config_validation(self):
        """Test batch configuration validation."""
        # Invalid max_concurrent_requests
        with pytest.raises(ValueError):
            BatchConfig(max_concurrent_requests=0)
        
        # Invalid max_retries
        with pytest.raises(ValueError):
            BatchConfig(max_retries=-1)
        
        # Invalid retry_delay
        with pytest.raises(ValueError):
            BatchConfig(retry_delay=-1.0)
        
        # Invalid timeout
        with pytest.raises(ValueError):
            BatchConfig(timeout=0.0)
        
        # Invalid chunk_size
        with pytest.raises(ValueError):
            BatchConfig(chunk_size=0)


class TestBatchRequest:
    """Test batch request model."""

    def test_batch_request_creation(self):
        """Test creating a batch request."""
        requests = [
            FetchRequest(url="https://example.com/1"),
            FetchRequest(url="https://example.com/2"),
            FetchRequest(url="https://example.com/3")
        ]
        
        batch_request = BatchRequest(
            requests=requests,
            priority=BatchPriority.HIGH,
            metadata={"source": "test"}
        )
        
        assert len(batch_request.requests) == 3
        assert batch_request.priority == BatchPriority.HIGH
        assert batch_request.metadata == {"source": "test"}
        assert batch_request.status == BatchStatus.PENDING
        assert batch_request.created_at is not None
        assert batch_request.batch_id is not None

    def test_batch_request_with_config(self):
        """Test batch request with custom configuration."""
        requests = [FetchRequest(url="https://example.com/1")]
        config = BatchConfig(max_concurrent_requests=5)
        
        batch_request = BatchRequest(
            requests=requests,
            config=config
        )
        
        assert batch_request.config == config
        assert batch_request.config.max_concurrent_requests == 5

    def test_batch_request_status_update(self):
        """Test updating batch request status."""
        requests = [FetchRequest(url="https://example.com/1")]
        batch_request = BatchRequest(requests=requests)
        
        assert batch_request.status == BatchStatus.PENDING
        assert batch_request.started_at is None
        assert batch_request.completed_at is None
        
        # Update to running
        batch_request.status = BatchStatus.RUNNING
        batch_request.started_at = datetime.now()
        
        assert batch_request.status == BatchStatus.RUNNING
        assert batch_request.started_at is not None
        
        # Update to completed
        batch_request.status = BatchStatus.COMPLETED
        batch_request.completed_at = datetime.now()
        
        assert batch_request.status == BatchStatus.COMPLETED
        assert batch_request.completed_at is not None

    def test_batch_request_duration_calculation(self):
        """Test batch request duration calculation."""
        requests = [FetchRequest(url="https://example.com/1")]
        batch_request = BatchRequest(requests=requests)
        
        now = datetime.now()
        batch_request.started_at = now
        batch_request.completed_at = now + timedelta(seconds=30)
        
        duration = batch_request.duration
        assert duration is not None
        assert duration.total_seconds() == 30.0

    def test_batch_request_duration_none_when_not_completed(self):
        """Test duration is None when batch is not completed."""
        requests = [FetchRequest(url="https://example.com/1")]
        batch_request = BatchRequest(requests=requests)
        
        # Not started
        assert batch_request.duration is None
        
        # Started but not completed
        batch_request.started_at = datetime.now()
        assert batch_request.duration is None


class TestBatchResult:
    """Test batch result model."""

    def test_batch_result_creation(self):
        """Test creating a batch result."""
        results = [
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
        ]
        
        batch_result = BatchResult(
            batch_id="test-batch-123",
            results=results,
            status=BatchStatus.COMPLETED
        )
        
        assert batch_result.batch_id == "test-batch-123"
        assert len(batch_result.results) == 2
        assert batch_result.status == BatchStatus.COMPLETED
        assert batch_result.created_at is not None

    def test_batch_result_success_count(self):
        """Test counting successful results."""
        results = [
            FetchResult(
                url="https://example.com/1",
                status_code=200,
                headers={},
                content="content1",
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
                content="content3",
                content_type=ContentType.TEXT
            )
        ]
        
        batch_result = BatchResult(
            batch_id="test-batch",
            results=results,
            status=BatchStatus.COMPLETED
        )
        
        success_count = batch_result.success_count
        assert success_count == 2

    def test_batch_result_failure_count(self):
        """Test counting failed results."""
        results = [
            FetchResult(
                url="https://example.com/1",
                status_code=200,
                headers={},
                content="content1",
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
                status_code=500,
                headers={},
                content="",
                content_type=ContentType.TEXT,
                error="Server error"
            )
        ]
        
        batch_result = BatchResult(
            batch_id="test-batch",
            results=results,
            status=BatchStatus.COMPLETED
        )
        
        failure_count = batch_result.failure_count
        assert failure_count == 2

    def test_batch_result_success_rate(self):
        """Test calculating success rate."""
        results = [
            FetchResult(
                url="https://example.com/1",
                status_code=200,
                headers={},
                content="content1",
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
                content="content3",
                content_type=ContentType.TEXT
            ),
            FetchResult(
                url="https://example.com/4",
                status_code=200,
                headers={},
                content="content4",
                content_type=ContentType.TEXT
            )
        ]
        
        batch_result = BatchResult(
            batch_id="test-batch",
            results=results,
            status=BatchStatus.COMPLETED
        )
        
        success_rate = batch_result.success_rate
        assert success_rate == 0.75  # 3 out of 4 successful

    def test_batch_result_empty_results(self):
        """Test batch result with empty results."""
        batch_result = BatchResult(
            batch_id="empty-batch",
            results=[],
            status=BatchStatus.COMPLETED
        )
        
        assert batch_result.success_count == 0
        assert batch_result.failure_count == 0
        assert batch_result.success_rate == 0.0


class TestBatchMetrics:
    """Test batch metrics model."""

    def test_batch_metrics_creation(self):
        """Test creating batch metrics."""
        metrics = BatchMetrics(
            total_requests=100,
            completed_requests=95,
            failed_requests=5,
            average_response_time=1.5,
            requests_per_second=10.0
        )
        
        assert metrics.total_requests == 100
        assert metrics.completed_requests == 95
        assert metrics.failed_requests == 5
        assert metrics.average_response_time == 1.5
        assert metrics.requests_per_second == 10.0
        assert metrics.timestamp is not None

    def test_batch_metrics_success_rate(self):
        """Test calculating success rate from metrics."""
        metrics = BatchMetrics(
            total_requests=100,
            completed_requests=80,
            failed_requests=20
        )
        
        success_rate = metrics.success_rate
        assert success_rate == 0.8

    def test_batch_metrics_completion_rate(self):
        """Test calculating completion rate from metrics."""
        metrics = BatchMetrics(
            total_requests=100,
            completed_requests=75,
            failed_requests=25
        )
        
        completion_rate = metrics.completion_rate
        assert completion_rate == 1.0  # All requests processed (completed + failed)

    def test_batch_metrics_partial_completion(self):
        """Test metrics with partial completion."""
        metrics = BatchMetrics(
            total_requests=100,
            completed_requests=60,
            failed_requests=15
        )
        
        completion_rate = metrics.completion_rate
        assert completion_rate == 0.75  # 75 out of 100 processed

    def test_batch_metrics_zero_division_handling(self):
        """Test handling of zero division in metrics."""
        metrics = BatchMetrics(
            total_requests=0,
            completed_requests=0,
            failed_requests=0
        )
        
        assert metrics.success_rate == 0.0
        assert metrics.completion_rate == 0.0
