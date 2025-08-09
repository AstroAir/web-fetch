"""
GraphQL resource component adapter bridging GraphQLClient to the unified API.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import HttpUrl, TypeAdapter

from ..graphql.client import GraphQLClient
from ..graphql.models import GraphQLConfig, GraphQLMutation, GraphQLQuery, GraphQLResult
from ..models.resource import ResourceConfig, ResourceKind, ResourceRequest, ResourceResult
from .base import ResourceComponent, component_registry


class GraphQLResourceComponent(ResourceComponent):
    kind = ResourceKind.GRAPHQL

    def __init__(self, config: Optional[ResourceConfig] = None, gql_config: Optional[GraphQLConfig] = None):
        super().__init__(config)
        self.gql_config = gql_config

    def _to_http_url(self, uri: str) -> HttpUrl:
        adapter = TypeAdapter(HttpUrl)
        return adapter.validate_python(uri)

    async def fetch(self, request: ResourceRequest) -> ResourceResult:
        # Expect options: {"query": str, "variables": dict, "operation": "query"|"mutation"}
        query_text = request.options.get("query")
        if not query_text:
            return ResourceResult(url=str(request.uri), error="Missing 'query' in options")
        variables = request.options.get("variables") or {}
        operation = str(request.options.get("operation", "query")).lower()

        config = self.gql_config or GraphQLConfig(endpoint=self._to_http_url(str(request.uri)))

        async with GraphQLClient(config) as client:
            # Use a common type for operation to satisfy type checker
            op: Any
            if operation == "mutation":
                op = GraphQLMutation(query=query_text, variables=variables)
            else:
                op = GraphQLQuery(query=query_text, variables=variables)

            gql_result: GraphQLResult = await client.execute(op)

        # Map GraphQLResult -> ResourceResult
        metadata: Dict[str, Any] = {
            "errors": gql_result.errors,
            "extensions": getattr(gql_result, "extensions", None),
        }

        return ResourceResult(
            url=str(request.uri),
            status_code=getattr(gql_result, "status_code", 200 if gql_result.success else 500),
            headers=getattr(gql_result, "headers", {}) or {},
            content=gql_result.data,
            content_type="application/json",
            metadata=metadata,
            response_time=getattr(gql_result, "response_time", 0.0),
            error=("; ".join(gql_result.error_messages) if getattr(gql_result, "has_errors", False) else None),
        )


# Register component in the global registry
component_registry.register(ResourceKind.GRAPHQL, lambda config=None: GraphQLResourceComponent(config))

__all__ = ["GraphQLResourceComponent"]

