"""
Monitoring and metrics collection module for web-fetch.

This module provides comprehensive performance monitoring, error tracking,
and usage analytics across all resource types with support for multiple
metrics backends including Prometheus, StatsD, and in-memory storage.
"""

from .metrics import (
    MetricsCollector,
    MetricType,
    MetricBackend,
    MetricPoint,
    TimingContext,
    MetricsBackendInterface,
    MemoryMetricsBackend,
    PrometheusMetricsBackend,
    ConsoleMetricsBackend,
    get_metrics_collector,
    configure_metrics,
    create_metrics_backend
)

__all__ = [
    "MetricsCollector",
    "MetricType",
    "MetricBackend", 
    "MetricPoint",
    "TimingContext",
    "MetricsBackendInterface",
    "MemoryMetricsBackend",
    "PrometheusMetricsBackend",
    "ConsoleMetricsBackend",
    "get_metrics_collector",
    "configure_metrics",
    "create_metrics_backend"
]
