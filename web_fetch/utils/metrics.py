"""
Metrics collection and monitoring utilities for the web_fetch library.

This module provides comprehensive metrics collection for monitoring
request performance, success rates, and system health.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, List, Optional
from urllib.parse import urlparse


@dataclass
class RequestMetrics:
    """Metrics for a single request."""

    url: str
    method: str
    status_code: int
    response_time: float
    response_size: int
    timestamp: datetime
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        """Check if request was successful."""
        return 200 <= self.status_code < 300 and self.error is None

    @property
    def is_client_error(self) -> bool:
        """Check if request was a client error (4xx)."""
        return 400 <= self.status_code < 500

    @property
    def is_server_error(self) -> bool:
        """Check if request was a server error (5xx)."""
        return 500 <= self.status_code < 600


@dataclass
class AggregatedMetrics:
    """Aggregated metrics over a time period."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    client_errors: int = 0
    server_errors: int = 0

    total_response_time: float = 0.0
    total_response_size: int = 0

    min_response_time: float = float("inf")
    max_response_time: float = 0.0

    status_code_counts: Dict[int, int] = field(default_factory=lambda: defaultdict(int))
    error_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    host_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def average_response_time(self) -> float:
        """Calculate average response time."""
        if self.total_requests == 0:
            return 0.0
        return self.total_response_time / self.total_requests

    @property
    def average_response_size(self) -> float:
        """Calculate average response size."""
        if self.total_requests == 0:
            return 0.0
        return self.total_response_size / self.total_requests

    def add_request(self, metrics: RequestMetrics) -> None:
        """Add a request to the aggregated metrics."""
        self.total_requests += 1

        if metrics.is_success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

            if metrics.is_client_error:
                self.client_errors += 1
            elif metrics.is_server_error:
                self.server_errors += 1

        # Update response time stats
        self.total_response_time += metrics.response_time
        self.min_response_time = min(self.min_response_time, metrics.response_time)
        self.max_response_time = max(self.max_response_time, metrics.response_time)

        # Update response size
        self.total_response_size += metrics.response_size

        # Update counts
        self.status_code_counts[metrics.status_code] += 1

        if metrics.error:
            self.error_counts[metrics.error] += 1

        # Extract host from URL
        try:
            parsed = urlparse(metrics.url)
            host = parsed.netloc or parsed.hostname or "unknown"
            self.host_counts[host] += 1
        except Exception:
            self.host_counts["unknown"] += 1


class MetricsCollector:
    """Collects and aggregates request metrics."""

    def __init__(self, max_history: int = 10000, retention_hours: int = 24):
        """
        Initialize metrics collector.

        Args:
            max_history: Maximum number of individual metrics to keep
            retention_hours: Hours to retain metrics data
        """
        self.max_history = max_history
        self.retention_hours = retention_hours

        self._metrics_history: Deque[RequestMetrics] = deque(maxlen=max_history)
        self._start_time = datetime.now()

    def record_request(
        self,
        url: str,
        method: str,
        status_code: int,
        response_time: float,
        response_size: int = 0,
        error: Optional[str] = None,
    ) -> None:
        """
        Record metrics for a single request.

        Args:
            url: Request URL
            method: HTTP method
            status_code: HTTP status code
            response_time: Response time in seconds
            response_size: Response size in bytes
            error: Error message if request failed
        """
        metrics = RequestMetrics(
            url=url,
            method=method.upper(),
            status_code=status_code,
            response_time=response_time,
            response_size=response_size,
            timestamp=datetime.now(),
            error=error,
        )

        self._metrics_history.append(metrics)
        self._cleanup_old_metrics()

    def _cleanup_old_metrics(self) -> None:
        """Remove metrics older than retention period."""
        cutoff_time = datetime.now() - timedelta(hours=self.retention_hours)

        while (
            self._metrics_history and self._metrics_history[0].timestamp < cutoff_time
        ):
            self._metrics_history.popleft()

    def get_aggregated_metrics(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        host_filter: Optional[str] = None,
    ) -> AggregatedMetrics:
        """
        Get aggregated metrics for a time period.

        Args:
            since: Start time for aggregation (default: all time)
            until: End time for aggregation (default: now)
            host_filter: Filter metrics by host

        Returns:
            AggregatedMetrics for the specified period
        """
        aggregated = AggregatedMetrics()

        for metrics in self._metrics_history:
            # Apply time filters
            if since and metrics.timestamp < since:
                continue
            if until and metrics.timestamp > until:
                continue

            # Apply host filter
            if host_filter:
                try:
                    parsed = urlparse(metrics.url)
                    host = parsed.netloc or parsed.hostname or "unknown"
                    if host_filter.lower() not in host.lower():
                        continue
                except Exception:
                    continue

            aggregated.add_request(metrics)

        return aggregated

    def get_recent_metrics(self, minutes: int = 5) -> AggregatedMetrics:
        """Get metrics for the last N minutes."""
        since = datetime.now() - timedelta(minutes=minutes)
        return self.get_aggregated_metrics(since=since)

    def get_hourly_metrics(self, hours: int = 1) -> AggregatedMetrics:
        """Get metrics for the last N hours."""
        since = datetime.now() - timedelta(hours=hours)
        return self.get_aggregated_metrics(since=since)

    def get_daily_metrics(self) -> AggregatedMetrics:
        """Get metrics for the last 24 hours."""
        return self.get_hourly_metrics(hours=24)

    def get_host_breakdown(
        self, since: Optional[datetime] = None
    ) -> Dict[str, AggregatedMetrics]:
        """Get metrics broken down by host."""
        host_metrics: Dict[str, AggregatedMetrics] = defaultdict(
            lambda: AggregatedMetrics()
        )

        for metrics in self._metrics_history:
            if since and metrics.timestamp < since:
                continue

            try:
                parsed = urlparse(metrics.url)
                host = parsed.netloc or parsed.hostname or "unknown"
                host_metrics[host].add_request(metrics)
            except Exception:
                host_metrics["unknown"].add_request(metrics)

        return dict(host_metrics)

    def get_performance_percentiles(
        self, percentiles: Optional[List[float]] = None
    ) -> Dict[str, float]:
        """
        Calculate response time percentiles.

        Args:
            percentiles: List of percentiles to calculate (default: [50, 90, 95, 99])

        Returns:
            Dict mapping percentile to response time
        """
        if percentiles is None:
            percentiles = [50, 90, 95, 99]

        response_times = [m.response_time for m in self._metrics_history]

        if not response_times:
            return {str(p): 0.0 for p in percentiles}

        response_times.sort()
        result: Dict[str, float] = {}

        for percentile in percentiles:
            index = int((percentile / 100) * len(response_times))
            index = min(index, len(response_times) - 1)
            result[f"p{percentile}"] = response_times[index]

        return result

    def get_error_summary(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """Get summary of errors and their frequencies."""
        error_counts: Dict[str, int] = defaultdict(int)
        status_counts: Dict[int, int] = defaultdict(int)

        for metrics in self._metrics_history:
            if since and metrics.timestamp < since:
                continue

            if metrics.error:
                error_counts[metrics.error] += 1

            if not metrics.is_success:
                status_counts[metrics.status_code] += 1

        return {
            "error_messages": dict(error_counts),
            "error_status_codes": dict(status_counts),
            "total_errors": sum(error_counts.values()) + sum(status_counts.values()),
        }

    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health metrics."""
        recent_metrics = self.get_recent_metrics(minutes=5)
        hourly_metrics = self.get_hourly_metrics()

        return {
            "uptime_seconds": (datetime.now() - self._start_time).total_seconds(),
            "total_requests": len(self._metrics_history),
            "recent_success_rate": recent_metrics.success_rate,
            "hourly_success_rate": hourly_metrics.success_rate,
            "recent_avg_response_time": recent_metrics.average_response_time,
            "hourly_avg_response_time": hourly_metrics.average_response_time,
            "performance_percentiles": self.get_performance_percentiles(),
            "active_hosts": len(
                self.get_host_breakdown(since=datetime.now() - timedelta(hours=1))
            ),
            "error_summary": self.get_error_summary(
                since=datetime.now() - timedelta(hours=1)
            ),
        }

    def reset(self) -> None:
        """Reset all collected metrics."""
        self._metrics_history.clear()
        self._start_time = datetime.now()


# Global metrics collector instance
_global_collector = MetricsCollector()


def record_request_metrics(
    url: str,
    method: str,
    status_code: int,
    response_time: float,
    response_size: int = 0,
    error: Optional[str] = None,
) -> None:
    """
    Convenience function to record request metrics.

    Records metrics for a single HTTP request using the global metrics
    collector. This is the primary interface for tracking request performance.

    Args:
        url: URL that was requested
        method: HTTP method used (GET, POST, etc.)
        status_code: HTTP response status code
        response_time: Request duration in seconds
        response_size: Response size in bytes (default: 0)
        error: Error message if request failed (default: None)

    Example:
        ```python
        # Record successful request
        record_request_metrics(
            "https://api.example.com/data",
            "GET",
            200,
            0.245,
            1024
        )

        # Record failed request
        record_request_metrics(
            "https://api.example.com/data",
            "POST",
            500,
            1.2,
            0,
            "Internal server error"
        )
        ```
    """
    _global_collector.record_request(
        url, method, status_code, response_time, response_size, error
    )


def get_metrics_summary() -> Dict[str, Any]:
    """
    Get a summary of all collected metrics.

    Returns comprehensive system health metrics including success rates,
    response times, error summaries, and performance percentiles.

    Returns:
        Dictionary containing:
        - recent_success_rate: Success rate for last 5 minutes
        - hourly_success_rate: Success rate for last hour
        - recent_avg_response_time: Average response time (5 min)
        - hourly_avg_response_time: Average response time (1 hour)
        - performance_percentiles: Response time percentiles (p50, p90, p95, p99)
        - active_hosts: Number of unique hosts accessed in last hour
        - error_summary: Error counts and status code breakdown

    Example:
        ```python
        summary = get_metrics_summary()
        print(f"Success rate: {summary['recent_success_rate']:.1f}%")
        print(f"P95 response time: {summary['performance_percentiles']['p95']:.3f}s")
        ```
    """
    return _global_collector.get_system_health()


def get_recent_performance() -> AggregatedMetrics:
    """
    Get performance metrics for the last 5 minutes.

    Returns aggregated metrics for recent requests, useful for monitoring
    current system performance and detecting issues.

    Returns:
        AggregatedMetrics object with recent performance data including
        request counts, success rates, response times, and error information.

    Example:
        ```python
        recent = get_recent_performance()
        print(f"Recent requests: {recent.total_requests}")
        print(f"Success rate: {recent.success_rate:.1f}%")
        print(f"Avg response time: {recent.average_response_time:.3f}s")
        ```
    """
    return _global_collector.get_recent_metrics()


__all__ = [
    "RequestMetrics",
    "AggregatedMetrics",
    "MetricsCollector",
    "record_request_metrics",
    "get_metrics_summary",
    "get_recent_performance",
]
