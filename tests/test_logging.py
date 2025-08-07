"""
Comprehensive tests for the logging module.
"""

import pytest
import logging
import tempfile
import asyncio
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from web_fetch.logging import (
    LoggingManager,
    setup_logging,
    StructuredFormatter,
    ColoredFormatter,
    CompactFormatter,
    AsyncFileHandler,
    RotatingAsyncFileHandler,
    MetricsHandler,
    SensitiveDataFilter,
    RateLimitFilter,
    ComponentFilter,
)
from web_fetch.config.models import LoggingConfig, LogLevel


class TestStructuredFormatter:
    """Test structured log formatter."""

    def test_structured_format(self):
        """Test structured log formatting."""
        formatter = StructuredFormatter()
        
        # Create a log record
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.created = time.time()
        
        formatted = formatter.format(record)
        
        # Should be valid JSON
        import json
        parsed = json.loads(formatted)
        
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "Test message"
        assert parsed["logger"] == "test.logger"
        assert "timestamp" in parsed
        assert "module" in parsed

    def test_structured_format_with_extra(self):
        """Test structured formatting with extra fields."""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="/test/path.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=None
        )
        record.created = time.time()
        record.user_id = "12345"
        record.request_id = "req-abc"
        
        formatted = formatter.format(record)
        
        import json
        parsed = json.loads(formatted)
        
        assert parsed["user_id"] == "12345"
        assert parsed["request_id"] == "req-abc"


class TestColoredFormatter:
    """Test colored log formatter."""

    def test_colored_format_info(self):
        """Test colored formatting for INFO level."""
        formatter = ColoredFormatter()
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Info message",
            args=(),
            exc_info=None
        )
        record.created = time.time()
        
        formatted = formatter.format(record)
        
        # Should contain ANSI color codes for INFO (typically green)
        assert "\033[" in formatted  # ANSI escape sequence
        assert "Info message" in formatted

    def test_colored_format_error(self):
        """Test colored formatting for ERROR level."""
        formatter = ColoredFormatter()
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="/test/path.py",
            lineno=42,
            msg="Error message",
            args=(),
            exc_info=None
        )
        record.created = time.time()
        
        formatted = formatter.format(record)
        
        # Should contain ANSI color codes for ERROR (typically red)
        assert "\033[" in formatted
        assert "Error message" in formatted

    def test_colored_format_no_colors(self):
        """Test colored formatter with colors disabled."""
        formatter = ColoredFormatter(use_colors=False)
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Info message",
            args=(),
            exc_info=None
        )
        record.created = time.time()
        
        formatted = formatter.format(record)
        
        # Should not contain ANSI color codes
        assert "\033[" not in formatted
        assert "Info message" in formatted


class TestCompactFormatter:
    """Test compact log formatter."""

    def test_compact_format(self):
        """Test compact log formatting."""
        formatter = CompactFormatter()
        
        record = logging.LogRecord(
            name="web_fetch.fetcher",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Request completed",
            args=(),
            exc_info=None
        )
        record.created = time.time()
        
        formatted = formatter.format(record)
        
        # Should be compact and contain essential info
        assert "INFO" in formatted
        assert "fetcher" in formatted  # Shortened logger name
        assert "Request completed" in formatted
        assert len(formatted) < 200  # Should be reasonably compact


class TestSensitiveDataFilter:
    """Test sensitive data filter."""

    def test_filter_passwords(self):
        """Test filtering of password data."""
        filter_obj = SensitiveDataFilter()
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Login with password=secret123 and token=abc123",
            args=(),
            exc_info=None
        )
        
        result = filter_obj.filter(record)
        
        assert result is True  # Record should pass through
        assert "secret123" not in record.getMessage()
        assert "abc123" not in record.getMessage()
        assert "[REDACTED]" in record.getMessage()

    def test_filter_api_keys(self):
        """Test filtering of API keys."""
        filter_obj = SensitiveDataFilter()
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="API request with api_key=sk-1234567890abcdef",
            args=(),
            exc_info=None
        )
        
        result = filter_obj.filter(record)
        
        assert result is True
        assert "sk-1234567890abcdef" not in record.getMessage()
        assert "[REDACTED]" in record.getMessage()

    def test_filter_custom_patterns(self):
        """Test filtering with custom patterns."""
        custom_patterns = [r'user_id=\d+']
        filter_obj = SensitiveDataFilter(additional_patterns=custom_patterns)
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Processing request for user_id=12345",
            args=(),
            exc_info=None
        )
        
        result = filter_obj.filter(record)
        
        assert result is True
        assert "user_id=12345" not in record.getMessage()
        assert "[REDACTED]" in record.getMessage()


class TestRateLimitFilter:
    """Test rate limiting filter."""

    def test_rate_limit_messages(self):
        """Test rate limiting of log messages."""
        filter_obj = RateLimitFilter(max_messages=2, time_window=1.0)
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Repeated message",
            args=(),
            exc_info=None
        )
        
        # First two messages should pass
        assert filter_obj.filter(record) is True
        assert filter_obj.filter(record) is True
        
        # Third message should be filtered
        assert filter_obj.filter(record) is False

    def test_rate_limit_reset(self):
        """Test rate limit reset after time window."""
        filter_obj = RateLimitFilter(max_messages=1, time_window=0.1)
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Repeated message",
            args=(),
            exc_info=None
        )
        
        # First message should pass
        assert filter_obj.filter(record) is True
        
        # Second message should be filtered
        assert filter_obj.filter(record) is False
        
        # Wait for time window to reset
        time.sleep(0.2)
        
        # Message should pass again
        assert filter_obj.filter(record) is True


class TestComponentFilter:
    """Test component-based filter."""

    def test_component_filter_allowed(self):
        """Test component filter with allowed levels."""
        allowed_levels = {"INFO", "WARNING"}
        filter_obj = ComponentFilter("fetcher", allowed_levels)
        
        info_record = logging.LogRecord(
            name="web_fetch.fetcher",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Info message",
            args=(),
            exc_info=None
        )
        
        warning_record = logging.LogRecord(
            name="web_fetch.fetcher",
            level=logging.WARNING,
            pathname="/test/path.py",
            lineno=42,
            msg="Warning message",
            args=(),
            exc_info=None
        )
        
        error_record = logging.LogRecord(
            name="web_fetch.fetcher",
            level=logging.ERROR,
            pathname="/test/path.py",
            lineno=42,
            msg="Error message",
            args=(),
            exc_info=None
        )
        
        assert filter_obj.filter(info_record) is True
        assert filter_obj.filter(warning_record) is True
        assert filter_obj.filter(error_record) is False

    def test_component_filter_wrong_component(self):
        """Test component filter with wrong component."""
        allowed_levels = {"INFO"}
        filter_obj = ComponentFilter("fetcher", allowed_levels)
        
        record = logging.LogRecord(
            name="web_fetch.cache",  # Different component
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Info message",
            args=(),
            exc_info=None
        )
        
        # Should pass through (filter only applies to specific component)
        assert filter_obj.filter(record) is True


@pytest.mark.asyncio
class TestAsyncFileHandler:
    """Test async file handler."""

    async def test_async_file_handler_write(self):
        """Test async file handler writing."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            handler = AsyncFileHandler(temp_path)
            
            record = logging.LogRecord(
                name="test.logger",
                level=logging.INFO,
                pathname="/test/path.py",
                lineno=42,
                msg="Test message",
                args=(),
                exc_info=None
            )
            
            handler.emit(record)
            
            # Give some time for async write
            await asyncio.sleep(0.1)
            
            # Check file content
            with open(temp_path, 'r') as f:
                content = f.read()
                assert "Test message" in content
                
        finally:
            # Cleanup
            Path(temp_path).unlink(missing_ok=True)


class TestLoggingManager:
    """Test logging manager."""

    def test_logging_manager_creation(self):
        """Test logging manager creation."""
        manager = LoggingManager()
        assert manager._configured is False
        assert len(manager._handlers) == 0

    def test_setup_console_logging(self):
        """Test console logging setup."""
        config = LoggingConfig(
            level=LogLevel.INFO,
            enable_console_logging=True,
            enable_file_logging=False
        )
        
        manager = LoggingManager()
        manager.setup_logging(config)
        
        assert manager._configured is True
        assert "console" in manager._handlers

    def test_setup_file_logging(self):
        """Test file logging setup."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            config = LoggingConfig(
                level=LogLevel.DEBUG,
                enable_console_logging=False,
                enable_file_logging=True,
                log_file=temp_path
            )
            
            manager = LoggingManager()
            manager.setup_logging(config)
            
            assert manager._configured is True
            assert "file" in manager._handlers
            
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_setup_logging_function(self):
        """Test the setup_logging convenience function."""
        config = LoggingConfig(
            level=LogLevel.WARNING,
            enable_console_logging=True
        )
        
        # Should not raise any exceptions
        setup_logging(config)
        
        # Verify logging level is set
        logger = logging.getLogger("web_fetch")
        assert logger.level <= logging.WARNING
