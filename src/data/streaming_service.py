"""
High-level streaming service coordinating WebSocket and Stream Processor.

This service manages the complete streaming pipeline from WebSocket connection
to processed market data, providing a unified interface for the trading system.
"""

import asyncio
from typing import List, Optional, Dict, Any, Set, Callable
from datetime import datetime, timezone
from dataclasses import dataclass, field
import logging

from .websocket_client import SchwabWebSocketClient, ConnectionState
from .websocket_parser import SchwabMessageParser, ServiceType
from .stream_processor import StreamProcessor, create_stream_processor, Tick, OHLCV, StreamHealth
from ..config.settings import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class StreamingStats:
    """Statistics for streaming service."""
    start_time: Optional[datetime] = None
    messages_received: int = 0
    ticks_processed: int = 0
    bars_created: int = 0
    errors: int = 0
    last_message_time: Optional[datetime] = None
    
    # Connection stats
    connection_attempts: int = 0
    successful_connections: int = 0
    disconnections: int = 0
    
    # Symbol tracking
    subscribed_symbols: Set[str] = field(default_factory=set)
    active_symbols: Set[str] = field(default_factory=set)
    
    @property
    def uptime_seconds(self) -> float:
        """Get uptime in seconds."""
        if not self.start_time:
            return 0.0
        return (datetime.now(timezone.utc) - self.start_time).total_seconds()
    
    @property
    def messages_per_second(self) -> float:
        """Calculate messages per second."""
        uptime = self.uptime_seconds
        return self.messages_received / uptime if uptime > 0 else 0.0
    
    @property
    def ticks_per_second(self) -> float:
        """Calculate ticks per second."""
        uptime = self.uptime_seconds
        return self.ticks_processed / uptime if uptime > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'uptime_seconds': self.uptime_seconds,
            'messages_received': self.messages_received,
            'messages_per_second': self.messages_per_second,
            'ticks_processed': self.ticks_processed,
            'ticks_per_second': self.ticks_per_second,
            'bars_created': self.bars_created,
            'errors': self.errors,
            'last_message_time': self.last_message_time.isoformat() if self.last_message_time else None,
            'connection_attempts': self.connection_attempts,
            'successful_connections': self.successful_connections,
            'disconnections': self.disconnections,
            'subscribed_symbols': list(self.subscribed_symbols),
            'active_symbols': list(self.active_symbols),
            'symbol_count': len(self.subscribed_symbols)
        }


class StreamingService:
    """
    High-level streaming service coordinating WebSocket and Stream Processor.
    
    Features:
    - Manages WebSocket lifecycle
    - Routes parsed ticks to Stream Processor
    - Monitors streaming health
    - Provides unified interface
    - Tracks comprehensive statistics
    """
    
    def __init__(
        self,
        account_id: str,
        redis_url: Optional[str] = None,
        save_to_db: bool = True,
        timeframes: List[int] = None
    ):
        """
        Initialize streaming service.
        
        Args:
            account_id: Schwab account ID for streaming
            redis_url: Optional Redis URL for pub/sub
            save_to_db: Whether to save bars to database
            timeframes: List of bar timeframes (default: [1, 5, 15])
        """
        self.account_id = account_id
        self.redis_url = redis_url
        self.save_to_db = save_to_db
        self.timeframes = timeframes or [1, 5, 15]
        
        # Components
        self.stream_processor: Optional[StreamProcessor] = None
        self.websocket_client: Optional[SchwabWebSocketClient] = None
        self.parser = SchwabMessageParser()
        
        # State
        self._running = False
        self._initialized = False
        self.stats = StreamingStats()
        
        # Monitoring
        self._monitor_task: Optional[asyncio.Task] = None
        self._health_check_interval = 30  # seconds
        
        # Callbacks
        self._connection_callbacks: List[Callable] = []
        self._error_callbacks: List[Callable] = []
        
        logger.info(f"StreamingService initialized for account {account_id}")
    
    async def initialize(self):
        """Initialize streaming components."""
        if self._initialized:
            return
        
        try:
            # Create Stream Processor
            logger.info("Creating stream processor...")
            self.stream_processor = await create_stream_processor(
                redis_url=self.redis_url,
                save_to_db=self.save_to_db,
                timeframes=self.timeframes
            )
            
            # Set up stream processor callbacks
            self.stream_processor.on_tick(self._on_tick_processed)
            self.stream_processor.on_bar(self._on_bar_created)
            
            # Create WebSocket client
            logger.info("Creating WebSocket client...")
            self.websocket_client = SchwabWebSocketClient(
                stream_processor=self.stream_processor,
                account_id=self.account_id
            )
            
            # Override WebSocket message handler to add our processing
            original_handler = self.websocket_client._handle_message
            self.websocket_client._handle_message = self._wrap_message_handler(original_handler)
            
            self._initialized = True
            logger.info("StreamingService initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize streaming service: {e}")
            raise
    
    async def start_streaming(
        self,
        symbols: List[str],
        data_types: List[str] = None
    ):
        """
        Start streaming for specified symbols.
        
        Args:
            symbols: List of symbols to stream
            data_types: Types of data to stream (default: ["QUOTE", "TRADE"])
        """
        if not self._initialized:
            await self.initialize()
        
        if self._running:
            logger.warning("Streaming already running, adding symbols to existing stream")
            await self.websocket_client.subscribe(symbols, data_types)
            return
        
        try:
            self._running = True
            self.stats.start_time = datetime.now(timezone.utc)
            self.stats.connection_attempts += 1
            
            # Connect WebSocket
            logger.info(f"Connecting WebSocket for {len(symbols)} symbols...")
            success = await self.websocket_client.connect()
            
            if not success:
                raise RuntimeError("Failed to establish WebSocket connection")
            
            self.stats.successful_connections += 1
            
            # Subscribe to symbols
            await self.websocket_client.subscribe(symbols, data_types)
            self.stats.subscribed_symbols.update(symbols)
            
            # Start monitoring
            self._monitor_task = asyncio.create_task(self._monitor_health())
            
            # Notify callbacks
            await self._notify_connection_callbacks(True)
            
            logger.info(f"Streaming started for {len(symbols)} symbols")
            
        except Exception as e:
            logger.error(f"Failed to start streaming: {e}")
            self._running = False
            self.stats.errors += 1
            await self._notify_error_callbacks(e)
            raise
    
    async def stop_streaming(self):
        """Stop all streaming."""
        if not self._running:
            return
        
        logger.info("Stopping streaming service...")
        self._running = False
        
        # Cancel monitoring
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        # Disconnect WebSocket
        if self.websocket_client:
            await self.websocket_client.disconnect()
            self.stats.disconnections += 1
        
        # Stop stream processor
        if self.stream_processor:
            await self.stream_processor.stop()
        
        # Notify callbacks
        await self._notify_connection_callbacks(False)
        
        logger.info("Streaming service stopped")
    
    async def add_symbols(
        self,
        symbols: List[str],
        data_types: List[str] = None
    ):
        """
        Add symbols to existing stream.
        
        Args:
            symbols: List of symbols to add
            data_types: Types of data to stream
        """
        if not self._running:
            raise RuntimeError("Streaming not running")
        
        await self.websocket_client.subscribe(symbols, data_types)
        self.stats.subscribed_symbols.update(symbols)
        logger.info(f"Added {len(symbols)} symbols to stream")
    
    async def remove_symbols(
        self,
        symbols: List[str],
        data_types: List[str] = None
    ):
        """
        Remove symbols from stream.
        
        Args:
            symbols: List of symbols to remove
            data_types: Types of data to unsubscribe
        """
        if not self._running:
            raise RuntimeError("Streaming not running")
        
        await self.websocket_client.unsubscribe(symbols, data_types)
        self.stats.subscribed_symbols.difference_update(symbols)
        self.stats.active_symbols.difference_update(symbols)
        logger.info(f"Removed {len(symbols)} symbols from stream")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get streaming statistics."""
        stats = self.stats.to_dict()
        
        # Add stream processor stats
        if self.stream_processor:
            stats['stream_processor'] = self.stream_processor.stats
        
        # Add WebSocket state
        if self.websocket_client:
            stats['websocket_state'] = self.websocket_client.state.value
        
        # Add health status
        stats['health'] = self.get_health_status()
        
        return stats
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status."""
        health = {
            'streaming_service': 'running' if self._running else 'stopped',
            'websocket': None,
            'stream_processor': None,
            'symbols': {}
        }
        
        # WebSocket health
        if self.websocket_client:
            health['websocket'] = {
                'state': self.websocket_client.state.value,
                'connected': self.websocket_client.state == ConnectionState.AUTHENTICATED,
                'reconnect_attempts': self.websocket_client._reconnect_attempts
            }
        
        # Stream processor health
        if self.stream_processor:
            health['stream_processor'] = {
                'running': self.stream_processor._running,
                'ticks_processed': self.stream_processor.stats['ticks_processed'],
                'bars_created': self.stream_processor.stats['bars_created'],
                'errors': self.stream_processor.stats['errors']
            }
            
            # Symbol-specific health
            for symbol, monitor in self.stream_processor.health_monitors.items():
                health['symbols'][symbol] = {
                    'status': monitor.status.value,
                    'is_healthy': monitor.is_healthy,
                    'ticks_received': monitor.ticks_received,
                    'avg_latency_ms': monitor.avg_latency_ms
                }
        
        return health
    
    # Stream processor access methods
    
    def get_recent_ticks(self, symbol: Optional[str] = None, limit: int = 100) -> List[Tick]:
        """Get recent ticks from stream processor."""
        if not self.stream_processor:
            return []
        return self.stream_processor.get_recent_ticks(symbol, limit)
    
    def get_recent_bars(self, symbol: str, timeframe: int = 1, limit: int = 100) -> List[OHLCV]:
        """Get recent bars from stream processor."""
        if not self.stream_processor:
            return []
        return self.stream_processor.get_recent_bars(symbol, timeframe, limit)
    
    def get_volume_profile(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get volume profile for a symbol."""
        if not self.stream_processor:
            return None
        
        profile = self.stream_processor.get_volume_profile(symbol)
        if not profile:
            return None
        
        return {
            'symbol': profile.symbol,
            'poc': profile.poc,
            'val': profile.val,
            'vah': profile.vah,
            'total_volume': profile.total_volume,
            'price_levels': dict(sorted(profile.price_levels.items()))
        }
    
    # Callback registration
    
    def on_connection_change(self, callback: Callable):
        """Register connection change callback."""
        self._connection_callbacks.append(callback)
        return callback
    
    def on_error(self, callback: Callable):
        """Register error callback."""
        self._error_callbacks.append(callback)
        return callback
    
    # Private methods
    
    def _wrap_message_handler(self, original_handler):
        """Wrap WebSocket message handler to add our processing."""
        async def wrapped_handler(message: str):
            try:
                # Update stats
                self.stats.messages_received += 1
                self.stats.last_message_time = datetime.now(timezone.utc)
                
                # Parse message
                parsed = self.parser.parse(message)
                
                # Extract ticks if it's a data message
                if parsed.is_data_message:
                    ticks = self.parser.to_ticks(parsed)
                    
                    # Update active symbols
                    for tick in ticks:
                        self.stats.active_symbols.add(tick.symbol)
                    
                    # Stats will be updated by callbacks
                    logger.debug(f"Extracted {len(ticks)} ticks from message")
                
                # Call original handler
                await original_handler(message)
                
            except Exception as e:
                logger.error(f"Error in message handler wrapper: {e}")
                self.stats.errors += 1
                await self._notify_error_callbacks(e)
        
        return wrapped_handler
    
    async def _on_tick_processed(self, tick: Tick):
        """Callback when tick is processed."""
        self.stats.ticks_processed += 1
    
    async def _on_bar_created(self, bar: OHLCV):
        """Callback when bar is created."""
        self.stats.bars_created += 1
    
    async def _monitor_health(self):
        """Monitor streaming health periodically."""
        while self._running:
            try:
                await asyncio.sleep(self._health_check_interval)
                
                # Check WebSocket state
                if self.websocket_client:
                    ws_state = self.websocket_client.state
                    if ws_state == ConnectionState.ERROR:
                        logger.error("WebSocket in error state")
                        await self._notify_error_callbacks(
                            RuntimeError("WebSocket connection error")
                        )
                    elif ws_state == ConnectionState.DISCONNECTED:
                        logger.warning("WebSocket disconnected")
                
                # Check for stale data
                if self.stats.last_message_time:
                    staleness = (
                        datetime.now(timezone.utc) - self.stats.last_message_time
                    ).total_seconds()
                    
                    if staleness > 60:  # No messages for 1 minute
                        logger.warning(f"No messages received for {staleness:.1f} seconds")
                
                # Log statistics
                logger.info(
                    f"Streaming stats: {self.stats.messages_received} messages, "
                    f"{self.stats.ticks_processed} ticks, {self.stats.bars_created} bars, "
                    f"{len(self.stats.active_symbols)} active symbols"
                )
                
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
    
    async def _notify_connection_callbacks(self, connected: bool):
        """Notify connection change callbacks."""
        for callback in self._connection_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(connected)
                else:
                    callback(connected)
            except Exception as e:
                logger.error(f"Connection callback error: {e}")
    
    async def _notify_error_callbacks(self, error: Exception):
        """Notify error callbacks."""
        for callback in self._error_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(error)
                else:
                    callback(error)
            except Exception as e:
                logger.error(f"Error callback error: {e}")
    
    # Context manager support
    
    async def __aenter__(self):
        """Enter async context."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        await self.stop_streaming()


# Utility functions

async def create_streaming_service(
    account_id: str,
    symbols: List[str],
    redis_url: Optional[str] = None,
    save_to_db: bool = True,
    timeframes: List[int] = None
) -> StreamingService:
    """
    Create and start a streaming service.
    
    Args:
        account_id: Schwab account ID
        symbols: Initial symbols to stream
        redis_url: Optional Redis URL
        save_to_db: Whether to save bars to database
        timeframes: List of bar timeframes
        
    Returns:
        Running StreamingService instance
    """
    service = StreamingService(
        account_id=account_id,
        redis_url=redis_url,
        save_to_db=save_to_db,
        timeframes=timeframes
    )
    
    await service.start_streaming(symbols)
    return service