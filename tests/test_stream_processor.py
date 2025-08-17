"""
Comprehensive tests for the stream processor module.
"""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from collections import deque

import pytest
import redis.asyncio as redis
from redis.exceptions import RedisError

from src.data.stream_processor import (
    Tick, TickType, OHLCV, VolumeProfile, StreamHealth, StreamStatus,
    BarAggregator, StreamProcessor, create_stream_processor,
    calculate_vwap, detect_tick_gaps
)
from src.data.models import PriceData


class TestTick:
    """Test the Tick data model."""
    
    def test_tick_creation(self):
        """Test basic tick creation."""
        now = datetime.now(timezone.utc)
        tick = Tick(
            symbol="AAPL",
            price=150.25,
            volume=100,
            timestamp=now,
            tick_type=TickType.TRADE
        )
        
        assert tick.symbol == "AAPL"
        assert tick.price == 150.25
        assert tick.volume == 100
        assert tick.timestamp == now
        assert tick.tick_type == TickType.TRADE
    
    def test_tick_validation(self):
        """Test tick validation."""
        now = datetime.now(timezone.utc)
        
        # Invalid price
        with pytest.raises(ValueError, match="Invalid price"):
            Tick(symbol="AAPL", price=-10, volume=100, timestamp=now)
        
        # Invalid volume
        with pytest.raises(ValueError, match="Invalid volume"):
            Tick(symbol="AAPL", price=150, volume=-5, timestamp=now)
    
    def test_tick_timezone_handling(self):
        """Test timezone handling for tick timestamps."""
        # Naive timestamp should be converted to UTC
        naive_time = datetime.now()
        tick = Tick(
            symbol="AAPL",
            price=150.25,
            volume=100,
            timestamp=naive_time
        )
        
        assert tick.timestamp.tzinfo == timezone.utc
    
    def test_tick_serialization(self):
        """Test tick to/from dictionary conversion."""
        now = datetime.now(timezone.utc)
        tick = Tick(
            symbol="AAPL",
            price=150.25,
            volume=100,
            timestamp=now,
            tick_type=TickType.BID,
            bid_price=150.20,
            ask_price=150.30,
            sequence_id=12345
        )
        
        # Convert to dict
        data = tick.to_dict()
        assert data['symbol'] == "AAPL"
        assert data['price'] == 150.25
        assert data['tick_type'] == "BID"
        assert data['sequence_id'] == 12345
        
        # Convert back from dict
        tick2 = Tick.from_dict(data)
        assert tick2.symbol == tick.symbol
        assert tick2.price == tick.price
        assert tick2.tick_type == tick.tick_type
        assert tick2.sequence_id == tick.sequence_id


class TestOHLCV:
    """Test the OHLCV bar model."""
    
    def test_ohlcv_creation(self):
        """Test OHLCV bar creation."""
        now = datetime.now(timezone.utc)
        bar = OHLCV(
            symbol="AAPL",
            open=150.00,
            high=151.00,
            low=149.50,
            close=150.75,
            volume=10000,
            timestamp=now,
            timeframe=1,
            vwap=150.60,
            trade_count=50
        )
        
        assert bar.symbol == "AAPL"
        assert bar.open == 150.00
        assert bar.high == 151.00
        assert bar.low == 149.50
        assert bar.close == 150.75
        assert bar.volume == 10000
        assert bar.vwap == 150.60
    
    def test_ohlcv_properties(self):
        """Test OHLCV calculated properties."""
        bar = OHLCV(
            symbol="AAPL",
            open=150.00,
            high=152.00,
            low=149.00,
            close=151.50,
            volume=10000,
            timestamp=datetime.now(timezone.utc),
            timeframe=1
        )
        
        assert bar.is_bullish is True  # close > open
        assert bar.range == 3.00  # high - low
        assert bar.body == 1.50  # abs(close - open)
    
    def test_ohlcv_to_price_data(self):
        """Test conversion to PriceData model."""
        now = datetime.now(timezone.utc)
        bar = OHLCV(
            symbol="AAPL",
            open=150.00,
            high=151.00,
            low=149.50,
            close=150.75,
            volume=10000,
            timestamp=now,
            timeframe=1,
            vwap=150.60
        )
        
        price_data = bar.to_price_data()
        assert isinstance(price_data, PriceData)
        assert price_data.symbol == "AAPL"
        assert price_data.open == Decimal("150.00")
        assert price_data.high == Decimal("151.00")
        assert price_data.low == Decimal("149.50")
        assert price_data.close == Decimal("150.75")
        assert price_data.volume == 10000
        assert price_data.vwap == Decimal("150.60")


class TestVolumeProfile:
    """Test the VolumeProfile functionality."""
    
    def test_volume_profile_creation(self):
        """Test volume profile initialization."""
        now = datetime.now(timezone.utc)
        profile = VolumeProfile(
            symbol="AAPL",
            start_time=now
        )
        
        assert profile.symbol == "AAPL"
        assert profile.start_time == now
        assert len(profile.price_levels) == 0
        assert profile.total_volume == 0
    
    def test_add_ticks_to_profile(self):
        """Test adding ticks to volume profile."""
        profile = VolumeProfile(
            symbol="AAPL",
            start_time=datetime.now(timezone.utc)
        )
        
        # Add ticks at different price levels
        ticks = [
            Tick("AAPL", 150.25, 100, datetime.now(timezone.utc)),
            Tick("AAPL", 150.25, 200, datetime.now(timezone.utc)),
            Tick("AAPL", 150.30, 150, datetime.now(timezone.utc)),
            Tick("AAPL", 150.20, 300, datetime.now(timezone.utc)),
            Tick("AAPL", 150.25, 50, datetime.now(timezone.utc)),
        ]
        
        for tick in ticks:
            profile.add_tick(tick)
        
        assert profile.total_volume == 800
        assert profile.price_levels[150.25] == 350  # 100 + 200 + 50
        assert profile.price_levels[150.30] == 150
        assert profile.price_levels[150.20] == 300
    
    def test_point_of_control(self):
        """Test POC calculation."""
        profile = VolumeProfile(
            symbol="AAPL",
            start_time=datetime.now(timezone.utc)
        )
        
        # Add ticks with 150.25 having the most volume
        profile.add_tick(Tick("AAPL", 150.20, 100, datetime.now(timezone.utc)))
        profile.add_tick(Tick("AAPL", 150.25, 500, datetime.now(timezone.utc)))  # POC
        profile.add_tick(Tick("AAPL", 150.30, 200, datetime.now(timezone.utc)))
        
        assert profile.poc == 150.25
    
    def test_value_area_calculation(self):
        """Test Value Area calculation."""
        profile = VolumeProfile(
            symbol="AAPL",
            start_time=datetime.now(timezone.utc)
        )
        
        # Add ticks across price range
        ticks = [
            (150.10, 50),
            (150.15, 100),
            (150.20, 200),
            (150.25, 300),  # POC
            (150.30, 150),
            (150.35, 100),
            (150.40, 50),
        ]
        
        for price, volume in ticks:
            profile.add_tick(Tick("AAPL", price, volume, datetime.now(timezone.utc)))
        
        # Total volume = 950, 70% = 665
        # Should include: 150.25 (300), 150.20 (200), 150.30 (150) = 650
        # Plus 150.15 (100) = 750 > 665
        val, vah = profile.calculate_value_area(0.70)
        
        assert val == 150.15  # Lowest price in value area
        assert vah == 150.30  # Highest price in value area


class TestStreamHealth:
    """Test stream health monitoring."""
    
    def test_health_initialization(self):
        """Test health monitor initialization."""
        health = StreamHealth()
        
        assert health.status == StreamStatus.DISCONNECTED
        assert health.ticks_received == 0
        assert health.error_count == 0
        assert health.is_healthy is False
    
    def test_tick_update(self):
        """Test updating health with ticks."""
        health = StreamHealth()
        health.status = StreamStatus.CONNECTED
        
        # Add a tick
        tick = Tick(
            symbol="AAPL",
            price=150.25,
            volume=100,
            timestamp=datetime.now(timezone.utc) - timedelta(milliseconds=50)
        )
        
        health.update_tick(tick)
        
        assert health.ticks_received == 1
        assert health.last_tick is not None
        assert len(health.latency_samples) == 1
        assert health.avg_latency_ms > 0
    
    def test_error_recording(self):
        """Test error recording and status degradation."""
        health = StreamHealth()
        health.status = StreamStatus.CONNECTED
        
        # Record errors
        for i in range(6):
            health.record_error(f"Error {i}")
        
        assert health.error_count == 6
        assert health.status == StreamStatus.DEGRADED
        
        # More errors should set ERROR status
        for i in range(5):
            health.record_error(f"Error {i+6}")
        
        assert health.error_count == 11
        assert health.status == StreamStatus.ERROR
    
    def test_health_check(self):
        """Test health status checking."""
        health = StreamHealth()
        
        # Not healthy when disconnected
        assert health.is_healthy is False
        
        # Healthy when connected with recent data
        health.status = StreamStatus.CONNECTED
        health.last_tick = datetime.now(timezone.utc)
        health.error_count = 0
        assert health.is_healthy is True
        
        # Not healthy with stale data
        health.last_tick = datetime.now(timezone.utc) - timedelta(seconds=60)
        assert health.is_healthy is False
        
        # Not healthy with too many errors
        health.last_tick = datetime.now(timezone.utc)
        health.error_count = 10
        assert health.is_healthy is False


class TestBarAggregator:
    """Test the BarAggregator functionality."""
    
    @pytest.mark.asyncio
    async def test_bar_timestamp_calculation(self):
        """Test bar timestamp calculation."""
        aggregator = BarAggregator(timeframe=5)  # 5-minute bars
        
        # Test various times
        test_cases = [
            (datetime(2024, 1, 1, 10, 3, 45), datetime(2024, 1, 1, 10, 0, 0)),
            (datetime(2024, 1, 1, 10, 7, 30), datetime(2024, 1, 1, 10, 5, 0)),
            (datetime(2024, 1, 1, 10, 14, 59), datetime(2024, 1, 1, 10, 10, 0)),
            (datetime(2024, 1, 1, 10, 15, 0), datetime(2024, 1, 1, 10, 15, 0)),
        ]
        
        for tick_time, expected_bar_time in test_cases:
            tick_time = tick_time.replace(tzinfo=timezone.utc)
            expected_bar_time = expected_bar_time.replace(tzinfo=timezone.utc)
            
            bar_time = aggregator.get_bar_timestamp(tick_time)
            assert bar_time == expected_bar_time
    
    @pytest.mark.asyncio
    async def test_single_bar_aggregation(self):
        """Test aggregating ticks into a single bar."""
        aggregator = BarAggregator(timeframe=1)
        
        base_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        
        # Add ticks within the same minute
        ticks = [
            Tick("AAPL", 150.00, 100, base_time + timedelta(seconds=10)),
            Tick("AAPL", 150.50, 200, base_time + timedelta(seconds=20)),
            Tick("AAPL", 149.75, 150, base_time + timedelta(seconds=30)),
            Tick("AAPL", 150.25, 100, base_time + timedelta(seconds=40)),
        ]
        
        for tick in ticks:
            completed_bar = await aggregator.add_tick(tick)
            assert completed_bar is None  # No bar completed yet
        
        # Add tick from next minute to complete the bar
        next_tick = Tick("AAPL", 151.00, 50, base_time + timedelta(minutes=1, seconds=5))
        completed_bar = await aggregator.add_tick(next_tick)
        
        assert completed_bar is not None
        assert completed_bar.symbol == "AAPL"
        assert completed_bar.open == 150.00
        assert completed_bar.high == 150.50
        assert completed_bar.low == 149.75
        assert completed_bar.close == 150.25
        assert completed_bar.volume == 550  # 100 + 200 + 150 + 100
        assert completed_bar.timestamp == base_time
        assert completed_bar.trade_count == 4
    
    @pytest.mark.asyncio
    async def test_vwap_calculation(self):
        """Test VWAP calculation in bars."""
        aggregator = BarAggregator(timeframe=1)
        
        base_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        
        # Add ticks
        ticks = [
            Tick("AAPL", 150.00, 100, base_time + timedelta(seconds=10)),
            Tick("AAPL", 151.00, 200, base_time + timedelta(seconds=20)),
            Tick("AAPL", 152.00, 100, base_time + timedelta(seconds=30)),
        ]
        
        for tick in ticks:
            await aggregator.add_tick(tick)
        
        # Flush to get the bar
        bars = await aggregator.flush_bars()
        assert len(bars) == 1
        
        bar = bars[0]
        # VWAP = (150*100 + 151*200 + 152*100) / (100+200+100)
        #      = (15000 + 30200 + 15200) / 400
        #      = 60400 / 400 = 151.0
        assert bar.vwap == 151.0
    
    @pytest.mark.asyncio
    async def test_bid_ask_volume_tracking(self):
        """Test tracking bid/ask volumes."""
        aggregator = BarAggregator(timeframe=1)
        
        base_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        
        # Add different tick types
        ticks = [
            Tick("AAPL", 150.00, 100, base_time + timedelta(seconds=10), TickType.BID),
            Tick("AAPL", 150.10, 200, base_time + timedelta(seconds=20), TickType.ASK),
            Tick("AAPL", 150.05, 150, base_time + timedelta(seconds=30), TickType.TRADE),
            Tick("AAPL", 150.00, 50, base_time + timedelta(seconds=40), TickType.BID),
        ]
        
        for tick in ticks:
            await aggregator.add_tick(tick)
        
        # Flush to get the bar
        bars = await aggregator.flush_bars()
        bar = bars[0]
        
        assert bar.bid_volume == 150  # 100 + 50
        assert bar.ask_volume == 200
        assert bar.volume == 500  # Total


@pytest.fixture
async def mock_redis():
    """Create a mock Redis client."""
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.publish = AsyncMock(return_value=1)
    redis_client.close = AsyncMock()
    return redis_client


@pytest.fixture
async def stream_processor(mock_redis):
    """Create a stream processor instance with mocks."""
    processor = StreamProcessor(
        redis_client=mock_redis,
        save_to_db=False,
        timeframes=[1, 5]
    )
    await processor.start()
    yield processor
    await processor.stop()


class TestStreamProcessor:
    """Test the StreamProcessor functionality."""
    
    @pytest.mark.asyncio
    async def test_processor_initialization(self, mock_redis):
        """Test stream processor initialization."""
        processor = StreamProcessor(
            redis_client=mock_redis,
            save_to_db=False,
            timeframes=[1, 5, 15]
        )
        
        assert len(processor.aggregators) == 3
        assert 1 in processor.aggregators
        assert 5 in processor.aggregators
        assert 15 in processor.aggregators
        assert processor._running is False
    
    @pytest.mark.asyncio
    async def test_start_stop(self, stream_processor):
        """Test starting and stopping the processor."""
        assert stream_processor._running is True
        assert stream_processor._processing_task is not None
        assert stream_processor.stats['start_time'] is not None
        
        await stream_processor.stop()
        assert stream_processor._running is False
    
    @pytest.mark.asyncio
    async def test_add_tick_to_queue(self, stream_processor, mock_redis):
        """Test adding ticks to processing queue."""
        tick = Tick(
            symbol="AAPL",
            price=150.25,
            volume=100,
            timestamp=datetime.now(timezone.utc)
        )
        
        success = await stream_processor.add_tick(tick)
        assert success is True
        
        # Check Redis publish was called
        mock_redis.publish.assert_called()
        
        # Check health monitor was updated
        assert "AAPL" in stream_processor.health_monitors
        assert stream_processor.health_monitors["AAPL"].ticks_received == 1
    
    @pytest.mark.asyncio
    async def test_tick_processing(self, stream_processor):
        """Test end-to-end tick processing."""
        base_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        
        # Add callback to track processed ticks
        processed_ticks = []
        stream_processor.on_tick(lambda tick: processed_ticks.append(tick))
        
        # Add callback to track completed bars
        completed_bars = []
        stream_processor.on_bar(lambda bar: completed_bars.append(bar))
        
        # Add ticks for a complete minute
        for i in range(5):
            tick = Tick(
                symbol="AAPL",
                price=150.00 + i * 0.10,
                volume=100,
                timestamp=base_time + timedelta(seconds=i * 10)
            )
            await stream_processor.add_tick(tick)
        
        # Allow processing
        await asyncio.sleep(0.1)
        
        # Add tick from next minute to complete bar
        next_tick = Tick(
            symbol="AAPL",
            price=151.00,
            volume=100,
            timestamp=base_time + timedelta(minutes=1, seconds=5)
        )
        await stream_processor.add_tick(next_tick)
        
        # Allow processing
        await asyncio.sleep(0.1)
        
        # Check callbacks were called
        assert len(processed_ticks) == 6
        assert len(completed_bars) >= 1  # At least one 1-minute bar
        
        # Check the completed bar
        bar = completed_bars[0]
        assert bar.symbol == "AAPL"
        assert bar.open == 150.00
        assert bar.high == 150.40
        assert bar.low == 150.00
        assert bar.close == 150.40
        assert bar.volume == 500
    
    @pytest.mark.asyncio
    async def test_volume_profile_tracking(self, stream_processor):
        """Test volume profile is updated with ticks."""
        # Add ticks
        ticks = [
            Tick("AAPL", 150.25, 100, datetime.now(timezone.utc)),
            Tick("AAPL", 150.25, 200, datetime.now(timezone.utc)),
            Tick("AAPL", 150.30, 150, datetime.now(timezone.utc)),
        ]
        
        for tick in ticks:
            await stream_processor.add_tick(tick)
        
        # Allow processing
        await asyncio.sleep(0.1)
        
        # Check volume profile
        profile = stream_processor.get_volume_profile("AAPL")
        assert profile is not None
        assert profile.total_volume == 450
        assert profile.poc == 150.25
    
    @pytest.mark.asyncio
    async def test_health_monitoring(self, stream_processor):
        """Test health monitoring functionality."""
        # Add a tick
        tick = Tick(
            symbol="AAPL",
            price=150.25,
            volume=100,
            timestamp=datetime.now(timezone.utc)
        )
        await stream_processor.add_tick(tick)
        
        # Allow processing
        await asyncio.sleep(0.1)
        
        # Check health
        health = stream_processor.get_health("AAPL")
        assert health is not None
        assert health.ticks_received >= 1
        assert health.last_tick is not None
        
        # Check overall health
        assert stream_processor.is_healthy("AAPL") is False  # Not connected yet
    
    @pytest.mark.asyncio
    async def test_recent_data_access(self, stream_processor):
        """Test accessing recent ticks and bars."""
        # Add some ticks
        for i in range(10):
            tick = Tick(
                symbol="AAPL",
                price=150.00 + i * 0.10,
                volume=100,
                timestamp=datetime.now(timezone.utc)
            )
            await stream_processor.add_tick(tick)
        
        # Allow processing
        await asyncio.sleep(0.1)
        
        # Get recent ticks
        recent_ticks = stream_processor.get_recent_ticks("AAPL", limit=5)
        assert len(recent_ticks) <= 5
        
        # All should be AAPL ticks
        for tick in recent_ticks:
            assert tick.symbol == "AAPL"
    
    @pytest.mark.asyncio
    async def test_error_handling(self, stream_processor):
        """Test error handling in tick processing."""
        # Add a callback that raises an error
        def error_callback(tick):
            raise Exception("Test error")
        
        stream_processor.on_tick(error_callback)
        
        # Add a tick
        tick = Tick(
            symbol="AAPL",
            price=150.25,
            volume=100,
            timestamp=datetime.now(timezone.utc)
        )
        await stream_processor.add_tick(tick)
        
        # Allow processing
        await asyncio.sleep(0.1)
        
        # Should still process the tick despite callback error
        assert stream_processor.stats['ticks_processed'] >= 1


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_calculate_vwap(self):
        """Test VWAP calculation."""
        ticks = [
            Tick("AAPL", 150.00, 100, datetime.now(timezone.utc)),
            Tick("AAPL", 151.00, 200, datetime.now(timezone.utc)),
            Tick("AAPL", 152.00, 100, datetime.now(timezone.utc)),
        ]
        
        vwap = calculate_vwap(ticks)
        # (150*100 + 151*200 + 152*100) / 400 = 151.0
        assert vwap == 151.0
        
        # Empty list
        assert calculate_vwap([]) == 0.0
    
    def test_detect_tick_gaps(self):
        """Test tick gap detection."""
        base_time = datetime.now(timezone.utc)
        
        ticks = [
            Tick("AAPL", 150.00, 100, base_time),
            Tick("AAPL", 150.10, 100, base_time + timedelta(seconds=2)),
            Tick("AAPL", 150.20, 100, base_time + timedelta(seconds=10)),  # Gap
            Tick("AAPL", 150.30, 100, base_time + timedelta(seconds=12)),
        ]
        
        gaps = detect_tick_gaps(ticks, threshold_seconds=5.0)
        assert len(gaps) == 1
        
        gap_before, gap_after, gap_seconds = gaps[0]
        assert gap_before.price == 150.10
        assert gap_after.price == 150.20
        assert gap_seconds == 8.0
    
    @pytest.mark.asyncio
    async def test_create_stream_processor(self):
        """Test create_stream_processor utility."""
        with patch('src.data.stream_processor.redis.from_url') as mock_redis_from_url:
            mock_redis_client = AsyncMock()
            mock_redis_client.ping = AsyncMock(return_value=True)
            
            async def mock_from_url(*args, **kwargs):
                return mock_redis_client
            
            mock_redis_from_url.side_effect = mock_from_url
            
            processor = await create_stream_processor(
                redis_url="redis://localhost:6379",
                save_to_db=False,
                timeframes=[1, 5]
            )
            
            assert processor is not None
            assert processor._running is True
            assert processor.redis_client == mock_redis_client
            
            await processor.stop()


class TestIntegration:
    """Integration tests for stream processor."""
    
    @pytest.mark.asyncio
    async def test_full_processing_pipeline(self, stream_processor):
        """Test full tick to bar processing pipeline."""
        base_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        
        # Track all events
        events = {
            'ticks': [],
            'bars': [],
            'health': []
        }
        
        stream_processor.on_tick(lambda t: events['ticks'].append(t))
        stream_processor.on_bar(lambda b: events['bars'].append(b))
        stream_processor.on_health_update(lambda h: events['health'].append(h))
        
        # Simulate a trading session
        for minute in range(3):
            for second in range(0, 60, 10):
                tick = Tick(
                    symbol="AAPL",
                    price=150.00 + (minute * 0.10) + (second * 0.001),
                    volume=100 + second,
                    timestamp=base_time + timedelta(minutes=minute, seconds=second)
                )
                await stream_processor.add_tick(tick)
        
        # Allow processing
        await asyncio.sleep(0.5)
        
        # Check results
        assert len(events['ticks']) == 18  # 3 minutes * 6 ticks per minute
        assert len(events['bars']) >= 2  # At least 2 complete 1-minute bars
        
        # Verify bar accuracy
        if events['bars']:
            first_bar = events['bars'][0]
            assert first_bar.symbol == "AAPL"
            assert first_bar.timeframe == 1
            assert first_bar.trade_count == 6  # 6 ticks per minute