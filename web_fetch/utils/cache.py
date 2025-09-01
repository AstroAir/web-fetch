"""
Enhanced caching utilities with multiple backend support.

This module provides comprehensive caching functionality including:
- Memory-based LRU cache
- File-based persistent cache
- Redis distributed cache
- Automatic cleanup and expiration
"""

import asyncio
import gzip
import hashlib
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from ..models import CacheConfig

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with metadata and compression support."""

    url: str
    response_data: Any
    headers: Dict[str, str]
    status_code: int
    timestamp: datetime
    ttl: timedelta
    compressed: bool = False

    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return datetime.now() > self.timestamp + self.ttl

    def get_data(self) -> Any:
        """Get response data, decompressing if needed."""
        if self.compressed and isinstance(self.response_data, bytes):
            try:
                decompressed = gzip.decompress(self.response_data)
                # Try to decode as UTF-8 string if it was originally a string
                try:
                    return decompressed.decode('utf-8')
                except UnicodeDecodeError:
                    return decompressed
            except Exception:
                return self.response_data
        return self.response_data


class SimpleCache:
    """
    Simple in-memory cache with LRU eviction and TTL support.

    This cache provides basic caching functionality with configurable
    size limits, TTL, and optional compression. Suitable for development
    and single-process applications.
    """

    def __init__(self, config: CacheConfig):
        """
        Initialize cache with configuration.

        Args:
            config: CacheConfig object specifying cache behavior including
                   max_size, TTL, compression settings, and header caching.

        Attributes:
            config: The cache configuration
            _cache: Internal storage for cache entries
            _access_order: List tracking access order for LRU eviction
        """
        self.config = config
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order: List[str] = []

    def _cleanup_expired(self) -> None:
        """
        Remove expired entries from cache.

        Scans all cache entries and removes those that have exceeded
        their TTL. Called automatically during get operations.
        """
        expired_keys = [key for key, entry in self._cache.items() if entry.is_expired]
        for key in expired_keys:
            self._remove_entry(key)

    def _remove_entry(self, key: str) -> None:
        """
        Remove entry from cache and access order.

        Args:
            key: Cache key to remove
        """
        if key in self._cache:
            del self._cache[key]
        if key in self._access_order:
            self._access_order.remove(key)

    def _evict_lru(self) -> None:
        """
        Evict least recently used entries if cache is full.

        Removes the oldest accessed entries until cache size is
        below the configured maximum. Uses LRU eviction policy.
        """
        while len(self._cache) >= self.config.max_size and self._access_order:
            lru_key = self._access_order.pop(0)
            self._remove_entry(lru_key)

    def get(self, url: str) -> Optional[CacheEntry]:
        """
        Get cached entry for URL.

        Args:
            url: URL to look up

        Returns:
            CacheEntry if found and not expired, None otherwise
        """
        self._cleanup_expired()

        if url not in self._cache:
            return None

        entry = self._cache[url]
        if entry.is_expired:
            self._remove_entry(url)
            return None

        # Update access order
        if url in self._access_order:
            self._access_order.remove(url)
        self._access_order.append(url)

        return entry

    def put(
        self, url: str, response_data: Any, headers: Dict[str, str], status_code: int
    ) -> None:
        """
        Store response in cache.

        Args:
            url: URL to cache
            response_data: Response data to cache
            headers: Response headers
            status_code: HTTP status code
        """
        self._cleanup_expired()
        self._evict_lru()

        # Compress data if enabled
        compressed = False
        if self.config.enable_compression and isinstance(response_data, (str, bytes)):
            try:
                if isinstance(response_data, str):
                    response_data = response_data.encode("utf-8")
                response_data = gzip.compress(response_data)
                compressed = True
            except Exception:
                pass  # Fall back to uncompressed

        entry = CacheEntry(
            url=url,
            response_data=response_data,
            headers=headers if self.config.cache_headers else {},
            status_code=status_code,
            timestamp=datetime.now(),
            ttl=timedelta(seconds=self.config.ttl_seconds),
            compressed=compressed,
        )

        self._cache[url] = entry
        if url in self._access_order:
            self._access_order.remove(url)
        self._access_order.append(url)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._access_order.clear()

    def size(self) -> int:
        """Get current cache size."""
        return len(self._cache)


# Enhanced Cache Implementation


class CacheBackend(str, Enum):
    """Cache backend types."""

    MEMORY = "memory"
    FILE = "file"
    REDIS = "redis"


@dataclass
class EnhancedCacheEntry:
    """Enhanced cache entry with metadata."""

    key: str
    data: Any
    timestamp: float
    ttl: Optional[float] = None
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    content_type: Optional[str] = None
    size: int = 0
    hit_count: int = 0
    last_accessed: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        if self.ttl is None:
            return False
        return time.time() - self.timestamp > self.ttl

    @property
    def age(self) -> float:
        """Get age of cache entry in seconds."""
        return time.time() - self.timestamp


@dataclass
class EnhancedCacheConfig:
    """Configuration for enhanced cache."""

    backend: CacheBackend = CacheBackend.MEMORY
    default_ttl: float = 3600.0  # 1 hour
    max_size: int = 1000  # Maximum number of entries
    max_memory_mb: int = 100  # Maximum memory usage in MB
    enable_etag: bool = True
    enable_conditional_requests: bool = True
    enable_compression: bool = True
    file_cache_dir: Optional[str] = None
    redis_url: Optional[str] = None
    redis_prefix: str = "web_fetch:"
    cleanup_interval: float = 300.0  # 5 minutes


class CacheBackendInterface(ABC):
    """Abstract interface for cache backends."""

    @abstractmethod
    async def get(self, key: str) -> Optional[EnhancedCacheEntry]:
        """Get cache entry by key."""
        pass

    @abstractmethod
    async def set(self, entry: EnhancedCacheEntry) -> bool:
        """Set cache entry."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete cache entry by key."""
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """Clear all cache entries."""
        pass

    @abstractmethod
    async def keys(self) -> List[str]:
        """Get all cache keys."""
        pass

    @abstractmethod
    async def size(self) -> int:
        """Get number of cache entries."""
        pass


class MemoryCacheBackend(CacheBackendInterface):
    """In-memory cache backend with LRU eviction."""

    def __init__(self, config: EnhancedCacheConfig):
        self.config = config
        self.cache: Dict[str, EnhancedCacheEntry] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[EnhancedCacheEntry]:
        """Get cache entry by key."""
        async with self._lock:
            entry = self.cache.get(key)
            if entry and not entry.is_expired:
                entry.hit_count += 1
                entry.last_accessed = time.time()
                return entry
            elif entry:
                # Remove expired entry
                del self.cache[key]
            return None

    async def set(self, entry: EnhancedCacheEntry) -> bool:
        """Set cache entry."""
        async with self._lock:
            # Check size limits
            if len(self.cache) >= self.config.max_size:
                await self._evict_entries()

            self.cache[entry.key] = entry
            return True

    async def delete(self, key: str) -> bool:
        """Delete cache entry by key."""
        async with self._lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False

    async def clear(self) -> bool:
        """Clear all cache entries."""
        async with self._lock:
            self.cache.clear()
            return True

    async def keys(self) -> List[str]:
        """Get all cache keys."""
        async with self._lock:
            return list(self.cache.keys())

    async def size(self) -> int:
        """Get number of cache entries."""
        async with self._lock:
            return len(self.cache)

    async def _evict_entries(self) -> None:
        """Evict least recently used entries."""
        if not self.cache:
            return

        # Sort by last accessed time and remove oldest entries
        sorted_entries = sorted(self.cache.items(), key=lambda x: x[1].last_accessed)

        # Remove 20% of entries
        num_to_remove = max(1, len(sorted_entries) // 5)
        for key, _ in sorted_entries[:num_to_remove]:
            del self.cache[key]


class FileCacheBackend(CacheBackendInterface):
    """File-based cache backend with persistent storage."""

    def __init__(self, config: EnhancedCacheConfig):
        self.config = config
        self.cache_dir = Path(config.file_cache_dir or "/tmp/web_fetch_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[EnhancedCacheEntry]:
        """Get cache entry by key from file."""
        cache_file = (
            self.cache_dir / f"{hashlib.sha256(key.encode()).hexdigest()}.cache"
        )

        async with self._lock:
            try:
                if not cache_file.exists():
                    return None

                import aiofiles

                async with aiofiles.open(cache_file, "rb") as f:
                    import pickle

                    entry = pickle.loads(await f.read())

                if not entry.is_expired:
                    entry.hit_count += 1
                    entry.last_accessed = time.time()
                    # Write back updated entry
                    async with aiofiles.open(cache_file, "wb") as f:
                        await f.write(pickle.dumps(entry))
                    return entry  # type: ignore[no-any-return]
                else:
                    # Remove expired entry
                    cache_file.unlink(missing_ok=True)
                    return None

            except Exception:
                return None

    async def set(self, entry: EnhancedCacheEntry) -> bool:
        """Set cache entry to file."""
        cache_file = (
            self.cache_dir / f"{hashlib.sha256(entry.key.encode()).hexdigest()}.cache"
        )

        async with self._lock:
            try:
                import pickle

                import aiofiles

                async with aiofiles.open(cache_file, "wb") as f:
                    await f.write(pickle.dumps(entry))
                return True
            except Exception:
                return False

    async def delete(self, key: str) -> bool:
        """Delete cache entry file."""
        cache_file = (
            self.cache_dir / f"{hashlib.sha256(key.encode()).hexdigest()}.cache"
        )

        async with self._lock:
            try:
                cache_file.unlink(missing_ok=True)
                return True
            except Exception:
                return False

    async def clear(self) -> bool:
        """Clear all cache files."""
        async with self._lock:
            try:
                for cache_file in self.cache_dir.glob("*.cache"):
                    cache_file.unlink(missing_ok=True)
                return True
            except Exception:
                return False

    async def keys(self) -> List[str]:
        """Get all cache keys from files."""
        async with self._lock:
            keys = []
            try:
                import pickle

                import aiofiles

                for cache_file in self.cache_dir.glob("*.cache"):
                    try:
                        async with aiofiles.open(cache_file, "rb") as f:
                            entry = pickle.loads(await f.read())
                            if not entry.is_expired:
                                keys.append(entry.key)
                    except Exception:
                        continue
            except Exception:
                pass
            return keys

    async def size(self) -> int:
        """Get number of cache files."""
        async with self._lock:
            return len(list(self.cache_dir.glob("*.cache")))


class RedisCacheBackend(CacheBackendInterface):
    """Redis cache backend for distributed caching."""

    def __init__(self, config: EnhancedCacheConfig):
        self.config = config
        self._redis = None
        self._lock = asyncio.Lock()

    async def _get_redis(self) -> Any:
        """Get or create Redis connection."""
        if self._redis is None:
            try:
                import aioredis

                self._redis = await aioredis.from_url(
                    self.config.redis_url or "redis://localhost:6379",
                    decode_responses=False,
                )
            except ImportError:
                raise ImportError(
                    "aioredis is required for Redis cache backend. Install with: pip install aioredis"
                )
        return self._redis

    async def get(self, key: str) -> Optional[EnhancedCacheEntry]:
        """Get cache entry from Redis."""
        redis_key = f"{self.config.redis_prefix}{key}"

        async with self._lock:
            try:
                redis = await self._get_redis()
                data = await redis.get(redis_key)

                if data:
                    import pickle

                    entry = pickle.loads(data)

                    if not entry.is_expired:
                        entry.hit_count += 1
                        entry.last_accessed = time.time()
                        # Update in Redis
                        await redis.set(
                            redis_key,
                            pickle.dumps(entry),
                            ex=int(entry.ttl) if entry.ttl else None,
                        )
                        return entry  # type: ignore[no-any-return]
                    else:
                        # Remove expired entry
                        await redis.delete(redis_key)
                        return None

            except Exception:
                return None

        return None

    async def set(self, entry: EnhancedCacheEntry) -> bool:
        """Set cache entry in Redis."""
        redis_key = f"{self.config.redis_prefix}{entry.key}"

        async with self._lock:
            try:
                redis = await self._get_redis()
                import pickle

                await redis.set(
                    redis_key,
                    pickle.dumps(entry),
                    ex=int(entry.ttl) if entry.ttl else None,
                )
                return True
            except Exception:
                return False

    async def delete(self, key: str) -> bool:
        """Delete cache entry from Redis."""
        redis_key = f"{self.config.redis_prefix}{key}"

        async with self._lock:
            try:
                redis = await self._get_redis()
                await redis.delete(redis_key)
                return True
            except Exception:
                return False

    async def clear(self) -> bool:
        """Clear all cache entries with prefix."""
        async with self._lock:
            try:
                redis = await self._get_redis()
                keys = await redis.keys(f"{self.config.redis_prefix}*")
                if keys:
                    await redis.delete(*keys)
                return True
            except Exception:
                return False

    async def keys(self) -> List[str]:
        """Get all cache keys from Redis."""
        async with self._lock:
            try:
                redis = await self._get_redis()
                redis_keys = await redis.keys(f"{self.config.redis_prefix}*")
                return [
                    key.decode().replace(self.config.redis_prefix, "")
                    for key in redis_keys
                ]
            except Exception:
                return []

    async def size(self) -> int:
        """Get number of cache entries."""
        async with self._lock:
            try:
                redis = await self._get_redis()
                keys = await redis.keys(f"{self.config.redis_prefix}*")
                return len(keys)
            except Exception:
                return 0

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()  # type: ignore[unreachable]


class EnhancedCache:
    """Enhanced cache with multiple backends and intelligent features."""

    def __init__(self, config: Optional[EnhancedCacheConfig] = None):
        """
        Initialize enhanced cache.

        Args:
            config: Cache configuration
        """
        self.config = config or EnhancedCacheConfig()
        self.backend = self._create_backend()
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "evictions": 0,
        }

        # Start cleanup task
        self._cleanup_task = None
        if self.config.cleanup_interval > 0:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    def _create_backend(self) -> CacheBackendInterface:
        """Create appropriate cache backend."""
        if self.config.backend == CacheBackend.MEMORY:
            return MemoryCacheBackend(self.config)
        elif self.config.backend == CacheBackend.FILE:
            return FileCacheBackend(self.config)
        elif self.config.backend == CacheBackend.REDIS:
            return RedisCacheBackend(self.config)
        else:
            raise ValueError(f"Unknown cache backend: {self.config.backend}")

    async def get(
        self, url: str, headers: Optional[Dict[str, str]] = None
    ) -> Optional[Any]:
        """Get cached response for URL."""
        key = self._generate_key(url, headers)
        entry = await self.backend.get(key)

        if entry:
            self.stats["hits"] += 1
            return entry.data
        else:
            self.stats["misses"] += 1
            return None

    async def set(
        self,
        url: str,
        data: Any,
        headers: Optional[Dict[str, str]] = None,
        ttl: Optional[float] = None,
    ) -> bool:
        """Cache response for URL."""
        key = self._generate_key(url, headers)

        entry = EnhancedCacheEntry(
            key=key,
            data=data,
            timestamp=time.time(),
            ttl=ttl or self.config.default_ttl,
            etag=headers.get("etag") if headers else None,
            last_modified=headers.get("last-modified") if headers else None,
            content_type=headers.get("content-type") if headers else None,
            size=len(str(data)) if data else 0,
        )

        success = await self.backend.set(entry)
        if success:
            self.stats["sets"] += 1
        return success

    def _generate_key(self, url: str, headers: Optional[Dict[str, str]] = None) -> str:
        """Generate cache key for URL and headers."""
        key_parts = [url]

        if headers:
            # Include relevant headers in key
            relevant_headers = ["authorization", "accept", "accept-language"]
            for header in relevant_headers:
                if header in headers:
                    key_parts.append(f"{header}:{headers[header]}")

        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode("utf-8")).hexdigest()

    async def _cleanup_loop(self) -> None:
        """Background cleanup task."""
        while True:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                # Cleanup logic would go here
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Cache cleanup error: {e}")

    async def close(self) -> None:
        """Close cache and cleanup resources."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        if hasattr(self.backend, "close"):
            await self.backend.close()
