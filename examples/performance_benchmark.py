"""
Performance benchmarking script for Web-Fetch MCP Server.

This script provides comprehensive performance testing and benchmarking
for various components of the web-fetch library and MCP server.
"""

import asyncio
import time
import statistics
from typing import List, Dict, Any
import json
from dataclasses import dataclass

from mcp_server.server import create_mcp_server


@dataclass
class BenchmarkResult:
    """Result of a benchmark test."""
    test_name: str
    total_time: float
    requests_per_second: float
    success_rate: float
    avg_response_time: float
    median_response_time: float
    min_response_time: float
    max_response_time: float
    memory_usage: Dict[str, Any]
    errors: List[str]


class PerformanceBenchmark:
    """Performance benchmarking suite."""

    def __init__(self):
        """Initialize the benchmark suite."""
        self.mcp = create_mcp_server()
        self.results: List[BenchmarkResult] = []

    async def get_tools(self):
        """Get MCP tools."""
        return await self.mcp.get_tools()

    async def call_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool."""
        tools = await self.get_tools()
        if tool_name not in tools:
            raise ValueError(f"Tool '{tool_name}' not found")
        
        tool = tools[tool_name]
        return await tool(**params)

    async def benchmark_web_fetch(self, num_requests: int = 50) -> BenchmarkResult:
        """Benchmark basic web fetching."""
        print(f"Benchmarking web fetch with {num_requests} requests...")
        
        start_time = time.time()
        response_times = []
        errors = []
        successful = 0

        # Test URLs
        test_urls = [
            "https://httpbin.org/json",
            "https://httpbin.org/html",
            "https://httpbin.org/xml",
            "https://httpbin.org/user-agent",
            "https://httpbin.org/headers"
        ]

        for i in range(num_requests):
            url = test_urls[i % len(test_urls)]
            
            request_start = time.time()
            try:
                result = await self.call_tool("web_fetch", {
                    "url": url,
                    "timeout": 30.0
                })
                
                if result.get("success", False):
                    successful += 1
                else:
                    errors.append(result.get("error", "Unknown error"))
                    
            except Exception as e:
                errors.append(str(e))
            
            response_time = time.time() - request_start
            response_times.append(response_time)

        total_time = time.time() - start_time
        
        # Get memory usage
        memory_result = await self.call_tool("performance_monitor", {
            "metric_type": "memory"
        })
        memory_usage = memory_result.get("memory_metrics", {})

        return BenchmarkResult(
            test_name="web_fetch",
            total_time=total_time,
            requests_per_second=num_requests / total_time,
            success_rate=(successful / num_requests) * 100,
            avg_response_time=statistics.mean(response_times),
            median_response_time=statistics.median(response_times),
            min_response_time=min(response_times),
            max_response_time=max(response_times),
            memory_usage=memory_usage,
            errors=errors[:10]  # Keep only first 10 errors
        )

    async def benchmark_batch_fetch(self, num_urls: int = 20) -> BenchmarkResult:
        """Benchmark batch fetching."""
        print(f"Benchmarking batch fetch with {num_urls} URLs...")
        
        # Generate test URLs
        urls = [f"https://httpbin.org/delay/{i%3}" for i in range(num_urls)]
        
        start_time = time.time()
        errors = []
        
        try:
            result = await self.call_tool("web_fetch_batch", {
                "urls": urls,
                "max_concurrent": 10,
                "timeout": 30.0
            })
            
            if result.get("success", False):
                batch_results = result.get("results", [])
                successful = sum(1 for r in batch_results if r.get("success", False))
                response_times = [r.get("response_time", 0) for r in batch_results if r.get("response_time")]
            else:
                successful = 0
                response_times = [0]
                errors.append(result.get("error", "Batch fetch failed"))
                
        except Exception as e:
            successful = 0
            response_times = [0]
            errors.append(str(e))

        total_time = time.time() - start_time
        
        # Get memory usage
        memory_result = await self.call_tool("performance_monitor", {
            "metric_type": "memory"
        })
        memory_usage = memory_result.get("memory_metrics", {})

        return BenchmarkResult(
            test_name="batch_fetch",
            total_time=total_time,
            requests_per_second=num_urls / total_time,
            success_rate=(successful / num_urls) * 100,
            avg_response_time=statistics.mean(response_times) if response_times else 0,
            median_response_time=statistics.median(response_times) if response_times else 0,
            min_response_time=min(response_times) if response_times else 0,
            max_response_time=max(response_times) if response_times else 0,
            memory_usage=memory_usage,
            errors=errors
        )

    async def benchmark_caching(self, num_requests: int = 100) -> BenchmarkResult:
        """Benchmark caching performance."""
        print(f"Benchmarking caching with {num_requests} requests...")
        
        # Enable caching first
        await self.call_tool("performance_optimize", {
            "action": "enable_cache",
            "config": {
                "max_size": 1000,
                "ttl": 3600
            }
        })
        
        # Use same URL to test cache hits
        test_url = "https://httpbin.org/json"
        
        start_time = time.time()
        response_times = []
        errors = []
        successful = 0

        for i in range(num_requests):
            request_start = time.time()
            try:
                result = await self.call_tool("web_fetch", {
                    "url": test_url,
                    "timeout": 30.0
                })
                
                if result.get("success", False):
                    successful += 1
                else:
                    errors.append(result.get("error", "Unknown error"))
                    
            except Exception as e:
                errors.append(str(e))
            
            response_time = time.time() - request_start
            response_times.append(response_time)

        total_time = time.time() - start_time
        
        # Get cache metrics
        cache_result = await self.call_tool("performance_monitor", {
            "metric_type": "cache"
        })
        cache_metrics = cache_result.get("cache_metrics", {})
        
        # Get memory usage
        memory_result = await self.call_tool("performance_monitor", {
            "metric_type": "memory"
        })
        memory_usage = memory_result.get("memory_metrics", {})
        memory_usage.update(cache_metrics)

        return BenchmarkResult(
            test_name="caching",
            total_time=total_time,
            requests_per_second=num_requests / total_time,
            success_rate=(successful / num_requests) * 100,
            avg_response_time=statistics.mean(response_times),
            median_response_time=statistics.median(response_times),
            min_response_time=min(response_times),
            max_response_time=max(response_times),
            memory_usage=memory_usage,
            errors=errors[:10]
        )

    async def benchmark_concurrent_tools(self, num_concurrent: int = 20) -> BenchmarkResult:
        """Benchmark concurrent tool execution."""
        print(f"Benchmarking concurrent execution with {num_concurrent} tools...")
        
        start_time = time.time()
        errors = []
        successful = 0

        # Create concurrent tasks
        tasks = []
        for i in range(num_concurrent):
            task = self.call_tool("metrics_summary", {})
            tasks.append(task)

        # Execute all tasks concurrently
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            response_times = []
            for result in results:
                if isinstance(result, Exception):
                    errors.append(str(result))
                elif isinstance(result, dict) and result.get("success", False):
                    successful += 1
                    # Estimate response time (not precise for concurrent)
                    response_times.append(0.1)  # Placeholder
                else:
                    errors.append("Tool call failed")
                    
        except Exception as e:
            errors.append(str(e))
            response_times = [0]

        total_time = time.time() - start_time
        
        # Get memory usage
        memory_result = await self.call_tool("performance_monitor", {
            "metric_type": "memory"
        })
        memory_usage = memory_result.get("memory_metrics", {})

        return BenchmarkResult(
            test_name="concurrent_tools",
            total_time=total_time,
            requests_per_second=num_concurrent / total_time,
            success_rate=(successful / num_concurrent) * 100,
            avg_response_time=statistics.mean(response_times) if response_times else 0,
            median_response_time=statistics.median(response_times) if response_times else 0,
            min_response_time=min(response_times) if response_times else 0,
            max_response_time=max(response_times) if response_times else 0,
            memory_usage=memory_usage,
            errors=errors[:10]
        )

    async def run_all_benchmarks(self) -> List[BenchmarkResult]:
        """Run all benchmark tests."""
        print("Starting comprehensive performance benchmarks...")
        
        # Optimize performance first
        await self.call_tool("performance_optimize", {
            "action": "configure_pool",
            "config": {
                "max_connections": 100,
                "max_per_host": 30
            }
        })
        
        benchmarks = [
            self.benchmark_web_fetch(50),
            self.benchmark_batch_fetch(20),
            self.benchmark_caching(100),
            self.benchmark_concurrent_tools(20)
        ]
        
        results = []
        for benchmark in benchmarks:
            try:
                result = await benchmark
                results.append(result)
                self.results.append(result)
            except Exception as e:
                print(f"Benchmark failed: {e}")
        
        return results

    def print_results(self, results: List[BenchmarkResult]):
        """Print benchmark results in a formatted way."""
        print("\n" + "="*80)
        print("PERFORMANCE BENCHMARK RESULTS")
        print("="*80)
        
        for result in results:
            print(f"\n{result.test_name.upper()} BENCHMARK:")
            print(f"  Total Time: {result.total_time:.2f}s")
            print(f"  Requests/sec: {result.requests_per_second:.2f}")
            print(f"  Success Rate: {result.success_rate:.1f}%")
            print(f"  Avg Response Time: {result.avg_response_time:.3f}s")
            print(f"  Median Response Time: {result.median_response_time:.3f}s")
            print(f"  Min Response Time: {result.min_response_time:.3f}s")
            print(f"  Max Response Time: {result.max_response_time:.3f}s")
            
            if result.memory_usage:
                print(f"  Memory Objects: {result.memory_usage.get('total_objects', 'N/A')}")
                if 'hit_rate' in result.memory_usage:
                    print(f"  Cache Hit Rate: {result.memory_usage['hit_rate']:.1f}%")
            
            if result.errors:
                print(f"  Errors: {len(result.errors)} (showing first few)")
                for error in result.errors[:3]:
                    print(f"    - {error}")
        
        print("\n" + "="*80)

    def save_results(self, filename: str = "benchmark_results.json"):
        """Save benchmark results to JSON file."""
        data = []
        for result in self.results:
            data.append({
                "test_name": result.test_name,
                "total_time": result.total_time,
                "requests_per_second": result.requests_per_second,
                "success_rate": result.success_rate,
                "avg_response_time": result.avg_response_time,
                "median_response_time": result.median_response_time,
                "min_response_time": result.min_response_time,
                "max_response_time": result.max_response_time,
                "memory_usage": result.memory_usage,
                "errors": result.errors,
                "timestamp": time.time()
            })
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Results saved to {filename}")


async def main():
    """Main function to run benchmarks."""
    benchmark = PerformanceBenchmark()
    
    try:
        results = await benchmark.run_all_benchmarks()
        benchmark.print_results(results)
        benchmark.save_results()
        
    except Exception as e:
        print(f"Benchmark suite failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
