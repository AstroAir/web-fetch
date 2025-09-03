"""
FTP functionality for the web_fetch library.

This package provides comprehensive FTP support including:
- Async FTP client with connection pooling
- File upload/download with progress tracking
- Batch operations and parallel transfers
- Streaming support for large files
- File verification and integrity checking
"""

from .fetcher import (
    FTPFetcher,
    ftp_download_batch,
    ftp_download_file,
    ftp_get_file_info,
    ftp_list_directory,
)
from .models import (
    FTPAuthType,
    FTPBatchRequest,
    FTPBatchResult,
    FTPConfig,
    FTPConnectionInfo,
    FTPFileInfo,
    FTPMode,
    FTPProgressInfo,
    FTPRequest,
    FTPResult,
    FTPTransferMode,
    FTPVerificationMethod,
    FTPVerificationResult,
)

# Performance optimization modules
from .metrics import (
    get_metrics_collector,
    reset_global_metrics,
    FTPMetricsCollector,
    TransferMetrics,
    ConnectionPoolMetrics,
    PerformanceSnapshot,
)
from .profiler import (
    get_profiler,
    profile,
    FTPProfiler,
    ProfileResult,
)
from .circuit_breaker import (
    get_circuit_breaker,
    reset_circuit_breaker,
    FTPCircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerState,
    CircuitBreakerError,
)
from .retry import (
    get_retry_manager,
    reset_retry_manager,
    FTPRetryManager,
    RetryConfig,
    RetryStrategy,
    RetryableError,
    NonRetryableError,
)
from .config_presets import (
    FTPConfigPresets,
    OptimizedPreset,
    UseCase,
)
from .monitoring import (
    get_monitor,
    reset_monitor,
    FTPMonitor,
    PerformanceReport,
    OptimizationRecommendation,
)

__all__ = [
    # Main FTP client
    "FTPFetcher",
    # Convenience functions
    "ftp_download_file",
    "ftp_download_batch",
    "ftp_list_directory",
    "ftp_get_file_info",
    # Models and configuration
    "FTPConfig",
    "FTPRequest",
    "FTPResult",
    "FTPBatchRequest",
    "FTPBatchResult",
    "FTPFileInfo",
    "FTPProgressInfo",
    "FTPConnectionInfo",
    "FTPVerificationResult",
    # Enums
    "FTPMode",
    "FTPAuthType",
    "FTPTransferMode",
    "FTPVerificationMethod",

    # Performance optimization modules
    # Metrics and monitoring
    "get_metrics_collector",
    "reset_global_metrics",
    "FTPMetricsCollector",
    "TransferMetrics",
    "ConnectionPoolMetrics",
    "PerformanceSnapshot",

    # Profiling
    "get_profiler",
    "profile",
    "FTPProfiler",
    "ProfileResult",

    # Circuit breaker
    "get_circuit_breaker",
    "reset_circuit_breaker",
    "FTPCircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerState",
    "CircuitBreakerError",

    # Retry mechanisms
    "get_retry_manager",
    "reset_retry_manager",
    "FTPRetryManager",
    "RetryConfig",
    "RetryStrategy",
    "RetryableError",
    "NonRetryableError",

    # Configuration presets
    "FTPConfigPresets",
    "OptimizedPreset",
    "UseCase",

    # Comprehensive monitoring
    "get_monitor",
    "reset_monitor",
    "FTPMonitor",
    "PerformanceReport",
    "OptimizationRecommendation",
]
