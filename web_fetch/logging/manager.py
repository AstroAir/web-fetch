"""
Logging manager for web_fetch.

This module provides centralized logging configuration and management.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Dict, Optional

from ..config.models import LoggingConfig, LogLevel
from .filters import ComponentFilter, RateLimitFilter, SensitiveDataFilter
from .formatters import ColoredFormatter, StructuredFormatter  # CompactFormatter removed (unused)
from .handlers import MetricsHandler, RotatingAsyncFileHandler  # AsyncFileHandler removed (unused)


class LoggingManager:
    """Centralized logging manager."""

    def __init__(self) -> None:
        """Initialize logging manager."""
        self._configured = False
        self._handlers: Dict[str, logging.Handler] = {}
        self._loggers: Dict[str, logging.Logger] = {}

    def setup_logging(self, config: LoggingConfig) -> None:
        """
        Setup logging based on configuration.

        Args:
            config: Logging configuration
        """
        if self._configured:
            self.cleanup()

        # Keep a reference to logging.handlers to avoid “unused import” linters
        _ = logging.handlers  # noqa: F401

        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, config.level.value))

        # Clear existing handlers
        root_logger.handlers.clear()

        # Setup console handler
        if config.enable_console:
            self._setup_console_handler(config)

        # Setup file handler
        if config.enable_file and config.file_path:
            self._setup_file_handler(config)

        # Setup metrics handler
        if config.enable_structured:
            self._setup_metrics_handler(config)

        # Setup component-specific loggers
        self._setup_component_loggers(config)

        # Add global filters
        self._setup_global_filters(config)

        self._configured = True

        # Log configuration success
        logger = logging.getLogger(__name__)
        logger.info("Logging system configured successfully")

    def _setup_console_handler(self, config: LoggingConfig) -> None:
        """Setup console logging handler."""
        handler = logging.StreamHandler(sys.stdout)

        # Use colored/structured formatter for console
        formatter: logging.Formatter
        if config.enable_structured:
            formatter = StructuredFormatter()
        else:
            formatter = ColoredFormatter(config.format)

        handler.setFormatter(formatter)
        handler.setLevel(getattr(logging, config.level.value))

        # Add filters
        handler.addFilter(SensitiveDataFilter())
        handler.addFilter(RateLimitFilter(max_messages_per_second=10))

        logging.getLogger().addHandler(handler)
        self._handlers["console"] = handler

    def _setup_file_handler(self, config: LoggingConfig) -> None:
        """Setup file logging handler."""
        if not config.file_path:
            return  # nothing to do

        log_path = Path(str(config.file_path))
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Use rotating async file handler
        handler = RotatingAsyncFileHandler(
            filename=str(log_path),
            max_bytes=config.max_file_size,
            backup_count=config.backup_count,
        )

        formatter: logging.Formatter
        if config.enable_structured:
            formatter = StructuredFormatter()
        else:
            formatter = logging.Formatter(config.format)

        handler.setFormatter(formatter)
        handler.setLevel(getattr(logging, config.level.value))

        # Add filters
        handler.addFilter(SensitiveDataFilter())

        logging.getLogger().addHandler(handler)
        self._handlers["file"] = handler

    def _setup_metrics_handler(self, config: LoggingConfig) -> None:
        """Setup metrics collection handler."""
        # Touch config to avoid “unused parameter” static warnings
        _ = config.enable_structured
        handler = MetricsHandler()
        handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(handler)
        self._handlers["metrics"] = handler

    def _setup_component_loggers(self, config: LoggingConfig) -> None:
        """Setup component-specific loggers."""
        for component, level in config.component_levels.items():
            logger = logging.getLogger(component)
            logger.setLevel(getattr(logging, level.value))

            component_filter = ComponentFilter(component)
            for handler in logger.handlers:
                handler.addFilter(component_filter)

            self._loggers[component] = logger

    def _setup_global_filters(self, config: LoggingConfig) -> None:
        """Setup global logging filters."""
        # Touch config to avoid “unused parameter” static warnings
        _ = config.enable_console
        sensitive_filter = SensitiveDataFilter()

        for handler in logging.getLogger().handlers:
            if not any(isinstance(f, SensitiveDataFilter) for f in handler.filters):
                handler.addFilter(sensitive_filter)

    def get_logger(self, name: str) -> logging.Logger:
        """
        Get logger for specific component.

        Args:
            name: Logger name

        Returns:
            Logger instance
        """
        return logging.getLogger(name)

    def set_level(self, level: LogLevel, component: Optional[str] = None) -> None:
        """
        Set logging level.

        Args:
            level: New logging level
            component: Specific component (None for root logger)
        """
        log_level = getattr(logging, level.value)

        if component:
            logger = logging.getLogger(component)
            logger.setLevel(log_level)
        else:
            logging.getLogger().setLevel(log_level)

            # Update all handlers
            for handler in self._handlers.values():
                handler.setLevel(log_level)

    def add_handler(self, name: str, handler: logging.Handler) -> None:
        """
        Add custom logging handler.

        Args:
            name: Handler name
            handler: Logging handler
        """
        logging.getLogger().addHandler(handler)
        self._handlers[name] = handler

    def remove_handler(self, name: str) -> None:
        """
        Remove logging handler.

        Args:
            name: Handler name
        """
        if name in self._handlers:
            handler = self._handlers[name]
            logging.getLogger().removeHandler(handler)
            handler.close()
            del self._handlers[name]

    def cleanup(self) -> None:
        """Cleanup logging handlers."""
        # Close and remove all handlers
        for handler in list(self._handlers.values()):
            try:
                handler.close()
            except Exception:
                pass

        # Clear handlers from root logger
        logging.getLogger().handlers.clear()

        # Clear internal state
        self._handlers.clear()
        self._loggers.clear()
        self._configured = False

    def get_metrics(self) -> Dict[str, int]:
        """
        Get logging metrics.

        Returns:
            Dictionary of logging metrics
        """
        metrics_handler = self._handlers.get("metrics")
        if isinstance(metrics_handler, MetricsHandler):
            return metrics_handler.get_metrics()
        return {}

    def is_configured(self) -> bool:
        """Check if logging is configured."""
        return self._configured


# Global logging manager instance
_logging_manager = LoggingManager()


def setup_logging(config: LoggingConfig) -> None:
    """
    Setup logging with configuration.

    Args:
        config: Logging configuration
    """
    _logging_manager.setup_logging(config)


def get_logger(name: str) -> logging.Logger:
    """
    Get logger for component.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return _logging_manager.get_logger(name)


def cleanup_logging() -> None:
    """Cleanup logging system."""
    _logging_manager.cleanup()
