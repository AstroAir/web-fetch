"""
Custom logging handlers for web_fetch.

This module provides async file handlers, metrics collection, and other
specialized logging handlers.
"""

import asyncio
import logging
import logging.handlers
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, Optional, TextIO, cast


class AsyncFileHandler(logging.Handler):
    """Asynchronous file logging handler."""

    def __init__(self, filename: str, mode: str = "a", encoding: str = "utf-8"):
        """
        Initialize async file handler.

        Args:
            filename: Log file path
            mode: File open mode
            encoding: File encoding
        """
        super().__init__()
        self.filename = filename
        self.mode = mode
        self.encoding = encoding
        self._file: Optional[TextIO] = None
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._task: Optional[asyncio.Task[None]] = None
        self._lock = threading.Lock()
        self._closed = False

    def emit(self, record: logging.LogRecord) -> None:
        """Emit log record asynchronously."""
        if self._closed:
            return

        try:
            # Format the record
            msg = self.format(record)

            # Add to queue for async processing
            if self._queue is not None:
                try:
                    self._queue.put_nowait(msg + "\n")
                except asyncio.QueueFull:
                    # Drop message if queue is full
                    pass
        except Exception:
            self.handleError(record)

    async def _writer_task(self) -> None:
        """Async task for writing log messages."""
        try:
            # Open file
            Path(self.filename).parent.mkdir(parents=True, exist_ok=True)
            self._file = cast(
                TextIO, open(self.filename, self.mode, encoding=self.encoding)
            )

            while not self._closed:
                try:
                    # Wait for message with timeout
                    msg = await asyncio.wait_for(self._queue.get(), timeout=1.0)

                    # Write to file
                    if self._file:
                        self._file.write(msg)
                        self._file.flush()

                except asyncio.TimeoutError:
                    # Flush periodically even without messages
                    if self._file:
                        self._file.flush()
                except Exception:
                    break

        finally:
            if self._file:
                self._file.close()
                self._file = None

    def start(self) -> None:
        """Start the async writer task."""
        if self._task is None:
            self._task = asyncio.create_task(self._writer_task())

    def close(self) -> None:
        """Close the handler."""
        with self._lock:
            if self._closed:
                return

            self._closed = True

            # Cancel task
            if self._task:
                self._task.cancel()
                self._task = None

            # Close file
            if self._file:
                self._file.close()
                self._file = None

        super().close()


class RotatingAsyncFileHandler(AsyncFileHandler):
    """Rotating async file handler."""

    def __init__(
        self,
        filename: str,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        encoding: str = "utf-8",
    ):
        """
        Initialize rotating async file handler.

        Args:
            filename: Log file path
            max_bytes: Maximum file size before rotation
            backup_count: Number of backup files to keep
            encoding: File encoding
        """
        super().__init__(filename, "a", encoding)
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._current_size = 0

    async def _writer_task(self) -> None:
        """Async task for writing with rotation."""
        try:
            # Open file and get current size
            Path(self.filename).parent.mkdir(parents=True, exist_ok=True)

            if Path(self.filename).exists():
                self._current_size = Path(self.filename).stat().st_size

            self._file = cast(
                TextIO, open(self.filename, self.mode, encoding=self.encoding)
            )

            while not self._closed:
                try:
                    # Wait for message
                    msg = await asyncio.wait_for(self._queue.get(), timeout=1.0)

                    # Check if rotation is needed
                    if (
                        self._current_size + len(msg.encode(self.encoding))
                        > self.max_bytes
                    ):
                        await self._rotate()

                    # Write to file
                    if self._file:
                        self._file.write(msg)
                        self._file.flush()
                    self._current_size += len(msg.encode(self.encoding))

                except asyncio.TimeoutError:
                    if self._file:
                        self._file.flush()
                except Exception:
                    break

        finally:
            if self._file:
                self._file.close()
                self._file = None

    async def _rotate(self) -> None:
        """Rotate log files."""
        if self._file:
            self._file.close()

        # Rotate backup files
        for i in range(self.backup_count - 1, 0, -1):
            old_name = f"{self.filename}.{i}"
            new_name = f"{self.filename}.{i + 1}"

            if Path(old_name).exists():
                if Path(new_name).exists():
                    Path(new_name).unlink()
                Path(old_name).rename(new_name)

        # Move current file to .1
        if Path(self.filename).exists():
            backup_name = f"{self.filename}.1"
            if Path(backup_name).exists():
                Path(backup_name).unlink()
            Path(self.filename).rename(backup_name)

        # Open new file
        self._file = open(self.filename, "w", encoding=self.encoding)
        self._current_size = 0


class MetricsHandler(logging.Handler):
    """Handler for collecting logging metrics."""

    def __init__(self) -> None:
        """Initialize metrics handler."""
        super().__init__()
        self._metrics: Dict[str, int] = defaultdict(int)
        self._recent_logs: deque[Dict[str, Any]] = deque(maxlen=1000)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        """Collect metrics from log record."""
        with self._lock:
            # Count by level
            self._metrics[f"logs_{record.levelname.lower()}"] += 1
            self._metrics["logs_total"] += 1

            # Count by logger
            logger_key = f"logger_{record.name.replace('.', '_')}"
            self._metrics[logger_key] += 1

            # Track recent logs
            self._recent_logs.append(
                {
                    "timestamp": time.time(),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage()[:100],  # Truncate long messages
                }
            )

            # Count errors and warnings
            if record.levelno >= logging.ERROR:
                self._metrics["errors_total"] += 1
            elif record.levelno >= logging.WARNING:
                self._metrics["warnings_total"] += 1

    def get_metrics(self) -> Dict[str, int]:
        """Get collected metrics."""
        with self._lock:
            return dict(self._metrics)

    def get_recent_logs(self) -> list[Dict[str, Any]]:
        """Get recent log entries."""
        with self._lock:
            return list(self._recent_logs)

    def reset_metrics(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._metrics.clear()
            self._recent_logs.clear()


class BufferedHandler(logging.Handler):
    """Buffered logging handler for high-performance scenarios."""

    def __init__(self, target_handler: logging.Handler, buffer_size: int = 100):
        """
        Initialize buffered handler.

        Args:
            target_handler: Handler to buffer for
            buffer_size: Number of records to buffer
        """
        super().__init__()
        self.target_handler = target_handler
        self.buffer_size = buffer_size
        self._buffer: list[logging.LogRecord] = []
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        """Buffer log record."""
        with self._lock:
            self._buffer.append(record)

            if len(self._buffer) >= self.buffer_size:
                self.flush()

    def flush(self) -> None:
        """Flush buffered records."""
        with self._lock:
            for record in self._buffer:
                self.target_handler.emit(record)
            self._buffer.clear()

            if hasattr(self.target_handler, "flush"):
                self.target_handler.flush()

    def close(self) -> None:
        """Close handler and flush remaining records."""
        self.flush()
        self.target_handler.close()
        super().close()
