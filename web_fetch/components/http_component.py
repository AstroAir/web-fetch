"""
HTTP resource component adapter bridging existing WebFetcher to the unified API.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import HttpUrl, TypeAdapter

from ..core_fetcher import WebFetcher
from ..models.base import ContentType
from ..models.http import FetchConfig as HTTPFetchConfig, FetchRequest
from ..models.resource import ResourceConfig, ResourceKind, ResourceRequest, ResourceResult
from .base import ResourceComponent, component_registry


class HTTPResourceComponent(ResourceComponent):
    kind = ResourceKind.HTTP

    def __init__(self, config: Optional[ResourceConfig] = None, http_config: Optional[HTTPFetchConfig] = None):
        super().__init__(config)
        self.http_config = http_config or HTTPFetchConfig()

    def _to_http_url(self, uri: str) -> HttpUrl:
        adapter = TypeAdapter(HttpUrl)
        return adapter.validate_python(uri)

    async def fetch(self, request: ResourceRequest) -> ResourceResult:
        # Map unified request -> existing HTTP FetchRequest
        method: str = str(request.options.get("method", "GET"))
        headers: Optional[Dict[str, str]] = request.headers
        data: Optional[Any] = request.options.get("data")
        params: Optional[Dict[str, Any]] = request.params  # Already Dict[str, Any]
        content_type = ContentType(request.options.get("content_type", ContentType.RAW))

        http_request = FetchRequest(
            url=self._to_http_url(str(request.uri)),
            method=method,
            headers=headers,
            data=data,
            params=params,
            content_type=content_type,
            timeout_override=request.timeout_seconds,
        )

        async with WebFetcher(self.http_config) as fetcher:
            http_result = await fetcher.fetch_single(http_request)

        # Map existing FetchResult -> unified ResourceResult
        result = ResourceResult(
            url=str(request.uri),
            status_code=http_result.status_code,
            headers=http_result.headers,
            content=http_result.content,
            content_type=http_result.content_type.value if hasattr(http_result.content_type, "value") else str(http_result.content_type),
            error=http_result.error,
            response_time=http_result.response_time,
        )

        # Fill metadata bag using existing structured fields
        metadata: Dict[str, Any] = {}
        if http_result.pdf_metadata:
            metadata["pdf"] = http_result.pdf_metadata.__dict__
        if http_result.image_metadata:
            metadata["image"] = http_result.image_metadata.__dict__
        if http_result.feed_metadata:
            metadata["feed"] = http_result.feed_metadata.__dict__
        if http_result.csv_metadata:
            metadata["csv"] = http_result.csv_metadata.__dict__
        if http_result.links:
            metadata["links"] = [l.__dict__ for l in http_result.links]
        if http_result.content_summary:
            metadata["content_summary"] = http_result.content_summary.__dict__
        if http_result.extracted_text:
            metadata["extracted_text"] = http_result.extracted_text
        if http_result.structured_data:
            metadata["structured_data"] = http_result.structured_data

        result.metadata = metadata
        return result


# Register component in the global registry
component_registry.register(ResourceKind.HTTP, lambda config=None: HTTPResourceComponent(config))

__all__ = ["HTTPResourceComponent"]

