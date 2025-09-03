"""
Performance metrics and monitoring for FTP operations.

This module provides comprehensive metrics collection, performance profiling,
and monitoring capabilities for the FTP component.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from threading import Lock
import asyncio


@dataclass
class TransferMetrics:
    """Metrics for a single file transfer operation."""
    
    url: str
    operation: str  # download, upload, list, etc.
    start_time: float
    end_time: Optional[float] = None
    bytes_transferred: int = 0
    total_bytes: Optional[int] = None
    chunk_size: int = 0
    connection_reused: bool = False
    error: Optional[str] = None
    
    @property
    def duration(self) -> float:
        """Get transfer duration in seconds."""
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time
    
    @property
    def transfer_rate(self) -> float:
        """Get transfer rate in bytes per second."""
        duration = self.duration
        if duration <= 0:
            return 0.0
        return self.bytes_transferred / duration
    
    @property
    def is_complete(self) -> bool:
        """Check if transfer is complete."""
        return self.end_time is not None


@dataclass
class ConnectionPoolMetrics:
    """Metrics for connection pool performance."""
    
    host: str
    port: int
    total_connections_created: int = 0
    total_connections_reused: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    failed_connections: int = 0
    cleanup_operations: int = 0
    average_connection_lifetime: float = 0.0
    
    @property
    def reuse_ratio(self) -> float:
        """Get connection reuse ratio."""
        total = self.total_connections_created + self.total_connections_reused
        if total == 0:
            return 0.0
        return self.total_connections_reused / total
    
    @property
    def total_connections(self) -> int:
        """Get total number of connections."""
        return self.active_connections + self.idle_connections


@dataclass
class PerformanceSnapshot:
    """Snapshot of current performance metrics."""
    
    timestamp: datetime
    active_transfers: int
    total_transfers_completed: int
    total_bytes_transferred: int
    average_transfer_rate: float
    connection_pool_efficiency: float
    error_rate: float
    memory_usage_mb: Optional[float] = None


class FTPMetricsCollector:
    """
    Comprehensive metrics collector for FTP operations.
    
    Collects and aggregates performance metrics including transfer rates,
    connection pool efficiency, error rates, and resource usage.
    """
    
    def __init__(self, max_history_size: int = 1000):
        """Initialize the metrics collector."""
        self.max_history_size = max_history_size
        self._lock = Lock()
        
        # Transfer metrics
        self._active_transfers: Dict[str, TransferMetrics] = {}
        self._completed_transfers: deque[TransferMetrics] = deque(maxlen=max_history_size)

        # Connection pool metrics
        self._connection_metrics: Dict[str, ConnectionPoolMetrics] = {}

        # Performance history
        self._performance_history: deque[PerformanceSnapshot] = deque(maxlen=100)  # Last 100 snapshots
        
        # Error tracking
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._last_snapshot_time = time.time()
    
    def start_transfer(self, transfer_id: str, url: str, operation: str, 
                      chunk_size: int = 0) -> None:
        """Start tracking a transfer operation."""
        with self._lock:
            self._active_transfers[transfer_id] = TransferMetrics(
                url=url,
                operation=operation,
                start_time=time.time(),
                chunk_size=chunk_size
            )
    
    def update_transfer(self, transfer_id: str, bytes_transferred: int, 
                       total_bytes: Optional[int] = None) -> None:
        """Update transfer progress."""
        with self._lock:
            if transfer_id in self._active_transfers:
                metrics = self._active_transfers[transfer_id]
                metrics.bytes_transferred = bytes_transferred
                if total_bytes is not None:
                    metrics.total_bytes = total_bytes
    
    def complete_transfer(self, transfer_id: str, success: bool = True, 
                         error: Optional[str] = None) -> None:
        """Mark a transfer as completed."""
        with self._lock:
            if transfer_id in self._active_transfers:
                metrics = self._active_transfers[transfer_id]
                metrics.end_time = time.time()
                if error:
                    metrics.error = error
                    self._error_counts[error] += 1
                
                self._completed_transfers.append(metrics)
                del self._active_transfers[transfer_id]
    
    def record_connection_created(self, host: str, port: int) -> None:
        """Record a new connection creation."""
        with self._lock:
            key = f"{host}:{port}"
            if key not in self._connection_metrics:
                self._connection_metrics[key] = ConnectionPoolMetrics(host, port)
            self._connection_metrics[key].total_connections_created += 1
    
    def record_connection_reused(self, host: str, port: int) -> None:
        """Record a connection reuse."""
        with self._lock:
            key = f"{host}:{port}"
            if key not in self._connection_metrics:
                self._connection_metrics[key] = ConnectionPoolMetrics(host, port)
            self._connection_metrics[key].total_connections_reused += 1
    
    def update_connection_pool_state(self, host: str, port: int, 
                                   active: int, idle: int) -> None:
        """Update connection pool state."""
        with self._lock:
            key = f"{host}:{port}"
            if key not in self._connection_metrics:
                self._connection_metrics[key] = ConnectionPoolMetrics(host, port)
            
            metrics = self._connection_metrics[key]
            metrics.active_connections = active
            metrics.idle_connections = idle
    
    def get_current_snapshot(self) -> PerformanceSnapshot:
        """Get current performance snapshot."""
        with self._lock:
            now = datetime.now()
            
            # Calculate metrics
            active_count = len(self._active_transfers)
            completed_count = len(self._completed_transfers)
            
            # Calculate average transfer rate from recent transfers
            recent_transfers = list(self._completed_transfers)[-50:]  # Last 50 transfers
            if recent_transfers:
                total_bytes = sum(t.bytes_transferred for t in recent_transfers)
                total_time = sum(t.duration for t in recent_transfers)
                avg_rate = total_bytes / total_time if total_time > 0 else 0.0
            else:
                avg_rate = 0.0
            
            # Calculate connection pool efficiency
            total_created = sum(m.total_connections_created for m in self._connection_metrics.values())
            total_reused = sum(m.total_connections_reused for m in self._connection_metrics.values())
            pool_efficiency = total_reused / (total_created + total_reused) if (total_created + total_reused) > 0 else 0.0
            
            # Calculate error rate
            total_errors = sum(self._error_counts.values())
            error_rate = total_errors / (completed_count + total_errors) if (completed_count + total_errors) > 0 else 0.0
            
            # Calculate total bytes transferred
            total_bytes_transferred = sum(t.bytes_transferred for t in recent_transfers)
            
            snapshot = PerformanceSnapshot(
                timestamp=now,
                active_transfers=active_count,
                total_transfers_completed=completed_count,
                total_bytes_transferred=total_bytes_transferred,
                average_transfer_rate=avg_rate,
                connection_pool_efficiency=pool_efficiency,
                error_rate=error_rate
            )
            
            self._performance_history.append(snapshot)
            return snapshot
    
    def get_transfer_statistics(self) -> Dict[str, Any]:
        """Get comprehensive transfer statistics."""
        with self._lock:
            if not self._completed_transfers:
                return {}
            
            transfers = list(self._completed_transfers)
            rates = [t.transfer_rate for t in transfers if t.transfer_rate > 0]
            durations = [t.duration for t in transfers]
            
            return {
                "total_transfers": len(transfers),
                "successful_transfers": len([t for t in transfers if t.error is None]),
                "failed_transfers": len([t for t in transfers if t.error is not None]),
                "average_transfer_rate": sum(rates) / len(rates) if rates else 0.0,
                "max_transfer_rate": max(rates) if rates else 0.0,
                "min_transfer_rate": min(rates) if rates else 0.0,
                "average_duration": sum(durations) / len(durations) if durations else 0.0,
                "total_bytes_transferred": sum(t.bytes_transferred for t in transfers),
                "error_breakdown": dict(self._error_counts)
            }
    
    def get_connection_statistics(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        with self._lock:
            if not self._connection_metrics:
                return {}
            
            total_created = sum(m.total_connections_created for m in self._connection_metrics.values())
            total_reused = sum(m.total_connections_reused for m in self._connection_metrics.values())
            total_active = sum(m.active_connections for m in self._connection_metrics.values())
            total_idle = sum(m.idle_connections for m in self._connection_metrics.values())
            
            return {
                "total_connections_created": total_created,
                "total_connections_reused": total_reused,
                "reuse_ratio": total_reused / (total_created + total_reused) if (total_created + total_reused) > 0 else 0.0,
                "active_connections": total_active,
                "idle_connections": total_idle,
                "connection_pools": len(self._connection_metrics),
                "pool_details": {k: {
                    "reuse_ratio": v.reuse_ratio,
                    "total_connections": v.total_connections,
                    "failed_connections": v.failed_connections
                } for k, v in self._connection_metrics.items()}
            }
    
    def reset_metrics(self) -> None:
        """Reset all collected metrics."""
        with self._lock:
            self._active_transfers.clear()
            self._completed_transfers.clear()
            self._connection_metrics.clear()
            self._performance_history.clear()
            self._error_counts.clear()


# Global metrics collector instance
_global_metrics_collector: Optional[FTPMetricsCollector] = None


def get_metrics_collector() -> FTPMetricsCollector:
    """Get the global metrics collector instance."""
    global _global_metrics_collector
    if _global_metrics_collector is None:
        _global_metrics_collector = FTPMetricsCollector()
    return _global_metrics_collector


def reset_global_metrics() -> None:
    """Reset the global metrics collector."""
    global _global_metrics_collector
    if _global_metrics_collector is not None:
        _global_metrics_collector.reset_metrics()
