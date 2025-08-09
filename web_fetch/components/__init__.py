"""
Component registry and built-in components for unified resources.

Importing this package registers built-in component implementations.
"""
from .base import ResourceComponent, ComponentFactory, ComponentRegistry, component_registry
from .manager import ResourceManager

# Import built-in adapters to register them via side-effects
from . import http_component as _http_component  # noqa: F401
from . import ftp_component as _ftp_component  # noqa: F401
from . import graphql_component as _graphql_component  # noqa: F401
from . import websocket_component as _websocket_component  # noqa: F401

# Import new extended resource components
from . import rss_component as _rss_component  # noqa: F401
from . import authenticated_api_component as _authenticated_api_component  # noqa: F401
from . import database_component as _database_component  # noqa: F401
from . import cloud_storage_component as _cloud_storage_component  # noqa: F401

__all__ = [
    "ResourceComponent",
    "ComponentFactory",
    "ComponentRegistry",
    "component_registry",
    "ResourceManager",
]

