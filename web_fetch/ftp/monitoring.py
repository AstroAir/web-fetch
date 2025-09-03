"""
Comprehensive monitoring and reporting for FTP operations.

This module provides detailed performance monitoring, optimization recommendations,
and comprehensive reporting capabilities for the FTP component.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import json

from .metrics import get_metrics_collector, PerformanceSnapshot
from .profiler import get_profiler
from .circuit_breaker import get_circuit_breaker
from .retry import get_retry_manager


@dataclass
class OptimizationRecommendation:
    """A specific optimization recommendation."""

    category: str  # performance, reliability, memory, etc.
    priority: str  # high, medium, low
    title: str
    description: str
    current_value: Any
    recommended_value: Any
    expected_impact: str
    implementation_effort: str  # low, medium, high


@dataclass
class PerformanceReport:
    """Comprehensive performance report."""

    timestamp: datetime
    duration_hours: float

    # Transfer statistics
    total_transfers: int
    successful_transfers: int
    failed_transfers: int
    total_bytes_transferred: int
    average_transfer_rate: float
    peak_transfer_rate: float

    # Connection statistics
    connection_pool_efficiency: float
    average_connection_reuse: float
    connection_failures: int

    # Error statistics
    error_rate: float
    top_errors: List[Tuple[str, int]]

    # Performance metrics
    average_response_time: float
    p95_response_time: float
    p99_response_time: float

    # Resource usage
    peak_memory_usage: Optional[float] = None
    average_cpu_usage: Optional[float] = None

    # Recommendations
    recommendations: List[OptimizationRecommendation] = field(default_factory=list)


class FTPMonitor:
    """
    Comprehensive monitoring and reporting for FTP operations.

    Provides performance analysis, optimization recommendations,
    and detailed reporting capabilities.
    """

    def __init__(self) -> None:
        """Initialize the FTP monitor."""
        self._metrics = get_metrics_collector()
        self._profiler = get_profiler()
        self._circuit_breaker = get_circuit_breaker()
        self._retry_manager = get_retry_manager()
        self._start_time = time.time()

    def get_current_performance_snapshot(self) -> PerformanceSnapshot:
        """Get current performance snapshot."""
        return self._metrics.get_current_snapshot()

    def get_transfer_statistics(self) -> Dict[str, Any]:
        """Get comprehensive transfer statistics."""
        return self._metrics.get_transfer_statistics()

    def get_connection_statistics(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        return self._metrics.get_connection_statistics()

    def get_profiling_summary(self) -> Dict[str, Any]:
        """Get profiling summary and bottlenecks."""
        return {
            "summary": self._profiler.get_profile_summary(),
            "bottlenecks": self._profiler.get_bottlenecks(top_n=10)
        }

    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get circuit breaker status for all hosts."""
        result = asyncio.run(self._circuit_breaker.get_stats())
        if isinstance(result, dict):
            return result
        else:
            return {"stats": result}

    def get_retry_statistics(self) -> Dict[str, Any]:
        """Get retry statistics."""
        return self._retry_manager.get_stats()

    def generate_performance_report(self, hours_back: float = 24.0) -> PerformanceReport:
        """
        Generate comprehensive performance report.

        Args:
            hours_back: How many hours back to analyze

        Returns:
            Detailed performance report with recommendations
        """
        # Get basic statistics
        transfer_stats = self.get_transfer_statistics()
        connection_stats = self.get_connection_statistics()
        profiling_stats = self.get_profiling_summary()

        # Calculate metrics
        total_transfers = transfer_stats.get("total_transfers", 0)
        successful_transfers = transfer_stats.get("successful_transfers", 0)
        failed_transfers = transfer_stats.get("failed_transfers", 0)

        error_rate = failed_transfers / total_transfers if total_transfers > 0 else 0.0

        # Create report
        report = PerformanceReport(
            timestamp=datetime.now(),
            duration_hours=hours_back,
            total_transfers=total_transfers,
            successful_transfers=successful_transfers,
            failed_transfers=failed_transfers,
            total_bytes_transferred=transfer_stats.get("total_bytes_transferred", 0),
            average_transfer_rate=transfer_stats.get("average_transfer_rate", 0.0),
            peak_transfer_rate=transfer_stats.get("max_transfer_rate", 0.0),
            connection_pool_efficiency=connection_stats.get("reuse_ratio", 0.0),
            average_connection_reuse=connection_stats.get("reuse_ratio", 0.0),
            connection_failures=sum(
                pool.get("failed_connections", 0)
                for pool in connection_stats.get("pool_details", {}).values()
            ),
            error_rate=error_rate,
            top_errors=list(transfer_stats.get("error_breakdown", {}).items())[:10],
            average_response_time=transfer_stats.get("average_duration", 0.0),
            p95_response_time=0.0,  # Would need percentile calculation
            p99_response_time=0.0,  # Would need percentile calculation
        )

        # Generate recommendations
        report.recommendations = self._generate_recommendations(
            transfer_stats, connection_stats, profiling_stats
        )

        return report

    def _generate_recommendations(
        self,
        transfer_stats: Dict[str, Any],
        connection_stats: Dict[str, Any],
        profiling_stats: Dict[str, Any]
    ) -> List[OptimizationRecommendation]:
        """Generate optimization recommendations based on statistics."""
        recommendations = []

        # Analyze transfer performance
        avg_rate = transfer_stats.get("average_transfer_rate", 0.0)
        if avg_rate < 100 * 1024:  # Less than 100KB/s
            recommendations.append(OptimizationRecommendation(
                category="performance",
                priority="high",
                title="Low Transfer Rate Detected",
                description="Average transfer rate is below optimal threshold. Consider increasing chunk size or enabling parallel downloads.",
                current_value=f"{avg_rate / 1024:.1f} KB/s",
                recommended_value="Increase chunk_size to 256KB+ or enable parallel downloads",
                expected_impact="2-5x transfer speed improvement",
                implementation_effort="low"
            ))

        # Analyze connection pool efficiency
        reuse_ratio = connection_stats.get("reuse_ratio", 0.0)
        if reuse_ratio < 0.5:  # Less than 50% reuse
            recommendations.append(OptimizationRecommendation(
                category="performance",
                priority="medium",
                title="Low Connection Reuse",
                description="Connection pool reuse ratio is low. Consider increasing max_connections_per_host or enabling connection health checks.",
                current_value=f"{reuse_ratio:.1%}",
                recommended_value="Increase max_connections_per_host to 5+ and enable health checks",
                expected_impact="Reduced connection overhead, 10-20% performance improvement",
                implementation_effort="low"
            ))

        # Analyze error rates
        total_transfers = transfer_stats.get("total_transfers", 0)
        failed_transfers = transfer_stats.get("failed_transfers", 0)
        error_rate = failed_transfers / total_transfers if total_transfers > 0 else 0.0

        if error_rate > 0.1:  # More than 10% error rate
            recommendations.append(OptimizationRecommendation(
                category="reliability",
                priority="high",
                title="High Error Rate",
                description="Error rate is above acceptable threshold. Consider implementing circuit breakers and increasing retry attempts.",
                current_value=f"{error_rate:.1%}",
                recommended_value="Enable circuit breakers and increase max_retries to 5+",
                expected_impact="Improved reliability and reduced failed transfers",
                implementation_effort="medium"
            ))

        # Analyze profiling bottlenecks
        bottlenecks = profiling_stats.get("bottlenecks", [])
        if bottlenecks:
            top_bottleneck = bottlenecks[0]
            if top_bottleneck.get("impact_score", 0) > 50:
                recommendations.append(OptimizationRecommendation(
                    category="performance",
                    priority="high",
                    title=f"Performance Bottleneck: {top_bottleneck['function_name']}",
                    description=f"Function {top_bottleneck['function_name']} is consuming significant resources.",
                    current_value=f"{top_bottleneck['avg_time']:.3f}s avg, {top_bottleneck['call_count']} calls",
                    recommended_value="Optimize function implementation or reduce call frequency",
                    expected_impact="10-30% overall performance improvement",
                    implementation_effort="high"
                ))

        # Memory usage recommendations
        overall_stats = profiling_stats.get("summary", {}).get("overall_stats", {})
        avg_memory = overall_stats.get("total_memory_used", 0)
        if avg_memory > 100 * 1024 * 1024:  # More than 100MB
            recommendations.append(OptimizationRecommendation(
                category="memory",
                priority="medium",
                title="High Memory Usage",
                description="Memory usage is high. Consider reducing chunk sizes or limiting concurrent downloads.",
                current_value=f"{avg_memory / 1024 / 1024:.1f} MB",
                recommended_value="Reduce chunk_size to 64KB or limit max_concurrent_downloads to 3",
                expected_impact="50-70% memory usage reduction",
                implementation_effort="low"
            ))

        return recommendations

    def export_report(self, report: PerformanceReport, format: str = "json") -> str:
        """
        Export performance report in specified format.

        Args:
            report: Performance report to export
            format: Export format ("json", "text", "csv")

        Returns:
            Formatted report string
        """
        if format.lower() == "json":
            return self._export_json(report)
        elif format.lower() == "text":
            return self._export_text(report)
        elif format.lower() == "csv":
            return self._export_csv(report)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def _export_json(self, report: PerformanceReport) -> str:
        """Export report as JSON."""
        # Convert dataclass to dict for JSON serialization
        report_dict = {
            "timestamp": report.timestamp.isoformat(),
            "duration_hours": report.duration_hours,
            "total_transfers": report.total_transfers,
            "successful_transfers": report.successful_transfers,
            "failed_transfers": report.failed_transfers,
            "total_bytes_transferred": report.total_bytes_transferred,
            "average_transfer_rate": report.average_transfer_rate,
            "peak_transfer_rate": report.peak_transfer_rate,
            "connection_pool_efficiency": report.connection_pool_efficiency,
            "average_connection_reuse": report.average_connection_reuse,
            "connection_failures": report.connection_failures,
            "error_rate": report.error_rate,
            "top_errors": report.top_errors,
            "average_response_time": report.average_response_time,
            "p95_response_time": report.p95_response_time,
            "p99_response_time": report.p99_response_time,
            "peak_memory_usage": report.peak_memory_usage,
            "average_cpu_usage": report.average_cpu_usage,
            "recommendations": [
                {
                    "category": rec.category,
                    "priority": rec.priority,
                    "title": rec.title,
                    "description": rec.description,
                    "current_value": str(rec.current_value),
                    "recommended_value": str(rec.recommended_value),
                    "expected_impact": rec.expected_impact,
                    "implementation_effort": rec.implementation_effort
                }
                for rec in report.recommendations
            ]
        }
        return json.dumps(report_dict, indent=2)

    def _export_text(self, report: PerformanceReport) -> str:
        """Export report as human-readable text."""
        lines = [
            "FTP Performance Report",
            "=" * 50,
            f"Generated: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Analysis Period: {report.duration_hours:.1f} hours",
            "",
            "Transfer Statistics:",
            f"  Total Transfers: {report.total_transfers:,}",
            f"  Successful: {report.successful_transfers:,} ({report.successful_transfers/report.total_transfers*100:.1f}%)" if report.total_transfers > 0 else "  Successful: 0",
            f"  Failed: {report.failed_transfers:,} ({report.error_rate*100:.1f}%)",
            f"  Total Bytes: {report.total_bytes_transferred:,} ({report.total_bytes_transferred/1024/1024:.1f} MB)",
            f"  Average Rate: {report.average_transfer_rate/1024:.1f} KB/s",
            f"  Peak Rate: {report.peak_transfer_rate/1024:.1f} KB/s",
            "",
            "Connection Statistics:",
            f"  Pool Efficiency: {report.connection_pool_efficiency:.1%}",
            f"  Connection Reuse: {report.average_connection_reuse:.1%}",
            f"  Connection Failures: {report.connection_failures:,}",
            "",
            "Performance Metrics:",
            f"  Average Response Time: {report.average_response_time:.3f}s",
            f"  95th Percentile: {report.p95_response_time:.3f}s",
            f"  99th Percentile: {report.p99_response_time:.3f}s",
            "",
        ]

        if report.recommendations:
            lines.extend([
                "Optimization Recommendations:",
                "-" * 30,
            ])

            for i, rec in enumerate(report.recommendations, 1):
                lines.extend([
                    f"{i}. {rec.title} ({rec.priority.upper()} PRIORITY)",
                    f"   Category: {rec.category.title()}",
                    f"   Description: {rec.description}",
                    f"   Current: {rec.current_value}",
                    f"   Recommended: {rec.recommended_value}",
                    f"   Expected Impact: {rec.expected_impact}",
                    f"   Implementation Effort: {rec.implementation_effort.title()}",
                    "",
                ])

        return "\n".join(lines)

    def _export_csv(self, report: PerformanceReport) -> str:
        """Export report as CSV."""
        lines = [
            "Metric,Value",
            f"Timestamp,{report.timestamp.isoformat()}",
            f"Duration Hours,{report.duration_hours}",
            f"Total Transfers,{report.total_transfers}",
            f"Successful Transfers,{report.successful_transfers}",
            f"Failed Transfers,{report.failed_transfers}",
            f"Total Bytes Transferred,{report.total_bytes_transferred}",
            f"Average Transfer Rate (KB/s),{report.average_transfer_rate/1024:.2f}",
            f"Peak Transfer Rate (KB/s),{report.peak_transfer_rate/1024:.2f}",
            f"Connection Pool Efficiency,{report.connection_pool_efficiency:.3f}",
            f"Average Connection Reuse,{report.average_connection_reuse:.3f}",
            f"Connection Failures,{report.connection_failures}",
            f"Error Rate,{report.error_rate:.3f}",
            f"Average Response Time,{report.average_response_time:.3f}",
        ]
        return "\n".join(lines)

    def reset_all_metrics(self) -> None:
        """Reset all monitoring metrics."""
        self._metrics.reset_metrics()
        self._profiler.clear_results()
        asyncio.run(self._circuit_breaker.reset())
        self._retry_manager.reset_stats()
        self._start_time = time.time()


# Global monitor instance
_global_monitor: Optional[FTPMonitor] = None


def get_monitor() -> FTPMonitor:
    """Get the global FTP monitor instance."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = FTPMonitor()
    return _global_monitor


def reset_monitor() -> None:
    """Reset the global FTP monitor."""
    global _global_monitor
    if _global_monitor is not None:
        _global_monitor.reset_all_metrics()
    _global_monitor = None
