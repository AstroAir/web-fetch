#!/usr/bin/env python3
"""
Monitoring and Metrics Demo

This example demonstrates the comprehensive monitoring and metrics collection
capabilities of web-fetch, including performance tracking, error monitoring,
and usage analytics.

Features demonstrated:
- Real-time metrics collection
- Multiple metrics backends (memory, Prometheus, console)
- Performance monitoring and analysis
- Error tracking and alerting
- Cache performance metrics
- Custom metrics and dashboards
"""

import asyncio
import time
from datetime import datetime
from typing import List, Dict, Any

from web_fetch.models.resource import ResourceRequest, ResourceKind, ResourceConfig
from web_fetch.monitoring import (
    MetricsCollector, MetricBackend, create_metrics_backend,
    configure_metrics, get_metrics_collector
)
from web_fetch.managers.cached_resource_manager import create_cached_resource_manager
from web_fetch.cache import CacheBackend
from pydantic import AnyUrl


class MonitoringDemo:
    """Demonstrate comprehensive monitoring capabilities."""
    
    def __init__(self):
        """Initialize the monitoring demo."""
        # Configure metrics backends
        self.memory_backend = create_metrics_backend(MetricBackend.MEMORY, max_points=1000)
        self.console_backend = create_metrics_backend(MetricBackend.CONSOLE)
        
        # Try to create Prometheus backend
        try:
            self.prometheus_backend = create_metrics_backend(MetricBackend.PROMETHEUS)
            self.prometheus_available = True
        except ImportError:
            self.prometheus_backend = None
            self.prometheus_available = False
            print("Prometheus not available, using memory and console backends only")
        
        # Configure global metrics collector
        backends = [self.memory_backend, self.console_backend]
        if self.prometheus_available:
            backends.append(self.prometheus_backend)
        
        configure_metrics(backends)
        self.metrics_collector = get_metrics_collector()
        
        # Create cached resource manager with monitoring
        self.resource_manager = create_cached_resource_manager(
            cache_backend=CacheBackend.MEMORY,
            cache_config={
                "max_size": 50,
                "default_ttl": 300
            }
        )
        
        # Demo requests
        self.demo_requests = self._create_demo_requests()
    
    def _create_demo_requests(self) -> List[ResourceRequest]:
        """Create demo requests for testing."""
        return [
            ResourceRequest(
                uri=AnyUrl("https://httpbin.org/json"),
                kind=ResourceKind.HTTP,
                use_cache=True
            ),
            ResourceRequest(
                uri=AnyUrl("https://httpbin.org/delay/1"),
                kind=ResourceKind.HTTP,
                use_cache=True
            ),
            ResourceRequest(
                uri=AnyUrl("https://httpbin.org/status/200"),
                kind=ResourceKind.HTTP,
                use_cache=True
            ),
            ResourceRequest(
                uri=AnyUrl("https://httpbin.org/status/404"),
                kind=ResourceKind.HTTP,
                use_cache=False  # Don't cache errors
            ),
            ResourceRequest(
                uri=AnyUrl("https://httpbin.org/status/500"),
                kind=ResourceKind.HTTP,
                use_cache=False
            )
        ]
    
    async def demo_basic_metrics(self) -> Dict[str, Any]:
        """Demonstrate basic metrics collection."""
        print("=== Basic Metrics Demo ===")
        
        # Record some custom metrics
        self.metrics_collector.record_counter("demo.requests.started", 1.0, {"demo": "basic"})
        self.metrics_collector.record_gauge("demo.active_connections", 5.0, {"demo": "basic"})
        self.metrics_collector.record_histogram("demo.response_size", 1024.0, {"demo": "basic"})
        
        # Use timing context
        with self.metrics_collector.time_operation("demo.operation", {"operation": "test"}):
            await asyncio.sleep(0.1)  # Simulate work
        
        print("Recorded basic metrics")
        
        return {
            "metrics_recorded": 4,
            "timing_operations": 1
        }
    
    async def demo_request_monitoring(self) -> Dict[str, Any]:
        """Demonstrate request monitoring and metrics."""
        print("\n=== Request Monitoring Demo ===")
        
        results = []
        
        # Make requests and monitor performance
        for i, request in enumerate(self.demo_requests):
            print(f"Making request {i+1}/{len(self.demo_requests)}: {request.uri}")
            
            start_time = time.time()
            result = await self.resource_manager.fetch_resource(request)
            duration = time.time() - start_time
            
            # Record additional custom metrics
            self.metrics_collector.record_timer(
                "demo.request.duration",
                duration,
                {
                    "method": "GET",
                    "status": str(result.status_code or 0),
                    "cached": str(result.metadata.get("cache_hit", False))
                }
            )
            
            results.append({
                "url": str(request.uri),
                "success": result.is_success,
                "duration": duration,
                "cache_hit": result.metadata.get("cache_hit", False),
                "status_code": result.status_code
            })
            
            # Small delay between requests
            await asyncio.sleep(0.1)
        
        print(f"Completed {len(results)} requests")
        
        return {
            "total_requests": len(results),
            "successful_requests": sum(1 for r in results if r["success"]),
            "cache_hits": sum(1 for r in results if r["cache_hit"]),
            "average_duration": sum(r["duration"] for r in results) / len(results),
            "results": results
        }
    
    async def demo_error_tracking(self) -> Dict[str, Any]:
        """Demonstrate error tracking and monitoring."""
        print("\n=== Error Tracking Demo ===")
        
        error_requests = [req for req in self.demo_requests if "status/4" in str(req.uri) or "status/5" in str(req.uri)]
        
        error_results = []
        
        for request in error_requests:
            print(f"Making error request: {request.uri}")
            
            result = await self.resource_manager.fetch_resource(request)
            
            # Record error metrics
            if not result.is_success or (result.status_code and result.status_code >= 400):
                error_type = "client_error" if result.status_code and 400 <= result.status_code < 500 else "server_error"
                
                self.metrics_collector.record_counter(
                    "demo.errors.total",
                    1.0,
                    {
                        "error_type": error_type,
                        "status_code": str(result.status_code or 0),
                        "url": str(request.uri)
                    }
                )
            
            error_results.append({
                "url": str(request.uri),
                "status_code": result.status_code,
                "error": result.error
            })
        
        print(f"Tracked {len(error_results)} error scenarios")
        
        return {
            "error_requests": len(error_results),
            "results": error_results
        }
    
    async def demo_cache_metrics(self) -> Dict[str, Any]:
        """Demonstrate cache performance monitoring."""
        print("\n=== Cache Metrics Demo ===")
        
        # Make requests to populate cache
        print("Populating cache...")
        cache_requests = [req for req in self.demo_requests if req.use_cache]
        
        for request in cache_requests:
            await self.resource_manager.fetch_resource(request)
        
        # Make same requests again to test cache hits
        print("Testing cache hits...")
        cache_hit_count = 0
        
        for request in cache_requests:
            result = await self.resource_manager.fetch_resource(request)
            if result.metadata.get("cache_hit", False):
                cache_hit_count += 1
        
        # Get cache statistics
        cache_stats = self.resource_manager.get_cache_stats()
        
        print(f"Cache hits: {cache_hit_count}/{len(cache_requests)}")
        print(f"Cache statistics: {cache_stats}")
        
        return {
            "cache_requests": len(cache_requests),
            "cache_hits": cache_hit_count,
            "cache_hit_rate": cache_hit_count / len(cache_requests) if cache_requests else 0,
            "cache_stats": cache_stats
        }
    
    async def demo_performance_analysis(self) -> Dict[str, Any]:
        """Demonstrate performance analysis and monitoring."""
        print("\n=== Performance Analysis Demo ===")
        
        # Run performance test
        test_request = self.demo_requests[0]  # Use first request
        iterations = 10
        
        print(f"Running performance test with {iterations} iterations...")
        
        durations = []
        for i in range(iterations):
            start_time = time.time()
            result = await self.resource_manager.fetch_resource(test_request)
            duration = time.time() - start_time
            durations.append(duration)
            
            # Record performance metrics
            self.metrics_collector.record_histogram(
                "demo.performance.request_duration",
                duration,
                {
                    "iteration": str(i + 1),
                    "cached": str(result.metadata.get("cache_hit", False))
                }
            )
        
        # Calculate statistics
        avg_duration = sum(durations) / len(durations)
        min_duration = min(durations)
        max_duration = max(durations)
        
        print(f"Performance results:")
        print(f"  Average: {avg_duration:.3f}s")
        print(f"  Min: {min_duration:.3f}s")
        print(f"  Max: {max_duration:.3f}s")
        
        return {
            "iterations": iterations,
            "average_duration": avg_duration,
            "min_duration": min_duration,
            "max_duration": max_duration,
            "durations": durations
        }
    
    def demo_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        print("\n=== Metrics Summary ===")
        
        # Get metrics from collector
        collector_stats = self.metrics_collector.get_summary()
        
        # Get metrics from memory backend
        memory_metrics = self.memory_backend.get_summary()
        
        print(f"Collector statistics:")
        for key, value in collector_stats.items():
            print(f"  {key}: {value}")
        
        print(f"\nMemory backend metrics:")
        for key, value in memory_metrics.items():
            print(f"  {key}: {value}")
        
        return {
            "collector_stats": collector_stats,
            "memory_metrics": memory_metrics,
            "prometheus_available": self.prometheus_available
        }
    
    async def run_all_demos(self) -> Dict[str, Any]:
        """Run all monitoring demos."""
        print("Monitoring and Metrics Demo")
        print("=" * 50)
        
        results = {}
        
        try:
            # Run demos
            results["basic_metrics"] = await self.demo_basic_metrics()
            results["request_monitoring"] = await self.demo_request_monitoring()
            results["error_tracking"] = await self.demo_error_tracking()
            results["cache_metrics"] = await self.demo_cache_metrics()
            results["performance_analysis"] = await self.demo_performance_analysis()
            results["metrics_summary"] = self.demo_metrics_summary()
            
        except Exception as e:
            print(f"Demo failed: {e}")
            results["error"] = str(e)
        
        finally:
            # Cleanup
            await self.resource_manager.cleanup()
        
        return results


async def main():
    """Main demo function."""
    demo = MonitoringDemo()
    results = await demo.run_all_demos()
    
    print("\n" + "=" * 50)
    print("MONITORING DEMO SUMMARY")
    print("=" * 50)
    
    if "error" in results:
        print(f"Demo failed: {results['error']}")
        return
    
    # Print summary
    if "request_monitoring" in results:
        req_mon = results["request_monitoring"]
        print(f"Total requests: {req_mon.get('total_requests', 0)}")
        print(f"Successful requests: {req_mon.get('successful_requests', 0)}")
        print(f"Cache hits: {req_mon.get('cache_hits', 0)}")
        print(f"Average duration: {req_mon.get('average_duration', 0):.3f}s")
    
    if "cache_metrics" in results:
        cache_metrics = results["cache_metrics"]
        print(f"Cache hit rate: {cache_metrics.get('cache_hit_rate', 0):.1%}")
    
    if "performance_analysis" in results:
        perf = results["performance_analysis"]
        print(f"Performance test iterations: {perf.get('iterations', 0)}")
        print(f"Average response time: {perf.get('average_duration', 0):.3f}s")
    
    if "metrics_summary" in results:
        summary = results["metrics_summary"]
        collector_stats = summary.get("collector_stats", {})
        print(f"Total metric requests: {collector_stats.get('total_requests', 0)}")
        print(f"Error rate: {collector_stats.get('error_rate', 0):.1%}")
    
    print("\nMonitoring demo completed successfully!")


if __name__ == "__main__":
    print("Monitoring and Metrics Demo")
    print("=" * 50)
    print("This demo shows comprehensive monitoring capabilities including:")
    print("- Real-time metrics collection")
    print("- Performance monitoring")
    print("- Error tracking")
    print("- Cache performance analysis")
    print("- Custom metrics and dashboards")
    print()
    
    asyncio.run(main())
