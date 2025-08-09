#!/usr/bin/env python3
"""
Advanced Caching Demo

This example demonstrates the advanced caching capabilities of web-fetch,
including intelligent caching strategies, cache warming, and invalidation.

Features demonstrated:
- Multiple cache backends (memory, Redis)
- Cache warming strategies
- Tag-based cache invalidation
- Performance monitoring
- Cache statistics and analytics
"""

import asyncio
import time
from datetime import datetime
from typing import List, Dict, Any

from web_fetch.models.resource import ResourceRequest, ResourceKind, ResourceConfig
from web_fetch.models.extended_resources import RSSConfig
from web_fetch.cache import CacheBackend, CacheStrategy
from web_fetch.managers.cached_resource_manager import create_cached_resource_manager
from pydantic import AnyUrl


class CachingDemo:
    """Demonstrate advanced caching capabilities."""
    
    def __init__(self):
        """Initialize the caching demo."""
        # Create cached resource manager with memory backend
        self.memory_manager = create_cached_resource_manager(
            cache_backend=CacheBackend.MEMORY,
            cache_config={
                "max_size": 100,
                "max_memory": 50 * 1024 * 1024,  # 50MB
                "default_ttl": 1800,  # 30 minutes
                "strategy": CacheStrategy.ADAPTIVE
            }
        )
        
        # Create cached resource manager with Redis backend (if available)
        try:
            self.redis_manager = create_cached_resource_manager(
                cache_backend=CacheBackend.REDIS,
                cache_config={
                    "redis_url": "redis://localhost:6379",
                    "key_prefix": "webfetch:demo:",
                    "default_ttl": 3600  # 1 hour
                }
            )
            self.redis_available = True
        except (ImportError, Exception):
            self.redis_manager = None
            self.redis_available = False
            print("Redis not available, using memory cache only")
        
        # Demo data
        self.demo_requests = self._create_demo_requests()
    
    def _create_demo_requests(self) -> List[ResourceRequest]:
        """Create demo requests for testing."""
        return [
            ResourceRequest(
                uri=AnyUrl("https://rss.cnn.com/rss/edition.rss"),
                kind=ResourceKind.RSS,
                config=ResourceConfig(enable_cache=True, cache_ttl_seconds=1800)
            ),
            ResourceRequest(
                uri=AnyUrl("https://feeds.bbci.co.uk/news/rss.xml"),
                kind=ResourceKind.RSS,
                config=ResourceConfig(enable_cache=True, cache_ttl_seconds=1800)
            ),
            ResourceRequest(
                uri=AnyUrl("https://feeds.feedburner.com/TechCrunch"),
                kind=ResourceKind.RSS,
                config=ResourceConfig(enable_cache=True, cache_ttl_seconds=3600)
            ),
            ResourceRequest(
                uri=AnyUrl("https://www.reddit.com/r/programming/.rss"),
                kind=ResourceKind.RSS,
                config=ResourceConfig(enable_cache=True, cache_ttl_seconds=900)
            )
        ]
    
    async def demo_basic_caching(self) -> Dict[str, Any]:
        """Demonstrate basic caching functionality."""
        print("=== Basic Caching Demo ===")
        
        manager = self.memory_manager
        request = self.demo_requests[0]
        
        # First fetch (cache miss)
        print("First fetch (should be cache miss)...")
        start_time = time.time()
        result1 = await manager.fetch_resource(request)
        first_fetch_time = time.time() - start_time
        
        print(f"First fetch time: {first_fetch_time:.3f}s")
        print(f"Cache hit: {result1.metadata.get('cache_hit', False)}")
        
        # Second fetch (cache hit)
        print("\nSecond fetch (should be cache hit)...")
        start_time = time.time()
        result2 = await manager.fetch_resource(request)
        second_fetch_time = time.time() - start_time
        
        print(f"Second fetch time: {second_fetch_time:.3f}s")
        print(f"Cache hit: {result2.metadata.get('cache_hit', False)}")
        
        # Performance improvement
        speedup = first_fetch_time / second_fetch_time if second_fetch_time > 0 else float('inf')
        print(f"Speedup: {speedup:.1f}x")
        
        return {
            "first_fetch_time": first_fetch_time,
            "second_fetch_time": second_fetch_time,
            "speedup": speedup,
            "cache_stats": manager.get_cache_stats()
        }
    
    async def demo_cache_warming(self) -> Dict[str, Any]:
        """Demonstrate cache warming functionality."""
        print("\n=== Cache Warming Demo ===")
        
        manager = self.memory_manager
        
        # Add warming pattern
        manager.add_warming_pattern(
            "news_feeds",
            self.demo_requests[:2],  # First 2 requests
            interval=3600
        )
        
        print("Running cache warming...")
        warming_results = await manager.run_warming_patterns()
        
        print(f"Warming results: {warming_results}")
        
        # Test that warmed items are now cached
        print("\nTesting warmed cache entries...")
        cache_hits = 0
        for request in self.demo_requests[:2]:
            result = await manager.fetch_resource(request)
            if result.metadata.get('cache_hit', False):
                cache_hits += 1
        
        print(f"Cache hits after warming: {cache_hits}/2")
        
        return {
            "warming_results": warming_results,
            "cache_hits_after_warming": cache_hits,
            "cache_stats": manager.get_cache_stats()
        }
    
    async def demo_cache_invalidation(self) -> Dict[str, Any]:
        """Demonstrate cache invalidation functionality."""
        print("\n=== Cache Invalidation Demo ===")
        
        manager = self.memory_manager
        
        # First, populate cache
        print("Populating cache...")
        for request in self.demo_requests:
            await manager.fetch_resource(request)
        
        initial_stats = manager.get_cache_stats()
        print(f"Initial cache size: {initial_stats.get('total_requests', 0)}")
        
        # Invalidate by host
        print("\nInvalidating CNN entries...")
        cnn_invalidated = await manager.invalidate_by_host("rss.cnn.com")
        print(f"Invalidated {cnn_invalidated} CNN entries")
        
        # Invalidate by kind
        print("\nInvalidating all RSS entries...")
        rss_invalidated = await manager.invalidate_by_kind("rss")
        print(f"Invalidated {rss_invalidated} RSS entries")
        
        final_stats = manager.get_cache_stats()
        print(f"Final cache size: {final_stats.get('total_requests', 0)}")
        
        return {
            "initial_cache_size": initial_stats.get('total_requests', 0),
            "cnn_invalidated": cnn_invalidated,
            "rss_invalidated": rss_invalidated,
            "final_cache_size": final_stats.get('total_requests', 0)
        }
    
    async def demo_performance_comparison(self) -> Dict[str, Any]:
        """Compare performance between cached and uncached requests."""
        print("\n=== Performance Comparison Demo ===")
        
        manager = self.memory_manager
        request = self.demo_requests[0]
        
        # Test uncached performance
        print("Testing uncached performance...")
        uncached_times = []
        for i in range(3):
            # Clear cache first
            await manager.invalidate_by_kind("rss")
            
            start_time = time.time()
            await manager.fetch_resource(request)
            uncached_times.append(time.time() - start_time)
        
        avg_uncached_time = sum(uncached_times) / len(uncached_times)
        print(f"Average uncached time: {avg_uncached_time:.3f}s")
        
        # Test cached performance
        print("Testing cached performance...")
        cached_times = []
        for i in range(3):
            start_time = time.time()
            await manager.fetch_resource(request)
            cached_times.append(time.time() - start_time)
        
        avg_cached_time = sum(cached_times) / len(cached_times)
        print(f"Average cached time: {avg_cached_time:.3f}s")
        
        # Calculate improvement
        improvement = avg_uncached_time / avg_cached_time if avg_cached_time > 0 else float('inf')
        print(f"Performance improvement: {improvement:.1f}x")
        
        return {
            "avg_uncached_time": avg_uncached_time,
            "avg_cached_time": avg_cached_time,
            "performance_improvement": improvement,
            "cache_stats": manager.get_cache_stats()
        }
    
    async def demo_redis_caching(self) -> Dict[str, Any]:
        """Demonstrate Redis caching if available."""
        if not self.redis_available:
            print("\n=== Redis Caching Demo (Skipped - Redis not available) ===")
            return {"skipped": True, "reason": "Redis not available"}
        
        print("\n=== Redis Caching Demo ===")
        
        manager = self.redis_manager
        request = self.demo_requests[0]
        
        # Test Redis caching
        print("Testing Redis caching...")
        
        # First fetch
        start_time = time.time()
        result1 = await manager.fetch_resource(request)
        first_time = time.time() - start_time
        
        # Second fetch (should be from Redis cache)
        start_time = time.time()
        result2 = await manager.fetch_resource(request)
        second_time = time.time() - start_time
        
        print(f"First fetch time: {first_time:.3f}s")
        print(f"Second fetch time: {second_time:.3f}s")
        print(f"Cache hit: {result2.metadata.get('cache_hit', False)}")
        
        speedup = first_time / second_time if second_time > 0 else float('inf')
        print(f"Redis cache speedup: {speedup:.1f}x")
        
        return {
            "first_time": first_time,
            "second_time": second_time,
            "speedup": speedup,
            "cache_stats": manager.get_cache_stats()
        }
    
    async def run_all_demos(self) -> Dict[str, Any]:
        """Run all caching demos."""
        print("Advanced Caching Demo")
        print("=" * 50)
        
        results = {}
        
        try:
            # Run demos
            results["basic_caching"] = await self.demo_basic_caching()
            results["cache_warming"] = await self.demo_cache_warming()
            results["cache_invalidation"] = await self.demo_cache_invalidation()
            results["performance_comparison"] = await self.demo_performance_comparison()
            results["redis_caching"] = await self.demo_redis_caching()
            
            # Final statistics
            print("\n=== Final Cache Statistics ===")
            memory_stats = self.memory_manager.get_cache_stats()
            print(f"Memory cache stats: {memory_stats}")
            
            if self.redis_available:
                redis_stats = self.redis_manager.get_cache_stats()
                print(f"Redis cache stats: {redis_stats}")
            
            results["final_stats"] = {
                "memory": memory_stats,
                "redis": redis_stats if self.redis_available else None
            }
            
        except Exception as e:
            print(f"Demo failed: {e}")
            results["error"] = str(e)
        
        finally:
            # Cleanup
            await self.memory_manager.cleanup()
            if self.redis_available:
                await self.redis_manager.cleanup()
        
        return results


async def main():
    """Main demo function."""
    demo = CachingDemo()
    results = await demo.run_all_demos()
    
    print("\n" + "=" * 50)
    print("DEMO SUMMARY")
    print("=" * 50)
    
    if "error" in results:
        print(f"Demo failed: {results['error']}")
        return
    
    # Print summary
    if "basic_caching" in results:
        basic = results["basic_caching"]
        print(f"Basic caching speedup: {basic.get('speedup', 0):.1f}x")
    
    if "performance_comparison" in results:
        perf = results["performance_comparison"]
        print(f"Overall performance improvement: {perf.get('performance_improvement', 0):.1f}x")
    
    if "cache_warming" in results:
        warming = results["cache_warming"]
        print(f"Cache warming hits: {warming.get('cache_hits_after_warming', 0)}")
    
    if "redis_caching" in results and not results["redis_caching"].get("skipped"):
        redis = results["redis_caching"]
        print(f"Redis cache speedup: {redis.get('speedup', 0):.1f}x")
    
    print("\nAdvanced caching demo completed successfully!")


if __name__ == "__main__":
    print("Advanced Caching Demo")
    print("=" * 50)
    print("This demo shows advanced caching capabilities including:")
    print("- Intelligent cache strategies")
    print("- Cache warming and invalidation")
    print("- Performance monitoring")
    print("- Multiple backend support")
    print()
    
    asyncio.run(main())
