"""
Test WebSocket client resilience with simplified mock setup.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

import pytest

from src.data.websocket_client import (
    SchwabWebSocketClient,
    ConnectionState,
    create_websocket_client
)
from src.data.websocket_state import ConnectionStateManager, StateStorage, WebSocketState
from src.data.message_dedup import MessageDeduplicator
from src.data.websocket_health import WebSocketHealthMonitor, HealthStatus, AlertSeverity
from src.data.stream_processor import StreamProcessor, Tick, TickType


class FakeWebSocket:
    """Fake WebSocket for testing."""
    
    def __init__(self):
        self.sent_messages = []
        self.recv_messages = []
        self.closed = False
        self.recv_index = 0
        
    async def send(self, message):
        self.sent_messages.append(message)
        
    async def recv(self):
        if self.recv_index < len(self.recv_messages):
            msg = self.recv_messages[self.recv_index]
            self.recv_index += 1
            return msg
        # Wait indefinitely
        await asyncio.sleep(100)
        
    async def close(self):
        self.closed = True
        

async def fake_websocket_connect(url, **kwargs):
    """Fake websocket connect function."""
    return FakeWebSocket()


@pytest.fixture
async def stream_processor():
    """Create mock stream processor."""
    processor = AsyncMock(spec=StreamProcessor)
    processor.add_tick = AsyncMock()
    return processor


@pytest.fixture
def temp_state_dir(tmp_path):
    """Create temporary directory for state storage."""
    state_dir = tmp_path / "websocket_state"
    state_dir.mkdir()
    return state_dir


class TestStateRecovery:
    """Test state recovery functionality."""
    
    @pytest.mark.asyncio
    async def test_state_persistence_and_recovery(self, stream_processor, temp_state_dir):
        """Test state persistence and recovery after crash."""
        connection_id = "test_connection"
        
        # First connection
        with patch('websockets.connect', side_effect=fake_websocket_connect):
            client1 = SchwabWebSocketClient(
                stream_processor=stream_processor,
                account_id="test_account",
                state_storage=StateStorage.FILE,
                connection_id=connection_id
            )
            
            # Override state directory
            client1.state_manager.state_dir = temp_state_dir
            client1.state_manager.state_file = temp_state_dir / f"ws_state_{connection_id}.json"
            
            # Mock authentication
            client1._get_streaming_params = AsyncMock()
            client1._authenticate = AsyncMock()
            
            await client1.connect()
            
            # Add subscriptions
            await client1.subscribe(["AAPL", "GOOGL"], ["QUOTE"])
            
            # Force checkpoint
            await client1.state_manager.checkpoint_state()
            
            await client1.disconnect()
        
        # Second connection - should recover state
        with patch('websockets.connect', side_effect=fake_websocket_connect):
            client2 = SchwabWebSocketClient(
                stream_processor=stream_processor,
                account_id="test_account", 
                state_storage=StateStorage.FILE,
                connection_id=connection_id
            )
            
            # Override state directory
            client2.state_manager.state_dir = temp_state_dir
            client2.state_manager.state_file = temp_state_dir / f"ws_state_{connection_id}.json"
            
            # Mock authentication and resubscribe
            client2._get_streaming_params = AsyncMock()
            client2._authenticate = AsyncMock()
            client2._resubscribe_all = AsyncMock()
            
            await client2.connect()
            
            # Should have recovered subscriptions
            assert "QUOTE" in client2.subscriptions
            assert client2.subscriptions["QUOTE"] == {"AAPL", "GOOGL"}
            client2._resubscribe_all.assert_called_once()
            
            await client2.disconnect()


class TestMessageDeduplication:
    """Test message deduplication functionality."""
    
    @pytest.mark.asyncio  
    async def test_deduplication_prevents_duplicates(self, stream_processor):
        """Test that deduplication prevents duplicate messages."""
        with patch('websockets.connect', side_effect=fake_websocket_connect):
            client = SchwabWebSocketClient(
                stream_processor=stream_processor,
                account_id="test_account",
                enable_deduplication=True
            )
            
            # Mock authentication
            client._get_streaming_params = AsyncMock()
            client._authenticate = AsyncMock()
            
            await client.connect()
            
            # Create duplicate message
            duplicate_message = {
                'data': [{
                    'service': 'TIMESALE',
                    'timestamp': 1234567890,
                    'content': [{
                        'key': 'AAPL',
                        '2': '150.00',  # price
                        '3': '100',     # size  
                        '4': '12345'    # sequence
                    }]
                }]
            }
            
            # Process message twice
            await client._handle_message(json.dumps(duplicate_message))
            await client._handle_message(json.dumps(duplicate_message))
            
            # Should only process once
            stream_processor.add_tick.assert_called_once()
            
            # Check deduplication stats
            stats = client.get_deduplication_stats()
            assert stats['duplicates_detected'] > 0
            
            await client.disconnect()


class TestHealthMonitoring:
    """Test health monitoring functionality."""
    
    @pytest.mark.asyncio
    async def test_health_monitoring_tracks_metrics(self, stream_processor):
        """Test that health monitoring tracks connection metrics."""
        alerts = []
        
        with patch('websockets.connect', side_effect=fake_websocket_connect):
            client = SchwabWebSocketClient(
                stream_processor=stream_processor,
                account_id="test_account",
                enable_health_monitoring=True
            )
            
            # Capture alerts
            client._handle_health_alert = lambda alert: alerts.append(alert)
            
            # Mock authentication  
            client._get_streaming_params = AsyncMock()
            client._authenticate = AsyncMock()
            
            await client.connect()
            
            # Record some activity to get healthy status
            if client.health_monitor:
                client.health_monitor.record_heartbeat()
                # Record some messages to get above min threshold
                for _ in range(10):
                    client.health_monitor.record_message()
            
            # Wait a moment for rates to calculate
            await asyncio.sleep(0.1)
            
            # Get initial health
            health = await client.get_health_status()
            assert health['status'] in [HealthStatus.HEALTHY.value, HealthStatus.DEGRADED.value]
            assert health['uptime'] >= 0
            
            # Process a message
            message = json.dumps({
                'data': [{
                    'service': 'QUOTE',
                    'content': [{'key': 'AAPL', '1': '150.00'}]
                }]
            })
            await client._handle_message(message)
            
            # Check health after activity
            health = await client.get_health_status()
            assert health['message_rate'] > 0
            
            await client.disconnect()


class TestReconnection:
    """Test reconnection with exponential backoff."""
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self, stream_processor):
        """Test reconnection uses exponential backoff with jitter."""
        delays = []
        
        async def mock_sleep(delay):
            delays.append(delay)
            
        # Mock failed connections
        connect_attempts = 0
        
        async def mock_connect(*args, **kwargs):
            nonlocal connect_attempts
            connect_attempts += 1
            if connect_attempts < 3:
                raise Exception("Connection failed")
            return FakeWebSocket()
        
        with patch('asyncio.sleep', side_effect=mock_sleep):
            with patch('websockets.connect', side_effect=mock_connect):
                client = SchwabWebSocketClient(
                    stream_processor=stream_processor,
                    account_id="test_account"
                )
                
                # Mock authentication
                client._get_streaming_params = AsyncMock()
                client._authenticate = AsyncMock()
                
                # Initialize state manager
                await client.state_manager.initialize()
                
                # Start deduplicator and health monitor if enabled
                if client.deduplicator:
                    await client.deduplicator.start()
                if client.health_monitor:
                    await client.health_monitor.start()
                
                # Trigger reconnection
                client._running = True
                await client._reconnect()
                
                # Check delays
                assert len(delays) == 2  # 2 failed attempts
                
                # First delay ~1s +/- jitter
                assert 0.7 <= delays[0] <= 1.3
                
                # Second delay ~2s +/- jitter  
                assert 1.4 <= delays[1] <= 2.6
                
                # Delays should differ due to jitter
                assert delays[0] != delays[1]


@pytest.mark.asyncio
async def test_context_manager(stream_processor):
    """Test context manager functionality."""
    with patch('websockets.connect', side_effect=fake_websocket_connect):
        async with create_websocket_client(
            stream_processor,
            "test_account",
            enable_deduplication=True,
            enable_health_monitoring=True,
            state_storage=StateStorage.MEMORY
        ) as client:
            # Mock authentication inside context
            with patch.object(client, '_get_streaming_params', return_value=None):
                with patch.object(client, '_authenticate', return_value=None):
                    # Client should be properly configured
                    assert client is not None
                    assert client.enable_deduplication is True
                    assert client.enable_health_monitoring is True
                    assert client.state_manager.storage_backend == StateStorage.MEMORY