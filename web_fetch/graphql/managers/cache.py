"""
Cache management for GraphQL operations.

This module provides response caching, cache statistics, and eviction policies
for GraphQL clients, enabling efficient response caching and management.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Any, Dict, Optional, Tuple

from pydantic import Field

from ..models import GraphQLResult
from .base import BaseGraphQLManager, GraphQLManagerConfig

logger = logging.getLogger(__name__)


class CacheManagerConfig(GraphQLManagerConfig):
    """Configuration for GraphQL cache manager."""
    
    # Cache settings
    max_cache_size_bytes: int = Field(default=50 * 1024 * 1024, ge=0, description="Maximum cache size in bytes")
    default_ttl: float = Field(default=300.0, ge=0, description="Default cache TTL in seconds")
    enable_compression: bool = Field(default=False, description="Enable cache compression")
    
    # Eviction settings
    eviction_strategy: str = Field(default="lru", description="Cache eviction strategy (lru, lfu, ttl)")
    max_entries: int = Field(default=1000, ge=0, description="Maximum number of cache entries")
    cleanup_interval: float = Field(default=60.0, ge=1.0, description="Cache cleanup interval in seconds")
    
    # Statistics settings
    enable_metrics: bool = Field(default=True, description="Enable cache metrics collection")
    
    class Config:
        """Pydantic configuration."""
        extra = "forbid"


class GraphQLCacheManager(BaseGraphQLManager):
    """
    Cache manager for GraphQL operations.
    
    Manages response caching, cache statistics, and eviction policies,
    providing efficient response caching and cache management.
    
    Features:
    - Response caching with TTL
    - Multiple eviction strategies (LRU, LFU, TTL)
    - Cache statistics and metrics
    - Configurable cache size limits
    - Automatic cache cleanup
    - Cache key generation
    
    Examples:
        Basic usage:
        ```python
        config = CacheManagerConfig(max_cache_size_bytes=100*1024*1024)
        async with GraphQLCacheManager(config) as cache_manager:
            # Cache a result
            await cache_manager.set("key", result, ttl=300)
            
            # Get cached result
            cached_result = await cache_manager.get("key")
        ```
        
        With custom eviction:
        ```python
        config = CacheManagerConfig(
            eviction_strategy="lfu",
            max_entries=500
        )
        cache_manager = GraphQLCacheManager(config)
        ```
    """
    
    def __init__(self, config: Optional[CacheManagerConfig] = None):
        """
        Initialize cache manager.
        
        Args:
            config: Cache manager configuration
        """
        super().__init__(config or CacheManagerConfig())
        
        # Cache storage: key -> (timestamp, result, access_count, size_bytes, last_access)
        self._cache: Dict[str, Tuple[float, GraphQLResult, int, int, float]] = {}
        
        # Cache statistics
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "total_size_bytes": 0,
            "sets": 0,
            "deletes": 0,
        }
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_lock = asyncio.Lock()
    
    @property
    def cache_config(self) -> CacheManagerConfig:
        """Get typed cache configuration."""
        return self.config  # type: ignore
    
    async def _initialize_impl(self) -> None:
        """Initialize cache manager."""
        # Start cleanup task
        if self.cache_config.cleanup_interval > 0:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            self._logger.debug("Cache cleanup task started")
    
    async def _close_impl(self) -> None:
        """Close cache manager and cleanup resources."""
        # Stop cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Clear cache
        self._cache.clear()
        
        self._logger.info(
            f"Cache manager closed. Final metrics: hits={self._stats['hits']}, "
            f"misses={self._stats['misses']}, evictions={self._stats['evictions']}, "
            f"total_size={self._stats['total_size_bytes']}"
        )
    
    async def get(self, key: str) -> Optional[GraphQLResult]:
        """
        Get cached result by key.
        
        Args:
            key: Cache key
            
        Returns:
            Cached result or None if not found/expired
        """
        self._ensure_initialized()
        
        if key not in self._cache:
            self._stats["misses"] += 1
            return None
        
        timestamp, result, access_count, size_bytes, _ = self._cache[key]
        
        # Check TTL
        if time.time() - timestamp > self.cache_config.default_ttl:
            # Expired, remove from cache
            del self._cache[key]
            self._stats["total_size_bytes"] -= size_bytes
            self._stats["misses"] += 1
            return None
        
        # Update access statistics
        self._cache[key] = (
            timestamp, 
            result, 
            access_count + 1, 
            size_bytes, 
            time.time()
        )
        
        self._stats["hits"] += 1
        return result
    
    async def set(
        self, 
        key: str, 
        result: GraphQLResult, 
        ttl: Optional[float] = None
    ) -> None:
        """
        Cache a result with optional TTL.
        
        Args:
            key: Cache key
            result: Result to cache
            ttl: Time to live in seconds (uses default if None)
        """
        self._ensure_initialized()
        
        # Calculate result size
        size_bytes = self._estimate_result_size(result)
        
        # Check if we need to evict entries
        await self._ensure_cache_space(size_bytes)
        
        # Store in cache
        cache_ttl = ttl or self.cache_config.default_ttl
        current_time = time.time()
        
        # Remove old entry if exists
        if key in self._cache:
            old_size = self._cache[key][3]
            self._stats["total_size_bytes"] -= old_size
        
        self._cache[key] = (
            current_time,  # timestamp
            result,        # result
            0,            # access_count
            size_bytes,   # size_bytes
            current_time  # last_access
        )
        
        self._stats["total_size_bytes"] += size_bytes
        self._stats["sets"] += 1
    
    async def delete(self, key: str) -> bool:
        """
        Delete cached result by key.
        
        Args:
            key: Cache key
            
        Returns:
            True if key was found and deleted
        """
        self._ensure_initialized()
        
        if key in self._cache:
            size_bytes = self._cache[key][3]
            del self._cache[key]
            self._stats["total_size_bytes"] -= size_bytes
            self._stats["deletes"] += 1
            return True
        
        return False
    
    async def clear(self) -> None:
        """Clear all cached entries."""
        self._ensure_initialized()
        
        entry_count = len(self._cache)
        self._cache.clear()
        self._stats["total_size_bytes"] = 0
        self._stats["deletes"] += entry_count
        
        self._logger.debug(f"Cache cleared, removed {entry_count} entries")
    
    def generate_cache_key(
        self, 
        query: str, 
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None
    ) -> str:
        """
        Generate cache key for GraphQL operation.
        
        Args:
            query: GraphQL query string
            variables: Query variables
            operation_name: Operation name
            
        Returns:
            Generated cache key
        """
        # Create deterministic key from query components
        key_components = [query.strip()]
        
        if variables:
            # Sort variables for consistent key generation
            import json
            sorted_vars = json.dumps(variables, sort_keys=True, separators=(',', ':'))
            key_components.append(sorted_vars)
        
        if operation_name:
            key_components.append(operation_name)
        
        key_string = "|".join(key_components)
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    async def _ensure_cache_space(self, required_bytes: int) -> None:
        """
        Ensure cache has space for new entry.
        
        Args:
            required_bytes: Bytes required for new entry
        """
        # Check size limit
        if (self._stats["total_size_bytes"] + required_bytes > 
            self.cache_config.max_cache_size_bytes):
            await self._evict_entries(required_bytes)
        
        # Check entry count limit
        if len(self._cache) >= self.cache_config.max_entries:
            await self._evict_entries(0)  # Evict at least one entry
    
    async def _evict_entries(self, required_bytes: int) -> None:
        """
        Evict cache entries based on eviction strategy.
        
        Args:
            required_bytes: Minimum bytes to free
        """
        if not self._cache:
            return
        
        strategy = self.cache_config.eviction_strategy.lower()
        evicted_bytes = 0
        evicted_count = 0
        
        if strategy == "lru":
            # Evict least recently used
            sorted_entries = sorted(
                self._cache.items(),
                key=lambda x: x[1][4]  # Sort by last_access
            )
        elif strategy == "lfu":
            # Evict least frequently used
            sorted_entries = sorted(
                self._cache.items(),
                key=lambda x: x[1][2]  # Sort by access_count
            )
        elif strategy == "ttl":
            # Evict oldest entries
            sorted_entries = sorted(
                self._cache.items(),
                key=lambda x: x[1][0]  # Sort by timestamp
            )
        else:
            # Default to LRU
            sorted_entries = sorted(
                self._cache.items(),
                key=lambda x: x[1][4]
            )
        
        # Evict entries until we have enough space
        for key, (_, _, _, size_bytes, _) in sorted_entries:
            del self._cache[key]
            evicted_bytes += size_bytes
            evicted_count += 1
            
            if (evicted_bytes >= required_bytes and 
                len(self._cache) < self.cache_config.max_entries):
                break
        
        self._stats["total_size_bytes"] -= evicted_bytes
        self._stats["evictions"] += evicted_count
        
        self._logger.debug(
            f"Evicted {evicted_count} entries, freed {evicted_bytes} bytes"
        )
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop for expired entries."""
        while not self._closed:
            try:
                await asyncio.sleep(self.cache_config.cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in cache cleanup: {e}")
    
    async def _cleanup_expired(self) -> None:
        """Remove expired cache entries."""
        async with self._cleanup_lock:
            current_time = time.time()
            expired_keys = []
            
            for key, (timestamp, _, _, _, _) in self._cache.items():
                if current_time - timestamp > self.cache_config.default_ttl:
                    expired_keys.append(key)
            
            # Remove expired entries
            freed_bytes = 0
            for key in expired_keys:
                if key in self._cache:
                    freed_bytes += self._cache[key][3]
                    del self._cache[key]
            
            if expired_keys:
                self._stats["total_size_bytes"] -= freed_bytes
                self._stats["evictions"] += len(expired_keys)
                self._logger.debug(
                    f"Cleaned up {len(expired_keys)} expired entries, "
                    f"freed {freed_bytes} bytes"
                )
    
    def _estimate_result_size(self, result: GraphQLResult) -> int:
        """
        Estimate the memory size of a GraphQL result.
        
        Args:
            result: GraphQL result to estimate
            
        Returns:
            Estimated size in bytes
        """
        import sys
        
        try:
            # Rough estimation based on string representation
            result_str = str(result.data) if result.data else ""
            result_str += str(result.errors) if result.errors else ""
            result_str += str(result.extensions) if result.extensions else ""
            
            return sys.getsizeof(result_str) + sys.getsizeof(result)
        except Exception:
            # Fallback estimation
            return 1024  # 1KB default
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get cache metrics.
        
        Returns:
            Dictionary containing cache metrics
        """
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / max(total_requests, 1)
        
        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": hit_rate,
            "evictions": self._stats["evictions"],
            "sets": self._stats["sets"],
            "deletes": self._stats["deletes"],
            "total_size_bytes": self._stats["total_size_bytes"],
            "max_size_bytes": self.cache_config.max_cache_size_bytes,
            "entry_count": len(self._cache),
            "max_entries": self.cache_config.max_entries,
            "size_utilization": self._stats["total_size_bytes"] / max(self.cache_config.max_cache_size_bytes, 1),
            "entry_utilization": len(self._cache) / max(self.cache_config.max_entries, 1),
        }
