# Unified Component Architecture

This document explains the new component-based design where all resource types (web pages, APIs, files, etc.) are treated as instances of a common interface.

## Goals

- Single, unified interface for fetching and processing heterogeneous resources
- Pluggable components registered via a registry (no core code changes to add new types)
- Consistent request and response data structures
- Extensible configuration shared across components with type-specific options
- Proper separation of concerns between core orchestration and resource-specific logic

## Key Concepts

- ResourceKind: enum of kinds (http, ftp, graphql, websocket, crawler, file, ...)
- ResourceRequest: unified request model with `uri`, `kind`, and `options`
- ResourceResult: unified response with status_code, headers, content, metadata
- ResourceComponent: abstract base defining `fetch`, optional `parse` and `validate`
- ComponentRegistry: global registry to register/instantiate components
- ResourceManager: high-level orchestrator that routes requests to components

## Directory Layout

- web_fetch/models/resource.py — shared models (kinds, request, result, config)
- web_fetch/components/base.py — base interface and registry
- web_fetch/components/http_component.py — adapter for existing WebFetcher
- web_fetch/components/ftp_component.py — adapter for existing FTPFetcher
- web_fetch/components/manager.py — ResourceManager orchestration

## Creating a New Resource Type

1. Choose a ResourceKind value (or add a new one specific to your type).
2. Implement a component class extending ResourceComponent.
3. Register the component factory with `component_registry.register(ResourceKind.X, lambda cfg=None: MyComponent(cfg))`.
4. Optionally add a convenience function in `convenience.py` or your app layer.

### Example: GraphQL Component

```python
from web_fetch.components.base import ResourceComponent, component_registry
from web_fetch.models.resource import ResourceKind, ResourceRequest, ResourceResult

class GraphQLComponent(ResourceComponent):
    kind = ResourceKind.GRAPHQL

    async def fetch(self, request: ResourceRequest) -> ResourceResult:
        # Use existing GraphQL client in web_fetch/graphql
        from web_fetch.graphql.client import GraphQLClient
        client = GraphQLClient()
        query = request.options["query"]
        variables = request.options.get("variables")
        data = await client.execute(query, variables)
        return ResourceResult(url=str(request.uri), status_code=200, content=data, content_type="application/json")

# Register
component_registry.register(ResourceKind.GRAPHQL, lambda cfg=None: GraphQLComponent(cfg))
```

## Unified Request/Response

- ResourceRequest
  - uri: AnyUrl (http, https, ftp, ws, wss, ...)
  - kind: ResourceKind
  - headers, params: optional common fields for HTTP-like use
  - options: dict of type-specific parameters (e.g., method, data, operation)
  - timeout_seconds, use_cache: common overrides

- ResourceResult
  - status_code, headers, content, content_type
  - metadata: dict for structured details (pdf/image metadata, file info, etc.)
  - is_success property for consistent success checks

## Configuration

- ResourceConfig: minimal shared config (cache enable, ttl, trace id)
- Type-specific configs remain in their domains (e.g., HTTP FetchConfig, FTPConfig)
- Components accept `ResourceConfig` plus can hold their own type-specific config

## Plugin/Factory Pattern

- Use `component_registry.register(kind, factory)` to add implementations
- The registry is used by `ResourceManager` to create components dynamically
- No changes to core code are required for new resource kinds

## Usage Examples

### HTTP via unified API

```python
from web_fetch.components.manager import ResourceManager
from web_fetch.models.resource import ResourceRequest, ResourceKind

manager = ResourceManager()
request = ResourceRequest(
    uri="https://api.example.com/data",
    kind=ResourceKind.HTTP,
    options={"method": "GET", "content_type": "json"}
)
result = await manager.fetch(request)
print(result.is_success, result.content)
```

### FTP via unified API

```python
from web_fetch.components.manager import ResourceManager
from web_fetch.models.resource import ResourceRequest, ResourceKind

manager = ResourceManager()
request = ResourceRequest(
    uri="ftp://ftp.example.com/pub/",
    kind=ResourceKind.FTP,
    options={"operation": "list"}
)
result = await manager.fetch(request)
print(result.metadata.get("files_list"))
```

## Testing

- Add unit tests under tests/components/ for each component implementation
- Mock underlying clients (WebFetcher, FTPFetcher) to ensure isolation
- Validate schema stability of ResourceRequest/ResourceResult

## Migration Notes

- Legacy HTTP/FTP APIs remain unchanged; components wrap them for the unified API
- You can incrementally adopt the component architecture alongside existing code
