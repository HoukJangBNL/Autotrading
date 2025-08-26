"""Streaming service for orchestrating real-time market data."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any
from enum import Enum

from ..data.streaming_client import StreamingClient, create_quote_handler, create_chart_handler
from ..data.stream_processor import StreamProcessor
from ..config.settings import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class StreamingMode(str, Enum):
    """Streaming service operational modes."""
    QUOTES = "QUOTES"  # Level 1 quotes only
    CHARTS = "CHARTS"  # Chart data (OHLCV)
    BOTH = "BOTH"     # Both quotes and charts


class StreamingService:
    """
    Orchestrates real-time data streaming.
    
    Features:
    - Manages streaming client lifecycle
    - Coordinates stream processing
    - Symbol subscription management
    - Health monitoring and recovery
    - Performance metrics
    """
    
    def __init__(self, mode: StreamingMode = StreamingMode.BOTH):
        """
        Initialize streaming service.
        
        Args:
            mode: Streaming mode (quotes, charts, or both)
        """
        self.mode = mode
        self.settings = get_settings()
        
        # Components
        self.streaming_client = None
        self.stream_processor = None
        
        # State management
        self.subscribed_symbols: Set[str] = set()
        self.active = False
        self.start_time = None
        
        # Health monitoring
        self._health_check_task = None
        self._health_check_interval = 30  # seconds
        self._last_message_time = None
        self._message_count = 0
        self._error_count = 0
    
    async def initialize(self):
        """Initialize streaming service components."""
        logger.info(f"Initializing streaming service in {self.mode} mode")
        
        try:
            # Initialize streaming client
            self.streaming_client = StreamingClient()
            await self.streaming_client.initialize()
            
            # Initialize stream processor
            self.stream_processor = StreamProcessor()
            await self.stream_processor.initialize()
            
            # Setup message handlers
            await self._setup_handlers()
            
            logger.info("Streaming service initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize streaming service: {e}")
            raise
    
    async def start(self):
        """Start streaming service."""
        if self.active:
            logger.warning("Streaming service already active")
            return
        
        logger.info("Starting streaming service")
        
        try:
            # Connect to streaming API
            await self.streaming_client.connect()
            
            # Mark as active
            self.active = True
            self.start_time = datetime.now()
            
            # Start health monitoring
            self._health_check_task = asyncio.create_task(self._monitor_health())
            
            logger.info("Streaming service started")
            
        except Exception as e:
            logger.error(f"Failed to start streaming service: {e}")
            self.active = False
            raise
    
    async def stop(self):
        """Stop streaming service."""
        if not self.active:
            return
        
        logger.info("Stopping streaming service")
        self.active = False
        
        try:
            # Stop health monitoring
            if self._health_check_task:
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass
            
            # Disconnect streaming client
            if self.streaming_client:
                await self.streaming_client.disconnect()
            
            # Shutdown processor
            if self.stream_processor:
                await self.stream_processor.shutdown()
            
            logger.info("Streaming service stopped")
            
        except Exception as e:
            logger.error(f"Error stopping streaming service: {e}")
    
    async def subscribe(self, symbols: List[str]):
        """
        Subscribe to symbols for streaming data.
        
        Args:
            symbols: List of symbols to subscribe to
        """
        if not symbols:
            return
        
        # Filter out already subscribed symbols
        new_symbols = [s for s in symbols if s not in self.subscribed_symbols]
        
        if not new_symbols:
            logger.info(f"Already subscribed to all requested symbols: {symbols}")
            return
        
        logger.info(f"Subscribing to {len(new_symbols)} new symbols: {new_symbols}")
        
        try:
            # Subscribe based on mode
            if self.mode in [StreamingMode.QUOTES, StreamingMode.BOTH]:
                await self.streaming_client.subscribe_equity_quotes(new_symbols)
            
            if self.mode in [StreamingMode.CHARTS, StreamingMode.BOTH]:
                await self.streaming_client.subscribe_chart_equity(new_symbols)
            
            # Update subscribed symbols
            self.subscribed_symbols.update(new_symbols)
            
            logger.info(f"Successfully subscribed to {len(new_symbols)} symbols")
            
        except Exception as e:
            logger.error(f"Failed to subscribe to symbols: {e}")
            raise
    
    async def unsubscribe(self, symbols: List[str]):
        """
        Unsubscribe from symbols.
        
        Args:
            symbols: List of symbols to unsubscribe from
        """
        if not symbols:
            return
        
        # Filter to only subscribed symbols
        symbols_to_remove = [s for s in symbols if s in self.subscribed_symbols]
        
        if not symbols_to_remove:
            return
        
        logger.info(f"Unsubscribing from {len(symbols_to_remove)} symbols: {symbols_to_remove}")
        
        try:
            # Unsubscribe based on mode
            if self.mode in [StreamingMode.QUOTES, StreamingMode.BOTH]:
                await self.streaming_client.unsubscribe_equity_quotes(symbols_to_remove)
            
            if self.mode in [StreamingMode.CHARTS, StreamingMode.BOTH]:
                # Chart unsubscribe not implemented in streaming_client yet
                pass
            
            # Update subscribed symbols
            for symbol in symbols_to_remove:
                self.subscribed_symbols.discard(symbol)
            
            logger.info(f"Successfully unsubscribed from {len(symbols_to_remove)} symbols")
            
        except Exception as e:
            logger.error(f"Failed to unsubscribe from symbols: {e}")
    
    async def _setup_handlers(self):
        """Setup message handlers for streaming data."""
        # Create quote handler
        if self.mode in [StreamingMode.QUOTES, StreamingMode.BOTH]:
            quote_handler = create_quote_handler(self._handle_quote)
            self.streaming_client.add_handler("LEVELONE_EQUITIES", quote_handler)
        
        # Create chart handler
        if self.mode in [StreamingMode.CHARTS, StreamingMode.BOTH]:
            chart_handler = create_chart_handler(self._handle_chart)
            self.streaming_client.add_handler("CHART_EQUITY", chart_handler)
    
    async def _handle_quote(self, quote: Dict[str, Any]):
        """Handle incoming quote data."""
        try:
            # Update metrics
            self._message_count += 1
            self._last_message_time = datetime.now()
            
            # Process quote
            await self.stream_processor.process_quote(quote)
            
        except Exception as e:
            logger.error(f"Error handling quote: {e}")
            self._error_count += 1
    
    async def _handle_chart(self, chart: Dict[str, Any]):
        """Handle incoming chart data."""
        try:
            # Update metrics
            self._message_count += 1
            self._last_message_time = datetime.now()
            
            # Process chart
            await self.stream_processor.process_chart(chart)
            
        except Exception as e:
            logger.error(f"Error handling chart: {e}")
            self._error_count += 1
    
    async def _monitor_health(self):
        """Monitor service health and recover if needed."""
        logger.info("Started health monitoring")
        
        while self.active:
            try:
                await asyncio.sleep(self._health_check_interval)
                
                # Check for recent messages
                if self._last_message_time:
                    time_since_last = datetime.now() - self._last_message_time
                    
                    # Alert if no messages for too long (during market hours)
                    if time_since_last > timedelta(minutes=5) and self._is_market_hours():
                        logger.warning(f"No messages received for {time_since_last.total_seconds():.0f} seconds")
                        
                        # Try to reconnect if needed
                        client_state = await self.streaming_client.get_state()
                        if client_state['state'] not in ['AUTHENTICATED', 'STREAMING']:
                            logger.warning("Streaming client not active, attempting reconnection")
                            await self.streaming_client.connect()
                            
                            # Resubscribe to symbols
                            if self.subscribed_symbols:
                                await self.subscribe(list(self.subscribed_symbols))
                
                # Log health metrics
                if self._message_count > 0:
                    logger.debug(
                        f"Health check - Messages: {self._message_count}, "
                        f"Errors: {self._error_count}, "
                        f"Error rate: {self._error_count/self._message_count*100:.2f}%"
                    )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring: {e}")
    
    def _is_market_hours(self) -> bool:
        """Check if current time is during market hours."""
        now = datetime.now()
        weekday = now.weekday()
        
        # Skip weekends
        if weekday >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Market hours: 9:30 AM - 4:00 PM EST
        # Adjust for your timezone as needed
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return market_open <= now <= market_close
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current service status and metrics."""
        status = {
            'active': self.active,
            'mode': self.mode.value,
            'subscribed_symbols': list(self.subscribed_symbols),
            'subscription_count': len(self.subscribed_symbols),
            'message_count': self._message_count,
            'error_count': self._error_count,
            'error_rate': self._error_count / max(self._message_count, 1) * 100,
            'last_message_time': self._last_message_time.isoformat() if self._last_message_time else None,
            'uptime': (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        }
        
        # Add streaming client state
        if self.streaming_client:
            status['streaming_client'] = await self.streaming_client.get_state()
        
        # Add processor stats
        if self.stream_processor:
            status['processor'] = await self.stream_processor.get_stats()
        
        return status
    
    async def get_current_candles(self) -> List[Dict[str, Any]]:
        """Get current in-progress candles."""
        if not self.stream_processor:
            return []
        
        return await self.stream_processor.aggregator.get_current_candles()


# Global service instance
_streaming_service: Optional[StreamingService] = None


async def get_streaming_service(mode: StreamingMode = StreamingMode.BOTH) -> StreamingService:
    """
    Get or create streaming service instance.
    
    Args:
        mode: Streaming mode
        
    Returns:
        StreamingService instance
    """
    global _streaming_service
    
    if not _streaming_service:
        _streaming_service = StreamingService(mode)
        await _streaming_service.initialize()
    
    return _streaming_service


async def start_streaming(symbols: List[str], mode: StreamingMode = StreamingMode.BOTH):
    """
    Start streaming for specified symbols.
    
    Args:
        symbols: List of symbols to stream
        mode: Streaming mode
    """
    service = await get_streaming_service(mode)
    
    if not service.active:
        await service.start()
    
    await service.subscribe(symbols)
    
    return service


async def stop_streaming():
    """Stop streaming service."""
    global _streaming_service
    
    if _streaming_service:
        await _streaming_service.stop()
        _streaming_service = None