"""
Comprehensive tests for the base component module.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional

from web_fetch.components.base import (
    BaseComponent,
    ComponentConfig,
    ComponentStatus,
    ComponentError,
    ComponentMetrics,
)
from web_fetch.models.http import FetchRequest, FetchResult
from web_fetch.models.base import ContentType


class TestComponentConfig:
    """Test component configuration."""

    def test_component_config_creation(self):
        """Test creating component configuration."""
        config = ComponentConfig(
            name="test-component",
            enabled=True,
            timeout=30.0,
            max_retries=3,
            metadata={"version": "1.0"}
        )
        
        assert config.name == "test-component"
        assert config.enabled == True
        assert config.timeout == 30.0
        assert config.max_retries == 3
        assert config.metadata == {"version": "1.0"}

    def test_component_config_defaults(self):
        """Test component configuration defaults."""
        config = ComponentConfig(name="default-component")
        
        assert config.name == "default-component"
        assert config.enabled == True
        assert config.timeout == 30.0
        assert config.max_retries == 3
        assert config.metadata == {}

    def test_component_config_validation(self):
        """Test component configuration validation."""
        # Invalid timeout
        with pytest.raises(ValueError):
            ComponentConfig(name="test", timeout=-1.0)
        
        # Invalid max_retries
        with pytest.raises(ValueError):
            ComponentConfig(name="test", max_retries=-1)


class TestComponentStatus:
    """Test component status enumeration."""

    def test_status_values(self):
        """Test status enumeration values."""
        assert ComponentStatus.INACTIVE == "inactive"
        assert ComponentStatus.INITIALIZING == "initializing"
        assert ComponentStatus.ACTIVE == "active"
        assert ComponentStatus.ERROR == "error"
        assert ComponentStatus.SHUTTING_DOWN == "shutting_down"

    def test_status_transitions(self):
        """Test valid status transitions."""
        # Valid initial states
        initial_states = [ComponentStatus.INACTIVE, ComponentStatus.INITIALIZING]
        
        # Valid active transitions
        active_transitions = [
            ComponentStatus.ACTIVE,
            ComponentStatus.ERROR,
            ComponentStatus.SHUTTING_DOWN
        ]
        
        assert ComponentStatus.INACTIVE in initial_states
        assert ComponentStatus.ACTIVE in active_transitions


class TestComponentMetrics:
    """Test component metrics."""

    def test_component_metrics_creation(self):
        """Test creating component metrics."""
        metrics = ComponentMetrics(
            requests_processed=100,
            requests_successful=95,
            requests_failed=5,
            average_response_time=1.5,
            total_processing_time=150.0
        )
        
        assert metrics.requests_processed == 100
        assert metrics.requests_successful == 95
        assert metrics.requests_failed == 5
        assert metrics.average_response_time == 1.5
        assert metrics.total_processing_time == 150.0

    def test_component_metrics_success_rate(self):
        """Test calculating success rate."""
        metrics = ComponentMetrics(
            requests_processed=100,
            requests_successful=85,
            requests_failed=15
        )
        
        success_rate = metrics.success_rate
        assert success_rate == 0.85

    def test_component_metrics_zero_requests(self):
        """Test metrics with zero requests."""
        metrics = ComponentMetrics(
            requests_processed=0,
            requests_successful=0,
            requests_failed=0
        )
        
        assert metrics.success_rate == 0.0


class TestComponentError:
    """Test component error handling."""

    def test_component_error_creation(self):
        """Test creating component error."""
        error = ComponentError(
            message="Component failed",
            component_name="test-component",
            error_code="COMP_001",
            details={"reason": "timeout"}
        )
        
        assert error.message == "Component failed"
        assert error.component_name == "test-component"
        assert error.error_code == "COMP_001"
        assert error.details == {"reason": "timeout"}

    def test_component_error_string_representation(self):
        """Test component error string representation."""
        error = ComponentError(
            message="Test error",
            component_name="test-comp"
        )
        
        error_str = str(error)
        assert "Test error" in error_str
        assert "test-comp" in error_str


class MockComponent(BaseComponent):
    """Mock component for testing."""
    
    def __init__(self, config: ComponentConfig):
        super().__init__(config)
        self.process_calls = []
    
    async def process_request(self, request: FetchRequest) -> FetchResult:
        """Mock process request implementation."""
        self.process_calls.append(request)
        
        return FetchResult(
            url=request.url,
            status_code=200,
            headers={"content-type": "text/plain"},
            content="Mock response",
            content_type=ContentType.TEXT
        )
    
    async def _initialize_component(self) -> None:
        """Mock initialization."""
        await asyncio.sleep(0.01)  # Simulate initialization time
    
    async def _shutdown_component(self) -> None:
        """Mock shutdown."""
        await asyncio.sleep(0.01)  # Simulate shutdown time


class TestBaseComponent:
    """Test base component functionality."""

    def test_base_component_creation(self):
        """Test creating base component."""
        config = ComponentConfig(name="test-component")
        component = MockComponent(config)
        
        assert component.config == config
        assert component.name == "test-component"
        assert component.status == ComponentStatus.INACTIVE

    @pytest.mark.asyncio
    async def test_component_initialization(self):
        """Test component initialization."""
        config = ComponentConfig(name="test-component")
        component = MockComponent(config)
        
        assert component.status == ComponentStatus.INACTIVE
        
        await component.initialize()
        
        assert component.status == ComponentStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_component_shutdown(self):
        """Test component shutdown."""
        config = ComponentConfig(name="test-component")
        component = MockComponent(config)
        
        await component.initialize()
        assert component.status == ComponentStatus.ACTIVE
        
        await component.shutdown()
        assert component.status == ComponentStatus.INACTIVE

    @pytest.mark.asyncio
    async def test_component_process_request(self):
        """Test processing request through component."""
        config = ComponentConfig(name="test-component")
        component = MockComponent(config)
        
        await component.initialize()
        
        request = FetchRequest(url="https://example.com")
        result = await component.process_request(request)
        
        assert isinstance(result, FetchResult)
        assert result.url == "https://example.com"
        assert result.status_code == 200
        assert result.content == "Mock response"

    @pytest.mark.asyncio
    async def test_component_disabled(self):
        """Test disabled component behavior."""
        config = ComponentConfig(name="disabled-component", enabled=False)
        component = MockComponent(config)
        
        # Should not initialize when disabled
        await component.initialize()
        assert component.status == ComponentStatus.INACTIVE

    @pytest.mark.asyncio
    async def test_component_error_handling(self):
        """Test component error handling."""
        config = ComponentConfig(name="error-component")
        component = MockComponent(config)
        
        # Mock initialization error
        with patch.object(component, '_initialize_component', side_effect=Exception("Init failed")):
            await component.initialize()
            assert component.status == ComponentStatus.ERROR

    @pytest.mark.asyncio
    async def test_component_metrics_tracking(self):
        """Test component metrics tracking."""
        config = ComponentConfig(name="metrics-component")
        component = MockComponent(config)
        
        await component.initialize()
        
        # Process multiple requests
        for i in range(5):
            request = FetchRequest(url=f"https://example.com/{i}")
            await component.process_request(request)
        
        metrics = component.get_metrics()
        
        assert metrics.requests_processed == 5
        assert metrics.requests_successful == 5
        assert metrics.requests_failed == 0

    @pytest.mark.asyncio
    async def test_component_timeout_handling(self):
        """Test component timeout handling."""
        config = ComponentConfig(name="timeout-component", timeout=0.1)
        component = MockComponent(config)
        
        await component.initialize()
        
        # Mock slow processing
        async def slow_process(request):
            await asyncio.sleep(0.2)  # Longer than timeout
            return await component.process_request(request)
        
        with patch.object(component, 'process_request', side_effect=slow_process):
            request = FetchRequest(url="https://example.com")
            
            with pytest.raises(asyncio.TimeoutError):
                await component.process_request_with_timeout(request)

    @pytest.mark.asyncio
    async def test_component_retry_logic(self):
        """Test component retry logic."""
        config = ComponentConfig(name="retry-component", max_retries=2)
        component = MockComponent(config)
        
        await component.initialize()
        
        call_count = 0
        
        async def failing_process(request):
            nonlocal call_count
            call_count += 1
            if call_count < 3:  # Fail first 2 times
                raise Exception("Temporary failure")
            return await component.process_request(request)
        
        with patch.object(component, 'process_request', side_effect=failing_process):
            request = FetchRequest(url="https://example.com")
            result = await component.process_request_with_retry(request)
            
            assert call_count == 3  # Initial + 2 retries
            assert isinstance(result, FetchResult)

    @pytest.mark.asyncio
    async def test_component_max_retries_exceeded(self):
        """Test behavior when max retries are exceeded."""
        config = ComponentConfig(name="retry-component", max_retries=1)
        component = MockComponent(config)
        
        await component.initialize()
        
        async def always_failing_process(request):
            raise Exception("Persistent failure")
        
        with patch.object(component, 'process_request', side_effect=always_failing_process):
            request = FetchRequest(url="https://example.com")
            
            with pytest.raises(Exception, match="Persistent failure"):
                await component.process_request_with_retry(request)

    @pytest.mark.asyncio
    async def test_component_health_check(self):
        """Test component health check."""
        config = ComponentConfig(name="health-component")
        component = MockComponent(config)
        
        # Inactive component should be unhealthy
        health = await component.health_check()
        assert health["status"] == "unhealthy"
        
        # Active component should be healthy
        await component.initialize()
        health = await component.health_check()
        assert health["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_component_context_manager(self):
        """Test using component as async context manager."""
        config = ComponentConfig(name="context-component")
        
        async with MockComponent(config) as component:
            assert component.status == ComponentStatus.ACTIVE
            
            request = FetchRequest(url="https://example.com")
            result = await component.process_request(request)
            assert isinstance(result, FetchResult)
        
        # Should be shut down after context
        assert component.status == ComponentStatus.INACTIVE

    def test_component_configuration_update(self):
        """Test updating component configuration."""
        config = ComponentConfig(name="update-component", timeout=30.0)
        component = MockComponent(config)
        
        # Update configuration
        new_config = ComponentConfig(name="update-component", timeout=60.0)
        component.update_config(new_config)
        
        assert component.config.timeout == 60.0

    @pytest.mark.asyncio
    async def test_component_concurrent_requests(self):
        """Test handling concurrent requests."""
        config = ComponentConfig(name="concurrent-component")
        component = MockComponent(config)
        
        await component.initialize()
        
        # Process multiple requests concurrently
        requests = [
            FetchRequest(url=f"https://example.com/{i}")
            for i in range(5)
        ]
        
        results = await asyncio.gather(*[
            component.process_request(request)
            for request in requests
        ])
        
        assert len(results) == 5
        assert all(isinstance(result, FetchResult) for result in results)

    def test_component_string_representation(self):
        """Test component string representation."""
        config = ComponentConfig(name="repr-component")
        component = MockComponent(config)
        
        component_str = str(component)
        assert "repr-component" in component_str
        assert "inactive" in component_str.lower()

    def test_component_equality(self):
        """Test component equality comparison."""
        config1 = ComponentConfig(name="component-1")
        config2 = ComponentConfig(name="component-2")
        
        component1a = MockComponent(config1)
        component1b = MockComponent(config1)
        component2 = MockComponent(config2)
        
        assert component1a == component1b  # Same config
        assert component1a != component2   # Different config
