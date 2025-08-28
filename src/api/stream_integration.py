"""Integration between StreamProcessor and WebSocket for real-time data broadcasting."""

import asyncio
import json
import logging
from typing import Dict, Any
from datetime import datetime
from decimal import Decimal

import redis.asyncio as redis

from ..data.stream_processor import StreamProcessor
from ..data.models import TimeFrame

logger = logging.getLogger(__name__)


class StreamWebSocketIntegration:
    """Integrates StreamProcessor with WebSocket broadcasting via Redis."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.stream_processor = StreamProcessor()
        self.running = False
        self._tasks = []
    
    async def start(self):
        """Start the stream processor and broadcasting."""
        try:
            logger.info("Starting StreamWebSocketIntegration...")
            self.running = True
            
            # Start stream processor
            await self.stream_processor.start()
            
            # Start candle broadcasting task
            candle_task = asyncio.create_task(self._broadcast_candles())
            self._tasks.append(candle_task)
            
            # Start quote broadcasting task
            quote_task = asyncio.create_task(self._broadcast_quotes())
            self._tasks.append(quote_task)
            
            logger.info("StreamWebSocketIntegration started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start StreamWebSocketIntegration: {e}")
            await self.stop()
            raise
    
    async def stop(self):
        """Stop the stream processor and broadcasting."""
        logger.info("Stopping StreamWebSocketIntegration...")
        self.running = False
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Stop stream processor
        await self.stream_processor.stop()
        
        logger.info("StreamWebSocketIntegration stopped")
    
    async def _broadcast_candles(self):
        """Subscribe to candle updates and broadcast via Redis."""
        logger.info("Started candle broadcasting")
        
        while self.running:
            try:
                # Get completed candles from stream processor
                candles = self.stream_processor.get_completed_candles()
                
                for candle_key, candle_data in candles.items():
                    # Parse candle key (symbol:timeframe)
                    symbol, timeframe = candle_key.split(':')
                    
                    # Convert Decimal to float for JSON serialization
                    candle_json = {
                        'timestamp': candle_data['timestamp'].isoformat(),
                        'open': float(candle_data['open']),
                        'high': float(candle_data['high']),
                        'low': float(candle_data['low']),
                        'close': float(candle_data['close']),
                        'volume': candle_data['volume']
                    }
                    
                    # Publish to Redis channel
                    channel = f"market_data:{symbol}:{timeframe}"
                    await self.redis_client.publish(
                        channel,
                        json.dumps(candle_json)
                    )
                    
                    logger.debug(f"Published candle to {channel}")
                
                # Clear processed candles
                self.stream_processor.clear_completed_candles()
                
                # Small delay to prevent tight loop
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error broadcasting candles: {e}")
                await asyncio.sleep(1)
    
    async def _broadcast_quotes(self):
        """Subscribe to quote updates and broadcast via Redis."""
        logger.info("Started quote broadcasting")
        
        while self.running:
            try:
                # Get latest quotes from stream processor
                quotes = self.stream_processor.get_latest_quotes()
                
                for symbol, quote_data in quotes.items():
                    # Convert to JSON-serializable format
                    quote_json = {
                        'symbol': symbol,
                        'last_price': float(quote_data.get('last_price', 0)),
                        'bid_price': float(quote_data.get('bid_price', 0)),
                        'ask_price': float(quote_data.get('ask_price', 0)),
                        'bid_size': quote_data.get('bid_size', 0),
                        'ask_size': quote_data.get('ask_size', 0),
                        'volume': quote_data.get('volume', 0),
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    # Publish to Redis channel
                    channel = f"market_data:{symbol}:quote"
                    await self.redis_client.publish(
                        channel,
                        json.dumps(quote_json)
                    )
                    
                    logger.debug(f"Published quote for {symbol}")
                
                # Rate limit quote broadcasts
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error broadcasting quotes: {e}")
                await asyncio.sleep(1)
    
    async def subscribe_symbol(self, symbol: str, timeframe: TimeFrame = TimeFrame.ONE_MIN):
        """Subscribe to a symbol for streaming."""
        try:
            await self.stream_processor.subscribe_symbol(symbol, timeframe)
            logger.info(f"Subscribed to {symbol} with timeframe {timeframe}")
        except Exception as e:
            logger.error(f"Failed to subscribe to {symbol}: {e}")
            raise
    
    async def unsubscribe_symbol(self, symbol: str):
        """Unsubscribe from a symbol."""
        try:
            await self.stream_processor.unsubscribe_symbol(symbol)
            logger.info(f"Unsubscribed from {symbol}")
        except Exception as e:
            logger.error(f"Failed to unsubscribe from {symbol}: {e}")
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the integration."""
        return {
            'running': self.running,
            'stream_processor_status': self.stream_processor.get_status(),
            'active_tasks': len([t for t in self._tasks if not t.done()]),
            'subscribed_symbols': list(self.stream_processor.subscribed_symbols.keys())
        }