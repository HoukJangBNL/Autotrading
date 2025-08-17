"""
Fixed tests for WebSocket client with proper async mocking.
"""

import asyncio
import json
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock, create_autospec
from datetime import datetime, timezone
import websockets
from websockets.exceptions import ConnectionClosed

from src.data.websocket_client import (
    SchwabWebSocketClient,
    ConnectionState,
    MessageType
)
from src.data.stream_processor import StreamProcessor, Tick, TickType


class TestSchwabWebSocketClientFixed:
    """Fixed test suite for Schwab WebSocket client."""
    
    @pytest.fixture
    def mock_stream_processor(self):
        """Create mock stream processor."""
        processor = Mock(spec=StreamProcessor)
        processor.add_tick = AsyncMock()
        return processor
    
    @pytest.fixture
    def mock_auth_service(self):
        """Create mock auth service."""
        auth_service = Mock()
        auth_service.get_client = Mock()
        auth_service.initialize = AsyncMock()
        return auth_service
    
    @pytest.fixture
    async def client(self, mock_stream_processor, mock_auth_service):
        """Create WebSocket client instance."""
        # Disable state management components for simpler testing
        client = SchwabWebSocketClient(
            stream_processor=mock_stream_processor,
            account_id="TEST123456",
            auth_service=mock_auth_service,
            enable_deduplication=False,
            enable_health_monitoring=False
        )
        yield client
        # Cleanup
        if client.state != ConnectionState.DISCONNECTED:
            # Force state to disconnected without calling disconnect if there are issues
            client.state = ConnectionState.DISCONNECTED
            client._running = False
    
    @pytest.mark.asyncio
    async def test_connect_success_fixed(self, client, mock_auth_service):
        """Test successful WebSocket connection with proper mocking."""
        # Create a proper mock for websocket connection
        mock_ws = MagicMock()
        mock_ws.close = AsyncMock()
        mock_ws.send = AsyncMock()
        mock_ws.recv = AsyncMock()
        
        # Mock the websockets.connect to return a coroutine
        async def mock_connect(*args, **kwargs):
            return mock_ws
        
        # Mock auth service
        mock_client = Mock()
        mock_client.get_user_preferences = AsyncMock(return_value={
            'streamerInfo': [{
                'token': 'test_token',
                'appId': 'test_app',
                'streamerSocketUrl': 'wss://test.schwab.com/ws',
                'userGroup': 'ACCT',
                'accessLevel': '1',
                'acl': 'test_acl'
            }]
        })
        mock_auth_service.get_client.return_value = mock_client
        
        # Mock authentication to be successful
        async def mock_authenticate():
            client.state = ConnectionState.AUTHENTICATED
        
        # Mock background loops to prevent actual execution
        async def mock_loop():
            await asyncio.sleep(0.01)
        
        with patch('websockets.connect', side_effect=mock_connect):
            with patch.object(client, '_authenticate', side_effect=mock_authenticate):
                with patch.object(client, '_heartbeat_loop', side_effect=mock_loop):
                    with patch.object(client, '_receive_loop', side_effect=mock_loop):
                        success = await client.connect()
        
        assert success is True
        assert client.state == ConnectionState.AUTHENTICATED
        assert client.websocket is not None
        assert client._running is True
    
    @pytest.mark.asyncio
    async def test_disconnect_fixed(self, client):
        """Test graceful disconnection with proper task mocking."""
        # Setup connected client
        client._running = True
        
        # Create proper mock for websocket
        mock_ws = MagicMock()
        mock_ws.close = AsyncMock()
        client.websocket = mock_ws
        client.state = ConnectionState.AUTHENTICATED
        
        # Create real asyncio tasks that can be cancelled
        async def dummy_task():
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                pass
        
        # Create real tasks
        client._heartbeat_task = asyncio.create_task(dummy_task())
        client._receive_task = asyncio.create_task(dummy_task())
        client._reconnect_task = None  # Often None during normal operation
        
        # Mock the state manager shutdown
        client.state_manager.shutdown = AsyncMock()
        
        await client.disconnect()
        
        assert client._running is False
        assert client.state == ConnectionState.DISCONNECTED
        assert client.websocket is None  # Should be None after disconnect
        mock_ws.close.assert_called_once()
        
        # Verify tasks were cancelled or done
        assert client._heartbeat_task.done()
        assert client._receive_task.done()
    
    @pytest.mark.asyncio
    async def test_context_manager_fixed(self, mock_stream_processor, mock_auth_service):
        """Test using client as async context manager with proper setup."""
        # Create a proper mock for websocket
        mock_ws = MagicMock()
        mock_ws.close = AsyncMock()
        mock_ws.send = AsyncMock()
        mock_ws.recv = AsyncMock()
        
        async def mock_connect(*args, **kwargs):
            return mock_ws
        
        # Mock auth service response
        mock_client = Mock()
        mock_client.get_user_preferences = AsyncMock(return_value={
            'streamerInfo': [{
                'token': 'test_token',
                'appId': 'test_app',
                'streamerSocketUrl': 'wss://test.schwab.com/ws',
                'userGroup': 'ACCT',
                'accessLevel': '1',
                'acl': 'test_acl'
            }]
        })
        mock_auth_service.get_client.return_value = mock_client
        
        entered = False
        exited = False
        
        with patch('websockets.connect', side_effect=mock_connect):
            # Patch the class methods before creating instance
            with patch.object(SchwabWebSocketClient, '_authenticate', new=AsyncMock()):
                with patch.object(SchwabWebSocketClient, '_heartbeat_loop', new=AsyncMock()):
                    with patch.object(SchwabWebSocketClient, '_receive_loop', new=AsyncMock()):
                        async with SchwabWebSocketClient(
                            stream_processor=mock_stream_processor,
                            account_id="TEST123456",
                            auth_service=mock_auth_service,
                            enable_deduplication=False,
                            enable_health_monitoring=False
                        ) as client:
                            entered = True
                            # Should be connected inside context
                            assert client._running is True
                            assert client.websocket is not None
                        
                        exited = True
                        # After context exit, should be disconnected
                        assert client.state == ConnectionState.DISCONNECTED
                        assert client._running is False
        
        assert entered and exited, "Context manager did not enter and exit properly"
    
    @pytest.mark.asyncio
    async def test_reconnect_with_backoff_fixed(self):
        """Test reconnection with exponential backoff - fixed version."""
        # Create client with shorter retry settings for testing
        client = SchwabWebSocketClient(
            stream_processor=Mock(spec=StreamProcessor),
            account_id="TEST123456",
            enable_deduplication=False,
            enable_health_monitoring=False
        )
        
        # Override reconnect settings for faster testing
        client.RECONNECT_MAX_ATTEMPTS = 3
        client.RECONNECT_BASE_DELAY = 0.1
        client.RECONNECT_MAX_DELAY = 0.5
        
        # Track connection attempts
        connection_attempts = []
        connection_times = []
        
        async def mock_connect():
            connection_times.append(asyncio.get_event_loop().time())
            connection_attempts.append(1)
            # Always fail to trigger retries
            client.state = ConnectionState.ERROR
            return False
        
        with patch.object(client, 'connect', side_effect=mock_connect):
            # Start reconnection
            client._running = True
            await client._reconnect()
        
        # Should have made max attempts
        assert len(connection_attempts) == client.RECONNECT_MAX_ATTEMPTS
        
        # Verify exponential backoff timing - just check that delays are increasing
        if len(connection_times) > 1:
            previous_delay = 0
            for i in range(1, len(connection_times)):
                actual_delay = connection_times[i] - connection_times[i-1]
                
                # For first delay, just check it's positive
                if i == 1:
                    assert actual_delay > 0
                    assert actual_delay < 1.0  # Should be less than 1 second
                else:
                    # Later delays should be larger than previous (exponential backoff)
                    assert actual_delay > previous_delay
                
                previous_delay = actual_delay
        
        # Should end in error state after max attempts
        assert client.state == ConnectionState.ERROR