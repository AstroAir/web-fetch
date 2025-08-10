"""
Tests for the metrics module.

This module tests the metrics collection and reporting functionality.
"""

import pytest
import time
from unittest.mock import Mock, patch

from web_fetch.monitoring.metrics import (
    MetricBackend,
    MetricPoint,
    MetricType,
    MetricsBackendInterface,
    MetricsCollector,
    MemoryMetricsBackend,
    ConsoleMetricsBackend,
    TimingContext,
    configure_metrics,
    create_metrics_backend,
)


class TestMetricPoint:
    """Test the MetricPoint model."""

    def test_metric_point_creation(self):
        """Test creating a metric point."""
        point = MetricPoint(
            name="test_metric",
            value=42.0,
            timestamp=time.time(),
            tags={"service": "web_fetch"},
            metric_type=MetricType.COUNTER
        )
        
        assert point.name == "test_metric"
        assert point.value == 42.0
        assert point.tags == {"service": "web_fetch"}
        assert point.metric_type == MetricType.COUNTER


class TestTimingContext:
    """Test the timing context manager."""

    def test_timing_context_basic(self):
        """Test basic timing context functionality."""
        mock_callback = Mock()
        
        with TimingContext("test_operation", mock_callback):
            time.sleep(0.01)  # Small delay
        
        mock_callback.assert_called_once()
        args = mock_callback.call_args[0]
        assert args[0] == "test_operation"
        assert args[1] > 0  # Duration should be positive

    def test_timing_context_with_tags(self):
        """Test timing context with tags."""
        mock_callback = Mock()
        tags = {"service": "test", "operation": "fetch"}
        
        with TimingContext("test_operation", mock_callback, tags=tags):
            time.sleep(0.01)
        
        mock_callback.assert_called_once()
        args = mock_callback.call_args[0]
        assert args[2] == tags


class TestMemoryMetricsBackend:
    """Test the memory metrics backend."""

    @pytest.fixture
    def memory_backend(self):
        """Create a memory metrics backend for testing."""
        return MemoryMetricsBackend()

    def test_memory_backend_record_counter(self, memory_backend):
        """Test recording counter metrics."""
        memory_backend.record_counter("test_counter", 5.0, {"service": "test"})
        
        metrics = memory_backend.metrics
        assert "test_counter" in metrics
        assert len(metrics["test_counter"]) == 1
        
        point = metrics["test_counter"][0]
        assert point.name == "test_counter"
        assert point.value == 5.0
        assert point.metric_type == MetricType.COUNTER

    def test_memory_backend_record_gauge(self, memory_backend):
        """Test recording gauge metrics."""
        memory_backend.record_gauge("test_gauge", 42.0)
        
        metrics = memory_backend.metrics
        assert "test_gauge" in metrics
        
        point = metrics["test_gauge"][0]
        assert point.metric_type == MetricType.GAUGE
        assert point.value == 42.0

    def test_memory_backend_record_histogram(self, memory_backend):
        """Test recording histogram metrics."""
        memory_backend.record_histogram("test_histogram", 123.45)
        
        metrics = memory_backend.metrics
        assert "test_histogram" in metrics
        
        point = metrics["test_histogram"][0]
        assert point.metric_type == MetricType.HISTOGRAM
        assert point.value == 123.45

    def test_memory_backend_record_timer(self, memory_backend):
        """Test recording timer metrics."""
        memory_backend.record_timer("test_timer", 0.5)
        
        metrics = memory_backend.metrics
        assert "test_timer" in metrics
        
        point = metrics["test_timer"][0]
        assert point.metric_type == MetricType.TIMER
        assert point.value == 0.5


class TestConsoleMetricsBackend:
    """Test the console metrics backend."""

    @pytest.fixture
    def console_backend(self):
        """Create a console metrics backend for testing."""
        mock_print = Mock()
        return ConsoleMetricsBackend(print_func=mock_print)

    def test_console_backend_record_counter(self, console_backend):
        """Test console backend counter recording."""
        console_backend.record_counter("test_counter", 10.0, {"env": "test"})

        console_backend.print_func.assert_called_once()
        call_args = console_backend.print_func.call_args[0][0]
        assert "COUNTER test_counter: 10.0" in call_args
        assert "{'env': 'test'}" in call_args

    def test_console_backend_record_gauge(self, console_backend):
        """Test console backend gauge recording."""
        console_backend.record_gauge("test_gauge", 25.5)

        console_backend.print_func.assert_called_once()
        call_args = console_backend.print_func.call_args[0][0]
        assert "GAUGE test_gauge: 25.5" in call_args

    def test_console_backend_record_histogram(self, console_backend):
        """Test console backend histogram recording."""
        console_backend.record_histogram("test_histogram", 100.0)

        console_backend.print_func.assert_called_once()
        call_args = console_backend.print_func.call_args[0][0]
        assert "HISTOGRAM test_histogram: 100.0" in call_args

    def test_console_backend_record_timer(self, console_backend):
        """Test console backend timer recording."""
        console_backend.record_timer("test_timer", 1.5)

        console_backend.print_func.assert_called_once()
        call_args = console_backend.print_func.call_args[0][0]
        assert "TIMER test_timer: 1.5" in call_args


class TestMetricsCollector:
    """Test the metrics collector."""

    @pytest.fixture
    def metrics_collector(self):
        """Create a metrics collector for testing."""
        backend = MemoryMetricsBackend()
        return MetricsCollector([backend])

    def test_metrics_collector_record_counter(self, metrics_collector):
        """Test metrics collector counter recording."""
        metrics_collector.record_counter("test_counter", 15.0)

        # Check that the metric was recorded in the backend
        backend = metrics_collector.backends[0]
        assert "test_counter" in backend.metrics

    def test_metrics_collector_record_gauge(self, metrics_collector):
        """Test metrics collector gauge recording."""
        metrics_collector.record_gauge("test_gauge", 50.0)

        backend = metrics_collector.backends[0]
        assert "test_gauge" in backend.metrics

    def test_metrics_manager_record_request(self, metrics_manager):
        """Test recording request metrics."""
        metrics_manager.record_request(
            resource_kind="http",
            success=True,
            duration=0.5,
            cache_hit=False
        )
        
        backend = metrics_manager.backends[0]
        # Should record multiple metrics for a request
        assert len(backend.metrics) > 0

    def test_metrics_manager_disabled(self):
        """Test metrics manager when disabled."""
        backend = MemoryMetricsBackend()
        manager = MetricsManager([backend])
        manager.disable()
        
        manager.record_counter("test_counter", 10.0)
        
        # Should not record when disabled
        assert len(backend.metrics) == 0

    def test_metrics_manager_enable_disable(self, metrics_manager):
        """Test enabling and disabling metrics manager."""
        assert metrics_manager.enabled is True
        
        metrics_manager.disable()
        assert metrics_manager.enabled is False
        
        metrics_manager.enable()
        assert metrics_manager.enabled is True

    def test_metrics_manager_error_handling(self):
        """Test metrics manager error handling."""
        # Create a backend that raises exceptions
        mock_backend = Mock()
        mock_backend.record_counter.side_effect = Exception("Backend error")
        
        manager = MetricsManager([mock_backend])
        
        # Should not raise exception, just log error
        manager.record_counter("test_counter", 1.0)


class TestMetricsFactory:
    """Test the metrics factory functions."""

    def test_create_memory_backend(self):
        """Test creating memory metrics backend."""
        backend = create_metrics_backend(MetricBackend.MEMORY)
        assert isinstance(backend, MemoryMetricsBackend)

    def test_create_print_backend(self):
        """Test creating print metrics backend."""
        backend = create_metrics_backend(MetricBackend.PRINT)
        assert isinstance(backend, PrintMetricsBackend)

    @patch('web_fetch.monitoring.metrics.PROMETHEUS_AVAILABLE', True)
    def test_create_prometheus_backend(self):
        """Test creating Prometheus metrics backend."""
        with patch('web_fetch.monitoring.metrics.PrometheusMetricsBackend') as mock_prometheus:
            backend = create_metrics_backend(MetricBackend.PROMETHEUS)
            mock_prometheus.assert_called_once()

    def test_configure_metrics(self):
        """Test configuring global metrics."""
        backend = MemoryMetricsBackend()
        configure_metrics([backend])
        
        # Should configure global metrics instance
        # This is tested indirectly through the global metrics object
