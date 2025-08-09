"""
Unified resource component models: types, request/response, and common config.

These models define a component-oriented abstraction for fetching and processing
various resource types (web pages, APIs, files, etc.) via a single interface.
They intentionally avoid importing heavy runtime utilities to minimize cycles.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import AnyUrl, BaseModel, ConfigDict, Field

from .base import BaseConfig, BaseResult


class ResourceKind(str, Enum):
    """Kinds of resources handled by components.

    Extendable: new kinds can be added without modifying core logic by
    registering a component implementation for the new kind.
    """

    HTTP = "http"
    FTP = "ftp"
    GRAPHQL = "graphql"
    WEBSOCKET = "websocket"
    CRAWLER = "crawler"
    FILE = "file"  # local/remote file abstraction if needed

    # New resource types for extended functionality
    RSS = "rss"  # RSS/Atom feed resources
    API_AUTH = "api_auth"  # Authenticated API endpoints
    DATABASE = "database"  # Database connections and queries
    CLOUD_STORAGE = "cloud_storage"  # Cloud storage services (S3, GCS, Azure)


class ResourceConfig(BaseConfig):
    """Common configuration shared across resource components.

    Component-specific settings should be passed via `options` on the request
    or implemented in component-specific config models; this base keeps the
    cross-cutting concerns consistent.
    """

    enable_cache: bool = Field(default=True, description="Enable component-level caching")
    cache_ttl_seconds: int = Field(default=300, ge=1, description="Default TTL for cache")
    trace_id: Optional[str] = Field(default=None, description="Correlation ID for tracing")


class ResourceRequest(BaseModel):
    """Unified request for any resource component.

    - `uri` supports multiple schemes (http, https, ftp, ws, wss, file, ...)
    - `kind` selects the component implementation via the registry
    - `headers` and `params` are optional and primarily used by HTTP-like kinds
    - `options` carries type-specific parameters (e.g., method, data, FTP operation)
    """

    uri: AnyUrl = Field(description="Target resource URI (http/https/ftp/ws/...) ")
    kind: ResourceKind = Field(description="Type of resource/component to use")

    # Common optional fields
    headers: Optional[Dict[str, str]] = Field(default=None)
    params: Optional[Dict[str, Any]] = Field(default=None)

    # Extensible bag of type-specific parameters (kept schema-free intentionally)
    options: Dict[str, Any] = Field(default_factory=dict)

    # Optional per-request override for common behavior
    timeout_seconds: Optional[float] = Field(default=None, gt=0)
    use_cache: Optional[bool] = Field(default=None)

    model_config = ConfigDict(use_enum_values=True)


@dataclass
class ResourceResult(BaseResult):
    """Unified result format across resource components.

    This wraps transport/protocol-specific results in a consistent shape while
    preserving detailed metadata via the `metadata` dict.
    """

    status_code: Optional[int] = None
    headers: Dict[str, str] = field(default_factory=dict)
    content: Any = None
    content_type: Optional[str] = None

    # Structured metadata bag for parsers/extractors (protocol- or content-specific)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        if self.error is not None:
            return False
        if self.status_code is None:
            # Non-HTTP protocols might omit status; treat absence as success unless error set
            return True
        return 200 <= int(self.status_code) < 300


__all__ = [
    "ResourceKind",
    "ResourceConfig",
    "ResourceRequest",
    "ResourceResult",
]

