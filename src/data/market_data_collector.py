"""Market Data Collector for real-time data mining."""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import redis.asyncio as redis
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MarketDataCollector:
    """Collects and stores real-time market data."""
    
    def __init__(self, client):
        self.client = client
        self.redis_client = None
        self.collection_cache = {}
        self._init_redis()
        
    def _init_redis(self):
        """Initialize Redis connection for caching."""
        try:
            self.redis_client = redis.Redis(
                host='localhost',
                port=6379,
                db=0,
                password='schwabtrading2024!',
                decode_responses=True
            )
            logger.info("Redis connected for data mining cache")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
    
    async def collect_quote(self, symbol: str) -> Dict[str, Any]:
        """Collect real-time quote data for a symbol."""
        try:
            response = self.client.get_quote(symbol)
            
            if response.status_code == 200:
                quote_data = response.json()
                
                # Process and store the data
                processed_data = self._process_quote_data(symbol, quote_data)
                
                # Store in Redis cache
                await self._store_in_cache(symbol, processed_data)
                
                # Store in local cache
                self.collection_cache[symbol] = processed_data
                
                return processed_data
            else:
                logger.error(f"Failed to get quote for {symbol}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error collecting quote for {symbol}: {e}")
            return None
    
    def _process_quote_data(self, symbol: str, raw_data: Dict) -> Dict[str, Any]:
        """Process raw quote data into structured format."""
        try:
            quote = raw_data.get(symbol, {}).get('quote', raw_data.get(symbol, {}))
            
            processed = {
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "price": {
                    "bid": quote.get('bidPrice', 0),
                    "ask": quote.get('askPrice', 0),
                    "last": quote.get('lastPrice', 0),
                    "open": quote.get('openPrice', 0),
                    "high": quote.get('highPrice', 0),
                    "low": quote.get('lowPrice', 0),
                    "close": quote.get('closePrice', 0),
                    "prev_close": quote.get('regularMarketPreviousClose', 0)
                },
                "volume": {
                    "current": quote.get('totalVolume', 0),
                    "avg_10d": quote.get('10DayAverageDailyVolume', 0),
                    "bid_size": quote.get('bidSize', 0),
                    "ask_size": quote.get('askSize', 0)
                },
                "change": {
                    "amount": quote.get('netChange', 0),
                    "percent": quote.get('netPercentChangeInDouble', 0),
                    "52w_high": quote.get('52WkHigh', 0),
                    "52w_low": quote.get('52WkLow', 0)
                },
                "market": {
                    "is_open": not quote.get('delayed', False),
                    "exchange": quote.get('exchangeName', ''),
                    "market_cap": quote.get('marketCap', 0)
                }
            }
            
            return processed
            
        except Exception as e:
            logger.error(f"Error processing quote data: {e}")
            return {
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    async def _store_in_cache(self, symbol: str, data: Dict):
        """Store collected data in Redis cache."""
        if not self.redis_client:
            return
            
        try:
            # Store current quote
            quote_key = f"quote:{symbol}"
            await self.redis_client.set(
                quote_key,
                json.dumps(data),
                ex=300  # 5 minute expiry
            )
            
            # Store in time series list
            ts_key = f"timeseries:{symbol}"
            await self.redis_client.lpush(ts_key, json.dumps(data))
            
            # Trim to keep only last 1000 data points
            await self.redis_client.ltrim(ts_key, 0, 999)
            
            # Update collection stats
            stats_key = "mining:stats"
            await self.redis_client.hincrby(stats_key, "total_points", 1)
            await self.redis_client.hset(stats_key, "last_update", data["timestamp"])
            
        except Exception as e:
            logger.error(f"Error storing data in cache: {e}")
    
    async def collect_batch(self, symbols: List[str]) -> Dict[str, Any]:
        """Collect quotes for multiple symbols in batch."""
        results = {}
        
        # Create tasks for parallel collection
        tasks = [self.collect_quote(symbol) for symbol in symbols]
        
        # Execute all tasks concurrently
        collected_data = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for symbol, data in zip(symbols, collected_data):
            if isinstance(data, Exception):
                logger.error(f"Failed to collect {symbol}: {data}")
                results[symbol] = {"error": str(data)}
            else:
                results[symbol] = data
        
        return results
    
    async def get_cached_data(self, symbol: str) -> Optional[Dict]:
        """Get cached data for a symbol."""
        if not self.redis_client:
            return self.collection_cache.get(symbol)
            
        try:
            quote_key = f"quote:{symbol}"
            cached = await self.redis_client.get(quote_key)
            
            if cached:
                return json.loads(cached)
            else:
                return self.collection_cache.get(symbol)
                
        except Exception as e:
            logger.error(f"Error getting cached data: {e}")
            return self.collection_cache.get(symbol)
    
    async def get_time_series(self, symbol: str, limit: int = 100) -> List[Dict]:
        """Get time series data for a symbol."""
        if not self.redis_client:
            return []
            
        try:
            ts_key = f"timeseries:{symbol}"
            data_list = await self.redis_client.lrange(ts_key, 0, limit - 1)
            
            return [json.loads(data) for data in data_list]
            
        except Exception as e:
            logger.error(f"Error getting time series data: {e}")
            return []
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get overall collection statistics."""
        stats = {
            "cache_size": len(self.collection_cache),
            "symbols_tracked": list(self.collection_cache.keys())
        }
        
        if self.redis_client:
            try:
                stats_key = "mining:stats"
                redis_stats = await self.redis_client.hgetall(stats_key)
                stats.update(redis_stats)
            except Exception as e:
                logger.error(f"Error getting stats from Redis: {e}")
        
        return stats