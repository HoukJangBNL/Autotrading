"""Stream processor for aggregating real-time market data into candles."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from decimal import Decimal
import redis.asyncio as redis

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..data.database import get_async_db
from ..data.models import Ticker, Candle
from ..config.settings import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class CandleAggregator:
    """
    Aggregates tick data into 1-minute OHLCV candles.
    
    Features:
    - Real-time tick aggregation
    - Redis-based in-progress candle storage
    - PostgreSQL persistence for completed candles
    - Redis pub/sub for broadcasting updates
    - Support for multiple symbols
    """
    
    def __init__(self):
        """Initialize the candle aggregator."""
        self.settings = get_settings()
        self.redis_client = None
        self.pubsub = None
        
        # In-memory cache for current candles
        self.current_candles: Dict[str, Dict[str, Any]] = {}
        
        # Symbol to ticker_id mapping
        self.ticker_map: Dict[str, int] = {}
        
        # Configuration
        self.candle_interval = 60  # 1 minute in seconds
        self.redis_ttl = 300  # 5 minutes TTL for Redis keys
        
        # Background tasks
        self._flush_task = None
        self._running = False
    
    async def initialize(self):
        """Initialize Redis connection and start background tasks."""
        logger.info("Initializing candle aggregator")
        
        try:
            # Connect to Redis
            self.redis_client = await redis.from_url(
                self.settings.database.redis_url,
                decode_responses=True
            )
            
            # Test connection
            await self.redis_client.ping()
            logger.info("Connected to Redis")
            
            # Start background flush task
            self._running = True
            self._flush_task = asyncio.create_task(self._flush_candles_periodically())
            
            logger.info("Candle aggregator initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize aggregator: {e}")
            raise
    
    async def shutdown(self):
        """Shutdown the aggregator and cleanup resources."""
        logger.info("Shutting down candle aggregator")
        self._running = False
        
        try:
            # Cancel background tasks
            if self._flush_task:
                self._flush_task.cancel()
                try:
                    await self._flush_task
                except asyncio.CancelledError:
                    pass
            
            # Flush any remaining candles
            await self.flush_all_candles()
            
            # Close Redis connection
            if self.redis_client:
                await self.redis_client.close()
            
            logger.info("Candle aggregator shut down")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    async def process_quote(self, quote: Dict[str, Any]):
        """
        Process a real-time quote (tick) and aggregate into candles.
        
        Args:
            quote: Quote data with symbol, last price, volume, timestamp
        """
        symbol = quote.get('symbol')
        if not symbol:
            return
        
        # Get current timestamp and candle timestamp (truncated to minute)
        timestamp = quote.get('timestamp', datetime.now(timezone.utc))
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        
        candle_timestamp = timestamp.replace(second=0, microsecond=0)
        candle_key = f"{symbol}:{candle_timestamp.isoformat()}"
        
        # Get or create candle
        if candle_key in self.current_candles:
            candle = self.current_candles[candle_key]
        else:
            candle = await self._create_candle(symbol, candle_timestamp)
            self.current_candles[candle_key] = candle
        
        # Update candle with quote data
        last_price = Decimal(str(quote.get('last', 0)))
        volume = int(quote.get('volume', 0))
        
        if last_price > 0:
            # Initialize open price on first tick
            if candle['open'] is None:
                candle['open'] = last_price
            
            # Update OHLC
            candle['high'] = max(candle['high'], last_price)
            candle['low'] = min(candle['low'], last_price)
            candle['close'] = last_price
            
            # Update volume (accumulate)
            candle['volume'] += volume
            
            # Update trade count
            candle['trade_count'] = candle.get('trade_count', 0) + 1
            
            # Store in Redis
            await self._update_redis_candle(candle_key, candle)
            
            # Publish update
            await self._publish_candle_update(candle)
    
    async def process_chart_data(self, chart: Dict[str, Any]):
        """
        Process chart data (OHLCV) from streaming.
        
        Args:
            chart: Chart data with OHLCV values
        """
        symbol = chart.get('symbol')
        if not symbol:
            return
        
        # Chart data already comes as OHLCV candles
        timestamp = chart.get('timestamp', datetime.now(timezone.utc))
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        
        candle_timestamp = timestamp.replace(second=0, microsecond=0)
        candle_key = f"{symbol}:{candle_timestamp.isoformat()}"
        
        # Create candle from chart data
        candle = {
            'symbol': symbol,
            'timestamp': candle_timestamp,
            'open': Decimal(str(chart.get('open', 0))),
            'high': Decimal(str(chart.get('high', 0))),
            'low': Decimal(str(chart.get('low', 0))),
            'close': Decimal(str(chart.get('close', 0))),
            'volume': int(chart.get('volume', 0)),
            'trade_count': 1,
            'complete': False
        }
        
        # Update current candle
        self.current_candles[candle_key] = candle
        
        # Store in Redis
        await self._update_redis_candle(candle_key, candle)
        
        # Publish update
        await self._publish_candle_update(candle)
    
    async def _create_candle(self, symbol: str, timestamp: datetime) -> Dict[str, Any]:
        """Create a new empty candle."""
        # Get or create ticker_id
        if symbol not in self.ticker_map:
            await self._load_ticker_id(symbol)
        
        return {
            'symbol': symbol,
            'ticker_id': self.ticker_map.get(symbol),
            'timestamp': timestamp,
            'open': None,
            'high': Decimal('0'),
            'low': Decimal('999999999'),
            'close': Decimal('0'),
            'volume': 0,
            'trade_count': 0,
            'complete': False
        }
    
    async def _load_ticker_id(self, symbol: str):
        """Load ticker_id from database."""
        async for session in get_async_db():
            try:
                result = await session.execute(
                    select(Ticker).where(Ticker.symbol == symbol)
                )
                ticker = result.scalar_one_or_none()
                
                if ticker:
                    self.ticker_map[symbol] = ticker.id
                else:
                    # Create ticker if not exists
                    ticker = Ticker(symbol=symbol, active=True)
                    session.add(ticker)
                    await session.commit()
                    self.ticker_map[symbol] = ticker.id
                    
            except Exception as e:
                logger.error(f"Error loading ticker_id for {symbol}: {e}")
            finally:
                await session.close()
                break
    
    async def _update_redis_candle(self, key: str, candle: Dict[str, Any]):
        """Store candle in Redis."""
        try:
            # Convert Decimal to float for JSON serialization
            candle_data = {
                **candle,
                'open': float(candle['open']) if candle['open'] is not None else 0.0,
                'high': float(candle['high']),
                'low': float(candle['low']),
                'close': float(candle['close']),
                'timestamp': candle['timestamp'].isoformat()
            }
            
            # Store with TTL
            await self.redis_client.setex(
                f"candle:{key}",
                self.redis_ttl,
                json.dumps(candle_data)
            )
            
        except Exception as e:
            logger.error(f"Error updating Redis candle {key}: {e}")
    
    async def _publish_candle_update(self, candle: Dict[str, Any]):
        """Publish candle update via Redis pub/sub."""
        try:
            # Create update message
            update = {
                'type': 'candle_update',
                'symbol': candle['symbol'],
                'timestamp': candle['timestamp'].isoformat(),
                'data': {
                    'open': float(candle['open']) if candle['open'] is not None else 0.0,
                    'high': float(candle['high']),
                    'low': float(candle['low']),
                    'close': float(candle['close']),
                    'volume': candle['volume'],
                    'trade_count': candle.get('trade_count', 0),
                    'complete': candle.get('complete', False)
                }
            }
            
            # Publish to symbol-specific channel
            await self.redis_client.publish(
                f"candles:{candle['symbol']}",
                json.dumps(update)
            )
            
            # Also publish to general channel
            await self.redis_client.publish(
                "candles:all",
                json.dumps(update)
            )
            
        except Exception as e:
            logger.error(f"Error publishing candle update: {e}")
    
    async def _flush_candles_periodically(self):
        """Background task to flush completed candles to database."""
        logger.info("Started candle flush task")
        
        while self._running:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                
                # Get current time
                now = datetime.now(timezone.utc)
                cutoff_time = now.replace(second=0, microsecond=0)
                
                # Find completed candles (older than current minute)
                completed_keys = []
                
                for key, candle in self.current_candles.items():
                    if candle['timestamp'] < cutoff_time:
                        completed_keys.append(key)
                
                # Flush completed candles
                if completed_keys:
                    logger.debug(f"Flushing {len(completed_keys)} completed candles")
                    
                    for key in completed_keys:
                        candle = self.current_candles.pop(key, None)
                        if candle:
                            candle['complete'] = True
                            await self._save_candle_to_db(candle)
                            await self._publish_candle_update(candle)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in flush task: {e}")
    
    async def _save_candle_to_db(self, candle_data: Dict[str, Any]):
        """Save completed candle to PostgreSQL."""
        if not candle_data.get('ticker_id'):
            logger.warning(f"No ticker_id for {candle_data.get('symbol')}")
            return
        
        # Skip if no valid price data
        if (candle_data['open'] is None or 
            candle_data['high'] == 0 or 
            candle_data['low'] == Decimal('999999999')):
            logger.debug(f"Skipping empty candle for {candle_data.get('symbol')}")
            return
        
        async for session in get_async_db():
            try:
                # Check if candle already exists
                existing = await session.execute(
                    select(Candle).where(
                        Candle.ticker_id == candle_data['ticker_id'],
                        Candle.timestamp == candle_data['timestamp']
                    )
                )
                
                if existing.scalar_one_or_none():
                    logger.debug(f"Candle already exists: {candle_data['symbol']} @ {candle_data['timestamp']}")
                    return
                
                # Create new candle
                candle = Candle(
                    ticker_id=candle_data['ticker_id'],
                    timestamp=candle_data['timestamp'],
                    open=candle_data['open'],
                    high=candle_data['high'],
                    low=candle_data['low'],
                    close=candle_data['close'],
                    volume=candle_data['volume']
                )
                
                session.add(candle)
                await session.commit()
                
                logger.debug(f"Saved candle: {candle_data['symbol']} @ {candle_data['timestamp']}")
                
            except Exception as e:
                logger.error(f"Error saving candle to DB: {e}")
                await session.rollback()
            finally:
                await session.close()
                break
    
    async def flush_all_candles(self):
        """Flush all current candles to database."""
        logger.info(f"Flushing {len(self.current_candles)} candles")
        
        for candle in self.current_candles.values():
            candle['complete'] = True
            await self._save_candle_to_db(candle)
            await self._publish_candle_update(candle)
        
        self.current_candles.clear()
    
    async def get_current_candles(self) -> List[Dict[str, Any]]:
        """Get all current in-progress candles."""
        candles = []
        
        for candle in self.current_candles.values():
            candles.append({
                'symbol': candle['symbol'],
                'timestamp': candle['timestamp'].isoformat(),
                'open': float(candle['open']) if candle['open'] is not None else 0.0,
                'high': float(candle['high']),
                'low': float(candle['low']),
                'close': float(candle['close']),
                'volume': candle['volume'],
                'trade_count': candle.get('trade_count', 0),
                'complete': candle.get('complete', False)
            })
        
        return candles


class StreamProcessor:
    """
    Main processor for handling streaming data.
    
    Coordinates between streaming client and candle aggregator.
    """
    
    def __init__(self):
        """Initialize the stream processor."""
        self.aggregator = CandleAggregator()
        self.processed_count = 0
        self.error_count = 0
        self.last_processed = None
    
    async def initialize(self):
        """Initialize the processor."""
        await self.aggregator.initialize()
        logger.info("Stream processor initialized")
    
    async def shutdown(self):
        """Shutdown the processor."""
        await self.aggregator.shutdown()
        logger.info("Stream processor shut down")
    
    async def process_quote(self, quote: Dict[str, Any]):
        """Process a quote from streaming client."""
        try:
            await self.aggregator.process_quote(quote)
            self.processed_count += 1
            self.last_processed = datetime.now()
            
        except Exception as e:
            logger.error(f"Error processing quote: {e}")
            self.error_count += 1
    
    async def process_chart(self, chart: Dict[str, Any]):
        """Process chart data from streaming client."""
        try:
            await self.aggregator.process_chart_data(chart)
            self.processed_count += 1
            self.last_processed = datetime.now()
            
        except Exception as e:
            logger.error(f"Error processing chart: {e}")
            self.error_count += 1
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics."""
        return {
            'processed_count': self.processed_count,
            'error_count': self.error_count,
            'last_processed': self.last_processed.isoformat() if self.last_processed else None,
            'current_candles': len(self.aggregator.current_candles),
            'symbols': list(set(c['symbol'] for c in self.aggregator.current_candles.values()))
        }