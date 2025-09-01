"""
Cache-aware resource manager with advanced caching strategies.

This module provides a resource manager that integrates with the advanced
caching system to provide intelligent caching, warming, and invalidation.
"""

import asyncio
import hashlib
import json
import time
from typing import Any, Dict, Optional, Set
from datetime import datetime

from ..models.resource import ResourceRequest, ResourceResult, ResourceConfig
from ..components.base import ResourceComponent
from ..components.manager import ResourceManager
from ..cache import AdvancedCacheManager, CacheBackend, create_cache_manager
from ..monitoring import get_metrics_collector, MetricsCollector


class CachedResourceManager(ResourceManager):
    """Resource manager with advanced caching capabilities."""

    def __init__(self,
                 cache_backend: CacheBackend = CacheBackend.MEMORY,
                 cache_config: Optional[Dict[str, Any]] = None,
                 enable_warming: bool = True,
                 enable_invalidation: bool = True):
        """
        Initialize cached resource manager.

        Args:
            cache_backend: Cache backend type
            cache_config: Cache configuration options
            enable_warming: Enable cache warming
            enable_invalidation: Enable cache invalidation
        """
        super().__init__()

        # Create advanced cache manager
        cache_config = cache_config or {}
        self.cache_manager = create_cache_manager(
            backend_type=cache_backend,
            enable_warming=enable_warming,
            enable_invalidation=enable_invalidation,
            **cache_config
        )

        # Cache warming configuration
        self.warming_enabled = enable_warming
        self.warming_patterns: Dict[str, Dict[str, Any]] = {}

        # Cache invalidation configuration
        self.invalidation_enabled = enable_invalidation
        self.invalidation_rules: Dict[str, Set[str]] = {}

        # Metrics collection
        self.metrics_collector = get_metrics_collector()

    async def fetch_resource(self, request: ResourceRequest) -> ResourceResult:
        """
        Fetch resource with advanced caching.

        Args:
            request: Resource request

        Returns:
            Resource result (from cache or fresh fetch)
        """
        start_time = time.time()

        component = self.get_component(request.kind)
        if not component:
            result = ResourceResult(
                url=str(request.uri),
                error=f"No component registered for kind: {request.kind}",
                status_code=500
            )

            # Record metrics for failed request
            duration = time.time() - start_time
            self.metrics_collector.record_request(
                resource_kind=request.kind.value,
                success=False,
                duration=duration,
                cache_hit=False,
                tags={"error": "no_component"}
            )

            return result

        # Check if caching is enabled (use use_cache from request or default config)
        enable_cache = request.use_cache
        if enable_cache is None:
            enable_cache = self.default_config.enable_cache

        if not enable_cache:
            return await self._fetch_fresh(component, request)

        # Generate cache key
        cache_key = self._generate_cache_key(component, request)
        if not cache_key:
            return await self._fetch_fresh(component, request)

        # Try to get from cache
        cached_result = await self.cache_manager.get(cache_key)
        if cached_result is not None and isinstance(cached_result, ResourceResult):
            # Return cached result with updated metadata
            cached_result.metadata = cached_result.metadata or {}
            cached_result.metadata["cache_hit"] = True
            cached_result.metadata["cached_at"] = cached_result.metadata.get("cached_at")

            # Record cache hit metrics
            duration = time.time() - start_time
            self.metrics_collector.record_request(
                resource_kind=request.kind.value,
                success=cached_result.is_success,
                duration=duration,
                cache_hit=True,
                tags={"source": "cache"}
            )

            return cached_result  # type: ignore[no-any-return]

        # Fetch fresh data
        result = await self._fetch_fresh(component, request)

        # Cache successful results
        if result.is_success:
            await self._cache_result(component, request, result, cache_key)

        # Record cache miss metrics
        duration = time.time() - start_time
        self.metrics_collector.record_request(
            resource_kind=request.kind.value,
            success=result.is_success,
            duration=duration,
            cache_hit=False,
            tags={"source": "fresh"}
        )

        return result

    async def _fetch_fresh(self, component: ResourceComponent,
                          request: ResourceRequest) -> ResourceResult:
        """Fetch fresh data from component."""
        result = await component.fetch(request)

        # Add cache metadata
        result.metadata = result.metadata or {}
        result.metadata["cache_hit"] = False
        result.metadata["fetched_at"] = datetime.utcnow().isoformat()

        return result

    async def _cache_result(self, component: ResourceComponent,
                           request: ResourceRequest, result: ResourceResult,
                           cache_key: str) -> None:
        """Cache the result with appropriate TTL and tags."""
        # Get cache TTL
        ttl = component.cache_ttl(request)
        if ttl is None:
            ttl = self.default_config.cache_ttl_seconds

        # Get cache tags
        tags = component.cache_tags(request)

        # Add caching metadata
        result.metadata = result.metadata or {}
        result.metadata["cached_at"] = datetime.utcnow().isoformat()
        result.metadata["cache_key"] = cache_key
        result.metadata["cache_tags"] = list(tags)

        # Cache the result
        await self.cache_manager.set(cache_key, result, ttl=ttl, tags=tags)

    def _generate_cache_key(self, component: ResourceComponent,
                           request: ResourceRequest) -> Optional[str]:
        """Generate cache key for request."""
        # Try component-specific cache key first
        cache_key = component.cache_key(request)
        if cache_key:
            return f"{component.kind.value}:{cache_key}"

        # Generate default cache key
        key_data = {
            "kind": request.kind.value,
            "uri": str(request.uri),
            "headers": dict(sorted(request.headers.items())) if request.headers else {},
            "options": request.options or {}
        }

        key_string = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]

        return f"{request.kind.value}:{key_hash}"

    async def warm_cache(self, request: ResourceRequest,
                        force: bool = False) -> bool:
        """
        Warm cache for a specific request.

        Args:
            request: Resource request to warm
            force: Force warming even if already cached

        Returns:
            True if warming was performed
        """
        if not self.warming_enabled:
            return False

        component = self.get_component(request.kind)
        if not component:
            return False

        cache_key = self._generate_cache_key(component, request)
        if not cache_key:
            return False

        # Check if already cached (unless forcing)
        if not force:
            cached_result = await self.cache_manager.get(cache_key)
            if cached_result is not None:
                return False

        # Create value factory
        async def value_factory() -> ResourceResult:
            return await self._fetch_fresh(component, request)

        # Get cache configuration
        ttl = component.cache_ttl(request) or self.default_config.cache_ttl_seconds
        tags = component.cache_tags(request)

        # Warm the cache
        await self.cache_manager.warm_cache(cache_key, value_factory, ttl=ttl, tags=tags)
        return True

    async def invalidate_by_tag(self, tag: str) -> int:
        """
        Invalidate cache entries by tag.

        Args:
            tag: Tag to invalidate

        Returns:
            Number of entries invalidated
        """
        if not self.invalidation_enabled:
            return 0

        return await self.cache_manager.invalidate_by_tag(tag)

    async def invalidate_by_host(self, host: str) -> int:
        """
        Invalidate all cache entries for a specific host.

        Args:
            host: Host to invalidate

        Returns:
            Number of entries invalidated
        """
        return await self.invalidate_by_tag(f"host:{host}")

    async def invalidate_by_kind(self, kind: str) -> int:
        """
        Invalidate all cache entries for a specific resource kind.

        Args:
            kind: Resource kind to invalidate

        Returns:
            Number of entries invalidated
        """
        return await self.invalidate_by_tag(f"kind:{kind}")

    def add_warming_pattern(self, pattern_name: str,
                           requests: list, interval: int = 3600) -> None:
        """
        Add cache warming pattern.

        Args:
            pattern_name: Name of the warming pattern
            requests: List of requests to warm
            interval: Warming interval in seconds
        """
        self.warming_patterns[pattern_name] = {
            "requests": requests,
            "interval": interval,
            "last_run": None
        }

    async def run_warming_patterns(self) -> Dict[str, int]:
        """
        Run all configured warming patterns.

        Returns:
            Dictionary with pattern names and number of requests warmed
        """
        results = {}

        for pattern_name, pattern_config in self.warming_patterns.items():
            warmed_count = 0

            for request in pattern_config["requests"]:
                if await self.warm_cache(request):
                    warmed_count += 1

            results[pattern_name] = warmed_count
            pattern_config["last_run"] = datetime.utcnow().isoformat()

        return results

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        base_stats = self.cache_manager.get_stats()

        return {
            **base_stats,
            "warming_patterns": len(self.warming_patterns),
            "warming_enabled": self.warming_enabled,
            "invalidation_enabled": self.invalidation_enabled
        }

    async def cleanup(self) -> None:
        """Cleanup cache resources."""
        await self.cache_manager.cleanup()


# Convenience function for creating cached resource manager
def create_cached_resource_manager(
    cache_backend: CacheBackend = CacheBackend.MEMORY,
    **kwargs: Any
) -> CachedResourceManager:
    """
    Create cached resource manager with default configuration.

    Args:
        cache_backend: Cache backend type
        **kwargs: Additional configuration options

    Returns:
        Configured cached resource manager
    """
    return CachedResourceManager(
        cache_backend=cache_backend,
        cache_config=kwargs.get("cache_config", {}),
        enable_warming=kwargs.get("enable_warming", True),
        enable_invalidation=kwargs.get("enable_invalidation", True)
    )
