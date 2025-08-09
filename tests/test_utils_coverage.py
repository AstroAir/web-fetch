"""
Tests for utility functions that need better coverage.

This module focuses on testing utility functions that are actually available
and may not have adequate test coverage.
"""

import pytest
from typing import Dict, Any
from unittest.mock import patch, MagicMock

from web_fetch.utils import (
    RequestDeduplicator,
    deduplicate_request,
    get_deduplication_stats,
    TransformationPipeline,
    JSONPathExtractor,
    HTMLExtractor,
    RegexExtractor,
    MetricsCollector,
    record_request_metrics,
    get_metrics_summary,
    get_recent_performance,
    ContentTypeDetector,
    SimpleCache,
    RateLimiter,
    ResponseAnalyzer,
    URLValidator,
)


class TestRequestDeduplicator:
    """Test request deduplication functionality."""

    def test_deduplicator_creation(self) -> None:
        """Test deduplicator creation."""
        dedup = RequestDeduplicator()
        assert dedup is not None

    def test_deduplicator_basic_functionality(self) -> None:
        """Test basic deduplication functionality."""
        dedup = RequestDeduplicator()
        
        # First request should not be duplicate
        is_duplicate = dedup.is_duplicate("GET", "https://example.com", {})
        assert not is_duplicate
        
        # Same request should be duplicate
        is_duplicate = dedup.is_duplicate("GET", "https://example.com", {})
        assert is_duplicate

    def test_deduplicator_different_methods(self) -> None:
        """Test deduplication with different HTTP methods."""
        dedup = RequestDeduplicator()
        
        # Different methods should not be duplicates
        dedup.is_duplicate("GET", "https://example.com", {})
        is_duplicate = dedup.is_duplicate("POST", "https://example.com", {})
        assert not is_duplicate

    def test_deduplicator_with_headers(self) -> None:
        """Test deduplication considering headers."""
        dedup = RequestDeduplicator()
        
        headers1 = {"Authorization": "Bearer token1"}
        headers2 = {"Authorization": "Bearer token2"}
        
        dedup.is_duplicate("GET", "https://example.com", headers1)
        is_duplicate = dedup.is_duplicate("GET", "https://example.com", headers2)
        assert not is_duplicate

    def test_get_deduplication_stats(self) -> None:
        """Test getting deduplication statistics."""
        # This should not raise an exception
        stats = get_deduplication_stats()
        assert isinstance(stats, dict)


class TestTransformationPipeline:
    """Test transformation pipeline functionality."""

    def test_pipeline_creation(self) -> None:
        """Test pipeline creation."""
        pipeline = TransformationPipeline()
        assert pipeline is not None

    def test_pipeline_add_transformer(self) -> None:
        """Test adding transformers to pipeline."""
        pipeline = TransformationPipeline()
        
        def uppercase_transformer(data: Any) -> Any:
            if isinstance(data, str):
                return data.upper()
            return data
        
        pipeline.add_transformer(uppercase_transformer)
        assert len(pipeline.transformers) == 1

    def test_pipeline_transform(self) -> None:
        """Test pipeline transformation."""
        pipeline = TransformationPipeline()
        
        def uppercase_transformer(data: Any) -> Any:
            if isinstance(data, str):
                return data.upper()
            return data
        
        def prefix_transformer(data: Any) -> Any:
            if isinstance(data, str):
                return f"PREFIX: {data}"
            return data
        
        pipeline.add_transformer(uppercase_transformer)
        pipeline.add_transformer(prefix_transformer)
        
        result = pipeline.transform("hello world")
        assert result == "PREFIX: HELLO WORLD"


class TestExtractors:
    """Test various extractor classes."""

    def test_json_path_extractor(self) -> None:
        """Test JSONPath extractor."""
        extractor = JSONPathExtractor("$.users[*].name")
        
        data = {
            "users": [
                {"name": "Alice", "age": 30},
                {"name": "Bob", "age": 25}
            ]
        }
        
        result = extractor.extract(data)
        assert result == ["Alice", "Bob"]

    def test_html_extractor(self) -> None:
        """Test HTML extractor."""
        extractor = HTMLExtractor("h1")
        
        html = "<html><body><h1>Title 1</h1><h1>Title 2</h1></body></html>"
        
        result = extractor.extract(html)
        assert len(result) == 2
        assert "Title 1" in result[0]
        assert "Title 2" in result[1]

    def test_regex_extractor(self) -> None:
        """Test regex extractor."""
        extractor = RegexExtractor(r"\b\w+@\w+\.\w+\b")
        
        text = "Contact us at support@example.com or sales@company.org"
        
        result = extractor.extract(text)
        assert "support@example.com" in result
        assert "sales@company.org" in result


class TestMetricsCollector:
    """Test metrics collection functionality."""

    def test_metrics_collector_creation(self) -> None:
        """Test metrics collector creation."""
        collector = MetricsCollector()
        assert collector is not None

    def test_record_request_metrics(self) -> None:
        """Test recording request metrics."""
        # This should not raise an exception
        record_request_metrics("https://example.com", 200, 0.5, 1024)

    def test_get_metrics_summary(self) -> None:
        """Test getting metrics summary."""
        # Record some metrics first
        record_request_metrics("https://example.com", 200, 0.5, 1024)
        record_request_metrics("https://example.com", 404, 0.3, 512)
        
        summary = get_metrics_summary()
        assert isinstance(summary, dict)
        assert "total_requests" in summary

    def test_get_recent_performance(self) -> None:
        """Test getting recent performance metrics."""
        # Record some metrics first
        record_request_metrics("https://example.com", 200, 0.5, 1024)
        
        performance = get_recent_performance()
        assert isinstance(performance, dict)


class TestContentTypeDetector:
    """Test content type detection."""

    def test_detector_creation(self) -> None:
        """Test detector creation."""
        detector = ContentTypeDetector()
        assert detector is not None

    def test_detect_from_content(self) -> None:
        """Test content type detection from content."""
        detector = ContentTypeDetector()
        
        # JSON content
        json_content = '{"key": "value"}'
        content_type = detector.detect_from_content(json_content.encode())
        assert "json" in content_type.lower()
        
        # HTML content
        html_content = "<html><body>Test</body></html>"
        content_type = detector.detect_from_content(html_content.encode())
        assert "html" in content_type.lower()

    def test_detect_from_headers(self) -> None:
        """Test content type detection from headers."""
        detector = ContentTypeDetector()
        
        headers = {"content-type": "application/json; charset=utf-8"}
        content_type = detector.detect_from_headers(headers)
        assert content_type == "application/json"

    def test_detect_from_url(self) -> None:
        """Test content type detection from URL."""
        detector = ContentTypeDetector()
        
        # JSON file
        content_type = detector.detect_from_url("https://example.com/data.json")
        assert "json" in content_type.lower()
        
        # HTML file
        content_type = detector.detect_from_url("https://example.com/page.html")
        assert "html" in content_type.lower()


class TestSimpleCache:
    """Test simple cache functionality."""

    def test_cache_creation(self) -> None:
        """Test cache creation."""
        cache = SimpleCache()
        assert cache is not None

    def test_cache_basic_operations(self) -> None:
        """Test basic cache operations."""
        cache = SimpleCache()
        
        # Set and get
        cache.set("key1", "value1")
        value = cache.get("key1")
        assert value == "value1"
        
        # Non-existent key
        value = cache.get("nonexistent")
        assert value is None

    def test_cache_delete(self) -> None:
        """Test cache deletion."""
        cache = SimpleCache()
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_cache_clear(self) -> None:
        """Test cache clearing."""
        cache = SimpleCache()
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        cache.clear()
        
        assert cache.get("key1") is None
        assert cache.get("key2") is None


class TestRateLimiter:
    """Test rate limiter functionality."""

    def test_rate_limiter_creation(self) -> None:
        """Test rate limiter creation."""
        limiter = RateLimiter(max_requests=10, time_window=60.0)
        assert limiter is not None

    def test_rate_limiter_allow_request(self) -> None:
        """Test rate limiter allowing requests."""
        limiter = RateLimiter(max_requests=5, time_window=1.0)
        
        # First few requests should be allowed
        for i in range(3):
            allowed = limiter.is_allowed("test_key")
            assert allowed


class TestResponseAnalyzer:
    """Test response analyzer functionality."""

    def test_analyzer_creation(self) -> None:
        """Test analyzer creation."""
        analyzer = ResponseAnalyzer()
        assert analyzer is not None


class TestURLValidator:
    """Test URL validator functionality."""

    def test_validator_creation(self) -> None:
        """Test validator creation."""
        validator = URLValidator()
        assert validator is not None

    def test_validate_url(self) -> None:
        """Test URL validation."""
        validator = URLValidator()
        
        # Valid URL
        assert validator.is_valid("https://example.com")
        
        # Invalid URL
        assert not validator.is_valid("not-a-url")
