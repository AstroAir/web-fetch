"""
Comprehensive tests for the cached resource manager module.
"""

import asyncio
import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, Any

from web_fetch.managers.cached_resource_manager import (
    CachedResourceManager,
    create_cached_resource_manager
)
from web_fetch.models.resource import (
    ResourceRequest,
    ResourceResult,
    ResourceKind,
    ResourceConfig
)
from web_fetch.cache import CacheBackend
from web_fetch.components.base import ResourceComponent
from web_fetch.exceptions import WebFetchError


class MockResourceComponent(ResourceComponent):
    """Mock resource component for testing."""

    def __init__(self, kind: ResourceKind):
        self.kind = kind
        self._cache_ttl = 300
        self._cache_tags = set()

    async def fetch(self, request: ResourceRequest) -> ResourceResult:
        """Mock fetch implementation."""
        return ResourceResult(
            url=str(request.uri),
            content={"data": "test"},
            status_code=200,
            metadata={}
        )

    def cache_key(self, request: ResourceRequest) -> str:
        """Generate cache key."""
        return f"mock:{request.uri}"

    def cache_ttl(self, request: ResourceRequest) -> int:
        """Get cache TTL."""
        return self._cache_ttl

    def cache_tags(self, request: ResourceRequest) -> set:
        """Get cache tags."""
        return self._cache_tags.copy()


class TestCachedResourceManagerInitialization:
    """Test CachedResourceManager initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        manager = CachedResourceManager()

        assert manager is not None
        assert manager.warming_enabled is True
        assert manager.invalidation_enabled is True
        assert manager.cache_manager is not None
        assert manager.metrics_collector is not None
        assert isinstance(manager.warming_patterns, dict)
        assert isinstance(manager.invalidation_rules, dict)

    def test_custom_initialization(self):
        """Test initialization with custom parameters."""
        cache_config = {"max_size": 100, "default_ttl": 600}

        manager = CachedResourceManager(
            cache_backend=CacheBackend.MEMORY,
            cache_config=cache_config,
            enable_warming=False,
            enable_invalidation=False
        )

        assert manager.warming_enabled is False
        assert manager.invalidation_enabled is False

    def test_create_cached_resource_manager_function(self):
        """Test the convenience creation function."""
        manager = create_cached_resource_manager(
            cache_backend=CacheBackend.MEMORY,
            enable_warming=True,
            enable_invalidation=True
        )

        assert isinstance(manager, CachedResourceManager)
        assert manager.warming_enabled is True
        assert manager.invalidation_enabled is True


class TestCachedResourceManagerCaching:
    """Test caching functionality."""

    @pytest.fixture
    def manager(self):
        """Create a CachedResourceManager instance for testing."""
        return CachedResourceManager(cache_backend=CacheBackend.MEMORY)

    @pytest.fixture
    def mock_component(self):
        """Create a mock component."""
        return MockResourceComponent(ResourceKind.HTTP)

    @pytest.fixture
    def sample_request(self):
        """Create a sample resource request."""
        return ResourceRequest(
            uri="https://example.com/api/data",
            kind=ResourceKind.HTTP,
            use_cache=True
        )

    @pytest.mark.asyncio
    async def test_fetch_resource_cache_hit(self, manager, mock_component, sample_request):
        """Test successful cache hit scenario."""
        # Mock the component registry
        with patch.object(manager, 'get_component', return_value=mock_component):
            # Mock cache manager to return cached result
            cached_result = ResourceResult(
                url=str(sample_request.uri),
                content={"cached": "data"},
                status_code=200,
                metadata={"cache_hit": True}
            )

            with patch.object(manager.cache_manager, 'get', return_value=cached_result):
                result = await manager.fetch_resource(sample_request)

                assert result == cached_result
                assert result.metadata["cache_hit"] is True
                manager.cache_manager.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_resource_cache_miss(self, manager, mock_component, sample_request):
        """Test cache miss scenario with fresh fetch."""
        # Mock the component registry
        with patch.object(manager, 'get_component', return_value=mock_component):
            # Mock cache manager to return None (cache miss)
            with patch.object(manager.cache_manager, 'get', return_value=None):
                with patch.object(manager.cache_manager, 'set') as mock_set:
                    result = await manager.fetch_resource(sample_request)

                    assert result.metadata["cache_hit"] is False
                    assert "fetched_at" in result.metadata
                    assert "cached_at" in result.metadata

                    # Verify cache was updated
                    mock_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_resource_no_component(self, manager, sample_request):
        """Test behavior when no component is registered."""
        # Mock get_component to return None
        with patch.object(manager, 'get_component', return_value=None):
            result = await manager.fetch_resource(sample_request)

            assert result.status_code == 500
            assert "No component registered" in result.error
            assert result.url == str(sample_request.uri)

    @pytest.mark.asyncio
    async def test_fetch_resource_caching_disabled(self, manager, mock_component):
        """Test behavior when caching is disabled."""
        request = ResourceRequest(
            uri="https://example.com/api/data",
            kind=ResourceKind.HTTP,
            use_cache=False
        )

        with patch.object(manager, 'get_component', return_value=mock_component):
            with patch.object(manager, '_fetch_fresh') as mock_fetch_fresh:
                mock_result = ResourceResult(
                    url=str(request.uri),
                    content={"fresh": "data"},
                    status_code=200
                )
                mock_fetch_fresh.return_value = mock_result

                result = await manager.fetch_resource(request)

                assert result == mock_result
                mock_fetch_fresh.assert_called_once_with(mock_component, request)

    @pytest.mark.asyncio
    async def test_cache_key_generation(self, manager, mock_component, sample_request):
        """Test cache key generation."""
        # Test component-specific cache key
        cache_key = manager._generate_cache_key(mock_component, sample_request)
        expected_key = f"{mock_component.kind.value}:mock:{sample_request.uri}"
        assert cache_key == expected_key

        # Test default cache key generation
        mock_component.cache_key = MagicMock(return_value=None)
        cache_key = manager._generate_cache_key(mock_component, sample_request)
        assert cache_key.startswith(f"{sample_request.kind.value}:")
        assert len(cache_key.split(':')[1]) == 16  # SHA256 hash truncated to 16 chars


class TestCachedResourceManagerWarming:
    """Test cache warming functionality."""

    @pytest.fixture
    def manager(self):
        """Create a CachedResourceManager with warming enabled."""
        return CachedResourceManager(
            cache_backend=CacheBackend.MEMORY,
            enable_warming=True
        )

    @pytest.fixture
    def mock_component(self):
        """Create a mock component."""
        return MockResourceComponent(ResourceKind.HTTP)

    @pytest.fixture
    def sample_request(self):
        """Create a sample resource request."""
        return ResourceRequest(
            uri="https://example.com/api/warm",
            kind=ResourceKind.HTTP
        )

    @pytest.mark.asyncio
    async def test_warm_cache_success(self, manager, mock_component, sample_request):
        """Test successful cache warming."""
        with patch.object(manager, 'get_component', return_value=mock_component):
            with patch.object(manager.cache_manager, 'get', return_value=None):
                with patch.object(manager.cache_manager, 'warm_cache') as mock_warm:
                    result = await manager.warm_cache(sample_request)

                    assert result is True
                    mock_warm.assert_called_once()

    @pytest.mark.asyncio
    async def test_warm_cache_already_cached(self, manager, mock_component, sample_request):
        """Test warming when cache already contains the item."""
        cached_result = ResourceResult(url=str(sample_request.uri), content={})

        with patch.object(manager, 'get_component', return_value=mock_component):
            with patch.object(manager.cache_manager, 'get', return_value=cached_result):
                result = await manager.warm_cache(sample_request)

                assert result is False

    @pytest.mark.asyncio
    async def test_warm_cache_force(self, manager, mock_component, sample_request):
        """Test forced cache warming."""
        cached_result = ResourceResult(url=str(sample_request.uri), content={})

        with patch.object(manager, 'get_component', return_value=mock_component):
            with patch.object(manager.cache_manager, 'get', return_value=cached_result):
                with patch.object(manager.cache_manager, 'warm_cache') as mock_warm:
                    result = await manager.warm_cache(sample_request, force=True)

                    assert result is True
                    mock_warm.assert_called_once()

    @pytest.mark.asyncio
    async def test_warm_cache_disabled(self, sample_request):
        """Test warming when warming is disabled."""
        manager = CachedResourceManager(enable_warming=False)

        result = await manager.warm_cache(sample_request)
        assert result is False

    @pytest.mark.asyncio
    async def test_warm_cache_no_component(self, manager, sample_request):
        """Test warming when no component is available."""
        with patch.object(manager, 'get_component', return_value=None):
            result = await manager.warm_cache(sample_request)
            assert result is False

    def test_add_warming_pattern(self, manager, sample_request):
        """Test adding warming patterns."""
        requests = [sample_request]
        manager.add_warming_pattern("test_pattern", requests, interval=1800)

        assert "test_pattern" in manager.warming_patterns
        pattern = manager.warming_patterns["test_pattern"]
        assert pattern["requests"] == requests
        assert pattern["interval"] == 1800
        assert pattern["last_run"] is None

    @pytest.mark.asyncio
    async def test_run_warming_patterns(self, manager, mock_component, sample_request):
        """Test running warming patterns."""
        # Add a warming pattern
        requests = [sample_request]
        manager.add_warming_pattern("test_pattern", requests)

        with patch.object(manager, 'warm_cache', return_value=True) as mock_warm:
            results = await manager.run_warming_patterns()

            assert "test_pattern" in results
            assert results["test_pattern"] == 1
            mock_warm.assert_called_once_with(sample_request)

            # Check that last_run was updated
            pattern = manager.warming_patterns["test_pattern"]
            assert pattern["last_run"] is not None


class TestCachedResourceManagerInvalidation:
    """Test cache invalidation functionality."""

    @pytest.fixture
    def manager(self):
        """Create a CachedResourceManager with invalidation enabled."""
        return CachedResourceManager(
            cache_backend=CacheBackend.MEMORY,
            enable_invalidation=True
        )

    @pytest.mark.asyncio
    async def test_invalidate_by_tag(self, manager):
        """Test invalidation by tag."""
        with patch.object(manager.cache_manager, 'invalidate_by_tag', return_value=5) as mock_invalidate:
            result = await manager.invalidate_by_tag("test_tag")

            assert result == 5
            mock_invalidate.assert_called_once_with("test_tag")

    @pytest.mark.asyncio
    async def test_invalidate_by_tag_disabled(self):
        """Test invalidation when invalidation is disabled."""
        manager = CachedResourceManager(enable_invalidation=False)

        result = await manager.invalidate_by_tag("test_tag")
        assert result == 0

    @pytest.mark.asyncio
    async def test_invalidate_by_host(self, manager):
        """Test invalidation by host."""
        with patch.object(manager, 'invalidate_by_tag', return_value=3) as mock_invalidate:
            result = await manager.invalidate_by_host("example.com")

            assert result == 3
            mock_invalidate.assert_called_once_with("host:example.com")

    @pytest.mark.asyncio
    async def test_invalidate_by_kind(self, manager):
        """Test invalidation by resource kind."""
        with patch.object(manager, 'invalidate_by_tag', return_value=7) as mock_invalidate:
            result = await manager.invalidate_by_kind("http")

            assert result == 7
            mock_invalidate.assert_called_once_with("kind:http")


class TestCachedResourceManagerStats:
    """Test cache statistics functionality."""

    @pytest.fixture
    def manager(self):
        """Create a CachedResourceManager for testing."""
        return CachedResourceManager()

    def test_get_cache_stats(self, manager):
        """Test getting cache statistics."""
        # Mock the cache manager stats
        mock_stats = {
            "hits": 100,
            "misses": 20,
            "hit_rate": 0.833,
            "total_requests": 120
        }

        with patch.object(manager.cache_manager, 'get_stats', return_value=mock_stats):
            stats = manager.get_cache_stats()

            # Check that base stats are included
            assert stats["hits"] == 100
            assert stats["misses"] == 20
            assert stats["hit_rate"] == 0.833
            assert stats["total_requests"] == 120

            # Check that additional stats are included
            assert "warming_patterns" in stats
            assert "warming_enabled" in stats
            assert "invalidation_enabled" in stats
            assert stats["warming_enabled"] is True
            assert stats["invalidation_enabled"] is True


class TestCachedResourceManagerErrorHandling:
    """Test error handling scenarios."""

    @pytest.fixture
    def manager(self):
        """Create a CachedResourceManager for testing."""
        return CachedResourceManager()

    @pytest.fixture
    def mock_component(self):
        """Create a mock component that can raise errors."""
        component = MockResourceComponent(ResourceKind.HTTP)
        return component

    @pytest.mark.asyncio
    async def test_fetch_resource_component_error(self, manager, mock_component):
        """Test handling of component fetch errors."""
        request = ResourceRequest(
            uri="https://example.com/error",
            kind=ResourceKind.HTTP,
            use_cache=True
        )

        # Mock component to raise an error
        mock_component.fetch = AsyncMock(side_effect=WebFetchError("Component error"))

        with patch.object(manager, 'get_component', return_value=mock_component):
            with patch.object(manager.cache_manager, 'get', return_value=None):
                with pytest.raises(WebFetchError, match="Component error"):
                    await manager.fetch_resource(request)

    @pytest.mark.asyncio
    async def test_cache_operation_error(self, manager, mock_component):
        """Test handling of cache operation errors."""
        request = ResourceRequest(
            uri="https://example.com/cache-error",
            kind=ResourceKind.HTTP,
            use_cache=True
        )

        with patch.object(manager, 'get_component', return_value=mock_component):
            # Mock cache get to raise an error
            with patch.object(manager.cache_manager, 'get', side_effect=Exception("Cache error")):
                # Should fall back to fresh fetch
                result = await manager.fetch_resource(request)
                assert result.metadata["cache_hit"] is False


class TestCachedResourceManagerCleanup:
    """Test cleanup functionality."""

    @pytest.fixture
    def manager(self):
        """Create a CachedResourceManager for testing."""
        return CachedResourceManager()

    @pytest.mark.asyncio
    async def test_cleanup(self, manager):
        """Test cleanup functionality."""
        with patch.object(manager.cache_manager, 'cleanup') as mock_cleanup:
            await manager.cleanup()
            mock_cleanup.assert_called_once()


class TestCachedResourceManagerEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def manager(self):
        """Create a CachedResourceManager for testing."""
        return CachedResourceManager()

    @pytest.fixture
    def mock_component(self):
        """Create a mock component."""
        return MockResourceComponent(ResourceKind.HTTP)

    @pytest.mark.asyncio
    async def test_cache_key_generation_with_complex_request(self, manager, mock_component):
        """Test cache key generation with complex request parameters."""
        request = ResourceRequest(
            uri="https://example.com/api/complex",
            kind=ResourceKind.HTTP,
            headers={"Authorization": "Bearer token", "Accept": "application/json"},
            options={"timeout": 30, "retries": 3}
        )

        cache_key = manager._generate_cache_key(mock_component, request)
        assert cache_key is not None
        assert cache_key.startswith(f"{request.kind.value}:")

    @pytest.mark.asyncio
    async def test_multiple_concurrent_requests(self, manager, mock_component):
        """Test handling of multiple concurrent requests for the same resource."""
        request = ResourceRequest(
            uri="https://example.com/api/concurrent",
            kind=ResourceKind.HTTP,
            use_cache=True
        )

        with patch.object(manager, 'get_component', return_value=mock_component):
            with patch.object(manager.cache_manager, 'get', return_value=None):
                with patch.object(manager.cache_manager, 'set'):
                    # Simulate concurrent requests
                    tasks = [
                        manager.fetch_resource(request)
                        for _ in range(3)
                    ]

                    results = await asyncio.gather(*tasks)

                    # All results should be successful
                    assert len(results) == 3
                    for result in results:
                        assert result.status_code == 200
                        assert result.metadata["cache_hit"] is False


class TestCachedResourceManagerCleanup:
    """Test cleanup functionality."""

    @pytest.fixture
    def manager(self):
        """Create a CachedResourceManager for testing."""
        return CachedResourceManager()

    @pytest.mark.asyncio
    async def test_cleanup(self, manager):
        """Test cleanup functionality."""
        with patch.object(manager.cache_manager, 'cleanup') as mock_cleanup:
            await manager.cleanup()
            mock_cleanup.assert_called_once()


class TestCachedResourceManagerEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def manager(self):
        """Create a CachedResourceManager for testing."""
        return CachedResourceManager()

    @pytest.fixture
    def mock_component(self):
        """Create a mock component."""
        return MockResourceComponent(ResourceKind.HTTP)

    @pytest.mark.asyncio
    async def test_cache_key_generation_with_complex_request(self, manager, mock_component):
        """Test cache key generation with complex request parameters."""
        request = ResourceRequest(
            uri="https://example.com/api/complex",
            kind=ResourceKind.HTTP,
            headers={"Authorization": "Bearer token", "Accept": "application/json"},
            options={"timeout": 30, "retries": 3}
        )

        cache_key = manager._generate_cache_key(mock_component, request)
        assert cache_key is not None
        assert cache_key.startswith(f"{request.kind.value}:")

    @pytest.mark.asyncio
    async def test_cache_result_with_metadata(self, manager, mock_component):
        """Test caching result with existing metadata."""
        request = ResourceRequest(
            uri="https://example.com/api/metadata",
            kind=ResourceKind.HTTP
        )

        result = ResourceResult(
            url=str(request.uri),
            content={"data": "test"},
            status_code=200,
            metadata={"existing": "metadata"}
        )

        cache_key = "test:cache:key"

        with patch.object(manager.cache_manager, 'set') as mock_set:
            await manager._cache_result(mock_component, request, result, cache_key)

            # Check that metadata was preserved and enhanced
            assert result.metadata["existing"] == "metadata"
            assert "cached_at" in result.metadata
            assert "cache_key" in result.metadata
            assert "cache_tags" in result.metadata

            mock_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_fresh_adds_metadata(self, manager, mock_component):
        """Test that _fetch_fresh adds appropriate metadata."""
        request = ResourceRequest(
            uri="https://example.com/api/fresh",
            kind=ResourceKind.HTTP
        )

        result = await manager._fetch_fresh(mock_component, request)

        assert result.metadata["cache_hit"] is False
        assert "fetched_at" in result.metadata

        # Verify timestamp format
        fetched_at = result.metadata["fetched_at"]
        datetime.fromisoformat(fetched_at.replace('Z', '+00:00'))  # Should not raise

    @pytest.mark.asyncio
    async def test_multiple_concurrent_requests(self, manager, mock_component):
        """Test handling of multiple concurrent requests for the same resource."""
        request = ResourceRequest(
            uri="https://example.com/api/concurrent",
            kind=ResourceKind.HTTP,
            use_cache=True
        )

        with patch.object(manager, 'get_component', return_value=mock_component):
            with patch.object(manager.cache_manager, 'get', return_value=None):
                with patch.object(manager.cache_manager, 'set') as mock_set:
                    # Simulate concurrent requests
                    tasks = [
                        manager.fetch_resource(request)
                        for _ in range(5)
                    ]

                    results = await asyncio.gather(*tasks)

                    # All results should be successful
                    assert len(results) == 5
                    for result in results:
                        assert result.status_code == 200
                        assert result.metadata["cache_hit"] is False

    def test_warming_patterns_empty_requests(self, manager):
        """Test warming patterns with empty request list."""
        manager.add_warming_pattern("empty_pattern", [], interval=3600)

        assert "empty_pattern" in manager.warming_patterns
        pattern = manager.warming_patterns["empty_pattern"]
        assert pattern["requests"] == []

    @pytest.mark.asyncio
    async def test_run_warming_patterns_empty(self, manager):
        """Test running warming patterns when no patterns exist."""
        results = await manager.run_warming_patterns()
        assert results == {}
