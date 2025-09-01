"""
Advanced caching strategies for web-fetch extended resource types.

This module provides intelligent caching with cache invalidation, distributed
caching support, and cache warming strategies for better performance.
"""

import asyncio
import json
import time
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None  # type: ignore
    REDIS_AVAILABLE = False

try:
    import memcache  # type: ignore
    MEMCACHE_AVAILABLE = True
except ImportError:
    memcache = None
    MEMCACHE_AVAILABLE = False


class CacheStrategy(Enum):
    """Cache strategy types."""
    LRU = "lru"
    LFU = "lfu"
    TTL = "ttl"
    ADAPTIVE = "adaptive"


class CacheBackend(Enum):
    """Cache backend types."""
    MEMORY = "memory"
    REDIS = "redis"
    MEMCACHE = "memcache"
    HYBRID = "hybrid"


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    key: str
    value: Any
    created_at: float
    last_accessed: float
    access_count: int = 0
    ttl: Optional[float] = None
    tags: Set[str] = field(default_factory=set)
    size: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    @property
    def age(self) -> float:
        """Get entry age in seconds."""
        return time.time() - self.created_at

    def touch(self) -> None:
        """Update access metadata."""
        self.last_accessed = time.time()
        self.access_count += 1


class CacheBackendInterface(ABC):
    """Abstract interface for cache backends."""

    @abstractmethod
    async def get(self, key: str) -> Optional[CacheEntry]:
        """Get cache entry by key."""
        pass

    @abstractmethod
    async def set(self, key: str, entry: CacheEntry) -> bool:
        """Set cache entry."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete cache entry."""
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """Clear all cache entries."""
        pass

    @abstractmethod
    async def keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching pattern."""
        pass

    @abstractmethod
    async def size(self) -> int:
        """Get cache size."""
        pass


class MemoryCacheBackend(CacheBackendInterface):
    """In-memory cache backend with LRU/LFU eviction."""

    def __init__(self, max_size: int = 1000, max_memory: int = 100 * 1024 * 1024):
        """
        Initialize memory cache backend.

        Args:
            max_size: Maximum number of entries
            max_memory: Maximum memory usage in bytes
        """
        self.max_size = max_size
        self.max_memory = max_memory
        self.cache: Dict[str, CacheEntry] = {}
        self.access_order: List[str] = []
        self.current_memory = 0

    async def get(self, key: str) -> Optional[CacheEntry]:
        """Get cache entry by key."""
        entry = self.cache.get(key)
        if entry is None:
            return None

        if entry.is_expired:
            await self.delete(key)
            return None

        # Update access order for LRU
        if key in self.access_order:
            self.access_order.remove(key)
        self.access_order.append(key)

        entry.touch()
        return entry

    async def set(self, key: str, entry: CacheEntry) -> bool:
        """Set cache entry."""
        # Calculate entry size
        entry.size = len(json.dumps(entry.value, default=str).encode())

        # Remove existing entry if present
        if key in self.cache:
            await self.delete(key)

        # Check if we need to evict entries
        await self._evict_if_needed(entry.size)

        # Add new entry
        self.cache[key] = entry
        self.access_order.append(key)
        self.current_memory += entry.size

        return True

    async def delete(self, key: str) -> bool:
        """Delete cache entry."""
        entry = self.cache.pop(key, None)
        if entry is None:
            return False

        if key in self.access_order:
            self.access_order.remove(key)

        self.current_memory -= entry.size
        return True

    async def clear(self) -> bool:
        """Clear all cache entries."""
        self.cache.clear()
        self.access_order.clear()
        self.current_memory = 0
        return True

    async def keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching pattern."""
        if pattern == "*":
            return list(self.cache.keys())

        # Simple pattern matching (could be enhanced)
        import fnmatch
        return [key for key in self.cache.keys() if fnmatch.fnmatch(key, pattern)]

    async def size(self) -> int:
        """Get cache size."""
        return len(self.cache)

    async def _evict_if_needed(self, new_entry_size: int) -> None:
        """Evict entries if needed to make space."""
        # Check size limit
        while len(self.cache) >= self.max_size and self.access_order:
            oldest_key = self.access_order[0]
            await self.delete(oldest_key)

        # Check memory limit
        while (self.current_memory + new_entry_size > self.max_memory and
               self.access_order):
            oldest_key = self.access_order[0]
            await self.delete(oldest_key)


class RedisCacheBackend(CacheBackendInterface):
    """Redis cache backend."""

    def __init__(self, redis_url: str = "redis://localhost:6379",
                 key_prefix: str = "webfetch:"):
        """
        Initialize Redis cache backend.

        Args:
            redis_url: Redis connection URL
            key_prefix: Prefix for all cache keys
        """
        if not REDIS_AVAILABLE:
            raise ImportError("redis package is required for Redis backend")

        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.redis_client: Optional[Any] = None

    async def _get_client(self) -> Any:
        """Get Redis client, creating if needed."""
        if self.redis_client is None:
            self.redis_client = redis.from_url(self.redis_url)
        return self.redis_client

    def _make_key(self, key: str) -> str:
        """Make prefixed key."""
        return f"{self.key_prefix}{key}"

    async def get(self, key: str) -> Optional[CacheEntry]:
        """Get cache entry by key."""
        client = await self._get_client()
        prefixed_key = self._make_key(key)

        data = await client.get(prefixed_key)
        if data is None:
            return None

        try:
            entry_data = json.loads(data)
            entry = CacheEntry(
                key=entry_data["key"],
                value=entry_data["value"],
                created_at=entry_data["created_at"],
                last_accessed=entry_data["last_accessed"],
                access_count=entry_data["access_count"],
                ttl=entry_data.get("ttl"),
                tags=set(entry_data.get("tags", [])),
                size=entry_data.get("size", 0)
            )

            if entry.is_expired:
                await self.delete(key)
                return None

            entry.touch()
            # Update entry in Redis with new access info
            await self.set(key, entry)

            return entry

        except (json.JSONDecodeError, KeyError):
            await self.delete(key)
            return None

    async def set(self, key: str, entry: CacheEntry) -> bool:
        """Set cache entry."""
        client = await self._get_client()
        prefixed_key = self._make_key(key)

        entry_data = {
            "key": entry.key,
            "value": entry.value,
            "created_at": entry.created_at,
            "last_accessed": entry.last_accessed,
            "access_count": entry.access_count,
            "ttl": entry.ttl,
            "tags": list(entry.tags),
            "size": entry.size
        }

        data = json.dumps(entry_data, default=str)

        # Set with TTL if specified
        if entry.ttl:
            await client.setex(prefixed_key, int(entry.ttl), data)
        else:
            await client.set(prefixed_key, data)

        return True

    async def delete(self, key: str) -> bool:
        """Delete cache entry."""
        client = await self._get_client()
        prefixed_key = self._make_key(key)

        result = await client.delete(prefixed_key)
        return bool(result)

    async def clear(self) -> bool:
        """Clear all cache entries."""
        client = await self._get_client()
        keys = await client.keys(f"{self.key_prefix}*")

        if keys:
            await client.delete(*keys)

        return True

    async def keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching pattern."""
        client = await self._get_client()
        prefixed_pattern = f"{self.key_prefix}{pattern}"

        keys = await client.keys(prefixed_pattern)
        # Remove prefix from keys
        return [key.decode().replace(self.key_prefix, "") for key in keys]

    async def size(self) -> int:
        """Get cache size."""
        keys = await self.keys()
        return len(keys)


class AdvancedCacheManager:
    """Advanced cache manager with intelligent strategies."""

    def __init__(self,
                 backend: CacheBackendInterface,
                 strategy: CacheStrategy = CacheStrategy.ADAPTIVE,
                 default_ttl: int = 3600,
                 enable_warming: bool = True,
                 enable_invalidation: bool = True):
        """
        Initialize advanced cache manager.

        Args:
            backend: Cache backend implementation
            strategy: Caching strategy to use
            default_ttl: Default TTL in seconds
            enable_warming: Enable cache warming
            enable_invalidation: Enable cache invalidation
        """
        self.backend = backend
        self.strategy = strategy
        self.default_ttl = default_ttl
        self.enable_warming = enable_warming
        self.enable_invalidation = enable_invalidation

        # Cache statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "evictions": 0
        }

        # Tag-based invalidation
        self.tag_keys: Dict[str, Set[str]] = {}

        # Cache warming tasks
        self.warming_tasks: Set[asyncio.Task] = set()

    async def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache.

        Args:
            key: Cache key
            default: Default value if not found

        Returns:
            Cached value or default
        """
        entry = await self.backend.get(key)

        if entry is None:
            self.stats["misses"] += 1
            return default

        self.stats["hits"] += 1
        return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None,
                  tags: Optional[Set[str]] = None) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            tags: Tags for invalidation

        Returns:
            True if successful
        """
        if ttl is None:
            ttl = self.default_ttl

        entry = CacheEntry(
            key=key,
            value=value,
            created_at=time.time(),
            last_accessed=time.time(),
            ttl=ttl,
            tags=tags or set()
        )

        result = await self.backend.set(key, entry)

        if result:
            self.stats["sets"] += 1

            # Update tag mappings
            if tags:
                for tag in tags:
                    if tag not in self.tag_keys:
                        self.tag_keys[tag] = set()
                    self.tag_keys[tag].add(key)

        return result

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        result = await self.backend.delete(key)

        if result:
            self.stats["deletes"] += 1

            # Remove from tag mappings
            for tag_set in self.tag_keys.values():
                tag_set.discard(key)

        return result

    async def invalidate_by_tag(self, tag: str) -> int:
        """
        Invalidate all keys with a specific tag.

        Args:
            tag: Tag to invalidate

        Returns:
            Number of keys invalidated
        """
        if not self.enable_invalidation:
            return 0

        keys = self.tag_keys.get(tag, set()).copy()
        count = 0

        for key in keys:
            if await self.delete(key):
                count += 1

        # Clean up tag mapping
        if tag in self.tag_keys:
            del self.tag_keys[tag]

        return count

    async def warm_cache(self, key: str, value_factory: Any, ttl: Optional[int] = None,
                        tags: Optional[Set[str]] = None) -> None:
        """
        Warm cache with a value factory function.

        Args:
            key: Cache key
            value_factory: Async function to generate value
            ttl: Time to live
            tags: Tags for invalidation
        """
        if not self.enable_warming:
            return

        async def warming_task() -> None:
            try:
                value = await value_factory()
                await self.set(key, value, ttl, tags)
            except Exception as e:
                # Log warming failure but don't raise
                print(f"Cache warming failed for key {key}: {e}")

        task = asyncio.create_task(warming_task())
        self.warming_tasks.add(task)

        # Clean up completed tasks
        task.add_done_callback(self.warming_tasks.discard)

    async def get_or_set(self, key: str, value_factory: Any, ttl: Optional[int] = None,
                        tags: Optional[Set[str]] = None) -> Any:
        """
        Get value from cache or set it using factory function.

        Args:
            key: Cache key
            value_factory: Async function to generate value if not cached
            ttl: Time to live
            tags: Tags for invalidation

        Returns:
            Cached or generated value
        """
        # Try to get from cache first
        value = await self.get(key)
        if value is not None:
            return value

        # Generate value
        value = await value_factory()

        # Cache the value
        await self.set(key, value, ttl, tags)

        return value

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total_requests if total_requests > 0 else 0

        return {
            **self.stats,
            "hit_rate": hit_rate,
            "total_requests": total_requests,
            "active_warming_tasks": len(self.warming_tasks)
        }

    async def cleanup(self) -> None:
        """Cleanup resources."""
        # Cancel warming tasks
        for task in self.warming_tasks:
            task.cancel()

        # Wait for tasks to complete
        if self.warming_tasks:
            await asyncio.gather(*self.warming_tasks, return_exceptions=True)

        self.warming_tasks.clear()


def create_cache_manager(backend_type: CacheBackend = CacheBackend.MEMORY,
                        **kwargs: Any) -> AdvancedCacheManager:
    """
    Create cache manager with specified backend.

    Args:
        backend_type: Type of cache backend
        **kwargs: Backend-specific configuration

    Returns:
        Configured cache manager
    """
    backend: CacheBackendInterface
    if backend_type == CacheBackend.MEMORY:
        backend = MemoryCacheBackend(
            max_size=kwargs.get("max_size", 1000),
            max_memory=kwargs.get("max_memory", 100 * 1024 * 1024)
        )
    elif backend_type == CacheBackend.REDIS:
        backend = RedisCacheBackend(
            redis_url=kwargs.get("redis_url", "redis://localhost:6379"),
            key_prefix=kwargs.get("key_prefix", "webfetch:")
        )
    else:
        raise ValueError(f"Unsupported backend type: {backend_type}")

    return AdvancedCacheManager(
        backend=backend,
        strategy=kwargs.get("strategy", CacheStrategy.ADAPTIVE),
        default_ttl=kwargs.get("default_ttl", 3600),
        enable_warming=kwargs.get("enable_warming", True),
        enable_invalidation=kwargs.get("enable_invalidation", True)
    )
