import pytest
from unittest.mock import AsyncMock

from web_fetch.components.manager import ResourceManager
from web_fetch.models.resource import ResourceKind, ResourceRequest


@pytest.mark.asyncio
async def test_websocket_component_adapter_minimal(monkeypatch):
    # Arrange: mock WebSocketClient to avoid real WS
    from web_fetch.websocket.client import WebSocketClient
    from web_fetch.websocket.models import WebSocketMessage, WebSocketMessageType, WebSocketResult, WebSocketConnectionState

    async def fake_aenter(self):
        return self

    async def fake_aexit(self, *args, **kwargs):
        return None

    async def fake_receive_message(timeout=None):
        return WebSocketMessage(type=WebSocketMessageType.TEXT, data="echo")

    monkeypatch.setattr(WebSocketClient, "__aenter__", fake_aenter)
    monkeypatch.setattr(WebSocketClient, "__aexit__", fake_aexit)
    monkeypatch.setattr(WebSocketClient, "receive_message", AsyncMock(side_effect=fake_receive_message))
    monkeypatch.setattr(WebSocketClient, "send_text", AsyncMock(return_value=None))

    manager = ResourceManager()
    req = ResourceRequest(
        uri="wss://example.com/socket",
        kind=ResourceKind.WEBSOCKET,
        options={"send_text": "hello", "receive_timeout": 0.01},
    )

    # Act
    res = await manager.fetch(req)

    # Assert
    assert res.is_success  # no error and no status_code -> success
    assert res.content == "echo"

