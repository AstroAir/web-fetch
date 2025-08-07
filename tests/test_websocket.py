"""
Comprehensive tests for the WebSocket module.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from web_fetch.websocket import (
    WebSocketClient,
    WebSocketConfig,
    WebSocketManager,
    WebSocketMessage,
    WebSocketMessageType,
    WebSocketConnectionState,
    WebSocketResult,
    WebSocketError,
)


class TestWebSocketConfig:
    """Test WebSocket configuration."""

    def test_websocket_config_defaults(self):
        """Test default WebSocket configuration."""
        config = WebSocketConfig(url="wss://example.com/ws")
        
        assert config.url == "wss://example.com/ws"
        assert config.connect_timeout == 10.0
        assert config.heartbeat_interval == 30.0
        assert config.max_reconnect_attempts == 5
        assert config.reconnect_delay == 1.0
        assert config.auto_reconnect is True

    def test_websocket_config_custom_values(self):
        """Test WebSocket configuration with custom values."""
        config = WebSocketConfig(
            url="wss://api.example.com/ws",
            connect_timeout=20.0,
            heartbeat_interval=60.0,
            max_reconnect_attempts=10,
            reconnect_delay=2.0,
            auto_reconnect=False,
            headers={"Authorization": "Bearer token123"}
        )
        
        assert config.url == "wss://api.example.com/ws"
        assert config.connect_timeout == 20.0
        assert config.heartbeat_interval == 60.0
        assert config.max_reconnect_attempts == 10
        assert config.reconnect_delay == 2.0
        assert config.auto_reconnect is False
        assert config.headers["Authorization"] == "Bearer token123"

    def test_websocket_config_validation(self):
        """Test WebSocket configuration validation."""
        # Valid config
        config = WebSocketConfig(url="wss://example.com/ws")
        assert config.url.startswith("wss://")
        
        # Test with ws:// URL
        config_ws = WebSocketConfig(url="ws://localhost:8080/ws")
        assert config_ws.url.startswith("ws://")


class TestWebSocketMessage:
    """Test WebSocket message model."""

    def test_text_message_creation(self):
        """Test creating text message."""
        message = WebSocketMessage(
            type=WebSocketMessageType.TEXT,
            data="Hello, WebSocket!"
        )
        
        assert message.type == WebSocketMessageType.TEXT
        assert message.data == "Hello, WebSocket!"
        assert message.timestamp is not None
        assert message.id is not None

    def test_binary_message_creation(self):
        """Test creating binary message."""
        binary_data = b"Binary content here"
        message = WebSocketMessage(
            type=WebSocketMessageType.BINARY,
            data=binary_data
        )
        
        assert message.type == WebSocketMessageType.BINARY
        assert message.data == binary_data

    def test_json_message_creation(self):
        """Test creating JSON message."""
        json_data = {"action": "subscribe", "channel": "updates"}
        message = WebSocketMessage(
            type=WebSocketMessageType.JSON,
            data=json_data
        )
        
        assert message.type == WebSocketMessageType.JSON
        assert message.data == json_data

    def test_message_serialization(self):
        """Test message serialization."""
        # Text message
        text_msg = WebSocketMessage(
            type=WebSocketMessageType.TEXT,
            data="Hello"
        )
        serialized = text_msg.serialize()
        assert serialized == "Hello"
        
        # JSON message
        json_msg = WebSocketMessage(
            type=WebSocketMessageType.JSON,
            data={"key": "value"}
        )
        serialized = json_msg.serialize()
        assert json.loads(serialized) == {"key": "value"}
        
        # Binary message
        binary_msg = WebSocketMessage(
            type=WebSocketMessageType.BINARY,
            data=b"binary data"
        )
        serialized = binary_msg.serialize()
        assert serialized == b"binary data"


class TestWebSocketClient:
    """Test WebSocket client."""

    def test_client_creation(self):
        """Test WebSocket client creation."""
        config = WebSocketConfig(url="wss://example.com/ws")
        client = WebSocketClient(config)
        
        assert client.config == config
        assert client.state == WebSocketConnectionState.DISCONNECTED
        assert client._websocket is None

    @pytest.mark.asyncio
    async def test_client_connect(self):
        """Test WebSocket client connection."""
        config = WebSocketConfig(url="wss://echo.websocket.org")
        client = WebSocketClient(config)
        
        with patch('websockets.connect') as mock_connect:
            mock_websocket = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_websocket
            
            result = await client.connect()
            
            assert result.success is True
            assert client.state == WebSocketConnectionState.CONNECTED
            assert client._websocket == mock_websocket

    @pytest.mark.asyncio
    async def test_client_connect_failure(self):
        """Test WebSocket client connection failure."""
        config = WebSocketConfig(url="wss://invalid-url.example.com/ws")
        client = WebSocketClient(config)
        
        with patch('websockets.connect') as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")
            
            result = await client.connect()
            
            assert result.success is False
            assert "Connection failed" in result.error
            assert client.state == WebSocketConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_client_send_text_message(self):
        """Test sending text message."""
        config = WebSocketConfig(url="wss://example.com/ws")
        client = WebSocketClient(config)
        
        # Mock connected state
        client.state = WebSocketConnectionState.CONNECTED
        client._websocket = AsyncMock()
        
        message = WebSocketMessage(
            type=WebSocketMessageType.TEXT,
            data="Hello, Server!"
        )
        
        result = await client.send_message(message)
        
        assert result.success is True
        client._websocket.send.assert_called_once_with("Hello, Server!")

    @pytest.mark.asyncio
    async def test_client_send_json_message(self):
        """Test sending JSON message."""
        config = WebSocketConfig(url="wss://example.com/ws")
        client = WebSocketClient(config)
        
        client.state = WebSocketConnectionState.CONNECTED
        client._websocket = AsyncMock()
        
        message = WebSocketMessage(
            type=WebSocketMessageType.JSON,
            data={"action": "ping", "timestamp": 1234567890}
        )
        
        result = await client.send_message(message)
        
        assert result.success is True
        # Should send JSON string
        expected_json = json.dumps({"action": "ping", "timestamp": 1234567890})
        client._websocket.send.assert_called_once_with(expected_json)

    @pytest.mark.asyncio
    async def test_client_send_binary_message(self):
        """Test sending binary message."""
        config = WebSocketConfig(url="wss://example.com/ws")
        client = WebSocketClient(config)
        
        client.state = WebSocketConnectionState.CONNECTED
        client._websocket = AsyncMock()
        
        binary_data = b"Binary message content"
        message = WebSocketMessage(
            type=WebSocketMessageType.BINARY,
            data=binary_data
        )
        
        result = await client.send_message(message)
        
        assert result.success is True
        client._websocket.send.assert_called_once_with(binary_data)

    @pytest.mark.asyncio
    async def test_client_send_message_not_connected(self):
        """Test sending message when not connected."""
        config = WebSocketConfig(url="wss://example.com/ws")
        client = WebSocketClient(config)
        
        # Client is not connected
        assert client.state == WebSocketConnectionState.DISCONNECTED
        
        message = WebSocketMessage(
            type=WebSocketMessageType.TEXT,
            data="Hello"
        )
        
        result = await client.send_message(message)
        
        assert result.success is False
        assert "not connected" in result.error.lower()

    @pytest.mark.asyncio
    async def test_client_receive_message(self):
        """Test receiving message."""
        config = WebSocketConfig(url="wss://example.com/ws")
        client = WebSocketClient(config)
        
        client.state = WebSocketConnectionState.CONNECTED
        client._websocket = AsyncMock()
        
        # Mock received message
        client._websocket.recv.return_value = "Hello from server"
        
        message = await client.receive_message()
        
        assert message is not None
        assert message.type == WebSocketMessageType.TEXT
        assert message.data == "Hello from server"

    @pytest.mark.asyncio
    async def test_client_receive_json_message(self):
        """Test receiving JSON message."""
        config = WebSocketConfig(url="wss://example.com/ws")
        client = WebSocketClient(config)
        
        client.state = WebSocketConnectionState.CONNECTED
        client._websocket = AsyncMock()
        
        # Mock received JSON message
        json_data = {"status": "ok", "data": [1, 2, 3]}
        client._websocket.recv.return_value = json.dumps(json_data)
        
        message = await client.receive_message()
        
        assert message is not None
        # Should auto-detect JSON and parse it
        if message.type == WebSocketMessageType.JSON:
            assert message.data == json_data
        else:
            # If not auto-detected, should still be text
            assert message.type == WebSocketMessageType.TEXT
            assert json.loads(message.data) == json_data

    @pytest.mark.asyncio
    async def test_client_disconnect(self):
        """Test WebSocket client disconnection."""
        config = WebSocketConfig(url="wss://example.com/ws")
        client = WebSocketClient(config)
        
        # Mock connected state
        client.state = WebSocketConnectionState.CONNECTED
        client._websocket = AsyncMock()
        
        await client.disconnect()
        
        assert client.state == WebSocketConnectionState.DISCONNECTED
        assert client._websocket is None

    @pytest.mark.asyncio
    async def test_client_heartbeat(self):
        """Test WebSocket heartbeat functionality."""
        config = WebSocketConfig(
            url="wss://example.com/ws",
            heartbeat_interval=0.1  # Fast heartbeat for testing
        )
        client = WebSocketClient(config)
        
        client.state = WebSocketConnectionState.CONNECTED
        client._websocket = AsyncMock()
        
        # Start heartbeat
        heartbeat_task = asyncio.create_task(client._heartbeat_loop())
        
        # Let it run for a short time
        await asyncio.sleep(0.2)
        
        # Cancel heartbeat
        heartbeat_task.cancel()
        
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        
        # Should have sent at least one ping
        assert client._websocket.ping.call_count >= 1

    @pytest.mark.asyncio
    async def test_client_auto_reconnect(self):
        """Test auto-reconnect functionality."""
        config = WebSocketConfig(
            url="wss://example.com/ws",
            auto_reconnect=True,
            max_reconnect_attempts=2,
            reconnect_delay=0.1
        )
        client = WebSocketClient(config)
        
        with patch('websockets.connect') as mock_connect:
            # First connection succeeds
            mock_websocket = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_websocket
            
            # Connect initially
            await client.connect()
            assert client.state == WebSocketConnectionState.CONNECTED
            
            # Simulate connection loss
            client.state = WebSocketConnectionState.DISCONNECTED
            client._websocket = None
            
            # Start reconnect process
            reconnect_task = asyncio.create_task(client._reconnect_loop())
            
            # Let it attempt reconnection
            await asyncio.sleep(0.3)
            
            # Cancel reconnect task
            reconnect_task.cancel()
            
            try:
                await reconnect_task
            except asyncio.CancelledError:
                pass
            
            # Should have attempted to reconnect
            assert mock_connect.call_count > 1


class TestWebSocketManager:
    """Test WebSocket manager."""

    def test_manager_creation(self):
        """Test WebSocket manager creation."""
        manager = WebSocketManager()
        
        assert len(manager._clients) == 0
        assert manager._running is False

    @pytest.mark.asyncio
    async def test_manager_add_client(self):
        """Test adding client to manager."""
        manager = WebSocketManager()
        
        config = WebSocketConfig(url="wss://example.com/ws")
        client_id = await manager.add_client("test-client", config)
        
        assert client_id == "test-client"
        assert "test-client" in manager._clients
        assert isinstance(manager._clients["test-client"], WebSocketClient)

    @pytest.mark.asyncio
    async def test_manager_remove_client(self):
        """Test removing client from manager."""
        manager = WebSocketManager()
        
        config = WebSocketConfig(url="wss://example.com/ws")
        await manager.add_client("test-client", config)
        
        assert "test-client" in manager._clients
        
        success = await manager.remove_client("test-client")
        
        assert success is True
        assert "test-client" not in manager._clients

    @pytest.mark.asyncio
    async def test_manager_connect_client(self):
        """Test connecting client through manager."""
        manager = WebSocketManager()
        
        config = WebSocketConfig(url="wss://example.com/ws")
        await manager.add_client("test-client", config)
        
        with patch.object(manager._clients["test-client"], 'connect') as mock_connect:
            mock_connect.return_value = WebSocketResult(success=True)
            
            result = await manager.connect_client("test-client")
            
            assert result.success is True
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_manager_send_message(self):
        """Test sending message through manager."""
        manager = WebSocketManager()
        
        config = WebSocketConfig(url="wss://example.com/ws")
        await manager.add_client("test-client", config)
        
        message = WebSocketMessage(
            type=WebSocketMessageType.TEXT,
            data="Hello from manager"
        )
        
        with patch.object(manager._clients["test-client"], 'send_message') as mock_send:
            mock_send.return_value = WebSocketResult(success=True)
            
            result = await manager.send_message("test-client", message)
            
            assert result.success is True
            mock_send.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_manager_broadcast_message(self):
        """Test broadcasting message to all clients."""
        manager = WebSocketManager()
        
        # Add multiple clients
        config1 = WebSocketConfig(url="wss://example1.com/ws")
        config2 = WebSocketConfig(url="wss://example2.com/ws")
        
        await manager.add_client("client1", config1)
        await manager.add_client("client2", config2)
        
        message = WebSocketMessage(
            type=WebSocketMessageType.TEXT,
            data="Broadcast message"
        )
        
        with patch.object(manager._clients["client1"], 'send_message') as mock_send1:
            with patch.object(manager._clients["client2"], 'send_message') as mock_send2:
                mock_send1.return_value = WebSocketResult(success=True)
                mock_send2.return_value = WebSocketResult(success=True)
                
                results = await manager.broadcast_message(message)
                
                assert len(results) == 2
                assert all(result.success for result in results.values())
                mock_send1.assert_called_once_with(message)
                mock_send2.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_manager_get_client_status(self):
        """Test getting client status."""
        manager = WebSocketManager()
        
        config = WebSocketConfig(url="wss://example.com/ws")
        await manager.add_client("test-client", config)
        
        status = await manager.get_client_status("test-client")
        
        assert status is not None
        assert "state" in status
        assert "url" in status
        assert status["url"] == "wss://example.com/ws"

    @pytest.mark.asyncio
    async def test_manager_get_all_clients_status(self):
        """Test getting all clients status."""
        manager = WebSocketManager()
        
        config1 = WebSocketConfig(url="wss://example1.com/ws")
        config2 = WebSocketConfig(url="wss://example2.com/ws")
        
        await manager.add_client("client1", config1)
        await manager.add_client("client2", config2)
        
        all_status = await manager.get_all_clients_status()
        
        assert len(all_status) == 2
        assert "client1" in all_status
        assert "client2" in all_status
        assert all_status["client1"]["url"] == "wss://example1.com/ws"
        assert all_status["client2"]["url"] == "wss://example2.com/ws"
