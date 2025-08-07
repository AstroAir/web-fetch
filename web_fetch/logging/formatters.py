"""
Custom logging formatters for web_fetch.

This module provides various logging formatters including structured JSON,
colored console output, and compact formats.
"""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict


class StructuredFormatter(logging.Formatter):
    """JSON structured logging formatter."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Base log data
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                          'filename', 'module', 'lineno', 'funcName', 'created',
                          'msecs', 'relativeCreated', 'thread', 'threadName',
                          'processName', 'process', 'getMessage', 'exc_info',
                          'exc_text', 'stack_info']:
                log_data[key] = value
        
        return json.dumps(log_data, default=str, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """Colored console logging formatter."""
    
    # Color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    def __init__(self, fmt: str = None, datefmt: str = None, use_colors: bool = None):
        """
        Initialize colored formatter.
        
        Args:
            fmt: Log format string
            datefmt: Date format string
            use_colors: Whether to use colors (auto-detect if None)
        """
        super().__init__(fmt, datefmt)
        
        # Auto-detect color support
        if use_colors is None:
            use_colors = (
                hasattr(sys.stdout, 'isatty') and 
                sys.stdout.isatty() and 
                sys.platform != 'win32'
            )
        
        self.use_colors = use_colors
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        if not self.use_colors:
            return super().format(record)
        
        # Get color for level
        color = self.COLORS.get(record.levelname, '')
        
        # Format the record
        formatted = super().format(record)
        
        # Apply colors
        if color:
            # Color the level name
            level_colored = f"{color}{self.BOLD}{record.levelname}{self.RESET}"
            formatted = formatted.replace(record.levelname, level_colored, 1)
        
        return formatted


class CompactFormatter(logging.Formatter):
    """Compact logging formatter for high-volume logs."""
    
    def __init__(self):
        """Initialize compact formatter."""
        # Very compact format
        super().__init__(
            fmt='%(asctime)s [%(levelname).1s] %(name)s: %(message)s',
            datefmt='%H:%M:%S'
        )
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record compactly."""
        # Truncate long logger names
        if len(record.name) > 20:
            parts = record.name.split('.')
            if len(parts) > 1:
                record.name = f"{parts[0]}...{parts[-1]}"
            else:
                record.name = record.name[:17] + "..."
        
        # Truncate long messages
        message = record.getMessage()
        if len(message) > 100:
            message = message[:97] + "..."
            record.msg = message
            record.args = ()
        
        return super().format(record)


class PerformanceFormatter(logging.Formatter):
    """Performance-focused logging formatter."""
    
    def __init__(self):
        """Initialize performance formatter."""
        super().__init__(
            fmt='%(asctime)s [%(levelname)s] %(name)s - %(message)s [%(duration)sms]',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with performance info."""
        # Add duration if available
        if not hasattr(record, 'duration'):
            record.duration = 0
        
        # Add memory usage if available
        if hasattr(record, 'memory_mb'):
            record.message = f"{record.getMessage()} (mem: {record.memory_mb}MB)"
        
        return super().format(record)


class RequestFormatter(logging.Formatter):
    """Specialized formatter for HTTP request logs."""
    
    def __init__(self):
        """Initialize request formatter."""
        super().__init__(
            fmt='%(asctime)s [%(levelname)s] %(method)s %(url)s - %(status_code)s %(response_time)sms',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def format(self, record: logging.LogRecord) -> str:
        """Format HTTP request log record."""
        # Set defaults for missing fields
        if not hasattr(record, 'method'):
            record.method = 'GET'
        if not hasattr(record, 'url'):
            record.url = 'unknown'
        if not hasattr(record, 'status_code'):
            record.status_code = 0
        if not hasattr(record, 'response_time'):
            record.response_time = 0
        
        return super().format(record)
