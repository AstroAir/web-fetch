"""
Performance metrics collection for web_fetch HTTP components.

This module provides comprehensive performance monitoring with request/response
timing, throughput analysis, and bottleneck identification.
"""

import asyncio
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional, Set
from urllib.parse import urlparse

from pydantic import BaseModel, Field


@dataclass
class RequestMetrics:
    """Metrics for a single HTTP request."""
    
    url: str
    method: str
    start_time: float
    end_time: Optional[float] = None
    connect_time: Optional[float] = None
    dns_time: Optional[float] = None
    ssl_time: Optional[float] = None
    response_time: Optional[float] = None
    status_code: Optional[int] = None
    bytes_sent: int = 0
    bytes_received: int = 0
    error: Optional[str] = None
    
    @property
    def total_time(self) -> Optional[float]:
        """Total request time in seconds."""
        if self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def is_success(self) -> bool:
        """Whether request was successful."""
        return self.error is None and (self.status_code or 0) < 400


@dataclass
class PerformanceStats:
    """Aggregated performance statistics."""
    
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_bytes_sent: int = 0
    total_bytes_received: int = 0
    
    # Timing statistics
    min_response_time: float = float('inf')
    max_response_time: float = 0.0
    avg_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    
    # Throughput statistics
    requests_per_second: float = 0.0
    bytes_per_second: float = 0.0
    
    # Error statistics
    error_rate: float = 0.0
    status_code_distribution: Dict[int, int] = field(default_factory=dict)
    error_types: Dict[str, int] = field(default_factory=dict)
    
    # Host statistics
    host_performance: Dict[str, Dict[str, float]] = field(default_factory=dict)


class MetricsCollector:
    """Collects and analyzes HTTP performance metrics."""
    
    def __init__(self, max_history: int = 10000):
        """
        Initialize metrics collector.
        
        Args:
            max_history: Maximum number of requests to keep in history
        """
        self.max_history = max_history
        self._request_history: deque[RequestMetrics] = deque(maxlen=max_history)
        self._active_requests: Dict[str, RequestMetrics] = {}
        self._lock = asyncio.Lock()
        
        # Real-time counters
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._start_time = time.time()
        
        # Response time tracking for percentiles
        self._response_times: deque[float] = deque(maxlen=1000)
    
    @asynccontextmanager
    async def track_request(
        self, 
        method: str, 
        url: str
    ) -> AsyncGenerator[RequestMetrics, None]:
        """
        Track a request with automatic timing.
        
        Args:
            method: HTTP method
            url: Request URL
            
        Yields:
            RequestMetrics object for the request
        """
        request_id = f"{id(asyncio.current_task())}-{time.time()}"
        metrics = RequestMetrics(
            url=url,
            method=method.upper(),
            start_time=time.time()
        )
        
        async with self._lock:
            self._active_requests[request_id] = metrics
            self._total_requests += 1
        
        try:
            yield metrics
        finally:
            # Finalize metrics
            metrics.end_time = time.time()
            
            async with self._lock:
                # Remove from active requests
                self._active_requests.pop(request_id, None)
                
                # Add to history
                self._request_history.append(metrics)
                
                # Update counters
                if metrics.is_success:
                    self._successful_requests += 1
                else:
                    self._failed_requests += 1
                
                # Track response time for percentiles
                if metrics.total_time:
                    self._response_times.append(metrics.total_time)
    
    def record_connection_timing(
        self, 
        metrics: RequestMetrics,
        connect_time: Optional[float] = None,
        dns_time: Optional[float] = None,
        ssl_time: Optional[float] = None
    ) -> None:
        """Record connection timing details."""
        if connect_time:
            metrics.connect_time = connect_time
        if dns_time:
            metrics.dns_time = dns_time
        if ssl_time:
            metrics.ssl_time = ssl_time
    
    def record_response(
        self,
        metrics: RequestMetrics,
        status_code: int,
        bytes_received: int = 0,
        response_time: Optional[float] = None
    ) -> None:
        """Record response details."""
        metrics.status_code = status_code
        metrics.bytes_received = bytes_received
        if response_time:
            metrics.response_time = response_time
    
    def record_error(self, metrics: RequestMetrics, error: str) -> None:
        """Record request error."""
        metrics.error = error
    
    def record_bytes_sent(self, metrics: RequestMetrics, bytes_sent: int) -> None:
        """Record bytes sent in request."""
        metrics.bytes_sent = bytes_sent
    
    async def get_stats(self) -> PerformanceStats:
        """Get current performance statistics."""
        async with self._lock:
            stats = PerformanceStats()
            
            # Basic counters
            stats.total_requests = self._total_requests
            stats.successful_requests = self._successful_requests
            stats.failed_requests = self._failed_requests
            
            # Calculate rates
            elapsed_time = time.time() - self._start_time
            if elapsed_time > 0:
                stats.requests_per_second = self._total_requests / elapsed_time
            
            # Process request history
            if self._request_history:
                # Timing statistics
                response_times = [
                    r.total_time for r in self._request_history 
                    if r.total_time is not None
                ]
                
                if response_times:
                    stats.min_response_time = min(response_times)
                    stats.max_response_time = max(response_times)
                    stats.avg_response_time = sum(response_times) / len(response_times)
                    
                    # Calculate percentiles
                    sorted_times = sorted(response_times)
                    if len(sorted_times) >= 20:  # Need reasonable sample size
                        p95_idx = int(len(sorted_times) * 0.95)
                        p99_idx = int(len(sorted_times) * 0.99)
                        stats.p95_response_time = sorted_times[p95_idx]
                        stats.p99_response_time = sorted_times[p99_idx]
                
                # Byte statistics
                stats.total_bytes_sent = sum(r.bytes_sent for r in self._request_history)
                stats.total_bytes_received = sum(r.bytes_received for r in self._request_history)
                
                if elapsed_time > 0:
                    stats.bytes_per_second = stats.total_bytes_received / elapsed_time
                
                # Error statistics
                if stats.total_requests > 0:
                    stats.error_rate = stats.failed_requests / stats.total_requests
                
                # Status code distribution
                status_codes: Dict[int, int] = defaultdict(int)
                error_types: Dict[str, int] = defaultdict(int)
                host_times = defaultdict(list)
                
                for request in self._request_history:
                    if request.status_code:
                        status_codes[request.status_code] += 1
                    
                    if request.error:
                        error_types[request.error] += 1
                    
                    # Host performance
                    if request.total_time:
                        host = urlparse(request.url).netloc
                        host_times[host].append(request.total_time)
                
                stats.status_code_distribution = dict(status_codes)
                stats.error_types = dict(error_types)
                
                # Host performance statistics
                host_performance = {}
                for host, times in host_times.items():
                    if times:
                        host_performance[host] = {
                            'avg_time': sum(times) / len(times),
                            'min_time': min(times),
                            'max_time': max(times),
                            'request_count': len(times)
                        }
                stats.host_performance = host_performance
            
            return stats
    
    def get_active_requests(self) -> List[RequestMetrics]:
        """Get currently active requests."""
        return list(self._active_requests.values())
    
    def reset_stats(self) -> None:
        """Reset all statistics."""
        self._request_history.clear()
        self._active_requests.clear()
        self._response_times.clear()
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._start_time = time.time()
    
    async def export_metrics(self) -> Dict[str, Any]:
        """Export metrics in a structured format."""
        stats = await self.get_stats()
        active_requests = self.get_active_requests()
        
        return {
            "timestamp": time.time(),
            "collection_period": time.time() - self._start_time,
            "stats": {
                "total_requests": stats.total_requests,
                "successful_requests": stats.successful_requests,
                "failed_requests": stats.failed_requests,
                "error_rate": stats.error_rate,
                "requests_per_second": stats.requests_per_second,
                "bytes_per_second": stats.bytes_per_second,
                "response_times": {
                    "min": stats.min_response_time if stats.min_response_time != float('inf') else None,
                    "max": stats.max_response_time,
                    "avg": stats.avg_response_time,
                    "p95": stats.p95_response_time,
                    "p99": stats.p99_response_time,
                },
                "status_codes": stats.status_code_distribution,
                "errors": stats.error_types,
                "hosts": stats.host_performance,
            },
            "active_requests": len(active_requests),
            "history_size": len(self._request_history),
        }


# Global metrics collector instance
_global_metrics: Optional[MetricsCollector] = None
_metrics_lock = asyncio.Lock()


async def get_global_metrics() -> MetricsCollector:
    """Get or create global metrics collector."""
    global _global_metrics
    
    async with _metrics_lock:
        if _global_metrics is None:
            _global_metrics = MetricsCollector()
    
    return _global_metrics


async def reset_global_metrics() -> None:
    """Reset global metrics collector."""
    global _global_metrics
    
    async with _metrics_lock:
        if _global_metrics:
            _global_metrics.reset_stats()
