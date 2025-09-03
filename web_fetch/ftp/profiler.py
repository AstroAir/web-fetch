"""
Performance profiler for FTP operations.

This module provides profiling capabilities to identify performance bottlenecks
and optimization opportunities in FTP operations.
"""

from __future__ import annotations

import asyncio
import functools
import time
import tracemalloc
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union, cast
import psutil
import os

from .metrics import get_metrics_collector

F = TypeVar('F', bound=Callable[..., Any])


@dataclass
class ProfileResult:
    """Result of a profiling operation."""
    
    function_name: str
    execution_time: float
    memory_peak: Optional[int] = None  # Peak memory usage in bytes
    memory_current: Optional[int] = None  # Current memory usage in bytes
    cpu_percent: Optional[float] = None
    args_info: Optional[str] = None
    success: bool = True
    error: Optional[str] = None


class FTPProfiler:
    """
    Performance profiler for FTP operations.
    
    Provides decorators and context managers for profiling function execution,
    memory usage, and system resource consumption.
    """
    
    def __init__(self, enable_memory_profiling: bool = True):
        """Initialize the profiler."""
        self.enable_memory_profiling = enable_memory_profiling
        self._profile_results: List[ProfileResult] = []
        self._process = psutil.Process(os.getpid())
        
        if enable_memory_profiling:
            tracemalloc.start()
    
    def profile_function(self, include_args: bool = False) -> Callable[[F], F]:
        """
        Decorator to profile function execution.
        
        Args:
            include_args: Whether to include function arguments in profiling info
        
        Returns:
            Decorated function with profiling capabilities
        """
        def decorator(func: F) -> F:
            if asyncio.iscoroutinefunction(func):
                @functools.wraps(func)
                async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                    return await self._profile_async_function(
                        func, args, kwargs, include_args
                    )
                return async_wrapper  # type: ignore
            else:
                @functools.wraps(func)
                def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                    return self._profile_sync_function(
                        func, args, kwargs, include_args
                    )
                return sync_wrapper  # type: ignore
        return decorator
    
    async def _profile_async_function(self, func: Callable[..., Any], args: tuple[Any, ...],
                                    kwargs: dict[str, Any], include_args: bool) -> Any:
        """Profile an async function execution."""
        start_time = time.time()
        start_memory = None
        peak_memory = None
        cpu_start = self._process.cpu_percent()
        
        if self.enable_memory_profiling:
            start_memory = tracemalloc.get_traced_memory()[0]
        
        args_info = None
        if include_args:
            args_info = f"args={len(args)}, kwargs={list(kwargs.keys())}"
        
        try:
            result: Any = await func(*args, **kwargs)
            success = True
            error = None
        except Exception as e:
            result = None
            success = False
            error = str(e)
            raise
        finally:
            end_time = time.time()
            execution_time = end_time - start_time
            
            current_memory = None
            if self.enable_memory_profiling:
                current_memory, peak_memory = tracemalloc.get_traced_memory()
                if start_memory:
                    current_memory -= start_memory
            
            cpu_end = self._process.cpu_percent()
            cpu_percent = max(0, cpu_end - cpu_start)  # Approximate CPU usage
            
            profile_result = ProfileResult(
                function_name=func.__name__,
                execution_time=execution_time,
                memory_peak=peak_memory,
                memory_current=current_memory,
                cpu_percent=cpu_percent,
                args_info=args_info,
                success=success,
                error=error
            )
            
            self._profile_results.append(profile_result)
            
            # Also record in metrics collector
            metrics = get_metrics_collector()
            transfer_id = f"profile_{func.__name__}_{int(start_time * 1000)}"
            metrics.start_transfer(transfer_id, func.__name__, "profile")
            metrics.complete_transfer(transfer_id, success, error)
        
        return result
    
    def _profile_sync_function(self, func: Callable[..., Any], args: tuple[Any, ...],
                             kwargs: dict[str, Any], include_args: bool) -> Any:
        """Profile a sync function execution."""
        start_time = time.time()
        start_memory = None
        peak_memory = None
        cpu_start = self._process.cpu_percent()
        
        if self.enable_memory_profiling:
            start_memory = tracemalloc.get_traced_memory()[0]
        
        args_info = None
        if include_args:
            args_info = f"args={len(args)}, kwargs={list(kwargs.keys())}"
        
        try:
            result = func(*args, **kwargs)
            success = True
            error = None
        except Exception as e:
            result = None
            success = False
            error = str(e)
            raise
        finally:
            end_time = time.time()
            execution_time = end_time - start_time
            
            current_memory = None
            if self.enable_memory_profiling:
                current_memory, peak_memory = tracemalloc.get_traced_memory()
                if start_memory:
                    current_memory -= start_memory
            
            cpu_end = self._process.cpu_percent()
            cpu_percent = max(0, cpu_end - cpu_start)
            
            profile_result = ProfileResult(
                function_name=func.__name__,
                execution_time=execution_time,
                memory_peak=peak_memory,
                memory_current=current_memory,
                cpu_percent=cpu_percent,
                args_info=args_info,
                success=success,
                error=error
            )
            
            self._profile_results.append(profile_result)
        
        return result
    
    @asynccontextmanager
    async def profile_context(self, operation_name: str) -> Any:
        """
        Context manager for profiling a block of code.
        
        Args:
            operation_name: Name of the operation being profiled
        """
        start_time = time.time()
        start_memory = None
        
        if self.enable_memory_profiling:
            start_memory = tracemalloc.get_traced_memory()[0]
        
        cpu_start = self._process.cpu_percent()
        
        try:
            yield
            success = True
            error = None
        except Exception as e:
            success = False
            error = str(e)
            raise
        finally:
            end_time = time.time()
            execution_time = end_time - start_time
            
            current_memory = None
            peak_memory = None
            if self.enable_memory_profiling:
                current_memory, peak_memory = tracemalloc.get_traced_memory()
                if start_memory:
                    current_memory -= start_memory
            
            cpu_end = self._process.cpu_percent()
            cpu_percent = max(0, cpu_end - cpu_start)
            
            profile_result = ProfileResult(
                function_name=operation_name,
                execution_time=execution_time,
                memory_peak=peak_memory,
                memory_current=current_memory,
                cpu_percent=cpu_percent,
                success=success,
                error=error
            )
            
            self._profile_results.append(profile_result)
    
    def get_profile_summary(self) -> Dict[str, Any]:
        """Get a summary of all profiling results."""
        if not self._profile_results:
            return {}
        
        # Group results by function name
        function_stats = {}
        for result in self._profile_results:
            if result.function_name not in function_stats:
                function_stats[result.function_name] = {
                    "call_count": 0,
                    "total_time": 0.0,
                    "avg_time": 0.0,
                    "max_time": 0.0,
                    "min_time": float('inf'),
                    "success_count": 0,
                    "error_count": 0,
                    "avg_memory": 0.0,
                    "max_memory": 0,
                    "avg_cpu": 0.0
                }
            
            stats = function_stats[result.function_name]
            stats["call_count"] += 1
            stats["total_time"] += result.execution_time
            stats["max_time"] = max(stats["max_time"], result.execution_time)
            stats["min_time"] = min(stats["min_time"], result.execution_time)
            
            if result.success:
                stats["success_count"] += 1
            else:
                stats["error_count"] += 1
            
            if result.memory_current:
                stats["avg_memory"] = (stats["avg_memory"] * (stats["call_count"] - 1) + 
                                     result.memory_current) / stats["call_count"]
                stats["max_memory"] = max(stats["max_memory"], result.memory_current)
            
            if result.cpu_percent:
                stats["avg_cpu"] = (stats["avg_cpu"] * (stats["call_count"] - 1) + 
                                  result.cpu_percent) / stats["call_count"]
        
        # Calculate averages
        for stats in function_stats.values():
            if stats["call_count"] > 0:
                stats["avg_time"] = stats["total_time"] / stats["call_count"]
                if stats["min_time"] == float('inf'):
                    stats["min_time"] = 0.0
        
        return {
            "total_operations": len(self._profile_results),
            "function_statistics": function_stats,
            "overall_stats": {
                "total_execution_time": sum(r.execution_time for r in self._profile_results),
                "average_execution_time": sum(r.execution_time for r in self._profile_results) / len(self._profile_results),
                "success_rate": sum(1 for r in self._profile_results if r.success) / len(self._profile_results),
                "total_memory_used": sum(r.memory_current or 0 for r in self._profile_results),
                "average_cpu_usage": sum(r.cpu_percent or 0 for r in self._profile_results) / len(self._profile_results)
            }
        }
    
    def get_bottlenecks(self, top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Identify performance bottlenecks.
        
        Args:
            top_n: Number of top bottlenecks to return
        
        Returns:
            List of bottleneck information sorted by impact
        """
        if not self._profile_results:
            return []
        
        # Group by function and calculate impact scores
        function_impact = {}
        for result in self._profile_results:
            if result.function_name not in function_impact:
                function_impact[result.function_name] = {
                    "function_name": result.function_name,
                    "total_time": 0.0,
                    "call_count": 0,
                    "avg_time": 0.0,
                    "max_time": 0.0,
                    "total_memory": 0,
                    "error_rate": 0.0,
                    "impact_score": 0.0
                }
            
            impact = function_impact[result.function_name]
            total_time = impact.get("total_time", 0.0)
            call_count = impact.get("call_count", 0)
            max_time = impact.get("max_time", 0.0)
            total_memory = impact.get("total_memory", 0)

            # Ensure we have numeric types
            total_time = float(total_time) if isinstance(total_time, (int, float, str)) else 0.0
            call_count = int(call_count) if isinstance(call_count, (int, float, str)) else 0
            max_time = float(max_time) if isinstance(max_time, (int, float, str)) else 0.0
            total_memory = int(total_memory) if isinstance(total_memory, (int, float, str)) else 0

            impact["total_time"] = total_time + result.execution_time
            impact["call_count"] = call_count + 1
            impact["max_time"] = max(max_time, result.execution_time)
            impact["total_memory"] = total_memory + (result.memory_current or 0)
            
            if not result.success:
                error_rate = impact.get("error_rate", 0.0)
                impact["error_rate"] = cast(float, error_rate) + 1

        # Calculate final metrics and impact scores
        for impact in function_impact.values():
            total_time = cast(float, impact.get("total_time", 0.0))
            call_count = cast(int, impact.get("call_count", 1))  # Avoid division by zero
            error_rate = cast(float, impact.get("error_rate", 0.0))

            impact["avg_time"] = total_time / max(call_count, 1)
            impact["error_rate"] = error_rate / max(call_count, 1)
            
            # Impact score considers total time, frequency, and error rate
            total_time = cast(float, impact.get("total_time", 0.0))
            call_count = cast(int, impact.get("call_count", 0))
            avg_time = cast(float, impact.get("avg_time", 0.0))
            error_rate = cast(float, impact.get("error_rate", 0.0))
            total_memory = cast(int, impact.get("total_memory", 0))

            impact["impact_score"] = (
                total_time * 0.4 +  # Total time impact
                call_count * avg_time * 0.3 +  # Frequency * avg time
                error_rate * 100 * 0.2 +  # Error impact
                (total_memory / 1024 / 1024) * 0.1  # Memory impact (MB)
            )
        
        # Sort by impact score and return top N
        bottlenecks = sorted(function_impact.values(),
                           key=lambda x: cast(float, x.get("impact_score", 0.0)), reverse=True)
        return bottlenecks[:top_n]
    
    def clear_results(self) -> None:
        """Clear all profiling results."""
        self._profile_results.clear()


# Global profiler instance
_global_profiler: Optional[FTPProfiler] = None


def get_profiler() -> FTPProfiler:
    """Get the global profiler instance."""
    global _global_profiler
    if _global_profiler is None:
        _global_profiler = FTPProfiler()
    return _global_profiler


def profile(include_args: bool = False) -> Callable[[F], F]:
    """
    Convenience decorator for profiling functions.
    
    Args:
        include_args: Whether to include function arguments in profiling info
    
    Returns:
        Decorated function with profiling capabilities
    """
    return get_profiler().profile_function(include_args=include_args)
