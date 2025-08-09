"""
Data models for batch operations.

This module defines all data models and types for batch processing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field

from ..models import FetchRequest, FetchResult


class BatchPriority(Enum):
    """Priority levels for batch requests."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class BatchStatus(Enum):
    """Status of batch operations."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


@dataclass
class BatchRequest:
    """Enhanced batch request with priority and metadata."""

    id: str = field(default_factory=lambda: str(uuid4()))
    requests: List[FetchRequest] = field(default_factory=list)
    priority: BatchPriority = BatchPriority.NORMAL
    max_concurrent: int = 10
    timeout: float = 300.0
    retry_failed: bool = True

    # Metadata
    name: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    # Callbacks
    progress_callback: Optional[Callable[..., Any]] = None
    completion_callback: Optional[Callable[..., Any]] = None
    error_callback: Optional[Callable[..., Any]] = None

    # Dependencies
    depends_on: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Post-initialization processing."""
        if not self.requests:
            raise ValueError("Batch request must contain at least one request")


@dataclass
class BatchResult:
    """Enhanced batch result with detailed metrics."""

    id: str
    status: BatchStatus
    results: List[FetchResult] = field(default_factory=list)

    # Timing
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    total_time: float = 0.0

    # Metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    retried_requests: int = 0

    # Performance metrics
    average_response_time: float = 0.0
    min_response_time: float = 0.0
    max_response_time: float = 0.0
    total_bytes_downloaded: int = 0

    # Error information
    errors: List[str] = field(default_factory=list)
    failed_urls: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def is_complete(self) -> bool:
        """Check if batch is complete."""
        return self.status in [
            BatchStatus.COMPLETED,
            BatchStatus.FAILED,
            BatchStatus.CANCELLED,
        ]

    def add_result(self, result: FetchResult) -> None:
        """Add a fetch result to the batch."""
        self.results.append(result)
        self.total_requests += 1

        if result.is_success:
            self.successful_requests += 1
            if result.response_time:
                self._update_timing_metrics(result.response_time)
            if hasattr(result, "bytes_downloaded") and result.bytes_downloaded:
                self.total_bytes_downloaded += result.bytes_downloaded
        else:
            self.failed_requests += 1
            if result.error:
                self.errors.append(result.error)
            if result.url:
                self.failed_urls.append(str(result.url))

    def _update_timing_metrics(self, response_time: float) -> None:
        """Update timing metrics with new response time."""
        if self.successful_requests == 1:
            # First successful request
            self.min_response_time = response_time
            self.max_response_time = response_time
            self.average_response_time = response_time
        else:
            # Update metrics
            self.min_response_time = min(self.min_response_time, response_time)
            self.max_response_time = max(self.max_response_time, response_time)

            # Update average (incremental calculation)
            old_avg = self.average_response_time
            self.average_response_time = (
                old_avg * (self.successful_requests - 1) + response_time
            ) / self.successful_requests


class BatchConfig(BaseModel):
    """Configuration for batch operations."""

    # Concurrency settings
    max_concurrent_batches: int = Field(
        default=5, description="Maximum concurrent batches", gt=0
    )
    max_concurrent_requests_per_batch: int = Field(
        default=10, description="Max concurrent requests per batch", gt=0
    )

    # Queue settings
    max_queue_size: int = Field(default=1000, description="Maximum queue size")
    priority_queue_enabled: bool = Field(
        default=True, description="Enable priority queue"
    )

    # Retry settings
    max_batch_retries: int = Field(
        default=3, description="Maximum batch retry attempts"
    )
    retry_delay: float = Field(default=5.0, description="Delay between batch retries")

    # Timeout settings
    batch_timeout: float = Field(
        default=3600.0, description="Maximum batch execution time", gt=0
    )
    request_timeout: float = Field(default=30.0, description="Default request timeout", gt=0)

    # Resource management
    memory_limit_mb: int = Field(default=1024, description="Memory limit in MB")
    disk_cache_enabled: bool = Field(default=True, description="Enable disk caching")

    # Monitoring
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    enable_progress_tracking: bool = Field(
        default=True, description="Enable progress tracking"
    )

    # Persistence
    persist_results: bool = Field(default=False, description="Persist results to disk")
    results_directory: Optional[str] = Field(
        default=None, description="Results directory"
    )


@dataclass
class BatchMetrics:
    """Metrics for batch operations."""

    # Queue metrics
    queued_batches: int = 0
    running_batches: int = 0
    completed_batches: int = 0
    failed_batches: int = 0

    # Request metrics
    total_requests_processed: int = 0
    successful_requests: int = 0
    failed_requests: int = 0

    # Performance metrics
    average_batch_time: float = 0.0
    average_request_time: float = 0.0
    total_bytes_processed: int = 0

    # Resource metrics
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0

    # Timing
    uptime_seconds: float = 0.0
    last_updated: float = field(default_factory=time.time)

    @property
    def total_batches(self) -> int:
        """Total number of batches processed."""
        return self.completed_batches + self.failed_batches

    @property
    def batch_success_rate(self) -> float:
        """Batch success rate."""
        total = self.total_batches
        if total == 0:
            return 0.0
        return self.completed_batches / total

    @property
    def request_success_rate(self) -> float:
        """Request success rate."""
        total = self.total_requests_processed
        if total == 0:
            return 0.0
        return self.successful_requests / total


@dataclass
class BatchProgress:
    """Progress information for batch operations."""

    batch_id: str
    total_requests: int
    completed_requests: int
    failed_requests: int
    current_request: Optional[str] = None

    # Timing
    started_at: float = field(default_factory=time.time)
    estimated_completion: Optional[float] = None

    @property
    def progress_percent(self) -> float:
        """Progress as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (
            (self.completed_requests + self.failed_requests) / self.total_requests * 100
        )

    @property
    def is_complete(self) -> bool:
        """Check if batch is complete."""
        return (self.completed_requests + self.failed_requests) >= self.total_requests

    def estimate_completion(self) -> None:
        """Estimate completion time based on current progress."""
        if self.completed_requests == 0:
            return

        elapsed = time.time() - self.started_at
        rate = self.completed_requests / elapsed
        remaining = self.total_requests - self.completed_requests - self.failed_requests

        if rate > 0:
            self.estimated_completion = time.time() + (remaining / rate)
