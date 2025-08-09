"""
Unified ResourceManager orchestrates components via the registry.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .base import ResourceComponent, component_registry
from ..models.resource import ResourceConfig, ResourceKind, ResourceRequest, ResourceResult


class ResourceManager:
    """High-level manager to interact with resource components uniformly."""

    def __init__(self, default_config: Optional[ResourceConfig] = None) -> None:
        self.default_config = default_config or ResourceConfig()

    def list_components(self) -> Dict[str, str]:
        return {k.value: v.__class__.__name__ for k, v in component_registry.available().items()}

    def get_component(self, kind: ResourceKind) -> ResourceComponent:
        return component_registry.create(kind, self.default_config)

    async def fetch(self, request: ResourceRequest) -> ResourceResult:
        component = self.get_component(request.kind)
        result: ResourceResult = await component.fetch(request)
        result = await component.parse(result)
        result = await component.validate(result)
        return result


__all__ = ["ResourceManager"]

