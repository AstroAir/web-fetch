"""
Comprehensive tests for the component manager.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from web_fetch.components.manager import (
    ComponentManager,
    ComponentRegistry,
    ComponentConfig,
    ComponentLifecycle,
    ComponentError,
)
from web_fetch.components.base import ResourceComponent
from web_fetch.components.http_component import HTTPComponent
from web_fetch.components.ftp_component import FTPComponent
from web_fetch.models.resource import ResourceRequest, ResourceResult, ResourceKind


class MockComponent(ResourceComponent):
    """Mock component for testing."""
    
    def __init__(self, kind: ResourceKind, name: str = "mock"):
        self.kind = kind
        self.name = name
        self._initialized = False
        self._cleaned_up = False
    
    async def fetch(self, request: ResourceRequest) -> ResourceResult:
        """Mock fetch implementation."""
        return ResourceResult(
            url=str(request.uri),
            content=f"Mock response from {self.name}",
            status_code=200
        )
    
    async def initialize(self):
        """Mock initialization."""
        self._initialized = True
    
    async def cleanup(self):
        """Mock cleanup."""
        self._cleaned_up = True
    
    def cache_key(self, request: ResourceRequest) -> str:
        """Generate cache key."""
        return f"{self.kind.value}:{request.uri}"
    
    def cache_ttl(self, request: ResourceRequest) -> int:
        """Get cache TTL."""
        return 300
    
    def cache_tags(self, request: ResourceRequest) -> set:
        """Get cache tags."""
        return {self.kind.value, self.name}


class TestComponentConfig:
    """Test component configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ComponentConfig()
        
        assert config.auto_initialize is True
        assert config.lazy_loading is True
        assert config.max_concurrent_components == 10
        assert config.component_timeout == 30.0
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = ComponentConfig(
            auto_initialize=False,
            lazy_loading=False,
            max_concurrent_components=20,
            component_timeout=60.0
        )
        
        assert config.auto_initialize is False
        assert config.lazy_loading is False
        assert config.max_concurrent_components == 20
        assert config.component_timeout == 60.0


class TestComponentRegistry:
    """Test component registry functionality."""
    
    @pytest.fixture
    def registry(self):
        """Create component registry."""
        return ComponentRegistry()
    
    def test_register_component(self, registry):
        """Test registering a component."""
        component = MockComponent(ResourceKind.HTTP, "test_http")
        
        registry.register(ResourceKind.HTTP, component)
        
        assert ResourceKind.HTTP in registry._components
        assert registry._components[ResourceKind.HTTP] == component
    
    def test_register_multiple_components(self, registry):
        """Test registering multiple components."""
        http_component = MockComponent(ResourceKind.HTTP, "http")
        ftp_component = MockComponent(ResourceKind.FTP, "ftp")
        
        registry.register(ResourceKind.HTTP, http_component)
        registry.register(ResourceKind.FTP, ftp_component)
        
        assert len(registry._components) == 2
        assert registry._components[ResourceKind.HTTP] == http_component
        assert registry._components[ResourceKind.FTP] == ftp_component
    
    def test_get_component(self, registry):
        """Test getting a component."""
        component = MockComponent(ResourceKind.HTTP, "test")
        registry.register(ResourceKind.HTTP, component)
        
        retrieved = registry.get(ResourceKind.HTTP)
        assert retrieved == component
        
        # Non-existent component
        assert registry.get(ResourceKind.WEBSOCKET) is None
    
    def test_unregister_component(self, registry):
        """Test unregistering a component."""
        component = MockComponent(ResourceKind.HTTP, "test")
        registry.register(ResourceKind.HTTP, component)
        
        unregistered = registry.unregister(ResourceKind.HTTP)
        assert unregistered == component
        assert ResourceKind.HTTP not in registry._components
        
        # Unregistering non-existent component
        assert registry.unregister(ResourceKind.FTP) is None
    
    def test_list_components(self, registry):
        """Test listing all components."""
        http_component = MockComponent(ResourceKind.HTTP, "http")
        ftp_component = MockComponent(ResourceKind.FTP, "ftp")
        
        registry.register(ResourceKind.HTTP, http_component)
        registry.register(ResourceKind.FTP, ftp_component)
        
        components = registry.list()
        assert len(components) == 2
        assert ResourceKind.HTTP in components
        assert ResourceKind.FTP in components
    
    def test_clear_registry(self, registry):
        """Test clearing the registry."""
        registry.register(ResourceKind.HTTP, MockComponent(ResourceKind.HTTP))
        registry.register(ResourceKind.FTP, MockComponent(ResourceKind.FTP))
        
        assert len(registry._components) == 2
        
        registry.clear()
        assert len(registry._components) == 0
    
    def test_component_exists(self, registry):
        """Test checking if component exists."""
        assert registry.exists(ResourceKind.HTTP) is False
        
        registry.register(ResourceKind.HTTP, MockComponent(ResourceKind.HTTP))
        assert registry.exists(ResourceKind.HTTP) is True


class TestComponentManager:
    """Test component manager functionality."""
    
    @pytest.fixture
    def config(self):
        """Create component configuration."""
        return ComponentConfig(auto_initialize=True, lazy_loading=False)
    
    @pytest.fixture
    def manager(self, config):
        """Create component manager."""
        return ComponentManager(config)
    
    def test_manager_initialization(self, manager):
        """Test manager initialization."""
        assert manager.config.auto_initialize is True
        assert manager.config.lazy_loading is False
        assert isinstance(manager.registry, ComponentRegistry)
        assert manager._lifecycle_state == ComponentLifecycle.CREATED
    
    @pytest.mark.asyncio
    async def test_register_and_initialize_component(self, manager):
        """Test registering and initializing a component."""
        component = MockComponent(ResourceKind.HTTP, "test")
        
        await manager.register_component(ResourceKind.HTTP, component)
        
        assert manager.registry.exists(ResourceKind.HTTP)
        assert component._initialized is True  # Auto-initialized
    
    @pytest.mark.asyncio
    async def test_register_without_auto_initialize(self):
        """Test registering without auto-initialization."""
        config = ComponentConfig(auto_initialize=False)
        manager = ComponentManager(config)
        
        component = MockComponent(ResourceKind.HTTP, "test")
        
        await manager.register_component(ResourceKind.HTTP, component)
        
        assert manager.registry.exists(ResourceKind.HTTP)
        assert component._initialized is False  # Not auto-initialized
    
    @pytest.mark.asyncio
    async def test_get_component(self, manager):
        """Test getting a component."""
        component = MockComponent(ResourceKind.HTTP, "test")
        await manager.register_component(ResourceKind.HTTP, component)
        
        retrieved = await manager.get_component(ResourceKind.HTTP)
        assert retrieved == component
        
        # Non-existent component
        assert await manager.get_component(ResourceKind.FTP) is None
    
    @pytest.mark.asyncio
    async def test_lazy_loading(self):
        """Test lazy loading of components."""
        config = ComponentConfig(lazy_loading=True)
        manager = ComponentManager(config)
        
        # Register component factory
        def create_http_component():
            return MockComponent(ResourceKind.HTTP, "lazy_http")
        
        manager.register_factory(ResourceKind.HTTP, create_http_component)
        
        # Component should be created on first access
        component = await manager.get_component(ResourceKind.HTTP)
        assert component is not None
        assert component.name == "lazy_http"
        
        # Second access should return same instance
        component2 = await manager.get_component(ResourceKind.HTTP)
        assert component is component2
    
    @pytest.mark.asyncio
    async def test_fetch_with_component(self, manager):
        """Test fetching using registered component."""
        component = MockComponent(ResourceKind.HTTP, "test")
        await manager.register_component(ResourceKind.HTTP, component)
        
        request = ResourceRequest(
            uri="https://example.com/test",
            kind=ResourceKind.HTTP
        )
        
        result = await manager.fetch(request)
        
        assert result.status_code == 200
        assert "Mock response from test" in result.content
        assert result.url == "https://example.com/test"
    
    @pytest.mark.asyncio
    async def test_fetch_with_no_component(self, manager):
        """Test fetching when no component is registered."""
        request = ResourceRequest(
            uri="https://example.com/test",
            kind=ResourceKind.HTTP
        )
        
        with pytest.raises(ComponentError, match="No component registered"):
            await manager.fetch(request)
    
    @pytest.mark.asyncio
    async def test_batch_fetch(self, manager):
        """Test batch fetching with multiple components."""
        http_component = MockComponent(ResourceKind.HTTP, "http")
        ftp_component = MockComponent(ResourceKind.FTP, "ftp")
        
        await manager.register_component(ResourceKind.HTTP, http_component)
        await manager.register_component(ResourceKind.FTP, ftp_component)
        
        requests = [
            ResourceRequest(uri="https://example.com/1", kind=ResourceKind.HTTP),
            ResourceRequest(uri="ftp://ftp.example.com/file", kind=ResourceKind.FTP),
            ResourceRequest(uri="https://example.com/2", kind=ResourceKind.HTTP),
        ]
        
        results = await manager.batch_fetch(requests)
        
        assert len(results) == 3
        assert all(result.status_code == 200 for result in results)
        assert "Mock response from http" in results[0].content
        assert "Mock response from ftp" in results[1].content
        assert "Mock response from http" in results[2].content
    
    @pytest.mark.asyncio
    async def test_concurrent_fetch_limit(self, manager):
        """Test concurrent fetch limit."""
        component = MockComponent(ResourceKind.HTTP, "test")
        await manager.register_component(ResourceKind.HTTP, component)
        
        # Override component fetch to add delay
        original_fetch = component.fetch
        
        async def slow_fetch(request):
            await asyncio.sleep(0.1)
            return await original_fetch(request)
        
        component.fetch = slow_fetch
        
        # Create many requests
        requests = [
            ResourceRequest(uri=f"https://example.com/{i}", kind=ResourceKind.HTTP)
            for i in range(20)
        ]
        
        start_time = asyncio.get_event_loop().time()
        results = await manager.batch_fetch(requests)
        end_time = asyncio.get_event_loop().time()
        
        assert len(results) == 20
        # Should take longer due to concurrency limit
        assert end_time - start_time > 0.1
    
    @pytest.mark.asyncio
    async def test_component_lifecycle(self, manager):
        """Test component lifecycle management."""
        component = MockComponent(ResourceKind.HTTP, "test")
        
        # Register and initialize
        await manager.register_component(ResourceKind.HTTP, component)
        assert component._initialized is True
        
        # Start manager
        await manager.start()
        assert manager._lifecycle_state == ComponentLifecycle.RUNNING
        
        # Stop manager
        await manager.stop()
        assert manager._lifecycle_state == ComponentLifecycle.STOPPED
        assert component._cleaned_up is True
    
    @pytest.mark.asyncio
    async def test_component_health_check(self, manager):
        """Test component health checking."""
        component = MockComponent(ResourceKind.HTTP, "test")
        
        # Add health check method
        component.health_check = AsyncMock(return_value=True)
        
        await manager.register_component(ResourceKind.HTTP, component)
        
        health_status = await manager.check_component_health(ResourceKind.HTTP)
        assert health_status is True
        
        component.health_check.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_component_metrics(self, manager):
        """Test component metrics collection."""
        component = MockComponent(ResourceKind.HTTP, "test")
        await manager.register_component(ResourceKind.HTTP, component)
        
        # Perform some fetches
        requests = [
            ResourceRequest(uri=f"https://example.com/{i}", kind=ResourceKind.HTTP)
            for i in range(5)
        ]
        
        await manager.batch_fetch(requests)
        
        metrics = manager.get_component_metrics(ResourceKind.HTTP)
        
        assert metrics["total_requests"] == 5
        assert metrics["successful_requests"] == 5
        assert metrics["failed_requests"] == 0
        assert "average_response_time" in metrics
    
    def test_get_registered_kinds(self, manager):
        """Test getting registered component kinds."""
        assert len(manager.get_registered_kinds()) == 0
        
        # Register components
        manager.registry.register(ResourceKind.HTTP, MockComponent(ResourceKind.HTTP))
        manager.registry.register(ResourceKind.FTP, MockComponent(ResourceKind.FTP))
        
        kinds = manager.get_registered_kinds()
        assert len(kinds) == 2
        assert ResourceKind.HTTP in kinds
        assert ResourceKind.FTP in kinds
    
    @pytest.mark.asyncio
    async def test_unregister_component(self, manager):
        """Test unregistering a component."""
        component = MockComponent(ResourceKind.HTTP, "test")
        await manager.register_component(ResourceKind.HTTP, component)
        
        assert manager.registry.exists(ResourceKind.HTTP)
        
        unregistered = await manager.unregister_component(ResourceKind.HTTP)
        assert unregistered == component
        assert not manager.registry.exists(ResourceKind.HTTP)
        assert component._cleaned_up is True
    
    @pytest.mark.asyncio
    async def test_component_error_handling(self, manager):
        """Test component error handling."""
        component = MockComponent(ResourceKind.HTTP, "failing")
        
        # Make component fetch fail
        component.fetch = AsyncMock(side_effect=Exception("Component error"))
        
        await manager.register_component(ResourceKind.HTTP, component)
        
        request = ResourceRequest(
            uri="https://example.com/fail",
            kind=ResourceKind.HTTP
        )
        
        with pytest.raises(Exception, match="Component error"):
            await manager.fetch(request)
    
    @pytest.mark.asyncio
    async def test_component_timeout(self):
        """Test component timeout handling."""
        config = ComponentConfig(component_timeout=0.1)  # Very short timeout
        manager = ComponentManager(config)
        
        component = MockComponent(ResourceKind.HTTP, "slow")
        
        # Make component fetch very slow
        async def slow_fetch(request):
            await asyncio.sleep(1.0)  # Longer than timeout
            return ResourceResult(url=str(request.uri), content="slow", status_code=200)
        
        component.fetch = slow_fetch
        
        await manager.register_component(ResourceKind.HTTP, component)
        
        request = ResourceRequest(
            uri="https://example.com/slow",
            kind=ResourceKind.HTTP
        )
        
        with pytest.raises(asyncio.TimeoutError):
            await manager.fetch(request)
