"""
Advanced caching module for web-fetch.

This module provides intelligent caching strategies including:
- Multiple backend support (memory, Redis, Memcache)
- Cache invalidation by tags
- Cache warming strategies
- Performance monitoring
- Distributed caching support
"""

from .advanced_cache import (
    AdvancedCacheManager,
    CacheBackend,
    CacheStrategy,
    CacheEntry,
    CacheBackendInterface,
    MemoryCacheBackend,
    RedisCacheBackend,
    create_cache_manager
)

__all__ = [
    "AdvancedCacheManager",
    "CacheBackend", 
    "CacheStrategy",
    "CacheEntry",
    "CacheBackendInterface",
    "MemoryCacheBackend",
    "RedisCacheBackend",
    "create_cache_manager"
]
