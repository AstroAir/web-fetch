"""
WebSocket resource component adapter bridging WebSocketClient to the unified API.

This is a minimal adapter to demonstrate unified component integration.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import HttpUrl, TypeAdapter

from ..websocket.client import WebSocketClient
from ..websocket.models import WebSocketConfig, WebSocketResult
from ..models.resource import ResourceConfig, ResourceKind, ResourceRequest, ResourceResult
from .base import ResourceComponent, component_registry


class WebSocketResourceComponent(ResourceComponent):
    kind = ResourceKind.WEBSOCKET

    def __init__(self, config: Optional[ResourceConfig] = None, ws_config: Optional[WebSocketConfig] = None):
        super().__init__(config)
        self.ws_config = ws_config

    def _to_ws_url(self, uri: str) -> HttpUrl:
        # HttpUrl in pydantic typically rejects ws/wss. We avoid strict validation here.
        # This method is retained for future normalization if models support ws/wss.
        adapter = TypeAdapter(HttpUrl)
        try:
            return adapter.validate_python(uri)
        except Exception:
            # Fallback: return as-is; component will use model_construct to bypass strict validation
            return uri  # type: ignore[return-value]

    async def fetch(self, request: ResourceRequest) -> ResourceResult:
        # Expect options: {"send_text": str} to send and echo back one message, then close
        if self.ws_config is not None:
            ws_config = self.ws_config
        else:
            # Bypass HttpUrl validation to allow ws/wss at this layer
            ws_config = WebSocketConfig.model_construct(url=str(request.uri))

        async with WebSocketClient(ws_config) as client:
            text = request.options.get("send_text")
            if text is not None:
                await client.send_text(str(text))
            # Try to receive a single message with small timeout if provided
            timeout = float(request.options.get("receive_timeout", 0.5))
            message = await client.receive_message(timeout=timeout)

        metadata: Dict[str, Any] = {}
        if message is not None:
            metadata["message_type"] = message.type.value
            metadata["message_size"] = message.size

        # Map to ResourceResult (status_code omitted for non-HTTP protocol)
        return ResourceResult(
            url=str(request.uri),
            headers={},
            content=(message.data if message else None),
            content_type=("text/plain" if message and isinstance(message.data, str) else None),
            metadata=metadata,
            response_time=getattr(client, "statistics", {}).get("total_connection_time", 0.0) if 'client' in locals() else 0.0,
            error=None,
        )


# Register component in the global registry
component_registry.register(ResourceKind.WEBSOCKET, lambda config=None: WebSocketResourceComponent(config))

__all__ = ["WebSocketResourceComponent"]

