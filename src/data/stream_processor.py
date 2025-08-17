"""
Real-time stream processor for market data with OHLCV aggregation and volume profiling.

This module provides real-time tick data processing, OHLCV bar construction,
volume profile tracking, and stream health monitoring for the trading system.
"""

import asyncio
import json
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Tuple, Union, Set
import logging
from functools import wraps

import redis.asyncio as redis
from redis.asyncio.client import Redis
from redis.exceptions import RedisError

from ..config.settings import get_settings
from ..utils.logger import get_logger
from .models import PriceData
from .database import get_async_db

logger = get_logger(__name__)


class TickType(str, Enum):
    """Type of tick data."""
    TRADE = "TRADE"
    BID = "BID"
    ASK = "ASK"
    
    
class StreamStatus(str, Enum):
    """Stream connection status."""
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"


@dataclass
class Tick:
    """Represents a single tick of market data."""
    
    symbol: str
    price: float
    volume: int
    timestamp: datetime
    tick_type: TickType = TickType.TRADE
    
    # Additional fields
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    
    # Metadata
    sequence_id: Optional[int] = None
    exchange: Optional[str] = None
    conditions: Optional[List[str]] = None
    
    def __post_init__(self):
        """Validate tick data after initialization."""
        if self.price <= 0:
            raise ValueError(f"Invalid price: {self.price}")
        if self.volume < 0:
            raise ValueError(f"Invalid volume: {self.volume}")
        
        # Ensure timezone-aware timestamp
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tick to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['tick_type'] = self.tick_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Tick':
        """Create Tick from dictionary."""
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if isinstance(data.get('tick_type'), str):
            data['tick_type'] = TickType(data['tick_type'])
        return cls(**data)


@dataclass
class OHLCV:
    """Open-High-Low-Close-Volume bar."""
    
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    timestamp: datetime  # Bar start time
    timeframe: int  # Minutes
    
    # Additional metrics
    vwap: Optional[float] = None
    trade_count: int = 0
    bid_volume: int = 0
    ask_volume: int = 0
    
    def __post_init__(self):
        """Calculate derived fields."""
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)
    
    @property
    def is_bullish(self) -> bool:
        """Check if bar is bullish (close > open)."""
        return self.close > self.open
    
    @property
    def range(self) -> float:
        """Calculate bar range (high - low)."""
        return self.high - self.low
    
    @property
    def body(self) -> float:
        """Calculate bar body size."""
        return abs(self.close - self.open)
    
    def to_price_data(self) -> PriceData:
        """Convert to PriceData model for database storage."""
        return PriceData(
            symbol=self.symbol,
            timestamp=self.timestamp,
            open=Decimal(str(self.open)),
            high=Decimal(str(self.high)),
            low=Decimal(str(self.low)),
            close=Decimal(str(self.close)),
            volume=self.volume,
            vwap=Decimal(str(self.vwap)) if self.vwap else None
        )


@dataclass
class VolumeProfile:
    """Volume profile tracking for price levels."""
    
    symbol: str
    start_time: datetime
    end_time: Optional[datetime] = None
    
    # Price level -> volume mapping
    price_levels: Dict[float, int] = field(default_factory=dict)
    
    # Cached calculations
    _poc: Optional[float] = None  # Point of Control
    _vah: Optional[float] = None  # Value Area High
    _val: Optional[float] = None  # Value Area Low
    _total_volume: Optional[int] = None
    
    def add_tick(self, tick: Tick):
        """Add tick volume to price level."""
        # Round price to nearest cent for grouping
        price_level = round(tick.price, 2)
        self.price_levels[price_level] = self.price_levels.get(price_level, 0) + tick.volume
        
        # Invalidate cache
        self._poc = None
        self._vah = None
        self._val = None
        self._total_volume = None
    
    @property
    def total_volume(self) -> int:
        """Get total volume across all price levels."""
        if self._total_volume is None:
            self._total_volume = sum(self.price_levels.values())
        return self._total_volume
    
    @property
    def poc(self) -> Optional[float]:
        """Get Point of Control (price level with highest volume)."""
        if self._poc is None and self.price_levels:
            self._poc = max(self.price_levels.items(), key=lambda x: x[1])[0]
        return self._poc
    
    def calculate_value_area(self, percentage: float = 0.70) -> Tuple[float, float]:
        """
        Calculate Value Area (typically 70% of volume).
        
        Returns:
            Tuple of (value_area_low, value_area_high)
        """
        if not self.price_levels:
            return 0.0, 0.0
        
        if self._val is not None and self._vah is not None:
            return self._val, self._vah
        
        # Sort price levels by volume (descending)
        sorted_levels = sorted(self.price_levels.items(), key=lambda x: x[1], reverse=True)
        
        target_volume = self.total_volume * percentage
        accumulated_volume = 0
        value_area_prices = []
        
        # Accumulate volume starting from POC
        for price, volume in sorted_levels:
            accumulated_volume += volume
            value_area_prices.append(price)
            if accumulated_volume >= target_volume:
                break
        
        self._val = min(value_area_prices)
        self._vah = max(value_area_prices)
        
        return self._val, self._vah
    
    @property
    def val(self) -> Optional[float]:
        """Get Value Area Low."""
        if self._val is None:
            self.calculate_value_area()
        return self._val
    
    @property
    def vah(self) -> Optional[float]:
        """Get Value Area High."""
        if self._vah is None:
            self.calculate_value_area()
        return self._vah


@dataclass
class StreamHealth:
    """Stream health monitoring metrics."""
    
    status: StreamStatus = StreamStatus.DISCONNECTED
    last_tick: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    
    # Metrics
    ticks_received: int = 0
    ticks_processed: int = 0
    ticks_dropped: int = 0
    
    # Gap detection
    gaps_detected: int = 0
    last_gap: Optional[datetime] = None
    
    # Latency tracking
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    latency_samples: deque = field(default_factory=lambda: deque(maxlen=100))
    
    # Error tracking
    error_count: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    
    def update_tick(self, tick: Tick):
        """Update health metrics with new tick."""
        now = datetime.now(timezone.utc)
        self.last_tick = now
        self.ticks_received += 1
        
        # Calculate latency
        if tick.timestamp:
            latency_ms = (now - tick.timestamp).total_seconds() * 1000
            self.latency_samples.append(latency_ms)
            self.avg_latency_ms = sum(self.latency_samples) / len(self.latency_samples)
            self.max_latency_ms = max(self.max_latency_ms, latency_ms)
    
    def record_error(self, error: str):
        """Record an error occurrence."""
        self.error_count += 1
        self.last_error = error
        self.last_error_time = datetime.now(timezone.utc)
        
        # Update status based on error frequency
        if self.error_count > 10:
            self.status = StreamStatus.ERROR
        elif self.error_count > 5:
            self.status = StreamStatus.DEGRADED
    
    @property
    def is_healthy(self) -> bool:
        """Check if stream is healthy."""
        if self.status not in (StreamStatus.CONNECTED, StreamStatus.HEALTHY):
            return False
        
        # Check for stale data (no ticks for 30 seconds during market hours)
        if self.last_tick:
            staleness = (datetime.now(timezone.utc) - self.last_tick).total_seconds()
            if staleness > 30:
                return False
        
        # Check error rate
        if self.error_count > 5:
            return False
        
        return True


class BarAggregator:
    """Aggregates ticks into OHLCV bars."""
    
    def __init__(self, timeframe: int = 1):
        """
        Initialize bar aggregator.
        
        Args:
            timeframe: Bar timeframe in minutes
        """
        self.timeframe = timeframe
        self.current_bars: Dict[str, Dict[str, Any]] = {}
        self.completed_bars: List[OHLCV] = []
        self._lock = asyncio.Lock()
    
    def get_bar_timestamp(self, tick_time: datetime) -> datetime:
        """Get the bar timestamp for a given tick time."""
        # Round down to nearest bar boundary
        minutes = tick_time.minute
        bar_minute = (minutes // self.timeframe) * self.timeframe
        
        return tick_time.replace(
            minute=bar_minute,
            second=0,
            microsecond=0
        )
    
    async def add_tick(self, tick: Tick) -> Optional[OHLCV]:
        """
        Add tick to aggregation.
        
        Returns:
            Completed OHLCV bar if a bar was completed, None otherwise
        """
        async with self._lock:
            bar_time = self.get_bar_timestamp(tick.timestamp)
            bar_key = f"{tick.symbol}:{bar_time.isoformat()}"
            
            # Check if we need to close previous bar
            completed_bar = None
            if tick.symbol in self.current_bars:
                current_bar = self.current_bars[tick.symbol]
                if current_bar['timestamp'] < bar_time:
                    # Complete the previous bar
                    completed_bar = self._create_ohlcv(current_bar)
                    self.completed_bars.append(completed_bar)
                    del self.current_bars[tick.symbol]
            
            # Update or create current bar
            if tick.symbol not in self.current_bars:
                self.current_bars[tick.symbol] = {
                    'symbol': tick.symbol,
                    'timestamp': bar_time,
                    'open': tick.price,
                    'high': tick.price,
                    'low': tick.price,
                    'close': tick.price,
                    'volume': tick.volume,
                    'vwap_numerator': tick.price * tick.volume,
                    'trade_count': 1,
                    'bid_volume': tick.volume if tick.tick_type == TickType.BID else 0,
                    'ask_volume': tick.volume if tick.tick_type == TickType.ASK else 0,
                }
            else:
                bar = self.current_bars[tick.symbol]
                bar['high'] = max(bar['high'], tick.price)
                bar['low'] = min(bar['low'], tick.price)
                bar['close'] = tick.price
                bar['volume'] += tick.volume
                bar['vwap_numerator'] += tick.price * tick.volume
                bar['trade_count'] += 1
                
                if tick.tick_type == TickType.BID:
                    bar['bid_volume'] += tick.volume
                elif tick.tick_type == TickType.ASK:
                    bar['ask_volume'] += tick.volume
            
            return completed_bar
    
    def _create_ohlcv(self, bar_data: Dict[str, Any]) -> OHLCV:
        """Create OHLCV object from bar data."""
        vwap = bar_data['vwap_numerator'] / bar_data['volume'] if bar_data['volume'] > 0 else bar_data['close']
        
        return OHLCV(
            symbol=bar_data['symbol'],
            open=bar_data['open'],
            high=bar_data['high'],
            low=bar_data['low'],
            close=bar_data['close'],
            volume=bar_data['volume'],
            timestamp=bar_data['timestamp'],
            timeframe=self.timeframe,
            vwap=vwap,
            trade_count=bar_data['trade_count'],
            bid_volume=bar_data['bid_volume'],
            ask_volume=bar_data['ask_volume']
        )
    
    async def flush_bars(self) -> List[OHLCV]:
        """Force completion of all current bars."""
        async with self._lock:
            completed = []
            for symbol, bar_data in self.current_bars.items():
                bar = self._create_ohlcv(bar_data)
                completed.append(bar)
                self.completed_bars.append(bar)
            
            self.current_bars.clear()
            return completed


class StreamProcessor:
    """
    Real-time stream processor for market data.
    
    Handles tick processing, OHLCV aggregation, volume profiling,
    and stream health monitoring.
    """
    
    def __init__(
        self,
        redis_client: Optional[Redis] = None,
        save_to_db: bool = True,
        timeframes: List[int] = None
    ):
        """
        Initialize stream processor.
        
        Args:
            redis_client: Redis client for pub/sub
            save_to_db: Whether to save bars to database
            timeframes: List of timeframes to aggregate (default: [1, 5, 15])
        """
        self.redis_client = redis_client
        self.save_to_db = save_to_db
        self.timeframes = timeframes or [1, 5, 15]
        
        # Components
        self.aggregators: Dict[int, BarAggregator] = {
            tf: BarAggregator(tf) for tf in self.timeframes
        }
        self.volume_profiles: Dict[str, VolumeProfile] = {}
        self.health_monitors: Dict[str, StreamHealth] = {}
        
        # Tick processing
        self.tick_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self.tick_buffer: deque = deque(maxlen=1000)
        
        # Callbacks
        self.tick_callbacks: List[Callable] = []
        self.bar_callbacks: List[Callable] = []
        self.health_callbacks: List[Callable] = []
        
        # Processing task
        self._processing_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Stats
        self.stats = {
            'ticks_processed': 0,
            'bars_created': 0,
            'errors': 0,
            'start_time': None
        }
        
        # Redis channels
        self.TICK_CHANNEL = "stream:ticks"
        self.BAR_CHANNEL = "stream:bars"
        self.HEALTH_CHANNEL = "stream:health"
        
        logger.info("Stream processor initialized")
    
    async def start(self):
        """Start the stream processor."""
        if self._running:
            logger.warning("Stream processor already running")
            return
        
        self._running = True
        self.stats['start_time'] = datetime.now(timezone.utc)
        
        # Start processing task
        self._processing_task = asyncio.create_task(self._process_ticks())
        
        # Start health monitoring
        asyncio.create_task(self._monitor_health())
        
        logger.info("Stream processor started")
    
    async def stop(self):
        """Stop the stream processor."""
        if not self._running:
            return
        
        self._running = False
        
        # Flush remaining bars
        await self.flush_all_bars()
        
        # Cancel processing task
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"Stream processor stopped. Stats: {self.stats}")
    
    async def add_tick(self, tick: Tick) -> bool:
        """
        Add tick to processing queue.
        
        Returns:
            True if tick was queued, False if queue is full
        """
        try:
            # Add to queue without blocking
            self.tick_queue.put_nowait(tick)
            
            # Update health monitor
            symbol = tick.symbol
            if symbol not in self.health_monitors:
                self.health_monitors[symbol] = StreamHealth()
            self.health_monitors[symbol].update_tick(tick)
            
            # Add to buffer for recent tick access
            self.tick_buffer.append(tick)
            
            # Publish to Redis if available
            if self.redis_client:
                try:
                    await self.redis_client.publish(
                        f"{self.TICK_CHANNEL}:{symbol}",
                        json.dumps(tick.to_dict())
                    )
                except RedisError as e:
                    logger.error(f"Redis publish error: {e}")
            
            return True
            
        except asyncio.QueueFull:
            logger.warning(f"Tick queue full, dropping tick for {tick.symbol}")
            if tick.symbol in self.health_monitors:
                self.health_monitors[tick.symbol].ticks_dropped += 1
            return False
    
    async def _process_ticks(self):
        """Main tick processing loop."""
        logger.info("Starting tick processing loop")
        
        while self._running:
            try:
                # Get tick from queue with timeout
                tick = await asyncio.wait_for(
                    self.tick_queue.get(),
                    timeout=1.0
                )
                
                # Process tick
                await self._process_single_tick(tick)
                
            except asyncio.TimeoutError:
                # No ticks received, check health
                await self._check_stale_streams()
                
            except Exception as e:
                logger.error(f"Error processing tick: {e}")
                self.stats['errors'] += 1
    
    async def _process_single_tick(self, tick: Tick):
        """Process a single tick."""
        try:
            # Update stats
            self.stats['ticks_processed'] += 1
            if tick.symbol in self.health_monitors:
                self.health_monitors[tick.symbol].ticks_processed += 1
            
            # Run tick callbacks
            for callback in self.tick_callbacks:
                try:
                    await callback(tick) if asyncio.iscoroutinefunction(callback) else callback(tick)
                except Exception as e:
                    logger.error(f"Tick callback error: {e}")
            
            # Add to aggregators
            completed_bars = []
            for timeframe, aggregator in self.aggregators.items():
                completed_bar = await aggregator.add_tick(tick)
                if completed_bar:
                    completed_bars.append(completed_bar)
                    self.stats['bars_created'] += 1
            
            # Update volume profile
            if tick.symbol not in self.volume_profiles:
                self.volume_profiles[tick.symbol] = VolumeProfile(
                    symbol=tick.symbol,
                    start_time=tick.timestamp
                )
            self.volume_profiles[tick.symbol].add_tick(tick)
            
            # Process completed bars
            for bar in completed_bars:
                await self._process_completed_bar(bar)
                
        except Exception as e:
            logger.error(f"Error processing tick {tick}: {e}")
            if tick.symbol in self.health_monitors:
                self.health_monitors[tick.symbol].record_error(str(e))
    
    async def _process_completed_bar(self, bar: OHLCV):
        """Process a completed OHLCV bar."""
        try:
            # Save to database if enabled
            if self.save_to_db:
                async with get_async_db() as db:
                    price_data = bar.to_price_data()
                    db.add(price_data)
                    await db.commit()
            
            # Publish to Redis
            if self.redis_client:
                try:
                    # Convert bar to dict with proper datetime serialization
                    bar_dict = asdict(bar)
                    bar_dict['timestamp'] = bar.timestamp.isoformat()
                    
                    await self.redis_client.publish(
                        f"{self.BAR_CHANNEL}:{bar.symbol}:{bar.timeframe}",
                        json.dumps(bar_dict)
                    )
                except RedisError as e:
                    logger.error(f"Redis publish error for bar: {e}")
            
            # Run bar callbacks
            for callback in self.bar_callbacks:
                try:
                    await callback(bar) if asyncio.iscoroutinefunction(callback) else callback(bar)
                except Exception as e:
                    logger.error(f"Bar callback error: {e}")
                    
        except Exception as e:
            logger.error(f"Error processing completed bar: {e}")
    
    async def _monitor_health(self):
        """Monitor stream health periodically."""
        while self._running:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                
                health_updates = {}
                for symbol, monitor in self.health_monitors.items():
                    # Update status based on current metrics
                    if monitor.is_healthy:
                        if monitor.avg_latency_ms < 50:
                            monitor.status = StreamStatus.HEALTHY
                        else:
                            monitor.status = StreamStatus.CONNECTED
                    
                    health_updates[symbol] = {
                        'status': monitor.status.value,
                        'ticks_received': monitor.ticks_received,
                        'ticks_processed': monitor.ticks_processed,
                        'avg_latency_ms': monitor.avg_latency_ms,
                        'is_healthy': monitor.is_healthy
                    }
                
                # Publish health status
                if self.redis_client and health_updates:
                    try:
                        await self.redis_client.publish(
                            self.HEALTH_CHANNEL,
                            json.dumps(health_updates)
                        )
                    except RedisError as e:
                        logger.error(f"Redis health publish error: {e}")
                
                # Run health callbacks
                for callback in self.health_callbacks:
                    try:
                        await callback(health_updates) if asyncio.iscoroutinefunction(callback) else callback(health_updates)
                    except Exception as e:
                        logger.error(f"Health callback error: {e}")
                        
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
    
    async def _check_stale_streams(self):
        """Check for stale streams that haven't received data."""
        now = datetime.now(timezone.utc)
        
        for symbol, monitor in self.health_monitors.items():
            if monitor.last_tick:
                staleness = (now - monitor.last_tick).total_seconds()
                if staleness > 60 and monitor.status == StreamStatus.HEALTHY:
                    monitor.status = StreamStatus.DEGRADED
                    logger.warning(f"Stream {symbol} is stale ({staleness:.1f}s)")
    
    async def flush_all_bars(self):
        """Flush all pending bars from aggregators."""
        all_bars = []
        
        for timeframe, aggregator in self.aggregators.items():
            bars = await aggregator.flush_bars()
            all_bars.extend(bars)
        
        # Process flushed bars
        for bar in all_bars:
            await self._process_completed_bar(bar)
        
        logger.info(f"Flushed {len(all_bars)} bars")
    
    # Callback registration
    
    def on_tick(self, callback: Callable):
        """Register a tick callback."""
        self.tick_callbacks.append(callback)
        return callback
    
    def on_bar(self, callback: Callable):
        """Register a bar completion callback."""
        self.bar_callbacks.append(callback)
        return callback
    
    def on_health_update(self, callback: Callable):
        """Register a health update callback."""
        self.health_callbacks.append(callback)
        return callback
    
    # Volume profile access
    
    def get_volume_profile(self, symbol: str) -> Optional[VolumeProfile]:
        """Get volume profile for a symbol."""
        return self.volume_profiles.get(symbol)
    
    def get_poc(self, symbol: str) -> Optional[float]:
        """Get Point of Control for a symbol."""
        profile = self.volume_profiles.get(symbol)
        return profile.poc if profile else None
    
    def get_value_area(self, symbol: str) -> Tuple[Optional[float], Optional[float]]:
        """Get Value Area for a symbol."""
        profile = self.volume_profiles.get(symbol)
        if profile:
            return profile.val, profile.vah
        return None, None
    
    # Health monitoring access
    
    def get_health(self, symbol: Optional[str] = None) -> Union[StreamHealth, Dict[str, StreamHealth]]:
        """Get health status for symbol(s)."""
        if symbol:
            return self.health_monitors.get(symbol)
        return dict(self.health_monitors)
    
    def is_healthy(self, symbol: Optional[str] = None) -> bool:
        """Check if stream(s) are healthy."""
        if symbol:
            monitor = self.health_monitors.get(symbol)
            return monitor.is_healthy if monitor else False
        
        # Check all streams
        return all(m.is_healthy for m in self.health_monitors.values())
    
    # Recent data access
    
    def get_recent_ticks(self, symbol: Optional[str] = None, limit: int = 100) -> List[Tick]:
        """Get recent ticks from buffer."""
        ticks = list(self.tick_buffer)
        
        if symbol:
            ticks = [t for t in ticks if t.symbol == symbol]
        
        return ticks[-limit:]
    
    def get_recent_bars(self, symbol: str, timeframe: int = 1, limit: int = 100) -> List[OHLCV]:
        """Get recent completed bars."""
        if timeframe not in self.aggregators:
            return []
        
        aggregator = self.aggregators[timeframe]
        bars = [b for b in aggregator.completed_bars if b.symbol == symbol]
        
        return bars[-limit:]


# Utility functions

async def create_stream_processor(
    redis_url: Optional[str] = None,
    save_to_db: bool = True,
    timeframes: List[int] = None
) -> StreamProcessor:
    """
    Create and initialize a stream processor.
    
    Args:
        redis_url: Redis connection URL
        save_to_db: Whether to save bars to database
        timeframes: List of timeframes to aggregate
        
    Returns:
        Initialized StreamProcessor instance
    """
    redis_client = None
    
    if redis_url:
        try:
            redis_client = await redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await redis_client.ping()
            logger.info("Redis connection established for stream processor")
        except RedisError as e:
            logger.error(f"Redis connection failed: {e}")
            redis_client = None
    
    processor = StreamProcessor(
        redis_client=redis_client,
        save_to_db=save_to_db,
        timeframes=timeframes
    )
    
    await processor.start()
    return processor


def calculate_vwap(ticks: List[Tick]) -> float:
    """Calculate Volume Weighted Average Price from ticks."""
    if not ticks:
        return 0.0
    
    total_value = sum(t.price * t.volume for t in ticks)
    total_volume = sum(t.volume for t in ticks)
    
    return total_value / total_volume if total_volume > 0 else 0.0


def detect_tick_gaps(ticks: List[Tick], threshold_seconds: float = 5.0) -> List[Tuple[Tick, Tick, float]]:
    """
    Detect gaps in tick stream.
    
    Returns:
        List of (tick_before, tick_after, gap_seconds) tuples
    """
    if len(ticks) < 2:
        return []
    
    gaps = []
    sorted_ticks = sorted(ticks, key=lambda t: t.timestamp)
    
    for i in range(1, len(sorted_ticks)):
        prev_tick = sorted_ticks[i-1]
        curr_tick = sorted_ticks[i]
        
        gap = (curr_tick.timestamp - prev_tick.timestamp).total_seconds()
        if gap > threshold_seconds:
            gaps.append((prev_tick, curr_tick, gap))
    
    return gaps