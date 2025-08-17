"""
Tests for high-level streaming service orchestration.
"""

import asyncio
import json
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
import redis.asyncio as redis
from redis.exceptions import RedisError

from src.data.streaming_service import (
    StreamingService,
    StreamingStats,
    create_streaming_service
)
from src.data.websocket_client import SchwabWebSocketClient, ConnectionState
from src.data.stream_processor import StreamProcessor, Tick, TickType, OHLCV, VolumeProfile


class TestStreamingStats:
    """Test streaming statistics tracking."""
    
    def test_initial_stats(self):
        """Test initial statistics state."""
        stats = StreamingStats()
        
        assert stats.start_time is None
        assert stats.messages_received == 0
        assert stats.ticks_processed == 0
        assert stats.bars_created == 0
        assert stats.errors == 0
        assert stats.connection_attempts == 0
        assert len(stats.subscribed_symbols) == 0
    
    def test_uptime_calculation(self):
        """Test uptime calculation."""
        stats = StreamingStats()
        
        # No start time
        assert stats.uptime_seconds == 0.0
        
        # With start time
        stats.start_time = datetime.now(timezone.utc) - timedelta(seconds=60)
        assert 59 <= stats.uptime_seconds <= 61  # Allow small variance
    
    def test_rate_calculations(self):
        """Test message and tick rate calculations."""
        stats = StreamingStats()
        stats.start_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        stats.messages_received = 100
        stats.ticks_processed = 200
        
        assert 9.5 <= stats.messages_per_second <= 10.5
        assert 19 <= stats.ticks_per_second <= 21
    
    def test_to_dict(self):
        """Test converting stats to dictionary."""
        stats = StreamingStats()
        stats.start_time = datetime.now(timezone.utc)
        stats.messages_received = 100
        stats.subscribed_symbols = {"AAPL", "GOOGL"}
        
        data = stats.to_dict()
        
        assert data['messages_received'] == 100
        assert data['symbol_count'] == 2
        assert 'AAPL' in data['subscribed_symbols']
        assert 'uptime_seconds' in data
        assert 'messages_per_second' in data


class TestStreamingService:
    """Test suite for streaming service."""
    
    @pytest.fixture
    def mock_stream_processor(self):
        """Create mock stream processor."""
        processor = Mock(spec=StreamProcessor)
        processor._running = True
        processor.stats = {
            'ticks_processed': 100,
            'bars_created': 50,
            'errors': 0
        }
        processor.health_monitors = {}
        processor.get_recent_ticks = Mock(return_value=[])
        processor.get_recent_bars = Mock(return_value=[])
        processor.get_volume_profile = Mock(return_value=None)
        processor.on_tick = Mock()
        processor.on_bar = Mock()
        processor.stop = AsyncMock()
        return processor
    
    @pytest.fixture
    def mock_websocket_client(self):
        """Create mock WebSocket client."""
        client = Mock(spec=SchwabWebSocketClient)
        client.state = ConnectionState.DISCONNECTED
        client._reconnect_attempts = 0
        client.connect = AsyncMock(return_value=True)
        client.disconnect = AsyncMock()
        client.subscribe = AsyncMock()
        client.unsubscribe = AsyncMock()
        client._handle_message = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_redis_client(self):
        """Create mock Redis client."""
        client = Mock(spec=redis.Redis)
        client.ping = AsyncMock()
        client.publish = AsyncMock()
        return client
    
    @pytest.fixture
    async def service(self):
        """Create streaming service instance."""
        service = StreamingService(
            account_id="TEST123456",
            redis_url=None,
            save_to_db=False,
            timeframes=[1, 5]
        )
        yield service
        # Cleanup
        if service._running:
            await service.stop_streaming()
    
    @pytest.mark.asyncio
    async def test_initialization(self, service, mock_stream_processor, mock_websocket_client):
        """Test service initialization."""
        with patch('src.data.streaming_service.create_stream_processor', return_value=mock_stream_processor):
            with patch('src.data.streaming_service.SchwabWebSocketClient', return_value=mock_websocket_client):
                await service.initialize()
        
        assert service._initialized is True
        assert service.stream_processor is not None
        assert service.websocket_client is not None
        
        # Check callbacks were registered
        mock_stream_processor.on_tick.assert_called_once()
        mock_stream_processor.on_bar.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_streaming(self, service, mock_stream_processor, mock_websocket_client):
        """Test starting streaming."""
        symbols = ["AAPL", "GOOGL"]
        
        with patch('src.data.streaming_service.create_stream_processor', return_value=mock_stream_processor):
            with patch('src.data.streaming_service.SchwabWebSocketClient', return_value=mock_websocket_client):
                await service.start_streaming(symbols)
        
        assert service._running is True
        assert service.stats.start_time is not None
        assert service.stats.connection_attempts == 1
        assert service.stats.successful_connections == 1
        assert service.stats.subscribed_symbols == {"AAPL", "GOOGL"}
        
        # Check WebSocket operations
        mock_websocket_client.connect.assert_called_once()
        mock_websocket_client.subscribe.assert_called_once_with(symbols, None)
    
    @pytest.mark.asyncio
    async def test_start_streaming_already_running(self, service, mock_stream_processor, mock_websocket_client):
        """Test starting streaming when already running."""
        service._running = True
        service._initialized = True
        service.websocket_client = mock_websocket_client
        
        await service.start_streaming(["MSFT"])
        
        # Should just add symbols, not reconnect
        mock_websocket_client.connect.assert_not_called()
        mock_websocket_client.subscribe.assert_called_once_with(["MSFT"], None)
    
    @pytest.mark.asyncio
    async def test_start_streaming_connection_failure(self, service, mock_stream_processor, mock_websocket_client):
        """Test handling connection failure."""
        mock_websocket_client.connect.return_value = False
        
        with patch('src.data.streaming_service.create_stream_processor', return_value=mock_stream_processor):
            with patch('src.data.streaming_service.SchwabWebSocketClient', return_value=mock_websocket_client):
                with pytest.raises(RuntimeError, match="Failed to establish WebSocket connection"):
                    await service.start_streaming(["AAPL"])
        
        assert service._running is False
        assert service.stats.errors == 1
    
    @pytest.mark.asyncio
    async def test_stop_streaming(self, service, mock_stream_processor, mock_websocket_client):
        """Test stopping streaming service."""
        # Start service first
        with patch('src.data.streaming_service.create_stream_processor', return_value=mock_stream_processor):
            with patch('src.data.streaming_service.SchwabWebSocketClient', return_value=mock_websocket_client):
                await service.start_streaming(["AAPL"])
        
        # Stop service
        await service.stop_streaming()
        
        assert service._running is False
        mock_websocket_client.disconnect.assert_called_once()
        mock_stream_processor.stop.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_add_symbols(self, service, mock_stream_processor, mock_websocket_client):
        """Test adding symbols to existing stream."""
        # Setup running service
        service._running = True
        service._initialized = True
        service.websocket_client = mock_websocket_client
        service.stats.subscribed_symbols = {"AAPL"}
        
        await service.add_symbols(["GOOGL", "MSFT"])
        
        assert service.stats.subscribed_symbols == {"AAPL", "GOOGL", "MSFT"}
        mock_websocket_client.subscribe.assert_called_once_with(["GOOGL", "MSFT"], None)
    
    @pytest.mark.asyncio
    async def test_remove_symbols(self, service, mock_stream_processor, mock_websocket_client):
        """Test removing symbols from stream."""
        # Setup running service
        service._running = True
        service._initialized = True
        service.websocket_client = mock_websocket_client
        service.stats.subscribed_symbols = {"AAPL", "GOOGL", "MSFT"}
        service.stats.active_symbols = {"AAPL", "GOOGL"}
        
        await service.remove_symbols(["AAPL", "GOOGL"])
        
        assert service.stats.subscribed_symbols == {"MSFT"}
        assert service.stats.active_symbols == set()
        mock_websocket_client.unsubscribe.assert_called_once_with(["AAPL", "GOOGL"], None)
    
    def test_get_statistics(self, service, mock_stream_processor):
        """Test getting comprehensive statistics."""
        service.stream_processor = mock_stream_processor
        service.stats.messages_received = 1000
        service.stats.ticks_processed = 2000
        
        stats = service.get_statistics()
        
        assert stats['messages_received'] == 1000
        assert stats['ticks_processed'] == 2000
        assert 'stream_processor' in stats
        assert 'health' in stats
    
    def test_get_health_status(self, service, mock_stream_processor, mock_websocket_client):
        """Test getting health status."""
        # Setup service components
        service._running = True
        service.websocket_client = mock_websocket_client
        service.stream_processor = mock_stream_processor
        
        # Mock health monitor
        from src.data.stream_processor import StreamHealth, StreamStatus
        health_monitor = StreamHealth()
        health_monitor.status = StreamStatus.HEALTHY
        health_monitor.ticks_received = 100
        health_monitor.avg_latency_ms = 10.5
        mock_stream_processor.health_monitors = {"AAPL": health_monitor}
        
        health = service.get_health_status()
        
        assert health['streaming_service'] == 'running'
        assert health['websocket']['connected'] is False  # Based on mock state
        assert health['stream_processor']['running'] is True
        assert health['symbols']['AAPL']['status'] == 'HEALTHY'
        assert health['symbols']['AAPL']['ticks_received'] == 100
    
    def test_get_recent_ticks(self, service, mock_stream_processor):
        """Test getting recent ticks."""
        service.stream_processor = mock_stream_processor
        
        # Create mock ticks
        tick1 = Mock(symbol="AAPL", price=150.50)
        tick2 = Mock(symbol="AAPL", price=150.52)
        mock_stream_processor.get_recent_ticks.return_value = [tick1, tick2]
        
        ticks = service.get_recent_ticks("AAPL", limit=2)
        
        assert len(ticks) == 2
        assert ticks[0].price == 150.50
        mock_stream_processor.get_recent_ticks.assert_called_with("AAPL", 2)
    
    def test_get_recent_bars(self, service, mock_stream_processor):
        """Test getting recent bars."""
        service.stream_processor = mock_stream_processor
        
        # Create mock bars
        bar1 = Mock(symbol="AAPL", close=150.50)
        bar2 = Mock(symbol="AAPL", close=150.75)
        mock_stream_processor.get_recent_bars.return_value = [bar1, bar2]
        
        bars = service.get_recent_bars("AAPL", timeframe=5, limit=2)
        
        assert len(bars) == 2
        assert bars[1].close == 150.75
        mock_stream_processor.get_recent_bars.assert_called_with("AAPL", 5, 2)
    
    def test_get_volume_profile(self, service, mock_stream_processor):
        """Test getting volume profile."""
        service.stream_processor = mock_stream_processor
        
        # Create mock volume profile
        profile = Mock(spec=VolumeProfile)
        profile.symbol = "AAPL"
        profile.poc = 150.50
        profile.val = 150.00
        profile.vah = 151.00
        profile.total_volume = 100000
        profile.price_levels = {150.00: 10000, 150.50: 50000, 151.00: 40000}
        
        mock_stream_processor.get_volume_profile.return_value = profile
        
        result = service.get_volume_profile("AAPL")
        
        assert result['symbol'] == "AAPL"
        assert result['poc'] == 150.50
        assert result['val'] == 150.00
        assert result['vah'] == 151.00
        assert result['total_volume'] == 100000
        assert 150.50 in result['price_levels']
    
    @pytest.mark.asyncio
    async def test_message_handler_wrapper(self, service, mock_stream_processor):
        """Test message handler wrapper functionality."""
        service.stream_processor = mock_stream_processor
        
        # Create original handler
        original_handler = AsyncMock()
        
        # Create wrapped handler
        wrapped = service._wrap_message_handler(original_handler)
        
        # Test with data message
        message = json.dumps({
            "data": [{
                "service": "QUOTE",
                "timestamp": 1640995200000,
                "content": [{
                    "key": "AAPL",
                    "1": 150.50,
                    "2": 150.55
                }]
            }]
        })
        
        await wrapped(message)
        
        # Should update stats
        assert service.stats.messages_received == 1
        assert service.stats.last_message_time is not None
        assert "AAPL" in service.stats.active_symbols
        
        # Should call original handler
        original_handler.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_monitor_health(self, service, mock_websocket_client):
        """Test health monitoring loop."""
        service._running = True
        service.websocket_client = mock_websocket_client
        mock_websocket_client.state = ConnectionState.ERROR
        
        # Mock callback
        health_callback = AsyncMock()
        service.on_error(health_callback)
        
        # Run monitor briefly
        monitor_task = asyncio.create_task(service._monitor_health())
        await asyncio.sleep(0.1)
        service._running = False
        
        try:
            await asyncio.wait_for(monitor_task, timeout=1.0)
        except asyncio.TimeoutError:
            monitor_task.cancel()
        
        # Should have detected error state
        health_callback.assert_called()
        error = health_callback.call_args[0][0]
        assert isinstance(error, RuntimeError)
        assert "WebSocket connection error" in str(error)
    
    @pytest.mark.asyncio
    async def test_notify_callbacks(self, service):
        """Test callback notification system."""
        # Test connection callbacks
        sync_callback = Mock()
        async_callback = AsyncMock()
        
        service.on_connection_change(sync_callback)
        service.on_connection_change(async_callback)
        
        await service._notify_connection_callbacks(True)
        
        sync_callback.assert_called_once_with(True)
        async_callback.assert_called_once_with(True)
        
        # Test error callbacks
        error = Exception("Test error")
        error_callback = AsyncMock()
        service.on_error(error_callback)
        
        await service._notify_error_callbacks(error)
        
        error_callback.assert_called_once_with(error)
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test using service as async context manager."""
        with patch('src.data.streaming_service.create_stream_processor'):
            with patch('src.data.streaming_service.SchwabWebSocketClient'):
                async with StreamingService("TEST123456") as service:
                    assert service._initialized is True
        
        # After exit, should be stopped
        assert service._running is False
    
    @pytest.mark.asyncio
    async def test_create_streaming_service(self, mock_stream_processor):
        """Test utility function for creating service."""
        with patch('src.data.streaming_service.create_stream_processor', return_value=mock_stream_processor):
            with patch('src.data.streaming_service.SchwabWebSocketClient'):
                service = await create_streaming_service(
                    account_id="TEST123456",
                    symbols=["AAPL", "GOOGL"],
                    redis_url=None,
                    save_to_db=False,
                    timeframes=[1, 5]
                )
        
        assert service._running is True
        assert service.stats.subscribed_symbols == {"AAPL", "GOOGL"}
        
        # Cleanup
        await service.stop_streaming()
    
    @pytest.mark.asyncio
    async def test_stale_data_detection(self, service):
        """Test detection of stale data."""
        service._running = True
        service.stats.last_message_time = datetime.now(timezone.utc) - timedelta(seconds=90)
        
        # Mock error callback
        error_callback = Mock()
        service.on_error(error_callback)
        
        # Run monitor briefly
        monitor_task = asyncio.create_task(service._monitor_health())
        await asyncio.sleep(0.1)
        service._running = False
        
        try:
            await asyncio.wait_for(monitor_task, timeout=1.0)
        except asyncio.TimeoutError:
            monitor_task.cancel()
        
        # Should have logged warning about stale data
        # (Would need to check logs in actual implementation)
    
    @pytest.mark.asyncio
    async def test_on_tick_processed(self, service):
        """Test tick processed callback."""
        tick = Mock(symbol="AAPL", price=150.50)
        
        await service._on_tick_processed(tick)
        
        assert service.stats.ticks_processed == 1
    
    @pytest.mark.asyncio
    async def test_on_bar_created(self, service):
        """Test bar created callback."""
        bar = Mock(symbol="AAPL", close=150.75)
        
        await service._on_bar_created(bar)
        
        assert service.stats.bars_created == 1
    
    @pytest.mark.asyncio
    async def test_error_handling_in_callbacks(self, service):
        """Test error handling in callback execution."""
        # Create callback that raises exception
        bad_callback = Mock(side_effect=Exception("Callback error"))
        service.on_connection_change(bad_callback)
        
        # Should not raise exception
        await service._notify_connection_callbacks(True)
        
        # Callback was attempted
        bad_callback.assert_called_once()