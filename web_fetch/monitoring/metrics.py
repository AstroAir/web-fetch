"""
Comprehensive metrics collection system for web-fetch.

This module provides performance monitoring, error tracking, and usage analytics
across all resource types with support for multiple metrics backends.
"""

import time
import asyncio
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Callable, Deque
from threading import Lock
import json

try:
    import prometheus_client
    PROMETHEUS_AVAILABLE = True
except ImportError:
    prometheus_client = None  # type: ignore
    PROMETHEUS_AVAILABLE = False

try:
    import statsd  # type: ignore
    STATSD_AVAILABLE = True
except ImportError:
    statsd = None
    STATSD_AVAILABLE = False


class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class MetricBackend(Enum):
    """Metric backend types."""
    MEMORY = "memory"
    PROMETHEUS = "prometheus"
    STATSD = "statsd"
    CONSOLE = "console"


@dataclass
class MetricPoint:
    """Individual metric data point."""
    name: str
    value: float
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)
    metric_type: MetricType = MetricType.GAUGE


@dataclass
class TimingContext:
    """Context manager for timing operations."""
    name: str
    tags: Dict[str, str]
    start_time: Optional[float] = None
    metrics_collector: Optional['MetricsCollector'] = None

    def __enter__(self) -> 'TimingContext':
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[BaseException], exc_tb: Optional[object]) -> None:
        if self.start_time and self.metrics_collector:
            duration = time.time() - self.start_time
            self.metrics_collector.record_timer(self.name, duration, self.tags)


class MetricsBackendInterface(ABC):
    """Abstract interface for metrics backends."""

    @abstractmethod
    def record_counter(self, name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None) -> None:
        """Record counter metric."""
        pass

    @abstractmethod
    def record_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record gauge metric."""
        pass

    @abstractmethod
    def record_histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record histogram metric."""
        pass

    @abstractmethod
    def record_timer(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record timer metric."""
        pass


class MemoryMetricsBackend(MetricsBackendInterface):
    """In-memory metrics backend for testing and development."""

    def __init__(self, max_points: int = 10000):
        """
        Initialize memory metrics backend.

        Args:
            max_points: Maximum number of metric points to store
        """
        self.max_points = max_points
        self.metrics: Dict[str, Deque[MetricPoint]] = defaultdict(lambda: deque(maxlen=max_points))
        self.lock = Lock()

    def record_counter(self, name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None) -> None:
        """Record counter metric."""
        with self.lock:
            point = MetricPoint(
                name=name,
                value=value,
                timestamp=time.time(),
                tags=tags or {},
                metric_type=MetricType.COUNTER
            )
            self.metrics[name].append(point)

    def record_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record gauge metric."""
        with self.lock:
            point = MetricPoint(
                name=name,
                value=value,
                timestamp=time.time(),
                tags=tags or {},
                metric_type=MetricType.GAUGE
            )
            self.metrics[name].append(point)

    def record_histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record histogram metric."""
        with self.lock:
            point = MetricPoint(
                name=name,
                value=value,
                timestamp=time.time(),
                tags=tags or {},
                metric_type=MetricType.HISTOGRAM
            )
            self.metrics[name].append(point)

    def record_timer(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record timer metric."""
        with self.lock:
            point = MetricPoint(
                name=name,
                value=value,
                timestamp=time.time(),
                tags=tags or {},
                metric_type=MetricType.TIMER
            )
            self.metrics[name].append(point)

    def get_metrics(self, name: Optional[str] = None) -> Dict[str, List[MetricPoint]]:
        """Get stored metrics."""
        with self.lock:
            if name:
                return {name: list(self.metrics.get(name, []))}
            return {k: list(v) for k, v in self.metrics.items()}

    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        with self.lock:
            summary = {}
            for name, points in self.metrics.items():
                if not points:
                    continue

                values = [p.value for p in points]
                summary[name] = {
                    "count": len(values),
                    "sum": sum(values),
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "latest": values[-1] if values else 0
                }

            return summary


class PrometheusMetricsBackend(MetricsBackendInterface):
    """Prometheus metrics backend."""

    def __init__(self, registry: Optional[Any] = None) -> None:
        """
        Initialize Prometheus metrics backend.

        Args:
            registry: Prometheus registry to use
        """
        if not PROMETHEUS_AVAILABLE:
            raise ImportError("prometheus_client package is required for Prometheus backend")

        self.registry = registry or prometheus_client.REGISTRY
        self.counters: Dict[str, Any] = {}
        self.gauges: Dict[str, Any] = {}
        self.histograms: Dict[str, Any] = {}
        self.lock = Lock()

    def _get_or_create_counter(self, name: str, tags: Dict[str, str]) -> Any:
        """Get or create Prometheus counter."""
        key = f"{name}_{hash(frozenset(tags.keys()))}"

        if key not in self.counters:
            with self.lock:
                if key not in self.counters:
                    self.counters[key] = prometheus_client.Counter(
                        name.replace('.', '_').replace('-', '_'),
                        f"Counter metric for {name}",
                        labelnames=list(tags.keys()),
                        registry=self.registry
                    )

        return self.counters[key]

    def _get_or_create_gauge(self, name: str, tags: Dict[str, str]) -> Any:
        """Get or create Prometheus gauge."""
        key = f"{name}_{hash(frozenset(tags.keys()))}"

        if key not in self.gauges:
            with self.lock:
                if key not in self.gauges:
                    self.gauges[key] = prometheus_client.Gauge(
                        name.replace('.', '_').replace('-', '_'),
                        f"Gauge metric for {name}",
                        labelnames=list(tags.keys()),
                        registry=self.registry
                    )

        return self.gauges[key]

    def _get_or_create_histogram(self, name: str, tags: Dict[str, str]) -> Any:
        """Get or create Prometheus histogram."""
        key = f"{name}_{hash(frozenset(tags.keys()))}"

        if key not in self.histograms:
            with self.lock:
                if key not in self.histograms:
                    self.histograms[key] = prometheus_client.Histogram(
                        name.replace('.', '_').replace('-', '_'),
                        f"Histogram metric for {name}",
                        labelnames=list(tags.keys()),
                        registry=self.registry
                    )

        return self.histograms[key]

    def record_counter(self, name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None) -> None:
        """Record counter metric."""
        tags = tags or {}
        counter = self._get_or_create_counter(name, tags)
        counter.labels(**tags).inc(value)

    def record_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record gauge metric."""
        tags = tags or {}
        gauge = self._get_or_create_gauge(name, tags)
        gauge.labels(**tags).set(value)

    def record_histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record histogram metric."""
        tags = tags or {}
        histogram = self._get_or_create_histogram(name, tags)
        histogram.labels(**tags).observe(value)

    def record_timer(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record timer metric."""
        # Use histogram for timing data
        self.record_histogram(f"{name}_duration_seconds", value, tags)


class ConsoleMetricsBackend(MetricsBackendInterface):
    """Console metrics backend for debugging."""

    def __init__(self, print_func: Callable = print):
        """
        Initialize console metrics backend.

        Args:
            print_func: Function to use for printing metrics
        """
        self.print_func = print_func

    def record_counter(self, name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None) -> None:
        """Record counter metric."""
        tags_str = f" {tags}" if tags else ""
        self.print_func(f"COUNTER {name}: {value}{tags_str}")

    def record_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record gauge metric."""
        tags_str = f" {tags}" if tags else ""
        self.print_func(f"GAUGE {name}: {value}{tags_str}")

    def record_histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record histogram metric."""
        tags_str = f" {tags}" if tags else ""
        self.print_func(f"HISTOGRAM {name}: {value}{tags_str}")

    def record_timer(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record timer metric."""
        tags_str = f" {tags}" if tags else ""
        self.print_func(f"TIMER {name}: {value:.3f}s{tags_str}")


class MetricsCollector:
    """Main metrics collector with multiple backend support."""

    def __init__(self, backends: Optional[List[MetricsBackendInterface]] = None):
        """
        Initialize metrics collector.

        Args:
            backends: List of metrics backends to use
        """
        self.backends = backends or [MemoryMetricsBackend()]
        self.enabled = True

        # Built-in metrics
        self.start_time = time.time()
        self.request_count = 0
        self.error_count = 0
        self.cache_hits = 0
        self.cache_misses = 0

    def record_counter(self, name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None) -> None:
        """Record counter metric across all backends."""
        if not self.enabled:
            return

        for backend in self.backends:
            try:
                backend.record_counter(name, value, tags)
            except Exception as e:
                # Don't let metrics failures break the application
                print(f"Metrics backend error: {e}")

    def record_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record gauge metric across all backends."""
        if not self.enabled:
            return

        for backend in self.backends:
            try:
                backend.record_gauge(name, value, tags)
            except Exception as e:
                print(f"Metrics backend error: {e}")

    def record_histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record histogram metric across all backends."""
        if not self.enabled:
            return

        for backend in self.backends:
            try:
                backend.record_histogram(name, value, tags)
            except Exception as e:
                print(f"Metrics backend error: {e}")

    def record_timer(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record timer metric across all backends."""
        if not self.enabled:
            return

        for backend in self.backends:
            try:
                backend.record_timer(name, value, tags)
            except Exception as e:
                print(f"Metrics backend error: {e}")

    def time_operation(self, name: str, tags: Optional[Dict[str, str]] = None) -> TimingContext:
        """Create timing context for measuring operation duration."""
        return TimingContext(name, tags or {}, metrics_collector=self)

    def record_request(self, resource_kind: str, success: bool, duration: float,
                      cache_hit: bool = False, tags: Optional[Dict[str, str]] = None) -> None:
        """Record resource request metrics."""
        base_tags = {"resource_kind": resource_kind, "success": str(success)}
        if tags:
            base_tags.update(tags)

        # Update internal counters
        self.request_count += 1
        if not success:
            self.error_count += 1
        if cache_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

        # Record metrics
        self.record_counter("webfetch.requests.total", 1.0, base_tags)
        self.record_timer("webfetch.request.duration", duration, base_tags)

        if cache_hit:
            self.record_counter("webfetch.cache.hits", 1.0, base_tags)
        else:
            self.record_counter("webfetch.cache.misses", 1.0, base_tags)

        if not success:
            self.record_counter("webfetch.errors.total", 1.0, base_tags)

    def record_component_metrics(self, component_name: str, metrics: Dict[str, Any]) -> None:
        """Record component-specific metrics."""
        base_tags = {"component": component_name}

        for metric_name, value in metrics.items():
            if isinstance(value, (int, float)):
                self.record_gauge(f"webfetch.component.{metric_name}", value, base_tags)

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        uptime = time.time() - self.start_time

        summary = {
            "uptime_seconds": uptime,
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "error_rate": self.error_count / self.request_count if self.request_count > 0 else 0,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0,
            "requests_per_second": self.request_count / uptime if uptime > 0 else 0
        }

        # Add backend-specific summaries
        for i, backend in enumerate(self.backends):
            if hasattr(backend, 'get_summary'):
                summary[f"backend_{i}"] = backend.get_summary()

        return summary

    def enable(self) -> None:
        """Enable metrics collection."""
        self.enabled = True

    def disable(self) -> None:
        """Disable metrics collection."""
        self.enabled = False


# Global metrics collector instance
_global_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance."""
    global _global_metrics_collector

    if _global_metrics_collector is None:
        _global_metrics_collector = MetricsCollector()

    return _global_metrics_collector


def configure_metrics(backends: List[MetricsBackendInterface]) -> None:
    """Configure global metrics collector with specific backends."""
    global _global_metrics_collector
    _global_metrics_collector = MetricsCollector(backends)


def create_metrics_backend(backend_type: MetricBackend, **kwargs: Any) -> MetricsBackendInterface:
    """
    Create metrics backend of specified type.

    Args:
        backend_type: Type of metrics backend
        **kwargs: Backend-specific configuration

    Returns:
        Configured metrics backend
    """
    if backend_type == MetricBackend.MEMORY:
        return MemoryMetricsBackend(max_points=kwargs.get("max_points", 10000))
    elif backend_type == MetricBackend.PROMETHEUS:
        return PrometheusMetricsBackend(registry=kwargs.get("registry"))
    elif backend_type == MetricBackend.CONSOLE:
        return ConsoleMetricsBackend(print_func=kwargs.get("print_func", print))
    else:
        raise ValueError(f"Unsupported backend type: {backend_type}")
