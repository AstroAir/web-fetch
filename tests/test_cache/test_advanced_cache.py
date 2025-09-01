"""
Tests for the advanced cache module.

This module tests the advanced caching strategies including cache invalidation,
distributed caching support, and cache warming strategies.
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, Mock, patch

from web_fetch.cache.advanced_cache import (
    AdvancedCacheManager,
    CacheBackend,
    CacheEntry,
    CacheStrategy,
    MemoryCacheBackend,
    RedisCacheBackend,
    create_cache_manager,
)


class TestCacheEntry:
    """Test the CacheEntry model."""

    def test_cache_entry_creation(self):
        """Test creating a cache entry."""
        entry = CacheEntry(
            key="test_key",
            value={"data": "test"},
            created_at=time.time(),
            last_accessed=time.time(),
            ttl=300
        )

        assert entry.key == "test_key"
        assert entry.value == {"data": "test"}
        assert entry.ttl == 300
        assert not entry.is_expired

    def test_cache_entry_expiration(self):
        """Test cache entry expiration."""
        # Create expired entry
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=time.time() - 400,  # 400 seconds ago
            last_accessed=time.time() - 400,
            ttl=300  # 300 second TTL
        )

        assert entry.is_expired

    def test_cache_entry_touch(self):
        """Test touching a cache entry updates access time."""
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=time.time(),
            last_accessed=time.time() - 100,
            ttl=300
        )

        old_access_time = entry.last_accessed
        entry.touch()

        assert entry.last_accessed > old_access_time
        assert entry.access_count == 1


class TestMemoryCacheBackend:
    """Test the memory cache backend."""

    @pytest.fixture
    def memory_backend(self):
        """Create a memory cache backend for testing."""
        return MemoryCacheBackend(max_size=10, max_memory=1024)

    @pytest.mark.asyncio
    async def test_memory_backend_basic_operations(self, memory_backend):
        """Test basic cache operations."""
        # Test set and get
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=time.time(),
            last_accessed=time.time(),
            ttl=300
        )

        result = await memory_backend.set("test_key", entry)
        assert result is True

        retrieved = await memory_backend.get("test_key")
        assert retrieved is not None
        assert retrieved.value == "test_value"

    @pytest.mark.asyncio
    async def test_memory_backend_delete(self, memory_backend):
        """Test deleting from memory cache."""
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=time.time(),
            last_accessed=time.time(),
            ttl=300
        )

        await memory_backend.set("test_key", entry)
        result = await memory_backend.delete("test_key")
        assert result is True

        retrieved = await memory_backend.get("test_key")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_memory_backend_clear(self, memory_backend):
        """Test clearing memory cache."""
        entry1 = CacheEntry(
            key="key1",
            value="value1",
            created_at=time.time(),
            last_accessed=time.time(),
            ttl=300
        )
        entry2 = CacheEntry(
            key="key2",
            value="value2",
            created_at=time.time(),
            last_accessed=time.time(),
            ttl=300
        )

        await memory_backend.set("key1", entry1)
        await memory_backend.set("key2", entry2)

        result = await memory_backend.clear()
        assert result is True

        assert await memory_backend.size() == 0

    @pytest.mark.asyncio
    async def test_memory_backend_keys(self, memory_backend):
        """Test getting keys from memory cache."""
        entry1 = CacheEntry(
            key="test_key1",
            value="value1",
            created_at=time.time(),
            last_accessed=time.time(),
            ttl=300
        )
        entry2 = CacheEntry(
            key="test_key2",
            value="value2",
            created_at=time.time(),
            last_accessed=time.time(),
            ttl=300
        )

        await memory_backend.set("test_key1", entry1)
        await memory_backend.set("test_key2", entry2)

        keys = await memory_backend.keys()
        assert "test_key1" in keys
        assert "test_key2" in keys
        assert len(keys) == 2


class TestAdvancedCacheManager:
    """Test the advanced cache manager."""

    @pytest.fixture
    def cache_manager(self):
        """Create a cache manager for testing."""
        backend = MemoryCacheBackend(max_size=10, max_memory=1024)
        return AdvancedCacheManager(
            backend=backend,
            strategy=CacheStrategy.LRU,
            default_ttl=300
        )

    @pytest.mark.asyncio
    async def test_cache_manager_basic_operations(self, cache_manager):
        """Test basic cache manager operations."""
        # Test set and get
        result = await cache_manager.set("test_key", "test_value", ttl=300)
        assert result is True

        retrieved = await cache_manager.get("test_key")
        assert retrieved == "test_value"

    @pytest.mark.asyncio
    async def test_cache_manager_with_tags(self, cache_manager):
        """Test cache manager with tags for invalidation."""
        tags = {"user:123", "category:news"}

        result = await cache_manager.set("test_key", "test_value", tags=tags)
        assert result is True

        # Test invalidation by tag
        invalidated = await cache_manager.invalidate_by_tag("user:123")
        assert invalidated == 1

        # Key should be gone
        retrieved = await cache_manager.get("test_key")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_cache_manager_delete(self, cache_manager):
        """Test deleting from cache manager."""
        await cache_manager.set("test_key", "test_value")

        result = await cache_manager.delete("test_key")
        assert result is True

        retrieved = await cache_manager.get("test_key")
        assert retrieved is None


class TestCacheFactory:
    """Test the cache factory functions."""

    def test_create_memory_cache_manager(self):
        """Test creating a memory cache manager."""
        manager = create_cache_manager(
            backend_type=CacheBackend.MEMORY,
            max_size=100,
            max_memory=1024 * 1024
        )

        assert isinstance(manager, AdvancedCacheManager)
        assert isinstance(manager.backend, MemoryCacheBackend)

    @patch('web_fetch.cache.advanced_cache.REDIS_AVAILABLE', True)
    def test_create_redis_cache_manager(self):
        """Test creating a Redis cache manager."""
        manager = create_cache_manager(
            backend_type=CacheBackend.REDIS,
            redis_url="redis://localhost:6379",
            key_prefix="test:"
        )

        assert isinstance(manager, AdvancedCacheManager)
        assert isinstance(manager.backend, RedisCacheBackend)

    def test_create_unsupported_cache_manager(self):
        """Test creating an unsupported cache manager raises error."""
        with pytest.raises(ValueError, match="Unsupported backend type"):
            create_cache_manager(backend_type="unsupported")
