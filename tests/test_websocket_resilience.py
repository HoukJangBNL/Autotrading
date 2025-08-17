"""
Comprehensive integration tests for enhanced WebSocket client resilience features.

Tests include:
- State synchronization and recovery
- Message deduplication
- Health monitoring
- Reconnection with exponential backoff and jitter
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock, create_autospec
from typing import Dict, List, Any

import pytest
import websockets
from websockets.exceptions import ConnectionClosed

from src.data.websocket_client import (
    SchwabWebSocketClient,
    ConnectionState,
    create_websocket_client
)
from src.data.websocket_state import ConnectionStateManager, StateStorage, WebSocketState
from src.data.message_dedup import MessageDeduplicator
from src.data.websocket_health import WebSocketHealthMonitor, HealthStatus, AlertSeverity
from src.data.stream_processor import StreamProcessor, Tick, TickType


@pytest.fixture
async def stream_processor():
    """Create mock stream processor."""
    processor = AsyncMock(spec=StreamProcessor)
    processor.add_tick = AsyncMock()
    return processor


@pytest.fixture
async def mock_websocket():
    """Create mock WebSocket connection."""
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.recv = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def temp_state_dir(tmp_path):
    """Create temporary directory for state storage."""
    state_dir = tmp_path / "websocket_state"
    state_dir.mkdir()
    return state_dir


class TestStateManagement:
    """Test state synchronization and recovery features."""
    
    @pytest.mark.asyncio
    async def test_state_initialization_and_recovery(self, stream_processor, temp_state_dir):
        """Test state manager initialization and recovery."""
        connection_id = str(uuid.uuid4())
        account_id = "test_account"
        
        # Create state manager
        state_manager = ConnectionStateManager(
            connection_id=connection_id,
            account_id=account_id,
            storage_backend=StateStorage.FILE
        )
        # Override state directory after creation
        state_manager.state_dir = temp_state_dir
        state_manager.state_file = temp_state_dir / f"ws_state_{connection_id}.json"
        
        # Initialize and update state
        await state_manager.initialize()
        state_manager.update_subscriptions("QUOTE", {"AAPL", "GOOGL"})
        state_manager.update_message_id(100)
        state_manager.update_sequence_number("AAPL", 12345)
        
        # Checkpoint state
        await state_manager.checkpoint_state()
        await state_manager.shutdown()
        
        # Create new state manager and recover
        new_state_manager = ConnectionStateManager(
            connection_id=connection_id,
            account_id=account_id,
            storage_backend=StateStorage.FILE
        )
        # Override state directory after creation
        new_state_manager.state_dir = temp_state_dir
        new_state_manager.state_file = temp_state_dir / f"ws_state_{connection_id}.json"
        
        recovered = await new_state_manager.initialize()
        
        assert recovered is True
        assert new_state_manager.state.subscriptions["QUOTE"] == {"AAPL", "GOOGL"}
        assert new_state_manager.state.last_message_id == 100
        assert new_state_manager.state.last_sequence_numbers["AAPL"] == 12345
        
        await new_state_manager.shutdown()
    
    @pytest.mark.asyncio
    async def test_state_validation(self, temp_state_dir):
        """Test state validation for stale checkpoints."""
        connection_id = str(uuid.uuid4())
        
        # Create old state
        old_state = WebSocketState(
            connection_id=connection_id,
            account_id="test_account",
            checkpoint_time=datetime.now(timezone.utc) - timedelta(hours=2)
        )
        
        # Save old state
        state_file = temp_state_dir / f"ws_state_{connection_id}.json"
        state_file.write_text(json.dumps(old_state.to_dict(), default=str))
        
        # Try to recover
        state_manager = ConnectionStateManager(
            connection_id=connection_id,
            account_id="test_account",
            storage_backend=StateStorage.FILE
        )
        # Override state directory after creation
        state_manager.state_dir = temp_state_dir
        state_manager.state_file = temp_state_dir / f"ws_state_{connection_id}.json"
        
        recovered = await state_manager.initialize()
        
        # Should not recover stale state
        assert recovered is False
        assert state_manager.state.last_message_id == 0
        
        await state_manager.shutdown()
    
    @pytest.mark.asyncio
    async def test_websocket_state_recovery(self, stream_processor, mock_websocket, temp_state_dir):
        """Test WebSocket client state recovery after crash."""
        with patch('websockets.connect', return_value=mock_websocket):
            # First connection
            client1 = SchwabWebSocketClient(
                stream_processor=stream_processor,
                account_id="test_account",
                state_storage=StateStorage.FILE,
                connection_id="test_connection"
            )
            
            # Mock auth
            with patch.object(client1, '_get_streaming_params', new_callable=AsyncMock):
                with patch.object(client1, '_authenticate', new_callable=AsyncMock):
                    # Set custom state dir
                    client1.state_manager.state_dir = temp_state_dir
                    client1.state_manager.state_file = temp_state_dir / "ws_state_test_connection.json"
                    
                    await client1.connect()
                    
                    # Add subscriptions
                    await client1.subscribe(["AAPL", "GOOGL"], ["QUOTE"])
                    
                    # Checkpoint state
                    await client1.state_manager.checkpoint_state()
                    
                    await client1.disconnect()
            
            # Second connection - should recover state
            client2 = SchwabWebSocketClient(
                stream_processor=stream_processor,
                account_id="test_account",
                state_storage=StateStorage.FILE,
                connection_id="test_connection"
            )
            
            with patch.object(client2, '_get_streaming_params', new_callable=AsyncMock):
                with patch.object(client2, '_authenticate', new_callable=AsyncMock):
                    with patch.object(client2, '_resubscribe_all', new_callable=AsyncMock) as mock_resubscribe:
                        # Set custom state dir
                        client2.state_manager.state_dir = temp_state_dir
                        client2.state_manager.state_file = temp_state_dir / "ws_state_test_connection.json"
                        
                        await client2.connect()
                        
                        # Should have recovered subscriptions
                        assert "QUOTE" in client2.subscriptions
                        assert client2.subscriptions["QUOTE"] == {"AAPL", "GOOGL"}
                        mock_resubscribe.assert_called_once()
                        
                        await client2.disconnect()


class TestMessageDeduplication:
    """Test message deduplication features."""
    
    @pytest.mark.asyncio
    async def test_bloom_filter_basic(self):
        """Test basic Bloom filter functionality."""
        from src.data.message_dedup import BloomFilter
        
        bloom = BloomFilter(expected_items=1000, false_positive_rate=0.01)
        
        # Add items
        assert bloom.add("test1") is False  # First time
        assert bloom.add("test1") is True   # Duplicate
        assert bloom.add("test2") is False  # First time
        
        # Check contains
        assert bloom.contains("test1") is True
        assert bloom.contains("test2") is True
        assert bloom.contains("test3") is False
    
    @pytest.mark.asyncio
    async def test_message_deduplicator(self):
        """Test message deduplicator with rotation."""
        dedup = MessageDeduplicator(
            expected_messages_per_minute=100,
            false_positive_rate=0.01,
            retention_minutes=1,
            rotation_interval_minutes=0.1  # 6 seconds for testing
        )
        
        await dedup.start()
        
        # Test message deduplication
        message1 = {
            'service': 'QUOTE',
            'timestamp': 123456,
            'data': [{
                'content': [{'key': 'AAPL', '1': '150.00'}]
            }]
        }
        
        # First time should not be duplicate
        assert dedup.is_duplicate(message1) is False
        
        # Second time should be duplicate
        assert dedup.is_duplicate(message1) is True
        
        # Check statistics
        stats = dedup.get_statistics()
        assert stats['total_messages'] == 2
        assert stats['duplicates_detected'] == 1
        assert stats['duplicate_rate'] == 0.5
        
        await dedup.stop()
    
    @pytest.mark.asyncio
    async def test_websocket_deduplication(self, stream_processor, mock_websocket):
        """Test WebSocket client message deduplication."""
        client = SchwabWebSocketClient(
            stream_processor=stream_processor,
            account_id="test_account",
            enable_deduplication=True
        )
        
        # Mock duplicate message
        duplicate_message = json.dumps({
            'data': [{
                'service': 'TIMESALE',
                'content': [{
                    'key': 'AAPL',
                    '2': '150.00',  # price
                    '3': '100',     # size
                    '4': '12345'    # sequence
                }]
            }]
        })
        
        # Mock receiving same message twice
        # Use AsyncMock properly for recv method
        async def mock_recv_sequence():
            # First return the duplicate message twice
            for _ in range(2):
                yield duplicate_message
            # Then raise ConnectionClosed to end the loop
            raise ConnectionClosed(None, None)
        
        recv_gen = mock_recv_sequence()
        mock_websocket.recv = AsyncMock(side_effect=lambda: recv_gen.__anext__())
        
        with patch('websockets.connect', return_value=mock_websocket):
            with patch.object(client, '_get_streaming_params', return_value=None):
                with patch.object(client, '_authenticate', return_value=None):
                    await client.connect()
                    
                    # Wait for messages to be processed
                    await asyncio.sleep(0.1)
                    
                    # Should only process first message
                    stream_processor.add_tick.assert_called_once()
                    
                    # Check deduplication stats
                    stats = client.get_deduplication_stats()
                    assert stats['duplicates_detected'] > 0
                    
                    await client.disconnect()


class TestHealthMonitoring:
    """Test health monitoring features."""
    
    @pytest.mark.asyncio
    async def test_health_monitor_basic(self):
        """Test basic health monitoring functionality."""
        alerts_received = []
        
        def alert_callback(alert):
            alerts_received.append(alert)
        
        monitor = WebSocketHealthMonitor(
            connection_id="test",
            check_interval=0.1,  # 100ms for testing
            alert_callback=alert_callback
        )
        
        await monitor.start()
        
        # Record some metrics
        monitor.record_message()
        monitor.record_message()
        monitor.record_error()
        monitor.record_latency(100)
        monitor.record_latency(200)
        
        # Get health status
        health = await monitor.check_health()
        
        assert health.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
        assert health.message_rate_per_second >= 0
        assert health.error_rate > 0  # We recorded an error
        assert health.latency_ms == 150  # Average of 100 and 200
        
        # Simulate stale heartbeat
        monitor.last_heartbeat_time = datetime.now(timezone.utc) - timedelta(seconds=120)
        
        await asyncio.sleep(0.2)  # Wait for health check
        
        # Should have received alert
        assert len(alerts_received) > 0
        assert any(alert.metric_name == 'heartbeat_stale' for alert in alerts_received)
        
        await monitor.stop()
    
    @pytest.mark.asyncio
    async def test_websocket_health_integration(self, stream_processor, mock_websocket):
        """Test WebSocket client health monitoring integration."""
        client = SchwabWebSocketClient(
            stream_processor=stream_processor,
            account_id="test_account",
            enable_health_monitoring=True
        )
        
        with patch('websockets.connect', return_value=mock_websocket):
            with patch.object(client, '_get_streaming_params', return_value=None):
                with patch.object(client, '_authenticate', return_value=None):
                    await client.connect()
                    
                    # Get initial health status
                    health = await client.get_health_status()
                    assert health['status'] == HealthStatus.HEALTHY.value
                    assert health['uptime'] >= 0
                    assert health['connection_id'] == client.connection_id
                    
                    # Simulate some activity
                    message = json.dumps({
                        'data': [{
                            'service': 'QUOTE',
                            'content': [{'key': 'AAPL', '1': '150.00'}]
                        }]
                    })
                    
                    await client._handle_message(message)
                    
                    # Check updated health
                    health = await client.get_health_status()
                    assert health['message_rate'] > 0
                    
                    await client.disconnect()


class TestReconnectionResilience:
    """Test reconnection with exponential backoff and jitter."""
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_with_jitter(self, stream_processor):
        """Test reconnection delays with exponential backoff and jitter."""
        client = SchwabWebSocketClient(
            stream_processor=stream_processor,
            account_id="test_account"
        )
        
        # Track delays
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
            # Return a proper mock websocket
            ws = AsyncMock()
            ws.send = AsyncMock()
            ws.recv = AsyncMock()
            ws.close = AsyncMock()
            return ws
        
        with patch('asyncio.sleep', side_effect=mock_sleep):
            with patch('websockets.connect', side_effect=mock_connect):
                with patch.object(client, '_get_streaming_params', return_value=None):
                    with patch.object(client, '_authenticate', return_value=None):
                        # Trigger reconnection
                        client._running = True
                        await client._reconnect()
                        
                        # Check delays
                        assert len(delays) == 2  # 2 failed attempts
                        
                        # First delay should be around 1 second +/- jitter
                        assert 0.7 <= delays[0] <= 1.3
                        
                        # Second delay should be around 2 seconds +/- jitter
                        assert 1.4 <= delays[1] <= 2.6
                        
                        # Delays should be different due to jitter
                        assert delays[0] != delays[1]
    
    @pytest.mark.asyncio
    async def test_max_reconnection_attempts(self, stream_processor):
        """Test max reconnection attempts with health alert."""
        client = SchwabWebSocketClient(
            stream_processor=stream_processor,
            account_id="test_account",
            enable_health_monitoring=True
        )
        
        # Mock all connections to fail
        async def mock_connect(*args, **kwargs):
            raise Exception("Connection failed")
        
        # Track health alerts
        critical_alerts = []
        
        def mock_check_metric(key, value, warning, critical, message):
            if key == 'connection_failed':
                critical_alerts.append(message)
        
        with patch('websockets.connect', side_effect=mock_connect):
            with patch.object(client, '_get_streaming_params', return_value=None):
                with patch('asyncio.sleep', return_value=None):  # Speed up test
                    with patch.object(client.health_monitor, '_check_metric', side_effect=mock_check_metric):
                        client._running = True
                        await client._reconnect()
                        
                        # Should have reached max attempts
                        assert client.state == ConnectionState.ERROR
                        assert client._reconnect_attempts == client.RECONNECT_MAX_ATTEMPTS
                        
                        # Should have triggered critical alert
                        assert len(critical_alerts) > 0
                        assert "failed after" in critical_alerts[0]


class TestIntegrationScenarios:
    """Test complete integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_full_crash_recovery_scenario(self, stream_processor, mock_websocket, temp_state_dir):
        """Test complete crash and recovery scenario."""
        connection_id = "integration_test"
        account_id = "test_account"
        
        # Phase 1: Initial connection and activity
        client1 = SchwabWebSocketClient(
            stream_processor=stream_processor,
            account_id=account_id,
            connection_id=connection_id,
            state_storage=StateStorage.FILE
        )
        
        # Override state directory
        client1.state_manager.state_dir = temp_state_dir
        client1.state_manager.state_file = temp_state_dir / f"ws_state_{connection_id}.json"
        
        with patch('websockets.connect', return_value=mock_websocket):
            with patch.object(client1, '_get_streaming_params', return_value=None):
                with patch.object(client1, '_authenticate', return_value=None):
                    await client1.connect()
                    
                    # Subscribe to symbols
                    await client1.subscribe(["AAPL", "GOOGL", "MSFT"], ["QUOTE", "TRADE"])
                    
                    # Process some messages
                    for i in range(10):
                        message = json.dumps({
                            'data': [{
                                'service': 'TIMESALE',
                                'content': [{
                                    'key': 'AAPL',
                                    '2': f'{150 + i}',
                                    '3': '100',
                                    '4': str(1000 + i)  # sequence
                                }]
                            }]
                        })
                        await client1._handle_message(message)
                    
                    # Force checkpoint
                    await client1.state_manager.checkpoint_state()
                    
                    # Get final state
                    final_sequence = client1.state_manager.state.last_sequence_numbers.get("AAPL", 0)
                    
                    await client1.disconnect()
        
        # Phase 2: Recovery after crash
        client2 = SchwabWebSocketClient(
            stream_processor=stream_processor,
            account_id=account_id,
            connection_id=connection_id,
            state_storage=StateStorage.FILE
        )
        
        # Override state directory
        client2.state_manager.state_dir = temp_state_dir
        client2.state_manager.state_file = temp_state_dir / f"ws_state_{connection_id}.json"
        
        mock_resubscribe_called = False
        
        async def mock_resubscribe():
            nonlocal mock_resubscribe_called
            mock_resubscribe_called = True
        
        with patch('websockets.connect', return_value=mock_websocket):
            with patch.object(client2, '_get_streaming_params', return_value=None):
                with patch.object(client2, '_authenticate', return_value=None):
                    with patch.object(client2, '_resubscribe_all', side_effect=mock_resubscribe):
                        await client2.connect()
                        
                        # Should have recovered state
                        assert client2.subscriptions["QUOTE"] == {"AAPL", "GOOGL", "MSFT"}
                        assert client2.subscriptions["TRADE"] == {"AAPL", "GOOGL", "MSFT"}
                        assert mock_resubscribe_called
                        
                        # Should skip duplicate sequences
                        duplicate_message = json.dumps({
                            'data': [{
                                'service': 'TIMESALE',
                                'content': [{
                                    'key': 'AAPL',
                                    '2': '155',
                                    '3': '100',
                                    '4': str(final_sequence - 1)  # Old sequence
                                }]
                            }]
                        })
                        
                        # Reset mock
                        stream_processor.add_tick.reset_mock()
                        
                        await client2._handle_message(duplicate_message)
                        
                        # Should not process duplicate
                        stream_processor.add_tick.assert_not_called()
                        
                        # Get health status
                        health = await client2.get_health_status()
                        assert health is not None
                        assert health['status'] == HealthStatus.HEALTHY.value
                        
                        await client2.disconnect()
    
    @pytest.mark.asyncio
    async def test_performance_under_load(self, stream_processor):
        """Test performance with high message volume."""
        client = SchwabWebSocketClient(
            stream_processor=stream_processor,
            account_id="test_account",
            enable_deduplication=True,
            enable_health_monitoring=True
        )
        
        # Generate high volume of messages
        messages = []
        for i in range(1000):
            messages.append({
                'data': [{
                    'service': 'QUOTE',
                    'timestamp': 1234567890 + i,
                    'content': [{
                        'key': f'SYM{i % 10}',  # 10 different symbols
                        '1': f'{100 + (i % 100)}',  # Varying prices
                        '2': f'{100 + (i % 50)}',
                        '3': f'{100 + (i % 25)}'
                    }]
                }]
            })
        
        # Process messages
        start_time = time.time()
        
        for message in messages:
            is_dup = client.deduplicator.is_duplicate(message)
            if not is_dup:
                client.state_manager.record_message_received()
                if client.health_monitor:
                    client.health_monitor.record_message()
        
        elapsed_time = time.time() - start_time
        
        # Check performance
        assert elapsed_time < 1.0  # Should process 1000 messages in under 1 second
        
        # Check deduplication effectiveness
        stats = client.get_deduplication_stats()
        assert stats['total_messages'] == 1000
        assert stats['false_positive_rate'] < 0.01  # Should maintain low false positive rate
        
        # Check health metrics
        health = await client.get_health_status()
        assert health['message_rate'] > 0


@pytest.mark.asyncio
async def test_context_manager_with_features(stream_processor):
    """Test context manager with all features enabled."""
    # Mock the websocket connection before creating the client
    mock_ws = AsyncMock()
    mock_ws.send = AsyncMock()
    mock_ws.recv = AsyncMock()
    mock_ws.close = AsyncMock()
    
    with patch('websockets.connect', return_value=mock_ws):
        async with create_websocket_client(
            stream_processor,
            "test_account",
            enable_deduplication=True,
            enable_health_monitoring=True,
            state_storage=StateStorage.MEMORY
        ) as client:
            # Client should be created with correct settings
            assert client is not None
            assert client.enable_deduplication is True
            assert client.enable_health_monitoring is True
            assert client.state_manager.storage_backend == StateStorage.MEMORY