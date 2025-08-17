"""
Real-time quote service with Redis caching and batch processing.

This service provides efficient quote fetching with caching, batch operations,
history tracking, and spread calculations for the Schwab trading system.
"""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any, Tuple, Union
from collections import deque
import logging

import redis.asyncio as redis
from redis.asyncio.client import Redis
from redis.exceptions import RedisError

from ..broker import SchwabBroker, get_schwab_broker
from ..broker.exceptions import MarketDataError, BrokerError
from ..config.settings import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Quote:
    """Represents a real-time stock quote."""
    
    symbol: str
    bid_price: float
    ask_price: float
    last_price: float
    bid_size: int
    ask_size: int
    last_size: int
    volume: int
    timestamp: datetime
    
    # Calculated fields
    spread: float = field(init=False)
    spread_percentage: float = field(init=False)
    mid_price: float = field(init=False)
    
    # Additional market data
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    close_price: Optional[float] = None
    previous_close: Optional[float] = None
    
    # Change tracking
    change: Optional[float] = None
    change_percentage: Optional[float] = None
    
    # Extended data
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    exchange: Optional[str] = None
    quote_time: Optional[datetime] = None
    trade_time: Optional[datetime] = None
    
    def __post_init__(self):
        """Calculate derived fields after initialization."""
        self.spread = self.ask_price - self.bid_price
        self.spread_percentage = (self.spread / self.ask_price * 100) if self.ask_price > 0 else 0
        self.mid_price = (self.bid_price + self.ask_price) / 2
        
        # Calculate change if previous close is available
        if self.previous_close and self.previous_close > 0:
            self.change = self.last_price - self.previous_close
            self.change_percentage = (self.change / self.previous_close) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert quote to dictionary."""
        data = asdict(self)
        # Convert datetime objects to ISO format
        data['timestamp'] = self.timestamp.isoformat()
        if self.quote_time:
            data['quote_time'] = self.quote_time.isoformat()
        if self.trade_time:
            data['trade_time'] = self.trade_time.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Quote':
        """Create Quote from dictionary."""
        # Convert ISO strings back to datetime objects
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if isinstance(data.get('quote_time'), str):
            data['quote_time'] = datetime.fromisoformat(data['quote_time'])
        if isinstance(data.get('trade_time'), str):
            data['trade_time'] = datetime.fromisoformat(data['trade_time'])
        
        # Remove calculated fields to let __post_init__ recalculate them
        data.pop('spread', None)
        data.pop('spread_percentage', None)
        data.pop('mid_price', None)
        
        return cls(**data)
    
    @classmethod
    def from_schwab_quote(cls, symbol: str, data: Dict[str, Any]) -> 'Quote':
        """Create Quote from Schwab API response."""
        quote_data = data.get('quote', {})
        
        return cls(
            symbol=symbol,
            bid_price=quote_data.get('bidPrice', 0.0),
            ask_price=quote_data.get('askPrice', 0.0),
            last_price=quote_data.get('lastPrice', 0.0),
            bid_size=quote_data.get('bidSize', 0),
            ask_size=quote_data.get('askSize', 0),
            last_size=quote_data.get('lastSize', 0),
            volume=quote_data.get('totalVolume', 0),
            timestamp=datetime.now(timezone.utc),
            
            # Additional fields
            open_price=quote_data.get('openPrice'),
            high_price=quote_data.get('highPrice'),
            low_price=quote_data.get('lowPrice'),
            close_price=quote_data.get('closePrice'),
            previous_close=quote_data.get('closePrice'),  # Previous day's close
            
            # Extended data
            fifty_two_week_high=quote_data.get('52WeekHigh'),
            fifty_two_week_low=quote_data.get('52WeekLow'),
            exchange=quote_data.get('exchangeName'),
            quote_time=cls._parse_timestamp(quote_data.get('quoteTime')),
            trade_time=cls._parse_timestamp(quote_data.get('tradeTime'))
        )
    
    @staticmethod
    def _parse_timestamp(timestamp_ms: Optional[int]) -> Optional[datetime]:
        """Parse timestamp from milliseconds."""
        if timestamp_ms:
            return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        return None


@dataclass
class QuoteHistory:
    """Tracks quote history for a symbol."""
    
    symbol: str
    max_history: int = 1000
    quotes: deque = field(default_factory=deque)
    
    def add_quote(self, quote: Quote):
        """Add a quote to history."""
        self.quotes.append(quote)
        if len(self.quotes) > self.max_history:
            self.quotes.popleft()
    
    def get_latest(self, n: int = 1) -> List[Quote]:
        """Get the latest n quotes."""
        return list(self.quotes)[-n:]
    
    def get_price_range(self, minutes: int = 5) -> Tuple[float, float]:
        """Get min and max prices over the last n minutes."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        recent_quotes = [q for q in self.quotes if q.timestamp >= cutoff]
        
        if not recent_quotes:
            return 0.0, 0.0
        
        prices = [q.last_price for q in recent_quotes]
        return min(prices), max(prices)
    
    def get_volume_total(self, minutes: int = 5) -> int:
        """Get total volume over the last n minutes."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        recent_quotes = [q for q in self.quotes if q.timestamp >= cutoff]
        
        if not recent_quotes:
            return 0
        
        # Since volume is cumulative, return the difference
        return recent_quotes[-1].volume - recent_quotes[0].volume


class QuoteService:
    """
    Real-time quote service with Redis caching and batch processing.
    
    Features:
    - Real-time quote fetching from Schwab API
    - Redis caching with configurable TTL
    - Batch quote requests for efficiency
    - Quote history tracking
    - Spread calculation and analysis
    - Pub/sub for real-time updates
    """
    
    def __init__(
        self,
        broker: Optional[SchwabBroker] = None,
        redis_client: Optional[Redis] = None,
        cache_ttl: int = 5,  # seconds
        history_enabled: bool = True,
        max_batch_size: int = 100
    ):
        """
        Initialize quote service.
        
        Args:
            broker: Schwab broker instance
            redis_client: Redis client instance
            cache_ttl: Cache time-to-live in seconds
            history_enabled: Whether to track quote history
            max_batch_size: Maximum symbols per batch request
        """
        self.broker = broker
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl
        self.history_enabled = history_enabled
        self.max_batch_size = max_batch_size
        
        # Quote history tracking
        self._quote_history: Dict[str, QuoteHistory] = {}
        
        # Batch request optimization
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._batch_lock = asyncio.Lock()
        self._batch_task: Optional[asyncio.Task] = None
        
        # Redis keys
        self.QUOTE_KEY_PREFIX = "quote:"
        self.HISTORY_KEY_PREFIX = "quote_history:"
        self.PUBSUB_CHANNEL = "quote_updates"
        
        self._initialized = False
    
    async def initialize(self):
        """Initialize the quote service."""
        if self._initialized:
            return
        
        # Initialize broker if not provided
        if not self.broker:
            self.broker = await get_schwab_broker()
        
        # Initialize Redis if not provided
        if not self.redis_client:
            settings = get_settings()
            self.redis_client = await redis.from_url(
                settings.database.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        
        # Test Redis connection
        try:
            await self.redis_client.ping()
            logger.info("Redis connection established")
        except RedisError as e:
            logger.error(f"Redis connection failed: {e}")
            # Continue without Redis (fallback to direct API calls)
            self.redis_client = None
        
        self._initialized = True
        logger.info("Quote service initialized")
    
    async def get_quote(self, symbol: str, use_cache: bool = True) -> Optional[Quote]:
        """
        Get a single quote with caching.
        
        Args:
            symbol: Stock symbol
            use_cache: Whether to use cached data
            
        Returns:
            Quote object or None if not found
        """
        symbol = symbol.upper()
        
        # Check cache first
        if use_cache and self.redis_client:
            cached_quote = await self._get_cached_quote(symbol)
            if cached_quote:
                logger.debug(f"Cache hit for {symbol}")
                return cached_quote
        
        # Fetch from API
        try:
            quotes = await self.broker.get_quotes([symbol])
            if symbol in quotes:
                quote = Quote.from_schwab_quote(symbol, quotes[symbol])
                
                # Cache the quote
                if self.redis_client:
                    await self._cache_quote(quote)
                
                # Track history
                if self.history_enabled:
                    self._add_to_history(quote)
                
                # Publish update
                if self.redis_client:
                    await self._publish_quote_update(quote)
                
                return quote
            
        except (MarketDataError, BrokerError) as e:
            logger.error(f"Failed to fetch quote for {symbol}: {e}")
            
        return None
    
    async def get_quotes_batch(
        self,
        symbols: List[str],
        use_cache: bool = True
    ) -> Dict[str, Quote]:
        """
        Get multiple quotes efficiently with batching.
        
        Args:
            symbols: List of stock symbols
            use_cache: Whether to use cached data
            
        Returns:
            Dictionary mapping symbols to Quote objects
        """
        symbols = [s.upper() for s in symbols]
        quotes: Dict[str, Quote] = {}
        symbols_to_fetch = []
        
        # Check cache for each symbol
        if use_cache and self.redis_client:
            for symbol in symbols:
                cached_quote = await self._get_cached_quote(symbol)
                if cached_quote:
                    quotes[symbol] = cached_quote
                    logger.debug(f"Cache hit for {symbol}")
                else:
                    symbols_to_fetch.append(symbol)
        else:
            symbols_to_fetch = symbols
        
        # Fetch missing quotes in batches
        if symbols_to_fetch:
            for i in range(0, len(symbols_to_fetch), self.max_batch_size):
                batch = symbols_to_fetch[i:i + self.max_batch_size]
                
                try:
                    api_quotes = await self.broker.get_quotes(batch)
                    
                    for symbol, data in api_quotes.items():
                        quote = Quote.from_schwab_quote(symbol, data)
                        quotes[symbol] = quote
                        
                        # Cache the quote
                        if self.redis_client:
                            await self._cache_quote(quote)
                        
                        # Track history
                        if self.history_enabled:
                            self._add_to_history(quote)
                    
                    # Publish batch update
                    if self.redis_client and quotes:
                        await self._publish_batch_update(list(quotes.values()))
                    
                except (MarketDataError, BrokerError) as e:
                    logger.error(f"Failed to fetch batch quotes: {e}")
        
        return quotes
    
    async def get_quote_with_history(
        self,
        symbol: str,
        history_count: int = 10
    ) -> Tuple[Optional[Quote], List[Quote]]:
        """
        Get current quote with recent history.
        
        Args:
            symbol: Stock symbol
            history_count: Number of historical quotes to return
            
        Returns:
            Tuple of (current_quote, historical_quotes)
        """
        symbol = symbol.upper()
        
        # Get current quote
        current_quote = await self.get_quote(symbol)
        
        # Get history
        history = []
        if self.history_enabled and symbol in self._quote_history:
            history = self._quote_history[symbol].get_latest(history_count)
        
        return current_quote, history
    
    def calculate_spread_stats(
        self,
        quotes: Union[Quote, List[Quote]]
    ) -> Dict[str, float]:
        """
        Calculate spread statistics for quotes.
        
        Args:
            quotes: Single quote or list of quotes
            
        Returns:
            Dictionary with spread statistics
        """
        if isinstance(quotes, Quote):
            quotes = [quotes]
        
        if not quotes:
            return {
                'avg_spread': 0.0,
                'avg_spread_pct': 0.0,
                'min_spread': 0.0,
                'max_spread': 0.0,
                'total_spread_cost': 0.0
            }
        
        spreads = [q.spread for q in quotes]
        spread_pcts = [q.spread_percentage for q in quotes]
        
        return {
            'avg_spread': sum(spreads) / len(spreads),
            'avg_spread_pct': sum(spread_pcts) / len(spread_pcts),
            'min_spread': min(spreads),
            'max_spread': max(spreads),
            'total_spread_cost': sum(spreads)  # Total cost if trading 1 share each
        }
    
    def get_quote_metrics(self, symbol: str, minutes: int = 5) -> Dict[str, Any]:
        """
        Get comprehensive quote metrics for a symbol.
        
        Args:
            symbol: Stock symbol
            minutes: Time window for metrics
            
        Returns:
            Dictionary with various metrics
        """
        symbol = symbol.upper()
        
        if symbol not in self._quote_history:
            return {
                'price_range': (0.0, 0.0),
                'volume': 0,
                'quote_count': 0,
                'avg_spread': 0.0
            }
        
        history = self._quote_history[symbol]
        min_price, max_price = history.get_price_range(minutes)
        volume = history.get_volume_total(minutes)
        recent_quotes = history.get_latest(100)  # Last 100 quotes
        
        spread_stats = self.calculate_spread_stats(recent_quotes) if recent_quotes else {}
        
        return {
            'price_range': (min_price, max_price),
            'price_volatility': max_price - min_price if max_price > 0 else 0,
            'volume': volume,
            'quote_count': len(recent_quotes),
            'avg_spread': spread_stats.get('avg_spread', 0.0),
            'avg_spread_pct': spread_stats.get('avg_spread_pct', 0.0)
        }
    
    # Redis caching methods
    
    async def _get_cached_quote(self, symbol: str) -> Optional[Quote]:
        """Get quote from Redis cache."""
        if not self.redis_client:
            return None
        
        try:
            key = f"{self.QUOTE_KEY_PREFIX}{symbol}"
            data = await self.redis_client.get(key)
            
            if data:
                quote_dict = json.loads(data)
                return Quote.from_dict(quote_dict)
                
        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"Cache read error for {symbol}: {e}")
        
        return None
    
    async def _cache_quote(self, quote: Quote):
        """Cache quote in Redis."""
        if not self.redis_client:
            return
        
        try:
            key = f"{self.QUOTE_KEY_PREFIX}{quote.symbol}"
            data = json.dumps(quote.to_dict())
            await self.redis_client.setex(key, self.cache_ttl, data)
            
        except (RedisError, json.JSONEncodeError) as e:
            logger.error(f"Cache write error for {quote.symbol}: {e}")
    
    # Quote history methods
    
    def _add_to_history(self, quote: Quote):
        """Add quote to history tracking."""
        if quote.symbol not in self._quote_history:
            self._quote_history[quote.symbol] = QuoteHistory(quote.symbol)
        
        self._quote_history[quote.symbol].add_quote(quote)
    
    # Pub/sub methods
    
    async def _publish_quote_update(self, quote: Quote):
        """Publish quote update to Redis pub/sub."""
        if not self.redis_client:
            return
        
        try:
            message = {
                'type': 'quote_update',
                'symbol': quote.symbol,
                'quote': quote.to_dict()
            }
            await self.redis_client.publish(
                self.PUBSUB_CHANNEL,
                json.dumps(message)
            )
        except RedisError as e:
            logger.error(f"Publish error for {quote.symbol}: {e}")
    
    async def _publish_batch_update(self, quotes: List[Quote]):
        """Publish batch quote update."""
        if not self.redis_client:
            return
        
        try:
            message = {
                'type': 'batch_update',
                'quotes': {q.symbol: q.to_dict() for q in quotes}
            }
            await self.redis_client.publish(
                self.PUBSUB_CHANNEL,
                json.dumps(message)
            )
        except RedisError as e:
            logger.error(f"Batch publish error: {e}")
    
    async def subscribe_to_updates(self) -> redis.client.PubSub:
        """
        Subscribe to quote updates via Redis pub/sub.
        
        Returns:
            PubSub instance for receiving updates
        """
        if not self.redis_client:
            raise RuntimeError("Redis client not available")
        
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(self.PUBSUB_CHANNEL)
        return pubsub
    
    # Cleanup
    
    async def shutdown(self):
        """Shutdown the quote service."""
        # Cancel any pending batch tasks
        if self._batch_task and not self._batch_task.done():
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass
        
        # Close Redis connection
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("Quote service shutdown complete")


# Utility functions

async def create_quote_service() -> QuoteService:
    """Create and initialize a quote service instance."""
    service = QuoteService()
    await service.initialize()
    return service