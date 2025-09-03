"""
Custom logging filters for web_fetch.

This module provides filters for sensitive data masking, rate limiting,
and component-specific filtering.
"""

import logging
import re
import threading
import time
from collections import defaultdict
from typing import Dict, List, Pattern, Set


class SensitiveDataFilter(logging.Filter):
    """Filter to mask sensitive data in log messages."""

    def __init__(self) -> None:
        """Initialize sensitive data filter."""
        super().__init__()

        # Patterns for sensitive data
        self.patterns: List[Pattern[str]] = [
            # API keys and tokens
            re.compile(
                r'(api[_-]?key|token|secret)["\s]*[:=]["\s]*([a-zA-Z0-9+/=]{20,})',
                re.IGNORECASE,
            ),
            re.compile(r"(bearer\s+)([a-zA-Z0-9+/=]{20,})", re.IGNORECASE),
            re.compile(
                r'(authorization["\s]*[:=]["\s]*["\']?)([a-zA-Z0-9+/=]{20,})',
                re.IGNORECASE,
            ),
            # Passwords
            re.compile(
                r'(password|passwd|pwd)["\s]*[:=]["\s]*([^\s"\']+)', re.IGNORECASE
            ),
            # URLs with credentials
            re.compile(r"(https?://[^:]+):([^@]+)@", re.IGNORECASE),
            # Credit card numbers (basic pattern)
            re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
            # Social security numbers
            re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            # Email addresses (partial masking)
            re.compile(r"\b([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b"),
            # IP addresses (partial masking)
            re.compile(r"\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b"),
        ]

        # Replacement patterns
        self.replacements = [
            r"\1: ***MASKED***",  # API keys and tokens
            r"\1***MASKED***",  # Bearer tokens
            r"\1***MASKED***",  # Authorization headers
            r"\1: ***MASKED***",  # Passwords
            r"\1:***MASKED***@",  # URL credentials
            r"****-****-****-****",  # Credit cards
            r"***-**-****",  # SSN
            r"\1***@\2",  # Email (keep domain)
            r"\1.\2.***.***",  # IP (keep first two octets)
        ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log record to mask sensitive data."""
        try:
            # Get the formatted message
            message = record.getMessage()

            # Apply all masking patterns
            for pattern, replacement in zip(self.patterns, self.replacements):
                message = pattern.sub(replacement, message)

            # Update the record
            record.msg = message
            record.args = ()

            return True

        except Exception:
            # If filtering fails, allow the record through
            return True


class RateLimitFilter(logging.Filter):
    """Filter to rate limit log messages."""

    def __init__(self, max_messages_per_second: float = 10.0):
        """
        Initialize rate limit filter.

        Args:
            max_messages_per_second: Maximum messages per second
        """
        super().__init__()
        self.max_messages_per_second = max_messages_per_second
        self.min_interval = 1.0 / max_messages_per_second
        self._last_log_time: Dict[str, float] = defaultdict(float)
        self._dropped_counts: Dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log record based on rate limits."""
        with self._lock:
            # Create key for this log message type
            key = f"{record.name}:{record.levelname}:{record.funcName}"

            current_time = time.time()
            last_time = self._last_log_time[key]

            # Check if enough time has passed
            if current_time - last_time >= self.min_interval:
                # Allow this message
                self._last_log_time[key] = current_time

                # Add dropped count if any were dropped
                dropped = self._dropped_counts[key]
                if dropped > 0:
                    record.msg = (
                        f"{record.getMessage()} (dropped {dropped} similar messages)"
                    )
                    record.args = ()
                    self._dropped_counts[key] = 0

                return True
            else:
                # Drop this message
                self._dropped_counts[key] += 1
                return False


class ComponentFilter(logging.Filter):
    """Filter for component-specific logging."""

    def __init__(self, component: str, allowed_levels: Set[str] | None = None) -> None:
        """
        Initialize component filter.

        Args:
            component: Component name to filter for
            allowed_levels: Set of allowed log levels
        """
        super().__init__()
        self.component = component
        self.allowed_levels = allowed_levels or {
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        }

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter based on component and level."""
        # Check if this record is from the target component
        if not record.name.startswith(self.component):
            return False

        # Check if level is allowed
        return record.levelname in self.allowed_levels


class PerformanceFilter(logging.Filter):
    """Filter for performance-related logging."""

    def __init__(self, min_duration_ms: float = 100.0):
        """
        Initialize performance filter.

        Args:
            min_duration_ms: Minimum duration in milliseconds to log
        """
        super().__init__()
        self.min_duration_ms = min_duration_ms

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter based on performance metrics."""
        # Only log if duration exceeds threshold
        duration = getattr(record, "duration", 0)
        return duration >= self.min_duration_ms


class ErrorFilter(logging.Filter):
    """Filter for error-related logging."""

    def __init__(self, include_stack_trace: bool = True):
        """
        Initialize error filter.

        Args:
            include_stack_trace: Whether to include stack traces
        """
        super().__init__()
        self.include_stack_trace = include_stack_trace

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter and enhance error records."""
        # Only process error and critical levels
        if record.levelno < logging.ERROR:
            return True

        # Add error context if available
        if hasattr(record, "url"):
            record.msg = f"{record.getMessage()} [URL: {record.url}]"
            record.args = ()

        # Remove stack trace if not wanted
        if not self.include_stack_trace:
            record.exc_info = None
            record.exc_text = None
            record.stack_info = None

        return True


class DuplicateFilter(logging.Filter):
    """Filter to prevent duplicate log messages."""

    def __init__(self, max_duplicates: int = 5, time_window: float = 60.0):
        """
        Initialize duplicate filter.

        Args:
            max_duplicates: Maximum duplicate messages allowed
            time_window: Time window in seconds for duplicate detection
        """
        super().__init__()
        self.max_duplicates = max_duplicates
        self.time_window = time_window
        self._message_counts: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter duplicate messages."""
        with self._lock:
            # Create message key
            message_key = f"{record.name}:{record.levelname}:{record.getMessage()}"
            current_time = time.time()

            # Clean old timestamps
            timestamps = self._message_counts[message_key]
            timestamps[:] = [
                t for t in timestamps if current_time - t <= self.time_window
            ]

            # Check if we've exceeded the limit
            if len(timestamps) >= self.max_duplicates:
                return False

            # Add current timestamp
            timestamps.append(current_time)
            return True
