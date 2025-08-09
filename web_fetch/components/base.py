"""
Component base interface and plugin registry for unified resources.

All resource types must implement ResourceComponent with the canonical
async methods:
- fetch: obtain raw/parsed content
- parse: optional additional parsing/transformation
- validate: check correctness/invariants
- cache_key: optional deterministic key for caching

Components are registered via the ComponentRegistry, supporting dynamic
lookup and instantiation without modifying core application code.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Protocol, Type, Set

from ..models.resource import ResourceConfig, ResourceKind, ResourceRequest, ResourceResult


class ResourceComponent(ABC):
    """Abstract base for all resource components."""

    kind: ResourceKind

    def __init__(self, config: Optional[ResourceConfig] = None) -> None:
        self.config = config or ResourceConfig()

    @abstractmethod
    async def fetch(self, request: ResourceRequest) -> ResourceResult:
        """Fetch and minimally process the resource."""
        raise NotImplementedError

    async def parse(self, result: ResourceResult) -> ResourceResult:
        """Optional deeper parsing step; default is identity."""
        return result

    async def validate(self, result: ResourceResult) -> ResourceResult:
        """Optional validation; default is identity."""
        return result

    def cache_key(self, request: ResourceRequest) -> Optional[str]:
        """Return a stable cache key for this request if applicable."""
        return None

    def cache_tags(self, request: ResourceRequest) -> Set[str]:
        """Return cache tags for invalidation purposes."""
        tags = {f"kind:{self.kind.value}"}

        # Add host-based tag if URI has a host
        if hasattr(request.uri, 'host') and request.uri.host:
            tags.add(f"host:{request.uri.host}")

        return tags

    def cache_ttl(self, request: ResourceRequest) -> Optional[int]:
        """Return custom TTL for this request, or None for default."""
        return None


class ComponentFactory(Protocol):
    """Callable that constructs a ResourceComponent."""

    def __call__(self, config: Optional[ResourceConfig] = None) -> ResourceComponent: ...


class ComponentRegistry:
    """Global registry for resource components (pluggable)."""

    def __init__(self) -> None:
        self._factories: Dict[ResourceKind, ComponentFactory] = {}

    def register(self, kind: ResourceKind, factory: ComponentFactory) -> None:
        self._factories[kind] = factory

    def unregister(self, kind: ResourceKind) -> None:
        self._factories.pop(kind, None)

    def create(self, kind: ResourceKind, config: Optional[ResourceConfig] = None) -> ResourceComponent:
        if kind not in self._factories:
            raise ValueError(f"No component factory registered for kind: {kind}")
        return self._factories[kind](config)

    def available(self) -> Dict[ResourceKind, ComponentFactory]:
        return dict(self._factories)


# Global default registry instance
component_registry = ComponentRegistry()


__all__ = [
    "ResourceComponent",
    "ComponentFactory",
    "ComponentRegistry",
    "component_registry",
]

